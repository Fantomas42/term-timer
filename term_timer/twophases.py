import builtins

_print = builtins.print
builtins.print = lambda *x, **y: None  # noqa: ARG005

from twophase.solver import solve  # noqa: E402

builtins.print = _print

__all__ = ['solve']
