from rich.console import Console
from rich.theme import Theme

theme = Theme(
    {
        'warning': 'bold #FF0000',
        'scramble': '#080808 on #00D700',
        'duration': '#080808 on #FF8700',
        'record': '#080808 on #5FFFAF',
        'consign': '#CECECE',

        'moves': 'bold #FFFFFF',
        'result': 'bold #FFFFFF',

        'stats': 'bold #00AFFF',
        'bar': 'on #00D700',

        'red': '#FF0000',
        'green': '#00D700',

        'mo3': 'bold #FF8700',
        'ao5': 'bold #00FFFF',
        'ao12': 'bold #FF00FF',
        'ao100': 'bold #FFFF00',

        'timer_base': '#080808 on #DDFF00',
        'timer_10': '#080808 on #33FF00',
        'timer_15': '#080808 on #00FFCC',
        'timer_20': '#080808 on #00FFFF',
        'timer_25': '#FFFFD7 on #3399FF',
        'timer_30': '#FFFFD7 on #0000FF',
        'timer_35': '#FFFFD7 on #6600FF',
        'timer_40': '#FFFFD7 on #9900FF',
        'timer_45': '#FFFFD7 on #CC00FF',
        'timer_50': '#FFFFD7 on #FF00FF',

        'face_w': '#080808 on #E4E4E4',
        'face_y': '#080808 on #FFFF00',
        'face_b': '#FFFFFF on #0000FF',
        'face_r': '#080808 on #FF0000',
        'face_g': '#080808 on #00D700',
        'face_o': '#080808 on #FF8700',
    },
)

console = Console(highlighter=None, theme=theme)
