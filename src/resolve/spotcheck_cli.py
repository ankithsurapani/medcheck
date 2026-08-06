"""Spot-check the >0.92 auto-merge tier (plan.md §4 Phase 2a).

    python src/resolve/spotcheck_cli.py [--n 40] [--seed 20260806]

plan.md's rule: *"never auto-merge above the review band without spot-checking a
sample."* "Confident" is not the same as "checked", and the auto tier is where the
volume is — 3,229 merges nobody was asked about. This tool asks about a sample.

The sample is deliberately not uniform. Half of it is the **weakest-cohesion**
clusters: union-find is transitive but similarity is not, so A~B and B~C can pull
A together with C even though A and C would never have matched directly. Those
clusters are where a bad merge would actually be, so they are checked first. The
other half is random, to catch anything the cohesion metric doesn't see.

Answers:  y = correctly merged   n = wrongly merged   s = skip   q = save and quit

Every verdict goes to the append-only merge log. A "n" does not un-merge anything
by itself — it is a finding to act on, recorded so the write-up can report the
real error rate rather than an assumed one.
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rapidfuzz import fuzz  # noqa: E402

import db  # noqa: E402
from manufacturers import (  # noqa: E402
    build_clusters, load_entities, log_append, log_read, pair_id,
)
from review_cli import wrap  # noqa: E402

BOLD, DIM, RESET = "\033[1m", "\033[2m", "\033[0m"


def already_checked() -> set[str]:
    return {e["cluster_id"] for e in log_read() if e.get("kind") == "spot_check"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=40, help="sample size (default 40)")
    ap.add_argument("--seed", type=int, default=20260806, help="sampling seed, for reproducibility")
    args = ap.parse_args()

    conn = db.connect()
    entities, _ = load_entities(conn)
    uf, _, _ = build_clusters(entities)

    merged = [sorted(m) for m in uf.clusters().values() if len(m) > 1]
    if not merged:
        print("no multi-member clusters to check — run --build/--apply first")
        return 1

    scored = []
    for members in merged:
        worst = min(fuzz.token_sort_ratio(entities[x]["norm"], entities[y]["norm"]) / 100
                    for x, y in itertools.combinations(members, 2))
        scored.append((worst, members))
    scored.sort(key=lambda t: t[0])

    half = max(1, args.n // 2)
    weakest = scored[:half]
    rest = scored[half:]
    rng = random.Random(args.seed)
    sample = weakest + rng.sample(rest, min(args.n - len(weakest), len(rest)))

    done = already_checked()
    todo = [(w, m) for w, m in sample if pair_id(m[0], m[-1]) not in done]

    print(__doc__.split("Answers:")[0].strip())
    print(f"\n{len(merged)} merged clusters total · sampling {len(sample)} "
          f"({len(weakest)} weakest-cohesion + {len(sample) - len(weakest)} random) · "
          f"{len(sample) - len(todo)} already checked\n")
    print("y = correctly merged   n = wrongly merged   s = skip   q = save and quit")

    if not todo:
        print("\nSample already fully checked.")
        return 0

    verdicts = []
    for i, (worst, members) in enumerate(todo, start=1):
        records = sum(entities[m]["records"] for m in members)
        print("\n" + "=" * 100)
        print(f"{BOLD}[{i}/{len(todo)}]{RESET}  {len(members)} spellings merged into one "
              f"company · {records} flagged batches · weakest internal name match "
              f"{worst:.2f}")
        print("-" * 100)
        for m in members[:10]:
            print(f"    {wrap(m, indent='        ')}")
        if len(members) > 10:
            print(f"    {DIM}... and {len(members) - 10} more{RESET}")
        try:
            ans = input("  all one company? [y/n/s/q] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if ans == "q":
            break
        if ans not in ("y", "n"):
            continue
        note = input("  note (optional): ").strip()
        verdicts.append({
            "kind": "spot_check",
            "cluster_id": pair_id(members[0], members[-1]),
            "verdict": "correct" if ans == "y" else "wrong",
            "reviewer": "human",
            "members": members,
            "size": len(members),
            "records": records,
            "weakest_name_sim": round(worst, 3),
            "note": note or None,
        })
        log_append([verdicts[-1]])

    ok = sum(1 for v in verdicts if v["verdict"] == "correct")
    bad = len(verdicts) - ok
    print(f"\n{len(verdicts)} checked this run — {ok} correct, {bad} wrong.")
    if bad:
        print("Wrong merges are logged. They need a fix before the write-up claims a rate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
