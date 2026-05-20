"""Terminal control utilities for cursor and line management."""
# ruff: noqa: T201


class Terminal:
    """Mixin providing terminal control utilities."""

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
