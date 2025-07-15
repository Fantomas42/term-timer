import os
from datetime import datetime
from datetime import timezone
from http import HTTPStatus
from wsgiref.simple_server import WSGIRequestHandler

from bottle import TEMPLATE_PATH
from bottle import Bottle
from bottle import abort
from bottle import jinja2_template
from bottle import request
from bottle import static_file

from term_timer.config import CUBE_ORIENTATION
from term_timer.constants import CUBE_SIZES
from term_timer.constants import SECOND
from term_timer.constants import STATIC_DIRECTORY
from term_timer.constants import TEMPLATES_DIRECTORY
from term_timer.formatter import format_duration
from term_timer.formatter import format_grade
from term_timer.formatter import format_time
from term_timer.in_out import load_all_solves
from term_timer.interface.console import console
from term_timer.methods.base import AUF
from term_timer.solve import Solve
from term_timer.stats import Statistics
from term_timer.stats import StatisticsReporter
from term_timer.transform import prettify_moves


def format_delta(delta: int) -> str:
    if delta == 0:
        return ''
    sign = ''
    if delta > 0:
        sign = '+'

    return f'{ sign }{ format_duration(delta) }'


def format_score(score: int, title: str = '') -> str:
    klass = 'good'
    if score < 14:
        klass = 'danger'
    if score < 8:
        klass = 'warning'

    return f'<span class="stat-{ klass }">{ title }{ score:.2f}</span>'


def normalize_value(value, method_applied, metric, name):
    klass = method_applied.normalize_value(metric, name, value, '')

    return f'<span class="metric-{ klass }">{ value }</span>'


def normalize_percent(value, method_applied, metric, name):
    klass = method_applied.normalize_value(metric, name, value, '')

    return f'<span class="metric-{ klass }">{ value:.2f}%</span>'


def reconstruction_step(step):
    move_classes = {
        i: {
            'classes': 'move',
            'move': step['moves_prettified'][i],
        }
        for i in range(len(step['moves_prettified']))
    }

    if step['aufs'][0]:
        for info in move_classes.values():
            if info['move'][0] == AUF:
                info['classes'] += ' pre-auf'
            else:
                break
    if step['aufs'][1]:
        for info in reversed(move_classes.values()):
            if info['move'][0] == AUF:
                info['classes'] += ' post-auf'
            else:
                break

    return ''.join(
        [
            f'<span class="{ info['classes'] }">{ info['move'] }</span>'
            for info in move_classes.values()
        ],
    )


def style_issues(value):
    if not value:
        return ''

    v = ''
    for m in value.split(' '):
        if not m.startswith('['):
            v += f'<span class="move">{ m }</span>'
        else:
            v += f' { m }'

    return v.replace(
        '[red]', '<span class="move deletion">',
    ).replace(
        '[/red]', '</span>',
    ).replace(
        '[green]', '<span class="move addition">',
    ).replace(
        '[/green]', '</span>',
    ).replace(
        '[pause]', '<span class="move pause">',
    ).replace(
        '[/pause]', '</span>',
    ).replace(
        '[reco_pause]', '<span class="move recognition-pause">',
    ).replace(
        '[/reco_pause]', '</span>',
    ).replace(
        '[pre-auf]', '<span class="move pre-auf">',
    ).replace(
        '[/pre-auf]', '</span>',
    ).replace(
        '[post-auf]', '<span class="move post-auf">',
    ).replace(
        '[/post-auf]', '</span>',
    )


class RichHandler(WSGIRequestHandler):

    def log_request(self, code, size):
        if isinstance(code, HTTPStatus):
            code = code.value

        klass = 'green'
        if int(code) > 400:
            klass = 'red'

        message = (
            f'[server][{ self.log_date_time_string() }][/server] '
            f'[{ klass }]{ code!s }[/{ klass }] '
            f'[result]{ self.requestline }[/result] '
            f'[comment]{ size!s }[/comment]'
        )

        console.print(message)


class View:
    template_name = ''

    def get_context(self):
        raise NotImplementedError

    def as_view(self, debug):
        return self.template(
            self.template_name,
            DEBUG=debug,
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
                    'format_score': format_score,
                    'normalize_value': normalize_value,
                    'normalize_percent': normalize_percent,
                    'style_issues': style_issues,
                    'reconstruction_step': reconstruction_step,
                    'prettify': prettify_moves,
                },
            },
            **context,
        )


