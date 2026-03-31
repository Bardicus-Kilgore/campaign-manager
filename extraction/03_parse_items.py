"""
03_parse_items.py — Magic Item Parser
Reads raw JSON files, extracts item stat blocks,
writes parsed/items.json.
"""

import json
import re
from pathlib import Path

RAW_DIR    = Path(__file__).parent / "raw"
PARSED_DIR = Path(__file__).parent / "parsed"

# Books with items — priority order
ITEM_BOOKS = {
    "Treasure Vault (Remastered).json":          "Treasure Vault",
    "Pathfinder 2e - Player Core Remaster.json": "Player Core",
    "Pathfinder 2e - Player Core 2.json":        "Player Core 2",
    "Secrets of Magic.json":                     "Secrets of Magic",
    "Dark Archive.json":                         "Dark Archive",
    "Pathfinder 2e - Guns & Gears Remastered.json": "Guns & Gears",
    "Pathfinder 2e - War of Immortals.json":     "War of Immortals",
    "Howl of the Wild.json":                     "Howl of the Wild",
    "Rage of Elements.json":                     "Rage of Elements",
    "Book of the Dead.json":                     "Book of the Dead",
    "Lost Omens #02 - Character Guide.json":     "LO: Character Guide",
    "Lost Omens #06 - Ancestry Guide.json":      "LO: Ancestry Guide",
    "Lost Omens #08 - The Grand Bazaar.JSON":    "LO: Grand Bazaar",
    "Lost Omens #13 - Impossible Lands.json":    "LO: Impossible Lands",
    "Lost Omens #16 - Tian Xia World Guide.json":"LO: Tian Xia World",
    "Lost Omens #18 - Divine Mysteries.json":    "LO: Divine Mysteries",
}

# Item block header: NAME then ITEM N (or ITEM N+)
ITEM_HEADER_RE = re.compile(
    r'\n([A-Z][A-Z ,\'\-\(\)\/0-9]+?)[ \t\x08]*(\[[\w\- ]+\])?[ \t]*\nITEM[ \t]+(\d+)(\+)?\n',
)

TRAIT_RE = re.compile(r'^[A-Z][A-Z\-]+(?:\s+[A-Z][A-Z\-]+)*$')

STAT_PREFIXES = ['Price', 'Usage', 'Bulk', 'Activate', 'Craft Requirements', 'Access']


def parse_stat_line(line, item):
    """Parse Price / Usage / Bulk from a stat line (may share a line with ;)."""
    chunks = [c.strip() for c in line.split(';') if c.strip()]
    for chunk in chunks:
        if chunk.startswith('Price '):
            item['price'] = chunk[6:].strip()
        elif chunk.startswith('Usage '):
            item['usage'] = chunk[6:].strip()
        elif chunk.startswith('Bulk '):
            item['bulk'] = chunk[5:].strip()
        elif chunk == 'Bulk':
            item['bulk'] = '—'


def parse_block(name_raw, action_raw, level, level_variable, block_text, source):
    item = {
        'name':          name_raw.strip(),
        'level':         int(level),
        'level_variable': level_variable == '+',   # True for "ITEM 5+"
        'action_cost':   '',
        'traits':        [],
        'price':         '',
        'usage':         '',
        'bulk':          '',
        'description':   '',
        'source':        source,
    }

    lines      = block_text.split('\n')
    desc_lines = []
    past_stats = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if past_stats:
                desc_lines.append('')
            continue

        # Traits
        if not past_stats and TRAIT_RE.match(stripped) and len(stripped.split()) <= 4:
            item['traits'].append(stripped)
            continue

        # Stat fields
        if not past_stats:
            is_stat = False
            for prefix in STAT_PREFIXES:
                if stripped.startswith(prefix + ' ') or stripped == prefix:
                    is_stat = True
                    break

            if is_stat:
                parse_stat_line(stripped, item)
                continue

        # Description
        past_stats = True
        desc_lines.append(stripped)

    # Collapse description
    parts   = []
    current = []
    for dl in desc_lines:
        if dl == '':
            if current:
                parts.append(' '.join(current))
                current = []
        else:
            current.append(dl)
    if current:
        parts.append(' '.join(current))

    item['description'] = '\n\n'.join(parts).strip()
    item['traits']      = ', '.join(item['traits'])
    return item


def get_full_text(json_path):
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)
    return '\n' + '\n'.join(p['text'] for p in data['pages'])


def parse_book(json_filename, source_label):
    json_path = RAW_DIR / json_filename
    if not json_path.exists():
        return []

    full_text = get_full_text(json_path)
    matches   = list(ITEM_HEADER_RE.finditer(full_text))
    items     = []

    for i, match in enumerate(matches):
        name_raw       = match.group(1)
        action_raw     = match.group(2) or ''
        level          = match.group(3)
        level_variable = match.group(4) or ''

        block_start = match.end()
        block_end   = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        block_text  = full_text[block_start:block_end]

        it = parse_block(name_raw, action_raw, level, level_variable, block_text, source_label)
        items.append(it)

    return items


def main():
    PARSED_DIR.mkdir(exist_ok=True)

    all_items  = []
    seen       = {}
    duplicates = 0

    for json_file, label in ITEM_BOOKS.items():
        json_path = RAW_DIR / json_file
        if not json_path.exists():
            continue
        items = parse_book(json_file, label)
        print(f"  {label}: {len(items)} items")

        for it in items:
            key = it['name'].lower()
            if key in seen:
                duplicates += 1
            else:
                seen[key] = it['source']
                all_items.append(it)

    all_items.sort(key=lambda i: i['name'].lower())

    out_path = PARSED_DIR / 'items.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)

    print(f"\n=== Item parsing complete ===")
    print(f"  Total unique items : {len(all_items)}")
    print(f"  Duplicates skipped : {duplicates}")
    print(f"\nWritten to: {out_path}")


if __name__ == "__main__":
    main()
