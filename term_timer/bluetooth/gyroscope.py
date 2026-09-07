"""Gyroscope data processing and rotation detection for smart cubes."""
import logging
import math
from dataclasses import dataclass
from typing import Final

from term_timer.bluetooth.annotations import QuaternionDict
from term_timer.bluetooth.annotations import RotationResult
from term_timer.config import ROTATION_THRESHOLD

logger = logging.getLogger(__name__)

# Quaternion math constants for rotation detection
QUATERNION_EPSILON: Final = 1e-10
NO_ROTATION_THRESHOLD: Final = 0.9999


@dataclass(slots=True)
class Quaternion:
    """
    Represents a quaternion for 3D rotation calculations.

    A quaternion is a mathematical construct used to represent rotations in
    3D space. It consists of four components: a scalar part (w) and a
    vector part (x, y, z).

    Attributes:
        w: Scalar component of the quaternion.
        x: X component of the vector part.
        y: Y component of the vector part.
        z: Z component of the vector part.

    """

    w: float
    x: float
    y: float
    z: float

    @classmethod
    def from_dict_raw(cls, q: QuaternionDict) -> 'Quaternion':
        """
        Create a quaternion from a dictionary.

        Args:
            q: Dictionary containing quaternion components with keys 'w',
                'x', 'y', 'z'.

        Returns:
            Quaternion instance with components from the input dictionary.

        """
        return cls(w=q['w'], x=q['x'], y=q['y'], z=q['z'])

    @classmethod
    def from_axis_angle(
            cls,
            axis: tuple[float, float, float],
            angle: float) -> 'Quaternion':
        """
        Build a unit quaternion rotating by `angle` radians around `axis`.

        Args:
            axis: Unit vector the rotation turns around.
            angle: Rotation angle, in radians.

        Returns:
            Quaternion instance representing that rotation.

        """
        half = angle / 2
        s = math.sin(half)
        ax, ay, az = axis

        return cls(w=math.cos(half), x=ax * s, y=ay * s, z=az * s)

    def to_dict(self) -> QuaternionDict:
        """
        Export this quaternion as a dictionary.

        Returns:
            Dictionary containing the quaternion components, keyed 'w',
            'x', 'y', 'z'.

        """
        return {'w': self.w, 'x': self.x, 'y': self.y, 'z': self.z}

    def conjugate(self) -> 'Quaternion':
        """
        Compute the conjugate of this quaternion.

        The conjugate of a quaternion (w, x, y, z) is (w, -x, -y, -z).
        For unit quaternions, the conjugate represents the inverse rotation.

        Returns:
            New Quaternion instance representing the conjugate.

        """
        return Quaternion(self.w, -self.x, -self.y, -self.z)

    def multiply(self, other: 'Quaternion') -> 'Quaternion':
        """
        Multiply this quaternion with another quaternion.

        Quaternion multiplication combines two rotations. The operation is
        non-commutative, meaning order matters.

        Args:
            other: The quaternion to multiply with.

        Returns:
            New Quaternion representing the combined rotation.

        """
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
        """
        Normalize this quaternion to unit length.

        A normalized quaternion has a magnitude of 1 and represents a pure
        rotation without scaling. If the magnitude is near zero, returns
        the identity quaternion.

        Returns:
            New Quaternion with unit length, or identity if magnitude is
            near zero.

        """
        norm = math.sqrt(self.w**2 + self.x**2 + self.y**2 + self.z**2)
        if norm < QUATERNION_EPSILON:
            return Quaternion(1.0, 0.0, 0.0, 0.0)
        inv_norm = 1.0 / norm
        return Quaternion(
            self.w * inv_norm,
            self.x * inv_norm,
            self.y * inv_norm,
            self.z * inv_norm,
        )

    def to_axis_angle(self) -> tuple[tuple[float, float, float], float]:
        """
        Convert quaternion to axis-angle representation.

        Assumes the quaternion is already normalized (unit length). Callers
        must normalize before calling this method.

        The axis-angle representation expresses a rotation as a unit vector
        (the axis) and an angle of rotation around that axis.

        Returns:
            Tuple containing the rotation axis as (x, y, z) and the rotation
            angle in radians. Returns ((1.0, 0.0, 0.0), 0.0) for negligible
            rotations.

        """
        # Handle the case where w is very close to 1 (no rotation)
        if abs(self.w) > NO_ROTATION_THRESHOLD:
            return ((1.0, 0.0, 0.0), 0.0)

        # Calculate angle
        angle = 2 * math.acos(max(-1.0, min(1.0, self.w)))

        # Calculate axis
        s = math.sqrt(1 - self.w * self.w)
        if s < QUATERNION_EPSILON:
            return ((1.0, 0.0, 0.0), 0.0)

        axis = (self.x / s, self.y / s, self.z / s)
        return (axis, angle)


class RotationDetector:
    """
    Detects cube rotations from gyroscope quaternion data.

    This detector tracks the absolute orientation of the cube and detects
    rotations by comparing the current orientation against the orientation
    at the time of the last detected rotation.

    Attributes:
        rotation_threshold: Minimum rotation angle in degrees to detect.
        initial_orientation: First quaternion received, used as neutral
            orientation for normalizing all subsequent measurements.
        last_rotation_orientation: Orientation at the last detected rotation,
            used as reference point for detecting the next rotation.

    """

    def __init__(self, rotation_threshold: float = ROTATION_THRESHOLD) -> None:
        """
        Initialize the rotation detector.

        Args:
            rotation_threshold: Minimum rotation angle in degrees required
                to register as a detected rotation. Defaults to the value
                from config.ROTATION_THRESHOLD.

        """
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
        """
        Calculate the rotation between two quaternion orientations.

        Computes the relative rotation from q1 to q2, converts it to
        axis-angle representation, and determines the rotation type using
        cube notation (x, y, z with optional prime or 2 suffix).

        Args:
            q1: Starting orientation quaternion.
            q2: Ending orientation quaternion.

        Returns:
            Dictionary with 'rotation' (cube notation string) and 'angle_deg'
            (rotation angle in degrees), or None if rotation is below the
            threshold.

        """
        # Calculate relative rotation: q_rel = q2 * q1^-1
        q_rel = q2.multiply(q1.conjugate()).normalize()

        # Convert to axis-angle
        axis, angle = q_rel.to_axis_angle()
        angle_deg = math.degrees(angle)

        # Check if rotation exceeds threshold
        if abs(angle_deg) < self.rotation_threshold:
            return None

        ax, ay, az = axis

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
        Process a gyroscope event and detect cube rotations.

        Tracks the absolute orientation of the cube and detects rotations
        by comparing current orientation against the orientation at the last
        detected rotation. This approach naturally accumulates slow rotations
        and works well in real-time without needing time windows.

        The first quaternion received defines the neutral/identity
        orientation. The quaternion is expected to already be in the
        canonical cube frame (+X=R, +Y=U, +Z=F) — the driver applies
        its `GYROSCOPE_BASIS` at decode time, so nothing here corrects
        for the sensor's own coordinate system.

        Args:
            quaternion_dict: Dictionary containing quaternion components
                from the gyroscope sensor.

        Returns:
            Dictionary with rotation information if a rotation exceeding the
            threshold is detected, None otherwise. On first call, returns
            None while initializing the reference orientation.

        """
        absolute_raw = Quaternion(
            quaternion_dict['w'],
            quaternion_dict['x'],
            quaternion_dict['y'],
            quaternion_dict['z'],
        )

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
