"""
engine/dice.py — Dice rolling engine.
Parses standard notation (2d6+3, d%, 1d20), rolls tables, weighted choices.
"""

import random
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RollResult:
    notation: str
    rolls: list[int]
    modifier: int
    total: int
    description: str


def roll_die(sides: int) -> int:
    return random.randint(1, sides)


def parse_notation(notation: str) -> tuple[int, int, int]:
    """Parse 'XdY+Z' → (count, sides, modifier). Supports d%, d20, 2d6-1."""
    notation = notation.strip().lower().replace("–", "-")
    if notation in ("d%", "d100", "1d100"):
        return 1, 100, 0
    m = re.match(r"^(\d*)d(\d+)([+-]\d+)?$", notation)
    if not m:
        # Plain integer
        try:
            return 0, 0, int(notation)
        except ValueError:
            raise ValueError(f"Cannot parse dice notation: {notation!r}")
    count    = int(m.group(1)) if m.group(1) else 1
    sides    = int(m.group(2))
    modifier = int(m.group(3)) if m.group(3) else 0
    return count, sides, modifier


def roll(notation: str) -> RollResult:
    """Roll dice from notation string and return full result."""
    count, sides, modifier = parse_notation(notation)
    if count == 0:
        # Constant
        return RollResult(notation, [], modifier, modifier, str(modifier))

    rolls = [roll_die(sides) for _ in range(count)]
    total = sum(rolls) + modifier
    mod_str = f" {'+' if modifier >= 0 else ''}{modifier}" if modifier else ""
    desc = f"{notation} → [{', '.join(str(r) for r in rolls)}]{mod_str} = {total}"
    return RollResult(notation, rolls, modifier, total, desc)


def average(notation: str) -> int:
    """Return mathematical average of a dice notation (for no-randomness mode)."""
    count, sides, modifier = parse_notation(notation)
    if count == 0:
        return modifier
    avg_die = (sides + 1) / 2
    return round(count * avg_die + modifier)


def roll_on_table(table: list[Any], notation: str = None) -> Any:
    """
    Pick an entry from a list using a dice roll.
    If notation is None, picks uniformly at random.
    """
    if not table:
        return None
    if notation is None:
        return random.choice(table)
    result = roll(notation)
    idx = max(0, min(result.total - 1, len(table) - 1))
    return table[idx]


def weighted_choice(choices: list[dict]) -> Any:
    """
    Pick from a list of {value, weight} dicts.
    Weights are relative (don't need to sum to 100).
    """
    total = sum(c["weight"] for c in choices)
    r = random.uniform(0, total)
    cumulative = 0
    for c in choices:
        cumulative += c["weight"]
        if r <= cumulative:
            return c["value"]
    return choices[-1]["value"]


def percentile_roll() -> int:
    """Roll d100, return 1–100."""
    return random.randint(1, 100)
