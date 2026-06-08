# shengji-engine

Pure Python game engine for six-player 拖拉机 (Sheng Ji / Upgrade / Tractor). No UI, no networking — just the rules, state machine, and legal action generator. This is the foundation that the server, UI, and AI agents all depend on.

## What This Is

A Python library implementing the complete game logic for 拖拉机 as played by a fixed six-player group. It exposes a clean `Game` interface following the OpenAI Gym convention so AI agents can plug in without knowing anything about the internals.

## What This Is Not

- Not a server (see `shengji-server`)
- Not a UI (see `shengji-app`)
- Not an AI agent (see `shengji-ai`)

## Game Rules Implemented

### Players and Roles
- 6 players, fixed seats 0–5 in clockwise order
- Each round: one Dealer, one or two Helpers (called by Dealer), remaining players are Farmers
- Helpers are not publicly known until they reveal themselves by playing the called card

### Decks
- 3 standard decks (156 cards + 6 Jokers = 162 cards total... adjust per house rules)
- Each deck: 52 standard cards + 2 Jokers (small/large)

### Level System
- 11 levels per round: `2, 4, 6, 7, 8, 9, 10, J, Q, K, A` (3 and 5 excluded from levels)
- Rounds: R1 → R2 → R3 → R4 → R5 (regular), B1 → B2 → ... → B10 (basement, below R1)
- All players start at R1:2
- Level movement is bidirectional — basement rounds are fully traversable

### Trump System
- Current level cards of all suits are trump (e.g. if playing 7s, all 7s are trump)
- One suit is declared trump suit each round (via bidding on Jokers/level cards)
- Trump rank within trump suit: Small Joker < Large Joker < Level card of trump suit < Level card of other suits < A < K < ... (of trump suit)
- Non-trump suits rank normally within themselves

### Card Combinations (legal plays)
- **Single**: any one card
- **Pair**: two identical cards
- **Tractor (拖拉机)**: two or more consecutive pairs of same suit (e.g. 77-88, JJ-QQ-KK)
- **Multi-card throw**: any combination of the above in one suit, when leading a trick

### Trick Rules
- Leader plays any legal combination
- Others must follow suit if able, matching the combination type and length
- If unable to follow, must play trump if able
- If unable to trump, play anything
- Highest card/combo of led suit wins, unless trumped

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

```python
from shengji.game import Game
from shengji.types import Action, GamePhase

# Create a new game
game = Game(num_players=6)
state = game.reset()

print(state.phase)          # GamePhase.DEALING
print(state.current_player) # 0
print(state.legal_actions)  # list of Action objects

# Step the game
action = state.legal_actions[0]
state, reward, done, info = game.step(action)
```

## Project Structure

```
shengji-engine/
├── shengji/
│   ├── __init__.py
│   ├── game.py          # Game class — main entry point
│   ├── state.py         # GameState dataclass
│   ├── card.py          # Card, Deck, CardCombination
│   ├── types.py         # Action, GamePhase, Suit, Rank enums
│   ├── rules.py         # Legal action generator, trick winner determination
│   ├── scoring.py       # Score calculation, level change computation
│   ├── trump.py         # Trump ordering, trump declaration logic
│   └── level.py         # Level system, LEVEL_SEQ, stepLevel
├── tests/
│   ├── test_card.py
│   ├── test_rules.py
│   ├── test_scoring.py
│   ├── test_trump.py
│   ├── test_level.py
│   └── test_game.py     # Full game integration tests
├── pyproject.toml
├── README.md
└── CLAUDE.md
```

## Key Design Decisions

- **Immutable state**: `GameState` is a frozen dataclass; `game.step()` returns a new state
- **Separation of concerns**: `rules.py` knows nothing about levels; `level.py` knows nothing about cards
- **Gym interface**: `reset()` / `step(action)` / `render()` so AI agents plug in directly
- **Serializable state**: all state can be `json.dumps()`-ed for the server to broadcast

## Running Tests

```bash
pytest tests/ -v
pytest tests/ --cov=shengji --cov-report=term-missing
```

## Dependencies

- Python 3.11+
- No runtime dependencies
- Dev: `pytest`, `pytest-cov`
