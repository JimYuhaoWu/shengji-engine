"""Trump card ordering and comparison.

Trump ranking (highest to lowest):
1. 5♥ (always trump)
2. 5♦ (always trump)
3. Large Joker
4. Small Joker
5. Captain = 3 of trump suit's color
6. Lieutenant = 3 of the other color in same pair
7. Trump Level Card (level being played, in trump suit)
8. Non-Trump Level Cards (level being played, in other suits)
9. A, K, Q, J, T, 9, 8, 7, 6, 4, 2 (of trump suit)

Non-trump suit cards rank: A, K, Q, J, T, 9, 8, 7, 6, 5, 4, 3, 2
"""

from typing import Tuple, Optional
from .types import Suit, Rank
from .card import Card, is_red_suit, is_black_suit


def is_always_trump(card: Card) -> bool:
    """Check if card is always trump (5♥ or 5♦)."""
    return card.rank == Rank.FIVE and card.suit in (Suit.HEARTS, Suit.DIAMONDS)


def is_joker(card: Card) -> bool:
    """Check if card is a Joker."""
    return card.suit == Suit.JOKER


def is_level_card(card: Card, level: str) -> bool:
    """Check if card matches the current level."""
    return card.rank.value == level and card.suit != Suit.JOKER


def is_captain(card: Card, trump_suit: Suit) -> bool:
    """Check if card is the Captain (3 of trump suit's color)."""
    if card.rank != Rank.THREE:
        return False
    if trump_suit == Suit.HEARTS:
        return card.suit == Suit.HEARTS
    elif trump_suit == Suit.DIAMONDS:
        return card.suit == Suit.DIAMONDS
    elif trump_suit == Suit.CLUBS:
        return card.suit == Suit.CLUBS
    elif trump_suit == Suit.SPADES:
        return card.suit == Suit.SPADES
    return False


def is_lieutenant(card: Card, trump_suit: Suit) -> bool:
    """Check if card is the Lieutenant (3 of the other color in the pair)."""
    if card.rank != Rank.THREE:
        return False
    if trump_suit == Suit.HEARTS:
        return card.suit == Suit.DIAMONDS
    elif trump_suit == Suit.DIAMONDS:
        return card.suit == Suit.HEARTS
    elif trump_suit == Suit.CLUBS:
        return card.suit == Suit.SPADES
    elif trump_suit == Suit.SPADES:
        return card.suit == Suit.CLUBS
    return False


def is_trump(card: Card, trump_suit: Suit, trump_level: str) -> bool:
    """Check if card is a trump card."""
    if is_always_trump(card):
        return True
    if is_joker(card):
        return True
    if is_captain(card, trump_suit):
        return True
    if is_lieutenant(card, trump_suit):
        return True
    if is_level_card(card, trump_level):
        return True
    return False


def trump_rank(card: Card, trump_suit: Suit, trump_level: str) -> Optional[int]:
    """
    Get trump rank for a trump card (higher = stronger).
    Returns None if card is not a trump.

    Ranking (higher is stronger):
    0. 5♥
    1. 5♦
    2. Large Joker
    3. Small Joker
    4. Captain
    5. Lieutenant
    6. Trump Level Card (in trump suit)
    7. Non-Trump Level Cards (in other suits)
    8-17. A, K, Q, J, T, 9, 8, 7, 6, 4, 2 (of trump suit)
    """
    # Always trump cards
    if card.suit == Suit.HEARTS and card.rank == Rank.FIVE:
        return 1000  # 5♥ is highest
    if card.suit == Suit.DIAMONDS and card.rank == Rank.FIVE:
        return 999   # 5♦ is second highest

    # Jokers
    if card.rank == Rank.LARGE_JOKER:
        return 998   # Large Joker
    if card.rank == Rank.SMALL_JOKER:
        return 997   # Small Joker

    # Captain and Lieutenant
    if is_captain(card, trump_suit):
        return 996   # Captain
    if is_lieutenant(card, trump_suit):
        return 995   # Lieutenant

    # Trump level card
    if is_level_card(card, trump_level):
        if card.suit == trump_suit:
            return 994   # Trump level card in trump suit
        else:
            return 993   # Trump level card in non-trump suit

    # Regular trump suit cards (A, K, Q, J, T, 9, 8, 7, 6, 4, 2)
    if card.suit == trump_suit:
        trump_rank_order = [
            Rank.ACE, Rank.KING, Rank.QUEEN, Rank.JACK, Rank.TEN,
            Rank.NINE, Rank.EIGHT, Rank.SEVEN, Rank.SIX, Rank.FOUR, Rank.TWO
        ]
        try:
            idx = trump_rank_order.index(card.rank)
            return 900 - idx  # 900 to 890
        except ValueError:
            return None

    return None


