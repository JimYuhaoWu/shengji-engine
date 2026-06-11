# CLAUDE.md — shengji-engine

## What You Are Building

A pure Python game engine for six-player 拖拉机 (Sheng Ji). No UI, no networking. This library is imported by `shengji-server` and `shengji-ai`. Think of it as the referee: it knows all the rules, tracks all state, and tells agents what moves are legal.

## Cardinal Rules

1. **No I/O anywhere in this library.** No `print()`, no file reads, no network calls.
2. **GameState must be fully serializable** to JSON at all times. No object references that can't be `json.dumps()`-ed.
3. **Never mutate state in place.** `game.step(state, action)` returns a new `(GameState, info)`; the input state is unchanged.
4. **Every public function must have a test.** Write tests alongside code, not after.
5. **Legal action generator is the most critical function.** It must be exhaustive (no legal move missing) and sound (no illegal move included). Test it obsessively.

## Coding Standards

### 1. Simplicity First
- **Minimum code that solves the problem.** No speculative abstractions or features beyond what's asked.
- **No error handling for impossible scenarios.** Trust internal code; validate only at system boundaries (user input, external APIs).
- **Three similar lines = time to extract.** One-off code stays inline.
- **Ask: "Is this overcomplicated?"** If yes, rewrite it.

### 2. Surgical Changes
- **Touch only what you must.** Don't improve adjacent code unless requested.
- **Match existing style.** Even if you'd do it differently.
- **Remove only YOUR orphans.** If your changes make an import/variable/function unused, delete it. Don't clean up pre-existing dead code.
- **Every changed line traces to the user's request.** No drive-by refactoring.

### 3. Think Before Coding
- **State assumptions explicitly.** Uncertain about interpretation? Ask before implementing.
- **Surface tradeoffs.** Don't pick silently between equally valid approaches.
- **Don't hide confusion.** If something is unclear, stop and name what's confusing.
- **Simplify when possible.** If 50 lines can do what 200 does, rewrite it.

### 4. Goal-Driven Execution
- **Define success criteria first.** Transform tasks into verifiable checks:
  - "Add validation" → Write tests for invalid inputs, make them pass
  - "Fix bug X" → Write test reproducing it, make it pass
  - "Implement phase Y" → Write tests for all legal actions, pass them
- **State brief plans for multi-step work.** Format: `1. [Step] → verify: [check]`
- **Loop until verified.** Success = tests pass + behavior matches spec.

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
env.py           ← ShengJiEnv: optional stateful Gym-style wrapper over Game
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
    kitty: tuple[Card]              # 6-card kitty (底牌, before dealer takes)
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

- **DEALING**: distribute 26 cards to each player, 6 cards to kitty (dealt one card at a time)
- **TRUMP_DECLARATION**: overlaps with DEALING; players bid with level cards (higher count or level beats previous); ends when all pass or 10-second grace period expires after dealing ends
- **KITTY**: dealer sees kitty, swaps up to 6 cards, buries remainder (底牌); scores in kitty count toward last trick winner (2x multiplier based on winning combo card count)
- **CALL_HELPER**: dealer calls a non-trump card; first two players to play it become helpers (or one player if they play 2+ copies first)
- **TRICK_PLAYING**: variable tricks of 6 cards each (max 26 if all singles, fewer with combos); scores tracked per-player until all helpers revealed
- **SCORING**: compute farmer side score, apply level changes, determine next dealer

## Legal Action Rules (implement in rules.py)

### Card Combinations

- **Single**: any one card
- **Pair**: two identical cards (same rank and suit, any deck_id)
- **Trio**: three identical cards (same rank and suit, any deck_id)
- **Tractor**: two or more consecutive pairs of the same suit
  - "Consecutive" means adjacent in the suit's rank ordering (skipping trump level cards)
  - Pairs that span trump/non-trump boundary are NOT tractors
  - Example: if 7 is trump level, ♦6-♦7 is not a tractor (spans boundary)
- **Limo (钢板/豪车)**: two or more consecutive trios of the same suit
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
1. **Suit is the first priority**: must follow the led suit if you have ANY cards of that suit
2. **Combination matching is the second priority**: within the suit, match the combination structure if able

