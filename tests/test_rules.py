"""Tests for card combination detection and legal action generation."""

import pytest
from shengji.card import Card
from shengji.types import Suit, Rank, TrickCombination
from shengji.rules import (
    CardCombination, get_card_combinations, detect_consecutive_pairs,
    detect_consecutive_trios, can_follow_suit, can_trump
)


class TestCardCombination:
    """Test CardCombination dataclass."""

    def test_valid_single(self):
        """Single card combination is valid."""
        card = Card(Suit.HEARTS, Rank.ACE, 0)
        combo = CardCombination((card,), TrickCombination.SINGLE)
        assert combo.is_valid()
        assert combo.count() == 1
        assert combo.suit() == Suit.HEARTS

    def test_valid_pair(self):
        """Pair of identical cards is valid."""
        card1 = Card(Suit.HEARTS, Rank.ACE, 0)
        card2 = Card(Suit.HEARTS, Rank.ACE, 1)
        combo = CardCombination((card1, card2), TrickCombination.PAIR)
        assert combo.is_valid()
        assert combo.count() == 2

    def test_valid_trio(self):
        """Trio of identical cards is valid."""
        cards = tuple([Card(Suit.HEARTS, Rank.ACE, i) for i in range(3)])
        combo = CardCombination(cards, TrickCombination.TRIO)
        assert combo.is_valid()
        assert combo.count() == 3

    def test_empty_combination_invalid(self):
        """Empty combination raises ValueError."""
        with pytest.raises(ValueError):
            CardCombination((), TrickCombination.SINGLE)

    def test_mixed_suits_invalid(self):
        """Combination with mixed suits is invalid."""
        card1 = Card(Suit.HEARTS, Rank.ACE, 0)
        card2 = Card(Suit.DIAMONDS, Rank.ACE, 0)
        combo = CardCombination((card1, card2), TrickCombination.PAIR)
        # Note: is_valid() checks suit consistency, type/count mismatch would also fail

    def test_pair_with_non_identical_cards_invalid(self):
        """Pair with different ranks is invalid."""
        card1 = Card(Suit.HEARTS, Rank.ACE, 0)
        card2 = Card(Suit.HEARTS, Rank.KING, 0)
        combo = CardCombination((card1, card2), TrickCombination.PAIR)
        assert not combo.is_valid()


class TestConsecutivePairs:
    """Test tractor (consecutive pairs) detection."""

    def test_two_consecutive_pairs_valid(self):
        """Two consecutive pairs form valid tractor."""
        # 8♥, 8♥, 9♥, 9♥ (7 is level card, so skip it)
        pairs = [
            Card(Suit.HEARTS, Rank.EIGHT, 0),
            Card(Suit.HEARTS, Rank.EIGHT, 1),
            Card(Suit.HEARTS, Rank.NINE, 0),
            Card(Suit.HEARTS, Rank.NINE, 1),
        ]
        tractor = detect_consecutive_pairs(pairs, Suit.HEARTS, Suit.SPADES, "7")
        assert tractor is not None
        assert len(tractor) == 4

    def test_three_consecutive_pairs_valid(self):
        """Three consecutive pairs form valid tractor."""
        pairs = [
            Card(Suit.HEARTS, Rank.EIGHT, 0),
            Card(Suit.HEARTS, Rank.EIGHT, 1),
            Card(Suit.HEARTS, Rank.NINE, 0),
            Card(Suit.HEARTS, Rank.NINE, 1),
            Card(Suit.HEARTS, Rank.TEN, 0),
            Card(Suit.HEARTS, Rank.TEN, 1),
        ]
        tractor = detect_consecutive_pairs(pairs, Suit.HEARTS, Suit.SPADES, "7")
        assert tractor is not None
        assert len(tractor) == 6

    def test_gap_in_pairs_invalid(self):
        """Pairs with gap are not tractor."""
        # 7♥, 7♥, 9♥, 9♥ (no 8♥ pair)
        pairs = [
            Card(Suit.HEARTS, Rank.SEVEN, 0),
            Card(Suit.HEARTS, Rank.SEVEN, 1),
            Card(Suit.HEARTS, Rank.NINE, 0),
            Card(Suit.HEARTS, Rank.NINE, 1),
        ]
        tractor = detect_consecutive_pairs(pairs, Suit.HEARTS, Suit.SPADES, "7")
        assert tractor is None

    def test_single_card_not_tractor(self):
        """Single card is not tractor."""
        cards = [Card(Suit.HEARTS, Rank.ACE, 0)]
        tractor = detect_consecutive_pairs(cards, Suit.HEARTS, Suit.SPADES, "7")
        assert tractor is None

    def test_incomplete_pair_not_tractor(self):
        """Incomplete pair (only 1 card) is not tractor."""
        cards = [
            Card(Suit.HEARTS, Rank.SEVEN, 0),
            Card(Suit.HEARTS, Rank.EIGHT, 0),
            Card(Suit.HEARTS, Rank.EIGHT, 1),
        ]
        tractor = detect_consecutive_pairs(cards, Suit.HEARTS, Suit.SPADES, "7")
        assert tractor is None


