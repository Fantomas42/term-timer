"""Tests for ghost racing mode."""
import io
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from rich.console import Console as RichConsole
from rich.theme import Theme

from term_timer.arguments import get_parser
from term_timer.formatter import format_ghost_delta
from term_timer.in_out import save_solves
from term_timer.in_out import scramble_to_key
from term_timer.interface.console import theme as console_theme
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

    def test_digest_is_stable(self) -> None:
        """The same scramble always digests to the same key."""
        self.assertEqual(scramble_to_key("R U R' U'"), 'e6b3c60b3559406a')

    def test_distinct_scrambles(self) -> None:
        """Two different scrambles map to two different keys."""
        self.assertNotEqual(
            scramble_to_key("R U R' U'"),
            scramble_to_key('R U F2 D'),
        )

    def test_key_is_url_safe(self) -> None:
        """The key only contains safe characters."""
        key = scramble_to_key(SHORT_SCRAMBLE)
        self.assertEqual(key, 'e80cd213e69009a6')

    def test_key_fits_a_filename(self) -> None:
        """A big cube scramble still yields a short, bounded key."""
        scramble = ' '.join(["3Rw'"] * 100)
        key = scramble_to_key(scramble)

        self.assertEqual(len(key), 16)
        self.assertLess(len(f'7x7x7-{ key }.json'), 255)


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
        """Omitting the reference is an error."""
        options = self.parse()
        self.assertIsNone(ghost_mod.load_reference(options))

    def test_out_of_range_errors(self) -> None:
        """An id past the pool is an error."""
        options = self.parse('5')
        with patch.object(ghost_mod, 'load_all_solves', return_value=[]):
            self.assertIsNone(ghost_mod.load_reference(options))

    def test_zero_is_not_an_id(self) -> None:
        """The pool is indexed from one, never from the end."""
        options = self.parse('0')
        with patch.object(
                ghost_mod, 'load_all_solves', return_value=[make_solve()],
        ):
            self.assertIsNone(ghost_mod.load_reference(options))

    def test_valid_id_resolves(self) -> None:
        """A valid id resolves and carries the command method."""
        options = self.parse('1', '-m', 'cfop')
        reference = make_solve(method='cf4op')
        with patch.object(
                ghost_mod, 'load_all_solves', return_value=[reference],
        ):
            resolved = ghost_mod.load_reference(options)

        if resolved is None:
            self.fail('a valid id must resolve')

        self.assertIs(resolved.solve, reference)
        self.assertEqual(resolved.key, scramble_to_key(SHORT_SCRAMBLE))
        self.assertEqual(resolved.label, '#1')
        self.assertEqual(reference.method_name, 'cfop')


