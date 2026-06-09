"""Test the dealing system across multiple games."""

from shengji.game import Game
from shengji.types import GamePhase, ActionType

def play_game():
    """Play one game and return stats about dealing and bidding."""
    game = Game()
    state = game.reset(dealer_id=0)

    cards_when_first_bid = None
    max_cards_dealt = 0
    bid_count = 0
    pass_count = 0

    step = 0
    while state.phase == GamePhase.DEALING and step < 500:
        action = state.legal_actions[0]

        if action.action_type == ActionType.BID_TRUMP:
            bid_count += 1
            if cards_when_first_bid is None:
                cards_when_first_bid = len(state.hands[0])

        elif action.action_type == ActionType.PASS_TRUMP:
            pass_count += 1

        state, info = game.step(state, action)
        max_cards_dealt = len(state.hands[0])
        step += 1

    return {
        'cards_dealt': max_cards_dealt,
        'bids_made': bid_count,
        'passes_made': pass_count,
        'cards_when_first_bid': cards_when_first_bid or 0,
        'phase_reached': state.phase.name,
        'trump_locked': state.trump_locked,
    }


print("Testing dealing system across 10 games:")
print("=" * 70)

stats_list = []
for game_num in range(10):
    stats = play_game()
    stats_list.append(stats)
    print(f"Game {game_num + 1}:")
    print(f"  Cards dealt: {stats['cards_dealt']}/26")
    print(f"  Bids made: {stats['bids_made']}, Passes: {stats['passes_made']}")
    print(f"  First bid at: {stats['cards_when_first_bid']} cards/player")
    print(f"  Phase reached: {stats['phase_reached']}")
    print(f"  Trump locked: {stats['trump_locked']}")
    print()

print("Summary:")
print(f"  Average cards dealt: {sum(s['cards_dealt'] for s in stats_list) / len(stats_list):.1f}/26")
print(f"  Average bids: {sum(s['bids_made'] for s in stats_list) / len(stats_list):.1f}")
print(f"  Games with all 26 cards: {sum(1 for s in stats_list if s['cards_dealt'] == 26)}/10")
print(f"  Games with trump locked: {sum(1 for s in stats_list if s['trump_locked'])}/10")
