# Ingestion accuracy

Evidence that what MedCheck publishes matches what CDSCO published. Every run is
appended, never overwritten, so the numbers can be tracked over time.

---

## Run 1 — 2026-08-06 — Phase 1a, portal JSON

**Loaded:** 6,155 records, 90 alert months (Jan-2019 → Jun-2026).
6,126 from the NSQ endpoint + 46 from the spurious endpoint, minus 17 duplicate
source rows collapsed.

| Section | Records |
|---|---|
| `central_lab` | 3,029 |
| `state_lab` | 3,079 |
| `spurious` | 46 |
| flagged (≥1 parse flag) | 2,937 |
| `label_claim_disputed = 1` | 43 |

### Cross-validation against source PDFs — alert month 2025-06

The one month present in both sources at good volume. Reproduce with
`python data/raw/crossvalidate.py`; raw output in `data/raw/crossvalidate_out.txt`.

Join key is the batch number compared on alphanumerics only — the two sources
differ in punctuation (`CDL, Kolkata` in the PDF vs `CDL Kolkata` in the JSON).

**Record coverage, union across all three PDFs:**

| | |
|---|---|
| Distinct batches in the June-2025 PDFs | 188 (187 real + 1 comparator artifact, below) |
| Distinct batches in the JSON for 2025-06 | 187 |
| Present in both | 186 (+1, see spurious note) |
| **Genuinely present only in the PDF** | **1** |
| Present only in the JSON | 0 |
| **JSON recall of PDF records** | **~99.5%** |

**The one real gap:** batch `1-3098`, *Dextrose Injection I.P. 5%w/v (D5)*,
M/s. Tam-Bran Pharmaceuticals Pvt. Ltd. — row 1 of the CDSCO June-2025 alert PDF.
It does not appear in the portal JSON for that month. The database does hold a
different Dextrose Injection I.P 5% w/v (D5) batch (`04BF0660`) for 2025-06, so
this is a missing record, not a renamed one.

**Conclusion: the portal is not a strict superset of the PDFs.** It is far more
complete overall — it covers 2020, 2021 and everything after Jun-2025, none of
which exist as PDFs — but a PDF-sourced record can still be absent from it. The
PDF path must stay alive as a cross-check, exactly as plan.md §5.8 says.

**Field-level spot check** — first 10 rows of the CDSCO June-2025 PDF, comparing
drug name, manufacturer and testing lab against the JSON-derived record:

| Result | Count |
|---|---|
| All three fields agree | 9 |
| Record absent from JSON (batch `1-3098`) | 1 |
| **Field disagreements among matched records** | **0** |

No invented or altered field values were found. Consistent with the Phase 1a
target of a 0% invented-data rate.

### Finding: the two sources disagree on central vs state

Record totals per section do **not** match, even though the record set does:

| Section | PDF rows | JSON records | Δ |
|---|---|---|---|
| central_lab | 55 | 81 | +26 |
| state_lab | 130 | 103 | −27 |
| spurious | 4 | 4 | 0 |
| **total** | **189** | **188** | **−1** |

27 batches published in the **State** NSQ PDF are labelled `CDSCO lab` by the
portal's `str_reporting_source`. The portal's own labelling is internally
consistent (`CDSCO lab` → CDL/CDTL/RDTL/CDSCO zone labs; `State lab` → DTL/SDTL
labs), so this is a genuine disagreement between two CDSCO publications about
which tier tested a sample, not a parsing error. One oddity worth noting:
`FDA Lab, Mumbai` — a state FDA laboratory — is labelled `CDSCO lab` by the portal.

**Consequence:** `alert_section` is CDSCO's claim, not ground truth. Any analysis
that splits central vs state (plan.md §4 Phase 4, "Central vs state lab detection
patterns") must state this caveat and should prefer `testing_lab` as the finer
signal. Flagged for the planner.

### Comparator limitations (not data defects)

- The June-2025 spurious PDF **changes column count mid-document**: 12 columns on
  page 1, 10 on page 2. The throwaway comparator carries the last-seen header
  forward, so on page 2 it read the expiry date (`05-2027`) as the batch number.
  The row's real batch, `SIF2736A`, is present in both sources — spurious is
  effectively 4/4. This is a warning for Phase 1b: column position cannot be
  assumed stable even within a single file.
- Row counting treats any table row whose first cell is a serial number as data.
  A row wrapped across a page boundary could be miscounted.

---

## Not yet measured

- **Pre-2019 records.** Not loaded — Phase 1b.
- **Hand-transcribed gold standard.** plan.md Phase 1b keeps this for PDF parsing.
  Phase 1a's data is structured at source, so cross-validation against the PDFs
  serves the same purpose for 2019-onward.
- **Additional cross-validated months.** Only 2025-06 has been checked. Jun-2024
  and the 2024-05 → 2025-03 banner-era months are available in both sources and
  should be added on the next run.
