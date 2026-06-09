"""Tests for scoring and level changes."""

import pytest
from shengji.card import Card
from shengji.types import Suit, Rank
from shengji.scoring import (
    compute_farmer_score,
    compute_level_changes,
    apply_level_changes,
    count_red_fives,
)


class TestComputeFarmerScore:
    """Test farmer score calculation."""

    def test_empty_tricks(self):
        """Empty tricks list yields 0 score."""
        assert compute_farmer_score(()) == 0

    def test_single_five(self):
        """Single 5 card yields 5 points."""
        cards = (Card(Suit.HEARTS, Rank.FIVE, 0),)
        assert compute_farmer_score(cards) == 5

    def test_single_ten(self):
        """Single 10 card yields 10 points."""
        cards = (Card(Suit.HEARTS, Rank.TEN, 0),)
        assert compute_farmer_score(cards) == 10

    def test_single_king(self):
        """Single K card yields 10 points."""
        cards = (Card(Suit.HEARTS, Rank.KING, 0),)
        assert compute_farmer_score(cards) == 10

    def test_non_scoring_cards_ignored(self):
        """Non-scoring cards (A, Q, J, etc.) don't count."""
        cards = (
            Card(Suit.HEARTS, Rank.ACE, 0),
            Card(Suit.DIAMONDS, Rank.QUEEN, 0),
            Card(Suit.CLUBS, Rank.JACK, 0),
        )
        assert compute_farmer_score(cards) == 0

    def test_mixed_scoring_cards(self):
        """Multiple scoring cards sum correctly."""
        cards = (
            Card(Suit.HEARTS, Rank.FIVE, 0),
            Card(Suit.DIAMONDS, Rank.TEN, 0),
            Card(Suit.CLUBS, Rank.KING, 0),
            Card(Suit.SPADES, Rank.FIVE, 0),
        )
        assert compute_farmer_score(cards) == 30  # 5 + 10 + 10 + 5 (black 5 doesn't count)

    def test_all_fives(self):
        """Six 5 cards (2 per suit, 3 decks = only red fives per rules)."""
        cards = (
            Card(Suit.HEARTS, Rank.FIVE, 0),
            Card(Suit.HEARTS, Rank.FIVE, 1),
            Card(Suit.HEARTS, Rank.FIVE, 2),
            Card(Suit.DIAMONDS, Rank.FIVE, 0),
            Card(Suit.DIAMONDS, Rank.FIVE, 1),
            Card(Suit.DIAMONDS, Rank.FIVE, 2),
        )
        assert compute_farmer_score(cards) == 30  # 6 * 5


