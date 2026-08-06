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

**Phase 3a (search site) — complete.** Static Next.js 15 + Tailwind v4 app in `web/`, built against a static JSON export. No API, no server, no tracking.

**Phase 3b (partial: re-point `web/` at resolved entities) — complete.** **8,017 static pages** build clean, down from 11,268 (6,155 record pages + **1,856 manufacturer pages** + 6 fixed).

- `scripts/export_static.py` groups by `manufacturer_id` / the `manufacturers` table, not `manufacturer_raw`. Client index **297 KB → 255 KB brotli** (5,107 per-spelling slugs became 1,856 canonical ones)
- Manufacturer slug scheme: `<canonical-name-slug>-m<manufacturers.id>` — Phase 3a's per-raw-string hash slug is gone
- Every manufacturer page lists **all** raw spellings that collapsed into it, in a `<details>` (open at ≤5, collapsed above — Jackson has 67)
- The 78 placeholder records get **no manufacturer page**; the record page renders `NotACompanyNotice` where the link would be
- Manufacturer search matches raw spelling **or** canonical name, and every spelling routes to one page
- Verified after rebuild: **0 dead links** across 6,155 record + 1,856 manufacturer pages; exactly 78 record pages have no manufacturer link. Zee 48 spellings/66 batches, Jackson 67/88, Unicure 62/77 — all single pages, all aliases rendered
- `npm run test:search` — **29 assertions** (was 17), all passing
- Search: MiniSearch fuzzy for drug names, exact for batch, substring for manufacturer
- `web/lib/{copy,failure-categories}.ts` hold every user-facing string — all 21 categories have plain-language explanations
- Verified: `label_claim_disputed` record renders the §5.5 notice with the firm's verbatim wording; missing-`state` record renders "Not published" + reason, never blank; non-disputed records do *not* show the dispute notice

Design system persisted at `design-system/medcheck/MASTER.md` (Swiss Modernism 2.0 + "Patent / IP Database" palette, via the ui-ux-pro-max skill).