class TestReferenceByKey(unittest.TestCase):
    """Tests for addressing a scramble by its permanent key."""

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
        self.key = scramble_to_key(SHORT_SCRAMBLE)

    @staticmethod
    def resolve(
            token: str,
            pool: list[Solve],
    ) -> ghost_mod.GhostReference | None:
        """
        Resolve a reference token against a controlled solve pool.

        Returns:
            The resolved reference, or None.

        """
        options = get_parser().parse_args(['ghost', token])
        with patch.object(ghost_mod, 'load_all_solves', return_value=pool):
            return ghost_mod.load_reference(options)

    def resolve_ok(
            self,
            token: str,
            pool: list[Solve],
    ) -> ghost_mod.GhostReference:
        """
        Resolve a token expected to name a stored scramble.

        Returns:
            The resolved reference.

        """
        resolved = self.resolve(token, pool)
        if resolved is None:
            self.fail(f'{ token } resolved to nothing')

        return resolved

    def test_prefix_resolves_the_scramble(self) -> None:
        """An unambiguous prefix names the stored scramble."""
        seed = make_solve()
        save_solves(3, self.key, [seed], directory=self.directory)

        resolved = self.resolve_ok(self.key[:4], [])

        self.assertEqual(resolved.key, self.key)
        self.assertEqual(resolved.solve.date, seed.date)

    def test_orphan_scramble_stays_raceable(self) -> None:
        """A scramble whose seed left the pool answers to its key."""
        save_solves(3, self.key, [make_solve()], directory=self.directory)

        resolved = self.resolve_ok(self.key, [make_solve(date=1)])

        self.assertEqual(resolved.label, self.key[:8])

    def test_pool_copy_wins_over_the_stored_seed(self) -> None:
        """A seed still in the pool races as edited, and keeps its id."""
        save_solves(3, self.key, [make_solve()], directory=self.directory)
        fresh = make_solve(flag='+2')

        resolved = self.resolve_ok(self.key, [make_solve(date=1), fresh])

        self.assertIs(resolved.solve, fresh)
        self.assertEqual(resolved.label, '#2')

    def test_short_prefix_rejected(self) -> None:
        """A prefix too short to be discriminating is refused."""
        save_solves(3, self.key, [make_solve()], directory=self.directory)

        self.assertIsNone(self.resolve(self.key[:3], []))

    def test_unknown_key_rejected(self) -> None:
        """A key matching no stored scramble is an error."""
        save_solves(3, self.key, [make_solve()], directory=self.directory)

        self.assertIsNone(self.resolve('ffffffff', []))

    def test_ambiguous_prefix_rejected(self) -> None:
        """A prefix matching two scrambles resolves to nothing."""
        for suffix in ('aa', 'bb'):
            save_solves(
                3, f'abcd00000000{ suffix }', [make_solve()],
                directory=self.directory,
            )

        self.assertIsNone(self.resolve('abcd', []))

    def test_empty_scramble_file_rejected(self) -> None:
        """A key naming a file without attempts is an error."""
        save_solves(3, self.key, [], directory=self.directory)

        self.assertIsNone(self.resolve(self.key, []))


class TestBuildRaceStack(unittest.TestCase):
    """Tests for seeding the scramble history with the reference."""

    def test_empty_history_seeds_the_reference(self) -> None:
        """The first race starts on a stack holding the reference."""
        reference = make_solve()
        stack = ghost_mod.build_race_stack(reference, [], 'KEY')

        self.assertEqual(stack, [reference])
        self.assertEqual(reference.session, 'KEY')
        self.assertEqual(reference.solve_id, 1)

    def test_reference_comes_first(self) -> None:
        """The reference is the oldest attempt, numbered #1."""
        reference = make_solve(date=1)
        attempt = make_solve(date=2)
        stack = ghost_mod.build_race_stack(reference, [attempt], 'KEY')

        self.assertEqual([solve.date for solve in stack], [1, 2])
        self.assertEqual([solve.solve_id for solve in stack], [1, 2])

    def test_stored_reference_is_not_duplicated(self) -> None:
        """A reference already written back stays a single attempt."""
        reference = make_solve(date=1)
        stored = make_solve(date=1)
        attempt = make_solve(date=2)
        stack = ghost_mod.build_race_stack(
            reference, [stored, attempt], 'KEY',
        )

        self.assertEqual(len(stack), 2)
        self.assertIs(stack[0], reference)

    def test_stored_copy_never_shadows_the_reference(self) -> None:
        """A reference edited since it was stored races as edited."""
        reference = make_solve(date=1, flag='+2')
        stored = make_solve(date=1)
        stack = ghost_mod.build_race_stack(reference, [stored], 'KEY')

        self.assertIs(stack[0], reference)
        self.assertEqual(stack[0].flag, '+2')

    def test_attempts_are_sorted_by_date(self) -> None:
        """A history out of order is put back in chronological order."""
        reference = make_solve(date=1)
        stack = ghost_mod.build_race_stack(
            reference,
            [make_solve(date=3), make_solve(date=2)],
            'KEY',
        )

        self.assertEqual([solve.date for solve in stack], [1, 2, 3])