**If you have the led suit (critical rule):**
- You MUST play cards of the led suit first
- If you have INSUFFICIENT cards of the led suit to match the combination:
  - Play ALL cards of the led suit you have
  - Fill remaining slots with non-trump cards from other suits
  - You can NEVER trump in this case, therefore can NEVER win the trick

**If you do not have the led suit:**
- You may **trump** with trump cards that EXACTLY match the led combination type
- Or you may **not trump** and play other cards
- Play cards totaling the trick size

**Trump exact match rule:** Trump must match led combination EXACTLY:
- Two non-sequential pairs do NOT match tractor (different structures)
- Pair + 2 singles matches pair + 2 singles (same structure, different cards)
- Tractor matches tractor (same type)
- Limo does NOT match tractor (different types, even with same 6-card count)

**How to match the leader's combination (when you have sufficient led suit cards):**
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
1. If no valid trump was played: highest card of led suit wins
2. If valid trump was played: compare trump plays as follows:
   - **For single trump cards:** highest trump rank wins
   - **For multi-card trump throws:** ONLY the **deciding component** is compared. The
     deciding component is the one with the largest *group size* — **trio > pair > single** —
     and, among equal group sizes, the longer/higher consecutive run. For plain combos this
     is just "the component with the most cards"; the group-size priority only matters in the
     mixed case below.
     - Example 1: Pair+2singles thrown. Both players trump with exact match (pair+2singles)
       - (Pair of Large Joker + Small Joker + Captain) vs (Pair of Small Joker + Large Joker + 5♥)
       - Only compare the PAIR: Large Joker pair > Small Joker pair
       - Small Joker, Captain, 5♥ are completely ignored
     - Example 2: Two pairs thrown. Both trump with exact match (two pairs)
       - (Pair of 5♥ + Pair of Lieutenant) vs (Pair of Large Joker + Pair of Small Joker)
       - Only compare highest PAIR: 5♥ > Large Joker
       - Second pair and whether it's part of a tractor doesn't matter
     - Example 3 (mixed): a throw containing both a **tractor-of-3** (3 consecutive pairs, 6
       cards) and a **limo-of-2** (2 consecutive trios, 6 cards) is decided by the **limo**,
       because a trio outranks a pair. The tractor portion is ignored.
   - **Type must match to compare/win:** a play only contends if it is the *same combination
     type* as the lead. In particular a **limo-of-2 matches only a limo-of-2**, never a
     **tractor-of-3**, even though both are 6 cards.
   - **Invalid trump** (not exact match): treated as lower play, cannot win

`_determine_trick_winner` implements this with a `(group_size, run_length)` signature for the
deciding component (single=(1,1), pair=(2,1), trio=(3,1), tractor-k=(2,k), limo-k=(3,k)).
Group size has priority (trio > pair > single); among equal group sizes the longer run wins.
A contender must hold a component of the **same** signature to win, so a limo-of-2 `(3,2)`
never matches a tractor-of-3 `(2,3)`, and two loose pairs `(2,1)` cannot beat a tractor
`(2,2)`. (Consecutive runs are detected per suit, matching the rest of the engine.)

## Trump Declaration (implement in trump.py)

**Two-Phase System:**

**Phase 1: DEALING & TRUMP_DECLARATION (Overlapping)**
- Trump declaration starts as soon as the first card is dealt
- Cards are dealt progressively (1-26 per player, one round at a time)
- Players MAY bid at any time during dealing if they have level cards (optional)
- Players do NOT formally pass during this phase — a player who doesn't bid simply means they haven't bid yet
- All 26 cards are dealt regardless of bidding status

**Phase 2: TRUMP_DECLARATION (After All 26 Cards Dealt)**
- After all 26 cards distributed to players, formal TRUMP_DECLARATION phase begins
- NOW players must formally bid or pass
- Formal passes are tracked; bidding continues until:
  - Some player bids count==3 (trump locked), OR
  - All 6 players formally pass (triggers fallback rule)

**Valid Bids:**
Bids involve only level cards (ranks: 2, 4, 6, 7, 8, 9, 10, J, Q, K, A).
- A bid consists of: count + level (e.g., "1×7", "2×7", "3×7")
- A valid bid must beat the previous highest bid by:
  - **Higher count of the same level**, OR
  - **Any count of a higher level**
