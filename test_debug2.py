"""Detailed debug test to trace the bidding issue."""

from shengji.game import Game
from shengji.types import GamePhase, ActionType

game = Game()
state = game.reset(dealer_id=0)

print(f"Starting state:")
print(f"  Phase: {state.phase}")
print(f"  Current player: {state.current_player}")
print(f"  Passed players: {state.passed_players}")
print(f"  Current trump bid: {state.current_trump_bid}")
print()

for step_num in range(1, 20):
    print(f"[Step {step_num}]")
    print(f"  Phase: {state.phase}")
    print(f"  Current player: {state.current_player}")
    print(f"  Passed players: {state.passed_players}")
    print(f"  Legal actions: {len(state.legal_actions)}")

    if not state.legal_actions:
        print(f"  ERROR: No legal actions!")
        # Try to debug why
        player_id = state.current_player
        print(f"  Player {player_id} in passed_players? {player_id in state.passed_players}")
        break

    action = state.legal_actions[0]
    action_type = action.action_type

    if action_type == ActionType.BID_TRUMP:
        bid = action.trump_bid
        print(f"  Action: BID {bid.count}x {bid.suit.value}")
    elif action_type == ActionType.PASS_TRUMP:
        print(f"  Action: PASS")

    state, info = game.step(state, action)

    if state.phase != GamePhase.DEALING:
        print(f"  Transitioned to: {state.phase}")
        break

    print()
