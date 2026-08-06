# MedCheck — Project Plan

**One line:** A searchable public database of medicines flagged as Not of Standard Quality (NSQ) or spurious by India's drug regulator, CDSCO.

**Why it exists:** CDSCO tests medicines pulled from real pharmacy shelves every month and publishes the failures. That data is public — and released as unsearchable monthly PDFs going back years. No Indian patient, pharmacist, or journalist can look up whether a specific medicine or batch has ever been flagged. MedCheck makes that possible.

**Status:** Greenfield. Started August 2026.

---

## 1. Non-negotiable design principles

These are not features. They are constraints. Violating any of them makes the project harmful instead of useful.

### 1.1 MedCheck is a mirror, not an accuser
Every record must reproduce CDSCO's own data faithfully and link to its source — CDSCO's own PDF alert or its public data portal. No editorial language. No "dangerous drug" labels. No inferred claims about a company's overall quality. We display what the regulator published, and nothing more.

### 1.2 Never advise anyone to stop taking medication
A flagged batch does not mean a patient should stop their treatment. Stopping cardiac, diabetes, epilepsy, or psychiatric medication on the basis of a website is a serious risk of real harm.

Required copy on every result page, non-dismissible:
> This batch was flagged by CDSCO. This does not mean you should stop taking your medicine. Show this page to your pharmacist or doctor and ask them.

### 1.3 A batch failure is not a product failure
CDSCO's own alerts state that a failure applies to the specific tested batch and does not imply other batches of the same product are affected. This must appear on every result, not buried in a footer.

### 1.4 Uncertainty is displayed, not hidden
If PDF parsing produced a low-confidence field, show it as uncertain rather than presenting a guess as fact. Same principle as the whole project: refusing to answer beats a confident wrong answer.

### 1.5 No user health data
MedCheck stores nothing about who searched for what. No accounts, no tracking of medicine searches tied to identity. Search analytics must be aggregate only.

---

## 2. Tech stack

Chosen for speed of shipping, not scale. Do not over-engineer.

| Layer | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Best PDF tooling |
| PDF parsing | `pdfplumber` (primary), `camelot` (fallback for ruled tables) | Handles digital PDFs well |
| OCR fallback | `pytesseract` + `pdf2image` | Needed for scanned months |
| Fuzzy matching | `rapidfuzz` | Faster than fuzzywuzzy, same API |
| Database | SQLite → Postgres later | File-based, zero setup, migrate only if needed |
| Backend | FastAPI | Minimal, fast, auto-docs |
| Frontend | Next.js + Tailwind | Static-friendly, good SEO — SEO matters a lot here |
| Hosting | Vercel (frontend) + Railway/Fly.io (API) | Free tiers sufficient |
| API fallback | Static pre-built JSON search index, bundled with the frontend, regenerated whenever the DB updates | Search still works (slightly stale) if the live API is down. No second live deployment — SQLite needs a persistent filesystem, which Vercel serverless doesn't give it |
| Scheduled scraping | GitHub Actions cron | Free, no server to maintain |

**Rule:** No feature gets added that requires a paid service before there are real users.

---

## 3. Data model

Flat and denormalized to start. Normalize only when the pain is real.

### 3.1 Core table: `nsq_records`

```
id                  TEXT PRIMARY KEY   -- deterministic, see docs/methodology.md for generation scheme
alert_month         TEXT               -- ISO: "2026-05"
alert_section       TEXT               -- "central_lab" | "state_lab" | "spurious"
drug_name_raw       TEXT               -- exactly as published
drug_name_clean     TEXT               -- normalized
active_ingredients  TEXT               -- JSON array, parsed where possible
dosage_form         TEXT               -- tablet / injection / syrup / device / cosmetic
batch_number        TEXT
mfg_date            TEXT               -- often partial: "2025-10"
expiry_date         TEXT
manufacturer_raw    TEXT               -- exactly as published
manufacturer_id     INTEGER            -- FK to manufacturers table, nullable
label_claim_disputed BOOLEAN           -- manufacturer claims batch isn't theirs
failure_reason_raw  TEXT               -- verbatim source text, may be multi-valued
failure_category    TEXT               -- JSON array — see 3.3; a record can fail more than one way
testing_lab         TEXT
state               TEXT               -- derived from lab or manufacturer address
source_url          TEXT               -- REQUIRED, never null — source PDF link or CDSCO portal query URL
source_type         TEXT               -- "pdf" | "portal_json"
source_page         INTEGER            -- nullable; PDF sources only
parse_confidence    REAL               -- 0.0-1.0
parse_flags         TEXT               -- JSON array of warnings
created_at          TIMESTAMP
```

### 3.2 `manufacturers`

