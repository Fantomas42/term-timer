import builtins
from pathlib import Path

from term_timer.console import console

computed = Path('twophase').exists()

if computed:
    _print = builtins.print
    builtins.print = lambda *x, **y: None  # noqa: ARG005
else:
    console.print(
        '[warning]:brain: Please be patient for the first run...[/warning]',
    )

from twophase.solver import solve  # noqa: E402

if computed:
    builtins.print = _print

__all__ = ['solve']
