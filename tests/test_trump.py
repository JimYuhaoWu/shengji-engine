"""Tests for trump card ordering and comparison."""

import pytest
from shengji.card import Card
from shengji.types import Suit, Rank
from shengji.trump import (
    is_always_trump, is_joker, is_level_card, is_captain, is_lieutenant,
    is_trump, trump_rank, non_trump_rank, compare_cards, winning_card
)


class TestAlwaysTrump:
    """Test identification of always-trump cards (5♥ and 5♦)."""

    def test_5_hearts_always_trump(self):
        assert is_always_trump(Card(Suit.HEARTS, Rank.FIVE, 0))
        assert is_always_trump(Card(Suit.HEARTS, Rank.FIVE, 1))
        assert is_always_trump(Card(Suit.HEARTS, Rank.FIVE, 2))

    def test_5_diamonds_always_trump(self):
        assert is_always_trump(Card(Suit.DIAMONDS, Rank.FIVE, 0))
        assert is_always_trump(Card(Suit.DIAMONDS, Rank.FIVE, 1))

    def test_5_black_not_always_trump(self):
        assert not is_always_trump(Card(Suit.CLUBS, Rank.FIVE, 0))
        assert not is_always_trump(Card(Suit.SPADES, Rank.FIVE, 0))

    def test_other_cards_not_always_trump(self):
        assert not is_always_trump(Card(Suit.HEARTS, Rank.TWO, 0))
        assert not is_always_trump(Card(Suit.HEARTS, Rank.ACE, 0))


class TestCaptainLieutenant:
    """Test identification of Captain (3 of trump color) and Lieutenant."""

    def test_captain_hearts_trump(self):
        """When hearts are trump, 3♥ is Captain."""
        assert is_captain(Card(Suit.HEARTS, Rank.THREE, 0), Suit.HEARTS)
        assert is_lieutenant(Card(Suit.DIAMONDS, Rank.THREE, 0), Suit.HEARTS)

    def test_captain_diamonds_trump(self):
        """When diamonds are trump, 3♦ is Captain."""
        assert is_captain(Card(Suit.DIAMONDS, Rank.THREE, 0), Suit.DIAMONDS)
        assert is_lieutenant(Card(Suit.HEARTS, Rank.THREE, 0), Suit.DIAMONDS)

    def test_captain_clubs_trump(self):
        """When clubs are trump, 3♣ is Captain."""
        assert is_captain(Card(Suit.CLUBS, Rank.THREE, 0), Suit.CLUBS)
        assert is_lieutenant(Card(Suit.SPADES, Rank.THREE, 0), Suit.CLUBS)

    def test_captain_spades_trump(self):
        """When spades are trump, 3♠ is Captain."""
        assert is_captain(Card(Suit.SPADES, Rank.THREE, 0), Suit.SPADES)
        assert is_lieutenant(Card(Suit.CLUBS, Rank.THREE, 0), Suit.SPADES)

    def test_black_threes_normal_when_red_trump(self):
        """When hearts or diamonds are trump, black 3s are normal cards."""
        assert not is_captain(Card(Suit.CLUBS, Rank.THREE, 0), Suit.HEARTS)
        assert not is_lieutenant(Card(Suit.CLUBS, Rank.THREE, 0), Suit.HEARTS)
        assert not is_captain(Card(Suit.SPADES, Rank.THREE, 0), Suit.HEARTS)
        assert not is_lieutenant(Card(Suit.SPADES, Rank.THREE, 0), Suit.HEARTS)


class TestLevelCard:
    """Test identification of level cards."""

    def test_level_2_identification(self):
        assert is_level_card(Card(Suit.HEARTS, Rank.TWO, 0), "2")
        assert is_level_card(Card(Suit.DIAMONDS, Rank.TWO, 0), "2")
        assert not is_level_card(Card(Suit.HEARTS, Rank.TWO, 0), "4")

    def test_level_joker_not_level_card(self):
        assert not is_level_card(Card(Suit.JOKER, Rank.SMALL_JOKER, 0), "2")
        assert not is_level_card(Card(Suit.JOKER, Rank.LARGE_JOKER, 0), "J")


