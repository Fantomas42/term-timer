from term_timer.constants import DNF
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import SECOND


def format_time(elapsed_ns: int) -> str:
    if not elapsed_ns:
        return DNF

    elapsed_sec = elapsed_ns / SECOND
    mins, secs = divmod(int(elapsed_sec), 60)
    hours, mins = divmod(mins, 60)
    milliseconds = (elapsed_ns // MS_TO_NS_FACTOR) % 1_000
    if hours:
        return f'{hours:02}:{mins:02}:{secs:02}.{milliseconds:03}'
    return f'{mins:02}:{secs:02}.{milliseconds:03}'


def format_duration(elapsed_ns: int) -> str:
    return f'{ elapsed_ns / SECOND:.2f}'


def format_edge(edge: int, max_edge: int) -> str:
    mins, secs = divmod(int(edge), 60)

    if max_edge < 60:
        return f'{secs:02}s'

    _, mins = divmod(mins, 60)

    padding = 1
    if max_edge >= 600:
        padding = 2

    return f'{mins:0{padding}}:{secs:02}'


def format_delta(delta: int) -> str:
    if delta == 0:
        return ''
    style = (delta > 0 and 'red') or 'green'
    sign = ''
    if delta > 0:
        sign = '+'

    return f'[{ style }]{ sign }{ format_duration(delta) }[/{ style }]'


def computing_padding(max_value: float) -> int:
    padding = 1
    if max_value > 1000:
        padding = 4
    elif max_value > 100:
        padding = 3
    elif max_value > 10:
        padding = 2

    return padding


def format_grade(score):
    if score == 20:
        return 'S'
    if score >= 18:
        return 'A+'
    if score >= 16:
        return 'A'
    if score >= 14:
        return 'B+'
    if score >= 12:
        return 'B'
    if score >= 10:
        return 'C+'
    if score >= 8:
        return 'C'
    if score >= 6:
        return 'D'
    if score >= 4:
        return 'E'
    return 'F'
