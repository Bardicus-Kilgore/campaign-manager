"""
05_add_translations.py — Import French translations from pf2_reference markdown files.

Adds desc_fr column to spells, feats, and items tables.
Matches by name (case-insensitive). Skips blanks ("—").
"""

import re
import sqlite3
from pathlib import Path

DB_PATH     = Path(__file__).parent.parent / "pf2e.db"
FR_DIR      = Path("/home/foutchi/projects/PATHFINDER/pf2_reference")

SOURCES = {
    "spells": [
        (FR_DIR / "fr_pf2_spells.md", 0, 2),       # col 0 = name, col 2 = desc
    ],
    "feats": [
        (FR_DIR / "fr_pf2_feats_general.md", 0, 3), # col 0 = name, col 3 = résumé
    ],
    "items": [
        (FR_DIR / "fr_pf2_armor.md",   0, 9),        # col 0 = name, col 9 = desc
        (FR_DIR / "fr_pf2_weapons.md", 0, 6),        # col 0 = name, col 6 = desc
    ],
}


def parse_md_table(path: Path, name_col: int, desc_col: int) -> dict[str, str]:
    """Parse a markdown table, return {UPPERCASE_NAME: french_desc}."""
    results = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        # Only table data rows (start with |, not separator rows)
        if not line.startswith("|"):
            continue
        if re.match(r"^\|[\s\-|]+\|$", line):
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) <= max(name_col, desc_col):
            continue
        name = cols[name_col].strip("* ")
        desc = cols[desc_col].strip()
        if not name or name.lower() in ("nom", "don", "—"):
            continue
        if desc == "—":
            desc = ""
        results[name.upper()] = desc
    return results


def add_column_if_missing(con, table, col):
    existing = [c[1] for c in con.execute(f"PRAGMA table_info({table})").fetchall()]
    if col not in existing:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT DEFAULT ''")
        print(f"  Added column '{col}' to {table}")


def apply_translations(con, table, translations: dict[str, str]):
    matched = 0
    skipped = 0
    for name_upper, desc_fr in translations.items():
        if not desc_fr:
            skipped += 1
            continue
        cur = con.execute(
            f"UPDATE {table} SET desc_fr = ? WHERE UPPER(name) = ?",
            (desc_fr, name_upper)
        )
        if cur.rowcount > 0:
            matched += 1
    return matched, skipped


def main():
    con = sqlite3.connect(DB_PATH)

    for table, sources in SOURCES.items():
        print(f"\n=== {table} ===")
        add_column_if_missing(con, table, "desc_fr")

        all_translations = {}
        for path, name_col, desc_col in sources:
            parsed = parse_md_table(path, name_col, desc_col)
            print(f"  Parsed {len(parsed)} entries from {path.name}")
            all_translations.update(parsed)

        matched, skipped = apply_translations(con, table, all_translations)
        total = len(all_translations)
        print(f"  Matched: {matched} / {total}  (skipped {skipped} blanks)")

    con.commit()
    con.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
