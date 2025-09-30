class Driver:
    service_uid = ''
    state_characteristic_uid = ''
    command_characteristic_uid = ''

    disable_gyro = True

    def __init__(self, client):
        self.client = client

        self.events = []
        self.cypher = self.init_cypher()

    def init_cypher(self):
        return None

    def send_command_handler(self, command: str) -> bool:
        raise NotImplementedError

    def notification_handler(self, sender, data) -> bool:
        raise NotImplementedError

    def add_event(self, store, event):
        if isinstance(event, list):
            store.extend(event)
            self.events.extend(event)
        else:
            store.append(event)
            self.events.append(event)
