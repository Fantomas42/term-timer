import logging
import math
from dataclasses import dataclass
from typing import TypedDict

from term_timer.bluetooth.types import QuaternionDict
from term_timer.bluetooth.types import VelocityDict

logger = logging.getLogger(__name__)

# Quaternion math constants for rotation detection
QUATERNION_EPSILON = 1e-10
NO_ROTATION_THRESHOLD = 0.9999


class RotationResult(TypedDict):
    """Result of rotation detection."""
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
        """Create quaternion from dict with coordinate transform.

        Applies the same Y↔Z swap and Y negation used in the OpenGL cube
        visualization to ensure detected rotations match the display.
        """
        qw, qx, qy, qz = q['w'], q['x'], q['y'], q['z']
        # Apply coordinate system transformation matching OpenGL cube
        # This swaps Y and Z axes and negates Y to match display orientation
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
    """Detects cube rotations from gyroscope quaternion data."""

    def __init__(
        self,
        rotation_threshold: float = 70.0,
        time_window: float = 0.5,
        velocity_threshold: float = 5.0,
        velocity_scale: float = 1.0,
    ) -> None:
        self.rotation_threshold = rotation_threshold
        self.time_window = time_window
        self.velocity_threshold = velocity_threshold
        self.velocity_scale = velocity_scale
        self.reference_quaternion: Quaternion | None = None
        self.last_quaternion: Quaternion | None = None
        self.last_timestamp: float = 0.0
        self.last_velocity_magnitude: float = 0.0
        self.last_detection_timestamp: float = 0.0
        self.rotations: list[str] = []

    def process_gyro_event(
        self,
        quaternion_dict: QuaternionDict,
        timestamp: float,
    ) -> RotationResult | None:
        """Process a gyro event and return detected rotation if any.

        Uses a reference quaternion approach: accumulates rotation from a
        reference point until threshold is reached, then resets the reference.
        This works better with low-frequency gyro data (12.5Hz).
        """
        current_quat = Quaternion.from_dict(quaternion_dict)

        # Initialize on first call
        if self.reference_quaternion is None:
            self.reference_quaternion = current_quat
            self.last_quaternion = current_quat
            self.last_timestamp = timestamp
            return None

        # Calculate accumulated rotation from reference point
        rotation_result = self.calculate_rotation(
            self.reference_quaternion,
            current_quat,
        )

        # Update last seen state
        self.last_quaternion = current_quat
        self.last_timestamp = timestamp

        if rotation_result:
            # Rotation detected! Reset reference to current position
            self.rotations.append(rotation_result['rotation'])
            self.last_detection_timestamp = timestamp
            self.reference_quaternion = current_quat
            return rotation_result

        # No rotation detected yet - check if we should reset reference
        # to avoid accumulating drift over time
        time_since_last_detection = timestamp - self.last_detection_timestamp
        if (
            self.last_detection_timestamp > 0
            and time_since_last_detection > self.time_window * 2
        ):
            # Been a while since last detection, reset reference to avoid drift
            self.reference_quaternion = current_quat

        return None

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

    def process_gyro_event_with_velocity(
        self,
        quaternion_dict: QuaternionDict,
        velocity: VelocityDict,
        timestamp: float,
    ) -> RotationResult | None:
        """Process a gyro event with velocity data for enhanced detection.

        Uses a reference quaternion approach: accumulates rotation from a
        reference point until threshold is reached, then resets the reference.
        Velocity data is used to filter out drift and validate rotations.

        Args:
            quaternion_dict: Current orientation quaternion
            timestamp: Event timestamp
            velocity: Angular velocity dict with 'x', 'y', 'z' keys

        Returns:
            RotationResult if rotation detected, None otherwise
        """
        current_quat = Quaternion.from_dict(quaternion_dict)

        # Transform velocity to match quaternion coordinate system
        # Apply same Y↔Z swap and Y negation as quaternion
        vx, vy, vz = velocity['x'], velocity['y'], velocity['z']
        vx_t, vy_t, vz_t = vx, vz, -vy  # Same transform as quaternion

        # Apply scale factor and calculate magnitude
        vx_scaled = vx_t * self.velocity_scale
        vy_scaled = vy_t * self.velocity_scale
        vz_scaled = vz_t * self.velocity_scale
        velocity_magnitude = math.sqrt(
            vx_scaled**2 + vy_scaled**2 + vz_scaled**2,
        )

        # Initialize on first call
        if self.reference_quaternion is None:
            self.reference_quaternion = current_quat
            self.last_quaternion = current_quat
            self.last_timestamp = timestamp
            self.last_velocity_magnitude = velocity_magnitude
            logger.debug(
                'Velocity init: mag=%.2f (raw: %.2f, %.2f, %.2f)',
                velocity_magnitude,
                vx,
                vy,
                vz,
            )
            return None

        # Calculate accumulated rotation from reference point
        rotation_result = self.calculate_rotation(
            self.reference_quaternion,
            current_quat,
        )

        # Velocity-based filtering and enhancement
        velocity_active = velocity_magnitude > self.velocity_threshold

        logger.debug(
            'Velocity check: mag=%.2f, threshold=%.2f, active=%s, '
            'quat_rotation=%s',
            velocity_magnitude,
            self.velocity_threshold,
            velocity_active,
            rotation_result['rotation'] if rotation_result else None,
        )

        # Strategy: Use velocity as a gate
        # - If velocity is low, reject quaternion-detected rotations
        #   (likely drift)
        # - If velocity is high, accept quaternion detection
        # - Use velocity direction to validate axis when available
        if rotation_result:
            if not velocity_active:
                # Quaternion detected rotation but velocity is too low
                # This is likely drift or slow manual reorientation
                logger.debug(
                    'Rejecting rotation %s: velocity too low (%.2f < %.2f)',
                    rotation_result['rotation'],
                    velocity_magnitude,
                    self.velocity_threshold,
                )
                rotation_result = None
            else:
                # Velocity confirms the rotation
                # Optionally validate that velocity axis aligns with
                # rotation axis
                abs_vx = abs(vx_scaled)
                abs_vy = abs(vy_scaled)
                abs_vz = abs(vz_scaled)

                # Determine dominant velocity axis
                velocity_axis = None
                if abs_vx > abs_vy and abs_vx > abs_vz:
                    velocity_axis = 'x'
                elif abs_vy > abs_vx and abs_vy > abs_vz:
                    velocity_axis = 'y'
                elif abs_vz > abs_vx and abs_vz > abs_vy:
                    velocity_axis = 'z'

                rotation_axis = rotation_result['rotation'][0]

                # Check if axes align (allow some tolerance)
                if velocity_axis and velocity_axis != rotation_axis:
                    # Axes don't align - reduce confidence or reject
                    max_vel_component = max(abs_vx, abs_vy, abs_vz)
                    second_max = sorted([abs_vx, abs_vy, abs_vz])[-2]

                    # If velocity is ambiguous (two axes similar), keep it
                    if max_vel_component < second_max * 1.5:
                        logger.debug(
                            'Velocity axis ambiguous, accepting rotation %s',
                            rotation_result['rotation'],
                        )
                    else:
                        logger.debug(
                            'Velocity axis mismatch: velocity=%s, rotation=%s, '
                            'rejecting',
                            velocity_axis,
                            rotation_axis,
                        )
                        rotation_result = None
                else:
                    logger.debug(
                        'Velocity confirms rotation %s (axis=%s)',
                        rotation_result['rotation'],
                        velocity_axis,
                    )

        # Update last seen state
        self.last_quaternion = current_quat
        self.last_timestamp = timestamp
        self.last_velocity_magnitude = velocity_magnitude

        if rotation_result:
            # Rotation detected! Reset reference to current position
            self.rotations.append(rotation_result['rotation'])
            self.last_detection_timestamp = timestamp
            self.reference_quaternion = current_quat
            return rotation_result

        # No rotation detected yet - check if we should reset reference
        # to avoid accumulating drift over time
        time_since_last_detection = timestamp - self.last_detection_timestamp
        if (
            self.last_detection_timestamp > 0
            and time_since_last_detection > self.time_window * 2
        ):
            # Been a while since last detection, reset reference to avoid drift
            self.reference_quaternion = current_quat

        return None
