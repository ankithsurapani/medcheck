"""Download CDSCO NSQ / spurious-drug alert PDFs and cache them in data/pdfs/.

CDSCO does not link to alert PDFs directly. The listing page renders a table whose
download column points at an intermediate JSP:

    /opencms/.../download_file_division.jsp?num_id=<base64 of a numeric id>

which returns a small HTML wrapper containing an <iframe> whose src is the real
PDF path. So resolving a download is two requests, not one.

Usage:
    python src/fetch.py --list-only        # show what's discoverable, download nothing
    python src/fetch.py --limit 10         # download the 10 most recent NSQ alerts
    python src/fetch.py --all              # download every NSQ alert found

Re-running is safe: a PDF already present in data/pdfs/ is skipped without a
network request for its content.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, unquote

import requests

BASE = "https://cdsco.gov.in"

# Alert PDFs are listed here. Archive holds older notifications; it uses the same
# table markup, so the same scraper handles both.
LISTING_PAGES = [
    f"{BASE}/opencms/opencms/en/Notifications/Alerts/",
    f"{BASE}/opencms/opencms/en/Notifications/Archive/",
]

# Titles vary a lot across years ("NSQ ALERT FOR THE MONTH OF ...", "List of Drugs,
# Medical Devices, Vaccine and Cosmetics declared as Not of Standard Quality ...",
# "STATE NSQ ALERT ...", "List of spurious Drugs ..."). Match broadly here and let
# the inventory step sort out what each one actually is.
NSQ_TITLE_RE = re.compile(r"\bnsq\b|not\s+of\s+standard|not\s+standard\s+quality|spurious", re.I)

PDF_ROOT = Path(__file__).resolve().parent.parent / "data" / "pdfs"
MANIFEST = PDF_ROOT / "manifest.json"

HEADERS = {
    "User-Agent": "MedCheck/0.1 (public-health data mirror; contact: repo owner)",
}

MONTHS = {m.lower(): i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}


@dataclass
class Alert:
    title: str
    release_date: str          # as printed, e.g. "2025-Jul-18"
    size_label: str            # as printed, e.g. "185 KB"
    jsp_url: str
    listing_page: str

    @property
    def release_iso(self) -> str:
        """'2025-Jul-18' -> '2025-07-18'. Returns '' if the date doesn't parse."""
        try:
            return datetime.strptime(self.release_date, "%Y-%b-%d").strftime("%Y-%m-%d")
        except ValueError:
            return ""

    @property
    def filename(self) -> str:
        # The slug is truncated, so two alerts released the same day whose titles
        # agree on their first 80 characters would collide — and CDSCO does publish
        # near-identical titles on the same day. The num_id fingerprint keeps every
        # source document distinct.
        slug = re.sub(r"[^a-z0-9]+", "-", self.title.lower()).strip("-")[:80]
        fp = hashlib.sha1(self.jsp_url.encode()).hexdigest()[:6]
        return f"{self.release_iso or 'undated'}_{slug}_{fp}.pdf"


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def _get(sess: requests.Session, url: str, *, tries: int = 3, timeout: int = 60) -> requests.Response:
    """cdsco.gov.in is intermittently slow. Retry with a linear backoff."""
    last: Exception | None = None
    for attempt in range(1, tries + 1):
        try:
            r = sess.get(url, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as exc:  # noqa: BLE001 - network flakiness, any failure retries
            last = exc
            if attempt < tries:
                time.sleep(2 * attempt)
    raise RuntimeError(f"GET failed after {tries} tries: {url}") from last


def _strip_tags(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html)).strip()


