# MedCheck

A searchable public database of medicines flagged as Not of Standard Quality (NSQ) or spurious by India's drug regulator, CDSCO.

CDSCO tests medicines pulled from real pharmacy shelves every month and publishes the failures — as unsearchable monthly PDFs. MedCheck makes that data searchable.

**Status:** Phase 1a complete — 6,155 records across 90 alert months (Jan-2019 → Jun-2026) in `data/medcheck.db`.

See `plan.md` for the full spec, `CLAUDE.md` for current state, `docs/pdf_inventory.md` for what the source data looks like, `docs/methodology.md` for how records are identified and scored, and `docs/parser_accuracy.md` for the accuracy evidence.

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

## Building the database

```bash
.venv/bin/python src/ingest/cdsco_json.py     # cache the CDSCO portal JSON
cd src && ../.venv/bin/python normalize.py    # normalize the cache -> data/medcheck.db
```

Both steps are idempotent. Raw API responses are cached in `data/raw/portal/` (committed) and normalization reads only from there, never the network — so the database is reproducible offline and `data/medcheck.db` itself is gitignored.

Add `--dry-run` to `normalize.py` to see the record and flag counts without writing.

```bash
.venv/bin/python data/raw/crossvalidate.py    # JSON vs source PDFs for 2025-06
```
