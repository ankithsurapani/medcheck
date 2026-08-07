# MedCheck — Project Memory

Searchable public database of medicines CDSCO flagged as Not of Standard Quality (NSQ) or spurious. Full spec: `plan.md`. Current task: `implementation.md`.

> **Builder:** update *Current Status* and *Key Learnings* below, and append decisions to [`docs/decisions.md`](docs/decisions.md), whenever you make a decision or hit something worth remembering. One line per entry. Don't touch `plan.md`.

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
- Manufacturer slug scheme: `<canonical-name-slug>-<cluster-hash>` (see the post-launch hardening section below — it was `-m<manufacturers.id>` until 2026-08-07)
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

**Phase 4 (the analysis) — complete.** All seven questions computed, written up, dataset published under CC0.

- `analysis/analyse.py` — one function per question (`q1_volume` … `q7_classes`), `--json` → `analysis/results.json`, `--sql q3` prints any question's query. FINDINGS.md cites the function beside every figure; no number is hand-typed
- `analysis/drug_classes.py` — WHO INN stem matcher (2018 stem book, cited), `python analysis/drug_classes.py` prints every word each stem matched
- `analysis/FINDINGS.md` — findings, methodology, 10-row limitations table, reproduction commands
- `analysis/dataset/` — `medcheck_nsq_records.csv` (6,155 rows × 21 cols, 2.8 MB) + `README.md` + `LICENSE` (**CC0 1.0**)
- `tests/test_drug_classes.py` — 41 checks, all passing

