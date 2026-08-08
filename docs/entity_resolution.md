# Manufacturer entity resolution — Phase 2a

How 5,107 distinct `manufacturer_raw` spellings were collapsed onto company
entities, what the thresholds are, and what a human actually looked at.

Code: `src/resolve/manufacturers.py`, `src/resolve/review_cli.py`,
`src/resolve/spotcheck_cli.py`. Tests: `tests/test_resolve_manufacturers.py`.
Audit trail: `data/resolve/manufacturer_merge_log.jsonl` (append-only).

---

## 1. The problem

`manufacturer_raw` is a company name **and** a full postal address in one cell,
re-typed by CDSCO every month. 6,155 records carry 5,107 distinct spellings. Most
appear exactly once; Zee Laboratories appears **48 different ways**:

```
M/s. Zee Laboratories Ltd., Behind 47, Industrial Area, Paonta Sahib-173025
ZEE LABORATORIES LTD.,Behind47, Industrial Area, Paonta Sahib- 173025
Zee Laboratories Ltd.Behind 47, Industrial Area, Paonta Sahib-173025
M/s. Zee Laboratories Limited, Behind 47, Industrial Area, Poanta Sahib-173025 (Punjab)
M/s. Zee Laboratories Ltd., Paonta Sahib
```

The differences are punctuation, spacing, casing, legal-suffix spelling, a
transposed PIN (`173025` / `173205`), a misspelt town (`Poanta`), a wrong state
(Punjab, for a Himachal Pradesh address), and one entry with no address at all.

Phase 3a shipped with `manufacturer_id` null on every record, so each of those
spellings became its own manufacturer page. This phase fixes the data.

## 2. Pipeline

```
python src/resolve/manufacturers.py --build     # score pairs, write the queues
python src/resolve/review_cli.py                # human decides the 0.75-0.92 band
python src/resolve/spotcheck_cli.py             # human samples the >0.92 tier
python src/resolve/manufacturers.py --apply     # write manufacturers + backfill ids
python src/resolve/manufacturers.py --cohesion  # weakest-link report per cluster
```

`--apply` treats any review-band pair with no recorded human decision as
**rejected**, and refuses to run at all unless `--allow-pending` is passed. Running
the pipeline early can therefore only under-merge, never over-merge.

## 3. Placeholders — excluded before anything else

Seven raw strings covering 78 records are not companies:

| string | records |
|---|---|
| `Under Investigation` | 51 |
| `Not Mentioned` | 11 |
| `Not applicable` | 8 |
| `Spurious` | 5 |
| `NIL,NIL NIL` | 1 |
| `NM` | 1 |
| `Not Applicable` | 1 |

They are excluded from clustering and keep `manufacturer_id` **NULL**. This is the
one place the ticket's "nothing ends up without an id" rule is deliberately not
applied: giving a counterfeit's unknown maker a company entity carrying 51 flagged
batches would be exactly the misattribution §1.1 forbids.

