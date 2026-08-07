"""Regenerate `src/resolve/pin_state.py`'s prefix tables from India Post's own
All India Pincode Directory.

The tables are *derived*, never hand-typed — same discipline as
`analysis/analyse.py` (no figure is typed by hand) and `src/resolve/labs.py`
(every entry cites where it came from). A prefix is written into the table only
if **every** post office under it in the directory sits in one state. Anything
mixed is left out and resolves to `state_ambiguous_pin:*` at lookup time, which
is the §1.4 answer: a boundary we cannot establish is reported as unknown, not
filled with the majority state.

Source
------
India Post, *All India Pincode Directory*, published on the Government of India
Open Government Data platform under the National Data Sharing and Accessibility
Policy:

    https://www.data.gov.in/resource/all-india-pincode-directory-till-last-month
    https://www.data.gov.in/files/ogdpv2dms/s3fs-public/dataurl03122020/pincode.csv

**data.gov.in returns HTTP 403 to non-browser clients**, so this script does not
download anything. Fetch the CSV yourself (any copy of India Post's directory
with `pincode` and `statename` columns works) and point `--csv` at it:

    python scripts/build_pin_table.py --csv /path/to/pincode.csv

The directory used to generate the committed table had 154,797 post-office rows
and predates the 2019 reorganisation that split Ladakh out of Jammu & Kashmir —
see STALE_PREFIXES in the generated module, which is maintained by hand for
exactly that reason.
"""

from __future__ import annotations

import argparse
import collections
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from normalize import INDIAN_STATES, STATE_ALIASES  # noqa: E402

OUT = ROOT / "src" / "resolve" / "pin_state.py"

# The directory spells several states its own way. Anything not listed here is
# title-cased ("UTTAR PRADESH" -> "Uttar Pradesh"), and the result is checked
# against INDIAN_STATES before it is written out.
DIRECTORY_NAMES = {
    "JAMMU & KASHMIR": "Jammu and Kashmir",
    "ANDAMAN & NICOBAR ISLANDS": "Andaman and Nicobar Islands",
    "DADRA & NAGAR HAVELI": "Dadra and Nagar Haveli",
    "DAMAN & DIU": "Daman and Diu",
}


def canonical(name: str) -> str:
    out = DIRECTORY_NAMES.get(name, name.title())
    return STATE_ALIASES.get(out.lower(), out)


def load(path: Path) -> dict[str, collections.Counter]:
    """prefix (2 and 3 digits) -> Counter of states seen under it."""
    pref: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    with path.open(encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh):
            pin = (row.get("pincode") or "").strip()
            state = (row.get("statename") or "").strip().upper()
            if len(pin) != 6 or not pin.isdigit():
                continue
            if not state or state == "NULL":
                continue
            pref[pin[:2]][state] += 1
            pref[pin[:3]][state] += 1
    return pref


def build(pref) -> tuple[dict[str, str], dict[str, str], list[str]]:
    two: dict[str, str] = {}
    three: dict[str, str] = {}
    mixed: list[str] = []
    for p2 in sorted(k for k in pref if len(k) == 2):
        if len(pref[p2]) == 1:
            two[p2] = canonical(pref[p2].most_common(1)[0][0])
            continue
        # Mixed at two digits — drop to the sorting district (three digits),
        # which is India Post's own next level down.
        for p3 in sorted(k for k in pref if len(k) == 3 and k.startswith(p2)):
            if len(pref[p3]) == 1:
                three[p3] = canonical(pref[p3].most_common(1)[0][0])
            else:
                mixed.append(p3)
    return two, three, mixed


HEADER = '''"""PIN-code prefix -> Indian state. Generated; do not edit by hand.

Regenerate with:  python scripts/build_pin_table.py --csv <pincode.csv>

Most of `manufacturer_raw` never names a state — it ends in a six-digit PIN and
stops. `src/normalize.py`'s `derive_state()` matches state *names* in the address
text, so those records came out null. This module is the fallback it consults
afterwards, and only afterwards: a PIN is a weaker signal than the regulator
writing the state down, so it never overrides a name match, and a PIN-derived
state is flagged as PIN-derived (plan.md §1.4 — a weaker source has to be
visible as one, not silently indistinguishable from a stronger one).

Source
------
India Post, *All India Pincode Directory* (Open Government Data platform,
National Data Sharing and Accessibility Policy):

    https://www.data.gov.in/resource/all-india-pincode-directory-till-last-month

A prefix appears below **only if every post office under it in that directory is
in one state**. India Post's structure is: first two digits = postal circle,
first three = sorting district. Fourteen two-digit prefixes straddle a state
boundary (Uttar Pradesh/Uttarakhand, Bihar/Jharkhand, Tamil Nadu/Puducherry,
Kerala/Lakshadweep, Gujarat/Dadra & Nagar Haveli, West Bengal/Sikkim, and
others), so those drop to the three-digit table. Prefixes still mixed at three
digits are in NOT_UNIFORM and deliberately map to nothing — the 2000
state-reorganisation boundaries cut across sorting districts that were drawn
before them, and picking the majority state there would be inventing a fact.
"""

'''