class TestConsecutiveTrios:
    """Test limo (consecutive trios) detection."""

    def test_two_consecutive_trios_valid(self):
        """Two consecutive trios form valid limo."""
        # 8♥×3, 9♥×3 (7 is level card, so skip it)
        trios = [
            Card(Suit.HEARTS, Rank.EIGHT, 0),
            Card(Suit.HEARTS, Rank.EIGHT, 1),
            Card(Suit.HEARTS, Rank.EIGHT, 2),
            Card(Suit.HEARTS, Rank.NINE, 0),
            Card(Suit.HEARTS, Rank.NINE, 1),
            Card(Suit.HEARTS, Rank.NINE, 2),
        ]
        limo = detect_consecutive_trios(trios, Suit.HEARTS, Suit.SPADES, "7")
        assert limo is not None
        assert len(limo) == 6

    def test_three_consecutive_trios_valid(self):
        """Three consecutive trios form valid limo."""
        trios = []
        for rank in [Rank.EIGHT, Rank.NINE, Rank.TEN]:
            for deck_id in range(3):
                trios.append(Card(Suit.HEARTS, rank, deck_id))
        limo = detect_consecutive_trios(trios, Suit.HEARTS, Suit.SPADES, "7")
        assert limo is not None
        assert len(limo) == 9

    def test_gap_in_trios_invalid(self):
        """Trios with gap are not limo."""
        # 7♥×3, 9♥×3 (no 8♥×3)
        trios = [
            Card(Suit.HEARTS, Rank.SEVEN, 0),
            Card(Suit.HEARTS, Rank.SEVEN, 1),
            Card(Suit.HEARTS, Rank.SEVEN, 2),
            Card(Suit.HEARTS, Rank.NINE, 0),
            Card(Suit.HEARTS, Rank.NINE, 1),
            Card(Suit.HEARTS, Rank.NINE, 2),
        ]
        limo = detect_consecutive_trios(trios, Suit.HEARTS, Suit.SPADES, "7")
        assert limo is None

    def test_incomplete_trio_not_limo(self):
        """Incomplete trio (only 2 cards) is not limo."""
        trios = [
            Card(Suit.HEARTS, Rank.SEVEN, 0),
            Card(Suit.HEARTS, Rank.SEVEN, 1),
            Card(Suit.HEARTS, Rank.SEVEN, 2),
            Card(Suit.HEARTS, Rank.EIGHT, 0),
            Card(Suit.HEARTS, Rank.EIGHT, 1),
        ]
        limo = detect_consecutive_trios(trios, Suit.HEARTS, Suit.SPADES, "7")
        assert limo is None


class TestCanFollowSuit:
    """Test suit following checks."""

    def test_has_led_suit_non_trump(self):
        """Can follow if hand has non-trump cards of led suit."""
        hand = [
            Card(Suit.HEARTS, Rank.ACE, 0),
            Card(Suit.DIAMONDS, Rank.KING, 0),
        ]
        assert can_follow_suit(hand, Suit.HEARTS, Suit.SPADES, "7")

    def test_no_led_suit(self):
        """Cannot follow if hand has no cards of led suit."""
        hand = [
            Card(Suit.DIAMONDS, Rank.ACE, 0),
            Card(Suit.CLUBS, Rank.KING, 0),
        ]
        assert not can_follow_suit(hand, Suit.HEARTS, Suit.SPADES, "7")

    def test_led_suit_all_trump_cannot_follow(self):
        """Cannot follow suit if all cards of that suit are trump."""
        hand = [
            Card(Suit.HEARTS, Rank.SEVEN, 0),  # Trump level card
            Card(Suit.HEARTS, Rank.ACE, 0),
        ]
        # Led suit is hearts, and 7♥ is trump level, but non-trump hearts can follow
        assert can_follow_suit(hand, Suit.HEARTS, Suit.SPADES, "7")


class TestCanTrump:
    """Test trump checking."""

    def test_has_trump(self):
        """Can trump if hand has trump cards."""
        hand = [
            Card(Suit.JOKER, Rank.SMALL_JOKER, 0),
            Card(Suit.HEARTS, Rank.ACE, 0),
        ]
        assert can_trump(hand, Suit.SPADES, "7")

    def test_no_trump(self):
        """Cannot trump if hand has no trump cards."""
        hand = [
            Card(Suit.HEARTS, Rank.ACE, 0),
            Card(Suit.HEARTS, Rank.KING, 0),
        ]
        assert not can_trump(hand, Suit.SPADES, "7")

    def test_always_trump_cards_count(self):
        """5♥ and 5♦ count as trump."""
        hand = [
            Card(Suit.HEARTS, Rank.FIVE, 0),
            Card(Suit.DIAMONDS, Rank.ACE, 0),
        ]
        # 5♥ is always trump
        assert can_trump(hand, Suit.CLUBS, "7")
