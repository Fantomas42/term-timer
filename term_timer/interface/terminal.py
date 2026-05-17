"""Terminal control utilities for cursor and line management."""
# ruff: noqa: T201
from term_timer.interface.sounds import SoundPlayer

SOUND_PLAYER = SoundPlayer()


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
    def beep() -> None:
        """Emit a generic beep sound."""
        SOUND_PLAYER.generic()

    @staticmethod
    def beep_metronome() -> None:
        """Emit a short neutral tick for metronome beats."""
        SOUND_PLAYER.metronome()

    @staticmethod
    def beep_step() -> None:
        """Emit a higher-pitched beep when a solve step is completed."""
        SOUND_PLAYER.step()

    @staticmethod
    def beep_countdown() -> None:
        """Emit a low urgent beep for inspection countdown warnings."""
        SOUND_PLAYER.countdown()

    @staticmethod
    def beep_scramble() -> None:
        """Emit a confirmation tone when scramble is finalized."""
        SOUND_PLAYER.scramble()

    @staticmethod
    def set_title(title: str) -> None:
        """Set the terminal window title."""
        print(f'\033]0;{title}\007', end='', flush=True)
