"""Bluetooth protocol constants and encryption keys for smart cubes."""
# ruff: noqa: E222 E501
from typing import Final

DEBOUNCE: Final[float] = 0.5

# Delay after which an unanswered move history request is retried
MOVE_HISTORY_TIMEOUT: Final[float] = 1.0

# Buffered moves above which the move sequence is considered lost
MOVE_BUFFER_LIMIT: Final[int] = 16

# CRC-16/CCITT-FALSE, the checksum closing every V3 frame: init 0xFFFF,
# polynomial 0x1021, MSB first, no reflection and no final XOR.
CRC16_INIT: Final[int] = 0xFFFF
CRC16_POLYNOMIAL: Final[int] = 0x1021

# Suffix of a move, indexed by its direction bit.
DIRECTIONS: Final[str] = " '"

# The firmware of the V2 and V3 protocols orders its faces D, U, B, F,
# L, R. A live move names one of them by the bit mask of g.java
# getSurfaceIdBy2, a move of the history by the plain index of
# getSurfaceIdByBy10. Both tables translate that into the index of the
# face in URFDLB, and a value absent of them is out of domain.
GEN3_MOVE_FACES: Final[dict[int, int]] = {
    2: 0, 32: 1, 8: 2, 1: 3, 16: 4, 4: 5,
}
GEN3_HISTORY_FACES: Final[dict[int, int]] = {
    1: 0, 5: 1, 3: 2, 0: 3, 4: 4, 2: 5,
}

# A V1 face angles message packs as many records of 25 bits as fit
# after its 10 bits of header, which a 20 bytes notification caps at
# six. The count field is read on 3 bits and can announce more.
GEN2_FACE_ANGLES_CAPACITY: Final[int] = 6

# A V1 move message carries the last move plus the six previous ones,
# which is the capacity of the protocol and not a choice of the driver :
# beyond that, the older moves only come back through a history request.
GEN2_MOVE_CAPACITY: Final[int] = 7

# maxElementCount of the formulaHistory answering a V1 history request,
# each move being read on five bits from the bit 17 of the message.
GEN2_MOVE_HISTORY_CAPACITY: Final[int] = 28

# The firmware of the MoYu orders its faces F, B, U, D, L, R, in the
# five bits naming a move as in the three bits naming the colour of a
# facelet. The table translates that order into the index of the face
# in URFDLB, and a value absent of it is out of domain. It is its own
# inverse, which is why the same six values read the two directions —
# a property a test pins rather than trusts.
MOYU_FACES: Final[dict[int, int]] = {
    0: 2, 1: 5, 2: 0, 3: 3, 4: 4, 5: 1,
}

# The letters those six faces are spelled with, in the order of the
# firmware : a facelet is named by the face whose colour it carries.
MOYU_FACE_NAMES: Final[str] = 'FBUDLR'

# A MoYu move message carries the last move plus the four previous
# ones, which is the capacity of the protocol. It has no history
# command, so a gap wider than that is lost for good.
MOYU_MOVE_CAPACITY: Final[int] = 5

PREFIX: Final[list[str]] = [
    'GAN',
    'MG',
    'AiCube',
    'WCU_MY32',
]

# Every event name the drivers publish, and therefore the contract any
# consumer draining the event queue has to cover. A driver growing a new
# event adds it here, and the consumers are tested against this set.
BLUETOOTH_EVENTS: Final[frozenset[str]] = frozenset({
    'hardware',
    'battery',
    'facelets',
    'gyro',
    'gyro-config',
    'move',
    'move_history',
    'solved',
    'disconnect',
    'reset',
})

# GAN Gen2 protocol BLE service
GAN_GEN2_SERVICE: Final[str] =                '6e400001-b5a3-f393-e0a9-e50e24dc4179'
GAN_GEN2_STATE_CHARACTERISTIC: Final[str] =   '28be4cb6-cd67-11e9-a32f-2a2ae2dbcce4'
GAN_GEN2_COMMAND_CHARACTERISTIC: Final[str] = '28be4a4a-cd67-11e9-a32f-2a2ae2dbcce4'

