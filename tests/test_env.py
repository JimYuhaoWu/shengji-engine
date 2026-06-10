"""Tests for the optional Gym-style ShengJiEnv wrapper."""

import random

import pytest

from shengji import ShengJiEnv, GamePhase


class TestShengJiEnv:
    def test_reset_returns_initial_observation(self):
        env = ShengJiEnv()
        obs = env.reset(dealer_id=0)
        assert obs.phase == GamePhase.DEALING
        assert obs.dealer_id == 0
        assert env.current_player == 0
        assert len(env.legal_actions) > 0
        assert env.done is False

    def test_step_before_reset_raises(self):
        env = ShengJiEnv()
        with pytest.raises(RuntimeError):
            env.step(None)

    def test_step_returns_four_tuple(self):
        env = ShengJiEnv()
        env.reset()
        obs, reward, done, info = env.step(env.legal_actions[0])
        assert reward == 0.0
        assert isinstance(done, bool)
        assert "phase" in info and "current_player" in info

    def test_full_game_reaches_done(self):
        """Playing random actions terminates at SCORING with done=True."""
        random.seed(123)
        env = ShengJiEnv()
        env.reset(dealer_id=0)
        done = False
        steps = 0
        info = {}
        while not done and steps < 5000:
            acts = env.legal_actions
            action = random.choice(acts) if acts else None
            obs, reward, done, info = env.step(action)
            steps += 1
        assert done is True
        assert env.done is True
        assert obs.phase == GamePhase.SCORING
        assert info.get("game_over") is True
        assert "farmer_score" in info and "next_dealer" in info
        # all cards played
        assert sum(len(h) for h in obs.hands) == 0

    def test_render_returns_string_without_printing(self, capsys):
        env = ShengJiEnv()
        assert env.render() == "<no game started>"
        env.reset()
        out = env.render()
        assert isinstance(out, str)
        assert "phase=DEALING" in out
        # render must not print anything (no-I/O rule)
        captured = capsys.readouterr()
        assert captured.out == ""
