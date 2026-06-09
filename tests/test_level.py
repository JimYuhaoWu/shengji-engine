"""Tests for level progression system."""

import pytest
from shengji.level import LEVEL_SEQ, key_index, step_level, parse_level, is_basement_level


class TestLevelSequence:
    """Test the level sequence definition."""

    def test_level_seq_has_all_levels(self):
        """LEVEL_SEQ should have all basement levels and all regular rounds."""
        assert len(LEVEL_SEQ) == 10 + 5 * 11  # 10 basement + 5 rounds × 11 levels
        assert LEVEL_SEQ[0] == "B10:2"
        assert LEVEL_SEQ[-1] == "R5:A"

    def test_level_cards(self):
        """Each regular round should have all 11 level cards."""
        for round_num in range(1, 6):
            level_cards = [k.split(":")[1] for k in LEVEL_SEQ if k.startswith(f"R{round_num}")]
            assert level_cards == ["2", "4", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]

    def test_basement_levels(self):
        """Basement levels should all have rank 2 and be B1-B10."""
        basement_levels = [k for k in LEVEL_SEQ if k.startswith("B")]
        assert len(basement_levels) == 10
        assert all(k.endswith(":2") for k in basement_levels)


class TestKeyIndex:
    """Test key_index function."""

    def test_first_level(self):
        assert key_index("B10:2") == 0

    def test_last_level(self):
        assert key_index("R5:A") == len(LEVEL_SEQ) - 1

    def test_r1_2_in_middle(self):
        r1_2_idx = key_index("R1:2")
        assert r1_2_idx == 10  # After B10:2, B9:2, ..., B1:2

    def test_invalid_level_raises(self):
        with pytest.raises(ValueError):
            key_index("R6:2")  # No R6
        with pytest.raises(ValueError):
            key_index("X1:2")


class TestStepLevel:
    """Test step_level function."""

    def test_step_up_within_round(self):
        assert step_level("R1:2", 1) == "R1:4"
        assert step_level("R1:4", 1) == "R1:6"

    def test_step_up_across_round(self):
        assert step_level("R1:A", 1) == "R2:2"
        assert step_level("R5:A", 1) == "R5:A"  # Already at top, clamped

    def test_step_down_within_round(self):
        assert step_level("R1:4", -1) == "R1:2"

    def test_step_down_across_basement(self):
        assert step_level("R1:2", -1) == "B1:2"

    def test_step_down_in_basement(self):
        assert step_level("B1:2", -1) == "B2:2"
        assert step_level("B2:2", -1) == "B3:2"

    def test_basement_lower_bound_clamped(self):
        assert step_level("B10:2", -1) == "B10:2"  # Can't go lower
        assert step_level("B10:2", -100) == "B10:2"

    def test_regular_upper_bound_clamped(self):
        assert step_level("R5:A", 1) == "R5:A"
        assert step_level("R5:A", 100) == "R5:A"

    def test_step_by_multiple(self):
        assert step_level("R1:2", 3) == "R1:7"
        assert step_level("B10:2", 1) == "B9:2"


class TestParseLevel:
    """Test parse_level function."""

    def test_parse_regular_level(self):
        assert parse_level("R1:2") == ("R1", "2")
        assert parse_level("R3:K") == ("R3", "K")

    def test_parse_basement_level(self):
        assert parse_level("B1:2") == ("B1", "2")
        assert parse_level("B10:2") == ("B10", "2")

    def test_parse_invalid_raises(self):
        with pytest.raises(ValueError):
            parse_level("R1")
        with pytest.raises(ValueError):
            parse_level("R1:2:extra")


class TestIsBasementLevel:
    """Test is_basement_level function."""

    def test_basement_levels_recognized(self):
        assert is_basement_level("B1:2")
        assert is_basement_level("B10:2")
        assert is_basement_level("B5:2")

    def test_regular_levels_not_basement(self):
        assert not is_basement_level("R1:2")
        assert not is_basement_level("R5:A")
