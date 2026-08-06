"""Fetch CDSCO's public NSQ / spurious JSON portal and cache every raw response.

The portal at https://cdscoonline.gov.in/CDSCO/viewPublicNSQDrug is a DataTables
front-end over undocumented JSON endpoints. plan.md §5.8: it has no spec and could
change shape or disappear, so every response is written to disk verbatim before
anything normalizes it. Normalization reads the cache, never the network.

Cache layout:
    data/raw/portal/nsq/<Mon-YYYY>.json
    data/raw/portal/spurious/<Mon-YYYY>.json
    data/raw/portal/spurious/_current.json     (viewPublicSpuriousDrugData)

Each cached file is an envelope, not the bare payload:
    {"url": ..., "tab": ..., "month": ..., "fetched_at": ..., "payload": {...}}

The url is kept because it becomes `source_url` on every derived record — a
reader must be able to re-run the exact query that produced a row.

Usage:
    python src/ingest/cdsco_json.py --list        # show months, fetch nothing
    python src/ingest/cdsco_json.py               # fetch everything not cached
    python src/ingest/cdsco_json.py --refresh     # re-fetch even if cached
    python src/ingest/cdsco_json.py --tab nsq     # one tab only
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

BASE = "https://cdscoonline.gov.in"

ENDPOINTS = {
    "nsq": "/CDSCO/filteredNsqDrugTable",
    "spurious": "/CDSCO/filteredSpuriousDrugTable",
}
YEARS_EP = "/CDSCO/reportingYears"
MONTHS_EP = "/CDSCO/publicReportingMonths"
SPURIOUS_CURRENT_EP = "/CDSCO/viewPublicSpuriousDrugData"

CACHE_ROOT = Path(__file__).resolve().parents[2] / "data" / "raw" / "portal"

HEADERS = {
    "User-Agent": "MedCheck/0.1 (public-health data mirror; contact: repo owner)",
    "X-Requested-With": "XMLHttpRequest",
}


def _get_json(sess: requests.Session, url: str, params: dict | None = None,
              *, tries: int = 3, timeout: int = 60):
    """GET and decode. The portal sometimes returns a JSON *string* containing
    JSON (the front-end calls JSON.parse on the response), so unwrap one level."""
    last: Exception | None = None
    for attempt in range(1, tries + 1):
        try:
            r = sess.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, str):
                data = json.loads(data)
            return data, r.url
        except Exception as exc:  # noqa: BLE001 - network/decode flakiness both retry
            last = exc
            if attempt < tries:
                time.sleep(2 * attempt)
    raise RuntimeError(f"GET failed after {tries} tries: {url} {params or ''}") from last


def discover_months(sess: requests.Session, tab: str) -> list[str]:
    """Return ['Jan-2019', ...] for a tab, oldest first."""
    years, _ = _get_json(sess, BASE + YEARS_EP, {"tab": tab})
    months: list[str] = []
    for year in years:
        ms, _ = _get_json(sess, BASE + MONTHS_EP, {"year": year, "tab": tab})
        months.extend(f"{m}-{year}" for m in ms)
    return months


def fetch_month(sess: requests.Session, tab: str, month: str, *, refresh: bool = False):
    """Fetch one month into the cache. Returns (status, n_records)."""
    dest = CACHE_ROOT / tab / f"{month}.json"
    if dest.exists() and not refresh:
        payload = json.loads(dest.read_text())["payload"]
        return "cached", payload.get("iTotalRecords", 0)

    data, effective_url = _get_json(
        sess, BASE + ENDPOINTS[tab], {"month": month, "source": "All", "tab": tab})

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({
        "url": effective_url,
        "tab": tab,
        "month": month,
        "fetched_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "payload": data,
    }, indent=1, ensure_ascii=False) + "\n")
    return "fetched", data.get("iTotalRecords", 0)


def fetch_spurious_current(sess: requests.Session, *, refresh: bool = False):
    dest = CACHE_ROOT / "spurious" / "_current.json"
    if dest.exists() and not refresh:
        return "cached", json.loads(dest.read_text())["payload"].get("iTotalRecords", 0)
    data, effective_url = _get_json(sess, BASE + SPURIOUS_CURRENT_EP)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({
        "url": effective_url,
        "tab": "spurious",
        "month": None,
        "fetched_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "payload": data,
    }, indent=1, ensure_ascii=False) + "\n")
    return "fetched", data.get("iTotalRecords", 0)


def load_cached(tab: str) -> list[dict]:
    """Every cached envelope for a tab, oldest month first. Used by normalize.py."""
    d = CACHE_ROOT / tab
    if not d.exists():
        return []
    out = [json.loads(p.read_text()) for p in sorted(d.glob("*.json"))]
    out.sort(key=lambda e: _month_sort_key(e.get("month")))
    return out


_MONTH_NUM = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


def _month_sort_key(month: str | None) -> tuple[int, int]:
    if not month:
        return (0, 0)   # _current.json sorts first
    mon, _, year = month.partition("-")
    return (int(year), _MONTH_NUM.get(mon.lower()[:3], 0))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tab", choices=["nsq", "spurious"], help="only this tab")
    ap.add_argument("--refresh", action="store_true", help="re-fetch even if cached")
    ap.add_argument("--list", action="store_true", dest="list_only",
                    help="list discoverable months, fetch nothing")
    args = ap.parse_args()

    sess = requests.Session()
    sess.headers.update(HEADERS)
    tabs = [args.tab] if args.tab else ["nsq", "spurious"]
    grand = 0

    for tab in tabs:
        print(f"\n== {tab} ==")
        try:
            months = discover_months(sess, tab)
        except RuntimeError as exc:
            print(f"  ! could not enumerate months: {exc}", file=sys.stderr)
            continue
        print(f"  {len(months)} months discoverable: {months[0]} .. {months[-1]}"
              if months else "  no months")

        if args.list_only:
            print("  " + ", ".join(months))
            continue

        counts = {"fetched": 0, "cached": 0, "error": 0}
        total = 0
        for month in months:
            try:
                status, n = fetch_month(sess, tab, month, refresh=args.refresh)
            except RuntimeError as exc:
                print(f"  ! {month}: {exc}", file=sys.stderr)
                counts["error"] += 1
                continue
            counts[status] += 1
            total += n
            if status == "fetched":
                time.sleep(0.5)   # be polite to a government server
        print(f"  {counts['fetched']} fetched, {counts['cached']} cached, "
              f"{counts['error']} errors — {total} records")
        grand += total

        if tab == "spurious":
            status, n = fetch_spurious_current(sess, refresh=args.refresh)
            print(f"  current-month endpoint: {status}, {n} records")

    if not args.list_only:
        print(f"\ntotal records across cached months: {grand}")
        print(f"cache: {CACHE_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
