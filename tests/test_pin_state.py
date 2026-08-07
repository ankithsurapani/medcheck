"""Regression cases for PIN-code state derivation (src/resolve/pin_state.py and
`derive_state`'s use of it).

    .venv/bin/python tests/test_pin_state.py

Every address string here is real `manufacturer_raw` text from data/medcheck.db.

The cases that matter are the ones where a plausible-looking shortcut is wrong:

  * a six-digit run that is a plot number, not a PIN, and sits *before* the real
    PIN in the string;
  * a six-digit run outside India's allocated range entirely;
  * a sorting district that straddles a state boundary — 247xxx is Saharanpur
    (Uttar Pradesh) *and* Roorkee (Uttarakhand), and it is the single largest
    unmapped prefix in this corpus, so the temptation to call it is real;
  * an address that already names a state, which a PIN must never overrule.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from normalize import derive_state  # noqa: E402
from resolve.pin_state import (  # noqa: E402
    NOT_UNIFORM, PIN2, PIN3, STALE_PREFIXES, extract_pin, state_from_pin,
)

failures: list[str] = []
checks = 0


def check(label, got, want):
    global checks
    checks += 1
    if got != want:
        failures.append(f"{label}\n     got:  {got!r}\n     want: {want!r}")


# --- extraction: which six-digit run is the PIN --------------------------
EXTRACT = [
    # Plain trailing PIN, hyphenated — the common shape.
    ("M/s. Syncom Healthcare Ltd., D-42, IIE, Sidcul, Selaqui, Dehradun-248197", "248197"),
    # The portal's mangled en-dash. The PIN is still the last six-digit run.
    ("M/s. Jackson Laboratories Pvt. Ltd., 22-24, Majitha Road, Amritsar ? 143001", "143001"),
    ("M/s. Unimarck Healthcare Ltd., Plot No.24,25,37, Sector-6A, SIDCUL, Haridwar-249403",
     "249403"),
    # Space-separated, end of string.
    ("Zee Laboratories Ltd., Village Kishanpura, Baddi, Solan 173205", "173205"),
    # A six-digit plot number BEFORE the PIN. Taking the first match would read
    # this address as Uttar Pradesh (2xxxxx) instead of Gujarat.
    ("Gidsha Pharmaceuticals Plot No. 611612, Mega GIDC, Ahmedabad-382445", "382445"),
    # Six-digit runs that are not PINs at all.
    ("M/s. Someone, Licence No. 999999, Nowhere", None),          # out of range (>855126)
    ("M/s. Someone, Reg. 100000, Nowhere", None),                 # out of range (<110001)
    # Embedded in a longer digit run — a registration number, not a PIN.
    ("M/s. Someone, GSTIN 24AAACR1234567, Plot 1731234567", None),
    ("", None),
    (None, None),
]
for addr, want in EXTRACT:
    check(f"extract_pin({(addr or '')[:60]!r})", extract_pin(addr), want)


# --- lookup: two-digit, three-digit, ambiguous ---------------------------
# Clean two-digit match: 17xxxx is Himachal Pradesh throughout.
check("173205 -> HP", state_from_pin("173205"), ("Himachal Pradesh", "state_derived_from_pin:173205"))
check("382445 -> Gujarat", state_from_pin("382445")[0], "Gujarat")
check("143001 -> Punjab", state_from_pin("143001")[0], "Punjab")

# Three-digit disambiguation: 24xxxx is Uttar Pradesh *and* Uttarakhand, so the
# answer has to come from the sorting district, not the circle.
check("248197 -> Uttarakhand (24 is mixed)", state_from_pin("248197")[0], "Uttarakhand")
check("249403 -> Uttarakhand (24 is mixed)", state_from_pin("249403")[0], "Uttarakhand")
check("243001 -> Uttar Pradesh (24 is mixed)", state_from_pin("243001")[0], "Uttar Pradesh")
check("24 is not in the two-digit table", "24" in PIN2, False)
check("248 is in the three-digit table", PIN3.get("248"), "Uttarakhand")
# Same shape one zone over: 82xxxx is Bihar and Jharkhand.
check("834001 -> Jharkhand", state_from_pin("834001")[0], "Jharkhand")
check("824001 -> Bihar", state_from_pin("824001")[0], "Bihar")

# Unmapped prefix: still mixed at three digits, so no answer.
check("247667 (Roorkee) is not resolved", state_from_pin("247667"),
      (None, "state_ambiguous_pin:247"))
check("247001 (Saharanpur) is not resolved", state_from_pin("247001"),
      (None, "state_ambiguous_pin:247"))
check("247 is on the not-uniform list", "247" in NOT_UNIFORM, True)
check("605 (Puducherry/Tamil Nadu) is not resolved", state_from_pin("605001"),
      (None, "state_ambiguous_pin:605"))

# The source directory predates the 2019 Ladakh split, so 194xxx is refused
# rather than answered "Jammu and Kashmir".
check("194101 (Leh) is refused, not mis-stated", state_from_pin("194101"),
      (None, "state_ambiguous_pin:194"))
check("194 is flagged stale", "194" in STALE_PREFIXES, True)
# The rest of 19xxxx is still Jammu and Kashmir and still answers.
check("192305 -> Jammu and Kashmir", state_from_pin("192305")[0], "Jammu and Kashmir")

# Out-of-range and malformed input never reaches the table.
check("out-of-range PIN", state_from_pin("999999"), (None, None))
check("too short", state_from_pin("17320"), (None, None))
check("not digits", state_from_pin("17320A"), (None, None))
check("None", state_from_pin(None), (None, None))


# --- derive_state: the fallback is a fallback ----------------------------
# An explicit state field wins outright; the PIN is never consulted.
check("explicit field beats everything",
      derive_state("Anywhere-248197", explicit="Gujarat"), ("Gujarat", None))

# A state named in the address wins, and its flag stays None — the record is not
# marked PIN-derived just because a PIN was also present.
check("name match beats PIN (and they disagree)",
      derive_state("M/s. Someone, Plot 4, Baddi, Solan, Himachal Pradesh-248197"),
      ("Himachal Pradesh", None))
check("abbreviation match beats PIN (and they disagree)",
      derive_state("M/s. Someone, Kasna, Greater Noida-248197 (U.P.)"),
      ("Uttar Pradesh", None))

# An address naming two states is a contradiction CDSCO published. The PIN must
# not settle it — that is the §1.4 case the whole flag vocabulary exists for.
check("ambiguous address is NOT resolved by its PIN",
      derive_state("M/s. Karnataka Antibiotics Ltd., Palghar, Maharashtra-248197"),
      (None, "state_ambiguous:Karnataka/Maharashtra"))

# Only with no name match at all does the PIN get a turn.
check("PIN fallback fires on a no-match address",
      derive_state("M/s. Syncom Healthcare Ltd., D-42, IIE, Sidcul, Selaqui, Dehradun-248197"),
      ("Uttarakhand", "state_derived_from_pin:248197"))
check("unmapped prefix falls through to ambiguous, not a guess",
      derive_state("M/s. Unison Pharmaceuticals, Bhagwanpur, Roorkee-247667"),
      (None, "state_ambiguous_pin:247"))
check("no PIN and no state name stays not-derived",
      derive_state("M/s. Someone, Some Road, Some Town"),
      (None, "state_not_derived:no_match"))
check("placeholder manufacturer is never given a state",
      derive_state("Under Investigation"),
      (None, "state_not_derived:manufacturer_unknown"))


# --- the table itself -----------------------------------------------------
check("no prefix is in both tables",
      sorted(set(PIN2) & {p[:2] for p in PIN3}), [])
check("no unmapped prefix is also mapped",
      sorted(NOT_UNIFORM & set(PIN3)), [])
# A stale prefix is only worth listing because the tables *would* answer for it:
# 19 is a uniform two-digit prefix, so without the explicit refusal 194101 would
# come back "Jammu and Kashmir". The check is that every stale prefix is one the
# tables can reach, and that state_from_pin refuses it anyway.
check("stale prefixes are ones the tables would otherwise answer",
      sorted(p for p in STALE_PREFIXES if p in PIN3 or p[:2] in PIN2),
      sorted(STALE_PREFIXES))
check("and state_from_pin refuses all of them",
      [state_from_pin(p + "101")[0] for p in sorted(STALE_PREFIXES)],
      [None] * len(STALE_PREFIXES))
check("table is not empty", len(PIN2) > 40 and len(PIN3) > 90, True)


# --- report ---------------------------------------------------------------
if failures:
    print(f"FAILED {len(failures)} of {checks} checks\n")
    for f in failures:
        print(f"  - {f}")
    raise SystemExit(1)
print(f"ok — {checks} checks passed")
