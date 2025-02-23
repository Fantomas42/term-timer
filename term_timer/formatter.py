from term_timer.colors import C_GREEN
from term_timer.colors import C_RED
from term_timer.colors import C_RESET
from term_timer.constants import SECOND


def format_time(elapsed_ns):
    if not elapsed_ns:
        return 'DNF'

    elapsed_sec = elapsed_ns / SECOND
    mins, secs = divmod(int(elapsed_sec), 60)
    _hours, mins = divmod(mins, 60)
    milliseconds = (elapsed_ns // 1_000_000) % 1000
    return f'{mins:02}:{secs:02}.{milliseconds:03}'


def format_duration(elapsed_ns):
    return f'{ elapsed_ns / SECOND:.2f}'


def format_edge(elapsed_ns):
    return f'{ elapsed_ns / SECOND:.0f}'


def format_delta(delta):
    return '%s%ss%s' % (
        (delta > 0 and f'{ C_RED }+') or C_GREEN,
        format_duration(delta),
        C_RESET,
    )