**Headline numbers** (all shares are of *flagged batches*, never a failure rate — CDSCO doesn't sample randomly and publishes no denominator):
- **6,155 batches, 90 months, 4.78× growth 2019 → 2025** (last complete year). Counts, not rates.
- **64.1% failed assay or dissolution** (potency); only **12.0%** are contamination-type. The published quality problem is medicines that may not work, not medicines that are dangerous.
- **13.5% of companies hold 54.5% of flags** — but **52.9% appear exactly once** and the median company has 1. Long tail with a heavy head, not a few bad actors.
- **82.9% state coverage** (was 58.1% before the PIN fallback); Himachal Pradesh is 33.6% of records *with* a state and **27.9% of all** records.
- **19.4% name an anti-infective** by INN stem. Over-representation is **not answerable** — no denominator.

**Lab labelling fix — complete.** `alert_section` was unusable: CDSCO files 13 of 239 laboratories under *both* `central_lab` and `state_lab`. `lab_type` is now derived from the laboratory's identity instead.

- `src/resolve/labs.py` — registry of CDSCO's own laboratories, each entry citing a source; `python src/resolve/labs.py` prints the full classification + every disagreement
- `src/db.py` gained `lab_type` + `lab_name_canonical` and a `migrate()` step (CREATE TABLE IF NOT EXISTS won't alter an existing table)
- `tests/test_labs.py` — 90 checks, all passing
- **Corrected split: 3,860 central (62.7%) / 2,272 state (36.9%) / 23 unknown (0.4%)** — CDSCO's published field said 49.2% / 50.0%, understating central-lab testing by **831 records**
- **857 records** carry an `alert_section_disputed` flag; `alert_section` itself is untouched (§1.1)
- Phase 4 q4 now does the real comparison: central labs report **9.4% particulate matter vs 0.7%** for state labs, plus more related-substances and clarity failures — the instrument-heavy injectable tests. State labs skew to description/labelling (19.7% vs 15.0%) and `other` (7.0% vs 2.7%). Capability difference, not diligence.
- Propagated end to end: normalize → resolve → export_static → 8,017-page rebuild → analysis → CC0 dataset (2 new columns)

**MedCheck is live.** GitHub: https://github.com/ankithsurapani/medcheck (public). Site: https://web-navy-three-91.vercel.app/ (Vercel, static export, free tier).

- Repo was previously local-only, no remote. Created public via `gh repo create`, pushed all history — clean secrets scan first (no `.env`/keys tracked).
- Deploy hit two real blockers, both fixed before going live, not worked around: (1) Vercel's file-count cap (8,017 pages = 16k+ files) — solved with `vercel --archive=tgz`; (2) Vercel refused the build outright over a **critical (CVSS 10) Next.js RCE** in the pinned `15.5.4` (`GHSA-9qr9-h5gf-34mp`, react flight protocol). Bumped to `15.5.22` (latest 15.5.x patch, no major-version risk), re-ran `test:search` (29/29 still pass), rebuilt, redeployed clean.
- 3 remaining `npm audit` findings (`postcss`/`sharp`, high severity) are build-tooling only — `images.unoptimized: true` means `sharp` isn't exercised, and nothing processes untrusted CSS/images. Fixing them needs Next.js 16 (breaking), deliberately not forced through mid-deploy — logged as a follow-up, not silently ignored.
- The per-deployment Vercel URL (e.g. `web-powrksadx-...`) redirects to Vercel SSO — that's normal per-deploy protection, not a public-access problem. The **stable production alias** (`web-navy-three-91.vercel.app`) is the real public URL and was verified 200 OK on `/`, a record page, a manufacturer page, and the search index asset.
- README.md updated — was stuck describing "Phase 1a complete," now points at the live site, dataset, and findings.

**Post-launch hardening — Ticket 1 (content-derived manufacturer slugs) — complete.**

Manufacturer URLs no longer move when an unrelated merge decision is made.

- `scripts/export_static.py`: slug is now `<canonical-name-slug>-<sha1(sorted known_aliases)[:8]>`, was `<canonical-name-slug>-m<manufacturers.id>`. `cluster_hash()` + `manufacturer_slug(canonical_name, members)`. Change is fully contained in that file — web code treats slugs as opaque lookup keys, and `manufacturers.id` (the SQL join key) is untouched and still positional
- **The bug, measured:** approving one pending review pair (two Hetero Labs Limited clusters) changed **1,207 of 1,856** public URLs under the positional scheme. Under the hash: **2 removed, 1 added, 1,854 byte-identical**
- Uniqueness is asserted over the full export, not hoped for — `SLUG_HASH_LEN = 8`, export exits non-zero on a collision
- Determinism verified: two consecutive `--apply --allow-pending` + re-export cycles with no decisions changed produce identical slugs for all 1,856
- Stability check ran on scratch copies of the DB *and* the merge log, so no review decision was actually recorded — the 190 pairs are still 190 pending
- Rebuild clean: 8,016 HTML pages, 0 missing manufacturer or record pages, 78 records with no manufacturer link (unchanged). `npm run test:search` 29/29
- `docs/entity_resolution.md` has the scheme and why it replaced the positional one

**Post-launch hardening — Ticket 2 (state coverage via PIN prefixes) — complete.**

**State coverage 58.1% → 82.9%** (3,576 of 6,155 → 5,104 of 6,155).

- `src/resolve/pin_state.py` — **generated**, not hand-typed: `scripts/build_pin_table.py --csv <pincode.csv>` derives it from India Post's *All India Pincode Directory*. A prefix is written only if **every** post office under it is in one state. 51 two-digit prefixes, 104 three-digit overrides, 18 sorting districts deliberately unmapped. `python src/resolve/pin_state.py` prints the table and everything it refuses
- `derive_state()` gained step 4, strictly after the existing checks: explicit field → state name in address → abbreviation → **last plausible PIN**. It never overrides, and it never resolves a `state_ambiguous` address
- **1,528 records** got a state from a PIN, each flagged `state_derived_from_pin:<pin>`. **181** hit a boundary-straddling prefix (`state_ambiguous_pin`), **827** have no PIN and no state name, **43** name two states — all four reported separately, none guessed
- **Shown, not just flagged (§1.4):** the record page prints "…the state the address's PIN code (248197) belongs to, not something the regulator wrote down" beside the value. A name-matched state shows no such note; verified on rendered HTML for all three cases
- Propagated end to end: normalize → resolve `--apply --allow-pending` → export_static → 8,016-page rebuild → `analyse.py --json` → CC0 dataset (2.8 → 3.1 MB; no new column — the flags ride in `parse_flags`, which was already published)
- `tests/test_pin_state.py` — **44 checks**, all passing. Every other suite still passes (categorise 59, labs 90, resolve 45, drug classes 41, `test:search` 29)
- `analysis/FINDINGS.md` §5 rewritten with the two-source derivation; limitations table gained rows 4b and 4c. `docs/methodology.md` §5a. `web/app/about/page.tsx` updated
- **Ticket 1 proved itself here:** a full normalize + re-apply + re-export moved **zero** manufacturer URLs. Under the positional scheme this pipeline run would have been a mass rename

Open / needs a planner decision:
- ~~190 review-band pairs undecided *and* slugs positional~~ — the slug half is **fixed** (above); resuming the 190-pair review is now safe and is still its own ticket.
- **`manufacturers.state` carries no provenance.** It is a majority vote across a company's records, some of which are now PIN-derived, and the manufacturer page shows it uncaveated. It was uncaveated before this ticket too, so nothing regressed — but it is the one place a PIN-derived state renders without saying so.
- **827 records still have no state and no PIN.** PIN lookup cannot help them; they need real address parsing (city/district → state), which is Phase 2 work.
- **The 3 remaining build-tooling vulnerabilities** (`postcss`/`sharp`) need a Next.js 16 major-version upgrade to clear — real work, not urgent (build-time only, no untrusted input processed), but shouldn't sit forever on a public repo.
- **Vercel project is named `web`** (generic) — the URL slug `web-navy-three-91` doesn't say "MedCheck." A custom domain or project rename is cosmetic, not urgent.
- ~~`alert_section` unreliability~~ — **fixed**, see the lab-labelling section above.
- **Search index is 255 KB brotli** (down from 297 KB). Lazy-loaded on idle/focus so the page is usable first, but still the biggest cost on a slow connection. A later Phase 3b option: server-side search, or a two-tier prefix index.
- Rest of Phase 3b (Hindi/i18n, live FastAPI) still deferred.
- **`alert_section` is unreliable.** The portal and the PDFs disagree on central-vs-state for 27 of 184 Jun-2025 records. Phase 4's "central vs state lab detection patterns" analysis needs this caveat.
- ~~State coverage is 58%~~ — **fixed**, 82.9% via the PIN fallback (Ticket 2 above).
- Phase 1b (pre-2019 PDF backfill) not started, per ticket boundary.
- Phase 2b (drug-name resolution) deferred — nothing depends on it yet.

## Decisions log

Moved to [`docs/decisions.md`](docs/decisions.md) — 73 entries of "why is it this
way", read on demand rather than loaded into every session. Append new ones there.

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
- **The published failure profile is potency, not contamination** — 64.1% of flagged batches failed assay or dissolution, only 12.0% failed sterility/microbial/endotoxin/particulate. The intuition that a "flagged medicine" list is mostly contamination is wrong by a factor of five. Both figures are set unions, not sums: adding category counts double-counts the 1,355 records with more than one category.
- **Manufacturer flags are far less concentrated than the top-20 table suggests.** 52.9% of resolved companies appear exactly once and the median company has a single flagged batch. The "few repeat offenders" framing survives only if you don't look past the head of the distribution.
- **`alert_section` is unreliable at a scale only visible in aggregate.** Per-record it looks fine; grouping by `testing_lab` shows the same lab filed both ways — RDTL Guwahati 202 central / 571 state. The Phase 1a caveat (27 of 184 in one month) understated it by an order of magnitude, and nothing short of a full-corpus group-by would have shown that.
- **2020 and 2021 are *below* 2019** (319 and 345 vs 403) — the only dip in an otherwise rising series, and it is the pandemic. A trend line drawn through it without comment would read as "Indian medicines improved in 2020".
- **August 2025 is a local trough (97/month) between a 131/month year and a 173/month year.** That is the shape of a publishing handover, not of drug quality. Any before/after comparison spanning the portal migration is measuring CDSCO's workflow.
- **A bare `azole` drug-name stem captures 367 proton-pump-inhibitor records** (pantoprazole, rabeprazole, omeprazole, esomeprazole) and would have turned them into "antibiotics" — the most dangerous available false positive, because the resulting finding looks entirely plausible. Bare `sulfa`/`sulpha` similarly captures every sulphate salt. Both are pinned open by negative cases in `tests/test_drug_classes.py`.
- **WHO's `-mycin` stem marks the source organism (Streptomyces), not the activity**, so it also catches dactinomycin (a cytotoxic antineoplastic) and natamycin (an antifungal). Stems encode chemistry or origin; mapping them to therapeutic effect needs named exceptions and an admission that the mapping is imperfect.
- **The same laboratory is filed under both `central_lab` and `state_lab`, and the split drifts by year rather than switching.** RDTL Guwahati is mostly "State lab" 2019–2023 and mostly "CDSCO lab" 2024–2025. A clean switch would have meant a convention change with a splittable date; the drift means it is data entry, and no date-based rule could have fixed it.
- **Correcting `alert_section` moved the central/state split from 49.2/50.0 to 62.7/36.9.** The published field understated CDSCO's own laboratories by 831 records — a near-even-looking split that was actually 5:3. Any "central vs state" analysis built on the published field was measuring CDSCO's filing habits.
- **Central and state labs find different *kinds* of defect, and it tracks equipment.** Central labs report particulate matter at 9.4% vs 0.7%, related substances 4.5% vs 0.6%, clarity of solution 2.4% vs 0.0% — particulate counting and chromatography. State labs report description/labelling more (19.7% vs 15.0%) and `other` more (7.0% vs 2.7%). Where a defect gets caught depends on who has the instrument.
- **Re-running `src/normalize.py` wipes `manufacturer_id`** — `_base_record` sets it to None, so Phase 2a's resolution has to be re-applied (`--apply --allow-pending`) after any normalize run. Idempotent and safe, but silent if forgotten: the site would rebuild with 6,155 unlinked records.
- **A positional id in a public URL is a link-rot generator, and the blast radius is much bigger than it looks.** `manufacturers.id` renumbers `1..N` in canonical-name order, so approving *one* merge near the top of the alphabet shifted **1,207 of 1,856** manufacturer URLs — not the two rows involved. The scheme looked fine for a year of local work and was only wrong once something outside the repo could hold a link.
- **The right hash input was already being computed.** `apply()` builds `sorted(members)` and serialises it to `known_aliases` before writing the row; the slug fix reads that back. Cluster membership is the only property invariant under re-sorting — canonical name isn't (ties break on record counts), address isn't (`primary` is picked by record count), and the id is the thing being replaced.
- **"Only the touched cluster changes" has to be tested by actually simulating a merge**, not by reasoning about the hash. Doing it needs a scratch copy of the merge log as well as the DB — `MERGE_LOG` is module-level in `src/resolve/manufacturers.py`, and `log_append` is append-only by design, so a check that forgot to redirect it would have permanently recorded a review decision nobody made.
- **Two thirds of the state-less records were one regex away from an answer.** 1,745 of the 2,579 records with no state ended in a plausible PIN code. The 58% coverage figure sat in CLAUDE.md for two phases reading like an inherent limit of messy addresses; it was mostly an unimplemented lookup.
- **India Post's sorting districts predate India's states.** The first three PIN digits identify a sorting district, and the 2000 reorganisation (Uttarakhand, Jharkhand, Chhattisgarh) cut new state lines *through* districts already drawn. 247xxx is Saharanpur (Uttar Pradesh) **and** Roorkee (Uttarakhand); 262xxx is a near-even Uttar Pradesh/Uttarakhand split; 81x and 82x each straddle Bihar/Jharkhand. Eighteen districts are like this, and no amount of prefix precision fixes them — going to four digits costs 80 more table entries and resolves **9 more records**, because 247 is still mixed at 2476.
- **Deriving the table from India Post's own directory made it 51 + 104 entries with zero judgement calls in it.** Written from memory it would have been a list of plausible-looking guesses at exactly the boundaries that are actually contested. Purity is measurable: count post offices per prefix, and write the prefix down only if they all agree.
- **An authoritative source can be authoritative and still be out of date.** The directory files 194xxx (Leh, Kargil) under Jammu & Kashmir because it predates the 2019 reorganisation that made Ladakh a UT. A generator can measure purity but cannot notice that its input is older than a border — that entry has to be hand-maintained, and is the only hand-maintained thing in the generated module.
- **`?` in an address does not break PIN extraction, but a leading plot number would.** The portal's mangled punctuation gives "Amritsar ? 143001", which a trailing-six-digit regex handles fine. The real trap is "Plot No. 611612, ... Ahmedabad-382445" — taking the *first* six-digit run reads that address as Uttar Pradesh. Last match wins, and the negative lookarounds keep it out of longer digit runs.
- **A flag in the database is tracking, not showing.** §1.4 says uncertainty is *shown*. `state_derived_from_pin` was in `parse_flags` and in the exported record and the page still rendered a bare "Uttarakhand", identical to a state CDSCO wrote down. Getting it visible needed a UI change too — a `note` prop on the field component, since the existing `hint` only rendered when a field was *missing*.
