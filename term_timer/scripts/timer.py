"""Main timer application entry point."""
import asyncio
import os
from argparse import Namespace

from term_timer.arguments import COMMAND_RESOLUTIONS
from term_timer.arguments import get_arguments
from term_timer.banner import show_banner
from term_timer.browse.app import run_browse
from term_timer.config import DEBUG
from term_timer.config import DISPLAY_BANNER
from term_timer.config_edit.app import run_config_edit
from term_timer.importers import Importer
from term_timer.interface.terminal import Terminal
from term_timer.logger import LOGGING_PATH
from term_timer.logger import configure_logging
from term_timer.panic import install_panic
from term_timer.publisher import PUBLISHER
from term_timer.scripts.commands.daily import daily
from term_timer.scripts.commands.doctor import doctor
from term_timer.scripts.commands.driller import driller
from term_timer.scripts.commands.ghost import ghost
from term_timer.scripts.commands.manage import manage
from term_timer.scripts.commands.reset import reset
from term_timer.scripts.commands.routine import routine
from term_timer.scripts.commands.timer import timer
from term_timer.scripts.commands.tools import tools
from term_timer.scripts.commands.trainer import trainer
from term_timer.server.app import Server

BANNER_MODES = {
    'ghost': 'Ghost',
    'daily': 'Daily',
    'drill': 'Drilling',
    'routine': 'Routine',
    'serve': 'Server',
    'solve': 'Timer',
    'train': 'Training',
    'cfop': 'CFOP',
    'list': 'Listing',
    'stats': 'Stats',
    'graph': 'Graph',
    'detail': 'Detail',
    'doctor': 'Doctor',
    'index': 'Index',
    'reset': 'Reset',
    'edit': 'Edition',
    'delete': 'Delete',
    'scramble': 'Scrambles',
}

# Commands running a session, hence the only ones publishing anything.
# The stream is bound for the whole life of the process, as the session
# identifier of the protocol says it is: it starts before the first
# state transition and outlives the cube, a session solved without one
# publishing its states just the same.
PUBLISHED_COMMANDS = frozenset(
    {'solve', 'ghost', 'daily', 'train', 'drill', 'routine'},
)


def main() -> int:
    """
    Run term-timer CLI application.

    Returns:
        Exit code (0 for success).

    """
    configure_logging()
    install_panic(LOGGING_PATH)

    options = get_arguments()
    command = COMMAND_RESOLUTIONS.get(options.command, options.command)

    if command not in {'merge', 'import'}:
        Terminal.set_title(f'{ command.title() } - Term-Timer')

    if (
            command in BANNER_MODES
            and DISPLAY_BANNER
            and not os.getenv('BOTTLE_CHILD')
    ):
        show_banner(BANNER_MODES[command])

    if command in PUBLISHED_COMMANDS:
        PUBLISHER.start(f'term-timer { command }')

    reason = 'closed'
    try:
        return run_command(command, options)
    except KeyboardInterrupt:
        reason = 'interrupted'
        return 0
    except Exception:
        reason = 'crashed'
        raise
    finally:
        PUBLISHER.stop(reason)


def run_command(  # noqa: C901, PLR0911, PLR0912
        command: str, options: Namespace,
) -> int:
    """
    Run the resolved command.

    Args:
        command: The resolved command name.
        options: The parsed command options.

    Returns:
        Exit code (0 for success).

    """
    if command == 'ghost':
        return asyncio.run(ghost(options), debug=DEBUG)
    if command == 'daily':
        return asyncio.run(daily(options), debug=DEBUG)
    if command == 'solve':
        return asyncio.run(timer(options), debug=DEBUG)
    if command == 'train':
        return asyncio.run(trainer(options), debug=DEBUG)
    if command == 'drill':
        return asyncio.run(driller(options), debug=DEBUG)
    if command == 'routine':
        return asyncio.run(routine(options), debug=DEBUG)
    if command == 'reset':
        return asyncio.run(reset(options), debug=DEBUG)
    if command == 'browse':
        asyncio.run(run_browse(), debug=DEBUG)
        return 0
    if command == 'config':
        asyncio.run(run_config_edit(), debug=DEBUG)
        return 0
    if command == 'import':
        return Importer().import_file(options.source)
    if command == 'serve':
        Server().run_server(options.host, options.port, debug=DEBUG)
        return 0
    if command == 'doctor':
        return doctor(options)
    if command in {'edit', 'delete', 'index', 'merge', 'scramble'}:
        return manage(command, options)
    return tools(command, options)
