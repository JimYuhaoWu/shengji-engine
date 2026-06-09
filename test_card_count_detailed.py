"""Detailed debugging of card counts."""

from shengji.game import Game
from shengji.types import GamePhase

game = Game()
state = game.reset(dealer_id=0)

print("Game reset:")
print(f"  Hands: {[len(h) for h in state.hands]} = {sum(len(h) for h in state.hands)} total")
print(f"  Kitty: {len(state.kitty)}")
print(f"  Deck: {len(state.deck)}")
print(f"  TOTAL: {sum(len(h) for h in state.hands) + len(state.kitty) + len(state.deck)}")
print()

# Fast-forward to KITTY phase
step = 0
while state.phase == GamePhase.DEALING and step < 100:
    if not state.legal_actions:
        print(f"[Step {step}] NO LEGAL ACTIONS!")
        break

    action = state.legal_actions[0]
    print(f"[Step {step}] Action: {action.action_type.name}, cards_dealt={state.cards_dealt}")

    state, _ = game.step(state, action)
    step += 1

print(f"\nAfter DEALING phase ({state.phase.name}):")
print(f"  Hands: {[len(h) for h in state.hands]} = {sum(len(h) for h in state.hands)} total")
print(f"  Kitty: {len(state.kitty)}")
print(f"  Deck: {len(state.deck)}")
print(f"  Cards dealt: {state.cards_dealt}")
print(f"  Dealer ID: {state.dealer_id}, Dealer hand: {len(state.hands[state.dealer_id])}")
print(f"  TOTAL: {sum(len(h) for h in state.hands) + len(state.kitty) + len(state.deck)}")

# Check if kitty cards are in dealer hand
if state.phase == GamePhase.KITTY:
    dealer_hand = state.hands[state.dealer_id]
    kitty_in_hand = sum(1 for card in dealer_hand if card in state.kitty)
    print(f"  Kitty cards in dealer hand: {kitty_in_hand}/6")
