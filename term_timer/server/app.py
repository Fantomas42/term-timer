import gc
import os
import re
from datetime import datetime
from datetime import timezone
from http import HTTPStatus
from wsgiref.simple_server import WSGIRequestHandler

from bottle import TEMPLATE_PATH
from bottle import Bottle
from bottle import abort
from bottle import jinja2_template
from bottle import redirect
from bottle import request
from bottle import static_file
from cubing_algs.transform.optimize import optimize_double_moves
from cubing_algs.transform.pause import pause_moves
from cubing_algs.transform.size import compress_moves
from cubing_algs.transform.timing import untime_moves

from term_timer.aggregator import SolvesMethodAggregator
from term_timer.config import CUBE_METHOD
from term_timer.config import CUBE_ORIENTATION
from term_timer.constants import CUBE_SIZES
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import PAUSE_FACTOR
from term_timer.constants import SECOND
from term_timer.constants import STATIC_DIRECTORY
from term_timer.constants import TEMPLATES_DIRECTORY
from term_timer.formatter import format_alg_aufs
from term_timer.formatter import format_alg_diff
from term_timer.formatter import format_alg_moves
from term_timer.formatter import format_alg_pauses
from term_timer.formatter import format_alg_triggers
from term_timer.formatter import format_duration
from term_timer.formatter import format_grade
from term_timer.formatter import format_time
from term_timer.in_out import load_all_solves
from term_timer.in_out import save_solves
from term_timer.interface.console import console
from term_timer.methods.base import get_step_config
from term_timer.solve import Solve
from term_timer.stats import Statistics
from term_timer.stats import StatisticsReporter
from term_timer.transform import humanize_moves
from term_timer.transform import prettify_moves

SPAN_REGEX = re.compile(r'(<span[^>]*>.*?</span>)')
BLOCK_REGEX = re.compile(r'\[([\w-]+)\](.*?)\[/([\w-]+)\]')

CLASS_CONVERTION = {
    'red': 'deletion',
    'green': 'addition',
}

LEGENDS = {
    'pair-ie': 'Pair insertion/extraction',
    'sexy-move': 'Sexy Move',
    'pre-auf': 'Pre-AUF',
    'post-auf': 'Post-AUF',
    'reco-pause': 'Recognition pause',
}


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


def format_line(value):
    if not value:
        return ''

    def replacer(matchobj):
        moves = matchobj.group(2)
        markup = matchobj.group(1)
        legend = LEGENDS.get(markup, markup.title())

        klass = 'move'
        move_name = ''
        if len(moves.split(' ')) > 1:
            klass = 'trigger'
        else:
            move_name = moves.lower().replace(
                "'", '',
            ).replace(
                '2', '',
            )

        return (
            f'<span class="{ klass } { markup } { move_name }"'
            f' title="{ legend }">{ moves }</span>'
        )

    result = BLOCK_REGEX.sub(replacer, value)

    processed_parts = []
    for part in SPAN_REGEX.split(result):
        if part.startswith('<span'):
            processed_parts.append(part)
        else:
            moves = part.split()
            for move in moves:
                if move.strip():
                    processed_parts.append(
                        f'<span class="move">{ move }</span>',
                    )

    return ' '.join(processed_parts)


def parse_case_name(value, step):
    try:
        code, name = value.split(' ', 1)
    except ValueError:
        if step == 'PLL':
            return value, f'{ step } { value }'
        return value, ''
    else:
        return code, name


def normalize_value(value, method_applied, metric, name):
    klass = method_applied.normalize_value(metric, name, value, '')

    return f'<span class="metric-{ klass }">{ value }</span>'


def normalize_percent(value, method_applied, metric, name):
    klass = method_applied.normalize_value(metric, name, value, '')

    return f'<span class="metric-{ klass }">{ value:.2f}%</span>'


def reconstruction_step(step):
    algorithm = str(step['moves_prettified'])

    algorithm = format_alg_triggers(
        format_alg_moves(
            format_alg_aufs(
                algorithm,
                *step['aufs'],
            ),
        ),
        get_step_config(step['name'], 'triggers', []),
    )

    return format_line(algorithm)


