"""
database.py — SQLite helpers for pf2e-baudot.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "pf2e.db"


def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


# ── Spells ────────────────────────────────────────────────────────────────────

def search_spells(q="", level=None, tradition=None, spell_type=None, limit=100):
    con = get_db()
    params = []
    clauses = []

    if q:
        clauses.append("""
            id IN (
                SELECT rowid FROM spells_fts
                WHERE spells_fts MATCH ?
            )
        """)
        params.append(q + "*")
    if level is not None:
        clauses.append("level = ?")
        params.append(int(level))
    if tradition:
        clauses.append("traditions LIKE ?")
        params.append(f"%{tradition}%")
    if spell_type:
        clauses.append("type = ?")
        params.append(spell_type)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM spells {where} ORDER BY level, name LIMIT ?"
    params.append(limit)

    rows = con.execute(sql, params).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_spell(spell_id):
    con = get_db()
    row = con.execute("SELECT * FROM spells WHERE id = ?", (spell_id,)).fetchone()
    con.close()
    return dict(row) if row else None


# ── Creatures ─────────────────────────────────────────────────────────────────

def search_creatures(q="", level=None, creature_type=None, limit=100):
    con = get_db()
    params = []
    clauses = []

    if q:
        clauses.append("""
            id IN (
                SELECT rowid FROM creatures_fts
                WHERE creatures_fts MATCH ?
            )
        """)
        params.append(q + "*")
    if level is not None:
        clauses.append("level = ?")
        params.append(int(level))
    if creature_type:
        clauses.append("type = ?")
        params.append(creature_type)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM creatures {where} ORDER BY level, name LIMIT ?"
    params.append(limit)

    rows = con.execute(sql, params).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_creature(creature_id):
    con = get_db()
    row = con.execute("SELECT * FROM creatures WHERE id = ?", (creature_id,)).fetchone()
    con.close()
    return dict(row) if row else None


# ── Feats ─────────────────────────────────────────────────────────────────────

def search_feats(q="", level=None, feat_class=None, limit=100):
    con = get_db()
    params = []
    clauses = []

    if q:
        clauses.append("""
            id IN (
                SELECT rowid FROM feats_fts
                WHERE feats_fts MATCH ?
            )
        """)
        params.append(q + "*")
    if level is not None:
        clauses.append("level = ?")
        params.append(int(level))
    if feat_class:
        clauses.append("class LIKE ?")
        params.append(f"%{feat_class}%")

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM feats {where} ORDER BY level, name LIMIT ?"
    params.append(limit)

    rows = con.execute(sql, params).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_feat(feat_id):
    con = get_db()
    row = con.execute("SELECT * FROM feats WHERE id = ?", (feat_id,)).fetchone()
    con.close()
    return dict(row) if row else None


# ── Items ─────────────────────────────────────────────────────────────────────

def search_items(q="", level=None, limit=100):
    con = get_db()
    params = []
    clauses = []

    if q:
        clauses.append("""
            id IN (
                SELECT rowid FROM items_fts
                WHERE items_fts MATCH ?
            )
        """)
        params.append(q + "*")
    if level is not None:
        clauses.append("level = ?")
        params.append(int(level))

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM items {where} ORDER BY level, name LIMIT ?"
    params.append(limit)

    rows = con.execute(sql, params).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_item(item_id):
    con = get_db()
    row = con.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    con.close()
    return dict(row) if row else None


# ── Conditions ────────────────────────────────────────────────────────────────

def get_all_conditions():
    con = get_db()
    rows = con.execute("SELECT * FROM conditions ORDER BY name").fetchall()
    con.close()
    return [dict(r) for r in rows]


# ── Stats ─────────────────────────────────────────────────────────────────────

def get_stats():
    con = get_db()
    stats = {}
    for table in ("spells", "creatures", "feats", "conditions", "items"):
        stats[table] = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    con.close()
    return stats
