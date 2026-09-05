"""
Deterministic Bluetooth replay interface for demos and dev sessions.

Replays a realistic solve described in a JSON file through the exact same
event pipeline a physical smart cube uses, so the full solve UI runs end to
end without any hardware. Activation is driven by the hidden ``--replay``
option of the solve command, or by the ``TERM_TIMER_REPLAY`` environment
variable (see ``scripts/commands/timer.py``), which keeps the typed command
in VHS tapes a plain ``term-timer solve``.

Two payloads share that pipeline, told apart by their root key:

- ``solves``: the scramble and the solution are written in the file, for the
  solving commands (solve, ghost, daily).
- ``trainings``: the trainer draws its own case and computes its setup from
  the live cube state, so nothing can be written ahead of time. The file
  only carries the pacing and the scenario, and the moves are derived from
  the trainer itself at each phase (see TrainerReplayInterface).
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
from typing import cast

from cubing_algs.algorithm import Algorithm
from cubing_algs.move import Move
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.degrip import degrip_moves
from cubing_algs.transform.wide import unwide_rotation_moves
from cubing_algs.vcube import VCube

from term_timer.bluetooth.interface import BluetoothInterface
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.exceptions import ReplayError
from term_timer.logger import spawn
from term_timer.publisher import PUBLISHER

if TYPE_CHECKING:
    from term_timer.bluetooth.annotations import BatteryEventDict
    from term_timer.bluetooth.annotations import FaceletsEventDictNoState
    from term_timer.bluetooth.annotations import HardwareEventDict
    from term_timer.bluetooth.annotations import MoveEventDict

logger = logging.getLogger(__name__)

HUMAN_SCRAMBLE_PACE_MS = 150

# Phases are gated on the timer's real state (see wait_for_state), so these
# pre-move pauses are purely cosmetic pacing now: 0 is safe. Used only when
# the file omits them. Kept at their v1 values, good for GIF readability.
DEFAULT_START_DELAY = 1.0
DEFAULT_INSPECTION = 1.0
DEFAULT_SAVE_DELAY = 2.0
DEFAULT_RECOGNITION = 1.0
DEFAULT_SOLVE_PACE_MS = 150
DEFAULT_DNF_DELAY = 2.0

DNF_OUTCOME = 'dnf'

SOLVED_FACELETS = VCube(size=3).state


class TimerStateProvider(Protocol):
    """State surface the replay schedule gates on."""

    state: str
    state_event: asyncio.Event
    free_play: bool


class TrainerStateProvider(TimerStateProvider, Protocol):
    """Trainer surface the derived replay reads its moves from."""

    scramble_oriented: Algorithm
    fsrs_reference_solution: Algorithm
    facelets_scrambled: str

    @property
    def cube_orientation_moves(self) -> Algorithm:
        """Rotations translating the cube frame into the user frame."""

    def step_is_completed(self, facelets: str) -> bool:
        """Check whether a cube state completes the training step."""

    def stop_solve(self) -> None:
        """Stop the running solve, as a key press does."""


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


class TrainerReplayDict(TypedDict, total=False):
    """
    A single replayable training attempt.

    Every field is optional: the setup and the solution are derived from
    the trainer, so an empty object already describes a clean attempt at
    the default pace.
    """

    start_delay: float
    scramble_pace: float
    recognition: float
    solve_pace: float
    pauses: list[list[float]]
    outcome: str
    dnf_moves: str
    dnf_delay: float
    finish_moves: str
    save_delay: float


class TrainerReplayRequired(TypedDict):
    """Mandatory fields of a trainer replay file."""

    device: ReplayDeviceDict
    trainings: list[TrainerReplayDict]


class TrainerReplayFileDict(TrainerReplayRequired, total=False):
    """Top-level schema of a trainer replay file."""

    loop: bool


ReplayPayload = ReplayFileDict | TrainerReplayFileDict

TimedMove = tuple[str, int]


def timed_moves(algorithm: Algorithm) -> list[TimedMove]:
    """
    Split a timed algorithm into ``(move, milliseconds)`` pairs.

    Args:
        algorithm: The moves to split, timed or not.

    Returns:
        Ordered list of untimed move strings with their millisecond offset.
        Moves without an explicit timing fall back to the human scramble pace.

    """
    moves: list[TimedMove] = []
    for index, move in enumerate(algorithm):
        milliseconds = move.timed if move.is_timed else index * (
            HUMAN_SCRAMBLE_PACE_MS
        )
        moves.append((str(move.untimed), milliseconds))
    return moves


def parse_timed_moves(moves_str: str) -> list[TimedMove]:
    """
    Parse a ``MOVE@ms`` sequence into ``(move, milliseconds)`` pairs.

    Args:
        moves_str: A whitespace-separated sequence such as ``B@0 U'@329``.

    Returns:
        Ordered list of untimed move strings with their millisecond offset.

    """
    return timed_moves(parse_moves(moves_str))


def paced_moves(
        algorithm: Algorithm,
        pace: float,
        pauses: list[list[float]] | None = None,
) -> list[TimedMove]:
    """
    Spread an algorithm over a regular pace, with optional pauses.

    The pace is the delay between two consecutive moves; a pause adds its
    own delay before the move it indexes, which is how a replay reproduces
    a hesitation in the middle of an execution.

    Args:
        algorithm: The moves to time.
        pace: Milliseconds between two consecutive moves.
        pauses: ``[move_index, seconds]`` pairs, the seconds being added
            before the indexed move.

    Returns:
        Ordered list of untimed move strings with their millisecond offset.

    """
    held = {int(index): seconds for index, seconds in (pauses or [])}

    moves: list[TimedMove] = []
    milliseconds = 0.0
    for index, move in enumerate(algorithm):
        milliseconds += held.get(index, 0.0) * 1000
        moves.append((str(move.untimed), int(milliseconds)))
        milliseconds += pace

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


def read_replay(path: str) -> object:
    """
    Read and decode a replay file from disk.

    Args:
        path: Filesystem path to the replay JSON file.

    Returns:
        The decoded payload, left to its validator to check.

    Raises:
        ReplayError: The file is missing, unreadable or not valid JSON.

    """
    file = Path(path)
    if not file.exists():
        msg = f'Replay file not found: { path }'
        raise ReplayError(msg)

    try:
        return json.loads(file.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as error:
        msg = f'Replay file could not be read: { error }'
        raise ReplayError(msg) from error


def validate_payload(data: object) -> dict[str, object]:
    """
    Validate the envelope shared by both replay payloads.

    Args:
        data: The object decoded from the replay JSON file.

    Returns:
        The payload as a plain dict, once its device is sound.

    Raises:
        ReplayError: The payload is not an object, or its device is
            missing or malformed.

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

    return cast('dict[str, object]', data)


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
    data = validate_payload(data)

    if 'trainings' in data:
        msg = (
            'This is a trainer replay file ("trainings"); '
            'a solving command needs a "solves" one.'
        )
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

    A missing, unreadable or invalid file raises ``ReplayError``, from
    ``read_replay`` or ``validate_replay``.

    Args:
        path: Filesystem path to the replay JSON file.

    Returns:
        The validated replay payload.

    """
    return validate_replay(read_replay(path))


def load_scramble_replay(
        path: str | None,
        scramble: str,
) -> ReplayFileDict | None:
    """
    Load a replay racing an imposed scramble.

    Commands seeded by an imposed scramble (ghost, daily) cannot let the
    replay inject its own, so every solve of the file is checked against
    it: a file landing on another state would leave the timer waiting in
    its scrambling phase forever, and validate_replay cannot catch it
    since it only compares the file to itself.

    Args:
        path: Filesystem path to the replay file, empty when the command
            runs without a replay.
        scramble: The scramble the command imposes.

    Returns:
        The validated replay payload, or None when no path is given.

    Raises:
        ReplayError: The file is invalid, or one of its solves does not
            scramble to the imposed state.

    """
    if not path:
        return None

    replay = load_replay(path)

    for index, solve in enumerate(replay['solves']):
        if not scramble_moves_reach_state(solve['scramble'], scramble):
            msg = (
                f'Replay solve #{ index + 1 } scrambles to another state '
                f'than the imposed scramble ({ scramble }); '
                'the timer would never start.'
            )
            raise ReplayError(msg)

    return replay


def validate_training(
        training: object, index: int, *, last: bool, loop: bool,
) -> None:
    """
    Validate a single attempt of a trainer replay payload.

    Args:
        training: The attempt object to validate.
        index: Zero-based position of the attempt in the file.
        last: Whether this is the last attempt of the file.
        loop: Whether the file loops, which chains the last attempt back
            to the first one and makes its save gesture mandatory too.

    Raises:
        ReplayError: The attempt is malformed, declares an unknown
            outcome, or is missing the finish_moves save gesture it needs
            to chain to the next one.

    """
    label = f'Replay training #{ index + 1 }'

    if not isinstance(training, dict):
        msg = f'{ label } must be a JSON object.'
        raise ReplayError(msg)

    outcome = training.get('outcome', '')
    if outcome not in {'', 'solved', DNF_OUTCOME}:
        msg = (
            f'{ label } has an unknown "outcome" ({ outcome }); '
            f'expected "solved" or "{ DNF_OUTCOME }".'
        )
        raise ReplayError(msg)

    for key in ('dnf_moves', 'finish_moves'):
        moves = training.get(key)
        if moves is not None and not isinstance(moves, str):
            msg = f'{ label } "{ key }" must be a string.'
            raise ReplayError(msg)

    pauses = training.get('pauses')
    if pauses is not None:
        if not isinstance(pauses, list):
            msg = f'{ label } "pauses" must be a list of [index, seconds].'
            raise ReplayError(msg)
        for pause in pauses:
            if not isinstance(pause, list) or len(pause) != 2:
                msg = (
                    f'{ label } "pauses" entries must be '
                    '[move_index, seconds] pairs.'
                )
                raise ReplayError(msg)

    if training.get('finish_moves') is None and (not last or loop):
        msg = (
            f'{ label } needs "finish_moves" (a save gesture, '
            'e.g. "U@0 U\'@250") to chain to the next attempt.'
        )
        raise ReplayError(msg)


def validate_trainer_replay(data: object) -> TrainerReplayFileDict:
    """
    Validate the structure of a decoded trainer replay payload.

    Nothing here can be checked against a cube: the setup and the
    solution are derived from the trainer at replay time, so the file
    only describes a rhythm and a scenario.

    Args:
        data: The object decoded from the replay JSON file.

    Returns:
        The payload, typed as a TrainerReplayFileDict, when it is valid.

    Raises:
        ReplayError: The payload is malformed, or one of its attempts is.

    """
    data = validate_payload(data)

    if 'solves' in data:
        msg = (
            'This is a solving replay file ("solves"); '
            'the train command needs a "trainings" one.'
        )
        raise ReplayError(msg)

    trainings = data.get('trainings')
    if not isinstance(trainings, list) or not trainings:
        msg = 'Replay file must contain a non-empty "trainings" list.'
        raise ReplayError(msg)

    loop = bool(data.get('loop', False))
    for index, training in enumerate(trainings):
        validate_training(
            training, index,
            last=index == len(trainings) - 1,
            loop=loop,
        )

    return cast('TrainerReplayFileDict', data)


def load_trainer_replay(path: str | None) -> TrainerReplayFileDict | None:
    """
    Load and validate a trainer replay file from disk.

    A missing, unreadable or invalid file raises ``ReplayError``, from
    ``read_replay`` or ``validate_trainer_replay``.

    Args:
        path: Filesystem path to the replay file, empty when the command
            runs without a replay.

    Returns:
        The validated payload, or None when no path is given.

    """
    if not path:
        return None

    return validate_trainer_replay(read_replay(path))


class ReplayClient:
    """Minimal BLE client stub exposing what the interface reads."""

    is_connected: bool = True

    def __init__(self, name: str) -> None:
        """Store the simulated device name."""
        self.name = name


class BaseReplayInterface(BluetoothInterface):
    """
    Drop-in BluetoothInterface pushing recorded events instead of BLE ones.

    Emits the same hardware, battery, facelets and move events a real cube
    would, on a real ``asyncio.sleep`` timeline, so the UI runs unchanged.
    Each flavour of replay only has its own ``run_schedule`` to write.
    """

    def __init__(
            self,
            queue: asyncio.Queue,  # type: ignore[type-arg]
            device: ReplayDeviceDict,
            timer: TimerStateProvider,
    ) -> None:
        """
        Initialize the replay interface with the queue and the device.

        Args:
            queue: Event queue consumed by the Bluetooth consumer.
            device: Simulated device metadata announced at connection.
            timer: Timer state surface the schedule gates each phase on.

        """
        super().__init__(queue)

        self.device = device
        self.timer = timer
        self.client = ReplayClient(  # type: ignore[assignment]
            device['name'],
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

        The link is announced all the same: a replay feeds the very
        same stream as a real cube, and a subscriber waiting for the
        cube to show up must not be able to tell the two apart.

        Returns:
            The replay interface itself.

        """
        PUBLISHER.publish_link(connected=True, reason='opened')

        return self

    async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            exc_traceback: object,
    ) -> None:
        """
        Cancel any pending playback.

        The stop sentinel is left to the caller, as on a real interface:
        a drop-in that stops the consumer on its own would hide from the
        replay every defect of the exit path.

        The link is closed on the stream like a real one, and never
        lost: a replay running out of events is an application letting
        go, not a cube going away.
        """
        if self.schedule_task and not self.schedule_task.done():
            self.schedule_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.schedule_task

        PUBLISHER.publish_link(connected=False, reason='closed')

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

        self.schedule_task = spawn(self.run_schedule(), 'replay-schedule')

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
        """
        Play the payload, each flavour on its own phases.

        Raises:
            NotImplementedError: Always; a flavour must define its own.

        """
        raise NotImplementedError

    async def play_moves(self, moves: list[TimedMove], gate: str = '') -> None:
        """
        Emit move events spaced by their millisecond offsets.

        Move clocks are anchored on ``time.perf_counter_ns()``, the clock
        real drivers stamp events with at reception: the timer display
        computes ``perf_counter_ns() - start_time``, so any other epoch
        shows garbage. The millisecond offsets are kept as exact deltas so
        the recorded solve duration stays deterministic.

        Args:
            moves: Ordered ``(move, milliseconds)`` pairs to replay.
            gate: State to wait for right after the first move, when the
                rest of the sequence must not be emitted before the timer
                caught up with it.

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
            if gate and not serial:
                await self.wait_for_state(gate)

    async def play_save_gesture(
            self,
            moves: list[TimedMove],
            delay: float,
    ) -> None:
        """
        Answer the save prompt with the gesture closing an attempt.

        Free play saves nothing, so it never prompts and never reaches
        the ``saving`` state: waiting for it there would hang the
        schedule on the attempt it just played, and the next one would
        wait forever for a setup nobody sends. The gesture is dropped
        instead, which leaves the very same file playable in both modes.

        Args:
            moves: The gesture, already translated into the cube frame.
            delay: Seconds to wait on the save prompt before the gesture.

        """
        if self.timer.free_play:
            return

        await self.wait_for_state('saving')
        await asyncio.sleep(delay)
        await self.play_moves(moves)

    async def emit_hardware(self) -> None:
        """Emit the hardware description event."""
        event: HardwareEventDict = {
            'event': 'hardware',
            'clock': 0,
            'timestamp': datetime.now(tz=UTC),
            'hardware_name': self.device['name'],
            'hardware_version': self.device['hardware_version'],
            'software_version': self.device['software_version'],
            'gyroscope_enabled': False,
            'gyroscope_ready': False,
            'restart_no_power': 0,
        }
        await self.emit([event])

    async def emit_battery(self) -> None:
        """Emit the battery level event."""
        event: BatteryEventDict = {
            'event': 'battery',
            'clock': 0,
            'timestamp': datetime.now(tz=UTC),
            'level': self.device['battery'],
            'charging_state': 0,
        }
        await self.emit([event])

    async def emit_facelets(self) -> None:
        """Emit the initial solved facelets event."""
        event: FaceletsEventDictNoState = {
            'event': 'facelets',
            'clock': 0,
            'timestamp': datetime.now(tz=UTC),
            'serial': 0,
            'facelets': SOLVED_FACELETS,
        }
        await self.emit([event])

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
        await self.emit([event])


class ReplayInterface(BaseReplayInterface):
    """
    Replay of solves fully described by their file.

    Every solve of the file is replayed in order; the ``finish_moves``
    save gesture of a solve (e.g. ``U U'``) answers the save prompt and
    chains to the next one, keyboard free.
    """

    def __init__(
            self,
            queue: asyncio.Queue,  # type: ignore[type-arg]
            replay: ReplayFileDict,
            timer: TimerStateProvider,
    ) -> None:
        """
        Initialize the replay interface with the validated payload.

        Args:
            queue: Event queue consumed by the Bluetooth consumer.
            replay: Validated replay payload; solves are played in order.
            timer: Timer state surface the schedule gates each phase on.

        """
        super().__init__(queue, replay['device'], timer)

        self.replay = replay

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
                await self.play_save_gesture(
                    parse_timed_moves(finish_moves),
                    solve.get('save_delay', DEFAULT_SAVE_DELAY),
                )


class TrainerReplayInterface(BaseReplayInterface):
    """
    Replay of training attempts, deriving its moves from the trainer.

    Nothing about the cube can be written in a trainer replay file: the
    case is drawn by FSRS and its setup is computed from the live cube
    state at every attempt. So the file only carries the pacing and the
    scenario, and each phase asks the trainer what it is waiting for:
    the setup path it displays, then the reference solution of the case
    for the execution.

    Everything the file does write — ``dnf_moves``, ``finish_moves`` — is
    read in the user frame, the one the trainer prints and the one the
    gestures are recognised in, and translated here. A trainer replay is
    therefore independent of the configured orientation, unlike a solving
    one whose moves are taken in the cube frame.
    """

    def __init__(
            self,
            queue: asyncio.Queue,  # type: ignore[type-arg]
            replay: TrainerReplayFileDict,
            trainer: TrainerStateProvider,
    ) -> None:
        """
        Initialize the trainer replay with the validated payload.

        Args:
            queue: Event queue consumed by the Bluetooth consumer.
            replay: Validated payload; attempts are played in order.
            trainer: Trainer surface the moves are derived from.

        """
        super().__init__(queue, replay['device'], trainer)

        self.replay = replay
        self.trainer = trainer

    def cube_frame(self, algorithm: Algorithm) -> Algorithm:
        """
        Translate user-frame moves into the frame the cube reports in.

        The rotations of the session orientation and of the algorithm
        itself are degripped away: a cube senses face turns, never the
        way it is held.

        Args:
            algorithm: The moves as a solver reads them.

        Returns:
            The rotation-free cube-frame equivalent.

        """
        return degrip_moves(self.trainer.cube_orientation_moves + algorithm)

    def execution_readings(self, solution: Algorithm) -> list[Algorithm]:
        """
        List the ways an execution could reach the trainer.

        A wide move is the ambiguity left. The drivers only ever report
        single face turns, so a solver's ``d'`` physically arrives as the
        face turn it contains, the whole-cube rotation going with it
        being sensed by nothing — but the trainer's own state model
        happily applies the wide turn it is handed. Both readings are
        offered, the one completing the step wins, and no case of any
        step is left unsolvable.

        Args:
            solution: The moves as a solver reads them.

        Returns:
            The distinct cube-frame readings to try, widest first.

        """
        readings = [
            self.cube_frame(solution),
            self.cube_frame(unwide_rotation_moves(solution)),
        ]

        if str(readings[0]) == str(readings[1]):
            return readings[:1]

        return readings

    def scramble_algorithm(self) -> Algorithm:
        """
        Take the setup the trainer displays back into the cube frame.

        The trainer solves that path itself, from the live cube state to
        the scrambled one, which is what lets a replay chain attempts:
        the cube never returns to solved. Reading its result rather than
        solving for it again keeps the replay move for move on what the
        scramble display highlights, and spares a second solver call.

        Returns:
            The moves leading the cube to the scrambled state.

        """
        return self.cube_frame(self.trainer.scramble_oriented)

    def solution_algorithm(self, training: TrainerReplayDict) -> Algorithm:
        """
        Build the execution of an attempt, in the cube frame.

        A solved attempt closes on the AUF the reference solution leaves
        out, the one a solver does without thinking: without it more than
        half the PLL cases would never complete their step.

        A DNF plays ``dnf_moves`` when the file names them, otherwise the
        reference solution deprived of its last move: the step stays
        unsolved, which is what the trainer flags, and the missing move
        feeds the rater the way a real fumble would.

        Args:
            training: The attempt being replayed.

        Returns:
            The moves to execute, translated into the cube frame.

        """
        reference = self.trainer.fsrs_reference_solution

        if training.get('outcome') == DNF_OUTCOME:
            dnf_moves = training.get('dnf_moves')
            if dnf_moves:
                return self.cube_frame(parse_moves(dnf_moves))

            return self.truncated_execution(
                self.complete_execution(reference),
            )

        return self.complete_execution(reference)

    def completes_step(self, execution: Algorithm) -> bool:
        """
        Check whether an execution leaves the trainer's step solved.

        Args:
            execution: Cube-frame moves applied to the scrambled state.

        Returns:
            True when the trainer would see its step completed.

        """
        cube = VCube(self.trainer.facelets_scrambled, size=3, check=False)
        cube.rotate(execution)

        return self.trainer.step_is_completed(cube.state)

    def truncated_execution(self, execution: Algorithm) -> Algorithm:
        """
        Shorten an execution until it no longer completes the step.

        Dropping the last move alone would not always do: a trailing AUF
        leaves an orientation step solved, being blind to the U angle,
        and a trailing rotation leaves the cube untouched. Moves come off
        the end until the trainer would really flag the attempt, which is
        the shortest fumble a DNF can be made of.

        Args:
            execution: The cube-frame execution completing the step.

        Returns:
            The longest prefix of it leaving the step unsolved.

        """
        shortened = execution
        while shortened and self.completes_step(shortened):
            shortened = Algorithm(shortened[:-1])

        return shortened

    def complete_execution(self, solution: Algorithm) -> Algorithm:
        """
        Build the execution completing the step, AUFs included.

        A permutation algorithm expects the last layer at a given angle
        and rarely leaves it aligned on the cube: the solver brackets it
        with U turns that belong to no algorithm. Those are deliberately
        absent from the reference solution, which the FSRS rater compares
        move counts against — an AUF is execution, not knowledge — and
        ``compute_pre_aufs`` finds none at all when the algorithm carries
        rotations, so both sides are searched here.

        The search runs on the cube state rather than on the algorithm,
        and against the trainer's own criterion: what has to be emitted
        is whatever leaves the trainer seeing its step solved.

        Args:
            solution: The moves as a solver reads them.

        Returns:
            The cube-frame execution completing the step, or the plain
            translation of the solution when nothing does.

        """
        aufs = ('', 'U', "U'", 'U2')
        turns = {
            auf: self.cube_frame(parse_moves(auf)) if auf else Algorithm()
            for auf in aufs
        }

        for execution in self.execution_readings(solution):
            for pre in aufs:
                for post in aufs:
                    candidate = Algorithm(
                        [*turns[pre], *execution, *turns[post]],
                    )

                    if self.completes_step(candidate):
                        return candidate

        return self.cube_frame(solution)

    def gesture_moves(self, finish_moves: str) -> list[TimedMove]:
        """
        Translate a save gesture into the cube frame.

        Gestures are read in the user frame, the one the trainer prints
        its algorithms in, so the file says what the solver would do:
        ``U U'`` is the U face of the printed cube, whatever orientation
        the configuration turns it into.

        Args:
            finish_moves: The gesture, as written in the file.

        Returns:
            The gesture moves, timed as written, in the cube frame.

        """
        return timed_moves(self.cube_frame(parse_moves(finish_moves)))

    async def run_schedule(self) -> None:
        """Replay every attempt of the file, looping when asked to."""
        while 42:
            for training in self.replay['trainings']:
                await self.run_training(training)

            if not self.replay.get('loop', False):
                break

    async def run_training(self, training: TrainerReplayDict) -> None:
        """
        Replay one attempt: setup, execution, then the save gesture.

        Args:
            training: The attempt to replay.

        """
        await self.wait_for_state('scrambling')
        await asyncio.sleep(training.get('start_delay', DEFAULT_START_DELAY))

        await self.play_moves(
            paced_moves(
                self.scramble_algorithm(),
                training.get('scramble_pace', HUMAN_SCRAMBLE_PACE_MS),
            ),
        )

        await self.wait_for_state('scrambled')

        # The trainer times from the first move on, so this pause sits
        # outside the recorded solve: it paces the display, not the score.
        await asyncio.sleep(training.get('recognition', DEFAULT_RECOGNITION))

        # The step completion is only watched from the solving state on,
        # and the first move is what gets the timer there: emitting the
        # rest before would leave the stopwatch running forever.
        await self.play_moves(
            paced_moves(
                self.solution_algorithm(training),
                training.get('solve_pace', DEFAULT_SOLVE_PACE_MS),
                training.get('pauses'),
            ),
            gate='solving',
        )

        if training.get('outcome') == DNF_OUTCOME:
            # An unsolved step never completes on its own: only a key
            # press ends the stopwatch, which is what a DNF really is.
            await asyncio.sleep(training.get('dnf_delay', DEFAULT_DNF_DELAY))
            self.trainer.stop_solve()

        finish_moves = training.get('finish_moves')
        if finish_moves:
            await self.play_save_gesture(
                self.gesture_moves(finish_moves),
                training.get('save_delay', DEFAULT_SAVE_DELAY),
            )


def build_replay_interface(
        queue: asyncio.Queue,  # type: ignore[type-arg]
        replay: ReplayPayload,
        timer: TimerStateProvider,
) -> BaseReplayInterface:
    """
    Build the replay interface the payload calls for.

    The root key tells the two apart, and each loader already refuses the
    other one, so a trainer payload can only reach here from the train
    command, on a Trainer.

    Args:
        queue: Event queue consumed by the Bluetooth consumer.
        replay: The validated payload to replay.
        timer: The timer or trainer driving the phases.

    Returns:
        The interface replaying that payload.

    """
    if 'trainings' in replay:
        return TrainerReplayInterface(
            queue,
            cast('TrainerReplayFileDict', replay),
            cast('TrainerStateProvider', timer),
        )

    return ReplayInterface(queue, replay, timer)
