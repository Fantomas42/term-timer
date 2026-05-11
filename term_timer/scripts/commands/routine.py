"""Routine command."""
import json
import time
from argparse import Namespace
from pathlib import Path

from term_timer.driller import Driller
from term_timer.exceptions import InvalidCaseError
from term_timer.formatter import format_time
from term_timer.interface.console import console
from term_timer.routine import SessionConfig
from term_timer.routine import build_drill_instance
from term_timer.routine import build_solve_instance
from term_timer.routine import build_train_instance
from term_timer.routine import run_session
from term_timer.timer import Timer
from term_timer.trainer import Trainer


async def routine(options: Namespace) -> int:  # noqa: C901, PLR0912, PLR0915
    """
    Run a daily practice routine from a JSON config file.

    Returns:
        Exit code (0 for success).

    """
    config_path = Path(options.routine_file)
    if not config_path.exists():  # noqa: ASYNC240
        console.print(
            f'😱 Routine file not found: { config_path }',
            style='warning',
        )
        return 1

    config = json.loads(
        config_path.read_text(encoding='utf-8'),  # noqa: ASYNC240
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
