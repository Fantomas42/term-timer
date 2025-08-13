import re

from cubing_algs.parsing import parse_moves
from cubing_algs.transform.offset import offset_y2_moves
from cubing_algs.transform.offset import offset_y_moves
from cubing_algs.transform.offset import offset_yprime_moves
from cubing_algs.transform.symmetry import symmetry_m_moves

BLOCK_PATTERN = re.compile(r'\[[^\]]+\].*?\[/[^\]]+\]')

BASE_TRIGGERS = {
    "RU2R'U'RU'R'": 'chair',

    "RUR'U'": 'sexy-move',

    "R'FRF'": 'sledgehammer',

    "RUR'U": 'su',
    "RU'R'U'": 'sa',

    "RU2R'": 'ne',
    "R'U2R": 'ne',

    "RUR'": 'pair-ie',
    "RU'R'": 'pair-ie',
}


TRIGGERS = {}
for algo_string, name in BASE_TRIGGERS.items():
    source_algo = parse_moves(algo_string)
    anti_algo = source_algo.transform(
        symmetry_m_moves,
    )

    TRIGGERS.setdefault(name, [])
    for algo in [source_algo, anti_algo]:
        TRIGGERS[name].append(str(algo))
        TRIGGERS[name].append(str(algo.transform(offset_y_moves)))
        TRIGGERS[name].append(str(algo.transform(offset_yprime_moves)))
        TRIGGERS[name].append(str(algo.transform(offset_y2_moves)))


TRIGGERS_REGEX = {
    name: re.compile(rf'({ "|".join(algos) })(?![2\'])')
    for name, algos in TRIGGERS.items()
}

DEFAULT_TRIGGERS = [
    'chair',
    'sexy-move',
    'sledgehammer',
    'su',
    'sa',
    'ne',
    'pair-ie',
]


def apply_trigger_outside_blocks(algorithm: str, regex, replacement_func):
    blocks = []

    for match in re.finditer(BLOCK_PATTERN, algorithm):
        blocks.append((match.start(), match.end(), match.group(0)))

    result = ''
    last_end = 0

    for start, end, block_content in blocks:
        segment_before = algorithm[last_end:start]
        processed_segment = regex.sub(replacement_func, segment_before)
        result += processed_segment

        result += block_content
        last_end = end

    final_segment = algorithm[last_end:]
    processed_final = regex.sub(replacement_func, final_segment)
    result += processed_final

    return result
