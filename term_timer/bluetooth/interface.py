"""Bluetooth cube interface for scanning, connecting, and communication."""
import asyncio
import logging
from asyncio import Queue
from typing import Final
from typing import Self
from typing import cast

from bleak import BleakClient
from bleak import BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.exc import BleakDBusError
from bleak.exc import BleakError

from term_timer.bluetooth.annotations import EventDict
from term_timer.bluetooth.constants import PREFIX
from term_timer.bluetooth.drivers.base import Driver
from term_timer.bluetooth.drivers.gan_gen2 import GanGen2Driver
from term_timer.bluetooth.drivers.gan_gen3 import GanGen3Driver
from term_timer.bluetooth.drivers.gan_gen4 import GanGen4Driver
from term_timer.bluetooth.drivers.moyu import MoyuWeilong10Driver
from term_timer.config import DEBUG
from term_timer.exceptions import CubeNotFoundError

logger = logging.getLogger(__name__)

DRIVERS: Final[list[type[Driver]]] = [
    GanGen2Driver,
    GanGen3Driver,
    GanGen4Driver,
    MoyuWeilong10Driver,
]


class BluetoothInterface:
    """
    Manages Bluetooth connection and communication with smart cubes.

    This class handles device scanning, connection management, and bidirectional
    communication with Bluetooth-enabled speedcubing smart cubes. It supports
    multiple cube brands through a driver-based architecture.

    Attributes:
        client: The BLE client for Bluetooth communication, or None if not
            connected.
        driver: The cube-specific driver for handling communication protocol,
            or None if not initialized.
        scan_timeout: Maximum seconds to scan for Bluetooth devices.
        connect_timeout: Maximum seconds to wait for connection establishment.

    """

    client: BleakClient | None = None
    driver: Driver | None = None

    scan_timeout: int = 5
    connect_timeout: int = 5

    def __init__(self, queue: Queue[list[EventDict] | None]) -> None:
        """
        Initialize the Bluetooth interface with an event queue.

        Args:
            queue: Queue for delivering cube events to the application. Events
                include moves, rotations, and battery status updates.

        """
        self.queue: Queue[list[EventDict] | None] = queue

    async def __aenter__(
            self,
            address: str | None = None,
            filter_name: str | None = None,
            *,
            use_gyroscope: bool,
    ) -> Self:
        """
        Enters async context manager by connecting to a Bluetooth cube.

        Scans for available cubes if no address is provided, establishes a
        connection, identifies the appropriate driver based on the cube's
        service UUID, and starts receiving notifications from the cube.

        Args:
            address: Specific Bluetooth device address to connect to. If None,
                performs a scan to discover available cubes.
            filter_name: Optional name filter to narrow device scan results.
                Only devices containing this string will be selected.
            use_gyroscope: Whether the driver should use gyroscope data.

        Returns:
            The initialized BluetoothInterface instance with an active
            connection and configured driver.

        Raises:
            CubeNotFoundError: No compatible cube found during scan, or
                connection failed, or no compatible driver found for the
                connected device.

        """
        if not address:
            device = await self.scan(filter_name)

            if not device:
                logger.debug(
                    'No Bluetooth cube found.\n'
                    'Make sure a cube is powered on and in pairing mode.',
                )
                raise CubeNotFoundError
            address = device.address

        self.client = BleakClient(address, timeout=self.connect_timeout)

        try:
            await self.client.connect()
        except BleakError as error:
            msg = (
                f'No Bluetooth cube found at { address }.\n'
                'Make sure the cube is powered on and in pairing mode.'
            )
            logger.debug(msg)
            raise CubeNotFoundError from error

        logger.debug(' * Connected: %r', self.client.is_connected)

        for service in self.client.services:
            for driver in DRIVERS:
                if service.uuid == driver.service_uid:
                    logger.debug(' * Using %s driver', driver.__name__)
                    self.driver = driver(
                        self.client,
                        use_gyroscope=use_gyroscope,
                    )
                    break
            if self.driver:
                break

        if not self.driver:
            logger.debug('No driver found')
            raise CubeNotFoundError

        try:
            await self.client.start_notify(
                self.driver.state_characteristic_uid,
                self.notification_handler,
            )
        except BleakDBusError as error:
            logger.debug(
                'start_notify failed: %r'
                ' (cube may be bonded to another device)',
                error,
            )
            raise CubeNotFoundError from error

        return self

    async def __aexit__(self, exc_type: type[BaseException] | None,
                        exc_value: BaseException | None,
                        exc_traceback: object) -> None:
        """Exit async context manager by disconnecting from cube."""
        logger.debug('Disconnect from client')
        # Send an "exit command to the consumer"
        await self.queue.put(None)

        if self.client and self.client.is_connected and self.driver:
            await self.client.stop_notify(
                self.driver.state_characteristic_uid,
            )
            try:
                await asyncio.wait_for(self.client.disconnect(), timeout=0.5)
            except asyncio.TimeoutError:  # noqa: UP041
                logger.debug('Disconnect timed out, leaving cleanup to OS')

    async def notification_handler(self, sender: BleakGATTCharacteristic,
                                   data: bytearray) -> None:
        """
        Handle incoming Bluetooth notifications from the connected cube.

        Processes raw Bluetooth data received from the cube by delegating to
        the appropriate driver for parsing, then queues the resulting events
        for consumption by the application.

        Args:
            sender: The GATT characteristic that sent the notification.
            data: Raw byte data received from the cube containing state changes,
                moves, or other events.

        """
        self.driver = cast('Driver', self.driver)

        events = await self.driver.event_handler(sender, data)

        if DEBUG:
            for event in events:
                logger.debug('Event: %s', event['event'].upper())
        await self.queue.put(events)

    async def send_command(self, command: str) -> bool:
        """
        Send a command to the connected Bluetooth cube.

        Translates a high-level command string into the appropriate protocol
        message using the active driver, then transmits it to the cube via
        Bluetooth GATT characteristic write.

        Args:
            command: High-level command string (e.g., 'reset', 'battery').

        Returns:
            True if the command was successfully sent, False if not connected
            or if the command is not recognized by the driver.

        """
        if not self.client or not self.client.is_connected:
            logger.debug('Command not connected to cube')
            return False

        logger.debug('Sending: %s', command)

        self.driver = cast('Driver', self.driver)
        msg = self.driver.send_command_handler(command)

        if msg is False:
            logger.debug('Unknown command "%s"', command)
            return False

        msg = cast('bytes', msg)
        await self.client.write_gatt_char(
            self.driver.command_characteristic_uid,
            msg,
        )

        return True

    async def scan(self, filter_name: str | None = None) -> BLEDevice | None:
        """
        Scan for available Bluetooth smart cubes in the vicinity.

        Performs a Bluetooth Low Energy scan to discover nearby devices,
        filtering for known smart cube prefixes and optionally matching a
        specific name pattern.

        Args:
            filter_name: Optional name substring to filter discovered devices.
                Only devices whose name contains this string will be returned.

        Returns:
            The first discovered BLE device matching the cube criteria, or None
            if no compatible cube is found within the scan timeout period.

        Raises:
            CubeNotFoundError: Bluetooth adapter error or system-level scanning
                failure occurred.

        """
        logger.debug(
            'Scanning for cube during %ss...',
            self.scan_timeout,
        )
        selected_device = None
        try:
            devices = await BleakScanner.discover(
                timeout=self.scan_timeout,
            )
        except (BleakError, OSError) as error:
            logger.debug(str(error))
            raise CubeNotFoundError from error

        for device in devices:
            name = device.name or 'N/A'
            logger.debug(' * %s %s', device, name)

            for prefix in PREFIX:
                if prefix in name and (not filter_name or filter_name in name):
                    logger.debug(
                        'Found %s cube: %s (%s)',
                        prefix, device.name, device.address,
                    )
                    selected_device = device
                    break
            if selected_device:
                break

        if not selected_device:
            return None

        return selected_device
