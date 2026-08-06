# MedCheck

A searchable public database of medicines flagged as Not of Standard Quality (NSQ) or spurious by India's drug regulator, CDSCO.

CDSCO tests medicines pulled from real pharmacy shelves every month and publishes the failures — as unsearchable monthly PDFs. MedCheck makes that data searchable.

**Status:** Phase 0 (Discovery). See `plan.md` for the full spec, `CLAUDE.md` for current state, `docs/pdf_inventory.md` for what the source data actually looks like.

## What MedCheck is not

MedCheck is a mirror of CDSCO's own published data, not an accuser. A flagged batch is not a flagged product, and **nothing here is a reason to stop taking a medicine** — show it to your pharmacist or doctor and ask them. See `plan.md` §1.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install pdfplumber requests
```

## Fetching source PDFs

```bash
.venv/bin/python src/fetch.py --list-only   # show what's discoverable
.venv/bin/python src/fetch.py --limit 10    # 10 most recent alerts
.venv/bin/python src/fetch.py --all         # all 50 known alerts
```

PDFs land in `data/pdfs/` (gitignored) with a `manifest.json` recording title, release date, source URL and SHA-256 for each. Re-running skips anything already downloaded.
