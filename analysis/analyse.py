"""Phase 4 analysis — every number in analysis/FINDINGS.md, computed from the DB.

    .venv/bin/python analysis/analyse.py            # print the report
    .venv/bin/python analysis/analyse.py --json     # write analysis/results.json
    .venv/bin/python analysis/analyse.py --sql q3   # print one question's SQL

Each question is one function named `q1_...` through `q7_...`, and FINDINGS.md
cites the function beside every figure it quotes. Nothing in the write-up is
hand-typed: `--json` emits the same structure the prose is built from, so a claim
that drifts from the data can be caught by re-running this.

Three constraints from plan.md that this file enforces rather than mentions:

  §5.6  CDSCO does not sample randomly. Nothing here is a population failure rate,
        so no function returns a "rate" and every percentage carries a denominator
        that says what it is a share *of*.
  §1.4  Uncertainty is shown, not hidden. Coverage is reported next to any figure
        computed on a subset (state is populated for 58% of records), and the
        questions that the data cannot answer say so instead of approximating.
  §4    `alert_section` is informative, not authoritative — q4 measures how
        unreliable it is rather than assuming it.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from drug_classes import WHO_INN_STEM_SOURCE, classify, stem_audit  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "medcheck.db"
RESULTS = Path(__file__).resolve().parent / "results.json"

# The corpus ends mid-year. Any per-year figure that includes it and does not say
# so invents a decline that is only a truncated year.
PARTIAL_YEAR = "2026"
PORTAL_MIGRATION = "2025-08"   # CDSCO stopped publishing monthly PDFs (Phase 1a)

SQL: dict[str, str] = {
    "q1_volume": """
        SELECT substr(alert_month, 1, 4) AS year, alert_month, COUNT(*) AS n
        FROM nsq_records GROUP BY alert_month ORDER BY alert_month""",
    "q2_categories": "SELECT failure_category FROM nsq_records",
    "q3_manufacturers": """
        SELECT m.id, m.canonical_name, m.state, m.total_flags,
               json_array_length(m.known_aliases) AS aliases
        FROM manufacturers m ORDER BY m.total_flags DESC, m.canonical_name""",
    "q4_labs": """
        SELECT testing_lab, alert_section, COUNT(*) AS n FROM nsq_records
        WHERE testing_lab IS NOT NULL GROUP BY testing_lab, alert_section""",
    "q5_trend": "SELECT alert_month, COUNT(*) AS n FROM nsq_records GROUP BY 1 ORDER BY 1",
    "q6_states": "SELECT state, COUNT(*) AS n FROM nsq_records GROUP BY state ORDER BY n DESC",
    "q7_classes": "SELECT drug_name_clean FROM nsq_records",
}


def connect() -> sqlite3.Connection:
    if not DB.exists():
        raise SystemExit(f"{DB} not found — run src/normalize.py first")
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def pct(n: int, d: int) -> float:
    return round(n / d * 100, 1) if d else 0.0


# ---------------------------------------------------------------------------
def q1_volume(conn) -> dict:
    """Flagged batches by year and by month."""
    rows = conn.execute(SQL["q1_volume"]).fetchall()
    by_month = {r["alert_month"]: r["n"] for r in rows if r["alert_month"]}
    by_year: Counter = Counter()
    for month, n in by_month.items():
        by_year[month[:4]] += n
    months = sorted(by_month)
    return {
        "total": sum(by_month.values()),
        "by_year": dict(sorted(by_year.items())),
        "by_month": {m: by_month[m] for m in months},
        "month_count": len(months),
        "first_month": months[0],
        "last_month": months[-1],
        "partial_year": PARTIAL_YEAR,
        "partial_year_months": sum(1 for m in months if m.startswith(PARTIAL_YEAR)),
        "no_alert_month": conn.execute(
            "SELECT COUNT(*) FROM nsq_records WHERE alert_month IS NULL").fetchone()[0],
    }


def q2_categories(conn) -> dict:
    """Failures by §3.3 category. Multi-valued: one record can fail several ways."""
    total = 0
    counts: Counter = Counter()
    per_record: Counter = Counter()
    all_cats: list[set] = []
    for (raw,) in conn.execute(SQL["q2_categories"]):
        cats = json.loads(raw or "[]")
        total += 1
        all_cats.append(set(cats))
        per_record[len(cats)] += 1
        for c in cats:
            counts[c] += 1

    # Grouped unions, not sums. Adding category counts double-counts the 1,355
    # records that carry more than one, which would overstate both groups.
    def union(group: set) -> dict:
        n = sum(1 for c in all_cats if group & c)
        return {"records": n, "share_of_records": pct(n, total)}

    # Text that names no test at all — "Not applicable", "NSQ", "Does not conform
    # to I.P." These stay in `other` permanently: assigning a category would invent
    # a finding the regulator did not report (plan.md §1.4).
    no_test = re.compile(
        r"^\s*(?:not applicable|nsq|not of standard quality|does not conform to "
        r"i\.?p\.?\.?|n\.?a\.?|-+)\s*$", re.I)
    untestable = sum(
        1 for (r,) in conn.execute(
            "SELECT failure_reason_raw FROM nsq_records "
            "WHERE failure_category LIKE '%other%'")
        if r and no_test.match(r.strip()))

    return {
        "potency_related": union({"assay", "dissolution"}),
        "contamination_related": union({"sterility", "microbial_contamination",
                                        "bacterial_endotoxins", "particulate_matter"}),
        "other_naming_no_test": untestable,
        "records": total,
        # Shares sum to more than 100 on purpose — the denominator is records, and
        # 1,355 records carry more than one category.
        "categories": [{"category": c, "records": n, "share_of_records": pct(n, total)}
                       for c, n in counts.most_common()],
        "categories_per_record": dict(sorted(per_record.items())),
        "multi_category_records": sum(n for k, n in per_record.items() if k > 1),
        "other_records": counts.get("other", 0),
        "other_share": pct(counts.get("other", 0), total),
    }


def q3_manufacturers(conn) -> dict:
    """Concentration of flags across resolved manufacturers.

    A lower bound on real concentration, not a measurement of it: Phase 2a's review
    band is only partly decided, so some of these 1,856 entities are the same
    company still sitting on separate rows. Finishing the review can only merge
    rows, which can only move flags onto fewer companies — never more.
    """
    rows = conn.execute(SQL["q3_manufacturers"]).fetchall()
    flags = [r["total_flags"] for r in rows]
    total = sum(flags)
    n = len(rows)

    def top_share(k: int) -> dict:
        k = min(k, n)
        return {"manufacturers": k, "share_of_manufacturers": pct(k, n),
                "flags": sum(flags[:k]), "share_of_flags": pct(sum(flags[:k]), total)}

    dist: Counter = Counter(flags)
    unresolved = conn.execute(
        "SELECT COUNT(*) FROM nsq_records WHERE manufacturer_id IS NULL").fetchone()[0]
    return {
        "manufacturers": n,
        "flags_attributed": total,
        "records_without_manufacturer": unresolved,
        "resolution_is_partial": True,
        "review_pairs_pending": 190,
        "top": [dict(rank=i + 1, name=r["canonical_name"], state=r["state"],
                     flags=r["total_flags"], spellings=r["aliases"])
                for i, r in enumerate(rows[:20])],
        "concentration": [top_share(k) for k in (1, 5, 10, 25, 50, 100, 250)],
        "single_flag_manufacturers": dist.get(1, 0),
        "single_flag_share": pct(dist.get(1, 0), n),
        "median_flags": sorted(flags)[n // 2],
        "max_flags": max(flags),
    }


def q4_labs(conn) -> dict:
    """Central vs state lab — and how far `alert_section` can be trusted.

    plan.md flags a portal-vs-PDF disagreement on 27 of 184 Jun-2025 records. The
    database contains a sharper version of the same problem: the *same laboratory*
    is filed under both labels, so the disagreement is measurable across the whole
    corpus rather than inferred from one month.
    """
    sections: Counter = Counter()
    for r in conn.execute(
            "SELECT alert_section, COUNT(*) n FROM nsq_records GROUP BY 1"):
        sections[r["alert_section"] or "missing"] = r["n"]

    by_lab: dict[str, Counter] = defaultdict(Counter)
    for r in conn.execute(SQL["q4_labs"]):
        by_lab[r["testing_lab"].strip().lower()][r["alert_section"] or "missing"] += r["n"]

    ambiguous = []
    for lab, secs in by_lab.items():
        both = {s: c for s, c in secs.items() if s in ("central_lab", "state_lab")}
        if len(both) > 1:
            minority = min(both.values())
            ambiguous.append({"lab": lab, "records": sum(secs.values()),
                              "by_section": dict(secs),
                              "minority_records": minority,
                              "minority_share": pct(minority, sum(both.values()))})
    ambiguous.sort(key=lambda a: -a["records"])
    total = sum(sections.values())
    return {
        "sections": dict(sections),
        "section_shares": {k: pct(v, total) for k, v in sections.items()},
        "distinct_labs": len(by_lab),
        "labs_filed_under_both": len(ambiguous),
        "records_involving_such_a_lab": sum(a["records"] for a in ambiguous),
        "records_involving_such_a_lab_share": pct(
            sum(a["records"] for a in ambiguous), total),
        # The minority-label count is the number of records that must be wrong on
        # one side or the other — a floor on the labelling error, not a guess.
        "minority_labelled_records": sum(a["minority_records"] for a in ambiguous),
        "worst": ambiguous[:8],
        "authoritative": False,
    }


def q5_trend(conn) -> dict:
    """Counts over time. Deliberately NOT a rate — there is no denominator.

    Nothing in CDSCO's published data says how many samples were tested in a given
    month, so a rise here is a rise in *published flags*. It could be more testing,
    more reporting, or more failures, and this data cannot separate them.
    """
    rows = conn.execute(SQL["q5_trend"]).fetchall()
    by_month = {r["alert_month"]: r["n"] for r in rows if r["alert_month"]}
    months = sorted(by_month)
    by_year: Counter = Counter()
    for m in months:
        by_year[m[:4]] += by_month[m]

    def window(end_exclusive: str, k: int = 12) -> list[int]:
        prior = [m for m in months if m < end_exclusive][-k:]
        return [by_month[m] for m in prior]

    before = window(PORTAL_MIGRATION)
    after = [by_month[m] for m in months if m >= PORTAL_MIGRATION][:12]
    complete_years = {y: c for y, c in by_year.items() if y != PARTIAL_YEAR}
    yrs = sorted(complete_years)
    return {
        "by_year": dict(sorted(by_year.items())),
        "complete_years": complete_years,
        "partial_year": PARTIAL_YEAR,
        "partial_year_months": sum(1 for m in months if m.startswith(PARTIAL_YEAR)),
        "first_complete_year": yrs[0], "last_complete_year": yrs[-1],
        "growth_over_complete_years": round(
            complete_years[yrs[-1]] / complete_years[yrs[0]], 2),
        "portal_migration_month": PORTAL_MIGRATION,
        "mean_12m_before_migration": round(sum(before) / len(before), 1),
        "mean_12m_after_migration": round(sum(after) / len(after), 1),
        "migration_month_count": by_month.get(PORTAL_MIGRATION),
        "peak_month": max(by_month, key=lambda m: by_month[m]),
        "peak_month_count": max(by_month.values()),
        "is_a_rate": False,
        "denominator_available": False,
    }


def q6_states(conn) -> dict:
    """Manufacturing state — reported with its coverage, never as if complete."""
    rows = conn.execute(SQL["q6_states"]).fetchall()
    total = sum(r["n"] for r in rows)
    known = [r for r in rows if r["state"]]
    with_state = sum(r["n"] for r in known)
    reasons: Counter = Counter()
    for (raw,) in conn.execute(
            "SELECT parse_flags FROM nsq_records WHERE state IS NULL"):
        for f in json.loads(raw or "[]"):
            if f.startswith("state_"):
                reasons[f.split(":")[0]] += 1
    top = [{"state": r["state"], "records": r["n"],
            "share_of_records_with_a_state": pct(r["n"], with_state)} for r in known]
    return {
        "records": total,
        "records_with_a_state": with_state,
        "coverage": pct(with_state, total),
        "records_without_a_state": total - with_state,
        "why_missing": dict(reasons.most_common()),
        "states": top,
        "top3_share_of_known": pct(sum(r["records"] for r in top[:3]), with_state),
        # The share that matters for honesty: the top state as a fraction of ALL
        # records, not just the ones a state could be read from.
        "top1_share_of_all_records": pct(top[0]["records"], total) if top else 0.0,
        "distinct_states": len(top),
    }


def q7_classes(conn) -> dict:
    """Anti-infectives by WHO INN stem — and what this cannot say.

    The ticket asks about therapeutic categories and antibiotic over-representation.
    The first is answerable in a narrow, citable form; the second is not answerable
    at all with this data, and saying so is the deliverable.
    """
    names = [r[0] for r in conn.execute(SQL["q7_classes"])]
    total = len(names)
    per_class: Counter = Counter()
    matched = 0
    for n in names:
        cls = classify(n)
        if cls:
            matched += 1
            for c in cls:
                per_class[c] += 1
    return {
        "records": total,
        "records_naming_an_anti_infective": matched,
        "share_of_records": pct(matched, total),
        "by_class": [{"class": c, "records": n, "share_of_records": pct(n, total)}
                     for c, n in per_class.most_common()],
        "stem_audit": stem_audit(names),
        "source": WHO_INN_STEM_SOURCE,
        "is_a_therapeutic_classification": False,
        "over_representation_answerable": False,
        "over_representation_blocker": (
            "Over-representation needs a denominator — what share of the medicines "
            "CDSCO tested, or of the medicines on the Indian market, are "
            "anti-infectives. CDSCO publishes neither, and this dataset contains "
            "only the batches that failed. A share of flagged batches is not "
            "evidence that anti-infectives fail more often than anything else."
        ),
    }


QUESTIONS = [q1_volume, q2_categories, q3_manufacturers, q4_labs, q5_trend,
             q6_states, q7_classes]


def run_all(conn) -> dict:
    return {fn.__name__: fn(conn) for fn in QUESTIONS}


# ---------------------------------------------------------------------------
CAVEAT = ("CDSCO does not test at random. Every share below is a share of the "
          "batches the regulator chose to test and published as failing — never a "
          "failure rate for medicines on the market.")


def report(res: dict) -> None:
    def head(t):
        print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")

    print(CAVEAT)

    head("q1 — flagged batches over time")
    v = res["q1_volume"]
    print(f"  {v['total']} batches · {v['month_count']} months · "
          f"{v['first_month']} to {v['last_month']}")
    for y, n in v["by_year"].items():
        note = f"  (partial year — {v['partial_year_months']} months)" if y == v["partial_year"] else ""
        print(f"    {y}  {n:5}{note}")

    head("q2 — failure categories")
    c = res["q2_categories"]
    print(f"  {c['records']} records; {c['multi_category_records']} fail in more than "
          f"one way, so shares sum above 100%")
    for row in c["categories"]:
        print(f"    {row['category']:26} {row['records']:5}  {row['share_of_records']:5.1f}% of records")
    print(f"  potency-related (assay or dissolution): {c['potency_related']['records']} "
          f"({c['potency_related']['share_of_records']}%)")
    print(f"  contamination-related (sterility/microbial/endotoxin/particulate): "
          f"{c['contamination_related']['records']} ({c['contamination_related']['share_of_records']}%)")
    print(f"  'other' (no §3.3 bucket matched): {c['other_records']} ({c['other_share']}%), "
          f"of which {c['other_naming_no_test']} name no test at all and never will be categorised")

    head("q3 — repeat manufacturers")
    m = res["q3_manufacturers"]
    print(f"  {m['manufacturers']} resolved manufacturers hold {m['flags_attributed']} flags")
    print(f"  LOWER BOUND: resolution is partial ({m['review_pairs_pending']} review pairs "
          f"undecided) — finishing it can only concentrate flags further")
    for row in m["concentration"]:
        print(f"    top {row['manufacturers']:4} ({row['share_of_manufacturers']:4.1f}% of companies)"
              f"  ->  {row['flags']:5} flags ({row['share_of_flags']:4.1f}%)")
    print(f"  {m['single_flag_manufacturers']} ({m['single_flag_share']}%) appear exactly once; "
          f"median {m['median_flags']}, max {m['max_flags']}")
    for r in m["top"][:8]:
        print(f"    {r['flags']:4}  {r['name'][:52]:52} {r['spellings']:3} spellings")

    head("q4 — central vs state lab")
    l = res["q4_labs"]
    for k, n in sorted(l["sections"].items(), key=lambda kv: -kv[1]):
        print(f"    {k:14} {n:5}  {l['section_shares'][k]:5.1f}%")
    print(f"\n  alert_section is NOT authoritative:")
    print(f"    {l['labs_filed_under_both']} of {l['distinct_labs']} labs appear under BOTH labels")
    print(f"    {l['records_involving_such_a_lab']} records "
          f"({l['records_involving_such_a_lab_share']}%) involve such a lab")
    print(f"    at least {l['minority_labelled_records']} records are mislabelled on one side")
    for a in l["worst"][:5]:
        print(f"      {a['records']:5}  {a['lab'][:32]:32} {a['by_section']}")

    head("q5 — trend (counts, not rates)")
    t = res["q5_trend"]
    print(f"  NO DENOMINATOR EXISTS — CDSCO publishes no testing volume, so this is a "
          f"trend in published flags, not in drug quality")
    for y, n in t["by_year"].items():
        note = "  (partial)" if y == t["partial_year"] else ""
        print(f"    {y}  {'#' * (n // 25):22} {n:5}{note}")
    print(f"  {t['first_complete_year']} -> {t['last_complete_year']}: "
          f"{t['growth_over_complete_years']}x over complete years")
    print(f"  portal migration {t['portal_migration_month']}: "
          f"{t['mean_12m_before_migration']}/month before -> "
          f"{t['mean_12m_after_migration']}/month after (reporting change, not necessarily quality)")

    head("q6 — manufacturing state")
    s = res["q6_states"]
    print(f"  COVERAGE {s['coverage']}% — {s['records_with_a_state']} of {s['records']} "
          f"records have a state; {s['records_without_a_state']} do not")
    for row in s["states"][:10]:
        print(f"    {row['state']:20} {row['records']:5}  "
              f"{row['share_of_records_with_a_state']:5.1f}% of those with a state")
    print(f"  top 3 = {s['top3_share_of_known']}% of records WITH a state, "
          f"but the top state is only {s['top1_share_of_all_records']}% of all records")

    head("q7 — anti-infectives (WHO INN stems)")
    d = res["q7_classes"]
    print(f"  {d['records_naming_an_anti_infective']} of {d['records']} records "
          f"({d['share_of_records']}%) name an anti-infective by INN stem")
    for row in d["by_class"]:
        print(f"    {row['class']:16} {row['records']:5}  {row['share_of_records']:5.1f}%")
    print(f"\n  NOT ANSWERABLE — over-representation:\n    {d['over_representation_blocker']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help=f"write {RESULTS.name}")
    ap.add_argument("--sql", metavar="Q", help="print the SQL for one question, e.g. q3")
    args = ap.parse_args()

    if args.sql:
        key = next((k for k in SQL if k.startswith(args.sql)), None)
        if not key:
            raise SystemExit(f"no such question: {args.sql}. try: {', '.join(SQL)}")
        print(SQL[key].strip())
        return 0

    conn = connect()
    res = run_all(conn)
    report(res)
    if args.json:
        RESULTS.write_text(json.dumps({"caveat": CAVEAT, **res}, indent=2,
                                      ensure_ascii=False), encoding="utf-8")
        print(f"\nwrote {RESULTS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
