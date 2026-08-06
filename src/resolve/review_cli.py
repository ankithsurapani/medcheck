"""Human review of the 0.75-0.92 manufacturer match band (plan.md §4 Phase 2a).

    python src/resolve/review_cli.py

plan.md's rule is that nothing in this band gets merged without a person looking
at it, because a wrong merge attributes one company's failures to another. This is
that step. It is a terminal tool, not a web page — Phase 3a is fully static and
there is no backend to host a review UI on.

Each question is **cluster vs cluster**, not string vs string. The >0.92 tier has
already collapsed obvious spellings, so you are asked "are these two companies the
same?" once per company pair rather than once per spelling pair — 205 questions
instead of 2,716. Rubber-stamping is the failure mode this guards against.

Answers:  y = same company   n = different companies   s = skip (stays undecided)
          b = go back one    q = save and quit

Progress is written to the append-only merge log after every answer, so quitting
mid-way loses nothing and re-running resumes where you left off. Changing your
mind later is fine: answer again and the new entry supersedes the old one, with
both preserved on the record.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from manufacturers import CANDIDATES, log_append, review_decisions  # noqa: E402

BOLD, DIM, RESET = "\033[1m", "\033[2m", "\033[0m"


def wrap(s: str, width: int = 96, indent: str = "      ") -> str:
    """Manual wrap — manufacturer_raw runs to 328 characters."""
    out, line = [], ""
    for word in s.split():
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    out.append(line)
    return f"\n{indent}".join(out)


def show(q: dict, i: int, total: int, decided: int) -> None:
    print("\n" + "=" * 100)
    print(f"{BOLD}[{i}/{total}]{RESET}  score {q['score']:.3f}   "
          f"name {q['name_sim']:.2f}   "
          f"address {'n/a' if q['addr_sim'] is None else f'{q_addr(q):.2f}'}   "
          f"{DIM}{decided} decided so far{RESET}")
    if q["signals"]:
        print(f"  {DIM}signals: {', '.join(q['signals'])}{RESET}")
    print("-" * 100)
    for label, key, rkey in (("A", "cluster_a", "records_a"), ("B", "cluster_b", "records_b")):
        members = q[key]
        print(f"  {BOLD}{label}{RESET}  {len(members)} spelling(s), {q[rkey]} flagged batch(es)")
        for m in members[:6]:
            print(f"      {wrap(m)}")
        if len(members) > 6:
            print(f"      {DIM}... and {len(members) - 6} more spelling(s){RESET}")
        if label == "A":
            print()


def q_addr(q: dict) -> float:
    return q["addr_sim"] if q["addr_sim"] is not None else 0.0


def main() -> int:
    if not CANDIDATES.exists():
        print("no candidates.json — run: python src/resolve/manufacturers.py --build")
        return 1
    queue = json.loads(CANDIDATES.read_text(encoding="utf-8"))["review_queue"]
    decisions = review_decisions()

    todo = [q for q in queue if q["pair_id"] not in decisions]
    print(__doc__.split("Answers:")[0].strip())
    print(f"\n{len(queue)} pairs in the band · {len(decisions)} already decided · "
          f"{len(todo)} to go\n")
    print("y = same company   n = different   s = skip   b = back   q = save and quit")

    if not todo:
        print("\nNothing left to review.")
        return 0

    i = 0
    while 0 <= i < len(todo):
        q = todo[i]
        show(q, i + 1, len(todo), len(decisions))
        try:
            ans = input("  same company? [y/n/s/b/q] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nsaved; re-run to continue.")
            return 0

        if ans == "q":
            break
        if ans == "b":
            i = max(0, i - 1)
            continue
        if ans == "s" or ans == "":
            i += 1
            continue
        if ans not in ("y", "n"):
            print("  ?  answer y, n, s, b or q")
            continue

        note = input("  note (optional): ").strip()
        log_append([{
            "kind": "review_decision",
            "pair_id": q["pair_id"],
            "decision": "approve" if ans == "y" else "reject",
            "reviewer": "human",
            "score": q["score"], "name_sim": q["name_sim"], "addr_sim": q["addr_sim"],
            "signals": q["signals"],
            "a": q["a"], "b": q["b"],
            "cluster_a": q["cluster_a"], "cluster_b": q["cluster_b"],
            "note": note or None,
        }])
        decisions[q["pair_id"]] = {"decision": "approve" if ans == "y" else "reject"}
        i += 1

    remaining = len([q for q in queue if q["pair_id"] not in decisions])
    print(f"\n{len(decisions)} decided, {remaining} still undecided.")
    if remaining:
        print("Re-run this tool to finish. Undecided pairs are treated as NOT merged.")
    else:
        print("Band complete. Next: python src/resolve/spotcheck_cli.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