class TestComputeLevelChanges:
    """Test level change computation based on score."""

    def test_farmer_score_zero_dealer_wins_3(self):
        """Score 0: dealer side +3 levels, farmers -3."""
        dealer_side = (0, 1, 2)
        farmer_side = (3, 4, 5)
        changes = compute_level_changes(0, 0, 0, dealer_side, farmer_side)

        assert changes[0] == 3
        assert changes[1] == 3
        assert changes[2] == 3
        assert changes[3] == -3
        assert changes[4] == -3
        assert changes[5] == -3

    def test_farmer_score_30_dealer_wins_2(self):
        """Score 30: dealer side +2 levels, farmers -2."""
        dealer_side = (0, 1, 2)
        farmer_side = (3, 4, 5)
        changes = compute_level_changes(30, 0, 0, dealer_side, farmer_side)

        assert changes[0] == 2
        assert changes[1] == 2
        assert changes[2] == 2
        assert changes[3] == -2
        assert changes[4] == -2
        assert changes[5] == -2

    def test_farmer_score_60_dealer_wins_1(self):
        """Score 60: dealer side +1 level, farmers -1."""
        dealer_side = (0, 1, 2)
        farmer_side = (3, 4, 5)
        changes = compute_level_changes(60, 0, 0, dealer_side, farmer_side)

        assert changes[0] == 1
        assert changes[1] == 1
        assert changes[2] == 1
        assert changes[3] == -1
        assert changes[4] == -1
        assert changes[5] == -1

    def test_farmer_score_150_neutral(self):
        """Score 120-175: neutral (farmer win, no change)."""
        dealer_side = (0, 1, 2)
        farmer_side = (3, 4, 5)
        changes = compute_level_changes(150, 0, 0, dealer_side, farmer_side)

        for player_id in range(6):
            assert changes[player_id] == 0

    def test_farmer_score_200_farmer_wins_1(self):
        """Score 200: farmer side +1 level."""
        dealer_side = (0, 1, 2)
        farmer_side = (3, 4, 5)
        changes = compute_level_changes(200, 0, 0, dealer_side, farmer_side)

        assert changes[0] == -1
        assert changes[1] == -1
        assert changes[2] == -1
        assert changes[3] == 1
        assert changes[4] == 1
        assert changes[5] == 1

    def test_farmer_score_250_farmer_wins_2(self):
        """Score 250: farmer side +2 levels."""
        dealer_side = (0, 1, 2)
        farmer_side = (3, 4, 5)
        changes = compute_level_changes(250, 0, 0, dealer_side, farmer_side)

        assert changes[0] == -2
        assert changes[1] == -2
        assert changes[2] == -2
        assert changes[3] == 2
        assert changes[4] == 2
        assert changes[5] == 2

    def test_farmer_score_300_farmer_wins_3(self):
        """Score 300+: farmer side +3 levels."""
        dealer_side = (0, 1, 2)
        farmer_side = (3, 4, 5)
        changes = compute_level_changes(300, 0, 0, dealer_side, farmer_side)

        assert changes[0] == -3
        assert changes[1] == -3
        assert changes[2] == -3
        assert changes[3] == 3
        assert changes[4] == 3
        assert changes[5] == 3

    def test_red_five_penalties_hearts_only(self):
        """Hearts 5 captured: dealer -2 per card."""
        dealer_side = (0, 1, 2)
        farmer_side = (3, 4, 5)
        # Base: score 30 = dealer +2, but 2 ♥5 = dealer -4 additional
        changes = compute_level_changes(30, 2, 0, dealer_side, farmer_side)

        # Base change: +2, additional: -4, total: -2
        # Farmer side gets inverse of base change: -2
        assert changes[0] == -2
        assert changes[1] == -2
        assert changes[2] == -2
        assert changes[3] == -2
        assert changes[4] == -2
        assert changes[5] == -2

    def test_red_five_penalties_diamonds_only(self):
        """Diamonds 5 captured: dealer -1 per card."""
        dealer_side = (0, 1, 2)
        farmer_side = (3, 4, 5)
        # Base: score 30 = dealer +2, but 3 ♦5 = dealer -3 additional
        changes = compute_level_changes(30, 0, 3, dealer_side, farmer_side)

        # Base change: +2, additional: -3, total: -1
        # Farmer side gets inverse of base change: -2
        assert changes[0] == -1
        assert changes[1] == -1
        assert changes[2] == -1
        assert changes[3] == -2
        assert changes[4] == -2
        assert changes[5] == -2

    def test_red_five_penalties_combined(self):
        """Both ♥5 and ♦5 captured."""
        dealer_side = (0, 1, 2)
        farmer_side = (3, 4, 5)
        # Base: score 30 = dealer +2, but 1 ♥5 + 2 ♦5 = dealer -4 additional
        changes = compute_level_changes(30, 1, 2, dealer_side, farmer_side)

        # Base change: +2, additional: -(2 + 2) = -4, total: -2
        # Farmer side gets inverse of base change: -2
        assert changes[0] == -2
        assert changes[1] == -2
        assert changes[2] == -2
        assert changes[3] == -2
        assert changes[4] == -2
        assert changes[5] == -2


