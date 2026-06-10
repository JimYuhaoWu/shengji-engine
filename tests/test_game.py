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


class TestLevelChangeScoring:
    """The live game loop must apply scoring/red-five penalties correctly.

    Regression guard: red fives captured by farmers penalize the DEALER side
    (they must not push the dealer up). This previously diverged from the
    unit-tested scoring.py due to an inverted sign in game.py.
    """

    def _state_with_trick(self, captured_cards, dealer_id=0, helpers=()):
        from shengji.card import Card  # noqa: F401
        game = Game(num_players=6)
        state = game.reset()
        return game, state.copy(
            dealer_id=dealer_id,
            helper_players=helpers,
            player_levels=("R1:2",) * 6,
            tricks_won=((1, tuple(captured_cards)),),  # player 1 (a farmer) won them
        )

    def test_red_five_penalizes_dealer(self):
        """Farmer score 200 (farmer +1) plus one ♥5 (dealer -2) => dealer -2.

        Asymmetric model: the losing dealer gets 0 from the score, so the only
        dealer movement is the -2 red-five penalty.
        """
        from shengji.card import Card
        from shengji.types import Suit, Rank

        # 19×K (190) + ♥5 (5) + ♣5 (5) = 200 points, one red (heart) five
        cards = (
            [Card(Suit.SPADES, Rank.KING, d % 3) for d in range(19)]
            + [Card(Suit.HEARTS, Rank.FIVE, 0), Card(Suit.CLUBS, Rank.FIVE, 0)]
        )
        game, state = self._state_with_trick(cards)
        new_levels = game._apply_level_changes(state)

        # Dealer moves DOWN 2 from R1:2 (0 base + -2 for the ♥5)
        assert new_levels[0] == "B2:2", f"dealer expected B2:2, got {new_levels[0]}"
        # Farmer side moves UP 1
        assert new_levels[1] == "R1:4", f"farmer expected R1:4, got {new_levels[1]}"

    def test_no_red_five_baseline(self):
        """Farmer score 200 with no red fives => dealer unchanged, farmer +1."""
        from shengji.card import Card
        from shengji.types import Suit, Rank

        # 20×K = 200 points, no fives
        cards = [Card(Suit.SPADES, Rank.KING, d % 3) for d in range(20)]
        game, state = self._state_with_trick(cards)
        new_levels = game._apply_level_changes(state)

        assert new_levels[0] == "R1:2", f"dealer expected R1:2, got {new_levels[0]}"
        assert new_levels[1] == "R1:4", f"farmer expected R1:4, got {new_levels[1]}"


class TestKittyMultiplier:
    """Buried-kitty points go to the last-trick winner x2x the winning play's
    largest component, and only count for farmers when a farmer wins it."""

    def test_max_component_count(self):
        from shengji.card import Card
        from shengji.types import Suit, Rank

        game = Game(num_players=6)
        ts, tl = Suit.HEARTS, "2"
        S, R = Suit.SPADES, Rank
        single = (Card(S, R.ACE, 0),)
        pair = (Card(S, R.KING, 0), Card(S, R.KING, 1))
        trio = (Card(S, R.KING, 0), Card(S, R.KING, 1), Card(S, R.KING, 2))
        tractor = (Card(S, R.SEVEN, 0), Card(S, R.SEVEN, 1),
                   Card(S, R.EIGHT, 0), Card(S, R.EIGHT, 1))
        pair_singles = (Card(S, R.KING, 0), Card(S, R.KING, 1),
                        Card(S, R.ACE, 0), Card(S, R.NINE, 0))

        assert game._max_component_count(single, ts, tl) == 1
        assert game._max_component_count(pair, ts, tl) == 2
        assert game._max_component_count(trio, ts, tl) == 3
        assert game._max_component_count(tractor, ts, tl) == 4
        assert game._max_component_count(pair_singles, ts, tl) == 2

    def test_kitty_bonus_farmer_wins_last_trick(self):
        """Farmer wins last trick with a pair (x4); buried K (10) => 40 points."""
        from shengji.card import Card
        from shengji.types import Suit, Rank

        game = Game(num_players=6)
        state = game.reset()
        pair = (Card(Suit.SPADES, Rank.SEVEN, 0), Card(Suit.SPADES, Rank.SEVEN, 1))
        buried = (Card(Suit.CLUBS, Rank.KING, 0),)  # 10 points
        # Engine appends buried to the last trick; player 1 (a farmer) won it.
        state = state.copy(
            dealer_id=0, helper_players=(), buried_cards=buried,
            kitty_multiplier=4, tricks_won=((1, pair + buried),),
        )
        assert game._calculate_farmer_score(state) == 40  # 10 x 4

    def test_kitty_bonus_zero_when_dealer_wins_last_trick(self):
        from shengji.card import Card
        from shengji.types import Suit, Rank

        game = Game(num_players=6)
        state = game.reset()
        pair = (Card(Suit.SPADES, Rank.SEVEN, 0), Card(Suit.SPADES, Rank.SEVEN, 1))
        buried = (Card(Suit.CLUBS, Rank.KING, 0),)
        # Dealer (player 0) won the last trick => farmers get nothing from kitty.
        state = state.copy(
            dealer_id=0, helper_players=(), buried_cards=buried,
            kitty_multiplier=4, tricks_won=((0, pair + buried),),
        )
        assert game._calculate_farmer_score(state) == 0


