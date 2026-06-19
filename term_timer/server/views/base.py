"""Base view class for template rendering."""
import gc
from datetime import datetime
from datetime import timezone

from bottle import jinja2_template

from term_timer.formatter import format_duration
from term_timer.formatter import format_grade
from term_timer.formatter import format_session_name
from term_timer.formatter import format_term_timer_case_url
from term_timer.formatter import format_time
from term_timer.server.annotations import AcademyCaseAlgorithmsDebugContext
from term_timer.server.annotations import AcademyCaseContext
from term_timer.server.annotations import AcademyOverviewContext
from term_timer.server.annotations import AcademyStepContext
from term_timer.server.annotations import AlgorithmDetailContext
from term_timer.server.annotations import CubeRenderContext
from term_timer.server.annotations import Error404Context
from term_timer.server.annotations import Error500Context
from term_timer.server.annotations import SessionDetailContext
from term_timer.server.annotations import SessionListContext
from term_timer.server.annotations import SolveDetailContext
from term_timer.server.annotations import StyleguideContext
from term_timer.server.filters import case_number
from term_timer.server.filters import first_case
from term_timer.server.filters import format_algorithm
from term_timer.server.filters import format_delta
from term_timer.server.filters import format_line
from term_timer.server.filters import format_score
from term_timer.server.filters import get_ohtm_delta
from term_timer.server.filters import get_step_case
from term_timer.server.filters import normalize_percent
from term_timer.server.filters import normalize_value
from term_timer.server.filters import optimized_step
from term_timer.server.filters import reconstruction_overheads
from term_timer.server.filters import reconstruction_pauses
from term_timer.server.filters import reconstruction_step
from term_timer.server.filters import sort_algorithms
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
        | StyleguideContext
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
                    'filters': {
                        'format_delta': format_delta,
                        'format_duration': format_duration,
                        'format_grade': format_grade,
                        'format_time': format_time,
                        'format_score': format_score,
                        'format_line': format_line,
                        'format_algorithm': format_algorithm,
                        'format_session_name': format_session_name,
                        'case_link': format_term_timer_case_url,
                        'get_step_case': get_step_case,
                        'get_ohtm_delta': get_ohtm_delta,
                        'normalize_value': normalize_value,
                        'normalize_percent': normalize_percent,
                        'reconstruction_step': reconstruction_step,
                        'reconstruction_overheads': reconstruction_overheads,
                        'reconstruction_pauses': reconstruction_pauses,
                        'optimized_step': optimized_step,
                        'prettify': prettify_moves,
                        'sort_algorithms': sort_algorithms,
                        'first_case': first_case,
                        'case_number': case_number,
                    },
                },
                **context,
            ),
        )
