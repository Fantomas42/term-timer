"""Tests for timer."""
import asyncio
import unittest
from random import Random
from unittest.mock import MagicMock
from unittest.mock import patch

from cubing_algs.algorithm import Algorithm
from cubing_algs.parsing import parse_moves

from term_timer.solve import Solve
from term_timer.stats import SolveStatisticsReporter
from term_timer.tests.test_ghost import make_solve
from term_timer.timer import Timer

SECOND = 1_000_000_000


def build_timer(
        stack: list[Solve] | None = None,
        *,
        scramble: str = '',
        scrambles: list[Algorithm] | None = None,
) -> Timer:
    """
    Build a Timer instance with minimal configuration for tests.

    Returns:
        A free-play Timer ready for display tests.

    """
    return Timer(
        cube_size=3,
        iterations=0,
        easy_cross=False,
        x_cross=False,
        edges_oriented=False,
        scramble=scramble,
        scrambles=scrambles or [],
        session='default',
        free_play=True,
        show_cube=False,
        show_highlights=False,
        show_doctor=False,
        show_reconstruction=False,
        show_time_graph=False,
        show_tps_graph=False,
        show_fluency_graph=False,
        show_recognition_graph=False,
        show_steps=False,
        countdown=0,
        metronome=0,
        orientation='DF',
        method='raw',
        stack=stack or [],
        rng=Random(),  # noqa: S311
    )


class TestTimerModule(unittest.TestCase):
    """Tests for Timer class."""

    def test_initialization(self) -> None:
        """Test that Timer initializes with all required attributes."""
        timer = Timer(
            cube_size=3,
            iterations=0,
            easy_cross=False,
            x_cross=False,
            edges_oriented=False,
            scramble='',
            scrambles=[],
            session='default',
            free_play=True,
            show_cube=False,
            show_highlights=True,
            show_doctor=True,
            show_reconstruction=False,
            show_time_graph=False,
            show_tps_graph=False,
            show_fluency_graph=False,
            show_recognition_graph=False,
            show_steps=False,
            countdown=0,
            metronome=0,
            orientation='DF',
            method='raw',
            stack=[],
            rng=Random(),  # noqa: S311
        )

        for key in (
                'moves',
                'bluetooth_queue',
                'bluetooth_cube',
                'bluetooth_interface',
                'bluetooth_consumer_ref',
                'bluetooth_hardware',
                'facelets_received_event',
                'hardware_received_event',
                'console',
                'cube_orientation_moves',
                'save_moves',
                'save_gesture',
                'save_gesture_event',
                'countdown',
                'inspection_completed_event',
                'scramble',
                'scrambled',
                'scramble_oriented',
                'counter',
                'facelets_scrambled',
                'scramble_completed_event',
                'state',
                'start_time',
                'end_time',
                'elapsed_time',
                'metronome',
                'solve_started_event',
                'solve_completed_event',
                'orientation_faces',
                'rng',
        ):
            self.assertTrue(hasattr(timer, key))


class TestProjectionLine(unittest.TestCase):
    """Tests for the next-solve average projection display."""

    @staticmethod
    def stats(seconds: list[float]) -> SolveStatisticsReporter:
        """
        Build a statistics reporter from a list of times in seconds.

        Returns:
            A reporter over the given solve times.

        """
        stack = [
            Solve(0, int(s * SECOND), '', cube_size=3)
            for s in seconds
        ]
        return SolveStatisticsReporter(3, stack)

    @staticmethod
    def render(stats: SolveStatisticsReporter) -> str:
        """
        Capture the console output of projection_line.

        Returns:
            The rendered projection text.

        """
        timer = build_timer()
        with timer.console.capture() as capture:
            timer.projection_line(stats)
        return capture.get()

    def test_disabled_when_no_projections(self) -> None:
        """No output is produced when STATS_AO_PROJECTIONS is empty."""
        stats = self.stats([12, 13, 11.5, 14, 12.5])
        with patch('term_timer.timer.STATS_AO_PROJECTIONS', []):
            self.assertEqual(self.render(stats), '')

    def test_shows_range_and_target(self) -> None:
        """A full window shows the BPA/WPA range and a reachable PB."""
        stats = self.stats([12, 13, 11.5, 14, 11])
        with patch('term_timer.timer.STATS_AO_PROJECTIONS', [5]):
            output = self.render(stats)
        self.assertIn('Estimate #2', output)
        self.assertIn('Ao5', output)
        self.assertIn('-', output)
        self.assertIn('PB', output)

    def test_preview_before_full_window_has_no_target(self) -> None:
        """One solve short of a window shows the range but no PB target."""
        stats = self.stats([12, 13, 11.5, 14])
        with patch('term_timer.timer.STATS_AO_PROJECTIONS', [5]):
            output = self.render(stats)
        self.assertIn('Ao5', output)
        self.assertNotIn('PB', output)

    def test_skips_average_without_enough_solves(self) -> None:
        """An average needing more solves than available is omitted."""
        stats = self.stats([12, 13, 11.5, 14, 12.5])
        with patch('term_timer.timer.STATS_AO_PROJECTIONS', [12]):
            self.assertEqual(self.render(stats), '')


