from term_timer.methods.cfop import CF4OPAnalyser
from term_timer.methods.cfop import CFOPAnalyser
from term_timer.methods.lbl import LBLAnalyser
from term_timer.methods.raw import RawAnalyser

METHOD_ANALYSERS = {
    'raw': RawAnalyser,
    'lbl': LBLAnalyser,
    'cfop': CFOPAnalyser,
    'cf4op': CF4OPAnalyser,
}


def get_method_analyser(method_name):
    return METHOD_ANALYSERS.get(method_name, CFOPAnalyser)
