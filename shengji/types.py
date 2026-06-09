"""Game enums and type definitions."""

from dataclasses import dataclass
from enum import Enum, auto


class Suit(Enum):
    """Card suits."""
    HEARTS = "H"
    DIAMONDS = "D"
    CLUBS = "C"
    SPADES = "S"
    JOKER = "J"  # for Jokers


class Rank(Enum):
    """Card ranks."""
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "T"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    ACE = "A"
    SMALL_JOKER = "Js"
    LARGE_JOKER = "Jl"


class GamePhase(Enum):
    """Game phase states."""
    DEALING = auto()
    TRUMP_DECLARATION = auto()
    KITTY = auto()
    CALL_HELPER = auto()
    TRICK_PLAYING = auto()
    SCORING = auto()


class ActionType(Enum):
    """Types of actions a player can take."""
    BID_TRUMP = auto()           # Bid level cards for trump declaration
    PASS_TRUMP = auto()          # Pass during trump declaration
    PLAY_CARDS = auto()          # Play cards in trick
    TAKE_KITTY = auto()          # Dealer takes kitty cards
    CALL_HELPER = auto()         # Dealer calls a specific card


@dataclass(frozen=True)
class TrumpBid:
    """Represents a trump declaration bid."""
    count: int                    # 1, 2, or 3
    suit: "Suit"                  # Suit being proposed
    bidder_id: int                # Player who made the bid


@dataclass(frozen=True)
class Action:
    """Represents a single action."""
    action_type: ActionType
    cards: tuple = ()             # Cards involved (for PLAY_CARDS, BID_TRUMP)
    trump_bid: "TrumpBid | None" = None  # Trump bid (for BID_TRUMP)
    target_suit: "Suit | None" = None  # Target suit (for DECLARE_TRUMP)
    target_card: "Card | None" = None  # Target card (for CALL_HELPER)

    def __hash__(self):
        return hash((self.action_type, self.cards, self.target_suit, self.target_card))


class TrickCombination(Enum):
    """Types of card combinations in tricks."""
    SINGLE = auto()
    PAIR = auto()
    TRIO = auto()
    TRACTOR = auto()
    LIMO = auto()
    MULTI = auto()  # Multiple components (pair+single, etc.)