```
id                  INTEGER PRIMARY KEY
canonical_name      TEXT
known_aliases       TEXT               -- JSON array of raw name variants
address_raw         TEXT
state               TEXT
first_seen_month    TEXT
total_flags         INTEGER            -- computed
```

### 3.3 `failure_category` — controlled vocabulary

Map messy free text into these buckets. Keep the raw text always.

- `assay` — active ingredient outside permissible limits
- `dissolution` — tablet doesn't dissolve correctly
- `disintegration`
- `sterility` — critical, injectables
- `microbial_contamination`
- `bacterial_endotoxins` — pyrogenic contamination, critical for injectables. Kept separate from `microbial_contamination`: endotoxins persist after the organisms that produced them are gone, so the two findings are not interchangeable
- `particulate_matter`
- `related_substances` — impurities
- `identification` — wrong or absent active ingredient
- `description_labelling`
- `ph` — outside the specified pH range
- `water_content` — moisture outside limits (Karl Fischer / water determination)
- `loss_on_drying` — total volatile content outside limits. Separate from `water_content`: LOD measures everything that evaporates, not water specifically
- `uniformity_of_weight` — individual units vary too much in weight
- `uniformity_of_dispersion` — dispersible tablets fail to disperse uniformly
- `density` — specific gravity, relative density, or weight per ml. One bucket because all three measure mass per unit volume; the source text records whichever the monograph specifies
- `extractable_volume` — deliverable/extractable volume or uniformity of volume, mainly injectables
- `clarity_of_solution` — appearance, clarity or colour of a reconstituted solution. Separate from `description_labelling`, which is about the dosage form and its labelling
- `dimensions` — physical measurements such as length or diameter, mainly devices
- `spurious` — declared fake
- `other` — always allowed, never force a match

**Rule:** if the mapper is under 0.8 confidence, assign `other` and flag it. Do not guess.

---

## 4. Phased build

### Phase 0 — Discovery (Days 1–3)

**Goal: understand the actual data before writing a parser.**

- [ ] Download every monthly NSQ alert PDF available from CDSCO. Start at the most recent and work backwards as far as they go.
- [ ] Build an inventory table: month, file size, page count, digital-text or scanned, number of table sections.
- [ ] Manually inspect 6 PDFs spread across different years. Structures change over time — find out where.
- [ ] Write down the column headers used in each era. Expect at least 2–3 distinct formats.
- [ ] Identify which months are scanned images (these need OCR and will be the worst).

**Deliverable:** `docs/pdf_inventory.md` — a table of every PDF and its structural type.

Do not skip this. Every hour here saves five in Phase 1.

---

### Phase 1 — Data ingestion (Week 1–3)

**Goal: get every available record into the database with honest confidence scores.**

Phase 0 found that CDSCO now publishes NSQ data as structured JSON (`docs/pdf_inventory.md` §0), covering every month Jan-2019 → present — more complete than the PDF corpus for that same range (no monthly PDF at all for 2020/2021; monthly PDFs stop after Jun-2025). That changes the plan: **JSON ingestion is Phase 1a and comes first.** PDF table parsing shrinks to Phase 1b — a smaller job scoped to what the JSON can't cover.

