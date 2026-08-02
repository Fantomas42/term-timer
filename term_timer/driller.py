"""Driller interface for repeating an algorithm to build fluency."""
from typing import cast

from cubing_algs.algorithm import Algorithm
from cubing_algs.annotations import CubeOrientation
from cubing_algs.move import Move

from term_timer.bluetooth.annotations import MoveEventDict
from term_timer.bluetooth.annotations import RotationEventDict
from term_timer.constants import ESCAPE_CHAR
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import SECOND
from term_timer.exceptions import InvalidAlgorithmError
from term_timer.formatter import format_delta
from term_timer.formatter import format_fluency
from term_timer.formatter import format_time
from term_timer.interface import SolveInterface
from term_timer.interface.sounds import SOUND_PLAYER
from term_timer.logger import spawn
from term_timer.solve import Solve


class Driller(SolveInterface):
    """
    Driller interface for repeating an algorithm to build fluency.

    Times repeated executions of a fixed algorithm without recording
    results. Supports bluetooth move validation: bad moves (deviations
    from the expected sequence) cause an immediate disconnect with a
    warning.
    """

    def __init__(  # noqa: PLR0913
            self, *,
            algorithm: str,
            times: int,
            duration: int,
            orientation: CubeOrientation,
            countdown: int,
            metronome: float,
    ) -> None:
        """
        Initialize driller with the algorithm and display options.

        Raises:
            InvalidAlgorithmError: If provided algorithm is too short.

        """
        super().__init__()

        self.set_state('configure')

        self.algorithm = Algorithm.parse_moves(algorithm)

        if self.algorithm.metrics.qtm < 2:
            error_string = (
                f'Invalid algorithm, "{ self.algorithm }" is too short.'
            )
            raise InvalidAlgorithmError(error_string)

        self.times = times
        self.duration = duration
        self.orientation_faces = orientation
        self.countdown = countdown
        self.metronome = metronome
        self.counter = 1

        self.rep_times: list[int] = []
        self.rep_fluencies: list[int] = []
        self.rep_tps: list[float] = []
        self.expected_moves = self.reorient(self.algorithm)
        self.move_index: int = 0
        self.move_accumulated: int = 0
        self.move_direction: int = 0
        self.bad_move: Move | str = ''

        self.header_line()

    def header_line(self) -> None:
        """Display the drill header with algorithm and move count."""
        suffix = (
            f' x{ self.times }'
            if self.times > 0
            else ''
        )
        if self.duration > 0:
            minutes, seconds = divmod(self.duration, 60)
            duration_str = (
                f'{ minutes }:{ seconds:02d}'
                if minutes
                else f'{ seconds }s'
            )
            suffix += f' | { duration_str }'
        self.console.print(
            f'Drilling: [moves]{ self.algorithm }[/moves]'
            f' ({ self.algorithm.metrics.htm } HTM)'
            f'{ suffix }',
            style='driller',
        )

    def start_line(self) -> None:
        """Display instructions to start the timer for a rep."""
        if self.bluetooth_interface:
            self.console.print(
                'Execute the algorithm on the cube to time the rep,',
                '[key](q)[/key] to quit.',
                end='', style='consign',
            )
        else:
            self.console.print(
                'Press any key to start/stop the timer,',
                '[key](q)[/key] to quit.',
                end='', style='consign',
            )

    def rep_line(self) -> None:
        """Display time, delta, TPS, and fluency for the completed rep."""
        extra = ''
        if len(self.rep_times) >= 2:
            delta = self.rep_times[-1] - self.rep_times[-2]
            extra = f' { format_delta(delta) }'

        moves = len(self.expected_moves)
        tps = moves / (self.elapsed_time / SECOND) if self.elapsed_time else 0

        fluency = 0
        fluency_line = ''
        if self.moves:
            start = self.moves[0]['time']
            timed_moves = []
            for m in self.moves:
                ms = (m['time'] - start) // MS_TO_NS_FACTOR
                timed_moves.append(Move(f'{ m["move"] }@{ ms }'))
            timed_alg = Algorithm(timed_moves)
            fluency = Solve.compute_fluency(timed_alg)
            if fluency > 0:
                fluency_line = f' { format_fluency(fluency) }'

        self.rep_fluencies.append(fluency)
        self.rep_tps.append(tps)

        self.console.print(
            f'[duration]Rep #{ self.counter:03d}:[/duration]',
            f'[time]{ format_time(self.elapsed_time) }[/time]'
            f' [tps]{ tps:05.2f} TPS[/tps]'
            f'{ fluency_line }'
            f'{ extra }',
        )

    def reset_drill_state(self) -> None:
        """Reset per-rep drill tracking state after init_solve()."""
        self.move_index = 0
        self.move_accumulated = 0
        self.move_direction = 0
        self.bad_move = ''

    def handle_bluetooth_move(
            self, event: MoveEventDict | RotationEventDict,
    ) -> None:
        """
        Handle a move or rotation event from the Bluetooth cube.

        Overrides the Bluetooth mixin to validate each move against the
        expected drill sequence instead of checking for a solved state.
        Delegates to base behaviour for scrambling and saving states.

        Args:
            event: Move or rotation event containing move notation and clock.

        """
        move = event['move']
        clock = event['clock']

        if self.state == 'scrambled':
            self.moves.append({'move': move, 'time': clock})

            if not self.solve_started_event.is_set():
                self.start_time = clock
                self.solve_started_event.set()

            self.validate_drill_move(Move(move), clock)
            return

        if self.state == 'solving':
            self.moves.append({'move': move, 'time': clock})

            self.validate_drill_move(Move(move), clock)

    def validate_drill_move(self, move: Move, clock: int) -> None:
        """
        Validate a move against the expected drill sequence.

        Advances the move index on a match, signals completion when
        the full sequence is done, or signals a bad move on mismatch.

        For double moves (U2), both U U and U' U' are accepted since
        both achieve the same half-turn. Mixed directions (U then U')
        cancel out and are rejected.

        Args:
            move: The move notation received from the bluetooth cube.
            clock: The nanosecond clock value of the move event.

        """
        if self.bad_move:
            return

        if self.move_index >= len(self.expected_moves):
            self.bad_move = move
            self.solve_completed_event.set()
            return

        expected = self.expected_moves[self.move_index]

        if move.base_move != expected.base_move:
            self.bad_move = move
            self.solve_completed_event.set()
            return

        if expected.is_double:
            direction = 1 if move.quarter_turns > 0 else -1

            if self.move_direction == 0:
                self.move_direction = direction

            elif direction != self.move_direction:
                self.bad_move = move
                self.solve_completed_event.set()
                return

            self.move_accumulated += abs(move.quarter_turns)

            if self.move_accumulated < 2:
                return

            self.move_direction = 0
            self.move_accumulated = 0

        elif move.quarter_turns != expected.quarter_turns:
            self.bad_move = move
            self.solve_completed_event.set()
            return

        self.move_index += 1

        if self.move_index == len(self.expected_moves):
            self.end_time = clock
            self.solve_completed_event.set()

    async def drill_rep(self) -> bool:
        """
        Execute one rep of the drill.

        Returns:
            True to continue drilling, False to quit.

        """
        self.init_solve()
        self.reset_drill_state()

        if self.bluetooth_interface:
            self.set_state('scrambled')
            self.start_line()

            getch_task = spawn(self.getch('start'), 'getch-start')
            await self.wait_control(
                [
                    getch_task,
                    spawn(
                        self.solve_started_event.wait(),
                        'event-solve-started',
                    ),
                ],
            )

            if not self.solve_started_event.is_set():
                char = getch_task.result()
                if char in {'q', ESCAPE_CHAR}:
                    return False

            if self.countdown:
                quit_drilling = await self.inspect_solve()
                if quit_drilling:
                    return False

            await self.time_solve()

            if self.bad_move:
                expected = (
                    self.reorient(
                        Algorithm(
                            [self.expected_moves[self.move_index]],
                        ),
                    )
                    if self.move_index < len(self.expected_moves)
                    else '(end of sequence)'
                )
                bad_move = self.reorient(
                    Algorithm([cast('Move', self.bad_move)]),
                )

                self.clear_line(full=True)
                self.console.print(
                    '😵 [warning]Bad move: '
                    f'[moves]{ bad_move }[/moves] - expected '
                    f'[moves]{ expected }[/moves][/warning]',
                )
                return False

        else:
            self.start_line()

            char = await self.getch('start')
            if char in {'q', ESCAPE_CHAR}:
                return False

            if self.countdown:
                quit_drilling = await self.inspect_solve()
                if quit_drilling:
                    return False

            await self.time_solve()

        self.elapsed_time = self.end_time - self.start_time
        self.rep_times.append(self.elapsed_time)

        SOUND_PLAYER.solve_step()
        self.clear_line(full=True)
        self.rep_line()

        self.counter += 1

        return True

    async def start(self) -> bool:
        """
        Execute one rep of the drill.

        Returns:
            True if completed, False if user quit early.

        """
        return await self.drill_rep()
