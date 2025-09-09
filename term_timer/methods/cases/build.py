import json
import sys
from pathlib import Path
from typing import Any

from cubing_algs.constants import INITIAL_STATE
from cubing_algs.masks import OLL_MASK
from cubing_algs.masks import PLL_MASK
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.mirror import mirror_moves
from cubing_algs.vcube import VCube

from term_timer.argparser import ArgumentParser
from term_timer.config import DEBUG
from term_timer.methods.base import FaceletAnalyser


SKIPPED = {
    'OLL': {
        'probability': 1 / 216,
        'probability_label': '1/216',
    },
    'PLL': {
        'probability': 1 / 72,
        'probability_label': '1/72',
    },
    'F2L': {
        'probability': 1 / 42,
        'probability_label': '1/42',
    },
    'AF2L': {
        'probability': 1 / 42,
        'probability_label': '1/42',
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


def select_mask(mode: str, _scheme_name: str) -> str:
    if mode == 'OLL':
        return FaceletAnalyser.build_facelets_masked(
            INITIAL_STATE, OLL_MASK,
        )
    if mode == 'PLL':
        return FaceletAnalyser.build_facelets_masked(
            INITIAL_STATE, PLL_MASK,
        )

    return ''


def compute_masks(name: str, moves: str,
                  mode: str) -> dict[str, dict[str, str]]:
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
                scheme_moves + algorithm
                + orientation_move + scheme_moves
            )

            mask = select_mask(mode, scheme_name)

            cube = VCube(mask, check=False)
            cube.rotate(algorithm)

            if DEBUG:
                print(
                    f'{ name } "{ scheme_name or "?"}-'
                    f'{ orientation_move or "?" }" : { algorithm }',
                )
                cube.show()
                print(f'{ name } { mode } mode')
                cube.show(mode=mode.lower())

            scheme_mask[orientation_move] = cube.state

    return masks


def format_case(mode: str, code: str, info: dict[str, Any],
                data: dict[str, Any]) -> None:
    name = code.split(' ')[1]
    if info['aliases']:
        name += f' { translate(info["aliases"][0]) }'

    case_data = data.setdefault(name, {})

    setups = []
    for algorithm in info['algos'][:5]:
        setups.append(
            str(
                parse_moves(algorithm['moves']).transform(
                    mirror_moves,
                ),
            ).replace(' ', ''),
        )

    main_algorithm = ''.join(info['algos'][0]['moves'])

    if 'F2L' in mode:
        case_data['probability'] = 1 / 42
        case_data['probability_label'] = '1/42'
    else:
        case_data['probability'] = eval(info['probability'])  # noqa: S307
        case_data['probability_label'] = info['probability']

    case_data['main'] = main_algorithm
    case_data['setups'] = setups
    case_data['rotations'] = compute_masks(name, main_algorithm, mode)


def format_cases(cases: dict[str, dict[str, Any]], mode: str) -> dict[str, Any]:
    data: dict[str, Any] = {}

    for code, info in cases.items():
        format_case(mode, code, info, data)

    if mode in SKIPPED:
        case_data = data.setdefault('SKIP', {})
        case_data.update(SKIPPED[mode])
        case_data.update(
            {
                'main': '',
                'setups': [],
                'rotations': {},
            },
        )

    return data


def build(data: dict[str, dict[str, Any]], mode: str) -> None:
    print(f'Processing { mode }')

    cases = {}

    for name, info in data.items():
        if info['type'] == mode:
            cases[name] = info

    print(f'- { len(cases) } cases to process')

    formatted_cases = format_cases(cases, mode)

    output_path = Path(__file__).parent / f'{ mode.lower()}.json'

    with output_path.open('w+', encoding='utf8') as fd:
        json.dump(
            formatted_cases,
            fd,
            indent=4,
            sort_keys=True,
        )

    print(f'- Wrote { output_path }')


def main() -> None:
    parser = ArgumentParser(
        description='Build cases data.',
    )

    parser.add_argument(
        'source',
        metavar='SOURCE',
        help='Source to use for build',
    )

    args = parser.parse_args(sys.argv[1:])

    with Path.open(args.source) as fd:
        data = json.load(fd)

    build(data, 'OLL')
    build(data, 'PLL')
    build(data, 'F2L')
    build(data, 'AF2L')


if __name__ == '__main__':
    main()
