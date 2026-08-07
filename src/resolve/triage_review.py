"""Group the pending manufacturer review-band pairs by judgment-type, so a human
reviewer isn't context-switching between different kinds of question pair to pair
(implementation.md, "Resume the 190 pending manufacturer review-band pairs").

    python src/resolve/triage_review.py

Reads `data/resolve/candidates.json` (write it first with `manufacturers.py
--build` if it's stale) and `data/resolve/manufacturer_merge_log.jsonl`, and
buckets every *undecided* review-band pair into one of three shapes already
identified by hand in `docs/entity_resolution.md` §9:

  multi_plant  same normalized company name, different address, and the scorer
               flagged a `state_differs:` signal — the Unicure Noida/Roorkee
               shape. Usually "yes", but still the reviewer's call.
  near_typo    normalized names within edit distance 2 — the
               `Navkar Lifesciences` / `Navkar Lifescienses` shape. Could be one
               firm mistyped, could be two firms that happen to look alike
               (`Deep Pharma` / `Deepin Pharmaceuticals`, §9's example of a
               near-miss that must NOT merge).
  other        no name-shape shortcut applies — read both clusters in full.

This writes no decisions and touches no merge state. It is a reading order, not
a verdict — `review_cli.py`'s own queue order is what actually runs; use this
output as a guide for the session, not a patch to the tool or the data.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from manufacturers import CANDIDATES, RESOLVE_DIR, norm_name, review_decisions, split_name  # noqa: E402
from rapidfuzz.distance import Levenshtein  # noqa: E402

TRIAGE_OUT = RESOLVE_DIR / "review_triage.json"

BOLD, DIM, RESET = "\033[1m", "\033[2m", "\033[0m"

BUCKET_ORDER = ("multi_plant", "near_typo", "other")
BUCKET_LABEL = {
    "multi_plant": "Same name, state differs — likely one company, two addresses",
    "near_typo": "Names within edit distance 2 — likely a CDSCO re-typing, "
                 "or two genuinely distinct near-spellings",
    "other": "No name-shape shortcut — read both clusters in full",
}


def bucket_of(q: dict) -> str:
    name_a = norm_name(split_name(q["a"])[0])
    name_b = norm_name(split_name(q["b"])[0])
    state_differs = any(s.startswith("state_differs:") for s in q["signals"])

    if name_a == name_b and state_differs:
        return "multi_plant"
    if Levenshtein.distance(name_a, name_b) <= 2:
        return "near_typo"
    return "other"


def main() -> int:
    if not CANDIDATES.exists():
        print("no candidates.json — run: python src/resolve/manufacturers.py --build")
        return 1

    queue = json.loads(CANDIDATES.read_text(encoding="utf-8"))["review_queue"]
    decisions = review_decisions()
    pending = [q for q in queue if q["pair_id"] not in decisions]

    buckets: dict[str, list[dict]] = {b: [] for b in BUCKET_ORDER}
    for q in pending:
        buckets[bucket_of(q)].append(q)

    # Every pending pair lands in exactly one bucket — no pair silently dropped
    # from the reading order, no pair double-counted across buckets.
    assert sum(len(v) for v in buckets.values()) == len(pending)

    print(f"{len(queue)} pairs in the band · {len(decisions)} already decided · "
          f"{len(pending)} to go\n")

    ordered_ids: list[str] = []
    for name in BUCKET_ORDER:
        items = sorted(buckets[name], key=lambda q: -q["score"])
        print(f"{BOLD}{name}{RESET}  ({len(items)})  {DIM}{BUCKET_LABEL[name]}{RESET}")
        for q in items:
            ordered_ids.append(q["pair_id"])
            addr_sim = "n/a" if q["addr_sim"] is None else f"{q['addr_sim']:.2f}"
            print(f"    {q['pair_id']}  score {q['score']:.3f}  "
                  f"name {q['name_sim']:.2f}  addr {addr_sim}  "
                  f"{len(q['cluster_a'])}+{len(q['cluster_b'])} spellings  "
                  f"{DIM}{', '.join(q['signals']) or 'no signals'}{RESET}")
        print()

    TRIAGE_OUT.write_text(json.dumps({
        "generated_from": "data/resolve/candidates.json",
        "pending": len(pending),
        "already_decided": len(decisions),
        "order": ordered_ids,
        "buckets": {b: [q["pair_id"] for q in items] for b, items in buckets.items()},
    }, indent=2), encoding="utf-8")
    print(f"wrote {TRIAGE_OUT} — reading order only, review_cli.py's own "
          f"queue order is what actually runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