class TestTrickWinner:
    """Trick-winner resolution: trump beats non-trump, higher beats lower, and
    only the max-count component is compared. Uses level 'Q' so the small test
    ranks (2,3,...) are not themselves level-card trumps."""

    def _winner(self, trick):
        from shengji.types import Suit
        game = Game(num_players=6)
        state = game.reset().copy(trump_suit=Suit.HEARTS, trump_level="Q")
        return trick[game._determine_trick_winner(trick, state)][0]

    def test_trump_beats_non_trump(self):
        """A low trump ruff beats a high non-trump card of the led suit."""
        from shengji.card import Card
        from shengji.types import Suit, Rank
        H, S = Suit.HEARTS, Suit.SPADES
        trick = (
            (0, (Card(S, Rank.ACE, 0),)),   # led suit (spades), highest non-trump
            (1, (Card(H, Rank.SIX, 0),)),   # ruff with a low trump
            (2, (Card(S, Rank.TWO, 0),)),
            (3, (Card(S, Rank.THREE, 0),)),
            (4, (Card(S, Rank.FOUR, 0),)),
            (5, (Card(S, Rank.SEVEN, 0),)),
        )
        assert self._winner(trick) == 1

    def test_highest_led_suit_when_no_trump(self):
        from shengji.card import Card
        from shengji.types import Suit, Rank
        S = Suit.SPADES
        trick = (
            (0, (Card(S, Rank.SEVEN, 0),)),
            (1, (Card(S, Rank.ACE, 0),)),
            (2, (Card(S, Rank.TWO, 0),)),
            (3, (Card(S, Rank.THREE, 0),)),
            (4, (Card(S, Rank.FOUR, 0),)),
            (5, (Card(S, Rank.SIX, 0),)),
        )
        assert self._winner(trick) == 1

    def test_pair_plus_singles_compares_only_pair(self):
        """pair+2singles led; a trump pair+2singles ruff wins on the PAIR."""
        from shengji.card import Card
        from shengji.types import Suit, Rank
        H, S, C, D = Suit.HEARTS, Suit.SPADES, Suit.CLUBS, Suit.DIAMONDS
        lead = (Card(S, Rank.NINE, 0), Card(S, Rank.NINE, 1), Card(S, Rank.ACE, 0), Card(S, Rank.KING, 0))
        ruff = (Card(H, Rank.SEVEN, 0), Card(H, Rank.SEVEN, 1), Card(H, Rank.ACE, 0), Card(H, Rank.KING, 0))
        trick = (
            (0, lead), (1, ruff),
            (2, (Card(C, Rank.TWO, 0), Card(C, Rank.THREE, 0), Card(C, Rank.FOUR, 0), Card(C, Rank.SIX, 0))),
            (3, (Card(C, Rank.SEVEN, 0), Card(C, Rank.EIGHT, 0), Card(C, Rank.NINE, 0), Card(C, Rank.TEN, 0))),
            (4, (Card(D, Rank.TWO, 0), Card(D, Rank.THREE, 0), Card(D, Rank.FOUR, 0), Card(D, Rank.SIX, 0))),
            (5, (Card(D, Rank.SEVEN, 0), Card(D, Rank.EIGHT, 0), Card(D, Rank.NINE, 0), Card(D, Rank.TEN, 0))),
        )
        assert self._winner(trick) == 1

    def test_tractor_not_beaten_by_two_loose_pairs(self):
        """A led tractor cannot be beaten by two non-consecutive trump pairs."""
        from shengji.card import Card
        from shengji.types import Suit, Rank
        H, S, C, D = Suit.HEARTS, Suit.SPADES, Suit.CLUBS, Suit.DIAMONDS
        lead = (Card(S, Rank.SEVEN, 0), Card(S, Rank.SEVEN, 1), Card(S, Rank.EIGHT, 0), Card(S, Rank.EIGHT, 1))
        loose = (Card(H, Rank.KING, 0), Card(H, Rank.KING, 1), Card(H, Rank.NINE, 0), Card(H, Rank.NINE, 1))
        trick = (
            (0, lead), (1, loose),
            (2, (Card(C, Rank.TWO, 0), Card(C, Rank.THREE, 0), Card(C, Rank.FOUR, 0), Card(C, Rank.SIX, 0))),
            (3, (Card(C, Rank.SEVEN, 0), Card(C, Rank.EIGHT, 0), Card(C, Rank.NINE, 0), Card(C, Rank.TEN, 0))),
            (4, (Card(D, Rank.TWO, 0), Card(D, Rank.THREE, 0), Card(D, Rank.FOUR, 0), Card(D, Rank.SIX, 0))),
            (5, (Card(D, Rank.SEVEN, 0), Card(D, Rank.EIGHT, 0), Card(D, Rank.NINE, 0), Card(D, Rank.TEN, 0))),
        )
        assert self._winner(trick) == 0  # leader keeps it

    def test_deciding_signature_priority(self):
        """Deciding component: trio > pair; longer run wins within a group size."""
        from shengji.card import Card
        from shengji.types import Suit, Rank
        game = Game(num_players=6)
        H, S = Suit.HEARTS, Suit.SPADES
        sig = lambda cards: game._deciding_signature(cards, H, "Q")

        assert sig((Card(S, Rank.ACE, 0),)) == (1, 1)
        assert sig((Card(S, Rank.KING, 0), Card(S, Rank.KING, 1))) == (2, 1)
        assert sig((Card(S, Rank.KING, 0), Card(S, Rank.KING, 1), Card(S, Rank.KING, 2))) == (3, 1)
        tractor3 = (Card(S, Rank.SEVEN, 0), Card(S, Rank.SEVEN, 1), Card(S, Rank.EIGHT, 0),
                    Card(S, Rank.EIGHT, 1), Card(S, Rank.NINE, 0), Card(S, Rank.NINE, 1))
        assert sig(tractor3) == (2, 3)
        limo2 = (Card(S, Rank.SEVEN, 0), Card(S, Rank.SEVEN, 1), Card(S, Rank.SEVEN, 2),
                 Card(S, Rank.EIGHT, 0), Card(S, Rank.EIGHT, 1), Card(S, Rank.EIGHT, 2))
        assert sig(limo2) == (3, 2)
        # Mixed throw with both a tractor-3 and a limo-2 is decided by the limo (trio).
        assert sig(tractor3 + limo2) == (3, 2)

    def test_limo2_not_beaten_by_tractor3(self):
        """A led limo-of-2 cannot be beaten by a (higher) tractor-of-3: different
        type, even though both are 6 cards."""
        from shengji.card import Card
        from shengji.types import Suit, Rank
        H, C = Suit.HEARTS, Suit.CLUBS
        led_limo = (Card(H, Rank.SEVEN, 0), Card(H, Rank.SEVEN, 1), Card(H, Rank.SEVEN, 2),
                    Card(H, Rank.EIGHT, 0), Card(H, Rank.EIGHT, 1), Card(H, Rank.EIGHT, 2))
        # Higher trump tractor-3 (9-10-J hearts pairs) — must NOT match the limo.
        trump_tractor3 = (Card(H, Rank.NINE, 0), Card(H, Rank.NINE, 1), Card(H, Rank.TEN, 0),
                          Card(H, Rank.TEN, 1), Card(H, Rank.JACK, 0), Card(H, Rank.JACK, 1))
        fill = tuple(Card(C, r, 0) for r in list(Rank)[:6])
        trick = (
            (0, led_limo), (1, trump_tractor3),
            (2, fill), (3, fill), (4, fill), (5, fill),
        )
        assert self._winner(trick) == 0  # leader keeps it (tractor-3 can't match limo-2)


