"""Routine session builders and runner."""
from argparse import Namespace
from random import Random
from typing import TypedDict

from term_timer.config import CUBE_METHOD
from term_timer.config import CUBE_ORIENTATION
from term_timer.config import DISPLAY_CONFIG
from term_timer.config import TIMER_CONFIG
from term_timer.config import TRAINER_STEP
from term_timer.driller import Driller
from term_timer.in_out import load_solves
from term_timer.stats import DrillStatistics
from term_timer.stats import SolveStatisticsReporter
from term_timer.stats import TrainerStatistics
from term_timer.timer import Timer
from term_timer.trainer import Trainer


class SessionConfig(TypedDict, total=False):
    """Typed shape of a single routine session config dict."""

    type: str
    count: int
    # train fields
    step: str
    cases: list[str]
    oldest: int
    slowest: int
    random: int
    new_cases_limit: int
    filters: list[str]
    states: list[str]
    show_solution: bool
    show_breakdown: bool
    # solve fields
    cube: int
    session: str
    iterations: int
    easy_cross: bool
    x_cross: bool
    edges_oriented: bool
    scramble: str
    show_highlights: bool
    show_doctor: bool
    show_reconstruction: bool
    show_tps_graph: bool
    show_time_graph: bool
    show_fluency_graph: bool
    show_recognition_graph: bool
    show_steps: bool
    method: str
    countdown: int
    # drill fields
    algorithm: str
    duration: int
    # daily fields
    date: str
    # ghost fields
    reference: str
    # shared
    free_play: bool
    show_cube: bool
    orientation: str
    metronome: float
    show_stats: bool


def display_flag(
        session_config: SessionConfig,
        key: str,
        config_key: str,
) -> bool:
    """
    Resolve a display toggle of a session, falling back on the config.

    A routine step says what it wants to see; what it says nothing about
    is displayed the way the configuration displays it everywhere else.

    Args:
        session_config: The session the toggle is read from.
        key: The session key naming the toggle.
        config_key: The display configuration key backing it.

    Returns:
        Whether that display is on for the session.

    """
    return bool(
        session_config.get(key, DISPLAY_CONFIG.get(config_key, True)),
    )


def race_options(session_config: SessionConfig) -> Namespace:
    """
    Adapt a routine session config to what ``build_race_timer`` reads.

    A Namespace, and not sixteen keyword arguments: ``build_race_timer``
    is written against the parsed command line, and both its callers
    pass one. Handing it the same shape keeps a routine step a second
    caller of the very function the commands use, instead of turning it
    into a function of sixteen named parameters and rewriting its two
    existing callers around it.

    Only the keys the function actually reads are set. ``attempts`` is
    not one of them: a race step gets its count from ``race_loop``.
    ``replay`` is empty, a routine having no replay file to play.

    Args:
        session_config: The session to adapt.

    Returns:
        The namespace the race timer builder reads its options from.

    """
    return Namespace(
        cube=session_config.get('cube', 3),
        replay='',
        free_play=session_config.get('free_play', False),
        show_highlights=display_flag(
            session_config, 'show_highlights', 'highlights',
        ),
        show_doctor=display_flag(session_config, 'show_doctor', 'doctor'),
        show_cube=display_flag(session_config, 'show_cube', 'scramble'),
        show_reconstruction=display_flag(
            session_config, 'show_reconstruction', 'reconstruction',
        ),
        show_tps_graph=display_flag(
            session_config, 'show_tps_graph', 'tps_graph',
        ),
        show_time_graph=display_flag(
            session_config, 'show_time_graph', 'time_graph',
        ),
        show_fluency_graph=display_flag(
            session_config, 'show_fluency_graph', 'fluency_graph',
        ),
        show_recognition_graph=display_flag(
            session_config, 'show_recognition_graph', 'recognition_graph',
        ),
        show_steps=session_config.get('show_steps', False),
        method=session_config.get('method', CUBE_METHOD),
        orientation=session_config.get('orientation', CUBE_ORIENTATION),
        countdown=session_config.get(
            'countdown', TIMER_CONFIG.get('countdown', 0),
        ),
        metronome=session_config.get(
            'metronome', TIMER_CONFIG.get('metronome', 0.0),
        ),
    )


def build_train_instance(session_config: SessionConfig) -> Trainer:
    """
    Build a Trainer from a routine session config dict.

    Returns:
        Configured Trainer instance.

    """
    instance = Trainer(
        step=session_config.get('step', TRAINER_STEP or 'oll'),
        case_codes=session_config.get('cases', []),
        oldest=session_config.get('oldest', 0),
        slowest=session_config.get('slowest', 0),
        random=int(session_config.get('random', 0)),
        filters=session_config.get('filters', []),
        states=session_config.get('states', []),
        free_play=session_config.get('free_play', False),
        show_solution=session_config.get('show_solution', False),
        show_breakdown=session_config.get('show_breakdown', False),
        show_cube=session_config.get(
            'show_cube', DISPLAY_CONFIG.get('scramble', True),
        ),
        orientation=session_config.get('orientation', CUBE_ORIENTATION),
        metronome=session_config.get(
            'metronome', TIMER_CONFIG.get('metronome', 0.0),
        ),
        new_cases_limit=session_config.get('new_cases_limit', 5),
        rng=Random(),  # noqa: S311
    )
    instance.trainer_line()
    return instance


