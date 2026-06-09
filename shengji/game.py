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

    def next_game(self, current_state: GameState) -> GameState:
        """Start the next game based on the current game's scoring.

        Returns:
            New GameState for the next game with correct dealer and updated levels
        """
        if current_state.phase != GamePhase.SCORING:
            raise ValueError("Can only start next game from SCORING phase")

        # Determine next dealer
        next_dealer = self._determine_next_dealer(current_state)

        # Get updated levels from current state
        new_levels = current_state.player_levels

        # Extract trump level from the level system
        level_key = new_levels[0]  # All players should have been updated
        trump_level = level_key.split(":")[1]

        # Deal cards
        deck = Deck.standard_decks(3)
        import random
        random.shuffle(deck)

        hands: List[List[Card]] = [[] for _ in range(6)]
        for i, card in enumerate(deck[:156]):  # 6 × 26 = 156 cards
            hands[i % 6].append(card)

        # Remaining 6 cards are kitty
        kitty = deck[156:162]

        # Convert hands to sorted tuples
        hands_tuple = tuple(tuple(sorted(hand, key=lambda c: (c.suit.value, c.rank.value))) for hand in hands)
        kitty_tuple = tuple(kitty)

        # Create initial state for next game
        state = GameState(
            phase=GamePhase.DEALING,
            current_player=0,
            dealer_id=next_dealer,
            hands=hands_tuple,
            kitty=kitty_tuple,
            trump_suit=None,
            trump_level=trump_level,
            trump_locked=False,
            current_trump_bid=None,
            passed_players=(),
            trump_bids_history=(),
            buried_cards=(),
            called_rank=None,
            called_suit=None,
            helper_players=(),
            current_trick=(),
            tricks_won=(),
            player_levels=new_levels,
            scores=tuple(0 for _ in range(6)),
            legal_actions=(),
        )

        # Generate legal actions for first player
        legal_actions = self._get_legal_actions(state)
        return state.copy(legal_actions=legal_actions)

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
            called_rank=None,
            called_suit=None,
            helper_players=(),
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
        """Get legal helper card calling actions for dealer.

        Dealer can call any non-trump card (identified by rank+suit only).
        """
        actions: List[Action] = []
        trump_level = state.trump_level

        # Collect all possible non-trump cards that could be called
        for suit in [Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS, Suit.SPADES]:
            for rank in Rank:
                if rank == Rank.LARGE_JOKER or rank == Rank.SMALL_JOKER:
                    continue
                # Check if this rank+suit combo is non-trump
                card = Card(suit, rank, 0)
                if not is_trump(card, state.trump_suit, trump_level):
                    # Store as action with rank and suit (deck_id doesn't matter for calling)
                    actions.append(Action(
                        action_type=ActionType.CALL_HELPER,
                        cards=(card,)  # Just one card representation (deck_id=0)
                    ))

        return tuple(actions)

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
            led_combo_type = self._detect_combination_type(led_cards, state.trump_suit, trump_level)

            # Get legal following plays
            legal_plays = self._get_legal_following_plays(
                player_hand,
                led_suit,
                led_combo_type,
                len(led_cards),
                state.trump_suit,
                trump_level
            )

            return tuple(
                Action(action_type=ActionType.PLAY_CARDS, cards=tuple(play))
                for play in legal_plays
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

        # Check if called card exists in the game (not all buried/in dealer hand)
        # Count copies of called card in hands and buried
        called_count = 0
        for hand in state.hands:
            called_count += sum(1 for c in hand if c.rank == called_card.rank and c.suit == called_suit)
        called_count += sum(1 for c in state.buried_cards if c.rank == called_card.rank and c.suit == called_suit)

        # If all 3 copies are with dealer or buried, there are no helpers
        # (This is determined after cards are visible, but we can check now)

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
        # Record play in current trick
        trick_play = (state.current_player, action.cards)
        current_trick = state.current_trick + (trick_play,)

        # Update helpers if called card is played
        new_helpers = self._update_helpers(state, state.current_player, action.cards)

        # If trick is complete (6 cards), determine winner and move to next trick
        if len(current_trick) >= 6:
            # Determine trick winner
            winner_idx = self._determine_trick_winner(current_trick, state)
            winner_id = current_trick[winner_idx][0]

            # Update tricks won with winner and cards
            trick_cards = tuple(c for _, cards in current_trick for c in cards)
            tricks_won = state.tricks_won + ((winner_id, trick_cards),)

            # Determine next player (winner leads)
            next_player = current_trick[winner][0]

            # Check if all cards played (26 tricks max)
            cards_remaining = sum(len(h) for h in state.hands)
            if cards_remaining <= 0:
                # Game complete - add buried cards to last trick winner
                final_tricks_won = tricks_won
                if state.buried_cards and tricks_won:
                    # Last trick winner also gets the buried cards (with multiplier applied in scoring)
                    last_winner_id, last_trick_cards = tricks_won[-1]
                    combined_cards = last_trick_cards + state.buried_cards
                    final_tricks_won = tricks_won[:-1] + ((last_winner_id, combined_cards),)

                # Calculate final state before SCORING
                state_before_scoring = state.copy(
                    tricks_won=final_tricks_won,
                    helper_players=new_helpers,
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
                    current_player=next_player,
                    current_trick=(),
                    tricks_won=tricks_won,
                    helper_players=new_helpers,
                    legal_actions=self._get_legal_actions_trick_playing(state.copy(current_player=next_player)),
                )
                return new_state

        else:
            # Continue trick with next player
            next_player = (state.current_player + 1) % 6
            new_state = state.copy(
                current_player=next_player,
                current_trick=current_trick,
                helper_players=new_helpers,
                legal_actions=self._get_legal_actions_trick_playing(state.copy(current_player=next_player, current_trick=current_trick)),
            )
            return new_state

    def _determine_trick_winner(self, trick: Tuple[Tuple[int, Tuple[Card, ...]], ...], state: GameState) -> int:
        """Determine which player won the trick (index in trick tuple).

        Rules:
        - Compare the component with maximum card count
        - Trump > non-trump
        - Within trump: higher trump rank wins
        - Within led suit: higher rank wins
        - Tie: earliest played player wins
        """
        if not trick:
            return 0

        # Get led suit from first player's cards
        first_player_cards = trick[0][1]
        led_suit = first_player_cards[0].suit

        trump_suit = state.trump_suit
        trump_level = state.trump_level

        # For each player in the trick, get their strongest card of led suit (or trump)
        best_idx = 0
        best_card = None
        best_rank = -1

        for idx, (player_id, cards) in enumerate(trick):
            # Find the highest card this player played (led suit first, then trump)
            player_best_card = None
            player_best_rank = -1

            # Check led suit cards
            led_suit_cards = [c for c in cards if c.suit == led_suit]
            if led_suit_cards:
                for card in led_suit_cards:
                    if is_trump(card, trump_suit, trump_level):
                        rank = trump_rank(card, trump_suit, trump_level)
                    else:
                        rank = non_trump_rank(card)
                    if rank > player_best_rank:
                        player_best_rank = rank
                        player_best_card = card
            else:
                # No led suit cards, check for trump
                trump_cards = [c for c in cards if is_trump(c, trump_suit, trump_level)]
                if trump_cards:
                    for card in trump_cards:
                        rank = trump_rank(card, trump_suit, trump_level)
                        if rank > player_best_rank:
                            player_best_rank = rank
                            player_best_card = card

            # Compare with current best
            if player_best_card is not None:
                if best_card is None or player_best_rank > best_rank:
                    best_rank = player_best_rank
                    best_card = player_best_card
                    best_idx = idx
                # If tie, keep the earliest played (earliest idx)

        return best_idx

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

    def _calculate_farmer_score(self, state: GameState) -> int:
        """Calculate total score for the farmer side.

        Farmers are all players except dealer and helpers.
        Sum all scoring cards captured by farmer players.
        """
        farmer_players = set(range(6)) - {state.dealer_id} - set(state.helper_players)

        total_score = 0
        scoring_values = {Rank.FIVE: 5, Rank.TEN: 10, Rank.KING: 10}

        for winner_id, cards in state.tricks_won:
            if winner_id in farmer_players:
                for card in cards:
                    total_score += scoring_values.get(card.rank, 0)

        return total_score

    def _get_level_change(self, farmer_score: int) -> int:
        """Determine level change based on farmer score.

        Returns:
            Positive for farmer win, negative for dealer win, 0 for no change
        """
        if farmer_score == 0:
            return -3  # Dealer side +3
        elif farmer_score <= 55:
            return -2  # Dealer side +2
        elif farmer_score <= 115:
            return -1  # Dealer side +1
        elif farmer_score <= 175:
            return 0   # Farmer win (neutral, resets)
        elif farmer_score <= 235:
            return 1   # Farmer side +1
        elif farmer_score <= 295:
            return 2   # Farmer side +2
        else:
            return 3   # Farmer side +3

    def _count_red_fives(self, state: GameState) -> Tuple[int, int]:
        """Count red fives (5♥ and 5♦) captured by farmers.

        Returns:
            (count_5♥, count_5♦)
        """
        farmer_players = set(range(6)) - {state.dealer_id} - set(state.helper_players)

        count_hearts_five = 0
        count_diamonds_five = 0

        for winner_id, cards in state.tricks_won:
            if winner_id in farmer_players:
                for card in cards:
                    if card.rank == Rank.FIVE:
                        if card.suit == Suit.HEARTS:
                            count_hearts_five += 1
                        elif card.suit == Suit.DIAMONDS:
                            count_diamonds_five += 1

        return (count_hearts_five, count_diamonds_five)

    def _apply_level_changes(self, state: GameState) -> Tuple[str, ...]:
        """Calculate new player levels based on scoring.

        Returns:
            Updated player_levels tuple
        """
        farmer_score = self._calculate_farmer_score(state)
        base_change = self._get_level_change(farmer_score)

        # Apply red five penalties (subtracted from dealer side, which means added to farmer side)
        hearts_fives, diamonds_fives = self._count_red_fives(state)
        red_five_penalty = hearts_fives * 2 + diamonds_fives * 1
        total_change = base_change - red_five_penalty

        # Update all players
        new_levels = []
        for player_id in range(6):
            current_level = state.player_levels[player_id]
            if player_id == state.dealer_id or player_id in state.helper_players:
                # Dealer side: opposite of farmer change
                new_level = step_level(current_level, -total_change)
            else:
                # Farmer side
                new_level = step_level(current_level, total_change)
            new_levels.append(new_level)

        return tuple(new_levels)

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
        """Check if cards form a valid tractor (consecutive pairs)."""
        # Extract pairs
        from collections import Counter
        rank_suit_counts = Counter((c.rank, c.suit) for c in cards)

        pairs = [rs for rs, count in rank_suit_counts.items() if count == 2]
        if len(pairs) < 2:
            return False

        # Check if pairs are consecutive in the suit's rank ordering
        suit = pairs[0][1]
        for rank_suit, count in rank_suit_counts.items():
            if rank_suit[1] != suit or count != 2:
                return False

        # Get rank order for this suit
        from .rules import get_rank_order_for_suit
        rank_order = get_rank_order_for_suit(suit, trump_suit, trump_level)

        pair_ranks = sorted([rs[0] for rs in pairs], key=lambda r: rank_order.index(r) if r in rank_order else -1)

        # Check if consecutive
        for i in range(len(pair_ranks) - 1):
            if rank_order.index(pair_ranks[i]) + 1 != rank_order.index(pair_ranks[i + 1]):
                return False

        return True

    def _is_limo(self, cards: Tuple[Card, ...], trump_suit: Suit, trump_level: str) -> bool:
        """Check if cards form a valid limo (consecutive trios)."""
        from collections import Counter
        rank_suit_counts = Counter((c.rank, c.suit) for c in cards)

        trios = [rs for rs, count in rank_suit_counts.items() if count == 3]
        if len(trios) < 2:
            return False

        # Check if trios are in same suit and consecutive
        suit = trios[0][1]
        for rank_suit, count in rank_suit_counts.items():
            if rank_suit[1] != suit or count != 3:
                return False

        # Get rank order for this suit
        from .rules import get_rank_order_for_suit
        rank_order = get_rank_order_for_suit(suit, trump_suit, trump_level)

        trio_ranks = sorted([rs[0] for rs in trios], key=lambda r: rank_order.index(r) if r in rank_order else -1)

        # Check if consecutive
        for i in range(len(trio_ranks) - 1):
            if rank_order.index(trio_ranks[i]) + 1 != rank_order.index(trio_ranks[i + 1]):
                return False

        return True

    def _get_legal_following_plays(self, hand: list, led_suit: Suit, led_combo_type: str, trick_size: int,
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
        led_suit_cards = [c for c in hand if c.suit == led_suit]

        if led_suit_cards:
            # Has led suit cards - must follow suit
            if led_combo_type == "single":
                for card in led_suit_cards:
                    legal_plays.append((card,))

            elif led_combo_type == "pair":
                # Pair → singles
                pairs = self._find_pairs_in_suit(led_suit_cards)
                if pairs:
                    for pair in pairs:
                        legal_plays.extend([tuple(p) for p in pairs])
                        break  # Only add each pair type once
                else:
                    for card in led_suit_cards:
                        legal_plays.append((card,))

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
                other_cards = [c for c in hand if c.suit != led_suit]
                needed = trick_size - len(led_suit_cards)
                if len(other_cards) >= needed:
                    for other_combo in combinations(other_cards, needed):
                        legal_plays.append(tuple(led_suit_cards + list(other_combo)))

        else:
            # No led suit cards - can play any combination of trick_size
            if len(hand) >= trick_size:
                for combo in combinations(hand, trick_size):
                    legal_plays.append(combo)

        return legal_plays if legal_plays else [(hand[0],)] if hand else [()]

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
        """Find all consecutive pair groups (tractors) in cards of the same suit."""
        if len(cards) < 4:
            return []

        from collections import Counter
        from .rules import get_rank_order_for_suit

        # Get the suit
        suit = cards[0].suit

        # Count cards by rank
        rank_counts = Counter(c.rank for c in cards if c.suit == suit)

        # Get rank order for this suit
        rank_order = get_rank_order_for_suit(suit, trump_suit, trump_level)

        # Find all pairs
        pair_ranks = [rank for rank, count in rank_counts.items() if count >= 2]
        if len(pair_ranks) < 2:
            return []

        # Sort by rank order
        pair_ranks.sort(key=lambda r: rank_order.index(r) if r in rank_order else 999)

        # Find consecutive sequences
        tractors = []
        i = 0
        while i < len(pair_ranks):
            sequence = [pair_ranks[i]]
            j = i + 1
            while j < len(pair_ranks):
                if rank_order.index(pair_ranks[j]) == rank_order.index(pair_ranks[j - 1]) + 1:
                    sequence.append(pair_ranks[j])
                    j += 1
                else:
                    break

            if len(sequence) >= 2:
                # Build tractor from this sequence
                tractor_cards = []
                for rank in sequence:
                    rank_cards = [c for c in cards if c.rank == rank and c.suit == suit][:2]
                    tractor_cards.extend(rank_cards)
                tractors.append(tractor_cards)

            i = j if j > i + 1 else i + 1

        return tractors

    def _find_limos_in_suit(self, cards: list, trump_suit: Suit, trump_level: str) -> List[List[Card]]:
        """Find all consecutive trio groups (limos) in cards of the same suit."""
        if len(cards) < 6:
            return []

        from collections import Counter
        from .rules import get_rank_order_for_suit

        # Get the suit
        suit = cards[0].suit

        # Count cards by rank
        rank_counts = Counter(c.rank for c in cards if c.suit == suit)

        # Get rank order for this suit
        rank_order = get_rank_order_for_suit(suit, trump_suit, trump_level)

        # Find all trios
        trio_ranks = [rank for rank, count in rank_counts.items() if count >= 3]
        if len(trio_ranks) < 2:
            return []

        # Sort by rank order
        trio_ranks.sort(key=lambda r: rank_order.index(r) if r in rank_order else 999)

        # Find consecutive sequences
        limos = []
        i = 0
        while i < len(trio_ranks):
            sequence = [trio_ranks[i]]
            j = i + 1
            while j < len(trio_ranks):
                if rank_order.index(trio_ranks[j]) == rank_order.index(trio_ranks[j - 1]) + 1:
                    sequence.append(trio_ranks[j])
                    j += 1
                else:
                    break

            if len(sequence) >= 2:
                # Build limo from this sequence
                limo_cards = []
                for rank in sequence:
                    rank_cards = [c for c in cards if c.rank == rank and c.suit == suit][:3]
                    limo_cards.extend(rank_cards)
                limos.append(limo_cards)

            i = j if j > i + 1 else i + 1

        return limos

    def _update_helpers(self, state: GameState, player_id: int, cards_played: Tuple[Card, ...]) -> Tuple[int, ...]:
        """Update helper list when a player plays cards.

        Returns updated helper_players tuple.
        Rules:
        - First player to play called card becomes helper #1
        - Second player to play called card becomes helper #2
        - If someone plays 2+ copies before anyone else plays it, they become sole helper
        """
        if not state.called_rank or not state.called_suit:
            return state.helper_players

        # Count how many called cards this player is playing
        called_card_count = sum(
            1 for c in cards_played
            if c.rank.value == state.called_rank and c.suit == state.called_suit
        )

        if called_card_count == 0:
            # Not playing called card
            return state.helper_players

        current_helpers = list(state.helper_players)

        # Check if this is the first called card played
        if len(current_helpers) == 0:
            # No helpers yet
            if called_card_count >= 2:
                # Playing 2+ copies - become sole helper
                return (player_id,)
            else:
                # Playing 1 copy - become first helper
                return (player_id,)

        elif len(current_helpers) == 1:
            # Already have one helper
            if current_helpers[0] == player_id:
                # Same player playing again - no change
                return current_helpers
            else:
                # Different player - becomes second helper
                return (current_helpers[0], player_id)

        else:
            # Already have 2 helpers, no changes
            return current_helpers
