"""Error views for HTTP error pages."""
import html
import logging
import traceback
from pathlib import Path
from random import Random

from bottle import HTTPError

from term_timer.scrambler import scrambler
from term_timer.server.annotations import Error404Context
from term_timer.server.annotations import Error500Context
from term_timer.server.annotations import TracebackFrame
from term_timer.server.views.base import View

logger = logging.getLogger(__name__)

# The package whose frames a traceback puts forward.
OWN_PACKAGE = 'term_timer'

# Directories after which a library frame is named.
LIBRARY_ROOTS = ('site-packages', 'dist-packages')


class ErrorView(View):
    """
    Base of the error pages, falling back to a bare page.

    An error page must not fail in turn: when the page itself cannot be
    rendered (a broken skeleton, navigation or filter), a minimal page
    without template nor style carries the status and the message.
    """

    def __init__(self, error: HTTPError, path: str = '') -> None:
        """
        Initialize the error view.

        Args:
            error: HTTP error object containing error details.
            path: Path of the request that failed.

        """
        self.error = error
        self.path = path

    def as_view(self, debug: bool) -> str:  # noqa: FBT001
        """
        Render the error page, or the bare one if it fails.

        Returns:
            Rendered HTML string.

        """
        try:
            return super().as_view(debug)
        except Exception:
            logger.exception('Error page %s failed', self.template_name)
            return self.fallback()

    def fallback(self) -> str:
        """
        Build the bare error page, escaped by hand.

        Returns:
            A minimal HTML page with the status and the message.

        """
        status = html.escape(str(self.error.status_line))
        message = html.escape(str(self.error.body or ''))

        return (
            '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">'
            f'<title>{ status } · Term Timer</title></head><body>'
            f'<h1>{ status }</h1><p>{ message }</p>'
            '<p><a href="/">Back to the sessions</a></p></body></html>'
        )


class Error404View(ErrorView):
    """View for rendering 404 Not Found error pages."""

    template_name = '404.html'

    def get_scramble(self) -> str:
        """
        Scramble a cube with the lost path as seed: the same wrong
        address always gives the same cube.

        Returns:
            The scramble, as a string.

        """
        rng = Random(self.path)  # noqa: S311
        scramble, _cube = scrambler(cube_size=3, iterations=0, rng=rng)

        return str(scramble)

    def get_context(self) -> Error404Context:
        """
        Build context for 404 error template.

        Returns:
            Dictionary containing error object and message.

        """
        return {
            'message': self.error.body,
            'path': self.path,
            'scramble': self.get_scramble(),
        }


class Error500View(ErrorView):
    """View for rendering 500 Internal Server Error pages."""

    template_name = '500.html'

    @staticmethod
    def frame_of(summary: traceback.FrameSummary) -> TracebackFrame:
        """
        Present one frame of a traceback, its file named from the
        package it belongs to.

        Returns:
            The frame, marked own when it belongs to term-timer.

        """
        parts = Path(summary.filename).parts
        library = next(
            (
                parts.index(root) + 1
                for root in LIBRARY_ROOTS if root in parts
            ),
            None,
        )
        own = library is None and OWN_PACKAGE in parts
        if own:
            start = len(parts) - 1 - parts[::-1].index(OWN_PACKAGE)
        else:
            start = library if library is not None else len(parts) - 1

        return {
            'file': '/'.join(parts[start:]),
            'line': summary.lineno or 0,
            'function': summary.name,
            'code': summary.line or '',
            'own': own,
        }

    def frames(self) -> list[TracebackFrame]:
        """
        Frames of the exception behind the error, innermost last.

        Returns:
            The frames, empty without an exception.

        """
        exception = self.error.exception
        if not isinstance(exception, BaseException):
            return []

        return [
            self.frame_of(summary)
            for summary in traceback.extract_tb(exception.__traceback__)
        ]

    def get_context(self) -> Error500Context:
        """
        Build context for 500 error template.

        The error is logged in any case: without debug mode the page
        hides the traceback, the log keeps it.

        Returns:
            Dictionary containing error, message, exception, and traceback.

        """
        exception = self.error.exception
        if isinstance(exception, BaseException):
            logger.error(
                'Server error on %s', self.path or '?', exc_info=exception,
            )

        return {
            'message': self.error.body,
            'exception': exception,
            'exception_name': (
                type(exception).__name__
                if isinstance(exception, BaseException) else ''
            ),
            'traceback': self.error.traceback,
            'frames': self.frames(),
            'path': self.path,
        }
