"""Timer interface for recording and analyzing cube solves."""
import logging
import operator
from random import Random
from typing import Any

from cubing_algs.algorithm import Algorithm
from cubing_algs.annotations import CubeOrientation
from cubing_algs.solver import facelets_to_facelets_algorithm
from cubing_algs.vcube import VCube

from term_timer.config import STATS_AO_PROJECTIONS
from term_timer.config import STATS_LIVE_SERIES
from term_timer.config import STATS_SESSION_SERIES
from term_timer.constants import DNF
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import SolveFlag
from term_timer.formatter import format_time
from term_timer.interface import SolveInterface
from term_timer.interface.sounds import SOUND_PLAYER
from term_timer.printer import print_cube_scrambled
from term_timer.publisher import PUBLISHER
from term_timer.publisher import SCRAMBLE_TOPIC
from term_timer.publisher import SOLVE_TOPIC
from term_timer.scrambler import scrambler
from term_timer.solve import Solve
from term_timer.stats import TARGET_ALWAYS
from term_timer.stats import SolveStatisticsReporter

logger = logging.getLogger(__name__)


class Timer(SolveInterface):
    """
    Main timer interface for recording and analyzing cube solves.

    Manages the complete solve workflow including scrambling, timing,
    recording moves, and displaying statistics.
    """

    def __init__(  # noqa: PLR0913
            self, *,
            cube_size: int,
            iterations: int,
            easy_cross: bool,
            x_cross: bool,
            edges_oriented: bool,
            scramble: str,
            scrambles: list[Algorithm],
            session: str,
            free_play: bool,
            show_highlights: bool,
            show_doctor: bool,
            show_cube: bool,
            show_reconstruction: bool,
            show_tps_graph: bool,
            show_time_graph: bool,
            show_fluency_graph: bool,
            show_recognition_graph: bool,
            show_steps: bool,
            method: str,
            orientation: CubeOrientation,
            countdown: int,
            metronome: float,
            stack: list[Solve],
            counter_start: int | None = None,
            rng: Random) -> None:
        """Initialize timer with configuration and existing solve stack."""
        super().__init__()

        self.set_state('configure')

        self.cube_size = cube_size
        self.session = session
        self.free_play = free_play
        self.iterations = iterations
        self.easy_cross = easy_cross
        self.x_cross = x_cross
        self.edges_oriented = edges_oriented
        self.raw_scramble = scramble
        self.scrambles = scrambles
        self.scramble_index = 0
        # A retry only differs from a discard when the next attempt would
        # draw another scramble: an imposed one is already replayed.
        self.retry_enabled = bool(scrambles) or not scramble
        self.show_highlights = show_highlights
        self.show_doctor = show_doctor
        self.show_cube = show_cube
        self.show_reconstruction = show_reconstruction
        self.show_tps_graph = show_tps_graph
        self.show_time_graph = show_time_graph
        self.show_fluency_graph = show_fluency_graph
        self.show_recognition_graph = show_recognition_graph
        self.show_steps = show_steps
        self.method = method
        self.orientation_faces = orientation
        self.countdown = countdown
        self.metronome = metronome
        self.stack = stack
        self.stack_done: list[Solve] = []
        self.rng = rng

        self.counter = (
            counter_start if counter_start is not None
            else len(stack)
        ) + 1

        if self.free_play:
            self.console.print(
                '🔒 Mode Free Play is active, '
                'solves will not be recorded !',
                style='warning',
            )

    def elect_ghost(self) -> None:
        """
        Elect the ghost to beat: the fastest solve of the stack.

        The pool is the timer stack, which holds the solves seeding the
        session plus the attempts raced since it started, so beating the
        ghost immediately promotes the fresh solve as the target of the
        next race. Free play never writes to the session file but its
        attempts still count for the pool.

        Every attempt is eligible, timed on the cube or on the keyboard,
        so a session raced without a connected cube still moves its
        target; a keyboard ghost simply carries no reconstruction, hence
        no checkpoint splits. Times are compared on ``final_time``: a DNF
        has none, and a +2 races with the two seconds it costs. The
        elected ghost is analysed with the session method and orientation
        to align its splits with the live checkpoints.

        A stack without a single timed attempt leaves the session without
        a ghost, which the stopwatch already handles.
        """
        candidates = [solve for solve in self.stack if solve.final_time]
        if not candidates:
            self.ghost = None
            return

        ghost = min(candidates, key=operator.attrgetter('final_time'))
        ghost.method_name = self.method
        ghost.orientation = self.orientation_faces

        self.ghost = ghost

    def publish_scramble(self) -> None:
        """
        Publish the scramble the attempt about to start is solving.

        Emitted once the scramble is drawn and reoriented, so that a
        subscriber reads the very moves the solver is shown, and the
        state the cube must reach.
        """
        if not PUBLISHER.active:
            return

        PUBLISHER.publish(
            SCRAMBLE_TOPIC,
            {
                'scramble': str(self.scramble),
                'oriented': str(self.scramble_oriented),
                'rotation': str(self.cube_orientation_moves),
                'facelets': self.facelets_scrambled,
                'cube_size': self.cube_size,
                'index': self.counter,
                'total': len(self.scrambles),
            },
        )

    @staticmethod
    def solve_steps(solve: Solve) -> list[dict[str, Any]]:
        """
        Break a solve down into the steps of its method.

        A DNF never reaches the solved state, so its breakdown is partial
        or wrong: it carries no steps at all rather than misleading ones.

        Args:
            solve: The solve that just ended.

        Returns:
            One object per step of the method analysis, empty when the
            solve carries no usable reconstruction.

        """
        if not solve.analysable or solve.method_applied is None:
            return []

        return [
            {
                'name': step['name'],
                'type': step['type'],
                'moves': str(step['moves_prettified']),
                'case': step['case'],
                'qtm': step['qtm'],
                'total': step['total'],
                'recognition': step['recognition'],
                'execution': step['execution'],
            }
            for step in solve.method_applied.summary
        ]

    def publish_solve(self, solve: Solve, counter: int) -> None:
        """
        Publish the solve that just ended, in its storage spelling.

        The payload is the one written to the session file, so a client
        writing down what it receives records a readable session, plus
        what only the running session knows: where the attempt sits, the
        method breakdown, and whether it counts.

        Called once the attempt is settled and kept, never before: the
        save prompt is where a manual solve is flagged DNF or +2, and
        where a discarded or retried one leaves the stack. A solve
        published any earlier would announce a flag it does not end up
        with, or an attempt that never happened.

        The breakdown is built only when someone listens: analysing a
        solve nobody displays is work a silent session must not pay for.

        Args:
            solve: The solve that just ended.
            counter: Rank of the attempt in the session, the one it was
                scrambled and timed under.

        """
        if not PUBLISHER.active:
            return

        data: dict[str, Any] = {**solve.as_save}
        data['dnf'] = solve.flag == DNF
        data['counter'] = counter
        data['session'] = self.session
        data['cube_size'] = self.cube_size
        data['free_play'] = self.free_play
        data['steps'] = self.solve_steps(solve)

        PUBLISHER.publish(SOLVE_TOPIC, data)

    def publish_settled_solve(self, solve: Solve, counter: int) -> None:
        """
        Publish the attempt once its fate is settled.

        The save prompt is where a manual solve is flagged DNF or +2,
        and where a discarded or retried one leaves the stack: an
        attempt no longer on it never happened, and one still there is
        published with the flag it ends up with. Free play holds no
        prompt, so its attempts are settled the moment they are timed.

        Args:
            solve: The attempt the save prompt just settled.
            counter: Rank of the attempt in the session, taken before
                the prompt: a saved attempt moves the counter on, and
                the one being published is not the next one.

        """
        if self.stack and self.stack[-1] is solve:
            self.publish_solve(solve, counter)

    def start_line(self, cube: VCube) -> None:
        """Display scramble information and instructions to start solve."""
        if self.show_cube:
            print_cube_scrambled(cube, self.orientation_faces, self.scramble)

        scramble_line = f'[scramble]Scramble #{ self.counter }:[/scramble] '
        if self.cube_orientation_moves:
            scramble_line += (
                f'[rotation]{ self.cube_orientation_moves }[/rotation] '
            )
        scramble_line += f'[moves]{ self.scramble_oriented }[/moves]'

        self.console.print(scramble_line)

        if self.bluetooth_interface:
            if self.countdown:
                self.console.print(
                    'Apply the scramble on the cube to start the inspection or',
                    '[[key]q[/key]] to quit.',
                    style='consign',
                    end='',
                )
            else:
                self.console.print(
                    'Apply the scramble on the cube to init the timer or',
                    '[[key]q[/key]] to quit.',
                    style='consign',
                    end='',
                )
        elif self.countdown:
            self.console.print(
                'Press any key once scrambled to start the inspection or',
                '[[key]q[/key]] to quit.',
                style='consign',
                end='',
            )
        else:
            self.console.print(
                'Press any key once scrambled to start/stop the timer or',
                '[[key]q[/key]] to quit.',
                style='consign',
                end='',
            )

    def save_line(self) -> None:
        """Display instructions for saving or canceling the solve."""
        tokens: list[str] = []

        if not self.bluetooth_interface:
            # The flag is read from the cube state when there is one,
            # so these keys only exist on a manual solve.
            tokens.extend(('dnf', 'plus_two'))

        if self.retry_enabled:
            tokens.append('retry')

        tokens.extend(('discard', 'quit', 'save_quit', 'save'))

        self.commands_line(
            ' Saving ',
            'Press any key to save and continue',
            tokens,
        )

    def solve_line(self, solve: Solve) -> None:  # noqa: C901
        """Display solve results, statistics, and record achievements."""
        old_stats = SolveStatisticsReporter(self.cube_size, self.stack)

        self.stack_done.append(solve)
        self.stack = [*self.stack, solve]
        new_stats = SolveStatisticsReporter(self.cube_size, self.stack)

        if solve.flag == DNF:
            SOUND_PLAYER.solve_failed()
        else:
            SOUND_PLAYER.solve_success()

        self.clear_line(full=True)

        if solve.advanced:
            if solve.flag != DNF:
                if self.show_reconstruction:
                    self.console.print(solve.method_line, end='')
                if self.show_time_graph:
                    solve.time_graph()
                if self.show_tps_graph:
                    solve.tps_graph()
                if self.show_fluency_graph:
                    solve.fluency_graph()
                if self.show_recognition_graph:
                    solve.recognition_graph()
                if self.show_highlights:
                    self.console.print(solve.highlights())
                if self.show_doctor:
                    self.console.print(solve.diagnostics(1))

                link = (
                    solve.link_term_timer
                    if not self.free_play
                    else solve.link_alg_cubing
                )
                self.console.print(
                    f'[localhost][link={ link }]'
                    f'Analysis #{ self.counter }:[/link][/localhost] '
                    f'{ solve.report_line }',
                )
            else:
                self.console.print(
                    f'[duration]Duration #{ self.counter }:[/duration]',
                    f'[time]{ format_time(self.elapsed_time) }[/time]',
                    '[dnf]DNF[/dnf]',
                )
                return

        self.console.print(
            f'[duration]Duration #{ self.counter }:[/duration]',
            f'[time]{ format_time(self.elapsed_time) }[/time]',
            self.format_series_line(new_stats, STATS_LIVE_SERIES),
        )

        records = self.print_best_record(new_stats, old_stats)

        records.extend(
            self.print_session_records(
                new_stats, old_stats, STATS_SESSION_SERIES,
            ),
        )

        self.publish_records(records, 'session')

        self.projection_line(new_stats)

    def projection_line(self, stats: SolveStatisticsReporter) -> None:
        """
        Display next-solve average projections.

        For each average size in ``STATS_AO_PROJECTIONS`` shows the range
        still reachable on the next solve, ``[BPA - WPA]``, and the time
        that solve must beat to set a new best average (PB target). The
        range alone appears one solve before a window is complete; the PB
        target appears once a best average exists.

        Args:
            stats: Statistics including the solve that just finished.

        """
        if not STATS_AO_PROJECTIONS:
            return

        rows = []
        for limit in STATS_AO_PROJECTIONS:
            bpa = stats.bpa(limit, stats.stack_time)
            wpa = stats.wpa(limit, stats.stack_time)
            if bpa == -1 and wpa == -1:
                continue
            rows.append((limit, bpa, wpa, stats.target_to_beat_best_ao(limit)))

        if not rows:
            return

        width = max(len(f'Ao{ limit }') for limit, *_ in rows)
        for limit, bpa, wpa, target in rows:
            style = f'ao{ limit }' if limit in {5, 12, 100, 1000} else 'result'
            label = f'Ao{ limit }'.ljust(width)
            low = format_time(bpa).strip()
            high = format_time(wpa).strip()
            line = (
                f'[estimate]Estimate #{ self.counter + 1 }:[/estimate] '
                f'[{ style }]{ label }[/{ style }] '
                f'[result]\\[{ low } - { high }][/result]'
            )
            if target == TARGET_ALWAYS:
                line += ' [record]PB any[/record]'
            elif target >= 0:
                line += f' [best]PB ≤ { format_time(target).strip() }[/best]'
            self.console.print(line)

    async def start(self) -> bool:
        """
        Execute the solve workflow, replaying the scramble on each retry.

        Returns:
            True to continue with next solve, False to quit.

        """
        pending: Algorithm | None = None
        keep_going = False

        while 42:
            keep_going, pending = await self.run_attempt(pending)

            if pending is None:
                break

        return keep_going

    async def run_attempt(  # noqa: C901, PLR0911, PLR0912, PLR0915
            self,
            pending: Algorithm | None = None,
    ) -> tuple[bool, Algorithm | None]:
        """
        Execute complete solve workflow from scramble to save.

        Args:
            pending: Scramble to replay, instead of drawing a new one.

        Returns:
            Tuple of (True to continue with next solve or False to quit,
            the scramble to replay or None when the solve is done with).

        """
        self.init_solve()
        self.retry_requested = False

        if pending is not None:
            self.scramble = pending

            cube = VCube(size=self.cube_size)
            cube.rotate(self.scramble)
        elif self.scrambles:
            if self.scramble_index >= len(self.scrambles):
                self.console.print(
                    'All scrambles completed!',
                    style='success',
                )
                return False, None

            self.scramble = self.scrambles[self.scramble_index]
            self.scramble_index += 1

            cube = VCube(size=self.cube_size)
            cube.rotate(self.scramble)
        else:
            self.scramble, cube = scrambler(
                cube_size=self.cube_size,
                iterations=self.iterations,
                easy_cross=self.easy_cross,
                x_cross=self.x_cross,
                edges_oriented=self.edges_oriented,
                raw_scramble=self.raw_scramble,
                rng=self.rng,
                orientation_moves=self.cube_orientation_moves,
            )

        if self.bluetooth_cube and not self.bluetooth_cube_is_solved:
            scramble = facelets_to_facelets_algorithm(
                self.bluetooth_cube_state,
                cube.state,
            )
            self.scramble_oriented = self.reorient(scramble)
        else:
            self.scramble_oriented = self.reorient(self.scramble)
        self.facelets_scrambled = cube.state

        self.publish_scramble()

        self.start_line(cube)

        quit_solving = await self.scramble_solve()

        if quit_solving is not None:
            return quit_solving, None

        if self.countdown:
            quit_solving = await self.inspect_solve()
            if quit_solving:
                return False, None
        else:
            quit_solving = await self.wait_solve()
            if quit_solving:
                return False, None

        await self.time_solve()

        self.elapsed_time = self.end_time - self.start_time

        if (
                self.bluetooth_cube
                and not self.moves
                and not self.bluetooth_scramble_is_completed
        ):
            # Keyboard start/stop without any move on the connected
            # cube: a misfire, not an attempt, nothing to record.
            self.clear_line(full=True)
            return True, None

        flag: SolveFlag = ''
        if self.bluetooth_cube and not self.bluetooth_scramble_is_completed:
            flag = DNF

        moves = []
        if self.moves:
            first_time = self.moves[0]['time']
            for move in self.moves:
                timing = int((move['time'] - first_time) / MS_TO_NS_FACTOR)
                moves.append(f'{ move["move"] }@{ timing }')

        solve = Solve(
            self.date,
            self.elapsed_time,
            self.scramble,
            flag=flag,
            timer='Term-Timer',
            device=(
                self.bluetooth_interface
                and self.bluetooth_interface.client
                and self.bluetooth_interface.client.name
            ) or '',
            session=self.session,
            solve_id=len(self.stack) + 1,
            cube_size=self.cube_size,
            moves=' '.join(moves),
        )

        solve.method_name = self.method
        solve.orientation = self.orientation_faces

        self.solve_line(solve)

        # The rank the attempt was scrambled, timed and celebrated
        # under: saving one moves the counter on, and the scramble,
        # the records and the solve of one attempt all say the same
        counter = self.counter

        if not self.free_play:
            self.save_line()

            quit_solving = await self.save_solve()

            self.publish_settled_solve(solve, counter)

            if self.retry_requested:
                return True, self.scramble

            if quit_solving:
                return False, None
        else:
            # Free play writes no session file, so the stream is the
            # only trace an attempt ever leaves
            self.publish_settled_solve(solve, counter)
            self.counter += 1

        return True, None
