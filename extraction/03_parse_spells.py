"""
03_parse_spells.py — Spell Parser
Reads raw JSON files for spell-containing books,
extracts spell and focus spell stat blocks,
writes parsed/spells.json.
"""

import json
import re
from pathlib import Path

RAW_DIR    = Path(__file__).parent / "raw"
PARSED_DIR = Path(__file__).parent / "parsed"

# Books that contain spells — in priority order (first occurrence wins on duplicates)
SPELL_BOOKS = {
    "Pathfinder 2e - Player Core Remaster.json": "Player Core",
    "Pathfinder 2e - Player Core 2.json":        "Player Core 2",
    "Secrets of Magic.json":                     "Secrets of Magic",
    "Dark Archive.json":                         "Dark Archive",
    "Book of the Dead.json":                     "Book of the Dead",
    "Howl of the Wild.json":                     "Howl of the Wild",
    "Rage of Elements.json":                     "Rage of Elements",
    "Pathfinder 2e - War of Immortals.json":     "War of Immortals",
}

# Matches a spell/focus block header:
#   LINE 1: SPELL NAME (possibly with [action cost]) + optional whitespace
#   LINE 2: SPELL N  or  FOCUS N
SPELL_HEADER_RE = re.compile(
    r'\n([A-Z][A-Z ,\'\-\(\)\/0-9]+?)[ \t]*(\[[\w\- ]+\])?[ \t]*\n(SPELL|FOCUS)[ \t]+(\d+)\n',
)

# Traits are ALL-CAPS-only lines (single or a few words, no lowercase)
TRAIT_RE = re.compile(r'^[A-Z][A-Z\-]+(?:\s+[A-Z][A-Z\-]+)*$')

# Known stat-field prefixes (order matters — longer first to avoid partial matches)
STAT_PREFIXES = [
    'Traditions', 'Cast', 'Requirements', 'Trigger',
    'Range', 'Area', 'Targets', 'Duration', 'Defense',
]


def parse_action(raw):
    """Convert [two-actions] → '2', [reaction] → 'reaction', etc.
    Also handles old-format Cast lines like '[two-actions] somatic, verbal'."""
    if not raw:
        return ""
    mapping = {
        'one-action':    '1',
        'two-actions':   '2',
        'three-actions': '3',
        'reaction':      'reaction',
        'free-action':   'free',
    }
    # Find all [action] tokens anywhere in the string (handles old Cast format)
    tokens = re.findall(r'\[([\w\-]+)\]', raw)
    if tokens:
        results = [mapping[t.lower()] for t in tokens if t.lower() in mapping]
        if results:
            return ' to '.join(results)
    # Fallback: strip brackets and try direct lookup
    inner = raw.strip().strip('[]')
    return mapping.get(inner.lower(), "")


def parse_stat_line(line, spell):
    """
    Parse a stat-block line (may contain multiple fields separated by ;).
    Updates spell dict in place. Returns True if it matched anything.
    """
    # Split on semicolons to get individual field chunks
    chunks = [c.strip() for c in line.split(';') if c.strip()]
    matched = False

    for chunk in chunks:
        for prefix in STAT_PREFIXES:
            if chunk.startswith(prefix + ' ') or chunk == prefix:
                value = chunk[len(prefix):].strip()
                if prefix == 'Traditions':
                    spell['traditions'] = value
                elif prefix == 'Cast':
                    spell['cast'] = value
                elif prefix == 'Range':
                    spell['range'] = value
                elif prefix == 'Area':
                    spell['area'] = value
                elif prefix == 'Targets':
                    spell['targets'] = value
                elif prefix == 'Duration':
                    spell['duration'] = value
                elif prefix == 'Defense':
                    spell['defense'] = value
                elif prefix == 'Trigger':
                    spell['trigger'] = value
                elif prefix == 'Requirements':
                    spell['requirements'] = value
                matched = True
                break  # found prefix for this chunk

    return matched


