"""Tests for triggers."""
# ruff: noqa: E731
import re
import unittest

from cubing_algs.triggers import TRIGGER_PATTERNS

from term_timer.triggers import BLOCK_PATTERN
from term_timer.triggers import DEFAULT_TRIGGERS
from term_timer.triggers import TRIGGERS
from term_timer.triggers import TRIGGERS_REGEX
from term_timer.triggers import apply_trigger_outside_blocks


def _slug(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


class TestTriggers(unittest.TestCase):
    """Tests for TRIGGERS generation."""

    def test_triggers_generated_from_patterns(self) -> None:
        """Test triggers generated from cubing_algs TRIGGER_PATTERNS."""
        for pattern in TRIGGER_PATTERNS:
            name = _slug(pattern.name)
            self.assertIn(name, TRIGGERS)
            for seed in [pattern.moves, *pattern.variations]:
                self.assertIn(seed, TRIGGERS[name])
            self.assertEqual(len(TRIGGERS[name]), len(set(TRIGGERS[name])))


class TestTriggersRegex(unittest.TestCase):
    """Tests for TRIGGERS_REGEX patterns."""

    def test_regex_compiled_for_all_triggers(self) -> None:
        """Test regex compiled for all triggers."""
        self.assertEqual(len(TRIGGERS_REGEX), len(TRIGGER_PATTERNS))

    def test_anti_sune_regex_matches(self) -> None:
        """Test anti-sune regex matches."""
        anti_sune_regex = TRIGGERS_REGEX['anti-sune']

        for trigger in TRIGGERS['anti-sune']:
            self.assertIsNotNone(anti_sune_regex.search(trigger))

    def test_regex_negative_lookahead(self) -> None:
        """Test regex negative lookahead."""
        # Test that the regex does not include moves with 2 or '
        sexy_regex = TRIGGERS_REGEX['sexy-move']
        self.assertIsNone(sexy_regex.search("RUR'U'2"))
        self.assertIsNone(sexy_regex.search("RUR'U''"))


class TestDefaultTriggers(unittest.TestCase):
    """Tests for DEFAULT_TRIGGERS configuration."""

    def test_all_default_triggers_in_triggers(self) -> None:
        """Test all default triggers are in TRIGGERS."""
        for trigger in DEFAULT_TRIGGERS:
            self.assertIn(trigger, TRIGGERS)


class TestBlockPattern(unittest.TestCase):
    """Tests for BLOCK_PATTERN regex."""

    def test_block_pattern_matches_simple_block(self) -> None:
        """Test block pattern matches simple block."""
        text = '[comment]some text[/comment]'
        matches = list(BLOCK_PATTERN.finditer(text))
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].group(), '[comment]some text[/comment]')

    def test_block_pattern_matches_multiple_blocks(self) -> None:
        """Test block pattern matches multiple blocks."""
        text = '[tag1]content1[/tag1] normal [tag2]content2[/tag2]'
        matches = list(BLOCK_PATTERN.finditer(text))
        self.assertEqual(len(matches), 2)

    def test_block_pattern_no_match_incomplete(self) -> None:
        """Test block pattern no match incomplete."""
        text = '[tag]content without closing'
        matches = list(BLOCK_PATTERN.finditer(text))
        self.assertEqual(len(matches), 0)


class TestApplyTriggerOutsideBlocks(unittest.TestCase):
    """Tests for apply_trigger_outside_blocks function."""

    def test_no_blocks_simple_replacement(self) -> None:
        """Test no blocks simple replacement."""
        algorithm = "RUR'U' F U F'"
        regex = re.compile(r"RUR'U'")
        replacement = lambda _: '[SEXY]'

        result = apply_trigger_outside_blocks(algorithm, regex, replacement)
        self.assertEqual(result, "[SEXY] F U F'")

    def test_with_blocks_no_replacement_inside(self) -> None:
        """Test with blocks no replacement inside."""
        algorithm = "RUR'U' [comment]RUR'U'[/comment] R U"
        regex = re.compile(r"RUR'U'")
        replacement = lambda _: '[SEXY]'

        result = apply_trigger_outside_blocks(algorithm, regex, replacement)
        self.assertEqual(result, "[SEXY] [comment]RUR'U'[/comment] R U")

    def test_multiple_blocks(self) -> None:
        """Test multiple blocks."""
        algorithm = (
            "RUR'U' [tag1]content[/tag1] "
            "RUR'U' [tag2]RUR'U'[/tag2] "
            "RUR'U'"
        )
        regex = re.compile(r"RUR'U'")
        replacement = lambda _: '[SEXY]'

        result = apply_trigger_outside_blocks(algorithm, regex, replacement)
        expected = (
            "[SEXY] [tag1]content[/tag1] "
            "[SEXY] [tag2]RUR'U'[/tag2] "
            "[SEXY]"
        )
        self.assertEqual(result, expected)

    def test_no_matches_no_change(self) -> None:
        """Test no matches no change."""
        algorithm = "F U F' [comment]content[/comment]"
        regex = re.compile(r"RUR'U'")
        replacement = lambda _: '[SEXY]'

        result = apply_trigger_outside_blocks(algorithm, regex, replacement)
        self.assertEqual(result, algorithm)

    def test_empty_algorithm(self) -> None:
        """Test empty algorithm."""
        algorithm = ''
        regex = re.compile(r"RUR'U'")
        replacement = lambda _: '[SEXY]'

        result = apply_trigger_outside_blocks(algorithm, regex, replacement)
        self.assertEqual(result, '')

    def test_only_blocks(self) -> None:
        """Test only blocks."""
        algorithm = "[comment]RUR'U'[/comment]"
        regex = re.compile(r"RUR'U'")
        replacement = lambda _: '[SEXY]'

        result = apply_trigger_outside_blocks(algorithm, regex, replacement)
        self.assertEqual(result, algorithm)

    def test_complex_replacement_function(self) -> None:
        """Test complex replacement function."""
        algorithm = "RUR'U' F RUR'U'"
        regex = re.compile(r"RUR'U'")
        replacement = lambda m: f'[{m.group().upper()}]'

        result = apply_trigger_outside_blocks(algorithm, regex, replacement)
        self.assertEqual(result, "[RUR'U'] F [RUR'U']")
