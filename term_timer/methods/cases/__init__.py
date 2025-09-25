import json
from pathlib import Path

CASES_DIRECTORY = Path(__file__).parent

AF2L_PATH = CASES_DIRECTORY / 'af2l.json'
F2L_PATH = CASES_DIRECTORY / 'f2l.json'
OLL_PATH = CASES_DIRECTORY / 'oll.json'
PLL_PATH = CASES_DIRECTORY / 'pll.json'

CASES: dict[str, dict[str, str]] = {}
CASES_MASKS: dict[str, dict[str, str]] = {}


def load_cases(path):
    case_type = path.name.replace('.json', '').upper()
    cases = CASES.setdefault(case_type, {})
    cases_masks = CASES_MASKS.setdefault(case_type, {})

    with path.open('r') as fd:
        for case_name, data in json.load(fd).items():
            case_info = {
                'name': case_name,
                'main': data['main'],
                'probability': data['probability'],
                'probability_label': data['probability_label'],
                'setups': data['setups'],
                'masks': data['masks'],
            }

            for mask, mask_info in data['masks'].items():
                cases_masks[mask] = {
                    'case': case_name,
                    'configurations': mask_info,
                }

            case_id = case_name.split(' ')[0]
            cases[case_id] = case_info


for path in {AF2L_PATH, F2L_PATH, OLL_PATH, PLL_PATH}:
    load_cases(path)
