# MedCheck — Project Memory

Searchable public database of medicines CDSCO flagged as Not of Standard Quality (NSQ) or spurious. Full spec: `plan.md`. Current task: `implementation.md`.

> **Builder:** update *Current Status*, *Decisions Log*, and *Key Learnings* below whenever you make a decision or hit something worth remembering. One line per entry. Don't touch `plan.md`.

---

## Non-negotiables (see plan.md §1 for full detail)

- **Mirror, not accuser.** Reproduce CDSCO's data faithfully, link the source PDF, no editorial language.
- **Never imply "stop taking this medicine."** Required non-dismissible copy on every result page (plan.md §1.2).
- **A batch failure is not a product failure** — must be visible on every result, not footnoted.
- **Uncertainty is shown, not hidden.** Low-confidence parse → labeled uncertain, never a confident guess.
- **No user health data.** No accounts, no per-identity search tracking, aggregate analytics only.
- **Never auto-merge entities** above the 0.75–0.92 fuzzy-match review band without a human look — wrongly merging manufacturers is reputational harm.
- **Sampling bias caveat everywhere a rate/percentage is shown** — CDSCO doesn't test randomly.

## Current status

**Phase 0 (Discovery) — complete.** Phase 1a (JSON ingestion) ticket is now active — see `implementation.md`.

Still open:
- Nothing committed yet: `git init` done but no git `user.name`/`user.email` configured, so no initial commit was made. Set this — ask the user for values, don't invent them — and commit Phase 0's work before starting Phase 1.

## Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| PDF parsing | `pdfplumber` primary, `camelot` fallback |
| OCR | `pytesseract` + `pdf2image` |
| Fuzzy matching | `rapidfuzz` |
| Database | SQLite → Postgres later |
| Backend | FastAPI |
| Frontend | Next.js + Tailwind |
| Hosting | Vercel (frontend) + Railway/Fly.io (API) |
| Scraping schedule | GitHub Actions cron |

## Repo structure

```
medcheck/
├── data/{pdfs,raw,gold,medcheck.db}
├── src/{fetch.py, ingest/cdsco_json.py, normalize.py, parse/{base,router,layout_a,layout_b,ocr}.py (Phase 1b, deferred), resolve/{manufacturers,drugs}.py, validate.py, db.py}
├── api/          # FastAPI
├── web/          # Next.js
├── analysis/     # notebooks + writeup
├── docs/{pdf_inventory.md, parser_accuracy.md, methodology.md}
└── README.md
```

## Decisions log

