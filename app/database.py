"""
app/database.py — SQLite helpers for Campaign Manager.
Single pf2e.db file holds both game data and app tables.
"""
import os
import sqlite3
from pathlib import Path

_default = Path("/data/pf2e.db") if Path("/data").exists() else Path(__file__).parent.parent / "pf2e.db"
DB_PATH  = Path(os.environ.get("DB_PATH", str(_default)))


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create app tables if they don't exist (game tables already present)."""
    conn = get_conn()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id   TEXT PRIMARY KEY,
            name TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS room_messages (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id   TEXT NOT NULL,
            username  TEXT NOT NULL,
            type      TEXT NOT NULL DEFAULT 'text',
            content   TEXT NOT NULL,
            timestamp DATETIME DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS polls (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            options  TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS poll_votes (
            poll_id    INTEGER NOT NULL,
            voter      TEXT    NOT NULL,
            option_idx INTEGER NOT NULL,
            PRIMARY KEY (poll_id, voter)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS session_notes (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            date    TEXT NOT NULL,
            title   TEXT NOT NULL,
            content TEXT NOT NULL,
            author  TEXT NOT NULL DEFAULT '',
            created DATETIME DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ref_files (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            filename      TEXT NOT NULL,
            original_name TEXT NOT NULL,
            uploaded_by   TEXT NOT NULL DEFAULT 'admin',
            created       DATETIME DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT NOT NULL,
            time        TEXT NOT NULL DEFAULT '',
            title       TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            author      TEXT NOT NULL,
            created     DATETIME DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS event_attendees (
            event_id INTEGER NOT NULL,
            username TEXT    NOT NULL,
            PRIMARY KEY (event_id, username)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS campaign_sessions (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT    NOT NULL,
            arc     TEXT    NOT NULL DEFAULT 'custom',
            created DATETIME DEFAULT (datetime('now')),
            updated DATETIME DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS session_encounters (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id     INTEGER NOT NULL REFERENCES campaign_sessions(id) ON DELETE CASCADE,
            hook           TEXT    NOT NULL DEFAULT '',
            who            TEXT    NOT NULL DEFAULT '',
            action         TEXT    NOT NULL DEFAULT '',
            modifier       TEXT    NOT NULL DEFAULT '',
            object         TEXT    NOT NULL DEFAULT '',
            creature_types TEXT    NOT NULL DEFAULT '[]',
            environment    TEXT    NOT NULL DEFAULT '',
            arc            TEXT    NOT NULL DEFAULT '',
            party_level    INTEGER NOT NULL DEFAULT 1,
            created        DATETIME DEFAULT (datetime('now'))
        )
    """)

    conn.execute("INSERT OR IGNORE INTO rooms (id, name) VALUES ('pf2e', 'Pathfinder 2e')")

    conn.commit()
    conn.close()


# ── PF2E game data queries ─────────────────────────────────────────────────────

def get_stats():
    conn = get_conn()
    stats = {}
    for table in ("spells", "creatures", "feats", "conditions", "items"):
        stats[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    conn.close()
    return stats


def search_spells(q="", level=None, tradition=None, spell_type=None, limit=100):
    conn = get_conn()
    params, clauses = [], []
    if q:
        clauses.append("id IN (SELECT rowid FROM spells_fts WHERE spells_fts MATCH ?)")
        params.append(q + "*")
    if level is not None:
        clauses.append("level = ?"); params.append(int(level))
    if tradition:
        clauses.append("traditions LIKE ?"); params.append(f"%{tradition}%")
    if spell_type:
        clauses.append("type = ?"); params.append(spell_type)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(f"SELECT * FROM spells {where} ORDER BY level, name LIMIT ?", params + [limit]).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_creatures(q="", level=None, creature_type=None, limit=100):
    conn = get_conn()
    params, clauses = [], []
    if q:
        clauses.append("id IN (SELECT rowid FROM creatures_fts WHERE creatures_fts MATCH ?)")
        params.append(q + "*")
    if level is not None:
        clauses.append("level = ?"); params.append(int(level))
    if creature_type:
        clauses.append("type = ?"); params.append(creature_type)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(f"SELECT * FROM creatures {where} ORDER BY level, name LIMIT ?", params + [limit]).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_feats(q="", level=None, feat_class=None, limit=100):
    conn = get_conn()
    params, clauses = [], []
    if q:
        clauses.append("id IN (SELECT rowid FROM feats_fts WHERE feats_fts MATCH ?)")
        params.append(q + "*")
    if level is not None:
        clauses.append("level = ?"); params.append(int(level))
    if feat_class:
        clauses.append("class LIKE ?"); params.append(f"%{feat_class}%")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(f"SELECT * FROM feats {where} ORDER BY level, name LIMIT ?", params + [limit]).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_items(q="", level=None, limit=100):
    conn = get_conn()
    params, clauses = [], []
    if q:
        clauses.append("id IN (SELECT rowid FROM items_fts WHERE items_fts MATCH ?)")
        params.append(q + "*")
    if level is not None:
        clauses.append("level = ?"); params.append(int(level))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(f"SELECT * FROM items {where} ORDER BY level, name LIMIT ?", params + [limit]).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_conditions():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM conditions ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Encounter / Adventure queries ──────────────────────────────────────────────

def search_encounters(q="", adventure_id=None, difficulty=None, level=None, limit=50):
    conn = get_conn()
    params, clauses = [], []
    if q:
        clauses.append("(title LIKE ? OR raw_text LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if adventure_id:
        clauses.append("adventure_id = ?"); params.append(adventure_id)
    if difficulty:
        clauses.append("difficulty = ?"); params.append(difficulty.upper())
    if level is not None:
        clauses.append("level = ?"); params.append(int(level))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(
        f"SELECT id, adventure_id, chapter_id, title, difficulty, level, raw_text "
        f"FROM encounters {where} ORDER BY adventure_id, id LIMIT ?",
        params + [limit]
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_encounter_by_id(enc_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM encounters WHERE id = ?", (enc_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Campaign sessions ──────────────────────────────────────────────────────────

def get_campaign_sessions() -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, name, arc, created, updated FROM campaign_sessions ORDER BY updated DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_campaign_session(name: str, arc: str = "custom") -> dict:
    conn = get_conn()
    cur  = conn.execute(
        "INSERT INTO campaign_sessions (name, arc) VALUES (?, ?)", (name, arc)
    )
    conn.commit()
    row = conn.execute(
        "SELECT id, name, arc, created, updated FROM campaign_sessions WHERE id = ?", (cur.lastrowid,)
    ).fetchone()
    conn.close()
    return dict(row)


def delete_campaign_session(session_id: int) -> bool:
    conn = get_conn()
    conn.execute("DELETE FROM campaign_sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()
    return True


def record_session_encounter(
    session_id: int,
    hook: str,
    who: str,
    action: str,
    modifier: str,
    obj: str,
    creature_types: list[str],
    environment: str,
    arc: str,
    party_level: int,
) -> None:
    import json as _json
    conn = get_conn()
    conn.execute(
        """INSERT INTO session_encounters
           (session_id, hook, who, action, modifier, object,
            creature_types, environment, arc, party_level)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (session_id, hook, who, action, modifier, obj,
         _json.dumps(creature_types), environment, arc, party_level)
    )
    conn.execute(
        "UPDATE campaign_sessions SET updated = datetime('now') WHERE id = ?", (session_id,)
    )
    conn.commit()
    conn.close()


def get_recent_types(session_id: int, limit: int = 5) -> list[str]:
    """Return creature types used in the last N encounters of a session."""
    import json as _json
    conn = get_conn()
    rows = conn.execute(
        """SELECT creature_types FROM session_encounters
           WHERE session_id = ? ORDER BY created DESC LIMIT ?""",
        (session_id, limit)
    ).fetchall()
    conn.close()
    types = []
    for row in rows:
        try:
            types.extend(_json.loads(row["creature_types"]))
        except Exception:
            pass
    return types


def get_session_history(session_id: int, limit: int = 20) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT id, hook, who, action, modifier, object,
                  creature_types, environment, arc, party_level, created
           FROM session_encounters
           WHERE session_id = ?
           ORDER BY created DESC LIMIT ?""",
        (session_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_adventures(limit=500):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, title, type, system FROM adventures ORDER BY title LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
