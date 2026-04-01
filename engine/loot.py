"""
engine/loot.py — Loot generator.

Uses official PF2e treasure tables (Table 10-9 / 10-10) and context profiles
(Standard, Boss, Poor, Rich, Hoard) to generate encounter-appropriate rewards.

Applies creature-type logic:
  - Beasts / Animals  → no coins, natural resources only
  - Undead            → no potions/food, ancient coins at half value
  - Constructs        → no coins, arcane components
  - Oozes             → no equipment, digested items only
  - Humanoids/Dragons → standard or hoard rules
"""

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from engine.dice import roll, weighted_choice

# ── Data Loading ───────────────────────────────────────────────────────────────

_DATA_DIR = Path(__file__).parent.parent / "static" / "data"


def _load(filename: str) -> any:
    path = _DATA_DIR / filename
    with open(path, encoding="utf-8") as f:
        return json.load(f)


_TREASURE_TABLES  = None
_CONTEXT_PROFILES = None
_ITEM_TABLES      = None


def _treasure() -> dict:
    global _TREASURE_TABLES
    if _TREASURE_TABLES is None:
        _TREASURE_TABLES = _load("pf2e_official_treasure_tables.json")
    return _TREASURE_TABLES


def _profiles() -> list:
    global _CONTEXT_PROFILES
    if _CONTEXT_PROFILES is None:
        _CONTEXT_PROFILES = _load("pf2e_loot_context_profiles.json")
    return _CONTEXT_PROFILES


def _items() -> dict:
    global _ITEM_TABLES
    if _ITEM_TABLES is None:
        _ITEM_TABLES = _load("pf2e_item_roll_tables.json")
    return _ITEM_TABLES


# ── Creature-type rules ────────────────────────────────────────────────────────

CREATURE_TYPE_RULES = {
    "beast": {
        "coins_multiplier": 0.0,
        "no_equipment": True,
        "flavour_items": ["pelt", "claws", "teeth", "bone", "hide"],
        "forbidden": ["potion", "scroll", "wand", "food"],
    },
    "animal": {
        "coins_multiplier": 0.0,
        "no_equipment": True,
        "flavour_items": ["pelt", "feathers", "gland", "meat"],
        "forbidden": ["potion", "scroll", "wand"],
    },
    "plant": {
        "coins_multiplier": 0.0,
        "no_equipment": True,
        "flavour_items": ["rare herb", "sap", "seed pod", "bark"],
        "forbidden": ["potion", "scroll", "weapon", "armor"],
    },
    "construct": {
        "coins_multiplier": 0.0,
        "no_equipment": True,
        "flavour_items": ["gear", "arcane component", "metal scrap", "lens"],
        "forbidden": ["potion", "food", "organic"],
    },
    "ooze": {
        "coins_multiplier": 0.3,
        "coins_note": "corroded, half value",
        "no_equipment": True,
        "flavour_items": ["partially dissolved item", "indigestible gem"],
        "forbidden": ["potion", "scroll", "food", "organic"],
    },
    "undead": {
        "coins_multiplier": 0.5,
        "coins_note": "ancient, may be foreign currency",
        "no_equipment": False,
        "equipment_condition": "deteriorated",
        "flavour_items": ["tarnished jewelry", "funeral shroud", "old weapon"],
        "forbidden": ["potion", "food", "healing item"],
    },
    "dragon": {
        "coins_multiplier": 3.0,
        "hoard_bonus": True,
        "flavour_items": ["gem", "art object", "ancient coin"],
        "forbidden": [],
    },
    "giant": {
        "coins_multiplier": 1.5,
        "flavour_items": ["oversized weapon", "crude jewelry"],
        "forbidden": [],
    },
    "fey": {
        "coins_multiplier": 0.5,
        "coins_note": "glamoured, may revert to leaves after 1 day",
        "flavour_items": ["trinket", "magical flower", "fey gift"],
        "forbidden": [],
    },
    "elemental": {
        "coins_multiplier": 0.0,
        "flavour_items": ["elemental essence", "gem", "raw material"],
        "forbidden": ["potion", "food"],
    },
}

# Default for anything not listed
DEFAULT_RULES = {
    "coins_multiplier": 1.0,
    "no_equipment": False,
    "flavour_items": [],
    "forbidden": [],
}

# Which item categories each creature type may carry.
# None means "use default" (all categories).
# Empty list means no items at all.
_ALL_CATS = ["wondrous", "consumable_healing", "consumable_combat", "consumable_utility"]