def reconstruction_overheads(step, solve):
    source, compressed = solve.missed_moves_pair(
        step['moves_humanized'],
    )
    source_paused = source.transform(
        untime_moves,
        optimize_double_moves,
    )
    compressed_paused = compressed.transform(
        untime_moves,
        optimize_double_moves,
    )

    algo = format_alg_triggers(
        format_alg_moves(
            format_alg_aufs(
                format_alg_diff(
                    source_paused,
                    compressed_paused,
                ),
                *step['aufs'],
            ),
        ),
        get_step_config(step['name'], 'triggers', []),
    )

    return format_line(algo)


def reconstruction_pauses(step, solve):
    source_paused = step['moves_humanized'].transform(
        pause_moves(
            solve.move_speed / MS_TO_NS_FACTOR,
            PAUSE_FACTOR,
            multiple=True,
        ),
        untime_moves,
        optimize_double_moves,
    )

    source_paused = format_alg_pauses(
        format_alg_triggers(
            format_alg_moves(
                format_alg_aufs(
                    str(source_paused),
                    *step['aufs'],
                ),
            ),
            get_step_config(step['name'], 'triggers', []),
        ),
        solve, step, multiple=True,
    )

    return format_line(source_paused)


def optimized_step(step):
    optimizers = []

    if not step['cases'] or 'SKIP' not in step['cases'][0]:
        optimizers = get_step_config(step['name'], 'optimizers', [])

    algorithm = humanize_moves(
        step['moves_reoriented'].transform(*optimizers),
    ).transform(
        compress_moves,
        untime_moves,
    )

    algorithm_string = format_alg_triggers(
        format_alg_moves(
            format_alg_aufs(
                str(algorithm),
                *step['aufs'],
            ),
        ),
        get_step_config(step['name'], 'triggers', []),
    )

    return format_line(algorithm_string), algorithm


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
        context = self.get_context()

        content = self.template(
            self.template_name,
            DEBUG=debug,
            **context,
        )
        gc.collect()

        return content

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
                    'format_line': format_line,
                    'parse_case_name': parse_case_name,
                    'normalize_value': normalize_value,
                    'normalize_percent': normalize_percent,
                    'reconstruction_step': reconstruction_step,
                    'reconstruction_overheads': reconstruction_overheads,
                    'reconstruction_pauses': reconstruction_pauses,
                    'optimized_step': optimized_step,
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


class SessionListView(View):
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