# GAN Gen3 protocol BLE service
GAN_GEN3_SERVICE: Final[str] =                '8653000a-43e6-47b7-9cb0-5fc21d4ae340'
GAN_GEN3_STATE_CHARACTERISTIC: Final[str] =   '8653000b-43e6-47b7-9cb0-5fc21d4ae340'
GAN_GEN3_COMMAND_CHARACTERISTIC: Final[str] = '8653000c-43e6-47b7-9cb0-5fc21d4ae340'

# GAN Gen4 protocol BLE service
GAN_GEN4_SERVICE: Final[str] =                '00000010-0000-fff7-fff6-fff5fff4fff0'
GAN_GEN4_STATE_CHARACTERISTIC: Final[str] =   '0000fff6-0000-1000-8000-00805f9b34fb'
GAN_GEN4_COMMAND_CHARACTERISTIC: Final[str] = '0000fff5-0000-1000-8000-00805f9b34fb'

# GAN Gen4 engine configuration, the single byte the 0xD4 *command*
# carries : Perf keeps the gyroscope on, Eco cuts it. The answer to
# that command rides the same opcode and does not answer in this
# domain — it is a flag, 1 streaming and 0 not, measured at the cube.
GAN_GEN4_ENGINE_PERF: Final[int] = 0x02
GAN_GEN4_ENGINE_ECO: Final[int] =  0x03

# The six raw channels a Gen4 colour sensor message carries, in the
# order the descriptor declares them. They are uncalibrated readings of
# one optical sensor, not the colours of a facelet : nothing in the
# protocol says which sticker, which scale, or which reference white
# they are read against.
GAN_GEN4_COLOR_CHANNELS: Final[tuple[str, ...]] = (
    'white',
    'red',
    'green',
    'yellow',
    'orange',
    'blue',
)

# Moyu Weilong v10 protocol BLE service
MOYU_WEILONG_SERVICE: Final[str] =                '0783b03e-7735-b5a0-1760-a305d2795cb0'
MOYU_WEILONG_STATE_CHARACTERISTIC: Final[str] =   '0783b03e-7735-b5a0-1760-a305d2795cb1'
MOYU_WEILONG_COMMAND_CHARACTERISTIC: Final[str] = '0783b03e-7735-b5a0-1760-a305d2795cb2'

# Key used by GAN Gen2, Gen3 and Gen4 cubes
GAN_ENCRYPTION_KEY: Final[dict[str, list[int]]] = {
    'key': [
        0x01, 0x02, 0x42, 0x28,
        0x31, 0x91, 0x16, 0x07,
        0x20, 0x05, 0x18, 0x54,
        0x42, 0x11, 0x12, 0x53,
    ],
    'iv': [
        0x11, 0x03, 0x32, 0x28,
        0x21, 0x01, 0x76, 0x27,
        0x20, 0x95, 0x78, 0x14,
        0x32, 0x12, 0x02, 0x43,
    ],
}

# Key used by MoYu AI 2023
MOYU_AI_ENCRYPTION_KEY: Final[dict[str, list[int]]] = {
    'key': [
        0x05, 0x12, 0x02, 0x45,
        0x02, 0x01, 0x29, 0x56,
        0x12, 0x78, 0x12, 0x76,
        0x81, 0x01, 0x08, 0x03,
    ],
    'iv': [
        0x01, 0x44, 0x28, 0x06,
        0x86, 0x21, 0x22, 0x28,
        0x51, 0x05, 0x08, 0x31,
        0x82, 0x02, 0x21, 0x06,
    ],
}


# Key used by MoYu Weilong v10
MOYU_WEILONG_ENCRYPTION_KEY: Final[dict[str, list[int]]] = {
    'key': [
        0x15, 0x77, 0x3A, 0x5C,
        0x67, 0x0E, 0x2D, 0x1F,
        0x17, 0x67, 0x2A, 0x13,
        0x9B, 0x67, 0x52, 0x57,
    ],
    'iv': [
        0x11, 0x23, 0x26, 0x25,
        0x86, 0x2A, 0x2C, 0x3B,
        0x55, 0x06, 0x7F, 0x31,
        0x7E, 0x67, 0x21, 0x57,
    ],
}
