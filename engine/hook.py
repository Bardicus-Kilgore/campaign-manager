"""
engine/hook.py — Exquisite corpse encounter hook generator.

Rolls from 4 word-bank pools (who / action / modifier / object) to produce
a narrative hook sentence that drives creature selection and strategy.

Weighted by:
  - environment  (current encounter location)
  - arc          (campaign-level theme)
  - recent_types (creature types used in recent session encounters — softly avoided)
"""

import json
import random
from pathlib import Path
from typing import Optional

_HOOKS_DIR = Path(__file__).parent.parent / "static" / "hooks"

_WHO: Optional[list]      = None
_ACTION: Optional[list]   = None
_MODIFIER: Optional[list] = None
_OBJECT: Optional[list]   = None


def _load(filename: str) -> list:
    with open(_HOOKS_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def _pools() -> tuple:
    global _WHO, _ACTION, _MODIFIER, _OBJECT
    if _WHO is None:
        _WHO      = _load("who.json")
        _ACTION   = _load("action.json")
        _MODIFIER = _load("modifier.json")
        _OBJECT   = _load("object.json")
    return _WHO, _ACTION, _MODIFIER, _OBJECT


ARC_OPTIONS = {
    "dungeon_delve":         "Dungeon Delve",
    "cult_activity":         "Cult Activity",
    "undead_siege":          "Undead Siege",
    "political_intrigue":    "Political Intrigue",
    "wilderness_expedition": "Wilderness Expedition",
    "planar_threat":         "Planar Threat",
    "ancient_mystery":       "Ancient Mystery",
    "custom":                "Custom",
}


def _score(entry: dict, environment: str, arc: str, avoid_types: set) -> float:
    score = 2.0
    if arc and arc != "custom" and arc in entry.get("arcs", []):
        score += 3.0
    if environment and environment in entry.get("environments", []):
        score += 2.0
    # Softly penalise recently used creature types (don't make it impossible)
    types = [t.lower() for t in entry.get("creature_types", [])]
    if avoid_types and types and all(t in avoid_types for t in types):
        score *= 0.25
    return max(score, 0.25)


def _weighted_pick(pool: list, environment: str, arc: str, avoid_types: set = None) -> dict:
    avoid_types = avoid_types or set()
    weights = [_score(e, environment, arc, avoid_types) for e in pool]
    total   = sum(weights)
    r       = random.uniform(0, total)
    cumul   = 0.0
    for entry, w in zip(pool, weights):
        cumul += w
        if r <= cumul:
            return entry
    return random.choice(pool)


def generate_hook(
    environment: str = "dungeon",
    arc: str = "custom",
    recent_types: Optional[list[str]] = None,
    locked: Optional[dict] = None,
) -> dict:
    """
    Generate an encounter hook sentence from 4 combinatorial slots.

    Args:
        environment:  Current encounter environment key.
        arc:          Campaign arc key (see ARC_OPTIONS).
        recent_types: Creature types used in recent session encounters.
        locked:       Dict of pre-fixed slot values, e.g. {"who": "a lich"}.
                      Locked slots are not re-rolled.

    Returns:
        {
          "hook":            full sentence string,
          "who":             slot label,
          "action":          slot label,
          "modifier":        slot label,
          "object":          slot label,
          "preferred_types": list[str] — from 'who' entry,
          "strategy_hint":   str|None  — from 'action' entry,
        }
    """
    locked      = locked or {}
    avoid       = set(t.lower() for t in (recent_types or []))
    who_p, action_p, modifier_p, object_p = _pools()

    # ── Roll each slot (or use locked value) ──────────────────────────────────
    def _find_or_bare(pool, label, extra_key=None, extra_default=None):
        """Find a pool entry by label, or return a minimal dict."""
        entry = next((e for e in pool if e["label"] == label), None)
        if entry:
            return entry
        bare = {"label": label, "arcs": [], "environments": []}
        if extra_key:
            bare[extra_key] = extra_default
        return bare

    if "who" in locked:
        who = _find_or_bare(who_p, locked["who"], "creature_types", [])
    else:
        who = _weighted_pick(who_p, environment, arc, avoid)

    if "action" in locked:
        action = _find_or_bare(action_p, locked["action"], "strategy", None)
    else:
        action = _weighted_pick(action_p, environment, arc)

    if "modifier" in locked:
        modifier = {"label": locked["modifier"], "arcs": [], "environments": []}
    else:
        modifier = _weighted_pick(modifier_p, environment, arc)

    if "object" in locked:
        obj = {"label": locked["object"], "article": "a", "arcs": [], "environments": []}
    else:
        obj = _weighted_pick(object_p, environment, arc)

    # ── Build sentence ─────────────────────────────────────────────────────────
    mod_label = modifier["label"]
    obj_label = obj["label"]
    # Article is always based on the modifier (it precedes the object)
    article = "an" if mod_label[0].lower() in "aeiou" else "a"

    hook = f"{who['label']} {action['label']} {article} {mod_label} {obj_label}"

    return {
        "hook":            hook,
        "who":             who["label"],
        "action":          action["label"],
        "modifier":        mod_label,
        "object":          obj_label,
        "preferred_types": who.get("creature_types", []),
        "strategy_hint":   action.get("strategy"),
    }