class TestTrumpHierarchyTractorInTrick:
    """Cross-suit trump-hierarchy tractors must be recognized in the trick logic."""

    def test_is_tractor_cross_suit_trump(self):
        from shengji.card import Card
        from shengji.types import Suit, Rank
        game = Game(num_players=6)
        H, D = Suit.HEARTS, Suit.DIAMONDS
        # 7 is the level, hearts trump: 7♥ (trump level) + 3♦ (lieutenant) are consecutive.
        cards = (Card(H, Rank.SEVEN, 0), Card(H, Rank.SEVEN, 1),
                 Card(D, Rank.THREE, 0), Card(D, Rank.THREE, 1))
        assert game._is_tractor(cards, H, "7") is True
        assert game._detect_combination_type(cards, H, "7") == "tractor"

    def test_joker_pairs_form_tractor(self):
        from shengji.card import Card
        from shengji.types import Suit, Rank
        game = Game(num_players=6)
        cards = (Card(Suit.JOKER, Rank.SMALL_JOKER, 0), Card(Suit.JOKER, Rank.SMALL_JOKER, 1),
                 Card(Suit.JOKER, Rank.LARGE_JOKER, 0), Card(Suit.JOKER, Rank.LARGE_JOKER, 1))
        assert game._is_tractor(cards, Suit.HEARTS, "7") is True

    def test_non_consecutive_trump_hierarchy_not_tractor(self):
        from shengji.card import Card
        from shengji.types import Suit, Rank
        game = Game(num_players=6)
        H = Suit.HEARTS
        # trump level (7♥) and Captain (3♥) are NOT adjacent (Lieutenant sits between).
        cards = (Card(H, Rank.SEVEN, 0), Card(H, Rank.SEVEN, 1),
                 Card(H, Rank.THREE, 0), Card(H, Rank.THREE, 1))
        assert game._is_tractor(cards, H, "7") is False


