"""Card combinations and legal action generation.

Combinations:
- Single: 1 card
- Pair: 2 identical cards
- Trio: 3 identical cards
- Tractor: 2+ consecutive pairs of same suit
- Limo (钢板/豪车): 2+ consecutive trios of same suit
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
from .card import Card, cards_are_identical, count_identical_cards, get_identical_cards, is_red_suit
from .types import Suit, Rank, TrickCombination
from .trump import is_trump, is_level_card, is_captain, is_lieutenant, trump_hierarchy_level


# Non-trump suit rank ordering (highest to lowest)
NON_TRUMP_RANK_ORDER = [
    Rank.ACE, Rank.KING, Rank.QUEEN, Rank.JACK, Rank.TEN,
    Rank.NINE, Rank.EIGHT, Rank.SEVEN, Rank.SIX, Rank.FIVE,
    Rank.FOUR, Rank.THREE, Rank.TWO
]


def get_trump_suit_rank_order(trump_suit: Suit, trump_level: str) -> List[Rank]:
    """
    Get the rank ordering for trump suit cards.
    Trump level cards are removed from their normal position and placed at the top.
    Jokers are excluded (they're always trump and handle separately).
    """
    trump_level_rank = Rank(trump_level)
    result = []
    for rank in NON_TRUMP_RANK_ORDER:
        if rank != trump_level_rank:
            result.append(rank)
    return result


def get_rank_order_for_suit(
    suit: Suit,
    trump_suit: Suit,
    trump_level: str
) -> List[Rank]:
    """Get rank ordering for cards of a given suit (used for detecting consecutive pairs/trios)."""
    if suit == trump_suit:
        return get_trump_suit_rank_order(trump_suit, trump_level)
    else:
        return NON_TRUMP_RANK_ORDER[:]


def get_rank_index(
    rank: Rank,
    suit: Suit,
    trump_suit: Suit,
    trump_level: str
) -> Optional[int]:
    """
    Get the index of a rank in its suit's ordering.
    Returns None if the rank is level card (it's removed from the sequence).
    """
    if is_level_card(Card(suit, rank, 0), trump_level):
        return None
    rank_order = get_rank_order_for_suit(suit, trump_suit, trump_level)
    try:
        return rank_order.index(rank)
    except ValueError:
        return None


@dataclass(frozen=True)
class CardCombination:
    """Represents a combination of cards (single, pair, trio, tractor, limo)."""
    cards: Tuple[Card, ...]
    combination_type: TrickCombination

    def __post_init__(self):
        if not self.cards:
            raise ValueError("Combination must have at least one card")

    def count(self) -> int:
        """Return the number of cards in this combination."""
        return len(self.cards)

    def suit(self) -> Suit:
        """Return the suit (all cards in combination have same suit)."""
        return self.cards[0].suit

    def is_valid(self) -> bool:
        """Check if combination is valid."""
        if not self.cards:
            return False

        suit = self.cards[0].suit
        if not all(c.suit == suit for c in self.cards):
            return False

        if self.combination_type == TrickCombination.SINGLE:
            return len(self.cards) == 1
        elif self.combination_type == TrickCombination.PAIR:
            return len(self.cards) == 2 and cards_are_identical(list(self.cards))
        elif self.combination_type == TrickCombination.TRIO:
            return len(self.cards) == 3 and cards_are_identical(list(self.cards))
        elif self.combination_type == TrickCombination.TRACTOR:
            return len(self.cards) % 2 == 0 and len(self.cards) >= 4
        elif self.combination_type == TrickCombination.LIMO:
            return len(self.cards) % 3 == 0 and len(self.cards) >= 6
        else:
            return True


def detect_consecutive_pairs(
    cards: List[Card],
    suit: Suit,
    trump_suit: Suit,
    trump_level: str
) -> Optional[List[Card]]:
    """
    Detect if cards form a tractor (consecutive pairs).
    Returns sorted list of cards forming tractor, or None if not a valid tractor.
    """
    # Filter to only cards of the given suit
    suited_cards = [c for c in cards if c.suit == suit]
    if len(suited_cards) < 4:  # At least 2 pairs
        return None

    # Group by rank and count
    rank_groups = {}
    for card in suited_cards:
        if card.rank not in rank_groups:
            rank_groups[card.rank] = []
        rank_groups[card.rank].append(card)

    # Check that each rank has at least 2 cards
    for rank, group in rank_groups.items():
        if len(group) < 2:
            return None

    # Check consecutiveness
    ranks = list(rank_groups.keys())
    rank_order = get_rank_order_for_suit(suit, trump_suit, trump_level)

    # Get indices
    indices = [get_rank_index(r, suit, trump_suit, trump_level) for r in ranks]
    if any(idx is None for idx in indices):  # Level cards not allowed in tractors
        return None

    # Sort by index
    indices.sort()
    # Check they are consecutive
    for i in range(len(indices) - 1):
        if indices[i + 1] - indices[i] != 1:
            return None

    # Return one pair from each consecutive rank
    result = []
    for rank in ranks:
        pair_cards = rank_groups[rank][:2]
        result.extend(pair_cards)

    return result


def detect_trump_hierarchy_tractor(
    cards: List[Card],
    trump_suit: Suit,
    trump_level: str
) -> Optional[List[Card]]:
    """
    Detect if trump cards form a tractor based on trump hierarchy levels.

    Example: When 7 is level and hearts is trump:
    - 7♥ + 7♥ + 7♦ + 7♦ (trump level pair + non-trump level pair)
    - 7♥ + 7♥ + 3♦ + 3♦ (trump level pair + lieutenant pair)
    - 3♥ + 3♥ + 3♦ + 3♦ (captain pair + lieutenant pair, only if 3 is not level)
    """
    # Filter to only trump cards that have hierarchy levels
    trump_cards = []
    for card in cards:
        if is_trump(card, trump_suit, trump_level):
            level = trump_hierarchy_level(card, trump_suit, trump_level)
            if level is not None:
                trump_cards.append((card, level))

    if len(trump_cards) < 4:  # At least 2 pairs
        return None

    # Group by hierarchy level and count
    level_groups = {}
    for card, level in trump_cards:
        if level not in level_groups:
            level_groups[level] = []
        level_groups[level].append(card)

    # Check that each level has at least 2 cards
    for level, group in level_groups.items():
        if len(group) < 2:
            return None

    # Check consecutiveness of levels
    levels = sorted(level_groups.keys())
    for i in range(len(levels) - 1):
        if levels[i + 1] - levels[i] != 1:
            return None

    # Return one pair from each level
    result = []
    for level in levels:
        pair_cards = level_groups[level][:2]
        result.extend(pair_cards)

    return result


def detect_consecutive_trios(
    cards: List[Card],
    suit: Suit,
    trump_suit: Suit,
    trump_level: str
) -> Optional[List[Card]]:
    """
    Detect if cards form a limo (consecutive trios).
    Returns sorted list of cards forming limo, or None if not a valid limo.
    """
    # Filter to only cards of the given suit
    suited_cards = [c for c in cards if c.suit == suit]
    if len(suited_cards) < 6:  # At least 2 trios
        return None

    # Group by rank and count
    rank_groups = {}
    for card in suited_cards:
        if card.rank not in rank_groups:
            rank_groups[card.rank] = []
        rank_groups[card.rank].append(card)

    # Check that each rank has at least 3 cards
    for rank, group in rank_groups.items():
        if len(group) < 3:
            return None

    # Check consecutiveness
    ranks = list(rank_groups.keys())
    rank_order = get_rank_order_for_suit(suit, trump_suit, trump_level)

    # Get indices
    indices = [get_rank_index(r, suit, trump_suit, trump_level) for r in ranks]
    if any(idx is None for idx in indices):  # Level cards not allowed in limos
        return None

    # Sort by index
    indices.sort()
    # Check they are consecutive
    for i in range(len(indices) - 1):
        if indices[i + 1] - indices[i] != 1:
            return None

    # Return one trio from each consecutive rank
    result = []
    for rank in ranks:
        trio_cards = rank_groups[rank][:3]
        result.extend(trio_cards)

    return result


def get_card_combinations(
    cards: List[Card],
    trump_suit: Suit,
    trump_level: str
) -> List[CardCombination]:
    """
    Get all valid card combinations from a list of cards.
    This is used when leading a trick (all combinations are legal).
    """
    combinations = []

    # Singles
    for card in cards:
        combinations.append(CardCombination((card,), TrickCombination.SINGLE))

    # Pairs
    for card in cards:
        count = count_identical_cards(card, cards)
        if count >= 2:
            identical = get_identical_cards(card, cards)[:2]
            combo = CardCombination(tuple(identical), TrickCombination.PAIR)
            if combo not in combinations:
                combinations.append(combo)

    # Trios
    for card in cards:
        count = count_identical_cards(card, cards)
        if count >= 3:
            identical = get_identical_cards(card, cards)[:3]
            combo = CardCombination(tuple(identical), TrickCombination.TRIO)
            if combo not in combinations:
                combinations.append(combo)

    # Tractors (per suit)
    for suit in [Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS, Suit.SPADES]:
        tractor = detect_consecutive_pairs(cards, suit, trump_suit, trump_level)
        if tractor:
            combinations.append(CardCombination(tuple(tractor), TrickCombination.TRACTOR))

    # Trump hierarchy tractors (cards with different ranks but consecutive hierarchy levels)
    trump_tractor = detect_trump_hierarchy_tractor(cards, trump_suit, trump_level)
    if trump_tractor:
        combinations.append(CardCombination(tuple(trump_tractor), TrickCombination.TRACTOR))

    # Limos (per suit)
    for suit in [Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS, Suit.SPADES]:
        limo = detect_consecutive_trios(cards, suit, trump_suit, trump_level)
        if limo:
            combinations.append(CardCombination(tuple(limo), TrickCombination.LIMO))

    return combinations


def can_follow_suit(
    hand: List[Card],
    led_suit: Suit,
    trump_suit: Suit,
    trump_level: str
) -> bool:
    """Check if player has any cards of the led suit."""
    return any(c.suit == led_suit and not is_trump(c, trump_suit, trump_level) for c in hand)


def can_trump(hand: List[Card], trump_suit: Suit, trump_level: str) -> bool:
    """Check if player has any trump cards."""
    return any(is_trump(c, trump_suit, trump_level) for c in hand)


def get_legal_plays_when_following(
    hand: List[Card],
    led_combination: CardCombination,
    trump_suit: Suit,
    trump_level: str
) -> List[CardCombination]:
    """
    Get legal plays when following a trick.
    Priority 1: Follow the led suit with matching structure.
    Priority 2: If can't follow, can trump or not trump.
    """
    led_suit = led_combination.suit()
    led_type = led_combination.combination_type
    led_count = led_combination.count()

    # Check if we have the led suit (non-trump)
    has_led_suit = can_follow_suit(hand, led_suit, trump_suit, trump_level)

    if not has_led_suit:
        # Can't follow suit: choose to trump or not trump
        # For now, return all possible plays of the correct count
        legal_plays = []
        for card in hand:
            if not is_trump(card, trump_suit, trump_level):
                legal_plays.append(CardCombination((card,), TrickCombination.SINGLE))
        return legal_plays

    # Must follow suit
    led_suit_cards = [c for c in hand if c.suit == led_suit and not is_trump(c, trump_suit, trump_level)]

    # TODO: Implement combination matching for following plays
    # For now, return basic structure matching
    legal_plays = []

    if led_type == TrickCombination.SINGLE:
        # Play any single
        for card in led_suit_cards:
            legal_plays.append(CardCombination((card,), TrickCombination.SINGLE))

    elif led_type == TrickCombination.PAIR:
        # Play pair if have, else singles
        pairs_found = False
        for card in led_suit_cards:
            if count_identical_cards(card, led_suit_cards) >= 2:
                identical = get_identical_cards(card, led_suit_cards)[:2]
                combo = CardCombination(tuple(identical), TrickCombination.PAIR)
                if combo not in legal_plays:
                    legal_plays.append(combo)
                    pairs_found = True

        if not pairs_found:
            # Play two singles
            for i, card1 in enumerate(led_suit_cards):
                for card2 in led_suit_cards[i+1:]:
                    legal_plays.append(CardCombination((card1, card2), TrickCombination.SINGLE))

    else:
        # Simplified: just play any combination of right size
        for card in led_suit_cards:
            legal_plays.append(CardCombination((card,), TrickCombination.SINGLE))

    return legal_plays
