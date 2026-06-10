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
    # Only the WINNING side advances from the score; the losing side is
    # unchanged by the score (asymmetric). Red-five penalties are then applied
    # on top, against the dealer side only.
    #
    #   farmer score   dealer_base   farmer_base
    #   0              +3            0
    #   5..55          +2            0
    #   60..115        +1            0
    #   120..175        0            0   (farmer win, dealer rotates)
    #   180..235        0           +1
    #   240..295        0           +2
    #   300+            0           +3
    if farmer_score == 0:
        dealer_base, farmer_base = 3, 0
    elif farmer_score <= 55:
        dealer_base, farmer_base = 2, 0
    elif farmer_score <= 115:
        dealer_base, farmer_base = 1, 0
    elif farmer_score <= 175:
        dealer_base, farmer_base = 0, 0
    elif farmer_score <= 235:
        dealer_base, farmer_base = 0, 1
    elif farmer_score <= 295:
        dealer_base, farmer_base = 0, 2
    else:  # 300+
        dealer_base, farmer_base = 0, 3

    # Red-five penalties hit the dealer side only (♥5 = -2 each, ♦5 = -1 each).
    red_five_penalty = hearts_fives_captured * 2 + diamonds_fives_captured * 1

    dealer_change = dealer_base - red_five_penalty
    farmer_change = farmer_base

    result = {}
    for player_id in dealer_side:
        result[player_id] = dealer_change
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
