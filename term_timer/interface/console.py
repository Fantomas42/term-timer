from rich.console import Console as RichConsole
from rich.theme import Theme

from term_timer.config import UI_CONFIG

RED = '#FF0000'
GREEN = '#00D700'
ORANGE = '#FF8700'
YELLOW = '#FFFF00'
TEXT_DARK = '#080808'
TEXT_LIGHT = '#FFFFD7'

theme = {
    'warning': f'bold { RED }',
    'caution': f'bold { ORANGE }',
    'success': f'bold { GREEN }',
    'comment': '#CC9933',

    'scramble': f'{ TEXT_DARK } on { GREEN }',
    'duration': f'{ TEXT_DARK } on { ORANGE }',
    'record': f'{ TEXT_DARK } on #5FFFAF',

    'analysis': f'bold { TEXT_LIGHT } on #4D0092',
    'inspection': f'{ TEXT_LIGHT } on #5F00D7',
    'recognition': f'{ TEXT_LIGHT } on #5F00D7',
    'execution': f'{ TEXT_LIGHT } on #4D0092',
    'consign': '#CECECE',
    'step': 'bold #00AFFF',
    'substep': 'bold #00DFFF',
    'skipped': f'{ TEXT_DARK } on #5FFFAF',

    'recognition_p': TEXT_LIGHT,
    'execution_p': TEXT_LIGHT,
    'duration_p': TEXT_LIGHT,

    'server': 'bold #00DFFF',
    'bluetooth': 'bold #FFFFFF on #133EBF',
    'extlink': 'bold #FFFFFF on #522081',

    'timer': f'bold { ORANGE }',
    'device': 'bold #CFAAD7',
    'session': 'bold #00FFCC',
    'title': f'bold { TEXT_LIGHT }',
    'moves': f'bold { TEXT_LIGHT }',
    'result': f'bold { TEXT_LIGHT }',
    'date': f'bold { GREEN}',
    'best': f'bold { GREEN}',

    'edge': 'bold #00DFFF',
    'percent': 'bold #00DFFF',
    'stats': 'bold #00AFFF',
    'bar': f'on { GREEN }',

    'red': f'{ RED }',
    'green': f'{ GREEN }',

    'dnf': f'bold { TEXT_LIGHT } on { RED }',
    'plus_two': f'bold { TEXT_DARK } on { ORANGE }',

    'mo3': f'bold { ORANGE }',
    'ao5': 'bold #00FFFF',
    'ao12': 'bold #FF00FF',
    'ao100': f'bold { YELLOW }',
    'ao1000': f'bold { RED }',

    'tps': 'bold #00DFFF',
    'tps_e': 'bold #00AAAA',
    'missed': 'bold #FF4444',
    'htm': 'bold #6EFFFF',
    'stm': 'bold #6EDFF6',
    'qtm': 'bold #99D799',
    'etm': 'bold #C2A0FA',
    'qstm': 'bold #FEBF8A',

    'grade_s': 'bold #FF7F7E',
    'grade_a+': 'bold #FFBF7F',
    'grade_a': 'bold #FFBF7F',
    'grade_b+': 'bold #FFDF80',
    'grade_b': 'bold #FFDF80',
    'grade_c+': 'bold #FEFF7F',
    'grade_c': 'bold #FEFF7F',
    'grade_d': 'bold #BEFF7F',
    'grade_e': 'bold #7EFF80',
    'grade_f': 'bold #7FFFFF',

    'timer_base': f'{ TEXT_DARK } on #FFE100',
    'timer_05': f'{ TEXT_DARK } on #C8FF00',
    'timer_10': f'{ TEXT_DARK } on #33FF00',
    'timer_15': f'{ TEXT_DARK } on #00FFCC',
    'timer_20': f'{ TEXT_DARK } on #00FFFF',
    'timer_25': f'{ TEXT_LIGHT } on #3399FF',
    'timer_30': f'{ TEXT_LIGHT } on #0000FF',
    'timer_35': f'{ TEXT_LIGHT } on #6600FF',
    'timer_40': f'{ TEXT_LIGHT } on #9900FF',
    'timer_45': f'{ TEXT_LIGHT } on #CC00FF',
    'timer_50': f'{ TEXT_LIGHT } on #FF00FF',

    'face_w': f'{ TEXT_DARK } on #E4E4E4',
    'face_y': f'{ TEXT_DARK } on { YELLOW }',
    'face_b': f'{ TEXT_LIGHT } on #0000FF',
    'face_r': f'{ TEXT_DARK } on { RED }',
    'face_g': f'{ TEXT_DARK } on { GREEN }',
    'face_o': f'{ TEXT_DARK } on { ORANGE }',
    'face_h': f'{ TEXT_DARK } on #666666',
}

theme.update(UI_CONFIG)


console = RichConsole(highlighter=None, theme=Theme(theme))

if __name__ == '__main__':
    for name, color in theme.items():
        console.print(
            f'[{ name }]{ name:>15}[/{ name }] : { color }',
        )


class Console:

    def __init__(self):
        super().__init__()

        self.console = console
