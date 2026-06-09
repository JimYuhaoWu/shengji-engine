"""Scoring and level progression for Sheng Ji."""

from typing import Dict, Tuple
from .card import Card
from .types import Rank, Suit
from .level import step_level


SCORING_VALUES = {
    Rank.FIVE: 5,
    Rank.TEN: 10,
    Rank.KING: 10,
}


def compute_farmer_score(tricks_won: Tuple[Card, ...]) -> int:
    """
    Compute the total score from tricks won by farmer side.
    Scores: 5 (5pts), 10 (10pts), K (10pts).
    """
    score = 0
    for card in tricks_won:
        score += SCORING_VALUES.get(card.rank, 0)
    return score


def compute_level_changes(
    farmer_score: int,
    hearts_fives_captured: int,
    diamonds_fives_captured: int,
    dealer_side: Tuple[int, ...],
    farmer_side: Tuple[int, ...],
) -> Dict[int, str]:
    """
    Compute level changes for all players based on farmer score and red five penalties.

    Args:
        farmer_score: Total score captured by farmer side
        hearts_fives_captured: Number of ♥5 cards captured by farmers (0-3)
        diamonds_fives_captured: Number of ♦5 cards captured by farmers (0-3)
        dealer_side: Tuple of player indices on dealer side
        farmer_side: Tuple of player indices on farmer side

    Returns:
        Dict mapping player_id to level delta (string that can be passed to step_level)
    """
    # Determine base level change for dealer side
    if farmer_score == 0:
        base_change = 3  # Dealer +3
    elif 5 <= farmer_score <= 55:
        base_change = 2  # Dealer +2
    elif 60 <= farmer_score <= 115:
        base_change = 1  # Dealer +1
    elif 120 <= farmer_score <= 175:
        base_change = 0  # Neutral (farmer win)
    elif 180 <= farmer_score <= 235:
        base_change = -1  # Farmer +1
    elif 240 <= farmer_score <= 295:
        base_change = -2  # Farmer +2
    else:  # 300+
        base_change = -3  # Farmer +3

    # Apply red five penalties (additional changes to dealer side)
    red_five_penalty = -(hearts_fives_captured * 2 + diamonds_fives_captured * 1)

    result = {}

    # Dealer side: base_change + red_five_penalty (both positive means dealer loses)
    dealer_change = base_change + red_five_penalty
    for player_id in dealer_side:
        result[player_id] = dealer_change

    # Farmer side: inverse of base_change (no red five penalty for farmers on their own points)
    farmer_change = -base_change
    for player_id in farmer_side:
        result[player_id] = farmer_change

    return result


def apply_level_changes(
    player_levels: Tuple[str, ...],
    level_changes: Dict[int, int],
) -> Tuple[str, ...]:
    """
    Apply level changes to player levels.

    Args:
        player_levels: Current level of each player
        level_changes: Dict mapping player_id to level delta

    Returns:
        New level tuple for all players
    """
    new_levels = list(player_levels)
    for player_id, delta in level_changes.items():
        new_levels[player_id] = step_level(player_levels[player_id], delta)
    return tuple(new_levels)


def count_red_fives(cards: Tuple[Card, ...]) -> Tuple[int, int]:
    """
    Count the number of ♥5 and ♦5 cards in a tuple of cards.

    Returns:
        Tuple of (hearts_fives_count, diamonds_fives_count)
    """
    hearts_fives = 0
    diamonds_fives = 0
    for card in cards:
        if card.rank == Rank.FIVE:
            if card.suit == Suit.HEARTS:
                hearts_fives += 1
            elif card.suit == Suit.DIAMONDS:
                diamonds_fives += 1
    return (hearts_fives, diamonds_fives)