class TestIsTrump:
    """Test comprehensive trump identification."""

    def test_always_trump_cards(self):
        """5♥ and 5♦ are always trump."""
        assert is_trump(Card(Suit.HEARTS, Rank.FIVE, 0), Suit.HEARTS, "2")
        assert is_trump(Card(Suit.DIAMONDS, Rank.FIVE, 0), Suit.HEARTS, "2")
        assert is_trump(Card(Suit.HEARTS, Rank.FIVE, 0), Suit.SPADES, "K")

    def test_jokers_always_trump(self):
        """Jokers are always trump."""
        assert is_trump(Card(Suit.JOKER, Rank.SMALL_JOKER, 0), Suit.HEARTS, "2")
        assert is_trump(Card(Suit.JOKER, Rank.LARGE_JOKER, 0), Suit.SPADES, "K")

    def test_captain_lieutenant_trump(self):
        """Captain and Lieutenant are trump."""
        assert is_trump(Card(Suit.HEARTS, Rank.THREE, 0), Suit.HEARTS, "2")
        assert is_trump(Card(Suit.DIAMONDS, Rank.THREE, 0), Suit.HEARTS, "2")

    def test_level_cards_trump(self):
        """Level cards are trump."""
        assert is_trump(Card(Suit.HEARTS, Rank.SEVEN, 0), Suit.HEARTS, "7")
        assert is_trump(Card(Suit.DIAMONDS, Rank.SEVEN, 0), Suit.HEARTS, "7")

    def test_non_trump_suit_card_not_trump(self):
        """Cards in non-trump suit (except level/special) are not trump."""
        assert not is_trump(Card(Suit.CLUBS, Rank.ACE, 0), Suit.HEARTS, "7")
        assert not is_trump(Card(Suit.SPADES, Rank.KING, 0), Suit.DIAMONDS, "10")


class TestTrumpRank:
    """Test trump card ranking (higher number = stronger)."""

    def test_5_hearts_highest(self):
        """5♥ should be the strongest trump."""
        rank_5h = trump_rank(Card(Suit.HEARTS, Rank.FIVE, 0), Suit.HEARTS, "7")
        rank_5d = trump_rank(Card(Suit.DIAMONDS, Rank.FIVE, 0), Suit.HEARTS, "7")
        assert rank_5h > rank_5d

    def test_5_diamonds_second_highest(self):
        """5♦ should be second strongest."""
        rank_5d = trump_rank(Card(Suit.DIAMONDS, Rank.FIVE, 0), Suit.HEARTS, "7")
        rank_large_joker = trump_rank(Card(Suit.JOKER, Rank.LARGE_JOKER, 0), Suit.HEARTS, "7")
        assert rank_5d > rank_large_joker

    def test_jokers_ranked_correctly(self):
        """Large Joker > Small Joker."""
        rank_large = trump_rank(Card(Suit.JOKER, Rank.LARGE_JOKER, 0), Suit.HEARTS, "7")
        rank_small = trump_rank(Card(Suit.JOKER, Rank.SMALL_JOKER, 0), Suit.HEARTS, "7")
        assert rank_large > rank_small

    def test_captain_beats_lieutenant(self):
        """Captain beats Lieutenant."""
        rank_captain = trump_rank(Card(Suit.HEARTS, Rank.THREE, 0), Suit.HEARTS, "7")
        rank_lieutenant = trump_rank(Card(Suit.DIAMONDS, Rank.THREE, 0), Suit.HEARTS, "7")
        assert rank_captain > rank_lieutenant

    def test_trump_level_beats_non_trump_level(self):
        """Trump level card beats non-trump level card."""
        rank_trump_level = trump_rank(Card(Suit.HEARTS, Rank.SEVEN, 0), Suit.HEARTS, "7")
        rank_non_trump_level = trump_rank(Card(Suit.SPADES, Rank.SEVEN, 0), Suit.HEARTS, "7")
        assert rank_trump_level > rank_non_trump_level

    def test_level_beats_ace(self):
        """Level card beats regular trump suit cards."""
        rank_level = trump_rank(Card(Suit.HEARTS, Rank.SEVEN, 0), Suit.HEARTS, "7")
        rank_ace = trump_rank(Card(Suit.HEARTS, Rank.ACE, 0), Suit.HEARTS, "7")
        assert rank_level > rank_ace

    def test_non_trump_card_returns_none(self):
        """Non-trump cards should return None."""
        assert trump_rank(Card(Suit.CLUBS, Rank.ACE, 0), Suit.HEARTS, "7") is None


