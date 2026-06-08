# CLAUDE.md — shengji-engine

## What You Are Building

A pure Python game engine for six-player 拖拉机 (Sheng Ji). No UI, no networking. This library is imported by `shengji-server` and `shengji-ai`. Think of it as the referee: it knows all the rules, tracks all state, and tells agents what moves are legal.

## Cardinal Rules

1. **No I/O anywhere in this library.** No `print()`, no file reads, no network calls.
2. **GameState must be fully serializable** to JSON at all times. No object references that can't be `json.dumps()`-ed.
3. **Never mutate state in place.** `game.step(action)` returns a new `GameState`. The old one is unchanged.
4. **Every public function must have a test.** Write tests alongside code, not after.
5. **Legal action generator is the most critical function.** It must be exhaustive (no legal move missing) and sound (no illegal move included). Test it obsessively.

## Architecture

```
game.py          ← entry point, orchestrates everything
state.py         ← GameState dataclass, all game data lives here
card.py          ← Card, Deck, CardCombination (pure data + comparison)
types.py         ← enums: Action, GamePhase, Suit, Rank, Role
rules.py         ← get_legal_actions(), determine_trick_winner()
scoring.py       ← compute_score(), compute_level_changes()
trump.py         ← trump card ordering, declaration resolution
level.py         ← LEVEL_SEQ, step_level(), key_index(), level_display()
```

**Dependency direction:** `game.py` imports everything. Nothing imports `game.py`. `rules.py` imports `card.py` and `trump.py`. `scoring.py` imports `level.py`. No circular imports.

## Key Data Types

### Card
```python
@dataclass(frozen=True)
class Card:
    suit: Suit          # HEARTS, DIAMONDS, CLUBS, SPADES, JOKER
    rank: Rank          # TWO, THREE, ..., ACE, SMALL_JOKER, LARGE_JOKER
    deck_id: int        # 0, 1, or 2 (three decks)
```

### GameState
```python
@dataclass(frozen=True)
class GameState:
    phase: GamePhase
    current_player: int             # 0–5, whose turn it is
    hands: tuple[tuple[Card]]       # hands[i] = player i's hand
    kitty: tuple[Card]              # 8-card kitty (before dealer takes)
    trump_suit: Suit | None
    trump_level: str                # "2","4","6","7","8","9","10","J","Q","K","A"
    dealer_id: int
    helper_card: Card | None        # the card dealer called to identify helpers
    revealed_helpers: tuple[int]    # player ids who have revealed themselves
    current_trick: tuple[tuple]     # [(player_id, cards_played), ...]
    tricks_won: tuple[tuple[Card]]  # scoring cards accumulated by farmer side
    player_levels: tuple[str]       # level key per player e.g. "R1:7"
    scores: tuple[int]              # current scoring card total
    legal_actions: tuple[Action]    # pre-computed for current_player
```

### Action
```python
@dataclass(frozen=True)
class Action:
    action_type: ActionType   # PLAY_CARDS, DECLARE_TRUMP, TAKE_KITTY, CALL_HELPER
    cards: tuple[Card]        # cards involved (empty for some action types)
    target: int | None        # target player id if relevant
```

### Level Key Format
String `"<round>:<level>"` e.g. `"R1:A"`, `"B2:2"`, `"R3:10"`.
Full sequence from lowest to highest:
`B10:2, B9:2, ..., B1:2, R1:2, R1:4, R1:6, R1:7, R1:8, R1:9, R1:10, R1:J, R1:Q, R1:K, R1:A, R2:2, ...`

## Game Phases

```
DEALING → TRUMP_DECLARATION → KITTY → CALL_HELPER → TRICK_PLAYING → SCORING
```

- **DEALING**: distribute cards to players and kitty
- **TRUMP_DECLARATION**: players may declare trump by showing Jokers or level cards; highest declaration wins
- **KITTY**: dealer sees kitty, swaps up to 8 cards, buries remainder
- **CALL_HELPER**: dealer names a card; whoever holds it becomes a helper (may be hidden)
- **TRICK_PLAYING**: 25 tricks of 6 cards each
- **SCORING**: compute farmer score, apply level changes, determine next dealer

## Legal Action Rules (implement in rules.py)

### Card Combinations

- **Single**: any one card
- **Pair**: two identical cards (same rank and suit, any deck_id)
- **Trio**: three identical cards (same rank and suit, any deck_id)
- **Tractor**: two or more consecutive pairs of the same suit
  - "Consecutive" means adjacent in the suit's rank ordering (skipping trump level cards)
  - Pairs that span trump/non-trump boundary are NOT tractors
  - Example: if 7 is trump level, ♦6-♦7 is not a tractor (spans boundary)
- **Limo**: two or more consecutive trios of the same suit
  - Same consecutiveness rules as tractors
