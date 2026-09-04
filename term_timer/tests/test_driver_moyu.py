"""Tests for driver moyu."""
import asyncio
import unittest
from collections.abc import Sequence
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import TYPE_CHECKING
from typing import cast
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

from term_timer.bluetooth.constants import MOYU_FACE_NAMES
from term_timer.bluetooth.constants import MOYU_FACES
from term_timer.bluetooth.constants import MOYU_MOVE_CAPACITY
from term_timer.bluetooth.constants import MOYU_WEILONG_COMMAND_CHARACTERISTIC
from term_timer.bluetooth.constants import MOYU_WEILONG_SERVICE
from term_timer.bluetooth.constants import MOYU_WEILONG_STATE_CHARACTERISTIC
from term_timer.bluetooth.drivers.base import Driver
from term_timer.bluetooth.drivers.moyu import MoyuWeilong10Driver

if TYPE_CHECKING:
    from term_timer.bluetooth.annotations import BatteryEventDict
    from term_timer.bluetooth.annotations import EventDict
    from term_timer.bluetooth.annotations import FaceletsEventDictNoState
    from term_timer.bluetooth.annotations import GyroConfigEventDict
    from term_timer.bluetooth.annotations import GyroEventDictNoVelocity
    from term_timer.bluetooth.annotations import HardwareEventMoyuDict
    from term_timer.bluetooth.annotations import MoveEventDict

# The eight stickers of a face, in the order the firmware reads them,
# and the six faces of a solved cube in its own FBUDLR order.
STICKERS_PER_FACE = 8

# A move message carries its moves five bits at a time from the bit 96,
# which is the last full word of the notification.
MOVES_OFFSET = 12

SOLVED = 'UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB'


def move_frame(serial: int,
               moves: Sequence[tuple[int, int]]) -> bytes:
    """
    Build a `0xA5` notification carrying up to five moves.

    Args:
        serial: The counter of the cube, naming the newest move.
        moves: The five bits mask and the elapsed register of each
            move, newest first, as the protocol packs them.

    Returns:
        The twenty bytes of the decrypted notification.

    """
    frame = bytearray(20)
    frame[0] = 0xA5
    frame[11] = serial

    packed = ['00000'] * MOYU_MOVE_CAPACITY

    for index, (mask, elapsed) in enumerate(moves):
        frame[1 + index * 2] = elapsed >> 8
        frame[2 + index * 2] = elapsed & 0xFF
        packed[index] = format(mask, '05b')

    # Twenty five bits of moves, padded to the four bytes they live in.
    word = int(''.join(packed) + '0000000', 2)
    frame[MOVES_OFFSET:MOVES_OFFSET + 4] = word.to_bytes(4, 'big')

    return bytes(frame)


def facelets_frame(serial: int, stickers: Sequence[int]) -> bytes:
    """
    Build a `0xA3` notification carrying a whole cube state.

    Args:
        serial: The counter of the cube.
        stickers: The forty eight stickers, three bits each, indexed
            by `native * 8 + sticker` in the FBUDLR order of the
            firmware.

    Returns:
        The twenty bytes of the decrypted notification.

    """
    frame = bytearray(20)
    frame[0] = 0xA3
    frame[19] = serial

    bits = ''.join(format(value, '03b') for value in stickers)
    frame[1:19] = int(bits, 2).to_bytes(18, 'big')

    return bytes(frame)


def solved_stickers() -> list[int]:
    """
    Give the forty eight stickers of a solved cube.

    Returns:
        Each face carrying its own colour, in the native order.

    """
    return [
        native
        for native in range(6)
        for _ in range(STICKERS_PER_FACE)
    ]


def hardware_frame(name: str, versions: tuple[int, int, int, int],
                   serial: int, *,
                   enabled: bool, ready: bool) -> bytes:
    """
    Build a `0xA1` notification carrying the identity of the cube.

    Args:
        name: The eight characters of the hardware name.
        versions: The major and minor of the hardware version, then
            those of the software one.
        serial: The counter of the cube, read on eight bits astride
            two bytes from the bit 109.
        enabled: The bit 105, saying the gyroscope streams.
        ready: The bit 106, saying the cube carries one.

    Returns:
        The twenty bytes of the decrypted notification.

    """
    frame = bytearray(20)
    frame[0] = 0xA1
    frame[1:9] = name.encode()
    frame[9], frame[10], frame[11], frame[12] = versions

    # The bits 104 to 119, where the two flags and the serial overlap.
    word = (serial & 0xFF) << 3

    if enabled:
        word |= 1 << 14
    if ready:
        word |= 1 << 13

    frame[13] = word >> 8
    frame[14] = word & 0xFF

    return bytes(frame)