class Error404View(View):
    template_name = '404.html'

    def __init__(self, error):
        self.error = error

    def get_context(self):
        return {
            'error': self.error,
            'message': self.error.body,
        }


class Error500View(View):
    template_name = '500.html'

    def __init__(self, error):
        self.error = error

    def get_context(self):
        return {
            'error': self.error,
            'message': self.error.body,
            'exception': self.error.exception,
            'traceback': self.error.traceback,
        }


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
            'punchcard': self.compute_punchcard(),
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

    def compute_punchcard(self):
        punchcard = {}
        for solve in self.stats.stack:
            dt = solve.datetime.astimezone()
            year = dt.strftime('%Y')
            date = dt.strftime('%Y-%m-%d')

            punchcard.setdefault(year, {}).setdefault(date, 0)
            punchcard[year][date] += 1

        return punchcard


class SolveView(View):
    template_name = 'solve.html'

    def __init__(self, cube, session, solve, method):
        self.cube = cube
        self.session = session

        self.solves = load_all_solves(
            cube,
            [] if session == 'all' else [session],
            [], '',
        )

        self.solve_id = solve
        try:
            self.solve = self.solves[solve - 1]
        except IndexError:
            abort(404, 'Invalid solve ID')

        if method:
            self.solve.method_name = method

    def get_context(self):
        tps = []
        steps = []
        scatter = []
        recognitions = []

        ranks = sorted([s.final_time for s in self.solves])
        rank = ranks.index(self.solve.final_time) + 1

        if self.solve.advanced:
            scatter = [
                {
                    'y': self.solve.move_times[i][1] / 1000,
                    'x': i + 1,
                }
                for i in range(len(self.solve.move_times))
            ]

            for s in self.solve.method_applied.summary:
                if s['type'] not in {'skipped', 'virtual'}:
                    index = s['index'][-1] + 1
                    steps.append(
                        {
                            'x': index,
                            'y': self.solve.move_times[index - 1][1] / 1000,
                            'label': s['name'],
                        },
                    )
                    tps.append(
                        {
                            'tps': Solve.compute_tps(s['qtm'], s['total']),
                            'etps': Solve.compute_tps(s['qtm'], s['execution']),
                            'label': s['name'],
                        },
                    )
                    recognitions.append(
                        {
                            'recognition': s['recognition'] / SECOND,
                            'execution': s['execution'] / SECOND,
                            'label': s['name'],
                        },
                    )

        return {
            'cube': self.cube,
            'session': self.session,
            'solve': self.solve,
            'solve_id': self.solve_id,
            'solves': self.solves,
            'scatter': scatter,
            'steps': steps,
            'tps': tps,
            'recognitions': recognitions,
            'cube_orientation': CUBE_ORIENTATION,
            'reconstruction': self.solve.method_text_builder(multiple=False),
            'timing': self.solve.timeline_inputs,
            'rank': rank,
        }


class Server:

    def run_server(self, host, port, debug):
        TEMPLATE_PATH.insert(0, TEMPLATES_DIRECTORY)

        app = self.create_app(debug)

        if not os.getenv('BOTTLE_CHILD'):
            console.print(
                '[server]Term Timer server is listening on [/server]'
                f'[localhost][link=http://{ host }:{ port }/]'
                f'http://{ host }:{ port }/[/link][/localhost]',
            )
            console.print('Hit Ctrl-C to quit.', style='comment')

        app.run(
            host=host,
            port=port,
            quiet=True,
            reloader=debug,
            debug=debug,
            server='wsgiref',
            handler_class=RichHandler,
        )

    def create_app(self, debug):
        app = Bottle()

        @app.route('/')
        def index():
            return IndexView().as_view(debug)

        @app.route('/<cube:int>/<session:path>/<solve:int>/')
        def solve(cube, session, solve):
            return SolveView(
                cube, session, solve,
                request.query.m or '',
            ).as_view(debug)

        @app.route('/<cube:int>/<session:path>/')
        def session(cube, session):
            return SessionView(
                cube, session,
            ).as_view(debug)

        @app.route('/static/<filepath:path>')
        def serve_static(filepath):
            return static_file(filepath, root=STATIC_DIRECTORY)

        @app.error(404)
        def error404(error):
            return Error404View(error).as_view(debug)

        @app.error(500)
        def error500(error):
            return Error500View(error).as_view(debug)

        return app
