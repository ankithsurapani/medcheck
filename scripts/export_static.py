"""Export data/medcheck.db to the static JSON the web app consumes.

plan.md §2 plans a static pre-built JSON index as the API fallback. Phase 3a
ships against it directly, so there is no live API to depend on yet.

Two shapes, because 6,155 full records is far too heavy to send to a phone:

  web/public/data/search-index.json   shipped to the browser for instant search.
                                      Short keys, only the fields search needs.
  web/data/records.json               full records, read at BUILD time only to
  web/data/manufacturers.json         render static pages. Never sent to a client.

Manufacturer grouping keys off `manufacturer_id` and the `manufacturers` table
produced by Phase 2a, not off `manufacturer_raw` text. One page per resolved
company, listing every raw spelling that collapsed into it. Records whose
`manufacturer_id` is NULL — the placeholder strings CDSCO prints when the real
maker is unknown — get no manufacturer page at all, by design (plan.md §1.1).

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


def manufacturer_slug(mfr_id: int, canonical_name: str) -> str:
    """Per-resolved-entity slug: readable name plus the `manufacturers.id`.

    Phase 3a hashed the full raw string, because two spellings that differed only
    past the 60-char cutoff had to stay on separate pages — merging companies was
    Phase 2's decision to make, not a side effect of slug truncation. Phase 2a has
    now made that decision with a human in the loop, so the id carries it and the
    hash is no longer doing any work.

    The id is positional: `--apply` renumbers 1..N in canonical-name order, so
    re-running resolution after more of the review band is decided will shift
    slugs. Nothing is public yet, and the alternative — a content hash — would cost
    the direct traceability from a URL back to a row in `manufacturers`.
    """
    return f"{slugify(canonical_name, 60)}-m{mfr_id}"


def main() -> int:
    if not DB.exists():
        print(f"error: {DB} not found — run src/normalize.py first", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM nsq_records ORDER BY alert_month DESC, id")]
    mfr_rows = [dict(r) for r in conn.execute(
        "SELECT id, canonical_name, known_aliases, address_raw, state, first_seen_month, "
        "total_flags FROM manufacturers ORDER BY total_flags DESC, canonical_name")]
    # lab_type is derived from the laboratory's identity; alert_section is CDSCO's
    # own field, which contradicts it on 857 records. Both ship — the UI leads with
    # the derived value and says so where they differ (plan.md §1.1).
    LAB_TYPE_CODE = {"central": 0, "state": 1, "unknown": 2}
    print(f"read {len(rows)} records and {len(mfr_rows)} resolved manufacturers from {DB.name}")

    if not mfr_rows:
        print("error: manufacturers table is empty — run src/resolve/manufacturers.py --apply",
              file=sys.stderr)
        return 1

    PUBLIC_DATA.mkdir(parents=True, exist_ok=True)
    BUILD_DATA.mkdir(parents=True, exist_ok=True)

    # One entry per resolved company, keyed by manufacturers.id.
    manufacturers: dict[int, dict] = {}
    for m in mfr_rows:
        slug = manufacturer_slug(m["id"], m["canonical_name"] or "")
        manufacturers[m["id"]] = {
            "id": m["id"],
            "slug": slug,
            "name": m["canonical_name"],
            # Every raw spelling that collapsed into this company, shown on the
            # page. plan.md §1.1 — a merge must not quietly delete published text,
            # and the alias list is the only place a reader can check the merge.
            "aliases": json.loads(m["known_aliases"] or "[]"),
            "addressRaw": m["address_raw"],
            "state": m["state"],
            "firstSeenMonth": m["first_seen_month"],
            "recordIds": [],
            "count": 0,
        }
    slug_by_mid = {mid: m["slug"] for mid, m in manufacturers.items()}
    name_by_mid = {mid: m["name"] for mid, m in manufacturers.items()}

    records = []
    # Columnar index: parallel arrays rather than an array of objects, so the
    # field names aren't repeated 6,155 times, and a deduped manufacturer table
    # referenced by integer, since ~17% of records share a manufacturer string.
    # Measured on this corpus: 1456 KB -> 1111 KB raw, 377 KB -> 277 KB gzipped.
    # Manufacturer strings are NOT truncated — the ticket specifies substring
    # matching on the full manufacturer_raw, and truncating saved only ~11 KB.
    #
    # The raw-spelling table stays: the card and the record page must keep showing
    # the manufacturer text CDSCO actually published, and manufacturer search is
    # substring-over-raw. What changed is that each raw spelling now points at its
    # resolved company (-1 for a placeholder), so 5,107 slugs became 1,856 —
    # cheaper than before, not more expensive.
    idx_mfrs: list[str] = []
    idx_mfr_pos: dict[str, int] = {}
    idx_mfr_canon: list[int] = []          # raw index -> canonical index, or -1
    idx_canon_pos: dict[int, int] = {}     # manufacturer_id -> canonical index
    idx_canon_names: list[str] = []
    idx_canon_slugs: list[str] = []
    col_id, col_drug, col_batch, col_mfr = [], [], [], []
    col_month, col_cats, col_section, col_disputed = [], [], [], []
    col_lab_type: list[int] = []

    def canon_pos(mid) -> int:
        """Index into the client's canonical table; -1 when unresolved."""
        if mid is None:
            return -1
        if mid not in idx_canon_pos:
            idx_canon_pos[mid] = len(idx_canon_names)
            idx_canon_names.append(name_by_mid[mid] or "")
            idx_canon_slugs.append(slug_by_mid[mid])
        return idx_canon_pos[mid]

    unresolved = 0
    for r in rows:
        cats = json.loads(r["failure_category"] or "[]")
        flags = json.loads(r["parse_flags"] or "[]")
        mraw = r["manufacturer_raw"] or ""
        mid = r["manufacturer_id"]
        if mid is None:
            unresolved += 1
        mslug = slug_by_mid.get(mid)
        mcanon = name_by_mid.get(mid)

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
            "manufacturerId": mid,
            # null on both when the record's manufacturer is a placeholder. The
            # record page renders a "this is not a company" notice in place of the
            # link rather than pointing at a page that must not exist.
            "manufacturerSlug": mslug,
            "manufacturerCanonical": mcanon,
            "labelClaimDisputed": r["label_claim_disputed"],
            "failureReason": r["failure_reason_raw"],
            "failureCategories": cats,
            "testingLab": r["testing_lab"],
            "labType": r["lab_type"],
            "labName": r["lab_name_canonical"],
            "sectionDisputed": any(f.startswith("alert_section_disputed") for f in flags),
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
            idx_mfr_canon.append(canon_pos(mid))
        col_id.append(r["id"])
        col_drug.append(r["drug_name_raw"])
        col_batch.append(r["batch_number"])
        col_mfr.append(idx_mfr_pos[mraw])
        col_month.append(r["alert_month"])
        col_cats.append(cats)
        col_section.append(r["alert_section"])
        col_disputed.append(1 if r["label_claim_disputed"] == 1 else 0)
        col_lab_type.append(LAB_TYPE_CODE.get(r["lab_type"], 2))

        if mid is not None:
            m = manufacturers[mid]
            m["recordIds"].append(r["id"])
            m["count"] += 1

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
        "mfrCanon": idx_mfr_canon,
        "canonNames": idx_canon_names,
        "canonSlugs": idx_canon_slugs,
        "id": col_id,
        "drug": col_drug,
        "batch": col_batch,
        "mfr": col_mfr,
        "month": col_month,
        "categories": col_cats,
        "section": col_section,
        "labType": col_lab_type,
        "disputed": col_disputed,
    }
    write(PUBLIC_DATA / "search-index.json", index, f"search index ({len(col_id)})")
    write(BUILD_DATA / "records.json", records, f"full records ({len(records)})")
    write(BUILD_DATA / "manufacturers.json",
          sorted(manufacturers.values(), key=lambda m: -m["count"]),
          f"manufacturers ({len(manufacturers)})")

    # A manufacturer with no records would render an empty page. It should be
    # impossible — total_flags is computed from these same records — so it is
    # asserted rather than tolerated.
    empty = [m["slug"] for m in manufacturers.values() if m["count"] == 0]
    if empty:
        print(f"error: {len(empty)} manufacturers have no records, e.g. {empty[:3]}",
              file=sys.stderr)
        return 1

    # Small enough to ship; powers the browse/stats strip without a second fetch.
    months = sorted({r["alertMonth"] for r in records if r["alertMonth"]}, reverse=True)
    cat_counts: dict[str, int] = {}
    for r in records:
        for c in r["failureCategories"]:
            cat_counts[c] = cat_counts.get(c, 0) + 1
    write(PUBLIC_DATA / "meta.json", {
        "recordCount": len(records),
        "manufacturerCount": len(manufacturers),
        "rawSpellingCount": len(idx_mfrs),
        "unresolvedRecordCount": unresolved,
        "months": months,
        "monthCount": len(months),
        "latestMonth": months[0] if months else None,
        "earliestMonth": months[-1] if months else None,
        "disputedCount": sum(1 for r in records if r["labelClaimDisputed"] == 1),
        "categoryCounts": dict(sorted(cat_counts.items(), key=lambda kv: -kv[1])),
    }, "meta")

    print(f"\n{len(records)} records, {len(manufacturers)} manufacturer pages "
          f"(from {len(idx_mfrs)} raw spellings), {len(months)} months")
    print(f"{unresolved} records have no manufacturer page — placeholder text, "
          f"not a company (plan.md §1.1)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
