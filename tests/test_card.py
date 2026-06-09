"""Tests for card utilities."""

import pytest
from shengji.card import (
    Card, Deck, cards_are_identical, count_identical_cards,
    get_identical_cards, is_red_suit, is_black_suit
)
from shengji.types import Suit, Rank


class TestCard:
    """Test Card class."""

    def test_card_equality_ignores_deck_id(self):
        """Cards are equal if same suit and rank, regardless of deck_id."""
        card1 = Card(Suit.HEARTS, Rank.ACE, 0)
        card2 = Card(Suit.HEARTS, Rank.ACE, 1)
        card3 = Card(Suit.HEARTS, Rank.ACE, 2)
        assert card1 == card2
        assert card2 == card3
        assert card1 == card3

    def test_card_inequality(self):
        """Cards differ if suit or rank differs."""
        card1 = Card(Suit.HEARTS, Rank.ACE, 0)
        card2 = Card(Suit.HEARTS, Rank.KING, 0)
        card3 = Card(Suit.DIAMONDS, Rank.ACE, 0)
        assert card1 != card2
        assert card1 != card3

    def test_card_str(self):
        """String representation uses suit and rank."""
        card = Card(Suit.HEARTS, Rank.ACE, 0)
        assert str(card) == "HA"

    def test_card_hash(self):
        """Cards can be hashed and used in sets/dicts."""
        card1 = Card(Suit.HEARTS, Rank.ACE, 0)
        card2 = Card(Suit.HEARTS, Rank.ACE, 1)
        # Same hash because equality ignores deck_id
        assert hash(card1) == hash(card2)
        s = {card1, card2}
        assert len(s) == 1  # Only one unique card in set


class TestDeck:
    """Test deck generation."""

    def test_single_deck_has_54_cards(self):
        """Single deck: 52 standard + 2 jokers."""
        decks = Deck.standard_decks(1)
        assert len(decks) == 54

    def test_three_decks_has_162_cards(self):
        """Three decks: 54 × 3."""
        decks = Deck.standard_decks(3)
        assert len(decks) == 162

    def test_deck_has_correct_suits(self):
        """Deck has cards in all four suits."""
        decks = Deck.standard_decks(1)
        suits = {card.suit for card in decks}
        assert suits == {Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS, Suit.SPADES, Suit.JOKER}

    def test_deck_has_correct_ranks(self):
        """Deck has all 13 standard ranks plus jokers."""
        decks = Deck.standard_decks(1)
        ranks = {card.rank for card in decks}
        expected = {
            Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX,
            Rank.SEVEN, Rank.EIGHT, Rank.NINE, Rank.TEN,
            Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE,
            Rank.SMALL_JOKER, Rank.LARGE_JOKER
        }
        assert ranks == expected

    def test_deck_ids_correct(self):
        """Cards have correct deck_id (0, 1, 2 for three decks)."""
        decks = Deck.standard_decks(3)
        deck_ids = {card.deck_id for card in decks}
        assert deck_ids == {0, 1, 2}

    def test_three_of_each_card(self):
        """Three decks have exactly 3 of each card (ignoring deck_id)."""
        decks = Deck.standard_decks(3)
        card_counts = {}
        for card in decks:
            key = (card.suit, card.rank)
            card_counts[key] = card_counts.get(key, 0) + 1
        # All cards should appear exactly 3 times
        assert all(count == 3 for count in card_counts.values())