class TestElectGhost(unittest.TestCase):
    """Tests for the ghost election over the timer stack."""

    def test_empty_stack_has_no_ghost(self) -> None:
        """An empty pool leaves the session ghostless instead of raising."""
        timer = build_timer([])

        timer.elect_ghost()

        self.assertIsNone(timer.ghost)

    def test_lone_solve_becomes_the_ghost(self) -> None:
        """A stack holding a single timed solve races it."""
        solve = make_solve()
        timer = build_timer([solve])

        timer.elect_ghost()

        self.assertIs(timer.ghost, solve)

    def test_fastest_solve_wins(self) -> None:
        """The fastest solve of the stack is the target."""
        faster = make_solve(date=2, time=1_000_000_000)
        slower = make_solve(date=3, time=9_000_000_000)
        timer = build_timer([slower, faster])

        timer.elect_ghost()

        self.assertIs(timer.ghost, faster)

    def test_dnf_never_becomes_the_ghost(self) -> None:
        """A DNF is out of the pool even when faster."""
        slower = make_solve(date=1, time=2_608_404_439)
        dnf = make_solve(date=2, time=1, flag='DNF')
        timer = build_timer([dnf, slower])

        timer.elect_ghost()

        self.assertIs(timer.ghost, slower)

    def test_all_dnf_stack_has_no_ghost(self) -> None:
        """A stack without a single official time races ghostless."""
        timer = build_timer(
            [
                make_solve(date=1, time=2_608_404_439, flag='DNF'),
                make_solve(date=2, time=1_000_000_000, flag='DNF'),
            ],
        )

        timer.elect_ghost()

        self.assertIsNone(timer.ghost)

    def test_plus_two_races_with_its_penalty(self) -> None:
        """A +2 is elected on its official time, penalty included."""
        clean = make_solve(date=1, time=2_608_404_439)
        penalised = make_solve(date=2, time=1_000_000_000, flag='+2')
        timer = build_timer([penalised, clean])

        timer.elect_ghost()

        self.assertIs(timer.ghost, clean)

    def test_keyboard_attempt_can_become_the_ghost(self) -> None:
        """An attempt timed without a cube still moves the target."""
        reference = make_solve(date=1, time=2_608_404_439)
        manual = make_solve(date=2, time=1_000_000_000, moves=None)
        timer = build_timer([reference, manual])

        timer.elect_ghost()

        self.assertIs(timer.ghost, manual)

    def test_ghost_follows_the_session_analysis(self) -> None:
        """The elected ghost is analysed as the session is."""
        solve = make_solve(method='cfop')
        timer = build_timer([solve])

        timer.elect_ghost()

        self.assertEqual(solve.method_name, timer.method)
        self.assertEqual(solve.orientation, timer.orientation_faces)

    def test_new_best_takes_over_the_ghost(self) -> None:
        """Beating the ghost promotes the fresh attempt for the next race."""
        stored = make_solve(date=1, time=2_608_404_439)
        timer = build_timer([stored])
        timer.elect_ghost()

        faster = make_solve(date=2, time=1_000_000_000)
        timer.stack = [*timer.stack, faster]
        timer.elect_ghost()

        self.assertIs(timer.ghost, faster)

    def test_slower_attempt_keeps_the_ghost(self) -> None:
        """A slower attempt leaves the target untouched."""
        stored = make_solve(date=1, time=2_608_404_439)
        timer = build_timer([stored])
        timer.elect_ghost()

        slower = make_solve(date=2, time=9_000_000_000)
        timer.stack = [*timer.stack, slower]
        timer.elect_ghost()

        self.assertIs(timer.ghost, stored)


