"""Map cached CDSCO portal JSON onto the `nsq_records` schema (plan.md §3).

Principles this module is bound by:
  §1.1  Mirror, not accuser — raw source text is always preserved alongside any
        derived value.
  §1.4  Uncertainty is displayed, not hidden — anything uncertain lowers
        parse_confidence and adds a parse_flags entry. Nothing is guessed and
        nothing is silently dropped.
  §3.3  A record can fail more than one way, so failure_category is an array,
        and an unmatched reason becomes ["other"] plus a flag — never a
        forced match.

Run:  python src/normalize.py            # normalize cache -> data/medcheck.db
      python src/normalize.py --dry-run  # report only, write nothing
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime

from ingest.cdsco_json import load_cached
from resolve.labs import classify_lab

import db
import validate

SOURCE_TYPE = "portal_json"

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}

# plan.md §3.3 controlled vocabulary. Patterns are matched against the lowercased
# failure text; a reason can match several buckets, which is the point.
#
# CDSCO's own text contains typos and line-break artifacts — "Sterillity",
# "Related Susbtances", "TEST FOR DISSOLUTI ON". Those are absorbed by the
# patterns below rather than left in "other", since the intended test is not in
# doubt. What stays in "other" is text that names no test at all ("Not
# applicable", "NSQ", "Does not conform to I.P."), where guessing would invent
# a finding the regulator did not report.
FAILURE_PATTERNS: list[tuple[str, str]] = [
    ("dissolution",             r"\bdissolutio?n\b|\bdissolutin\b|\bdissoluti\s+on\b"),
    ("disintegration",          r"\bdisintegrat"),
    ("sterility",               r"\bsterilit|\bsterillit|\bsterile\b|\bnon-?sterile\b"),
    ("microbial_contamination", r"\bmicrobial\b|\bmicrobiolog|total aerobic|\byeast|\bmould|\bmold\b"
                                r"|\be\.?\s?coli\b|staphylococ|pseudomonas|salmonella|\bfungal\b"),
    # Separate from microbial_contamination on purpose (plan.md §3.3): endotoxins
    # persist after the organisms that produced them are gone, so reporting one as
    # the other would misstate what the regulator found.
    ("bacterial_endotoxins",    r"\bendotoxin|\bbet\b|\bpyrogen"),
    ("particulate_matter",      r"particulate"),
    # "Related Susbtances" is a recurring CDSCO typo; \w* absorbs it.
    ("related_substances",      r"related\s+su\w*t\w*ces?|\bimpurit"),
    ("identification",          r"\bidentification\b|\bidentity\b"),
    ("spurious",                r"\bspurious\b|\bcounterfeit\b|\badulterat|17-?b"),
    ("description_labelling",   r"\bdescriptions?\b|\bdescriptive\b|\bmisbrand|\bmisbrand[ae]d\b"
                                r"|\blabell?ing\b|the label is|\blabel claim is\b"
                                r"|not (?:mentioned|declared|printed|specified) on the label"),
    ("ph",                      r"\bph\b|\bp\.h\.?\b"),
    # "Water-soluble substances" is excluded — that is a solubility/impurity
    # test, not a moisture limit. Loss on drying has its own bucket below.
    ("water_content",           r"\bwater\b(?!\s*-?\s*soluble)(?!\s+per\s+ml)|\bmoisture\b"),
    ("loss_on_drying",          r"loss\s+on\s+drying|\bl\.?o\.?d\.?\b(?=\s|$)"),
    ("uniformity_of_weight",    r"uniformity of (?:filled\s+)?weight"),
    ("uniformity_of_dispersion", r"uniformity of dispersion"),
    # Specific gravity, relative density and weight per ml are three names for a
    # mass-per-unit-volume measurement; which one appears depends on the monograph.
    ("density",                 r"specific\s+gravity|relative\s+density|weight\s+per\s+ml"),
    ("extractable_volume",      r"extractable\s+volume|deliverable\s+volume"
                                r"|uniformity\s+of\s+volume"),
    ("clarity_of_solution",     r"clarity\b|appearance\s+of\s+solution"
                                r"|colou?r\s+of\s+solution"),
    ("dimensions",              r"\blength\b|\bdiameter\b"),
    # "labelled amount/claim" is an assay statement, not a labelling defect, so the
    # assay pattern owns those phrases and the labelling pattern above excludes them.
    # The lookbehinds stop "water content" / "moisture content" being read as an
    # assay of the active ingredient — those belong to water_content alone.
    ("assay",                   r"\bassay\b|(?<!water )(?<!moisture )\bcontent\b"
                                r"|labell?ed (?:amount|claim)|\bpotency\b|\bstrength\b"),
]

# Used only for an exact, whole-word match against the tail of a manufacturer
# address. Anything less certain than that is left null (plan.md §1.4); real
# address parsing is Phase 2's job.
INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Chattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala",
    "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland",
    "Odisha", "Orissa", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana",
    "Tripura", "Uttar Pradesh", "Uttarakhand", "Uttaranchal", "West Bengal",
    "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli", "Daman and Diu",
    "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry", "Pondicherry",
]
STATE_ALIASES = {
    "chattisgarh": "Chhattisgarh", "orissa": "Odisha", "uttaranchal": "Uttarakhand",
    "pondicherry": "Puducherry",
}
STATE_RE = re.compile(r"\b(" + "|".join(re.escape(s) for s in
                                        sorted(INDIAN_STATES, key=len, reverse=True)) + r")\b", re.I)

# Addresses very often end in an abbreviation rather than a full state name —
# "...Baddi, Dist-Solan, H.P.-173205", "...Kasna, Greater Noida-201306 (U.P.)".
# Only abbreviations with exactly one conventional expansion are listed. A.P.
# (Andhra vs Arunachal Pradesh) and U.K. (Uttarakhand vs United Kingdom) are
# deliberately excluded — plan.md §1.4, an ambiguous read stays null.
STATE_ABBREV = {
    r"\(?\bU\.\s?P\.": "Uttar Pradesh",
    r"\(?\bH\.\s?P\.": "Himachal Pradesh",
    r"\(?\bM\.\s?P\.": "Madhya Pradesh",
    r"\(?\bT\.\s?N\.": "Tamil Nadu",
    r"\(?\bW\.\s?B\.": "West Bengal",
    r"\bJ\s?&\s?K\b": "Jammu and Kashmir",
    r"\bNCT of Delhi\b|\bNew Delhi\b": "Delhi",
}
STATE_ABBREV_RE = [(re.compile(p, re.I), s) for p, s in STATE_ABBREV.items()]

# Spurious records name no real manufacturer — CDSCO prints a placeholder because
# the drug is a counterfeit and the true maker is unknown. Treating that string as
# a company name would be a §1.1 violation, so it is flagged and never resolved.
UNKNOWN_MANUFACTURER_RE = re.compile(r"^\s*(under investigation|not known|unknown|n\.?a\.?)\s*$", re.I)

DISPUTE_RE = re.compile(
    r"has not been manufactured by them|not manufactured by (?:them|us)|denied|denies"
    r"|is a spurious drug|purported to be (?:spurious|manufactured)|actual manufacturer",
    re.I)


def clean_text(v) -> str | None:
    """Collapse whitespace and repair the portal's mojibake.

    The portal renders typographic quotes as literal '?', e.g. It fails the test
    ?Dissolution? as per IP. Those are stripped to spaces rather than guessed at,
    but the untouched original always stays in the *_raw column.
    """
    if v is None:
        return None
    s = unicodedata.normalize("NFKC", str(v))
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def norm_month(v: str | None) -> str | None:
    """'JUN-2026' / 'Jun-2026' -> '2026-06'. Returns None if unparseable."""
    if not v:
        return None
    m = re.match(r"\s*([A-Za-z]{3,})[-/\s]+(\d{4})\s*$", str(v))
    if not m:
        return None
    mon = MONTHS.get(m.group(1)[:3].lower())
    return f"{m.group(2)}-{mon:02d}" if mon else None


def norm_date(v: str | None) -> tuple[str | None, str | None]:
    """Normalize a source date to ISO. Returns (value, flag).

    The portal is consistent (Mon-YYYY) but PDF-era data is not, so the extra
    formats are handled here too rather than assumed away. Partial dates stay
    partial — 'Jun-2025' becomes '2025-06', never '2025-06-01'.
    """
    s = clean_text(v)
    if not s:
        return None, None
    if (m := norm_month(s)):
        return m, None
    if (m := re.match(r"^(\d{1,2})[/-](\d{4})$", s)):                 # 06/2025
        mm, yy = int(m.group(1)), m.group(2)
        if 1 <= mm <= 12:
            return f"{yy}-{mm:02d}", None
    if (m := re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$", s)):    # 12-09-2024 (dd-mm-yyyy)
        d, mm, yy = int(m.group(1)), int(m.group(2)), m.group(3)
        if 1 <= mm <= 12 and 1 <= d <= 31:
            return f"{yy}-{mm:02d}-{d:02d}", None
    if (m := re.match(r"^(\d{4})-(\d{2})(?:-(\d{2}))?", s)):          # already ISO
        return s[:10], None
    if (m := re.match(r"^([A-Za-z]{3,})'?\s*(\d{2})$", s)):           # Feb'16
        mon = MONTHS.get(m.group(1)[:3].lower())
        if mon:
            return f"20{m.group(2)}-{mon:02d}", "date_two_digit_year_assumed_20xx"
    return None, f"date_unparsed:{s[:40]}"


def norm_section(reporting_source: str | None) -> tuple[str | None, str | None]:
    """'CDSCO lab'/'CDSCO Labs' -> central_lab; 'State lab'/'State Lab' -> state_lab.

    Case and pluralisation vary across months; 'Not applicable' occurs once.
    """
    s = (clean_text(reporting_source) or "").lower()
    if "cdsco" in s or "central" in s:
        return "central_lab", None
    if "state" in s:
        return "state_lab", None
    if not s:
        return None, "alert_section_missing"
    return None, f"alert_section_unrecognised:{s[:40]}"


CATEGORY_ORDER = [n for n, _ in FAILURE_PATTERNS] + ["other"]


def order_cats(cats) -> list[str]:
    """Stable output in §3.3's declared order."""
    return sorted(set(cats), key=CATEGORY_ORDER.index)


