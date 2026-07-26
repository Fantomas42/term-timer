"""Timer command."""
from argparse import Namespace
from pathlib import Path
from random import Random

from cubing_algs.exceptions import InvalidMoveError
from cubing_algs.parsing import parse_moves

from term_timer.aggregator import SolvesDoctorAggregator
from term_timer.bluetooth.replay import load_replay
from term_timer.constants import DOCTOR_SESSION_BASELINE_MIN
from term_timer.exceptions import ReplayError
from term_timer.in_out import load_scrambles
from term_timer.in_out import load_solves
from term_timer.interface.console import console
from term_timer.interface.doctor import DoctorReporter
from term_timer.solve import Solve
from term_timer.stats import SolveStatisticsReporter
from term_timer.timer import Timer


def print_session_doctor(
    method_name: str,
    stack_done: list[Solve],
    history: list[Solve],
) -> None:
    """
    Print the aggregated doctor report of the solves just done.

    Displayed when the round has more than two analysable solves. Trend
    markers compare the round against a baseline of the analysable solves
    preceding it, sized as max(round size, DOCTOR_SESSION_BASELINE_MIN).
    When fewer than DOCTOR_SESSION_BASELINE_MIN prior solves are
    available the baseline is too thin, so no trend is shown.

    Args:
        method_name: Method used to analyse the solves.
        stack_done: Solves of the round that just ended.
        history: Solves of the session preceding the round.

    """
    analysable_done = [solve for solve in stack_done if solve.analysable]
    if len(analysable_done) <= 2:
        return

    aggregator = SolvesDoctorAggregator(method_name, analysable_done)
    if not aggregator.results['total']:
        return

    previous = None
    earlier_analysable = [solve for solve in history if solve.analysable]
    baseline_size = max(len(analysable_done), DOCTOR_SESSION_BASELINE_MIN)
    previous_window = earlier_analysable[-baseline_size:]
    if len(previous_window) >= DOCTOR_SESSION_BASELINE_MIN:
        previous = SolvesDoctorAggregator(
            method_name, previous_window,
        ).results

    reporter = DoctorReporter(aggregator.results)
    console.print(reporter.report(previous))


async def timer(options: Namespace) -> int:  # noqa: C901, PLR0912, PLR0915
    """
    Run speedcubing timer with scrambles and solve tracking.

    Returns:
        Exit code (0 for success).

    """
    cube = options.cube

    replay = None
    if options.replay:
        try:
            replay = load_replay(options.replay)
        except ReplayError as error:
            console.print('😱', str(error), style='warning')
            return 1

    session_parts = []
    if options.session:
        session_parts.append(options.session)

    scrambles = []
    if replay is not None:
        scrambles = [
            parse_moves(solve['scramble'])
            for solve in replay['solves']
        ]
    elif options.scrambles_file:
        scrambles_file = Path(options.scrambles_file)
        scrambles = load_scrambles(scrambles_file)
        if not scrambles:
            console.print(
                f'🤔 No scrambles in { scrambles_file.name }.',
                style='warning',
            )
            return 0
        session_parts.append(f'scrambles-{ scrambles_file.stem }')
    elif not options.scramble:
        if options.seed:
            session_parts.append(f'seed-{ options.seed }')
        if options.easy_cross:
            session_parts.append('easy-cross')
        elif options.x_cross:
            session_parts.append('x-cross')
        elif options.edges_oriented:
            session_parts.append('edges-oriented')
        elif options.iterations:
            session_parts.append(f'iterations-{ options.iterations }')

    session = '-'.join(session_parts)

    stack = [] if options.free_play else load_solves(cube, session)

    rng = Random(options.seed) if options.seed else Random()  # noqa: S311

    instance = Timer(
        cube_size=cube,
        iterations=options.iterations,
        easy_cross=options.easy_cross,
        x_cross=options.x_cross,
        edges_oriented=options.edges_oriented,
        scramble=options.scramble,
        scrambles=scrambles,
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

    if replay is not None:
        instance.bluetooth_replay = replay

    if options.bluetooth or replay is not None:
        await instance.bluetooth_connect(
            use_gyroscope=options.use_gyroscope,
        )

    solves_done = 0

    try:
        while 42:
            done = await instance.start()

            if done:
                solves_done += 1

                if options.solves and solves_done >= options.solves:
                    break
            else:
                break

        if len(instance.stack) > len(instance.stack_done):
            session_stats = SolveStatisticsReporter(cube, instance.stack)
            session_stats.print_summary('Session ')

        if len(instance.stack_done) > 1:
            round_stats = SolveStatisticsReporter(cube, instance.stack_done)
            round_stats.print_summary(
                'Free Play ' if options.free_play else 'Current ',
                'round',
            )

        if options.show_doctor:
            print_session_doctor(
                options.method, instance.stack_done, stack,
            )

    except InvalidMoveError as error:
        console.print('😱', str(error), style='warning')
    finally:
        if instance.bluetooth_interface:
            await instance.bluetooth_disconnect()

    return 0