class TestSelectGhost(unittest.TestCase):
    """Tests for ghost selection over the race stack."""

    @staticmethod
    def parse(*args: str) -> Namespace:
        """
        Parse a ghost command line into options.

        Returns:
            The parsed namespace.

        """
        return get_parser().parse_args(['ghost', *args])

    def test_seeded_reference_is_the_first_ghost(self) -> None:
        """With no attempt yet the reference itself is the ghost."""
        options = self.parse('1')
        reference = make_solve()
        stack = ghost_mod.build_race_stack(reference, [], 'KEY')

        self.assertIs(ghost_mod.select_ghost(stack, options), reference)

    def test_pb_selected_over_the_stack(self) -> None:
        """The fastest solve wins, reference included."""
        options = self.parse('1')
        reference = make_solve(date=1, time=2_608_404_439)
        faster = make_solve(date=2, time=1_000_000_000)
        slower = make_solve(date=3, time=9_000_000_000)
        stack = ghost_mod.build_race_stack(
            reference, [slower, faster], 'KEY',
        )

        self.assertIs(ghost_mod.select_ghost(stack, options), faster)

    def test_dnf_attempt_ignored(self) -> None:
        """A DNF attempt never becomes the ghost even if faster."""
        options = self.parse('1')
        reference = make_solve(date=1, time=2_608_404_439)
        dnf = make_solve(date=2, time=1, flag='DNF')
        stack = ghost_mod.build_race_stack(reference, [dnf], 'KEY')

        self.assertIs(ghost_mod.select_ghost(stack, options), reference)

    def test_plus_two_races_with_its_penalty(self) -> None:
        """A +2 is elected on its official time, penalty included."""
        options = self.parse('1')
        reference = make_solve(date=1, time=2_608_404_439)
        penalised = make_solve(date=2, time=1_000_000_000, flag='+2')
        stack = ghost_mod.build_race_stack(reference, [penalised], 'KEY')

        self.assertIs(ghost_mod.select_ghost(stack, options), reference)

    def test_keyboard_attempt_can_become_the_ghost(self) -> None:
        """An attempt timed without a cube still moves the target."""
        options = self.parse('1')
        reference = make_solve(date=1, time=2_608_404_439)
        manual = make_solve(date=2, time=1_000_000_000, moves=None)
        stack = ghost_mod.build_race_stack(reference, [manual], 'KEY')

        self.assertIs(ghost_mod.select_ghost(stack, options), manual)


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

    def summarize(self, pool: list[Solve]) -> tuple[int, str]:
        """
        Run the summary against a controlled solve pool.

        Returns:
            The exit code and the rendered output.

        """
        recorder = RichConsole(
            record=True, width=120, theme=Theme(console_theme),
        )
        with (
                patch.object(ghost_mod, 'console', recorder),
                patch.object(
                    ghost_mod, 'load_all_solves', return_value=pool,
                ),
        ):
            code = ghost_mod.ghost_summary(self.parse())

        return code, recorder.export_text()

    def test_summary_empty(self) -> None:
        """An empty library reports nothing recorded."""
        code, _output = self.summarize([])
        self.assertEqual(code, 1)

    def test_summary_lists_scrambles(self) -> None:
        """The summary lists a row per recorded scramble."""
        key = scramble_to_key(SHORT_SCRAMBLE)
        save_solves(3, key, [make_solve()], directory=self.directory)

        code, output = self.summarize([])

        self.assertEqual(code, 0)
        self.assertIn(SHORT_SCRAMBLE, output)

    def test_summary_names_the_reference_id(self) -> None:
        """A ghost is labelled by the id of the solve that seeded it."""
        key = scramble_to_key(SHORT_SCRAMBLE)
        save_solves(3, key, [make_solve()], directory=self.directory)

        _code, output = self.summarize(
            [make_solve(date=1), make_solve(), make_solve(date=3)],
        )

        self.assertIn('#2', output)

    def test_summary_shows_the_scramble_key(self) -> None:
        """Each row carries the permanent key of its scramble."""
        key = scramble_to_key(SHORT_SCRAMBLE)
        save_solves(3, key, [make_solve()], directory=self.directory)

        _code, output = self.summarize([])

        self.assertIn(key[:8], output)

    def test_summary_without_matching_reference(self) -> None:
        """A ghost whose seed is out of the pool shows no id."""
        key = scramble_to_key(SHORT_SCRAMBLE)
        save_solves(3, key, [make_solve()], directory=self.directory)

        _code, output = self.summarize([make_solve(date=1)])

        self.assertIn('—', output)
        self.assertNotIn('#', output)

    def test_summary_best_counts_keyboard_attempts(self) -> None:
        """An attempt without reconstruction can hold the best time."""
        key = scramble_to_key(SHORT_SCRAMBLE)
        save_solves(
            3, key,
            [
                make_solve(date=1),
                make_solve(date=2, time=1_000_000_000, moves=None),
            ],
            directory=self.directory,
        )

        _code, output = self.summarize([])

        self.assertIn('00:01.000', output)
        self.assertNotIn('00:02.608', output)

    def test_summary_best_uses_the_official_time(self) -> None:
        """A +2 is ranked with the two seconds it costs."""
        key = scramble_to_key(SHORT_SCRAMBLE)
        save_solves(
            3, key,
            [
                make_solve(date=1),
                make_solve(date=2, time=1_000_000_000, flag='+2'),
            ],
            directory=self.directory,
        )

        _code, output = self.summarize([])

        self.assertIn('00:02.608', output)
        self.assertNotIn('00:01.000', output)

    def test_summary_of_a_scramble_never_solved(self) -> None:
        """A scramble whose attempts are all DNF has no best time."""
        key = scramble_to_key(SHORT_SCRAMBLE)
        save_solves(
            3, key,
            [make_solve(flag='DNF')],
            directory=self.directory,
        )

        code, output = self.summarize([])

        self.assertEqual(code, 0)
        self.assertIn('DNF', output)

    def test_summary_orders_by_best_time(self) -> None:
        """The fastest scramble opens the library, the DNF one closes it."""
        other = "R U R' U'"
        never = "F R F' R'"
        for scramble, solve in (
                (SHORT_SCRAMBLE, make_solve()),
                (other, make_solve(
                    scramble=other, time=1_000_000_000, moves=None,
                )),
                (never, make_solve(
                    scramble=never, moves=None, flag='DNF',
                )),
        ):
            save_solves(
                3, scramble_to_key(scramble), [solve],
                directory=self.directory,
            )

        _code, output = self.summarize([])

        self.assertLess(
            output.index('00:01.000'), output.index('00:02.608'),
        )
        self.assertLess(output.index('00:02.608'), output.index('DNF'))

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
    def build_instance(ghost_solve: Solve, stack: list[Solve]) -> Namespace:
        """
        Build a timer stand-in carrying a ghost and a race stack.

        Returns:
            The stand-in instance.

        """
        return Namespace(ghost=ghost_solve, stack=stack)

    def test_new_best_becomes_the_ghost(self) -> None:
        """Beating the ghost promotes the fresh attempt for the next race."""
        options = self.parse('1')
        reference = make_solve(date=1, time=2_608_404_439)
        faster = make_solve(date=2, time=1_000_000_000)
        instance = self.build_instance(reference, [reference, faster])

        ghost_mod.refresh_ghost(instance, options)  # type: ignore[arg-type]

        self.assertIs(instance.ghost, faster)

    def test_slower_attempt_keeps_the_ghost(self) -> None:
        """A slower attempt leaves the target untouched."""
        options = self.parse('1')
        reference = make_solve(date=1, time=2_608_404_439)
        slower = make_solve(date=2, time=9_000_000_000)
        instance = self.build_instance(reference, [reference, slower])

        ghost_mod.refresh_ghost(instance, options)  # type: ignore[arg-type]

        self.assertIs(instance.ghost, reference)

    def test_history_stays_in_the_pool(self) -> None:
        """A stored attempt still wins over a slower session solve."""
        options = self.parse('1')
        reference = make_solve(date=1, time=2_608_404_439)
        stored = make_solve(date=2, time=1_000_000_000)
        attempt = make_solve(date=3, time=2_000_000_000)
        instance = self.build_instance(
            reference, [reference, stored, attempt],
        )

        ghost_mod.refresh_ghost(instance, options)  # type: ignore[arg-type]

        self.assertIs(instance.ghost, stored)
