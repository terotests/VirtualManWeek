from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Optional, Iterable
from datetime import datetime, date
from ..config import appdata_root, settings_path
import json

DB_FILE = "data.sqlite3"
SCHEMA_VERSION = 1

# Mutable override (set from UI based on Settings)
_DB_PATH_OVERRIDE: Optional[Path] = None


def set_db_path(path: Path | None) -> None:
    global _DB_PATH_OVERRIDE
    _DB_PATH_OVERRIDE = path


def db_path() -> Path:
    if _DB_PATH_OVERRIDE:
        return _DB_PATH_OVERRIDE
    # Try to read persisted setting for database_path to avoid circular import of Settings dataclass
    try:
        p = settings_path()
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            dbp = data.get("database_path")
            if dbp:
                return Path(dbp)
    except Exception:
        pass
    return appdata_root() / DB_FILE


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
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
    _ensure_time_entries_manual_seconds(cur)
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
            manual_seconds INTEGER DEFAULT 0,
            project_id INTEGER,
            mode_label TEXT,
            description TEXT,
            source TEXT CHECK(source in ('auto','manual','manual_replace')),
            replaced_by INTEGER,
            FOREIGN KEY(project_id) REFERENCES projects(id),
            FOREIGN KEY(week_id) REFERENCES weeks(id)
        );
        CREATE TABLE setup(
            key TEXT PRIMARY KEY,
            value TEXT
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


def _ensure_time_entries_manual_seconds(cur: sqlite3.Cursor) -> None:
    cur.execute("PRAGMA table_info(time_entries)")
    cols = [r[1] for r in cur.fetchall()]
    if "manual_seconds" not in cols:
        cur.execute("ALTER TABLE time_entries ADD COLUMN manual_seconds INTEGER DEFAULT 0")


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
    *, start_ts: int, end_ts: int, active_seconds: int, idle_seconds: int, project_id: Optional[int], mode_label: str, description: Optional[str] = None, source: str = "auto", manual_seconds: int = 0
) -> None:
    dt = datetime.fromtimestamp(start_ts)
    week_id = ensure_week(dt.date())
    date_str = dt.strftime("%Y-%m-%d")
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO time_entries(week_id,date,start_ts,end_ts,active_seconds,idle_seconds,manual_seconds,project_id,mode_label,description,source)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (week_id, date_str, start_ts, end_ts, active_seconds, idle_seconds, manual_seconds, project_id, mode_label, description, source),
        )
        conn.commit()


def list_active_projects():
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, code, name FROM projects WHERE archived=0 ORDER BY LOWER(code)")
        return [dict(r) for r in cur.fetchall()]


def list_all_projects():
    """List all projects including archived ones, with archived status"""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, code, name, archived FROM projects ORDER BY archived ASC, LOWER(code)")
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
        # Get all modes with actual usage count from time_entries
        cur.execute("""
            SELECT 
                m.id, 
                m.label, 
                COALESCE(usage.count, 0) as count,
                m.last_used_at 
            FROM modes m
            LEFT JOIN (
                SELECT mode_label, COUNT(*) as count 
                FROM time_entries 
                GROUP BY mode_label
            ) usage ON m.label = usage.mode_label
            ORDER BY LOWER(m.label)
        """)
        modes_from_db = [dict(r) for r in cur.fetchall()]
        
        # Also get any modes that exist in time_entries but not in modes table
        cur.execute("""
            SELECT DISTINCT mode_label 
            FROM time_entries 
            WHERE mode_label NOT IN (SELECT label FROM modes)
        """)
        orphaned_modes = [r[0] for r in cur.fetchall()]
        
        # Add orphaned modes as temporary entries
        for mode_label in orphaned_modes:
            cur.execute("SELECT COUNT(*) FROM time_entries WHERE mode_label = ?", (mode_label,))
            count = cur.fetchone()[0]
            modes_from_db.append({
                'id': None,  # No ID since it's not in modes table
                'label': mode_label,
                'count': count,
                'last_used_at': None
            })
        
        return sorted(modes_from_db, key=lambda x: x['label'].lower())


