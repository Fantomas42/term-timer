import builtins
import os
from importlib.util import find_spec
from pathlib import Path

from term_timer.console import console

TWO_PHASE_INSTALLED = find_spec('twophase') is not None
TWO_PHASE_ENABLED = bool(int(os.getenv('TWO_PHASE_ENABLED', '1')))

USE_TWO_PHASE = TWO_PHASE_INSTALLED and TWO_PHASE_ENABLED


if USE_TWO_PHASE:
    computed = Path('twophase').exists()

    if computed:
        _print = builtins.print
        builtins.print = lambda *x, **y: None  # noqa: ARG005
    else:
        console.print(
            '[warning]:brain: Please be patient for the first run...[/warning]',
        )

    from twophase.solver import solve

    if computed:
        builtins.print = _print
else:
    solve = None


__all__ = ['solve']
