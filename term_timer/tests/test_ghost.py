"""Tests for ghost racing mode."""
import io
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from rich.console import Console as RichConsole

from term_timer.arguments import get_parser
from term_timer.formatter import format_ghost_delta
from term_timer.in_out import save_solves
from term_timer.in_out import scramble_to_key
from term_timer.interface.sounds import STEP_AHEAD_FUNDAMENTAL
from term_timer.interface.sounds import STEP_BEHIND_FUNDAMENTAL
from term_timer.interface.sounds import SoundPlayer
from term_timer.interface.stopwatch import StopWatch
from term_timer.interface.terminal import Terminal
from term_timer.methods import get_method_analyser
from term_timer.methods.annotations import TrackedStep
from term_timer.scripts.commands import ghost as ghost_mod
from term_timer.solve import Solve

SHORT_SCRAMBLE = "L2 D' L' F' L'"
SHORT_MOVES = 'L@0 F@507 L@1019 D@1768 L@2518 L@2608'


def make_solve(  # noqa: PLR0913
        date: int = 1766883476,
        time: int = 2608404439,
        scramble: str = SHORT_SCRAMBLE,
        moves: str | None = SHORT_MOVES,
        *,
        method: str = 'cfop',
        flag: str = '',
) -> Solve:
    """
    Build a Solve fixture with a reconstruction.

    Returns:
        A configured Solve instance.

    """
    solve = Solve(date, time, scramble, moves=moves, flag=flag)  # type: ignore[arg-type]
    solve.method_name = method
    solve.orientation = 'auto'
    return solve


def build_groups(method: str) -> tuple[tuple[TrackedStep, ...], ...]:
    """
    Build the tracked step groups the live stopwatch would use.

    Returns:
        The groups for the given method.

    """
    cls = get_method_analyser(method)
    return cls.step_groups or tuple(
        (TrackedStep(name, None),)
        for name in cls.step_list
    )


class GhostStopWatch(StopWatch, Terminal):
    """Minimal StopWatch harness with terminal helpers for rendering tests."""


class TestScrambleToKey(unittest.TestCase):
    """Tests for the scramble to file-key transform."""

    def test_spaces_and_quotes(self) -> None:
        """Spaces become underscores and quotes become dashes."""
        self.assertEqual(scramble_to_key("R U R' U'"), 'R_U_R-_U-')

    def test_plain_scramble(self) -> None:
        """A scramble without quotes only swaps spaces."""
        self.assertEqual(scramble_to_key('R U F2 D'), 'R_U_F2_D')

    def test_key_is_url_safe(self) -> None:
        """The key only contains safe characters."""
        key = scramble_to_key(SHORT_SCRAMBLE)
        self.assertEqual(key, 'L2_D-_L-_F-_L-')


class TestGhostSplits(unittest.TestCase):
    """Tests for Solve.ghost_splits extraction."""

    def test_cfop_splits_with_skips(self) -> None:
        """CFOP splits map every group; skips inherit the previous time."""
        solve = make_solve(method='cfop')
        splits = solve.ghost_splits(build_groups('cfop'))

        self.assertEqual(
            splits,
            (
                (1_768_000_000,),
                (1_768_000_000,),
                (1_768_000_000,),
                (2_608_000_000,),
            ),
        )

    def test_absent_tracked_step_is_omitted(self) -> None:
        """A tracked step the ghost never names is left out entirely."""
        solve = make_solve(method='cf4op')
        splits = solve.ghost_splits(build_groups('cf4op'))

        # This degenerate solve is an XXXXCross, so the tracked Cross and
        # per-pair F2L steps have no matching summary entry and their
        # groups stay empty. OLL is a real (skipped) summary step, so it
        # stays, inheriting the last known checkpoint (0, since Cross
        # could not be aligned).
        self.assertEqual(
            splits,
            ((), (), (0,), (2_608_000_000,)),
        )

    def test_group_splits_are_chronological(self) -> None:
        """Slots solved out of order are sorted into race positions."""
        solve = make_solve()
        groups = (
            (
                TrackedStep('F2L 1', 'F2L FR'),
                TrackedStep('F2L 2', 'F2L FL'),
            ),
        )
        summary = [
            {'name': 'F2L 1', 'times': [2000.0]},
            {'name': 'F2L 2', 'times': [1000.0]},
        ]
        # cached_property is a non-data descriptor: seeding the instance
        # dict swaps the analysis without running it.
        solve.__dict__['method_applied'] = SimpleNamespace(summary=summary)

        self.assertEqual(
            solve.ghost_splits(groups),
            ((1_000_000_000, 2_000_000_000),),
        )

    def test_no_reconstruction_returns_empty(self) -> None:
        """A solve without moves yields no splits."""
        solve = make_solve(moves=None)
        self.assertEqual(solve.ghost_splits(build_groups('cfop')), ())


