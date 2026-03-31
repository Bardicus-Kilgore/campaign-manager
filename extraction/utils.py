"""
utils.py — Shared helpers for the pf2e-baudot extraction pipeline.
"""

import re

# PDF page-number clusters and sidebar navigation noise
_NOISE = re.compile(
    r'\s+\d{1,3}\s+\d{1,3}\s*\d{0,3}'       # bare page number pairs/triples
    r'|'
    r'\s+(?:'
        r'Introduction|Ancestries\s*&?\s*Backgrounds?|Classes|Skills|Feats|Equipment|'
        r'Spells|Rules|Playing the Game|Conditions Appendix|Character Sheet|'
        r'Glossary(?:\s*&\s*Index)?|Spell Lists|Focus Spells|Rituals|'
        r'Arcane|Divine|Occult|Primal|'
        r'Monster\s*CORE|Player\s*Core\s*\d*|GM\s*Core|Secrets of Magic|'
        r'Dark Archive|Book of the Dead|Howl of the Wild|Rage of Elements|'
        r'War of Immortals|Guns\s*&\s*Gears|NPC\s*Core\s*\d*|'
        r'Bestiary\s*\d*|Treasure Vault|'
        r'Spell Descriptions|SPELL DESCRIPTIONS'
    r')\b.*$',
    re.DOTALL | re.IGNORECASE,
)


def clean_description(text: str) -> str:
    """Strip PDF page numbers and sidebar navigation from extracted description text."""
    if not text:
        return text
    return _NOISE.sub('', text).strip()