def build_solve_instance(session_config: SessionConfig) -> Timer:
    """
    Build a Timer from a routine session config dict.

    Returns:
        Configured Timer instance.

    """
    cube_size = session_config.get('cube', 3)
    free_play = session_config.get('free_play', False)

    session_parts = []
    if session_config.get('session'):
        session_parts.append(session_config['session'])
    if not session_config.get('scramble'):
        if session_config.get('easy_cross'):
            session_parts.append('easy-cross')
        elif session_config.get('x_cross'):
            session_parts.append('x-cross')
        elif session_config.get('edges_oriented'):
            session_parts.append('edges-oriented')
        elif session_config.get('iterations'):
            session_parts.append(f'iterations-{ session_config["iterations"] }')
    session_name = '-'.join(session_parts)

    stack = [] if free_play else load_solves(cube_size, session_name)

    return Timer(
        cube_size=cube_size,
        iterations=session_config.get('iterations', 0),
        easy_cross=session_config.get('easy_cross', False),
        x_cross=session_config.get('x_cross', False),
        edges_oriented=session_config.get('edges_oriented', False),
        scramble=session_config.get('scramble', ''),
        scrambles=[],
        session=session_name,
        free_play=free_play,
        show_highlights=display_flag(
            session_config, 'show_highlights', 'highlights',
        ),
        show_doctor=display_flag(session_config, 'show_doctor', 'doctor'),
        show_cube=display_flag(session_config, 'show_cube', 'scramble'),
        show_reconstruction=display_flag(
            session_config, 'show_reconstruction', 'reconstruction',
        ),
        show_tps_graph=display_flag(
            session_config, 'show_tps_graph', 'tps_graph',
        ),
        show_time_graph=display_flag(
            session_config, 'show_time_graph', 'time_graph',
        ),
        show_fluency_graph=display_flag(
            session_config, 'show_fluency_graph', 'fluency_graph',
        ),
        show_recognition_graph=display_flag(
            session_config, 'show_recognition_graph', 'recognition_graph',
        ),
        show_steps=session_config.get('show_steps', False),
        method=session_config.get('method', CUBE_METHOD),
        orientation=session_config.get('orientation', CUBE_ORIENTATION),
        countdown=session_config.get(
            'countdown', TIMER_CONFIG.get('countdown', 0),
        ),
        metronome=session_config.get(
            'metronome', TIMER_CONFIG.get('metronome', 0.0),
        ),
        stack=stack,
        counter_start=0,
        rng=Random(),  # noqa: S311
    )


def build_drill_instance(session_config: SessionConfig) -> Driller:
    """
    Build a Driller from a routine session config dict.

    Returns:
        Configured Driller instance.

    """
    return Driller(
        algorithm=session_config.get('algorithm', ''),
        times=session_config.get('count', 0),
        duration=session_config.get('duration', 0),
        orientation=session_config.get('orientation', CUBE_ORIENTATION),
        countdown=session_config.get(
            'countdown', TIMER_CONFIG.get('countdown', 0),
        ),
        metronome=session_config.get(
            'metronome', TIMER_CONFIG.get('metronome', 0.0),
        ),
    )


def show_instance_stats(instance: Timer | Trainer | Driller) -> None:
    """Display end-of-session statistics for solve and drill instances."""
    if isinstance(instance, Timer):
        if len(instance.stack_done) > 1:
            SolveStatisticsReporter(
                instance.cube_size,
                instance.stack_done,
            ).print_summary('Session ')
    elif isinstance(instance, Trainer) and len(instance.session_data) >= 2:
        TrainerStatistics(
            instance.session_data,
            instance.trainings.cases,
        ).print_summary()
    elif isinstance(instance, Driller) and len(instance.rep_times) >= 2:
        DrillStatistics(
            instance.rep_times,
            instance.rep_tps,
            instance.rep_fluencies,
            qtm=instance.algorithm.metrics.qtm,
        ).print_summary()


async def run_session(
        instance: Timer | Trainer | Driller,
        count: int,
        *,
        show_stats: bool = False,
) -> None:
    """
    Run start() in a loop until count is reached or user quits a step.

    Errors propagate: the runner holds no policy of its own, the caller
    chaining the sessions decides what a failing one costs.
    """
    solves_done = 0

    while 42:
        done = await instance.start()

        if done:
            solves_done += 1
            if count and solves_done >= count:
                break
        else:
            break

    if show_stats:
        show_instance_stats(instance)