class TestFormatGhostDelta(unittest.TestCase):
    """Tests for the ghost delta formatter."""

    def test_behind_is_red_down(self) -> None:
        """A positive delta renders a red down arrow with a plus sign."""
        self.assertEqual(
            format_ghost_delta(390_000_000),
            '[red]▼  +0.39[/red]',
        )

    def test_ahead_is_green_up(self) -> None:
        """A negative delta renders a green up arrow with a minus sign."""
        self.assertEqual(
            format_ghost_delta(-390_000_000),
            '[green]▲  -0.39[/green]',
        )

    def test_tie_counts_as_ahead(self) -> None:
        """A zero delta renders as ahead."""
        self.assertEqual(
            format_ghost_delta(0),
            '[green]▲   0.00[/green]',
        )

    def test_values_share_a_column(self) -> None:
        """Deltas of different magnitudes render on the same width."""
        self.assertEqual(
            len(format_ghost_delta(390_000_000).replace('red', '')),
            len(format_ghost_delta(-13_180_000_000).replace('green', '')),
        )


class TestGhostSounds(unittest.TestCase):
    """Tests for the ahead/behind step sound variants."""

    def test_pitched_waves_differ_from_base(self) -> None:
        """Ahead is pitched above and behind below the neutral ting."""
        self.assertGreater(STEP_AHEAD_FUNDAMENTAL, 880.0)
        self.assertLess(STEP_BEHIND_FUNDAMENTAL, 880.0)

        base = SoundPlayer.generate_step_wave()
        ahead = SoundPlayer.generate_step_wave(STEP_AHEAD_FUNDAMENTAL)
        behind = SoundPlayer.generate_step_wave(STEP_BEHIND_FUNDAMENTAL)

        self.assertFalse((base == ahead).all())
        self.assertFalse((base == behind).all())

    def test_variants_fall_back_to_bell(self) -> None:
        """Both variants emit the bell when audio is unavailable."""
        player = SoundPlayer.__new__(SoundPlayer)
        player.available = False

        buf = io.StringIO()
        with patch('sys.stdout', buf):
            player.solve_step_ahead()
            player.solve_step_behind()

        self.assertEqual(buf.getvalue(), '\a' * 2)


class TestLoadReference(unittest.TestCase):
    """Tests for reference-solve resolution."""

    @staticmethod
    def parse(*args: str) -> Namespace:
        """
        Parse a ghost command line into options.

        Returns:
            The parsed namespace.

        """
        return get_parser().parse_args(['ghost', *args])

    def test_missing_id_errors(self) -> None:
        """Omitting the solve id is an error."""
        options = self.parse()
        self.assertIsNone(ghost_mod.load_reference(options))

    def test_out_of_range_errors(self) -> None:
        """An id past the pool is an error."""
        options = self.parse('5')
        with patch.object(ghost_mod, 'load_all_solves', return_value=[]):
            self.assertIsNone(ghost_mod.load_reference(options))

    def test_valid_id_resolves(self) -> None:
        """A valid id resolves and carries the command method."""
        options = self.parse('1', '-m', 'cfop')
        reference = make_solve(method='cf4op')
        with patch.object(
                ghost_mod, 'load_all_solves', return_value=[reference],
        ):
            resolved = ghost_mod.load_reference(options)

        self.assertIs(resolved, reference)
        self.assertEqual(reference.method_name, 'cfop')


class TestSelectGhost(unittest.TestCase):
    """Tests for ghost selection over the scramble history."""

    @staticmethod
    def parse(*args: str) -> Namespace:
        """
        Parse a ghost command line into options.

        Returns:
            The parsed namespace.

        """
        return get_parser().parse_args(['ghost', *args])

    def test_empty_history_selects_reference(self) -> None:
        """With no history the reference itself is the ghost."""
        options = self.parse('1')
        reference = make_solve()
        ghost_solve = ghost_mod.select_ghost(reference, [], options)
        self.assertIs(ghost_solve, reference)

    def test_pb_selected_including_reference(self) -> None:
        """The fastest analysable solve wins, reference included."""
        options = self.parse('1')
        reference = make_solve(date=1, time=2_608_404_439)
        faster = make_solve(date=2, time=1_000_000_000)
        slower = make_solve(date=3, time=9_000_000_000)

        ghost_solve = ghost_mod.select_ghost(
            reference, [slower, faster], options,
        )
        self.assertIs(ghost_solve, faster)

    def test_dnf_history_ignored(self) -> None:
        """A DNF attempt never becomes the ghost even if faster."""
        options = self.parse('1')
        reference = make_solve(date=1, time=2_608_404_439)
        dnf = make_solve(date=2, time=1, flag='DNF')

        ghost_solve = ghost_mod.select_ghost(reference, [dnf], options)
        self.assertIs(ghost_solve, reference)


