"""Export data/medcheck.db to the static JSON the web app consumes.

plan.md §2 plans a static pre-built JSON index as the API fallback. Phase 3a
ships against it directly, so there is no live API to depend on yet.

Two shapes, because 6,155 full records is far too heavy to send to a phone:

  web/public/data/search-index.json   shipped to the browser for instant search.
                                      Short keys, only the fields search needs.
  web/data/records.json               full records, read at BUILD time only to
  web/data/manufacturers.json         render static pages. Never sent to a client.

Run after any change to medcheck.db:

    .venv/bin/python scripts/export_static.py

Neither output is committed — both regenerate from the database, like the
database itself regenerates from data/raw/portal/.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "medcheck.db"
PUBLIC_DATA = ROOT / "web" / "public" / "data"
BUILD_DATA = ROOT / "web" / "data"


def slugify(value: str, maxlen: int = 60) -> str:
    s = unicodedata.normalize("NFKD", value or "")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s[:maxlen].strip("-") or "unknown"


def manufacturer_slug(raw: str) -> str:
    """Stable per-raw-string slug.

    Deliberately derived from the FULL raw string, hash included: two
    manufacturers whose names differ only past the slug cutoff must not collide
    into one page. Merging distinct companies is exactly the reputational harm
    plan.md §5.3 warns about — that is Phase 2's decision to make, with a human
    in the loop, not a side effect of slug truncation here.
    """
    import hashlib
    digest = hashlib.sha1((raw or "").encode("utf-8")).hexdigest()[:8]
    return f"{slugify(raw, 60)}-{digest}"


def main() -> int:
    if not DB.exists():
        print(f"error: {DB} not found — run src/normalize.py first", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM nsq_records ORDER BY alert_month DESC, id")]
    print(f"read {len(rows)} records from {DB.name}")

    PUBLIC_DATA.mkdir(parents=True, exist_ok=True)
    BUILD_DATA.mkdir(parents=True, exist_ok=True)

    records = []
    manufacturers: dict[str, dict] = {}
    # Columnar index: parallel arrays rather than an array of objects, so the
    # field names aren't repeated 6,155 times, and a deduped manufacturer table
    # referenced by integer, since ~17% of records share a manufacturer string.
    # Measured on this corpus: 1456 KB -> 1111 KB raw, 377 KB -> 277 KB gzipped.
    # Manufacturer strings are NOT truncated — the ticket specifies substring
    # matching on the full manufacturer_raw, and truncating saved only ~11 KB.
    idx_mfrs: list[str] = []
    idx_mfr_pos: dict[str, int] = {}
    col_id, col_drug, col_batch, col_mfr = [], [], [], []
    col_month, col_cats, col_section, col_disputed = [], [], [], []

    for r in rows:
        cats = json.loads(r["failure_category"] or "[]")
        flags = json.loads(r["parse_flags"] or "[]")
        mraw = r["manufacturer_raw"] or ""
        mslug = manufacturer_slug(mraw)

        rec = {
            "id": r["id"],
            "alertMonth": r["alert_month"],
            "alertSection": r["alert_section"],
            "drugName": r["drug_name_raw"],
            "dosageForm": r["dosage_form"],
            "batchNumber": r["batch_number"],
            "mfgDate": r["mfg_date"],
            "expiryDate": r["expiry_date"],
            "manufacturer": mraw,
            "manufacturerSlug": mslug,
            "labelClaimDisputed": r["label_claim_disputed"],
            "failureReason": r["failure_reason_raw"],
            "failureCategories": cats,
            "testingLab": r["testing_lab"],
            "state": r["state"],
            "sourceUrl": r["source_url"],
            "sourceType": r["source_type"],
            "parseConfidence": r["parse_confidence"],
            "parseFlags": flags,
        }
        records.append(rec)

        if mraw not in idx_mfr_pos:
            idx_mfr_pos[mraw] = len(idx_mfrs)
            idx_mfrs.append(mraw)
        col_id.append(r["id"])
        col_drug.append(r["drug_name_raw"])
        col_batch.append(r["batch_number"])
        col_mfr.append(idx_mfr_pos[mraw])
        col_month.append(r["alert_month"])
        col_cats.append(cats)
        col_section.append(r["alert_section"])
        col_disputed.append(1 if r["label_claim_disputed"] == 1 else 0)

        m = manufacturers.setdefault(mslug, {
            "slug": mslug, "name": mraw, "state": r["state"], "recordIds": [], "count": 0,
        })
        m["recordIds"].append(r["id"])
        m["count"] += 1
        if not m["state"] and r["state"]:
            m["state"] = r["state"]

    # Newest first within each manufacturer page.
    by_id = {r["id"]: r for r in records}
    for m in manufacturers.values():
        m["recordIds"].sort(key=lambda i: (by_id[i]["alertMonth"] or ""), reverse=True)

    def write(path: Path, payload, label: str):
        path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        kb = path.stat().st_size / 1024
        print(f"  {label:<28} {kb:8.1f} KB  {path.relative_to(ROOT)}")

    index = {
        "manufacturers": idx_mfrs,
        "manufacturerSlugs": [manufacturer_slug(m) for m in idx_mfrs],
        "id": col_id,
        "drug": col_drug,
        "batch": col_batch,
        "mfr": col_mfr,
        "month": col_month,
        "categories": col_cats,
        "section": col_section,
        "disputed": col_disputed,
    }
    write(PUBLIC_DATA / "search-index.json", index, f"search index ({len(col_id)})")
    write(BUILD_DATA / "records.json", records, f"full records ({len(records)})")
    write(BUILD_DATA / "manufacturers.json",
          sorted(manufacturers.values(), key=lambda m: -m["count"]),
          f"manufacturers ({len(manufacturers)})")

    # Small enough to ship; powers the browse/stats strip without a second fetch.
    months = sorted({r["alertMonth"] for r in records if r["alertMonth"]}, reverse=True)
    cat_counts: dict[str, int] = {}
    for r in records:
        for c in r["failureCategories"]:
            cat_counts[c] = cat_counts.get(c, 0) + 1
    write(PUBLIC_DATA / "meta.json", {
        "recordCount": len(records),
        "manufacturerCount": len(manufacturers),
        "months": months,
        "monthCount": len(months),
        "latestMonth": months[0] if months else None,
        "earliestMonth": months[-1] if months else None,
        "disputedCount": sum(1 for r in records if r["labelClaimDisputed"] == 1),
        "categoryCounts": dict(sorted(cat_counts.items(), key=lambda kv: -kv[1])),
    }, "meta")

    print(f"\n{len(records)} records, {len(manufacturers)} manufacturer pages, {len(months)} months")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