class TestMoyuFaceTable(unittest.TestCase):
    """Tests for the face table the moves and the facelets share."""

    def test_face_table_names_every_face_once(self) -> None:
        """Test the six native faces map onto the six of URFDLB."""
        self.assertEqual(sorted(MOYU_FACES), list(range(6)))
        self.assertEqual(sorted(MOYU_FACES.values()), list(range(6)))

    def test_face_table_is_its_own_inverse(self) -> None:
        """Test the same table reads the two directions."""
        # The plan reads the moves and the facelets with the same six
        # values, which is only correct because the permutation is an
        # involution. Pinned rather than believed.
        for native, index in MOYU_FACES.items():
            with self.subTest(face=native):
                self.assertEqual(MOYU_FACES[index], native)

    def test_face_table_keeps_the_letter_of_the_face(self) -> None:
        """Test a native face and its URFDLB index name one letter."""
        for native, index in MOYU_FACES.items():
            with self.subTest(face=native):
                self.assertEqual(
                    MOYU_FACE_NAMES[native],
                    'URFDLB'[index],
                )


class TestMoyuWeilong10Driver(unittest.IsolatedAsyncioTestCase):  # noqa: PLR0904
    """Tests for MoyuWeilong10Driver class."""

    def setUp(self) -> None:
        """Test setup."""
        self.mock_client = Mock()
        self.mock_client.address = 'AA:BB:CC:DD:EE:FF'
        self.mock_client.name = 'WCU_MY32_A6A7'
        self.mock_client.disconnect = AsyncMock()

        with patch(
                'term_timer.bluetooth.drivers.moyu.get_salt',
                return_value=b'salt12',
        ):
            self.driver = MoyuWeilong10Driver(
                self.mock_client,
                use_gyroscope=False,
            )

        self.timestamp = datetime.now(tz=timezone.utc)  # noqa: UP017

    async def notify(self, frame: bytes) -> list['EventDict']:
        """
        Hand a decrypted notification to the driver.

        Args:
            frame: The bytes the cube would have sent, in the clear.

        Returns:
            The events the driver decoded out of it.

        """
        with patch(
                'term_timer.bluetooth.drivers.base.time.perf_counter_ns',
                return_value=123456789,
        ), patch(
            'term_timer.bluetooth.drivers.base.datetime',
        ) as mock_datetime, patch.object(
            self.driver, 'cypher',
        ) as mock_cypher:
            mock_datetime.now.return_value = self.timestamp
            mock_cypher.decrypt.return_value = frame

            return await self.driver.event_handler(Mock(), bytearray(frame))

    def test_init_sets_correct_attributes(self) -> None:
        """Test init sets correct attributes."""
        self.assertEqual(self.driver.client, self.mock_client)
        self.assertEqual(self.driver.serial, -1)
        self.assertEqual(self.driver.cube_timestamp, 0)
        self.assertIsNone(self.driver.last_move_timestamp)

    def test_class_constants(self) -> None:
        """Test class constants."""
        self.assertEqual(
            MoyuWeilong10Driver.service_uid,
            MOYU_WEILONG_SERVICE,
        )
        self.assertEqual(
            MoyuWeilong10Driver.state_characteristic_uid,
            MOYU_WEILONG_STATE_CHARACTERISTIC,
        )
        self.assertEqual(
            MoyuWeilong10Driver.command_characteristic_uid,
            MOYU_WEILONG_COMMAND_CHARACTERISTIC,
        )
        self.assertEqual(MoyuWeilong10Driver.payload_offset, 8)
        self.assertFalse(MoyuWeilong10Driver.chained)
        self.assertIsNone(MoyuWeilong10Driver.head_magic)
        self.assertEqual(MoyuWeilong10Driver.crc_reserve, 0)

    def test_shared_handlers_are_the_ones_of_the_socle(self) -> None:
        """Test the two handlers MoYu shares with GAN are not copied."""
        # The point of the lot : a driver carries the bytes of its own
        # protocol and nothing else. Counting events would not notice a
        # handler quietly coming back, the identity of the functions
        # does.
        for name in ('handle_battery', 'handle_disconnect'):
            with self.subTest(handler=name):
                self.assertIs(
                    getattr(MoyuWeilong10Driver, name),
                    getattr(Driver, name),
                )

    def test_init_cypher(self) -> None:
        """Test init cypher."""
        cypher = self.driver.init_cypher()
        self.assertIsNotNone(cypher)

    def test_send_command_handler_request_facelets(self) -> None:
        """Test send command handler request facelets."""
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            result = self.driver.send_command_handler('REQUEST_FACELETS')

            self.assertEqual(result, b'encrypted_data')
            self.assertEqual(mock_cypher.encrypt.call_args[0][0][0], 0xA3)

    def test_send_command_handler_request_hardware(self) -> None:
        """Test send command handler request hardware."""
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            self.driver.send_command_handler('REQUEST_HARDWARE')

            self.assertEqual(mock_cypher.encrypt.call_args[0][0][0], 0xA1)

    def test_send_command_handler_request_battery(self) -> None:
        """Test send command handler request battery."""
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            self.driver.send_command_handler('REQUEST_BATTERY')

            self.assertEqual(mock_cypher.encrypt.call_args[0][0][0], 0xA4)

    def test_send_command_handler_request_enable_gyro(self) -> None:
        """Test send command handler request enable gyro."""
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            self.driver.send_command_handler('REQUEST_ENABLE_GYRO')

            plaintext = mock_cypher.encrypt.call_args[0][0]
            self.assertEqual(plaintext[0], 0xAC)
            self.assertEqual(plaintext[2], 0x01)

    def test_send_command_handler_request_disable_gyro(self) -> None:
        """Test send command handler request disable gyro."""
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            self.driver.send_command_handler('REQUEST_DISABLE_GYRO')

            plaintext = mock_cypher.encrypt.call_args[0][0]
            self.assertEqual(plaintext[0], 0xAC)
            self.assertEqual(plaintext[2], 0x00)

    def test_send_command_handler_request_reset(self) -> None:
        """Test send command handler request reset."""
        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            self.driver.send_command_handler('REQUEST_RESET')

            plaintext = mock_cypher.encrypt.call_args[0][0]
            self.assertEqual(plaintext[0], 0xA2)
            self.assertEqual(len(plaintext), 20)

    def test_send_command_handler_invalid_command(self) -> None:
        """Test send command handler invalid command."""
        self.assertFalse(self.driver.send_command_handler('NOPE'))
        self.assertFalse(self.driver.send_command_handler(''))

    def test_send_command_handler_never_emits_rename(self) -> None:
        """
        Test that no supported command builds the 0xAD rename opcode.

        The undocumented 0xAD command permanently renames the cube's
        Bluetooth device name with no guard, bricking discovery. term-timer
        must never emit it: this pins the invariant so a future command
        addition cannot silently introduce it.
        """
        rename_opcode = 0xAD
        commands = [
            'REQUEST_FACELETS',
            'REQUEST_HARDWARE',
            'REQUEST_BATTERY',
            'REQUEST_ENABLE_GYRO',
            'REQUEST_DISABLE_GYRO',
            'REQUEST_RESET',
        ]

        for command in commands:
            with patch.object(self.driver, 'cypher') as mock_cypher:
                mock_cypher.encrypt.return_value = b'encrypted_data'

                self.driver.send_command_handler(command)

                plaintext = mock_cypher.encrypt.call_args[0][0]
                self.assertNotEqual(
                    plaintext[0], rename_opcode,
                    f'Command {command} produced a 0xAD opcode',
                )

    async def test_move_frame_names_its_face_and_its_direction(self) -> None:
        """Test a move frame publishes an URFDLB index and a bit."""
        # The two fields carried the raw five bits mask, measured on
        # the wire the 2026-09-02 as `face=9 direction=9 move=L'`.
        self.driver.serial = 100

        events = await self.notify(move_frame(101, [(9, 1234)]))

        self.assertEqual(len(events), 1)
        move = cast('MoveEventDict', events[0])
        self.assertEqual(move['move'], "L'")
        self.assertEqual(move['face'], 'URFDLB'.index('L'))
        self.assertEqual(move['direction'], 1)
        self.assertEqual(move['serial'], 101)
        self.assertEqual(move['cube_timestamp'], 1234)

    async def test_move_frame_names_the_six_faces(self) -> None:
        """Test the six masks of the cube name the six faces."""
        for mask, expected in enumerate(
                ['F', "F'", 'B', "B'", 'U', "U'",
                 'D', "D'", 'L', "L'", 'R', "R'"],
        ):
            with self.subTest(mask=mask):
                self.driver.serial = 0
                self.driver.cube_timestamp = 0.0

                events = await self.notify(move_frame(1, [(mask, 100)]))

                move = cast('MoveEventDict', events[0])
                self.assertEqual(move['move'], expected)
                self.assertEqual(
                    move['face'], 'URFDLB'.index(expected[0]),
                )
                self.assertEqual(move['direction'], mask & 1)

    async def test_move_frame_out_of_domain_keeps_the_clock_running(
            self,
    ) -> None:
        """Test an unnamable mask costs the move, never the clock."""
        # Five bits name sixteen faces for six : masks 6 to 15, so
        # move values from 12 up, have no move to answer to. The clock
        # of the cube advanced all the same, and dropping it would
        # shift every move coming after.
        self.driver.serial = 100

        with self.assertLogs(
                'term_timer.bluetooth.drivers.moyu', level='DEBUG',
        ) as logged:
            events = await self.notify(move_frame(101, [(12, 1234)]))

        self.assertEqual(events, [])
        self.assertEqual(self.driver.cube_timestamp, 1234)
        self.assertEqual(self.driver.serial, 101)
        self.assertIn('out of domain move', logged.output[0])
        self.assertIn('mask "6"', logged.output[0])

    async def test_move_frame_carries_five_moves_oldest_first(self) -> None:
        """Test a full move frame delivers its five moves in order."""
        self.driver.serial = 100

        events = await self.notify(
            move_frame(105, [
                (10, 500),   # serial 105, R
                (8, 400),    # serial 104, L
                (6, 300),    # serial 103, D
                (4, 200),    # serial 102, U
                (2, 100),    # serial 101, B
            ]),
        )

        self.assertEqual(len(events), MOYU_MOVE_CAPACITY)
        moves = [cast('MoveEventDict', event) for event in events]

        self.assertEqual(
            [move['serial'] for move in moves],
            [101, 102, 103, 104, 105],
        )
        self.assertEqual(
            [move['move'] for move in moves],
            ['B', 'U', 'D', 'L', 'R'],
        )
        # Oldest first, so the clock of the cube only ever grows
        self.assertEqual(
            [move['cube_timestamp'] for move in moves],
            [100, 300, 600, 1000, 1500],
        )
        # Only the newest move of a frame has a local timestamp
        self.assertEqual(
            [move['local_timestamp'] is None for move in moves],
            [True, True, True, True, False],
        )

    async def test_move_frame_serials_wrap_on_their_byte(self) -> None:
        """Test the counter of the cube is compared on a byte."""
        self.driver.serial = 254

        events = await self.notify(
            move_frame(1, [(0, 100), (2, 100), (4, 100)]),
        )

        self.assertEqual(
            [cast('MoveEventDict', event)['serial'] for event in events],
            [255, 0, 1],
        )

    async def test_move_frame_is_capped_at_the_capacity(self) -> None:
        """Test a gap wider than the frame yields what it carries."""
        self.driver.serial = 100

        events = await self.notify(
            move_frame(120, [(0, 100)] * MOYU_MOVE_CAPACITY),
        )

        self.assertEqual(len(events), MOYU_MOVE_CAPACITY)
        self.assertEqual(self.driver.serial, 120)

    async def test_move_frame_of_a_serial_that_did_not_move(self) -> None:
        """Test a repeated counter publishes nothing."""
        self.driver.serial = 100

        self.assertEqual(await self.notify(move_frame(100, [(0, 100)])), [])

    async def test_moves_are_blocked_before_the_facelets(self) -> None:
        """Test event handler moves blocked before facelets."""
        self.assertEqual(self.driver.serial, -1)

        self.assertEqual(await self.notify(move_frame(101, [(0, 100)])), [])

    async def test_move_frame_falls_back_on_the_local_clock(self) -> None:
        """Test a null register is replaced by milliseconds."""
        # The register of the cube counts in milliseconds, and the
        # local elapsed time standing in for an overflow is converted
        # to them. It was added in seconds, which is the defect the
        # Gen2 carried at the same place before the socle took it.
        self.driver.serial = 100
        self.driver.last_move_timestamp = self.timestamp - timedelta(
            seconds=1.5,
        )

        events = await self.notify(move_frame(101, [(0, 0)]))

        move = cast('MoveEventDict', events[0])
        self.assertEqual(move['cube_timestamp'], 1500)

    async def test_move_frame_of_a_saturated_register(self) -> None:
        """Test a saturated register is replaced by milliseconds."""
        # 0xFFFF is the same register as the null one, stopped at its
        # ceiling rather than wrapped : the cube had been still for
        # more than 65,5 seconds. Added as it comes, it would push the
        # clock of the cube a minute forward. Measured the 2026-09-04,
        # once in 366 moves, on the frame following a long pause.
        self.driver.serial = 100
        self.driver.last_move_timestamp = self.timestamp - timedelta(
            seconds=2.0,
        )

        events = await self.notify(move_frame(101, [(0, 0xFFFF)]))

        move = cast('MoveEventDict', events[0])
        self.assertEqual(move['cube_timestamp'], 2000)

    async def test_move_frame_of_a_saturated_register_opening_a_session(
            self) -> None:
        """Test a saturated register alone leaves the clock in place."""
        # The very case the cube produced : the first move of a session
        # carries a gap inherited from before the connection, and there
        # is no earlier move to date it against. The clock stays where
        # it is rather than opening on 65,5 seconds.
        self.driver.serial = 100

        self.assertIsNone(self.driver.last_move_timestamp)

        events = await self.notify(move_frame(101, [(0, 0xFFFF)]))

        move = cast('MoveEventDict', events[0])
        self.assertEqual(move['cube_timestamp'], 0)
        self.assertEqual(self.driver.cube_timestamp, 0)

    async def test_move_frame_of_a_null_register_opening_a_session(
            self) -> None:
        """Test an overflow alone leaves the clock in place."""
        self.driver.serial = 100

        self.assertIsNone(self.driver.last_move_timestamp)

        events = await self.notify(move_frame(101, [(0, 0)]))

        move = cast('MoveEventDict', events[0])
        self.assertEqual(move['cube_timestamp'], 0)

    async def test_facelets_frame_of_a_solved_cube(self) -> None:
        """Test a solved state is read in the URFDLB order."""
        events = await self.notify(facelets_frame(50, solved_stickers()))

        self.assertEqual(len(events), 1)
        facelets = cast('FaceletsEventDictNoState', events[0])
        self.assertEqual(facelets['serial'], 50)
        self.assertEqual(facelets['facelets'], SOLVED)

    async def test_reset_is_answered_by_the_command_read_back(
            self) -> None:
        """Test the frame answering a reset is the command itself."""
        # Measured on a Weilong v10 AI the 2026-09-04 (§6.5) : this
        # protocol has no reset message, and the cube answers
        # REQUEST_RESET with the very bytes it was written — 0xA2
        # turned 0xA3, and its serial in place of the trailing zero.
        answer = bytes.fromhex(
            'a3000000249249492492'
            '6db6db924924b6db6dea',
        )

        events = await self.notify(answer)

        self.assertEqual(len(events), 1)
        facelets = cast('FaceletsEventDictNoState', events[0])
        self.assertEqual(facelets['serial'], 234)
        self.assertEqual(facelets['facelets'], SOLVED)

        with patch.object(self.driver, 'cypher') as mock_cypher:
            mock_cypher.encrypt.return_value = b'encrypted_data'

            self.driver.send_command_handler('REQUEST_RESET')

            written = mock_cypher.encrypt.call_args[0][0]

        self.assertEqual(written[0], 0xA2)
        self.assertEqual(bytes(written[1:19]), answer[1:19])
        self.assertEqual(written[19], 0x00)

    async def test_facelets_frame_unblocks_the_moves(self) -> None:
        """Test the counter starts on the state the driver could read."""
        await self.notify(facelets_frame(50, solved_stickers()))

        self.assertEqual(self.driver.serial, 50)

    async def test_facelets_frame_does_not_restart_the_counter(self) -> None:
        """Test only the first state read starts the counter."""
        # The counter is the one of the cube and not of the session :
        # a facelets frame arriving mid solve says where the cube is,
        # never where the moves resume from.
        await self.notify(facelets_frame(50, solved_stickers()))
        await self.notify(facelets_frame(80, solved_stickers()))

        self.assertEqual(self.driver.serial, 50)

    async def test_facelets_frame_places_a_turned_sticker(self) -> None:
        """Test a sticker of another colour lands where it belongs."""
        # The first sticker of the native face U — the face MOYU_FACES
        # sends to the head of the string — carries the colour of R.
        stickers = solved_stickers()
        stickers[MOYU_FACE_NAMES.index('U') * STICKERS_PER_FACE] = (
            MOYU_FACE_NAMES.index('R')
        )

        events = await self.notify(facelets_frame(50, stickers))

        facelets = cast('FaceletsEventDictNoState', events[0])
        self.assertEqual(facelets['facelets'], 'R' + SOLVED[1:])

    async def test_facelets_frame_out_of_domain_is_dropped_whole(
            self,
    ) -> None:
        """Test a colour of 6 or 7 costs the frame, not a sticker."""
        # Skipping the sticker would shorten the string and slide
        # every one coming after it : a false state is worse than no
        # state, the driver already holding its moves until one comes.
        for colour in (6, 7):
            with self.subTest(colour=colour):
                stickers = solved_stickers()
                stickers[9] = colour

                with self.assertLogs(
                        'term_timer.bluetooth.drivers.moyu', level='DEBUG',
                ) as logged:
                    events = await self.notify(facelets_frame(50, stickers))

                self.assertEqual(events, [])
                self.assertEqual(self.driver.serial, -1)
                self.assertIn('out of domain colour', logged.output[0])

    async def test_hardware_frame_reads_its_identity(self) -> None:
        """Test event handler hardware event."""
        events = await self.notify(
            hardware_frame(
                'MY32AI01', (1, 2, 3, 4), 123,
                enabled=True, ready=True,
            ),
        )

        self.assertEqual(len(events), 1)
        hardware = cast('HardwareEventMoyuDict', events[0])
        self.assertEqual(hardware['hardware_name'], 'MY32AI01')
        self.assertEqual(hardware['hardware_version'], '1.2')
        self.assertEqual(hardware['software_version'], '3.4')
        self.assertEqual(hardware['serial'], 123)
        self.assertTrue(hardware['gyroscope_enabled'])
        self.assertTrue(hardware['gyroscope_ready'])
        self.assertTrue(hardware['gyroscope_supported'])

    async def test_hardware_frame_supports_what_it_has_turned_off(
            self,
    ) -> None:
        """Test gyroscope_supported no longer depends on enabled."""
        # The cube in hand announces enabled False, ready True, and
        # was published as not supporting a gyroscope it had simply
        # switched off. Measured on a WCU_MY32_A6A7 the 2026-09-02.
        events = await self.notify(
            hardware_frame(
                'MY32AI01', (1, 2, 3, 4), 7,
                enabled=False, ready=True,
            ),
        )

        hardware = cast('HardwareEventMoyuDict', events[0])
        self.assertFalse(hardware['gyroscope_enabled'])
        self.assertTrue(hardware['gyroscope_ready'])
        self.assertTrue(hardware['gyroscope_supported'])

    async def test_hardware_frame_of_a_cube_without_a_sensor(self) -> None:
        """Test a cube saying it is not ready is not said to support."""
        events = await self.notify(
            hardware_frame(
                'MY32AI01', (1, 2, 3, 4), 7,
                enabled=False, ready=False,
            ),
        )

        hardware = cast('HardwareEventMoyuDict', events[0])
        self.assertFalse(hardware['gyroscope_supported'])

    async def test_gyro_config_frame_follows_what_the_cube_announces(
            self,
    ) -> None:
        """Test the answer to a gyroscope command is read, not assumed."""
        # The command writes its flag in the byte 2 and the handler
        # reads its own in the byte 2 : coherent, and not a proof. The
        # V3 fell exactly there (§5.6.bis), and what the two answers
        # of the MoYu really carry is what the bench of §6.8 raises.
        for enabled in (0x01, 0x00):
            with self.subTest(enabled=enabled):
                frame = bytearray(20)
                frame[0] = 0xAC
                frame[1] = 0x01
                frame[2] = enabled

                events = await self.notify(bytes(frame))

                self.assertEqual(len(events), 1)
                config = cast('GyroConfigEventDict', events[0])
                self.assertEqual(
                    config['gyroscope_enabled'], bool(enabled),
                )
                self.assertTrue(config['gyroscope_ready'])
                self.assertTrue(config['gyroscope_supported'])

    async def test_gyroscope_frame_is_silent_when_disarmed(self) -> None:
        """Test event handler gyroscope disabled."""
        self.driver.use_gyroscope = False

        frame = bytearray(20)
        frame[0] = 0xAB

        self.assertEqual(await self.notify(bytes(frame)), [])

    async def test_gyroscope_frame_reads_its_quaternion(self) -> None:
        """Test event handler gyroscope enabled."""
        self.driver.use_gyroscope = True

        frame = bytearray(20)
        frame[0] = 0xAB
        # Four words of thirty two bits, little endian and signed
        frame[1:5] = (self.driver.factor).to_bytes(4, 'little')
        frame[5:9] = (-self.driver.factor).to_bytes(
            4, 'little', signed=True,
        )
        frame[9:13] = (0).to_bytes(4, 'little')
        frame[13:17] = (self.driver.factor // 2).to_bytes(4, 'little')

        events = await self.notify(bytes(frame))

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['event'], 'gyro')
        gyro = cast('GyroEventDictNoVelocity', events[0])
        self.assertEqual(
            gyro['quaternion'],
            {'w': 1.0, 'x': -1.0, 'y': 0.0, 'z': 0.5},
        )

    async def test_battery_frame_is_the_one_of_the_socle(self) -> None:
        """Test event handler battery event."""
        frame = bytearray(20)
        frame[0] = 0xA4
        frame[1] = 75

        events = await self.notify(bytes(frame))

        self.assertEqual(len(events), 1)
        battery = cast('BatteryEventDict', events[0])
        self.assertEqual(battery['level'], 75)
        # MoYu declares no charging state, and the socle publishes none
        self.assertEqual(battery['charging_state'], 0)

    async def test_battery_frame_level_is_capped(self) -> None:
        """Test event handler battery level capped."""
        frame = bytearray(20)
        frame[0] = 0xA4
        frame[1] = 150

        events = await self.notify(bytes(frame))

        self.assertEqual(cast('BatteryEventDict', events[0])['level'], 100)

    async def test_disconnect_frame_journals_its_payload(self) -> None:
        """Test the payload of a disconnect is journaled before cutting."""
        # The oracle of the open question 2, armed on the fourth and
        # last protocol : the byte is read at the payload_offset of the
        # protocol, and no cube of any generation has ever sent one.
        frame = bytearray(20)
        frame[0] = 0xA0
        frame[1] = 0x03

        with self.assertLogs(
                'term_timer.bluetooth.drivers.base', level='WARNING',
        ) as logged:
            events = await self.notify(bytes(frame))

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['event'], 'disconnect')
        self.assertIn('payload starts with "0x03"', logged.output[0])
        self.mock_client.disconnect.assert_awaited_once()

    async def test_unknown_opcode_is_journaled(self) -> None:
        """Test event handler unknown event."""
        frame = bytearray(20)
        frame[0] = 0xA2

        with self.assertLogs(
                'term_timer.bluetooth.drivers.base', level='DEBUG',
        ) as logged:
            events = await self.notify(bytes(frame))

        self.assertEqual(events, [])
        self.assertIn('Unknown event type "0xA2"', logged.output[0])

    def test_event_handler_is_async(self) -> None:
        """Test event handler is async."""
        self.assertTrue(
            asyncio.iscoroutinefunction(self.driver.event_handler),
        )
