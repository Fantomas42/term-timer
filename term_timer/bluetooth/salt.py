"""Generate encryption salt from Bluetooth MAC address."""
from typing import Final

MAC_OCTETS: Final[int] = 6
MAX_OCTET: Final[int] = 0xFF

INVALID_MAC: Final[str] = (
    'MAC address must be 6 colon-separated hex octets'
)


def get_salt(mac_address: str) -> bytearray:
    """
    Generate encryption salt array from Bluetooth MAC address.

    The salt must correspond exactly to the connected cube's real MAC
    address. A mismatched salt can make an otherwise valid command decrypt,
    on the cube side, into a different (potentially destructive) opcode, so
    the format is validated strictly rather than silently producing a
    wrong-length or out-of-range salt.

    Returns:
        Bytearray containing reversed MAC address bytes.

    Raises:
        ValueError: If the MAC address is not 6 colon-separated hex octets.

    """
    mac_parts = mac_address.split(':')

    if len(mac_parts) != MAC_OCTETS:
        raise ValueError(INVALID_MAC)

    # Convert hex strings to integers and reverse the order
    salt_array = []
    for part in mac_parts:
        value = int(part, 16)
        if value < 0 or value > MAX_OCTET:
            raise ValueError(INVALID_MAC)
        salt_array.append(value)

    salt_array.reverse()

    return bytearray(salt_array)
