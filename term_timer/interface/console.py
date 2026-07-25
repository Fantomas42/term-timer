"""Console theme configuration and Rich console instance."""
from typing import Final

from rich.console import Console as RichConsole
from rich.theme import Theme

from term_timer.config import UI_CONFIG

RED: Final = '#FF0000'
GREEN: Final = '#00D700'
ORANGE: Final = '#FF8700'
YELLOW: Final = '#FFFF00'
TEXT_DARK: Final = '#080808'
TEXT_LIGHT: Final = '#FFFFD7'
BG_HIDDEN: Final = '#333333'

theme: dict[str, str] = {
    'warning': f'bold { RED }',
    'caution': f'bold { ORANGE }',
    'success': f'bold { GREEN }',
    'comment': '#CC9933',

    'scramble': f'{ TEXT_DARK } on { GREEN }',
    'duration': f'{ TEXT_DARK } on { ORANGE }',
    'estimate': f'{ TEXT_DARK } on #00FFD7',
    'record': f'{ TEXT_DARK } on #5FFFAF',
    'solution': f'{ TEXT_DARK } on #9999FF',

    'analysis': f'bold { TEXT_LIGHT } on #4D0092',
    'inspection': f'{ TEXT_LIGHT } on #5F00D7',
    'recognition': f'{ TEXT_LIGHT } on #5F00D7',
    'execution': f'{ TEXT_LIGHT } on #4D0092',
    'consign': '#CECECE',
    'highlight': f'bold { TEXT_LIGHT }',
    'diagnostic': f'bold { TEXT_LIGHT }',
    'examen': f'bold { TEXT_LIGHT } on #2E8B57',
    'critical': f'bold { RED }',
    'high': f'bold { ORANGE }',
    'medium': f'bold { YELLOW }',
    'low': f'bold { GREEN }',
    'trainer': f'bold { TEXT_LIGHT } on #5555CC',
    'routine': f'bold { TEXT_DARK } on #55CCFF',
    'key':  f'bold { TEXT_LIGHT }',
    'confirm': TEXT_LIGHT,
    'step': 'bold #00AFFF',
    'substep': 'bold #00DFFF',
    'skipped': f'{ TEXT_DARK } on #5FFFAF',
    'scrambled': 'bold #BBAAEE',
    'eo': 'bold #40E0D0',

    'fsrs-case': f'bold { TEXT_LIGHT } on #CC33CC',
    'fsrs-result': f'bold { TEXT_LIGHT } on #8F248F',
    'fsrs-focus': f'bold { TEXT_LIGHT } on #03A8A3',
    'context': TEXT_LIGHT,
    'new': f'bold { GREEN}',
    'learning': f'bold { YELLOW }',
    'relearning': 'bold #FFCC00',
    'review': 'bold #00FFAF',
    'stable': 'bold #5BAFF0',
    'easy': 'bold #00AFFF',
    'good': f'bold { GREEN }',
    'hard': f'bold { ORANGE }',
    'again': f'bold { RED}',

    'recognition-p': TEXT_LIGHT,
    'execution-p': TEXT_LIGHT,
    'duration-p': TEXT_LIGHT,

    'server': 'bold #00DFFF',
    'bluetooth': 'bold #FFFFFF on #133EBF',
    'localhost': 'bold #FFFFFF on #522081',
    'algcubing': 'bold #FFFFFF on #006060',
    'cubedb': 'bold #FFFFFF on #444444',

    'timer': f'bold { ORANGE }',
    'device': 'bold #CFAAD7',
    'session': 'bold #00FFCC',
    'title': f'bold { TEXT_LIGHT }',
    'moves': f'bold { TEXT_LIGHT }',
    'result': f'bold { TEXT_LIGHT }',
    'time': f'bold { TEXT_DARK } on { TEXT_LIGHT }',
    'date': f'bold { GREEN}',
    'best': f'bold { GREEN}',

    'pause': f'bold { ORANGE }',
    'reco-pause': 'bold #00FFCC',
    'pre-auf': f'bold { TEXT_LIGHT } on #5F5F8E',
    'post-auf': f'bold { TEXT_LIGHT } on  #003D80',

    'anti-sune': f'{ TEXT_DARK } on #20C997',
    'sexy-move': f'{ TEXT_DARK } on #FF6666',
    'sledgehammer': f'{ TEXT_DARK } on #88CCFF',
    'hedgeslammer': f'{ TEXT_DARK } on #FFD966',
    'slot-extract': f'{ TEXT_DARK } on #66FF66',
    'slot-insert': f'{ TEXT_DARK } on #AAFFAA',
    'sune-trigger': f'{ TEXT_LIGHT } on #AA3333',
    'sane-trigger': f'{ TEXT_DARK } on #FF8888',
    't-perm-trigger': f'{ TEXT_DARK } on #CC88FF',
    'sune': f'{ TEXT_DARK } on #FF8844',
    'sexy-sledge': f'{ TEXT_DARK } on #FF6699',
    'niklas': f'{ TEXT_LIGHT } on #9966CC',
    'slot-extended': f'{ TEXT_DARK } on #33FFCC',
    'wide-sexy': f'{ TEXT_DARK } on #FF44DD',
    'wide': 'bold #FF00FF',
    'slice': 'bold #00DFFF',
    'rotation': f'bold { ORANGE }',
    'rotation_x': 'bold #C070FF',
    'rotation_y': 'bold #FF60A0',
    'rotation_z': 'bold #A0FF60',

    'edge': 'bold #00DFFF',
    'percent': 'bold #00DFFF',
    'stats': 'bold #00AFFF',
    'round': 'bold #00FFFF',
    'bar': f'on { GREEN }',

    'addition': f'{ GREEN }',
    'deletion': f'{ RED }',

    'red': f'{ RED }',
    'green': f'{ GREEN }',
    'orange': f'{ ORANGE }',

    'dnf': f'bold { TEXT_LIGHT } on { RED }',
    'plus-two': f'bold { TEXT_DARK } on { ORANGE }',

    'mo3': f'bold { ORANGE }',
    'ao5': 'bold #00FFFF',
    'ao12': 'bold #FF00FF',
    'ao25': 'bold #99FFCC',
    'ao50': 'bold #FF99CC',
    'ao100': 'bold #FFCC99',
    'ao200': 'bold #99CCFF',
    'ao500': 'bold #CC99FF',
    'ao1000': 'bold #CCFF99',
    'average': f'bold { TEXT_LIGHT }',
    'no-ao': 'bold #666666',
    'detail': '#8A8A8A',

    'punchcard-1': '#2A4A6B',
    'punchcard-2': '#4A8FD0',
    'punchcard-3': '#6FC0FF',
    'punchcard-4': '#A8E4FF',

    'trend-up': f'bold { GREEN }',
    'trend-flat': 'bold #888888',
    'trend-down': f'bold { RED }',

    'tps': 'bold #00DFFF',
    'tps-e': 'bold #00AAAA',
    'exec-overhead': 'bold #FF4444',
    'trans-overhead': 'bold #FF8844',
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
}

theme.update(UI_CONFIG)


console = RichConsole(highlighter=None, theme=Theme(theme))


class Console:
    """Mixin providing Rich console access for styled terminal output."""

    def __init__(self) -> None:
        """Initialize console mixin with Rich console instance."""
        super().__init__()

        self.console: RichConsole = console


if __name__ == '__main__':
    for name, color in theme.items():
        console.print(
            f'[{ name }]{ name:>15}[/{ name }] : { color }',
        )
