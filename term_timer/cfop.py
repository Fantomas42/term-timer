from term_timer.magic_cube import Cube

STEPS = ['cross', 'f2l', 'oll', 'pll', ]#'auf']


def build_facelets_masked(mask: str, facelets: str) -> str:
    masked = []
    for i, value in enumerate(facelets):
        if mask[i] == '0':
            masked.append('-')
        else:
            masked.append(value)

    return ''.join(masked)


def check_cross(cube):
    mask = '010111010' + '000010000' * 5
    facelets = build_facelets_masked(mask, cube.as_twophase_facelets)
    return '-U-UUU-U-----R--------F--------D--------L--------B----' == facelets


def check_f2l(cube):
    mask = '111111111' + ('111111000' * 2) + '000000000' + ('111111000' * 2)
    facelets = build_facelets_masked(mask, cube.as_twophase_facelets)
    return 'UUUUUUUUURRRRRR---FFFFFF------------LLLLLL---BBBBBB---' == facelets


def check_oll(cube):
    mask = '111111111' + ('111111000' * 2) + '111111111' + ('111111000' * 2)
    facelets = build_facelets_masked(mask, cube.as_twophase_facelets)
    return 'UUUUUUUUURRRRRR---FFFFFF---DDDDDDDDDLLLLLL---BBBBBB---' == facelets


def check_pll(cube):
    mask = '1' * 54
    facelets = build_facelets_masked(mask, cube.as_twophase_facelets)
    return 'UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB' == facelets


def check_auf(cube):
    mask = '1' * 54
    facelets = build_facelets_masked(mask, cube.as_twophase_facelets)
    return 'UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB' == facelets


def cfop_steps(scramble, move_times):
    steps = {
        'cross': {},
        'f2l': {},
        'oll': {},
        'pll': {},
        #'auf': {},
    }
    cube = Cube(3)
    cube.rotate(scramble)

    index = 0
    current_step = 'cross'
    step_moves = []

    while not cube.is_done():
        step_index = STEPS.index(current_step)

        for step in STEPS[step_index:]:
            step_passed = globals()[f'check_{ step }'](cube)
            if step_passed:
                steps[step] = {
                    'moves': step_moves.copy(),
                }
                current_step = STEPS[step_index + 1]
                step_moves = []
            else:
                break

        step_moves.append(move_times[index])
        cube.rotate(move_times[index][0])
        index += 1

    steps[current_step] = {
        'moves': step_moves.copy(),
    }

    return steps
