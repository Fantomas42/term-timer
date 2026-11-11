"""Tests for the main entry point dispatching the commands."""
import subprocess  # noqa: S404
import sys
import unittest
from argparse import Namespace
from unittest.mock import MagicMock
from unittest.mock import call
from unittest.mock import patch

from term_timer.scripts import timer as entry

# Command name -> the coroutine function it runs, patched where the entry
# point reads it: browse and config import theirs only when they run
ASYNC_COMMANDS = {
    'ghost': 'term_timer.scripts.timer.ghost',
    'daily': 'term_timer.scripts.timer.daily',
    'solve': 'term_timer.scripts.timer.timer',
    'train': 'term_timer.scripts.timer.trainer',
    'drill': 'term_timer.scripts.timer.driller',
    'routine': 'term_timer.scripts.timer.routine',
    'reset': 'term_timer.scripts.timer.reset',
    'browse': 'term_timer.browse.app.run_browse',
    'config': 'term_timer.config_edit.app.run_config_edit',
}


class TestAsyncioDebug(unittest.TestCase):
    """
    The asyncio debug mode is its own flag, apart from the debug logging.

    The debug logging is exported permanently, being the black box, while
    the asyncio debug mode captures a stack at every scheduled callback:
    a third of the CPU of a running stopwatch.
    """

    @staticmethod
    def run_debug(
            command: str, *, debug: bool, asyncio_debug: bool,
    ) -> object:
        """
        Run a command with the asyncio loop mocked out.

        Returns:
            The debug argument the event loop was started with.

        """
        run = MagicMock(return_value=0)
        with (
            patch.object(entry, 'DEBUG', debug),
            patch.object(entry, 'ASYNCIO_DEBUG', asyncio_debug),
            patch(ASYNC_COMMANDS[command], MagicMock()),
            patch('asyncio.run', run),
        ):
            entry.run_command(command, Namespace())

        run.assert_called_once()
        return run.call_args.kwargs['debug']

    def test_debug_logging_leaves_asyncio_debug_off(self) -> None:
        """The permanent debug logging no longer slows the event loop."""
        for command in ASYNC_COMMANDS:
            with self.subTest(command=command):
                self.assertFalse(
                    self.run_debug(
                        command, debug=True, asyncio_debug=False,
                    ),
                )

    def test_asyncio_debug_flag_enables_it(self) -> None:
        """The dedicated flag turns the asyncio debug mode on."""
        for command in ASYNC_COMMANDS:
            with self.subTest(command=command):
                self.assertTrue(
                    self.run_debug(
                        command, debug=False, asyncio_debug=True,
                    ),
                )

    def test_server_debug_follows_debug_logging(self) -> None:
        """The web server debug mode is not asyncio, it keeps DEBUG."""
        server = MagicMock()
        with (
            patch.object(entry, 'DEBUG', new=True),
            patch.object(entry, 'ASYNCIO_DEBUG', new=False),
            patch('term_timer.server.app.Server', return_value=server),
        ):
            entry.run_command(
                'serve', Namespace(host='localhost', port=8333),
            )

        self.assertEqual(
            server.run_server.call_args, call('localhost', 8333, debug=True),
        )


class TestLazyImports(unittest.TestCase):
    """
    The entry point leaves the modules of a few commands unloaded.

    Textual, behind browse and config, and the web server weigh a third
    of the imports of the entry point, about 120ms paid by every command
    for interfaces that only three of them open.
    """

    def test_entry_point_skips_heavy_interfaces(self) -> None:
        """Importing the entry point loads neither Textual nor the server."""
        code = (
            'import sys; '
            'import term_timer.scripts.timer; '
            'print(sorted('
            'name for name in ('
            '"textual", "term_timer.browse.app", '
            '"term_timer.config_edit.app", "term_timer.server.app") '
            'if name in sys.modules))'
        )
        result = subprocess.run(  # noqa: S603
            [sys.executable, '-c', code],
            capture_output=True,
            check=True,
            text=True,
        )

        self.assertEqual(result.stdout.strip(), '[]')

    def test_entry_point_skips_portaudio(self) -> None:
        """
        Importing the entry point leaves sounddevice unloaded.

        Its import initializes PortAudio, 35ms warm and up to 180ms
        cold: the audio thread pays it, at the first sound only.
        """
        code = (
            'import sys; '
            'import term_timer.scripts.timer; '
            'print("sounddevice" in sys.modules)'
        )
        result = subprocess.run(  # noqa: S603
            [sys.executable, '-c', code],
            capture_output=True,
            check=True,
            text=True,
        )

        self.assertEqual(result.stdout.strip(), 'False')
