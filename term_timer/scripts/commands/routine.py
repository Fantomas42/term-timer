"""Routine command."""
import json
import time
from argparse import Namespace
from pathlib import Path
from typing import TYPE_CHECKING

from cubing_algs.exceptions import InvalidMoveError
from rich import box
from rich.table import Table

from term_timer.config import CubeDevice
from term_timer.constants import ROUTINES_DIRECTORY
from term_timer.exceptions import InvalidCaseError
from term_timer.formatter import format_time
from term_timer.interface.console import console
from term_timer.routine import SessionConfig
from term_timer.routine import build_drill_instance
from term_timer.routine import build_solve_instance
from term_timer.routine import build_train_instance
from term_timer.routine import run_session

if TYPE_CHECKING:
    from collections.abc import Callable

    from term_timer.driller import Driller
    from term_timer.timer import Timer
    from term_timer.trainer import Trainer

    SessionInstance = Timer | Trainer | Driller
    SessionBuilder = Callable[[SessionConfig], SessionInstance]

SESSION_BUILDERS: 'dict[str, SessionBuilder]' = {
    'train': build_train_instance,
    'solve': build_solve_instance,
    'drill': build_drill_instance,
}


def resolve_routine_cube(selector: object) -> CubeDevice | None:
    """
    Resolve the cube a routine file asks for.

    The ``bluetooth`` key holds either a boolean, asking for the cube the
    configuration designates, or the label of one of the configured
    cubes, so that a routine can pin the cube it was tuned for.

    Args:
        selector: Raw value of the routine ``bluetooth`` key.

    Returns:
        The cube to connect to, or None to run without one.

    """
    if isinstance(selector, str):
        cleaned = CubeDevice.clean_selector(selector)

        if not cleaned:
            console.print(
                f'😱 Unknown cube in routine: { selector }',
                style='warning',
            )
            return None

        return CubeDevice.resolve(cleaned)

    if selector:
        return CubeDevice.resolve(None)

    return None


def resolve_routine_gyroscope(selector: object) -> bool | None:
    """
    Resolve the gyroscope setting a routine file asks for.

    The ``use_gyroscope`` key is optional: left out, the cube being
    connected keeps its own setting, exactly like the ``-g`` option left
    out of the command line.

    Args:
        selector: Raw value of the routine ``use_gyroscope`` key.

    Returns:
        The setting to force on the driver, or None to leave the choice
        to the cube.

    """
    if selector is None:
        return None

    return bool(selector)


def list_routines() -> int:
    """
    List available routine files from the routines directory.

    Returns:
        Exit code (0 for success).

    """
    routine_files = sorted(ROUTINES_DIRECTORY.glob('*.json'))

    if not routine_files:
        console.print('🤔 No routines found.', style='warning')
        return 0

    table = Table(
        title=f'Routines in { ROUTINES_DIRECTORY }',
        box=box.SIMPLE,
    )
    table.add_column('Name')
    table.add_column('Steps', width=8, justify='right')
    table.add_column('Bluetooth', width=9, justify='center')
    table.add_column('Comment')

    for path in routine_files:
        try:
            config = json.loads(path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            continue

        sessions = config.get('sessions', [])
        bluetooth = config.get('bluetooth', False)
        comment = config.get('comment', '')

        session_count = f'[stats]{ len(sessions) }[/stats]'
        bt_str = (
            '[success]Yes[/success]'
            if bluetooth else '[warning]No[/warning]'
        )

        table.add_row(
            f'[localhost]{ path.name.replace(".json", "") }[/localhost]',
            session_count,
            bt_str,
            f'[comment]{ comment }[/comment]' if comment else '',
        )

    console.print(table)
    return 0


async def run_routine_sessions(
        sessions: list[SessionConfig],
        cube: CubeDevice | None,
        *,
        use_gyroscope: bool | None,
) -> int:
    """
    Build and run every session of a routine, in order.

    The cube is connected once, by the first session, then handed over
    from one session to the next, and released whatever happens.

    Args:
        sessions: The sessions the routine chains.
        cube: The cube to connect to, or None to run without one.
        use_gyroscope: The gyroscope setting to force on the driver, or
            None to leave the choice to the cube.

    Returns:
        Exit code (0 for success).

    """
    current: SessionInstance | None = None
    started_at = time.monotonic_ns()

    try:
        for index, session_config in enumerate(sessions):
            session_type = session_config.get('type', '')

            console.print(
                f'🥋 Routine { index + 1 }/{ len(sessions) }:'
                f' { session_type.title() }',
                style='routine',
            )

            builder = SESSION_BUILDERS.get(session_type)

            if builder is None:
                console.print(
                    f'😱 Unknown session type: { session_type }',
                    style='warning',
                )
                return 1

            try:
                instance = builder(session_config)
            except InvalidCaseError as error:
                console.print('😱', str(error), style='warning')
                return 1

            if index == 0 and cube is not None:
                await instance.bluetooth_connect(
                    cube,
                    use_gyroscope=use_gyroscope,
                )
            elif current is not None and current.bluetooth_interface:
                await current.bluetooth_handoff(instance)

            current = instance

            await run_session(
                instance,
                session_config.get('count', 0),
                show_stats=session_config.get('show_stats', False),
            )

        elapsed_ns = time.monotonic_ns() - started_at
        duration = format_time(elapsed_ns, allow_dnf=False)
        console.print(
            f'[routine]🏆 Routine complete ![/routine] '
            f'[time]{ duration }[/time]',
        )

    except InvalidMoveError as error:
        console.print('😱', str(error), style='warning')
        return 1
    finally:
        if current and current.bluetooth_interface:
            await current.bluetooth_disconnect()

    return 0


async def routine(options: Namespace) -> int:
    """
    Run a daily practice routine from a JSON config file.

    Returns:
        Exit code (0 for success).

    """
    if not options.routine_file:
        return list_routines()

    if options.routine_file.endswith('.json'):
        config_path = Path(options.routine_file)
    else:
        config_path = ROUTINES_DIRECTORY / f'{ options.routine_file }.json'

    if not config_path.exists():
        console.print(
            f'😱 Routine not found: { options.routine_file }',
            style='warning',
        )
        return 1

    config = json.loads(
        config_path.read_text(encoding='utf-8'),
    )
    sessions: list[SessionConfig] = config.get('sessions', [])

    if not sessions:
        console.print('🤔 No sessions defined.', style='warning')
        return 0

    cube = resolve_routine_cube(config.get('bluetooth'))
    use_gyroscope = resolve_routine_gyroscope(config.get('use_gyroscope'))

    return await run_routine_sessions(
        sessions,
        cube,
        use_gyroscope=use_gyroscope,
    )