def categorise(reason: str | None) -> tuple[list[str], str | None]:
    """Map free-text failure reason -> list of §3.3 buckets. Never forces a match."""
    s = (clean_text(reason) or "").lower()
    if not s:
        return ["other"], "failure_reason_empty"
    cats = [name for name, pat in FAILURE_PATTERNS if re.search(pat, s)]
    if not cats:
        return ["other"], f"failure_category_unmapped:{s[:60]}"
    return order_cats(cats), None


def derive_state(address: str | None, explicit: str | None = None) -> tuple[str | None, str | None]:
    """State from an explicit field if present, else an exact state-name match in
    the address. Ambiguity (two different states named) yields null + a flag."""
    if (e := clean_text(explicit)):
        return STATE_ALIASES.get(e.lower(), e), None
    s = clean_text(address)
    if not s:
        return None, "state_not_derived:no_address"
    if UNKNOWN_MANUFACTURER_RE.match(s):
        return None, "state_not_derived:manufacturer_unknown"

    canon = set()
    for h in STATE_RE.findall(s):
        full = next((st for st in INDIAN_STATES if st.lower() == h.lower()), h)
        canon.add(STATE_ALIASES.get(full.lower(), full))
    for rx, state in STATE_ABBREV_RE:
        if rx.search(s):
            canon.add(state)

    if len(canon) == 1:
        return canon.pop(), None
    if len(canon) > 1:
        return None, f"state_ambiguous:{'/'.join(sorted(canon))}"
    return None, "state_not_derived:no_match"


