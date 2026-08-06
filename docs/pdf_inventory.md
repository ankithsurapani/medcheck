# PDF Inventory — Phase 0 Discovery

Date of survey: **2026-08-06**. Source: `src/fetch.py --all` (50 PDFs, 440 pages, cached in `data/pdfs/`).
Structural profile produced by `data/raw/profile_pdfs.py` → `data/raw/profile.json`.

---

## 0. Headline finding — read this before writing any parser

**CDSCO now publishes NSQ data as structured JSON, not just PDFs.**

In August 2025 CDSCO issued a notice, *"Availability of Not Standard Quality (NSQ) Alert on New Link in CDSCO Website"*, and moved the NSQ alert to `https://cdscoonline.gov.in/CDSCO/viewPublicNSQDrug`. That page is a DataTables front-end over JSON endpoints:

| Endpoint (base `https://cdscoonline.gov.in`) | Returns |
|---|---|
| `/CDSCO/reportingYears?tab=nsq` | `["2019", ..., "2026"]` |
| `/CDSCO/publicReportingMonths?year=2026&tab=nsq` | `["Jan", ..., "Jun"]` |
| `/CDSCO/publicNsqDrugTable` | current month, `aaData` array |
| `/CDSCO/filteredNsqDrugTable?month=Jun-2026&source=All&tab=nsq` | any month |
| `/CDSCO/viewPublicSpuriousDrugData` | spurious list |
| `/CDSCO/statesPendingSubmission` | which states haven't reported |

No auth, no key, no rate limit observed. A record looks like:

```json
{"str_product_name":"Permethrin Medicated Soap","str_batch_no":"9147",
 "dt_manufacturing_date":"Sep-2025","dt_expiry_date":"Aug-2027",
 "str_manufactured_by":"Vimson Derma, 816/3, Kothari Estate, Santej - 382721, (Gujarat).",
 "str_nsq_result":"Content","str_reporting_source":"State Lab",
 "str_reported_by_lab_or_state":"DTL, Chennai-06","dt_reporting_month_year":"JUN-2026"}
```

That maps almost 1:1 onto `nsq_records` in `plan.md` §3.1.

**Coverage — JSON vs PDF:**

| Year | NSQ records in JSON API | NSQ alert PDFs on the Alerts page |
|---|---|---|
| 2019 | 404 | 2 |
| 2020 | 326 | 0 |
| 2021 | 345 | 0 |
| 2022 | 572 | 2 |
| 2023 | 644 | 2 |
| 2024 | 877 | 13 |
| 2025 | 1,898 | 19 |
| 2026 (to Jun) | 1,060 | 0 |
| **Total** | **6,126** | **50 documents (many are one-off notices, not monthly data)** |

The JSON API has **every month from Jan-2019 to Jun-2026**. The PDF corpus does not: there is no monthly PDF at all for 2020 or 2021, and monthly PDFs stop after June 2025. The spurious tab is separate and much thinner (2 records at time of survey).

**Implication for Phase 1.** The plan's premise — "the parser is the project" — no longer holds for 2019-onward. The JSON API is a more complete, higher-fidelity source than the PDFs for that entire range. The PDF parser's real job shrinks to (a) pre-2019 history, and (b) an independent cross-check against the API. This is a planner decision, not one to make inside this ticket.

---

## 1. Corpus at a glance

| | |
|---|---|
| PDFs cached | 50 |
| Total pages | 440 |
| Born-digital | **48** |
| Scanned (image-only) | **2** |
| Release-date range | 2010-02-24 → 2025-08-28 |

**Scanned PDFs are a non-issue.** Both are one-off notices, not tabular monthly data:

- `2018-03-14_nsq-vi-conjugate-typhoid-vaccine-...` — 1p, single-batch vaccine notice
- `2025-08-28_availability-of-not-standard-quality-nsq-alert-on-new-link...` — 1p, the "we moved to a new link" notice

**Every monthly NSQ alert in the corpus is born-digital with an extractable table layer.** The plan budgeted for `pytesseract` + `pdf2image` and ">80% accuracy on OCR'd months"; on this evidence OCR is not needed at all for the monthly series.

---

## 2. The three PDFs inspected in depth

