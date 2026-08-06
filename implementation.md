# Current Task — Phase 3b (partial): Re-point web/ at Resolved Manufacturer Entities

**Read first:** `CLAUDE.md` (current status + decisions — the Phase 2a numbers below are already applied to `data/medcheck.db`), `plan.md` §3.2 (`manufacturers` schema), §4 Phase 3b ("re-point manufacturer pages/search at resolved entities once Phase 2 lands" — that line is this ticket).

## What changed under you

Phase 2a is done and applied. `data/medcheck.db` now has:
- `manufacturers` table populated: **1,856 canonical entities**
- `manufacturer_id` backfilled on **6,077 of 6,155** records
- The 78 unlinked records are the `manufacturer_unknown_placeholder` ones (e.g. `"Under Investigation"`) — deliberately left with `manufacturer_id = NULL`, never resolved into a company

Resolution is **partial by design**: 15 of 205 ambiguous pairs were human-approved and merged; 190 remain undecided and are correctly treated as separate entities for now (safe default, not a bug). More may get merged later if the review resumes — this ticket's output should tolerate that without a rewrite.

## Task

1. **`scripts/export_static.py`** — rework the manufacturer grouping to key off `manufacturer_id` / the `manufacturers` table instead of raw `manufacturer_raw` text:
   - One page per canonical manufacturer (`manufacturers.id`), not per raw string
   - Each manufacturer page should list its `known_aliases` (the raw spellings that collapsed into it) — this is the transparency/audit trail, keep it visible, don't hide the messiness
   - Records with `manufacturer_id IS NULL` (the placeholder ones) don't get a manufacturer page at all — on their own record card, show the existing "This is not a company" notice inline instead of a broken/missing link
   - Client search index's manufacturer table: dedupe on `manufacturer_id`, not raw string

2. **`web/` manufacturer pages**:
   - URL/slug scheme changes from per-raw-string to per-`manufacturer_id` (or canonical name + id, your call) — this **will** break existing manufacturer page URLs from Phase 3a; that's expected and fine, nothing is live/public yet
   - Update or remove the Phase 3a disclaimer ("this matches one spelling, not one company") — it's no longer accurate for merged entities, but a lighter note is still honest: resolution is real but partial, so a small number of near-duplicate manufacturer pages may still exist for the 190 undecided pairs
   - List all flagged batches across every alias, chronological, same as before

3. **Search** — manufacturer search should now match against canonical names/aliases and route to the one canonical page, not surface duplicate raw-string results for the same real company

4. **Rebuild and verify**: page count should drop from 11,268 toward roughly **1,856 manufacturer pages + 6,155 record pages + fixed pages** (~8,000ish, not exact — confirm the real number after rebuild). Spot-check: Zee Laboratories, Jackson Laboratories, Unicure — these had the largest alias collapses in Phase 2a — render as single pages with all aliases and batches present.

## Explicit boundary — do NOT do yet

- No Hindi/i18n (still deferred, rest of Phase 3b)
- No live FastAPI (still deferred, rest of Phase 3b)
- No Phase 2b (drug-name resolution) — out of scope here
- No further manufacturer merging or re-running the resolution pipeline — this ticket only *consumes* what Phase 2a already produced

## Done when

- [ ] `scripts/export_static.py` groups by `manufacturer_id`, not raw string
- [ ] Manufacturer page count matches the `manufacturers` table count (1,856), plus placeholder records handled without a broken page
- [ ] `known_aliases` visible on each manufacturer page
- [ ] Search routes duplicate-spelling queries to one canonical page
- [ ] Spot-checked: a merged manufacturer (e.g. Zee) shows all its aliases and combined batch history correctly
- [ ] Spot-checked: a placeholder record (e.g. `"Under Investigation"`) still shows its existing non-company notice, no broken link
- [ ] `npm run test:search` (or equivalent) updated for the new manufacturer shape and passing
- [ ] `CLAUDE.md` updated: Current Status, Decisions Log, Key Learnings

## Before ending the session

Update `CLAUDE.md`:
- **Current Status** → new page count, confirm which spot-checks passed
- **Decisions Log** → slug scheme chosen, how the "partial resolution" disclaimer was worded
- **Key Learnings** → anything about the resolved data that was awkward to render (e.g. a manufacturer with an unusually large alias list, any placeholder edge case)

Do not start Hindi translation, live API work, or Phase 2b even if it feels like the natural next step — those are separate tickets.