- **Multi-card throws**: any combination in one suit when leading (e.g. pair + single, trio + two singles, tractor + single)

### During TRICK_PLAYING

**Leading a trick:**
- Any single card
- Any pair of identical cards
- Any trio of identical cards
- Any tractor (2+ consecutive pairs, same suit)
- Any limo (2+ consecutive trios, same suit)
- Any multi-component combination in one suit (e.g. pair + single, tractor + singles)

**Following a trick:**
Priority order:
1. **Suit is the first priority**: must follow the led suit if you have cards of that suit
2. **Combination matching is the second priority**: within the suit, match the combination structure if able

If you do not have the led suit:
- You may choose to **trump**, which is a higher play
- Or you may choose **not to trump**, which is a lower play
- Play any cards matching the trick size

**How to match the leader's combination (when you have the led suit):**
1. **If single is led**: play a single
2. **If pair is led**: 
   - Play a pair if you have one, else play singles
3. **If trio is led**: 
   - Play a trio if you have one, else
   - Play a pair plus a single, else
   - Play three singles
4. **If tractor is led**:
   - Play a tractor if you have one, else
   - Play two pairs, else
   - Play one pair plus two singles, else
   - Play four singles
5. **If limo is led**:
   - Play a limo, else
   - Play two trios, else
   - Play a trio plus a pair plus a single, else
   - Play a tractor plus two singles, else
   - Play two pairs plus two singles, else
   - Play a pair plus four singles, else
   - Play six singles

**Trick winner:**
- Highest card of led suit wins, UNLESS
- A trump card was played, in which case highest trump wins
- When comparing same-suit cards, use rank ordering for that suit under current trump

## Trump Ordering (implement in trump.py)

Within the trump suit (highest to lowest):
```
Large Joker > Small Joker > [trump level card of trump suit] > [trump level card of other suits] > A > K > Q > J > 10 > 9 > 8 > 7 > 6 > 5 > 4 > 3 > 2
```
(of trump suit, skipping the level card rank which moved to the top)

Level cards of non-trump suits also count as trump but rank below the trump-suit level card.

## Scoring (implement in scoring.py)

```python
SCORING_VALUES = {Rank.FIVE: 5, Rank.TEN: 10, Rank.KING: 10}

def compute_farmer_score(tricks_won: list[Card]) -> int:
    # Sum of scoring card values in farmer-captured tricks

def compute_level_changes(
    farmer_score: int,
    heart_fives_captured: int,
    diamond_fives_captured: int,
    dealer_side: list[int],
    farmer_side: list[int],
) -> dict[int, int]:
    # Returns {player_id: level_delta} for all players
    # Score-based change + red five penalties
```

## Testing Strategy

### Unit Tests (fast, no game needed)
```python
# test_level.py
def test_step_level_up(): assert step_level("R1:2", 1) == "R1:4"
def test_step_level_across_round(): assert step_level("R1:A", 1) == "R2:2"
def test_step_level_into_basement(): assert step_level("R1:2", -1) == "B1:2"
def test_step_level_basement_up(): assert step_level("B2:2", 1) == "B1:2"
def test_step_level_basement_skip(): assert step_level("B2:2", 3) == "R1:4"
def test_step_level_clamped(): assert step_level("B10:2", -5) == "B10:2"

# test_trump.py
def test_joker_beats_trump(): ...
def test_level_card_beats_ace(): ...
def test_tractor_detection(): ...
```

### Integration Tests (full game loop)
```python
# test_game.py
def test_full_game_completes():
    game = Game(num_players=6)
    state = game.reset()
    while not done:
        action = random.choice(state.legal_actions)
        state, reward, done, info = game.step(action)
    assert state.phase == GamePhase.SCORING

def test_legal_actions_never_empty_mid_game():
    # During TRICK_PLAYING, legal_actions must never be empty
```

## Common Mistakes to Avoid

- **Joker pairs are tractors** — Large+Small Joker is the highest tractor of length 2
- **Level cards across suits** — a pair of ♥7 and ♦7 (when 7 is trump level) ARE a pair because both are trump
- **Kitty scoring** — if dealer side loses, the last trick's scoring cards are multiplied by 2x, and kitty cards count double; implement this carefully
- **Helper reveal timing** — a player is only a helper once they play the called card; before that, they appear to be a farmer
- **Three decks** — there are 3 copies of every card; pairs require same rank+suit but can be from different decks; tractors can use cards from different decks

## Build Order

1. `types.py` + `level.py` + tests — no card logic needed
2. `card.py` + `trump.py` + tests — card comparison
3. `rules.py` (legal actions for a single trick) + tests — most complex
4. `state.py` + `scoring.py` + tests
5. `game.py` (full state machine) + integration tests

Do not proceed to step N+1 until tests for step N all pass.
