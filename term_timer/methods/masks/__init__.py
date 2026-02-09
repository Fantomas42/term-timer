"""CFOP case's masks loading and management."""
import json
from pathlib import Path
from typing import Final

from term_timer.methods.annotations import CaseMaskInfo
from term_timer.methods.annotations import CaseMasks

CASES_DIRECTORY: Final = Path(__file__).parent

AF2L_PATH: Final = CASES_DIRECTORY / 'af2l.json'
F2L_PATH: Final = CASES_DIRECTORY / 'f2l.json'
OLL_PATH: Final = CASES_DIRECTORY / 'oll.json'
PLL_PATH: Final = CASES_DIRECTORY / 'pll.json'

CASES_MASKS: dict[str, dict[str, CaseMaskInfo]] = {}


def load_cases(path: Path) -> None:
    """Load case definitions from JSON file into CASES and CASES_MASKS."""
    case_type = path.name.replace('.json', '').upper()
    cases_masks = CASES_MASKS.setdefault(case_type, {})

    with path.open('r', encoding='utf-8') as fd:
        json_data: dict[str, CaseMasks] = json.load(fd)
        for case_code, masks_dict in json_data.items():
            for mask, mask_info in masks_dict.items():
                cases_masks[mask] = {
                    'case': case_code,
                    'configurations': mask_info,
                }


for path in {AF2L_PATH, F2L_PATH, OLL_PATH, PLL_PATH}:
    load_cases(path)
