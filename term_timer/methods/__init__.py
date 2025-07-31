from term_timer.methods.cfop import CF4OPAnalyser
from term_timer.methods.cfop import CFOPAnalyser
from term_timer.methods.lbl import LBLAnalyser
from term_timer.methods.raw import RawAnalyser

METHOD_ANALYSERS = {
    'cfop': CFOPAnalyser,
    'cf4op': CF4OPAnalyser,
    'lbl': LBLAnalyser,
    'raw': RawAnalyser,
}


def get_method_analyser(method_name):
    return METHOD_ANALYSERS.get(method_name, CF4OPAnalyser)