def derive_lab(testing_lab: str | None, alert_section: str | None) -> tuple[str, str | None, str | None]:
    """Lab type from the laboratory's identity. Returns (type, canonical, flag).

    CDSCO's own reporting-source field contradicts itself — the same laboratory is
    filed as "CDSCO lab" in one record and "State lab" in the next, on 857 records.
    The lab's identity is stable where the label is not, so type is derived from
    which lab it is (src/resolve/labs.py).

    `alert_section` is NOT corrected from this. §1.1 — MedCheck mirrors what the
    regulator published; overwriting the field would hide the fact that CDSCO's own
    two publications disagree, which is itself a finding. Where the derived type
    contradicts the published section, both are kept and a flag records it (§1.4).
    """
    lab_type, canonical, basis = classify_lab(testing_lab)
    flag = None
    if lab_type in ("central", "state") and alert_section in ("central_lab", "state_lab"):
        published = "central" if alert_section == "central_lab" else "state"
        if published != lab_type:
            flag = f"alert_section_disputed:published_{published}_lab_but_{basis}"
    elif lab_type == "unknown" and testing_lab:
        flag = f"lab_type_underived:{(testing_lab or '')[:40]}"
    return lab_type, canonical, flag


def clean_drug_name(raw: str | None) -> str | None:
    """Light normalization for search only. Raw is always kept in drug_name_raw."""
    s = clean_text(raw)
    if not s:
        return None
    s = re.sub(r"[‘’“”]", "", s)
    s = re.sub(r"\s*[\(\[]\s*$", "", s)
    return s.lower().strip(" .,-") or None


