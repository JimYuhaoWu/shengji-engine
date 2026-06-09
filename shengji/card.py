"""Card representation and utilities."""

from dataclasses import dataclass
from typing import List, Tuple

from .types import Suit, Rank


@dataclass(frozen=True)
class Card:
    """Immutable card representation."""
    suit: Suit
    rank: Rank
    deck_id: int  # 0, 1, or 2 (three decks total)

    def __str__(self) -> str:
        return f"{self.suit.value}{self.rank.value}"

    def __repr__(self) -> str:
        return f"Card({self.suit.name}, {self.rank.name}, deck={self.deck_id})"

    def __eq__(self, other) -> bool:
        """Cards are equal if they have the same suit and rank (deck_id doesn't matter)."""
        if not isinstance(other, Card):
            return NotImplemented
        return self.suit == other.suit and self.rank == other.rank

    def __hash__(self) -> int:
        return hash((self.suit, self.rank))


class Deck:
    """Standard deck generator (52 cards per color + 2 Jokers per deck)."""

    @staticmethod
    def standard_decks(num_decks: int = 3) -> List[Card]:
        """Generate num_decks standard decks (156 + 6 Jokers = 162 cards total)."""
        cards: List[Card] = []

        for deck_id in range(num_decks):
            # Standard cards: 2-A in each suit
            for suit in [Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS, Suit.SPADES]:
                for rank in [
                    Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX,
                    Rank.SEVEN, Rank.EIGHT, Rank.NINE, Rank.TEN,
                    Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE
                ]:
                    cards.append(Card(suit, rank, deck_id))

            # Jokers: Small and Large
            cards.append(Card(Suit.JOKER, Rank.SMALL_JOKER, deck_id))
            cards.append(Card(Suit.JOKER, Rank.LARGE_JOKER, deck_id))

        return cards


def cards_are_identical(cards: List[Card]) -> bool:
    """Check if all cards in list have the same suit and rank (ignoring deck_id)."""
    if not cards:
        return False
    first = cards[0]
    return all(card.suit == first.suit and card.rank == first.rank for card in cards)


def count_identical_cards(card: Card, hand: List[Card]) -> int:
    """Count how many cards identical to `card` are in hand."""
    return sum(1 for c in hand if c.suit == card.suit and c.rank == card.rank)


def get_identical_cards(card: Card, hand: List[Card]) -> List[Card]:
    """Get all cards in hand that are identical to `card`."""
    return [c for c in hand if c.suit == card.suit and c.rank == card.rank]


def is_red_suit(suit: Suit) -> bool:
    """Check if suit is red (hearts or diamonds)."""
    return suit in (Suit.HEARTS, Suit.DIAMONDS)


def is_black_suit(suit: Suit) -> bool:
    """Check if suit is black (clubs or spades)."""
    return suit in (Suit.CLUBS, Suit.SPADES)
