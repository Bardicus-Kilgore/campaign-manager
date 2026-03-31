"""
03_parse_feats.py — Feat Parser
Reads raw JSON files, extracts feat stat blocks,
writes parsed/feats.json.
Feats appear in almost every book — all books are scanned.
"""

import json
import re
from pathlib import Path

RAW_DIR    = Path(__file__).parent / "raw"
PARSED_DIR = Path(__file__).parent / "parsed"

# All books, in priority order (first occurrence wins on duplicates)
ALL_BOOKS = {
    "Pathfinder 2e - Player Core Remaster.json": "Player Core",
    "Pathfinder 2e - Player Core 2.json":        "Player Core 2",
    "Pathfinder 2e - GM Core Remaster.json":     "GM Core",
    "Pathfinder 2e - Guns & Gears Remastered.json": "Guns & Gears",
    "Dark Archive.json":                         "Dark Archive",
    "Secrets of Magic.json":                     "Secrets of Magic",
    "Pathfinder 2e - War of Immortals.json":     "War of Immortals",
    "Howl of the Wild.json":                     "Howl of the Wild",
    "Rage of Elements.json":                     "Rage of Elements",
    "Book of the Dead.json":                     "Book of the Dead",
    "Lost Omens #01 - World Guide.json":         "LO: World Guide",
    "Lost Omens #02 - Character Guide.json":     "LO: Character Guide",
    "Lost Omens #03 - Gods & Magic.json":        "LO: Gods & Magic",
    "Lost Omens #05 - Pathfinder Society Guide.json": "LO: PFS Guide",
    "Lost Omens #06 - Ancestry Guide.json":      "LO: Ancestry Guide",
    "Lost Omens #07 - The Mwangi Expanse.json":  "LO: Mwangi Expanse",
    "Lost Omens #08 - The Grand Bazaar.JSON":    "LO: Grand Bazaar",
    "Lost Omens #09 - Absalom, City of Lost Omens.json": "LO: Absalom",
    "Lost Omens #10 - Monsters Of Myth.json":    "LO: Monsters of Myth",
    "Lost Omens #11 - Knights of Lastwall.json": "LO: Knights of Lastwall",
    "Lost Omens #12 - Travel Guide.json":        "LO: Travel Guide",
    "Lost Omens #13 - Impossible Lands.json":    "LO: Impossible Lands",
    "Lost Omens #14 - Firebrands.json":          "LO: Firebrands",
    "Lost Omens #15 - Highhelm.json":            "LO: Highhelm",
    "Lost Omens #16 - Tian Xia World Guide.json":"LO: Tian Xia World",
    "Lost Omens #17 - Tian Xia Character Guide.json": "LO: Tian Xia Char",
    "Lost Omens #18 - Divine Mysteries.json":    "LO: Divine Mysteries",
    "Lost Omens #19 - Rival Academies.json":     "LO: Rival Academies",
    "Treasure Vault (Remastered).json":          "Treasure Vault",
}

# Feat block header: NAME (optional [action]) then FEAT N
FEAT_HEADER_RE = re.compile(
    r'\n([A-Z][A-Z ,\'\-\(\)\/0-9]+?)[ \t\x08]*(\[[\w\- ]+\])?[ \t]*\n(FEAT)[ \t]+(\d+)\n',
)

TRAIT_RE = re.compile(r'^[A-Z][A-Z\-]+(?:\s+[A-Z][A-Z\-]+)*$')

STAT_PREFIXES = ['Prerequisites', 'Frequency', 'Trigger', 'Requirements', 'Access']

# Known class names (for the 'class' field)
CLASS_NAMES = {
    'ALCHEMIST', 'BARBARIAN', 'BARD', 'CHAMPION', 'CLERIC', 'DRUID',
    'FIGHTER', 'GUNSLINGER', 'INVENTOR', 'INVESTIGATOR', 'MAGUS', 'MONK',
    'ORACLE', 'PSYCHIC', 'RANGER', 'ROGUE', 'SORCERER', 'SUMMONER',
    'SWASHBUCKLER', 'THAUMATURGE', 'WITCH', 'WIZARD',
}

# Known ancestry names (for the 'class' field when it's an ancestry feat)
ANCESTRY_NAMES = {
    'DWARF', 'ELF', 'GNOME', 'GOBLIN', 'HALFLING', 'HUMAN', 'LESHY',
    'ORC', 'CATFOLK', 'KOBOLD', 'LIZARDFOLK', 'RATFOLK', 'SPRITE',
    'TENGU', 'AUTOMATON', 'FETCHLING', 'FLESHWARP', 'GHORAN',
    'GOLOMA', 'GRIPPLI', 'KITSUNE', 'POPPET', 'SHOONY', 'STRIX',
    'VANARA', 'VISHKANYA', 'GENIEKIN', 'NEPHILIM', 'REFLECTION',
    'AIUVARIN', 'DROMAAR',
}


