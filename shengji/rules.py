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


def _get_plays_for_count(
    cards: List[Card],
    count: int,
    combination_type: TrickCombination
) -> List[Tuple[Card, ...]]:
    """Get all possible card combinations of a given count from a hand."""
    if count == 1:
        return [(c,) for c in cards]
    if count == 2:
        # Pairs or two singles
        plays = []
        for i, card1 in enumerate(cards):
            for card2 in cards[i+1:]:
                plays.append((card1, card2))
        return plays
    if count >= 3:
        # For 3+ cards, return all combinations
        from itertools import combinations
        return [combo for combo in combinations(cards, count)]
    return []


def _match_combination_structure(
    hand: List[Card],
    led_suit: Suit,
    led_type: TrickCombination,
    led_count: int,
    trump_suit: Suit,
    trump_level: str
) -> List[CardCombination]:
    """
    Get legal plays when following led suit with sufficient cards.
    Matches led combination structure in priority order.
    """
    led_suit_cards = [c for c in hand if c.suit == led_suit and not is_trump(c, trump_suit, trump_level)]
    legal_plays = []

    if led_type == TrickCombination.SINGLE:
        # Play any single of led suit
        for card in led_suit_cards:
            legal_plays.append(CardCombination((card,), TrickCombination.SINGLE))

    elif led_type == TrickCombination.PAIR:
        # Try to play pair, else two singles
        pairs_attempted = False
        for card in led_suit_cards:
            if count_identical_cards(card, led_suit_cards) >= 2:
                pair = tuple(get_identical_cards(card, led_suit_cards)[:2])
                pairs_attempted = True
                if CardCombination(pair, TrickCombination.PAIR) not in legal_plays:
                    legal_plays.append(CardCombination(pair, TrickCombination.PAIR))

        if not pairs_attempted:
            # Play two singles (only if pair not found)
            from itertools import combinations
            for combo in combinations(led_suit_cards, 2):
                legal_plays.append(CardCombination(combo, TrickCombination.SINGLE))

    elif led_type == TrickCombination.TRIO:
        # Try: trio, else pair+single, else three singles
        trio_attempted = False
        for card in led_suit_cards:
            if count_identical_cards(card, led_suit_cards) >= 3:
                trio = tuple(get_identical_cards(card, led_suit_cards)[:3])
                trio_attempted = True
                if CardCombination(trio, TrickCombination.TRIO) not in legal_plays:
                    legal_plays.append(CardCombination(trio, TrickCombination.TRIO))

        if not trio_attempted:
            # Try pair + single
            pair_attempted = False
            for card in led_suit_cards:
                if count_identical_cards(card, led_suit_cards) >= 2:
                    pair = get_identical_cards(card, led_suit_cards)[:2]
                    pair_attempted = True
                    remaining = [c for c in led_suit_cards if c not in pair or led_suit_cards.count(c) > pair.count(c)]
                    for single in remaining:
                        if single not in pair:
                            play = tuple(pair + [single])
                            if CardCombination(play, TrickCombination.SINGLE) not in legal_plays:
                                legal_plays.append(CardCombination(play, TrickCombination.SINGLE))

            if not pair_attempted:
                # Play three singles
                from itertools import combinations
                for combo in combinations(led_suit_cards, 3):
                    legal_plays.append(CardCombination(combo, TrickCombination.SINGLE))

    elif led_type == TrickCombination.TRACTOR:
        # Try: tractor, else two pairs, else pair+two singles, else four singles
        tractor = detect_consecutive_pairs(led_suit_cards, led_suit, trump_suit, trump_level)
        if tractor:
            legal_plays.append(CardCombination(tuple(tractor), TrickCombination.TRACTOR))
        else:
            # Try two pairs
            pair_count = 0
            pairs = []
            for card in led_suit_cards:
                if count_identical_cards(card, led_suit_cards) >= 2:
                    pair = tuple(get_identical_cards(card, led_suit_cards)[:2])
                    if all(p not in pairs for p in pair):  # Avoid duplicate pairs
                        pairs.append(pair)
                        pair_count += 1

            if pair_count >= 2:
                # Found two pairs - add them
                two_pairs = tuple(pairs[0] + pairs[1])
                legal_plays.append(CardCombination(two_pairs, TrickCombination.SINGLE))
            else:
                # Try pair + two singles
                pair_attempted = False
                for card in led_suit_cards:
                    if count_identical_cards(card, led_suit_cards) >= 2:
                        pair = get_identical_cards(card, led_suit_cards)[:2]
                        pair_attempted = True
                        remaining = [c for c in led_suit_cards if c not in pair]
                        from itertools import combinations
                        for singles_combo in combinations(remaining, 2):
                            play = tuple(pair + list(singles_combo))
                            if CardCombination(play, TrickCombination.SINGLE) not in legal_plays:
                                legal_plays.append(CardCombination(play, TrickCombination.SINGLE))

                if not pair_attempted:
                    # Play four singles
                    from itertools import combinations
                    for combo in combinations(led_suit_cards, 4):
                        legal_plays.append(CardCombination(combo, TrickCombination.SINGLE))

    elif led_type == TrickCombination.LIMO:
        # Try: limo, else two trios, else trio+pair+single, else tractor+two singles,
        # else two pairs+two singles, else pair+four singles, else six singles
        limo = detect_consecutive_trios(led_suit_cards, led_suit, trump_suit, trump_level)
        if limo:
            legal_plays.append(CardCombination(tuple(limo), TrickCombination.LIMO))
        else:
            # Try two trios
            trios = []
            for card in led_suit_cards:
                if count_identical_cards(card, led_suit_cards) >= 3:
                    trio = tuple(get_identical_cards(card, led_suit_cards)[:3])
                    if trio not in trios:
                        trios.append(trio)

            if len(trios) >= 2:
                two_trios = tuple(trios[0] + trios[1])
                legal_plays.append(CardCombination(two_trios, TrickCombination.SINGLE))
            else:
                # Try trio + pair + single
                trio_attempted = False
                for card in led_suit_cards:
                    if count_identical_cards(card, led_suit_cards) >= 3:
                        trio = get_identical_cards(card, led_suit_cards)[:3]
                        trio_attempted = True
                        remaining = [c for c in led_suit_cards if c not in trio]

                        for card2 in remaining:
                            if count_identical_cards(card2, remaining) >= 2:
                                pair = tuple(get_identical_cards(card2, remaining)[:2])
                                remaining2 = [c for c in remaining if c not in pair]
                                for single in remaining2:
                                    play = tuple(list(trio) + list(pair) + [single])
                                    if CardCombination(play, TrickCombination.SINGLE) not in legal_plays:
                                        legal_plays.append(CardCombination(play, TrickCombination.SINGLE))

                if not trio_attempted:
                    # Try tractor + two singles
                    tractor = detect_consecutive_pairs(led_suit_cards, led_suit, trump_suit, trump_level)
                    if tractor:
                        remaining = [c for c in led_suit_cards if c not in tractor]
                        from itertools import combinations
                        for singles_combo in combinations(remaining, 2):
                            play = tuple(tractor + list(singles_combo))
                            if CardCombination(play, TrickCombination.SINGLE) not in legal_plays:
                                legal_plays.append(CardCombination(play, TrickCombination.SINGLE))
                    else:
                        # Try two pairs + two singles
                        pairs = []
                        for card in led_suit_cards:
                            if count_identical_cards(card, led_suit_cards) >= 2:
                                pair = tuple(get_identical_cards(card, led_suit_cards)[:2])
                                if pair not in pairs:
                                    pairs.append(pair)

                        if len(pairs) >= 2:
                            two_pairs = pairs[0] + pairs[1]
                            remaining = [c for c in led_suit_cards if c not in two_pairs]
                            from itertools import combinations
                            for singles_combo in combinations(remaining, 2):
                                play = tuple(two_pairs + tuple(singles_combo))
                                if CardCombination(play, TrickCombination.SINGLE) not in legal_plays:
                                    legal_plays.append(CardCombination(play, TrickCombination.SINGLE))
                        else:
                            # Try pair + four singles
                            pair_attempted = False
                            for card in led_suit_cards:
                                if count_identical_cards(card, led_suit_cards) >= 2:
                                    pair = get_identical_cards(card, led_suit_cards)[:2]
                                    pair_attempted = True
                                    remaining = [c for c in led_suit_cards if c not in pair]
                                    from itertools import combinations
                                    for singles_combo in combinations(remaining, 4):
                                        play = tuple(pair + list(singles_combo))
                                        if CardCombination(play, TrickCombination.SINGLE) not in legal_plays:
                                            legal_plays.append(CardCombination(play, TrickCombination.SINGLE))

                            if not pair_attempted:
                                # Play six singles
                                from itertools import combinations
                                for combo in combinations(led_suit_cards, 6):
                                    legal_plays.append(CardCombination(combo, TrickCombination.SINGLE))

    return legal_plays