**Phase 1a — JSON ingestion (do this first)**
- [ ] `src/ingest/cdsco_json.py` — enumerate years/months via `reportingYears`/`publicReportingMonths`, fetch `filteredNsqDrugTable` per month and `viewPublicSpuriousDrugData`, cache raw responses locally (mirrors `src/fetch.py`'s caching pattern from Phase 0)
- [ ] `src/db.py` — SQLite schema per §3, idempotent (`CREATE TABLE IF NOT EXISTS`)
- [ ] `src/normalize.py` — map raw JSON fields → `nsq_records` (mapping in `docs/pdf_inventory.md` §0); split multi-valued `NSQ Result` text into the `failure_category` array; normalize inconsistent date formats
- [ ] `src/validate.py` — sanity rules (expiry after mfg date, batch number plausible, required fields non-empty); violations become `parse_flags`, never a silently dropped record
- [ ] Decide and document a stable `id` generation scheme for JSON-sourced records (the sample record has no obvious unique id field — check for one; if absent, hash month + batch + drug + manufacturer, and note the collision risk from §5.4: batch numbers are not unique)
- [ ] Cross-validate: for one month present in both sources (Jun-2025 or Jun-2024), compare JSON-derived records against the Phase 0 PDF dump — record counts and spot-checked field values

**Phase 1b — Historical PDF backfill (deferred, small scope)**
- [ ] `src/parse/base.py`, `router.py`, and parsers for the pre-2019 layouts only (Era A vaccine alerts, Era B composite list) — the only ranges the JSON API doesn't cover
- [ ] OCR (`src/parse/ocr.py`) — deprioritized: Phase 0 found only 2 scanned PDFs in the whole corpus, both single-page non-tabular notices
- Do not start this until Phase 1a is loaded and there's a working database to show for it

**Validation approach:** cross-validation against source PDFs (Phase 1a) doubles as the gold-standard check for months where both exist; Phase 1b gets its own hand-transcribed gold CSV once it starts, same method as originally planned. Track findings in `docs/parser_accuracy.md`.

**Target:** 0% invented-data rate — a missing field comes out empty, never guessed. (The >95%/>80% digital/OCR accuracy targets apply to Phase 1b; Phase 1a's data is already structured at the source.)

---

### Phase 2 — Entity resolution (Week 3–4)

**The genuinely hard problem.** Manufacturer names appear inconsistently across years: "M/s. Gidsha Pharmaceuticals", "Gidsha Pharma Pvt Ltd", "GIDSHA PHARMACEUTICALS PVT. LTD." Split into 2a/2b since manufacturer resolution is what's actually blocking things (Phase 3a shipped with 5,107 unmerged manufacturer pages) and drug-name resolution isn't blocking anything yet.

**Phase 2a — Manufacturers (do this first)**
- [ ] Normalizer: strip "M/s.", legal suffixes, punctuation, casing
- [ ] Blocking: group candidates by first token + state to avoid O(n²)
- [ ] `rapidfuzz` similarity within blocks, threshold tuned by hand
- [ ] Address as a secondary signal — same address is strong evidence
- [ ] **Human review queue**: anything in the 0.75–0.92 similarity band goes to a review pass. You approve or reject. Since Phase 3a is fully static with no backend, this is a CLI/offline step, not a web UI.
- [ ] Store every merge decision in a log so it's auditable and reversible

**Phase 2b — Drug names (deferred)**
- [ ] Same approach, but be more conservative — merging two different drugs is worse than leaving duplicates

**Rule:** never auto-merge above the review band without spot-checking a sample. A wrongly-merged manufacturer means you'd be attributing another company's failures to them. That's a real reputational harm.

---

### Phase 3 — Search site (Week 4–6)

Boring and fast beats clever and slow. Entity resolution (Phase 2) hasn't run yet, so this splits into a data-ready MVP now and a follow-up once identity/i18n work lands.

**Phase 3a — Static-data search site (do this first)**
- [ ] Search by drug name (fuzzy, tolerant of misspelling)
- [ ] Search by batch number (exact)
- [ ] Search by manufacturer — matches on `manufacturer_raw` text; not merged/canonical yet (Phase 2 hasn't run), so near-duplicate names show as separate results. Say so, don't hide it.
- [ ] Result card: drug, batch, manufacturer, month, failure reason in plain language, source link (PDF or CDSCO portal record), mandatory safety copy
- [ ] "No results" page that clearly says: not found means not flagged in our data, not that it's verified safe
- [ ] Manufacturer page: all flagged batches under that exact `manufacturer_raw` string, chronological
- [ ] Mobile-first. Most Indian users will be on a phone — keep the initial payload light (see below).
- [ ] No login. No signup. No friction.
- [ ] Data source: a static pre-built JSON export from `data/medcheck.db` (this is the same fallback-index artifact from §2's API fallback row — build it once, use it for both). No live FastAPI needed for this ticket; avoids standing up paid hosting before there's demand.

**Plain-language failure explanations** — write these by hand, one per category (21 total, see §3.3):
> **Dissolution failure** — The tablet did not break down properly in lab testing. This can mean the body absorbs less of the medicine than intended.

Keep them factual and non-alarming.

**Phase 3b — deferred**
- [ ] Hindi translation of all interface copy and failure-reason explanations. Ship English first; structure copy so i18n slots in later.
- [ ] Swap the static export for a live FastAPI once Phase 5's public API is needed, or once data needs to update without a redeploy
- [ ] Re-point manufacturer pages/search at resolved entities once Phase 2 lands

---

### Phase 4 — The analysis (Week 6–8)

**This is the part that makes the project matter.** Once every alert is in one database, ask questions nobody has been able to ask.

- [ ] Total flagged batches across the full time range
- [ ] Failures by category — which failure types dominate?
- [ ] Repeat manufacturers — what share of flags come from what share of companies?
- [ ] Therapeutic categories — are antibiotics over-represented? (Relevant to antimicrobial resistance.)
- [ ] Central vs state lab detection patterns — do they find different things?
- [ ] Trend over time — is the flag rate rising, falling, or is testing volume just changing?
- [ ] Geographic clustering by manufacturing state

**Write it up properly**, with:
- Methodology section — how PDFs were parsed, what the accuracy is
- Explicit limitations — OCR error rates, unresolved entities, sampling bias (CDSCO doesn't test randomly, so this is NOT a population failure rate and you must say so loudly)
- Every number reproducible from the public database

**Publish the underlying dataset as CSV under an open licence.** That single act turns this from a project into infrastructure, and it's what makes journalists and researchers cite you.

---

### Phase 5 — Automation & maintenance (Week 8+)

- [ ] GitHub Action: monthly check for new CDSCO alerts, auto-parse, open a PR with the new records for you to review before merge
- [ ] Never auto-publish unreviewed parses
- [ ] Simple email alert: users can subscribe to a manufacturer or drug name (store only email + query string, nothing else)
- [ ] Public API endpoint, rate-limited, so others can build on it

---

## 5. Known hard problems

Write these down so they don't surprise you.

1. **PDF layout drift.** Columns change across years. Solved by the layout router, but expect to add parsers as you go back further. Only relevant to Phase 1b now (pre-2019 backfill) — 2019-onward comes from the JSON portal instead.
2. **Scanned PDFs.** Some months are images. OCR accuracy on Indian pharmaceutical names with unusual spellings will be poor. Flag heavily, consider hand-correcting the worst.
3. **Entity resolution.** Covered in Phase 2. The hardest correctness problem in the project.
4. **Batch numbers are not unique.** Different manufacturers reuse batch formats. Never treat batch number alone as a key.
5. **Disputed entries.** Some alerts note that the named manufacturer denies making the batch — it's a counterfeit using their label. Displaying this wrongly would defame a legitimate company. Parse and display `label_claim_disputed` prominently.
6. **Selection bias.** CDSCO's sampling is not random. Any rate you compute is a rate *among tested samples*, never a market-wide failure rate. State this everywhere you show a percentage.
7. **Site availability.** cdsco.gov.in is occasionally slow or down. Cache aggressively, never depend on live fetches for user-facing search. Same principle applies to our own API: the frontend ships a static pre-built JSON fallback index so search keeps working if Railway/Fly.io is down.
8. **The JSON portal is undocumented.** No official spec, could change shape or disappear without notice. Cache every raw response before normalizing it, and keep the PDF ingestion path alive as a fallback/cross-check rather than deleting it once JSON ingestion works.

---

## 6. Explicitly out of scope (for now)

Scope control matters more than features. Do not build:

- Any recommendation about what medicine to take instead
- User-submitted reports of bad medicines (moderation burden, defamation risk)
- Price comparison
- Pharmacy locator
- Anything requiring user accounts
- Mobile apps — the mobile web is enough
- Coverage of countries other than India

---

## 7. Success criteria

**Minimum (project is real):**
- Every available monthly alert parsed into one database
- Public search site live, working on mobile
- Parser accuracy documented against a hand-built gold standard

**Good (project matters):**
- Open dataset published
- Written analysis with reproducible findings
- Used by people who aren't you — measured by aggregate search volume

**Excellent (project has legs):**
- Cited by a journalist, researcher, or health organisation
- Someone else builds on the API
- CDSCO publishes structured data because this made the gap obvious

---

## 8. Repo structure

```
medcheck/
├── data/
│   ├── pdfs/              # downloaded source PDFs (gitignored, large)
│   ├── raw/               # parser output, JSON per month
│   ├── gold/              # hand-transcribed validation sets
│   └── medcheck.db        # SQLite
├── src/
│   ├── fetch.py           # Phase 0/1b — PDF download & cache
│   ├── ingest/
│   │   └── cdsco_json.py  # Phase 1a — JSON portal ingestion (primary path)
│   ├── normalize.py       # Phase 1a — raw JSON → nsq_records
│   ├── parse/             # Phase 1b — pre-2019 PDF layouts only (deferred)
│   │   ├── base.py
│   │   ├── router.py
│   │   ├── layout_a.py
│   │   ├── layout_b.py
│   │   └── ocr.py
│   ├── resolve/
│   │   ├── manufacturers.py
│   │   └── drugs.py
│   ├── validate.py
│   └── db.py
├── api/                   # FastAPI
├── web/                   # Next.js
├── analysis/              # notebooks + writeup
├── docs/
│   ├── pdf_inventory.md
│   ├── parser_accuracy.md
│   └── methodology.md
└── README.md
```

---

## 9. First session checklist

1. `git init`, create the structure above
2. Download 8–10 recent NSQ PDFs into `data/pdfs/`
3. Write `src/fetch.py` to automate further downloads
4. Open 3 PDFs manually, document their structure in `docs/pdf_inventory.md`
5. Write a throwaway script that dumps `pdfplumber.extract_tables()` output for one PDF — just look at it
6. Only then start `src/parse/layout_a.py`

**Do not write the website first.** The parser is the project. Everything else is a thin layer on top.
