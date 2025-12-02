"""Base driver class for Bluetooth cube communication."""

from collections.abc import Sequence
from typing import ClassVar

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic

from term_timer.bluetooth.encrypter import GanGen2CubeEncrypter
from term_timer.bluetooth.types import EventDict


class Driver:
    """
    Base class for Bluetooth smart cube communication drivers.

    Defines the interface for cube-specific protocol implementations.
    Subclasses must implement encryption, command handling, and event
    processing for their specific cube model.
    """

    service_uid: ClassVar[str] = ''
    state_characteristic_uid: ClassVar[str] = ''
    command_characteristic_uid: ClassVar[str] = ''

    def __init__(self, client: BleakClient,
                 *, use_gyroscope: bool) -> None:
        """
        Initialize driver with BleakClient and encryption.

        Args:
            client: The BLE client connection to the cube.
            use_gyroscope: Whether the driver should use gyroscope data.

        """
        self.client: BleakClient = client
        self.use_gyroscope = use_gyroscope

        self.events: list[EventDict] = []
        self.cypher: GanGen2CubeEncrypter = self.init_cypher()

    def init_cypher(self) -> GanGen2CubeEncrypter:
        """Initialize encryption handler for cube communication."""
        raise NotImplementedError

    def send_command_handler(self, command: str) -> bytes | bool:
        """Build command bytes for cube-specific protocol."""
        raise NotImplementedError

    async def event_handler(self, sender: BleakGATTCharacteristic,
                            data: bytearray) -> list[EventDict]:
        """Process incoming notification data from cube."""
        raise NotImplementedError

    def add_event(self, store: list[EventDict],
                  event: EventDict | Sequence[EventDict]) -> None:
        """Add event(s) to both local store and global event list."""
        if isinstance(event, Sequence):
            store.extend(event)
            self.events.extend(event)
        else:
            store.append(event)
            self.events.append(event)
