"""Solve detail, update, and delete views."""
from typing import TYPE_CHECKING
from typing import cast

from bottle import abort
from bottle import redirect
from cubing_algs.annotations import CubeOrientation
from cubing_algs.constants import ORIENTATION_FACE_MOVES

from term_timer.cheers import generate_solve_cheers
from term_timer.constants import SECOND
from term_timer.constants import SolveFlag
from term_timer.constants import SolveFlagInput
from term_timer.in_out import load_all_solves
from term_timer.in_out import save_solves
from term_timer.methods import METHOD_ANALYSERS
from term_timer.server.annotations import FluencyData

if TYPE_CHECKING:
    from term_timer.methods.base import Analyser
from term_timer.server.annotations import RecognitionData
from term_timer.server.annotations import ScatterPoint
from term_timer.server.annotations import SolveDetailContext
from term_timer.server.annotations import StepMarker
from term_timer.server.annotations import TPSData
from term_timer.server.views.base import View
from term_timer.solve import Solve


class SolveDetailView(View):
    """View for displaying detailed analysis of a single solve."""

    template_name = 'solve.html'

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

        ranks = sorted([s.final_time for s in self.solves])
        rank = ranks.index(self.solve.final_time) + 1

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
            'solve': self.solve,
            'solve_id': self.solve_id,
            'solves': self.solves,
            'scatter': scatter,
            'steps': steps,
            'cheers': generate_solve_cheers(self.solve),
            'tps': tps,
            'fluencies': fluencies,
            'recognitions': recognitions,
            'reconstruction_text': reconstruction_text,
            'reconstruction_timing': self.solve.reconstruction_steps_timing,
            'reconstruction_index': step_index,
            'rank': rank,
            'available_orientations': ORIENTATION_FACE_MOVES,
            'available_methods': list(METHOD_ANALYSERS.keys()),
        }


class SolveUpdateFlagView:
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
        )

        self.solve_index = solve_id - 1
        try:
            self.solve = self.solves[self.solve_index]
        except IndexError:
            abort(404, 'Invalid solve ID')

        normalized_flag: SolveFlag = '' if flag == 'OK' else flag
        self.solves[self.solve_index].flag = normalized_flag
        save_solves(cube, session, self.solves)

        redirect(f'/{ cube }/{ session }/{ solve_id }/')


class SolveUpdateCommentView:
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
        )

        self.solve_index = solve_id - 1
        try:
            self.solve = self.solves[self.solve_index]
        except IndexError:
            abort(404, 'Invalid solve ID')

        self.solves[self.solve_index].comment = comment.strip()
        save_solves(cube, session, self.solves)

        redirect(f'/{ cube }/{ session }/{ solve_id }/')


class SolveDeleteView:
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
        )

        self.solve_index = solve_id - 1
        try:
            self.solve = self.solves[self.solve_index]
        except IndexError:
            abort(404, 'Invalid solve ID')

        self.solves.pop(self.solve_index)
        save_solves(cube, session, self.solves)

        redirect(f'/{ cube }/{ session }/')