FOOTER = '''

# India's allocated PIN range. Six-digit runs outside it are not PINs — plot
# numbers, registration numbers and phone fragments in these addresses are
# routinely six digits long.
PIN_MIN, PIN_MAX = 110001, 855126

# A trailing six-digit run, not embedded in a longer one. Indian addresses put
# the PIN last, so the *last* match wins: "Plot No. 611612, ... Ahmedabad-382445"
# must read 382445, not 611612.
PIN_RE = re.compile(r"(?<!\\d)(\\d{6})(?!\\d)")


def extract_pin(address: str | None) -> str | None:
    """Last plausible PIN in an address, or None."""
    if not address:
        return None
    for pin in reversed(PIN_RE.findall(address)):
        if PIN_MIN <= int(pin) <= PIN_MAX:
            return pin
    return None


def state_from_pin(pin: str | None) -> tuple[str | None, str | None]:
    """(state, flag). Never guesses: an unmapped or mixed prefix returns None.

    The flag is returned on a *hit* as well as a miss. A PIN-derived state is a
    weaker claim than one CDSCO wrote out, and §1.4 says the difference has to be
    visible rather than merely tracked.
    """
    if not pin or len(pin) != 6 or not pin.isdigit():
        return None, None
    if not (PIN_MIN <= int(pin) <= PIN_MAX):
        return None, None
    p3, p2 = pin[:3], pin[:2]
    if p3 in STALE_PREFIXES:
        return None, f"state_ambiguous_pin:{p3}"
    if (state := PIN3.get(p3)) or (state := PIN2.get(p2)):
        return state, f"state_derived_from_pin:{pin}"
    return None, f"state_ambiguous_pin:{p3}"


def _report() -> None:
    """python src/resolve/pin_state.py — print the table and what it can't answer."""
    print(f"{len(PIN2)} two-digit prefixes, {len(PIN3)} three-digit overrides, "
          f"{len(NOT_UNIFORM)} sorting districts left unmapped, "
          f"{len(STALE_PREFIXES)} unmapped because the source predates the boundary\\n")
    for p, s in sorted(PIN2.items()):
        print(f"  {p}xxxx  {s}")
    print()
    for p, s in sorted(PIN3.items()):
        print(f"  {p}xxx   {s}")
    print("\\nnot uniform at three digits (state_ambiguous_pin):")
    print("  " + ", ".join(sorted(NOT_UNIFORM)))
    print("\\nsource predates the boundary (state_ambiguous_pin):")
    for p, why in sorted(STALE_PREFIXES.items()):
        print(f"  {p}   {why}")


if __name__ == "__main__":
    _report()
'''

# Hand-maintained, and the only hand-maintained thing in the generated file: the
# directory this table is built from predates a boundary change, so it would
# confidently return the wrong state for these prefixes.
STALE = {
    "194": ("Leh and Kargil. The directory predates the Jammu and Kashmir "
            "Reorganisation Act 2019 (in force 31 Oct 2019), which made Ladakh "
            "a separate union territory, so it still files 194xxx under Jammu "
            "& Kashmir. Unmapped rather than wrong."),
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", required=True, type=Path,
                    help="India Post All India Pincode Directory CSV")
    args = ap.parse_args()

    if not args.csv.exists():
        print(f"error: {args.csv} not found — see this script's docstring", file=sys.stderr)
        return 1

    pref = load(args.csv)
    two, three, mixed = build(pref)

    known = {s.lower() for s in INDIAN_STATES} | {v.lower() for v in STATE_ALIASES.values()}
    unknown = sorted({s for s in list(two.values()) + list(three.values())
                      if s.lower() not in known})
    if unknown:
        print(f"error: directory names not in INDIAN_STATES: {unknown}", file=sys.stderr)
        return 1

    def fmt(d: dict[str, str]) -> str:
        return "\n".join(f'    "{k}": "{v}",' for k, v in sorted(d.items()))

    body = [
        "from __future__ import annotations\n",
        "import re\n",
        f"# Two-digit prefixes uniform across India Post's directory ({len(two)}).",
        "PIN2 = {",
        fmt(two),
        "}\n",
        "# Two-digit prefixes that straddle a state boundary, resolved one level",
        f"# down at India Post's sorting district ({len(three)}).",
        "PIN3 = {",
        fmt(three),
        "}\n",
        "# Sorting districts that straddle a state boundary too. These resolve to",
        "# nothing on purpose — see the module docstring.",
        "NOT_UNIFORM = {",
        "\n".join(f'    "{p}",' for p in sorted(mixed)),
        "}\n",
        "# The one hand-maintained entry: prefixes where the source directory is",
        "# older than the boundary and would answer confidently and wrongly.",
        "STALE_PREFIXES = {",
        "\n".join(f'    "{p}": ("{why[:70]}"\n            "{why[70:]}"),'
                  for p, why in sorted(STALE.items())),
        "}",
    ]
    OUT.write_text(HEADER + "\n".join(body) + FOOTER, encoding="utf-8")

    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  {len(two)} two-digit prefixes")
    print(f"  {len(three)} three-digit overrides")
    print(f"  {len(mixed)} sorting districts not uniform -> state_ambiguous_pin")
    print(f"  {len(STALE)} unmapped because the source predates the boundary")
    print(f"\nnot uniform: {', '.join(sorted(mixed))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
