from rich.console import Console
from rich.theme import Theme

RED = '#FF0000'
GREEN = '#00D700'
ORANGE = '#FF8700'
YELLOW = '#FFFF00'
TEXT_DARK = '#080808'
TEXT_LIGHT = '#FFFFD7'

theme = Theme(
    {
        'warning': f'bold { RED }',
        'scramble': f'{ TEXT_DARK } on { GREEN }',
        'duration': f'{ TEXT_DARK } on { ORANGE }',
        'record': f'{ TEXT_DARK } on #5FFFAF',
        'inspection': f'{ TEXT_LIGHT } on #5F00D7',
        'consign': '#CECECE',

        'moves': f'bold { TEXT_LIGHT }',
        'result': f'bold { TEXT_LIGHT }',
        'best': f'bold { GREEN}',

        'edge': 'bold #00DFFF',
        'stats': 'bold #00AFFF',
        'bar': f'on { GREEN }',

        'red': f'{ RED }',
        'green': f'{ GREEN }',

        'mo3': f'bold { ORANGE }',
        'ao5': 'bold #00FFFF',
        'ao12': 'bold #FF00FF',
        'ao100': f'bold { YELLOW }',

        'timer_base': f'{ TEXT_DARK } on #DDFF00',
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
    },
)

console = Console(highlighter=None, theme=theme)
