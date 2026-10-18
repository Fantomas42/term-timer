"""Base view class for template rendering."""
import gc
from datetime import datetime
from datetime import timezone

from bottle import jinja2_template
from bottle import request

from term_timer.formatter import format_duration
from term_timer.formatter import format_grade
from term_timer.formatter import format_session_name
from term_timer.formatter import format_term_timer_case_url
from term_timer.server.annotations import AcademyCaseAlgorithmsDebugContext
from term_timer.server.annotations import AcademyCaseContext
from term_timer.server.annotations import AcademyOverviewContext
from term_timer.server.annotations import AcademyStepContext
from term_timer.server.annotations import AlgorithmDetailContext
from term_timer.server.annotations import CubeRenderContext
from term_timer.server.annotations import DailyDayContext
from term_timer.server.annotations import DailyListContext
from term_timer.server.annotations import DesignStyleguideContext
from term_timer.server.annotations import Error404Context
from term_timer.server.annotations import Error500Context
from term_timer.server.annotations import ScrambleDetailContext
from term_timer.server.annotations import ScrambleHomeContext
from term_timer.server.annotations import SessionDetailContext
from term_timer.server.annotations import SessionListContext
from term_timer.server.annotations import SolveDetailContext
from term_timer.server.annotations import TrainingForecastContext
from term_timer.server.annotations import TrainingReviewContext
from term_timer.server.filters import STATIC_ASSETS
from term_timer.server.filters import alg_text
from term_timer.server.filters import alg_tokens
from term_timer.server.filters import algorithm_tokens
from term_timer.server.filters import count_tone
from term_timer.server.filters import days_ago
from term_timer.server.filters import fluency_tone
from term_timer.server.filters import format_delta
from term_timer.server.filters import grade_tone
from term_timer.server.filters import hours
from term_timer.server.filters import metric_tone
from term_timer.server.filters import paragraphs
from term_timer.server.filters import short_date
from term_timer.server.filters import short_time
from term_timer.server.filters import sort_algorithms
from term_timer.server.filters import sparkline
from term_timer.server.filters import split_time
from term_timer.server.filters import weekday
from term_timer.server.views.navigation import Navigation
from term_timer.transform import prettify_moves


class View:
    """Base view class for rendering Jinja2 templates with custom filters."""

    template_name = ''

    def get_context(
        self,
    ) -> (
        Error404Context
        | Error500Context
        | SessionListContext
        | SessionDetailContext
        | SolveDetailContext
        | AlgorithmDetailContext
        | AcademyOverviewContext
        | AcademyStepContext
        | AcademyCaseContext
        | AcademyCaseAlgorithmsDebugContext
        | CubeRenderContext
        | DesignStyleguideContext
        | ScrambleHomeContext
        | ScrambleDetailContext
        | DailyListContext
        | DailyDayContext
        | TrainingForecastContext
        | TrainingReviewContext
    ):
        """
        Build template context dictionary.

        Returns:
            Dictionary of context variables for template rendering.

        Raises:
            NotImplementedError: Must be implemented by subclasses.

        """
        raise NotImplementedError

    def as_view(self, debug: bool) -> str:  # noqa: FBT001
        """
        Render view template with context data.

        Args:
            debug: Enable debug mode for template rendering.

        Returns:
            Rendered HTML string.

        """
        context = self.get_context()

        content = self.template(
            self.template_name,
            DEBUG=debug,
            navigation=Navigation.items(request.path, debug=debug),
            **context,
        )
        gc.collect()

        return content

    @staticmethod
    def template(
        template_name: str,
        **context: bool | str | float | datetime | object,
    ) -> str:
        """
        Render Jinja2 template with custom filters and context.

        Every template escapes its values by default, set on the
        environment: a {% autoescape %} block would cover neither the
        blocks a child page redefines nor the imported macros. A trusted
        HTML fragment is marked with the safe filter.

        Args:
            template_name: Name of template file to render.
            **context: Template context variables.

        Returns:
            Rendered template as HTML string.

        """
        context['now'] = datetime.now(tz=timezone.utc)  # noqa: UP017

        return str(
            jinja2_template(
                template_name,
                template_settings={
                    'autoescape': True,
                    'globals': {'import_map': STATIC_ASSETS.import_map},
                    'filters': {
                        'asset': STATIC_ASSETS.url,
                        'format_delta': format_delta,
                        'format_duration': format_duration,
                        'format_grade': format_grade,
                        'format_session_name': format_session_name,
                        'case_link': format_term_timer_case_url,
                        'prettify': prettify_moves,
                        'sort_algorithms': sort_algorithms,
                        'alg_tokens': alg_tokens,
                        'algorithm_tokens': algorithm_tokens,
                        'alg_text': alg_text,
                        'grade_tone': grade_tone,
                        'split_time': split_time,
                        'metric_tone': metric_tone,
                        'fluency_tone': fluency_tone,
                        'count_tone': count_tone,
                        'short_time': short_time,
                        'short_date': short_date,
                        'days_ago': days_ago,
                        'hours': hours,
                        'weekday': weekday,
                        'paragraphs': paragraphs,
                        'sparkline': sparkline,
                    },
                },
                **context,
            ),
        )
