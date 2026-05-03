"""Driller interface for repeating an algorithm to build fluency."""
from cubing_algs.algorithm import Algorithm
from cubing_algs.annotations import CubeOrientation
from cubing_algs.move import Move
from cubing_algs.transform.size import expand_moves

from term_timer.bluetooth.annotations import MoveEventDict
from term_timer.bluetooth.annotations import RotationEventDict
from term_timer.constants import ESCAPE_CHAR
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.formatter import format_delta
from term_timer.formatter import format_time
from term_timer.interface import SolveInterface


class Driller(SolveInterface):
    """
    Driller interface for repeating an algorithm to build fluency.

    Times repeated executions of a fixed algorithm without recording
    results. Supports bluetooth move validation: bad moves (deviations
    from the expected sequence) cause an immediate disconnect with a
    warning.
    """

    def __init__(
            self, *,
            algorithm: str,
            times: int,
            orientation: CubeOrientation,
            countdown: int,
            metronome: float,
    ) -> None:
        """Initialize driller with the algorithm and display options."""
        super().__init__()

        self.set_state('configure')

        self.algorithm = Algorithm.parse_moves(algorithm)

        self.times = times
        self.orientation_faces = orientation
        self.countdown = countdown
        self.metronome = metronome
        self.counter = 1

        self.rep_times: list[int] = []
        self.expected_moves = expand_moves(self.reorient(self.algorithm))
        self.move_index: int = 0
        self.bad_move: str = ''

        self.header_line()

    def header_line(self) -> None:
        """Display the drill header with algorithm and move count."""
        suffix = (
            f' x{ self.times }'
            if self.times > 0
            else ''
        )
        self.console.print(
            f'Drilling: [moves]{ self.algorithm }[/moves]'
            f' ({ self.algorithm.metrics.htm } HTM)'
            f'{ suffix }',
            style='trainer',
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
        """Display time and optional delta for the completed rep."""
        extra = ''
        if len(self.rep_times) >= 2:
            delta = self.rep_times[-1] - self.rep_times[-2]
            extra = f' { format_delta(delta) }'

        self.console.print(
            f'[duration]Rep #{ self.counter }:[/duration]',
            f'[time]{ format_time(self.elapsed_time) }[/time]'
            f'{ extra }',
        )

    def reset_drill_state(self) -> None:
        """Reset per-rep drill tracking state after init_solve()."""
        self.move_index = 0
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
        # rotation = event['event'] == 'rotation'

        # timed_move = Move(f'{ move }@{ int(clock / MS_TO_NS_FACTOR) }')

        # if self.state in {'start', 'scrambling'}:
        #     self.handle_scrambled(timed_move)
        #     return

        # if self.state == 'saving':
        #     self.handle_save_gestures(timed_move)
        #     return

        if self.state == 'scrambled':
            # if rotation:
            #     return
            self.moves.append({'move': move, 'time': clock})
            if not self.solve_started_event.is_set():
                self.start_time = clock
                self.solve_started_event.set()
            self.validate_drill_move(Move(move), clock)
            return

        if self.state == 'solving':
            self.moves.append({'move': move, 'time': clock})
            # if rotation:
            #     return
            self.validate_drill_move(Move(move), clock)

    def validate_drill_move(self, move: Move, clock: int) -> None:
        """
        Validate a move against the expected drill sequence.

        Advances the move index on a match, signals completion when
        the full sequence is done, or signals a bad move on mismatch.

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

        if move.base_move != self.expected_moves[self.move_index].base_move:
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

            await self.wait_solve()

            if self.countdown:
                await self.inspect_solve()

            await self.time_solve()

            if self.bad_move:
                expected = (
                    self.expected_moves[self.move_index]
                    if self.move_index < len(self.expected_moves)
                    else '(end of sequence)'
                )
                self.clear_line(full=True)
                self.console.print(
                    f'[warning]Bad move: [moves]{ self.bad_move }[/moves]'
                    f' — expected [moves]{ expected }[/moves][/warning]',
                )
                await self.bluetooth_disconnect()
                return False

        else:
            self.start_line()

            char = await self.getch('start')
            if char in {'q', ESCAPE_CHAR}:
                return False

            if self.countdown:
                await self.inspect_solve()

            await self.time_solve()

        self.elapsed_time = self.end_time - self.start_time
        self.rep_times.append(self.elapsed_time)

        self.clear_line(full=True)
        self.rep_line()

        self.counter += 1

        return True

    async def start(self) -> bool:
        """
        Run the drill session.

        Returns:
            True if completed, False if user quit early.

        """
        if self.times > 0:
            return await self.drill_rep()

        while 42:
            if not await self.drill_rep():
                return False

        return True