class TestNonTrumpRank:
    """Test non-trump card ranking."""

    def test_ace_beats_king(self):
        """Ace is highest non-trump card."""
        rank_ace = non_trump_rank(Card(Suit.HEARTS, Rank.ACE, 0))
        rank_king = non_trump_rank(Card(Suit.HEARTS, Rank.KING, 0))
        assert rank_ace > rank_king

    def test_two_lowest(self):
        """Two is lowest non-trump card."""
        rank_two = non_trump_rank(Card(Suit.HEARTS, Rank.TWO, 0))
        rank_three = non_trump_rank(Card(Suit.HEARTS, Rank.THREE, 0))
        assert rank_two < rank_three

    def test_normal_ranking_order(self):
        """Full ranking: A > K > Q > J > T > 9 > 8 > 7 > 6 > 5 > 4 > 3 > 2."""
        ranks = [
            non_trump_rank(Card(Suit.HEARTS, Rank.ACE, 0)),
            non_trump_rank(Card(Suit.HEARTS, Rank.KING, 0)),
            non_trump_rank(Card(Suit.HEARTS, Rank.QUEEN, 0)),
            non_trump_rank(Card(Suit.HEARTS, Rank.JACK, 0)),
            non_trump_rank(Card(Suit.HEARTS, Rank.TEN, 0)),
            non_trump_rank(Card(Suit.HEARTS, Rank.NINE, 0)),
            non_trump_rank(Card(Suit.HEARTS, Rank.EIGHT, 0)),
            non_trump_rank(Card(Suit.HEARTS, Rank.SEVEN, 0)),
            non_trump_rank(Card(Suit.HEARTS, Rank.SIX, 0)),
            non_trump_rank(Card(Suit.HEARTS, Rank.FIVE, 0)),
            non_trump_rank(Card(Suit.HEARTS, Rank.FOUR, 0)),
            non_trump_rank(Card(Suit.HEARTS, Rank.THREE, 0)),
            non_trump_rank(Card(Suit.HEARTS, Rank.TWO, 0)),
        ]
        assert ranks == sorted(ranks, reverse=True)


class TestCompareCards:
    """Test card comparison in trick context."""

    def test_trump_beats_non_trump(self):
        """Trump card beats non-trump."""
        trump_card = Card(Suit.JOKER, Rank.SMALL_JOKER, 0)
        non_trump = Card(Suit.HEARTS, Rank.ACE, 0)
        result = compare_cards(trump_card, non_trump, Suit.HEARTS, Suit.SPADES, "7")
        assert result == 1

    def test_5_hearts_beats_all(self):
        """5♥ beats everything."""
        five_hearts = Card(Suit.HEARTS, Rank.FIVE, 0)
        large_joker = Card(Suit.JOKER, Rank.LARGE_JOKER, 0)
        result = compare_cards(five_hearts, large_joker, Suit.HEARTS, Suit.SPADES, "7")
        assert result == 1

    def test_captain_beats_lieutenant(self):
        """Captain beats Lieutenant."""
        captain = Card(Suit.HEARTS, Rank.THREE, 0)
        lieutenant = Card(Suit.DIAMONDS, Rank.THREE, 0)
        result = compare_cards(captain, lieutenant, Suit.HEARTS, Suit.HEARTS, "7")
        assert result == 1

    def test_higher_non_trump_card_in_same_suit_wins(self):
        """Higher card in same non-trump suit wins."""
        king = Card(Suit.CLUBS, Rank.KING, 0)
        queen = Card(Suit.CLUBS, Rank.QUEEN, 0)
        result = compare_cards(king, queen, Suit.CLUBS, Suit.HEARTS, "7")
        assert result == 1

    def test_different_non_trump_suits_no_winner(self):
        """Different non-trump suits can't be compared."""
        king_clubs = Card(Suit.CLUBS, Rank.KING, 0)
        ace_spades = Card(Suit.SPADES, Rank.ACE, 0)
        result = compare_cards(king_clubs, ace_spades, Suit.HEARTS, Suit.HEARTS, "7")
        assert result == 0  # No comparison


class TestWinningCard:
    """Test finding the winning card from a trick."""

    def test_single_card(self):
        """Single card is winner."""
        card = Card(Suit.HEARTS, Rank.ACE, 0)
        winner = winning_card([card], Suit.HEARTS, Suit.HEARTS, "7")
        assert winner == card

    def test_trump_beats_led_suit(self):
        """Trump beats led suit."""
        led = Card(Suit.HEARTS, Rank.ACE, 0)
        trump_card = Card(Suit.JOKER, Rank.SMALL_JOKER, 0)
        cards = [led, trump_card]
        winner = winning_card(cards, Suit.HEARTS, Suit.SPADES, "7")
        assert winner == trump_card

    def test_highest_trump_wins(self):
        """Highest trump wins."""
        small = Card(Suit.JOKER, Rank.SMALL_JOKER, 0)
        large = Card(Suit.JOKER, Rank.LARGE_JOKER, 0)
        cards = [small, large]
        winner = winning_card(cards, Suit.HEARTS, Suit.SPADES, "7")
        assert winner == large

    def test_highest_led_suit_wins_no_trump(self):
        """Highest card of led suit wins if no trump."""
        queen = Card(Suit.CLUBS, Rank.QUEEN, 0)
        king = Card(Suit.CLUBS, Rank.KING, 0)
        ace = Card(Suit.CLUBS, Rank.ACE, 0)
        cards = [queen, king, ace]
        winner = winning_card(cards, Suit.CLUBS, Suit.HEARTS, "7")
        assert winner == ace
