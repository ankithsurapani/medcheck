"""Regression cases for manufacturer entity resolution (plan.md §4 Phase 2a).

Runs without pytest, matching tests/test_categorise.py:

    .venv/bin/python tests/test_resolve_manufacturers.py

Every string here is real `manufacturer_raw` text from data/medcheck.db. The cases
that matter are the ones encoding a *decision*: which strings are a company and
which are a placeholder, where the tier boundaries sit, and which near-miss pairs
must reach a human rather than being merged automatically. Getting those wrong
attributes one company's failures to another (plan.md §1.1).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from resolve.manufacturers import (  # noqa: E402
    REVIEW_HIGH, REVIEW_LOW, is_placeholder, norm_name, pair_id, score_pair,
    split_name, tier_of,
)

failures: list[str] = []


def check(label, got, want):
    if got != want:
        failures.append(f"{label}\n     got:  {got!r}\n     want: {want!r}")


# --- name / address split -------------------------------------------------
SPLIT_CASES = [
    # M/s. prefix stripped; cut at the first comma
    ("M/s. Zee Laboratories Ltd., Behind 47, Industrial Area, Paonta Sahib-173025",
     "Zee Laboratories Ltd"),
    # no comma — cut at the address keyword "Behind"
    ("Zee Laboratories Ltd. Behind 47, Indl. Area, Paonta Sahib-173025",
     "Zee Laboratories Ltd"),
    # no comma, no keyword — cut at the first numeric token
    ("Zee Laboratories 47, Industrial Area, Paonta Sahib-173025", "Zee Laboratories"),
    # missing space after the suffix, which the comma cut still handles
    ("ZEE LABORATORIES LTD.,Behind47, Industrial Area, Paonta Sahib- 173025",
     "ZEE LABORATORIES LTD"),
    # certification boilerplate is not part of the name
    ("M/s. Navkar Lifesciences WHO-GMP Certified Company, Plot No. 76, Lodhi Majra",
     "Navkar Lifesciences"),
    ("Pharma Impex Laboratories Pvt. Ltd. (ISO 9001 : 2015 & WHO GMP Certified), Ramnagar",
     "Pharma Impex Laboratories Pvt. Ltd"),
    # "Plot No." ends the name even without a comma
    ("Gidsha Pharmaceuticals Plot No. 611 612, Mega GIDC, Kharedi, Dahod 389151, Gujarat",
     "Gidsha Pharmaceuticals"),
    # a name with no address at all stays whole
    ("Poonia Brothers Pvt Ltd", "Poonia Brothers Pvt Ltd"),
    ("GLENMARK PHARMACEUTICALS LTD.", "GLENMARK PHARMACEUTICALS LTD"),
]
for raw, want_name in SPLIT_CASES:
    check(f"split_name({raw[:50]!r})", split_name(raw)[0], want_name)


# --- name normalization ---------------------------------------------------
# Industry words are folded onto one token rather than deleted: dropping
# "Laboratories" would reduce this to "zee", short enough to collide with an
# unrelated firm.
NORM_CASES = [
    ("Zee Laboratories Ltd.", "zee lab"),
    ("ZEE LABORATORIES", "zee lab"),
    ("Zee Labs Pvt. Ltd.", "zee lab"),
    ("Gidsha Pharmaceuticals", "gidsha pharma"),
    ("Gidsha Pharma Pvt Ltd", "gidsha pharma"),
    ("Naprod Life Science Pvt. Ltd.", "naprod lifescience"),
    ("Naprod Lifesciences", "naprod lifescience"),
    ("Vee Excel Drugs & Pharmaceuticals (P) Ltd", "vee excel drugs pharma"),
    ("Hindustan Syringes & Medical Devices Ltd.", "hindustan syringes medical devices"),
    # trailing single letters are splitter debris ("...Ltd. R.S. No. 1818" cut at "No")
    ("Bajaj Healthcare Ltd. R.S.", "bajaj healthcare"),
    # a trailing "India" is a suffix, not a distinguishing token
    ("Medivin India", "medivin"),
]
for name, want in NORM_CASES:
    check(f"norm_name({name!r})", norm_name(name), want)


# --- placeholders ---------------------------------------------------------
# These are not companies. Resolving them into a manufacturer entity would give a
# counterfeit's unknown maker a company page carrying 51 flagged batches (§1.1).
# Phase 1a only flags "Under Investigation"; the rest are found here.
for s in ["Under Investigation", "under investigation", "Not Mentioned", "Not applicable",
          "Not Applicable", "Spurious", "NM", "NIL,NIL NIL", "Unknown", "N.A."]:
    check(f"is_placeholder({s!r})", is_placeholder(s), True)

# Real companies whose names brush against those words must not be swept up.
for s in ["Nilkanth Pharmaceuticals, Baddi", "M/s. Spurio Labs Pvt Ltd",
          "NM Pharma Industries, Vapi", "Poonia Brothers Pvt Ltd"]:
    check(f"is_placeholder({s!r})", is_placeholder(s), False)


# --- tier boundaries ------------------------------------------------------
# plan.md §4 Phase 2a: <0.75 no match, 0.75-0.92 human review, >0.92 auto.
check("tier_of(0.749)", tier_of(0.749), "no_match")
check("tier_of(REVIEW_LOW)", tier_of(REVIEW_LOW), "review")
check("tier_of(REVIEW_HIGH)", tier_of(REVIEW_HIGH), "review")
check("tier_of(0.9201)", tier_of(0.9201), "auto")


# --- scoring --------------------------------------------------------------
def ent(raw):
    from resolve.manufacturers import PIN_RE, core_name, norm_address
    from normalize import derive_state
    name, address = split_name(raw)
    n = norm_name(name)
    return {"raw": raw, "name": name, "norm": n, "core": core_name(n),
            "address": norm_address(address), "pins": set(PIN_RE.findall(raw)),
            "state": derive_state(raw)[0], "records": 1, "first_month": "2025-01"}


def tier(a, b):
    return tier_of(score_pair(ent(a), ent(b))["score"])


ZEE_A = "M/s. Zee Laboratories Ltd., Behind 47, Industrial Area, Paonta Sahib-173025"
ZEE_B = "ZEE LABORATORIES LTD., Behind 47, Indl. Area, Paonta Sahib- 173025"
ZEE_C = "Zee Laboratories, 47, Industrial Area, Paonta Sahib-173025, Himachal Pradesh"

# Same company, same plant, punctuation and casing apart — no human needed.
check("tier(ZEE_A, ZEE_B)", tier(ZEE_A, ZEE_B), "auto")
check("tier(ZEE_A, ZEE_C)", tier(ZEE_A, ZEE_C), "auto")

# Different companies that share a blocking token must not reach the review band,
# let alone auto-merge.
check("tier(Zee, Zenith)",
      tier(ZEE_A, "M/s. Zenith Drugs Pvt. Ltd., Plot 12, Baddi-173205, Himachal Pradesh"),
      "no_match")
check("tier(Gidsha, Glenmark)",
      tier("Gidsha Pharmaceuticals, Dahod 389151, Gujarat",
           "GLENMARK PHARMACEUTICALS LTD., Baddi-173205"),
      "no_match")

# One letter apart and a different address: exactly the call a person should make,
# not the machine. "Deep Pharma" and "Deepin Pharmaceuticals" are real, distinct
# CDSCO entries.
check("tier(Deep Pharma, Deepin Pharmaceuticals)",
      tier("Deep Pharma Unit-2, Survey No. 293/3, Kalikund, Gujarat",
           "M/s. Deepin Pharmaceuticals Pvt. Ltd., Village: Dharawara, Gujarat"),
      "review")

# Identical name, two plants in two states — the address signal is what pulls this
# down into the band. Merging it is probably right, but "probably" is the band's job.
check("tier(Unicure Noida, Unicure Roorkee)",
      tier("Unicure India Ltd, C-21, 22 & 23, Sector-3, Noida-201301, Uttar Pradesh",
           "Unicure India Ltd., Plot No. 46(B)/49B, Vill. Raipur, Roorkee-247661, Uttarakhand"),
      "review")

# pair_id is order-independent, so a decision recorded once is found again
# regardless of which side the next build puts first.
check("pair_id symmetric", pair_id(ZEE_A, ZEE_B), pair_id(ZEE_B, ZEE_A))


# --- report ---------------------------------------------------------------
total = (len(SPLIT_CASES) + len(NORM_CASES) + 14 + 4 + 7)
if failures:
    print(f"FAILED {len(failures)} of {total} checks\n")
    for f in failures:
        print(f"  - {f}")
    raise SystemExit(1)
print(f"ok — {total} checks passed")
