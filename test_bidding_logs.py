"""Generate detailed bidding logs for multiple games."""

from shengji.game import Game
from shengji.types import GamePhase, ActionType

def generate_bidding_log(game_num):
    """Play one game and return detailed bidding log."""
    game = Game()
    state = game.reset(dealer_id=0)

    log = {
        'game_num': game_num,
        'bids': [],
        'bidding_ended_at_cards': None,
        'final_trump': None,
        'total_steps': 0,
    }

    step = 0
    while state.phase == GamePhase.DEALING:
        cards_per_player = state.cards_dealt

        # Track when bidding ends
        if state.bidding_ended and log['bidding_ended_at_cards'] is None:
            log['bidding_ended_at_cards'] = cards_per_player

        if state.legal_actions:
            action = state.legal_actions[0]

            if action.action_type == ActionType.BID_TRUMP:
                bid = action.trump_bid
                log['bids'].append({
                    'step': step,
                    'cards_dealt': cards_per_player,
                    'player': bid.bidder_id,
                    'bid_count': bid.count,
                    'suit': bid.suit.value,
                })

            state, _ = game.step(state, action)
        else:
            # No legal actions (bidding ended), auto-deal
            if log['bidding_ended_at_cards'] is None:
                log['bidding_ended_at_cards'] = cards_per_player
            state, _ = game.step(state, None)

        step += 1

    log['final_trump'] = state.trump_suit.value if state.trump_suit else "From kitty"
    log['total_steps'] = step

    return log


def print_bid_log(log):
    """Pretty print a bid log."""
    print(f"\n{'='*70}")
    print(f"GAME {log['game_num']}")
    print(f"{'='*70}")

    if not log['bids']:
        print("No bids made - all players passed")
    else:
        print("\nBidding sequence:")
        for bid in log['bids']:
            print(f"  Step {bid['step']:2d} | After {bid['cards_dealt']:2d} cards dealt | "
                  f"Player {bid['player']} bids {bid['bid_count']}x {bid['suit']}")

    print(f"\nBidding ended: After {log['bidding_ended_at_cards']} cards dealt per player")
    print(f"Final trump: {log['final_trump']}")
    print(f"Total steps to DEALING->KITTY transition: {log['total_steps']}")


# Generate 10 games
print("BIDDING LOGS - PARALLEL DEALING SYSTEM")
print("=" * 70)
print("\nThis shows how cards are dealt progressively and bidding happens")
print("during the dealing process, with cards continuing to be dealt after")
print("bidding ends (all pass or count==3).\n")

logs = []
for i in range(1, 11):
    log = generate_bidding_log(i)
    logs.append(log)
    print_bid_log(log)

# Summary statistics
print(f"\n{'='*70}")
print("SUMMARY STATISTICS")
print(f"{'='*70}")

total_bids = sum(len(log['bids']) for log in logs)
games_with_bids = sum(1 for log in logs if log['bids'])
avg_cards_when_first_bid = sum(log['bids'][0]['cards_dealt'] if log['bids'] else 0 for log in logs) / games_with_bids if games_with_bids > 0 else 0

bidding_ended_values = [log['bidding_ended_at_cards'] for log in logs if log['bidding_ended_at_cards'] is not None]
avg_cards_when_bidding_ended = sum(bidding_ended_values) / len(bidding_ended_values) if bidding_ended_values else 0

print(f"\nTotal games: {len(logs)}")
print(f"Games with bids: {games_with_bids}/10")
print(f"Games with no bids (all pass): {10 - games_with_bids}/10")
print(f"Average cards dealt when first bid made: {avg_cards_when_first_bid:.1f}")
print(f"Average cards dealt when bidding ended: {avg_cards_when_bidding_ended:.1f}")
print(f"Total bids across all games: {total_bids}")

# Show some patterns
max_bids = max(len(log['bids']) for log in logs)
games_with_max = [log['game_num'] for log in logs if len(log['bids']) == max_bids]
print(f"\nGames with most bids ({max_bids}): Game(s) {', '.join(map(str, games_with_max))}")

# Show trump locked games
locked_games = [log for log in logs if log['bids'] and log['bids'][-1]['bid_count'] == 3]
print(f"Games with trump locked (count==3): {len(locked_games)}/10")
if locked_games:
    for log in locked_games:
        last_bid = log['bids'][-1]
        print(f"  Game {log['game_num']}: Player {last_bid['player']} bid 3x {last_bid['suit']} "
              f"after {last_bid['cards_dealt']} cards dealt")