Spread across eras, per the ticket. Dumps are in `data/raw/peek_*.txt`.

| | PDF | Month | Size | Pages | Digital/scanned | Table sections | Producer |
|---|---|---|---|---|---|---|---|
| 1 | `2025-07-18_cdsco-nsq-alert-for-the-month-of-june-2025_d2879e.pdf` | Jun-2025 | 185 KB | 6 | digital | 7 (1/page + 1 split) | MS Word 2019 |
| 2 | `2024-07-19_nsq-alert-for-the-month-of-june-2024_fd8c22.pdf` | Jun-2024 | 312 KB | 6 | digital | 6 (1/page) | MS Word 2016 |
| 3 | `2018-02-05_not-of-standard-quality-alert-for-the-month-of-jan-2018_0693c3.pdf` | Jan-2018 | 201 KB | 1 | digital | 1 | MS **Excel** 2016 |

A fourth was inspected because it turned out to be a distinct layout:

| 4 | `2018-06-11_list-of-drugs-medical-devices-and-cosmetics-declared-...-quality-_272a0f.pdf` | May-2018 | 390 KB | 7 | digital | 7 | MS Word 2016 |

### Column headers per inspected PDF

**1 — Jun-2025 (8 cols).** Header on page 1 only:
```
S.No | Product/Drug Name | Batch No. | Manufacturing Date | Expiry Date |
Manufactured By | NSQ Result | Reported by CDSCO Laboratory
```

**2 — Jun-2024 (8 cols).** Same 8 columns, but row 0 is a section banner spanning the table:
```
r0: ['A. CDSCO/Central Laboratories', '', '', '', '', '', '', '']
r1: S.No | Product/Drug Name | Batch No. | Manufacturing Date | Expiry Date |
    Manufactured By | NSQ Result | Reported by CDSCO Laboratory
```

**3 — Jan-2018 (8 cols).** Same shape, but the product column is `Vaccine Name` — the 2017–2019 alerts are **vaccine-only**, not general drugs:
```
r0: ['A. Central Laboratories', '', ...]
r1: S.No. | Vaccine Name | Batch No. | Manufacturing Date | Expiry Date |
    Manufactured By | NSQ Result | Reported by CDSCO Laboratory
```

**4 — May-2018 (6 cols).** Structurally different and the hardest of the four:
```
Sl. No. | Name of Drugs/medical device/cosmetics |
Batch No./Date of Manufacture/Date of Expiry/Manufactured By |
Reason for failure | Drawn By | From
```
Column 3 is a **composite cell** holding four logical fields as free text:
`"B. No.: CBP-00711217, Mfg dt: 12/2017, Exp dt: ..."`. Batch, mfg date, expiry and manufacturer all need sub-parsing out of one string.

---

## 3. Layout eras across the whole corpus

Derived from the header row of every table in all 50 PDFs (`profile.json`).

| Era | Months | Cols | Distinguishing feature |
|---|---|---|---|
| **A — Vaccine alert** | 2017-07 → 2019-04, 2022, 2023 | 8 | Product column is `Vaccine Name`. Banner row `A. Central Laboratories`. 1 page, Excel-produced. |
| **B — Composite list** | 2018-05, 2018-08 | 6 | `Sl. No.` + composite batch/mfg/exp/manufacturer cell. Word-produced. |
| **C — Banner era** | 2024-05 → 2025-03 | 8 | Banner row `A. CDSCO/Central Laboratories` or `B. State Laboratories` precedes the header. |
| **D — Split-file era** | 2025-04 → 2025-07 | 8 | Banner dropped; CDSCO and State published as **separate PDFs**. Last column is `Reported by CDSCO Laboratory` or `Reported by State Laboratory` accordingly. |
| **S — Spurious series** | 2024-09 → 2025-07 | 10 | `S.No. \| Name of Drugs/medical device/cosmetics \| Batch No. \| Date of Manufacture \| Date of Expiry \| Manufactured By \| Reason for failure \| Drawn By \| Firm's reply \| Remarks` |

Era A and Era C/D share a column *set* but differ in banner presence and in whether the product column says `Vaccine Name` or `Product/Drug Name`. A layout router keyed on the normalized header row plus banner presence will separate all five.

