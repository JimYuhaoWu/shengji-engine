"""Generate detailed bidding logs showing the exact state transitions."""

import sys
import pathlib

# Allow running directly (`python examples/bidding_demo.py`) without installing.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from shengji.game import Game
from shengji.types import GamePhase, ActionType

def generate_detailed_bidding_log(game_num, max_cards_to_show=15):
    """Play one game and return detailed bidding log with state at each step."""
    game = Game()
    state = game.reset(dealer_id=0)

    log = []
    step = 0

    print(f"\n{'='*80}")
    print(f"GAME {game_num}")
    print(f"{'='*80}")
    print(f"{'Step':>4} | {'Cards':>5} | {'Bidding':>8} | {'Trump':>6} | {'Legal':>6} | Action")
    print(f"{'-'*80}")

    while state.phase == GamePhase.DEALING and step <= max_cards_to_show:
        cards_dealt = state.cards_dealt
        formal_bidding = state.formal_bidding_started
        trump_locked = state.trump_locked
        num_legal = len(state.legal_actions)
        phase = state.phase.name[:5]  # Show first 5 chars of phase

        # Print current state
        action_str = ""
        if state.legal_actions:
            action = state.legal_actions[0]
            if action.action_type == ActionType.BID_TRUMP:
                bid = action.trump_bid
                action_str = f"BID {bid.count}x {bid.suit.value}"
            elif action.action_type == ActionType.PASS_TRUMP:
                action_str = "PASS"
        else:
            action_str = "AUTO-DEAL"

        print(f"{step:4d} | {cards_dealt:5d} | {phase:>5} | {str(formal_bidding):>8} | {num_legal:6d} | {action_str}")

        if state.legal_actions:
            action = state.legal_actions[0]
            if action.action_type == ActionType.BID_TRUMP:
                bid = action.trump_bid
                log.append({
                    'cards_dealt': cards_dealt,
                    'player': bid.bidder_id,
                    'bid_count': bid.count,
                    'suit': bid.suit.value,
                })
            state, _ = game.step(state, action)
        else:
            # Auto-deal
            state, _ = game.step(state, None)

        step += 1

    print(f"{'-'*80}")
    print(f"Final: Phase={state.phase.name}, Cards dealt={state.cards_dealt}, Trump={state.trump_suit}, Formal bidding={state.formal_bidding_started}")

    return log


# Generate 5 detailed games
print("DETAILED BIDDING LOGS - PARALLEL DEALING SYSTEM")
print("="*80)
print("\nShowing card dealing progress and when bidding ends relative to card distribution.\n")

for i in range(1, 6):
    log = generate_detailed_bidding_log(i)

    if log:
        print(f"\nBids in Game {i}:")
        for entry in log:
            print(f"  Cards dealt: {entry['cards_dealt']:2d} | Player {entry['player']} bids {entry['bid_count']}x {entry['suit']}")
    else:
        print(f"\nGame {i}: No bids (all passed)")
