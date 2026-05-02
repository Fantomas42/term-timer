"""Error views for HTTP error pages."""
from bottle import HTTPError

from term_timer.server.annotations import Error404Context
from term_timer.server.annotations import Error500Context
from term_timer.server.views.base import View


class Error404View(View):
    """View for rendering 404 Not Found error pages."""

    template_name = '404.html'

    def __init__(self, error: HTTPError) -> None:
        """
        Initialize 404 error view.

        Args:
            error: HTTP error object containing error details.

        """
        self.error = error

    def get_context(self) -> Error404Context:
        """
        Build context for 404 error template.

        Returns:
            Dictionary containing error object and message.

        """
        return {
            'error': self.error,
            'message': self.error.body,
        }


class Error500View(View):
    """View for rendering 500 Internal Server Error pages."""

    template_name = '500.html'

    def __init__(self, error: HTTPError) -> None:
        """
        Initialize 500 error view.

        Args:
            error: HTTP error object containing error details.

        """
        self.error = error

    def get_context(self) -> Error500Context:
        """
        Build context for 500 error template.

        Returns:
            Dictionary containing error, message, exception, and traceback.

        """
        return {
            'error': self.error,
            'message': self.error.body,
            'exception': self.error.exception,
            'traceback': self.error.traceback,
        }
