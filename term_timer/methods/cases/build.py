import json
import sys
from pathlib import Path
from pprint import pformat
from typing import Any

from cubing_algs.constants import INITIAL_STATE
from cubing_algs.masks import OLL_MASK
from cubing_algs.masks import PLL_MASK
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.mirror import mirror_moves
from cubing_algs.vcube import VCube

from term_timer.argparser import ArgumentParser
from term_timer.methods.base import FaceletAnalyser
from term_timer.methods.base import get_step_config

SKIPPED = {
    'OLL': {
        'probability': '1/216',
        'aliases': [],
        'algorithms': [],
        'main': '',
    },
    'PLL': {
        'probability': '1/72',
        'aliases': [],
        'algorithms': [],
        'main': '',
    },
    'F2L': {
        'probability': '1/42',
        'aliases': [],
        'algorithms': [],
        'main': '',
    },
    'AF2L': {
        'probability': '1/42',
        'aliases': [],
        'algorithms': [],
        'main': '',
    },
}

TRANSLATIONS = {
    'Tortue': 'Turtle',
    'Serpent': 'Snake',
    'Right front wide antisune (RFWAS)': 'RFWAS',
    'Stérilet': 'Bottlecap',
    'Orque': 'Killer whale',
    'Left Wide Sune (LWS)': 'LWS',
    'Anti-Professeur Xavier': 'Anti-Prof X',
    'Professeur Xavier': 'Prof X',
    "Seein' Headlights (C and headlights)": "Seein' Headlights",
    'Right back wide antisune (RBWAS)': 'RBWAS',
    'Anti-Serpent': 'Anti-Snake',
    'Anti-Barbu': 'Anti-Bearded',
    'Barbu': 'Bearded',
    'Anti-Spotted Chameleon': 'Anti-Chameleon',
    'Spotted Chameleon': 'Chameleon',
}


def translate(value: str) -> str:
    return TRANSLATIONS.get(value, value)


def select_mask(mode: str, scheme_name: str) -> str:
    if mode == 'OLL':
        return FaceletAnalyser.build_facelets_masked(
            INITIAL_STATE, OLL_MASK,
        )
    if mode == 'PLL':
        return FaceletAnalyser.build_facelets_masked(
            INITIAL_STATE, PLL_MASK,
        )
    if mode == 'F2L':
        name = {
            'FR': 'F2L 1',
            'FL': 'F2L 2',
            'BR': 'F2L 3',
            'BL': 'F2L 4',
        }[scheme_name]

        return FaceletAnalyser.build_facelets_masked(
            INITIAL_STATE, get_step_config(
                name, 'mask',
            ),
        )

    return ''


def compute_masks(name: str, moves: str, mode: str,
                  *, debug: bool = False) -> dict[str, dict[str, str]]:
    if mode == 'AF2L':
        return {}

    masks: dict[str, dict[str, str]] = {}

    # For URF format
    initial_schemes = ['FR', 'FL', 'BR', 'BL']
    # Apply z2 because algorithms are designed to be applied with D on top
    initial_schemes_moves = ["z2 y'", 'z2', 'x2', 'z2 y']

    # Angular orientations
    orientation_moves = ['', 'y', "y'", 'y2']

    # In OLL other facelets than D are useless to track
    if mode == 'OLL':
        orientation_moves = ['']

    for scheme_name, scheme_moves in zip(
            initial_schemes,
            initial_schemes_moves,
            strict=True,
    ):
        scheme_mask = masks.setdefault(scheme_name, {})

        for orientation_move in orientation_moves:
            algorithm = parse_moves(moves).transform(
                mirror_moves,
            )
            # Orient scheme for having multiple colors,
            # apply reverse algorithm,
            # offset Y to capture all angular variations,
            # restore to URF state
            algorithm = (
                scheme_moves
                + algorithm
                + orientation_move
                + scheme_moves
            )

            mask = select_mask(mode, scheme_name)

            cube = VCube(mask, check=False)
            cube.rotate(algorithm)

            if debug:
                print(
                    f'{ name } "{ scheme_name or "?" }-'
                    f'{ orientation_move or "?" }" : { algorithm }',
                )
                cube.show()
                print(f'{ name } { mode } mode')
                cube.show(mode=mode.lower())

            scheme_mask[orientation_move] = cube.state

    return masks


def format_case(mode: str, code: str, info: dict[str, Any],
                data: dict[str, Any], *, debug: bool = False) -> None:
    name = code.split(' ')[1]
    if info['aliases'] and mode == 'OLL':
        name += f' { translate(info["aliases"][0]) }'

    case_data = data.setdefault(name, {})

    setups = []
    for algorithm in info['algorithms'][:10]:
        setups.append(
            str(
                parse_moves(algorithm).transform(
                    mirror_moves,
                ),
            ).replace(' ', ''),
        )

    main_algorithm = ''.join(info['main'])
    if main_algorithm:
        setups.insert(0, main_algorithm)

    if 'F2L' in mode:
        case_data['probability'] = 1 / 42
        case_data['probability_label'] = '1/42'
    else:
        case_data['probability'] = eval(info['probability'])  # noqa: S307
        case_data['probability_label'] = info['probability']

    case_data['main'] = main_algorithm
    case_data['setups'] = setups
    case_data['rotations'] = compute_masks(
        name, main_algorithm, mode,
        debug=debug,
    )


def format_cases(cases: dict[str, dict[str, Any]], mode: str,
                 *, debug: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {}

    for code, info in cases.items():
        format_case(mode, code, info, data, debug=debug)

    if mode in SKIPPED and len(cases) > 1:
        source = SKIPPED[mode]
        format_case(
            mode, f'{ mode } SKIP', source,
            data, debug=debug,
        )

    return data


def build(data: dict[str, dict[str, Any]], mode: str, case: str) -> None:
    print(f'Processing { mode }')

    cases = {}

    for name, info in data.items():
        if info['type'] == mode:
            if case:
                if case in name:
                    cases[name] = info
            else:
                cases[name] = info

    print(f'- { len(cases) } cases to process')

    formatted_cases = format_cases(cases, mode, debug=bool(case))

    output_path = Path(__file__).parent / f'{ mode.lower() }.json'

    if not case:
        with output_path.open('w+', encoding='utf8') as fd:
            json.dump(
                formatted_cases,
                fd,
                indent=4,
                sort_keys=True,
            )

        print(f'- Wrote { output_path }')
    else:
        print(pformat(formatted_cases))


def main() -> None:
    parser = ArgumentParser(
        description='Build cases data.',
    )

    parser.add_argument(
        'source',
        metavar='SOURCE',
        help='Source to use for build',
    )
    parser.add_argument(
        '-m', '--mode',
        metavar='MODE',
        default='all',
        help='Mode cases to build\nDefault: all',
    )
    parser.add_argument(
        '-c', '--case',
        metavar='CASE',
        default='',
        help='Case name to filter\nDefault: None',
    )

    args = parser.parse_args(sys.argv[1:])

    with Path.open(args.source) as fd:
        data = json.load(fd)

    mode = args.mode.upper()
    all_modes = ['OLL', 'PLL', 'F2L', 'AF2L']

    if mode == 'ALL':
        for mode in all_modes:
            build(data, mode, args.case)
    elif mode in all_modes:
        build(data, mode, args.case)


if __name__ == '__main__':
    main()
