import builtins

_print = builtins.print
builtins.print = lambda *x, **y: None  # noqa: ARG005

from twophase import solver  # noqa: E402 F401

builtins.print = _print
