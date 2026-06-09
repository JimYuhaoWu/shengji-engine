"""Main game engine orchestrator."""

import random
from typing import List, Tuple
from .card import Card, Deck
from .level import LEVEL_SEQ
from .state import GameState
from .types import GamePhase, Suit, Rank, Action, ActionType
from .trump import is_level_card


class Game:
    """Six-player Sheng Ji game engine."""

    def __init__(self, num_players: int = 6):
        if num_players != 6:
            raise ValueError("Only 6-player games are supported")
        self.num_players = num_players

    def reset(self, dealer_id: int = 0) -> GameState:
        """Start a new game.

        Args:
            dealer_id: which player is the dealer (0-5)

        Returns:
            Initial GameState in DEALING phase
        """
        # Deal cards
        deck = Deck.standard_decks(3)
        random.shuffle(deck)

        hands: List[List[Card]] = [[] for _ in range(6)]
        for i, card in enumerate(deck[:156]):  # 6 × 26 = 156 cards
            hands[i % 6].append(card)

        # Remaining 6 cards are kitty
        kitty = deck[156:162]

        # Convert hands to sorted tuples (for consistency)
        hands_tuple = tuple(tuple(sorted(hand, key=lambda c: (c.suit.value, c.rank.value))) for hand in hands)
        kitty_tuple = tuple(kitty)

        # Initialize player levels
        player_levels = tuple(LEVEL_SEQ[10] for _ in range(6))  # All start at R1:2

        # Create initial state
        state = GameState(
            phase=GamePhase.DEALING,
            current_player=0,  # Player 0 starts bidding
            dealer_id=dealer_id,
            hands=hands_tuple,
            kitty=kitty_tuple,
            trump_suit=None,
            trump_level="2",
            trump_declarations=(),
            trump_declared_by=None,
            helper_card=None,
            revealed_helpers=(),
            current_trick=(),
            tricks_won=(),
            player_levels=player_levels,
            scores=tuple(0 for _ in range(6)),
            legal_actions=self._get_legal_actions_dealing(hands_tuple),
        )

        return state

    def _get_legal_actions_dealing(self, hands: Tuple[Tuple[Card, ...], ...]) -> Tuple[Action, ...]:
        """Get legal trump declaration actions during DEALING phase."""
        player_hand = hands[0]  # Start with player 0
        actions: List[Action] = []

        # Can declare any level card in hand
        for card in player_hand:
            if is_level_card(card, card.rank.value):
                actions.append(Action(
                    action_type=ActionType.DECLARE_TRUMP,
                    cards=(card,),
                    target_suit=card.suit,
                ))

        # Can also pass
        actions.append(Action(action_type=ActionType.DECLARE_TRUMP, cards=(), target_suit=None))

        return tuple(actions)

    def step(self, action: Action) -> Tuple[GameState, dict]:
        """Execute one action and return new state + info.

        Args:
            action: Action to execute

        Returns:
            (new_state, info_dict)
        """
        # This is a placeholder - full implementation will handle all phases
        raise NotImplementedError("Game.step() not yet implemented")
