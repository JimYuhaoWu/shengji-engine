"""Immutable game state representation."""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from .card import Card
from .types import Suit, GamePhase, Action, TrumpBid


@dataclass(frozen=True)
class GameState:
    """Represents the complete immutable game state.

    All public functions return a new GameState; the old one is never modified.
    """
    # Phase and players
    phase: GamePhase
    current_player: int  # 0-5
    dealer_id: int

    # Cards
    hands: Tuple[Tuple[Card, ...], ...]  # hands[i] = player i's cards
    kitty: Tuple[Card, ...]  # 6 cards during KITTY phase
    cards_dealt: int = 0  # Number of cards dealt to each player (0-26)
    deck: Tuple[Card, ...] = ()  # Remaining cards to deal (initially all 162 cards)

    # Trump
    trump_suit: Optional[Suit] = None
    trump_level: str = "2"  # "2", "4", "6", "7", "8", "9", "10", "J", "Q", "K", "A"
    trump_locked: bool = False  # True when someone bids 3 of a level

    # Trump declaration bidding (during TRUMP_DECLARATION phase)
    current_trump_bid: Optional[TrumpBid] = None  # Highest bid so far
    passed_players: Tuple[int, ...] = ()  # Players who formally passed (after dealing done)
    trump_bids_history: Tuple[TrumpBid, ...] = ()  # All bids made in order
    formal_bidding_started: bool = False  # True after all 26 cards dealt, when formal passing begins

    # Buried cards (during and after KITTY phase)
    buried_cards: Tuple[Card, ...] = ()  # 6 cards buried by dealer, revealed at end
    kitty_multiplier: int = 1  # 2 x (max-component count of the last trick's winning play)

    # Helper card (identified by rank and suit only, ignoring deck_id)
    called_rank: Optional[str] = None  # Rank of called card (e.g., "5", "K")
    called_suit: Optional[Suit] = None  # Suit of called card
    helper_players: Tuple[int, ...] = ()  # player ids who are helpers (0, 1, or 2)
    helpers_locked: bool = False  # True once the helper set is final (2 found, or a sole helper)

    # Trick tracking
    current_trick: Tuple[Tuple[int, Tuple[Card, ...]], ...] = ()  # [(player_id, cards), ...]
    tricks_won: Tuple[Tuple[int, Tuple[Card, ...]], ...] = ()  # [(winner_id, cards), ...] all tricks

    # Player levels
    player_levels: Tuple[str, ...] = ()  # "R1:2", etc.

    # Scoring
    scores: Tuple[int, ...] = ()  # current scoring card total per player?

    # Legal actions (pre-computed)
    legal_actions: Tuple[Action, ...] = ()

    def copy(self, **kwargs) -> "GameState":
        """Create a new GameState with updated fields."""
        # Get current state as dict
        state_dict = {
            'phase': self.phase,
            'current_player': self.current_player,
            'dealer_id': self.dealer_id,
            'hands': self.hands,
            'kitty': self.kitty,
            'cards_dealt': self.cards_dealt,
            'deck': self.deck,
            'trump_suit': self.trump_suit,
            'trump_level': self.trump_level,
            'trump_locked': self.trump_locked,
            'current_trump_bid': self.current_trump_bid,
            'passed_players': self.passed_players,
            'trump_bids_history': self.trump_bids_history,
            'formal_bidding_started': self.formal_bidding_started,
            'buried_cards': self.buried_cards,
            'kitty_multiplier': self.kitty_multiplier,
            'called_rank': self.called_rank,
            'called_suit': self.called_suit,
            'helper_players': self.helper_players,
            'helpers_locked': self.helpers_locked,
            'current_trick': self.current_trick,
            'tricks_won': self.tricks_won,
            'player_levels': self.player_levels,
            'scores': self.scores,
            'legal_actions': self.legal_actions,
        }
        # Update with provided kwargs
        state_dict.update(kwargs)
        return GameState(**state_dict)

    def is_valid(self) -> bool:
        """Check basic consistency of game state."""
        # Must have 6 players
        if len(self.hands) != 6:
            return False
        # Hands must be tuples of cards
        for hand in self.hands:
            if not isinstance(hand, tuple):
                return False
            for card in hand:
                if not isinstance(card, Card):
                    return False
        # Kitty must be tuple of cards
        if not isinstance(self.kitty, tuple):
            return False
        for card in self.kitty:
            if not isinstance(card, Card):
                return False
        # Player count checks
        if len(self.player_levels) > 0 and len(self.player_levels) != 6:
            return False
        return True
