"""
05b_translations_from_pg.py — Pull full French descriptions from PostgreSQL backup.

Queries the pf2_temp Docker container (must be running with backup restored).
Updates desc_fr in pf2e.db with full, untruncated text.
Also cleans @UUID[...] and @Damage[...] Foundry tags.
"""

import re
import json
import sqlite3
import subprocess
from pathlib import Path

DB_PATH    = Path(__file__).parent.parent / "pf2e.db"
DOCKER_CMD = ["docker", "exec", "pf2_temp", "psql", "-U", "postgres", "-d", "pathfinder", "-t", "-A"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def pg_query(sql):
    result = subprocess.run(DOCKER_CMD + ["-c", sql],
                            capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    out = result.stdout.strip()
    if not out or out == "null":
        return []
    return json.loads(out)


def clean_fr(text):
    if not text:
        return ""
    # Remove @UUID[...] Foundry references — keep just the display name if present
    # e.g. @UUID[Compendium.pf2e.conditionitems.Item.Blinded]{Aveuglé} → Aveuglé
    text = re.sub(r'@UUID\[[^\]]+\]\{([^}]+)\}', r'\1', text)
    # Remove bare @UUID[...] with no label
    text = re.sub(r'@UUID\[[^\]]+\]', '', text)
    # Remove @Damage[...] expressions
    text = re.sub(r'@Damage\[[^\]]+\]', '', text)
    # Remove @Check[...] expressions
    text = re.sub(r'@Check\[[^\]]+\]', '', text)
    # Remove @Template[...] expressions
    text = re.sub(r'@Template\[[^\]]+\]', '', text)
    # Remove remaining @ tags
    text = re.sub(r'@\w+\[[^\]]*\]', '', text)
    # Clean up extra whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ── Pull from PostgreSQL ──────────────────────────────────────────────────────

def fetch_spells():
    print("  Fetching spells...")
    rows = pg_query(
        "SELECT json_agg(json_build_object('name', name, 'desc_fr', "
        "COALESCE(description_fr_clean, description_fr))) "
        "FROM spells WHERE COALESCE(description_fr_clean, description_fr) IS NOT NULL "
        "AND LENGTH(COALESCE(description_fr_clean, description_fr, '')) > 10;"
    )
    return {r["name"].upper(): clean_fr(r["desc_fr"]) for r in rows if r.get("name")}


def fetch_feats():
    print("  Fetching feats...")
    rows = pg_query(
        "SELECT json_agg(json_build_object('name', name, 'desc_fr', "
        "COALESCE(description_fr_clean, description_fr))) "
        "FROM feats WHERE COALESCE(description_fr_clean, description_fr) IS NOT NULL "
        "AND LENGTH(COALESCE(description_fr_clean, description_fr, '')) > 10;"
    )
    return {r["name"].upper(): clean_fr(r["desc_fr"]) for r in rows if r.get("name")}


def fetch_items():
    print("  Fetching equipment...")
    rows = pg_query(
        "SELECT json_agg(json_build_object('name', name, 'desc_fr', "
        "COALESCE(description_fr_clean, description_fr))) "
        "FROM equipment WHERE COALESCE(description_fr_clean, description_fr) IS NOT NULL "
        "AND LENGTH(COALESCE(description_fr_clean, description_fr, '')) > 10;"
    )
    return {r["name"].upper(): clean_fr(r["desc_fr"]) for r in rows if r.get("name")}


# ── Apply to SQLite ───────────────────────────────────────────────────────────

def apply(con, table, translations):
    matched = 0
    for name_upper, desc_fr in translations.items():
        if not desc_fr:
            continue
        cur = con.execute(
            f"UPDATE {table} SET desc_fr = ? WHERE UPPER(name) = ?",
            (desc_fr, name_upper)
        )
        if cur.rowcount > 0:
            matched += 1
    total_with_fr = con.execute(f"SELECT COUNT(*) FROM {table} WHERE desc_fr != ''").fetchone()[0]
    total = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  {table}: updated {matched} rows → {total_with_fr}/{total} now have FR")


# ── Also clean existing desc_fr that still have @UUID tags ───────────────────

def clean_existing(con, table):
    rows = con.execute(f"SELECT id, desc_fr FROM {table} WHERE desc_fr LIKE '%@%'").fetchall()
    count = 0
    for row in rows:
        cleaned = clean_fr(row[1])
        if cleaned != row[1]:
            con.execute(f"UPDATE {table} SET desc_fr = ? WHERE id = ?", (cleaned, row[0]))
            count += 1
    if count:
        print(f"  Cleaned @-tags in {count} existing {table} rows")


def main():
    print("Pulling full French translations from PostgreSQL...")
    spells = fetch_spells()
    feats  = fetch_feats()
    items  = fetch_items()
    print(f"  Got: {len(spells)} spells, {len(feats)} feats, {len(items)} items")
    print()

    con = sqlite3.connect(DB_PATH)
    print("Applying to pf2e.db...")
    apply(con, "spells", spells)
    apply(con, "feats",  feats)
    apply(con, "items",  items)
    print()
    print("Cleaning leftover @-tags...")
    clean_existing(con, "spells")
    clean_existing(con, "feats")
    clean_existing(con, "items")

    con.commit()
    con.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
