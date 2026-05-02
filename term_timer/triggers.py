"""Trigger pattern detection and formatting for algorithm analysis."""
import re
from collections.abc import Callable
from re import Pattern
from typing import Final

from cubing_algs.parsing import parse_moves
from cubing_algs.transform.offset import offset_y2_moves
from cubing_algs.transform.offset import offset_y_moves
from cubing_algs.transform.offset import offset_yprime_moves
from cubing_algs.transform.symmetry import symmetry_m_moves
from cubing_algs.triggers import TRIGGER_PATTERNS

BLOCK_PATTERN: Final = re.compile(r'\[[^\]]+\].*?\[/[^\]]+\]')
SLUG_PATTERN: Final = re.compile(r'[^a-z0-9]+')


TRIGGERS: dict[str, list[str]] = {}
for pattern in TRIGGER_PATTERNS:
    name = SLUG_PATTERN.sub('-', pattern.name.lower()).strip('-')
    source = parse_moves(pattern.moves)
    anti = source.transform(symmetry_m_moves)
    TRIGGERS.setdefault(name, [])
    for algo in [source, anti]:
        TRIGGERS[name].append(str(algo))
        TRIGGERS[name].append(str(algo.transform(offset_y_moves)))
        TRIGGERS[name].append(str(algo.transform(offset_yprime_moves)))
        TRIGGERS[name].append(str(algo.transform(offset_y2_moves)))


TRIGGERS_REGEX: Final = {
    name: re.compile(rf'({ "|".join(algos) })(?![2\'])')
    for name, algos in TRIGGERS.items()
}

DEFAULT_TRIGGERS: Final = [
    'anti-sune',
    'sexy-move',
    'sledgehammer',
    'sune-trigger',
    'sane-trigger',
    'slot-extended',
    'slot-extract',
    'slot-insert',
]


def apply_trigger_outside_blocks(
        algorithm: str, regex: Pattern[str],
        replacement_func: Callable[[re.Match[str]], str]) -> str:
    """
    Apply trigger pattern.

    Returns:
        Algorithm string with trigger replacements applied outside blocks.

    """
    blocks = [
        (match.start(), match.end(), match.group(0))
        for match in re.finditer(BLOCK_PATTERN, algorithm)
    ]

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
