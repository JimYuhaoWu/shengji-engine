"""Main game engine orchestrator."""

import random
from typing import Dict, List, Optional, Tuple
from .card import Card, Deck, count_identical_cards, get_identical_cards
from .level import LEVEL_SEQ, step_level
from .state import GameState
from .types import GamePhase, Suit, Rank, Action, ActionType, TrickCombination, TrumpBid
from .trump import is_level_card, is_trump, compare_cards, winning_card
from .rules import CardCombination, get_card_combinations, can_follow_suit, can_trump, get_legal_plays_when_following, get_legal_trump_bids
from .scoring import compute_farmer_score, compute_level_changes, count_red_fives, apply_level_changes


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

        # Extract trump level from the level system (all players should have same level in initial setup)
        level_key = player_levels[0]  # e.g., "R1:2"
        trump_level = level_key.split(":")[1]  # e.g., "2"

        # Create initial state
        state = GameState(
            phase=GamePhase.DEALING,
            current_player=0,  # Player 0 can bid first
            dealer_id=dealer_id,
            hands=hands_tuple,
            kitty=kitty_tuple,
            trump_suit=None,
            trump_level=trump_level,
            trump_locked=False,
            current_trump_bid=None,
            passed_players=(),
            trump_bids_history=(),
            helper_card=None,
            revealed_helpers=(),
            current_trick=(),
            tricks_won=(),
            player_levels=player_levels,
            scores=tuple(0 for _ in range(6)),
            legal_actions=(),
        )

        # Generate legal actions for first player
        legal_actions = self._get_legal_actions(state)
        return state.copy(legal_actions=legal_actions)

    def _get_legal_actions(self, state: GameState) -> Tuple[Action, ...]:
        """Get legal actions for current state."""
        if state.phase == GamePhase.DEALING:
            return self._get_legal_actions_dealing(state)
        elif state.phase == GamePhase.TRUMP_DECLARATION:
            return self._get_legal_actions_trump_declaration(state)
        elif state.phase == GamePhase.KITTY:
            return self._get_legal_actions_kitty(state)
        elif state.phase == GamePhase.CALL_HELPER:
            return self._get_legal_actions_call_helper(state)
        elif state.phase == GamePhase.TRICK_PLAYING:
            return self._get_legal_actions_trick_playing(state)
        elif state.phase == GamePhase.SCORING:
            return ()  # No actions in scoring phase
        else:
            return ()

    def _get_legal_actions_dealing(self, state: GameState) -> Tuple[Action, ...]:
        """Get legal trump bid actions during DEALING and TRUMP_DECLARATION phases."""
        player_id = state.current_player
        player_hand = state.hands[player_id]
        trump_level = state.trump_level

        actions: List[Action] = []

        # Get all valid bids for this player
        valid_bids = get_legal_trump_bids(
            player_hand,
            trump_level,
            state.current_trump_bid,
            player_id
        )

        # Add each valid bid as an action
        for bid in valid_bids:
            actions.append(Action(
                action_type=ActionType.BID_TRUMP,
                trump_bid=bid,
            ))

        # Can always pass (unless already passed)
        if player_id not in state.passed_players:
            actions.append(Action(action_type=ActionType.PASS_TRUMP))

        return tuple(actions)

    def _get_legal_actions_trump_declaration(self, state: GameState) -> Tuple[Action, ...]:
        """Get legal trump declaration actions (continuation of auction)."""
        return self._get_legal_actions_dealing(state)

    def _get_legal_actions_kitty(self, state: GameState) -> Tuple[Action, ...]:
        """Get legal bury actions for dealer during kitty phase.

        Dealer's hand already includes kitty cards (32 total: 26 original + 6 from kitty).
        Dealer selects 6 cards to bury, keeps the rest.
        """
        from itertools import combinations

        dealer_hand = state.hands[state.dealer_id]
        actions: List[Action] = []

        # Generate all possible ways to select 6 cards to bury from 32
        # Note: This can be large (C(32,6) = 906,192), but it's needed for complete game rules
        for buried_combo in combinations(dealer_hand, 6):
            actions.append(Action(action_type=ActionType.TAKE_KITTY, cards=tuple(buried_combo)))

        return tuple(actions)

    def _get_legal_actions_call_helper(self, state: GameState) -> Tuple[Action, ...]:
        """Get legal helper card calling actions for dealer."""
        # Dealer can call any non-trump card from the deck
        actions: List[Action] = []

        # Collect all possible cards (non-trump) that could be called
        for suit in [Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS, Suit.SPADES]:
            for rank in Rank:
                if rank == Rank.LARGE_JOKER or rank == Rank.SMALL_JOKER:
                    continue
                card = Card(suit, rank, 0)
                if not is_trump(card, state.trump_suit, state.player_levels[state.dealer_id].split(":")[1]):
                    actions.append(Action(action_type=ActionType.CALL_HELPER, cards=(card,), target_suit=None))

        return tuple(actions)

    def _get_legal_actions_trick_playing(self, state: GameState) -> Tuple[Action, ...]:
        """Get legal plays for current player in trick playing phase."""
        player_hand = list(state.hands[state.current_player])
        trick_size = 6

        if not state.current_trick:
            # Leading a trick - any combination is legal
            combos = get_card_combinations(player_hand, state.trump_suit, state.player_levels[0].split(":")[1])
            return tuple(
                Action(action_type=ActionType.PLAY_CARDS, cards=combo.cards, target_suit=None)
                for combo in combos
            )

        else:
            # Following - must follow suit if possible
            led_suit = state.current_trick[0][1][0].suit
            led_count = len(state.current_trick[0][1])
            led_type = TrickCombination.SINGLE  # Simplified

            # Get legal following plays
            plays = get_legal_plays_when_following(player_hand, CardCombination((Card(led_suit, Rank.TWO, 0),), TrickCombination.SINGLE), state.trump_suit, state.player_levels[0].split(":")[1])

            return tuple(
                Action(action_type=ActionType.PLAY_CARDS, cards=play.cards, target_suit=None)
                for play in plays
            )

    def step(self, state: GameState, action: Action) -> Tuple[GameState, dict]:
        """Execute one action and return new state + info.

        Args:
            state: Current game state
            action: Action to execute

        Returns:
            (new_state, info_dict)
        """
        new_state = state  # Will be overwritten

        if action.action_type == ActionType.BID_TRUMP:
            new_state = self._handle_bid_trump(state, action)
        elif action.action_type == ActionType.PASS_TRUMP:
            new_state = self._handle_pass_trump(state, action)
        elif action.action_type == ActionType.TAKE_KITTY:
            new_state = self._handle_kitty(state, action)
        elif action.action_type == ActionType.CALL_HELPER:
            new_state = self._handle_call_helper(state, action)
        elif action.action_type == ActionType.PLAY_CARDS:
            new_state = self._handle_play_cards(state, action)

        info = {"phase": new_state.phase, "current_player": new_state.current_player}
        return (new_state, info)

    def _handle_bid_trump(self, state: GameState, action: Action) -> GameState:
        """Handle trump bid action during DEALING/TRUMP_DECLARATION phases."""
        bid = action.trump_bid
        if bid is None:
            return state

        # Update current bid and history
        new_bid_history = state.trump_bids_history + (bid,)

        # Check if trump is locked (bid count == 3)
        trump_locked = (bid.count == 3)
        new_trump_suit = bid.suit if trump_locked else None

        # Move to next player
        next_player = (state.current_player + 1) % 6

        if trump_locked:
            # Trump is locked - transition to KITTY phase immediately
            # First, add kitty cards to dealer's hand
            new_hands = self._add_kitty_to_dealer_hand(state)

            new_state = state.copy(
                phase=GamePhase.KITTY,
                current_player=state.dealer_id,
                hands=new_hands,
                trump_suit=new_trump_suit,
                trump_locked=True,
                current_trump_bid=bid,
                trump_bids_history=new_bid_history,
                legal_actions=(),  # Will be set below
            )
            # Now get legal actions with updated hand
            new_state = new_state.copy(legal_actions=self._get_legal_actions_kitty(new_state))
        else:
            # Continue bidding - move to next player
            new_state = state.copy(
                current_player=next_player,
                current_trump_bid=bid,
                trump_bids_history=new_bid_history,
                legal_actions=self._get_legal_actions_dealing(state.copy(current_player=next_player)),
            )

        return new_state

    def _handle_pass_trump(self, state: GameState, action: Action) -> GameState:
        """Handle pass trump action during DEALING/TRUMP_DECLARATION phases."""
        # Add current player to passed list
        new_passed = state.passed_players + (state.current_player,)

        # Check if all players have passed
        if len(new_passed) >= 6:
            # All passed - use fallback rule: random card from kitty
            trump_suit = self._resolve_trump_from_kitty(state)

            # Add kitty cards to dealer's hand
            new_hands = self._add_kitty_to_dealer_hand(state)

            new_state = state.copy(
                phase=GamePhase.KITTY,
                current_player=state.dealer_id,
                hands=new_hands,
                trump_suit=trump_suit,
                passed_players=new_passed,
                legal_actions=(),  # Will be set below
            )
            # Now get legal actions with updated hand
            new_state = new_state.copy(legal_actions=self._get_legal_actions_kitty(new_state))
            return new_state

        # Move to next player
        next_player = (state.current_player + 1) % 6

        new_state = state.copy(
            current_player=next_player,
            passed_players=new_passed,
            legal_actions=self._get_legal_actions_dealing(state.copy(current_player=next_player)),
        )

        return new_state

    def _resolve_trump_from_kitty(self, state: GameState) -> Suit:
        """Fallback: pick a random non-Joker card from kitty to determine trump suit."""
        non_joker_cards = [c for c in state.kitty if c.suit != Suit.JOKER]
        if non_joker_cards:
            return random.choice(non_joker_cards).suit
        else:
            # All kitty cards are Jokers (unlikely) - default to hearts
            return Suit.HEARTS

    def _add_kitty_to_dealer_hand(self, state: GameState) -> Tuple[Tuple[Card, ...], ...]:
        """Add kitty cards to dealer's hand and sort."""
        new_hands = list(state.hands)
        dealer_hand = list(new_hands[state.dealer_id])
        dealer_hand.extend(state.kitty)
        # Sort for consistency
        dealer_hand.sort(key=lambda c: (c.suit.value, c.rank.value))
        new_hands[state.dealer_id] = tuple(dealer_hand)
        return tuple(new_hands)

    def _handle_kitty(self, state: GameState, action: Action) -> GameState:
        """Handle kitty phase - dealer selects 6 cards to bury.

        The buried cards are hidden until the last trick is won.
        """
        # Cards to bury
        buried = action.cards
        if len(buried) != 6:
            # Invalid action - should have 6 cards
            return state

        # Remove buried cards from dealer's hand
        dealer_hand = list(state.hands[state.dealer_id])
        for card in buried:
            dealer_hand.remove(card)

        new_hands = list(state.hands)
        new_hands[state.dealer_id] = tuple(dealer_hand)

        # Transition to CALL_HELPER
        new_state = state.copy(
            phase=GamePhase.CALL_HELPER,
            hands=tuple(new_hands),
            buried_cards=tuple(buried),
            current_player=state.dealer_id,
            legal_actions=self._get_legal_actions_call_helper(state.copy(hands=tuple(new_hands))),
        )
        return new_state

    def _handle_call_helper(self, state: GameState, action: Action) -> GameState:
        """Handle call helper action."""
        # Record the called card
        helper_card = action.cards[0] if action.cards else None

        # Transition to TRICK_PLAYING
        new_state = state.copy(
            phase=GamePhase.TRICK_PLAYING,
            current_player=state.current_player,  # Will be set to lead player in trick playing
            helper_card=helper_card,
            legal_actions=self._get_legal_actions_trick_playing(state),
        )
        return new_state

    def _handle_play_cards(self, state: GameState, action: Action) -> GameState:
        """Handle play cards action during trick playing."""
        # Record play in current trick
        trick_play = (state.current_player, action.cards)
        current_trick = state.current_trick + (trick_play,)

        # If trick is complete (6 cards), determine winner and move to next trick
        if len(current_trick) >= 6:
            # Determine trick winner
            winner = self._determine_trick_winner(current_trick, state)

            # Update tricks won with scoring cards
            trick_cards = tuple(c for _, cards in current_trick for c in cards)
            tricks_won = state.tricks_won + (trick_cards,)

            # Determine next player (winner leads)
            next_player = current_trick[winner][0]

            # Check if all cards played (26 tricks max)
            cards_remaining = sum(len(h) for h in state.hands)
            if cards_remaining <= 0:
                # Game complete - apply buried card scoring to last trick winner
                # Buried cards belong to winner of last trick
                buried_score = 0
                if state.buried_cards:
                    multiplier = self._get_max_card_count_in_combo(trick_cards)
                    buried_score = self._compute_buried_card_score(state.buried_cards, multiplier)

                # Add buried cards to tricks won (conceptually they go to last trick winner)
                # For scoring purposes, we can add them to the last trick
                final_tricks_won = tricks_won[:-1] + (tricks_won[-1] + state.buried_cards,) if tricks_won else (state.buried_cards,)

                # Transition to SCORING
                new_state = state.copy(
                    phase=GamePhase.SCORING,
                    tricks_won=final_tricks_won,
                    legal_actions=(),
                )
                return new_state

            else:
                # Continue to next trick
                new_state = state.copy(
                    current_player=next_player,
                    current_trick=(),
                    tricks_won=tricks_won,
                    legal_actions=self._get_legal_actions_trick_playing(state.copy(current_player=next_player)),
                )
                return new_state

        else:
            # Continue trick with next player
            next_player = (state.current_player + 1) % 6
            new_state = state.copy(
                current_player=next_player,
                current_trick=current_trick,
                legal_actions=self._get_legal_actions_trick_playing(state.copy(current_player=next_player, current_trick=current_trick)),
            )
            return new_state

    def _determine_trick_winner(self, trick: Tuple[Tuple[int, Tuple[Card, ...]], ...], state: GameState) -> int:
        """Determine which player won the trick (index in trick tuple)."""
        # Simplified: just return index 0 for now
        # Full implementation would compare cards using trump hierarchy
        return 0

    def _get_max_card_count_in_combo(self, cards: Tuple[Card, ...]) -> int:
        """Get the maximum card count in a combo (for buried card multiplier)."""
        # For a simple combo, just return the count
        # For complex combos (pair+single, tractor, etc.), return the count of largest component
        # Simplified: just return the total count for now
        return len(cards)

    def _compute_buried_card_score(self, buried_cards: Tuple[Card, ...], multiplier: int) -> int:
        """Compute the score value of buried cards with multiplier.

        Scoring cards: 5 (5 pts), 10 (10 pts), K (10 pts)
        Multiplied by the max card count in the winning combo.
        """
        scoring_values = {Rank.FIVE: 5, Rank.TEN: 10, Rank.KING: 10}
        base_score = sum(scoring_values.get(card.rank, 0) for card in buried_cards)
        return base_score * multiplier