def make_id(alert_month: str | None, batch: str | None, drug: str | None,
            manufacturer: str | None, lab: str | None, reason: str | None) -> str:
    """Deterministic id for a portal NSQ record (see docs/methodology.md).

    The NSQ endpoint exposes no stable key, so the id is a hash over the fields
    that together identify a tested sample. plan.md §5.4 — batch numbers are not
    unique across manufacturers — is why manufacturer is in the key and why
    batch alone never is.
    """
    parts = [(alert_month or ""), (batch or ""), (drug or ""), (manufacturer or ""),
             (lab or ""), (reason or "")]
    basis = "|".join(re.sub(r"\s+", " ", p.strip().lower()) for p in parts)
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:12]
    return f"NSQ_{alert_month or 'unknown'}_{digest}"


def _base_record(source_url: str) -> dict:
    return {
        "active_ingredients": None,   # Phase 2+
        "dosage_form": None,
        "manufacturer_id": None,      # Phase 2 — entity resolution
        "source_url": source_url,
        "source_type": SOURCE_TYPE,
        "source_page": None,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def normalize_nsq_row(row: dict, source_url: str) -> dict:
    flags: list[str] = []

    def flag(f):
        if f:
            flags.append(f)

    alert_month = norm_month(row.get("dt_reporting_month_year"))
    if not alert_month:
        flag(f"alert_month_unparsed:{row.get('dt_reporting_month_year')}")

    section, f = norm_section(row.get("str_reporting_source"));      flag(f)
    mfg, f = norm_date(row.get("dt_manufacturing_date"));            flag(f)
    exp, f = norm_date(row.get("dt_expiry_date"));                   flag(f)
    cats, f = categorise(row.get("str_nsq_result"));                 flag(f)
    manufacturer_raw = clean_text(row.get("str_manufactured_by"))
    if manufacturer_raw and UNKNOWN_MANUFACTURER_RE.match(manufacturer_raw):
        flag(f"manufacturer_unknown_placeholder:{manufacturer_raw}")
    state, f = derive_state(manufacturer_raw);                       flag(f)
    testing_lab = clean_text(row.get("str_reported_by_lab_or_state"))
    lab_type, lab_canonical, f = derive_lab(testing_lab, section);   flag(f)

    rec = _base_record(source_url)
    rec.update({
        "alert_month": alert_month,
        "alert_section": section,
        "drug_name_raw": clean_text(row.get("str_product_name")),
        "drug_name_clean": clean_drug_name(row.get("str_product_name")),
        "batch_number": clean_text(row.get("str_batch_no")),
        "mfg_date": mfg,
        "expiry_date": exp,
        "manufacturer_raw": manufacturer_raw,
        "label_claim_disputed": None,   # NSQ endpoint carries no dispute field
        "failure_reason_raw": clean_text(row.get("str_nsq_result")),
        "failure_category": json.dumps(cats),
        "testing_lab": testing_lab,
        "lab_type": lab_type,
        "lab_name_canonical": lab_canonical,
        "state": state,
    })
    rec["id"] = make_id(alert_month, rec["batch_number"], rec["drug_name_raw"],
                        rec["manufacturer_raw"], rec["testing_lab"], rec["failure_reason_raw"])
    rec["_flags"] = flags
    return rec


def normalize_spurious_row(row: dict, source_url: str) -> dict:
    """The spurious endpoint is a richer record: it has a stable num_id, an
    explicit manufacturing state, dosage form, and — critically — str_firm_reply
    and str_nsq_remarks, which are the source for label_claim_disputed
    (plan.md §1.1, §5.5)."""
    flags: list[str] = []

    def flag(f):
        if f:
            flags.append(f)

    alert_month = norm_month(row.get("dt_reporting_month_year"))
    if not alert_month:
        flag(f"alert_month_unparsed:{row.get('dt_reporting_month_year')}")

    mfg, f = norm_date(row.get("dt_manufacturing_date"));   flag(f)
    exp, f = norm_date(row.get("dt_expiry_date"));          flag(f)
    manufacturer_raw = clean_text(row.get("str_manufactured_by"))
    if manufacturer_raw and UNKNOWN_MANUFACTURER_RE.match(manufacturer_raw):
        flag(f"manufacturer_unknown_placeholder:{manufacturer_raw}")
    state, f = derive_state(manufacturer_raw, row.get("str_manufacturing_state")); flag(f)

    reason = clean_text(row.get("str_nsq_result"))
    cats, f = categorise(reason); flag(f)
    # These records come from the spurious endpoint, so the category is known
    # regardless of what the free-text reason says. "other" is dropped once a
    # real bucket applies — the unmapped flag still records that the reason text
    # itself didn't match anything.
    cats = order_cats([c for c in cats if c != "other"] + ["spurious"])

    firm_reply = clean_text(row.get("str_firm_reply"))
    remarks = clean_text(row.get("str_nsq_remarks"))
    disputed = bool(DISPUTE_RE.search(f"{firm_reply or ''} {remarks or ''}")) or None
    if disputed is None and not (firm_reply or remarks):
        flag("dispute_status_unknown:no_firm_reply_or_remarks")

    # The firm's own reply and CDSCO's remarks are kept verbatim on the record.
    # §1.1: displaying a dispute wrongly would defame a legitimate company, so the
    # exact published wording travels with the flag rather than just a boolean.
    reason_parts = [p for p in [reason,
                                f"[Firm's reply] {firm_reply}" if firm_reply else None,
                                f"[Remarks] {remarks}" if remarks else None] if p]

    testing_lab = clean_text(row.get("str_reported_by_lab_or_state"))
    # alert_section is "spurious" here, not central/state, so there is nothing for
    # the derived type to contradict — the flag from derive_lab only fires when the
    # lab itself cannot be identified.
    lab_type, lab_canonical, f = derive_lab(testing_lab, "spurious"); flag(f)

    rec = _base_record(source_url)
    rec.update({
        "alert_month": alert_month,
        "alert_section": "spurious",
        "drug_name_raw": clean_text(row.get("product_name_from_dtl")),
        "drug_name_clean": clean_drug_name(row.get("product_name_from_dtl")),
        "dosage_form": clean_text(row.get("str_dosage_form")),
        "batch_number": clean_text(row.get("str_batch_no")),
        "mfg_date": mfg,
        "expiry_date": exp,
        "manufacturer_raw": manufacturer_raw,
        "label_claim_disputed": 1 if disputed else 0,
        "failure_reason_raw": "\n".join(reason_parts) or None,
        "failure_category": json.dumps(cats),
        "testing_lab": testing_lab,
        "lab_type": lab_type,
        "lab_name_canonical": lab_canonical,
        "state": state,
    })
    # Only the current-month endpoint (viewPublicSpuriousDrugData) exposes num_id;
    # the per-month filtered endpoint does not, so most spurious records get the
    # same deterministic hash id as NSQ records. Not a defect — see
    # docs/methodology.md — so it carries an id prefix, not a parse flag.
    num_id = row.get("num_id")
    rec["id"] = (f"SPU_{num_id}" if num_id is not None
                 else "SPU_" + make_id(alert_month, rec["batch_number"], rec["drug_name_raw"],
                                       rec["manufacturer_raw"], rec["testing_lab"], reason)[4:])
    rec["_flags"] = flags
    return rec


def build_all() -> tuple[list[dict], Counter]:
    """Normalize everything in the cache. Returns (records, stats)."""
    stats: Counter = Counter()
    records: list[dict] = []

    for tab, fn in (("nsq", normalize_nsq_row), ("spurious", normalize_spurious_row)):
        for env in load_cached(tab):
            # _current.json duplicates rows already covered by a month query;
            # skipping it avoids double-counting while keeping the file cached.
            if env.get("month") is None:
                stats["skipped_current_snapshot"] += 1
                continue
            for row in env["payload"].get("aaData", []):
                records.append(fn(row, env["url"]))
                stats[f"rows_{tab}"] += 1

    # Deterministic ids can in principle collide. Detect it rather than let
    # INSERT OR REPLACE silently drop a real record (see docs/methodology.md).
    by_id: dict[str, list[dict]] = {}
    for r in records:
        by_id.setdefault(r["id"], []).append(r)

    final: list[dict] = []
    for rid, group in by_id.items():
        if len(group) == 1:
            final.append(group[0])
            continue
        # Identical source rows are true duplicates in CDSCO's own listing.
        fingerprints = {json.dumps({k: v for k, v in g.items()
                                    if k not in ("created_at", "_flags")}, sort_keys=True)
                        for g in group}
        if len(fingerprints) == 1:
            g = group[0]
            g["_flags"].append(f"duplicate_source_rows_collapsed:{len(group)}")
            stats["duplicate_rows_collapsed"] += len(group) - 1
            final.append(g)
        else:
            for i, g in enumerate(group, start=1):
                g["id"] = f"{rid}_{i}"
                g["_flags"].append(f"id_collision_disambiguated:{i}of{len(group)}")
                final.append(g)
            stats["id_collisions_disambiguated"] += len(group)

    for r in final:
        flags = r.pop("_flags")
        flags.extend(validate.check(r))
        r["parse_flags"] = json.dumps(flags)
        r["parse_confidence"] = validate.confidence(flags)
        for f in flags:
            stats[f"flag:{f.split(':')[0]}"] += 1
        stats["records"] += 1

    return final, stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    args = ap.parse_args()

    records, stats = build_all()
    print(f"normalized {len(records)} records")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")

    if args.dry_run:
        print("\n[dry run — nothing written]")
        return 0

    conn = db.connect()
    db.init(conn)
    n = db.upsert_records(conn, records)
    print(f"\nwrote {n} rows to {db.DB_PATH}")
    for k, v in db.counts(conn).items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