def parse_block(name_raw, action_raw, spell_type, level, block_text, source):
    """Parse a single spell block into a structured dict."""
    spell = {
        'name':         name_raw.strip(),
        'level':        int(level),
        'type':         spell_type.lower(),   # 'spell' or 'focus'
        'action_cost':  parse_action(action_raw),
        'traits':       [],
        'traditions':   '',
        'cast':         '',
        'range':        '',
        'area':         '',
        'targets':      '',
        'duration':     '',
        'defense':      '',
        'trigger':      '',
        'requirements': '',
        'description':  '',
        'source':       source,
    }

    lines = block_text.split('\n')
    desc_lines = []
    past_stats   = False   # once we start description, stop trying to parse stat fields
    last_stat    = None    # last stat key we wrote to (for multi-line continuation)
    stat_key_map = {
        'Traditions': 'traditions', 'Cast': 'cast', 'Range': 'range',
        'Area': 'area', 'Targets': 'targets', 'Duration': 'duration',
        'Defense': 'defense', 'Trigger': 'trigger', 'Requirements': 'requirements',
    }

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if past_stats:
                desc_lines.append('')
            else:
                last_stat = None  # blank line ends stat continuation
            continue

        # ── Traits: ALL CAPS, short, before any stat line ─────────────────
        if not past_stats and last_stat is None and TRAIT_RE.match(stripped):
            word_count = len(stripped.split())
            if word_count <= 3 and stripped not in ('SPELLS', 'FOCUS SPELLS', 'RITUALS'):
                spell['traits'].append(stripped)
                continue

        # ── Stat fields ────────────────────────────────────────────────────
        if not past_stats:
            matched_prefix = None
            for prefix in STAT_PREFIXES:
                if stripped.startswith(prefix + ' ') or stripped == prefix:
                    matched_prefix = prefix
                    break

            if matched_prefix:
                parse_stat_line(stripped, spell)
                # Only continue Trigger/Requirements across lines — other fields are always short
                if matched_prefix in ('Trigger', 'Requirements'):
                    val = spell.get(stat_key_map.get(matched_prefix, ''), '')
                    last_stat = matched_prefix if val and not val.endswith('.') else None
                else:
                    last_stat = None
                continue

            # Not a known stat prefix — might be continuation of previous stat
            if last_stat is not None:
                key = stat_key_map.get(last_stat, '')
                if key and spell[key]:
                    spell[key] += ' ' + stripped
                    # Check if now complete
                    if stripped.endswith('.') or stripped.endswith('?') or stripped.endswith('!'):
                        last_stat = None
                    continue
                else:
                    last_stat = None

        # ── Description ────────────────────────────────────────────────────
        past_stats = True
        last_stat  = None
        desc_lines.append(stripped)

    # Clean up description: collapse multi-space, join with spaces
    # but preserve paragraph breaks (empty lines → double newline)
    desc_parts = []
    current = []
    for dl in desc_lines:
        if dl == '':
            if current:
                desc_parts.append(' '.join(current))
                current = []
        else:
            current.append(dl)
    if current:
        desc_parts.append(' '.join(current))

    spell['description'] = '\n\n'.join(desc_parts).strip()
    spell['traits']      = ', '.join(spell['traits'])

    # If action_cost wasn't in the header, derive it from Cast line
    if not spell['action_cost'] and spell['cast']:
        parsed = parse_action(spell['cast'])
        # If parse_action found a known action word, use it; otherwise keep the cast string directly
        spell['action_cost'] = parsed if parsed else spell['cast']

    return spell


def get_full_text(json_path):
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)
    # Prepend a newline so the first entry's regex can match
    return '\n' + '\n'.join(p['text'] for p in data['pages'])


def parse_book(json_filename, source_label):
    json_path = RAW_DIR / json_filename
    if not json_path.exists():
        print(f"  WARNING: {json_filename} not found, skipping.")
        return []

    print(f"  Parsing: {source_label}...")
    full_text = get_full_text(json_path)

    matches = list(SPELL_HEADER_RE.finditer(full_text))
    spells  = []

    for i, match in enumerate(matches):
        name_raw   = match.group(1)
        action_raw = match.group(2) or ''
        spell_type = match.group(3)
        level      = match.group(4)

        block_start = match.end()
        block_end   = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        block_text  = full_text[block_start:block_end]

        spell = parse_block(name_raw, action_raw, spell_type, level, block_text, source_label)
        spells.append(spell)

    print(f"    → {len(spells)} entries found")
    return spells


def main():
    PARSED_DIR.mkdir(exist_ok=True)

    all_spells = []
    seen       = {}    # name_lower → source (for duplicate tracking)
    duplicates = 0

    for json_file, label in SPELL_BOOKS.items():
        book_spells = parse_book(json_file, label)

        for spell in book_spells:
            key = spell['name'].lower()
            if key in seen:
                duplicates += 1
            else:
                seen[key] = spell['source']
                all_spells.append(spell)

    # Sort alphabetically by name
    all_spells.sort(key=lambda s: s['name'].lower())

    out_path = PARSED_DIR / 'spells.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_spells, f, ensure_ascii=False, indent=2)

    print(f"\n=== Spell parsing complete ===")
    print(f"  Total unique spells : {len(all_spells)}")
    print(f"  Duplicates skipped  : {duplicates}")
    print(f"\nWritten to: {out_path}")
    print("Spot-check a few entries in parsed/spells.json, then move to the next parser.")


if __name__ == "__main__":
    main()
