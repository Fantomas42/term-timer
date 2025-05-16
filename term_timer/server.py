from datetime import datetime
from datetime import timezone

import bottle
from bottle import Bottle
from bottle import jinja2_template
from bottle import TEMPLATE_PATH
from bottle import static_file

from term_timer.constants import SECOND
from term_timer.constants import STATIC_DIRECTORY
from term_timer.constants import TEMPLATES_DIRECTORY
from term_timer.formatter import format_duration
from term_timer.formatter import format_grade
from term_timer.formatter import format_time
from term_timer.in_out import list_sessions
from term_timer.in_out import load_all_solves
from term_timer.stats import StatisticsReporter


def format_delta(delta: int) -> str:
    if delta == 0:
        return ''
    sign = ''
    if delta > 0:
        sign = '+'

    return f'{ sign }{ format_duration(delta) }'


class Server:

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
            indices.append(str(i + 1))

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

    def get_export_context(self):
        self.stats = StatisticsReporter(
            3,
            load_all_solves(
                3, [], [], '',
            ),
        )

        return {
            'stats': self.stats,
            'sessions': self.compute_sessions(),
            'cfop': self.stats.compute_cfop(),
            'trend': self.compute_trend(),
            'distribution': self.compute_distribution(),
        }

    def get_index_context(self):
        all_sessions = list_sessions()

        return {
            'now': datetime.now(tz=timezone.utc),  # noqa UP017
            'sessions': all_sessions,
        }

    def template(self, template_name, **context):
        return jinja2_template(
            template_name,
            template_settings={
                'filters': {
                    'format_delta': format_delta,
                    'format_duration': format_duration,
                    'format_grade': format_grade,
                    'format_time': format_time,
                },
            },
            **context,
        )

    def run_server(self, host, port, debug):
        TEMPLATE_PATH.insert(0, TEMPLATES_DIRECTORY)

        app = self.create_app()

        app.run(
            host=host,
            port=port,
            debug=debug,
            reloader=debug,
        )

    def create_app(self):
        app = Bottle()

        def context_processors():
            bottle.BaseTemplate.defaults['now'] = datetime.now(tz=timezone.utc)  # noqa UP017

        app.add_hook(
            'before_request',
            context_processors,
        )

        @app.route('/')
        def index():
            return self.template(
                'index.html',
                **self.get_index_context(),
            )

        @app.route('/export/')
        def export():
            return self.template(
                'export.html',
                **self.get_export_context(),
            )

        @app.route('/static/<filepath:path>')
        def serve_static(filepath):
            return static_file(filepath, root=STATIC_DIRECTORY)

        return app
