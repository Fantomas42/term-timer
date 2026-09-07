"""
Decode the manufacturer data a cube broadcasts before any GATT connection.

Measured on real hardware, not derived from the protocol descriptor: the
MAC tag is confirmed on all four cube generations, the battery tag on a
Gen4 cube only, its `is_valid` field never seen set. `decode_advertised_mac`
feeds `Driver.resolve_salt()`; `decode_advertised_battery` feeds the DEBUG
log only, never `Driver.handle_battery`.
"""
from dataclasses import dataclass
from typing import Final

from term_timer.bluetooth.message import GanProtocolMessage

# Company id candidates once bleak strips the leading 0xFF AD type byte and
# reads the next two as a little endian company id: 0x0001 for the three GAN
# generations, 0x0000 for the MoYu — a different vendor, the same shape.
MAC_COMPANY_IDS: Final[tuple[int, ...]] = (0x0001, 0x0000)

# Only the trailing 6 bytes of the payload are read (the cube's address,
# reversed); the leading bytes seen so far (3, not identified) are ignored.
MAC_TAG_MINIMUM: Final[int] = 6

# ASCII "ba" of "bat:", the only 2 of its 4 bytes bleak keeps as a company
# id — the payload it hands back therefore reopens on the tag's tail.
BATTERY_COMPANY_ID: Final[int] = 0x6162
BATTERY_TAG_HEADER: Final[int] = 2
BATTERY_TAG_LENGTH: Final[int] = 5


@dataclass(frozen=True, slots=True)
class AdvertisedBattery:
    """The battery/charging fields a Gen4 cube's advertisement carries."""

    is_valid: int
    version: str
    is_open: int
    charging_state: int
    battery_power: int
    cube_battery_power: int


def decode_advertised_mac(manufacturer_data: dict[int, bytes]) -> str | None:
    """
    Decode the MAC address a cube's advertisement broadcasts in clear.

    Args:
        manufacturer_data: The company id keyed payloads of one
            advertisement, as bleak exposes them.

    Returns:
        The MAC address, colon joined, or None when no candidate
        company id carries a long enough payload.

    """
    for company_id in MAC_COMPANY_IDS:
        payload = manufacturer_data.get(company_id)

        if payload is None or len(payload) < MAC_TAG_MINIMUM:
            continue

        mac_bytes = payload[-6:]
        return ':'.join(f'{ byte:02X}' for byte in reversed(mac_bytes))

    return None


def decode_advertised_battery(
        manufacturer_data: dict[int, bytes],
) -> AdvertisedBattery | None:
    """
    Decode the battery/charging fields a Gen4 cube's advertisement carries.

    Args:
        manufacturer_data: The company id keyed payloads of one
            advertisement, as bleak exposes them.

    Returns:
        The decoded fields, or None when the battery company id is
        absent (Gen2, Gen3, MoYu, normal) or its payload too short.

    """
    payload = manufacturer_data.get(BATTERY_COMPANY_ID)

    if payload is None:
        return None

    fields = payload[BATTERY_TAG_HEADER:]

    if len(fields) < BATTERY_TAG_LENGTH:
        return None

    message = GanProtocolMessage(fields)

    return AdvertisedBattery(
        is_valid=message.get_bit_word(0, 8),
        version=(
            f'{ message.get_bit_word(8, 4) }.'
            f'{ message.get_bit_word(12, 4) }'
        ),
        is_open=message.get_bit_word(16, 1),
        charging_state=message.get_bit_word(17, 1),
        battery_power=message.get_bit_word(24, 8),
        cube_battery_power=message.get_bit_word(32, 8),
    )
