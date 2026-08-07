"""Export the MedCheck dataset as CSV for reuse (plan.md §4 Phase 4).

    .venv/bin/python analysis/export_dataset.py

Writes analysis/dataset/:
    medcheck_nsq_records.csv   one row per flagged batch, with the resolved
                               manufacturer joined on
    README.md                  column-by-column description + the limitations
                               that must travel with the data
    LICENSE                    CC0 1.0 public-domain dedication

The limitations are not optional context. A CSV of "flagged medicines" separated
from its sampling caveat is a table of accusations — CDSCO does not test at random,
so nothing in here is a failure rate, and the README says that before it says
anything else. That is why README.md is regenerated here rather than hand-kept:
the data and the warning ship from the same command.
"""

from __future__ import annotations

import csv
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyse import review_pairs_pending  # noqa: E402 — reuse, don't re-hardcode

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "medcheck.db"
OUT = Path(__file__).resolve().parent / "dataset"
CSV_NAME = "medcheck_nsq_records.csv"

# (column, source, description). Order is the CSV's column order.
COLUMNS: list[tuple[str, str, str]] = [
    ("record_id", "nsq_records.id",
     "Stable MedCheck id. Deterministic hash — see docs/methodology.md §2."),
    ("alert_month", "nsq_records.alert_month",
     "Month CDSCO published the alert, ISO 'YYYY-MM'. NOT the month of testing."),
    ("alert_section", "nsq_records.alert_section",
     "central_lab | state_lab | spurious, exactly as CDSCO published it. UNRELIABLE "
     "— CDSCO files 13 laboratories under both labels, and this field contradicts "
     "the laboratory's actual identity on 857 records. Kept unchanged for fidelity; "
     "use lab_type instead."),
    ("drug_name", "nsq_records.drug_name_raw",
     "Product name exactly as CDSCO published it, including strength and brand."),
    ("dosage_form", "nsq_records.dosage_form",
     "Only the spurious-drug endpoint publishes this; empty for most records."),
    ("batch_number", "nsq_records.batch_number",
     "As published. NOT unique — different manufacturers reuse short batch numbers."),
    ("mfg_date", "nsq_records.mfg_date",
     "ISO, often month-precision only ('2025-06'). Empty where CDSCO published none."),
    ("expiry_date", "nsq_records.expiry_date", "As above."),
    ("manufacturer_raw", "nsq_records.manufacturer_raw",
     "Manufacturer name AND full postal address in one field, as published. This is "
     "the source text; nothing was corrected."),
    ("manufacturer_id", "nsq_records.manufacturer_id",
     "MedCheck's resolved company id, empty where the manufacturer field is a "
     "placeholder rather than a company. NOT a CDSCO identifier."),
    ("manufacturer_canonical", "manufacturers.canonical_name",
     "Company name after entity resolution. PARTIAL — see the limitations below."),
    ("manufacturer_state", "manufacturers.state",
     "State of the resolved company: the most common `state` across its records. "
     "A summary of the column below, and inherits its two sources."),
    ("state", "nsq_records.state",
     "Manufacturing state derived from this record's address, from two sources in "
     "strict order: a state named in the address text, else the address's PIN "
     "code. Rows sourced from a PIN carry `state_derived_from_pin:<pin>` in "
     "`parse_flags` — filter on it to keep only states CDSCO actually named. "
     "Empty where neither source answers unambiguously — never guessed."),
    ("failure_reason", "nsq_records.failure_reason_raw",
     "CDSCO's exact wording for why the batch failed, reproduced unchanged. For "
     "spurious records this also carries the firm's reply and CDSCO's remarks."),
    ("failure_categories", "nsq_records.failure_category",
     "Pipe-separated MedCheck categories (21 buckets + 'other'). MedCheck's mapping "
     "of the text above, not CDSCO's own classification. 'other' = no bucket matched."),
    ("label_claim_disputed", "nsq_records.label_claim_disputed",
     "1 = the named manufacturer told CDSCO the batch is not theirs. 0 = no dispute "
     "recorded. EMPTY = not published, which is not the same as 'not disputed' — the "
     "NSQ endpoint has no dispute field at all."),
    ("testing_lab", "nsq_records.testing_lab",
     "Laboratory that reported the result, as published."),
    ("lab_type", "nsq_records.lab_type",
     "central | state | unknown. Derived from WHICH laboratory it is, checked "
     "against CDSCO's published list of its own laboratories — not from "
     "alert_section. Prefer this over alert_section. 'unknown' (23 records) means "
     "the string names no identifiable laboratory; it is never a guess."),
    ("lab_name_canonical", "manufacturers-style canonicalisation in src/resolve/labs.py",
     "Full name of the laboratory where it could be identified as one of CDSCO's. "
     "Empty for state labs, which are not individually registered here."),
    ("source_url", "nsq_records.source_url",
     "The CDSCO page or file this row came from. Check any row against it."),
    ("source_type", "nsq_records.source_type", "portal_json | pdf"),
    ("parse_confidence", "nsq_records.parse_confidence",
     "0-1. MedCheck's own confidence in this row, not CDSCO's."),
    ("parse_flags", "nsq_records.parse_flags",
     "Pipe-separated processing flags — what was uncertain about this row and why."),
]

