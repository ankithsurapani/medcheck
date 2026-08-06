# Current Task — Phase 2a: Manufacturer Entity Resolution

**Read first:** `CLAUDE.md` (current status + decisions), `plan.md` §1 (non-negotiable: never auto-merge the 0.75–0.92 band without a human), §3.2 (`manufacturers` schema), §4 Phase 2 (now split 2a/2b, this ticket is 2a only).

## Why this matters more than it looks

Phase 3a shipped with `manufacturer_id` null on every record — 5,107 distinct `manufacturer_raw` strings became 5,107 separate manufacturer pages (Zee Laboratories alone has 5). Each page already discloses this, but it's a real defect, and it blocks Phase 4's "repeat manufacturers" analysis outright. This ticket fixes the data. **It does not touch `web/`** — regenerating the site against resolved entities is the very next ticket, kept separate on purpose so this one stays data engineering, not frontend work.

**The review step is real, not a formality.** `plan.md` §4 Phase 2's rule: *"never auto-merge above the review band without spot-checking a sample. A wrongly-merged manufacturer means attributing another company's failures to them. That's a real reputational harm."* The 0.75–0.92 band needs a human judgment call on each pair — build the tooling to make that fast, but don't skip it or auto-approve it yourself.

## Task

1. **`src/resolve/manufacturers.py`**:
   - Normalizer: strip `M/s.`, legal suffixes (`Pvt Ltd`, `Ltd`, `Private Limited`, `Pharmaceuticals`/`Pharma`, etc.), punctuation, casing, whitespace
   - Reuse the state-derivation logic already built in `src/normalize.py` (Phase 1a) rather than rebuilding it — it already handles the ambiguous-abbreviation cases (`A.P.`, `U.K.` excluded, etc.)
   - Blocking: normalized first token + state, to avoid O(n²) over ~5,107 distinct `manufacturer_raw` strings
   - `rapidfuzz` similarity within blocks; address as a secondary signal for borderline pairs
   - Three tiers: **<0.75** no match · **0.75–0.92** human review band · **>0.92** auto-merge candidate

2. **Review tooling** (CLI — no backend exists to host a web review UI):
   - A script that steps through the 0.75–0.92 band, shows both raw strings + addresses side by side, records approve/reject. This is the step the user runs themselves.
   - A second script that samples the >0.92 auto-merge tier for spot-checking (required even for the "confident" tier per the non-negotiable above)
   - Every decision — human or auto — written to an append-only log (e.g. `data/resolve/manufacturer_merge_log.jsonl`). Never overwritten silently; a bad merge must be traceable and reversible.

3. **Apply merges**: populate `manufacturers` (`canonical_name`, `known_aliases`, `address_raw`, `state`, `first_seen_month`, `total_flags` computed), backfill `manufacturer_id` on every `nsq_records` row. Unmatched raw strings still get their own singleton `manufacturers` row — nothing ends up without an id.
   - Respect the existing `manufacturer_unknown_placeholder` flag from Phase 1a — the 51 `"Under Investigation"` spurious records must never be resolved into a company entity (§1.1 — that would misattribute a counterfeit to a real company).

4. **Write it up** — thresholds used, block strategy, the collapse ratio (5,107 raw strings → N canonical manufacturers), and spot-check results, in `docs/methodology.md` or a new `docs/entity_resolution.md`.

## Explicit boundary — do NOT do yet

- No drug-name resolution (Phase 2b — separate ticket, deferred, needs a more conservative threshold approach).
- No changes to `web/` or `scripts/export_static.py` — the 5,107 pages stay exactly as they are until the next ticket regenerates against resolved entities.
- No merge, in either tier, skips the log or the spot-check step — not even the >0.92 "obvious" ones.

## Done when

- [ ] `src/resolve/manufacturers.py` runs end to end, produces all three tiers
- [ ] CLI review tool exists, and the 0.75–0.92 band has actually been reviewed by the user (real approve/reject calls, not rubber-stamped)
- [ ] Auto-merge tier sample spot-checked and results recorded
- [ ] `manufacturers` table populated, `manufacturer_id` backfilled on all `nsq_records`
- [ ] Merge log complete, auditable, append-only
- [ ] `manufacturer_unknown_placeholder` records confirmed still unresolved (no company entity assigned)
- [ ] Write-up exists with the collapse ratio and threshold rationale
- [ ] `CLAUDE.md` updated: Current Status, Decisions Log, Key Learnings

## Before ending the session

Update `CLAUDE.md`:
- **Current Status** → collapse ratio achieved (5,107 → N), review band size, how many were human-approved vs rejected
- **Decisions Log** → exact thresholds/blocking strategy used, any deviation from this scope
- **Key Learnings** → anything about manufacturer name variation that surprised you, tricky pairs the reviewer had to think hard about, edge cases in the address-derived state signal

Do not start Phase 2b or the `web/` regeneration even if it feels like the natural next step — those are separate tickets, written after the planner reviews what this one produced.
