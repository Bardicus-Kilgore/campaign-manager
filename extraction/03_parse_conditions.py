"""
03_parse_conditions.py — Conditions Parser
Conditions live in the Player Core Remaster appendix.
Unlike spells/feats/creatures, they have no structured header —
just a title-case name followed by prose description.
We anchor on the known set of ~40 PF2e conditions.
"""

import json
import re
from pathlib import Path

RAW_DIR    = Path(__file__).parent / "raw"
PARSED_DIR = Path(__file__).parent / "parsed"

SOURCE_BOOK = "Pathfinder 2e - Player Core Remaster.json"

# All known PF2e Remaster conditions (canonical names)
KNOWN_CONDITIONS = [
    "Blinded", "Broken", "Clumsy", "Concealed", "Confused", "Controlled",
    "Dazzled", "Deafened", "Doomed", "Drained", "Dying", "Encumbered",
    "Enfeebled", "Fascinated", "Fatigued", "Fleeing", "Friendly", "Grabbed",
    "Helpful", "Hidden", "Hostile", "Immobilized", "Indifferent", "Invisible",
    "Observed", "Off-Guard", "Panicked", "Paralyzed", "Petrified", "Prone",
    "Quickened", "Restrained", "Sickened", "Slowed", "Stunned", "Stupefied",
    "Unconscious", "Undetected", "Unfriendly", "Unnoticed",
]

# Conditions that include a numeric value (Clumsy 2, Drained 3, etc.)
VALUED_CONDITIONS = {
    "Clumsy", "Doomed", "Drained", "Dying", "Enfeebled",
    "Quickened", "Sickened", "Slowed", "Stunned", "Stupefied",
}


def get_full_text():
    json_path = RAW_DIR / SOURCE_BOOK
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)
    return '\n'.join(p['text'] for p in data['pages'])


def main():
    PARSED_DIR.mkdir(exist_ok=True)

    full_text = get_full_text()

    # Find the "List of Conditions" section
    anchor = full_text.find("List of Conditions")
    if anchor < 0:
        print("ERROR: 'List of Conditions' section not found.")
        return
    section = full_text[anchor:]

    # Build a regex that matches any condition name at the start of a line
    # Conditions appear as their own line (possibly preceded by page nav noise)
    name_pattern = re.compile(
        r'(?:^|\n)(' + '|'.join(re.escape(c) for c in KNOWN_CONDITIONS) + r')\n',
    )

    matches = list(name_pattern.finditer(section))
    conditions = []

    for i, match in enumerate(matches):
        name = match.group(1)

        text_start = match.end()
        text_end   = matches[i + 1].start() if i + 1 < len(matches) else len(section)
        raw_text   = section[text_start:text_end]

        # Clean up the description: strip page numbers, nav text, collapse whitespace
        lines = []
        for line in raw_text.split('\n'):
            stripped = line.strip()
            if not stripped:
                continue
            # Skip bare page numbers and known nav strings
            if re.match(r'^\d+$', stripped):
                continue
            if stripped in ('Player Core', 'Conditions Appendix', 'CONDITIONS APPENDIX',
                            'Glossary & Index', 'Playing the Game'):
                continue
            lines.append(stripped)

        description = ' '.join(lines).strip()

        conditions.append({
            'name':        name,
            'has_value':   name in VALUED_CONDITIONS,
            'description': description,
            'source':      'Player Core',
        })

    conditions.sort(key=lambda c: c['name'])

    out_path = PARSED_DIR / 'conditions.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(conditions, f, ensure_ascii=False, indent=2)

    print(f"=== Conditions parsing complete ===")
    print(f"  Total conditions : {len(conditions)}")
    print(f"\nWritten to: {out_path}")


if __name__ == "__main__":
    main()
