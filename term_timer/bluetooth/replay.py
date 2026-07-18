"""
Deterministic Bluetooth replay interface for demos and dev sessions.

Replays a realistic solve described in a JSON file through the exact same
event pipeline a physical smart cube uses, so the full solve UI runs end to
end without any hardware. Activation is driven by the hidden ``--replay``
option of the solve command, or by the ``TERM_TIMER_REPLAY`` environment
variable (see ``scripts/commands/timer.py``), which keeps the typed command
in VHS tapes a plain ``term-timer solve``.
"""
import asyncio
import json
import logging
import time
from contextlib import suppress
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Protocol
from typing import Self
from typing import TypedDict

from cubing_algs.move import Move
from cubing_algs.parsing import parse_moves
from cubing_algs.vcube import VCube

from term_timer.bluetooth.interface import BluetoothInterface
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.exceptions import ReplayError

if TYPE_CHECKING:
    from term_timer.bluetooth.annotations import BatteryEventDict
    from term_timer.bluetooth.annotations import FaceletsEventDictNoState
    from term_timer.bluetooth.annotations import HardwareEventDict
    from term_timer.bluetooth.annotations import MoveEventDict

logger = logging.getLogger(__name__)

HUMAN_SCRAMBLE_PACE_MS = 350

# Phases are gated on the timer's real state (see wait_for_state), so these
# pre-move pauses are purely cosmetic pacing now: 0 is safe. Used only when
# the file omits them. Kept at their v1 values, good for GIF readability.
DEFAULT_START_DELAY = 1.5
DEFAULT_INSPECTION = 1.0
DEFAULT_SAVE_DELAY = 2.0

SOLVED_FACELETS = VCube(size=3).state


class TimerStateProvider(Protocol):
    """State surface the replay schedule gates on."""

    state: str
    state_event: asyncio.Event


class ReplayDeviceDict(TypedDict):
    """Simulated device metadata for the replay session."""

    name: str
    hardware_version: str
    software_version: str
    battery: int


class ReplaySolveRequired(TypedDict):
    """Mandatory fields of a replay solve."""

    scramble: str
    solution: str


class ReplaySolveDict(ReplaySolveRequired, total=False):
    """A single replayable solve, with its optional pacing fields."""

    scramble_moves: str
    inspection: float
    start_delay: float
    finish_moves: str
    save_delay: float


class ReplayFileDict(TypedDict):
    """Top-level schema of a replay file."""

    device: ReplayDeviceDict
    solves: list[ReplaySolveDict]


TimedMove = tuple[str, int]


def parse_timed_moves(moves_str: str) -> list[TimedMove]:
    """
    Parse a ``MOVE@ms`` sequence into ``(move, milliseconds)`` pairs.

    Args:
        moves_str: A whitespace-separated sequence such as ``B@0 U'@329``.

    Returns:
        Ordered list of untimed move strings with their millisecond offset.
        Moves without an explicit timing fall back to the human scramble pace.

    """
    moves: list[TimedMove] = []
    for index, move in enumerate(parse_moves(moves_str)):
        milliseconds = move.timed if move.is_timed else index * (
            HUMAN_SCRAMBLE_PACE_MS
        )
        moves.append((str(move.untimed), milliseconds))
    return moves


def scramble_moves_reach_state(scramble_moves: str, scramble: str) -> bool:
    """
    Check that a ``scramble_moves`` sequence lands on the scrambled state.

    The moves may include realistic errors and corrections, but they must
    end on the same cube state the target scramble produces; otherwise the
    timer would never detect the scramble as complete.

    Args:
        scramble_moves: The ``MOVE@ms`` sequence to validate.
        scramble: The reference scramble producing the target state.

    Returns:
        True if applying scramble_moves reaches the scrambled state.

    """
    target = VCube(size=3)
    target.rotate(parse_moves(scramble))

    actual = VCube(size=3)
    for move, _ in parse_timed_moves(scramble_moves):
        actual.rotate(move)

    return actual.is_equal(target, strict=False)