def discover(sess: requests.Session, pages: list[str] = LISTING_PAGES) -> list[Alert]:
    """Scrape the listing tables and return NSQ-related alerts, newest first."""
    found: dict[str, Alert] = {}   # keyed by jsp_url so the two pages can't duplicate
    for page in pages:
        try:
            html = _get(sess, page).text
        except RuntimeError as exc:
            print(f"  ! skipping {page}: {exc}", file=sys.stderr)
            continue

        # Only the main table body; the sidebar marquee repeats some of these entries.
        body = html[html.find("<tbody>"):] if "<tbody>" in html else html
        rows = re.findall(r"<tr>(.*?)</tr>", body, re.S)
        for row in rows:
            cells = [_strip_tags(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
            link = re.search(r"href=['\"]([^'\"]*download_file_division\.jsp[^'\"]*)['\"]", row)
            if not link or len(cells) < 3:
                continue
            title = cells[1]
            if not NSQ_TITLE_RE.search(title):
                continue
            jsp = urljoin(BASE, link.group(1))
            found.setdefault(jsp, Alert(
                title=title,
                release_date=cells[2],
                size_label=cells[-1],
                jsp_url=jsp,
                listing_page=page,
            ))

    alerts = list(found.values())
    alerts.sort(key=lambda a: a.release_iso, reverse=True)
    return alerts


def resolve_pdf_url(sess: requests.Session, jsp_url: str) -> str | None:
    """Follow the JSP wrapper to the real PDF path."""
    html = _get(sess, jsp_url).text
    m = re.search(r"src=['\"]([^'\"]+\.pdf)['\"]", html, re.I) or \
        re.search(r"<!--\s*(/[^>]+?\.pdf)\s*-->", html, re.I)
    if not m:
        return None
    # Paths contain spaces and non-ASCII (e.g. a curly apostrophe); requests
    # percent-encodes what it must, but existing %XX must not be double-encoded.
    return urljoin(BASE, unquote(m.group(1).strip()))


def _load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {}


def _save_manifest(manifest: dict) -> None:
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


def download(sess: requests.Session, alert: Alert, manifest: dict) -> tuple[str, Path | None]:
    """Download one alert. Returns (status, path) where status is
    'skipped' | 'downloaded' | 'unresolved' | 'not-a-pdf' | 'error'."""
    dest = PDF_ROOT / alert.filename
    if dest.exists() and dest.stat().st_size > 0:
        return "skipped", dest

    try:
        pdf_url = resolve_pdf_url(sess, alert.jsp_url)
    except RuntimeError as exc:
        print(f"  ! {alert.title[:60]}: {exc}", file=sys.stderr)
        return "error", None
    if not pdf_url:
        print(f"  ! no PDF found behind {alert.jsp_url}", file=sys.stderr)
        return "unresolved", None

    try:
        resp = _get(sess, pdf_url, timeout=120)
    except RuntimeError as exc:
        print(f"  ! {alert.title[:60]}: {exc}", file=sys.stderr)
        return "error", None

    body = resp.content
    if not body.startswith(b"%PDF"):
        # CDSCO sometimes serves an HTML error page with a 200 status.
        print(f"  ! not a PDF ({len(body)} bytes): {pdf_url}", file=sys.stderr)
        return "not-a-pdf", None

    dest.write_bytes(body)
    manifest[alert.filename] = {
        **asdict(alert),
        "release_iso": alert.release_iso,
        "pdf_url": pdf_url,
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "downloaded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    return "downloaded", dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=10, help="how many recent alerts to download (default 10)")
    ap.add_argument("--all", action="store_true", help="download every NSQ alert found")
    ap.add_argument("--list-only", action="store_true", help="print what was discovered, download nothing")
    args = ap.parse_args()

    PDF_ROOT.mkdir(parents=True, exist_ok=True)
    sess = _session()

    print("Discovering alerts from CDSCO listing pages...")
    alerts = discover(sess)
    print(f"Found {len(alerts)} NSQ-related alerts "
          f"({alerts[-1].release_date} .. {alerts[0].release_date})" if alerts else "Found none")

    if args.list_only:
        for a in alerts:
            print(f"  {a.release_iso or '??????????'}  {a.size_label:>8}  {a.title[:95]}")
        return 0

    targets = alerts if args.all else alerts[: args.limit]
    manifest = _load_manifest()
    counts: dict[str, int] = {}

    for i, alert in enumerate(targets, start=1):
        status, path = download(sess, alert, manifest)
        counts[status] = counts.get(status, 0) + 1
        mark = {"downloaded": "+", "skipped": "=", }.get(status, "!")
        print(f"  [{i}/{len(targets)}] {mark} {status:<11} {alert.filename}")
        if status == "downloaded":
            time.sleep(1)  # be polite to a government server

    _save_manifest(manifest)
    print("\n" + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())))
    print(f"PDFs in {PDF_ROOT}: {len(list(PDF_ROOT.glob('*.pdf')))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
