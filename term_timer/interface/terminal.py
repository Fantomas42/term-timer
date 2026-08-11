"""Terminal control utilities for cursor and line management."""
# ruff: noqa: T201
from collections.abc import Iterator
from contextlib import contextmanager


class Terminal:
    """Mixin providing terminal control utilities."""

    @staticmethod
    @contextmanager
    def hidden_cursor() -> Iterator[None]:
        """
        Hide the terminal cursor for the duration of a redraw phase.

        In-place displays move the cursor around at every frame, which reads
        as flickering. Hiding it while such a display is running removes the
        motion entirely. The cursor is restored on any exit, including
        exceptions and task cancellation.

        Yields:
            None, for the duration of the hidden cursor.

        """
        print('\033[?25l', end='', flush=True)
        try:
            yield
        finally:
            print('\033[?25h', end='', flush=True)

    @staticmethod
    def clear_line(*, full: bool) -> None:
        """Clear the current terminal line."""
        if full:
            print(f'\r{ " " * 100}\r', flush=True, end='')
        else:
            print('\r', end='')

    @staticmethod
    def back(size: int) -> None:
        """Move cursor back by specified number of characters."""
        print('\b' * size, end='')

    @staticmethod
    def set_title(title: str) -> None:
        """Set the terminal window title."""
        print(f'\033]0;{title}\007', end='', flush=True)
