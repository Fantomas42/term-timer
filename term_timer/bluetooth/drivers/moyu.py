from term_timer.bluetooth.constants import MOYU_WEILONG_COMMAND_CHARACTERISTIC
from term_timer.bluetooth.constants import MOYU_WEILONG_SERVICE
from term_timer.bluetooth.constants import MOYU_WEILONG_STATE_CHARACTERISTIC
from term_timer.bluetooth.drivers.base import Driver


class MoyuWeilong10Driver(Driver):
    """
    Weilong v10
    """
    service_uid = MOYU_WEILONG_SERVICE
    state_characteristic_uid = MOYU_WEILONG_STATE_CHARACTERISTIC
    command_characteristic_uid = MOYU_WEILONG_COMMAND_CHARACTERISTIC