Phase 1a's `manufacturer_unknown_placeholder` flag only covers `Under
Investigation` (51 records) — its regex matches "under investigation / not known /
unknown / n.a." and nothing else. The other 27 records were found here. Phase 1a's
flag was left alone rather than widened, since that is Phase 1a's scope; the
resolver carries the wider list and `tests/test_resolve_manufacturers.py` asserts
both that the placeholders match and that real firms brushing against those words
(`Nilkanth Pharmaceuticals`, `NM Pharma Industries`) do not.

## 4. Normalizing

**Split name from address.** Cut at whichever comes first: the first comma, the
first address keyword (`plot`, `khasra`, `village`, `behind`, `industrial`, `no`,
`sector`, … 40 of them), or the first numeric token. Certification boilerplate is
stripped before the cut — `(ISO 9001 : 2015 & WHO GMP Certified)` and
`WHO-GMP Certified Company` are not part of a company's name, and CDSCO includes
them one month and not the next.

**Normalize the name.** Strip `M/s.`, lowercase, de-punctuate, drop legal tokens
(`pvt`, `ltd`, `limited`, `llp`, `co`, `company`, …), drop a trailing `India`, drop
trailing single characters (splitter debris from addresses like
`Bajaj Healthcare Ltd. R.S. No. 1818`, cut at `No`).

**Fold industry synonyms rather than delete them.** `Laboratories` / `Labs` /
`Lab` → `lab`; `Pharmaceuticals` / `Pharma` / `Pharmacia` → `pharma`;
`Life Sciences` / `Lifesciences` → `lifescience`; and similarly for `industries`,
`healthcare`, `biotech`, `formulation`, `remedies`, `drugs`, `products`,
`chemicals`, `science`. The ticket asks for these to be *stripped*; folding them is
a deliberate deviation. Stripping reduces "Zee Laboratories" to `zee` — four
characters, short enough to score highly against an unrelated firm. Folding keeps
`zee lab`, which still matches every Zee spelling and matches nothing else. The
generic tokens *are* dropped, but only to build the blocking key (§5), where a
block called `pharma` would hold a third of the corpus.

## 5. Blocking

Three keys per entity, not one:

| key | catches |
|---|---|
| first token of the generic-stripped name | the common case |
| its first 4 characters | typos in the first token (`Navkar` / `Navkar`, `Pharmecia` / `Pharmacia`) |
| the name's tokens, sorted | reordered names |

Blocks larger than 400 entities are skipped as degenerate — a 4-character prefix
shared by unrelated firms is not a company, and the other two keys already cover
anything real inside it.

**The ticket asks for "first token + state" and this uses state as a score signal
instead.** State is derivable for only 58% of records, and CDSCO gets it wrong
outright on at least one (a Paonta Sahib, H.P. address labelled Punjab). Blocking
on it would have refused to consider that Zee record at all. State earns its keep
as a penalty in §6, where a disagreement pushes a pair toward a human rather than
away from a match.

Result: **38,095 candidate pairs** out of a possible 13.0 million — the O(n²) the
ticket was worried about, avoided by a factor of 340.

## 6. Scoring

```
score = token_sort_ratio(normalized names)
        - 0.09  if both states known and they differ
        - 0.05  if both PINs present and none shared
        + 0.03  if a PIN is shared
        - 0.04  if both addresses present and token_set_ratio < 0.40
