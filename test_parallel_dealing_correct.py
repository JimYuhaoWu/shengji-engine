"""Test the corrected parallel dealing with continuous card distribution."""

from shengji.game import Game
from shengji.types import GamePhase, ActionType

game = Game()
state = game.reset(dealer_id=0)

print("Testing corrected parallel dealing:")
print("Cards should continue to be dealt until 26, even after bidding ends")
print("=" * 70)

step = 0
max_steps = 300
bidding_ended_at = None

while state.phase == GamePhase.DEALING and step < max_steps:
    cards_per_player = len(state.hands[0])
    print(f"[Step {step}] Cards/player: {cards_per_player:2d}, Bidding ended: {state.bidding_ended}, Hands: {[len(h) for h in state.hands]}")

    if state.legal_actions:
        action = state.legal_actions[0]
        if action.action_type == ActionType.BID_TRUMP:
            bid = action.trump_bid
            print(f"          -> BID {bid.count}x {bid.suit.value}")
        elif action.action_type == ActionType.PASS_TRUMP:
            print(f"          -> PASS")
    else:
        # No legal actions means bidding ended, just dealing cards
        if not state.bidding_ended and bidding_ended_at is None:
            bidding_ended_at = step
            print(f"          -> Bidding ends, but dealing continues...")

    if state.legal_actions:
        state, _ = game.step(state, state.legal_actions[0])
    else:
        # No legal actions means bidding ended, auto-deal
        state, _ = game.step(state, None)
    step += 1

    if state.phase != GamePhase.DEALING:
        print(f"\nTransitioned to {state.phase}")
        break

print(f"\nFinal state:")
print(f"  Phase: {state.phase}")
print(f"  Cards per player: {len(state.hands[0])}")
print(f"  All players have 26 cards: {all(len(h) == 26 for h in state.hands)}")
print(f"  Bidding ended at step: {bidding_ended_at}")
print(f"  Trump suit: {state.trump_suit}")
