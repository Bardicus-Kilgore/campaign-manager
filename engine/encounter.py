"""
engine/encounter.py — Encounter generator.

Given party level + difficulty + environment + terrain + encounter type,
calculates XP budget, queries the DB for matching creatures, and returns
a balanced encounter composition with tactical context.
"""

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ── d100 encounter tables ──────────────────────────────────────────────────────

_D100_TABLES: dict = {}

def _load_d100_tables() -> None:
    global _D100_TABLES
    path = Path(__file__).parent.parent / "static" / "encounter_d100_tables.json"
    with open(path, encoding="utf-8") as f:
        _D100_TABLES = json.load(f)

_load_d100_tables()


def _lookup_d100(environment: str, roll: int) -> Optional[dict]:
    for entry in _D100_TABLES.get(environment, []):
        if entry["min"] <= roll <= entry["max"]:
            return entry
    return None

# ── XP Tables (PF2e Core Rulebook) ────────────────────────────────────────────

CREATURE_XP = {
    -4: 10,
    -3: 15,
    -2: 20,
    -1: 30,
     0: 40,
     1: 60,
     2: 80,
     3: 120,
     4: 160,
}

DIFFICULTY_BUDGET = {
    "trivial":  40,
    "low":      60,
    "moderate": 80,
    "severe":   120,
    "extreme":  160,
}

# ── Environment definitions ────────────────────────────────────────────────────

ENVIRONMENT_TAGS = {
    "dungeon":    {"flavour": "stone corridors and dark chambers"},
    "wilderness": {"flavour": "open terrain, natural hazards"},
    "urban":      {"flavour": "streets, buildings, crowds"},
    "underwater": {"flavour": "currents, limited visibility"},
    "desert":     {"flavour": "heat, scarce water, sandstorms"},
    "arctic":     {"flavour": "cold, snow, ice hazards"},
    "forest":     {"flavour": "dense trees, difficult terrain"},
    "swamp":      {"flavour": "mud, water, disease"},
    "mountain":   {"flavour": "altitude, rockfall, wind"},
    "planar":     {"flavour": "extraplanar traits, strange physics"},
}

# ── Terrain definitions ────────────────────────────────────────────────────────
# terrain_type → preferred creature traits/types, tactical notes, valid environments

