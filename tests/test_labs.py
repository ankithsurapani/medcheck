"""Regression cases for laboratory classification (src/resolve/labs.py).

    .venv/bin/python tests/test_labs.py

Every string here is real `testing_lab` text from data/medcheck.db. The cases that
matter are the collisions: `RDTL` names CDSCO laboratories at Guwahati and
Chandigarh *and* Karnataka state laboratories at Bellary and Hubli, and the
spelled-out "Drugs Testing Laboratory" appears inside both "Central Drugs Testing
Laboratory, Chennai" (CDSCO) and "Drugs Testing Laboratory, Chennai-06" (Tamil
Nadu). Getting either backwards moves records between a central regulator and a
state government.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from resolve.labs import CENTRAL, STATE, UNKNOWN, classify_lab  # noqa: E402

failures: list[str] = []


def check(label, got, want):
    if got != want:
        failures.append(f"{label}\n     got:  {got!r}\n     want: {want!r}")


def kind(raw):
    return classify_lab(raw)[0]


# --- CDSCO's own laboratories --------------------------------------------
CENTRAL_CASES = [
    "CDL Kolkata", "CDL, Kolkata", "CDTL Kolkata",
    "CDL Kasauli", "Central Drugs Laboratory, Kasauli",
    "CDTL Mumbai", "CDTL, Mumbai", "CDTL-Mumbai",
    "CDTL Chennai", "CDTL- Chennai", "CDL Chennai",
    "CDTL Hyderabad", "CDTL,Hyderabad", "CDTL HYDERABAD",
    "CDTL Indore", "CDTL -Indore", "CDTL,Indore",
    "RDTL Guwahati", "RDTL, Guwahati", "RDTL,Guwahati",
    "RDTL Chandigarh", "RDTL, Chandigarh", "RDTL,Chandigarh",
]
for s in CENTRAL_CASES:
    check(f"central: {s!r}", kind(s), CENTRAL)


# --- the RDTL collision ---------------------------------------------------
# Karnataka established regional laboratories at Hubli and Bellary in Dec 2008
# under its Drugs Control Department; Kerala runs one at Ernakulam. A rule that
# read "RDTL means CDSCO" would hand 89 state records to the central regulator.
for s in ["RDTL, Bellary, Karnataka", "RDTL, Hubli, Karnataka",
          "RDTL Ernakulam", "RDTL, Ernakulam, Kerala", "RDTL Ernakulam,Kerala"]:
    check(f"state RDTL: {s!r}", kind(s), STATE)


# --- the spelled-out collision -------------------------------------------
# "Drugs Testing Laboratory" is a substring of the central labs' full names, and
# Chennai hosts BOTH a CDSCO lab and a Tamil Nadu state lab.
check("central Chennai spelled out",
      kind("Central Drugs Testing Laboratory, Chennai"), CENTRAL)
check("state Chennai spelled out",
      kind("Drugs Testing Laboratory, Chennai-06"), STATE)
check("state Chennai spelled out, trailing dot",
      kind("Drugs Testing Laboratory, Chennai-06."), STATE)
check("state Madurai spelled out",
      kind("Drugs Testing Laboratory, Madurai-19"), STATE)
check("state Thiruvananthapuram spelled out",
      kind("Drugs Testing Laboratory Thiruvananthapuram"), STATE)


# --- ordinary state laboratories -----------------------------------------
STATE_CASES = [
    "DTL Thiruvananthapuram", "DTL, Bengaluru, Karnataka", "DTL Chennai",
    "DTL Jaipur", "DTL Madurai", "DTL, Puducherry", "DTL Baddi H.P.", "DTL Thrissur",
    "DTLBikaner",                       # published with no space
    "SDTL, Punjab", "SDTL, Assam", "SDTL Agartala, Tripura", "SDT&RL, Bhubaneswar",
    "SFTRL, Odisha Bhubaneswar", "FDTL,Uttarakhand", "MDTL Kathua, Jammu and Kashmir",
    "State Lab Karnataka", "State Drugs Laboratory, Punjab", "State Lab Maharashtra",
    "DCL, Telangana", "FDL, Vadodara", "FDAL, Mumbai", "BDCL, PATNA",
    "Food & Drugs Laboratory, Vadodara", "King Institute Chennai",
    "Government of NCT of Delhi", "Drugs Control Department, Mizoram",
    "Drugs Inspector, Bihar", "Office of Drugs Controller, Meghalaya",
    "DCA Vijayawada, Andhara Pradesh", "Modern Drug Testing Laboratory Kathua (J&K)",
    "Combined Food & Drug Testing Laboratory Jammu",
    "NRS Medical College 138 AJC Bose Road, Kolkata",
    # A bare place name is a state reporting its own testing.
    "Karnataka", "Puducherry", "West Bengal", "NCT of Delhi", "Uttar Pradesh",
]
for s in STATE_CASES:
    check(f"state: {s!r}", kind(s), STATE)

# Maharashtra's FDA laboratory, which CDSCO files as "CDSCO lab" on all 13 of its
# records. It is a state laboratory; this is one of the disagreements the module
# exists to surface.
check("FDA Lab Mumbai is state despite CDSCO's label",
      kind("FDA Lab , Mumbai"), STATE)


# --- CDSCO offices are central, and say they are not laboratories ---------
for s in ["CDSCO, East Zone, Kolkata", "CDSCO, Sub Zone, Baddi", "CDSCO, N.Z., GZB",
          "CDSCO, SubZone Goa", "CDSCO, Hyderabad"]:
    check(f"cdsco office: {s!r}", kind(s), CENTRAL)
check("cdsco office is labelled as not a lab",
      classify_lab("CDSCO, East Zone, Kolkata")[1], "CDSCO office (not a laboratory)")


# --- declining to classify is a valid answer ------------------------------
for s in ["Not applicable", "", None, "N.A.", "  "]:
    check(f"not a lab: {s!r}", kind(s), UNKNOWN)
# Genuinely ambiguous strings stay unknown rather than being forced to a side.
for s in ["H.Q., J&K", "V.P. Khedkar, Pune-Zone 2", "CDL Kandaghat"]:
    check(f"ambiguous stays unknown: {s!r}", kind(s), UNKNOWN)


# --- the basis is always traceable ----------------------------------------
check("central basis cites a source",
      classify_lab("RDTL Guwahati")[2], "cdsco_laboratory:cdsco_seven")
check("state-run RDTL basis cites a source",
      classify_lab("RDTL, Hubli, Karnataka")[2], "state_run_regional_lab:karnataka_rdtl")
check("CDTL Indore cites its own source",
      classify_lab("CDTL Indore")[2], "cdsco_laboratory:cdtl_indore")
check("canonical name for a CDSCO lab",
      classify_lab("RDTL, Guwahati")[1], "Regional Drugs Testing Laboratory, Guwahati")


# --- report ---------------------------------------------------------------
total = (len(CENTRAL_CASES) + 5 + 5 + len(STATE_CASES) + 1 + 5 + 1 + 5 + 3 + 4)
if failures:
    print(f"FAILED {len(failures)} of {total} checks\n")
    for f in failures:
        print(f"  - {f}")
    raise SystemExit(1)
print(f"ok — {total} checks passed")