class TestSoloHelperSealing:
    """A player who plays 2+ copies of the called card first is the only helper."""

    def _state(self):
        from shengji.types import Suit
        game = Game(num_players=6)
        base = game.reset().copy(called_rank="K", called_suit=Suit.CLUBS,
                                 helper_players=(), helpers_locked=False)
        return game, base

    def test_sole_helper_sealed_blocks_second(self):
        from shengji.card import Card
        from shengji.types import Suit, Rank
        game, base = self._state()
        C = Suit.CLUBS
        helpers, locked = game._update_helpers(base, 2, (Card(C, Rank.KING, 0), Card(C, Rank.KING, 1)))
        assert helpers == (2,) and locked is True
        # A later different player playing the called card cannot become helper #2.
        sealed = base.copy(helper_players=helpers, helpers_locked=locked)
        helpers2, locked2 = game._update_helpers(sealed, 4, (Card(C, Rank.KING, 2),))
        assert helpers2 == (2,) and locked2 is True

    def test_two_distinct_helpers_seal(self):
        from shengji.card import Card
        from shengji.types import Suit, Rank
        game, base = self._state()
        C = Suit.CLUBS
        h1, l1 = game._update_helpers(base, 1, (Card(C, Rank.KING, 0),))
        assert h1 == (1,) and l1 is False
        s1 = base.copy(helper_players=h1, helpers_locked=l1)
        h2, l2 = game._update_helpers(s1, 3, (Card(C, Rank.KING, 1),))
        assert h2 == (1, 3) and l2 is True


class TestCallHelperFiltering:
    """Dealer cannot call a non-trump card whose 3 copies it holds entirely."""

    def test_fully_held_card_not_callable(self):
        from shengji.card import Card
        from shengji.types import Suit, Rank, GamePhase
        game = Game(num_players=6)
        base = game.reset()
        C, H = Suit.CLUBS, Suit.HEARTS
        hands = list(base.hands)
        hands[0] = (Card(C, Rank.KING, 0), Card(C, Rank.KING, 1), Card(C, Rank.KING, 2))
        state = base.copy(phase=GamePhase.CALL_HELPER, dealer_id=0,
                          trump_suit=H, trump_level="2", hands=tuple(hands), buried_cards=())
        actions = game._get_legal_actions_call_helper(state)
        called = {(a.cards[0].rank, a.cards[0].suit) for a in actions}
        assert (Rank.KING, C) not in called          # all 3 held -> not callable
        assert (Rank.QUEEN, C) in called              # not fully held -> callable
