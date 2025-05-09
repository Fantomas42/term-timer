from datetime import datetime
from datetime import timezone

from jinja2 import Environment
from jinja2 import FileSystemLoader

from term_timer.console import console
from term_timer.constants import EXPORT_DIRECTORY
from term_timer.constants import TEMPLATES_DIRECTORY
from term_timer.constants import SECOND
from term_timer.formatter import format_duration
from term_timer.formatter import format_grade
from term_timer.formatter import format_time

TEMPLATES = Environment(
    loader=FileSystemLoader(TEMPLATES_DIRECTORY),
    lstrip_blocks=True,
    trim_blocks=True,
    autoescape=True,
)


def format_delta(delta: int) -> str:
    if delta == 0:
        return ''
    sign = ''
    if delta > 0:
        sign = '+'

    return f'{ sign }{ format_duration(delta) }'


TEMPLATES.filters['format_delta'] = format_delta
TEMPLATES.filters['format_duration'] = format_duration
TEMPLATES.filters['format_grade'] = format_grade
TEMPLATES.filters['format_time'] = format_time


class Exporter:

    def compute_sessions(self):
        sessions = {}
        for solve in self.stats.stack:
            sessions.setdefault(solve.session, 0)
            sessions[solve.session] += 1

        return sessions

    def compute_trend(self):
        ao5s = []
        ao12s = []
        ao100s = []
        ao1000s = []
        times = []
        indices = []

        stack_time = list(self.stats.stack_time)
        for i, time in enumerate(stack_time):
            seconds = time / SECOND
            times.append(seconds)
            indices.append(i + 1)

            ao5 = self.stats.ao(5, stack_time[:i + 1])
            ao12 = self.stats.ao(12, stack_time[:i + 1])
            ao100 = self.stats.ao(100, stack_time[:i + 1])
            ao1000 = self.stats.ao(1000, stack_time[:i + 1])

            ao5s.append(ao5 / SECOND if ao5 > 0 else None)
            ao12s.append(ao12 / SECOND if ao12 > 0 else None)
            ao100s.append(ao100 / SECOND if ao100 > 0 else None)
            ao1000s.append(ao1000 / SECOND if ao1000 > 0 else None)

        return {
            'indices': indices,
            'times': times,
            'ao5s': ao5s,
            'ao12s': ao12s,
            'ao100s': ao100s,
            'ao1000s': ao1000s,
        }

    def compute_distribution(self):
        dist_labels = []
        dist_counts = []
        for count, edge in self.stats.repartition:
            dist_labels.append(f'{ edge }s')
            dist_counts.append(int(count))

        return {
            'labels': dist_labels,
            'counts': dist_counts,
        }

    def get_context(self):
        return {
            'now': datetime.now(tz=timezone.utc),  # noqa UP017
            'stats': self.stats,
            'sessions': self.compute_sessions(),
            'cfop': self.stats.compute_cfop(),
            'trend': self.compute_trend(),
            'distribution': self.compute_distribution(),
        }

    def export_html(self, stats):
        self.stats = stats

        timestamp = datetime.now(
            tz=timezone.utc,  # noqa: UP017
        ).strftime('%Y%m%d_%H%M%S')

        output_path = (
            EXPORT_DIRECTORY /
            f'{ stats.cube_name }_{ timestamp }.html'
        )

        template = TEMPLATES.get_template('export.html')
        context = self.get_context()

        html = template.render(**context)

        with output_path.open('w+', encoding='utf-8') as fd:
            fd.write(html)

        console.print(
            f'[success]HTML report generated at :[/success] { output_path }',
        )
