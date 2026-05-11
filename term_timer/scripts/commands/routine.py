"""Routine command."""
import json
import time
from argparse import Namespace
from pathlib import Path
from typing import TYPE_CHECKING

from rich import box
from rich.table import Table

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
    from term_timer.driller import Driller
    from term_timer.timer import Timer
    from term_timer.trainer import Trainer


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
    table.add_column('File', width=30)
    table.add_column('Sessions', width=8, justify='right')
    table.add_column('Bluetooth', width=9, justify='center')
    table.add_column('Comment', width=40)

    for path in routine_files:
        try:
            config = json.loads(path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            continue

        sessions = config.get('sessions', [])
        bluetooth = config.get('bluetooth', False)
        comment = config.get('comment', '')

        session_count = f'[stats]{ len(sessions) }[/stats]'
        bt_str = '[ao5]yes[/ao5]' if bluetooth else '[no-ao]no[/no-ao]'

        table.add_row(
            f'[localhost]{ path.name }[/localhost]',
            session_count,
            bt_str,
            f'[comment]{ comment }[/comment]' if comment else '',
        )

    console.print(table)
    return 0


async def routine(options: Namespace) -> int:  # noqa: C901, PLR0912, PLR0915
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

    use_bluetooth: bool = bool(config.get('bluetooth'))
    use_gyroscope: bool = bool(config.get('use_gyroscope'))
    current: Timer | Trainer | Driller | None = None
    started_at = time.monotonic_ns()

    try:
        for index, session_config in enumerate(sessions):
            session_type = session_config.get('type', '')
            count = session_config.get('count', 0)

            console.print(
                f'🥋 Routine { index + 1 }/{ len(sessions) }:'
                f' { session_type.title() }',
                style='routine',
            )

            if session_type == 'train':
                try:
                    train_instance = build_train_instance(session_config)
                except InvalidCaseError as error:
                    console.print('😱', str(error), style='warning')
                    return 1

                if index == 0 and use_bluetooth:
                    await train_instance.bluetooth_connect(
                        use_gyroscope=use_gyroscope,
                    )
                elif current is not None and current.bluetooth_interface:
                    await current.bluetooth_handoff(train_instance)

                current = train_instance

                await run_session(
                    train_instance,
                    count,
                    show_stats=session_config.get('show_stats', False),
                )

            elif session_type == 'solve':
                solve_instance = build_solve_instance(session_config)

                if index == 0 and use_bluetooth:
                    await solve_instance.bluetooth_connect(
                        use_gyroscope=use_gyroscope,
                    )
                elif current is not None and current.bluetooth_interface:
                    await current.bluetooth_handoff(solve_instance)

                current = solve_instance

                await run_session(
                    solve_instance,
                    count,
                    show_stats=session_config.get('show_stats', False),
                )

            elif session_type == 'drill':
                drill_instance = build_drill_instance(session_config)

                if index == 0 and use_bluetooth:
                    await drill_instance.bluetooth_connect(
                        use_gyroscope=use_gyroscope,
                    )
                elif current is not None and current.bluetooth_interface:
                    await current.bluetooth_handoff(drill_instance)

                current = drill_instance

                await run_session(
                    drill_instance,
                    count,
                    show_stats=session_config.get('show_stats', False),
                )

            else:
                console.print(
                    f'😱 Unknown session type: { session_type }',
                    style='warning',
                )
                return 1

        elapsed_ns = time.monotonic_ns() - started_at
        duration = format_time(elapsed_ns, allow_dnf=False)
        console.print(
            f'[routine]🏆 Routine complete ![/routine] '
            f'[time]{ duration }[/time]',
        )

    finally:
        if current and current.bluetooth_interface:
            await current.bluetooth_disconnect()

    return 0