TERRAIN_PROFILES = {
    # Dungeon terrains
    "corridor": {
        "environments": ["dungeon"],
        "preferred_traits": ["undead", "construct", "humanoid"],
        "preferred_types":  ["Undead", "Construct", "Humanoid"],
        "tactics": "Narrow space — line-of-sight limited. Ranged attackers lose advantage. Ambush likely.",
        "xp_modifier": 0,
    },
    "chamber": {
        "environments": ["dungeon"],
        "preferred_traits": ["undead", "construct", "humanoid", "aberration"],
        "preferred_types":  ["Undead", "Construct", "Humanoid", "Aberration"],
        "tactics": "Open room — full tactical movement possible. Mixed range and melee.",
        "xp_modifier": 0,
    },
    "flooded_room": {
        "environments": ["dungeon", "swamp"],
        "preferred_traits": ["aquatic", "undead", "aberration"],
        "preferred_types":  ["Aberration", "Undead", "Beast"],
        "tactics": "Difficult terrain throughout. Swimming or wading required. Fire spells reduced.",
        "xp_modifier": 10,  # Environmental hazard adds effective XP
    },
    "throne_room": {
        "environments": ["dungeon", "urban"],
        "preferred_traits": ["humanoid", "undead"],
        "preferred_types":  ["Humanoid", "Undead"],
        "tactics": "Boss likely enthroned with guards. Chokepoint at entrance. High ground advantage.",
        "xp_modifier": 20,
    },
    "shrine": {
        "environments": ["dungeon"],
        "preferred_traits": ["undead", "fiend", "celestial"],
        "preferred_types":  ["Undead", "Fiend", "Spirit"],
        "tactics": "Religious site. Casters and summoners likely. May include active hazard or trap.",
        "xp_modifier": 10,
    },
    "pit_room": {
        "environments": ["dungeon"],
        "preferred_traits": ["beast", "aberration", "undead"],
        "preferred_types":  ["Beast", "Aberration", "Undead"],
        "tactics": "Central pit hazard. Pushes and grapples are deadly. Flight is decisive.",
        "xp_modifier": 20,
    },
    "workshop": {
        "environments": ["dungeon", "urban"],
        "preferred_traits": ["humanoid", "construct"],
        "preferred_types":  ["Humanoid", "Construct"],
        "tactics": "Cover from workbenches. Alchemical hazards possible. Lots of improvised weapons.",
        "xp_modifier": 0,
    },
    # Wilderness terrains
    "forest_clearing": {
        "environments": ["forest", "wilderness"],
        "preferred_traits": ["beast", "fey", "humanoid"],
        "preferred_types":  ["Beast", "Fey", "Humanoid"],
        "tactics": "Open area ringed by trees. Ranged attackers retreat into cover. Difficult terrain at edges.",
        "xp_modifier": 0,
    },
    "dense_forest": {
        "environments": ["forest", "wilderness"],
        "preferred_traits": ["beast", "fey", "plant"],
        "preferred_types":  ["Beast", "Fey", "Plant"],
        "tactics": "Heavily obscured. Ambush-heavy. Difficult terrain everywhere. Line of sight rarely exceeds 30ft.",
        "xp_modifier": 10,
    },
    "river_crossing": {
        "environments": ["wilderness", "swamp"],
        "preferred_traits": ["aquatic", "beast"],
        "preferred_types":  ["Beast", "Humanoid"],
        "tactics": "Party split by river. Difficult terrain in water. Attack during crossing is classic ambush.",
        "xp_modifier": 20,
    },
    "cave_entrance": {
        "environments": ["wilderness", "mountain"],
        "preferred_traits": ["beast", "humanoid", "giant"],
        "preferred_types":  ["Beast", "Humanoid", "Giant"],
        "tactics": "Defenders hold the high ground inside. Attackers funnel through entrance.",
        "xp_modifier": 10,
    },
    "rocky_outcrop": {
        "environments": ["mountain", "wilderness", "desert"],
        "preferred_traits": ["beast", "giant", "humanoid"],
        "preferred_types":  ["Beast", "Giant", "Humanoid"],
        "tactics": "Elevation advantage for defenders. Boulders as improvised hazards.",
        "xp_modifier": 0,
    },
    "open_road": {
        "environments": ["wilderness", "urban"],
        "preferred_traits": ["humanoid"],
        "preferred_types":  ["Humanoid"],
        "tactics": "Flat, open. No cover. Speed and ranged attacks dominant. Classic bandit terrain.",
        "xp_modifier": 0,
    },
    # Urban terrains
    "alley": {
        "environments": ["urban"],
        "preferred_traits": ["humanoid", "undead"],
        "preferred_types":  ["Humanoid", "Undead"],
        "tactics": "Very narrow. Two-wide max. Ranged useless. Escape routes limited.",
        "xp_modifier": 0,
    },
    "rooftop": {
        "environments": ["urban"],
        "preferred_traits": ["humanoid"],
        "preferred_types":  ["Humanoid"],
        "tactics": "Falling damage risk. Ranged superiority. Acrobatics checks to traverse gaps.",
        "xp_modifier": 10,
    },
    "marketplace": {
        "environments": ["urban"],
        "preferred_traits": ["humanoid"],
        "preferred_types":  ["Humanoid"],
        "tactics": "Crowd = cover + collateral risk. Bystanders limit AoE. Chase likely.",
        "xp_modifier": 0,
    },
    "tavern": {
        "environments": ["urban"],
        "preferred_traits": ["humanoid"],
        "preferred_types":  ["Humanoid"],
        "tactics": "Tight quarters. Improvised weapons everywhere. Brawl more likely than lethal combat.",
        "xp_modifier": -10,
    },
    # Special
    "swamp_bog": {
        "environments": ["swamp"],
        "preferred_traits": ["beast", "undead", "plant", "aberration"],
        "preferred_types":  ["Beast", "Undead", "Plant"],
        "tactics": "Difficult terrain throughout. Sink hazard. Visibility poor. Disease risk.",
        "xp_modifier": 20,
    },
    "ice_field": {
        "environments": ["arctic"],
        "preferred_traits": ["beast", "elemental"],
        "preferred_types":  ["Beast", "Elemental"],
        "tactics": "Slippery surface. Falling prone likely. Cold immunity creatures at advantage.",
        "xp_modifier": 10,
    },
    "ruins": {
        "environments": ["wilderness", "dungeon", "urban"],
        "preferred_traits": ["undead", "humanoid", "beast", "construct"],
        "preferred_types":  ["Undead", "Humanoid", "Beast", "Construct"],
        "tactics": "Partial cover everywhere. Unstable floors possible. Mix of indoor and outdoor.",
        "xp_modifier": 0,
    },
}

