from collections.abc import Sequence
from typing import ClassVar

from bleak import BleakClient

from term_timer.bluetooth.encrypter import GanGen2CubeEncrypter
from term_timer.bluetooth.types import EventDict


class Driver:
    service_uid: ClassVar[str] = ''
    state_characteristic_uid: ClassVar[str] = ''
    command_characteristic_uid: ClassVar[str] = ''

    disable_gyro: bool = True

    def __init__(self, client: BleakClient) -> None:
        self.client: BleakClient = client

        self.events: list[EventDict] = []
        self.cypher: GanGen2CubeEncrypter = self.init_cypher()

    def init_cypher(self) -> GanGen2CubeEncrypter:
        raise NotImplementedError

    def send_command_handler(self, command: str) -> bytes | bool:
        raise NotImplementedError

    async def event_handler(self, sender: int, data: bytes) -> list[EventDict]:
        raise NotImplementedError

    def add_event(self, store: list[EventDict],
                  event: EventDict | Sequence[EventDict]) -> None:
        if isinstance(event, Sequence):
            store.extend(event)
            self.events.extend(event)
        else:
            store.append(event)
            self.events.append(event)
