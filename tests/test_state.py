"""Tests for GameState."""

import pytest
from shengji.card import Card
from shengji.types import Suit, Rank, GamePhase
from shengji.state import GameState


class TestGameState:
    """Test GameState dataclass."""

    def test_state_creation(self):
        """Can create a valid GameState."""
        state = GameState(
            phase=GamePhase.DEALING,
            current_player=0,
            dealer_id=0,
            hands=tuple(tuple() for _ in range(6)),
            kitty=(),
        )
        assert state.phase == GamePhase.DEALING
        assert state.current_player == 0

    def test_state_is_immutable(self):
        """GameState cannot be modified after creation."""
        state = GameState(
            phase=GamePhase.DEALING,
            current_player=0,
            dealer_id=0,
            hands=tuple(tuple() for _ in range(6)),
            kitty=(),
        )
        with pytest.raises(AttributeError):
            state.current_player = 1

    def test_copy_creates_new_state(self):
        """copy() creates a new GameState with updated fields."""
        state1 = GameState(
            phase=GamePhase.DEALING,
            current_player=0,
            dealer_id=0,
            hands=tuple(tuple() for _ in range(6)),
            kitty=(),
        )
        state2 = state1.copy(current_player=1)

        assert state1.current_player == 0
        assert state2.current_player == 1
        assert state1.phase == state2.phase
        assert state1 is not state2

    def test_copy_preserves_other_fields(self):
        """copy() preserves fields not specified in kwargs."""
        cards = tuple(Card(Suit.HEARTS, Rank.ACE, i) for i in range(3))
        state1 = GameState(
            phase=GamePhase.DEALING,
            current_player=0,
            dealer_id=2,
            hands=tuple(tuple() for _ in range(6)),
            kitty=cards,
            trump_level="7",
        )
        state2 = state1.copy(phase=GamePhase.TRUMP_DECLARATION)

        assert state2.dealer_id == 2
        assert state2.kitty == cards
        assert state2.trump_level == "7"
        assert state2.phase == GamePhase.TRUMP_DECLARATION

    def test_is_valid_empty_state(self):
        """Empty state with 6 players is valid."""
        state = GameState(
            phase=GamePhase.DEALING,
            current_player=0,
            dealer_id=0,
            hands=tuple(tuple() for _ in range(6)),
            kitty=(),
        )
        assert state.is_valid()

    def test_is_valid_wrong_player_count(self):
        """State with wrong number of hands is invalid."""
        state = GameState(
            phase=GamePhase.DEALING,
            current_player=0,
            dealer_id=0,
            hands=tuple(tuple() for _ in range(5)),  # Only 5 hands!
            kitty=(),
        )
        assert not state.is_valid()

    def test_is_valid_with_cards(self):
        """State with valid hands and kitty is valid."""
        cards = tuple(Card(Suit.HEARTS, Rank.ACE, i) for i in range(3))
        hands = tuple(
            (Card(Suit.HEARTS, Rank.KING, 0),) for _ in range(6)
        )
        state = GameState(
            phase=GamePhase.DEALING,
            current_player=0,
            dealer_id=0,
            hands=hands,
            kitty=cards,
        )
        assert state.is_valid()
