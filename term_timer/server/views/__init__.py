"""Web server views package."""
from term_timer.server.views.academy import AcademyCaseAlgorithmsDebugView
from term_timer.server.views.academy import AcademyCaseView
from term_timer.server.views.academy import AcademyStepView
from term_timer.server.views.academy import AcademyView
from term_timer.server.views.algorithm import AlgorithmDetailView
from term_timer.server.views.cube import CubeImageView
from term_timer.server.views.cube import CubeRenderView
from term_timer.server.views.daily import DailyDayView
from term_timer.server.views.daily import DailyListView
from term_timer.server.views.daily import DailySolveDeleteView
from term_timer.server.views.daily import DailySolveDetailView
from term_timer.server.views.daily import DailySolveUpdateCommentView
from term_timer.server.views.daily import DailySolveUpdateFlagView
from term_timer.server.views.errors import Error404View
from term_timer.server.views.errors import Error500View
from term_timer.server.views.scramble import ScrambleDetailView
from term_timer.server.views.scramble import ScrambleHomeView
from term_timer.server.views.sessions import SessionDetailView
from term_timer.server.views.sessions import SessionListView
from term_timer.server.views.solves import SolveDeleteView
from term_timer.server.views.solves import SolveDetailView
from term_timer.server.views.solves import SolveUpdateCommentView
from term_timer.server.views.solves import SolveUpdateFlagView
from term_timer.server.views.styleguide import DesignStyleguideView
from term_timer.server.views.styleguide import StyleguideView
from term_timer.server.views.training import TrainingForecastView
from term_timer.server.views.training import TrainingReviewView

__all__ = [
    'AcademyCaseAlgorithmsDebugView',
    'AcademyCaseView',
    'AcademyStepView',
    'AcademyView',
    'AlgorithmDetailView',
    'CubeImageView',
    'CubeRenderView',
    'DailyDayView',
    'DailyListView',
    'DailySolveDeleteView',
    'DailySolveDetailView',
    'DailySolveUpdateCommentView',
    'DailySolveUpdateFlagView',
    'DesignStyleguideView',
    'Error404View',
    'Error500View',
    'ScrambleDetailView',
    'ScrambleHomeView',
    'SessionDetailView',
    'SessionListView',
    'SolveDeleteView',
    'SolveDetailView',
    'SolveUpdateCommentView',
    'SolveUpdateFlagView',
    'StyleguideView',
    'TrainingForecastView',
    'TrainingReviewView',
]
