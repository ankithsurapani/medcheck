# Current Task — Resume the 190 pending manufacturer review-band pairs

**Read first:** `CLAUDE.md` (Current Status — Phase 2a's partial-resolution numbers,
the post-launch hardening section confirming slugs are now stable), `docs/entity_resolution.md`
in full — especially §9 "Human review — status" and its "what the band actually
contains, for whoever sits down with it" list, and the "Public slugs are
content-derived" section at the bottom, which is *why* this ticket is safe to run
now. `plan.md` §1 (non-negotiables — specifically **"never auto-merge entities
above the 0.75–0.92 review band without a human look"**) and §4 Phase 2a.

## Read this before doing anything else

**This is not an autonomous ticket.** Every other item in the post-launch batch
was pure engineering — an AI agent could implement, test, and verify all of it
without a human in the loop. This one is different: `src/resolve/review_cli.py`
hardcodes `"reviewer": "human"` on every decision it logs, and that is not an
accident — it is the literal mechanism behind CLAUDE.md's non-negotiable
("wrongly merging manufacturers is reputational harm"). Answering the 190 y/n
questions yourself, however confident a pair looks, would be the exact thing
this project's design exists to prevent.

**What you're actually being asked to do:**
1. Everything that makes the review faster and better without touching the
   decisions themselves (pre-flight check, triage/grouping).
2. Conduct the review **together with the user, in real time** — present each
   pair's evidence clearly, let them answer, log exactly what they said. Chat-driven
   is fine (you don't have to hand them a terminal), but the judgment call is
   theirs, every time, including the ones that look obvious.
3. Everything downstream of a completed (or partially completed) review —
   apply, rebuild, re-analyze, document.

**If the user isn't available to answer questions in this session:** do step 1
(pre-flight + triage) and stop. Report what you found and wait. Do not guess at
answers to make progress look faster — a partially-reviewed queue with 15 or 40
or 100 honest decisions is a fine place to stop, exactly like the first pass was
(`docs/entity_resolution.md` §9: "Partly done, and that is a legitimate resting
state"). It is not fine to reach 190/190 by deciding any of them yourself.

## Why this ticket, now

Two things changed since the review was left at 15/205:

- **Slugs are content-derived** (post-launch hardening Ticket 1). Approving a
  pending pair used to rename up to 1,207 of 1,856 public manufacturer URLs with
  no redirect; now it changes only the URLs of the cluster(s) actually touched.
  That was the reason the review was left unfinished rather than rushed.
- **State coverage moved 58.1% → 82.9%** (Ticket 2, PIN-prefix fallback). This
  matters *directly* to the review band: the scoring formula in
  `src/resolve/manufacturers.py` (`§6` of `docs/entity_resolution.md`) applies a
  `-0.09` penalty when both entities have a known state and it differs, and a
  `state_differs:<a>|<b>` signal the reviewer sees. More entities now have a
  known state than when the 205-pair queue was built. **This can move pairs
  across the 0.75/0.92 tier boundaries** — see Task 1, this has to be checked,
  not assumed away.

## Task

### 1. Pre-flight — confirm the queue didn't shift under you

```
.venv/bin/python src/resolve/manufacturers.py --build
```

This rescoring runs against the current `entities` table, which now has more
derived states than the 2026-08-06 build that produced the "205 cluster-pair
decisions" number in `docs/entity_resolution.md` §8. Compare the new
`review_queue` length and the new `auto` tier size against the committed numbers
(205 review-band pairs, 21,219 auto-tier pairs). Also confirm every one of the 15
already-decided `pair_id`s is still present in the new queue — `pair_id()` hashes
the two raw entity keys (`src/resolve/manufacturers.py:390-394`), not their
state, so it should be stable, but confirm rather than assume.

- **If the counts match exactly:** proceed, and say so in the write-up — this is
  worth one line, not a paragraph.
- **If they don't:** report exactly what changed (pairs newly in the band, pairs
  that left it, signal changes on existing pairs) before doing anything else.
  This is a real, expected, and interesting consequence of Ticket 2 shipping
  better address data — write it up honestly, the same way the alert_section fix
  wrote up an 831-record discrepancy rather than burying it.

### 2. Triage the queue into the three patterns already identified

`docs/entity_resolution.md` §9 already characterizes the band as three shapes.
Write a small script, `src/resolve/triage_review.py`, that reads
`data/resolve/candidates.json`'s `review_queue` and buckets each pending pair
(skip anything already in `review_decisions()`) so the human reviewer isn't
context-switching between judgment types pair to pair:

- **`multi_plant`** — normalized names are identical (or would be after
  `manufacturers.py`'s generic-token folding) and the `signals` list contains a
  `state_differs:` entry. Expected to be roughly the 26 pairs §9 describes —
  same company, second address, "yes" is very likely but still the user's call.
- **`near_typo`** — Levenshtein distance ≤2 between the two normalized names
  (`rapidfuzz.distance.Levenshtein.distance`, already a project dependency via
  `rapidfuzz`). These are the `Navkar Lifesciences` / `Navkar Lifescienses`
  shape: could be a CDSCO re-typing of one real firm, could be two firms that
  happen to be near-spellings (`Deep Pharma` / `Deepin Pharmaceuticals` scores
  0.75 and is a real §9 example of "must not merge").
- **`other`** — everything left. No name-shape shortcut applies; read both
  clusters' evidence in full.

Order the interactive session `multi_plant` → `near_typo` → `other`: front-load
the pattern that's fastest to reason about once the reviewer has seen a couple of
examples, save the genuinely case-by-case ones for when they're warmed up, not
rushed. The script should print (or write to a file) `pair_id`, bucket, score,
`signals`, and both clusters' member counts — not a verdict, not a suggestion,
just faster access to the same evidence `review_cli.py` already shows.

### 3. Conduct the review with the user

Two ways to run this, both fine — pick based on what's actually happening in the
session:

- **Hand them the terminal:** `python src/resolve/review_cli.py` (it resumes
  automatically past the 15 already-decided pairs; nothing to configure). If
  you built the triage ordering in Task 2, note it for them, but
  `review_cli.py`'s own queue order is what actually runs — don't reorder
  `candidates.json` itself; use the triage output as a reading guide, not a
  patch to the tool.
- **Present pairs in chat, log via `review_cli`'s own machinery:** for each pair,
  show what `review_cli.py`'s `show()` shows (both clusters' spellings up to 6,
  record counts, score, signals), ask the same y/n/skip question, and on an
  answer call `manufacturers.log_append()` with the same dict shape
  `review_cli.py` constructs (`kind: "review_decision"`, `reviewer: "human"`,
  `decision: "approve"|"reject"`, plus `pair_id`, `score`, `name_sim`, `addr_sim`,
  `signals`, `a`, `b`, `cluster_a`, `cluster_b`, `note`). Whichever path, the
  logged `reviewer` field must read `"human"` and must reflect an answer the
  user actually gave — never write a decision without one.

Stopping partway through 190 is a legitimate outcome. Log exactly how many were
decided, how many approved vs rejected, and how many remain — don't round up.

### 4. Apply and re-propagate

Once the session's review pass is done (whether that's 190/190 or fewer):

```
.venv/bin/python src/resolve/manufacturers.py --apply --allow-pending   # if any remain pending
.venv/bin/python src/resolve/manufacturers.py --apply                  # only if 0 remain pending
.venv/bin/python scripts/export_static.py
```

Then the full downstream chain, same order as every prior ticket that touched
`manufacturers`:

```
cd web && npm run build && npm run test:search
.venv/bin/python analysis/analyse.py --json
.venv/bin/python analysis/export_dataset.py     # regenerates analysis/dataset/medcheck_nsq_records.csv + README
```

Numbers that will move and need re-quoting, not hand-typed: manufacturer count
(currently 1,856), collapse ratio (currently 2.75:1), and the "13.5% of companies
hold 54.5% of flags" repeat-manufacturer concentration stat in `CLAUDE.md` and
`analysis/FINDINGS.md` — all three come from the same `apply()` output and the
same `analyse.py` function, so pull them from the actual re-run, not by
estimating how they'd move.

Consider running `spotcheck_cli.py` again afterward if the auto tier grew
meaningfully (more merges in the review band can also feed newly-eligible pairs
into future rebuilds) — optional, not blocking, same "weakest-cohesion first"
sampling the tool already does.

### 5. Document it

- `docs/entity_resolution.md` §9 rewritten: replace "Partly done" framing with
  the actual final state (fully done, or still-partial-but-further-along — say
  which, with real numbers), and update the "To resume" block if anything is
  still left pending.
- `docs/decisions.md` — one line: how many pairs were decided this session,
  approve/reject split, and whether the Task 1 pre-flight found any tier
  movement from the PIN-derived states.
- `CLAUDE.md` Current Status — updated manufacturer count, collapse ratio,
  concentration stat, and whether Phase 2a is now fully complete or still
  legitimately partial.

## Explicit boundary — do NOT do yet

- **Never answer a review question yourself.** Not for the "obvious" multi-plant
  pairs, not for anything. If the user has to step away mid-session, stop and
  leave the remainder pending — that's what `--allow-pending` is for.
- Don't re-tune the scoring formula, the 0.75/0.92 thresholds, or the
  name-normalization/folding rules — those were Phase 2a's original decisions
  (`docs/entity_resolution.md` §4–§6) and are out of scope here. This ticket
  exhausts the existing queue; it doesn't re-litigate how the queue was built.
  (Task 1's tier-boundary check is about *detecting* movement caused by better
  state data, not about *tuning* anything.)
- Don't touch `scripts/export_static.py`'s slug scheme, `src/resolve/pin_state.py`,
  or anything else from the just-shipped post-launch hardening batch.
- Don't deploy to production Vercel as an automatic last step — same checkpoint
  as every prior ticket that ends in a rebuild: confirm with the user first.
- Don't resume/start Phase 1b, Phase 2b, or Phase 3b work even if it looks
  newly convenient.

## Done when

- [ ] Pre-flight rebuild run; queue/tier stability (or the exact drift found)
      reported
- [ ] `src/resolve/triage_review.py` exists and was actually used to order the
      session, not just written and ignored
- [ ] Every review-band decision made this session has `"reviewer": "human"` in
      the merge log and traces to an answer the user actually gave — spot-check
      this by reading back the new log entries, don't just trust the code path
- [ ] Honest count reported: N decided this session (approve/reject split), M
      still pending — N + M + 15 (or whatever the pre-flight found) should equal
      the current queue size
- [ ] `--apply` run with the correct flag for however many pairs remain pending
- [ ] Full pipeline re-run: `export_static.py`, `web/` rebuild, `test:search`
      (must still be 29/29 — the slug-stability property from Ticket 1 is what
      makes this safe to re-run at all), `analysis/analyse.py`, CC0 dataset
- [ ] `docs/entity_resolution.md` §9, `docs/decisions.md`, `CLAUDE.md` updated
      with real, re-derived numbers — no hand-typed estimates

## Before ending the session

Update `CLAUDE.md`:
- **Current Status** → manufacturer count, collapse ratio, concentration stat,
  and the review's actual completion state (don't round "184 of 190" up to "done")
- **Decisions Log** (`docs/decisions.md`) → the session's approve/reject numbers
  and whether Task 1 found any tier movement
- **Key Learnings** → anything that surprised you — e.g. if the triage buckets
  didn't split the way §9 predicted, or if a `multi_plant`-bucketed pair turned
  out to be a "no" (that would itself be worth recording, since it means the
  bucket heuristic isn't a safe shortcut for reasoning, only for ordering)

Do not start the 190-pair-adjacent-but-separate work — a real custom domain,
`manufacturers.state` provenance, the 827 records with no state and no PIN, or
any deferred phase — even if it looks like a natural next step from here.
