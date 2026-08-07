"""SQLite schema and write helpers for MedCheck (plan.md §3).

Idempotent: CREATE TABLE IF NOT EXISTS, and records are upserted by primary key
so re-running ingestion refreshes rows rather than duplicating them.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "medcheck.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS nsq_records (
    id                   TEXT PRIMARY KEY,
    alert_month          TEXT,      -- ISO "2026-05"
    alert_section        TEXT,      -- central_lab | state_lab | spurious
    drug_name_raw        TEXT,
    drug_name_clean      TEXT,
    active_ingredients   TEXT,      -- JSON array; null until a later phase parses it
    dosage_form          TEXT,
    batch_number         TEXT,
    mfg_date             TEXT,      -- ISO, often partial: "2025-10"
    expiry_date          TEXT,
    manufacturer_raw     TEXT,
    manufacturer_id      INTEGER REFERENCES manufacturers(id),
    label_claim_disputed INTEGER,   -- 0/1/NULL
    failure_reason_raw   TEXT,
    failure_category     TEXT,      -- JSON array (plan.md §3.3)
    testing_lab          TEXT,
    -- Derived from the laboratory's identity, NOT from CDSCO's reporting-source
    -- field. alert_section above stays exactly as published even where the two
    -- disagree (857 records); the disagreement is recorded in parse_flags.
    -- See src/resolve/labs.py.
    lab_type             TEXT,      -- central | state | unknown
    lab_name_canonical   TEXT,
    state                TEXT,
    source_url           TEXT NOT NULL,
    source_type          TEXT,      -- pdf | portal_json
    source_page          INTEGER,
    parse_confidence     REAL,
    parse_flags          TEXT,      -- JSON array
    created_at           TIMESTAMP
);

CREATE TABLE IF NOT EXISTS manufacturers (
    id               INTEGER PRIMARY KEY,
    canonical_name   TEXT,
    known_aliases    TEXT,          -- JSON array
    address_raw      TEXT,
    state            TEXT,
    first_seen_month TEXT,
    total_flags      INTEGER
);

CREATE INDEX IF NOT EXISTS idx_nsq_batch        ON nsq_records(batch_number);
CREATE INDEX IF NOT EXISTS idx_nsq_month        ON nsq_records(alert_month);
CREATE INDEX IF NOT EXISTS idx_nsq_section      ON nsq_records(alert_section);
CREATE INDEX IF NOT EXISTS idx_nsq_drug_clean   ON nsq_records(drug_name_clean);
CREATE INDEX IF NOT EXISTS idx_nsq_manufacturer ON nsq_records(manufacturer_raw);
CREATE INDEX IF NOT EXISTS idx_nsq_disputed     ON nsq_records(label_claim_disputed);
"""

COLUMNS = [
    "id", "alert_month", "alert_section", "drug_name_raw", "drug_name_clean",
    "active_ingredients", "dosage_form", "batch_number", "mfg_date", "expiry_date",
    "manufacturer_raw", "manufacturer_id", "label_claim_disputed", "failure_reason_raw",
    "failure_category", "testing_lab", "lab_type", "lab_name_canonical", "state",
    "source_url", "source_type", "source_page", "parse_confidence", "parse_flags",
    "created_at",
]

# Columns added after the table first shipped. CREATE TABLE IF NOT EXISTS will not
# alter an existing table, so an already-populated data/medcheck.db needs these
# added explicitly rather than silently going without them.
MIGRATIONS = [
    ("nsq_records", "lab_type", "TEXT"),
    ("nsq_records", "lab_name_canonical", "TEXT"),
]


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    migrate(conn)
    conn.commit()


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Add any post-launch columns missing from an existing database. Idempotent."""
    applied = []
    for table, column, decl in MIGRATIONS:
        existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
            applied.append(f"{table}.{column}")
    if applied:
        conn.commit()
    return applied


def upsert_records(conn: sqlite3.Connection, records: list[dict]) -> int:
    """Insert or replace by id. Returns rows written."""
    if not records:
        return 0
    placeholders = ",".join("?" * len(COLUMNS))
    sql = f"INSERT OR REPLACE INTO nsq_records ({','.join(COLUMNS)}) VALUES ({placeholders})"
    conn.executemany(sql, [[r.get(c) for c in COLUMNS] for r in records])
    conn.commit()
    return len(records)


def counts(conn: sqlite3.Connection) -> dict:
    q = lambda s: conn.execute(s).fetchone()[0]  # noqa: E731
    return {
        "total": q("SELECT COUNT(*) FROM nsq_records"),
        "central_lab": q("SELECT COUNT(*) FROM nsq_records WHERE alert_section='central_lab'"),
        "state_lab": q("SELECT COUNT(*) FROM nsq_records WHERE alert_section='state_lab'"),
        "spurious": q("SELECT COUNT(*) FROM nsq_records WHERE alert_section='spurious'"),
        "disputed": q("SELECT COUNT(*) FROM nsq_records WHERE label_claim_disputed=1"),
        "flagged": q("SELECT COUNT(*) FROM nsq_records WHERE parse_flags != '[]'"),
        "with_state": q("SELECT COUNT(*) FROM nsq_records WHERE state IS NOT NULL"),
        "months": q("SELECT COUNT(DISTINCT alert_month) FROM nsq_records"),
    }


if __name__ == "__main__":
    conn = connect()
    init(conn)
    print(f"initialised {DB_PATH}")
    print(counts(conn))
