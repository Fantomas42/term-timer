import asyncio
import logging
import sys
import termios
import tty

logger = logging.getLogger(__name__)


class Interface:

    @staticmethod
    def clear_line(full) -> None:
        if full:
            print(f'\r{ " " * 100}\r', flush=True, end='')
        else:
            print('\r', end='')

    @staticmethod
    def beep() -> None:
        print('\a', end='', flush=True)

    async def getch(self, timeout: float | None = None) -> str:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        ch = ''

        try:
            tty.setcbreak(fd)

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
            except asyncio.TimeoutError:  # noqa UP041
                ch = ''
            except Exception as e:
                logger.exception('Error in getch')
                ch = ''
            finally:
                if loop.is_closed():
                    pass
                else:
                    loop.remove_reader(fd)

        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

        self.clear_line(full=True)

        return ch
