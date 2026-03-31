"""
04_build_db.py — Build SQLite Database
Reads all parsed JSON files and loads them into pf2e.db.
Run after all 03_parse_*.py scripts are complete.
"""

import json
import sqlite3
from pathlib import Path

PARSED_DIR = Path(__file__).parent / "parsed"
DB_PATH    = Path(__file__).parent.parent / "pf2e.db"


def connect(db_path):
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def create_schema(con):
    con.executescript("""
        DROP TABLE IF EXISTS spells;
        DROP TABLE IF EXISTS creatures;
        DROP TABLE IF EXISTS feats;
        DROP TABLE IF EXISTS conditions;
        DROP TABLE IF EXISTS items;

        CREATE TABLE spells (
            id          INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            level       INTEGER,
            type        TEXT,          -- 'spell' or 'focus'
            action_cost TEXT,
            traits      TEXT,
            traditions  TEXT,
            cast        TEXT,
            range       TEXT,
            area        TEXT,
            targets     TEXT,
            duration    TEXT,
            defense     TEXT,
            trigger     TEXT,
            requirements TEXT,
            description TEXT,
            source      TEXT
        );

        CREATE TABLE creatures (
            id            INTEGER PRIMARY KEY,
            name          TEXT NOT NULL,
            level         INTEGER,
            size          TEXT,
            type          TEXT,
            traits        TEXT,
            perception    TEXT,
            languages     TEXT,
            skills        TEXT,
            ability_scores TEXT,
            items         TEXT,
            ac            TEXT,
            saves         TEXT,
            hp            TEXT,
            immunities    TEXT,
            weaknesses    TEXT,
            resistances   TEXT,
            speed         TEXT,
            attacks       TEXT,
            abilities     TEXT,
            source        TEXT
        );

        CREATE TABLE feats (
            id           INTEGER PRIMARY KEY,
            name         TEXT NOT NULL,
            level        INTEGER,
            action_cost  TEXT,
            traits       TEXT,
            class        TEXT,
            prerequisites TEXT,
            frequency    TEXT,
            trigger      TEXT,
            requirements TEXT,
            access       TEXT,
            description  TEXT,
            source       TEXT
        );

        CREATE TABLE conditions (
            id          INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            has_value   INTEGER,       -- 1 if condition takes a numeric value
            description TEXT,
            source      TEXT
        );

        CREATE TABLE items (
            id             INTEGER PRIMARY KEY,
            name           TEXT NOT NULL,
            level          INTEGER,
            level_variable INTEGER,   -- 1 if 'ITEM N+'
            action_cost    TEXT,
            traits         TEXT,
            price          TEXT,
            usage          TEXT,
            bulk           TEXT,
            description    TEXT,
            source         TEXT
        );

        -- Full-text search indexes
        CREATE VIRTUAL TABLE spells_fts USING fts5(
            name, traits, traditions, description,
            content='spells', content_rowid='id'
        );
        CREATE VIRTUAL TABLE creatures_fts USING fts5(
            name, type, traits, abilities, attacks,
            content='creatures', content_rowid='id'
        );
        CREATE VIRTUAL TABLE feats_fts USING fts5(
            name, class, traits, prerequisites, description,
            content='feats', content_rowid='id'
        );
        CREATE VIRTUAL TABLE items_fts USING fts5(
            name, traits, description,
            content='items', content_rowid='id'
        );
    """)
    con.commit()


