"""Show several representative bidding examples."""

from shengji.game import Game
from shengji.types import GamePhase, ActionType

def show_game_bidding(game_num):
    """Play one game and show bidding sequence."""
    game = Game()
    state = game.reset(dealer_id=0)
    
    bids = []
    step = 0
    
    while state.phase == GamePhase.DEALING and step < 50:
        cards_dealt = state.cards_dealt
        
        if state.legal_actions:
            action = state.legal_actions[0]
            if action.action_type == ActionType.BID_TRUMP:
                bid = action.trump_bid
                bids.append((cards_dealt, bid.bidder_id, bid.count, bid.suit.value))
            state, _ = game.step(state, action)
        else:
            state, _ = game.step(state, None)
        step += 1
    
    return bids, state.trump_suit

print("="*75)
print("REPRESENTATIVE SHENG JI BIDDING LOGS - PARALLEL DEALING")
print("="*75)
print()
print("Format: 'Cards/player' = number of cards dealt to each player when bid occurs")
print()

# Generate until we find interesting patterns
found_patterns = {'no_bids': 0, 'single_bid': 0, 'multiple_bids': 0, 'trump_locked': 0}
game_count = 1

while game_count <= 20:
    bids, final_trump = show_game_bidding(game_count)
    
    # Skip if already have examples of this pattern
    if len(bids) == 0:
        if found_patterns['no_bids'] < 1:
            found_patterns['no_bids'] += 1
            print(f"GAME {game_count}: All players passed (no bids)")
            print(f"  Result: Trump determined from kitty")
            print()
    elif len(bids) == 1:
        if found_patterns['single_bid'] < 2:
            found_patterns['single_bid'] += 1
            cards, player, count, suit = bids[0]
            print(f"GAME {game_count}: Single bid")
            print(f"  Step 1: After {cards} cards dealt → Player {player} bids {count}x {suit}")
            print(f"  Then: All other players passed")
            print(f"  Result: Trump determined from kitty (count < 3)")
            print()
    elif len(bids) >= 2:
        if found_patterns['multiple_bids'] < 2:
            found_patterns['multiple_bids'] += 1
            print(f"GAME {game_count}: Multiple bids (counter-bidding)")
            for idx, (cards, player, count, suit) in enumerate(bids, 1):
                print(f"  Step {idx}: After {cards:2d} cards dealt → Player {player} bids {count}x {suit}")
            if bids[-1][2] == 3:
                print(f"  Result: Trump LOCKED at {bids[-1][3]} (count == 3)")
                found_patterns['trump_locked'] += 1
            else:
                print(f"  Result: Trump determined from kitty")
            print()
    
    game_count += 1
    if sum(found_patterns.values()) >= 5:
        break

print("="*75)
print("KEY OBSERVATIONS:")
print("="*75)
print()
print("1. Cards are dealt progressively (1 per player per round)")
print("2. Bidding happens when players have level cards (first 1-7 cards typical)")
print("3. Bidding ends when all 6 players have passed")
print("4. After bidding ends, remaining cards continue to be dealt automatically")
print("5. All players receive exactly 26 cards before KITTY phase")
print()
print("Pattern frequencies in this sample:")
for pattern, count in found_patterns.items():
    if count > 0:
        print(f"  {pattern}: {count} game(s)")