class TestSaveSolveRetry(unittest.IsolatedAsyncioTestCase):
    """save_solve() treats 'r' as a discard that asks for a replay."""

    async def run_save(self, char: str, *, scramble: str = '') -> Timer:
        """
        Run save_solve with a fixed key on a timer holding one solve.

        Returns:
            The timer after save_solve has returned.

        """
        solve = make_solve()
        timer = build_timer([solve], scramble=scramble)
        timer.stack_done = [solve]
        timer.console = MagicMock()
        self.counter_start = timer.counter

        async def fake_getch(_mode: str, *_: object) -> str:
            await asyncio.sleep(0)
            return char

        with (
            patch('term_timer.interface.save_solves'),
            patch('term_timer.interface.SOUND_PLAYER'),
            patch.object(timer, 'getch', side_effect=fake_getch),
        ):
            self.quit_flag = await timer.save_solve()

        return timer

    async def test_retry_key_pops_the_solve_and_asks_for_replay(self) -> None:
        """'r' drops the solve like 'z' and flags the replay."""
        timer = await self.run_save('r')

        self.assertFalse(self.quit_flag)
        self.assertEqual(timer.stack, [])
        self.assertEqual(timer.stack_done, [])
        self.assertTrue(timer.retry_requested)

    async def test_retry_key_is_not_a_save(self) -> None:
        """'r' is never swallowed as an unrecognised key keeping the solve."""
        timer = await self.run_save('r')

        self.assertEqual(timer.counter, self.counter_start)

    async def test_discard_key_does_not_ask_for_replay(self) -> None:
        """'z' discards without flagging any replay."""
        timer = await self.run_save('z')

        self.assertEqual(timer.stack, [])
        self.assertFalse(timer.retry_requested)
        self.assertEqual(timer.counter, self.counter_start)

    async def test_save_key_keeps_the_solve(self) -> None:
        """Any other key saves, counts the solve and asks for no replay."""
        timer = await self.run_save('')

        self.assertEqual(len(timer.stack), 1)
        self.assertFalse(timer.retry_requested)
        self.assertEqual(timer.counter, self.counter_start + 1)

    async def test_retry_key_saves_on_an_imposed_scramble(self) -> None:
        """Where the retry is disabled, 'r' saves like any other key."""
        timer = await self.run_save('r', scramble="R U R' U'")

        self.assertEqual(len(timer.stack), 1)
        self.assertEqual(len(timer.stack_done), 1)
        self.assertFalse(timer.retry_requested)
        self.assertEqual(timer.counter, self.counter_start + 1)


class TestRetryEnabled(unittest.TestCase):
    """The retry is offered only when the next scramble would differ."""

    def test_random_scramble_enables_the_retry(self) -> None:
        """A drawn scramble differs on every attempt, so a retry helps."""
        timer = build_timer()

        self.assertTrue(timer.retry_enabled)

    def test_imposed_scramble_disables_the_retry(self) -> None:
        """An imposed scramble is already replayed by the next attempt."""
        timer = build_timer(scramble="R U R' U'")

        self.assertFalse(timer.retry_enabled)

    def test_scramble_list_enables_the_retry(self) -> None:
        """A list moves on after a discard, so a retry stays meaningful."""
        timer = build_timer(
            scramble="R U R' U'",
            scrambles=[parse_moves("F R U R' U' F'")],
        )

        self.assertTrue(timer.retry_enabled)


class TestSaveLine(unittest.TestCase):
    """The save prompt advertises the retry only when it is available."""

    @staticmethod
    def render(*, scramble: str = '', bluetooth: bool = False) -> str:
        """
        Capture the console output of save_line.

        Returns:
            The rendered prompt text.

        """
        timer = build_timer(scramble=scramble)
        if bluetooth:
            timer.bluetooth_interface = MagicMock()
        with timer.console.capture() as capture:
            timer.save_line()
        return capture.get()

    def test_retry_key_is_offered(self) -> None:
        """A drawn scramble shows the retry next to the discard."""
        output = self.render()

        self.assertIn('(r)', output)
        self.assertIn('(z)', output)

    def test_retry_key_is_hidden_on_an_imposed_scramble(self) -> None:
        """An imposed scramble drops the retry but keeps the discard."""
        output = self.render(scramble="R U R' U'")

        self.assertNotIn('(r)', output)
        self.assertIn('(z)', output)

    def test_manual_flag_keys_are_kept(self) -> None:
        """Without a Bluetooth cube the DNF and +2 keys stay offered."""
        output = self.render()

        self.assertIn('(d)', output)
        self.assertIn('(2)', output)

    def test_flag_keys_are_dropped_with_a_cube(self) -> None:
        """A connected cube reads the flag itself, the keys are inactive."""
        output = self.render(bluetooth=True)

        self.assertNotIn('(d)', output)
        self.assertNotIn('(2)', output)

    def test_help_key_is_always_offered(self) -> None:
        """The prompt names no command but points at the ones it hides."""
        for output in (
                self.render(),
                self.render(bluetooth=True),
                self.render(scramble="R U R' U'"),
        ):
            self.assertIn('(?)', output)

    def test_prompt_holds_on_a_single_line(self) -> None:
        """
        The prompt never wraps, whatever it offers.

        `clear_line` wipes one physical line: an enrolled prompt would
        leave its first row on screen for the rest of the session.
        """
        for output in (
                self.render(),
                self.render(bluetooth=True),
                self.render(scramble="R U R' U'"),
        ):
            self.assertNotIn('\n', output)


