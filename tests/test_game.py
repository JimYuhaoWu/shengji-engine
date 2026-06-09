"""Tests for Game orchestrator."""

import pytest
from shengji.game import Game
from shengji.types import GamePhase, ActionType


class TestGame:
    """Test Game class."""

    def test_game_creation(self):
        """Can create a Game."""
        game = Game(num_players=6)
        assert game.num_players == 6

    def test_game_only_supports_6_players(self):
        """Game only supports 6 players."""
        with pytest.raises(ValueError):
            Game(num_players=4)
        with pytest.raises(ValueError):
            Game(num_players=5)

    def test_reset_creates_initial_state(self):
        """reset() creates a valid initial game state."""
        game = Game(num_players=6)
        state = game.reset(dealer_id=0)

        assert state.phase == GamePhase.DEALING
        assert state.current_player == 0
        assert state.dealer_id == 0
        assert state.is_valid()

    def test_reset_deals_one_round(self):
        """reset() deals the first round (one card per player) under parallel dealing."""
        game = Game(num_players=6)
        state = game.reset()

        # After reset, exactly one round dealt: 1 card per player
        assert state.cards_dealt == 1
        for i, hand in enumerate(state.hands):
            assert len(hand) == 1, f"Player {i} has {len(hand)} cards, expected 1"

        # All 162 cards accounted for between hands, kitty, and remaining deck
        total = sum(len(hand) for hand in state.hands) + len(state.kitty) + len(state.deck)
        assert total == 162

    def test_full_dealing_distributes_correctly(self):
        """Dealing all 26 rounds gives 26 cards/player, 6 to kitty, 162 total."""
        game = Game(num_players=6)
        state = game.reset()

        # Auto-deal (passing) until all 26 cards are dealt and formal bidding begins
        guard = 0
        while state.cards_dealt < 26 and guard < 200:
            # Pass each round so dealing continues without bids
            pass_action = next(
                (a for a in state.legal_actions if a.action_type == ActionType.PASS_TRUMP),
                None,
            )
            state, _ = game.step(state, pass_action)
            guard += 1

        # Each player should now have 26 cards
        for i, hand in enumerate(state.hands):
            assert len(hand) == 26, f"Player {i} has {len(hand)} cards, expected 26"

        # Kitty should have 6 cards
        assert len(state.kitty) == 6

        # Total should be 162 (26*6 + 6)
        total = sum(len(hand) for hand in state.hands) + len(state.kitty)
        assert total == 162

        # After all cards dealt, formal bidding phase has begun
        assert state.formal_bidding_started
        assert state.phase == GamePhase.TRUMP_DECLARATION

    def test_reset_initializes_all_players_at_r1_2(self):
        """reset() sets all players to R1:2 level."""
        game = Game(num_players=6)
        state = game.reset()

        assert state.player_levels == ("R1:2", "R1:2", "R1:2", "R1:2", "R1:2", "R1:2")

    def test_reset_with_different_dealers(self):
        """reset() works with different dealer ids."""
        game = Game(num_players=6)
        for dealer_id in range(6):
            state = game.reset(dealer_id=dealer_id)
            assert state.dealer_id == dealer_id
            assert state.is_valid()

    def test_reset_legal_actions_available(self):
        """reset() produces legal actions."""
        game = Game(num_players=6)
        state = game.reset()

        assert state.legal_actions is not None
        assert len(state.legal_actions) > 0

    def test_reset_shuffle_differs_on_multiple_calls(self):
        """reset() deals random cards (with high probability, cards differ between resets)."""
        game = Game(num_players=6)

        state1 = game.reset()
        state2 = game.reset()

        # With 162 cards, it's virtually impossible for two shuffles to be identical
        hands1 = state1.hands[0]
        hands2 = state2.hands[0]

        # At least they should be different
        assert hands1 != hands2

    def test_trump_suit_initially_none(self):
        """Trump suit is None before declaration."""
        game = Game(num_players=6)
        state = game.reset()

        assert state.trump_suit is None

    def test_trump_level_initially_2(self):
        """Trump level is initially "2"."""
        game = Game(num_players=6)
        state = game.reset()

        assert state.trump_level == "2"
