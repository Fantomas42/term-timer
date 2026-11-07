"""Tests for the main entry point dispatching the commands."""
import unittest
from argparse import Namespace
from unittest.mock import MagicMock
from unittest.mock import call
from unittest.mock import patch

from term_timer.scripts import timer as entry

# Command name -> name of the coroutine function it runs in the entry point
ASYNC_COMMANDS = {
    'ghost': 'ghost',
    'daily': 'daily',
    'solve': 'timer',
    'train': 'trainer',
    'drill': 'driller',
    'routine': 'routine',
    'reset': 'reset',
    'browse': 'run_browse',
    'config': 'run_config_edit',
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
            patch.object(entry, ASYNC_COMMANDS[command], MagicMock()),
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
            patch.object(entry, 'Server', return_value=server),
        ):
            entry.run_command(
                'serve', Namespace(host='localhost', port=8333),
            )

        self.assertEqual(
            server.run_server.call_args, call('localhost', 8333, debug=True),
        )
