# shengji-engine

Pure Python game engine for six-player 拖拉机 (Sheng Ji / Upgrade / Tractor). No UI, no networking — just the rules, state machine, and legal action generator. This is the foundation that the server, UI, and AI agents all depend on.

## What This Is

A Python library implementing the complete game logic for 拖拉机 as played by a fixed six-player group. The core is a pure, immutable `Game` (state in → new state out); an optional `ShengJiEnv` wrapper adapts it to the OpenAI-Gym `(observation, reward, done, info)` convention so AI agents can plug in without knowing anything about the internals.

## What This Is Not

- Not a server (see `shengji-server`)
- Not a UI (see `shengji-app`)
- Not an AI agent (see `shengji-ai`)

## Project Status

**Playable end-to-end** — 175 passing tests; random full games complete from deal to scoring.

- ✅ Card system (deck handling, card equality)
- ✅ Level progression (R1:2 → R5:A, basement B1-B10)
- ✅ Trump ranking (5♥ > 5♦ > Jokers > Captain > Lieutenant > Level > A-2)
- ✅ Card combinations (single, pair, trio, tractor, **limo/钢板/豪车**)
- ✅ Game state (immutable GameState, 26 cards/player + 6-card kitty)
- ✅ Card dealing (card-by-card with two-phase trump declaration)
- ✅ Game loop (trump declaration → kitty → call helper → trick playing → scoring → next game)
- ✅ Trick winner with combination-type matching (limo-2 ≠ tractor-3); scoring with asymmetric level changes, red-five penalties, and the kitty multiplier
- ✅ Optional `ShengJiEnv` Gym-style wrapper

### Known gaps / approximations

