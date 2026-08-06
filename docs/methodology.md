# Methodology

How MedCheck's data is obtained, identified and scored. Written for someone
checking our work — every number in the database should be traceable from here
back to a CDSCO URL.

Last updated: 2026-08-06 (Phase 1a).

---

## 1. Sources

| Source | Range | How |
|---|---|---|
| CDSCO portal JSON (`cdscoonline.gov.in`) | Jan-2019 → Jun-2026 | `src/ingest/cdsco_json.py` |
| CDSCO alert PDFs (`cdsco.gov.in`) | 2010 → Jun-2025, sporadic | `src/fetch.py` (Phase 0) |

Phase 1a loads the portal JSON only. PDF-sourced records (`source_type = "pdf"`)
are Phase 1b and are scoped to pre-2019, which the portal does not cover.

Every raw API response is written to `data/raw/portal/<tab>/<Mon-YYYY>.json`
**before** any normalization, in an envelope that records the exact request URL
and fetch timestamp. The portal is undocumented (plan.md §5.8) and could change
shape or vanish; normalization always reads that cache, never the network, so
the pipeline is reproducible from disk.

`source_url` on every record is the exact query URL that produced it. Re-running
that URL is the way to check a row against the regulator.

---

## 2. Record identity

### The problem

The NSQ endpoint returns nine fields and **no stable identifier**:

```
str_product_name, str_batch_no, dt_manufacturing_date, dt_expiry_date,
str_manufactured_by, str_nsq_result, str_reporting_source,
str_reported_by_lab_or_state, dt_reporting_month_year
```

(The spurious *current-month* endpoint, `viewPublicSpuriousDrugData`, does return
a `num_id`. The per-month `filteredSpuriousDrugTable` endpoint does not — the two
endpoints for the same tab return different field sets.)

### The scheme

```
NSQ_<alert_month>_<first 12 hex of sha256(basis)>
```

where `basis` is these six values, whitespace-collapsed and lowercased, joined
with `|`:

```
alert_month | batch_number | drug_name_raw | manufacturer_raw | testing_lab | failure_reason_raw
```

Spurious records use `SPU_<num_id>` when the portal supplies one, otherwise
`SPU_<same 12 hex>`.

### Why these six fields

plan.md §5.4: **batch numbers are not unique across manufacturers.** Different
companies reuse formats like `001` or `2451`, so batch alone can never be a key,
and neither can batch + month. `manufacturer_raw` is included precisely to keep
two companies' identically-numbered batches apart.

`failure_reason_raw` and `testing_lab` are included because CDSCO does legitimately
list the same batch twice in one month when two different labs tested it, or when
one sample failed on separate grounds reported as separate rows. Without those
fields those genuine records would collapse into one.

### Known collision risk

The id is a hash of source text, so two records collide when all six fields are
byte-identical after normalization. That happens in exactly two ways:

1. **CDSCO published the same row twice.** A true duplicate. The pipeline keeps
   one record and flags it `duplicate_source_rows_collapsed:<n>`.
2. **Two genuinely distinct tests are indistinguishable in the published data.**
   If CDSCO's own nine fields don't differ, no id scheme can separate them —
   the information isn't there.

Case 2 is detected rather than assumed away: when records share an id but differ
in any normalized field, each gets a `_1`, `_2` suffix and a
`id_collision_disambiguated:NofM` flag rather than one silently overwriting the
other via `INSERT OR REPLACE`.

**Observed on the current corpus (6,172 source rows):** 17 duplicate rows
collapsed, 2 records disambiguated. No silent loss.

### Stability

Ids are deterministic — the same source row always produces the same id, so
re-running ingestion updates rows in place. But they are **derived from source
text**, so if CDSCO edits a drug name or manufacturer address in a past month,
that record's id changes and it will appear as a new row. Ids are safe to use as
internal keys and in URLs; they are not a promise that CDSCO will never revise a
record.

---

## 3. Field derivation