```

Clamped to [0, 1]. The name carries the score; the address only adjusts it, and
only far enough to move a pair into the review band.

That ordering is the central judgment call here. A company with two plants writes
**the same name against two addresses** — Unicure India Ltd has one plant in Noida
and one in Roorkee, in different states with different PINs. Weighting the address
heavily (an earlier draft used 28%) refused to merge those and pushed **353**
cluster pairs to review, most of them "same name, other plant". A reviewer asked
that question 353 times stops reading it. Address-as-adjustment puts the same
Unicure question in the band exactly once, which is where it belongs, and cuts the
queue to 205.

`token_sort_ratio` rather than `token_set_ratio`: the set variant scores
`Sun Pharma` against `Sun Pharma Laboratories` as a perfect match, which is a
merge nobody authorized.

### Tiers (plan.md §4 Phase 2a)

| score | tier | what happens |
|---|---|---|
| > 0.92 | auto | merged, logged, sampled for spot-check |
| 0.75 – 0.92 | review | a human answers, one question per company pair |
| < 0.75 | no match | nothing |

## 7. The review queue is cluster-vs-cluster

Auto merges are applied **first**, then the review band is expressed as pairs of
*clusters* rather than pairs of strings. Of 2,716 raw pairs in the band, 1,183 turn
out to connect two spellings that a stronger path already merged — there is nothing
left to decide. The remaining 1,533 collapse into **205 distinct cluster pairs**.

So the reviewer is asked "are these two companies the same?" 205 times instead of
2,716 times, sees every spelling and batch count on both sides at once, and is not
asked the same question forty times for forty spellings. Rubber-stamping is the
failure mode the ticket names, and queue length is what causes it.

## 8. Results

Numbers below are from the 2026-08-07 rebuild (`--build`, then `--apply`), run as
the pre-flight for resuming the review (§9). The original 2026-08-06 build scored
21,219/2,716/205 for the auto/review/queue rows below; the PIN-prefix state
fallback (state coverage 58.1% → 82.9%, `docs/methodology.md` §5a) gave more
entities a known state between builds, and the scorer's `state_differs:` penalty
now applies to pairs it previously couldn't evaluate — so re-running `--build`
against the same 6,155 records produced a **different** score for some pairs, not
just a re-count. That's expected: a rebuild is a re-scoring against current data,
not a replay of a fixed one. See `docs/decisions.md` 2026-08-07 for the specific
pair (Bioaltus Pharmaceuticals) whose approval didn't survive the rescoring intact.

| | |
|---|---|
| distinct `manufacturer_raw` | 5,107 |
| placeholder strings excluded | 7 (78 records) |
| entities clustered | 5,100 |
| candidate pairs scored | 38,095 |
| pairs scoring ≥ 0.70 | 24,416 |
| auto tier (> 0.92) | 20,632 pairs, of which **3,211 actually joined two clusters** |
| review band (0.75–0.92) | 3,101 pairs → 1,605 already implied → **210 cluster-pair decisions** |
| clusters after auto-merge | **1,889** |

**Collapse ratio: 5,100 → 1,889 canonical manufacturers (2.70 : 1)** before the
review band is applied. **The review is now complete: 209 of 210 pairs decided
(175 approved, 34 rejected), 1 left undecided because it carries no company name
on either side to judge by.** Six review sessions ran against this rebuilt queue
across 2026-08-07 to 2026-08-09 — full session-by-session detail, including the
complete sequence of applied figures, is in §9. **Final applied figure: 1,727
manufacturers (2.95 : 1)** — the numbers the site is built against.

Largest clusters:

| canonical name | spellings | flagged batches |
|---|---|---|
| Jackson Laboratories Pvt. Ltd | 68 | 89 |
| Unicure India Ltd | 62 | 77 |
| Zee Laboratories Ltd | 48 | 66 |
| Martin & Brown Bio-Sciences Pvt. Ltd | 40 | 62 |
| Apple Formulations Pvt. Ltd | 37 | 51 |

Verified after `--apply`:

- 6,077 of 6,155 records carry a `manufacturer_id`; the 78 unlinked are exactly
  the placeholder records listed in §3, and all 51 Phase 1a
  `manufacturer_unknown_placeholder` rows are still unresolved.
- No `manufacturer_id` points at a missing row, and `SUM(total_flags)` over
  `manufacturers` equals the linked record count exactly.
- All 48 Zee spellings landed in one cluster.

### Canonical name and address

`canonical_name` is the most-recorded spelling of the *name* portion; ties break
toward mixed case over ALL CAPS and then toward the longer string. `address_raw`
is the full raw string of the most-recorded spelling. Every spelling in the
cluster — including the ones that lost — is preserved verbatim in `known_aliases`,
so a merge never destroys published text (§1.1). `state` is the majority of the
non-null derived states in the cluster, `first_seen_month` the earliest
`alert_month`, `total_flags` the record count.

A company with two plants therefore resolves to **one** entity with one
representative address. That matches the §3.2 schema, which has a single
`address_raw`, and matches what Phase 4's "repeat manufacturers" analysis needs.
The per-plant detail is not lost — it is all in `known_aliases`.

## 9. Human review — status

**Complete.** Every pair in the 0.75–0.92 band that could be judged on its
evidence has been. What follows is the full session history, oldest first, kept
rather than compressed because the false-match patterns it documents (Centaur/
Century, the Baddi "Medi-" cluster, the transitivity chain risk) are exactly
what a future re-review needs to recognize fast.

| | |
|---|---|
| review-band pairs decided | **209 of 210** — 175 approved, 34 rejected |
| score range of the decided pairs | 0.750 – 0.919 |
| review-band pairs left undecided | **1** — no company name on either side; not deferred, undecidable |
| auto-tier clusters spot-checked | **5**, all verdict `correct` |
| spot-check sample | weakest-cohesion first: internal name similarity 0.88–0.889, cluster sizes 4–38 |

The first pass (2026-08-06) decided 15 of the then-205 pairs, all in a single
0.910–0.919 score band. The second pass (2026-08-07, `src/resolve/triage_review.py`
ordering the queue into `multi_plant`/`near_typo`/`other`) decided 12 more —
started against the rescored 210-pair queue (§8), stopped deliberately partway
through the `multi_plant` bucket at the reviewer's own call, and covered a wider
score range (0.860–0.910) because the triage grouping surfaced same-name,
different-state pairs the first pass's straight score-order hadn't reached yet.
All 12 were multi-plant Indian pharma manufacturers confirmed by a human reading
the actual cluster evidence — Apex Formulations, Aristo Pharmaceuticals (3
plants), Alkem Laboratories, Hetero Labs (3 plants), Intas Pharmaceuticals, Linux
Life Sciences, Sanofi India. One pair (Bal Pharma) was explicitly skipped by the
reviewer rather than decided either way. Full detail: `docs/decisions.md`
2026-08-07.

One of the 15 first-pass approvals (Bioaltus Pharmaceuticals, `pair_id
fff35c61ddf622bb`) did not survive the rescoring between passes — the exact pair
it was recorded against no longer exists in the rebuilt queue, and the same
underlying question now appears as two different, still-undecided pairs. That
approval is not among the decided count above; the question needs deciding again
under its new pair_id.

A third pass, same day, finished the `near_typo` bucket: **14 of 14 decided — 9
approved, 5 rejected.** This is where rejections start appearing, and each is a
real finding, not noise:

- **Centaur Pharmaceuticals vs Century Pharmaceuticals** — three different
  Centaur plants (Haryana, two in Goa) each scored 0.7986 against the same lone
  Century Pharmaceuticals (Halol, Gujarat) entry. Same score, three times, against
  one name — the reviewer read this as a name-similarity coincidence ("Centaur"
  and "Century" share length and several letters) rather than three independent
  pieces of evidence for one relationship, and rejected all three.
- **Karnal Pharmaceuticals (Selaqui, Uttarakhand) vs a second Karnani
  Pharmaceuticals entity in Rajasthan**, carrying an Ayurvedic manufacturing
  licence (`RJ 529-AYU`) rather than an allopathic one. Approving it would have
  chain-merged the already-approved Selaqui cluster (a different Karnal/Karnani
  pair, same physical address, approved earlier the same session) into an
  unrelated Rajasthan entity through transitivity — flagged and rejected before
  that chain could form.
- **Regain Laboratories (Hisar) vs Regal Laboratories (Goindwal Sahib, Punjab)**
  — different names, different states, `address_unlike:0.11`. The same shape as
  the already-documented Deep Pharma / Deepin Pharmaceuticals near-miss.

A fourth pass (2026-08-08) worked the `other` bucket — no name-shape shortcut,
each pair read on its own evidence — across four applied checkpoints, deciding
**80 of 141** (67 approved, 13 rejected) before stopping deliberately with 61
still pending. Most of the 61 rejects and approves in this bucket were
straightforward once the raw address text was read in full: an identical plot
number settles most of them either way. A few are worth recording:

- **Vivek Pharmaceuticals Pvt. Ltd. / Vivek Pharmachem (India) Ltd** — the same
  Jammu plant address under two different legal-suffix spellings, approved into
  what was already a large cluster; this is the merge that pushed Vivek
  Pharmachem into `FINDINGS.md` §3's top-8 table (rank 6, 45 flags).
- **Five more name-similarity false matches rejected**, same shape as
  Centaur/Century: Medley Pharmaceuticals vs Medline Pharmaceuticals, Indica
  Pharmaceuticals vs Indilina Pharmaceuticals, Aryatech Pharma vs Arya
  Pharmaceuticals, Integrated Laboratories vs Intermed Laboratories, Healthy
  Life Pharma vs Healthwise Pharma, Life Pharmaceuticals vs Lifecom
  Pharmaceuticals — different names, different states, no corroborating signal,
  every one of them.
- **A Baddi-specific pattern**: several small firms sharing the same industrial
  town (Baddi, H.P.) but different specific plots scored in-band against each
  other purely on name shape — Medipol/Mediosa, Medicef/Mediosa, Medion/Mediwell
  all rejected as distinct firms coincidentally sharing a very short list of
  "Medi-" name stems and a postal code.
- **A data-quality finding outside this review's scope**: one already
  auto-merged cluster (Pulse Pharmaceuticals, centered on Roorkee, Uttarakhand)
  contains a member reading "...Sua Asil, Raiwind Road Lhore" — Raiwind Road is
  in Lahore, **Pakistan**, not India. That merge happened at the automatic
  (>0.92) tier before any review pass, so no single review-band decision made
  or could have made it; it needs its own look, not a fix folded into this one.

A fifth pass (2026-08-09) finished the `other` bucket outright — **all remaining
61 pairs decided, 41 approved / 20 rejected** — closing every pair that had no
name-shape shortcut to lean on. A sixth pass, same session, then cleared the
entire `multi_plant` bucket: **28 of the 29 remaining decided (27 approved, 1
rejected), 1 left genuinely undecidable.** Three things from this final stretch
are worth recording:

- **The orphaned Bioaltus pair finally closed the loop it opened.** The
  original 2026-08-06 approval (Baddi, H.P. vs Rangpo, Sikkim) that the
  2026-08-07 rescoring silently invalidated (§8) resurfaced here as two new
  pairs under new pair_ids, and both were re-approved with the same reasoning
  as the original — Baddi↔Sikkim directly, and Baddi↔a third, typo'd-PIN
  Sikkim variant. The second Rajasthan "Karnani Pharmaceuticals (P) Ltd."
  entity carrying an Ayurvedic licence (`RJ 529-AYU`) — flagged and rejected
  once already at the `near_typo` stage — resurfaced twice more from different
  angles in `multi_plant` and was rejected again both times, for the same
  transitivity reason.
- **One pair was genuinely undecidable, not merely hard.** Neither side named
  a manufacturer at all — two bare addresses (`Plot No. 20, Ext. HPSIDC Ind
  Area, Baddi` vs `Plot No.11, Pharmacity-Selaqui, Dehradun`) scored against
  each other on nothing but coincidence. Left pending rather than guessed at —
  this is the 1 pair that keeps the review from reading as 210/210.
- **A striking number of the last ~90 pairs were the *same* company reaching
  the review band from multiple angles** — Sanofi India, Lupin, Centaur, Sun
  Pharma, Stadmed, Tosc International, Vivek Pharmachem, and Micro Labs
  (the real one, not "Microwin") all had 2–4 of their own plants surface as
  separate pairs, each approved consistently with the others. This is the
  expected shape for large multi-state manufacturers sitting just under the
  auto-merge threshold — one real company, several pairwise questions, not
  several real companies coincidentally sharing a name.

**Applied result: 1,889 → 1,727 manufacturers, collapse ratio 2.70 → 2.95 : 1.**
The full sequence of applied figures, in order: 1,856 (pre-rebuild) → 1,889
(rebuild baseline, before any review-band decision) → 1,865 (26 decided) →
1,856 (40 decided) → 1,817 → 1,808 → 1,803 → 1,797 → 1,791 (120 decided) →
1,786 → 1,777 → 1,772 → 1,767 → 1,760 → 1,748 (181 decided, `other` complete) →
1,727 (209 decided, review complete). Only the rebuild step moves the count up
— every decision applied against the fixed 210-pair queue after that moves it
down or leaves it unchanged, never up, which is exactly what "undecided is
treated as not-merged" guarantees.

The 1 still-undecided pair is treated as *not merged*, same as the 34
explicitly rejected — rejection is a recorded decision, not a pending state,
and neither counts toward a future merge unless someone reopens it. `--apply`
still runs with `--allow-pending` because that single genuinely-undecidable
pair means the queue will never report zero pending, by design — the flag is
not standing in for unfinished work anymore, it's acknowledging a pair that
has no evidence to decide on.

No wrong merge was found in the auto tier. Five clusters is a small sample and
the write-up does not claim an error *rate* from it — what it supports is that
the five riskiest clusters by the transitivity metric, including the 38-spelling
`Mascot Health Series` / `Mascot Health Services` group, were checked by a person
and held up.

If the review is ever reopened — a corpus update, a threshold change, or the 1
undecidable pair getting real address data some future month — resume with:
```
python src/resolve/manufacturers.py --build     # rescore first — see §8 on why
python src/resolve/triage_review.py             # bucket the pending pairs
python src/resolve/review_cli.py                # picks up automatically past decided pairs
python src/resolve/spotcheck_cli.py             # skips the 5 already checked
python src/resolve/manufacturers.py --apply
```

What the band contained, bucketed by `triage_review.py` — kept as a record of
the full 210-pair queue, not a to-do list:

- **41 `multi_plant` pairs — complete: 39 approved, 1 rejected, 1 undecidable.**
  Mostly one company with two or three plants: Aristo Pharmaceuticals
  (Sikkim/H.P./M.P.), Hetero Labs (H.P./Telangana/Puducherry), Alkem, Intas,
  Sanofi India, Lupin, Centaur, Sun Pharma, and others.
- **14 `near_typo` pairs — complete: 9 approved, 5 rejected.** The rejects are
  the sharpest examples yet of the "must not merge" case §9 warns about:
  `Centaur Pharmaceuticals` / `Century Pharmaceuticals` (three plants, one
  coincidentally similar name), `Karnal Pharmaceuticals` / a second `Karnani
  Pharmaceuticals` entity carrying an Ayurvedic licence, and `Regain
  Laboratories` / `Regal
  Laboratories`. Historical examples from before this bucket was decided:
  `Navkar Lifesciences` / `Navkar Lifescienses` (a CDSCO typo, approved),
  `Deep Pharma` / `Deepin Pharmaceuticals` (different companies, score 0.75).
- **141 `other` pairs — complete: 108 approved, 33 rejected.** No name-shape
  shortcut applied to any of these; every one was read on its own address
  evidence. This bucket produced most of the review's rejections — see §9's
  fourth- and fifth-pass writeups for the Centaur/Century-shaped false matches
  and the Baddi same-town-different-plot pattern found here.

## 10. Known limits

- **Transitivity.** Clustering is union-find, so A~B and B~C merge A with C even
  when A and C would never have matched directly. `--cohesion` reports the weakest
  internal name match per cluster, and `spotcheck_cli.py` puts those clusters at
  the front of its sample rather than sampling uniformly. The weakest merged
  cluster currently sits at 0.89 internal name similarity — Mascot Health
  **Series** vs Mascot Health **Services**, 38 spellings, 43 flagged batches. That
  one is at the top of the spot-check sample for a reason.
- **The merge log records the spanning edges, not all 21,219 auto pairs.** An edge
  inside an already-joined cluster changes no outcome, and the 3,229 spanning
  edges alone reconstruct or undo the clustering exactly. The full scored list is
  in `data/resolve/candidates.json` (gitignored — 7.9 MB, and regenerable).
- **A wrong merge is reversible but not automatic.** A `wrong` spot-check verdict
  is a logged finding, not an un-merge; acting on it means adjusting a threshold
  or adding a rejection and re-running `--apply`.
- **`web/` now builds against these entities** (the follow-up ticket, done):
  1,727 manufacturer pages instead of 5,107, each listing the raw spellings that
  collapsed into it.
- **A likely auto-tier data-quality error, found 2026-08-08, not yet fixed.**
  The cluster canonicalized as a Roorkee, Uttarakhand "Pulse Pharmaceuticals"
  entity contains a spanning-edge member reading "M/s.Pulse Pharmaceuticals
  (Pvt.) Ltd., Sua Asil, Raiwind Road Lhore" — Raiwind Road is in Lahore,
  **Pakistan**. That merge happened at the >0.92 automatic tier, so no human
  ever looked at it before this review incidentally surfaced it while reading a
  neighboring review-band pair. It sits outside what any single review-band
  decision can fix — un-merging a spanning edge means editing the auto-tier
  threshold logic or adding an explicit rejection to the merge log and
  re-running `--apply`, neither of which happened here. Flagged for a
  follow-up, not silently left in the data.

## Public slugs are content-derived, not positional

A manufacturer page's URL is

```
/manufacturer/<canonical-name-slug>-<cluster_hash>
    e.g.  /manufacturer/zee-laboratories-ltd-b7c4f77e