CREATURE_ITEM_CATEGORIES: dict[str, list[str]] = {
    "beast":     [],
    "animal":    [],
    "plant":     [],
    "ooze":      [],
    "construct": ["wondrous"],
    "elemental": ["wondrous"],
    "spirit":    ["wondrous"],
    "undead":    ["wondrous", "consumable_combat", "consumable_utility"],
    "fiend":     ["wondrous", "consumable_combat", "consumable_utility"],
    "giant":     ["wondrous", "consumable_combat"],
    "fey":       ["wondrous", "consumable_utility"],
    "dragon":    ["wondrous", "consumable_utility"],
    "celestial": ["wondrous", "consumable_utility", "consumable_healing"],
    "monitor":   ["wondrous", "consumable_utility"],
    "humanoid":  _ALL_CATS,
    "fungus":    [],
}


def _allowed_categories(creature_types: list[str]) -> list[str]:
    """
    Intersect allowed item categories across all creature types in the encounter.
    Uses most-restrictive logic: if any type forbids healing items, none appear.
    Falls back to all categories if a type is unknown.
    """
    if not creature_types:
        return _ALL_CATS
    sets = []
    for ct in creature_types:
        cats = CREATURE_ITEM_CATEGORIES.get(ct.lower())
        if cats is None:
            # Unknown type — allow everything
            sets.append(set(_ALL_CATS))
        else:
            sets.append(set(cats))
    # Intersection: most restrictive wins
    result = sets[0]
    for s in sets[1:]:
        result = result | s   # union: if ANY creature can have it, allow it
    return list(result)


def _rules_for(creature_type: str) -> dict:
    return CREATURE_TYPE_RULES.get((creature_type or "").lower(), DEFAULT_RULES)


# ── Profile selection ──────────────────────────────────────────────────────────

PROFILE_NAMES = {
    "standard": "Standard Encounter",
    "boss":     "Boss Encounter",
    "poor":     "Poor Encounter",
    "rich":     "Rich Encounter",
    "hoard":    "Hoard Discovery",
}


def _get_profile(profile_key: str) -> dict:
    name = PROFILE_NAMES.get(profile_key.lower(), "Standard Encounter")
    for p in _profiles():
        if p["name"] == name:
            return p
    return _profiles()[0]


# ── Item rolling ───────────────────────────────────────────────────────────────

def _parse_range(s: str) -> tuple[int, int]:
    """Parse "3-5" → (3, 5), "10" → (10, 10)."""
    try:
        parts = [int(x) for x in str(s).split("-")]
        return parts[0], parts[-1]
    except (ValueError, IndexError):
        return 1, 20


def _pick_item(
    level_range: str,
    rarity: str,
    item_tables: dict,
    allowed_categories: Optional[list[str]] = None,
) -> Optional[str]:
    """
    Pick a random item from pf2e_item_roll_tables.json.
    Uses range-overlap matching so "3-5" will pull from "3-4" and "5-6" tables.
    allowed_categories restricts which item pools are drawn from.
    """
    req_lo, req_hi = _parse_range(level_range)

    candidates = []
    for category, ranges in item_tables.items():
        if allowed_categories is not None and category not in allowed_categories:
            continue
        if not isinstance(ranges, dict):
            continue
        for range_key, items in ranges.items():
            if not isinstance(items, list):
                continue
            tbl_lo, tbl_hi = _parse_range(range_key)
            if tbl_lo <= req_hi and tbl_hi >= req_lo:
                candidates.extend(items)

    if not candidates:
        return None  # caller decides what to do with no results

    item = random.choice(candidates)
    if isinstance(item, dict):
        return item.get("name") or item.get("item") or str(item)
    return str(item)


# ── Main generator ─────────────────────────────────────────────────────────────

@dataclass
class LootItem:
    name: str
    item_type: str      # "permanent", "consumable", "flavour", "currency"
    rarity: str = "common"
    level_range: str = ""
    quantity: int = 1
    value_note: str = ""


@dataclass
class LootResult:
    party_level: int
    profile: str
    creature_types: list[str]
    gold: float
    gold_note: str
    items: list[LootItem]
    roll_log: list[str]


