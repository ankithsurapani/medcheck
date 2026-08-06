# Current Task — Phase 4: The Analysis

**Read first:** `CLAUDE.md` (current status — especially the Phase 2a partial-resolution numbers and Phase 1a data-quality caveats you'll need to cite), `plan.md` §1.4 (uncertainty shown, not hidden), §5.6 (sampling bias — CDSCO's testing isn't random, so nothing here is a population failure rate), §4 Phase 4 (now annotated with the constraints below).

## Why this phase, now

Everything it needs is in place: 6,155 categorized records (21 failure buckets, `other` down to 4.4%), manufacturer identity resolved (partial — 1,856 canonical entities, 190 pairs still undecided). This is `plan.md`'s own "the part that makes the project matter" — turning the database into findings nobody could previously ask, and publishing the dataset openly is what makes this infrastructure rather than a demo.

## Task

1. **`analysis/`** — Python script(s) or notebook computing, directly from `data/medcheck.db`:
   - Total flagged batches, by year and by month
   - Failures by category (all 21 buckets + `other`, with its share)
   - Repeat manufacturers: distribution of flags across the 1,856 resolved manufacturers — top N, concentration (e.g. what share of flags come from what share of companies). **Must state the resolution is partial** (190 review pairs still undecided) — this analysis is a lower bound on real concentration, not the final number.
   - Central vs state lab detection patterns — **with the caveat from Phase 1a**: the portal and PDFs disagreed on this for 27/184 Jun-2025 records, so treat `alert_section` as informative, not authoritative.
   - Trend over time — **flag-count trend only.** There is no testing-volume denominator anywhere in the data, so do not phrase this as a rate. Report counts by month/year, and flag the Aug-2025 CDSCO portal migration (Phase 1a) as a possible reporting-behavior discontinuity, not necessarily a real trend in drug quality.
   - Geographic clustering by manufacturing state — **state is populated for ~58% of records** (Phase 1a). Report coverage alongside the clustering, don't silently analyze only the 58% as if it were the whole picture.
   - Therapeutic categories / antibiotics over-representation — **conditional.** The schema has no therapeutic classification field. If there's a defensible way to derive one (e.g. matching `drug_name_clean` against a public, citable drug-class reference) without inventing data, attempt it and cite the source. If not, write up *why this question can't be answered with current data* instead of forcing a guess — that's a valid, honest deliverable per §1.4.

2. **Write it up** in `analysis/FINDINGS.md`:
   - **Methodology** — how records were ingested (JSON-first, Phase 1a), categorized (Phase 1a's 21-bucket vocabulary), and entity-resolved (Phase 2a, partial)
   - **Explicit limitations section** — sampling bias (CDSCO's testing is not random — nothing here is a population failure rate, say so loudly), partial manufacturer resolution, `alert_section` unreliability, 58% state coverage, no rate denominator for trends, and the therapeutic-category gap if unresolved
   - Every number should be reproducible — link each finding to the script/query that produced it

3. **Publish the dataset** — export `nsq_records` (joined with resolved `manufacturers.canonical_name` where available) as CSV. Recommend **CC0** (public-domain dedication) as the license — it removes reuse friction entirely, which is the whole point of "this is what makes journalists and researchers cite you." Include a short header/companion note describing the columns and pointing back to `analysis/FINDINGS.md` for the limitations that must travel with the data.

## Explicit boundary — do NOT do yet

- No new web pages surfacing these findings on `web/` — this ticket produces the analysis and dataset, not a UI for them. That can be a follow-up ticket once there's something worth designing around.
- Don't force the therapeutic-category question if it requires data we don't have — document the gap, don't approximate with an invented mapping.
- Don't phrase any trend as a rate — count-based framing only, and the sampling-bias disclaimer travels with every percentage shown (non-negotiable, not optional).

## Done when

- [ ] All seven analysis questions computed (or, for therapeutic categories, explicitly documented as unanswerable with current data and why)
- [ ] `analysis/FINDINGS.md` exists with methodology, explicit limitations, and reproducible numbers
- [ ] Dataset exported as CSV under CC0 (or documented reasoning if a different license was chosen instead)
- [ ] Every percentage/rate in the write-up carries its caveat inline, not just in a limitations footnote
- [ ] `CLAUDE.md` updated: Current Status, Decisions Log, Key Learnings

## Before ending the session

Update `CLAUDE.md`:
- **Current Status** → headline numbers from the analysis, dataset export location
- **Decisions Log** → license chosen, how the therapeutic-category question was resolved (answered or documented as a gap)
- **Key Learnings** → anything surprising in the findings themselves, any data quality issue that only became visible once you tried to aggregate across the whole dataset

Do not start building a findings/insights page on `web/`, Phase 2b, or the rest of Phase 3b (Hindi, live API) even if it feels like the natural next step — those are separate tickets.