class SessionDetailView(View):
    template_name = 'session.html'

    def __init__(self, cube, session, method_name, step, case_uid):
        self.cube = cube
        self.session = session

        solves = load_all_solves(
            cube,
            [] if session == 'all' else [session],
            [], '',
        )
        if not method_name:
            method_name = CUBE_METHOD

        self.step = step.strip().lower()
        self.case_uid = case_uid.strip().lower()
        self.method_name = method_name.strip().lower()

        self.method_aggregation = SolvesMethodAggregator(
            self.method_name, solves, full=True,
        )

        solves = self.method_aggregation.results['stack']

        if self.step and self.case_uid:
            filtered_solves = []

            for solve in solves:
                if not solve.advanced:
                    continue

                for s_step in reversed(solve.method_applied.summary):
                    if s_step['name'].lower() == self.step:
                        if s_step['cases']:
                            step_case = s_step['cases'][0].split(' ')[0].lower()
                            if step_case == self.case_uid:
                                filtered_solves.append(solve)
                        break

            solves = filtered_solves

        if not solves:
            abort(404, 'No solve to display')

        self.stats = StatisticsReporter(
            cube, solves,
        )

    def get_context(self):
        return {
            'cube': self.cube,
            'session': self.session,
            'stats': self.stats,
            'sessions': self.compute_sessions(),
            'trend': self.compute_trend(),
            'distribution': self.compute_distribution(),
            'punchcard': self.compute_punchcard(),
            'step': self.step,
            'case_uid': self.case_uid,
            'method_aggregation': self.method_aggregation,
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


class SolveDetailView(View):
    template_name = 'solve.html'

    def __init__(self, cube, session, solve, method_name):
        self.cube = cube
        self.session = session

        self.solves = load_all_solves(
            cube,
            [] if session == 'all' else [session],
            [], '',
        )

        self.solve_id = solve
        self.solve_index = solve - 1
        try:
            self.solve = self.solves[self.solve_index]
        except IndexError:
            abort(404, 'Invalid solve ID')

        method_name = method_name.strip().lower()
        if method_name:
            self.solve.method_name = method_name

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

        reconstruction_text = self.solve.method_text_builder(
            multiple=False,
        )
        step_index = {}
        index = 0
        for line in reconstruction_text.split('\n'):
            if not line:
                continue
            moves, comment = line.split('//')
            name = comment
            if 'Reco' in name:
                name = name.split('Reco')[0]
            if '(' in name:
                name = name.split('(')[0]
            name = name.strip()
            step_index[name] = index
            if ' ' in name:
                name = name.split(' ')[0]
                if name not in step_index:
                    step_index[name] = index

            index += len(moves.strip().split(' '))

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
            'reconstruction_text': reconstruction_text,
            'reconstruction_timing': self.solve.reconstruction_steps_timing,
            'reconstruction_index': step_index,
            'rank': rank,
        }


class SolveUpdateView:

    def __init__(self, cube, session, solve_id, flag):
        self.cube = cube
        self.session = session
        self.solve_id = solve_id
        self.flag = flag

        self.solves = load_all_solves(
            cube,
            [] if session == 'all' else [session],
            [], '',
        )

        self.solve_index = solve_id - 1
        try:
            self.solve = self.solves[self.solve_index]
        except IndexError:
            abort(404, 'Invalid solve ID')

        self.solves[self.solve_index].flag = flag
        save_solves(cube, session, self.solves)

        redirect(f'/{ cube }/{ session }/{ solve_id }/')


class SolveDeleteView:

    def __init__(self, cube, session, solve_id):
        self.cube = cube
        self.session = session
        self.solve_id = solve_id

        self.solves = load_all_solves(
            cube,
            [] if session == 'all' else [session],
            [], '',
        )

        self.solve_index = solve_id - 1
        try:
            self.solve = self.solves[self.solve_index]
        except IndexError:
            abort(404, 'Invalid solve ID')

        self.solves.pop(self.solve_index)
        save_solves(cube, session, self.solves)

        redirect(f'/{ cube }/{ session }/')


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
        def session_list():
            return SessionListView().as_view(debug)

        @app.route('/<cube:int>/<session:path>/<solve:int>/update/',
                   method='POST')
        def solve_update(cube, session, solve):
            return SolveUpdateView(
                cube, session, solve,
                request.POST.flag,
            ).as_view(debug)

        @app.route('/<cube:int>/<session:path>/<solve:int>/delete/',
                   method='POST')
        def solve_delete(cube, session, solve):
            return SolveDeleteView(
                cube, session, solve,
            ).as_view(debug)

        @app.route('/<cube:int>/<session:path>/<solve:int>/')
        def solve_detail(cube, session, solve):
            return SolveDetailView(
                cube, session, solve,
                request.GET.m or '',
            ).as_view(debug)

        @app.route('/<cube:int>/<session:path>/')
        def session_detail(cube, session):
            return SessionDetailView(
                cube, session,
                request.GET.m or '',
                request.GET.step or '',
                request.GET.case_uid or '',
            ).as_view(debug)

        @app.route('/static/<filepath:path>')
        def static_serve(filepath):
            return static_file(filepath, root=STATIC_DIRECTORY)

        @app.error(404)
        def error_404(error):
            return Error404View(error).as_view(debug)

        @app.error(500)
        def error_500(error):
            return Error500View(error).as_view(debug)

        return app