# ── Encounter type definitions ─────────────────────────────────────────────────

ENCOUNTER_TYPES = {
    "combat": {
        "description": "Standard open fight.",
        "budget_modifier": 0,
        "preferred_strategy": None,  # use all strategies
        "loot_profile_hint": "standard",
    },
    "ambush": {
        "description": "Enemies attack with surprise. Attackers have advantage first round.",
        "budget_modifier": -10,  # Effectively harder — reduce available budget to compensate
        "preferred_strategy": "horde_or_leader",
        "loot_profile_hint": "standard",
        "tactical_note": "Surprise round: all enemies act before party rolls initiative.",
    },
    "boss": {
        "description": "Single powerful enemy, possibly with elite minions.",
        "budget_modifier": 20,
        "preferred_strategy": "solo_or_leader",
        "loot_profile_hint": "boss",
    },
    "patrol": {
        "description": "A group of guards or wandering enemies, not on alert.",
        "budget_modifier": -10,
        "preferred_strategy": "equal_group",
        "loot_profile_hint": "poor",
        "tactical_note": "Patrol may call reinforcements if not silenced quickly.",
    },
    "guard_post": {
        "description": "Stationed defenders holding a fixed position.",
        "budget_modifier": 10,
        "preferred_strategy": "leader_plus_minions",
        "loot_profile_hint": "standard",
        "tactical_note": "Defenders have prepared positions. Attacker must breach.",
    },
    "trap_heavy": {
        "description": "Encounter features active traps alongside creatures.",
        "budget_modifier": -20,  # Part of budget consumed by traps (not creature XP)
        "preferred_strategy": None,
        "loot_profile_hint": "poor",
        "tactical_note": "Traps represent ~25% of XP budget. Perception and Thievery are key.",
    },
    "siege": {
        "description": "Large numbers attack a defended position.",
        "budget_modifier": 30,
        "preferred_strategy": "horde",
        "loot_profile_hint": "rich",
        "tactical_note": "Waves may continue after initial group is defeated.",
    },
    "social": {
        "description": "Non-combat encounter — negotiation, infiltration, or tense standoff.",
        "budget_modifier": -40,
        "preferred_strategy": "equal_group",
        "loot_profile_hint": "poor",
        "tactical_note": "Combat is possible but not the primary challenge.",
    },
}


@dataclass
class EncounterCreature:
    name: str
    level: int
    creature_type: str
    quantity: int
    xp_each: int
    xp_total: int


@dataclass
class EncounterResult:
    party_level: int
    difficulty: str
    encounter_type: str
    environment: str
    terrain: Optional[str]
    xp_budget: int
    xp_used: int
    creatures: list[EncounterCreature]
    tactics: str
    loot_profile_hint: str
    roll_log: list[str]
    warnings: list[str] = field(default_factory=list)


def _xp_for_level_diff(diff: int) -> int:
    return CREATURE_XP.get(max(-4, min(4, diff)), 10 if diff < -4 else 160)


def _fetch_candidates(db_con, party_level: int, environment: str,
                      terrain_profile: Optional[dict], preferred_types: Optional[list[str]]) -> list[dict]:
    min_level = party_level - 4
    max_level = party_level + 4

    rows = db_con.execute(
        "SELECT name, level, type, traits FROM creatures WHERE level BETWEEN ? AND ?",
        (min_level, max_level),
    ).fetchall()
    candidates = [dict(r) for r in rows]

    # Build preferred type set from terrain + explicit request
    pref_types = set()
    if terrain_profile:
        pref_types.update(t.lower() for t in terrain_profile.get("preferred_types", []))
    if preferred_types:
        pref_types.update(t.lower() for t in preferred_types)

    if pref_types:
        preferred = [c for c in candidates if (c.get("type") or "").lower() in pref_types]
        fallback  = [c for c in candidates if (c.get("type") or "").lower() not in pref_types]
        random.shuffle(preferred)
        random.shuffle(fallback)
        candidates = preferred + fallback
    else:
        random.shuffle(candidates)

    return candidates


