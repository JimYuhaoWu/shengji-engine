"""Debug test to understand game flow issues."""

from shengji.game import Game
from shengji.types import GamePhase, ActionType

game = Game()
state = game.reset(dealer_id=0)

print(f"Initial phase: {state.phase}")
print(f"Current player: {state.current_player}")
print(f"Dealer: {state.dealer_id}")
print(f"Trump level: {state.trump_level}")
print(f"Number of legal actions: {len(state.legal_actions)}")

# Show first few actions
for i, action in enumerate(state.legal_actions[:5]):
    print(f"  Action {i}: {action.action_type}")

# Try to take one step
if state.legal_actions:
    action = state.legal_actions[0]
    print(f"\nTaking action: {action.action_type}")
    state, info = game.step(state, action)
    print(f"New phase: {state.phase}")
    print(f"New current player: {state.current_player}")
    print(f"Number of legal actions: {len(state.legal_actions)}")

# Try several more steps
for step_num in range(2, 20):
    if not state.legal_actions:
        print(f"\n[Step {step_num}] No legal actions! Game stuck in {state.phase}")
        break

    action = state.legal_actions[0]
    state, info = game.step(state, action)
    print(f"[Step {step_num}] Phase: {state.phase}, Actions available: {len(state.legal_actions)}")

    if state.phase != GamePhase.DEALING:
        print(f"[Step {step_num}] Successfully transitioned to {state.phase}")
        break
