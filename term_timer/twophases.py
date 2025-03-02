import builtins
from importlib.util import find_spec
from pathlib import Path

from term_timer.console import console

TWO_PHASE_INSTALLED = find_spec('twophase') is not None

if TWO_PHASE_INSTALLED:
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
else:
    solve = None


__all__ = ['solve']