def validate_solve(solve: object, index: int, *, last: bool) -> None:
    """
    Validate a single solve of a replay payload.

    Args:
        solve: The solve object to validate.
        index: Zero-based position of the solve in the file.
        last: Whether this is the last solve of the file; every other
            solve needs finish_moves to chain to the next one.

    Raises:
        ReplayError: The solve is malformed, its scramble_moves do not
            reach the scrambled state, or a chained solve is missing its
            finish_moves save gesture.

    """
    label = f'Replay solve #{ index + 1 }'

    if not isinstance(solve, dict):
        msg = f'{ label } must be a JSON object.'
        raise ReplayError(msg)

    for key in ('scramble', 'solution'):
        if not isinstance(solve.get(key), str) or not solve[key]:
            msg = f'{ label } is missing a non-empty "{ key }".'
            raise ReplayError(msg)

    scramble_moves = solve.get('scramble_moves')
    if scramble_moves is not None:
        if not isinstance(scramble_moves, str):
            msg = f'{ label } "scramble_moves" must be a string.'
            raise ReplayError(msg)
        if not scramble_moves_reach_state(scramble_moves, solve['scramble']):
            msg = (
                f'{ label } "scramble_moves" do not reach the scrambled '
                'state; the timer would never start.'
            )
            raise ReplayError(msg)

    finish_moves = solve.get('finish_moves')
    if finish_moves is not None and not isinstance(finish_moves, str):
        msg = f'{ label } "finish_moves" must be a string.'
        raise ReplayError(msg)
    if finish_moves is None and not last:
        msg = (
            f'{ label } needs "finish_moves" (a save gesture, '
            'e.g. "U@0 U\'@250") to chain to the next solve.'
        )
        raise ReplayError(msg)


def validate_replay(data: object) -> ReplayFileDict:
    """
    Validate the structure and coherence of a decoded replay payload.

    Args:
        data: The object decoded from the replay JSON file.

    Returns:
        The payload, typed as a ReplayFileDict, when it is valid.

    Raises:
        ReplayError: The payload is malformed, a solve's scramble_moves
            do not reach the scrambled state, or a chained solve is
            missing its finish_moves save gesture.

    """
    if not isinstance(data, dict):
        msg = 'Replay file must contain a JSON object.'
        raise ReplayError(msg)

    device = data.get('device')
    if not isinstance(device, dict):
        msg = 'Replay file is missing a "device" object.'
        raise ReplayError(msg)

    for key in ('name', 'hardware_version', 'software_version'):
        if not isinstance(device.get(key), str):
            msg = f'Replay device is missing a string "{ key }".'
            raise ReplayError(msg)
    if not isinstance(device.get('battery'), int):
        msg = 'Replay device is missing an integer "battery".'
        raise ReplayError(msg)

    solves = data.get('solves')
    if not isinstance(solves, list) or not solves:
        msg = 'Replay file must contain a non-empty "solves" list.'
        raise ReplayError(msg)

    for index, solve in enumerate(solves):
        validate_solve(solve, index, last=index == len(solves) - 1)

    return data  # type: ignore[return-value]


