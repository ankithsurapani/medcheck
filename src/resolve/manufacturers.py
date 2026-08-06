"""Manufacturer entity resolution (plan.md §4 Phase 2a).

`manufacturer_raw` is a company name *and* a full postal address in one cell, and
CDSCO re-types it from scratch every month. 6,155 records carry 5,107 distinct
spellings; Zee Laboratories alone appears 49 different ways. This module collapses
those spellings onto company entities and backfills `nsq_records.manufacturer_id`.

Principles this module is bound by:
  §1.1  Mirror, not accuser — every raw spelling survives in `known_aliases`, and
        the placeholder strings CDSCO prints when the real maker is unknown are
        never resolved into a company.
  §1.4  Uncertainty is displayed, not hidden — a pair that isn't obviously the
        same company goes to a human, not to a guess.
  §4 Phase 2 rule: **never auto-merge above the review band without spot-checking
        a sample.** A wrongly-merged manufacturer attributes another company's
        failures to a real firm. That is reputational harm, not a data defect.

Pipeline:

    python src/resolve/manufacturers.py --build    # score pairs, write the queues
    python src/resolve/review_cli.py               # human decides the 0.75-0.92 band
    python src/resolve/spotcheck_cli.py            # human samples the >0.92 tier
    python src/resolve/manufacturers.py --apply    # write manufacturers + backfill

`--apply` is conservative by construction: a review-band pair with no recorded
human decision is treated as *rejected*, so running the pipeline early can only
under-merge, never over-merge.
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rapidfuzz import fuzz

import db
from normalize import clean_text, derive_state

RESOLVE_DIR = Path(__file__).resolve().parents[2] / "data" / "resolve"
MERGE_LOG = RESOLVE_DIR / "manufacturer_merge_log.jsonl"
CANDIDATES = RESOLVE_DIR / "candidates.json"

# Tier boundaries are plan.md §4 Phase 2a's, not tuned to make the queue smaller.
REVIEW_LOW = 0.75
REVIEW_HIGH = 0.92
FLOOR = 0.70          # below this a pair is not even written out

# ---------------------------------------------------------------------------
# Placeholders — strings that are not a company at all
# ---------------------------------------------------------------------------
# Phase 1a flags `manufacturer_unknown_placeholder` on 51 spurious records whose
# maker CDSCO records as "Under Investigation". Resolution has to recognise more
# than that: "Not Mentioned", "Not applicable", "Spurious", "NIL,NIL NIL" and "NM"
# are all non-company placeholders too, and none of them carry the Phase 1a flag.
# They are excluded from clustering entirely and keep manufacturer_id NULL —
# giving a counterfeit's unknown maker a company page would be a §1.1 violation.
PLACEHOLDER_RE = re.compile(
    r"^\s*(?:under\s+investigation|not\s+known|unknown|n\.?\s*a\.?|n\.?\s*m\.?"
    r"|not\s+mentioned|not\s+applicable|not\s+available|spurious|nil[\s,.]*(?:nil[\s,.]*)*"
    r"|-+|\.+)\s*$",
    re.I,
)

# ---------------------------------------------------------------------------
# Splitting the name off the address
# ---------------------------------------------------------------------------
# Certification boilerplate is not part of a company's name. CDSCO includes it
# inconsistently — "Pharma Impex Laboratories Pvt. Ltd. (ISO 9001 : 2015 & WHO GMP
# Certified)" one month, plain the next — so leaving it in splits one company into
# two entities. The raw string keeps it; only the matching key drops it.
BLURB_RE = re.compile(
    r"\((?:[^()]*?(?:gmp|iso|who|certif|unit\s+of|approved|accredit)[^()]*?)\)"
    r"|\b(?:an?\s+)?(?:who[\s-]*)?gmp\s+certified\s+(?:company|unit|firm)\b"
    r"|\bwho[\s-]*gmp\s+certified\b",
    re.I,
)

MS_PREFIX_RE = re.compile(r"^\s*(?:m\s*/\s*s\.?|m/s|ms\.)\s*[.,]?\s*", re.I)

# The first address token ends the name. This list is deliberately long: the cost
# of cutting one token early is a slightly shorter name key (harmless, both sides
# get cut the same way), while the cost of cutting late is address text leaking
# into the name and splitting one company across several entities.
ADDR_KEYWORDS = (
    r"plot|survey|khasra|khewat|khata|mouza|village|vill|gat|gut|shed|sector|phase|street"
    r"|road|marg|lane|nagar|industrial|industial|indl|estate|gidc|midc|sidcul|siidcul|epip"
    r"|iie|near|opp|opposite|behind|post|dist|distt|district|taluka|tal|teh|tehsil|via|nh"
    r"|km|floor|building|bldg|complex|premises|door|no|s\.?no|h\.?no|sy\.?no|at|unit|area|block"
)
ADDR_RE = re.compile(r"[\s,.]\(?(?:" + ADDR_KEYWORDS + r")\b", re.I)
NUMBER_RE = re.compile(r"[\s,](?=\(?\d)")
PIN_RE = re.compile(r"\b(\d{6})\b")


def split_name(raw: str | None) -> tuple[str, str]:
    """Split `manufacturer_raw` into (name, address).

    Cuts at whichever comes first: the first comma, the first address keyword, or
    the first numeric token. Everything before the cut is the company name.
    """
    s = clean_text(raw) or ""
    s = MS_PREFIX_RE.sub("", s)
    s = re.sub(r"\s+", " ", BLURB_RE.sub(" ", s)).strip()
    if not s:
        return "", ""

    cuts = [len(s)]
    if (i := s.find(",")) > 0:
        cuts.append(i)
    if (m := ADDR_RE.search(s, 1)):
        cuts.append(m.start())
    if (m := NUMBER_RE.search(s, 1)):
        cuts.append(m.start())
    cut = min(cuts)
    name = s[:cut].strip(" ,.-")
    # A string that is *only* address (no leading name) keeps the whole thing as
    # the name rather than becoming empty and matching every other empty name.
    return (name or s.strip(" ,.-")), s[cut:].strip(" ,.-")


# ---------------------------------------------------------------------------
# Normalizing the name
# ---------------------------------------------------------------------------
# Industry words are spelled several ways for the same company across months
# ("Laboratories" / "Labs" / "Lab", "Pharmaceuticals" / "Pharma"). They are folded
# onto one token rather than deleted: deleting them would reduce "Zee Laboratories"
# to "zee", which is short enough to collide with unrelated firms.
SYNONYMS: list[tuple[str, str]] = [
    (r"\blife\s*sciences?\b|\blifesciences?\b", "lifescience"),
    (r"\bpharmaceutical(?:s|es)?\b|\bpharmaceutics\b|\bpharmacia\b|\bpharmacy\b|\bpharma\b", "pharma"),
    (r"\blaborator(?:ies|y)\b|\blabs?\b", "lab"),
    (r"\bindustr(?:ies|y|ial)\b|\binds\b", "industries"),
    (r"\bhealth\s*care\b|\bhealthcare\b", "healthcare"),
    (r"\bbio\s*tech(?:nolog(?:y|ies))?\b|\bbiotech\b", "biotech"),
    (r"\bformulations?\b", "formulation"),
    (r"\bremed(?:ies|y)\b", "remedies"),
    (r"\bdrugs?\b", "drugs"),
    (r"\bproducts?\b", "products"),
    (r"\bchemicals?\b", "chemicals"),
    (r"\bsciences?\b", "science"),
]

LEGAL_TOKENS = {
    "pvt", "private", "ltd", "limited", "llp", "inc", "corp", "corporation",
    "co", "company", "plc", "gmbh", "the", "and", "p",
}

# Dropped only to build the *blocking* key, never from the similarity key —
# blocking on "pharma" would put a third of the corpus in one block.
GENERIC_TOKENS = {
    "pharma", "lab", "industries", "healthcare", "biotech", "formulation",
    "remedies", "drugs", "products", "chemicals", "science", "lifescience",
}

TRAILING_NOISE = {"india", "indian"}


def norm_name(name: str) -> str:
    """Lowercase, de-punctuate, fold industry synonyms, drop legal suffixes.

    Trailing single characters are dropped because the splitter leaves them behind
    on addresses like "Bajaj Healthcare Ltd. R.S. No. 1818" — cut at "No", the
    name keeps a stray "R.S.". No Indian pharma name in the corpus ends in a bare
    letter, so this costs nothing and stops one company splitting in two.
    """
    s = name.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    for pattern, replacement in SYNONYMS:
        s = re.sub(pattern, replacement, s)
    toks = [t for t in s.split() if t not in LEGAL_TOKENS]
    while toks and (len(toks[-1]) == 1 or toks[-1] in TRAILING_NOISE):
        toks.pop()
    return " ".join(toks)


def core_name(normalized: str) -> str:
    """Normalized name minus generic industry tokens — the blocking key's basis."""
    return " ".join(t for t in normalized.split() if t not in GENERIC_TOKENS) or normalized