- **Solo-helper rule not sealed.** A player who plays 2+ copies of the called card before anyone else should be the *only* helper, but the engine can still add a second helper later.
- **Trump-hierarchy tractors only half-wired.** Cross-suit hierarchy tractors (e.g. `7♥7♥ + 3♦3♦` when 7 is the level) are recognized when *leading* a trick, but the follow-play generator and trick-winner logic detect tractors per physical suit, so such combos aren't matched/won correctly.
- **"No helpers when all three called copies are buried"** is not enforced (the dealer isn't prevented from calling a card it holds/buried all copies of). The natural outcome is still "no helpers", so impact is low.
- **Kitty burial** enumerates all C(32,6) ≈ 906k legal burials — correct but heavy for a UI/agent; could be sampled or pruned.

## Game Rules Implemented

### Players and Roles
- 6 players, fixed seats 0–5 in clockwise order
- Each round: one Dealer, one or two Helpers (called by Dealer), remaining players are Farmers
- Helpers are not publicly known until they reveal themselves by playing the called card

### Decks
- **Three decks total**: 162 cards (3 × 54 cards: 52 standard + 2 Jokers per deck)
- Each player is dealt 26 cards
- Remaining 6 cards form the kitty (底牌)
- Each card has a deck_id (0, 1, or 2) to distinguish duplicates

### Level System
- 11 levels per round: `2, 4, 6, 7, 8, 9, 10, J, Q, K, A` (3 and 5 excluded from levels)
- Rounds: R1 → R2 → R3 → R4 → R5 (regular), B1 → B2 → ... → B10 (basement, below R1)
- All players start at R1:2
- Level movement is bidirectional — basement rounds are fully traversable

### Trump Declaration Phase (Two-Phase System)
- **Phase 1 (DEALING & TRUMP_DECLARATION overlapping)**:
  - Cards dealt progressively (1-26 per player)
  - Players MAY bid if they have level cards (optional, no pass tracking)
  - All 26 cards are always dealt, regardless of bidding status
- **Phase 2 (TRUMP_DECLARATION after all 26 cards dealt)**:
  - Players MUST formally bid or pass
  - Formal passes are tracked; bidding continues until count==3 or all pass
- **Valid bids**: Count + level (e.g., 1×7♥, 2×7s, 3×Ks)
- **Bid hierarchy**: 1×Level < 2×Level < 3×Level < 1×HigherLevel, etc.
- **Trump Determination**:
  - If ANY bids made: Highest bidder determines trump suit
  - If NO bids made: Random kitty card drawn (fallback rule)
- **Result**: Trump suit established before KITTY phase begins

### Trump System
- **Trump suit** is the suit called by the highest bidder
- **Trump cards** (highest to lowest): 5♥ > 5♦ > Large Joker > Small Joker > Captain (3 of trump color) > Lieutenant (3 of other color) > Trump Level Card > Non-Trump Level Cards > A > K > Q > J > T > 9 > 8 > 7 > 6 > 4 > 2
- **Non-trump suit cards** rank: A > K > Q > J > T > 9 > 8 > 7 > 6 > 5 > 4 > 3 > 2
- **Special rule:** Pairs and tractors can form from trump hierarchy levels (e.g., 7♥+7♥+7♦+7♦ form a tractor; 7♥+7♥+3♦+3♦ form a tractor)

### Call Helper Phase
- **Dealer calls** a non-trump card (3 identical copies exist)
- **Helper #1**: First player to play the called card
- **Helper #2**: Second player to play the called card
- **Solo helper exception**: If a player plays 2+ copies of the called card (pair or larger combo) BEFORE anyone else plays it, that player becomes the only helper
- **No helpers**: If all three called cards are buried in the kitty

### Card Combinations
- **Single**: any one card
- **Pair**: two identical cards (same rank and suit)
- **Trio**: three identical cards (same rank and suit)
- **Tractor (拖拉机)**: two or more consecutive pairs
  - Regular suit: consecutive ranks in same suit (e.g., ♥7-♥7, ♥8-♥8)
  - Trump cards: consecutive levels in trump hierarchy (e.g., 7♥-7♥, 7♦-7♦ when 7 is level; or 7♥-7♥, 3♦-3♦)
- **Limo (钢板/豪车)**: two or more consecutive trios of same suit (e.g., ♥7-♥7-♥7, ♥8-♥8-♥8)
- **Multi-card throw**: any combination in one suit (when leading)

### Trick Rules
- **Number of tricks per game**: variable (max 26 if all singles, fewer with combos)
- **Suit priority**: must follow the led suit if you have ANY cards of that suit
- **Combination priority**: within the led suit, match the combination structure if able

**When you have the led suit (critical):**
- If you have SUFFICIENT led suit cards to match the combination: play them matched as required
- If you have INSUFFICIENT led suit cards:
  - Play ALL led suit cards you have
  - Fill remaining slots with ANY cards (any suit, including trump)
  - **You can NEVER WIN because you failed to match the combination**

**Combination matching (when you have sufficient led suit cards):**
- Single: play a single
- Pair: play a pair if any, else play singles
- Trio: play a trio if any, else a pair+single, else three singles
- Tractor: play a tractor if any, else two pairs, else a pair+two singles, else four singles
- Limo: play a limo, else two trios, else a trio+pair+single, else a tractor+two singles, else two pairs+two singles, else a pair+four singles, else six singles

**If you don't have the led suit:**
- You may **trump** with cards that EXACTLY match the led combination type
- Or play any cards without trumping (lower play)

**Trump exact match rule:** Trump must be EXACTLY the same combination **type**, not merely the same card count:
- ❌ Two non-sequential pairs cannot trump a tractor
- ❌ Pair+2singles cannot trump two pairs
- ✅ Tractor can trump tractor
- ✅ Pair+2singles can trump pair+2singles (different card ranks, same structure)
- ❌ A **limo (2 consecutive trios, 6 cards)** does **not** match a **tractor of 3 (3 consecutive pairs, 6 cards)** — same card count, different type, so they never compare against each other.

**Trick winner:** Highest card of led suit wins, UNLESS valid trump was played. When comparing multiple trump plays:
- **For single cards:** highest trump rank wins
- **For multi-card throws:** ONLY the **deciding component** is compared. The deciding component is the one whose *group size* is largest — a **trio beats a pair beats a single** — and, among equal group sizes, the longer/higher consecutive run. (For plain combos this equals "the component with the most cards"; the group-size rule only matters for the mixed cases below.)
  - Example: (Pair of Large Joker + Small Joker + Captain) vs (Pair of Small Joker + Large Joker + 5♥) when pair+2singles led
    - Only compare the PAIRS: Large Joker pair wins
    - Singles (Small Joker, Captain, 5♥) are completely ignored
  - Another example: (Pair of 5♥ + Pair of Lieutenant) vs (Pair of Large Joker + Pair of Small Joker) when two pairs led
    - Only compare highest PAIR: 5♥ > Large Joker
    - Second pair (and whether it's a tractor) doesn't matter
  - Mixed-combo example: a multi-throw that contains **both a tractor-of-3 (pairs) and a limo-of-2 (trios)** — both 6 cards — is decided by the **limo**, because a trio outranks a pair. The tractor portion is ignored for comparison.

The engine implements this via a `(group_size, run_length)` signature for the deciding component: a contender must hold a component of the **same** signature to win (so a limo-of-2 `(3,2)` never matches a tractor-of-3 `(2,3)`, and two loose pairs `(2,1)` cannot beat a tractor `(2,2)`).

**Kitty scoring**: Scores in kitty belong to the winner of the last trick, multiplied by 2× the number of cards in the winning combination

### Scoring
- Scoring cards: 5 (5 pts), 10 (10 pts), K (10 pts)
- Farmers accumulate scoring cards; total determines level changes

### Score → Level Changes
| Farmer Score | Result |
|---|---|
| 0 | Dealer side +3 levels |
| 5–55 | Dealer side +2 levels |
| 60–115 | Dealer side +1 level |
| 120–175 | Farmer win, 0 levels (counts as farmer win in statistics) |
| 180–235 | Farmer side +1 level |
| 240–295 | Farmer side +2 levels |
| 300+ | Farmer side +3 levels |

### Red Five Penalties (applied on top of score result)
- ♥5 captured by farmers: Dealer side −2 levels per card (up to 3 cards, one per deck)
- ♦5 captured by farmers: Dealer side −1 level per card (up to 3 cards)

### Wrong-Play Penalty
- Individual player −1 level per wrong play (tracked externally by scorer app, not enforced by engine mid-game)

## Installation

```bash
git clone https://github.com/jimyuhaowu/shengji-engine
cd shengji-engine
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

## Usage

### Functional core (immutable)

`Game` is pure: you pass a state in and get a new state back. The old state is
never mutated.

```python
from shengji import Game, GamePhase

game = Game(num_players=6)
state = game.reset(dealer_id=0)

print(state.phase)          # GamePhase.DEALING
print(state.current_player) # 0
print(state.legal_actions)  # tuple of Action objects

# step(state, action) -> (new_state, info). During DEALING you may pass
# action=None to auto-deal the next round.
action = state.legal_actions[0]
state, info = game.step(state, action)

# The game is over when it reaches SCORING; `info` then carries the outcome.
done = state.phase == GamePhase.SCORING
# info == {"phase": ..., "current_player": ..., "farmer_score": ...,
#          "next_dealer": ..., "game_over": True}  (at SCORING)
```

### Optional Gym-style wrapper

For reinforcement-learning consumers, `ShengJiEnv` adapts the functional core to
the familiar stateful `(observation, reward, done, info)` convention. It stores
the current state internally and delegates all rules to `Game`.

```python
from shengji import ShengJiEnv

env = ShengJiEnv()
obs = env.reset(dealer_id=0)            # observation is the GameState

done = False
while not done:
    actions = env.legal_actions        # action mask for the current player
    action = actions[0] if actions else None
    obs, reward, done, info = env.step(action)

print(env.render())                    # returns a text summary (does not print)
```

Reward is sparse (`0.0` every step): Sheng Ji is a six-player game with no single
canonical agent, so the wrapper leaves reward shaping to the consumer and reports
the terminal outcome (farmer score, next dealer, updated levels) in `info`.

## Project Structure

```
shengji-engine/
├── shengji/                # The library
│   ├── __init__.py
│   ├── game.py             # Game class — main entry point
│   ├── state.py            # GameState dataclass
│   ├── card.py             # Card, Deck, CardCombination
│   ├── types.py            # Action, GamePhase, Suit, Rank enums
│   ├── rules.py            # Legal action generator, trick winner determination
│   ├── scoring.py          # Score calculation, level change computation
│   ├── trump.py            # Trump ordering, trump declaration logic
│   ├── level.py            # Level system, LEVEL_SEQ, step_level
│   └── env.py              # ShengJiEnv — optional Gym-style wrapper
├── tests/                  # pytest suite (unit + integration)
│   ├── test_card.py
│   ├── test_rules.py
│   ├── test_scoring.py
│   ├── test_trump.py
│   ├── test_level.py
│   ├── test_state.py
│   ├── test_env.py
│   └── test_game.py
├── examples/               # Runnable demo / integration scripts
│   ├── full_game.py        # Play a complete game end-to-end
│   ├── edge_cases.py       # Walk through edge-case scenarios
│   └── bidding_demo.py     # Show the two-phase bidding flow
├── docs/                   # Supplementary documentation
│   ├── REFACTORING_SUMMARY.md
│   └── TEST_RESULTS.md
├── pyproject.toml
├── .gitignore
├── README.md
└── CLAUDE.md
```

## Key Design Decisions

- **Immutable state**: `GameState` is a frozen dataclass; `game.step()` returns a new state
- **Separation of concerns**: `rules.py` knows nothing about levels; `level.py` knows nothing about cards
- **Functional core + optional Gym wrapper**: `Game.reset(dealer_id) -> state` and `Game.step(state, action) -> (state, info)` keep the engine pure and immutable; `ShengJiEnv` adds a stateful `step(action) -> (obs, reward, done, info)` adapter for RL consumers
- **Serializable state**: all state can be `json.dumps()`-ed for the server to broadcast

## Running Tests

```bash
pytest tests/ -v
pytest tests/ --cov=shengji --cov-report=term-missing
```

## Examples

Runnable scripts demonstrating the engine (run from the repo root):

```bash
python examples/full_game.py     # play a complete game end-to-end
python examples/edge_cases.py    # walk through edge-case scenarios
python examples/bidding_demo.py  # show the two-phase bidding flow
```

## Dependencies

- Python 3.11+
- No runtime dependencies
- Dev: `pytest`, `pytest-cov`
