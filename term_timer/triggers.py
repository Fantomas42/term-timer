import re

from cubing_algs.parsing import parse_moves
from cubing_algs.transform.offset import offset_y2_moves
from cubing_algs.transform.offset import offset_y_moves
from cubing_algs.transform.offset import offset_yprime_moves

BASE_TRIGGERS = {
    "RUR'U'": 'sexy-move',
    "R'FRF'": 'sledgehammer',
    "RUR'": 'pair-ie',
    "RU'R'": 'pair-ie',
    "R'UR": 'pair-ie',
    "R'U'R": 'pair-ie',
    # TODO: Add chaise
}


TRIGGERS = {}
for algo_string, name in BASE_TRIGGERS.items():
    algo = parse_moves(algo_string)

    TRIGGERS.setdefault(name, [])

    TRIGGERS[name].append(str(algo))
    TRIGGERS[name].append(str(algo.transform(offset_y_moves)))
    TRIGGERS[name].append(str(algo.transform(offset_yprime_moves)))
    TRIGGERS[name].append(str(algo.transform(offset_y2_moves)))


TRIGGERS_REGEX = {
    name: re.compile(rf'(?<!\])({ "|".join(algos) })')
    for name, algos in TRIGGERS.items()
}