def parse_action(raw):
    if not raw:
        return ""
    mapping = {
        'one-action': '1', 'two-actions': '2', 'three-actions': '3',
        'reaction': 'reaction', 'free-action': 'free',
    }
    tokens = re.findall(r'\[([\w\-]+)\]', raw)
    results = [mapping[t.lower()] for t in tokens if t.lower() in mapping]
    return ' to '.join(results) if results else ""


def infer_class(traits_list):
    """Pick the most relevant class/ancestry from the trait list."""
    for t in traits_list:
        upper = t.upper()
        if upper in CLASS_NAMES:
            return upper.title()
    for t in traits_list:
        upper = t.upper()
        if upper in ANCESTRY_NAMES:
            return upper.title() + ' (ancestry)'
    # Check for general/skill/archetype
    uppers = {t.upper() for t in traits_list}
    if 'ARCHETYPE' in uppers:
        return 'Archetype'
    if 'SKILL' in uppers:
        return 'General/Skill'
    if 'GENERAL' in uppers:
        return 'General'
    return ''


def parse_block(name_raw, action_raw, level, block_text, source):
    feat = {
        'name':          name_raw.strip(),
        'level':         int(level),
        'action_cost':   parse_action(action_raw),
        'traits':        [],
        'class':         '',
        'prerequisites': '',
        'frequency':     '',
        'trigger':       '',
        'requirements':  '',
        'access':        '',
        'description':   '',
        'source':        source,
    }

    lines       = block_text.split('\n')
    desc_lines  = []
    past_stats  = False
    last_stat   = None
    stat_key_map = {
        'Prerequisites': 'prerequisites', 'Frequency': 'frequency',
        'Trigger': 'trigger', 'Requirements': 'requirements', 'Access': 'access',
    }

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if past_stats:
                desc_lines.append('')
            else:
                last_stat = None
            continue

        # Traits
        if not past_stats and last_stat is None and TRAIT_RE.match(stripped) and len(stripped.split()) <= 4:
            feat['traits'].append(stripped)
            continue

        # Stat fields
        if not past_stats:
            matched = None
            for prefix in STAT_PREFIXES:
                if stripped.startswith(prefix + ' ') or stripped == prefix:
                    matched = prefix
                    break

            if matched:
                value = stripped[len(matched):].strip()
                key = stat_key_map[matched]
                feat[key] = value
                # Only continue Trigger/Requirements across lines
                # Prerequisites only continues if the value ends with a comma (list still going)
                if matched == 'Trigger':
                    last_stat = matched if value and not value.endswith('.') else None
                elif matched == 'Requirements':
                    last_stat = matched if value and not value.endswith('.') else None
                elif matched == 'Prerequisites':
                    last_stat = matched if value.endswith(',') else None
                else:
                    last_stat = None
                continue

            # Continuation of previous stat
            if last_stat is not None:
                key = stat_key_map[last_stat]
                feat[key] += ' ' + stripped
                if last_stat == 'Prerequisites':
                    last_stat = None if not stripped.endswith(',') else last_stat
                elif stripped.endswith('.') or stripped.endswith('?'):
                    last_stat = None
                continue

        # Description
        past_stats = True
        last_stat  = None
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

    feat['description'] = '\n\n'.join(parts).strip()
    feat['class']       = infer_class(feat['traits'])
    feat['traits']      = ', '.join(feat['traits'])

    return feat


def get_full_text(json_path):
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)
    return '\n' + '\n'.join(p['text'] for p in data['pages'])


def parse_book(json_filename, source_label):
    json_path = RAW_DIR / json_filename
    if not json_path.exists():
        return []

    full_text = get_full_text(json_path)
    matches   = list(FEAT_HEADER_RE.finditer(full_text))
    feats     = []

    for i, match in enumerate(matches):
        name_raw   = match.group(1)
        action_raw = match.group(2) or ''
        level      = match.group(4)

        block_start = match.end()
        block_end   = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        block_text  = full_text[block_start:block_end]

        feat = parse_block(name_raw, action_raw, level, block_text, source_label)
        feats.append(feat)

    return feats


def main():
    PARSED_DIR.mkdir(exist_ok=True)

    all_feats  = []
    seen       = {}
    duplicates = 0

    for json_file, label in ALL_BOOKS.items():
        json_path = RAW_DIR / json_file
        if not json_path.exists():
            continue
        feats = parse_book(json_file, label)
        print(f"  {label}: {len(feats)} feats")

        for feat in feats:
            key = feat['name'].lower()
            if key in seen:
                duplicates += 1
            else:
                seen[key] = feat['source']
                all_feats.append(feat)

    all_feats.sort(key=lambda f: f['name'].lower())

    out_path = PARSED_DIR / 'feats.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_feats, f, ensure_ascii=False, indent=2)

    print(f"\n=== Feat parsing complete ===")
    print(f"  Total unique feats : {len(all_feats)}")
    print(f"  Duplicates skipped : {duplicates}")
    print(f"\nWritten to: {out_path}")


if __name__ == "__main__":
    main()
