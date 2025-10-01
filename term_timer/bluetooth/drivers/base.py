from bleak import BleakClient


class Driver:
    service_uid = ''
    state_characteristic_uid = ''
    command_characteristic_uid = ''

    disable_gyro = True

    def __init__(self, client: BleakClient) -> None:
        self.client = client

        self.events: list[dict[str, object]] = []
        self.cypher = self.init_cypher()

    def init_cypher(self) -> None:
        pass

    def send_command_handler(self, command: str) -> bool:
        raise NotImplementedError

    def event_handler(self, sender, data) -> list[dict[str, object]]:
        raise NotImplementedError

    def add_event(self,
                  store: list[dict[str, object]],
                  event: dict[str, object] | list[dict[str, object]]) -> None:
        if isinstance(event, list):
            store.extend(event)
            self.events.extend(event)
        else:
            store.append(event)
            self.events.append(event)
