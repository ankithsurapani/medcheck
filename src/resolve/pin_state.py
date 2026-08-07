"""PIN-code prefix -> Indian state. Generated; do not edit by hand.

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

from __future__ import annotations

import re

# Two-digit prefixes uniform across India Post's directory (51).
PIN2 = {
    "11": "Delhi",
    "12": "Haryana",
    "13": "Haryana",
    "15": "Punjab",
    "17": "Himachal Pradesh",
    "18": "Jammu and Kashmir",
    "19": "Jammu and Kashmir",
    "20": "Uttar Pradesh",
    "21": "Uttar Pradesh",
    "22": "Uttar Pradesh",
    "23": "Uttar Pradesh",
    "25": "Uttar Pradesh",
    "27": "Uttar Pradesh",
    "28": "Uttar Pradesh",
    "30": "Rajasthan",
    "31": "Rajasthan",
    "32": "Rajasthan",
    "33": "Rajasthan",
    "34": "Rajasthan",
    "37": "Gujarat",
    "38": "Gujarat",
    "41": "Maharashtra",
    "42": "Maharashtra",
    "43": "Maharashtra",
    "44": "Maharashtra",
    "45": "Madhya Pradesh",
    "46": "Madhya Pradesh",
    "47": "Madhya Pradesh",
    "48": "Madhya Pradesh",
    "49": "Chhattisgarh",
    "51": "Andhra Pradesh",
    "52": "Andhra Pradesh",
    "56": "Karnataka",
    "57": "Karnataka",
    "58": "Karnataka",
    "59": "Karnataka",
    "61": "Tamil Nadu",
    "62": "Tamil Nadu",
    "63": "Tamil Nadu",
    "64": "Tamil Nadu",
    "69": "Kerala",
    "70": "West Bengal",
    "71": "West Bengal",
    "72": "West Bengal",
    "75": "Odisha",
    "76": "Odisha",
    "77": "Odisha",
    "80": "Bihar",
    "83": "Jharkhand",
    "84": "Bihar",
    "85": "Bihar",
}

# Two-digit prefixes that straddle a state boundary, resolved one level
# down at India Post's sorting district (104).
PIN3 = {
    "141": "Punjab",
    "142": "Punjab",
    "143": "Punjab",
    "144": "Punjab",
    "145": "Punjab",
    "146": "Punjab",
    "147": "Punjab",
    "148": "Punjab",
    "241": "Uttar Pradesh",
    "242": "Uttar Pradesh",
    "243": "Uttar Pradesh",
    "245": "Uttar Pradesh",
    "248": "Uttarakhand",
    "249": "Uttarakhand",
    "261": "Uttar Pradesh",
    "263": "Uttarakhand",
    "360": "Gujarat",
    "361": "Gujarat",
    "363": "Gujarat",
    "364": "Gujarat",
    "365": "Gujarat",
    "390": "Gujarat",
    "391": "Gujarat",
    "392": "Gujarat",
    "393": "Gujarat",
    "394": "Gujarat",
    "395": "Gujarat",
    "400": "Maharashtra",
    "401": "Maharashtra",
    "402": "Maharashtra",
    "403": "Goa",
    "500": "Telangana",
    "501": "Telangana",
    "502": "Telangana",
    "503": "Telangana",
    "504": "Telangana",
    "505": "Telangana",
    "506": "Telangana",
    "508": "Telangana",
    "509": "Telangana",
    "530": "Andhra Pradesh",
    "531": "Andhra Pradesh",
    "532": "Andhra Pradesh",
    "534": "Andhra Pradesh",
    "535": "Andhra Pradesh",
    "600": "Tamil Nadu",
    "601": "Tamil Nadu",
    "602": "Tamil Nadu",
    "603": "Tamil Nadu",
    "604": "Tamil Nadu",
    "606": "Tamil Nadu",
    "608": "Tamil Nadu",
    "670": "Kerala",
    "671": "Kerala",
    "676": "Kerala",
    "678": "Kerala",
    "679": "Kerala",
    "680": "Kerala",
    "683": "Kerala",
    "685": "Kerala",
    "686": "Kerala",
    "688": "Kerala",
    "689": "Kerala",
    "731": "West Bengal",
    "732": "West Bengal",
    "733": "West Bengal",
    "734": "West Bengal",
    "735": "West Bengal",
    "736": "West Bengal",
    "737": "Sikkim",
    "741": "West Bengal",
    "742": "West Bengal",
    "743": "West Bengal",
    "744": "Andaman and Nicobar Islands",
    "781": "Assam",
    "782": "Assam",
    "784": "Assam",
    "785": "Assam",
    "786": "Assam",
    "787": "Assam",
    "788": "Assam",
    "790": "Arunachal Pradesh",
    "791": "Arunachal Pradesh",
    "792": "Arunachal Pradesh",
    "793": "Meghalaya",
    "794": "Meghalaya",
    "795": "Manipur",
    "796": "Mizoram",
    "797": "Nagaland",
    "798": "Nagaland",
    "799": "Tripura",
    "811": "Bihar",
    "812": "Bihar",
    "815": "Jharkhand",
    "816": "Jharkhand",
    "821": "Bihar",
    "822": "Jharkhand",
    "823": "Bihar",
    "824": "Bihar",
    "825": "Jharkhand",
    "826": "Jharkhand",
    "827": "Jharkhand",
    "828": "Jharkhand",
    "829": "Jharkhand",
}

# Sorting districts that straddle a state boundary too. These resolve to
# nothing on purpose — see the module docstring.
NOT_UNIFORM = {
    "140",
    "160",
    "244",
    "246",
    "247",
    "262",
    "362",
    "396",
    "507",
    "533",
    "605",
    "607",
    "609",
    "673",
    "682",
    "783",
    "813",
    "814",
}

# The one hand-maintained entry: prefixes where the source directory is
# older than the boundary and would answer confidently and wrongly.
STALE_PREFIXES = {
    "194": ("Leh and Kargil. The directory predates the Jammu and Kashmir Reorganis"
            "ation Act 2019 (in force 31 Oct 2019), which made Ladakh a separate union territory, so it still files 194xxx under Jammu & Kashmir. Unmapped rather than wrong."),
}

# India's allocated PIN range. Six-digit runs outside it are not PINs — plot
# numbers, registration numbers and phone fragments in these addresses are
# routinely six digits long.
PIN_MIN, PIN_MAX = 110001, 855126

# A trailing six-digit run, not embedded in a longer one. Indian addresses put
# the PIN last, so the *last* match wins: "Plot No. 611612, ... Ahmedabad-382445"
# must read 382445, not 611612.
PIN_RE = re.compile(r"(?<!\d)(\d{6})(?!\d)")


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
          f"{len(STALE_PREFIXES)} unmapped because the source predates the boundary\n")
    for p, s in sorted(PIN2.items()):
        print(f"  {p}xxxx  {s}")
    print()
    for p, s in sorted(PIN3.items()):
        print(f"  {p}xxx   {s}")
    print("\nnot uniform at three digits (state_ambiguous_pin):")
    print("  " + ", ".join(sorted(NOT_UNIFORM)))
    print("\nsource predates the boundary (state_ambiguous_pin):")
    for p, why in sorted(STALE_PREFIXES.items()):
        print(f"  {p}   {why}")


if __name__ == "__main__":
    _report()
