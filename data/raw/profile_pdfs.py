"""THROWAWAY (Phase 0 discovery). Structural profile of every cached PDF —
page count, digital-vs-scanned, table sections, column headers. Feeds
docs/pdf_inventory.md. No parsing/normalization logic; it only measures shape.

    python data/raw/profile_pdfs.py > data/raw/profile.json
"""
import json
import sys
from pathlib import Path

import pdfplumber

PDF_DIR = Path(__file__).resolve().parent.parent / "pdfs"
manifest = json.loads((PDF_DIR / "manifest.json").read_text())

out = []
for p in sorted(PDF_DIR.glob("*.pdf")):
    rec = {"file": p.name, "kb": round(p.stat().st_size / 1024)}
    rec.update({k: manifest.get(p.name, {}).get(k) for k in ("title", "release_iso", "pdf_url")})
    try:
        with pdfplumber.open(p) as pdf:
            rec["pages"] = len(pdf.pages)
            chars = tables = images = 0
            headers = []
            for page in pdf.pages:
                t = page.extract_text() or ""
                chars += len(t)
                images += len(page.images)
                tbls = page.extract_tables()
                tables += len(tbls)
                for tbl in tbls:
                    if tbl and tbl[0]:
                        h = [" ".join((c or "").split()) for c in tbl[0]]
                        if any(h) and h not in headers:
                            headers.append(h)
            rec["chars"] = chars
            rec["chars_per_page"] = round(chars / max(rec["pages"], 1))
            rec["images"] = images
            rec["tables"] = tables
            # A born-digital alert carries hundreds of characters per page. A scan
            # carries almost none (only whatever OCR layer, if any, was embedded).
            rec["kind"] = "digital" if rec["chars_per_page"] > 200 else (
                "scanned" if images else "empty/unknown")
            rec["headers"] = headers[:4]
    except Exception as exc:  # noqa: BLE001
        rec["error"] = f"{type(exc).__name__}: {exc}"
    out.append(rec)
    print(f"{rec['file'][:60]:<62} {rec.get('pages','?'):>3}p "
          f"{rec.get('kind','ERR'):<14} tables={rec.get('tables','?')}", file=sys.stderr)

print(json.dumps(out, indent=2, ensure_ascii=False))
