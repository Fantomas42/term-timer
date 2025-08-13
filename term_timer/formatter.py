import difflib

from cubing_algs.constants import INNER_MOVES
from cubing_algs.constants import OUTER_WIDE_MOVES
from cubing_algs.constants import PAUSE_CHAR
from cubing_algs.constants import ROTATIONS

from term_timer.constants import DNF
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import SECOND
from term_timer.methods.base import AUF
from term_timer.triggers import TRIGGERS_REGEX
from term_timer.triggers import apply_trigger_outside_blocks


def format_time(elapsed_ns: int, *, allow_dnf: bool = True) -> str:
    if not elapsed_ns and allow_dnf:
        return f'{ DNF:>9}'

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
        return f'+{secs:02}s'

    _, mins = divmod(mins, 60)

    padding = 1
    if max_edge >= 600:
        padding = 2

    return f'+{mins:0{padding}}:{secs:02}'


def format_delta(delta: int) -> str:
    if delta == 0:
        return ''
    style = (delta > 0 and 'red') or 'green'
    sign = ''
    if delta > 0:
        sign = '+'

    return f'[{ style }]{ sign }{ format_duration(delta) }[/{ style }]'


def format_score(score: int) -> str:
    style = 'green'
    if score < 14:
        style = 'orange'
    if score < 8:
        style = 'red'

    return f'[{ style }]{ score:.2f}[/{ style }]'


def compute_padding(max_value: float) -> int:
    padding = 1
    if max_value >= 1000:
        padding = 4
    elif max_value >= 100:
        padding = 3
    elif max_value >= 10:
        padding = 2

    return padding


def format_grade(score: float) -> str:
    if score >= 20:
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


def clean_url(string: str) -> str:
    return string.replace(
        ' ', '_',
    ).replace(
        "'", '-',
    ).replace(
        '/', '%2F',
    ).replace(
        '\n', '%0A',
    ).replace(
        '+', '%26%232b%3B',
    ).replace(
        '-AUF', '%26%2345%3BAUF',
    )


def format_alg_cubing_url(title: str, setup: str, alg: str) -> str:
    return (
        'https://alg.cubing.net/'
        f'?title={ title }'
        f'&alg={ clean_url(alg) }'
        f'&setup={ clean_url(setup) }'
    )


def format_cube_db_url(title: str, setup: str, alg: str) -> str:
    return (
        'https://cubedb.net/'
        f'?title={ title }'
        f'&alg={ clean_url(alg) }'
        f'&scramble={ clean_url(setup) }'
    )


def format_alg_diff(algo_a, algo_b) -> str:
    moves = []
    matcher = difflib.SequenceMatcher(None, algo_a, algo_b)

    for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
        if opcode == 'equal':
            moves.extend(algo_a[i1:i2])
        elif opcode == 'delete':
            moves.extend(
                [
                    f'[deletion]{ item }[/deletion]'
                    for item in algo_a[i1:i2]
                ],
            )
        elif opcode == 'insert':
            moves.extend(
                [
                    f'[addition]{ item }[/addition]'
                    for item in algo_b[j1:j2]
                ],
            )

        elif opcode == 'replace':
            moves.extend(
                [
                    f'[deletion]{ item }[/deletion]'
                    for item in algo_a[i1:i2]
                ],
            )
            moves.extend(
                [
                    f'[addition]{ item }[/addition]'
                    for item in algo_b[j1:j2]
                ],
            )

    return ' '.join([str(m) for m in moves])


def format_alg_triggers(algorithm: str, trigger_names: list[str]) -> str:
    for trigger_name in trigger_names:
        regex = TRIGGERS_REGEX[trigger_name]

        def replacer(matchobj):
            return (
                f'[{ trigger_name }]'   # noqa: B023
                f'{ matchobj.group(0) }'
                f'[/{ trigger_name }]'  # noqa: B023
            )

        algorithm = apply_trigger_outside_blocks(
            algorithm, regex, replacer,
        )

    return algorithm


def format_alg_aufs(algorithm: str, pre_auf: int, post_auf: int) -> str:
    if pre_auf and algorithm:
        algorithm_parts = algorithm.split(' ')
        for i, move in enumerate(algorithm_parts):
            if move[0] == AUF:
                algorithm_parts[i] = f'[pre-auf]{ move }[/pre-auf]'
            elif move != PAUSE_CHAR:
                break
        algorithm = ' '.join(algorithm_parts)

    if post_auf and algorithm:
        algorithm_parts = list(reversed(algorithm.split(' ')))
        for i, move in enumerate(algorithm_parts):
            if move[0] == AUF:
                algorithm_parts[i] = f'[post-auf]{ move }[/post-auf]'
            elif move != PAUSE_CHAR:
                break
        algorithm = ' '.join(reversed(algorithm_parts))

    return algorithm


def format_alg_pauses(algorithm: str, solve, step, *, multiple=False) -> str:
    post = int(step['post_pause'] / solve.pause_threshold)
    if post:
        algorithm += f' [reco-pause]{ PAUSE_CHAR }[/reco-pause]' * (
            post if multiple else 1
        )

    return algorithm.replace(
        ' .',
        ' [pause].[/pause]',
    )


def format_alg_moves(algorithm: str) -> str:
    if not algorithm:
        return ''

    algorithm_parts = algorithm.split(' ')

    for i, move in enumerate(algorithm_parts):
        if move[0] in OUTER_WIDE_MOVES:
            algorithm_parts[i] = f'[wide]{ move }[/wide]'
        elif move[0] in INNER_MOVES:
            algorithm_parts[i] = f'[slice]{ move }[/slice]'
        elif move[0] in ROTATIONS:
            algorithm_parts[i] = f'[rotation]{ move }[/rotation]'

    return ' '.join(algorithm_parts)
