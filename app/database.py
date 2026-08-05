"""SQLite database layer for the corrective actions tracking system."""
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get("CAT_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "corrective_actions.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    department TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS escapes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ref TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    escape_type TEXT NOT NULL CHECK (escape_type IN ('internal', 'external')),
    customer TEXT NOT NULL DEFAULT '',
    program TEXT NOT NULL DEFAULT '',
    part_number TEXT NOT NULL DEFAULT '',
    severity INTEGER NOT NULL DEFAULT 3 CHECK (severity BETWEEN 1 AND 4),
    likelihood INTEGER NOT NULL DEFAULT 2 CHECK (likelihood BETWEEN 1 AND 4),
    rating_score INTEGER NOT NULL DEFAULT 0,
    escalation_level TEXT NOT NULL DEFAULT 'None',
    status TEXT NOT NULL DEFAULT 'Open'
        CHECK (status IN ('Open', 'Containment', 'In Progress', 'Pending Closure', 'Closed')),
    containment_plan TEXT NOT NULL DEFAULT '',
    containment_due TEXT,
    due_date TEXT,
    owner_id INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    closed_at TEXT
);

CREATE TABLE IF NOT EXISTS cars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ref TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    car_type TEXT NOT NULL CHECK (car_type IN ('internal', 'external')),
    supplier TEXT NOT NULL DEFAULT '',
    escape_id INTEGER REFERENCES escapes(id),
    severity INTEGER NOT NULL DEFAULT 3 CHECK (severity BETWEEN 1 AND 4),
    status TEXT NOT NULL DEFAULT 'Draft'
        CHECK (status IN ('Draft', 'Validated', 'Issued', 'Response Submitted',
                          'Response Accepted', 'Response Rejected', 'Closed')),
    validation_notes TEXT NOT NULL DEFAULT '',
    validated_by INTEGER REFERENCES users(id),
    validated_at TEXT,
    response_text TEXT NOT NULL DEFAULT '',
    response_submitted_at TEXT,
    response_decision_notes TEXT NOT NULL DEFAULT '',
    escalation_level TEXT NOT NULL DEFAULT 'None',
    due_date TEXT,
    owner_id INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    closed_at TEXT
);

CREATE TABLE IF NOT EXISTS capas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ref TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    car_id INTEGER REFERENCES cars(id),
    rcca_method TEXT NOT NULL DEFAULT '5-Why'
        CHECK (rcca_method IN ('5-Why', 'Fishbone', '8D', 'Fault Tree', 'Other')),
    root_cause_category TEXT NOT NULL DEFAULT ''
        CHECK (root_cause_category IN ('', 'Process', 'Design', 'Supplier', 'Training',
                                       'Equipment', 'Documentation', 'Material', 'Other')),
    root_cause TEXT NOT NULL DEFAULT '',
    corrective_action TEXT NOT NULL DEFAULT '',
    preventive_action TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Open'
        CHECK (status IN ('Open', 'RCCA In Progress', 'Actions In Progress',
                          'Effectiveness Verification', 'Closed')),
    effectiveness_result TEXT NOT NULL DEFAULT '',
    effective INTEGER,
    verified_by INTEGER REFERENCES users(id),
    verified_at TEXT,
    due_date TEXT,
    owner_id INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    closed_at TEXT
);

CREATE TABLE IF NOT EXISTS bulletins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ref TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    car_id INTEGER REFERENCES cars(id),
    audience TEXT NOT NULL DEFAULT 'All Quality',
    issued_by INTEGER REFERENCES users(id),
    issued_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_type TEXT NOT NULL CHECK (record_type IN ('escape', 'car', 'capa', 'bulletin')),
    record_id INTEGER NOT NULL,
    recipient TEXT NOT NULL,
    message TEXT NOT NULL,
    sent_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_type TEXT NOT NULL CHECK (record_type IN ('escape', 'car', 'capa', 'bulletin')),
    record_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    changed_by TEXT NOT NULL DEFAULT 'system',
    changed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_history_record ON history(record_type, record_id);
CREATE INDEX IF NOT EXISTS idx_notifications_record ON notifications(record_type, record_id);
"""


def init_db(path: str | None = None) -> None:
    target = path or DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
    with sqlite3.connect(target) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_conn(path: str | None = None):
    target = path or DB_PATH
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def next_ref(conn: sqlite3.Connection, table: str, prefix: str) -> str:
    row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
    return f"{prefix}-{row['n'] + 1:04d}"


def log_history(conn: sqlite3.Connection, record_type: str, record_id: int,
                action: str, detail: str = "", changed_by: str = "system") -> None:
    conn.execute(
        "INSERT INTO history (record_type, record_id, action, detail, changed_by) VALUES (?, ?, ?, ?, ?)",
        (record_type, record_id, action, detail, changed_by),
    )


def send_notification(conn: sqlite3.Connection, record_type: str, record_id: int,
                      recipient: str, message: str) -> None:
    """Record an outbound notification. Integration with email/Teams can hook in here."""
    conn.execute(
        "INSERT INTO notifications (record_type, record_id, recipient, message) VALUES (?, ?, ?, ?)",
        (record_type, record_id, recipient, message),
    )
