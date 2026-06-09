"""Test the new card-by-card dealing system."""

from shengji.game import Game
from shengji.types import GamePhase

game = Game()
state = game.reset(dealer_id=0)

print(f"After reset:")
print(f"  Cards dealt: {state.cards_dealt}")
print(f"  Hands sizes: {[len(h) for h in state.hands]}")
print(f"  Deck size: {len(state.deck)}")
print(f"  Kitty size: {len(state.kitty)}")
print(f"  Legal actions: {len(state.legal_actions)}")
print()

step = 0
while state.phase == GamePhase.DEALING and step < 100:
    print(f"[Step {step}] cards_dealt={state.cards_dealt}, hands={[len(h) for h in state.hands]}, deck={len(state.deck)}, actions={len(state.legal_actions)}")

    if not state.legal_actions:
        print("ERROR: No legal actions!")
        break

    action = state.legal_actions[0]
    state, info = game.step(state, action)
    step += 1

print(f"\nAfter DEALING phase:")
print(f"  Phase: {state.phase}")
print(f"  Cards dealt: {state.cards_dealt}")
print(f"  Hands sizes: {[len(h) for h in state.hands]}")
print(f"  Total cards in hands: {sum(len(h) for h in state.hands)}")
print(f"  Deck size: {len(state.deck)}")
print(f"  Kitty size: {len(state.kitty)}")
