from term_timer.magic_cube import Cube


class CFOPAnalyser:
    STEPS = ('cross', 'f2l', 'oll', 'pll') #, 'auf')

    def __init__(self, scramble, move_times):
        self.scramble = scramble
        self.move_times = move_times

        self.steps = {}
        for step in self.STEPS:
            self.steps[step] = {
                'moves': [],
                'comments': [],
            }

        self.split_steps()

    def split_steps(self):
        cube = Cube(3)
        cube.rotate(self.scramble)

        move_index = 0
        current_step = self.STEPS[0]
        step_moves = []

        while not cube.is_done():
            step_index = self.STEPS.index(current_step)

            for step in self.STEPS[step_index:]:
                step_passed = getattr(self, f'check_{ step}')(cube)
                if step_passed:
                    self.steps[step]['moves'] = step_moves.copy()
                    current_step = self.STEPS[step_index + 1]
                    step_moves = []
                else:
                    break

            step_moves.append(self.move_times[move_index])
            cube.rotate(self.move_times[move_index][0])
            move_index += 1

        self.steps[current_step]['moves'] = step_moves.copy()

    @staticmethod
    def build_facelets_masked(mask: str, facelets: str) -> str:
        masked = []
        for i, value in enumerate(facelets):
            if mask[i] == '0':
                masked.append('-')
            else:
                masked.append(value)

        return ''.join(masked)

    def check_cross(self, cube):
        mask = '010111010' + '000010000' * 5
        facelets = self.build_facelets_masked(mask, cube.as_twophase_facelets)
        return '-U-UUU-U-----R--------F--------D--------L--------B----' == facelets

    def check_f2l(self, cube):
        mask = '111111111' + ('111111000' * 2) + '000000000' + ('111111000' * 2)
        facelets = self.build_facelets_masked(mask, cube.as_twophase_facelets)
        return 'UUUUUUUUURRRRRR---FFFFFF------------LLLLLL---BBBBBB---' == facelets

    def check_oll(self, cube):
        mask = '111111111' + ('111111000' * 2) + '111111111' + ('111111000' * 2)
        facelets = self.build_facelets_masked(mask, cube.as_twophase_facelets)
        return 'UUUUUUUUURRRRRR---FFFFFF---DDDDDDDDDLLLLLL---BBBBBB---' == facelets

    def check_pll(self, cube):
        mask = '1' * 54
        facelets = self.build_facelets_masked(mask, cube.as_twophase_facelets)
        return 'UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB' == facelets
