"""Sanity rules over normalized records (plan.md §1.4, Phase 1a).

A violation becomes a parse_flags entry and lowers parse_confidence. Nothing is
dropped and nothing is silently corrected — a record that fails a rule is still
published, labelled uncertain. That is the whole point of §1.4: refusing to
answer beats a confident wrong answer, and quietly "fixing" data would be the
confident wrong answer.
"""

from __future__ import annotations

import re

REQUIRED = ["drug_name_raw", "batch_number", "manufacturer_raw", "failure_reason_raw",
            "alert_month", "source_url"]

# Records are published monthly, so a manufacture date in the future, or an
# implausibly old one, means the source value is wrong or was misread.
MIN_YEAR = 1990
MAX_YEAR = 2100

# Confidence starts high because the portal is a structured source, not an OCR
# guess. Each flag class deducts; the floor is 0.3 so a flagged record is always
# distinguishable from a clean one but never scored at zero.
DEDUCTIONS = {
    "missing_required": 0.15,
    "date_unparsed": 0.10,
    "expiry_before_mfg": 0.20,
    "date_implausible": 0.15,
    "failure_category_unmapped": 0.10,
    "failure_reason_empty": 0.20,
    "alert_section_unrecognised": 0.10,
    "alert_section_missing": 0.10,
    "alert_month_unparsed": 0.20,
    "id_collision_disambiguated": 0.10,
    "batch_number_implausible": 0.05,
    "dispute_status_unknown": 0.05,
    "date_two_digit_year_assumed_20xx": 0.05,
    # Not a data defect — the state field is optional and Phase 2 owns address
    # parsing — so these are recorded without a confidence penalty.
    "state_not_derived": 0.0,
    "state_ambiguous": 0.0,
    "duplicate_source_rows_collapsed": 0.0,
    # Also no penalty, for a different reason. These mark a contradiction in
    # CDSCO's *own* publication — the same laboratory filed as "CDSCO lab" on one
    # record and "State lab" on the next — not a problem with our parse. The
    # record is intact and now carries a better-sourced lab_type than it did
    # before, so scoring it down would tell readers 857 records got less
    # trustworthy when they got more so. The flag is still recorded: §1.4 is about
    # showing the uncertainty, not about arithmetic.
    "alert_section_disputed": 0.0,
    # Declined to classify rather than guessed — same posture as state_not_derived.
    "lab_type_underived": 0.0,
}
FLOOR = 0.3
BASE = 1.0


def _year(iso: str | None) -> int | None:
    if not iso:
        return None
    m = re.match(r"^(\d{4})", iso)
    return int(m.group(1)) if m else None


def check(rec: dict) -> list[str]:
    """Return flags for one normalized record."""
    flags: list[str] = []

    for field in REQUIRED:
        if not rec.get(field):
            flags.append(f"missing_required:{field}")

    mfg, exp = rec.get("mfg_date"), rec.get("expiry_date")
    if mfg and exp and len(mfg) >= 7 and len(exp) >= 7 and exp[:7] < mfg[:7]:
        flags.append(f"expiry_before_mfg:{mfg}>{exp}")

    for label, value in (("mfg_date", mfg), ("expiry_date", exp)):
        y = _year(value)
        if y is not None and not (MIN_YEAR <= y <= MAX_YEAR):
            flags.append(f"date_implausible:{label}={value}")

    batch = (rec.get("batch_number") or "").strip()
    if batch and (len(batch) > 40 or not re.search(r"[A-Za-z0-9]", batch)):
        flags.append(f"batch_number_implausible:{batch[:30]}")

    return flags


def confidence(flags: list[str]) -> float:
    """Score a record from its flags. Unknown flag classes deduct a default 0.05
    so a new flag can never silently leave confidence untouched."""
    score = BASE
    for f in flags:
        score -= DEDUCTIONS.get(f.split(":")[0], 0.05)
    return round(max(score, FLOOR), 3)
