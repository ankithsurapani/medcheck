# Current Task — Phase 1a: JSON Ingestion

**Read first:** `CLAUDE.md` (project memory + latest decisions), `docs/pdf_inventory.md` §0 (the JSON portal finding — field mapping and endpoint list are there), and `plan.md` §3 (schema, now updated) and §4 Phase 1 (now split into 1a/1b, this ticket is 1a only).

**Housekeeping before anything else:** git identity still isn't configured (no `user.name`/`user.email`), so Phase 0's work was never committed. Ask the user for the values to use — don't invent them — set them, and commit Phase 0's work as a first commit before starting this ticket's work.

## Why this ticket looks different from the original plan.md Phase 1

Phase 0 found CDSCO now publishes NSQ data as structured JSON, covering every month Jan-2019 → present (6,126 records) — more complete than the PDF corpus for that same range. So instead of building PDF layout parsers first, this ticket builds a JSON ingestion pipeline: it's more data, higher fidelity, and far less parsing risk. PDF layout parsing (`layout_a.py` etc.) is Phase 1b, a separate later ticket scoped to pre-2019 backfill only — **don't start it now.**

## Task

1. **Inspect the spurious endpoint first.** Fetch `https://cdscoonline.gov.in/CDSCO/viewPublicSpuriousDrugData` and look at its shape — confirm whether it carries fields equivalent to the PDF spurious series' `Firm's reply` / `Remarks` columns (that's where `label_claim_disputed` comes from — non-negotiable, see plan.md §1.1 and §5.5). Note findings in `CLAUDE.md`.

2. **`src/ingest/cdsco_json.py`** — enumerate years via `reportingYears?tab=nsq` and months via `publicReportingMonths?year=...&tab=nsq`, then fetch `filteredNsqDrugTable?month=<Mon-YYYY>&source=All&tab=nsq` for each, plus `viewPublicSpuriousDrugData`. Cache every raw response to disk before normalizing anything (plan.md §5.8 — the portal is undocumented and could change). Make it idempotent like `src/fetch.py` — skip months already cached, safe to re-run.

3. **`src/db.py`** — SQLite schema from `plan.md` §3 (`nsq_records`, `manufacturers`), `CREATE TABLE IF NOT EXISTS`, writes to `data/medcheck.db`.

4. **`src/normalize.py`** — map raw JSON fields to `nsq_records` columns (mapping shape is in `docs/pdf_inventory.md` §0). Specifically:
   - Split multi-valued `str_nsq_result` (e.g. `"Particulate Matter, Extractable Volume and Description"`) into the `failure_category` JSON array — one-to-many, not one-to-one (plan.md §3.3).
   - Normalize date formats — expect inconsistency even within the same source (docs/pdf_inventory.md §4.5 catalogued PDF examples; check whether the JSON's date fields are cleaner, don't assume).
   - `source_url` = the exact query URL fetched for that record's month/tab (reproducible — required, never null). `source_type` = `"portal_json"`.
   - `alert_section` from `str_reporting_source` ("central_lab" / "state_lab"); `testing_lab` from `str_reported_by_lab_or_state`.
   - `state`: only derive it if it's a clean, low-risk extraction from the address tail in `str_manufactured_by`. If it's ambiguous, leave it null and flag it — don't guess (plan.md §1.4). Full manufacturer-address parsing is Phase 2's job, not this ticket's.
   - `parse_confidence`: structured source data, so this should sit high by default — but drop it and add a `parse_flags` entry per-record for anything genuinely uncertain (ambiguous date, ambiguous category split, etc.).

5. **Decide and document an `id` scheme.** The sample JSON record has no obvious stable unique id — check for one across the actual API responses. If there isn't one, construct a deterministic id from month + batch number + drug name + manufacturer, and write down the collision risk explicitly (plan.md §5.4: batch numbers are not unique across manufacturers). Put the scheme in `docs/methodology.md`.

6. **`src/validate.py`** — sanity rules: expiry after mfg date where both are parseable, batch number non-empty/plausible, required fields present. A violation becomes a `parse_flags` entry, never a silently dropped or silently "fixed" record.

7. **Cross-validate against Phase 0's PDFs.** Pick one month that exists in both sources — Jun-2025 or Jun-2024 (both already cached in `data/pdfs/`, dumps in `data/raw/peek_*.txt`). Compare: does the JSON-derived record count match the PDF table row count for that month? Spot-check ~10 field values. Write findings to `docs/parser_accuracy.md`.

## Explicit boundary — do NOT do yet

- No `src/parse/layout_a.py`/`layout_b.py`/`router.py`/`ocr.py` — that's Phase 1b, a separate ticket, pre-2019 backfill only.
- No entity resolution — `manufacturer_raw` stays raw text, `manufacturer_id` stays null, no fuzzy matching. That's Phase 2.
- No API or web code.

## Done when

- [ ] Git identity set, Phase 0 committed
- [ ] Spurious endpoint shape documented, `label_claim_disputed` source field confirmed or flagged as missing
- [ ] `src/ingest/cdsco_json.py` runs, idempotent, all months Jan-2019 → latest cached raw to disk
- [ ] `data/medcheck.db` exists with `nsq_records` populated (~6,126+ rows) and spurious records loaded
- [ ] `id` scheme decided and documented in `docs/methodology.md`
- [ ] Cross-validation against one PDF month written up in `docs/parser_accuracy.md`
- [ ] `CLAUDE.md` updated: Current Status, Decisions Log, Key Learnings

## Before ending the session

Update `CLAUDE.md`:
- **Current Status** → what's loaded, what's still open, record counts actually achieved
- **Decisions Log** → id scheme chosen, any schema deviations, cross-validation outcome
- **Key Learnings** → JSON field quirks, date format reality, spurious-endpoint shape, anything that surprised you

Do not start Phase 1b or Phase 2 even if it feels like the natural next step — that's the next ticket, written after the planner reviews what this one found.
