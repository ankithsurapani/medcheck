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

**Phase 0 (Discovery) — complete and committed.**

**Phase 1a (JSON ingestion) — complete.** `data/medcheck.db` holds **6,155 records across 90 alert months (Jan-2019 → Jun-2026)**: 3,029 central_lab, 3,079 state_lab, 46 spurious, 43 marked `label_claim_disputed`. Whole pipeline is idempotent — re-running ingest and normalize leaves the count unchanged.

- `src/ingest/cdsco_json.py` — caches every raw portal response to `data/raw/portal/` before normalizing (plan.md §5.8)
- `src/db.py` / `src/normalize.py` / `src/validate.py` — schema, mapping, sanity rules
- `docs/methodology.md` — id scheme, field derivation, confidence model
- `docs/parser_accuracy.md` — cross-validation vs the Jun-2025 PDFs

**`failure_category` vocabulary extended twice (2026-08-06)** — §3.3 went from 11 to 21 buckets: `ph`, `water_content`, `uniformity_of_weight`, `bacterial_endotoxins`, `uniformity_of_dispersion`, then `loss_on_drying`, `density`, `extractable_volume`, `clarity_of_solution`, `dimensions`. `other` fell **657 → 363 → 269 records (10.7% → 4.4%)**. Guarded by `tests/test_categorise.py` (59 cases).

**Phase 3a (search site) — now active.** Jumping ahead of Phase 2 (entity resolution) on user instruction — see `implementation.md`.