class TestCommandsHelp(unittest.TestCase):
    """The help block names every command, cube gestures included."""

    @staticmethod
    def unfold(*, bluetooth: bool = False) -> tuple[list[str], str]:
        """
        Capture the help block unfolded for the current save prompt.

        Returns:
            The commands offered by the prompt, and the rendered help.

        """
        timer = build_timer()
        if bluetooth:
            timer.bluetooth_interface = MagicMock()

        with timer.console.capture():
            timer.save_line()

        tokens = timer.save_commands[2]

        with timer.console.capture() as capture:
            timer.commands_help(tokens)

        return tokens, capture.get()

    def render(self, *, bluetooth: bool = False) -> str:
        """
        Capture the help block unfolded for the current save prompt.

        Returns:
            The rendered help text.

        """
        return self.unfold(bluetooth=bluetooth)[1]

    def test_keyboard_commands_are_named(self) -> None:
        """Every key of the prompt gets its meaning spelled out."""
        output = self.render()

        for label in ('Save', 'Retry', 'Discard', 'Quit', 'Save & quit'):
            self.assertIn(label, output)

    def test_cube_column_is_hidden_without_a_cube(self) -> None:
        """Gestures are unreachable without a cube, so they stay unsaid."""
        output = self.render()

        self.assertNotIn('Cube', output)
        self.assertNotIn("U U'", output)

    def test_cube_gestures_are_cancelled_pairs(self) -> None:
        """A gesture is a face undone, never the same move played twice."""
        output = self.render(bluetooth=True)

        self.assertIn('Cube', output)
        for gesture in ('U', 'M', 'E', 'D'):
            self.assertIn(gesture, output)

    def test_flag_rows_follow_the_flag_keys(self) -> None:
        """The DNF and +2 rows show up exactly where their keys are."""
        output = self.render()
        self.assertIn('DNF', output)
        self.assertIn('+2', output)

        cubed = self.render(bluetooth=True)
        self.assertNotIn('DNF', cubed)
        self.assertNotIn('+2', cubed)

    def test_no_command_prints_nothing(self) -> None:
        """An empty prompt has no table to unfold, not an empty one."""
        timer = build_timer()

        with timer.console.capture() as capture:
            timer.commands_help([])

        self.assertEqual(capture.get(), '')

    def test_every_row_holds_on_a_single_line(self) -> None:
        """The block is a table: a wrapped row would break its columns."""
        for bluetooth in (False, True):
            with self.subTest(bluetooth=bluetooth):
                tokens, output = self.unfold(bluetooth=bluetooth)

                # Header, one row per command, and the gesture note
                # the cube column comes with.
                expected = 1 + len(tokens) + int(bluetooth)

                self.assertEqual(len(output.splitlines()), expected)


class TestSaveHelpKey(unittest.IsolatedAsyncioTestCase):
    """The help key unfolds the commands instead of deciding the solve."""

    async def run_save(self, chars: list[str]) -> Timer:
        """
        Run save_solve against a sequence of pressed keys.

        Returns:
            The timer after save_solve has returned.

        """
        solve = make_solve()
        timer = build_timer([solve])
        timer.stack_done = [solve]
        timer.console = MagicMock()
        timer.save_line()
        self.counter_start = timer.counter

        pressed = iter(chars)

        async def fake_getch(_mode: str, *_: object) -> str:
            await asyncio.sleep(0)
            return next(pressed)

        with (
            patch('term_timer.interface.save_solves'),
            patch('term_timer.interface.SOUND_PLAYER'),
            patch.object(timer, 'getch', side_effect=fake_getch),
        ):
            await timer.save_solve()

        return timer

    @staticmethod
    def printed(timer: Timer) -> list[str]:
        """
        Collect the strings the timer printed.

        Returns:
            The first positional argument of every console print.

        """
        return [
            call.args[0]
            for call in timer.console.print.call_args_list  # type: ignore[attr-defined]
            if call.args and isinstance(call.args[0], str)
        ]

    async def test_help_key_does_not_save(self) -> None:
        """The solve is still waiting once the commands have been read."""
        timer = await self.run_save(['?', 'z'])

        self.assertEqual(timer.stack, [])
        self.assertEqual(timer.counter, self.counter_start)

    async def test_help_key_unfolds_the_commands(self) -> None:
        """The block naming every command is printed once."""
        timer = await self.run_save(['?', ''])

        headers = [line for line in self.printed(timer) if 'Commands #' in line]
        self.assertEqual(len(headers), 1)

    async def test_help_key_asks_again(self) -> None:
        """The prompt comes back under the block it just unfolded."""
        timer = await self.run_save(['?', ''])

        prompts = [line for line in self.printed(timer) if 'Save #' in line]
        self.assertEqual(len(prompts), 2)


