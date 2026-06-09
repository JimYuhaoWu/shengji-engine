"""Test a complete game with detailed progress tracking."""

import sys
import pathlib

# Allow running directly (`python examples/full_game.py`) without installing.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from shengji.game import Game
from shengji.types import GamePhase

game = Game()
state = game.reset(dealer_id=0)

print(f"Starting game with dealer {state.dealer_id}")
print(f"Initial phase: {state.phase}\n")

step_count = 0
max_steps = 2000

while state.phase != GamePhase.SCORING and step_count < max_steps:
    if not state.legal_actions:
        print(f"\nERROR: No legal actions at step {step_count}, phase {state.phase}")
        break

    action = state.legal_actions[0]
    state, info = game.step(state, action)
    step_count += 1

    # Print phase transitions
    if step_count <= 5 or state.phase != GamePhase.TRICK_PLAYING or step_count % 50 == 0:
        print(f"Step {step_count:4d}: {state.phase.name:18s} | Current player: {state.current_player} | Tricks won: {len(state.tricks_won)}")

print(f"\nFinal state after {step_count} steps:")
print(f"  Phase: {state.phase}")
print(f"  Tricks won: {len(state.tricks_won)}")
print(f"  Current player: {state.current_player}")
print(f"  Remaining cards in hands: {sum(len(h) for h in state.hands)}")

if state.phase == GamePhase.SCORING:
    print("\n[SUCCESS] Game reached SCORING phase!")
    farmer_score = game._calculate_farmer_score(state)
    print(f"  Farmer score: {farmer_score}")
    next_dealer = game._determine_next_dealer(state)
    print(f"  Next dealer: {next_dealer}")
else:
    print(f"\n[INCOMPLETE] Game stuck in {state.phase.name} after {step_count} steps")
