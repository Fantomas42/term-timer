import asyncio
import logging
import sys

is_windows = sys.platform in {'win32', 'cygwin'}

if is_windows:
    import msvcrt
else:
    import termios

logger = logging.getLogger(__name__)


class Getcher:

    async def getch(self, mode, timeout: float | None = None) -> str:
        logger.info('Getch %s', mode.upper())

        if is_windows:
            ch = await self.getch_windows(timeout)
        else:
            ch = await self.getch_unix(timeout)

        self.clear_line(full=True)

        logger.info('Getched %s: %s', mode.upper(), repr(ch))

        return ch

    async def getch_windows(self, timeout: float | None = None) -> str:
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        ch = ''

        def windows_getch() -> None:
            try:
                if msvcrt.kbhit():
                    key_bytes = msvcrt.getch()
                    key_str = key_bytes.decode('utf-8', errors='replace')
                    if not future.done():
                        future.set_result(key_str)
                else:
                    loop.call_later(0.01, windows_getch)
            except Exception as e:
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

    async def getch_unix(self, timeout: float | None = None) -> str:
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
                try:
                    ch = sys.stdin.read(1)
                    if not future.done():
                        future.set_result(ch)
                except Exception as e:
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