def get_legal_plays_when_following(
    hand: List[Card],
    led_combination: CardCombination,
    trump_suit: Suit,
    trump_level: str
) -> List[CardCombination]:
    """
    Get legal plays when following a trick.
    Priority 1: Follow the led suit with matching structure (if sufficient cards).
    Priority 2: If insufficient led suit cards, play all led suit + fill with non-trump.
    Priority 3: If no led suit, can trump (exact match) or play other cards.
    """
    led_suit = led_combination.suit()
    led_type = led_combination.combination_type
    led_count = led_combination.count()

    # Get all led suit cards (non-trump)
    led_suit_cards = [c for c in hand if c.suit == led_suit and not is_trump(c, trump_suit, trump_level)]

    # Case 1: Have the led suit
    if led_suit_cards:
        # Check if sufficient to match led combination
        if len(led_suit_cards) >= led_count:
            # SUFFICIENT: Match the led combination structure
            return _match_combination_structure(hand, led_suit, led_type, led_count, trump_suit, trump_level)
        else:
            # INSUFFICIENT: Must play all led suit cards + fill with non-trump cards
            # These plays can NEVER WIN (no matched structure)
            legal_plays = []
            remaining_slots = led_count - len(led_suit_cards)

            # Get non-trump, non-led-suit cards to fill
            fill_cards = [c for c in hand if c.suit != led_suit and not is_trump(c, trump_suit, trump_level)]

            if len(fill_cards) >= remaining_slots:
                from itertools import combinations
                for fill_combo in combinations(fill_cards, remaining_slots):
                    play = tuple(led_suit_cards + list(fill_combo))
                    legal_plays.append(CardCombination(play, TrickCombination.SINGLE))
            else:
                # Not enough non-trump cards to fill - can use trump to fill
                all_other_cards = [c for c in hand if c.suit != led_suit and c not in led_suit_cards]
                if len(all_other_cards) >= remaining_slots:
                    from itertools import combinations
                    for fill_combo in combinations(all_other_cards, remaining_slots):
                        play = tuple(led_suit_cards + list(fill_combo))
                        legal_plays.append(CardCombination(play, TrickCombination.SINGLE))

            return legal_plays

    # Case 2: Don't have led suit - can trump (exact match) or play other cards
    legal_plays = []

    # Try to find trump plays with exact matching combination
    hand_combos = get_card_combinations(hand, trump_suit, trump_level)
    for combo in hand_combos:
        # Check if this combo matches led type exactly
        if combo.combination_type == led_type and combo.count() == led_count:
            # Check if all cards are trump
            if all(is_trump(c, trump_suit, trump_level) for c in combo.cards):
                legal_plays.append(combo)

    # If no trump plays, or can also play non-trump
    # Add any non-trump plays of the right count
    non_trump_cards = [c for c in hand if not is_trump(c, trump_suit, trump_level)]
    if non_trump_cards:
        from itertools import combinations
        for combo_cards in combinations(non_trump_cards, led_count):
            legal_plays.append(CardCombination(combo_cards, TrickCombination.SINGLE))

    return legal_plays if legal_plays else [CardCombination((hand[0],), TrickCombination.SINGLE)]
