"""Testing-laboratory identity, and whether a lab is central or state-run.

## The problem this fixes

`alert_section` is derived from CDSCO's `str_reporting_source` field ("CDSCO lab"
/ "State lab"), and CDSCO fills that field inconsistently. Measured across the
whole corpus: **13 of 239 laboratories appear under BOTH labels**, covering 3,537
records (57.5%), with at least 459 records provably mislabelled on one side.

The two worst cases are not edge cases:

    RDTL Guwahati     202 records filed "CDSCO lab",  571 filed "State lab"
    RDTL Chandigarh   380 records filed "CDSCO lab",  234 filed "State lab"

Both are CDSCO's own National Drugs Testing Laboratories. Per year, the split
drifts rather than switching cleanly — Guwahati is mostly "State lab" 2019-2023
and mostly "CDSCO lab" 2024-2025 — so this is inconsistent data entry, not a
convention CDSCO changed on a known date.

## The fix, and what it deliberately does not do

The laboratory's *identity* is stable even when CDSCO's label for it is not. So
lab type is derived from which laboratory it is, against the published list of
CDSCO's own laboratories.

**`alert_section` is never overwritten.** plan.md §1.1 — MedCheck mirrors what the
regulator published; silently correcting the regulator's field would make this an
accuser and would destroy the evidence that the disagreement exists. The derived
value lands in a separate `lab_type` column, the published value stays exactly as
it was, and records where the two disagree get an explicit parse flag (§1.4).

## Why acronyms alone do not work

`RDTL` means two different things, and this is the trap the whole module exists
to avoid:

  - **CDSCO** runs Regional Drugs Testing Laboratories at Guwahati and Chandigarh.
    Central.
  - **Karnataka** runs Regional Drugs Testing Laboratories at Bellary and Hubli,
    established December 2008 under its Drugs Control Department. State.
    Kerala runs one at Ernakulam. State.

A rule that read "RDTL means central" would move 89 Karnataka and Kerala records
onto CDSCO. Classification is therefore per *named laboratory*, not per acronym.

## Sources

CDSCO's seven National Drugs Testing Laboratories:
    https://cdsco.gov.in/opencms/opencms/en/About-us/Laboratories/
CDTL Indore, inaugurated January 2024 (Press Information Bureau):
    https://www.pib.gov.in/PressReleasePage.aspx?PRID=1994024
Karnataka's state RDTLs at Hubli and Bellary (Karnataka Drugs Control Department):
    https://drugs.karnataka.gov.in/39/manual-9/en
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CENTRAL = "central"
STATE = "state"
UNKNOWN = "unknown"

SOURCES = {
    "cdsco_seven": "https://cdsco.gov.in/opencms/opencms/en/About-us/Laboratories/",
    "cdtl_indore": "https://www.pib.gov.in/PressReleasePage.aspx?PRID=1994024",
    "karnataka_rdtl": "https://drugs.karnataka.gov.in/39/manual-9/en",
}

# The lab-name part, as an acronym OR spelled out. The spelled-out forms MUST
# contain "CENTRAL" or "REGIONAL": without that guard, "Drugs Testing Laboratory,
# Chennai-06" — Tamil Nadu's state lab — would match the Chennai entry below and
# 80 state records would be handed to CDSCO.
CDL_PATTERN = r"(?:\bCDL\b|\bCDTL\b|\bCENTRAL\s+DRUGS?\s+(?:TESTING\s+)?LABORATORY\b)"
RDTL_PATTERN = r"(?:\bRDTL\b|\bREGIONAL\s+DRUGS?\s+TESTING\s+LABORATORY\b)"

# CDSCO's own laboratories, keyed on (name pattern, city). Each entry cites why it
# is on this list. Nothing goes here on the strength of its acronym alone.
#
# canonical name                                pattern       city          source
CENTRAL_LABS: list[tuple[str, str, str, str]] = [
    ("Central Drugs Laboratory, Kolkata",          CDL_PATTERN,  "kolkata",    "cdsco_seven"),
    ("Central Drugs Laboratory, Kasauli",          CDL_PATTERN,  "kasauli",    "cdsco_seven"),
    ("Central Drugs Testing Laboratory, Mumbai",   CDL_PATTERN,  "mumbai",     "cdsco_seven"),
    ("Central Drugs Testing Laboratory, Chennai",  CDL_PATTERN,  "chennai",    "cdsco_seven"),
    ("Central Drugs Testing Laboratory, Hyderabad", CDL_PATTERN, "hyderabad",  "cdsco_seven"),
    ("Regional Drugs Testing Laboratory, Guwahati", RDTL_PATTERN, "guwahati",  "cdsco_seven"),
    ("Regional Drugs Testing Laboratory, Chandigarh", RDTL_PATTERN, "chandigarh", "cdsco_seven"),
    # Not among the "seven" on CDSCO's page, which predates it: the Union Health
    # Minister inaugurated a CDSCO sub-zonal office and CDTL at Indore in Jan 2024,
    # and the records here start in 2024, which matches.
    ("Central Drugs Testing Laboratory, Indore",   CDL_PATTERN,  "indore",     "cdtl_indore"),
]

# Laboratories that carry a central-looking acronym but are run by a state.
# Listed explicitly and checked BEFORE the central lookup, because they are the
# whole reason acronym matching is unsafe.
STATE_RUN_DESPITE_ACRONYM: list[tuple[str, str, str, str]] = [
    ("Regional Drugs Testing Laboratory, Bellary (Karnataka)", RDTL_PATTERN, "bellary", "karnataka_rdtl"),
    ("Regional Drugs Testing Laboratory, Hubli (Karnataka)",   RDTL_PATTERN, "hubli",   "karnataka_rdtl"),
    # Kerala's regional lab. Kerala's other labs in this corpus (DTL
    # Thiruvananthapuram, DTL Thrissur, DTL Konni) are unambiguously state, and
    # Ernakulam is never claimed by CDSCO's list.
    ("Regional Drugs Testing Laboratory, Ernakulam (Kerala)",  RDTL_PATTERN, "ernakulam", "karnataka_rdtl"),
]

# CDSCO zonal and sub-zonal OFFICES, which report samples without being
# laboratories ("CDSCO, East Zone, Kolkata", "CDSCO, Sub Zone, Baddi"). The
# reporting body is still central, and the canonical name says office, not lab.
CDSCO_OFFICE = re.compile(r"\bCDSCO\b", re.I)

# Acronyms and words that mark a state laboratory or state drugs authority. Only
# consulted after the registries above, so a central lab in a state capital is
# never caught by its city name.
STATE_MARKERS = re.compile(
    # DTL is prefix-anchored, not word-bounded: CDSCO publishes "DTLBikaner" with
    # no space. Nothing central begins with DTL — CDTL and RDTL have a letter
    # before it, so \b keeps them out.
    r"(?:\bDTL\w*"
    r"|\b(?:SDTL|SDT&RL|SDFTL|SFTRL|FDTL|MDTL|DCL|FDL|FDAL|FDA|BDCL|CFDL|GDTL|DCA"
    r"|STATE|GOVERNMENT|GOVT|DIRECTORATE|MUNICIPAL"
    r"|KING\s+INSTITUTE|MEDICAL\s+COLLEGE"
    r"|DRUGS?\s+(?:TESTING\s+)?LABORATORY"
    r"|DRUGS?\s+CONTROL"
    r"|DRUGS?\s+INSPECTOR"
    r"|DRUGS?\s+CONTROLLER"
    r"|FOOD\s*(?:&|AND)?\s*DRUGS?"
    r"|COMBINED\s+FOOD)\b)",
    re.I)

# A bare place name in the reporting field is a state reporting its own testing —
# "Karnataka", "West Bengal", "NCT of Delhi". Nothing central is ever published
# under a bare place name.
#
# Duplicated from normalize.py rather than imported: normalize.py imports THIS
# module, and importing back would be a cycle. The list is short and static.
INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Chattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala",
    "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland",
    "Odisha", "Orissa", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana",
    "Tripura", "Uttar Pradesh", "Uttarakhand", "Uttaranchal", "West Bengal",
    "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli", "Daman and Diu",
    "Delhi", "NCT of Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep",
    "Puducherry", "Pondicherry",
]
BARE_STATE = re.compile(
    r"^(?:" + "|".join(re.escape(s.upper()) for s in
                       sorted(INDIAN_STATES, key=len, reverse=True)) + r")$", re.I)

# Strings that name no laboratory at all. These stay UNKNOWN rather than being
# forced to a side — the same rule Phase 1a applies to unmapped failure reasons.
NOT_A_LAB = re.compile(r"^\s*(?:not\s+applicable|not\s+available|n\.?\s*a\.?|nil|-+|\.+)\s*$", re.I)


def _normalise(raw: str) -> str:
    """Uppercase, de-punctuate, collapse whitespace. 'CDTL-Mumbai' -> 'CDTL MUMBAI'."""
    s = re.sub(r"[^A-Za-z0-9&]+", " ", raw or "")
    return re.sub(r"\s+", " ", s).strip().upper()


def _matches(norm: str, pattern: str, city: str) -> bool:
    """Both the lab-name pattern and the city must appear as whole words."""
    return bool(re.search(rf"\b{city.upper()}\b", norm)
                and re.search(pattern, norm, re.I))


def classify_lab(raw: str | None) -> tuple[str, str | None, str | None]:
    """Return (lab_type, canonical_name, basis).

    lab_type is 'central', 'state' or 'unknown'. `basis` names the evidence — a
    source key for a registry hit, or the marker that decided a state match — so
    every classification can be traced back to why.

    Order is load-bearing. State-run regional labs are checked before the central
    registry because they share its acronym; the central registry is checked
    before the state markers because "Central Drugs Testing Laboratory" contains
    the words "Drugs Testing Laboratory".
    """
    if not raw or NOT_A_LAB.match(raw):
        return UNKNOWN, None, "not_a_lab_name"

    norm = _normalise(raw)

    for name, pattern, city, source in STATE_RUN_DESPITE_ACRONYM:
        if _matches(norm, pattern, city):
            return STATE, name, f"state_run_regional_lab:{source}"

    for name, pattern, city, source in CENTRAL_LABS:
        if _matches(norm, pattern, city):
            return CENTRAL, name, f"cdsco_laboratory:{source}"

    if CDSCO_OFFICE.search(norm):
        return CENTRAL, "CDSCO office (not a laboratory)", "cdsco_office"

    if (m := STATE_MARKERS.search(norm)):
        return STATE, None, f"state_marker:{m.group(0).lower()}"

    if BARE_STATE.match(norm):
        return STATE, None, "bare_state_name"

    return UNKNOWN, None, "unrecognised_lab"


def audit(labs: dict[str, int]) -> dict:
    """Classify every distinct lab string. Input {raw: record_count}."""
    out: dict[str, list] = {CENTRAL: [], STATE: [], UNKNOWN: []}
    for raw, n in labs.items():
        lab_type, canonical, basis = classify_lab(raw)
        out[lab_type].append({"raw": raw, "records": n, "canonical": canonical,
                              "basis": basis})
    for v in out.values():
        v.sort(key=lambda r: -r["records"])
    return out


def main() -> int:
    import sqlite3
    from collections import Counter

    db = Path(__file__).resolve().parents[2] / "data" / "medcheck.db"
    conn = sqlite3.connect(db)
    labs = {r[0]: r[1] for r in conn.execute(
        "SELECT testing_lab, COUNT(*) FROM nsq_records WHERE testing_lab IS NOT NULL "
        "GROUP BY 1")}
    res = audit(labs)
    total = sum(labs.values())

    for kind in (CENTRAL, STATE, UNKNOWN):
        rows = res[kind]
        recs = sum(r["records"] for r in rows)
        print(f"\n=== {kind}: {len(rows)} lab strings, {recs} records "
              f"({recs / total * 100:.1f}%) ===")
        for r in rows[:14 if kind != UNKNOWN else 40]:
            print(f"  {r['records']:5}  {r['raw'][:46]:46} {r['basis']}")
        if len(rows) > 14 and kind != UNKNOWN:
            print(f"  ... and {len(rows) - 14} more")

    # Where the derived type contradicts what CDSCO published.
    disagree: Counter = Counter()
    for r in conn.execute(
            "SELECT testing_lab, alert_section, COUNT(*) n FROM nsq_records "
            "WHERE alert_section IN ('central_lab','state_lab') GROUP BY 1,2"):
        derived, _, _ = classify_lab(r[0])
        published = "central" if r[1] == "central_lab" else "state"
        if derived != UNKNOWN and derived != published:
            disagree[(r[0], published, derived)] += r[2]
    print(f"\n=== records where CDSCO's label disagrees with the lab's identity: "
          f"{sum(disagree.values())} ===")
    for (lab, pub, der), n in disagree.most_common(12):
        print(f"  {n:5}  {lab[:42]:42} published={pub:7} -> {der}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