def generate_encounter(
    db_con,
    party_level: int,
    difficulty: str = "moderate",
    environment: str = "dungeon",
    terrain: Optional[str] = None,
    encounter_type: str = "combat",
    preferred_types: Optional[list[str]] = None,
    strategy_override: Optional[str] = None,
) -> EncounterResult:
    difficulty     = difficulty.lower()
    encounter_type = encounter_type.lower()
    environment    = environment.lower()
    terrain        = terrain.lower() if terrain else None

    log      = []
    warnings = []

    # ── XP budget ─────────────────────────────────────────────────────────────
    base_budget  = DIFFICULTY_BUDGET.get(difficulty, 80)
    enc_def      = ENCOUNTER_TYPES.get(encounter_type, ENCOUNTER_TYPES["combat"])
    terrain_prof = TERRAIN_PROFILES.get(terrain) if terrain else None

    budget = base_budget
    budget += enc_def.get("budget_modifier", 0)
    if terrain_prof:
        budget += terrain_prof.get("xp_modifier", 0)
    budget = max(10, budget)  # never below 10

    log.append(f"Base XP: {base_budget} | Type modifier: {enc_def.get('budget_modifier',0)} | Terrain modifier: {terrain_prof.get('xp_modifier',0) if terrain_prof else 0} → Budget: {budget}")

    # ── Tactical description ───────────────────────────────────────────────────
    tactics_parts = []
    if terrain_prof:
        tactics_parts.append(terrain_prof["tactics"])
    if "tactical_note" in enc_def:
        tactics_parts.append(enc_def["tactical_note"])
    if not tactics_parts:
        env_def = ENVIRONMENT_TAGS.get(environment, {})
        tactics_parts.append(f"Setting: {env_def.get('flavour', environment)}.")
    tactics = " ".join(tactics_parts)

    # Terrain/environment mismatch warning
    if terrain_prof and environment not in terrain_prof.get("environments", [environment]):
        warnings.append(f"Terrain '{terrain}' is unusual for environment '{environment}'.")

    # ── Strategy: encounter_type > hook override > d100 fallback ──────────────
    # encounter_type's fixed strategy always wins (boss, patrol, etc.)
    strategy_hint = enc_def.get("preferred_strategy")
    # Hook's strategy fills in when encounter_type is generic ("combat")
    if not strategy_hint and strategy_override:
        strategy_hint = strategy_override

    # d100 only fires when the hook provided no guidance (types AND strategy both absent)
    if not preferred_types and not strategy_override:
        d100_roll  = random.randint(1, 100)
        roll_entry = _lookup_d100(environment, d100_roll)
        if roll_entry:
            log.append(f"d100={d100_roll} → {roll_entry['name']} (fallback)")
            if not strategy_hint:
                strategy_hint = roll_entry.get("strategy")
            preferred_types = roll_entry.get("preferred_types")

    # ── Candidate creatures ────────────────────────────────────────────────────
    candidates = _fetch_candidates(db_con, party_level, environment, terrain_prof, preferred_types)

    if not candidates:
        warnings.append(f"No creatures found for party level {party_level}.")
        return EncounterResult(
            party_level, difficulty, encounter_type, environment, terrain,
            budget, 0, [], tactics, enc_def["loot_profile_hint"], log, warnings
        )

    log.append(f"{len(candidates)} candidates | Strategy hint: {strategy_hint or 'any'}")

    # ── Composition ────────────────────────────────────────────────────────────
    creatures = _build_composition(candidates, party_level, budget, strategy_hint, log)
    xp_used   = sum(c.xp_total for c in creatures)

    return EncounterResult(
        party_level, difficulty, encounter_type, environment, terrain,
        budget, xp_used, creatures, tactics, enc_def["loot_profile_hint"], log, warnings
    )