def load_spells(con):
    path = PARSED_DIR / "spells.json"
    with open(path) as f:
        data = json.load(f)

    rows = [(
        s['name'], s['level'], s['type'], s['action_cost'],
        s['traits'], s['traditions'], s['cast'], s['range'],
        s['area'], s['targets'], s['duration'], s['defense'],
        s['trigger'], s['requirements'], s['description'], s['source'],
    ) for s in data]

    con.executemany("""
        INSERT INTO spells
        (name, level, type, action_cost, traits, traditions, cast, range,
         area, targets, duration, defense, trigger, requirements, description, source)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, rows)
    con.commit()

    # Populate FTS
    con.execute("INSERT INTO spells_fts(spells_fts) VALUES('rebuild')")
    con.commit()
    return len(rows)


def load_creatures(con):
    path = PARSED_DIR / "creatures.json"
    with open(path) as f:
        data = json.load(f)

    rows = [(
        c['name'], c['level'], c['size'], c['type'], c['traits'],
        c['perception'], c['languages'], c['skills'], c['ability_scores'],
        c['items'], c['ac'], c['saves'], c['hp'],
        c['immunities'], c['weaknesses'], c['resistances'],
        c['speed'], c['attacks'], c['abilities'], c['source'],
    ) for c in data]

    con.executemany("""
        INSERT INTO creatures
        (name, level, size, type, traits, perception, languages, skills,
         ability_scores, items, ac, saves, hp, immunities, weaknesses,
         resistances, speed, attacks, abilities, source)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, rows)
    con.commit()

    con.execute("INSERT INTO creatures_fts(creatures_fts) VALUES('rebuild')")
    con.commit()
    return len(rows)


def load_feats(con):
    path = PARSED_DIR / "feats.json"
    with open(path) as f:
        data = json.load(f)

    rows = [(
        f['name'], f['level'], f['action_cost'], f['traits'],
        f['class'], f['prerequisites'], f['frequency'], f['trigger'],
        f['requirements'], f['access'], f['description'], f['source'],
    ) for f in data]

    con.executemany("""
        INSERT INTO feats
        (name, level, action_cost, traits, class, prerequisites, frequency,
         trigger, requirements, access, description, source)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, rows)
    con.commit()

    con.execute("INSERT INTO feats_fts(feats_fts) VALUES('rebuild')")
    con.commit()
    return len(rows)


def load_conditions(con):
    path = PARSED_DIR / "conditions.json"
    with open(path) as f:
        data = json.load(f)

    rows = [(
        c['name'], 1 if c['has_value'] else 0, c['description'], c['source'],
    ) for c in data]

    con.executemany("""
        INSERT INTO conditions (name, has_value, description, source)
        VALUES (?,?,?,?)
    """, rows)
    con.commit()
    return len(rows)


def load_items(con):
    path = PARSED_DIR / "items.json"
    with open(path) as f:
        data = json.load(f)

    rows = [(
        i['name'], i['level'], 1 if i['level_variable'] else 0,
        i['action_cost'], i['traits'], i['price'],
        i['usage'], i['bulk'], i['description'], i['source'],
    ) for i in data]

    con.executemany("""
        INSERT INTO items
        (name, level, level_variable, action_cost, traits, price,
         usage, bulk, description, source)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, rows)
    con.commit()

    con.execute("INSERT INTO items_fts(items_fts) VALUES('rebuild')")
    con.commit()
    return len(rows)


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"Removed existing {DB_PATH.name}")

    print(f"Building {DB_PATH} ...")
    con = connect(DB_PATH)

    create_schema(con)
    print("  Schema created.")

    n = load_spells(con);     print(f"  Spells loaded     : {n}")
    n = load_creatures(con);  print(f"  Creatures loaded  : {n}")
    n = load_feats(con);      print(f"  Feats loaded      : {n}")
    n = load_conditions(con); print(f"  Conditions loaded : {n}")
    n = load_items(con);      print(f"  Items loaded      : {n}")

    # Quick sanity check
    print("\n  Sanity checks:")
    for table in ('spells', 'creatures', 'feats', 'conditions', 'items'):
        row = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        print(f"    {table}: {row[0]} rows")

    # Test FTS
    row = con.execute("""
        SELECT s.name, s.level FROM spells s
        JOIN spells_fts ON spells_fts.rowid = s.id
        WHERE spells_fts MATCH 'fireball'
    """).fetchone()
    print(f"\n  FTS test — 'fireball': {row}")

    con.close()
    size_kb = DB_PATH.stat().st_size // 1024
    print(f"\nDone. Database size: {size_kb} KB")
    print(f"Path: {DB_PATH}")


if __name__ == "__main__":
    main()