QUERY = """
SELECT r.id, r.alert_month, r.alert_section, r.drug_name_raw, r.dosage_form,
       r.batch_number, r.mfg_date, r.expiry_date, r.manufacturer_raw,
       r.manufacturer_id, m.canonical_name, m.state AS mfr_state, r.state,
       r.failure_reason_raw, r.failure_category, r.label_claim_disputed,
       r.testing_lab, r.lab_type, r.lab_name_canonical,
       r.source_url, r.source_type, r.parse_confidence, r.parse_flags
FROM nsq_records r
LEFT JOIN manufacturers m ON m.id = r.manufacturer_id
ORDER BY r.alert_month DESC, r.id
"""

LICENSE = """CC0 1.0 Universal (Public Domain Dedication)

To the extent possible under law, the MedCheck project has waived all copyright and
related or neighbouring rights to the MedCheck NSQ dataset
(analysis/dataset/medcheck_nsq_records.csv).

Full text: https://creativecommons.org/publicdomain/zero/1.0/legalcode

You may copy, modify, distribute and use this dataset, including for commercial
purposes, without asking permission and without attribution.

Two notes that are NOT licence conditions, because CC0 does not permit conditions,
but which matter more than most licence terms would:

1. The underlying facts are CDSCO's published record, not MedCheck's. Anyone can
   re-derive them from https://cdscoonline.gov.in — the waiver here covers the
   compilation, the categorisation and the entity resolution MedCheck added.

2. Please carry README.md with the data. It states that CDSCO does not test at
   random, so no figure computed from this file is a failure rate for medicines on
   the market. Republished without that, this dataset becomes a list of
   accusations, which is exactly what it is not.
"""


def readme(row_count: int, mfr_count: int, months: tuple[str, str],
           unresolved: int, with_state: int, state_from_pin: int,
           state_ambiguous_pin: int, pending: int) -> str:
    state_named = with_state - state_from_pin
    cols = "\n".join(
        f"| `{name}` | `{src}` | {desc} |" for name, src, desc in COLUMNS)
    return f"""# MedCheck NSQ dataset

Every medicine batch India's drug regulator (CDSCO) published as **Not of Standard
Quality** or **spurious**, from {months[0]} to {months[1]}.

- **{row_count:,} rows**, one per flagged batch
- **{mfr_count:,} resolved manufacturers**
- Licence: **CC0 1.0** — public domain, no attribution required (see `LICENSE`)
- Generated: {date.today().isoformat()} by `analysis/export_dataset.py`
- Findings computed from this data: [`../FINDINGS.md`](../FINDINGS.md)

## Read this before computing anything

**CDSCO does not test medicines at random.** Samples are drawn on suspicion, on
complaint, and on risk-based targeting. This file contains only batches that
*failed* — there is no record here of what was tested and passed, and no published
denominator anywhere in CDSCO's data.

Consequences, all of them load-bearing:

- **No percentage computed from this file is a failure rate.** "X% of flagged
  batches were antibiotics" is a fact about this file. "X% of antibiotics fail" is
  not supported by it and is not true.
- **A manufacturer appearing often may be tested often.** Frequency here reflects
  regulatory attention as much as product quality.
- **Counts rising over time may be reporting changes.** CDSCO moved from monthly
  PDFs to a data portal in August 2025, and published volume changed with it.
- **A flagged batch is not a flagged product.** One batch failing says nothing
  about other batches of the same medicine.
- **A named manufacturer is not necessarily the maker.** For spurious drugs the
  name on the label is often the company being counterfeited — see
  `label_claim_disputed`.

## Columns

| Column | Source | Notes |
|---|---|---|
{cols}

Multi-valued fields (`failure_categories`, `parse_flags`) are pipe-separated.
Empty means "CDSCO did not publish this", never zero and never "none".

## Known limitations

| Limitation | Effect |
|---|---|
| Sampling is not random | Nothing here is a population failure rate. |
| Manufacturer resolution is **partial** | {mfr_count:,} companies from 5,107 published spellings, but {pending} ambiguous pairs were left unmerged pending human review. Some companies still appear under more than one `manufacturer_id`. Concentration measured from this file is a **lower bound**. |
| `alert_section` is unreliable | CDSCO files 13 laboratories under both `central_lab` and `state_lab`, and the field contradicts the laboratory's identity on 857 rows. It is kept verbatim for fidelity. **Use `lab_type` instead** — derived from which laboratory it is, against CDSCO's published list of its own labs. |
| `state` is {with_state / row_count * 100:.0f}% populated | Derived from free-text addresses, left empty rather than guessed where ambiguous. Do not treat the populated subset as the whole picture. |
| `state` mixes two sources of different strength | {state_named:,} rows have a state CDSCO named in the address. {state_from_pin:,} have one read back from the address's PIN code, using only prefixes that are uniform across India Post's All India Pincode Directory — a well-founded inference, but an inference. Those rows carry `state_derived_from_pin:<pin>` in `parse_flags`. |
| {state_ambiguous_pin:,} rows have a PIN whose prefix spans a state boundary | Flagged `state_ambiguous_pin:<prefix>` and left empty. Eighteen of India Post's sorting districts predate the 2000 state reorganisation (247xxx is both Saharanpur, Uttar Pradesh and Roorkee, Uttarakhand), and 194xxx is refused because the source directory predates Ladakh's 2019 separation. Assigning the majority state would have filled these with a silent error rate. |
| No therapeutic classification | There is no drug-class column. `analysis/drug_classes.py` derives anti-infective groups from published WHO INN stems; that is a claim about names, not an ATC classification. |
| {unresolved} rows have no `manufacturer_id` | Their manufacturer field is a placeholder ("Under Investigation" and similar), not a company. Deliberately not resolved. |
| Pre-2019 is absent | CDSCO's portal starts at January 2019. Earlier PDF alerts exist but are not yet ingested. |
| `?` appears inside some text | CDSCO's portal mangles typographic punctuation into literal `?`. Not reversible, so it is left as published. |

## Reproducing this file

```
python src/ingest/cdsco_json.py     # fetch + cache CDSCO's portal responses
python src/normalize.py             # -> data/medcheck.db
python src/resolve/manufacturers.py --build && --apply
python analysis/export_dataset.py   # -> this file
```

Every row's `source_url` points at the CDSCO page it came from. MedCheck adds
compilation, categorisation and entity resolution; it does not add facts.
"""


