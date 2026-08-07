# MedCheck — Findings

What 6,155 medicine batches flagged by India's drug regulator between January 2019
and June 2026 do and do not show.

Every figure below is produced by [`analyse.py`](analyse.py) and cited to the
function that computes it. Re-run `python analysis/analyse.py --json` to regenerate
[`results.json`](results.json) — nothing here is typed by hand. The dataset itself
is in [`dataset/`](dataset/) under CC0.

---

## Read this first

**CDSCO does not test medicines at random.** Samples are drawn on suspicion, on
complaint, and on risk-based targeting. This dataset contains only the batches that
*failed*, and CDSCO publishes no count anywhere of what was tested and passed.

There is therefore **no denominator in this data**, which means:

> **No percentage in this document is a failure rate.** Every share below is a
> share *of the flagged batches*, and says nothing about how often medicines fail.

That is not a disclaimer to be read once and set aside. It changes what each
finding means, so it is repeated inline at every number where forgetting it would
produce a false statement.

---

## 1. How much is published, and when

`analyse.py::q1_volume` · `analyse.py::q5_trend`

**6,155 flagged batches across 90 months**, January 2019 to June 2026.

| Year | Flagged batches |
|---|---|
| 2019 | 403 |
| 2020 | 319 |
| 2021 | 345 |
| 2022 | 571 |
| 2023 | 644 |
| 2024 | 873 |
| 2025 | **1,927** |
| 2026 | 1,073 *(6 months only — the data ends at June)* |

Published flags grew **4.78×** between 2019 and 2025, the last complete year. 2026
is on pace to exceed it, but it is a truncated year and is not compared.

**This is a trend in publishing, not necessarily in drug quality**, and the data
cannot separate the two. Three specific reasons:

- **No testing volume is published.** A rise in flagged batches is consistent with
  more testing, more thorough reporting, or more failures. Nothing here
  distinguishes them, so no rate is computed anywhere in this document.
- **CDSCO changed how it publishes in August 2025**, moving from monthly PDF alerts
  to a data portal. The 12 months before that migration averaged **131.0 flagged
  batches a month**; the 12 months after averaged **172.7**. August 2025 itself is
  a local trough (97) — the shape of a reporting handover, not of a sudden
  improvement in medicine quality followed by a sudden collapse.
