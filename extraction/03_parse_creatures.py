"""
03_parse_creatures.py — Creature Parser
Reads raw JSON files for bestiary/creature books,
extracts creature stat blocks, writes parsed/creatures.json.
"""

import json
import re
from pathlib import Path

RAW_DIR    = Path(__file__).parent / "raw"
PARSED_DIR = Path(__file__).parent / "parsed"

# Books that contain creatures — priority order (first occurrence wins on duplicates)
CREATURE_BOOKS = {
    "Pathfinder 2e - Monster Core.json":     "Monster Core",
    "Bestiary.json":                         "Bestiary",
    "Bestiary 2.json":                       "Bestiary 2",
    "Bestiary 3.json":                       "Bestiary 3",
    "Book of the Dead.json":                 "Book of the Dead",
    "Howl of the Wild.json":                 "Howl of the Wild",
    "Rage of Elements.json":                 "Rage of Elements",
    "Pathfinder 2e - War of Immortals.json": "War of Immortals",
    "Pathfinder 2e - NPC Core 1.json":       "NPC Core",
}

# Matches a creature block header: NAME line (may end in tab/backspace) then CREATURE N line
CREATURE_HEADER_RE = re.compile(
    r'\n([A-Z][A-Z ,\'\-\(\)\/0-9]+?)[ \t\x08]*\nCREATURE[ \t]+(-?\d+)\n',
)

# Trait classification
CREATURE_TYPES = {
    'ABERRATION', 'ANIMAL', 'BEAST', 'CELESTIAL', 'CONSTRUCT', 'DRAGON',
    'ELEMENTAL', 'FEY', 'FIEND', 'FUNGUS', 'GIANT', 'HUMANOID',
    'MONITOR', 'OOZE', 'PLANT', 'SPIRIT', 'UNDEAD',
}
SIZES = {'TINY', 'SMALL', 'MEDIUM', 'LARGE', 'HUGE', 'GARGANTUAN'}
RARITIES = {'COMMON', 'UNCOMMON', 'RARE', 'UNIQUE'}
ALIGNMENTS = {'LG', 'LN', 'LE', 'NG', 'N', 'NE', 'CG', 'CN', 'CE'}

TRAIT_RE = re.compile(r'^[A-Z][A-Z\-]+(?:\s+[A-Z][A-Z\-]+)*$')

# Known stat-line patterns
PERCEPTION_RE    = re.compile(r'^Perception\s+(.+)$', re.IGNORECASE)
LANGUAGES_RE     = re.compile(r'^Languages\s+(.+)$', re.IGNORECASE)
SKILLS_RE        = re.compile(r'^Skills\s+(.+)$', re.IGNORECASE)
ABILITY_SCORE_RE = re.compile(r'^Str\s+[+\-]\d')
ITEMS_RE         = re.compile(r'^Items\s+(.+)$', re.IGNORECASE)
AC_RE            = re.compile(r'^AC\s+(\d+)(.*)')
HP_RE            = re.compile(r'^HP\s+(\d+)(.*)')
SPEED_RE         = re.compile(r'^Speed\s+(.+)$', re.IGNORECASE)
ATTACK_RE        = re.compile(r'^(?:Melee|Ranged)\s+\[')


def parse_saves(rest_of_ac_line):
    """Extract Fort/Ref/Will from the text after 'AC N'."""
    m = re.search(r'Fort\s+([+\-]\d+),\s*Ref\s+([+\-]\d+),\s*Will\s+([+\-]\d+)', rest_of_ac_line)
    if m:
        return f"Fort {m.group(1)}, Ref {m.group(2)}, Will {m.group(3)}"
    return rest_of_ac_line.strip('; ').strip()


