"""Regression cases for the failure_category mapper (plan.md §3.3).

Runs without pytest so there's no new dependency:

    .venv/bin/python tests/test_categorise.py

Every case here came from real CDSCO text in data/raw/portal/. The boundary cases
matter more than the obvious ones — they encode decisions that are easy to undo by
accident, and getting them wrong misreports what the regulator actually found.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from normalize import categorise  # noqa: E402

CASES: list[tuple[str, set[str]]] = [
    # --- single buckets ---
    ("Dissolution", {"dissolution"}),
    ("Assay", {"assay"}),
    ("Content", {"assay"}),
    ("Assay of Vitamin D3", {"assay"}),
    ("Description", {"description_labelling"}),
    ("Sterility", {"sterility"}),
    ("Disintegration", {"disintegration"}),
    ("Related Substances", {"related_substances"}),
    ("Particulate Matter", {"particulate_matter"}),
    ("Identification", {"identification"}),
    ("Misbranded", {"description_labelling"}),

    # --- the five buckets added 2026-08-06 ---
    ("pH", {"ph"}),
    ("?pH?", {"ph"}),                      # portal mangles quotes into '?'
    ("sample does not Conform to the requirement for PH", {"ph"}),
    ("Water", {"water_content"}),
    ("Water Content", {"water_content"}),
    ("Test for Water", {"water_content"}),
    ("Uniformity of weight", {"uniformity_of_weight"}),
    ("Uniformity of filled weight", {"uniformity_of_weight"}),
    ("Uniformity of Dispersion", {"uniformity_of_dispersion"}),
    ("Bacterial endotoxins", {"bacterial_endotoxins"}),
    ("BET", {"bacterial_endotoxins"}),
    ("Bacterial Endotoxins test", {"bacterial_endotoxins"}),

    # --- boundaries that must NOT map (plan.md §3.3: never force a match) ---
    # Total volatiles, not water specifically.
    ("Loss on Drying", {"other"}),
    # A solubility/impurity test, not a moisture limit.
    ("Water-soluble and Ether- soluble substances", {"other"}),
    ("Water soluble substances", {"other"}),
    ("Weight per ml", {"other"}),
    ("Specific Gravity", {"other"}),
    ("Appearance of solution", {"other"}),

    # --- multi-valued: a record can fail more than one way ---
    ("Dissolution and Assay", {"dissolution", "assay"}),
    ("Bacterial endotoxins and Sterility", {"sterility", "bacterial_endotoxins"}),
    ("pH and Assay of Heparin (Anti-factor Xa)", {"ph", "assay"}),
    ("Description & Particulate Matter", {"particulate_matter", "description_labelling"}),
    ("pH, water content & Assay", {"ph", "water_content", "assay"}),
    ("Particulate Matter, Extractable Volume and Description",
     {"particulate_matter", "description_labelling"}),

    # --- endotoxins must not collapse into microbial_contamination ---
    ("Bacterial endotoxins", {"bacterial_endotoxins"}),
    ("Microbial contamination test", {"microbial_contamination"}),

    # --- empty input is flagged, not guessed ---
    ("", {"other"}),
]


def main() -> int:
    failures = []
    for text, expected in CASES:
        got, _flag = categorise(text)
        if set(got) != expected:
            failures.append((text, sorted(expected), got))

    for text, expected, got in failures:
        print(f"FAIL  {text[:60]!r}\n        expected {expected}\n        got      {got}")

    print(f"\n{len(CASES) - len(failures)}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
