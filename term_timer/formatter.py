from term_timer.constants import DNF
from term_timer.constants import SECOND


def format_time(elapsed_ns: int) -> str:
    if not elapsed_ns:
        return DNF

    elapsed_sec = elapsed_ns / SECOND
    mins, secs = divmod(int(elapsed_sec), 60)
    hours, mins = divmod(mins, 60)
    milliseconds = (elapsed_ns // 1_000_000) % 1000
    if hours:
        return f'{hours:02}:{mins:02}:{secs:02}.{milliseconds:03}'
    return f'{mins:02}:{secs:02}.{milliseconds:03}'


def format_duration(elapsed_ns: int) -> str:
    return f'{ elapsed_ns / SECOND:.2f}'


def format_edge(edge: int) -> str:
    mins, secs = divmod(int(edge), 60)
    _, mins = divmod(mins, 60)

    return f'{mins:02}:{secs:02}'


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
