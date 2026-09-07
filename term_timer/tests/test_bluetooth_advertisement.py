"""Tests for the decoding of a cube's advertisement data."""
import unittest

from term_timer.bluetooth.advertisement import BATTERY_COMPANY_ID
from term_timer.bluetooth.advertisement import AdvertisedBattery
from term_timer.bluetooth.advertisement import decode_advertised_battery
from term_timer.bluetooth.advertisement import decode_advertised_mac

# GAN i4: 0x0001 -> 00 00 00 22 fb 9d 50 6c 54, measured against its real
# address, 54:6C:50:9D:FB:22.
GAN_MAC_PAYLOAD = bytes([0x00, 0x00, 0x00, 0x22, 0xFB, 0x9D, 0x50, 0x6C, 0x54])
GAN_MAC = '54:6C:50:9D:FB:22'

# MoYu WL v10: 0x0000 -> 00 00 30 a7 a6 00 16 30 cf, its own real address,
# CF:30:16:00:A6:A7 — a different company id, the same shape.
MOYU_MAC_PAYLOAD = bytes([0x00, 0x00, 0x30, 0xA7, 0xA6, 0x00, 0x16, 0x30, 0xCF])
MOYU_MAC = 'CF:30:16:00:A6:A7'

# GAN i4: 0x6162 -> 74 3a 00 ff ff ff 64, an "in charge" reading reproduced
# identically across five reads, including one confirmed by eye.
BATTERY_PAYLOAD = bytes([0x74, 0x3A, 0x00, 0xFF, 0xFF, 0xFF, 0x64])


class TestDecodeAdvertisedMac(unittest.TestCase):
    """Tests for the MAC address decoded out of the advertisement."""

    def test_decodes_a_gan_payload(self) -> None:
        """Test the trailing 6 bytes, reversed, give the GAN address."""
        self.assertEqual(
            decode_advertised_mac({0x0001: GAN_MAC_PAYLOAD}),
            GAN_MAC,
        )

    def test_decodes_a_moyu_payload_under_its_own_company_id(self) -> None:
        """Test the MoYu is read the same way, under a different id."""
        self.assertEqual(
            decode_advertised_mac({0x0000: MOYU_MAC_PAYLOAD}),
            MOYU_MAC,
        )

    def test_no_candidate_company_id_present(self) -> None:
        """Test an advertisement carrying neither company id decodes to None."""
        self.assertIsNone(
            decode_advertised_mac({BATTERY_COMPANY_ID: BATTERY_PAYLOAD}),
        )

    def test_payload_too_short(self) -> None:
        """Test a payload shorter than 6 bytes is refused, not misread."""
        self.assertIsNone(decode_advertised_mac({0x0001: bytes([0x01, 0x02])}))

    def test_empty_manufacturer_data(self) -> None:
        """Test no manufacturer data at all decodes to None."""
        self.assertIsNone(decode_advertised_mac({}))


class TestDecodeAdvertisedBattery(unittest.TestCase):
    """Tests for the battery/charging fields decoded out of an advertisement."""

    def test_decodes_the_measured_gan_i4_payload(self) -> None:
        """Test the fields read out of the payload measured on the bench."""
        self.assertEqual(
            decode_advertised_battery({BATTERY_COMPANY_ID: BATTERY_PAYLOAD}),
            AdvertisedBattery(
                is_valid=0,
                version='15.15',
                is_open=1,
                charging_state=1,
                battery_power=255,
                cube_battery_power=100,
            ),
        )

    def test_absent_on_gen2_gen3_and_moyu(self) -> None:
        """Test an advertisement with no battery company id decodes to None."""
        self.assertIsNone(
            decode_advertised_battery({0x0001: GAN_MAC_PAYLOAD}),
        )

    def test_payload_too_short(self) -> None:
        """Test a payload shorter than the tag's length is refused."""
        short_payload = bytes([0x74, 0x3A])

        self.assertIsNone(
            decode_advertised_battery({BATTERY_COMPANY_ID: short_payload}),
        )

    def test_empty_manufacturer_data(self) -> None:
        """Test no manufacturer data at all decodes to None."""
        self.assertIsNone(decode_advertised_battery({}))
