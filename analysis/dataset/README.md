# MedCheck NSQ dataset

Every medicine batch India's drug regulator (CDSCO) published as **Not of Standard
Quality** or **spurious**, from 2019-01 to 2026-06.

- **6,155 rows**, one per flagged batch
- **1,856 resolved manufacturers**
- Licence: **CC0 1.0** — public domain, no attribution required (see `LICENSE`)
- Generated: 2026-08-07 by `analysis/export_dataset.py`
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
| `record_id` | `nsq_records.id` | Stable MedCheck id. Deterministic hash — see docs/methodology.md §2. |
| `alert_month` | `nsq_records.alert_month` | Month CDSCO published the alert, ISO 'YYYY-MM'. NOT the month of testing. |
| `alert_section` | `nsq_records.alert_section` | central_lab | state_lab | spurious, exactly as CDSCO published it. UNRELIABLE — CDSCO files 13 laboratories under both labels, and this field contradicts the laboratory's actual identity on 857 records. Kept unchanged for fidelity; use lab_type instead. |
| `drug_name` | `nsq_records.drug_name_raw` | Product name exactly as CDSCO published it, including strength and brand. |
| `dosage_form` | `nsq_records.dosage_form` | Only the spurious-drug endpoint publishes this; empty for most records. |
| `batch_number` | `nsq_records.batch_number` | As published. NOT unique — different manufacturers reuse short batch numbers. |
| `mfg_date` | `nsq_records.mfg_date` | ISO, often month-precision only ('2025-06'). Empty where CDSCO published none. |
| `expiry_date` | `nsq_records.expiry_date` | As above. |
| `manufacturer_raw` | `nsq_records.manufacturer_raw` | Manufacturer name AND full postal address in one field, as published. This is the source text; nothing was corrected. |
| `manufacturer_id` | `nsq_records.manufacturer_id` | MedCheck's resolved company id, empty where the manufacturer field is a placeholder rather than a company. NOT a CDSCO identifier. |
| `manufacturer_canonical` | `manufacturers.canonical_name` | Company name after entity resolution. PARTIAL — see the limitations below. |
| `manufacturer_state` | `manufacturers.state` | State of the resolved company, derived from the address. Empty ~42% of the time. |
| `state` | `nsq_records.state` | Manufacturing state derived from this record's address. Empty where the address could not be read unambiguously — never guessed. |
| `failure_reason` | `nsq_records.failure_reason_raw` | CDSCO's exact wording for why the batch failed, reproduced unchanged. For spurious records this also carries the firm's reply and CDSCO's remarks. |
| `failure_categories` | `nsq_records.failure_category` | Pipe-separated MedCheck categories (21 buckets + 'other'). MedCheck's mapping of the text above, not CDSCO's own classification. 'other' = no bucket matched. |
| `label_claim_disputed` | `nsq_records.label_claim_disputed` | 1 = the named manufacturer told CDSCO the batch is not theirs. 0 = no dispute recorded. EMPTY = not published, which is not the same as 'not disputed' — the NSQ endpoint has no dispute field at all. |
| `testing_lab` | `nsq_records.testing_lab` | Laboratory that reported the result, as published. |
| `lab_type` | `nsq_records.lab_type` | central | state | unknown. Derived from WHICH laboratory it is, checked against CDSCO's published list of its own laboratories — not from alert_section. Prefer this over alert_section. 'unknown' (23 records) means the string names no identifiable laboratory; it is never a guess. |
| `lab_name_canonical` | `manufacturers-style canonicalisation in src/resolve/labs.py` | Full name of the laboratory where it could be identified as one of CDSCO's. Empty for state labs, which are not individually registered here. |
| `source_url` | `nsq_records.source_url` | The CDSCO page or file this row came from. Check any row against it. |
| `source_type` | `nsq_records.source_type` | portal_json | pdf |
| `parse_confidence` | `nsq_records.parse_confidence` | 0-1. MedCheck's own confidence in this row, not CDSCO's. |
| `parse_flags` | `nsq_records.parse_flags` | Pipe-separated processing flags — what was uncertain about this row and why. |

Multi-valued fields (`failure_categories`, `parse_flags`) are pipe-separated.
Empty means "CDSCO did not publish this", never zero and never "none".

## Known limitations

| Limitation | Effect |
|---|---|
| Sampling is not random | Nothing here is a population failure rate. |
| Manufacturer resolution is **partial** | 1,856 companies from 5,107 published spellings, but 190 ambiguous pairs were left unmerged pending human review. Some companies still appear under more than one `manufacturer_id`. Concentration measured from this file is a **lower bound**. |
| `alert_section` is unreliable | CDSCO files 13 laboratories under both `central_lab` and `state_lab`, and the field contradicts the laboratory's identity on 857 rows. It is kept verbatim for fidelity. **Use `lab_type` instead** — derived from which laboratory it is, against CDSCO's published list of its own labs. |
| `state` is 58% populated | Derived from free-text addresses, left empty rather than guessed where ambiguous. Do not treat the populated subset as the whole picture. |
| No therapeutic classification | There is no drug-class column. `analysis/drug_classes.py` derives anti-infective groups from published WHO INN stems; that is a claim about names, not an ATC classification. |
| 78 rows have no `manufacturer_id` | Their manufacturer field is a placeholder ("Under Investigation" and similar), not a company. Deliberately not resolved. |
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
