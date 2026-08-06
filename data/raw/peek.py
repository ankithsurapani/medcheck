"""THROWAWAY. Dump pdfplumber.extract_tables() output for one PDF, just to see
the raw shape of the data before any parser exists.

    python data/raw/peek.py <path-to-pdf> [--pages 1-3] [--out dump.txt]

Not part of the pipeline. Delete once src/parse/ exists.
"""
import sys
from pathlib import Path

import pdfplumber

pdf_path = Path(sys.argv[1])
pages_arg = None
out_path = None
for i, a in enumerate(sys.argv):
    if a == "--pages":
        pages_arg = sys.argv[i + 1]
    if a == "--out":
        out_path = Path(sys.argv[i + 1])

buf = []
def emit(s=""):
    print(s)
    buf.append(str(s))

with pdfplumber.open(pdf_path) as pdf:
    emit(f"FILE: {pdf_path.name}")
    emit(f"PAGES: {len(pdf.pages)}")
    emit(f"METADATA: {pdf.metadata}")
    emit("=" * 100)

    if pages_arg:
        lo, _, hi = pages_arg.partition("-")
        idxs = range(int(lo) - 1, int(hi or lo))
    else:
        idxs = range(len(pdf.pages))

    for pi in idxs:
        if pi >= len(pdf.pages):
            break
        page = pdf.pages[pi]
        text = page.extract_text() or ""
        tables = page.extract_tables()
        emit(f"\n--- PAGE {pi + 1} --- chars={len(text)} words={len(page.extract_words())} "
             f"tables={len(tables)} images={len(page.images)} lines={len(page.lines)} "
             f"rects={len(page.rects)} curves={len(page.curves)}")
        emit(f"TEXT HEAD: {text[:400]!r}")
        for ti, tbl in enumerate(tables):
            emit(f"\n  TABLE {ti}: {len(tbl)} rows x {max((len(r) for r in tbl), default=0)} cols")
            for ri, row in enumerate(tbl[:8]):
                cells = [(c or "").replace("\n", "\\n")[:38] for c in row]
                emit(f"    r{ri}: {cells}")
            if len(tbl) > 8:
                emit(f"    ... {len(tbl) - 8} more rows")

if out_path:
    out_path.write_text("\n".join(buf), encoding="utf-8")
    print(f"\n[written to {out_path}]", file=sys.stderr)