```

where `cluster_hash` is the first 8 hex characters of
`sha1("\n".join(sorted(known_aliases)))` — see `cluster_hash()` in
`scripts/export_static.py`. It is reproducible from `manufacturers.known_aliases`
alone; nothing in the web app parses it, slugs are opaque lookup keys built at
export time.

**Why not the row id.** The first version of this was
`<canonical-name-slug>-m<manufacturers.id>`. `apply()` renumbers ids `1..N` in
`(canonical_name.lower(), address_raw)` order on *every* run, so approving a
single review-band pair shifted the id — and therefore the public URL — of every
manufacturer sorting after it. Measured on the current corpus: approving one
pending pair (two Hetero Labs Limited clusters, pair `1eae55cb55ad64cc`) changed
**1,207 of 1,856** URLs under the positional scheme. That was tolerable while the
site was unpublished. It stopped being tolerable when it went live, since it is
link rot with no redirect behind it — and the 190 still-pending review decisions
are exactly the thing that would trigger it.

Cluster membership is the one property that survives re-sorting: it changes only
when *this* company's merge decision changes, never when some other cluster gains
or loses a member. The same simulated approval under the hash scheme changes
**2 slugs** (the two merged clusters disappear) and adds **1** (their union);
the other 1,854 are byte-identical.

**Verified**, not assumed:

- **Uniqueness.** `export_static.py` asserts no two clusters share a slug and
  exits non-zero if they do. 8 hex chars is 32 bits, so across ~1,900 clusters a
  collision is ~4e-4 likely — negligible, but a collision would silently merge
  two companies onto one public page, which is the reputational harm §4 Phase 2
  exists to prevent. If it ever fires, raise `SLUG_HASH_LEN`; never special-case
  the colliding pair.
- **Determinism.** Two consecutive `--apply --allow-pending` + re-export cycles
  with no decisions changed in between produce byte-identical slugs for all
  1,856 — the hash is not dict-order dependent.
- **Stability.** The simulated approval above, run on scratch copies of the DB
  and merge log so no decision was actually recorded.

`manufacturers.id` is deliberately unchanged: it stays positional, because it is
a SQL join key (`nsq_records.manufacturer_id`) and nothing outside the database
treats it as a stable public identifier any more.

The old positional slugs are **not** redirected. The site went live 2026-08-06,
nothing has had time to accumulate backlinks, and taking the one-time break now —
before resuming the 190-pair review — is the entire point of doing this first.
