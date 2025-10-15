import logging
import math
from dataclasses import dataclass
from typing import TypedDict

from term_timer.bluetooth.types import QuaternionDict

logger = logging.getLogger(__name__)

# Quaternion math constants for rotation detection
QUATERNION_EPSILON = 1e-10
NO_ROTATION_THRESHOLD = 0.9999


class RotationResult(TypedDict):
    """
    Result of rotation detection.
    """
    rotation: str
    angle_deg: float
    confidence: float


@dataclass
class Quaternion:
    w: float
    x: float
    y: float
    z: float

    @classmethod
    def from_dict(cls, q: QuaternionDict) -> 'Quaternion':
        """
        Create quaternion from dict with coordinate transform.

        Applies the same Y↔Z swap and Y negation used in the OpenGL cube
        visualization to ensure detected rotations match the display.
        """
        qw, qx, qy, qz = q['w'], q['x'], q['y'], q['z']

        return cls(w=qw, x=qx, y=qz, z=-qy)

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

    def __init__(self, rotation_threshold: float = 70.0) -> None:
        self.rotation_threshold = rotation_threshold

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

        # Determine which axis is dominant
        ax, ay, az = axis
        abs_x, abs_y, abs_z = abs(ax), abs(ay), abs(az)

        # Determine rotation type based on dominant axis
        rotation_type = None
        confidence = 0.0

        if abs_x > abs_y and abs_x > abs_z:
            # X-axis rotation
            rotation_type = 'x' if ax > 0 else "x'"
            confidence = abs_x
        elif abs_y > abs_x and abs_y > abs_z:
            # Y-axis rotation
            rotation_type = 'y' if ay > 0 else "y'"
            confidence = abs_y
        elif abs_z > abs_x and abs_z > abs_y:
            # Z-axis rotation
            rotation_type = 'z' if az > 0 else "z'"
            confidence = abs_z

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
            'confidence': confidence,
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
        """
        current_orientation = Quaternion.from_dict(quaternion_dict)

        if self.last_rotation_orientation is None:
            self.last_rotation_orientation = current_orientation
            return None

        rotation_result = self.calculate_rotation(
            self.last_rotation_orientation,
            current_orientation,
        )

        if rotation_result:
            self.last_rotation_orientation = current_orientation
            return rotation_result

        return None
