"""Anti-infective detection by WHO INN stem (plan.md §4 Phase 4, question 7).

## What this is, and what it is deliberately not

`nsq_records` has no therapeutic classification field, and the Phase 4 ticket is
explicit that one must not be invented. This module does something narrower and
checkable instead: it matches drug names against **published WHO INN stems** — the
syllables the World Health Organization assigns to mark a substance's
pharmacological group when it issues an International Nonproprietary Name.

    Source: WHO, "The use of stems in the selection of International
    Nonproprietary Names (INN) for pharmaceutical substances", 2018.
    https://www.who.int/publications/i/item/WHO-EMP-RHT-TSN-2018.1

Every stem below is in that document. Nothing here is a guess about what a drug
treats — a stem is a naming convention with a defined meaning, so a match is a
verifiable statement about the *name*, not a clinical claim about the product.

**This is not an ATC classification and does not attempt to be one.** The WHO ATC
index is copyrighted and not redistributable, most flagged entries are branded or
multi-ingredient products with no single ATC code, and a name-pattern match cannot
distinguish a drug's approved indication from its chemistry. What comes out of
here is: "this product's name contains a stem WHO assigns to <group>."

## Why the stems are so narrow

Loose patterns wreck this. Measured against the real corpus:

  - bare `azole` matches **367 proton-pump inhibitor records** (pantoprazole,
    rabeprazole, omeprazole, esomeprazole) which are not anti-infectives at all.
    So the stems here are `-idazole`, `-conazole` and `-bendazole`, never `azole`.
  - bare `sulpha`/`sulfa` matches every sulphate salt in the corpus — magnesium
    sulphate, salbutamol sulphate, zinc sulphate. So sulfonamides are matched on
    the full substance names only.
  - unanchored `cef` matches 23 brand names (`monocef`, `zylocef`, `pancef`).
    A brand is not an INN, so the cephalosporin stem is anchored to word-start.

Anchoring does not eliminate brands, it only stops them being matched on their
tail: about a dozen of the 45 words `cef-` matches are Indian brand names *built
on* the cef- prefix (`cefcare`, `cefikam`, `cefydoc`), one record each. They are
almost certainly cephalosporins — that is what the prefix is for — but the claim
this module makes about them is a claim about the name, not about the molecule.

Run `python analysis/drug_classes.py` to print what each stem actually matched in
the current corpus — the false-positive audit above is reproducible, not a claim.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

WHO_INN_STEM_SOURCE = (
    'WHO, "The use of stems in the selection of International Nonproprietary Names '
    '(INN) for pharmaceutical substances", 2018 — '
    "https://www.who.int/publications/i/item/WHO-EMP-RHT-TSN-2018.1"
)

# (regex, class, stem as WHO writes it, what WHO says it marks)
#
# Suffix stems are anchored at word end, prefix stems at word start. Indian
# labelling misspells INNs freely ("amoxcycillin", "intraconazole", "gentamycin"),
# and \w* on the non-anchored side absorbs that without loosening the stem itself.
STEMS: list[tuple[str, str, str, str]] = [
    (r"\b\w*cillin\b",       "antibacterial", "-cillin",   "penicillins"),
    (r"\bcef\w+\b",          "antibacterial", "cef-",      "cephalosporins"),
    (r"\b\w*oxacin\b",       "antibacterial", "-oxacin",   "quinolones"),
    (r"\b\w*cycline\b",      "antibacterial", "-cycline",  "tetracyclines"),
    (r"\b\w*mycin\b",        "antibacterial", "-mycin",    "Streptomyces-derived antibacterials"),
    (r"\b\w*micin\b",        "antibacterial", "-micin",    "Micromonospora-derived antibacterials"),
    (r"\b\w*kacin\b",        "antibacterial", "-kacin",    "aminoglycosides (kanamycin group)"),
    (r"\b\w*penem\b",        "antibacterial", "-penem",    "carbapenems"),
    (r"\b\w*bactam\b",       "antibacterial", "-bactam",   "beta-lactamase inhibitors"),
    (r"\b\w*oxazolid\w*\b|\blinezolid\b",
                             "antibacterial", "-(z)olid",  "oxazolidinones"),
    # Sulfonamides by full substance name only — see the docstring on `sulpha`.
    (r"\bsul[fp]h?amethoxazole\b|\b\w*trimoxazole\b|\btrimethoprim\b",
                             "antibacterial", "sulfa-",    "sulfonamides / co-trimoxazole"),
    (r"\bnitrofuran\w*\b|\bnitrofurantoin\b",
                             "antibacterial", "nitrofur-", "nitrofuran antibacterials"),
    (r"\brifampicin\b|\brifampin\b|\b\w*rifa\w*mycin\b",
                             "antibacterial", "rifa-",     "rifamycins"),
    (r"\bisoniazid\b|\bethambutol\b|\bpyrazinamide\b",
                             "antibacterial", "(anti-TB)", "first-line antitubercular agents"),
    (r"\bchloramphenicol\b", "antibacterial", "-phenicol", "chloramphenicol group"),
    (r"\b\w*conazole\b",     "antifungal",    "-conazole", "systemic antifungals (miconazole group)"),
    (r"\b\w*fungin\b|\bgriseofulvin\b|\bnystatin\b|\bterbinafine\b",
                             "antifungal",    "-fungin",   "other antifungals"),
    (r"\b\w*idazole\b",      "antiprotozoal", "-idazole",  "nitroimidazole antiprotozoals"),
    (r"\b\w*bendazole\b|\b\w*ectin\b|\bpraziquantel\b|\bniclosamide\b",
                             "anthelmintic",  "-bendazole/-ectin", "anthelmintics"),
    (r"\b\w*[ci]clovir\b|\b\w*navir\b|\b\w*vudine\b|\b\w*tegravir\b|\boseltamivir\b",
                             "antiviral",     "-vir",      "antivirals"),
]

COMPILED = [(re.compile(p, re.I), cls, stem, note) for p, cls, stem, note in STEMS]

# Order for stable reporting: broadest group first.
CLASS_ORDER = ["antibacterial", "antifungal", "antiprotozoal", "anthelmintic", "antiviral"]

# WHO's `-mycin` stem marks the *source organism* (Streptomyces), not what the drug
# treats, so it over-reaches on exactly the substances where those two come apart.
# Dactinomycin is a cytotoxic antineoplastic and natamycin an antifungal — both
# Streptomyces-derived, neither antibacterial.
#
# Named exceptions rather than a narrower stem, because the stem is not wrong: it
# means what WHO says it means. It just does not mean what this question needs it
# to mean, and that gap is the honest thing to encode. Found by auditing the words
# each stem matched (`python analysis/drug_classes.py`), not by assumption.
WORD_OVERRIDES: dict[str, list[str]] = {
    "dactinomycin": [],             # antineoplastic
    "natamycin": ["antifungal"],
}


def classify(name: str | None) -> list[str]:
    """Anti-infective classes whose INN stem appears in `name`. [] if none match.

    A product can match more than one — combination products are common in this
    corpus ("Amoxycillin and Potassium Clavulanate", "Ofloxacin & Ornidazole") and
    collapsing them to a single class would misreport what CDSCO tested.
    """
    if not name:
        return []
    found: set[str] = set()
    for rx, cls, _, _ in COMPILED:
        for word in rx.findall(name):
            w = word.lower() if isinstance(word, str) else ""
            found.update(WORD_OVERRIDES[w] if w in WORD_OVERRIDES else [cls])
    return [c for c in CLASS_ORDER if c in found]


def is_anti_infective(name: str | None) -> bool:
    return bool(classify(name))


def stem_audit(names: list[str]) -> list[dict]:
    """Every stem, what it matched, and the distinct words it matched on.

    This is the false-positive check. It is a function rather than a one-off script
    because the stems are only defensible if the words they catch can be inspected.
    """
    out = []
    for rx, cls, stem, note in COMPILED:
        words: Counter = Counter()
        records = 0
        for n in names:
            ms = rx.findall(n or "")
            if ms:
                records += 1
                for m in ms:
                    words[m.lower()] += 1
        out.append({
            "stem": stem, "class": cls, "who_note": note,
            "records": records,
            "distinct_words": len(words),
            "words": [w for w, _ in words.most_common()],
        })
    return out


def main() -> int:
    import sqlite3
    db = Path(__file__).resolve().parents[1] / "data" / "medcheck.db"
    conn = sqlite3.connect(db)
    names = [r[0] for r in conn.execute(
        "SELECT drug_name_clean FROM nsq_records WHERE drug_name_clean IS NOT NULL")]
    print(f"{len(names)} drug names from {db.name}\n")
    print(f"{'stem':22} {'class':14} {'recs':>6}  words matched")
    for a in stem_audit(names):
        shown = ", ".join(a["words"][:6])
        more = f" (+{a['distinct_words'] - 6} more)" if a["distinct_words"] > 6 else ""
        print(f"{a['stem']:22} {a['class']:14} {a['records']:6}  {shown}{more}")
    matched = sum(1 for n in names if is_anti_infective(n))
    print(f"\n{matched} of {len(names)} records name an anti-infective by INN stem "
          f"({matched / len(names) * 100:.1f}%)")
    print(f"\nsource: {WHO_INN_STEM_SOURCE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
