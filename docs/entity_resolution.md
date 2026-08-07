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
review band is applied. Two review sessions ran against this same rebuilt queue
the same day: the first decided 26 of 210 (all approve, applied figure 1,865); a
second session, starting on the `near_typo` bucket, decided 14 more — **9 approve,
5 reject** (the first rejections this review has recorded — including a 3-pair
"Centaur Pharmaceuticals" vs "Century Pharmaceuticals" group the reviewer
identified as a name-similarity coincidence, not a real relationship). **Current
applied figure: 1,856 (2.73 : 1)**, with **40 of 210 pairs decided** (35 approved,
5 rejected) — the numbers the site is built against. That this lands back at the
same manufacturer count as the pre-rebuild 1,856 is coincidence, not a sign
nothing changed — both the underlying entity set and the specific decisions are
different (§9).

Largest clusters:

| canonical name | spellings | flagged batches |
|---|---|---|
| Jackson Laboratories Pvt. Ltd | 67 | 88 |
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

**Partly done, and that is a legitimate resting state.**

| | |
|---|---|
| review-band pairs decided | **40 of 210** — 35 approved, 5 rejected |
| score range of the decided pairs | 0.759 – 0.919 |
| review-band pairs still undecided | **170**, treated as *rejected* |
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

**Applied result: 1,889 → 1,856 manufacturers, collapse ratio 2.70 → 2.73 : 1.**
Landing back at the pre-rebuild count (1,856) is coincidence — the entity set
underneath is not the same one the 2026-08-06 build produced.

The 170 undecided pairs are still treated as *not merged*, which is the
conservative direction: finishing the review can only lower the manufacturer
count further, never split one apart. `--apply` was run with `--allow-pending` to
record that state deliberately rather than blocking on a queue nobody is obliged
to finish in one sitting.

No wrong merge was found in the auto tier. Five clusters is a small sample and
the write-up does not claim an error *rate* from it — what it supports is that
the five riskiest clusters by the transitivity metric, including the 38-spelling
`Mascot Health Series` / `Mascot Health Services` group, were checked by a person
and held up.

To resume:
```
python src/resolve/manufacturers.py --build     # rescore first — see §8 on why
python src/resolve/triage_review.py             # bucket the pending pairs
python src/resolve/review_cli.py                # picks up automatically past decided pairs
python src/resolve/spotcheck_cli.py             # skips the 5 already checked
python src/resolve/manufacturers.py --apply
```

What the band actually contains, for whoever sits down with it — bucketed by
`triage_review.py` as of the 210-pair queue (§8):

- **41 `multi_plant` pairs** — normalized names identical, `state_differs` signal
  present. Mostly one company with two or three plants: Aristo Pharmaceuticals
  (Sikkim/H.P./M.P.), Hetero Labs (H.P./Telangana/Puducherry), Alkem, Intas,
  Sanofi India, and others. 12 of these were decided in the 2026-08-07 session
  (all approve); **29 remain**.
- **14 `near_typo` pairs** — normalized names within edit distance 2. **Fully
  decided (2026-08-07): 9 approved, 5 rejected.** The rejects are the sharpest
  examples yet of the "must not merge" case §9 warns about: `Centaur
  Pharmaceuticals` / `Century Pharmaceuticals` (three plants, one coincidentally
  similar name), `Karnal Pharmaceuticals` / a second `Karnani Pharmaceuticals`
  entity carrying an Ayurvedic licence, and `Regain Laboratories` / `Regal
  Laboratories`. Historical examples from before this bucket was decided:
  `Navkar Lifesciences` / `Navkar Lifescienses` (a CDSCO typo, approved),
  `Deep Pharma` / `Deepin Pharmaceuticals` (different companies, score 0.75).
- **141 `other` pairs** — no name-shape shortcut applies; each needs its own
  read of both clusters' evidence. **None decided yet.**

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
  1,856 manufacturer pages instead of 5,107, each listing the raw spellings that
  collapsed into it.

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
