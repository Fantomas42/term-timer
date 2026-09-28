"""Solve detail, update, and delete views."""
from pathlib import Path
from typing import TYPE_CHECKING
from typing import cast

from bottle import abort
from bottle import redirect
from cubing_algs.annotations import CubeOrientation
from cubing_algs.constants import ORIENTATION_FACE_MOVES

from term_timer.constants import SECOND
from term_timer.constants import SOLVES_DIRECTORY
from term_timer.constants import SolveFlag
from term_timer.constants import SolveFlagInput
from term_timer.doctor import generate_solve_diagnostics
from term_timer.formatter import format_duration
from term_timer.formatter import format_session_name
from term_timer.formatter import format_term_timer_case_url
from term_timer.highlights import generate_solve_highlights
from term_timer.in_out import load_all_solves
from term_timer.in_out import save_solves
from term_timer.methods import METHOD_ANALYSERS
from term_timer.server.annotations import BreadcrumbItem
from term_timer.server.annotations import FluencyData

if TYPE_CHECKING:
    from term_timer.methods.annotations import StepSummary
    from term_timer.methods.base import Analyser
from term_timer.server.annotations import PlayerData
from term_timer.server.annotations import RecognitionData
from term_timer.server.annotations import ScatterPoint
from term_timer.server.annotations import SolveDetailContext
from term_timer.server.annotations import SolveStepRow
from term_timer.server.annotations import StepCase
from term_timer.server.annotations import StepMarker
from term_timer.server.annotations import StepMetric
from term_timer.server.annotations import StepPanel
from term_timer.server.annotations import TPSData
from term_timer.server.filters import alg_tokens
from term_timer.server.filters import count_tone
from term_timer.server.filters import fluency_tone
from term_timer.server.filters import get_ohtm_delta
from term_timer.server.filters import get_step_case
from term_timer.server.filters import metric_tone
from term_timer.server.filters import optimized_markup
from term_timer.server.filters import overheads_markup
from term_timer.server.filters import pauses_markup
from term_timer.server.filters import plain_tokens
from term_timer.server.views.base import View
from term_timer.solve import Solve


class SolveLocation:
    """Where the solves of a session are stored and served."""

    directory: Path = SOLVES_DIRECTORY
    url_prefix = ''

    @classmethod
    def session_url(cls, cube: int, session: str) -> str:
        """
        Build the URL of a session.

        Returns:
            Absolute path of the session page.

        """
        return f'{ cls.url_prefix }/{ cube }/{ session }/'

    @classmethod
    def breadcrumb(cls, cube: int, session: str,
                   solve_id: int) -> list[BreadcrumbItem]:
        """
        Build the breadcrumb of a solve page.

        Returns:
            Home, the session, then the solve itself.

        """
        name = (
            'All sessions' if session == 'all'
            else format_session_name(session or 'default')
        )
        return [
            {'label': 'Home', 'href': '/'},
            {
                'label': f'{ name } { cube }x{ cube }x{ cube }',
                'href': cls.session_url(cube, session),
            },
            {'label': f'#{ solve_id }', 'href': ''},
        ]


