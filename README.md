# MedCheck

A searchable public database of medicines flagged as Not of Standard Quality (NSQ) or spurious by India's drug regulator, CDSCO.

CDSCO tests medicines pulled from real pharmacy shelves every month and publishes the failures — as unsearchable monthly PDFs. MedCheck makes that data searchable.

**Status:** 6,155 records across 90 alert months (Jan-2019 → Jun-2026), search site live, dataset published, analysis written up. Manufacturer identity resolution is intentionally partial (1,856 of ~5,107 raw spellings collapsed so far) — every merged page says so.

- **Search the data:** _(live URL added here at deploy time)_
- **Download the dataset:** `analysis/dataset/medcheck_nsq_records.csv` (CC0) — see `analysis/dataset/README.md`
- **Read the findings:** `analysis/FINDINGS.md` — methodology, limitations, every number reproducible

See `plan.md` for the full spec, `CLAUDE.md` for current project state and decision history, `docs/pdf_inventory.md` for what the source data looks like, `docs/methodology.md` for how records are identified and scored, `docs/entity_resolution.md` for the manufacturer-matching approach, and `docs/parser_accuracy.md` for the accuracy evidence.

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

## The search site

```bash
.venv/bin/python scripts/export_static.py   # medcheck.db -> static JSON for web/
cd web && npm install && npm run dev        # http://localhost:3000
npm run build                               # static export to web/out/
```

Re-run `export_static.py` after any change to `data/medcheck.db`. It writes two shapes:

| Output | Shipped to the browser? | Purpose |
|---|---|---|
| `web/public/data/search-index.json` | yes (~297 KB brotli) | client-side search, lazy-loaded on first interaction |
| `web/public/data/meta.json` | yes (~1.5 KB) | record counts and coverage |
| `web/data/records.json` | **no** | read at build time to render static record pages |
| `web/data/manufacturers.json` | **no** | read at build time to render manufacturer pages |

Neither is committed — both regenerate from the database, which itself regenerates from `data/raw/portal/`.

The build is a fully static export (`output: 'export'`): no server, so there is nowhere for a search to be logged. It produces ~11,000 pages, one per record and per manufacturer, which takes a couple of minutes.

## Tests

```bash
.venv/bin/python tests/test_categorise.py     # failure_category mapper (no pytest needed)
cd web && npm run test:search                 # search behaviour against the real index
```