<!-- Format: YYYY-MM-DD — decision, one line. Newest last. -->
- 2026-08-06 — API fallback is a static pre-built JSON search index shipped with the frontend, not a second live API deployment (SQLite needs persistent filesystem, Vercel serverless doesn't give it).
- 2026-08-06 — UI (Phase 3) will be built by the same Opus builder terminal — no separate UI workflow/tool.
- 2026-08-06 — `fetch.py` scrapes both `/Notifications/Alerts/` and `/Notifications/Archive/`; alerts are matched on title regex (`nsq|not of standard|not standard quality|spurious`) because CDSCO titles are too inconsistent for anything narrower.
- 2026-08-06 — Cached PDF filenames are `<release-date>_<title-slug>_<6-char sha1 of source url>.pdf`. The fingerprint is deliberate: CDSCO publishes same-day alerts whose titles agree for the first 80 chars, and without it distinct source documents silently overwrite each other.
- 2026-08-06 — Downloaded all 50 discoverable alerts rather than the 8–10 the ticket asked for. The recent 10 are all 2025, which would have made "inspect PDFs from different eras" impossible; the full set is ~15 MB and the fetch is idempotent.
- 2026-08-06 — Phase 0 structural profiling lives in `data/raw/profile_pdfs.py` (throwaway), not `src/parse/`, to respect the ticket boundary. It measures shape only — no normalization.
- 2026-08-06 — **Phase 1 pivots to JSON-first**, given the discovery that CDSCO's portal covers Jan-2019→present more completely than the PDF corpus does. Phase 1a (JSON ingestion, `src/ingest/`) is now the primary path and comes first; Phase 1b (PDF layout parsers) is deferred and scoped down to pre-2019 backfill only. See `plan.md` §4 Phase 1.
- 2026-08-06 — `nsq_records` schema changed: `source_pdf_url` → `source_url` + new `source_type` ("pdf"|"portal_json"), since records can now come from a JSON portal query, not just a PDF. `failure_category` changed from a single value to a JSON array, since `NSQ Result` is multi-valued at the source. Non-negotiable §1.1 wording updated to match ("link to its source" instead of "link to the source PDF").

## Key learnings / gotchas

<!-- Format: short bullet, concrete and specific. Newest last. -->
- **A structured JSON source exists.** `https://cdscoonline.gov.in/CDSCO/filteredNsqDrugTable?month=Jun-2026&source=All&tab=nsq` returns clean per-month JSON, no auth, fields mapping ~1:1 to `nsq_records`. Every month Jan-2019 → Jun-2026: 6,126 records. Also `/CDSCO/viewPublicSpuriousDrugData`, `/CDSCO/reportingYears`, `/CDSCO/publicReportingMonths`, `/CDSCO/statesPendingSubmission`.
- **The PDF corpus is not a complete monthly series.** 50 documents total, and several are one-off notices. Zero monthly alerts exist for 2020 and 2021; monthly PDFs stop after Jun-2025 (CDSCO moved to the portal in Aug-2025). PDFs alone cannot reconstruct the record.
- **OCR is essentially not needed.** 48 of 50 PDFs are born-digital with extractable tables. The only 2 scanned files are single-page notices with no table. The plan's `pytesseract`/`pdf2image` budget and its ">80% on OCR'd months" target are moot for the monthly series.
- **Five distinct PDF layouts, not 2–3.** Era A vaccine-only (`Vaccine Name` column, 2017–2019/2022/2023), Era B composite 6-col (2018), Era C banner 8-col (2024-05→2025-03), Era D split CDSCO/State files 8-col (2025-04→2025-07), plus a separate 10-col spurious series. Router should key on the whitespace-normalized header row plus banner presence.
- **Tables continue across pages without repeating the header.** Page 2+ of a multi-page alert starts straight at a data row. Any per-page loop that treats row 0 as a header will eat one real record per page.
- **Header text has soft line breaks, inconsistently placed** — `Manufacturing\nDate`, `Manufact\nuring\nDate`, `Manufactu ring Date` are all the same column. Collapse whitespace before matching.
- **`Manufactured By` is company name + full postal address in one cell.** That single blob is the entire input to Phase 2 entity resolution, and `state` has to be derived from its tail.
- **`NSQ Result` is multi-valued** — e.g. "Particulate Matter, Extractable Volume and Description" is three failure categories in one cell. §3.3 needs one-to-many mapping.
- **The spurious series carries `Firm's reply` and `Remarks` columns** — this is where "the named manufacturer denies making this batch" appears, i.e. the source for `label_claim_disputed`. Not optional; §5.5 defamation risk lives here.
- **Date formats vary within a single file**: `01/2025`, `Feb-24`, `Feb'16`, `12-09-2024`, and dates broken across a newline (`11-09-\n2026`).
- **PDFs have no ruling lines** (`page.lines` == 0); cells are drawn as `rects`. `camelot` lattice mode will likely fail — use stream mode or pdfplumber.
- **PDF metadata dates lie.** The Jan-2018 alert reports `CreationDate: 2024-09-06` (re-exported later). Use the listing-page release date from `data/pdfs/manifest.json`.
- **CDSCO never links PDFs directly.** Downloads go through `download_file_division.jsp?num_id=<base64 id>`, which returns a ~275-byte HTML wrapper containing an `<iframe src='...pdf'>`. Two requests per download.
- **Scrape only `<tbody>`.** Every CDSCO page has a sidebar `<marquee>` repeating alert links; unscoped scraping double-counts. The listing table ships all 300 rows inline — pagination is client-side.
- **cdsco.gov.in is slow** (4–20s responses) but was up throughout. `fetch.py` retries 3× with linear backoff.