| Column | Derived from | Rule |
|---|---|---|
| `alert_month` | `dt_reporting_month_year` | `"JUN-2026"` → `"2026-06"` |
| `alert_section` | `str_reporting_source` | contains "cdsco"/"central" → `central_lab`; "state" → `state_lab`; spurious endpoint → `spurious` |
| `drug_name_raw` | `str_product_name` / `product_name_from_dtl` | whitespace-collapsed only |
| `drug_name_clean` | as above | lowercased, quotes stripped — **search convenience only**, never displayed as fact |
| `batch_number` | `str_batch_no` | verbatim |
| `mfg_date` / `expiry_date` | `dt_*` | → ISO. Partial stays partial: `Jun-2025` → `2025-06`, never `2025-06-01` |
| `manufacturer_raw` | `str_manufactured_by` | verbatim (name + address in one blob) |
| `manufacturer_id` | — | always null in Phase 1a; entity resolution is Phase 2 |
| `failure_reason_raw` | `str_nsq_result` | verbatim |
| `failure_category` | `str_nsq_result` | JSON array, see §4 |
| `testing_lab` | `str_reported_by_lab_or_state` | verbatim |
| `state` | `str_manufacturing_state`, else address | see §5 |
| `label_claim_disputed` | `str_firm_reply` + `str_nsq_remarks` | see §6 |
| `source_url` | request URL | required, never null |
| `source_type` | — | `"portal_json"` |

`active_ingredients` and `dosage_form` are left null for NSQ records — the portal
publishes neither, and inferring an active ingredient from a brand name would be
a guess (§1.4). Spurious records do carry `str_dosage_form`, which is used.

---

## 4. Failure categories

`failure_category` is a **JSON array**, not a single value: CDSCO's `NSQ Result`
is routinely multi-valued — *"Particulate Matter, Extractable Volume and
Description"* is three failures in one cell.

Mapping is keyword-based against plan.md §3.3's controlled vocabulary, and the
verbatim text is always kept in `failure_reason_raw`.

**Unmatched text becomes `["other"]` plus a `failure_category_unmapped` flag. It
is never forced into the nearest bucket.** On the current corpus that is **364 of
6,155 records (5.9%)**.

### Vocabulary extension — 2026-08-06

§3.3 originally had eleven buckets and left 657 records (10.7%) in `other`. Five
buckets were added for test failures that occur constantly in CDSCO's data and
had nowhere to go:

| New bucket | Records |
|---|---|
| `ph` | 260 |
| `uniformity_of_weight` | 114 |
| `bacterial_endotoxins` | 106 |
| `water_content` | 94 |
| `uniformity_of_dispersion` | 46 |

`other` fell from 657 to 363 as a result — a 45% reduction, with 620 records
gaining a real category.

Two boundaries were drawn deliberately rather than by convenience:

- **`bacterial_endotoxins` is not folded into `microbial_contamination`.**
  Endotoxins persist after the organisms that produced them are gone, so a batch
  can fail endotoxin testing while passing sterility. Reporting one as the other
  would misstate the regulator's finding.
- **`water_content` excludes "Loss on Drying" and "Water-soluble substances".**
  LOD measures total volatiles, not water specifically; water-soluble substances
  is a solubility/impurity test. Both still fall to `other`.

Additionally, the `assay` pattern uses negative lookbehinds so that
*"water content"* and *"moisture content"* are read as `water_content` alone
rather than also matching `assay`'s bare `content` keyword.

### Still unmapped

The remaining 364 are dominated by tests that genuinely have no bucket:
Loss on Drying, weight per ml, specific gravity, length, appearance of solution,
extractable volume, and a long tail of narrative one-offs. They stay in `other`
with the specific term recorded in the flag, so a future extension can again be
made on evidence.

---

## 5. State derivation

`state` is populated only when it is unambiguous:

1. An explicit `str_manufacturing_state` field, when the endpoint provides one.
2. Otherwise, an exact whole-word match of one Indian state or UT name in
   `manufacturer_raw`.