- **Suit doesn't matter for bid validity** — a bid of 2×7s can mix suits (e.g., 7♥ + 7♦)

Examples (in order of strength):
1. 1×7 (one seven, any suit)
2. 2×7 (two sevens, any suits including mixed)
3. 3×7 (three sevens, any suits including mixed) ← locks level 7 as trump
4. 1×J (one jack, any suit)
5. 2×J (two jacks, any suits)
6. 3×J (three jacks, any suits) ← locks level J as trump

**Trump Determination:**
- If ANY bids are made (during Phase 1 or Phase 2): Highest bidder's level determines trump suit
- If NO bids are made at all: Randomly draw a card from the kitty (fallback rule)
  - If Joker: discard and redraw
  - Non-Joker card's suit becomes trump

## Call Helper (implement in state.py)

**When:** After TRUMP_DECLARATION and KITTY phases, before TRICK_PLAYING

**Dealer's Call:**
- Dealer calls a non-trump card (any card that is not a trump card based on the declared trump suit and level)
- Since three decks exist, there are exactly three identical copies of the called card

**Helper Determination (during TRICK_PLAYING):**
0. **The dealer can NEVER be a helper.** Helpers are the dealer's partners, so the
   dealer playing the called card (e.g. from a copy they were dealt) does not make
   them a helper — those plays are ignored for helper assignment.
1. The first *non-dealer* player to play the called card becomes helper #1
2. The second *non-dealer* player to play the called card becomes helper #2
3. **Special rule:** If a (non-dealer) player plays 2+ copies of the called card (as a pair or part of a larger combination) BEFORE any other player has played the called card, that player becomes the ONLY helper (no second helper)
4. **Edge case:** If all three copies are buried in the kitty (dealer swapped them out), there are no helpers for that round

**Helper Reveal:**
- Helpers do not reveal themselves until they play the called card
- Before then, they appear to be farmers to other players

## Trump Ordering (implement in trump.py)

Trump card ranking (highest to lowest):
```
5♥ > 5♦ > Large Joker > Small Joker > Captain > Lieutenant > Trump Level Card > Non-Trump Level Cards > A > K > Q > J > 10 > 9 > 8 > 7 > 6 > 4 > 2
```

Where:
- **Captain**: 3 of trump suit's color (e.g., 3♥ if hearts are trump)
- **Lieutenant**: 3 of the other color in same pair (e.g., 3♦ if hearts are trump)
- **Trump Level Card**: the level being played, in trump suit
- **Non-Trump Level Cards**: the level being played, in non-trump suits
- **Rest**: A through 2 (of trump suit), skipping level card rank

Non-trump suits rank: A > K > Q > J > 10 > 9 > 8 > 7 > 6 > 5 > 4 > 3 > 2

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
# test_game.py — functional core: step(state, action) -> (state, info)
def test_full_game_completes():
    game = Game(num_players=6)
    state = game.reset(dealer_id=0)
    while state.phase != GamePhase.SCORING:
        action = random.choice(state.legal_actions) if state.legal_actions else None
        state, info = game.step(state, action)
    assert state.phase == GamePhase.SCORING

# test_env.py — optional Gym wrapper: step(action) -> (obs, reward, done, info)
def test_env_full_game():
    env = ShengJiEnv()
    env.reset(dealer_id=0)
    done = False
    while not done:
        action = random.choice(env.legal_actions) if env.legal_actions else None
        obs, reward, done, info = env.step(action)
    assert obs.phase == GamePhase.SCORING

def test_legal_actions_never_empty_mid_game():
    # During TRICK_PLAYING, legal_actions must never be empty
