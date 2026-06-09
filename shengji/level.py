"""Level progression system for Sheng Ji.

Level format: "R1:2", "R1:4", ..., "R1:A", "R2:2", ..., "R5:A", "B1:2", ..., "B10:A"

Full sequence (lowest to highest):
B10:2, B9:2, ..., B1:2, R1:2, R1:4, R1:6, R1:7, R1:8, R1:9, R1:10, R1:J, R1:Q, R1:K, R1:A, R2:2, ...
"""

from typing import List, Tuple

# All possible levels in a single round (2, 4, 6, 7, 8, 9, 10, J, Q, K, A)
# Note: 3 and 5 are excluded from levels (they're captains/lieutenants and always trump)
LEVEL_CARDS = ["2", "4", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]

# Full sequence from lowest to highest
LEVEL_SEQ: List[str] = []

# Basement levels (B10 to B1, all with rank "2")
for i in range(10, 0, -1):
    LEVEL_SEQ.append(f"B{i}:2")

# Regular rounds (R1 to R5)
for round_num in range(1, 6):
    for level_card in LEVEL_CARDS:
        LEVEL_SEQ.append(f"R{round_num}:{level_card}")

# LEVEL_SEQ is now complete with all possible levels


def key_index(level_key: str) -> int:
    """Get the index of a level key in LEVEL_SEQ (0 = lowest, len-1 = highest)."""
    if level_key not in LEVEL_SEQ:
        raise ValueError(f"Invalid level key: {level_key}")
    return LEVEL_SEQ.index(level_key)


def step_level(level_key: str, delta: int) -> str:
    """
    Move a level key by delta steps in the sequence.
    Returns the new level key, clamped to [B10:2, R5:A].
    """
    idx = key_index(level_key)
    new_idx = idx + delta

    # Clamp to valid range
    new_idx = max(0, min(len(LEVEL_SEQ) - 1, new_idx))

    return LEVEL_SEQ[new_idx]


def level_display(level_key: str) -> str:
    """Return a human-readable display string for a level key."""
    return level_key


def parse_level(level_key: str) -> Tuple[str, str]:
    """Parse a level key into (round_part, level_card).

    Examples:
        "R1:2" -> ("R1", "2")
        "B3:2" -> ("B3", "2")
    """
    parts = level_key.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid level key: {level_key}")
    return parts[0], parts[1]


def is_basement_level(level_key: str) -> bool:
    """Check if a level key is in basement (B1-B10)."""
    round_part, _ = parse_level(level_key)
    return round_part.startswith("B")
