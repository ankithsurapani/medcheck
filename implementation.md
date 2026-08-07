# Current Task — Post-Launch Hardening Batch (4 tickets)

**Read first:** `CLAUDE.md` (Current Status, especially the Phase 2a partial-resolution
numbers and the "Open / needs a planner decision" list this batch is drawn from),
`docs/entity_resolution.md` (slug/id scheme, blocking, thresholds), `docs/decisions.md`
(prior deploy decisions — Vercel `--archive=tgz`, the Next 15.5.22 CVE bump),
`plan.md` §1.4 (uncertainty shown, not hidden), §5.6 (sampling bias — nothing here is
a population rate), §3.2 (`manufacturers` schema), §4 Phase 2a and Phase 5.

MedCheck is **live and public** (https://web-navy-three-91.vercel.app/,
https://github.com/ankithsurapani/medcheck). Every ticket below touches something a
real visitor can already reach — treat production deploys and public-URL changes
accordingly (see the checkpoint in Ticket 3 and Ticket 4).

## Why this batch, now

Four items sat in CLAUDE.md's "Open" list after Phase 4 shipped. None blocks the
others technically, but **Ticket 1 should land before Ticket 2**, and before any
further work on the 190 pending manufacturer-review pairs: Ticket 2 re-runs
`--apply`, and until Ticket 1 fixes the slug scheme, every re-apply reshuffles
every manufacturer URL. Tickets 3 and 4 are fully independent of 1, 2, and each
other — do them in any order, including in parallel across sessions.

## Sequencing

1. **Ticket 1 — content-derived manufacturer slugs** (do first)
2. **Ticket 2 — state coverage via PIN-prefix mapping** (do after Ticket 1)
3. **Ticket 3 — Next.js 16 upgrade** (independent)
4. **Ticket 4 — Vercel project rename** (independent, cosmetic)

Commit each ticket separately. Update CLAUDE.md's Current Status / Decisions Log /
Key Learnings after *each* ticket, not once at the end of the batch — if the session
ends after Ticket 2, CLAUDE.md must already reflect Tickets 1 and 2 as done.

---

## Ticket 1 — Content-derived manufacturer slugs

### Why

`scripts/export_static.py:48-62`, `manufacturer_slug()`:

```python
def manufacturer_slug(mfr_id: int, canonical_name: str) -> str:
    return f"{slugify(canonical_name, 60)}-m{mfr_id}"
```

`mfr_id` comes from `src/resolve/manufacturers.py:592-598` (`apply()`): rows are
sorted by `(canonical_name.lower(), address_raw)` and renumbered `1..N` on *every*
`--apply` run. That means approving even one of the 190 pending review-band pairs
today would shift the alphabetical position — and therefore the id, and therefore
the public URL — of every manufacturer that sorts after it. On a live site that's
silent link rot: anything anyone bookmarked, cited, or indexed breaks with no
redirect.

Web code never parses the integer back out of the slug — confirmed by grep:
`web/lib/data.ts:65` and `79` do `new Map(ALL_MFRS.map(m => [m.slug, m]))` /
`mfrBySlug.get(slug)`, i.e. slugs are opaque lookup keys built at export time.
`web/app/manufacturer/[slug]/page.tsx` and `web/lib/search.ts` are the same — the
fix is fully contained in `scripts/export_static.py`. `manufacturers.id` (the SQL
integer primary key used for joins in `nsq_records.manufacturer_id`) is untouched.

### Task

Replace the `-m{mfr_id}` suffix with a hash over the one thing that's actually
invariant under re-sorting: the cluster's own membership. `apply()` already builds
this per row before serializing it to `known_aliases`
(`src/resolve/manufacturers.py:584`, `json.dumps(members, ensure_ascii=False)`,
where `members = sorted(members)` at line 574) — the sorted list of raw
`manufacturer_raw` strings that collapsed into this entity. That list only changes
when a merge decision actually adds or removes a member from *that specific*
cluster; it's unaffected by any other cluster gaining or losing a member.

In `scripts/export_static.py`:

1. Add a slug-stability hash function, e.g.:
   ```python
   import hashlib

   def cluster_hash(members: list[str], length: int = 8) -> str:
       """Stable id for a manufacturer cluster: sha1 of its sorted raw-string
       membership, joined by \\n. Changes only when this cluster's own merge
       decision changes — not when any other cluster's id would have shifted
       under the old positional scheme."""
       joined = "\n".join(sorted(members))
       return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:length]
   ```
2. `manufacturers.known_aliases` is already the JSON-encoded members list per row
   (see schema note above) — decode it where the manufacturer dict is built (around
   `scripts/export_static.py:93`) and pass it into a new
   `manufacturer_slug(canonical_name: str, members: list[str]) -> str` that calls
   `cluster_hash(members)` instead of taking `mfr_id`.
3. **Collision check, not just a hope:** after building all 1,856 (or however many
   at the time) slugs, assert uniqueness. At `length=8` hex (32 bits) collision risk
   across ~1,900 items is negligible but must be *checked*, not assumed — if the
   assert ever fires, bump `length` rather than special-casing one manufacturer.
4. Update every call site that constructed the old slug shape (`scripts/export_static.py`
   around lines 93, 108, 129-141, 152-169, 219) to pass members through instead of
   `m["id"]`.
5. `manufacturers.id` (the SQL PK) is untouched by this ticket — it keeps
   renumbering on `--apply` as before, since nothing outside `export_static.py`
   treats it as a stable public identifier.

### Explicit boundary — do NOT do yet

- Don't touch `src/resolve/manufacturers.py`'s `apply()` id assignment — the SQL
  `id` is allowed to stay positional; only the *public slug* needs to be stable.
- Don't attempt to preserve the *old* positional slugs with a redirect map. Nothing
  outside this repo has had time to accumulate backlinks to them (site went live
  2026-08-06); a one-time slug change now, before resuming the 190-pair review, is
  the whole point of doing this ticket first.
- Don't resume the manufacturer review-band decisions (`review_cli.py`) as part of
  this ticket — that's separate work this ticket is merely unblocking.

### Done when

- [ ] `manufacturer_slug()` takes `(canonical_name, members)`, not `(mfr_id, canonical_name)`
- [ ] Uniqueness assertion runs over the full export and passes (or `length` was
      bumped until it does, with that decision logged)
- [ ] Regression check: run `--apply --allow-pending` twice in a row with **no**
      review decisions changed in between, re-export, and confirm every slug is
      byte-identical across the two runs (sanity check that the hash is
      deterministic, not e.g. dict-order-dependent)
- [ ] Stability check: pick one pending pair from `data/resolve/manufacturer_merge_log.jsonl`'s
      190 undecided, simulate approving it (or use `review_cli.py` on a scratch
      copy of the DB), re-apply, re-export, and confirm **only** the touched
      cluster's slug changed — every other manufacturer's slug is unchanged. This
      is the actual acceptance criterion; a hash scheme that still churns
      unrelated slugs hasn't fixed the bug.
- [ ] `npm run build` in `web/` succeeds, `npm run test:search` (29 assertions) passes
- [ ] `docs/entity_resolution.md` updated with the new slug scheme and why it
      replaced the positional one
- [ ] CLAUDE.md updated (see "Before ending the session" below)

---

## Ticket 2 — State coverage via PIN-prefix mapping

### Why

`src/normalize.py:222-245`, `derive_state()`, only matches an explicit state field
or a state *name* appearing literally in the address text (`STATE_RE`,
`STATE_ABBREV_RE`). It has no fallback for addresses that end in a PIN code but
never spell out the state — which is most of them. Sampling records where `state
IS NULL`:

```
M/s. Syncom Healthcare Ltd., D-42, IIE, Sidcul, Selaqui, Dehradun-248197
M/s. Jackson Laboratories Pvt. Ltd., 22-24, Majitha Road, Bye Pass, Amritsar ? 143001
M/s. Unimarck Healthcare Ltd., Plot No.24,25,37, Sector-6A, SIDCUL, Haridwar-249403
```

Every one of these has a 6-digit Indian PIN code at the end (`248197`, `143001`,
`249403`) and every one is derivable to a state from the PIN alone — India Post's
PIN structure is public and citable (first digit = zone, first two digits =
postal circle, which maps to state/UT with only a handful of exceptions that need
the third digit). This is exactly the "58% state coverage" gap CLAUDE.md already
flags, and it's additive: a PIN-derived fallback only fires when name-matching
already failed.

### Task

1. Add a PIN-prefix → state table, sourced from India Post's published circle
   list (cite the source URL in a comment, same pattern as
   `src/resolve/labs.py`'s laboratory registry — every entry cites where it came
   from). Structure it as two-digit prefix → state where that's unambiguous, with
   a three-digit override table for the known non-uniform two-digit prefixes
   (e.g. the 80–85 range spans Bihar/Jharkhand/Odisha/West Bengal at the third
   digit). Do not guess at boundaries you can't cite — leave a prefix unmapped
   and let it fall through to the ambiguous case below rather than picking a
   plausible-looking state.
2. Add PIN extraction: a regex over `manufacturer_raw` that finds a 6-digit run
   that is *plausibly* a PIN (India's PIN range is 110001–855126; reject 6-digit
   runs outside that, since plot/street numbers can coincidentally be 6 digits).
   Prefer the *last* such match in the string — Indian addresses put the PIN at
   the end — and require it be adjacent to a hyphen, space, or string end, not
   embedded in a longer digit run (guards against accidentally matching inside a
   longer registration number).
3. Wire it into `derive_state()` **as a fallback only**, after the existing
   name/abbreviation checks return no match (today's `"state_not_derived:no_match"`
   branch, `src/normalize.py:245`). Never let a PIN-derived state override an
   explicit or name-matched one — this project's non-negotiable is uncertainty
   shown, not resolved by picking the more-confident-looking source silently.
4. Track provenance. Add a way to tell "this state came from the address text"
   apart from "this state came from a PIN lookup" — e.g. a new flag value
   `state_derived_from_pin` alongside the existing `state_not_derived:*` /
   `state_ambiguous:*` flag vocabulary (`derive_state()` already returns
   `(state, flag)` — a PIN-sourced hit should return a flag too, not silently
   look identical to a name-matched one, since PIN lookup is a weaker signal and
   §1.4 says uncertainty must be visible, not just internally tracked).
5. If the PIN maps to a genuinely ambiguous prefix (no third-digit resolution
   available, or the prefix isn't in the table at all), return `None` with a
   `state_ambiguous_pin:<prefix>` flag — same discipline as the existing
   `state_ambiguous:<states>` case. Do not fall back to a guess.
6. Re-run the full pipeline in order: `src/normalize.py` (regenerates
   `medcheck.db`, which **wipes `manufacturer_id`** — see CLAUDE.md's Key
   Learnings, this is expected) → `src/resolve/manufacturers.py --apply
   --allow-pending` (re-links manufacturers; safe because Ticket 1 already made
   slugs stable across this exact operation) → `scripts/export_static.py` →
   `web/` rebuild → `python analysis/analyse.py --json` (state-coverage number in
   `analysis/FINDINGS.md` needs updating) → re-export
   `analysis/dataset/medcheck_nsq_records.csv` (CC0 dataset; note the new
   provenance flag if it becomes a column, in `analysis/dataset/README.md`).

### Explicit boundary — do NOT do yet

- Don't touch manufacturer *name* parsing/splitting — this ticket is the `state`
  field only.
- Don't let a PIN-derived state feed back into changing `manufacturers.state`
  silently in a way that contradicts an already-published, name-derived value for
  the same cluster — if `apply()`'s `states.most_common(1)` picks a different
  winner because of newly-PIN-filled records, that's fine (more data, better
  answer); just don't special-case PIN-derived votes to win ties.
- Don't rewrite `STATE_RE`/`STATE_ABBREV_RE` — PIN lookup is additive, not a
  replacement for the existing text-match path.

### Done when

- [ ] PIN table exists with a cited source, and an ambiguous/unmapped prefix
      returns `state_ambiguous_pin:*` rather than a guess
- [ ] `derive_state()` fallback only fires when the existing checks already
      returned no match; a unit test proves an explicit/name-matched state is
      never overridden by a PIN result
- [ ] `tests/test_normalize.py` (or a new `tests/test_pin_state.py`, matching the
      house pattern of `tests/test_labs.py` / `tests/test_categorise.py`) covers:
      a clean two-digit match, a three-digit-disambiguation case, a PIN embedded
      mid-address that must NOT be picked up as the trailing PIN, an
      out-of-range 6-digit number that must be rejected, and an unmapped prefix
      returning the ambiguous flag
- [ ] State coverage percentage recomputed end-to-end and reported (replacing the
      "58.1%" figure in CLAUDE.md and `analysis/FINDINGS.md` — expect it to rise,
      report the actual number, don't estimate it)
- [ ] `analysis/FINDINGS.md`'s geographic-clustering section and limitations
      table updated to describe the two-source (name-match + PIN-fallback) state
      derivation and that a residual ambiguous/unmapped share remains
- [ ] CC0 dataset re-exported; `analysis/dataset/README.md` documents the new
      provenance flag if a column was added
- [ ] `web/` rebuilds clean, `npm run test:search` passes, spot-check that a
      record whose state was previously blank now renders one (or still renders
      "Not published" + reason if it's still ambiguous — never a silent guess)
- [ ] CLAUDE.md updated

---

## Ticket 3 — Next.js 16 upgrade

### Why

`npm audit` (`web/`) reports 3 high-severity findings, all resolved only by the
major-version bump:

```
postcss  <=8.5.22 — XSS via unescaped </style>, source-map path traversal (3 advisories)
sharp    <0.35.0  — libvips CVEs (CVE-2026-33327/33328/35590/35591)
fix available via `npm audit fix --force` → installs next@16.3.0 (breaking)
```

CLAUDE.md already logged these as "build-tooling only, not urgent" because
`images.unoptimized: true` means `sharp` never processes untrusted input and
nothing runs untrusted CSS through `postcss` — true, but they've been sitting on
a public repo since launch and the fix is now well-defined (Next 16.3.0, current
stable, not a preview).

### Task

1. Bump `next` to `16.3.0` (or whatever is current stable at execution time — check,
   don't assume 16.3.0 is still latest), `react`/`react-dom` to whatever Next 16
   requires (currently 19.x, already satisfied — verify).
2. Read Next.js 16's breaking-changes/migration notes before touching config —
   this site uses `output: 'export'` (fully static, no server runtime), so most of
   Next 16's server-side breaking changes (async `cookies()`/`headers()`, etc.)
   likely don't apply, but confirm rather than assume. Check
   `web/next.config.*` for anything Next 16 deprecates or renames.
3. Run the codemods Next.js ships for major bumps if any apply
   (`npx @next/codemod@latest`), reviewing every changed file rather than
   accepting blind.
4. Rebuild: `npm run build` must still produce all pages statically (**8,017 as of
   the last full rebuild** — record pages + manufacturer pages; the exact count
   will differ if Ticket 1/2 already ran and changed manufacturer clustering —
   compare against whatever the current pre-upgrade count is, not the stale
   8,017 figure).
5. `npm run test:search` — all assertions (29 as of last count) must still pass.
6. `npm audit` — confirm 0 high/critical findings remain. If any persist,
   document exactly what's left and why (same discipline as the current 3-item
   writeup in CLAUDE.md — don't silently drop the finding).
7. Manual smoke check before considering this done: serve the static export
   locally and check a record page, a manufacturer page, and the search index
   asset load correctly (same three checks used to verify the original launch —
   see CLAUDE.md's Ship-it entry).

### Explicit boundary — do NOT do yet

- **Do not run the production Vercel deploy as part of this ticket without a
  checkpoint.** Build and verify locally, commit the dependency bump, and stop —
  confirm with the user before `vercel --prod` (or equivalent) pushes this to
  the live public site. This mirrors the project's existing practice: the
  original launch deploy is logged in CLAUDE.md as something that hit two real
  blockers and was fixed deliberately, not rushed.
- Don't chase unrelated dependency bumps while in here (e.g. Tailwind, MiniSearch)
  unless Next 16 forces a peer-dependency requirement — scope creep on a
  security-motivated ticket makes the diff harder to review.
- Don't change `images.unoptimized` or any other config unless Next 16 requires it.

### Done when

- [ ] `next` (and required peers) bumped to current stable 16.x
- [ ] `npm run build` succeeds with the expected page count
- [ ] `npm run test:search` passes in full
- [ ] `npm audit` shows 0 high/critical (or remaining findings are documented with
      the same rigor as before)
- [ ] Manual smoke check (record page, manufacturer page, search index) done
      against the local static export
- [ ] User has explicitly confirmed before any production deploy runs
- [ ] CLAUDE.md updated — including whether/when the production deploy happened

---

## Ticket 4 — Vercel project rename (cosmetic)

### Why

The live URL is `web-navy-three-91.vercel.app` — an autogenerated Vercel slug from
a project literally named `web`. Cosmetic, not urgent, but it's been the public
face of the project since launch and doesn't say "MedCheck" anywhere.

### Task

1. Rename the Vercel project (dashboard: Project Settings → General → Project
   Name, or `vercel` CLI if it supports non-interactive rename at execution
   time — check current CLI capability rather than assuming). **This step likely
   needs the user's authenticated Vercel session** — if the CLI can't do it
   headless, say so explicitly and hand the one manual step back to the user
   rather than silently skipping the ticket.
2. Decide whether renaming the project also changes the production URL, or
   whether to add a custom domain / a stable alias instead (Vercel supports
   assigning a custom production alias independent of the project's auto-slug).
   A custom domain is a bigger step (DNS) — if the user hasn't already got one in
   mind, default to just renaming the project + picking a cleaner
   `<something>.vercel.app` alias, and leave a real custom domain as a separate,
   future ticket.
3. Once the URL changes, update every place it's currently referenced — confirmed
   by grep to be exactly two files: `README.md` (`Search the data:` link) and
   `CLAUDE.md` (the "MedCheck is live" line and the deploy notes below it).
4. Verify the new URL serves `/`, a record page, a manufacturer page, and the
   search index asset with `200 OK` — same verification CLAUDE.md logged for the
   original launch. Don't consider this done on "the dashboard says renamed."

### Explicit boundary — do NOT do yet

- Don't set up a custom domain unless the user has one ready to point at Vercel —
  DNS changes are outward-facing and slower to reverse than a project rename.
- Don't touch the GitHub repo name or description as part of this ticket — scope
  is the Vercel-side URL only.

### Done when

- [ ] Vercel project renamed (or the manual step handed back to the user with
      clear instructions, if the CLI can't do it headless)
- [ ] New URL verified 200 OK on the same four checks as the original launch
- [ ] `README.md` and `CLAUDE.md` updated to the new URL
- [ ] CLAUDE.md updated

---

## Before ending the session

After each ticket (not just once at the very end), update `CLAUDE.md`:
- **Current Status** → mark the ticket done, with the concrete before/after numbers
  (slug scheme changed, state coverage %, npm audit finding count, live URL)
- **Decisions Log** (`docs/decisions.md`) → append one line per real decision made
  (hash length chosen for slugs, which PIN-prefix source was cited, which Next.js
  16 version landed, whether a custom domain was deferred)
- **Key Learnings** → anything that surprised you executing this — e.g. if the
  PIN table turned out messier than expected at some boundary, or Next 16's
  migration touched something the static-export assumption didn't cover

Do not start the 190 pending manufacturer review-band decisions, Phase 1b (PDF
backfill), Phase 2b (drug-name resolution), or Phase 3b's Hindi/live-API work as
part of this batch, even if a ticket above makes one of them look newly
convenient — those are separate tickets.