def generate_loot(
    party_level: int,
    profile_key: str = "standard",
    creature_types: Optional[list[str]] = None,
    randomize: bool = True,
) -> LootResult:
    """
    Generate loot for an encounter.

    Args:
        party_level:    Party's current level (1–20).
        profile_key:    "standard", "boss", "poor", "rich", "hoard".
        creature_types: List of creature types in the encounter (affects loot logic).
        randomize:      If False, use average values (deterministic GM mode).
    """
    creature_types = creature_types or ["humanoid"]
    log = []
    items = []

    profile     = _get_profile(profile_key)
    level_key   = str(min(20, max(1, party_level)))
    enc_data    = profile.get("treasure_per_encounter_level", {}).get(level_key, {})

    if not enc_data:
        # Nearest defined level (Hoard only has 1, 5, 10, 15, 20)
        defined_levels = sorted(int(k) for k in profile.get("treasure_per_encounter_level", {}).keys())
        nearest = min(defined_levels, key=lambda l: abs(l - party_level))
        enc_data = profile["treasure_per_encounter_level"][str(nearest)]
        log.append(f"Using nearest defined level {nearest} for profile '{profile['name']}'")

    log.append(f"Profile: {profile['name']} | Party level: {party_level}")

    # ── Determine dominant creature rules ────────────────────────────────────
    # If multiple creature types, apply most restrictive coins rule
    all_rules   = [_rules_for(t) for t in creature_types]
    min_mult    = min(r["coins_multiplier"] for r in all_rules)
    no_equip    = any(r.get("no_equipment") for r in all_rules)
    flavour_pool = []
    for r in all_rules:
        flavour_pool.extend(r.get("flavour_items", []))

    # Allowed item categories — derived from creature types
    allowed_cats = _allowed_categories(creature_types)
    # If no_equipment is set on ALL creature types, suppress permanent items
    all_no_equip = all(r.get("no_equipment") for r in all_rules)

    # ── Gold ─────────────────────────────────────────────────────────────────
    base_gold = enc_data.get("currency", {}).get("gp", 0)
    if randomize and base_gold > 0:
        # Add ±20% variance via a roll
        variance = max(1, int(base_gold * 0.2))
        gold_roll = random.randint(-variance, variance)
        actual_gold = max(0, base_gold + gold_roll)
        log.append(f"Gold: {base_gold}gp base ±{variance} → {actual_gold}gp")
    else:
        actual_gold = base_gold

    actual_gold = round(actual_gold * min_mult, 1)
    gold_note = ""
    for r in all_rules:
        if r.get("coins_note"):
            gold_note = r["coins_note"]
            break

    if min_mult == 0:
        log.append("No coins (creature type carries no currency)")
    elif min_mult < 1:
        log.append(f"Coins reduced to {int(min_mult*100)}% ({gold_note})")

    # ── Permanent items ───────────────────────────────────────────────────────
    item_tables = _items()

    if all_no_equip:
        log.append("No equipment (creature type carries no items)")
    else:
        perm_cats = [c for c in allowed_cats if c == "wondrous"]  # only wondrous as permanent
        if not perm_cats:
            perm_cats = ["wondrous"]  # always allow wondrous for permanent slots if equip allowed
        for slot in enc_data.get("permanent_items", []):
            level_range = slot.get("level_range", level_key)
            rarity      = slot.get("rarity", "common")
            count       = slot.get("count", 1)
            for _ in range(count):
                name = _pick_item(level_range, rarity, item_tables, perm_cats)
                if name:
                    items.append(LootItem(name, "permanent", rarity, level_range))
            log.append(f"Permanent: {count}x {rarity} item(s) level {level_range}")

    # ── Consumable items ──────────────────────────────────────────────────────
    cons_cats = [c for c in allowed_cats if c.startswith("consumable")]
    if cons_cats:
        for slot in enc_data.get("consumable_items", []):
            level_range = slot.get("level_range", level_key)
            rarity      = slot.get("rarity", "common")
            count       = slot.get("count", 1)
            for _ in range(count):
                name = _pick_item(level_range, rarity, item_tables, cons_cats)
                if name:
                    items.append(LootItem(name, "consumable", rarity, level_range))
            if count > 0:
                log.append(f"Consumable: {count}x {rarity} item(s) level {level_range}")

    # ── Flavour items (creature-specific drops) ───────────────────────────────
    if flavour_pool:
        qty = random.randint(1, 2) if randomize else 1
        chosen = random.sample(flavour_pool, min(qty, len(flavour_pool)))
        for f in chosen:
            items.append(LootItem(f, "flavour", "common", "", 1, "creature-specific drop"))
        log.append(f"Flavour: {', '.join(chosen)}")

    # ── Dragon hoard bonus ────────────────────────────────────────────────────
    for r in all_rules:
        if r.get("hoard_bonus"):
            bonus_gold = round(actual_gold * 2)
            actual_gold += bonus_gold
            items.append(LootItem("Gem (assorted)", "permanent", "uncommon", level_key, random.randint(1, 6)))
            items.append(LootItem("Art object", "permanent", "uncommon", level_key, random.randint(1, 3)))
            log.append(f"Dragon hoard bonus: +{bonus_gold}gp, gems, art objects")
            break

    return LootResult(party_level, profile["name"], creature_types, actual_gold, gold_note, items, log)
