import logging
import math
from dataclasses import dataclass
from typing import Final

from term_timer.bluetooth.types import QuaternionDict
from term_timer.bluetooth.types import RotationResult
from term_timer.config import ROTATION_THRESHOLD

logger = logging.getLogger(__name__)

# Quaternion math constants for rotation detection
QUATERNION_EPSILON: Final = 1e-10
NO_ROTATION_THRESHOLD: Final = 0.9999


@dataclass
class Quaternion:
    w: float
    x: float
    y: float
    z: float

    @classmethod
    def from_dict_raw(cls, q: QuaternionDict) -> 'Quaternion':
        """
        Create quaternion from dict in raw sensor frame.

        Used for normalization calculations
        before applying coordinate transform.
        """
        return cls(w=q['w'], x=q['x'], y=q['y'], z=q['z'])

    def conjugate(self) -> 'Quaternion':
        return Quaternion(self.w, -self.x, -self.y, -self.z)

    def multiply(self, other: 'Quaternion') -> 'Quaternion':
        w = (
            self.w * other.w
            - self.x * other.x
            - self.y * other.y
            - self.z * other.z
        )
        x = (
            self.w * other.x
            + self.x * other.w
            + self.y * other.z
            - self.z * other.y
        )
        y = (
            self.w * other.y
            - self.x * other.z
            + self.y * other.w
            + self.z * other.x
        )
        z = (
            self.w * other.z
            + self.x * other.y
            - self.y * other.x
            + self.z * other.w
        )
        return Quaternion(w, x, y, z)

    def normalize(self) -> 'Quaternion':
        norm = math.sqrt(self.w**2 + self.x**2 + self.y**2 + self.z**2)
        if norm < QUATERNION_EPSILON:
            return Quaternion(1.0, 0.0, 0.0, 0.0)
        return Quaternion(
            self.w / norm,
            self.x / norm,
            self.y / norm,
            self.z / norm,
        )

    def to_axis_angle(self) -> tuple[tuple[float, float, float], float]:
        """Convert quaternion to axis-angle representation."""
        # Normalize first
        q = self.normalize()

        # Handle the case where w is very close to 1 (no rotation)
        if abs(q.w) > NO_ROTATION_THRESHOLD:
            return ((1.0, 0.0, 0.0), 0.0)

        # Calculate angle
        angle = 2 * math.acos(max(-1.0, min(1.0, q.w)))

        # Calculate axis
        s = math.sqrt(1 - q.w * q.w)
        if s < QUATERNION_EPSILON:
            # Axis is arbitrary for no rotation
            return ((1.0, 0.0, 0.0), 0.0)

        axis = (q.x / s, q.y / s, q.z / s)
        return (axis, angle)


class RotationDetector:
    """
    Detects cube rotations from gyroscope quaternion data.

    This detector tracks the absolute orientation of the cube and detects
    rotations by comparing the current orientation against the orientation
    at the time of the last detected rotation.
    """

    def __init__(self, rotation_threshold: float = ROTATION_THRESHOLD) -> None:
        self.rotation_threshold = rotation_threshold

        # Initial orientation used to normalize all measurements
        self.initial_orientation: Quaternion | None = None

        # Orientation at the last detected rotation (or initial orientation)
        self.last_rotation_orientation: Quaternion | None = None

    def calculate_rotation(
            self,
            q1: Quaternion,
            q2: Quaternion,
    ) -> RotationResult | None:
        """Calculate rotation between two quaternions."""
        # Calculate relative rotation: q_rel = q2 * q1^-1
        q_rel = q2.multiply(q1.conjugate()).normalize()

        # Convert to axis-angle
        axis, angle = q_rel.to_axis_angle()
        angle_deg = math.degrees(angle)

        # Check if rotation exceeds threshold
        if abs(angle_deg) < self.rotation_threshold:
            return None

        # Transform axis if requested (Y↔Z swap for display coordinates)
        ax, ay, az = axis
        ay, az = az, -ay  # Y→Z, Z→-Y

        abs_x, abs_y, abs_z = abs(ax), abs(ay), abs(az)

        # Determine rotation type based on dominant axis
        rotation_type = None

        if abs_x > abs_y and abs_x > abs_z:
            # X-axis rotation
            rotation_type = "x'" if ax > 0 else 'x'
        elif abs_y > abs_x and abs_y > abs_z:
            # Y-axis rotation
            rotation_type = "y'" if ay > 0 else 'y'
        elif abs_z > abs_x and abs_z > abs_y:
            # Z-axis rotation
            rotation_type = "z'" if az > 0 else 'z'

        if rotation_type is None:
            return None

        # Check if it's a double rotation (close to 180 degrees)
        if abs(abs(angle_deg) - 180) < 30:
            if rotation_type.endswith("'"):
                rotation_type = rotation_type[0] + '2'
            else:
                rotation_type += '2'

        return {
            'rotation': rotation_type,
            'angle_deg': angle_deg,
        }

    def process_gyro_event(
            self,
            quaternion_dict: QuaternionDict,
    ) -> RotationResult | None:
        """
        Process a gyro event and return detected rotation if any.

        Tracks the absolute orientation of the cube and detects rotations
        by comparing current orientation against the orientation at the last
        detected rotation. This approach naturally accumulates slow rotations
        and works well in real-time without needing time windows.

        The first quaternion received defines the neutral/identity orientation.
        All rotations are computed in the raw sensor frame, then the rotation
        axis is transformed to match the display coordinate system.
        """
        # Work entirely in raw sensor frame
        absolute_raw = Quaternion.from_dict_raw(quaternion_dict)

        # Initialize with first quaternion as neutral orientation
        if (
                self.initial_orientation is None
                or self.last_rotation_orientation is None
        ):
            self.initial_orientation = absolute_raw
            self.last_rotation_orientation = Quaternion(1.0, 0.0, 0.0, 0.0)
            return None

        # Normalize in raw sensor frame: q_normalized = q_initial^-1 * q_current
        # This transforms from world frame to cube's local frame
        current_orientation = self.initial_orientation.conjugate().multiply(
            absolute_raw,
        ).normalize()

        rotation_result = self.calculate_rotation(
            self.last_rotation_orientation,
            current_orientation,
        )

        if rotation_result:
            self.last_rotation_orientation = current_orientation
            return rotation_result

        return None