class TestRunAttemptPendingScramble(unittest.IsolatedAsyncioTestCase):
    """run_attempt() replays the pending scramble instead of drawing one."""

    @staticmethod
    async def drive_to_scramble(
            pending: Algorithm | None,
            scrambles: list[Algorithm],
    ) -> Timer:
        """
        Drive one attempt up to the scramble phase, then quit there.

        Returns:
            The timer once the attempt has returned on the quit.

        """
        timer = build_timer()
        timer.scrambles = scrambles
        timer.console = MagicMock()

        async def quit_scrambling() -> bool:
            await asyncio.sleep(0)
            return False

        with patch.object(
                timer, 'scramble_solve', side_effect=quit_scrambling,
        ):
            await timer.run_attempt(pending)

        return timer

    async def test_pending_scramble_is_replayed(self) -> None:
        """The pending scramble is used as is, ignoring the pool."""
        pending = parse_moves("R U R' U'")
        listed = parse_moves("F R U R' U' F'")

        timer = await self.drive_to_scramble(pending, [listed])

        self.assertEqual(str(timer.scramble), str(pending))

    async def test_pending_scramble_does_not_consume_the_list(self) -> None:
        """A replay leaves the --scrambles list where it was."""
        pending = parse_moves("R U R' U'")
        listed = parse_moves("F R U R' U' F'")

        timer = await self.drive_to_scramble(pending, [listed])

        self.assertEqual(timer.scramble_index, 0)

    async def test_without_pending_the_list_is_consumed(self) -> None:
        """A fresh attempt draws the next scramble of the list."""
        listed = parse_moves("F R U R' U' F'")

        timer = await self.drive_to_scramble(None, [listed])

        self.assertEqual(str(timer.scramble), str(listed))
        self.assertEqual(timer.scramble_index, 1)


class TestStartRetryLoop(unittest.IsolatedAsyncioTestCase):
    """start() replays the scramble for as long as a retry is asked for."""

    @staticmethod
    async def run_start(
            outcomes: list[tuple[bool, Algorithm | None]],
    ) -> tuple[bool, list[Algorithm | None]]:
        """
        Run start() over a scripted sequence of run_attempt() outcomes.

        Returns:
            Tuple of (start() return value, scrambles passed to
            run_attempt).

        """
        timer = build_timer()
        received: list[Algorithm | None] = []
        remaining = list(outcomes)

        async def fake_run_attempt(
                pending: Algorithm | None = None,
        ) -> tuple[bool, Algorithm | None]:
            await asyncio.sleep(0)
            received.append(pending)
            return remaining.pop(0)

        with patch.object(timer, 'run_attempt', side_effect=fake_run_attempt):
            keep_going = await timer.start()

        return keep_going, received

    async def test_single_attempt_returns_immediately(self) -> None:
        """Without any retry, start() runs a single attempt."""
        keep_going, received = await self.run_start([(True, None)])

        self.assertTrue(keep_going)
        self.assertEqual(received, [None])

    async def test_retry_replays_the_same_scramble(self) -> None:
        """A retry feeds the pending scramble back into run_attempt()."""
        scramble = parse_moves("R U R' U'")

        keep_going, received = await self.run_start(
            [(True, scramble), (True, None)],
        )

        self.assertTrue(keep_going)
        self.assertEqual(received, [None, scramble])

    async def test_retries_are_not_limited(self) -> None:
        """Consecutive retries all replay before start() returns once."""
        scramble = parse_moves("R U R' U'")

        keep_going, received = await self.run_start(
            [
                (True, scramble), (True, scramble),
                (True, scramble), (True, None),
            ],
        )

        self.assertTrue(keep_going)
        self.assertEqual(len(received), 4)
        self.assertEqual(received[1:], [scramble, scramble, scramble])

    async def test_quit_after_retry_is_propagated(self) -> None:
        """Quitting the replayed attempt still quits the session."""
        scramble = parse_moves("R U R' U'")

        keep_going, received = await self.run_start(
            [(True, scramble), (False, None)],
        )

        self.assertFalse(keep_going)
        self.assertEqual(len(received), 2)