def parse_block(name_raw, level, block_text, source):
    creature = {
        'name':        name_raw.strip(),
        'level':       int(level),
        'size':        '',
        'type':        '',
        'traits':      [],
        'perception':  '',
        'languages':   '',
        'skills':      '',
        'ability_scores': '',
        'items':       '',
        'ac':          '',
        'saves':       '',
        'hp':          '',
        'immunities':  '',
        'weaknesses':  '',
        'resistances': '',
        'speed':       '',
        'attacks':     [],
        'abilities':   [],
        'source':      source,
    }

    lines = block_text.split('\n')

    # ── Phase 1: collect traits (ALL CAPS block at the start) ──────────────
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        # Accept trait if it matches the pattern OR is a known short alignment (N, CE, etc.)
        if TRAIT_RE.match(line) or line.upper() in ALIGNMENTS:
            upper = line.upper()
            if upper in SIZES:
                creature['size'] = upper.title()
            elif upper in CREATURE_TYPES:
                if not creature['type']:
                    creature['type'] = upper.title()
                else:
                    creature['traits'].append(line.title())
            elif upper in RARITIES or upper in ALIGNMENTS:
                creature['traits'].append(line)
            else:
                creature['traits'].append(line.title())
            i += 1
        else:
            break  # hit something that's not a trait

    # ── Phase 2: parse known stat lines (order varies, scan all remaining) ─
    while i < len(lines):
        line = lines[i].strip()
        i += 1

        if not line:
            continue

        m = PERCEPTION_RE.match(line)
        if m:
            creature['perception'] = m.group(1).strip()
            continue

        m = LANGUAGES_RE.match(line)
        if m:
            creature['languages'] = m.group(1).strip()
            continue

        m = SKILLS_RE.match(line)
        if m:
            val = m.group(1).strip()
            # Skills can wrap to next line — accumulate continuation lines
            while i < len(lines):
                nxt = lines[i].strip()
                if nxt and not any(nxt.startswith(p) for p in (
                    'Str ', 'AC ', 'HP ', 'Speed ', 'Perception ',
                    'Languages ', 'Items ', 'Melee ', 'Ranged ',
                )) and not TRAIT_RE.match(nxt) and not nxt[0].isupper():
                    val += ' ' + nxt
                    i += 1
                else:
                    break
            creature['skills'] = val
            continue

        if ABILITY_SCORE_RE.match(line):
            val = line
            while i < len(lines):
                nxt = lines[i].strip()
                if nxt and not any(nxt.startswith(p) for p in (
                    'AC ', 'HP ', 'Speed ', 'Items ', 'Melee ', 'Ranged ',
                )) and not TRAIT_RE.match(nxt) and re.match(r'^[+\-]?\d', nxt):
                    val += ' ' + nxt
                    i += 1
                else:
                    break
            creature['ability_scores'] = val
            continue

        m = ITEMS_RE.match(line)
        if m:
            creature['items'] = m.group(1).strip()
            continue

        m = AC_RE.match(line)
        if m:
            creature['ac']    = m.group(1)
            creature['saves'] = parse_saves(m.group(2))
            continue

        m = HP_RE.match(line)
        if m:
            creature['hp'] = m.group(1)
            rest = m.group(2).strip('; ')
            # Parse immunities, weaknesses, resistances from rest
            for chunk in rest.split(';'):
                chunk = chunk.strip()
                if chunk.lower().startswith('immunities'):
                    creature['immunities'] = chunk[len('Immunities'):].strip().lstrip()
                elif chunk.lower().startswith('weaknesses') or chunk.lower().startswith('weakness'):
                    creature['weaknesses'] = re.sub(r'^[Ww]eaknesses?\s*', '', chunk)
                elif chunk.lower().startswith('resistances') or chunk.lower().startswith('resistance'):
                    creature['resistances'] = re.sub(r'^[Rr]esistances?\s*', '', chunk)
            continue

        m = SPEED_RE.match(line)
        if m:
            creature['speed'] = m.group(1).strip()
            # Speed line is the last fixed stat line — everything after is attacks/abilities
            break

        # Everything that's not a recognized stat line is an ability (before Speed)
        creature['abilities'].append(line)

    # ── Phase 3: attacks and abilities after Speed ─────────────────────────
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line:
            continue
        if ATTACK_RE.match(line):
            creature['attacks'].append(line)
        else:
            creature['abilities'].append(line)

    # ── Finalize ───────────────────────────────────────────────────────────
    creature['traits']    = ', '.join(creature['traits'])
    creature['attacks']   = '\n'.join(creature['attacks'])
    creature['abilities'] = '\n'.join(creature['abilities'])

    return creature


def get_full_text(json_path):
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)
    return '\n' + '\n'.join(p['text'] for p in data['pages'])


def parse_book(json_filename, source_label):
    json_path = RAW_DIR / json_filename
    if not json_path.exists():
        print(f"  WARNING: {json_filename} not found, skipping.")
        return []

    print(f"  Parsing: {source_label}...")
    full_text = get_full_text(json_path)

    matches  = list(CREATURE_HEADER_RE.finditer(full_text))
    creatures = []

    for idx, match in enumerate(matches):
        name_raw  = match.group(1)
        level     = match.group(2)

        block_start = match.end()
        block_end   = matches[idx + 1].start() if idx + 1 < len(matches) else len(full_text)
        block_text  = full_text[block_start:block_end]

        c = parse_block(name_raw, level, block_text, source_label)
        creatures.append(c)

    print(f"    → {len(creatures)} entries found")
    return creatures


def main():
    PARSED_DIR.mkdir(exist_ok=True)

    all_creatures = []
    seen          = {}
    duplicates    = 0

    for json_file, label in CREATURE_BOOKS.items():
        book_creatures = parse_book(json_file, label)
        for c in book_creatures:
            key = c['name'].lower()
            if key in seen:
                duplicates += 1
            else:
                seen[key] = c['source']
                all_creatures.append(c)

    all_creatures.sort(key=lambda c: c['name'].lower())

    out_path = PARSED_DIR / 'creatures.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_creatures, f, ensure_ascii=False, indent=2)

    print(f"\n=== Creature parsing complete ===")
    print(f"  Total unique creatures : {len(all_creatures)}")
    print(f"  Duplicates skipped     : {duplicates}")
    print(f"\nWritten to: {out_path}")


if __name__ == "__main__":
    main()
