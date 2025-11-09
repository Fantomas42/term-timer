"""Solving method analysis modules for CFOP, LBL, and other methods."""

from typing import Final

from term_timer.methods.base import Analyser
from term_timer.methods.cfop import CF4OPAnalyser
from term_timer.methods.cfop import CFOPAnalyser
from term_timer.methods.lbl import LBLAnalyser
from term_timer.methods.raw import RawAnalyser

METHOD_ANALYSERS: Final[dict[str, type[Analyser]]] = {
    'raw': RawAnalyser,
    'lbl': LBLAnalyser,
    'cfop': CFOPAnalyser,
    'cf4op': CF4OPAnalyser,
}


def get_method_analyser(method_name: str) -> type[Analyser]:
    """
    Get method analyser class for specified method name.

    Returns:
        Analyser class for the method, defaulting to CFOPAnalyser.

    """
    return METHOD_ANALYSERS.get(method_name, CFOPAnalyser)