def non_trump_rank(card: Card) -> Optional[int]:
    """
    Get rank for a non-trump card in its own suit.
    Returns None if card is a trump or invalid.

    Ranking (higher is stronger): A, K, Q, J, T, 9, 8, 7, 6, 5, 4, 3, 2
    """
    # Level cards that are trump shouldn't appear here
    rank_order = [
        Rank.ACE, Rank.KING, Rank.QUEEN, Rank.JACK, Rank.TEN,
        Rank.NINE, Rank.EIGHT, Rank.SEVEN, Rank.SIX, Rank.FIVE,
        Rank.FOUR, Rank.THREE, Rank.TWO
    ]
    try:
        idx = rank_order.index(card.rank)
        return 1000 - idx  # 1000 to 988
    except ValueError:
        return None


def compare_cards(
    card1: Card,
    card2: Card,
    led_suit: Suit,
    trump_suit: Suit,
    trump_level: str
) -> int:
    """
    Compare two cards in a trick context.
    Returns: 1 if card1 > card2, -1 if card1 < card2, 0 if equal

    Rules:
    - Trump > non-trump
    - Within trump: higher trump rank wins
    - Within led suit non-trump: higher non-trump rank wins
    - Different non-trump suits: neither wins (compare_cards shouldn't be called)
    """
    card1_is_trump = is_trump(card1, trump_suit, trump_level)
    card2_is_trump = is_trump(card2, trump_suit, trump_level)

    # Both trump: compare trump ranks
    if card1_is_trump and card2_is_trump:
        rank1 = trump_rank(card1, trump_suit, trump_level)
        rank2 = trump_rank(card2, trump_suit, trump_level)
        if rank1 > rank2:
            return 1
        elif rank1 < rank2:
            return -1
        else:
            return 0

    # Only card1 is trump
    if card1_is_trump:
        return 1

    # Only card2 is trump
    if card2_is_trump:
        return -1

    # Both non-trump: must be in same suit to compare
    if card1.suit != card2.suit:
        return 0  # Can't compare different suits

    rank1 = non_trump_rank(card1)
    rank2 = non_trump_rank(card2)
    if rank1 > rank2:
        return 1
    elif rank1 < rank2:
        return -1
    else:
        return 0


def winning_card(cards: list[Card], led_suit: Suit, trump_suit: Suit, trump_level: str) -> Card:
    """Find the winning card from a list of cards played in a trick."""
    winner = cards[0]
    for card in cards[1:]:
        if compare_cards(card, winner, led_suit, trump_suit, trump_level) > 0:
            winner = card
    return winner


def trump_hierarchy_level(card: Card, trump_suit: Suit, trump_level: str) -> Optional[int]:
    """
    Get the hierarchy level for a card in trump context.
    Used for detecting consecutive pairs in trump cards.

    Returns a number representing position in trump hierarchy (higher = stronger).
    Returns None if card is not a trump.

    Hierarchy (from lowest to highest):
    0. Non-trump level cards (7♦, 7♣, 7♠ when 7 is level, hearts is trump)
    1. Trump level card (7♥ when 7 is level, hearts is trump)
    2. Captain (3♥ when hearts is trump)
    3. Lieutenant (3♦ when hearts is trump)
    ...higher levels for 5s and Jokers as needed
    """
    # Non-trump level cards
    if is_level_card(card, trump_level) and card.suit != trump_suit:
        return 0

    # Trump level card
    if is_level_card(card, trump_level) and card.suit == trump_suit:
        return 1

    # Captain and Lieutenant (these have fixed hierarchy positions regardless of current level)
    if is_captain(card, trump_suit):
        return 3
    if is_lieutenant(card, trump_suit):
        return 2

    # Other trump cards don't form special tractors
    return None