def norm_address(address: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", address.lower()).split())


def is_placeholder(raw: str | None) -> bool:
    s = clean_text(raw)
    return bool(s) and bool(PLACEHOLDER_RE.match(s))


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------
def load_entities(conn) -> tuple[dict[str, dict], list[str]]:
    """One entity per distinct `manufacturer_raw`. Returns (entities, placeholders)."""
    rows = conn.execute(
        "SELECT manufacturer_raw AS raw, COUNT(*) AS n, MIN(alert_month) AS first_month "
        "FROM nsq_records WHERE manufacturer_raw IS NOT NULL GROUP BY manufacturer_raw"
    ).fetchall()

    entities: dict[str, dict] = {}
    placeholders: list[str] = []
    for r in rows:
        raw = r["raw"]
        if is_placeholder(raw):
            placeholders.append(raw)
            continue
        name, address = split_name(raw)
        normalized = norm_name(name)
        state, _ = derive_state(raw)
        entities[raw] = {
            "raw": raw,
            "name": name,
            "norm": normalized,
            "core": core_name(normalized),
            "address": norm_address(address),
            "pins": set(PIN_RE.findall(raw)),
            "state": state,
            "records": r["n"],
            "first_month": r["first_month"],
        }
    return entities, placeholders


# ---------------------------------------------------------------------------
# Blocking
# ---------------------------------------------------------------------------
# Three keys per entity rather than one. plan.md asks for "first token + state",
# but state is only derivable for 58% of records and CDSCO gets it wrong outright
# on at least one record (a Paonta Sahib, H.P. address labelled Punjab), so using
# state as a hard block would refuse to consider real merges. It is used as a
# scoring signal instead. The prefix key catches typos in the first token
# ("Navkar" / "Navkar"), the sorted-token key catches reordered names.
MAX_BLOCK = 400


def block_keys(entity: dict) -> list[tuple[str, str]]:
    first = (entity["core"].split() or ["?"])[0]
    return [
        ("token", first),
        ("prefix", first[:4]),
        ("sorted", " ".join(sorted(entity["norm"].split()))),
    ]


def candidate_pairs(entities: dict[str, dict]) -> set[tuple[str, str]]:
    blocks: dict[tuple[str, str], set[str]] = defaultdict(set)
    for raw, e in entities.items():
        for key in block_keys(e):
            blocks[key].add(raw)

    pairs: set[tuple[str, str]] = set()
    for key, members in blocks.items():
        if len(members) > MAX_BLOCK:
            # A block this size is a degenerate key (e.g. a 4-char prefix shared by
            # unrelated firms), not a company. Skipping it costs nothing the other
            # two keys don't already cover.
            continue
        for a, b in itertools.combinations(sorted(members), 2):
            pairs.add((a, b))
    return pairs


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
# The name carries the score; the address only adjusts it, and only downward
# enough to move a pair into review. That ordering is deliberate. A company with
# two plants writes the same name against two addresses, and weighting the address
# heavily would refuse to merge it. A different company with a similar name is
# caught by the name comparison, which is where the real risk lives.
PENALTY_STATE_DIFFERS = 0.09
PENALTY_PIN_DIFFERS = 0.05
PENALTY_ADDRESS_UNLIKE = 0.04
BONUS_PIN_SHARED = 0.03
ADDRESS_UNLIKE_BELOW = 0.40


def score_pair(a: dict, b: dict) -> dict:
    """Similarity in [0,1] plus the signals behind it, for the reviewer to read."""
    if not a["norm"] or not b["norm"]:
        return {"score": 0.0, "name_sim": 0.0, "addr_sim": None, "signals": ["empty_name"]}

    name_sim = fuzz.token_sort_ratio(a["norm"], b["norm"]) / 100
    addr_sim = (fuzz.token_set_ratio(a["address"], b["address"]) / 100
                if (a["address"] and b["address"]) else None)

    score = name_sim
    signals: list[str] = []

    if a["state"] and b["state"] and a["state"] != b["state"]:
        score -= PENALTY_STATE_DIFFERS
        signals.append(f"state_differs:{a['state']}|{b['state']}")
    if a["pins"] and b["pins"]:
        if a["pins"] & b["pins"]:
            score += BONUS_PIN_SHARED
            signals.append("pin_shared:" + ",".join(sorted(a["pins"] & b["pins"])))
        else:
            score -= PENALTY_PIN_DIFFERS
            signals.append(f"pin_differs:{','.join(sorted(a['pins']))}|{','.join(sorted(b['pins']))}")
    if addr_sim is not None and addr_sim < ADDRESS_UNLIKE_BELOW:
        score -= PENALTY_ADDRESS_UNLIKE
        signals.append(f"address_unlike:{addr_sim:.2f}")

    return {
        "score": round(max(0.0, min(1.0, score)), 4),
        "name_sim": round(name_sim, 4),
        "addr_sim": None if addr_sim is None else round(addr_sim, 4),
        "signals": signals,
    }


def tier_of(score: float) -> str:
    if score > REVIEW_HIGH:
        return "auto"
    if score >= REVIEW_LOW:
        return "review"
    return "no_match"


# ---------------------------------------------------------------------------
# Union-find
# ---------------------------------------------------------------------------
class Union:
    def __init__(self, items):
        self.parent = {i: i for i in items}

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        self.parent[ra] = rb
        return True

    def clusters(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = defaultdict(list)
        for x in self.parent:
            out[self.find(x)].append(x)
        return out


# ---------------------------------------------------------------------------
# Merge log — append-only
# ---------------------------------------------------------------------------
def log_append(entries: list[dict]) -> None:
    """Append to the merge log. Never truncates: a bad merge has to stay traceable."""
    if not entries:
        return
    RESOLVE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().astimezone().isoformat(timespec="seconds")
    with MERGE_LOG.open("a", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps({"ts": ts, **e}, ensure_ascii=False) + "\n")


def log_read() -> list[dict]:
    if not MERGE_LOG.exists():
        return []
    with MERGE_LOG.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def review_decisions() -> dict[str, dict]:
    """Latest human decision per review-band pair, keyed by pair_id.

    The log is append-only, so a reviewer who changes their mind appends a second
    entry. Last write wins; both remain on the record.
    """
    out: dict[str, dict] = {}
    for entry in log_read():
        if entry.get("kind") == "review_decision":
            out[entry["pair_id"]] = entry
    return out


def pair_id(a: str, b: str) -> str:
    """Stable id for a raw-string pair, independent of the run that produced it."""
    import hashlib
    basis = "\x00".join(sorted([a, b]))
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Build — score everything and write the queues
# ---------------------------------------------------------------------------
def build(conn) -> dict:
    entities, placeholders = load_entities(conn)
    pairs = candidate_pairs(entities)

    scored: list[dict] = []
    for a, b in pairs:
        s = score_pair(entities[a], entities[b])
        if s["score"] >= FLOOR:
            scored.append({"a": a, "b": b, "pair_id": pair_id(a, b), **s,
                           "tier": tier_of(s["score"])})
    # Sorted by score, then by the strings themselves. The tie-break is not
    # cosmetic: `pairs` is a set, and without it the spanning forest below differs
    # between runs on the same data — same clusters, different edges — which would
    # make the merge log grow by thousands of lines every rebuild and stop it
    # showing what actually changed.
    scored.sort(key=lambda p: (-p["score"], p["a"], p["b"]))

    auto = [p for p in scored if p["tier"] == "auto"]
    review = [p for p in scored if p["tier"] == "review"]

    # Auto merges first, so the review queue can be expressed as cluster-vs-cluster
    # rather than string-vs-string. A reviewer asked "is this company the same as
    # that company?" once beats being asked the same thing forty times for forty
    # spellings, and a tired reviewer is how a bad merge gets waved through.
    uf = Union(entities)
    spanning: list[dict] = []
    for p in auto:
        if uf.union(p["a"], p["b"]):
            spanning.append(p)

    clusters = uf.clusters()
    review_groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    implied = 0
    for p in review:
        ra, rb = uf.find(p["a"]), uf.find(p["b"])
        if ra == rb:
            implied += 1     # already merged by a stronger path; nothing to decide
            continue
        review_groups[tuple(sorted((ra, rb)))].append(p)

    queue = []
    for (ra, rb), members in review_groups.items():
        best = max(members, key=lambda p: p["score"])
        queue.append({
            "pair_id": best["pair_id"],
            "score": best["score"],
            "name_sim": best["name_sim"],
            "addr_sim": best["addr_sim"],
            "signals": best["signals"],
            "a": best["a"], "b": best["b"],
            "cluster_a": sorted(clusters[ra]),
            "cluster_b": sorted(clusters[rb]),
            "records_a": sum(entities[x]["records"] for x in clusters[ra]),
            "records_b": sum(entities[x]["records"] for x in clusters[rb]),
            "supporting_pairs": len(members),
        })
    queue.sort(key=lambda q: -q["score"])

    RESOLVE_DIR.mkdir(parents=True, exist_ok=True)
    CANDIDATES.write_text(json.dumps({
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "thresholds": {"floor": FLOOR, "review_low": REVIEW_LOW, "review_high": REVIEW_HIGH},
        "counts": {
            "distinct_raw": len(entities) + len(placeholders),
            "entities": len(entities),
            "placeholders": len(placeholders),
            "candidate_pairs": len(pairs),
            "scored_pairs": len(scored),
            "auto_pairs": len(auto),
            "auto_merging_pairs": len(spanning),
            "review_pairs": len(review),
            "review_pairs_implied_by_auto": implied,
            "review_queue": len(queue),
            "clusters_after_auto": len(clusters),
        },
        "auto_pairs": [{k: p[k] for k in ("pair_id", "score", "name_sim", "addr_sim",
                                          "signals", "a", "b")} for p in auto],
        "review_queue": queue,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    # Every auto merge that actually joined two entities is logged. Redundant edges
    # inside an already-joined cluster are counted, not written: they change no
    # outcome, and the spanning set alone is enough to reconstruct or undo the
    # clustering. The full scored list lives in candidates.json alongside.
    #
    # An edge already on the record at the same score is not written twice. The log
    # is append-only, not append-blindly — re-running --build after a data refresh
    # should show what changed, and 3,229 identical lines a second time would bury
    # it. A *changed* score does get a new line.
    logged = {(e["pair_id"], e["score"]) for e in log_read() if e.get("kind") == "auto_merge"}
    log_append(
        [{"kind": "auto_merge", "pair_id": p["pair_id"], "score": p["score"],
          "name_sim": p["name_sim"], "addr_sim": p["addr_sim"], "signals": p["signals"],
          "a": p["a"], "b": p["b"], "reviewer": "automatic"}
         for p in spanning if (p["pair_id"], p["score"]) not in logged]
        + [{"kind": "build_summary", "reviewer": "automatic",
            "auto_pairs": len(auto), "auto_merging_pairs": len(spanning),
            "auto_redundant_pairs": len(auto) - len(spanning),
            "review_pairs": len(review), "review_queue": len(queue),
            "review_pairs_implied_by_auto": implied,
            "entities": len(entities), "placeholders": len(placeholders),
            "clusters_after_auto": len(clusters)}]
    )

    return json.loads(CANDIDATES.read_text(encoding="utf-8"))["counts"]


# ---------------------------------------------------------------------------
# Apply — build clusters from auto merges + recorded human decisions
# ---------------------------------------------------------------------------
def build_clusters(entities: dict[str, dict]) -> tuple[Union, dict, list[dict]]:
    """Re-derive clusters from the merge log alone. Returns (uf, stats, pending)."""
    if not CANDIDATES.exists():
        raise SystemExit("no candidates.json — run --build first")
    cand = json.loads(CANDIDATES.read_text(encoding="utf-8"))

    uf = Union(entities)
    applied_auto = 0
    for p in cand["auto_pairs"]:
        if p["a"] in entities and p["b"] in entities and uf.union(p["a"], p["b"]):
            applied_auto += 1

    decisions = review_decisions()
    approved = rejected = 0
    pending: list[dict] = []
    for q in cand["review_queue"]:
        d = decisions.get(q["pair_id"])
        if d is None:
            pending.append(q)
            continue
        if d["decision"] == "approve":
            uf.union(q["a"], q["b"])
            approved += 1
        else:
            rejected += 1

    return uf, {"auto_edges_applied": applied_auto, "review_approved": approved,
                "review_rejected": rejected, "review_pending": len(pending)}, pending


def pick_canonical(members: list[str], entities: dict[str, dict]) -> str:
    """Canonical display name for a cluster.

    Most-recorded spelling wins. Ties break toward mixed case over SHOUTING and
    then toward the longer string, because CDSCO's all-caps months carry no more
    information and the longer variant usually keeps the legal suffix.
    """
    by_name: Counter = Counter()
    for raw in members:
        e = entities[raw]
        if e["name"]:
            by_name[e["name"]] += e["records"]
    if not by_name:
        return entities[members[0]]["raw"][:120]
    top = max(by_name.values())
    finalists = [n for n, c in by_name.items() if c == top]
    return sorted(finalists, key=lambda n: (n.isupper(), -len(n), n))[0]


def apply(conn, allow_pending: bool = False) -> dict:
    entities, placeholders = load_entities(conn)
    uf, stats, pending = build_clusters(entities)

    if pending and not allow_pending:
        raise SystemExit(
            f"{len(pending)} review-band pairs have no recorded human decision.\n"
            f"Run:  python src/resolve/review_cli.py\n"
            f"Or pass --allow-pending to apply now, treating every undecided pair as\n"
            f"NOT merged (conservative — it can only under-merge)."
        )

    clusters = uf.clusters()
    rows = []
    for root, members in clusters.items():
        members = sorted(members)
        records = sum(entities[m]["records"] for m in members)
        states = Counter(entities[m]["state"] for m in members if entities[m]["state"])
        # The fullest raw string of the most-recorded spelling stands in as the
        # address. Every other spelling is preserved in known_aliases, so nothing
        # a merge touched is lost.
        primary = max(members, key=lambda m: (entities[m]["records"], len(m)))
        months = [entities[m]["first_month"] for m in members if entities[m]["first_month"]]
        rows.append({
            "canonical_name": pick_canonical(members, entities),
            "known_aliases": json.dumps(members, ensure_ascii=False),
            "address_raw": entities[primary]["raw"],
            "state": states.most_common(1)[0][0] if states else None,
            "first_seen_month": min(months) if months else None,
            "total_flags": records,
            "_members": members,
        })
    # Sorted so ids are stable across reruns rather than dependent on dict order.
    rows.sort(key=lambda r: (r["canonical_name"].lower(), r["address_raw"]))

    cur = conn.cursor()
    cur.execute("UPDATE nsq_records SET manufacturer_id = NULL")
    cur.execute("DELETE FROM manufacturers")
    for i, r in enumerate(rows, start=1):
        r["id"] = i
        cur.execute(
            "INSERT INTO manufacturers (id, canonical_name, known_aliases, address_raw, "
            "state, first_seen_month, total_flags) VALUES (?,?,?,?,?,?,?)",
            (i, r["canonical_name"], r["known_aliases"], r["address_raw"],
             r["state"], r["first_seen_month"], r["total_flags"]))
    cur.executemany(
        "UPDATE nsq_records SET manufacturer_id = ? WHERE manufacturer_raw = ?",
        [(r["id"], m) for r in rows for m in r["_members"]])
    conn.commit()

    linked = conn.execute("SELECT COUNT(*) FROM nsq_records WHERE manufacturer_id IS NOT NULL").fetchone()[0]
    unlinked = conn.execute("SELECT COUNT(*) FROM nsq_records WHERE manufacturer_id IS NULL").fetchone()[0]
    placeholder_rows = conn.execute(
        "SELECT COUNT(*) FROM nsq_records WHERE manufacturer_raw IN "
        f"({','.join('?' * len(placeholders))})", placeholders).fetchone()[0] if placeholders else 0

    stats.update({
        "distinct_raw": len(entities) + len(placeholders),
        "placeholder_strings": len(placeholders),
        "placeholder_records": placeholder_rows,
        "manufacturers": len(rows),
        "records_linked": linked,
        "records_unlinked": unlinked,
        "collapse_ratio": round(len(entities) / len(rows), 2) if rows else 0,
    })

    log_append([{"kind": "apply", "reviewer": "automatic", **stats}])
    return stats


# ---------------------------------------------------------------------------
def cohesion_report(conn, limit: int = 15) -> list[tuple[float, int, list[str]]]:
    """Weakest link inside each cluster — where transitive merging is riskiest.

    Union-find is transitive but similarity is not: A~B and B~C can merge A with C
    even when A and C would never have matched directly. This surfaces the clusters
    where that happened so the spot-check can start with them rather than with a
    random sample that is mostly obvious.
    """
    entities, _ = load_entities(conn)
    uf, _, _ = build_clusters(entities)
    out = []
    for members in uf.clusters().values():
        if len(members) < 2:
            continue
        worst = min(fuzz.token_sort_ratio(entities[x]["norm"], entities[y]["norm"]) / 100
                    for x, y in itertools.combinations(members, 2))
        out.append((round(worst, 3), len(members), sorted(members)))
    out.sort(key=lambda t: t[0])
    return out[:limit]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--build", action="store_true", help="score pairs, write review queues")
    g.add_argument("--apply", action="store_true", help="write manufacturers + backfill ids")
    g.add_argument("--cohesion", action="store_true", help="weakest-link report per cluster")
    ap.add_argument("--allow-pending", action="store_true",
                    help="with --apply: treat undecided review pairs as rejected")
    args = ap.parse_args()

    conn = db.connect()
    db.init(conn)

    if args.build:
        counts = build(conn)
        print("built candidate queues")
        for k, v in counts.items():
            print(f"  {k}: {v}")
        print(f"\nwrote {CANDIDATES}")
        print(f"next: python src/resolve/review_cli.py   ({counts['review_queue']} decisions)")
    elif args.apply:
        stats = apply(conn, allow_pending=args.allow_pending)
        print("applied")
        for k, v in stats.items():
            print(f"  {k}: {v}")
    else:
        for worst, size, members in cohesion_report(conn):
            print(f"min_name_sim={worst:.2f} size={size}")
            for m in members[:4]:
                print(f"    {m[:100]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
