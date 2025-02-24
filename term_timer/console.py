from rich.console import Console
from rich.theme import Theme

theme = Theme(
    {
        'warning': 'bold red',
        'scramble': '#080808 on #00D700',
        'duration': '#080808 on #cccc00',
        'moves': 'bold white',
        'result': 'bold white',
        'stats': 'bold blue',
        'record': 'bold white on #0000cc',
        'bar': 'green on green',

        'red': 'red',
        'green': 'green',

        'mo3': 'bold',
        'ao5': 'bold',
        'ao12': 'bold',

        'timer_base': 'green',
        'timer_10': 'blue',
        'timer_15': 'green',
        'timer_20': 'green',
        'timer_25': 'green',
        'timer_30': 'green',
        'timer_35': 'green',
    },
)

console = Console(theme=theme)
