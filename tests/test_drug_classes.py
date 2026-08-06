"""Precision guards for the WHO INN stem matcher (analysis/drug_classes.py).

Runs without pytest, matching the other suites:

    .venv/bin/python tests/test_drug_classes.py

Every name here is real `drug_name_clean` text from data/medcheck.db. The
negative cases matter more than the positive ones: a loose stem silently turns
367 proton-pump-inhibitor records into "antibiotics" and the resulting finding
looks perfectly plausible. These cases pin the traps open.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))

from drug_classes import classify, is_anti_infective  # noqa: E402

failures: list[str] = []


def check(label, got, want):
    if got != want:
        failures.append(f"{label}\n     got:  {got!r}\n     want: {want!r}")


# --- positives, one per stem ----------------------------------------------
POSITIVE = [
    ("amoxycillin oral suspension ip", ["antibacterial"]),
    ("cefixime tablets ip 200 mg", ["antibacterial"]),
    ("ciprofloxacin tablets ip", ["antibacterial"]),
    ("doxycycline capsules ip", ["antibacterial"]),
    ("azithromycin tablets ip 500 mg", ["antibacterial"]),
    ("gentamicin injection ip", ["antibacterial"]),
    ("amikacin sulphate injection", ["antibacterial"]),
    ("meropenem injection ip", ["antibacterial"]),
    ("cefoperazone and sulbactam injection", ["antibacterial"]),
    ("linezolid tablets", ["antibacterial"]),
    ("sulphamethoxazole and trimethoprim tablets", ["antibacterial"]),
    ("nitrofurantoin tablets", ["antibacterial"]),
    ("rifampicin capsules ip", ["antibacterial"]),
    ("isoniazid tablets ip", ["antibacterial"]),
    ("chloramphenicol eye ointment", ["antibacterial"]),
    ("fluconazole tablets ip", ["antifungal"]),
    ("terbinafine cream", ["antifungal"]),
    ("metronidazole tablets ip 400 mg", ["antiprotozoal"]),
    ("albendazole tablets ip 400 mg", ["anthelmintic"]),
    ("ivermectin tablets", ["anthelmintic"]),
    ("aciclovir tablets ip", ["antiviral"]),
]
for name, want in POSITIVE:
    check(f"classify({name!r})", classify(name), want)


# --- combinations keep every class ----------------------------------------
# Collapsing these to one class would misreport what the regulator tested.
check("ofloxacin + ornidazole", classify("ofloxacin & ornidazole tablets"),
      ["antibacterial", "antiprotozoal"])
check("albendazole + ivermectin (vet)",
      classify("oxfendazole & ivermectin bolus (vet.) wellmox-1"), ["anthelmintic"])


# --- the traps ------------------------------------------------------------
# Proton-pump inhibitors. A bare `azole` stem matches all four of these, and they
# are 367 records in this corpus — the single most damaging false positive
# available, because "antibiotics are 25% of flagged batches" would read fine.
for ppi in ["pantoprazole tablets ip 40 mg", "rabeprazole sodium injection ip",
            "omeprazole capsules ip", "esomeprazole tablets"]:
    check(f"PPI not anti-infective: {ppi!r}", classify(ppi), [])

# Sulphate salts. A bare `sulpha`/`sulfa` stem matches every one of these.
for salt in ["magnesium sulphate injection ip", "salbutamol sulphate respirator solution",
             "zinc sulphate dispersible tablets", "atropine sulphate injection ip"]:
    check(f"sulphate salt not sulfonamide: {salt!r}", classify(salt), [])

# The -mycin stem marks the source organism, not the activity.
check("dactinomycin is antineoplastic, not antibacterial",
      classify("dactinomycin injection ip"), [])
check("natamycin is antifungal, not antibacterial",
      classify("natamycin eye drops"), ["antifungal"])

# Ordinary non-anti-infectives, including the corpus's most-flagged products.
for other in ["telmisartan tablets ip 40 mg", "paracetamol tablets ip 500 mg",
              "calcium and vitamin d3 tablets ip", "aceclofenac & paracetamol tablets",
              "compound sodium lactate injection i.p", "dextrose injection ip 5%w/v"]:
    check(f"not anti-infective: {other!r}", is_anti_infective(other), False)

check("empty name", classify(None), [])
check("blank name", classify(""), [])


# --- report ---------------------------------------------------------------
total = len(POSITIVE) + 2 + 4 + 4 + 2 + 6 + 2
if failures:
    print(f"FAILED {len(failures)} of {total} checks\n")
    for f in failures:
        print(f"  - {f}")
    raise SystemExit(1)
print(f"ok — {total} checks passed")
