"""Debug test to track card count during game."""

from shengji.game import Game
from shengji.types import GamePhase

game = Game()
state = game.reset(dealer_id=0)

print("Checking card count at each phase:")
print(f"After reset: Total cards = {sum(len(h) for h in state.hands) + len(state.kitty) + len(state.deck)}")

# Fast-forward to TRICK_PLAYING
step = 0
while state.phase != GamePhase.TRICK_PLAYING and step < 100:
    if not state.legal_actions:
        break

    before = sum(len(h) for h in state.hands) + len(state.kitty) + len(state.deck)
    state, _ = game.step(state, state.legal_actions[0])
    after = sum(len(h) for h in state.hands) + len(state.kitty) + len(state.deck)

    if before != after:
        print(f"[Step {step}] Card count changed! Before: {before}, After: {after}")

    if state.phase != GamePhase.DEALING:
        print(f"Phase: {state.phase}")
        print(f"  Cards in hands: {sum(len(h) for h in state.hands)}")
        print(f"  Cards in kitty: {len(state.kitty)}")
        print(f"  Cards in deck: {len(state.deck)}")
        print(f"  Total: {before}")
        break

    step += 1

print(f"\nInitial deck had: 162 cards")
print(f"Final count: {sum(len(h) for h in state.hands) + len(state.kitty) + len(state.deck)}")