class TestApplyLevelChanges:
    """Test applying level changes to player levels."""

    def test_apply_positive_change(self):
        """Applying +1 to R1:2 gives R1:4."""
        levels = ("R1:2", "R1:2", "R1:2", "R1:2", "R1:2", "R1:2")
        changes = {0: 1, 1: 1, 2: 1, 3: 0, 4: 0, 5: 0}
        new_levels = apply_level_changes(levels, changes)

        assert new_levels[0] == "R1:4"
        assert new_levels[1] == "R1:4"
        assert new_levels[2] == "R1:4"
        assert new_levels[3] == "R1:2"

    def test_apply_negative_change(self):
        """Applying -1 to R1:4 gives R1:2."""
        levels = ("R1:4", "R1:4", "R1:4", "R1:4", "R1:4", "R1:4")
        changes = {0: -1, 1: -1, 2: -1, 3: 0, 4: 0, 5: 0}
        new_levels = apply_level_changes(levels, changes)

        assert new_levels[0] == "R1:2"
        assert new_levels[1] == "R1:2"
        assert new_levels[2] == "R1:2"
        assert new_levels[3] == "R1:4"

    def test_apply_mixed_changes(self):
        """Some players get +1, others -1."""
        levels = ("R1:2", "R1:4", "R1:6", "R1:7", "R1:8", "R1:9")
        changes = {0: 1, 1: 1, 2: 1, 3: -1, 4: -1, 5: -1}
        new_levels = apply_level_changes(levels, changes)

        assert new_levels[0] == "R1:4"
        assert new_levels[1] == "R1:6"
        assert new_levels[2] == "R1:7"
        assert new_levels[3] == "R1:6"
        assert new_levels[4] == "R1:7"
        assert new_levels[5] == "R1:8"

    def test_apply_zero_change(self):
        """Applying 0 to any level keeps it unchanged."""
        levels = ("R1:2", "R1:4", "R1:6", "R1:7", "R1:8", "R1:9")
        changes = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        new_levels = apply_level_changes(levels, changes)

        assert new_levels == levels


class TestCountRedFives:
    """Test counting red five cards."""

    def test_no_fives(self):
        """No five cards yields (0, 0)."""
        cards = (
            Card(Suit.HEARTS, Rank.ACE, 0),
            Card(Suit.DIAMONDS, Rank.KING, 0),
        )
        assert count_red_fives(cards) == (0, 0)

    def test_single_hearts_five(self):
        """Single ♥5 yields (1, 0)."""
        cards = (Card(Suit.HEARTS, Rank.FIVE, 0),)
        assert count_red_fives(cards) == (1, 0)

    def test_single_diamonds_five(self):
        """Single ♦5 yields (0, 1)."""
        cards = (Card(Suit.DIAMONDS, Rank.FIVE, 0),)
        assert count_red_fives(cards) == (0, 1)

    def test_mixed_red_fives(self):
        """Multiple ♥5 and ♦5 count correctly."""
        cards = (
            Card(Suit.HEARTS, Rank.FIVE, 0),
            Card(Suit.HEARTS, Rank.FIVE, 1),
            Card(Suit.DIAMONDS, Rank.FIVE, 0),
            Card(Suit.CLUBS, Rank.FIVE, 0),  # Black 5 doesn't count
        )
        assert count_red_fives(cards) == (2, 1)

    def test_all_red_fives(self):
        """All 6 red fives (3 ♥5 + 3 ♦5)."""
        cards = (
            Card(Suit.HEARTS, Rank.FIVE, 0),
            Card(Suit.HEARTS, Rank.FIVE, 1),
            Card(Suit.HEARTS, Rank.FIVE, 2),
            Card(Suit.DIAMONDS, Rank.FIVE, 0),
            Card(Suit.DIAMONDS, Rank.FIVE, 1),
            Card(Suit.DIAMONDS, Rank.FIVE, 2),
        )
        assert count_red_fives(cards) == (3, 3)