def load_replay(path: str) -> ReplayFileDict:
    """
    Load and validate a replay file from disk.

    Args:
        path: Filesystem path to the replay JSON file.

    Returns:
        The validated replay payload.

    Raises:
        ReplayError: The file is missing, unreadable, not valid JSON, or does
            not satisfy the replay schema.

    """
    file = Path(path)
    if not file.exists():
        msg = f'Replay file not found: { path }'
        raise ReplayError(msg)

    try:
        raw = json.loads(file.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as error:
        msg = f'Replay file could not be read: { error }'
        raise ReplayError(msg) from error

    return validate_replay(raw)


class ReplayClient:
    """Minimal BLE client stub exposing what the interface reads."""

    is_connected: bool = True

    def __init__(self, name: str) -> None:
        """Store the simulated device name."""
        self.name = name


class ReplayInterface(BluetoothInterface):
    """
    Drop-in BluetoothInterface that replays solves from a file.

    Pushes the same hardware, battery, facelets and move events a real cube
    would emit, on a real ``asyncio.sleep`` timeline, so the solve UI runs
    unchanged. Every solve of the file is replayed in order; the
    ``finish_moves`` save gesture of a solve (e.g. ``U U'``) answers the
    save prompt and chains to the next one, keyboard free.
    """

    def __init__(
            self,
            queue: asyncio.Queue,  # type: ignore[type-arg]
            replay: ReplayFileDict,
            timer: TimerStateProvider,
    ) -> None:
        """
        Initialize the replay interface with the queue and validated payload.

        Args:
            queue: Event queue consumed by the Bluetooth consumer.
            replay: Validated replay payload; solves are played in order.
            timer: Timer state surface the schedule gates each phase on.

        """
        super().__init__(queue)

        self.replay = replay
        self.timer = timer
        self.client = ReplayClient(  # type: ignore[assignment]
            replay['device']['name'],
        )
        self.driver = None
        self.schedule_task: asyncio.Task[None] | None = None

    async def __aenter__(
            self,
            address: str | None = None,
            filter_name: str | None = None,
            *,
            use_gyroscope: bool,
    ) -> Self:
        """
        Enter the context without touching any hardware.

        Returns:
            The replay interface itself.

        """
        return self

    async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            exc_traceback: object,
    ) -> None:
        """Cancel any pending playback and signal disconnection."""
        if self.schedule_task and not self.schedule_task.done():
            self.schedule_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.schedule_task

        await self.queue.put(None)

    async def send_command(  # noqa: PLR6301
            self, command: str,  # noqa: ARG002
    ) -> bool:
        """
        Accept any command without side effects.

        Returns:
            Always True; the replay ignores outgoing commands.

        """
        return True

    async def send_init_commands(self) -> None:
        """Emit initial device events and launch the playback schedule."""
        await self.emit_hardware()
        await self.emit_battery()
        await self.emit_facelets()

        self.schedule_task = asyncio.create_task(self.run_schedule())

    async def wait_for_state(self, *targets: str) -> None:
        """
        Block until the timer reaches one of the target states.

        Args:
            targets: State names that satisfy the wait.

        """
        while self.timer.state not in targets:
            self.timer.state_event.clear()
            await self.timer.state_event.wait()

    async def run_schedule(self) -> None:
        """Replay each solve: scramble, inspection, solution, save gesture."""
        for solve in self.replay['solves']:
            await self.wait_for_state('scrambling')
            await asyncio.sleep(
                solve.get('start_delay', DEFAULT_START_DELAY),
            )

            # A bare scramble goes through the same parser: its untimed
            # moves fall back to the human scramble pace.
            await self.play_moves(parse_timed_moves(
                solve.get('scramble_moves') or solve['scramble'],
            ))

            await self.wait_for_state('scrambled', 'inspecting')
            await asyncio.sleep(solve.get('inspection', DEFAULT_INSPECTION))

            await self.play_moves(parse_timed_moves(solve['solution']))

            finish_moves = solve.get('finish_moves')
            if finish_moves:
                await self.wait_for_state('saving')
                await asyncio.sleep(
                    solve.get('save_delay', DEFAULT_SAVE_DELAY),
                )
                await self.play_moves(parse_timed_moves(finish_moves))

    async def play_moves(self, moves: list[TimedMove]) -> None:
        """
        Emit move events spaced by their millisecond offsets.

        Move clocks are anchored on ``time.perf_counter_ns()``, the clock
        real drivers stamp events with at reception: the timer display
        computes ``perf_counter_ns() - start_time``, so any other epoch
        shows garbage. The file's millisecond offsets are kept as exact
        deltas so the recorded solve duration stays deterministic.

        Args:
            moves: Ordered ``(move, milliseconds)`` pairs to replay.

        """
        clock_base = time.perf_counter_ns()
        previous_ms = 0
        for serial, (move, milliseconds) in enumerate(moves):
            delay = (milliseconds - previous_ms) / 1000
            if delay > 0:
                await asyncio.sleep(delay)
            previous_ms = milliseconds
            await self.emit_move(
                move, serial,
                clock_base + milliseconds * MS_TO_NS_FACTOR,
            )

    async def emit_hardware(self) -> None:
        """Emit the hardware description event."""
        device = self.replay['device']
        event: HardwareEventDict = {
            'event': 'hardware',
            'clock': 0,
            'timestamp': datetime.now(tz=UTC),
            'hardware_name': device['name'],
            'hardware_version': device['hardware_version'],
            'software_version': device['software_version'],
            'gyroscope_enabled': False,
            'gyroscope_ready': False,
            'gyroscope_supported': False,
            'restart_no_power': 0,
        }
        await self.queue.put([event])

    async def emit_battery(self) -> None:
        """Emit the battery level event."""
        event: BatteryEventDict = {
            'event': 'battery',
            'clock': 0,
            'timestamp': datetime.now(tz=UTC),
            'level': self.replay['device']['battery'],
            'charging_state': 0,
        }
        await self.queue.put([event])

    async def emit_facelets(self) -> None:
        """Emit the initial solved facelets event."""
        event: FaceletsEventDictNoState = {
            'event': 'facelets',
            'clock': 0,
            'timestamp': datetime.now(tz=UTC),
            'serial': 0,
            'facelets': SOLVED_FACELETS,
        }
        await self.queue.put([event])

    async def emit_move(
            self, move: str, serial: int, clock: int,
    ) -> None:
        """
        Emit a single move event.

        Args:
            move: Untimed move notation, e.g. ``R`` or ``U'``.
            serial: Monotonic move counter.
            clock: Nanosecond clock of the move, perf_counter based.

        """
        parsed = Move(move)
        event: MoveEventDict = {
            'event': 'move',
            'clock': clock,
            'timestamp': datetime.now(tz=UTC),
            'serial': serial,
            'local_timestamp': None,
            'cube_timestamp': None,
            'face': 0,
            'direction': 0,
            'move': str(parsed),
        }
        await self.queue.put([event])
