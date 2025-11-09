"""Async character input from terminal for user interaction."""

import asyncio
import logging
import os
import sys
from typing import TYPE_CHECKING

is_windows = sys.platform in {'win32', 'cygwin'}

if is_windows:
    import msvcrt  # type: ignore[import-not-found,unused-ignore]
else:
    import termios

logger = logging.getLogger(__name__)


class Getcher:
    """
    Mixin providing async character input from terminal.

    This mixin provides cross-platform asynchronous character input
    functionality for terminal applications. It handles platform-specific
    differences between Windows and Unix-like systems.
    """

    if TYPE_CHECKING:
        # Methods from Terminal mixin
        def clear_line(self, *, full: bool) -> None:
            """
            Clear the current line in the terminal.

            Args:
                full: If True, clear the entire line. If False, clear from
                    cursor position to end of line.

            """
            ...

    async def getch(self, mode: str, timeout: float | None = None) -> str:  # noqa: ASYNC109
        """
        Get a character from the terminal asynchronously.

        Reads a single character from the terminal using platform-specific
        methods. Clears the terminal line after reading and logs the
        operation.

        Args:
            mode: Description of the current input mode for logging purposes.
            timeout: Maximum time in seconds to wait for input. If None,
                waits indefinitely.

        Returns:
            The character read from terminal, or empty string if timeout
            occurs or an error happens.

        """
        logger.info('Getch %s', mode.upper())

        if is_windows:
            ch = await self.getch_windows(timeout)
        else:
            ch = await self.getch_unix(timeout)

        self.clear_line(full=True)

        logger.info('Getched %s: %r', mode.upper(), ch)

        return ch

    @staticmethod
    async def getch_windows(timeout: float | None = None) -> str:  # noqa: ASYNC109
        """
        Get a character from terminal on Windows platform.

        Uses msvcrt module to poll for keyboard input asynchronously on
        Windows. Polls every 10ms until a key is pressed or timeout occurs.

        Args:
            timeout: Maximum time in seconds to wait for input. If None,
                waits indefinitely.

        Returns:
            The character read from terminal, or empty string if timeout
            occurs or an error happens.

        """
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        ch = ''

        def windows_getch() -> None:
            """Poll for keyboard input and resolve future when key pressed."""
            try:
                if msvcrt.kbhit():  # type: ignore[attr-defined]
                    key_bytes = msvcrt.getch()  # type: ignore[attr-defined]
                    key_str = key_bytes.decode('utf-8', errors='replace')
                    if not future.done():
                        future.set_result(key_str)
                else:
                    loop.call_later(0.01, windows_getch)
            except Exception as e:  # noqa: BLE001
                if not future.done():
                    future.set_exception(e)

        loop.call_soon(windows_getch)

        try:
            if timeout is not None:
                ch = await asyncio.wait_for(future, timeout)
            else:
                ch = await future
        except asyncio.TimeoutError:  # noqa: UP041
            ch = ''
        except Exception:
            logger.exception('Error in getch (Windows)')
            ch = ''

        return ch

    @staticmethod
    async def getch_unix(timeout: float | None = None) -> str:  # noqa: ASYNC109
        """
        Get a character from terminal on Unix-like platforms.

        Uses termios to configure stdin for raw mode and asyncio event loop
        to read input asynchronously. Handles up to 3 bytes to support
        multi-byte UTF-8 characters and escape sequences.

        Args:
            timeout: Maximum time in seconds to wait for input. If None,
                waits indefinitely.

        Returns:
            The character read from terminal, or empty string if timeout
            occurs or an error happens.

        """
        fd = sys.stdin.fileno()

        old_settings = termios.tcgetattr(fd)
        term = termios.tcgetattr(fd)
        ch = ''

        try:
            term[3] &= ~(
                termios.ICANON | termios.ECHO |
                termios.IGNBRK | termios.BRKINT
            )
            termios.tcsetattr(fd, termios.TCSAFLUSH, term)

            loop = asyncio.get_running_loop()
            future = loop.create_future()

            def stdin_callback() -> None:
                """Read stdin and resolve future with decoded character."""
                try:
                    ch_bytes = os.read(fd, 3)
                    ch = ch_bytes.decode('utf-8', errors='replace')
                    if not future.done():
                        future.set_result(ch)
                except Exception as e:  # noqa: BLE001
                    if not future.done():
                        future.set_exception(e)

            loop.add_reader(fd, stdin_callback)

            try:
                if timeout is not None:
                    ch = await asyncio.wait_for(future, timeout)
                else:
                    ch = await future
            except asyncio.TimeoutError:  # noqa: UP041
                ch = ''
            except Exception:
                logger.exception('Error in getch (Unix)')
                ch = ''
            finally:
                if not loop.is_closed():
                    loop.remove_reader(fd)

        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

        return ch