class TestGhostLibrary(unittest.TestCase):
    """Tests for the ghost summary and review handlers."""

    def setUp(self) -> None:
        """Point the ghost directory at a temporary folder."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)
        patcher = patch.object(
            ghost_mod, 'GHOSTS_DIRECTORY', self.directory,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def parse(*args: str) -> Namespace:
        """
        Parse a ghost command line into options.

        Returns:
            The parsed namespace.

        """
        return get_parser().parse_args(['ghost', *args])

    def test_summary_empty(self) -> None:
        """An empty library reports nothing recorded."""
        self.assertEqual(ghost_mod.ghost_summary(3), 1)

    def test_summary_lists_scrambles(self) -> None:
        """The summary lists a row per recorded scramble."""
        key = scramble_to_key(SHORT_SCRAMBLE)
        save_solves(3, key, [make_solve()], directory=self.directory)

        recorder = RichConsole(record=True)
        with patch.object(ghost_mod, 'console', recorder):
            code = ghost_mod.ghost_summary(3)

        self.assertEqual(code, 0)
        self.assertIn(SHORT_SCRAMBLE, recorder.export_text())

    def test_review_without_attempts(self) -> None:
        """Reviewing a scramble with no stored attempts warns."""
        options = self.parse('1')
        with patch.object(
                ghost_mod, 'load_all_solves', return_value=[make_solve()],
        ):
            self.assertEqual(ghost_mod.ghost_review(options), 1)


class TestGhostDisplay(unittest.TestCase):
    """Tests for the ghost segments grafted onto stopwatch lines."""

    def setUp(self) -> None:
        """Patch sound playback for each test."""
        sound_patcher = patch(
            'term_timer.interface.sounds.sd', create=True,
        )
        sound_patcher.start()
        self.addCleanup(sound_patcher.stop)

    @staticmethod
    def build(*, ghost_active: bool) -> GhostStopWatch:
        """
        Build a stopwatch harness with a recording console.

        Returns:
            The configured harness.

        """
        watch = GhostStopWatch()
        watch.console = RichConsole(record=True, width=120)
        watch.step_width = 0
        if ghost_active:
            watch.ghost_splits = ((6_020_000_000,),)
        return watch

    def test_step_renders_ghost_segment(self) -> None:
        """A completed ghost step prints the split and delta segment."""
        watch = self.build(ghost_active=True)
        with patch('sys.stdout', io.StringIO()):
            watch.print_step(
                'timer_base', 6_410_000_000, 'Cross',
                htm=6, ghost_split=6_020_000_000,
            )
        output = watch.console.export_text()
        self.assertIn('👻', output)
        self.assertIn('6.02', output)
        self.assertIn('▼  +0.39', output)

    def test_first_step_holds_the_delta_column(self) -> None:
        """A step without delta keeps the ghost segment aligned."""
        watch = self.build(ghost_active=True)
        watch.step_width = 6
        with patch('sys.stdout', io.StringIO()):
            watch.print_step(
                'timer_base', 6_410_000_000, 'Cross',
                htm=6, ghost_split=6_020_000_000,
            )
            watch.print_step(
                'timer_base', 9_410_000_000, 'F2L',
                delta_time=3_000_000_000, htm=6,
                ghost_split=8_020_000_000,
            )
        first, second = [
            line for line in watch.console.export_text().splitlines()
            if '👻' in line
        ]
        self.assertEqual(first.index('👻'), second.index('👻'))

    def test_final_step_renders_verdict(self) -> None:
        """The solved checkpoint appends WIN or LOSS to the delta."""
        watch = self.build(ghost_active=True)
        with patch('sys.stdout', io.StringIO()):
            watch.print_step(
                'timer_base', 5_000_000_000, 'PLL',
                last=True, ghost_split=6_020_000_000,
            )
        output = watch.console.export_text()
        self.assertIn('6.02', output)
        self.assertIn('▲  -1.02', output)
        self.assertIn('WIN', output)

    def test_final_step_renders_loss(self) -> None:
        """Finishing behind the ghost prints LOSS."""
        watch = self.build(ghost_active=True)
        with patch('sys.stdout', io.StringIO()):
            watch.print_step(
                'timer_base', 7_000_000_000, 'PLL',
                last=True, ghost_split=6_020_000_000,
            )
        self.assertIn('LOSS', watch.console.export_text())

    def test_step_uses_the_overridden_emoji(self) -> None:
        """The ghost marker follows the stopwatch emoji."""
        watch = self.build(ghost_active=True)
        watch.ghost_emoji = '📅'
        with patch('sys.stdout', io.StringIO()):
            watch.print_step(
                'timer_base', 6_410_000_000, 'Cross',
                htm=6, ghost_split=6_020_000_000,
            )
        output = watch.console.export_text()
        self.assertIn('📅', output)
        self.assertNotIn('👻', output)

    def test_no_ghost_segment_when_inactive(self) -> None:
        """Without a ghost the step line carries no ghost marker."""
        watch = self.build(ghost_active=False)
        with patch('sys.stdout', io.StringIO()):
            watch.print_step('timer_base', 6_410_000_000, 'Cross', htm=6)
        self.assertNotIn('👻', watch.console.export_text())

    def test_running_line_carries_no_ghost_segment(self) -> None:
        """The running timer stays free of ghost markup."""
        watch = self.build(ghost_active=True)
        with patch('sys.stdout', io.StringIO()):
            watch.print_timer(6_410_000_000, 'timer_base')
        output = watch.console.export_text()
        self.assertIn('06.41', output)
        self.assertNotIn('👻', output)


class TestCurrentGhostSplit(unittest.TestCase):
    """Tests for the positional lookup of a ghost checkpoint."""

    @staticmethod
    def build() -> GhostStopWatch:
        """
        Build a stopwatch racing a two-group ghost.

        Returns:
            The configured harness.

        """
        watch = GhostStopWatch()
        watch.ghost_splits = (
            (5_490_000_000,),
            (
                10_320_000_000, 15_260_000_000,
                19_230_000_000, 22_550_000_000,
            ),
        )
        return watch

    def test_position_inside_group(self) -> None:
        """Each checkpoint races the ghost checkpoint at the same rank."""
        watch = self.build()
        watch.group_progress = 1

        self.assertEqual(watch.current_ghost_split(0), 10_320_000_000)
        self.assertEqual(watch.current_ghost_split(3), 22_550_000_000)

    def test_beyond_group_returns_none(self) -> None:
        """An extra live checkpoint races without a ghost split."""
        watch = self.build()
        watch.group_progress = 1

        self.assertIsNone(watch.current_ghost_split(4))

    def test_beyond_groups_returns_none(self) -> None:
        """A group the ghost never reached yields no split."""
        watch = self.build()
        watch.group_progress = 2

        self.assertIsNone(watch.current_ghost_split(0))

    def test_without_ghost_returns_none(self) -> None:
        """No ghost means no split at all."""
        watch = GhostStopWatch()

        self.assertIsNone(watch.current_ghost_split(0))


class TestRefreshGhost(unittest.TestCase):
    """Tests for the in-session ghost re-election."""

    @staticmethod
    def parse(*args: str) -> Namespace:
        """
        Parse a ghost command line into options.

        Returns:
            The parsed namespace.

        """
        return get_parser().parse_args(['ghost', *args])

    @staticmethod
    def build_instance(ghost_solve: Solve, done: list[Solve]) -> Namespace:
        """
        Build a timer stand-in carrying a ghost and finished solves.

        Returns:
            The stand-in instance.

        """
        return Namespace(ghost=ghost_solve, stack_done=done)

    def test_new_best_becomes_the_ghost(self) -> None:
        """Beating the ghost promotes the fresh attempt for the next race."""
        options = self.parse('1')
        reference = make_solve(date=1, time=2_608_404_439)
        faster = make_solve(date=2, time=1_000_000_000)
        instance = self.build_instance(reference, [faster])

        ghost_mod.refresh_ghost(instance, reference, [], options)  # type: ignore[arg-type]

        self.assertIs(instance.ghost, faster)

    def test_slower_attempt_keeps_the_ghost(self) -> None:
        """A slower attempt leaves the target untouched."""
        options = self.parse('1')
        reference = make_solve(date=1, time=2_608_404_439)
        slower = make_solve(date=2, time=9_000_000_000)
        instance = self.build_instance(reference, [slower])

        ghost_mod.refresh_ghost(instance, reference, [], options)  # type: ignore[arg-type]

        self.assertIs(instance.ghost, reference)

    def test_history_stays_in_the_pool(self) -> None:
        """A stored attempt still wins over a slower session solve."""
        options = self.parse('1')
        reference = make_solve(date=1, time=2_608_404_439)
        stored = make_solve(date=2, time=1_000_000_000)
        attempt = make_solve(date=3, time=2_000_000_000)
        instance = self.build_instance(reference, [attempt])

        ghost_mod.refresh_ghost(instance, reference, [stored], options)  # type: ignore[arg-type]

        self.assertIs(instance.ghost, stored)
