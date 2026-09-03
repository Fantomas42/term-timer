"""Type definitions for bluetooth event payloads."""
from datetime import datetime
from typing import TYPE_CHECKING
from typing import TypedDict

if TYPE_CHECKING:
    from collections.abc import Awaitable
    from collections.abc import Callable

    from term_timer.bluetooth.message import GanProtocolMessage

    MoveEventDictList = list['MoveEventDict']

    # Signature shared by every message handler of every driver.
    # The handlers are resolved by name through Driver.MESSAGE_HANDLERS,
    # so nothing but this alias documents what they receive.
    MessageHandler = Callable[
        [GanProtocolMessage, int, datetime],
        Awaitable[list['EventDict']],
    ]


class MoveInfo(TypedDict):
    """Representing a move with timing information."""

    move: str
    time: int


class RotationResult(TypedDict):
    """Result of rotation detection."""

    rotation: str
    angle_deg: float


class QuaternionDict(TypedDict):
    """Quaternion orientation data."""

    x: float
    y: float
    z: float
    w: float


class VelocityDict(TypedDict):
    """Angular velocity data."""

    x: float
    y: float
    z: float


class CubeStateDict(TypedDict):
    """Cube state with corner/edge permutation and orientation."""

    CP: list[int]
    CO: list[int]
    EP: list[int]
    EO: list[int]


class BaseEventDict(TypedDict):
    """Base fields present in all events."""

    event: str
    clock: int
    timestamp: datetime


class GyroEventDict(BaseEventDict):
    """Gyroscope event payload."""

    quaternion: QuaternionDict
    velocity: VelocityDict


class GyroEventDictNoVelocity(BaseEventDict):
    """Gyroscope event payload without velocity (Moyu Weilong)."""

    quaternion: QuaternionDict


class MoveEventDict(BaseEventDict):
    """Move event payload."""

    serial: int
    local_timestamp: datetime | None
    cube_timestamp: float | None
    face: int
    direction: int
    move: str


class RotationEventDict(BaseEventDict):
    """Rotation event payload."""

    move: str


class FaceletsEventDict(BaseEventDict):
    """Facelets event payload."""

    serial: int
    facelets: str
    state: CubeStateDict


class FaceletsEventDictNoState(BaseEventDict):
    """Facelets event payload without state (Moyu Weilong)."""

    serial: int
    facelets: str


class HardwareEventDict(BaseEventDict):
    """Hardware info event payload."""

    hardware_name: str
    hardware_version: str
    software_version: str
    gyroscope_enabled: bool
    gyroscope_ready: bool
    gyroscope_supported: bool
    restart_no_power: int


class HardwareEventPartialDict(BaseEventDict):
    """Partial hardware info event payload (Gen4 sends info in parts)."""

    product_date: str


class HardwareEventNameOnlyDict(BaseEventDict):
    """Hardware name only event payload (Gen4)."""

    hardware_name: str
    gyroscope_supported: bool


class HardwareEventVersionOnlyDict(BaseEventDict):
    """Hardware version only event payload (Gen4)."""

    hardware_version: str


class HardwareEventSoftwareVersionOnlyDict(BaseEventDict):
    """Software version only event payload (Gen4)."""

    software_version: str


class HardwareEventMoyuDict(BaseEventDict):
    """Hardware info event payload for Moyu."""

    hardware_name: str
    hardware_version: str
    software_version: str
    gyroscope_enabled: bool
    gyroscope_ready: bool
    gyroscope_supported: bool
    serial: int


class BatteryEventDict(BaseEventDict):
    """Battery level event payload."""

    level: int
    charging_state: int


class ResetEventDict(BaseEventDict):
    """Reset event payload."""

    result: int


class SolvedEventDict(BaseEventDict):
    """Solved event payload."""

    cube_timestamp: int


class DisconnectEventDict(BaseEventDict):
    """Disconnect event payload."""


class GyroConfigEventDict(BaseEventDict):
    """Gyro configuration event payload (Moyu, GAN Gen4)."""

    gyroscope_enabled: bool
    gyroscope_ready: bool
    gyroscope_supported: bool


# Union type for all possible event payloads
EventDict = (
    GyroEventDict
    | GyroEventDictNoVelocity
    | MoveEventDict
    | FaceletsEventDict
    | FaceletsEventDictNoState
    | HardwareEventDict
    | HardwareEventPartialDict
    | HardwareEventNameOnlyDict
    | HardwareEventVersionOnlyDict
    | HardwareEventSoftwareVersionOnlyDict
    | HardwareEventMoyuDict
    | BatteryEventDict
    | SolvedEventDict
    | DisconnectEventDict
    | GyroConfigEventDict
    | ResetEventDict
)