**The spurious series is where `label_claim_disputed` lives.** Its `Firm's reply` and `Remarks` columns carry exactly the "the named manufacturer denies making this batch" text that `plan.md` §5.5 flags as a defamation risk. Example from Jun-2025:

> *Firm's reply:* "The actual manufacturer (as per label) has denied…"
> *Remarks:* "The product is purported to be manufactured by…"

Those two columns are not optional. They must be parsed and surfaced, per §1.1.

---

## 4. Concrete parser gotchas observed

1. **Header cells contain soft line breaks, inconsistently.** The same logical column appears as `Manufacturing\nDate`, `Manufact\nuring\nDate`, `Manufactu ring Date`, and `Manufacturi ng Date` across months. Header matching must collapse all whitespace before comparing.
2. **Tables continue across pages without repeating the header.** Page 2 of the Jun-2025 alert starts directly at row `9.` — no header row. A per-page `extract_tables()` loop that assumes row 0 is a header will silently eat a data row on every page after the first.
3. **`extract_tables()` returns one table per page**, so a logical monthly table is N page-tables that must be stitched. Table counts in `profile.json` are page-tables, not logical tables.
4. **`Manufactured By` is name + full postal address in one cell**, e.g. `"M/s. Martin & Brown Bio-Sciences Pvt.Ltd., K.No-918/419, Malkumajra, Nalagarh Road, Baddi, Dist-Solan, HP-173205"`. This single field is the entire input to Phase 2 entity resolution, and the state must be derived from the tail of it.
5. **Date formats are not consistent even within one file.** Observed: `01/2025`, `12/2027`, `Feb-24`, `Feb'16`, `12-09-2024`, and `11-09-\n2026` (line-broken mid-date). No single `strptime` format will do.
6. **`NSQ Result` is multi-valued free text**, e.g. `"Particulate Matter, Extractable Volume and Description"` → three failure categories in one cell. The controlled vocabulary in `plan.md` §3.3 needs a one-to-many mapping, not one-to-one.
7. **No ruling lines.** `page.lines` is 0 across these files; cells are drawn with `rects` (157–281 per page). `camelot`'s lattice mode will likely fail; its stream mode or pdfplumber's default is the right call.
8. **PDF `CreationDate` is unreliable as an alert date.** The Jan-2018 alert has `CreationDate: 2024-09-06` — it was re-exported years later. Use the release date from the listing page (captured in `data/pdfs/manifest.json`), not PDF metadata.
9. **Non-ASCII in source URLs.** Some PDF paths contain a curly apostrophe (`Dr. Reddy's`) and spaces; `fetch.py` unquotes then re-joins to handle it.

---

## 5. CDSCO site quirks (relevant to `fetch.py`)

- Alert PDFs are **not** linked directly. The listing table links to `download_file_division.jsp?num_id=<base64 numeric id>`, which returns a ~275-byte HTML wrapper containing an `<iframe src='…​.pdf'>`. Resolving one download is two requests.
- The listing page ships **all 300 rows in the HTML**; the pagination is client-side (footable). No pagination requests needed.
- Every CDSCO page carries a sidebar `<marquee>` that repeats some alert links. Scraping must be scoped to `<tbody>` or entries get double-counted.
- Titles are wildly inconsistent for the same document type: `NSQ ALERT FOR THE MONTH OF MAY-2025`, `CDSCO NSQ ALERT FOR THE MONTH OF June 2025`, `Not Of Standard of Quality (NSQ) ALERT FOR THE MONTH OF April-2025`, `NSQ May 2024 CDSCO Labs`, plus a typo (`JUlY-2024`). Month cannot be derived from the title with a simple regex.
- Same-day releases with near-identical titles are common, so filenames include a fingerprint of the source id to prevent collisions.
- Response times observed at 4–20s. `fetch.py` retries three times with linear backoff.
- Two listing pages carry alerts: `/en/Notifications/Alerts/` and `/en/Notifications/Archive/`.

---

## 6. Full profile of all 50 PDFs

Machine-readable: `data/raw/profile.json` (file, KB, pages, chars/page, images, page-tables, kind, first 4 distinct header rows, title, release date, source URL).