class SolveDetailView(SolveLocation, View):
    """View for displaying detailed analysis of a single solve."""

    template_name = 'v2/solve.html'

    def __init__(self, cube: int, session: str, solve_id: int,
                 method_name: str, orientation: CubeOrientation) -> None:
        """
        Initialize solve detail view.

        Args:
            cube: Cube size (2-7).
            session: Session identifier or 'all' for all sessions.
            solve_id: 1-based solve identifier within the session.
            method_name: Solving method to apply for analysis.
            orientation: Cube orientation for display.

        """
        self.cube = cube
        self.session = session

        self.solves = load_all_solves(
            cube,
            [] if session == 'all' else [session],
            [], [],
            directory=self.directory,
        )

        self.solve_id = solve_id
        self.solve_index = solve_id - 1
        try:
            self.solve = self.solves[self.solve_index]
        except IndexError:
            abort(404, 'Invalid solve ID')

        method_name = method_name.strip().lower()
        if method_name:
            self.solve.method_name = method_name
        self.solve.orientation = orientation

    def legacy(self, *, v1: bool) -> 'SolveDetailView':
        """
        Render the V1 page instead, kept to compare with the V2 one until
        the V1 is removed.

        Args:
            v1: Whether the V1 page is asked for, by ?v1 in the URL.

        Returns:
            The view itself.

        """
        if v1:
            self.template_name = 'solve.html'
        return self

    def get_context(self) -> SolveDetailContext:
        """
        Build context with solve details and analysis data.

        Returns:
            Dictionary containing solve data, reconstruction, timing charts,
            TPS metrics, and step analysis.

        """
        tps: list[TPSData] = []
        steps: list[StepMarker] = []
        scatter: list[ScatterPoint] = []
        fluencies: list[FluencyData] = []
        recognitions: list[RecognitionData] = []

        # A DNF has a final time of 0: only the valid solves are ranked.
        ranks = sorted(s.final_time for s in self.solves if s.final_time)
        rank = (
            ranks.index(self.solve.final_time) + 1
            if self.solve.final_time else None
        )

        if self.solve.advanced:
            scatter = [
                {
                    'y': self.solve.move_times[i][1] / 1000,
                    'x': i + 1,
                }
                for i in range(len(self.solve.move_times))
            ]

            method_applied = cast('Analyser', self.solve.method_applied)

            for s in method_applied.summary:
                if s['type'] not in {'skipped', 'virtual'}:
                    index = s['index'][-1] + 1
                    steps.append(
                        {
                            'x': index,
                            'y': self.solve.move_times[index - 1][1] / 1000,
                            'label': s['name'],
                        },
                    )
                    tps.append(
                        {
                            'tps': Solve.compute_tps(s['qtm'], s['total']),
                            'etps': Solve.compute_tps(s['qtm'], s['execution']),
                            'label': s['name'],
                        },
                    )
                    fluencies.append(
                        {
                            'fluency': Solve.compute_fluency(s['moves']),
                            'label': s['name'],
                        },
                    )
                    recognitions.append(
                        {
                            'recognition': s['recognition'] / SECOND,
                            'execution': s['execution'] / SECOND,
                            'label': s['name'],
                        },
                    )

        reconstruction_text = self.solve.method_text_builder(
            multiple=False,
        )
        step_index: dict[str, int] = {}
        index = 0
        for line in reconstruction_text.split('\n'):
            if not line:
                continue
            moves, comment = line.split('//')
            name = comment
            if 'Reco' in name:
                name = name.split('Reco')[0]
            if '(' in name:
                name = name.split('(')[0]
            name = name.strip()
            step_index[name] = index
            if ' ' in name:
                name = name.split(' ')[0]
                if name not in step_index:
                    step_index[name] = index

            index += len(moves.strip().split(' '))

        return {
            'cube': self.cube,
            'session': self.session,
            'session_url': self.session_url(self.cube, self.session),
            'solve': self.solve,
            'solve_id': self.solve_id,
            'solves': self.solves,
            'scatter': scatter,
            'steps': steps,
            'highlights': generate_solve_highlights(self.solve),
            'diagnostics': generate_solve_diagnostics(self.solve),
            'tps': tps,
            'fluencies': fluencies,
            'recognitions': recognitions,
            'reconstruction_text': reconstruction_text,
            'reconstruction_timing': self.solve.reconstruction_steps_timing,
            'reconstruction_index': step_index,
            'rank': rank,
            'ranked': len(ranks),
            'available_orientations': ORIENTATION_FACE_MOVES,
            'available_methods': list(METHOD_ANALYSERS.keys()),
            'breadcrumb': self.breadcrumb(
                self.cube, self.session, self.solve_id,
            ),
            'previous_url': self.solve_url(self.solve_id - 1),
            'next_url': self.solve_url(self.solve_id + 1),
            'step_rows': self.step_rows() if self.solve.advanced else [],
            'replay': self.replay_data(reconstruction_text, step_index),
        }

    def solve_url(self, solve_id: int) -> str:
        """
        Build the URL of another solve of the same session.

        Returns:
            The solve page, or an empty string past either end.

        """
        if not 1 <= solve_id <= len(self.solves):
            return ''
        return f'{ self.session_url(self.cube, self.session) }{ solve_id }/'

    def replay_data(self, reconstruction_text: str,
                    step_index: dict[str, int]) -> PlayerData:
        """
        Build what the replay module plays: moves, timings, step starts.

        Returns:
            The reconstruction, the scramble, the puzzle and the
            start and end of every move.

        """
        timing: list[tuple[int, int]] = []
        if self.solve.advanced:
            timing = [
                (start, end)
                for start, end, _move in (
                    self.solve.reconstruction_steps_timing
                )
            ]
        return {
            'alg': reconstruction_text,
            'setup': str(self.solve.scramble),
            'anchor': 'start',
            'puzzle': f'{ self.cube }x{ self.cube }x{ self.cube }',
            'timing': timing,
            'index': step_index,
        }

    def step_rows(self) -> list[SolveStepRow]:
        """
        Build the reconstruction, one row per step, a panel per tab.

        Returns:
            The steps of the applied method, in order.

        """
        method_applied = cast('Analyser', self.solve.method_applied)

        return [
            {
                'name': step['name'],
                'slug': step['name'].lower().replace(' ', '-'),
                'type': step['type'],
                'share': round(step['total_percent'], 1),
                'case': self.step_case(step),
                'skip': 'SKIP' in step['case'],
                'panels': self.step_panels(step, method_applied),
            }
            for step in method_applied.summary
        ]

    @staticmethod
    def step_case(step: 'StepSummary') -> StepCase | None:
        """
        Describe the case recognised at a step, SKIP excluded.

        Returns:
            The case code, label, link and thumbnail parameters, or None.

        """
        if not step['case'] or 'SKIP' in step['case']:
            return None

        case = get_step_case(step['name'], step['case'])
        if case.code == 'SKIP':
            return None

        label = (
            case.aliases[0] if case.aliases
            else ', '.join(step['case_infos'])
        )
        return {
            'code': case.code,
            'label': label,
            'href': format_term_timer_case_url(case),
            'algorithm': str(case.main_algorithm),
            'mode': step['name'].split(' ', maxsplit=1)[0].lower(),
            'arrows': case.arrows,
        }

    def step_panels(self, step: 'StepSummary',
                    method_applied: 'Analyser') -> dict[str, StepPanel]:
        """
        Build the moves and metrics each reconstruction tab shows.

        The time tab carries the pauses: the V1 pauses tab is merged
        into it. The raw and issues tabs are only shown in debug.

        Returns:
            The panels by tab slug.

        """
        solve = self.solve
        name = step['name']
        virtual = step['type'] == 'virtual'

        def metric(label: str, value: str, tone: str = '',
                   *, strong: bool = False) -> StepMetric:
            return {
                'label': label, 'value': value,
                'tone': tone, 'strong': strong,
            }

        def aufs(value: int | None) -> tuple[str, str]:
            if value is None:
                return '---', ''
            return str(value), count_tone(value, 2)

        def percent(value: float) -> str:
            return f'{ value:.2f}%'

        pauses = solve.pauses(step['moves_humanized'])
        fluency = solve.compute_fluency(step['moves_humanized'])
        missed = solve.missed_moves(step['moves_humanized'])
        htm = step['moves_prettified'].metrics.htm
        pre_auf, pre_auf_tone = aufs(step['aufs'][0])
        post_auf, post_auf_tone = aufs(step['aufs'][1])
        optimized, optimized_algorithm = optimized_markup(step)
        gains = (
            step['moves_prettified'].metrics.qtm
            - optimized_algorithm.metrics.qtm
        )
        ohtm = get_ohtm_delta(step)

        return {
            'time': {
                'tokens': [] if virtual else alg_tokens(
                    pauses_markup(step, solve),
                ),
                'metrics': [
                    metric('Reco', format_duration(step['recognition'])),
                    metric('Exec', format_duration(step['execution'])),
                    metric('Time', format_duration(step['total']),
                           strong=True),
                    metric('HTM', str(htm), metric_tone(
                        htm, method_applied, 'moves', name,
                    )),
                    metric('TPS', f'{ solve.compute_tps(
                        step["qtm"], step["total"]):.2f}'),
                    metric('eTPS', f'{ solve.compute_tps(
                        step["qtm"], step["execution"]):.2f}'),
                    metric('Flu.', f'{ fluency }', fluency_tone(fluency)),
                    metric('Pauses', str(pauses), count_tone(pauses, 1)),
                ],
            },
            'percent': {
                'tokens': [] if virtual else alg_tokens(
                    pauses_markup(step, solve),
                ),
                'metrics': [
                    metric('Reco', percent(step['recognition_percent'])),
                    metric('Exec', percent(step['execution_percent'])),
                    metric(
                        'Time', percent(step['total_percent']),
                        metric_tone(
                            step['total_percent'], method_applied,
                            'percent', name,
                        ),
                        strong=True,
                    ),
                    metric(
                        'Step reco',
                        percent(step['step_recognition_percent']),
                        metric_tone(
                            step['step_recognition_percent'],
                            method_applied, 'recognition', name,
                        ),
                    ),
                    metric(
                        'Step exec',
                        percent(step['step_execution_percent']),
                        metric_tone(
                            step['step_execution_percent'],
                            method_applied, 'execution', name,
                        ),
                    ),
                ],
            },
            'overheads': {
                'tokens': [] if virtual else alg_tokens(
                    overheads_markup(step, solve),
                ),
                'metrics': [
                    metric('Overhead', str(missed), count_tone(missed, 2)),
                    metric('Pre-AUF', pre_auf, pre_auf_tone),
                    metric('Post-AUF', post_auf, post_auf_tone),
                ],
            },
            'optimized': {
                'tokens': [] if virtual else alg_tokens(optimized),
                'metrics': [
                    metric(
                        'HTM', str(optimized_algorithm.metrics.htm),
                        metric_tone(
                            optimized_algorithm.metrics.htm,
                            method_applied, 'moves', name,
                        ),
                    ),
                    metric(
                        'Gains', f'-{ gains }' if gains else '0',
                        'good' if gains else '',
                    ),
                ],
            },
            'raw': {
                'tokens': [] if virtual else plain_tokens(
                    ' '.join(
                        str(move.untimed)
                        for move in step['moves_reoriented']
                    ),
                ),
                'metrics': [
                    metric('QTM', str(
                        step['moves_reoriented'].metrics.qtm,
                    )),
                ],
            },
            'issues': {
                'tokens': [] if virtual else alg_tokens(
                    solve.reconstruction_step_line(step, multiple=True),
                ),
                'metrics': [
                    metric('Pauses', str(pauses), count_tone(pauses, 1)),
                    metric('Overhead', str(missed), count_tone(missed, 2)),
                    metric('Pre-AUF', pre_auf, pre_auf_tone),
                    metric('Post-AUF', post_auf, post_auf_tone),
                    metric(
                        '+oHTM', '---' if ohtm < 1 else str(ohtm),
                        '' if ohtm < 1 else count_tone(ohtm, 2),
                    ),
                ],
            },
        }


