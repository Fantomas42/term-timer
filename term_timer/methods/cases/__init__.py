import json
from pathlib import Path
from typing import TypedDict

CASES_DIRECTORY = Path(__file__).parent

AF2L_PATH = CASES_DIRECTORY / 'af2l.json'
F2L_PATH = CASES_DIRECTORY / 'f2l.json'
OLL_PATH = CASES_DIRECTORY / 'oll.json'
PLL_PATH = CASES_DIRECTORY / 'pll.json'


class CaseInfo(TypedDict):
    """Information about a specific case."""
    name: str
    main: str
    probability: float
    probability_label: str
    setups: list[str]
    masks: dict[str, list[str]]


class CaseMaskInfo(TypedDict):
    """Mask configuration for a case."""
    case: str
    configurations: list[str]


CASES: dict[str, dict[str, CaseInfo]] = {}
CASES_MASKS: dict[str, dict[str, CaseMaskInfo]] = {}


def load_cases(path: Path) -> None:
    case_type = path.name.replace('.json', '').upper()
    cases = CASES.setdefault(case_type, {})
    cases_masks = CASES_MASKS.setdefault(case_type, {})

    with path.open('r') as fd:
        json_data: dict[str, CaseInfo] = json.load(fd)
        for case_name, case_data in json_data.items():
            case_info = case_data
            case_info['name'] = case_name

            masks_dict = case_data['masks']
            for mask, mask_info in masks_dict.items():
                cases_masks[mask] = {
                    'case': case_name,
                    'configurations': mask_info,
                }

            case_id = case_name.split(' ')[0]
            cases[case_id] = case_info


for path in {AF2L_PATH, F2L_PATH, OLL_PATH, PLL_PATH}:
    load_cases(path)
