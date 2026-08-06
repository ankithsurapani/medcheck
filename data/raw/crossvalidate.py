"""THROWAWAY (Phase 1a). Cross-validate JSON-derived records against the Phase 0
source PDFs for one month that exists in both sources.

Counts data rows in a PDF's tables without building a parser: a data row is one
whose first cell is a serial number. Feeds docs/parser_accuracy.md.

    python data/raw/crossvalidate.py
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

SERIAL_RE = re.compile(r"^\s*\d{1,3}\s*\.?\s*$")


def pdf_rows(path: Path):
    """Return (page, cells, batch_idx) for every data row in a PDF.

    The batch column is located from the header rather than assumed, because a
    single file changes shape: the Jun-2025 spurious alert has 12 columns on
    page 1 and 10 on page 2. Continuation pages carry no header, so the last
    header seen in the file is carried forward.
    """
    rows = []
    batch_idx = None
    with pdfplumber.open(path) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            for tbl in page.extract_tables():
                for row in tbl:
                    cells = [(c or "").replace("\n", " ").strip() for c in row]
                    if not cells or not cells[0]:
                        continue
                    is_data = bool(SERIAL_RE.match(cells[0]))
                    if not is_data:
                        # A header cell is the short label "Batch No.", not prose.
                        # Data rows mention "batch" in the firm's reply text, so
                        # matching the bare word here would swallow real rows.
                        hdr = [i for i, c in enumerate(cells)
                               if re.match(r"^batch\s*(no\.?|number)?\s*\.?$", c, re.I)]
                        if hdr:
                            batch_idx = hdr[0]
                        continue
                    rows.append((pno, cells, batch_idx))
    return rows


def norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def key(s):
    """Join key: punctuation and spacing differ between the two sources
    ('CDL, Kolkata' in the PDF vs 'CDL Kolkata' in the JSON), so compare on
    alphanumerics only."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


TARGETS = [
    ("central_lab", "2025-07-18_cdsco-nsq-alert-for-the-month-of-june-2025_d2879e.pdf"),
    ("state_lab", "2025-07-18_state-nsq-alert-for-the-month-of-june-2025_5bd0fd.pdf"),
    ("spurious", "2025-07-18_list-of-spurious-drugs-for-the-month-of-june-2025_f9baf5.pdf"),
]
MONTH = "2025-06"

conn = sqlite3.connect(ROOT / "data" / "medcheck.db")
conn.row_factory = sqlite3.Row

print(f"# Cross-validation — alert month {MONTH}\n")
summary = []
all_pdf_batches = set()
for section, fname in TARGETS:
    path = ROOT / "data" / "pdfs" / fname
    rows = pdf_rows(path)
    db_rows = conn.execute(
        "SELECT * FROM nsq_records WHERE alert_month=? AND alert_section=?",
        (MONTH, section)).fetchall()
    print(f"## {section}")
    print(f"  PDF  : {fname}  -> {len(rows)} data rows")
    print(f"  JSON : {len(db_rows)} records in db")
    print(f"  delta: {len(db_rows) - len(rows):+d}")

    # Batch numbers are the most reliable join key available in both sources.
    pdf_batches = {key(r[1][r[2]]) for r in rows if r[2] is not None and len(r[1]) > r[2]}
    db_batches = {key(r["batch_number"]) for r in db_rows}
    only_pdf = sorted(b for b in pdf_batches - db_batches if b)
    only_db = sorted(b for b in db_batches - pdf_batches if b)
    print(f"  batches in both : {len(pdf_batches & db_batches)}")
    print(f"  only in PDF     : {len(only_pdf)} {only_pdf[:8]}")
    print(f"  only in JSON    : {len(only_db)} {only_db[:8]}")
    summary.append((section, len(rows), len(db_rows), len(pdf_batches & db_batches),
                    len(only_pdf), len(only_db)))
    all_pdf_batches.update(b for b in pdf_batches if b)
    print()

# The two sources split central-vs-state differently, so the meaningful fidelity
# question is whether the same set of tested batches appears in both, regardless
# of which file or section each landed in.
all_db = {key(r["batch_number"]) for r in conn.execute(
    "SELECT batch_number FROM nsq_records WHERE alert_month=?", (MONTH,)).fetchall()}
all_db = {b for b in all_db if b}
print("## union across sections")
print(f"  distinct batches in PDFs : {len(all_pdf_batches)}")
print(f"  distinct batches in JSON : {len(all_db)}")
print(f"  in both                  : {len(all_pdf_batches & all_db)}")
print(f"  only in PDFs             : {len(all_pdf_batches - all_db)} "
      f"{sorted(all_pdf_batches - all_db)[:10]}")
print(f"  only in JSON             : {len(all_db - all_pdf_batches)} "
      f"{sorted(all_db - all_pdf_batches)[:10]}")
recall = len(all_pdf_batches & all_db) / max(len(all_pdf_batches), 1)
print(f"  JSON recall of PDF batches: {recall:.1%}")
print()

print("## Spot-check — 10 records, JSON vs PDF text")
path = ROOT / "data" / "pdfs" / TARGETS[0][1]
rows = pdf_rows(path)
checked = agree = 0
for pno, cells, bidx in rows[:10]:
    if len(cells) < 8:
        continue
    batch = key(cells[bidx])
    rec = next((r for r in conn.execute(
        "SELECT * FROM nsq_records WHERE alert_month=?", (MONTH,))
        if key(r["batch_number"]) == batch), None)
    checked += 1
    if not rec:
        print(f"  [{batch}] NOT FOUND in db")
        continue
    drug_ok = key(cells[1])[:16] in key(rec["drug_name_raw"])
    mfr_ok = key(cells[5])[:16] in key(rec["manufacturer_raw"])
    lab_ok = key(cells[7])[:8] in key(rec["testing_lab"])
    ok = drug_ok and mfr_ok and lab_ok
    agree += ok
    print(f"  [{batch}] drug={'Y' if drug_ok else 'N'} mfr={'Y' if mfr_ok else 'N'} "
          f"lab={'Y' if lab_ok else 'N'}  {rec['drug_name_raw'][:46]}")
print(f"\n  agreed on all 3 fields: {agree}/{checked}")

print("\n## machine summary")
print(json.dumps(summary))
