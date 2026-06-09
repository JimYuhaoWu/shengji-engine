"""Detailed test of card-by-card dealing with bidding timeline."""

from shengji.game import Game
from shengji.types import GamePhase, ActionType

game = Game()
state = game.reset(dealer_id=0)

print("Card-by-card dealing with bidding timeline:")
print("=" * 70)

step = 0
while state.phase == GamePhase.DEALING and step < 50:
    player_id = state.current_player
    cards_per_player = [len(h) for h in state.hands]

    # Show state before action
    print(f"\n[Step {step}] Cards/player: {cards_per_player[0]}")
    print(f"  Current player: {player_id}")
    print(f"  Legal actions: {len(state.legal_actions)}")

    # Show what action will be taken
    action = state.legal_actions[0]
    if action.action_type == ActionType.BID_TRUMP:
        bid = action.trump_bid
        print(f"  Action: BID {bid.count}x {bid.suit.value} by player {bid.bidder_id}")
    elif action.action_type == ActionType.PASS_TRUMP:
        print(f"  Action: PASS by player {player_id}")

    if not state.legal_actions:
        print("ERROR: No legal actions!")
        break

    state, info = game.step(state, action)
    step += 1

    # Show state after action
    if state.phase != GamePhase.DEALING:
        print(f"\n  -> Transitioned to {state.phase}")
        break

print(f"\nFinal state:")
print(f"  Phase: {state.phase}")
print(f"  Cards dealt per player: {len(state.hands[0])}")
print(f"  Total cards in play: {sum(len(h) for h in state.hands)}")
print(f"  Trump suit: {state.trump_suit}")
print(f"  Bid history: {[(b.count, b.suit.value, f'Player {b.bidder_id}') for b in state.trump_bids_history]}")
