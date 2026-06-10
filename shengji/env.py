"""Optional stateful, Gym-style wrapper around the functional Game engine.

The core engine (``Game``) is pure and immutable: ``reset(dealer_id) -> state``
and ``step(state, action) -> (state, info)``. Reinforcement-learning consumers
often expect the OpenAI-Gym convention instead — a stateful object whose
``step(action)`` returns ``(observation, reward, done, info)``. ``ShengJiEnv`` is
a thin adapter that provides exactly that while delegating all rules to ``Game``.

Design notes:
- The observation IS the immutable ``GameState`` (it already carries
  ``legal_actions`` for the current player).
- Reward is sparse (``0.0`` every step). Sheng Ji is a six-player game with no
  single canonical agent, so a built-in scalar reward would bake in a
  perspective. The terminal outcome (farmer score, next dealer, updated levels)
  is reported in ``info`` and via the final ``GameState``; reward shaping is left
  to the consumer.
- ``render`` returns a string and never prints, honouring the library's no-I/O rule.
"""

from typing import Optional, Tuple

from .game import Game
from .state import GameState
from .types import Action, GamePhase


class ShengJiEnv:
    """Stateful Gym-style adapter over the functional :class:`Game` engine."""

    def __init__(self, num_players: int = 6):
        self.game = Game(num_players=num_players)
        self.state: Optional[GameState] = None

    def reset(self, dealer_id: int = 0) -> GameState:
        """Start a new game and return the initial observation (GameState)."""
        self.state = self.game.reset(dealer_id=dealer_id)
        return self.state

    def step(self, action: Optional[Action] = None) -> Tuple[GameState, float, bool, dict]:
        """Apply ``action`` and return ``(observation, reward, done, info)``.

        ``action`` may be ``None`` during DEALING to auto-deal the next round
        (forwarded to the underlying engine). ``done`` is True once the game
        reaches the SCORING phase.
        """
        if self.state is None:
            raise RuntimeError("reset() must be called before step().")
        self.state, info = self.game.step(self.state, action)
        done = self.state.phase == GamePhase.SCORING
        reward = 0.0
        return self.state, reward, done, info

    @property
    def legal_actions(self) -> Tuple[Action, ...]:
        """Legal actions for the current player (empty before reset)."""
        return self.state.legal_actions if self.state is not None else ()

    @property
    def current_player(self) -> int:
        """Index of the player to act (0 before reset)."""
        return self.state.current_player if self.state is not None else 0

    @property
    def done(self) -> bool:
        """Whether the game has reached the SCORING phase."""
        return self.state is not None and self.state.phase == GamePhase.SCORING

    def render(self, mode: str = "ansi") -> str:
        """Return a one-glance text summary of the current state (does NOT print)."""
        if self.state is None:
            return "<no game started>"
        s = self.state
        return "\n".join([
            f"phase={s.phase.name} current_player={s.current_player} dealer={s.dealer_id}",
            f"trump_suit={s.trump_suit} trump_level={s.trump_level}",
            f"hand_sizes={[len(h) for h in s.hands]} tricks_won={len(s.tricks_won)} "
            f"legal_actions={len(s.legal_actions)}",
        ])
