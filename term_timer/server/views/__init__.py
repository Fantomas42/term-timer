"""Web server views package."""
from term_timer.server.views.academy import AcademyCaseView
from term_timer.server.views.academy import AcademyStepView
from term_timer.server.views.academy import AcademyView
from term_timer.server.views.algorithm import AlgorithmDetailView
from term_timer.server.views.cube import CubeImageView
from term_timer.server.views.cube import CubeRenderView
from term_timer.server.views.errors import Error404View
from term_timer.server.views.errors import Error500View
from term_timer.server.views.sessions import SessionDetailView
from term_timer.server.views.sessions import SessionListView
from term_timer.server.views.solves import SolveDeleteView
from term_timer.server.views.solves import SolveDetailView
from term_timer.server.views.solves import SolveUpdateCommentView
from term_timer.server.views.solves import SolveUpdateFlagView

__all__ = [
    'AcademyCaseView',
    'AcademyStepView',
    'AcademyView',
    'AlgorithmDetailView',
    'CubeImageView',
    'CubeRenderView',
    'Error404View',
    'Error500View',
    'SessionDetailView',
    'SessionListView',
    'SolveDeleteView',
    'SolveDetailView',
    'SolveUpdateCommentView',
    'SolveUpdateFlagView',
]
