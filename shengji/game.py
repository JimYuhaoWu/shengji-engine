"""Main game engine orchestrator."""

import random
from typing import Dict, List, Optional, Tuple
from .card import Card, Deck, count_identical_cards, get_identical_cards
from .level import LEVEL_SEQ
from .state import GameState
from .types import GamePhase, Suit, Rank, Action, ActionType, TrickCombination, TrumpBid
from .trump import (
    is_level_card, is_trump, is_captain, is_lieutenant,
    compare_cards, winning_card, trump_rank, non_trump_rank,
)
from .rules import (
    CardCombination, get_card_combinations, can_follow_suit, can_trump,
    get_legal_plays_when_following, get_legal_trump_bids,
    get_rank_order_for_suit, NON_TRUMP_RANK_ORDER,
)
from .scoring import compute_farmer_score, compute_level_changes, count_red_fives, apply_level_changes


class Game:
    """Six-player Sheng Ji game engine."""

    def __init__(self, num_players: int = 6):
        if num_players != 6:
            raise ValueError("Only 6-player games are supported")
        self.num_players = num_players

    def next_game(self, current_state: GameState) -> GameState:
        """Start the next game based on the current game's scoring.

        Reuses the same card-by-card dealing + parallel-bidding flow as the very
        first game (``reset``), carrying over the updated player levels and
        rotating to the next dealer. (A previous implementation pre-dealt every
        card and skipped that flow, which broke dealing/bidding and corrupted
        hand sizes.)

        Returns:
            New GameState for the next game with correct dealer and updated levels
        """
        if current_state.phase != GamePhase.SCORING:
            raise ValueError("Can only start next game from SCORING phase")

        next_dealer = self._determine_next_dealer(current_state)
        return self.reset(dealer_id=next_dealer, player_levels=current_state.player_levels)

    def reset(self, dealer_id: int = 0, player_levels: Optional[Tuple[str, ...]] = None) -> GameState:
        """Start a new game with card-by-card dealing and parallel bidding.

        Args:
            dealer_id: which player is the dealer (0-5)
            player_levels: carried-over level keys (e.g. from a finished game);
                defaults to everyone at R1:2 for a brand-new match.

        Returns:
            Initial GameState in DEALING phase (no cards dealt yet)
        """
        # Create full deck
        full_deck = Deck.standard_decks(3)
        random.shuffle(full_deck)

        # Initialize empty hands for each player
        hands_tuple = tuple(tuple() for _ in range(6))

        # Keep kitty (last 6 cards) and remaining cards in deck
        deck_tuple = tuple(full_deck)  # All cards start in deck

        # Player levels: carried over between games, or all R1:2 for a new match.
        if player_levels is None:
            player_levels = tuple(LEVEL_SEQ[10] for _ in range(6))  # All start at R1:2

        # Trump level is the DEALER's current level (their side sets the level).
        level_key = player_levels[dealer_id]  # e.g., "R1:2"
        trump_level = level_key.split(":")[1]  # e.g., "2"

        # Create initial state with empty hands and full deck
        state = GameState(
            phase=GamePhase.DEALING,
            current_player=0,  # Player 0 can bid first
            dealer_id=dealer_id,
            hands=hands_tuple,
            kitty=(),  # Will be set at end of dealing
            cards_dealt=0,  # No cards dealt yet
            deck=deck_tuple,  # All 162 cards in deck
            trump_suit=None,
            trump_level=trump_level,
            trump_locked=False,
            current_trump_bid=None,
            passed_players=(),
            trump_bids_history=(),
            called_rank=None,
            called_suit=None,
            helper_players=(),
            current_trick=(),
            tricks_won=(),
            player_levels=player_levels,
            scores=tuple(0 for _ in range(6)),
            legal_actions=(),
        )

        # Deal first cards and generate legal actions
        return self._deal_next_round(state)

    def _deal_next_round(self, state: GameState) -> GameState:
        """Deal one more round of cards.

        If all 26 cards have been dealt, start formal TRUMP_DECLARATION phase.
        Otherwise deal one more round and allow optional bids.
        """
        current_state = state

        # Deal one more round if not all dealt yet
        if current_state.cards_dealt < 26:
            current_state = self._deal_one_round(current_state)

        # If all cards now dealt, transition to formal TRUMP_DECLARATION
        if current_state.cards_dealt >= 26 and not current_state.formal_bidding_started:
            # Start formal bidding phase where passes are tracked
            current_state = current_state.copy(
                phase=GamePhase.TRUMP_DECLARATION,
                formal_bidding_started=True,
                current_player=0,  # Start formal bidding from player 0
                passed_players=(),  # Reset - only count formal passes now
            )

        # Generate legal actions for current phase
        return current_state.copy(legal_actions=self._get_legal_actions(current_state))

    def _deal_one_round(self, state: GameState) -> GameState:
        """Deal exactly one round of cards (one to each player).

        Does NOT generate legal actions. Use _deal_next_round for the public API.
        """
        if state.cards_dealt >= 26:
            return state

        # Deal one card to each player in order
        new_hands = list(state.hands)
        remaining_deck = list(state.deck)

        for player_id in range(6):
            if remaining_deck:
                card = remaining_deck.pop(0)
                new_hands[player_id] = new_hands[player_id] + (card,)

        new_cards_dealt = state.cards_dealt + 1
        new_state = state.copy(
            hands=tuple(new_hands),
            deck=tuple(remaining_deck),
            cards_dealt=new_cards_dealt,
        )

        # When all 26 cards dealt, extract kitty
        if new_cards_dealt == 26:
            # Extract last 6 cards as kitty
            kitty_cards = tuple(remaining_deck[-6:]) if len(remaining_deck) >= 6 else tuple()
            remaining_deck = remaining_deck[:-6] if len(remaining_deck) >= 6 else []
            new_state = new_state.copy(
                kitty=kitty_cards,
                deck=tuple(remaining_deck),
            )

        return new_state

    def _transition_to_kitty(self, state: GameState) -> GameState:
        """Transition from DEALING to KITTY phase.

        Assumes all 26 cards have been dealt and bidding has ended.
        """
        # Add kitty cards to dealer's hand
        new_hands = self._add_kitty_to_dealer_hand(state)

        new_state = state.copy(
            phase=GamePhase.KITTY,
            current_player=state.dealer_id,
            hands=new_hands,
            kitty=(),  # Clear kitty field (cards now in dealer's hand)
            legal_actions=(),  # Will be set below
        )
        # Generate legal actions with updated hand
        new_state = new_state.copy(legal_actions=self._get_legal_actions_kitty(new_state))
        return new_state

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
        """Get legal trump bid actions during DEALING phase (cards 1-26).

        During DEALING, players can bid if they have level cards.
        No formal passing tracked yet (that's in formal TRUMP_DECLARATION).
        Returns either bid actions or a default action to continue dealing.
        """
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

        # During dealing, players can pass (choose not to bid yet)
        # But this is not a formal pass - it just means continue dealing
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
        """Get legal helper-card calling actions for the dealer.

        The dealer may call any non-trump card (identified by rank+suit only),
        EXCEPT a card whose three copies are all unavailable to the other players
        (entirely in the dealer's own hand and/or the buried kitty) — calling such
        a card could never produce a helper. If that filter leaves nothing
        callable (practically impossible), fall back to all non-trump cards.
        """
        from collections import Counter

        trump_level = state.trump_level

        # Copies that are NOT available to other players (dealer's hand + buried).
        unavailable = Counter(
            (c.rank, c.suit)
            for c in list(state.hands[state.dealer_id]) + list(state.buried_cards)
        )

        actions: List[Action] = []
        fallback: List[Action] = []
        for suit in [Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS, Suit.SPADES]:
            for rank in Rank:
                if rank in (Rank.LARGE_JOKER, Rank.SMALL_JOKER):
                    continue
                card = Card(suit, rank, 0)
                if is_trump(card, state.trump_suit, trump_level):
                    continue
                action = Action(action_type=ActionType.CALL_HELPER, cards=(card,))
                fallback.append(action)
                # At least one copy must be reachable by another player.
                if unavailable[(rank, suit)] < 3:
                    actions.append(action)

        return tuple(actions) if actions else tuple(fallback)

    def _get_legal_actions_trick_playing(self, state: GameState) -> Tuple[Action, ...]:
        """Get legal plays for current player in trick playing phase."""
        player_hand = list(state.hands[state.current_player])
        trump_level = state.trump_level

        if not state.current_trick:
            # Leading a trick - any combination is legal
            combos = get_card_combinations(player_hand, state.trump_suit, trump_level)
            return tuple(
                Action(action_type=ActionType.PLAY_CARDS, cards=combo.cards)
                for combo in combos
            )

        else:
            # Following a trick - apply following rules
            led_cards = state.current_trick[0][1]
            led_suit = led_cards[0].suit
            led_is_trump = is_trump(led_cards[0], state.trump_suit, trump_level)
            led_combo_type = self._detect_combination_type(led_cards, state.trump_suit, trump_level)

            # Get legal following plays
            legal_plays = self._get_legal_following_plays(
                player_hand,
                led_suit,
                led_is_trump,
                led_combo_type,
                len(led_cards),
                state.trump_suit,
                trump_level
            )

            return tuple(
                Action(action_type=ActionType.PLAY_CARDS, cards=tuple(play))
                for play in legal_plays
            )

    def step(self, state: GameState, action: Optional[Action] = None) -> Tuple[GameState, dict]:
        """Execute one action and return new state + info.

        Args:
            state: Current game state
            action: Action to execute (can be None if auto-dealing)

        Returns:
            (new_state, info_dict)
        """
        # Special case: if action is None and we're in DEALING, auto-deal
        if action is None and state.phase == GamePhase.DEALING:
            new_state = self._deal_next_round(state)
        elif action is None:
            new_state = state
        else:
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

        # Note: dealing during the DEALING phase is driven by the action handlers
        # (_handle_bid_trump / _handle_pass_trump) and the action=None auto-deal
        # branch above, each of which deals exactly one round. We must NOT deal
        # again here or each step would advance dealing by two rounds.

        info = {
            "phase": new_state.phase,
            "current_player": new_state.current_player,
        }

        # Add SCORING info if game is over
        if new_state.phase == GamePhase.SCORING:
            farmer_score = self._calculate_farmer_score(new_state)
            next_dealer = self._determine_next_dealer(new_state)
            info.update({
                "farmer_score": farmer_score,
                "next_dealer": next_dealer,
                "game_over": True,
            })

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

        if not state.formal_bidding_started:
            # During DEALING phase: Continue dealing after bid
            new_state = state.copy(
                current_player=next_player,
                current_trump_bid=bid,
                trump_bids_history=new_bid_history,
                trump_suit=new_trump_suit,
                trump_locked=trump_locked,
                legal_actions=(),  # Will be set by _deal_next_round
            )
            # Continue dealing
            return self._deal_next_round(new_state)
        else:
            # During formal TRUMP_DECLARATION phase
            if trump_locked:
                # Trump is locked - transition to KITTY immediately
                new_hands = self._add_kitty_to_dealer_hand(state)

                new_state = state.copy(
                    phase=GamePhase.KITTY,
                    current_player=state.dealer_id,
                    hands=new_hands,
                    current_trump_bid=bid,
                    trump_bids_history=new_bid_history,
                    trump_suit=new_trump_suit,
                    trump_locked=True,
                    kitty=(),  # Clear kitty (cards already in dealer's hand)
                    legal_actions=(),  # Will be set below
                )
                # Generate legal actions for KITTY phase
                new_state = new_state.copy(legal_actions=self._get_legal_actions_kitty(new_state))
            else:
                # Continue formal bidding - move to next player, skipping those who formally passed
                while next_player in state.passed_players and len(state.passed_players) < 6:
                    next_player = (next_player + 1) % 6

                new_state = state.copy(
                    current_player=next_player,
                    current_trump_bid=bid,
                    trump_bids_history=new_bid_history,
                    legal_actions=self._get_legal_actions_trump_declaration(state.copy(current_player=next_player)),
                )

            return new_state

    def _handle_pass_trump(self, state: GameState, action: Action) -> GameState:
        """Handle pass trump action.

        During DEALING phase: Just continue to next player (not a formal pass yet)
        During formal TRUMP_DECLARATION: Track formal pass, check if all have passed
        """
        if not state.formal_bidding_started:
            # During DEALING phase: Just move to next player and continue dealing
            next_player = (state.current_player + 1) % 6
            new_state = state.copy(
                current_player=next_player,
                legal_actions=(),  # Will be set by _deal_next_round
            )
            # Continue dealing
            return self._deal_next_round(new_state)
        else:
            # During formal TRUMP_DECLARATION: Track formal passes
            new_passed = state.passed_players + (state.current_player,)

            # Check if all players have formally passed
            if len(new_passed) >= 6:
                # All formally passed. The highest standing bid (current_trump_bid)
                # sets the trump suit. Only when NO bid was ever made do we fall
                # back to drawing a random non-Joker card from the kitty.
                if state.current_trump_bid is not None:
                    trump_suit = state.current_trump_bid.suit
                    trump_locked = True
                else:
                    trump_suit = self._resolve_trump_from_kitty(state)
                    trump_locked = False
                new_hands = self._add_kitty_to_dealer_hand(state)

                new_state = state.copy(
                    phase=GamePhase.KITTY,
                    current_player=state.dealer_id,
                    hands=new_hands,
                    trump_suit=trump_suit,
                    trump_locked=trump_locked,
                    passed_players=new_passed,
                    kitty=(),  # Clear kitty (cards already in dealer's hand)
                    legal_actions=(),  # Will be set below
                )
                # Generate legal actions for KITTY phase
                new_state = new_state.copy(legal_actions=self._get_legal_actions_kitty(new_state))
                return new_state

            # Move to next player
            next_player = (state.current_player + 1) % 6
            while next_player in new_passed and len(new_passed) < 6:
                next_player = (next_player + 1) % 6

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
        """Handle call helper action.

        Dealer selects a non-trump card to call. The first two players to play
        this card (by rank+suit) become helpers.
        """
        # Extract the called card (rank and suit)
        called_card = action.cards[0] if action.cards else None
        if not called_card:
            return state

        called_rank = called_card.rank.value
        called_suit = called_card.suit

        # The legal-action generator already prevents calling a card whose three
        # copies are all in the dealer's hand/kitty, so a helper is always
        # reachable in principle. (If all copies still end up buried/with the
        # dealer, no one plays the card and there are simply no helpers.)

        # Transition to TRICK_PLAYING with dealer as first player
        new_state = state.copy(
            phase=GamePhase.TRICK_PLAYING,
            current_player=state.dealer_id,  # Dealer leads first trick
            called_rank=called_rank,
            called_suit=called_suit,
            legal_actions=self._get_legal_actions_trick_playing(state.copy(current_player=state.dealer_id)),
        )
        return new_state

    def _handle_play_cards(self, state: GameState, action: Action) -> GameState:
        """Handle play cards action during trick playing."""
        # Remove played cards from player's hand
        player_id = state.current_player
        player_hand = list(state.hands[player_id])
        for card in action.cards:
            if card in player_hand:
                player_hand.remove(card)

        new_hands = list(state.hands)
        new_hands[player_id] = tuple(player_hand)

        # Record play in current trick
        trick_play = (state.current_player, action.cards)
        current_trick = state.current_trick + (trick_play,)

        # Update helpers if called card is played
        new_helpers, new_helpers_locked = self._update_helpers(state, state.current_player, action.cards)

        # If trick is complete (6 cards), determine winner and move to next trick
        if len(current_trick) >= 6:
            # Determine trick winner
            winner_idx = self._determine_trick_winner(current_trick, state)
            winner_id = current_trick[winner_idx][0]

            # Update tricks won with winner and cards
            trick_cards = tuple(c for _, cards in current_trick for c in cards)
            tricks_won = state.tricks_won + ((winner_id, trick_cards),)

            # Determine next player (winner leads)
            next_player = current_trick[winner_idx][0]

            # Check if all cards played (26 tricks max)
            cards_remaining = sum(len(h) for h in new_hands)
            if cards_remaining <= 0:
                # Game complete - the last trick winner captures the buried kitty.
                # The buried cards are appended to the last trick (this gives their
                # base x1 points and counts any buried red fives once). The kitty
                # POINT multiplier is applied separately in scoring via
                # state.kitty_multiplier = 2 x (max-component count of the winning play).
                final_tricks_won = tricks_won
                if state.buried_cards and tricks_won:
                    last_winner_id, last_trick_cards = tricks_won[-1]
                    combined_cards = last_trick_cards + state.buried_cards
                    final_tricks_won = tricks_won[:-1] + ((last_winner_id, combined_cards),)

                # Multiplier from the winning play of this final trick
                winning_play = current_trick[winner_idx][1]
                kitty_multiplier = 2 * self._max_component_count(
                    winning_play, state.trump_suit, state.trump_level
                )

                # Calculate final state before SCORING
                state_before_scoring = state.copy(
                    hands=tuple(new_hands),
                    tricks_won=final_tricks_won,
                    helper_players=new_helpers,
                    helpers_locked=new_helpers_locked,
                    kitty_multiplier=kitty_multiplier,
                )

                # Calculate new levels
                new_levels = self._apply_level_changes(state_before_scoring)

                # Transition to SCORING
                new_state = state_before_scoring.copy(
                    phase=GamePhase.SCORING,
                    player_levels=new_levels,
                    legal_actions=(),
                )
                return new_state

            else:
                # Continue to next trick
                new_state = state.copy(
                    hands=tuple(new_hands),
                    current_player=next_player,
                    current_trick=(),
                    tricks_won=tricks_won,
                    helper_players=new_helpers,
                    helpers_locked=new_helpers_locked,
                    # current_trick=() so the new leader gets LEADING actions, not
                    # follow-plays restricted to the just-finished trick's led suit.
                    legal_actions=self._get_legal_actions_trick_playing(state.copy(hands=tuple(new_hands), current_player=next_player, current_trick=())),
                )
                return new_state

        else:
            # Continue trick with next player
            next_player = (state.current_player + 1) % 6
            new_state = state.copy(
                hands=tuple(new_hands),
                current_player=next_player,
                current_trick=current_trick,
                helper_players=new_helpers,
                helpers_locked=new_helpers_locked,
                legal_actions=self._get_legal_actions_trick_playing(state.copy(hands=tuple(new_hands), current_player=next_player, current_trick=current_trick)),
            )
            return new_state

    def _determine_trick_winner(self, trick: Tuple[Tuple[int, Tuple[Card, ...]], ...], state: GameState) -> int:
        """Determine which player won the trick (index in trick tuple).

        Rules:
        - The leader sets the structure. Its *deciding component* is the one with
          the largest group size (trio > pair > single) and, among equal group
          sizes, the longest consecutive run. That gives a signature
          ``(group_size, run_length)`` (single=(1,1), pair=(2,1), trio=(3,1),
          tractor-k=(2,k), limo-k=(3,k)).
        - A play can only win if its contention group contains a component of the
          SAME signature. So a limo-of-2 (3,2) does not match a tractor-of-3
          (2,3) even though both are 6 cards, and two loose pairs (2,1) cannot
          beat a tractor (2,2).
        - Trump beats non-trump; among contenders, trump.compare_cards ranks the
          representative (strongest card of the matching component). Lower
          components (e.g. the singles in a pair+2-singles throw) are ignored.
        - Ties keep the earliest-played player.
        """
        if not trick:
            return 0

        trump_suit = state.trump_suit
        trump_level = state.trump_level

        led_cards = trick[0][1]
        led_suit = led_cards[0].suit
        led_is_trump = is_trump(led_cards[0], trump_suit, trump_level)
        led_gs, led_run = self._deciding_signature(led_cards, trump_suit, trump_level)

        # The leader is always a valid contender and the initial best.
        best_idx = 0
        best_rep = self._winning_representative(
            led_cards, led_suit, led_is_trump, led_gs, led_run, trump_suit, trump_level
        )

        for idx in range(1, len(trick)):
            cards = trick[idx][1]
            rep = self._winning_representative(
                cards, led_suit, led_is_trump, led_gs, led_run, trump_suit, trump_level
            )
            if rep is None:
                continue  # cannot match the led structure -> cannot win
            if best_rep is None or compare_cards(rep, best_rep, led_suit, trump_suit, trump_level) > 0:
                best_rep = rep
                best_idx = idx

        return best_idx

    def _trump_ladder(self, trump_suit: Suit, trump_level: str) -> list:
        """Ordered (low -> high) list of trump 'tier' keys.

        Adjacent entries are consecutive trumps, which lets tractors/limos span
        physical suits within the trump domain (e.g. A♥ next to a non-trump level
        card, the trump level next to the Lieutenant, the two Jokers, 5♦ then 5♥).
        """
        low_to_high = list(reversed(NON_TRUMP_RANK_ORDER))  # 2,3,4,...,A
        level_rank = Rank(trump_level)
        regular = []
        for r in low_to_high:
            if r == level_rank:        # the level is its own (trump-level) tier
                continue
            if r == Rank.THREE:        # 3 of the trump suit is the Captain
                continue
            if r == Rank.FIVE and trump_suit in (Suit.HEARTS, Suit.DIAMONDS):
                continue               # 5 of a red trump suit is always-trump (5♥/5♦)
            regular.append(("reg", r))
        return regular + [
            ("nontrump_level",), ("trump_level",), ("lieutenant",), ("captain",),
            ("small_joker",), ("large_joker",), ("5d",), ("5h",),
        ]

    def _trump_tier(self, card: Card, trump_suit: Suit, trump_level: str):
        """Tier key of a trump card within :meth:`_trump_ladder` (or None)."""
        if card.rank == Rank.FIVE and card.suit == Suit.HEARTS:
            return ("5h",)
        if card.rank == Rank.FIVE and card.suit == Suit.DIAMONDS:
            return ("5d",)
        if card.rank == Rank.LARGE_JOKER:
            return ("large_joker",)
        if card.rank == Rank.SMALL_JOKER:
            return ("small_joker",)
        if is_captain(card, trump_suit):
            return ("captain",)
        if is_lieutenant(card, trump_suit):
            return ("lieutenant",)
        if is_level_card(card, trump_level):
            return ("trump_level",) if card.suit == trump_suit else ("nontrump_level",)
        if card.suit == trump_suit:
            return ("reg", card.rank)
        return None

    def _logical_runs(self, cards, group_size: int, trump_suit: Suit, trump_level: str):
        """Maximal consecutive runs of (rank,suit) groups of size >= ``group_size``.

        Cards are partitioned into logical suits — each non-trump suit, plus a
        single TRUMP domain ordered by :meth:`_trump_ladder` — so trump tractors
        and limos may span physical suits (7♥7♥ + 3♦3♦, the two Jokers, etc.).
        Returns a list of ``(run_length, cards_in_run)`` where ``run_length`` is
        the number of consecutive groups.
        """
        from collections import Counter, defaultdict

        counts = Counter((c.rank, c.suit) for c in cards)
        ladder_pos = {t: i for i, t in enumerate(self._trump_ladder(trump_suit, trump_level))}

        buckets = defaultdict(list)  # logical_suit -> [(index, rank, suit)]
        for (rank, suit), n in counts.items():
            if n < group_size:
                continue
            card = Card(suit, rank, 0)
            if is_trump(card, trump_suit, trump_level):
                tier = self._trump_tier(card, trump_suit, trump_level)
                if tier in ladder_pos:
                    buckets["TRUMP"].append((ladder_pos[tier], rank, suit))
            else:
                order = get_rank_order_for_suit(suit, trump_suit, trump_level)
                if rank in order:
                    buckets[suit].append((order.index(rank), rank, suit))

        runs = []
        for items in buckets.values():
            items.sort(key=lambda t: t[0])
            i = 0
            while i < len(items):
                j = i + 1
                while j < len(items) and items[j][0] == items[j - 1][0] + 1:
                    j += 1
                run_cards = []
                for _, rank, suit in items[i:j]:
                    run_cards.extend(
                        [c for c in cards if c.rank == rank and c.suit == suit][:group_size]
                    )
                runs.append((j - i, run_cards))
                i = j
        return runs

    def _max_run_at_group_size(
        self, cards, group_size: int, trump_suit: Suit, trump_level: str
    ) -> int:
        """Longest consecutive run of ranks that each have >= ``group_size`` copies.

        Returns 0 if no rank reaches ``group_size``. Trumps form a single logical
        suit (via the trump ladder), so cross-suit trump tractors/limos count.
        """
        runs = self._logical_runs(cards, group_size, trump_suit, trump_level)
        return max((run_len for run_len, _ in runs), default=0)

    def _deciding_signature(
        self, cards, trump_suit: Suit, trump_level: str
    ) -> Tuple[int, int]:
        """Signature (group_size, run_length) of a play's deciding component.

        Group size has priority (trio beats pair beats single); among equal group
        sizes the longer run wins. Every non-empty play has at least (1, 1).
        """
        best = (1, 1)
        for gs in (3, 2):
            run = self._max_run_at_group_size(cards, gs, trump_suit, trump_level)
            if run >= 1 and (gs, run) > best:
                best = (gs, run)
        return best

    def _winning_representative(
        self,
        cards: Tuple[Card, ...],
        led_suit: Suit,
        led_is_trump: bool,
        led_gs: int,
        led_run: int,
        trump_suit: Suit,
        trump_level: str,
    ) -> Optional[Card]:
        """Representative card used to rank a play, or None if it cannot win.

        The contention group is the cards eligible to win:
        - if the lead is trump, only trump cards contend;
        - else if the player has led-suit (non-trump) cards, those contend (they
          followed suit and cannot ruff);
        - else the player's trump cards contend (a ruff).
        A play only contends if its contention group contains a component whose
        signature matches the led ``(led_gs, led_run)`` exactly. The representative
        is then the strongest card among that group's cards of size >= led_gs.
        """
        from collections import Counter

        if led_is_trump:
            group = [c for c in cards if is_trump(c, trump_suit, trump_level)]
        else:
            led_group = [
                c for c in cards
                if c.suit == led_suit and not is_trump(c, trump_suit, trump_level)
            ]
            group = led_group if led_group else [c for c in cards if is_trump(c, trump_suit, trump_level)]

        if not group:
            return None

        # Must contain a component matching the led signature exactly.
        if self._max_run_at_group_size(group, led_gs, trump_suit, trump_level) < led_run:
            return None

        # Representative = strongest card among cards in groups of size >= led_gs
        # (for singles, the whole group qualifies). Lower components are ignored.
        counts = Counter((c.rank, c.suit) for c in group)
        if led_gs == 1:
            qualifying = list(group)
        else:
            qualifying = [c for c in group if counts[(c.rank, c.suit)] >= led_gs]
        if not qualifying:
            return None

        best = qualifying[0]
        for c in qualifying[1:]:
            if compare_cards(c, best, led_suit, trump_suit, trump_level) > 0:
                best = c
        return best

    def _max_component_count(self, cards: Tuple[Card, ...], trump_suit: Suit, trump_level: str) -> int:
        """Largest structural component (in cards) of a played combination.

        Used for the kitty-point multiplier: single=1, pair=2, trio=3,
        tractor=its length (e.g. 4 or 6), limo=its length. For a multi-component
        throw, the largest single component is returned (e.g. pair+2 singles => 2).
        """
        if len(cards) <= 1:
            return len(cards)

        from collections import Counter

        # Largest identical group (covers single/pair/trio).
        best = max(Counter((c.rank, c.suit) for c in cards).values())

        # Longest tractor / limo (logical-suit aware, so trump combos that span
        # physical suits are counted too).
        for tractor in self._find_tractors_in_suit(cards, trump_suit, trump_level):
            best = max(best, len(tractor))
        for limo in self._find_limos_in_suit(cards, trump_suit, trump_level):
            best = max(best, len(limo))

        return best

    def _player_sides(self, state: GameState) -> Tuple[Tuple[int, ...], Tuple[int, ...]]:
        """Return (dealer_side, farmer_side) player-id tuples."""
        dealer_side = tuple(sorted({state.dealer_id} | set(state.helper_players)))
        farmer_side = tuple(p for p in range(6) if p not in dealer_side)
        return dealer_side, farmer_side

    def _farmer_captured_cards(self, state: GameState) -> Tuple[Card, ...]:
        """All cards captured in tricks won by farmer-side players."""
        _, farmer_side = self._player_sides(state)
        farmer_set = set(farmer_side)
        captured: List[Card] = []
        for winner_id, cards in state.tricks_won:
            if winner_id in farmer_set:
                captured.extend(cards)
        return tuple(captured)

    def _kitty_bonus_points(self, state: GameState) -> int:
        """Extra farmer points from the multiplied kitty.

        The buried kitty is already counted once via the last trick (see the
        game-end handler), so this returns only the *additional* points from the
        multiplier, and only when a farmer won the last trick.
        """
        if not state.tricks_won or state.kitty_multiplier <= 1:
            return 0
        last_winner_id = state.tricks_won[-1][0]
        _, farmer_side = self._player_sides(state)
        if last_winner_id not in set(farmer_side):
            return 0
        base_kitty_points = compute_farmer_score(state.buried_cards)
        return base_kitty_points * (state.kitty_multiplier - 1)

    def _calculate_farmer_score(self, state: GameState) -> int:
        """Total scoring-card points captured by the farmer side.

        Includes the multiplied kitty bonus when a farmer won the last trick.
        Base card points delegate to scoring.compute_farmer_score (5=5, 10=10, K=10).
        """
        base = compute_farmer_score(self._farmer_captured_cards(state))
        return base + self._kitty_bonus_points(state)

    def _apply_level_changes(self, state: GameState) -> Tuple[str, ...]:
        """Calculate new player levels based on scoring.

        Delegates to the tested scoring.py functions so the live game loop and
        the unit-tested scoring logic cannot diverge. Red-five penalties are
        applied against the dealer side per the rules. Buried red fives count
        once (via the last trick); the kitty multiplier affects points only.

        Returns:
            Updated player_levels tuple
        """
        farmer_cards = self._farmer_captured_cards(state)
        farmer_score = self._calculate_farmer_score(state)
        hearts_fives, diamonds_fives = count_red_fives(farmer_cards)
        dealer_side, farmer_side = self._player_sides(state)

        level_changes = compute_level_changes(
            farmer_score,
            hearts_fives,
            diamonds_fives,
            dealer_side,
            farmer_side,
        )
        return apply_level_changes(state.player_levels, level_changes)

    def _determine_next_dealer(self, state: GameState) -> int:
        """Determine the dealer for the next game.

        Rules:
        - If farmer score >= 120: Farmers win, next player in clockwise order becomes dealer
        - If farmer score < 120: Dealer side wins, current dealer stays as dealer
        """
        farmer_score = self._calculate_farmer_score(state)

        if farmer_score >= 120:
            # Farmers win - next player in clockwise order becomes dealer
            return (state.dealer_id + 1) % 6
        else:
            # Dealer side wins - current dealer stays
            return state.dealer_id

    def _detect_combination_type(self, cards: Tuple[Card, ...], trump_suit: Suit, trump_level: str) -> str:
        """Detect the combination type of cards played.

        Returns: "single", "pair", "trio", "tractor", "limo", or "multi"
        """
        if len(cards) == 1:
            return "single"

        # Group cards by rank and suit
        from collections import Counter
        identical_groups = {}
        for card in cards:
            key = (card.rank, card.suit)
            identical_groups[key] = identical_groups.get(key, 0) + 1

        # Get group sizes
        group_sizes = sorted(identical_groups.values(), reverse=True)

        # Determine combination type
        if len(group_sizes) == 1:
            # All cards identical
            if group_sizes[0] == 2:
                return "pair"
            elif group_sizes[0] == 3:
                return "trio"
            elif group_sizes[0] >= 4:
                return "tractor" if self._is_tractor(cards, trump_suit, trump_level) else "multi"
        else:
            # Mixed groups - could be tractor, limo, or multi
            if all(size == 2 for size in group_sizes) and len(group_sizes) >= 2:
                if self._is_tractor(cards, trump_suit, trump_level):
                    return "tractor"
            elif all(size == 3 for size in group_sizes) and len(group_sizes) >= 2:
                if self._is_limo(cards, trump_suit, trump_level):
                    return "limo"
            return "multi"

        return "multi"

    def _is_tractor(self, cards: Tuple[Card, ...], trump_suit: Suit, trump_level: str) -> bool:
        """Check if cards form a valid tractor (>= 2 consecutive pairs).

        Logical-suit aware, so trump-hierarchy tractors that span physical suits
        (e.g. 7♥7♥ + 3♦3♦) are recognized.
        """
        from collections import Counter

        counts = Counter((c.rank, c.suit) for c in cards)
        if len(counts) < 2 or any(n != 2 for n in counts.values()):
            return False  # must be all pairs, at least two of them
        return any(
            run_len == len(counts)
            for run_len, _ in self._logical_runs(cards, 2, trump_suit, trump_level)
        )

    def _is_limo(self, cards: Tuple[Card, ...], trump_suit: Suit, trump_level: str) -> bool:
        """Check if cards form a valid limo (>= 2 consecutive trios), logical-suit aware."""
        from collections import Counter

        counts = Counter((c.rank, c.suit) for c in cards)
        if len(counts) < 2 or any(n != 3 for n in counts.values()):
            return False  # must be all trios, at least two of them
        return any(
            run_len == len(counts)
            for run_len, _ in self._logical_runs(cards, 3, trump_suit, trump_level)
        )

    def _get_legal_following_plays(self, hand: list, led_suit: Suit, led_is_trump: bool,
                                   led_combo_type: str, trick_size: int,
                                   trump_suit: Suit, trump_level: str) -> List[Tuple[Card, ...]]:
        """Generate all legal plays when following a trick.

        Combination matching rules:
        - Single: play a single
        - Pair: play a pair if any, else singles
        - Trio: play a trio if any, else pair+single, else three singles
        - Tractor: play a tractor if any, else two pairs, else pair+two singles, else four singles
        - Limo: play a limo, else two trios, else trio+pair+single, else tractor+two singles,
                else two pairs+two singles, else pair+four singles, else six singles
        """
        from itertools import combinations

        legal_plays = []
        # "Following suit" works on logical suits: all trumps (jokers, level
        # cards, 5♥/5♦, Captain/Lieutenant, trump-suit cards) form ONE suit, and
        # a non-trump lead only obliges non-trump cards of that physical suit.
        if led_is_trump:
            follows = lambda c: is_trump(c, trump_suit, trump_level)
        else:
            follows = lambda c: c.suit == led_suit and not is_trump(c, trump_suit, trump_level)
        led_suit_cards = [c for c in hand if follows(c)]

        if led_suit_cards:
            # Has led suit cards - must follow suit
            if led_combo_type == "single":
                for card in led_suit_cards:
                    legal_plays.append((card,))

            elif led_combo_type == "pair":
                # Pair → a pair if any, else two singles of the led suit.
                # Must always play trick_size (2) cards to keep hand sizes in sync.
                pairs = self._find_pairs_in_suit(led_suit_cards)
                if pairs:
                    legal_plays.extend([tuple(p) for p in pairs])
                elif len(led_suit_cards) >= 2:
                    # No pair available but enough led-suit cards: play any two singles
                    for combo in combinations(led_suit_cards, 2):
                        legal_plays.append(combo)
                # If only 1 led-suit card, the insufficient-led-suit fill branch below
                # handles it (play the single + one card of another suit).

            elif led_combo_type == "trio":
                # Trio → pair+single → three singles
                trios = self._find_trios_in_suit(led_suit_cards)
                if trios:
                    for trio in trios:
                        legal_plays.append(tuple(trio))
                else:
                    # Try pair+single
                    pairs = self._find_pairs_in_suit(led_suit_cards)
                    if pairs:
                        for pair in pairs:
                            for single in led_suit_cards:
                                if single not in pair:
                                    legal_plays.append(tuple(pair + [single]))
                    # Three singles
                    if len(led_suit_cards) >= 3:
                        for combo in combinations(led_suit_cards, 3):
                            legal_plays.append(combo)

            elif led_combo_type == "tractor":
                # Tractor → two pairs → pair+two singles → four singles
                tractors = self._find_tractors_in_suit(led_suit_cards, trump_suit, trump_level)
                if tractors:
                    for tractor in tractors:
                        legal_plays.append(tuple(tractor))
                else:
                    # Two pairs
                    pairs = self._find_pairs_in_suit(led_suit_cards)
                    if len(pairs) >= 2:
                        for combo in combinations(pairs, 2):
                            legal_plays.append(tuple(combo[0] + combo[1]))
                    # Pair + two singles
                    if pairs:
                        for pair in pairs:
                            remaining = [c for c in led_suit_cards if c not in pair]
                            if len(remaining) >= 2:
                                for singles in combinations(remaining, 2):
                                    legal_plays.append(tuple(pair + list(singles)))
                    # Four singles
                    if len(led_suit_cards) >= 4:
                        for combo in combinations(led_suit_cards, 4):
                            legal_plays.append(combo)

            elif led_combo_type == "limo":
                # Limo → two trios → trio+pair+single → tractor+two singles →
                # two pairs+two singles → pair+four singles → six singles
                limos = self._find_limos_in_suit(led_suit_cards, trump_suit, trump_level)
                if limos:
                    for limo in limos:
                        legal_plays.append(tuple(limo))
                else:
                    trios = self._find_trios_in_suit(led_suit_cards)
                    # Two trios
                    if len(trios) >= 2:
                        for combo in combinations(trios, 2):
                            legal_plays.append(tuple(combo[0] + combo[1]))
                    # Trio + pair + single
                    if trios and len(led_suit_cards) >= 6:
                        pairs = self._find_pairs_in_suit(led_suit_cards)
                        for trio in trios:
                            for pair in pairs:
                                if not any(c in trio for c in pair):
                                    remaining = [c for c in led_suit_cards if c not in trio and c not in pair]
                                    if remaining:
                                        legal_plays.append(tuple(trio + pair + [remaining[0]]))
                    # Tractor + two singles
                    tractors = self._find_tractors_in_suit(led_suit_cards, trump_suit, trump_level)
                    if tractors:
                        for tractor in tractors:
                            remaining = [c for c in led_suit_cards if c not in tractor]
                            if len(remaining) >= 2:
                                for singles in combinations(remaining, 2):
                                    legal_plays.append(tuple(tractor + list(singles)))
                    # Two pairs + two singles
                    pairs = self._find_pairs_in_suit(led_suit_cards)
                    if len(pairs) >= 2:
                        for pair_combo in combinations(pairs, 2):
                            remaining = [c for c in led_suit_cards if c not in pair_combo[0] and c not in pair_combo[1]]
                            if len(remaining) >= 2:
                                for singles in combinations(remaining, 2):
                                    legal_plays.append(tuple(pair_combo[0] + pair_combo[1] + list(singles)))
                    # Pair + four singles
                    for pair in pairs:
                        remaining = [c for c in led_suit_cards if c not in pair]
                        if len(remaining) >= 4:
                            for singles in combinations(remaining, 4):
                                legal_plays.append(tuple(pair + list(singles)))
                    # Six singles
                    if len(led_suit_cards) >= 6:
                        for combo in combinations(led_suit_cards, 6):
                            legal_plays.append(combo)

            elif led_combo_type == "multi":
                # Multi: play matching count
                if len(led_suit_cards) >= trick_size:
                    for combo in combinations(led_suit_cards, trick_size):
                        legal_plays.append(combo)

            # If insufficient led suit cards - play all + fill with any other cards
            if not legal_plays and len(led_suit_cards) < trick_size:
                other_cards = [c for c in hand if not follows(c)]
                needed = trick_size - len(led_suit_cards)
                if len(other_cards) >= needed:
                    for other_combo in combinations(other_cards, needed):
                        legal_plays.append(tuple(led_suit_cards + list(other_combo)))

        else:
            # No led suit cards - can play any combination of trick_size
            if len(hand) >= trick_size:
                for combo in combinations(hand, trick_size):
                    legal_plays.append(combo)

        if legal_plays:
            return legal_plays

        # Safety fallback: always play exactly trick_size cards to keep hand
        # sizes synchronized across players. This should rarely trigger.
        if len(hand) >= trick_size:
            return [combo for combo in combinations(hand, trick_size)]
        elif hand:
            return [tuple(hand)]
        return [()]

    def _find_pairs_in_suit(self, cards: list) -> List[List[Card]]:
        """Find all pairs in a list of cards (same rank and suit)."""
        from collections import Counter
        rank_suit_counts = Counter((c.rank, c.suit) for c in cards)
        pairs = []
        for (rank, suit), count in rank_suit_counts.items():
            if count >= 2:
                pair_cards = [c for c in cards if c.rank == rank and c.suit == suit][:2]
                pairs.append(pair_cards)
        return pairs

    def _find_trios_in_suit(self, cards: list) -> List[List[Card]]:
        """Find all trios in a list of cards (same rank and suit)."""
        from collections import Counter
        rank_suit_counts = Counter((c.rank, c.suit) for c in cards)
        trios = []
        for (rank, suit), count in rank_suit_counts.items():
            if count >= 3:
                trio_cards = [c for c in cards if c.rank == rank and c.suit == suit][:3]
                trios.append(trio_cards)
        return trios

    def _find_tractors_in_suit(self, cards: list, trump_suit: Suit, trump_level: str) -> List[List[Card]]:
        """Find all tractors (>= 2 consecutive pairs) among ``cards``.

        Trumps are treated as one logical suit via the trump ladder, so a tractor
        may span physical suits (e.g. 7♥7♥ + 3♦3♦ when 7 is the level, or a pair
        of each Joker). Non-trump tractors stay within their own suit.
        """
        return [
            run_cards
            for run_len, run_cards in self._logical_runs(cards, 2, trump_suit, trump_level)
            if run_len >= 2
        ]

    def _find_limos_in_suit(self, cards: list, trump_suit: Suit, trump_level: str) -> List[List[Card]]:
        """Find all limos (>= 2 consecutive trios) among ``cards`` (logical-suit aware)."""
        return [
            run_cards
            for run_len, run_cards in self._logical_runs(cards, 3, trump_suit, trump_level)
            if run_len >= 2
        ]

    def _update_helpers(
        self, state: GameState, player_id: int, cards_played: Tuple[Card, ...]
    ) -> Tuple[Tuple[int, ...], bool]:
        """Update the helper set when a player plays cards.

        Returns ``(helper_players, helpers_locked)``.
        Rules:
        - The dealer can NEVER be a helper (helpers are the dealer's partners);
          the dealer playing the called card does not make them a helper.
        - First (non-dealer) player to play the called card becomes helper #1.
        - The second *different* player to play it becomes helper #2 (which then
          locks the set).
        - If a player plays 2+ copies of the called card BEFORE anyone else has
          played it, that player is the SOLE helper and the set is locked
          immediately (no second helper may join).
        """
        helpers = state.helper_players
        locked = state.helpers_locked

        if locked or not state.called_rank or not state.called_suit:
            return helpers, locked

        # The dealer is the declarer, not a helper — ignore their plays here.
        if player_id == state.dealer_id:
            return helpers, locked

        called_card_count = sum(
            1 for c in cards_played
            if c.rank.value == state.called_rank and c.suit == state.called_suit
        )
        if called_card_count == 0:
            return helpers, locked

        if len(helpers) == 0:
            if called_card_count >= 2:
                # Sole helper: 2+ copies before anyone else played it -> sealed.
                return (player_id,), True
            return (player_id,), False  # first helper; a second may still join

        # len(helpers) == 1 (not locked, so the lone helper was not a sole helper)
        if player_id == helpers[0]:
            return helpers, locked  # same player again, no change
        return (helpers[0], player_id), True  # second helper -> sealed
