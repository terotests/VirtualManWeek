from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Optional, Iterable
from datetime import datetime, date
from ..config import appdata_root

DB_FILE = "data.sqlite3"
SCHEMA_VERSION = 1


def db_path() -> Path:
    return appdata_root() / DB_FILE


def connect() -> sqlite3.Connection:
    path = db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def initialize() -> None:
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS meta(
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    cur.execute("SELECT value FROM meta WHERE key='schema_version'")
    row = cur.fetchone()
    if row is None:
        _create_schema(cur)
        cur.execute("INSERT INTO meta(key,value) VALUES('schema_version', ?)", (str(SCHEMA_VERSION),))
    # Ensure new columns (lightweight migration)
    _ensure_time_entries_description(cur)
    conn.commit()
    conn.close()


def _create_schema(cur: sqlite3.Cursor) -> None:
    cur.executescript(
        """
        CREATE TABLE projects(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            code_lower TEXT UNIQUE,
            name TEXT,
            archived INTEGER DEFAULT 0,
            created_at INTEGER,
            updated_at INTEGER
        );
        CREATE TABLE modes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT,
            label_lower TEXT UNIQUE,
            usage_count INTEGER DEFAULT 0,
            last_used_at INTEGER
        );
        CREATE TABLE weeks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            iso_year INTEGER,
            iso_week INTEGER,
            start_date TEXT,
            created_at INTEGER
        );
        CREATE TABLE time_entries(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_id INTEGER,
            date TEXT,
            start_ts INTEGER,
            end_ts INTEGER,
            active_seconds INTEGER,
            idle_seconds INTEGER DEFAULT 0,
            project_id INTEGER,
            mode_label TEXT,
            description TEXT,
            source TEXT CHECK(source in ('auto','manual','manual_replace')),
            replaced_by INTEGER,
            FOREIGN KEY(project_id) REFERENCES projects(id),
            FOREIGN KEY(week_id) REFERENCES weeks(id)
        );
        CREATE INDEX idx_time_entries_week_date ON time_entries(week_id, date);
        CREATE INDEX idx_modes_usage ON modes(usage_count DESC);
        CREATE INDEX idx_projects_code ON projects(code_lower);
        """
    )


def _ensure_time_entries_description(cur: sqlite3.Cursor) -> None:
    cur.execute("PRAGMA table_info(time_entries)")
    cols = [r[1] for r in cur.fetchall()]
    if "description" not in cols:
        cur.execute("ALTER TABLE time_entries ADD COLUMN description TEXT")


def upsert_project(code: str, name: str) -> int:
    code_norm = code.strip()
    code_lower = code_norm.lower()
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM projects WHERE code_lower=?", (code_lower,))
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE projects SET name=?, updated_at=strftime('%s','now') WHERE id=?", (name, row["id"]))
            return row["id"]
        cur.execute(
            "INSERT INTO projects(code, code_lower, name, created_at, updated_at) VALUES(?,?,?,?,strftime('%s','now'))",
            (code_norm, code_lower, name, None),
        )
        return cur.lastrowid


def upsert_mode(label: str) -> int:
    norm = label.strip()
    lower = norm.lower()
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM modes WHERE label_lower=?", (lower,))
        row = cur.fetchone()
        if row:
            cur.execute(
                "UPDATE modes SET usage_count=usage_count+1, last_used_at=strftime('%s','now') WHERE id=?",
                (row["id"],),
            )
            return row["id"]
        cur.execute(
            "INSERT INTO modes(label, label_lower, usage_count, last_used_at) VALUES(?,?,1,strftime('%s','now'))",
            (norm, lower),
        )
        return cur.lastrowid


def ensure_week(dt: date) -> int:
    """Return week_id for ISO week of given date, creating if needed."""
    iso_year, iso_week, _ = dt.isocalendar()
    start = iso_week_start(iso_year, iso_week)
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM weeks WHERE iso_year=? AND iso_week=?",
            (iso_year, iso_week),
        )
        row = cur.fetchone()
        if row:
            return row["id"]
        cur.execute(
            "INSERT INTO weeks(iso_year, iso_week, start_date, created_at) VALUES(?,?,?, strftime('%s','now'))",
            (iso_year, iso_week, start.isoformat()),
        )
        return cur.lastrowid


def iso_week_start(iso_year: int, iso_week: int) -> date:
    # Python 3.8+ provides fromisocalendar
    return date.fromisocalendar(iso_year, iso_week, 1)


def insert_time_entry(
    *, start_ts: int, end_ts: int, active_seconds: int, idle_seconds: int, project_id: Optional[int], mode_label: str, description: Optional[str] = None, source: str = "auto"
) -> None:
    dt = datetime.fromtimestamp(start_ts)
    week_id = ensure_week(dt.date())
    date_str = dt.strftime("%Y-%m-%d")
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO time_entries(week_id,date,start_ts,end_ts,active_seconds,idle_seconds,project_id,mode_label,description,source)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (week_id, date_str, start_ts, end_ts, active_seconds, idle_seconds, project_id, mode_label, description, source),
        )
        conn.commit()


def list_active_projects():
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, code, name FROM projects WHERE archived=0 ORDER BY LOWER(code)")
        return [dict(r) for r in cur.fetchall()]


def set_project_archived(project_id: int, archived: bool):
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE projects SET archived=? WHERE id=?", (1 if archived else 0, project_id))
        conn.commit()


def tag_cloud(limit: int):
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT label FROM modes ORDER BY LOWER(label) LIMIT ?", (limit,))
        return [r[0] for r in cur.fetchall()]


def mode_suggestions():
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT label FROM modes ORDER BY LOWER(label)")
        return [r[0] for r in cur.fetchall()]


# New helpers for mode management

def list_modes():
    """Return all stored modes with usage stats."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, label, usage_count, last_used_at FROM modes ORDER BY LOWER(label)")
        return [dict(r) for r in cur.fetchall()]


def delete_mode(mode_id: int):
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM modes WHERE id=?", (mode_id,))
        conn.commit()


def mode_distribution(limit: Optional[int] = None):
    """Return list of {mode, total_active_seconds} sorted descending by active time.
    Optionally limit number of rows (for charts)."""
    with connect() as conn:
        cur = conn.cursor()
        base = "SELECT mode_label AS mode, SUM(active_seconds) AS total_active FROM time_entries GROUP BY mode_label ORDER BY total_active DESC"
        if limit:
            base += f" LIMIT {int(limit)}"
        cur.execute(base)
        return [dict(r) for r in cur.fetchall()]


def clear_logged_entries() -> dict:
    """Remove all logged time data (time_entries + weeks) and reset mode usage stats.
    Returns counts of deleted rows for feedback."""
    stats = {"time_entries": 0, "weeks": 0, "modes_reset": 0}
    with connect() as conn:
        cur = conn.cursor()
        # Count rows first
        cur.execute("SELECT COUNT(*) FROM time_entries")
        stats["time_entries"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM weeks")
        stats["weeks"] = cur.fetchone()[0]
        # Delete time entries & weeks
        cur.execute("DELETE FROM time_entries")
        cur.execute("DELETE FROM weeks")
        # Reset mode usage stats (keep labels for convenience)
        cur.execute("UPDATE modes SET usage_count=0, last_used_at=NULL")
        cur.execute("SELECT COUNT(*) FROM modes")
        stats["modes_reset"] = cur.fetchone()[0]
        conn.commit()
    return stats