```

## Important Rules (Not Mistakes, But Easy to Confuse)

- **5♥ + 5♦ tractor** — These form the highest tractor of length 2 (not Jokers)
- **Level cards and pairing** — When 7 is trump level, hearts is trump suit:
  - ♥7 + ♦7 = NOT a pair (two singles, both non-trump level cards)
  - ♣7 + ♣7 = a pair (identical rank and suit)
  - ♥7 + ♥7 + ♣7 + ♣7 = a tractor (two consecutive pairs)
  - ♥7 + ♥7 + ♣7 + ♣7 + ♦7 + ♦7 = multi-throw (tractor + pair of non-trumps)
- **Kitty scoring multiplier** — Scores in kitty belong to the winner of the last trick:
  - Multiplied by 2x the number of cards in the winning combination
  - For multi-card throws, use the combination with maximum cards (e.g., tractor=4, pair=2, single=1; tractor has 4 so multiply by 8)
- **Score tracking phases** — Before all helpers reveal, each player tracks their own scores individually. After all roles known, sum up Farmer side scores together.
- **Helper reveal timing** — A player is only a helper once they play the called card; before that, they are potential Farmers
- **Three decks** — 3 copies of every card exist; pairs require same rank+suit but can be from different deck_ids; tractors can use cards from different decks

## Build Order

1. `types.py` + `level.py` + tests — no card logic needed
2. `card.py` + `trump.py` + tests — card comparison
3. `rules.py` (legal actions for a single trick) + tests — most complex
4. `state.py` + `scoring.py` + tests
5. `game.py` (full state machine) + integration tests

Do not proceed to step N+1 until tests for step N all pass.

## Session Log — 2026-06-11 (live-playtest bug fixes)

A human-vs-5-AI playtest surfaced several engine bugs. All fixed in `game.py`
with regression tests in `tests/test_game.py` (suite now 189 passing). If you
are catching up, these are the behaviors to keep in mind:

1. **Follow-suit treats trump as ONE logical suit.** `_get_legal_following_plays`
   now takes a `led_is_trump` flag. When the lead is trump (a Joker, any level
   card, 5♥/5♦, Captain/Lieutenant, or a trump-suit card), *every* trump in hand
   "follows suit"; when a plain suit is led, only the non-trump cards of that
   physical suit follow. Previously it compared the led card's literal `.suit`,
   so a Joker lead only let you follow with Jokers, and an off-suit level card
   (e.g. 2♠ when ♥2 is trump) was mis-read as a spades lead.

2. **New trick leader gets LEADING actions, not stale follow-plays.** When a
   trick completes, the next leader's `legal_actions` are now computed with
   `current_trick=()`. Before, the just-finished trick leaked in, so the leader
   was restricted to the previous trick's led suit (often "trump only").

3. **A standing trump bid wins when everyone passes.** `_handle_pass_trump`: if
   `current_trump_bid` exists when all 6 pass, that bid's suit becomes trump and
   trump locks. The random-kitty fallback (`_resolve_trump_from_kitty`) now fires
   only when *no* bid was ever made. Before, a 2♥ bid that nobody beat was thrown
   away and a random kitty suit was chosen.

4. **The dealer can never be a helper.** `_update_helpers` ignores plays by
   `dealer_id` (helpers are the dealer's partners). See the Call Helper section.

5. **`next_game` reuses the real dealing flow.** It now calls
   `reset(dealer_id=next_dealer, player_levels=...)` instead of pre-dealing all
   156 cards into a half-initialized state. `reset` gained an optional
   `player_levels` arg and now derives `trump_level` from the **dealer's** level
   (not player 0's). This fixes the next hand not starting like the first and the
   corrupted/unequal hand sizes that followed.

### Known issues / planned work (NOT yet done)

- **KITTY still enumerates C(32,6) ≈ 906k legal actions** even though every
  6-card bury is valid. This is wasted work the serializer just discards. Plan:
  skip legal-action generation for KITTY and validate a submitted bury directly
  as a **sub-multiset** of the dealer's hand (6 cards; duplicates allowed up to
  the count actually held). See shengji-server `_bury_is_valid`.
- **Multi-card throws (甩牌) on the lead are not supported.** `get_card_combinations`
  only emits clean single/pair/trio/tractor/limo. Planned: a staged *validator*
  (validate the submitted play instead of enumerating) — Stage 1 logical-suit
  check, Stage 2 type detection, Stage 3 multi-throw with a throw-success/penalty
  rule resolved at play time using other players' hands. Lead and follow need
  separate branches. Keep a bounded candidate generator for AI move selection.