- **2020–2021 is visibly suppressed** (319 and 345, below 2019's 403) and those are
  the pandemic years, when inspection and sampling capacity went elsewhere. Reading
  that as "Indian medicines were better in 2020" would be the exact error this
  section exists to prevent.

The peak month is January 2026 at 222 flagged batches.

## 2. How medicines fail

`analyse.py::q2_categories`

MedCheck maps CDSCO's free-text test result onto a 21-bucket controlled vocabulary.
A batch can fail several tests at once, and **1,355 of 6,155 records (22%) do**, so
the shares below sum to more than 100%. The denominator is records.

| Failure | Records | Share of flagged batches |
|---|---|---|
| Assay (wrong amount of active ingredient) | 2,565 | 41.7% |
| Dissolution | 1,695 | 27.5% |
| Description / labelling | 1,031 | 16.8% |
| Particulate matter | 378 | 6.1% |
| Identification | 323 | 5.2% |
| Sterility | 280 | 4.5% |
| *(other — no bucket matched)* | 269 | 4.4% |
| pH | 260 | 4.2% |
| Disintegration | 234 | 3.8% |
| Related substances | 186 | 3.0% |
| Uniformity of weight | 114 | 1.9% |
| Bacterial endotoxins | 106 | 1.7% |
| Spurious | 104 | 1.7% |
| Water content | 94 | 1.5% |
| Clarity of solution | 93 | 1.5% |
| Microbial contamination | 82 | 1.3% |
| Uniformity of dispersion | 46 | 0.7% |
| Density | 43 | 0.7% |
| Extractable volume | 31 | 0.5% |
| Dimensions | 26 | 0.4% |
| Loss on drying | 24 | 0.4% |

**Two failure modes account for most of the record.** **3,947 flagged batches
(64.1%) failed assay, dissolution, or both.** Both are potency failures in effect:
assay means the tablet does not contain the stated amount of drug, dissolution
means it does not release it in the body at the required rate. Neither is
contamination — the dominant published quality problem in this data is **medicines
that may not work as labelled**, not medicines that are dangerous in themselves.

Contamination-type failures — sterility, microbial contamination, bacterial
endotoxins, particulate matter — appear on **741 batches (12.0%)**. They are the
more alarming category and the smaller one. (Both figures are unions, not sums of
the table above: adding category counts would double-count the 1,355 records that
carry more than one.)

**`other` is 4.4%**, and **exactly 20 of those records will never be categorised**:
they name no test at all ("Not applicable", "NSQ", "Does not conform to I.P.").
Assigning a category to those would invent a finding the regulator did not report.

## 3. Repeat manufacturers

`analyse.py::q3_manufacturers`

After entity resolution, **1,791 companies** account for 6,077 flagged batches
(78 records name no company — see §7).

| Top N companies | Share of companies | Flagged batches | Share of flags |
|---|---|---|---|
| 1 | 0.1% | 88 | 1.4% |
| 5 | 0.3% | 344 | 5.7% |
| 10 | 0.6% | 555 | 9.1% |
| 25 | 1.4% | 1,032 | 17.0% |
| 50 | 2.8% | 1,537 | 25.3% |
| 100 | 5.6% | 2,233 | 36.7% |
| 250 | 14.0% | 3,372 | 55.5% |

**Flags are concentrated, but less than the headline shape suggests.** 14.0% of
companies account for 55.5% of flagged batches. At the same time **922 companies
(51.5%) appear exactly once**, and the median company has a single flagged batch.
This is not a picture of a few bad actors and a clean industry; it is a long tail
with a heavy head.

The most-flagged companies:

| Flags | Company | Published spellings |
|---|---|---|
| 88 | Jackson Laboratories Pvt. Ltd | 67 |
| 77 | Unicure India Ltd | 62 |
| 66 | Zee Laboratories Ltd | 48 |
| 62 | Martin & Brown Bio-Sciences Pvt. Ltd | 40 |
| 51 | Apple Formulations Pvt. Ltd | 37 |
| 45 | Vivek Pharmachem (India) Ltd | 38 |
| 44 | Karnataka Antibiotics & Pharmaceuticals Ltd | 36 |
| 43 | Mascot Health Series Pvt. Ltd | 38 |

Vivek Pharmachem entering the top 8 (displacing Gidsha Pharmaceuticals, still at
42 flags) is this review session's clearest visible effect: three previously
separate spellings — a Jaipur, Rajasthan plant and a Jammu plant filed under
"Vivek Pharmaceuticals Pvt. Ltd." and "Vivek Pharmachem (India) Ltd." — were
confirmed as one company and merged.

Three things have to be said about this table, and none of them are optional.

**It is a lower bound on concentration.** Manufacturer resolution is *partial*:
5,107 published spellings were collapsed onto 1,791 companies, but 90 ambiguous
pairs were left unmerged pending human review (see
[`../docs/entity_resolution.md`](../docs/entity_resolution.md) §9). Every one of
those, if merged, moves flags onto *fewer* companies. Finishing the review can only
make concentration look higher, never lower.

**Appearing often may mean being tested often.** CDSCO targets its sampling. A
company already under scrutiny gets sampled more, which produces more flags, which
sustains the scrutiny. This data cannot separate "makes more failing batches" from
"is checked more".

**A flag is a batch, not a verdict on a company.** 88 flagged batches over seven
years is 88 samples out of an unpublished production volume that is certainly
enormous. Nothing here supports a statement about what share of any company's
output fails.

## 4. Central versus state laboratories

`analyse.py::q4_labs` · [`../src/resolve/labs.py`](../src/resolve/labs.py)

### The published field could not be used, so it isn't

CDSCO's own reporting-source field contradicts itself. **The same named laboratory
is filed under both labels:**

| Records | Laboratory | Filed by CDSCO as |
|---|---|---|
| 1,248 | CDL Kolkata | central 1,246 · state 2 |
| 773 | RDTL Guwahati | central 202 · **state 571** |
| 614 | RDTL Chandigarh | central 380 · **state 234** |
| 385 | CDL, Kolkata | central 365 · spurious 17 · state 3 |
| 275 | CDTL Mumbai | central 271 · state 4 |

13 of 239 laboratories appear under both labels. Per year the split drifts rather
than switching cleanly — Guwahati is mostly "State lab" 2019–2023 and mostly
"CDSCO lab" 2024–2025 — so this is inconsistent data entry, not a convention CDSCO
changed on a knowable date.

**A laboratory's identity is stable even when CDSCO's label for it is not.** So
`lab_type` is derived from *which laboratory it is*, checked against CDSCO's
published list of its own laboratories:

> CDSCO's seven National Drugs Testing Laboratories —
> <https://cdsco.gov.in/opencms/opencms/en/About-us/Laboratories/> · CDTL Indore,
> inaugurated January 2024 —
> <https://www.pib.gov.in/PressReleasePage.aspx?PRID=1994024> · Karnataka's state
> regional laboratories at Hubli and Bellary —
> <https://drugs.karnataka.gov.in/39/manual-9/en>

The trap this avoids: **`RDTL` names two different kinds of institution.** CDSCO
runs Regional Drugs Testing Laboratories at Guwahati and Chandigarh; *Karnataka*
runs Regional Drugs Testing Laboratories at Bellary and Hubli, and Kerala one at
Ernakulam. A rule reading "RDTL means central" would have moved 89 state records
onto the central regulator. Classification is therefore per named laboratory, not
per acronym.

**`alert_section` is not overwritten.** MedCheck mirrors what the regulator
published (§1.1); silently correcting the field would destroy the evidence that
CDSCO's own publications disagree. Both values are on every record, and the 857
where they conflict carry an `alert_section_disputed` flag.

### The corrected split

| | Derived from lab identity | As CDSCO published |
|---|---|---|
| Central | **3,860 (62.7%)** | 3,029 (49.2%) |
| State | **2,272 (36.9%)** | 3,079 (50.0%) |
| Unknown | 23 (0.4%) | — |

**CDSCO's published field understates central-laboratory testing by 831 records.**
Of the 857 disagreements, 832 are records filed as "State lab" that come from a
CDSCO laboratory, and 25 are the reverse — including all 13 records from Maharashtra
FDA's Mumbai laboratory, which CDSCO files as "CDSCO lab".

Only 23 records (0.4%) could not be classified, 20 of which are the literal string
"Not applicable". The remaining three are genuinely ambiguous and are left
`unknown` rather than assigned.

### What each kind of laboratory finds

Now that the split is trustworthy, the comparison the data was collected for
becomes possible. Shares are within each laboratory type, so the columns are
comparable to each other.

| Failure | Central labs | State labs | Difference |
|---|---|---|---|
| Particulate matter | 9.4% | 0.7% | **+8.7pp** |
| Dissolution | 29.5% | 24.3% | +5.2pp |
| Description / labelling | 15.0% | 19.7% | **−4.7pp** |
| *(other — no bucket matched)* | 2.7% | 7.0% | −4.3pp |
| Related substances | 4.5% | 0.6% | +3.9pp |
| Identification | 6.3% | 3.2% | +3.1pp |
| Clarity of solution | 2.4% | 0.0% | +2.4pp |
| pH | 5.0% | 3.0% | +2.0pp |

**The pattern is instrument capability, not diligence.** The tests central
laboratories report far more often — particulate matter, related substances,
clarity of solution — are the analytically demanding ones: particulate counting for
injectables, chromatography for degradation products. The tests state laboratories
report more often are description and labelling, which need a trained eye rather
than an instrument, and `other`, which is disproportionately free text that names
no standard test at all.

This says something about **where a given kind of defect is likely to be caught**,
which is a real finding about the testing system. It says nothing about which
laboratories are better, and — no denominator again — nothing about how often
either kind of laboratory finds anything, since the number of samples each tested
is not published.

## 5. Where flagged medicines are made

`analyse.py::q6_states`

**Coverage first: a manufacturing state could be derived for 5,104 of 6,155 records
— 82.9%.**

State comes from two sources, in strict order, and they never compete:

1. **The address names the state**, in full or as an unambiguous abbreviation
   ("…Baddi, Dist-Solan, H.P.-173205"). 3,576 records.
2. **The address's PIN code**, consulted only where the first found nothing.
   CDSCO usually does not write the state down — the address simply ends in six
   digits — so this is where most of the corpus lives. 1,528 records, each
   flagged `state_derived_from_pin:<pin>` in the published dataset, because a PIN
   lookup is a weaker claim than the regulator stating the state and the two must
   not be indistinguishable. Prefixes come from India Post's own All India
   Pincode Directory, and a prefix is used **only if every post office under it
   is in one state** (`src/resolve/pin_state.py`).

The remaining **1,051 records** still have no state, for three separate reasons,
none of which is guessed at:

| Why no state | Records |
|---|---|
| No state named and no PIN in the address at all | 827 |
| PIN present, but its prefix spans a state boundary (`state_ambiguous_pin`) | 181 |
| The address named two different states (`state_ambiguous`) | 43 |

The 181 are the honest cost of the rule above. India's 2000 state
reorganisation cut new boundaries across sorting districts drawn before it, so
247xxx is Saharanpur (Uttar Pradesh) *and* Roorkee (Uttarakhand); 605xxx is
Tamil Nadu *and* Puducherry. Eighteen sorting districts are like this. Naming
the majority state would have added ~180 records and a silent error rate.

Missingness is still not random — these are the records with the messiest
addresses — but it is now 17.1% rather than 41.9%. Everything below describes
the 82.9%.

| State | Records | Share of records *with a state* |
|---|---|---|
| Himachal Pradesh | 1,717 | 33.6% |
| Uttarakhand | 723 | 14.2% |
| Gujarat | 502 | 9.8% |
| Madhya Pradesh | 267 | 5.2% |
| Maharashtra | 213 | 4.2% |
| Haryana | 198 | 3.9% |
| Punjab | 176 | 3.4% |
| Uttar Pradesh | 154 | 3.0% |
| Telangana | 144 | 2.8% |
| Tamil Nadu | 135 | 2.6% |

**The clustering is real, it is geographic, and it survived the coverage jump.**
Himachal Pradesh, Uttarakhand and Gujarat account for 57.6% of records where a
state is known. Himachal Pradesh alone is 33.6% of those — and **27.9% of all
records**, the figure to quote if the 17% with no state are not to be silently
discarded. Adding 1,528 records moved the top-three share only from 61.1% to
57.6% and lifted Himachal Pradesh's share of the *whole corpus* from 20.4% to
27.9%: the concentration was not an artifact of which addresses happened to be
readable.

This is consistent with where India makes medicines: the Baddi–Solan belt in
Himachal Pradesh and the Roorkee–Haridwar belt in Uttarakhand are the country's
densest pharmaceutical manufacturing clusters, both built up under excise
exemptions. **A state with more factories will produce more flagged batches without
being worse at making medicines**, and this data has no production denominator to
correct for that either. The clustering here tracks manufacturing density; it is
not evidence of regional quality differences.

## 6. Therapeutic categories and antibiotics

`analyse.py::q7_classes` · [`drug_classes.py`](drug_classes.py)

The ticket asks two things here. One is partly answerable and one is not.

### Partly answerable: how many flagged batches are anti-infectives

`nsq_records` has no therapeutic classification field. Rather than invent one, this
matches drug names against **published WHO INN stems** — the syllables the World
Health Organization assigns to mark a substance's pharmacological group when it
issues an International Nonproprietary Name.

> Source: WHO, *The use of stems in the selection of International Nonproprietary
> Names (INN) for pharmaceutical substances*, 2018.
> <https://www.who.int/publications/i/item/WHO-EMP-RHT-TSN-2018.1>

**1,192 of 6,155 flagged batches (19.4%) name an anti-infective by INN stem:**

| Group | Records | Share of flagged batches |
|---|---|---|
| Antibacterial | 916 | 14.9% |
| Anthelmintic | 147 | 2.4% |
| Antiprotozoal | 112 | 1.8% |
| Antifungal | 82 | 1.3% |
| Antiviral | 14 | 0.2% |

Groups overlap: combination products are common in this corpus
("Ofloxacin & Ornidazole") and are counted in both groups rather than forced into
one.

**This is a claim about names, not an ATC classification.** A stem match says the
product's name contains a syllable WHO assigns to a group. It is not a clinical
claim, and roughly a dozen of the cephalosporin matches are Indian brand names
built on the `cef-` prefix rather than INNs. The stems are deliberately narrow, and
`python analysis/drug_classes.py` prints every word each one matched so the
precision can be checked rather than trusted. Two traps that a looser rule would
have walked into, both measured on this corpus:

- a bare `azole` stem matches **367 proton-pump inhibitor records** (pantoprazole,
  rabeprazole, omeprazole, esomeprazole), which are not anti-infectives at all;
- a bare `sulfa`/`sulpha` stem matches every sulphate salt — magnesium sulphate,
  salbutamol sulphate, zinc sulphate.

A third is subtler: WHO's `-mycin` stem marks the *source organism* (Streptomyces),
not the activity, so it also catches dactinomycin (a cytotoxic antineoplastic) and
natamycin (an antifungal). Both are corrected by name in `drug_classes.py`, and the
correction is the honest encoding of a stem that does not mean quite what this
question needs.

### Not answerable: whether antibiotics are over-represented

**They cannot be shown to be, with this data, and no figure in this document should
be read as showing it.**

Over-representation is a comparison, and it needs a denominator: what share of the
medicines CDSCO *tested*, or of the medicines on the Indian market, are
anti-infectives. **CDSCO publishes neither.** This dataset contains only batches
that failed.

"19.4% of flagged batches are anti-infectives" is a fact about this file. Turning it
into "anti-infectives fail more often" requires knowing that anti-infectives are
less than 19.4% of what gets tested — which is unknown, and which sampling policy
makes actively unlikely, since antibiotics are a known regulatory priority and are
plausibly sampled *more* than their market share.

Answering this properly needs a data source MedCheck does not have: CDSCO testing
volumes by drug class, or a citable breakdown of the Indian pharmaceutical market by
class. Until one exists, the honest answer is that the question is open.

## 7. Records with no manufacturer

`analyse.py::q3_manufacturers`

**78 records have no company attached, deliberately.** Their manufacturer field
holds a placeholder — "Under Investigation" (51 records), "Not Mentioned" (11),
"Not applicable" (9), "Spurious" (5), and two others — which is what CDSCO publishes
when the real maker of a batch is not known. That is normal for a suspected
counterfeit.

Resolving those into a company entity would attribute a counterfeit to a real firm.
They are excluded from every manufacturer figure in §3, and their exclusion is why
§3 totals 6,077 rather than 6,155.

Separately, **43 records are marked `label_claim_disputed`**: the company named on
the packaging has told CDSCO the batch is not theirs. On those records the
manufacturer name is the name being counterfeited, not the maker.

---

## Methodology

**Laboratory type.** `alert_section` reproduces CDSCO's reporting-source field
unchanged. `lab_type` is derived separately from the laboratory's identity
(`src/resolve/labs.py`), because that field contradicts itself on 857 records —
see §4. 90 cases in `tests/test_labs.py` pin the collisions, chiefly that `RDTL`
names both CDSCO and Karnataka laboratories.

**Ingestion.** CDSCO publishes NSQ data two ways: monthly PDF alerts, and a JSON
data portal at `cdscoonline.gov.in`. The portal covers January 2019 to the present
more completely than the PDF corpus does — there are no monthly PDF alerts at all
for 2020 or 2021 — so ingestion is JSON-first (`src/ingest/cdsco_json.py`). Every
raw portal response is cached to `data/raw/portal/` before anything is derived from
it, so the pipeline can be re-run and audited without re-fetching. Normalization
(`src/normalize.py`) maps portal fields onto the schema, deriving only what can be
derived unambiguously and flagging what cannot.

The portal is **not** a strict superset of the PDFs — one June 2025 batch appears
only in the PDF — so the PDF path is kept as a cross-check rather than retired.
Pre-2019 PDF backfill has not been done.

**Categorisation.** CDSCO's free-text test result is mapped onto a 21-bucket
controlled vocabulary by regex (`src/normalize.py`, guarded by 59 cases in
`tests/test_categorise.py`). The mapping is one-to-many: "Particulate Matter,
Extractable Volume and Description" is three failures in one cell. Text that names
no test stays in `other` rather than being forced into the nearest bucket. CDSCO's
own typos ("Sterillity", "Related Susbtances") are absorbed, since the intended test
is not in doubt.

**Entity resolution.** 5,107 published manufacturer spellings were collapsed onto
1,791 companies (`src/resolve/manufacturers.py`) using normalized-name similarity
with address, PIN code and state as secondary signals. Pairs above 0.92 similarity
were merged automatically and sampled for human spot-checking; pairs between 0.75
and 0.92 went to a human review queue. **That review is partial** — 120 of 210 pairs
decided, 90 outstanding and treated as *not merged*. Full method and audit trail:
[`../docs/entity_resolution.md`](../docs/entity_resolution.md).

**Drug classes.** WHO INN stem matching only, described in §6 above. No ATC
classification was used or approximated.

---

## Limitations

Collected in one place. Each is load-bearing for at least one finding above.

| # | Limitation | What it invalidates |
|---|---|---|
| 1 | **CDSCO does not sample at random.** Samples are drawn on suspicion, complaint and risk-targeting; only failures are published; no denominator exists anywhere in the data. | Every rate-style claim. No percentage in this document is a failure rate for medicines on the market. |
| 2 | **Manufacturer resolution is partial** — 90 review-band pairs undecided, so one company can still hold more than one id. | §3's concentration figures are a **lower bound**. |
| 3 | **`alert_section` is unreliable** — CDSCO files 13 laboratories under both labels, contradicting the laboratory's identity on 857 records. It is kept verbatim and **`lab_type` is derived instead**, from CDSCO's own published list of its laboratories. | Nothing, now — but any analysis using `alert_section` rather than `lab_type` inherits the error. §4. |
| 3b | **`lab_type` is derived, not published.** 23 records (0.4%) could not be classified and are `unknown`; CDSCO publishes no machine-readable list of which laboratories are its own, so the registry in `src/resolve/labs.py` is assembled from its website and a government press release and would need updating if CDSCO opens new laboratories. | The precision of §4's split, at the margin. |
| 4 | **State is 82.9% populated**, and missing non-randomly (messiest addresses). | §5's shares are of the 82.9%, not of the corpus. Both denominators are given. |
| 4b | **State comes from two sources of different strength.** 3,576 records have a state CDSCO named in the address; 1,528 have one read back from the address's PIN code and flagged `state_derived_from_pin`. A PIN prefix identifies a postal sorting district, not a legal boundary, so this is an inference — a well-founded one (only prefixes uniform across India Post's own directory are used), but not the regulator's statement. | Nothing in §5's shape, which barely moved when coverage rose from 58.1%. Anyone needing regulator-stated states only should filter on the flag. |
| 4c | **181 records have a PIN whose prefix straddles a state boundary** and are left empty rather than assigned the majority state — 18 sorting districts predate the 2000 state reorganisation. A further 1 prefix (194xxx, Leh/Kargil) is refused because the source directory predates Ladakh's 2019 separation. | Nothing. It is why §5's coverage is 82.9% and not ~86%. |
| 5 | **No testing-volume denominator for trends.** | §1's growth is in *published flags*. It cannot be attributed to drug quality. |
| 6 | **The August 2025 portal migration is a reporting discontinuity.** | Any before/after comparison spanning it, including the 4.78× growth figure. |
| 7 | **No therapeutic classification exists in the data**, and antibiotic over-representation has no available denominator. | §6's second question, which is documented as unanswerable rather than estimated. |
| 8 | **Pre-2019 data is absent** — the portal begins January 2019. | Any claim about long-term trends before 2019. |
| 9 | **`?` characters appear inside published text.** CDSCO's portal mangles typographic punctuation; it is not safely reversible and is left as published. | String matching on `failure_reason` and `manufacturer_raw`. |
| 10 | **A batch is not a product, and a flag is not a verdict.** One batch failing says nothing about other batches of the same medicine, or about a manufacturer overall. | Any reading of §3 as a company ranking. |

## Reproducing everything here

```bash
python src/ingest/cdsco_json.py                      # fetch + cache CDSCO responses
python src/normalize.py                              # -> data/medcheck.db
python src/resolve/manufacturers.py --build
python src/resolve/review_cli.py                     # human review (partial)
python src/resolve/manufacturers.py --apply --allow-pending
python analysis/analyse.py --json                    # -> results.json, this document's numbers
python analysis/export_dataset.py                    # -> dataset/ (CC0)
python analysis/drug_classes.py                      # INN stem audit
```

Tests: `tests/test_categorise.py` (59), `tests/test_resolve_manufacturers.py` (45),
`tests/test_drug_classes.py` (41), `tests/test_labs.py` (90).

`python analysis/analyse.py --sql q3` prints the query behind any question.
