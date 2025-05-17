from datetime import datetime
from datetime import timezone

from bottle import Bottle
from bottle import jinja2_template
from bottle import TEMPLATE_PATH
from bottle import static_file

from term_timer.constants import CUBE_SIZES
from term_timer.constants import SECOND
from term_timer.constants import STATIC_DIRECTORY
from term_timer.constants import TEMPLATES_DIRECTORY
from term_timer.formatter import format_duration
from term_timer.formatter import format_grade
from term_timer.formatter import format_time
from term_timer.in_out import load_all_solves
from term_timer.stats import Statistics
from term_timer.stats import StatisticsReporter


def format_delta(delta: int) -> str:
    if delta == 0:
        return ''
    sign = ''
    if delta > 0:
        sign = '+'

    return f'{ sign }{ format_duration(delta) }'


class View:
    template_name = ''

    def get_context(self):
        raise NotImplementedError

    def as_view(self):
        return self.template(
            self.template_name,
            **self.get_context(),
        )

    def template(self, template_name, **context):
        context['now'] = datetime.now(tz=timezone.utc)  # noqa UP017

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


class IndexView(View):
    template_name = 'index.html'

    def get_context(self):
        sessions = {}
        for cube in CUBE_SIZES:
            solves = load_all_solves(cube, [], [], '')
            sessions[cube] = {}
            for solve in solves:
                sessions[cube].setdefault(
                    solve.session, {},
                ).setdefault(
                    'solves', [],
                ).append(
                    solve,
                )

        for cube in CUBE_SIZES:
            values = sessions[cube].values()
            for info in values:
                info['stats'] = Statistics(info['solves'])

            if len(values) > 1:
                all_solves = []
                for info in values:
                    all_solves.extend(info['solves'])
                sessions[cube]['all'] = {
                    'solves': all_solves,
                    'stats': Statistics(all_solves),
                }

            sessions[cube] = dict(
                sorted(
                    sessions[cube].items(),
                    key=lambda item: len(item[1]['solves']),
                    reverse=True,
                ),
            )

        return {
            'sessions': sessions,
        }


class SessionView(View):
    template_name = 'session.html'

    def __init__(self, cube, session):
        self.cube = cube
        self.session = session

        self.stats = StatisticsReporter(
            cube,
            load_all_solves(
                cube,
                [] if session == 'all' else [session],
                [], '',
            ),
        )

    def get_context(self):
        return {
            'cube': self.cube,
            'session': self.session,
            'stats': self.stats,
            'sessions': self.compute_sessions(),
            'cfop': self.stats.compute_cfop(),
            'trend': self.compute_trend(),
            'distribution': self.compute_distribution(),
        }

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


class SolveView(View):
    template_name = 'solve.html'

    def __init__(self, cube, session, solve):
        self.cube = cube
        self.session = session

        self.solves = load_all_solves(
            cube,
            [] if session == 'all' else [session],
            [], '',
        )

        self.solve_id = solve
        self.solve = self.solves[solve - 1]

    def get_context(self):
        return {
            'cube': self.cube,
            'session': self.session,
            'solve': self.solve,
            'solve_id': self.solve_id,
            'solves': self.solves,
        }


class Server:

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

        @app.route('/')
        def index():
            return IndexView().as_view()

        @app.route('/<cube:int>/<session:path>/<solve:int>/')
        def solve(cube, session, solve):
            return SolveView(cube, session, solve).as_view()

        @app.route('/<cube:int>/<session:path>/')
        def session(cube, session):
            return SessionView(cube, session).as_view()

        @app.route('/static/<filepath:path>')
        def serve_static(filepath):
            return static_file(filepath, root=STATIC_DIRECTORY)

        return app
