# ruff: noqa: E731
import re
import unittest

from term_timer.triggers import BASE_TRIGGERS
from term_timer.triggers import BLOCK_PATTERN
from term_timer.triggers import DEFAULT_TRIGGERS
from term_timer.triggers import TRIGGERS
from term_timer.triggers import TRIGGERS_REGEX
from term_timer.triggers import apply_trigger_outside_blocks


class TestBaseTriggers(unittest.TestCase):

    def test_chair_trigger(self):
        self.assertEqual(BASE_TRIGGERS["RU2R'U'RU'R'"], 'chair')

    def test_sexy_move_trigger(self):
        self.assertEqual(BASE_TRIGGERS["RUR'U'"], 'sexy-move')

    def test_sledgehammer_trigger(self):
        self.assertEqual(BASE_TRIGGERS["R'FRF'"], 'sledgehammer')


class TestTriggers(unittest.TestCase):

    def test_triggers_generated_from_base(self):
        # 8 variationss (2 algos x 4 rotations)
        for name in BASE_TRIGGERS.values():
            self.assertIn(name, TRIGGERS)
            self.assertEqual(len(TRIGGERS[name]) % 8, 0)


class TestTriggersRegex(unittest.TestCase):

    def test_regex_compiled_for_all_triggers(self):
        self.assertEqual(len(TRIGGERS_REGEX), len(set(BASE_TRIGGERS.values())))

    def test_chair_regex_matches(self):
        chair_regex = TRIGGERS_REGEX['chair']

        for trigger in TRIGGERS['chair']:
            self.assertIsNotNone(chair_regex.search(trigger))

    def test_regex_negative_lookahead(self):
        # Test that the regex does not include moves with 2 or '
        sexy_regex = TRIGGERS_REGEX['sexy-move']
        self.assertIsNone(sexy_regex.search("RUR'U'2"))
        self.assertIsNone(sexy_regex.search("RUR'U''"))


class TestDefaultTriggers(unittest.TestCase):

    def test_all_default_triggers_in_base(self):
        base_trigger_names = set(BASE_TRIGGERS.values())
        for trigger in DEFAULT_TRIGGERS:
            self.assertIn(trigger, base_trigger_names)


class TestBlockPattern(unittest.TestCase):

    def test_block_pattern_matches_simple_block(self):
        text = '[comment]some text[/comment]'
        matches = list(BLOCK_PATTERN.finditer(text))
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].group(), '[comment]some text[/comment]')

    def test_block_pattern_matches_multiple_blocks(self):
        text = '[tag1]content1[/tag1] normal [tag2]content2[/tag2]'
        matches = list(BLOCK_PATTERN.finditer(text))
        self.assertEqual(len(matches), 2)

    def test_block_pattern_no_match_incomplete(self):
        text = '[tag]content without closing'
        matches = list(BLOCK_PATTERN.finditer(text))
        self.assertEqual(len(matches), 0)


class TestApplyTriggerOutsideBlocks(unittest.TestCase):
    def test_no_blocks_simple_replacement(self):
        algorithm = "RUR'U' F U F'"
        regex = re.compile(r"RUR'U'")
        replacement = lambda _: '[SEXY]'

        result = apply_trigger_outside_blocks(algorithm, regex, replacement)
        self.assertEqual(result, "[SEXY] F U F'")

    def test_with_blocks_no_replacement_inside(self):
        algorithm = "RUR'U' [comment]RUR'U'[/comment] R U"
        regex = re.compile(r"RUR'U'")
        replacement = lambda _: '[SEXY]'

        result = apply_trigger_outside_blocks(algorithm, regex, replacement)
        self.assertEqual(result, "[SEXY] [comment]RUR'U'[/comment] R U")

    def test_multiple_blocks(self):
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

    def test_no_matches_no_change(self):
        algorithm = "F U F' [comment]content[/comment]"
        regex = re.compile(r"RUR'U'")
        replacement = lambda _: '[SEXY]'

        result = apply_trigger_outside_blocks(algorithm, regex, replacement)
        self.assertEqual(result, algorithm)

    def test_empty_algorithm(self):
        algorithm = ''
        regex = re.compile(r"RUR'U'")
        replacement = lambda _: '[SEXY]'

        result = apply_trigger_outside_blocks(algorithm, regex, replacement)
        self.assertEqual(result, '')

    def test_only_blocks(self):
        algorithm = "[comment]RUR'U'[/comment]"
        regex = re.compile(r"RUR'U'")
        replacement = lambda _: '[SEXY]'

        result = apply_trigger_outside_blocks(algorithm, regex, replacement)
        self.assertEqual(result, algorithm)

    def test_complex_replacement_function(self):
        algorithm = "RUR'U' F RUR'U'"
        regex = re.compile(r"RUR'U'")
        replacement = lambda m: f'[{m.group().upper()}]'

        result = apply_trigger_outside_blocks(algorithm, regex, replacement)
        self.assertEqual(result, "[RUR'U'] F [RUR'U']")
