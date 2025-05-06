class Driver:
    service_uid = ''
    state_characteristic_uid = ''
    command_characteristic_uid = ''

    disable_gyro = True

    def __init__(self, client, device):
        self.client = client
        self.device = device

        self.events = []
        self.cube_timestamp = 0

        self.cypher = self.init_cypher()

    def init_cypher(self):
        return None

    def send_command_handler(self, command: str) -> bool:
        raise NotImplementedError

    def notification_handler(self, sender, data) -> bool:
        raise NotImplementedError

    def add_event(self, store, event):
        store.append(event)
        self.events.append(event)
