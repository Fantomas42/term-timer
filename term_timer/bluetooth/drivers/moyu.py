from term_timer.bluetooth.constants import MOYU_WEILONG_COMMAND_CHARACTERISTIC
from term_timer.bluetooth.constants import MOYU_WEILONG_ENCRYPTION_KEY
from term_timer.bluetooth.constants import MOYU_WEILONG_SERVICE
from term_timer.bluetooth.constants import MOYU_WEILONG_STATE_CHARACTERISTIC
from term_timer.bluetooth.drivers.base import Driver
from term_timer.bluetooth.encrypter import GanGen2CubeEncrypter
from term_timer.bluetooth.salt import get_salt


class MoyuWeilong10Driver(Driver):
    """
    Weilong v10
    """
    service_uid = MOYU_WEILONG_SERVICE
    state_characteristic_uid = MOYU_WEILONG_STATE_CHARACTERISTIC
    command_characteristic_uid = MOYU_WEILONG_COMMAND_CHARACTERISTIC
    encrypter = GanGen2CubeEncrypter

    def init_cypher(self):
        return self.encrypter(
            MOYU_WEILONG_ENCRYPTION_KEY['key'],
            MOYU_WEILONG_ENCRYPTION_KEY['iv'],
            get_salt(self.device.address),
        )

    def send_command_handler(self, command: str):
        msg = bytearray(20)

        if command == 'REQUEST_FACELETS':
            msg[0] = 0xA3
        elif command == 'REQUEST_HARDWARE':
            msg[0] = 0xA1
        elif command == 'REQUEST_BATTERY':
            msg[0] = 0xA4
        elif command == 'REQUEST_RESET':
            return False
        else:
            return False

        return self.cypher.encrypt(bytes(msg))
