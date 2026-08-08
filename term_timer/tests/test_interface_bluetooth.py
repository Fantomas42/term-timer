"""Tests for the gyroscope reconciliation of the Bluetooth mixin."""
import unittest
from unittest.mock import AsyncMock
from unittest.mock import Mock

from term_timer.interface.bluetooth import Bluetooth


class TestReconcileGyroscopeState(unittest.IsolatedAsyncioTestCase):
    """Tests for Bluetooth.reconcile_gyroscope_state."""

    def setUp(self) -> None:
        """Test setup."""
        self.bluetooth = Bluetooth()

        self.interface = Mock()
        self.interface.send_command = AsyncMock()
        self.interface.driver = Mock()

        self.bluetooth.bluetooth_interface = self.interface

    def configure(self, *, wanted: bool,
                  enabled: bool, ready: bool) -> None:
        """Set the user preference and what the cube reports."""
        self.interface.driver.use_gyroscope = wanted
        self.bluetooth.bluetooth_hardware = {
            'gyroscope_enabled': enabled,
            'gyroscope_ready': ready,
        }

    async def test_disables_an_unwanted_gyroscope(self) -> None:
        """Test the cube is told to stop streaming what nobody reads."""
        self.configure(wanted=False, enabled=True, ready=True)

        await self.bluetooth.reconcile_gyroscope_state()

        self.interface.send_command.assert_awaited_once_with(
            'REQUEST_DISABLE_GYRO',
        )

    async def test_enables_a_wanted_gyroscope(self) -> None:
        """Test a cube found with its gyroscope off is turned back on."""
        self.configure(wanted=True, enabled=False, ready=True)

        await self.bluetooth.reconcile_gyroscope_state()

        self.interface.send_command.assert_awaited_once_with(
            'REQUEST_ENABLE_GYRO',
        )

    async def test_says_nothing_when_already_aligned(self) -> None:
        """Test no command is sent when the cube is in the wanted state."""
        self.configure(wanted=True, enabled=True, ready=True)

        await self.bluetooth.reconcile_gyroscope_state()

        self.interface.send_command.assert_not_awaited()

    async def test_says_nothing_when_already_disabled(self) -> None:
        """Test a gyroscope already off is not disabled twice."""
        self.configure(wanted=False, enabled=False, ready=False)

        await self.bluetooth.reconcile_gyroscope_state()

        self.interface.send_command.assert_not_awaited()

    async def test_does_not_enable_a_sensor_reported_not_ready(self) -> None:
        """
        Test nothing is sent to a cube reporting its sensor not ready.

        The guard exists for cubes without a gyroscope at all. On Gen2
        it also covers a sensor this very application turned off, since
        disabling clears the ready bit too: the reconciliation cannot
        undo its own disable within one connection, and relies on the
        cube coming back enabled at the next one.
        """
        self.configure(wanted=True, enabled=False, ready=False)

        await self.bluetooth.reconcile_gyroscope_state()

        self.interface.send_command.assert_not_awaited()

    async def test_says_nothing_without_an_interface(self) -> None:
        """Test the reconciliation is a no-op before any connection."""
        self.bluetooth.bluetooth_interface = None

        await self.bluetooth.reconcile_gyroscope_state()

        self.interface.send_command.assert_not_awaited()

    async def test_says_nothing_without_a_driver(self) -> None:
        """Test the reconciliation is a no-op with no driver bound."""
        self.configure(wanted=False, enabled=True, ready=True)
        self.interface.driver = None

        await self.bluetooth.reconcile_gyroscope_state()

        self.interface.send_command.assert_not_awaited()

    async def test_missing_hardware_report_enables_nothing(self) -> None:
        """
        Test an empty hardware report sends no command.

        The flags are read with a False default, so a reconciliation
        running before the cube described itself must stay silent
        rather than act on what it does not know yet.
        """
        self.interface.driver.use_gyroscope = True
        self.bluetooth.bluetooth_hardware = {}

        await self.bluetooth.reconcile_gyroscope_state()

        self.interface.send_command.assert_not_awaited()
