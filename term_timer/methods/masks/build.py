"""Build CFOP case database from JSON source files."""
# ruff: noqa: T201
import json
import sys
from collections.abc import Callable
from pathlib import Path
from pprint import pformat

from cubing_algs.masks import F2L_BL_MASK
from cubing_algs.masks import F2L_BR_MASK
from cubing_algs.masks import F2L_FL_MASK
from cubing_algs.masks import F2L_FR_MASK
from cubing_algs.parsing import parse_moves
from cubing_algs.transform.mirror import mirror_moves
from cubing_algs.vcube import VCube

from term_timer.argparser import ArgumentParser
from term_timer.methods.masks.encoders import f2l_case_encoder
from term_timer.methods.masks.encoders import oll_case_encoder
from term_timer.methods.masks.encoders import pll_case_encoder
from term_timer.methods.types import CaseMasks
from term_timer.methods.types import SourceCaseInfo

CFOP_CASE_ENCODERS: dict[str, Callable[[str], str]] = {
    'OLL': oll_case_encoder,
    'PLL': pll_case_encoder,

    'F2L FR': f2l_case_encoder(F2L_FR_MASK),
    'F2L FL': f2l_case_encoder(F2L_FL_MASK),
    'F2L BR': f2l_case_encoder(F2L_BR_MASK),
    'F2L BL': f2l_case_encoder(F2L_BL_MASK),
}


def compute_masks(name: str, moves: str, mode: str,
                  *, debug: bool = False) -> CaseMasks:
    """
    Compute facelet masks for case across different orientations.

    Returns:
        Dictionary mapping encoded cases to orientation configurations.

    """
    if mode == 'AF2L':
        return {}

    masks: CaseMasks = {}

    algorithm = parse_moves(moves).transform(
        mirror_moves,
    )

    # For URF format,
    # can represent a color schema variations and a pairs of faces
    initial_schemes = ['FR', 'FL', 'BR', 'BL']
    # Apply orientations because algorithms are designed
    # to be applied with D on top, FRU angle from user,
    # so the schemes are correctly tracked
    initial_schemes_moves = ["z2 y'", 'z2', 'x2', 'z2 y']

    # Angular orientations
    # the masks will be taken from multiple points of views
    orientation_moves = ['', 'y', "y'", 'y2']

    # F2L cases also need to have AUF extra move to catch
    # correctly all cases when the top layer is involded
    if mode == 'F2L':
        auf_moves = ['U', "U'", 'U2']
        new_orientations = orientation_moves.copy()
        for auf_move in auf_moves:
            for orientation_move in orientation_moves:
                new_orientations.append(
                    f'{ auf_move } { orientation_move }'.strip(),
                )
        orientation_moves = new_orientations

    for scheme_name, scheme_moves in zip(
            initial_schemes,
            initial_schemes_moves,
            strict=True,
    ):
        for orientation_move in orientation_moves:
            # Orientation scheme for having multiple colors,
            # apply reverse algorithm,
            # offset in Y to capture all angular variations,
            # cancel orientation scheme back to U on top.
            case_algorithm = (
                scheme_moves
                + algorithm
                + orientation_move
                + scheme_moves
            )

            mode_key = mode
            if mode == 'F2L':
                mode_key += f' { scheme_name }'

            cube = VCube()
            cube.rotate(case_algorithm)

            if debug:
                config = (
                    f'"{ scheme_name or "?" }-{ orientation_move or "?" }" '
                    f': { algorithm }'
                )
                print('*' * 25)
                print(f'{ name } { config }')
                cube.show()
                print(f'{ name } { mode } { config }')
                cube.show(mode=mode.lower())

            encoded_case = CFOP_CASE_ENCODERS[mode_key](cube.state)

            mask_infos = masks.setdefault(
                encoded_case, [],
            )
            configuration = f'{ scheme_name } { orientation_move }'.strip()
            if configuration not in mask_infos:
                mask_infos.append(configuration)

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