class SolveUpdateFlagView(SolveLocation):
    """View for updating solve flag."""

    def __init__(self, cube: int, session: str, solve_id: int,
                 flag: SolveFlagInput) -> None:
        """
        Update solve flag and redirect to solve detail.

        Args:
            cube: Cube size (2-7).
            session: Session identifier or 'all' for all sessions.
            solve_id: 1-based solve identifier within the session.
            flag: New flag value to set (DNF, +2, or OK).

        """
        self.cube = cube
        self.session = session
        self.solve_id = solve_id
        self.flag = flag

        self.solves = load_all_solves(
            cube,
            [] if session == 'all' else [session],
            [], [],
            directory=self.directory,
        )

        self.solve_index = solve_id - 1
        try:
            self.solve = self.solves[self.solve_index]
        except IndexError:
            abort(404, 'Invalid solve ID')

        if self.solve.advanced:
            abort(403, 'Flag cannot be edited on an advanced solve')

        normalized_flag: SolveFlag = '' if flag == 'OK' else flag
        self.solves[self.solve_index].flag = normalized_flag
        save_solves(cube, session, self.solves, self.directory)

        redirect(f'{ self.session_url(cube, session) }{ solve_id }/')


class SolveUpdateCommentView(SolveLocation):
    """View for updating solve comment."""

    def __init__(self, cube: int, session: str, solve_id: int,
                 comment: str) -> None:
        """
        Update solve comment and redirect to solve detail.

        Args:
            cube: Cube size (2-7).
            session: Session identifier or 'all' for all sessions.
            solve_id: 1-based solve identifier within the session.
            comment: New comment value to set.

        """
        self.cube = cube
        self.session = session
        self.solve_id = solve_id
        self.comment = comment

        self.solves = load_all_solves(
            cube,
            [] if session == 'all' else [session],
            [], [],
            directory=self.directory,
        )

        self.solve_index = solve_id - 1
        try:
            self.solve = self.solves[self.solve_index]
        except IndexError:
            abort(404, 'Invalid solve ID')

        self.solves[self.solve_index].comment = comment.strip()
        save_solves(cube, session, self.solves, self.directory)

        redirect(f'{ self.session_url(cube, session) }{ solve_id }/')


class SolveDeleteView(SolveLocation):
    """View for deleting a solve from the database."""

    def __init__(self, cube: int, session: str, solve_id: int) -> None:
        """
        Delete solve and redirect to session overview.

        Args:
            cube: Cube size (2-7).
            session: Session identifier or 'all' for all sessions.
            solve_id: 1-based solve identifier within the session.

        """
        self.cube = cube
        self.session = session
        self.solve_id = solve_id

        self.solves = load_all_solves(
            cube,
            [] if session == 'all' else [session],
            [], [],
            directory=self.directory,
        )

        self.solve_index = solve_id - 1
        try:
            self.solve = self.solves[self.solve_index]
        except IndexError:
            abort(404, 'Invalid solve ID')

        self.solves.pop(self.solve_index)
        save_solves(cube, session, self.solves, self.directory)

        redirect(self.session_url(cube, session))
