"""Shared plumbing for the commands racing an imposed scramble."""
from argparse import Namespace
from pathlib import Path
from random import Random

from cubing_algs.exceptions import InvalidMoveError

from term_timer.bluetooth.replay import load_scramble_replay
from term_timer.exceptions import ReplayError
from term_timer.formatter import format_time
from term_timer.interface.console import console
from term_timer.solve import Solve
from term_timer.stats import SolveStatisticsReporter
from term_timer.timer import Timer


def race_header(title: str, ghost_solve: Solve | None) -> str:
    """
    Build the session header, carrying the time to beat when there is one.

    Args:
        title: The styled title naming the session.
        ghost_solve: The elected ghost, None when nothing is raced yet.

    Returns:
        The header line to print.

    """
    if ghost_solve is None:
        return title

    return f'{ title } [time]{ format_time(ghost_solve.final_time) }[/time]'


def build_race_timer(  # noqa: PLR0913
        options: Namespace, *,
        session: str,
        scramble: str,
        stack: list[Solve],
        rng: Random,
        save_directory: Path,
) -> Timer | None:
    """
    Build the timer of a session run on a single imposed scramble.

    The scramble being given, the whole scramble generation group is
    fixed: no iteration, no cross constraint, no scramble list. What
    remains varies from one command to the next, hence the keywords.

    The save directory, the replay payload and the ghost stay out of the
    Timer signature and are posted here, on the command side.

    Args:
        options: The parsed command options.
        session: The session name the solves are saved under.
        scramble: The scramble every attempt of the session solves.
        stack: The solves seeding the session.
        rng: The random source, seeded when the scramble is.
        save_directory: Where the session writes its solves.

    Returns:
        The ready timer, or None when the replay file is unusable, its
        error being printed.

    """
    try:
        replay = load_scramble_replay(options.replay, scramble)
    except ReplayError as error:
        console.print('😱', str(error), style='warning')
        return None

    instance = Timer(
        cube_size=options.cube,
        iterations=0,
        easy_cross=False,
        x_cross=False,
        edges_oriented=False,
        scramble=scramble,
        scrambles=[],
        session=session,
        free_play=options.free_play,
        show_highlights=options.show_highlights,
        show_doctor=options.show_doctor,
        show_cube=options.show_cube,
        show_reconstruction=options.show_reconstruction,
        show_tps_graph=options.show_tps_graph,
        show_time_graph=options.show_time_graph,
        show_fluency_graph=options.show_fluency_graph,
        show_recognition_graph=options.show_recognition_graph,
        show_steps=options.show_steps,
        method=options.method,
        orientation=options.orientation,
        countdown=options.countdown,
        metronome=options.metronome,
        stack=stack,
        rng=rng,
    )
    instance.save_directory = save_directory

    if replay is not None:
        instance.bluetooth_replay = replay

    instance.elect_ghost()

    return instance


async def run_seeded_race(
        instance: Timer,
        options: Namespace,
        title: str,
) -> int:
    """
    Run the race loop of a session, then report on the scramble.

    The ghost is re-elected after every attempt, so beating it moves the
    target for the next one. The closing summary covers the whole stack,
    seeding solves included, and is skipped while the session holds a
    single attempt: there is nothing to compare yet.

    Args:
        instance: The timer to run.
        options: The parsed command options.
        title: The title of the closing summary.

    Returns:
        Exit code (0 for success, 1 on an invalid move).

    """
    if options.bluetooth or instance.bluetooth_replay is not None:
        await instance.bluetooth_connect(
            use_gyroscope=options.use_gyroscope,
        )

    try:
        while 42:
            done = await instance.start()

            instance.elect_ghost()

            if not done:
                break

        if len(instance.stack) > 1:
            console.print(f'[title]{ title }[/title]')

            stats = SolveStatisticsReporter(
                instance.cube_size, instance.stack,
            )
            stats.print_summary()
            stats.graph('Tendency')

    except InvalidMoveError as error:
        console.print('😱', str(error), style='warning')
        return 1
    finally:
        if instance.bluetooth_interface:
            await instance.bluetooth_disconnect()

    return 0
