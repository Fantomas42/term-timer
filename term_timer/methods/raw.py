from term_timer.methods.base import Analyser


class RawAnalyser(Analyser):
    name = 'Raw'
    step_list = ('RAW',)

    def compute_progress(self, *args, **kwargs):  # noqa: ARG002
        return 0, []