def main() -> int:
    if not DB.exists():
        print(f"error: {DB} not found — run src/normalize.py first", file=sys.stderr)
        return 1
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    OUT.mkdir(parents=True, exist_ok=True)

    rows = conn.execute(QUERY).fetchall()
    months = [r["alert_month"] for r in rows if r["alert_month"]]
    span = (min(months), max(months))

    path = OUT / CSV_NAME
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([c[0] for c in COLUMNS])
        for r in rows:
            w.writerow([
                r["id"], r["alert_month"], r["alert_section"], r["drug_name_raw"],
                r["dosage_form"], r["batch_number"], r["mfg_date"], r["expiry_date"],
                r["manufacturer_raw"], r["manufacturer_id"], r["canonical_name"],
                r["mfr_state"], r["state"], r["failure_reason_raw"],
                "|".join(json.loads(r["failure_category"] or "[]")),
                "" if r["label_claim_disputed"] is None else r["label_claim_disputed"],
                r["testing_lab"], r["lab_type"], r["lab_name_canonical"],
                r["source_url"], r["source_type"],
                r["parse_confidence"],
                "|".join(json.loads(r["parse_flags"] or "[]")),
            ])

    mfr_count = conn.execute("SELECT COUNT(*) FROM manufacturers").fetchone()[0]
    unresolved = conn.execute(
        "SELECT COUNT(*) FROM nsq_records WHERE manufacturer_id IS NULL").fetchone()[0]
    with_state = conn.execute(
        "SELECT COUNT(*) FROM nsq_records WHERE state IS NOT NULL").fetchone()[0]
    state_from_pin = conn.execute(
        "SELECT COUNT(*) FROM nsq_records WHERE parse_flags LIKE "
        "'%state_derived_from_pin%'").fetchone()[0]
    state_ambiguous_pin = conn.execute(
        "SELECT COUNT(*) FROM nsq_records WHERE parse_flags LIKE "
        "'%state_ambiguous_pin%'").fetchone()[0]

    (OUT / "README.md").write_text(
        readme(len(rows), mfr_count, span, unresolved, with_state,
               state_from_pin, state_ambiguous_pin, review_pairs_pending()),
        encoding="utf-8")
    (OUT / "LICENSE").write_text(LICENSE, encoding="utf-8")

    print(f"wrote {len(rows)} rows to {path.relative_to(ROOT)} "
          f"({path.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"  {mfr_count} manufacturers joined · {unresolved} rows without one "
          f"(placeholders) · state on {with_state}")
    print(f"  {(OUT / 'README.md').relative_to(ROOT)} · {(OUT / 'LICENSE').relative_to(ROOT)} (CC0 1.0)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