class TestCardsAreIdentical:
    """Test card identity checking."""

    def test_empty_list(self):
        """Empty list returns False."""
        assert not cards_are_identical([])

    def test_single_card(self):
        """Single card is trivially identical to itself."""
        card = Card(Suit.HEARTS, Rank.ACE, 0)
        assert cards_are_identical([card])

    def test_two_identical_cards_different_decks(self):
        """Two cards with same suit/rank but different deck_id are identical."""
        card1 = Card(Suit.HEARTS, Rank.ACE, 0)
        card2 = Card(Suit.HEARTS, Rank.ACE, 1)
        assert cards_are_identical([card1, card2])

    def test_three_identical_cards(self):
        """Three cards from different decks are identical."""
        cards = [
            Card(Suit.HEARTS, Rank.ACE, 0),
            Card(Suit.HEARTS, Rank.ACE, 1),
            Card(Suit.HEARTS, Rank.ACE, 2),
        ]
        assert cards_are_identical(cards)

    def test_different_ranks_not_identical(self):
        """Cards with different ranks are not identical."""
        cards = [
            Card(Suit.HEARTS, Rank.ACE, 0),
            Card(Suit.HEARTS, Rank.KING, 1),
        ]
        assert not cards_are_identical(cards)

    def test_different_suits_not_identical(self):
        """Cards with different suits are not identical."""
        cards = [
            Card(Suit.HEARTS, Rank.ACE, 0),
            Card(Suit.DIAMONDS, Rank.ACE, 1),
        ]
        assert not cards_are_identical(cards)


class TestCountIdenticalCards:
    """Test counting identical cards in hand."""

    def test_no_matches(self):
        """Count 0 if card not in hand."""
        card = Card(Suit.HEARTS, Rank.ACE, 0)
        hand = [
            Card(Suit.HEARTS, Rank.KING, 0),
            Card(Suit.DIAMONDS, Rank.ACE, 0),
        ]
        assert count_identical_cards(card, hand) == 0

    def test_one_match(self):
        """Count 1 if one match exists."""
        card = Card(Suit.HEARTS, Rank.ACE, 0)
        hand = [
            Card(Suit.HEARTS, Rank.ACE, 1),
            Card(Suit.HEARTS, Rank.KING, 0),
        ]
        assert count_identical_cards(card, hand) == 1

    def test_multiple_matches_ignore_deck_id(self):
        """Count all matches regardless of deck_id."""
        card = Card(Suit.HEARTS, Rank.ACE, 0)
        hand = [
            Card(Suit.HEARTS, Rank.ACE, 1),
            Card(Suit.HEARTS, Rank.ACE, 2),
            Card(Suit.HEARTS, Rank.KING, 0),
        ]
        assert count_identical_cards(card, hand) == 2


class TestGetIdenticalCards:
    """Test getting identical cards from hand."""

    def test_empty_hand(self):
        """Empty hand returns empty list."""
        card = Card(Suit.HEARTS, Rank.ACE, 0)
        result = get_identical_cards(card, [])
        assert result == []

    def test_no_matches(self):
        """No matches returns empty list."""
        card = Card(Suit.HEARTS, Rank.ACE, 0)
        hand = [Card(Suit.HEARTS, Rank.KING, 0)]
        result = get_identical_cards(card, hand)
        assert result == []

    def test_all_matches_returned(self):
        """Returns all identical cards."""
        card = Card(Suit.HEARTS, Rank.ACE, 0)
        match1 = Card(Suit.HEARTS, Rank.ACE, 1)
        match2 = Card(Suit.HEARTS, Rank.ACE, 2)
        hand = [match1, match2, Card(Suit.HEARTS, Rank.KING, 0)]
        result = get_identical_cards(card, hand)
        assert set(result) == {match1, match2}


class TestSuitColor:
    """Test suit color classification."""

    def test_red_suits(self):
        """Hearts and Diamonds are red."""
        assert is_red_suit(Suit.HEARTS)
        assert is_red_suit(Suit.DIAMONDS)

    def test_black_suits(self):
        """Clubs and Spades are black."""
        assert is_black_suit(Suit.CLUBS)
        assert is_black_suit(Suit.SPADES)

    def test_joker_not_red_or_black(self):
        """Joker is neither red nor black."""
        assert not is_red_suit(Suit.JOKER)
        assert not is_black_suit(Suit.JOKER)