def delete_mode(mode_id: int):
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM modes WHERE id=?", (mode_id,))
        conn.commit()


def update_mode(mode_id: int, new_label: str):
    """Update the label of an existing mode."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE modes SET label=? WHERE id=?", (new_label, mode_id))
        conn.commit()


def rename_mode_everywhere(old_label: str, new_label: str):
    """Rename a mode everywhere it appears (modes table and time_entries table).
    This ensures consistency across all tables."""
    with connect() as conn:
        cur = conn.cursor()
        
        # Update the modes table
        cur.execute("UPDATE modes SET label=? WHERE label=?", (new_label, old_label))
        
        # Update all time_entries that use this mode_label
        cur.execute("UPDATE time_entries SET mode_label=? WHERE mode_label=?", (new_label, old_label))
        
        conn.commit()


def check_mode_name_conflict(new_name: str, exclude_id: Optional[int] = None) -> bool:
    """Check if a mode name already exists (case-insensitive, trimmed).
    Returns True if conflict exists, False if name is available.
    exclude_id: mode ID to exclude from the check (for editing existing modes)."""
    new_name_normalized = new_name.strip().lower()
    
    with connect() as conn:
        cur = conn.cursor()
        
        # Check in modes table
        if exclude_id is not None:
            cur.execute("SELECT id FROM modes WHERE LOWER(TRIM(label))=? AND id!=?", (new_name_normalized, exclude_id))
        else:
            cur.execute("SELECT id FROM modes WHERE LOWER(TRIM(label))=?", (new_name_normalized,))
        
        if cur.fetchone():
            return True
        
        # Also check in time_entries for auto-detected modes
        cur.execute("SELECT DISTINCT mode_label FROM time_entries WHERE LOWER(TRIM(mode_label))=?", (new_name_normalized,))
        if cur.fetchone():
            return True
    
    return False


def mode_distribution(start_date: Optional['datetime'] = None, end_date: Optional['datetime'] = None, limit: Optional[int] = None):
    """Return list of {mode, total_active_seconds} sorted descending by active time.
    Optionally filter by date range and limit number of rows (for charts)."""
    with connect() as conn:
        cur = conn.cursor()
        base = "SELECT mode_label AS mode, SUM(active_seconds) AS total_active FROM time_entries"
        
        # Add date filtering if provided
        conditions = []
        params = []
        if start_date:
            conditions.append("start_ts >= ?")
            params.append(int(start_date.timestamp()))
        if end_date:
            conditions.append("start_ts <= ?")
            params.append(int(end_date.timestamp()))
        
        if conditions:
            base += " WHERE " + " AND ".join(conditions)
        
        base += " GROUP BY mode_label ORDER BY total_active DESC"
        
        if limit:
            base += f" LIMIT {int(limit)}"
        
        cur.execute(base, params)
        return [dict(r) for r in cur.fetchall()]


def project_distribution(start_date: Optional['datetime'] = None, end_date: Optional['datetime'] = None, limit: Optional[int] = None):
    """Return list of {project_name, total_active_seconds} sorted descending by active time.
    Optionally filter by date range and limit number of rows (for charts)."""
    with connect() as conn:
        cur = conn.cursor()
        base = """
            SELECT 
                CASE 
                    WHEN te.project_id IS NULL THEN '(No Project)'
                    WHEN p.code IS NOT NULL AND p.name IS NOT NULL THEN p.code || ' - ' || p.name
                    WHEN p.code IS NOT NULL THEN p.code
                    WHEN p.name IS NOT NULL THEN p.name
                    ELSE '(Unknown Project)'
                END AS project_name,
                SUM(te.active_seconds) AS total_active
            FROM time_entries te
            LEFT JOIN projects p ON te.project_id = p.id
        """
        
        # Add date filtering if provided
        conditions = []
        params = []
        if start_date:
            conditions.append("te.start_ts >= ?")
            params.append(int(start_date.timestamp()))
        if end_date:
            conditions.append("te.start_ts <= ?")
            params.append(int(end_date.timestamp()))
        
        if conditions:
            base += " WHERE " + " AND ".join(conditions)
        
        base += " GROUP BY te.project_id, p.code, p.name ORDER BY total_active DESC"
        
        if limit:
            base += f" LIMIT {int(limit)}"
        
        cur.execute(base, params)
        return [dict(r) for r in cur.fetchall()]


def get_time_entries_for_export(start_date: Optional['datetime'] = None, end_date: Optional['datetime'] = None, limit: int = 1000):
    """Get time entries for CSV export, optionally filtered by date range."""
    with connect() as conn:
        cur = conn.cursor()
        base = "SELECT date, project_id, mode_label, active_seconds, idle_seconds, manual_seconds, description FROM time_entries"
        
        # Add date filtering if provided
        conditions = []
        params = []
        if start_date:
            conditions.append("start_ts >= ?")
            params.append(int(start_date.timestamp()))
        if end_date:
            conditions.append("start_ts <= ?")
            params.append(int(end_date.timestamp()))
        
        if conditions:
            base += " WHERE " + " AND ".join(conditions)
        
        base += " ORDER BY start_ts DESC"
        if limit:
            base += f" LIMIT {int(limit)}"
        
        cur.execute(base, params)
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


def get_last_entry_end_time(date_str: str) -> Optional[int]:
    """Get the end timestamp of the last NON-IDLE entry for a given date.
    Returns None if no non-idle entries exist for that date."""
    with connect() as conn:
        cur = conn.cursor()
        # Try to get end_ts first, but if it's None or 0, calculate from start_ts + duration
        # Exclude entries where mode_label is 'Idle' (case-insensitive)
        cur.execute(
            """SELECT start_ts, end_ts, active_seconds, idle_seconds, manual_seconds 
               FROM time_entries WHERE date=? AND LOWER(mode_label) != 'idle' 
               ORDER BY start_ts DESC LIMIT 1""",
            (date_str,)
        )
        row = cur.fetchone()
        if not row:
            return None
        
        start_ts, end_ts, active_seconds, idle_seconds, manual_seconds = row
        
        # If we have a valid end_ts, use it
        if end_ts and end_ts > 0:
            return end_ts
        
        # Otherwise calculate from start_ts + total duration
        if start_ts:
            total_seconds = (active_seconds or 0) + (idle_seconds or 0) + (manual_seconds or 0)
            return start_ts + total_seconds
        
        return None


def _ensure_setup_table(cur: sqlite3.Cursor) -> None:
    """Ensure the setup table exists for tracking initialization state."""
    try:
        cur.execute("SELECT COUNT(*) FROM setup LIMIT 1")
    except sqlite3.OperationalError:
        # Table doesn't exist, create it
        cur.execute("""
            CREATE TABLE setup(
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)


def initialize_default_modes():
    """Initialize default modes if not already done."""
    from ..utils.constants import QUICK_MODES
    
    with connect() as conn:
        cur = conn.cursor()
        
        # Ensure setup table exists
        _ensure_setup_table(cur)
        
        # Check if modes have been initialized
        cur.execute("SELECT value FROM setup WHERE key = 'modes_initialized'")
        row = cur.fetchone()
        
        if row and row[0] == '1':
            return  # Already initialized
        
        # Add default modes that don't exist yet
        for mode_label in QUICK_MODES:
            mode_lower = mode_label.lower()
            cur.execute("SELECT id FROM modes WHERE label_lower = ?", (mode_lower,))
            if not cur.fetchone():
                # Mode doesn't exist, add it
                cur.execute(
                    "INSERT INTO modes(label, label_lower, usage_count, last_used_at) VALUES(?, ?, 0, NULL)",
                    (mode_label, mode_lower)
                )
        
        # Mark as initialized
        cur.execute(
            "INSERT OR REPLACE INTO setup(key, value) VALUES('modes_initialized', '1')"
        )
        
        conn.commit()