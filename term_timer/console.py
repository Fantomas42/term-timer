from rich.console import Console
from rich.theme import Theme

theme = Theme(
    {
        'warning': 'bold red',
        'scramble': '#080808 on #00D700',
        'duration': '#080808 on #FF8700',
        'record': '#080808 on #5FFFAF',
        'consign': '#CECECE',

        'moves': 'bold white',
        'result': 'bold white',

        'stats': 'bold #00AFFF',
        'bar': 'on #00D700',

        'red': '#ff0000',
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
    },
)

console = Console(highlighter=None, theme=theme)