Open / needs a planner decision:
- **`alert_section` is unreliable.** The portal and the PDFs disagree on central-vs-state for 27 of 184 Jun-2025 records. Phase 4's "central vs state lab detection patterns" analysis needs this caveat.
- **State coverage is 58%.** PIN-prefix → state mapping would lift it a lot; belongs with Phase 2's address parsing.
- Phase 1b (pre-2019 PDF backfill) not started, per ticket boundary.
- Phase 2 (entity resolution) not started — Phase 3a's manufacturer search/pages run on raw text, not merged identity, until it does.

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
- 2026-08-06 — **id scheme:** `NSQ_<alert_month>_<12 hex of sha256>` over `alert_month|batch|drug|manufacturer|testing_lab|failure_reason`. Manufacturer is in the key because §5.4 batch numbers aren't unique; lab and reason are in it because CDSCO legitimately lists one batch twice when two labs tested it. Spurious uses `SPU_<num_id>` when the portal gives one, else the same hash. Collisions are detected and disambiguated with a flag, never resolved by silent overwrite. Full rationale in `docs/methodology.md` §2.
- 2026-08-06 — Unmapped failure reasons go to `["other"]` + a flag rather than being forced into the nearest §3.3 bucket.
- 2026-08-06 — **§3.3 extended with 5 buckets** on the user's instruction: `ph`, `water_content`, `uniformity_of_weight`, `bacterial_endotoxins`, `uniformity_of_dispersion`. `other` 657 → 363 records. This edited `plan.md`, which the builder note above otherwise forbids — done because §3.3 *is* the canonical vocabulary and the user asked for it directly.
- 2026-08-06 — `bacterial_endotoxins` kept separate from `microbial_contamination`: endotoxins persist after the organisms that produced them are gone, so a batch can fail endotoxins while passing sterility. Merging them would misreport the regulator.
- 2026-08-06 — `water_content` deliberately excludes "Water-soluble substances" (a solubility/impurity test), and "Loss on Drying" got its own bucket rather than being folded in — LOD measures all volatiles, water determination measures water.
- 2026-08-06 — **§3.3 extended a second time** with `loss_on_drying`, `density`, `extractable_volume`, `clarity_of_solution`, `dimensions`. `density` deliberately merges specific gravity / relative density / weight per ml — three monograph names for one mass-per-unit-volume measurement. `clarity_of_solution` kept separate from `description_labelling` because CDSCO lists them as distinct tests and frequently cites both on one record.
- 2026-08-06 — CDSCO's own typos are absorbed into existing buckets rather than left in `other` (`Sterillity`, `Related Susbtances`, `TEST FOR DISSOLUTI ON`) — the intended test isn't in doubt. But reasons that name **no test at all** (`Not applicable`, `NSQ`, `Does not conform to I.P.`, `Not of Standard Quality`, ~20 records) stay in `other` permanently; assigning a category would invent a finding (§1.4). Asserted in the test suite.
- 2026-08-06 — Stopped extending the vocabulary at 21 buckets. What remains in `other` is a long tail where no group exceeds 3 records; adding buckets at that frequency would over-fit the current corpus.
- 2026-08-06 — `state` is derived only from an explicit state field, an exact state-name match, or one of seven unambiguous abbreviations (`U.P.`, `H.P.`, `M.P.`, `T.N.`, `W.B.`, `J&K`, `New Delhi`). `A.P.` and `U.K.` are excluded as ambiguous. Two different states named → null + `state_ambiguous` flag.
- 2026-08-06 — `label_claim_disputed` is null (not 0) for all NSQ records: the NSQ endpoint has no dispute field, so null means "not published", not "not disputed". Only the spurious endpoint carries `str_firm_reply`/`str_nsq_remarks`, and both are appended verbatim to `failure_reason_raw` so the published wording travels with the boolean (§1.1).
- 2026-08-06 — Cross-validation is a throwaway script in `data/raw/crossvalidate.py`, not `src/`, matching the Phase 0 precedent for discovery-only tooling.
- 2026-08-06 — `nsq_records` schema changed: `source_pdf_url` → `source_url` + new `source_type` ("pdf"|"portal_json"), since records can now come from a JSON portal query, not just a PDF. `failure_category` changed from a single value to a JSON array, since `NSQ Result` is multi-valued at the source. Non-negotiable §1.1 wording updated to match ("link to its source" instead of "link to the source PDF").
- 2026-08-06 — **Jumping to Phase 3 (UI) ahead of Phase 2** on user instruction. Split into 3a (now: static-data MVP) / 3b (deferred: Hindi, live API, resolved-entity manufacturer pages) — same a/b pattern as Phase 1. See `plan.md` §4 Phase 3.
- 2026-08-06 — Phase 3a serves the UI from a static JSON export of `medcheck.db`, not a live FastAPI. This is the same artifact already planned as the API fallback (§2) — building it now does double duty and avoids standing up Railway/Fly.io hosting before there's demand.
- 2026-08-06 — Manufacturer search/pages in 3a match on exact `manufacturer_raw` text, not a resolved entity — near-duplicate company names will show as separate results until Phase 2 runs. The UI must say this, not hide it (§1.1 mirror-not-accuser: don't imply a merge that hasn't happened).

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
- **The two spurious endpoints return different field sets.** `viewPublicSpuriousDrugData` (current month) gives 23 fields including a stable `num_id`, `str_manufacturing_state` and `str_dosage_form`. The per-month `filteredSpuriousDrugTable` gives only 13 and has **no `num_id`**. Don't assume one shape per tab.
- **The portal is NOT a strict superset of the PDFs.** Jun-2025: 187 of 188 PDF batches are in the JSON, but batch `1-3098` (Dextrose Injection I.P. 5%w/v, M/s. Tam-Bran) appears only in the PDF. Keep the PDF path alive as a cross-check (§5.8), don't retire it.
- **The portal and the PDFs disagree on central vs state.** 27 of 184 Jun-2025 records sit in the State PDF but are labelled `CDSCO lab` by the portal. The portal is internally consistent about it, so it's a real disagreement between two CDSCO publications, not a parse error. `FDA Lab, Mumbai` — a state lab — is labelled `CDSCO lab`.
- **Portal dates are clean, unlike the PDFs.** Every `dt_*` value is `Mon-YYYY`; only 100/6,126 mfg and 105/6,126 expiry dates are empty. The messy formats catalogued in `pdf_inventory.md` §4.5 are a PDF problem, so `norm_date` handles them for Phase 1b but they never fire on portal data.
- **`str_reporting_source` has four casings plus a junk value** — `CDSCO lab`, `CDSCO Labs`, `State lab`, `State Lab`, and one `Not applicable`. Match case-insensitively on substrings.
- **The portal mangles typographic quotes into literal `?`** — e.g. `It fails the test ?Dissolution? as per IP`, `Amritsar ? 143001`. Not an encoding fix we can safely reverse, so it's normalized to whitespace and the original is kept in the `*_raw` column.
- **Spurious records name no manufacturer.** 51 records carry the literal string `Under Investigation` in `str_manufactured_by` because the true maker of a counterfeit is unknown. Flagged `manufacturer_unknown_placeholder` so Phase 2 never resolves it into a company entity — treating it as one would be a §1.1 violation.
- **A single PDF can change column count mid-document.** The Jun-2025 spurious alert has 12 columns on page 1 and 10 on page 2. Phase 1b must locate columns per-table from the header, not by fixed index.
- **`pH` is the single most common failure with no original §3.3 bucket** — 260 records, more than `disintegration` (234) or `related_substances` (186). Now mapped.
- **CDSCO's failure text contains typos and OCR-style line breaks in the source itself** — `Sterillity`, `Related Susbtances`, `TEST FOR DISSOLUTI ON`, `Misbrandad`, `Dissolutin`. This is the published JSON, not a parsing artifact. Category patterns have to tolerate them or real findings get dropped into `other`.
- **Device/dressing records use a different test vocabulary entirely** — "Threads per stated Length", "Weight in g/m2", "Warp threads per 10 cm", "Fluorescence" (absorbent gauze and similar). Drug-oriented buckets don't fit them; `dimensions` covers some.
- **`\bwater\b` alone is not safe as a water-content pattern** — it matches "Water-**soluble** and Ether-soluble substances", a solubility/impurity test. Caught by spot-checking matches after the vocabulary extension, not by the unit cases.
- **`content` is ambiguous between buckets** — "water content" and "moisture content" are moisture limits, not an assay of the active ingredient. The `assay` pattern needs negative lookbehinds or it double-counts them.
- **State names appear inside company names and road names.** "M/s. Karnataka Antibiotics… Palghar, Maharashtra", "G.I.D.C. Kerala (Bavla), Ahmedabad, Gujarat", "Delhi-Mathura Road, Faridabad, Haryana". Naive first-match state extraction would be wrong on all three — hence the ambiguity check.
- **Himachal Pradesh dominates** (1,258 of 3,576 records with a derived state), then Uttarakhand (562) and Gujarat (365). Consistent with Baddi/Solan being India's pharma manufacturing hub — a sanity check that state derivation isn't badly skewed.
