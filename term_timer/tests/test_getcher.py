"""Tests for what reading a key does to the terminal."""
import os
import sys
import unittest
from typing import TYPE_CHECKING
from unittest import mock

from term_timer.interface.getcher import Getcher
from term_timer.interface.getcher import is_windows

if not is_windows:
    import termios

if TYPE_CHECKING:
    from collections.abc import Sequence


@unittest.skipIf(is_windows, 'termios is POSIX only')
class TerminalFlagsTestCase(unittest.IsolatedAsyncioTestCase):
    """Tests for the local flags getch applies while it reads."""

    def setUp(self) -> None:
        """Offer a readable descriptor standing in for the terminal."""
        self.read_fd, self.write_fd = os.pipe()
        self.addCleanup(os.close, self.read_fd)
        self.addCleanup(os.close, self.write_fd)

        self.local_flags = (
            termios.ISIG | termios.ICANON | termios.ECHO | termios.IEXTEN
        )
        self.settings = [0, 0, 0, self.local_flags, 0, 0, []]
        self.applied: list[int] = []

    async def read_a_key(self) -> None:
        """Run one full getch, collecting the flags it applies."""
        def tcgetattr(_fd: int) -> list[object]:
            return list(self.settings)

        def tcsetattr(
                _fd: int, _when: int, attributes: 'Sequence[object]',
        ) -> None:
            self.applied.append(int(attributes[3]))  # type: ignore[call-overload]

        with mock.patch.object(termios, 'tcgetattr', tcgetattr), \
             mock.patch.object(termios, 'tcsetattr', tcsetattr), \
             mock.patch.object(
                 sys, 'stdin', mock.Mock(fileno=lambda: self.read_fd),
             ):
            await Getcher.getch_unix(0.01)

    async def test_getch_keeps_the_signals_of_the_terminal(self) -> None:
        r"""
        ISIG survives the read, so the panic key stays a signal.

        IGNBRK and BRKINT used to be cleared here as well. They are
        input flags, and their values in lflag are those of ISIG and
        ICANON: the mask turned the signals of the terminal off for the
        whole read, so Ctrl+\\ and Ctrl+C arrived as ordinary bytes that
        nothing in the application looks at.
        """
        await self.read_a_key()

        self.assertTrue(self.applied[0] & termios.ISIG)

    async def test_getch_still_reads_one_key_at_a_time(self) -> None:
        """What the mask was there for is left untouched."""
        await self.read_a_key()

        self.assertFalse(self.applied[0] & termios.ICANON)
        self.assertFalse(self.applied[0] & termios.ECHO)

    async def test_getch_restores_the_terminal(self) -> None:
        """The flags of the caller are given back, whatever happened."""
        await self.read_a_key()

        self.assertEqual(self.applied[-1], self.local_flags)