**Phase 2a (manufacturer entity resolution) — complete.** Human review actually happened (partial, and that's a legitimate stopping point — see below), then applied.

- `src/resolve/manufacturers.py` — normalizer, 3-key blocking, `rapidfuzz` scoring, three tiers, `--build` / `--apply` / `--cohesion`
- `src/resolve/review_cli.py` — the 0.75–0.92 band, cluster-vs-cluster, **15 of 205 pairs decided (all approve), 190 left pending**
- `src/resolve/spotcheck_cli.py` — **5 auto-merge clusters spot-checked, all verdict `correct`** (weakest-cohesion clusters sampled first)
- `data/resolve/manufacturer_merge_log.jsonl` — append-only audit trail: 3,229 auto-merge edges, 15 review decisions, 5 spot-checks, 2 apply runs
- `docs/entity_resolution.md` — thresholds, blocking, collapse ratio, known limits
- `tests/test_resolve_manufacturers.py` — 45 checks, all passing

**Final applied state: manufacturers 1,871 → 1,856** (the 15 approvals), **collapse ratio 2.75 : 1**. `--apply` refuses to run with undecided review pairs unless given `--allow-pending`; that flag was used deliberately — the 190 still-pending pairs are treated as **not merged** (conservative, can only under-merge). 6,077 of 6,155 records carry a `manufacturer_id`; the 78 unlinked are the 7 placeholder strings (`manufacturer_unknown_placeholder`), which deliberately stay `NULL` — never resolved into a company entity.

Open / needs a planner decision:
- **190 review-band pairs are still undecided**, by the user's choice — legitimate, not a bug. Re-running `review_cli.py` later and re-applying with `--allow-pending` will only ever tighten the collapse further, never wrongly merge. No urgency, but worth remembering it's there.
- **Manufacturer slugs carry a positional id** (`-m<manufacturers.id>`), and `--apply` renumbers 1..N in canonical-name order. Finishing the 190 pending review pairs will therefore change most manufacturer URLs. Fine now (nothing is public); if the site ever ships, the slug needs a content-derived id first.
- **Search index is 255 KB brotli** (down from 297 KB). Lazy-loaded on idle/focus so the page is usable first, but still the biggest cost on a slow connection. A later Phase 3b option: server-side search, or a two-tier prefix index.
- Rest of Phase 3b (Hindi/i18n, live FastAPI) still deferred.
- **`alert_section` is unreliable.** The portal and the PDFs disagree on central-vs-state for 27 of 184 Jun-2025 records. Phase 4's "central vs state lab detection patterns" analysis needs this caveat.
- **State coverage is 58%.** PIN-prefix → state mapping would lift it a lot; belongs with Phase 2a's address parsing.
- Phase 1b (pre-2019 PDF backfill) not started, per ticket boundary.
- Phase 2b (drug-name resolution) deferred — nothing depends on it yet.

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
├── src/{fetch.py, ingest/cdsco_json.py, normalize.py, parse/{base,router,layout_a,layout_b,ocr}.py (Phase 1b, deferred), resolve/{manufacturers.py, review_cli.py, spotcheck_cli.py, drugs.py (Phase 2b, deferred)}, validate.py, db.py}
├── api/          # FastAPI
├── web/          # Next.js
├── analysis/     # notebooks + writeup
├── docs/{pdf_inventory.md, parser_accuracy.md, methodology.md, entity_resolution.md}
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

- 2026-08-06 — **Phase 3a search library: MiniSearch**, not Fuse.js. Fuse scores every record on every keystroke over 6,155 records; MiniSearch builds an inverted index once and answers from it, and it ships a smaller bundle. Fuzzy 0.2 + prefix matching handles the typo tolerance the ticket asked for.
- 2026-08-06 — **Batch search is exact and deliberately never fuzzy.** plan.md §5.4: batch numbers are not unique across manufacturers and are often short ("2451"). A fuzzy batch match would show a different company's batch as if it were the user's — the exact confusion the site exists to remove. Asserted in `web/tests/search.test.mjs` (`SIF2736B` must return 0).
- 2026-08-06 — Client index is **columnar** (parallel arrays + deduped manufacturer table), not an array of objects: 377 KB → 277 KB gzipped. Manufacturer strings are *not* truncated — truncating saved only ~11 KB and would break substring matching on the full `manufacturer_raw` the ticket specifies.
- 2026-08-06 — Index is **lazy-loaded** on browser idle or first input focus, not on mount, so a phone renders the page without paying for 297 KB first. Explicit "Preparing search…" state rather than a dead input.
- 2026-08-06 — Manufacturer page slugs are `<60-char slug>-<8 hex of sha1 of the FULL raw string>`. The hash is not decoration: two manufacturers differing only past the 60-char cutoff must not collapse onto one page. Merging distinct companies is Phase 2's decision with a human in the loop, never a side effect of slug truncation (§5.3).
- 2026-08-06 — **No red in the palette.** plan.md §1.1 — MedCheck mirrors a regulator, it does not accuse. Flags are amber; the only strong colour is reserved for `label_claim_disputed`, and the heaviest element on any result page is the §1.2 notice telling people *not* to stop their medicine.
- 2026-08-06 — Deviated from the ui-ux-pro-max generic recommendation ("Exaggerated Minimalism", `font-weight: 900`, `clamp(3rem, 10vw, 12rem)`). Oversized statement typography reads as alarming on flagged-medicine data. Used the skill's "Patent / IP Database" analog instead — Swiss Modernism 2.0 + formal neutral palette + status chips — which is what a public-records lookup should feel like.
- 2026-08-06 — Typography is Figtree + Noto Sans (the skill's healthcare pairing). Noto Sans also has full Devanagari coverage, so Phase 3b's Hindi translation won't force a type change.
- 2026-08-06 — `output: 'export'` (fully static). No server means no server-side log of what anyone searched — §1.5 enforced by architecture, not by policy.
- 2026-08-06 — **Phase 2 splits into 2a (manufacturers, now) / 2b (drug names, deferred)** — same a/b pattern as Phase 1 and 3. Manufacturer resolution is what's actually blocking things (5,107 unmerged pages); drug names aren't blocking anything yet. See `plan.md` §4 Phase 2.
- 2026-08-06 — Phase 2a's human review queue is a CLI/offline step, not a web UI — Phase 3a's architecture is fully static with no backend to host one.
- 2026-08-06 — Phase 2a is scoped data-only: produces `manufacturers` + `manufacturer_id` backfill, but does not touch `web/` to collapse the 5,107 pages. That regeneration is the next ticket, kept separate on purpose.
- 2026-08-06 — **Phase 2a scoring: the name carries the score, the address only adjusts it** — `token_sort_ratio(names)` minus 0.09 (states differ) / 0.05 (PINs differ) / 0.04 (address similarity < 0.40), plus 0.03 (PIN shared). An earlier draft weighted address at 28% and pushed **353** cluster pairs to review, most of them one company's two plants (Unicure has a Noida plant and a Roorkee plant). A reviewer asked that question 353 times stops reading it — queue length is what causes rubber-stamping. Address-as-adjustment asks it once and cuts the queue to 205.
- 2026-08-06 — `token_sort_ratio`, not `token_set_ratio`: the set variant scores "Sun Pharma" against "Sun Pharma Laboratories" as a perfect match, which is a merge nobody authorized.
- 2026-08-06 — **Industry words are folded, not stripped**, deviating from the ticket's "strip `Pharmaceuticals`/`Pharma`". Stripping reduces "Zee Laboratories" to `zee` — four characters, high-scoring against unrelated firms. Folding to `zee lab` matches all 48 Zee spellings and nothing else. Generic tokens *are* dropped, but only for the blocking key, where a block named `pharma` would hold a third of the corpus.
- 2026-08-06 — **Blocking is first-token + 4-char-prefix + sorted-tokens, and state is a score signal rather than a block**, deviating from the ticket's "first token + state". State is derivable for only 58% of records and CDSCO gets it wrong outright on at least one (a Paonta Sahib, H.P. address labelled Punjab); blocking on it would have refused to consider that record at all. 38,095 candidate pairs out of a possible 13.0M.
- 2026-08-06 — **The review queue is cluster-vs-cluster, not string-vs-string.** Auto merges are applied first, so 1,183 of the 2,716 band pairs turn out to already be connected by a stronger path, and the remaining 1,533 collapse into 205 distinct company-pair questions.
- 2026-08-06 — **`--apply` treats an undecided review pair as rejected** and refuses to run without `--allow-pending`. Running the pipeline before the human review can therefore only under-merge, never over-merge.
- 2026-08-06 — The merge log records the **3,229 spanning edges**, not all 21,219 auto pairs. A redundant edge inside an already-joined cluster changes no outcome, and the spanning set alone reconstructs or undoes the clustering exactly. `data/resolve/candidates.json` (7.9 MB, the full scored list) is gitignored — derived, and regenerable from the DB.
- 2026-08-06 — Placeholders keep `manufacturer_id` **NULL**, deliberately breaking the ticket's "nothing ends up without an id". 78 records across 7 non-company strings; giving a counterfeit's unknown maker a company entity with 51 flagged batches is the §1.1 misattribution the rule exists to prevent.
- 2026-08-06 — Human review stopped at **15 of 205** pairs by user choice, applied with `--allow-pending` (190 pending → treated as not-merged). This is accepted as a legitimate stopping point, not a shortcut: the asymmetry the rule protects against (false merge = reputational harm) doesn't apply to "haven't decided yet" — only to auto-approving without looking. Review can resume anytime; `--apply --allow-pending` is safe to re-run after.
- 2026-08-06 — Web regeneration against resolved entities is its own ticket, not folded into Phase 2a — keeps entity resolution as pure data engineering, frontend work separate. Scoped as partial Phase 3b (entity re-pointing only; Hindi and live API remain deferred).
- 2026-08-06 — **Manufacturer slug is `<canonical-name-slug>-m<manufacturers.id>`**, replacing Phase 3a's `<slug>-<sha1 of the full raw string>`. The hash existed to stop two spellings colliding onto one page before a human had decided they were the same company; Phase 2a made that decision, so the id carries it. Cost: the id is positional (`--apply` renumbers 1..N by canonical name), so finishing the 190 pending pairs will change most manufacturer URLs. Accepted — nothing is public, and a content hash would lose the direct URL → `manufacturers` row traceability.
- 2026-08-06 — **The Phase 3a "this page matches one exact spelling" disclaimer is replaced, not deleted.** New copy says the merge happened *and* that it is unfinished: pairs nobody was confident about were left apart, so one company may still have several pages. Wording commits to the direction of error out loud — "we would rather show you two pages for one company than put one company's failures on another company's page."
- 2026-08-06 — **Placeholder records get no manufacturer page at all**, where Phase 3a gave them one carrying a "this is not a company" notice. The notice moved onto the record page, replacing the link. A page would imply an entity; there isn't one.
- 2026-08-06 — Manufacturer **search** matches the raw spelling **or** the canonical name (and MiniSearch indexes both), so a query typed as the merged company name reaches batches published under spellings that don't literally contain it. Displayed text stays the raw spelling — §1.1, the site mirrors what CDSCO published and never substitutes its own merged name for it.

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
- **Tailwind v4 silently breaks `@theme` nested inside `@media`.** A `@theme` block inside `@media (prefers-color-scheme: dark)` is hoisted and merged with the top-level one, so the dark values *replace* the light ones and the built CSS contains zero `prefers-color-scheme` rules — the site is permanently dark for everyone. Fix: keep one top-level `@theme` for light, override the plain custom properties in a normal `@media` + `:root` block. Caught by grepping the built CSS, not by looking at the page.
- **Headless Chrome clamps its viewport to ~500px wide.** `--window-size=375,900` produces a 375px-wide *screenshot* of a 500px-wide *layout*, so a perfectly fine responsive page looks badly clipped. Verified with a control page reporting `window.innerWidth` (=500). To check a real 375px viewport, load the page in a 375px-wide `<iframe>` — iframes get their own layout viewport.
- **5,107 distinct `manufacturer_raw` values for 6,155 records** — most manufacturers appear exactly once, and Zee Laboratories alone has 5 spellings differing only in punctuation and case. Until Phase 2 runs, every manufacturer page has to state that it matches one spelling, not one company.
- **The mojibake `?` from the portal reaches the UI.** Addresses render as "Paonta Sahib?173025" and reasons as "It fails the test ?Dissolution?". It is not safely reversible (the original could be an en-dash, a quote, or a hyphen), so it is displayed as published rather than guessed at.
- **`manufacturer_raw` is a full postal address, not a name**, so it is the single messiest field to display — up to 328 characters. Needs `overflow-wrap: anywhere` everywhere it appears or it forces horizontal scroll at 375px.
- **51 records have "Under Investigation" as the manufacturer**, which would otherwise render as a company page with 51 flagged batches. It gets its own explicit "This is not a company" notice.
- **The longest single failure reason is 994 characters** of narrative text — the design has to accommodate a paragraph, not a label, in the "CDSCO's exact wording" block.
- **Phase 1a's `manufacturer_unknown_placeholder` flag misses 27 records.** Its regex covers "under investigation / not known / unknown / n.a." only. `Not Mentioned` (11), `Not applicable` + `Not Applicable` (9), `Spurious` (5), `NIL,NIL NIL` and `NM` are all non-company placeholders carrying no flag. The resolver keeps the wider list; Phase 1a's flag was left alone as out of scope.
- **A company's name is 30% of `manufacturer_raw` and the split point is not punctuated.** "Gidsha Pharmaceuticals Plot No. 611 612, Mega GIDC…" has no comma between name and address. Cutting at the first comma *or* the first of ~40 address keywords *or* the first numeric token handles it; cutting on the comma alone leaves address text in the name and splits one company across several entities.
- **Certification boilerplate is inside the name field, inconsistently.** "Pharma Impex Laboratories Pvt. Ltd. (ISO 9001 : 2015 & WHO GMP Certified)" one month, plain the next; "Navkar Lifesciences WHO-GMP Certified Company" likewise. Left in, it splits one company in two.
- **Address keywords cut the name early and that is harmless but confusing** — "Bajaj Healthcare Ltd. R.S. No. 1818" cuts at `No`, leaving a stray "R.S." on the name. Dropping trailing single-character tokens fixes it. No name in the corpus ends in a bare letter.
- **The same company writes the same name against two addresses when it has two plants.** Unicure India Ltd (Noida, U.P. and Roorkee, Uttarakhand) is the clearest case: identical normalized name, different state, different PIN, address similarity near zero. 26 of the 205 review-band questions are this shape. Any scheme that weights address heavily will refuse to merge a multi-plant company.
- **Tricky pairs the reviewer has to actually think about** are one character apart: `Navkar Lifesciences` / `Navkar Lifescienses`, `Scott-Edil Pharmacia` / `Scott - Edil Pharmecia`, `Mascot Health Series` / `Mascot Health Services`, `Cosmas Pharma` / `Cosmas Pharmacls`. Some are CDSCO typos; `Deep Pharma` vs `Deepin Pharmaceuticals` (both Gujarat, different addresses, score 0.75) are genuinely different firms.
- **Union-find is transitive; similarity is not.** A~B and B~C merge A with C even when A and C would never have matched. `--cohesion` reports the weakest internal name match per cluster and the spot-check tool samples those first — a uniform sample is mostly obvious merges and would miss exactly the failure it is looking for.
- **Resolving manufacturers made the client index smaller, not bigger.** Phase 3a shipped 5,107 per-raw-string slugs (~68 chars each); replacing them with 1,856 canonical slugs plus a 5,107-int lookup cut the payload **297 KB → 255 KB brotli**. The raw-spelling table stays at full length — display must keep mirroring CDSCO's text — so all the saving came from the slug array.
- **A resolved manufacturer page has to render up to 67 alias strings of up to 328 characters each.** Left inline they push the batch list off the screen entirely, so the alias list is a `<details>` — open at ≤5 aliases, collapsed above. It is collapsed, never truncated or elided: the alias list is the only place a reader can audit the merge, so eliding it would defeat the point.
- **`manufacturer_raw` and `canonical_name` are different lengths of thing**, and the manufacturer page needed re-laying-out because of it. Phase 3a's `<h1>` was a 328-char name-plus-address blob; it is now a ~25-char company name, with the address demoted to a subtitle line. Same data, completely different visual weight.
- **Removing the placeholder manufacturer page moved a notice, it didn't delete one.** Phase 3a's "This is not a company" copy lived on `/manufacturer/under-investigation-<hash>/`. With no such page, the notice had to move to the 78 record pages themselves — otherwise the change would have silently dropped the one thing those records most needed to say.
- **Grep-counting rendered HTML lies about repeated elements.** Next's output is one long line, so `grep -c '<li class=...>'` returned 1 for a list of 48. Counting needs a real parse (or `findall` over the extracted block) — the first spot-check looked like a bug in the alias list when the list was fine.