3. Otherwise, one of seven unambiguous address abbreviations: `U.P.`, `H.P.`,
   `M.P.`, `T.N.`, `W.B.`, `J&K`, `New Delhi`/`NCT of Delhi`.

`A.P.` (Andhra vs Arunachal Pradesh) and `U.K.` (Uttarakhand vs United Kingdom)
are **excluded** — they have more than one expansion.

If two different states are named, `state` is left null with a
`state_ambiguous:X/Y` flag. This matters more than it looks:

| Address | Naive result | Actual |
|---|---|---|
| "M/s. **Karnataka** Antibiotics & Pharmaceuticals Ltd., Palghar, **Maharashtra**" | Karnataka | Maharashtra |
| "G.I.D.C, **Kerala** (Bavla), Distt. Ahmedabad, **Gujarat**" | Kerala | Gujarat (Kerala is a village) |
| "14/4, **Delhi**-Mathura Road, Faridabad, **Haryana**" | Delhi | Haryana (road name) |

**Current coverage: 3,576 of 6,155 records (58%) have a state; 43 are flagged
ambiguous; 2,536 have no derivable state.** Most of the remainder are addresses
that give only a city and PIN code. PIN-prefix → state mapping would raise
coverage substantially and is recommended for Phase 2, alongside full address
parsing.

---

## 6. `label_claim_disputed`

plan.md §5.5 — some alerts record that the named manufacturer denies making the
batch, i.e. it is a counterfeit using their label. Displaying that wrongly would
defame a legitimate company.

The spurious endpoint carries two free-text fields that hold this:
`str_firm_reply` and `str_nsq_remarks`. `label_claim_disputed` is set to 1 when
either matches a denial phrase ("has not been manufactured by them", "denied",
"the actual manufacturer", "purported to be spurious", …).

The boolean alone is never the whole record: **the firm's own wording and CDSCO's
remarks are appended verbatim to `failure_reason_raw`**, labelled
`[Firm's reply]` and `[Remarks]`, so any display can show what was actually
published rather than our interpretation of it.

**Current state: 43 of 46 spurious records are marked disputed. The NSQ endpoint
carries no dispute field at all, so `label_claim_disputed` is null — not 0 — for
all 6,109 NSQ records.** Null means "not published", not "not disputed".

### Manufacturer is often unknown

On spurious records CDSCO frequently prints `"Under Investigation"` in the
manufacturer field, because the real maker of a counterfeit is not known. 51
records carry this. They are flagged `manufacturer_unknown_placeholder` so that
Phase 2 never resolves the string into an entity and no UI renders it as a company.

---

## 7. Confidence and flags

`parse_confidence` starts at **1.0** — this is a structured source, not an OCR
guess — and each flag deducts, with a floor of 0.3. `parse_flags` is a JSON array
of specific, greppable reasons.

| Flag | Deduction |
|---|---|
| `expiry_before_mfg`, `failure_reason_empty`, `alert_month_unparsed` | 0.20 |
| `missing_required`, `date_implausible` | 0.15 |
| `date_unparsed`, `failure_category_unmapped`, `alert_section_*`, `id_collision_disambiguated` | 0.10 |
| `batch_number_implausible`, `dispute_status_unknown`, `date_two_digit_year_assumed_20xx` | 0.05 |
| `state_not_derived`, `state_ambiguous`, `duplicate_source_rows_collapsed` | 0.00 |
| unrecognised flag | 0.05 (default, so a new flag can never be silently free) |

State flags carry no penalty: `state` is an optional derived convenience, and its
absence says nothing about whether the record faithfully mirrors CDSCO.

**No record is ever dropped or silently corrected.** A row that fails a validation
rule is loaded, flagged, and scored down — that is what plan.md §1.4 requires.
2,937 of 6,155 records carry at least one flag, overwhelmingly `state_not_derived`.