def _build_composition(candidates, party_level, budget, strategy_hint, log):
    # Strategy map
    all_strategies = {
        "solo":                _strategy_solo_boss,
        "solo_or_leader":      _strategy_solo_boss,
        "leader_plus_minions": _strategy_leader_plus_minions,
        "equal_group":         _strategy_equal_group,
        "horde":               _strategy_horde,
        "horde_or_leader":     _strategy_horde,
    }

    if strategy_hint and strategy_hint in all_strategies:
        # Try hinted strategy first, fall back to others
        ordered = [all_strategies[strategy_hint]] + [
            s for k, s in all_strategies.items()
            if s is not all_strategies[strategy_hint]
        ]
    else:
        ordered = list(all_strategies.values())

    # Deduplicate while preserving order
    seen = set()
    strategies = []
    for s in ordered:
        if id(s) not in seen:
            seen.add(id(s))
            strategies.append(s)

    results = []
    for strategy in strategies:
        composition = strategy(candidates, party_level, budget)
        if composition:
            used = sum(c.xp_total for c in composition)
            if used <= budget * 1.1:
                results.append((used, composition))

    if not results:
        log.append("No clean composition — using fallback")
        return _fallback_single(candidates, party_level, budget)

    results.sort(key=lambda x: abs(budget - x[0]))
    chosen_xp, chosen = results[0]
    log.append(f"Composition: {len(chosen)} creature type(s), {chosen_xp} XP")
    return chosen


def _strategy_solo_boss(candidates, party_level, budget):
    for c in candidates:
        xp = _xp_for_level_diff(c["level"] - party_level)
        if budget * 0.7 <= xp <= budget * 1.1:
            return [EncounterCreature(c["name"], c["level"], c.get("type",""), 1, xp, xp)]
    return None


def _strategy_leader_plus_minions(candidates, party_level, budget):
    leaders = [c for c in candidates if 0 <= c["level"] - party_level <= 2]
    minions = [c for c in candidates if -3 <= c["level"] - party_level <= -1]
    if not leaders or not minions:
        return None
    leader  = random.choice(leaders)
    l_xp    = _xp_for_level_diff(leader["level"] - party_level)
    remaining = budget - l_xp
    if remaining <= 0:
        return None
    minion  = random.choice(minions)
    m_xp    = _xp_for_level_diff(minion["level"] - party_level)
    qty     = max(1, min(6, remaining // m_xp))
    if l_xp + m_xp * qty > budget * 1.1:
        return None
    return [
        EncounterCreature(leader["name"], leader["level"], leader.get("type",""), 1, l_xp, l_xp),
        EncounterCreature(minion["name"], minion["level"], minion.get("type",""), qty, m_xp, m_xp * qty),
    ]


def _strategy_equal_group(candidates, party_level, budget):
    for c in candidates:
        xp = _xp_for_level_diff(c["level"] - party_level)
        for qty in range(2, 5):
            if xp * qty <= budget * 1.05:
                return [EncounterCreature(c["name"], c["level"], c.get("type",""), qty, xp, xp * qty)]
    return None


def _strategy_horde(candidates, party_level, budget):
    weak = [c for c in candidates if c["level"] - party_level <= -2]
    if not weak:
        return None
    c   = random.choice(weak)
    xp  = _xp_for_level_diff(c["level"] - party_level)
    qty = min(10, budget // xp)
    if qty < 3:
        return None
    return [EncounterCreature(c["name"], c["level"], c.get("type",""), qty, xp, xp * qty)]


def _fallback_single(candidates, party_level, budget):
    best = min(candidates, key=lambda c: abs(_xp_for_level_diff(c["level"] - party_level) - budget))
    xp   = _xp_for_level_diff(best["level"] - party_level)
    return [EncounterCreature(best["name"], best["level"], best.get("type",""), 1, xp, xp)]


# ── Reference data for API ─────────────────────────────────────────────────────

def get_options() -> dict:
    return {
        "difficulties":     list(DIFFICULTY_BUDGET.keys()),
        "environments":     list(ENVIRONMENT_TAGS.keys()),
        "encounter_types":  {k: v["description"] for k, v in ENCOUNTER_TYPES.items()},
        "terrains": {
            k: {
                "environments": v["environments"],
                "tactics":      v["tactics"],
            }
            for k, v in TERRAIN_PROFILES.items()
        },
    }
