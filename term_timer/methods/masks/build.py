"""Build CFOP case database from JSON source files."""
# ruff: noqa: T201
import json
import sys
from pathlib import Path
from pprint import pformat

from cubing_algs.annotations import CubeDisplayMask
from cubing_algs.display.masks import F2L_MASK
from cubing_algs.display.masks import OLL_MASK
from cubing_algs.display.masks import PLL_MASK
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.invert import invert_moves
from cubing_algs.vcube import VCube

from term_timer.argparser import ArgumentParser
from term_timer.methods.annotations import CaseMasks
from term_timer.methods.annotations import SourceCaseInfo
from term_timer.methods.cfop import CFOP_CASE_ENCODERS

CFOP_CASE_MASKS: dict[str, CubeDisplayMask] = {
    'OLL': OLL_MASK,
    'PLL': PLL_MASK,
    'F2L': F2L_MASK,
}


def compute_masks(
        name: str,
        moves: str,
        mode: str,
        *,
        debug: bool = False,
) -> CaseMasks:
    """
    Compute facelet masks for case across different orientations.

    Returns:
        Dictionary mapping encoded cases to orientation configurations.

    """
    if mode == 'AF2L':
        return {}

    masks: CaseMasks = {}

    algorithm = parse_moves(moves).transform(
        invert_moves,
    )

    initial_schemes = ['']
    # POV orientations
    # the mask will be taken from multiple points of views
    orientation_moves = ['', 'y', "y'", 'y2']

    # F2L cases also need to have AUF extra move to catch
    # correctly all cases when the top layer is involded
    if mode == 'F2L':
        # For URF format,
        # can represent a color schema variations and a pairs of faces
        initial_schemes = [
            'Front Right', 'Front Left',
            'Back Right', 'Back Left',
        ]

        auf_moves = ['U', "U'", 'U2']
        new_orientations = orientation_moves.copy()
        for auf_move in auf_moves:
            for orientation_move in orientation_moves:
                new_orientations.append(
                    f'{ auf_move } { orientation_move }'.strip(),
                )
        orientation_moves = new_orientations

    for scheme in initial_schemes:
        for orientation_move in orientation_moves:
            case_algorithm = algorithm + orientation_move

            cube = VCube(size=3)
            cube.rotate(case_algorithm)

            if debug:
                print('*' * 25)
                print(f'{ name }: { case_algorithm }')
                cube.show(mode=CFOP_CASE_MASKS.get(mode, ''))

            encoded_case = CFOP_CASE_ENCODERS[
                f'{mode} {scheme}'.strip()
            ](cube.state)

            mask_infos = masks.setdefault(
                encoded_case, [],
            )
            mask_infos.append(orientation_move)

    return masks


def format_case(mode: str, code: str, info: SourceCaseInfo,
                data: dict[str, CaseMasks], *,
                debug: bool = False) -> None:
    """Format single case from source info into mask structure."""
    name = code.split(' ')[1]

    main_algorithm = ''.join(info['main'])

    masks = compute_masks(
        name, main_algorithm, mode,
        debug=debug,
    )

    data[name] = masks


def format_cases(cases: dict[str, SourceCaseInfo], mode: str, *,
                 debug: bool = False) -> dict[str, CaseMasks]:
    """
    Format all cases for a mode into masks dictionary.

    Returns:
        Dictionary mapping case names to formatted masks structures.

    """
    data: dict[str, CaseMasks] = {}

    for code, info in cases.items():
        format_case(mode, code, info, data, debug=debug)

    if len(cases) > 1:
        format_case(
            mode, f'{ mode } SKIP', {'main': '', 'type': mode},
            data, debug=debug,
        )

    return data


def build(data: dict[str, SourceCaseInfo], mode: str, case: str) -> None:
    """Build case data JSON file for specified mode from source data."""
    print(f'Processing { mode }')

    cases: dict[str, SourceCaseInfo] = {}

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
        with output_path.open('w+', encoding='utf-8') as fd:
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
    """Build case data from source files."""
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
