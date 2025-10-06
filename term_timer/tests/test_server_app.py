import contextlib
import unittest
from http import HTTPStatus
from unittest.mock import Mock
from unittest.mock import patch

from bottle import Bottle
from bottle import HTTPError

from term_timer.server.app import BLOCK_REGEX
from term_timer.server.app import CLASS_CONVERTION
from term_timer.server.app import LEGENDS
from term_timer.server.app import SPAN_REGEX
from term_timer.server.app import Error404View
from term_timer.server.app import Error500View
from term_timer.server.app import RichHandler
from term_timer.server.app import Server
from term_timer.server.app import SessionDetailView
from term_timer.server.app import SessionListView
from term_timer.server.app import SolveDeleteView
from term_timer.server.app import SolveDetailView
from term_timer.server.app import SolveUpdateView
from term_timer.server.app import View
from term_timer.server.app import format_delta
from term_timer.server.app import format_line
from term_timer.server.app import format_score
from term_timer.server.app import normalize_percent
from term_timer.server.app import normalize_value
from term_timer.server.app import parse_case_name


class TestConstants(unittest.TestCase):
    def test_class_conversion_constants(self) -> None:
        self.assertEqual(CLASS_CONVERTION['red'], 'deletion')
        self.assertEqual(CLASS_CONVERTION['green'], 'addition')

    def test_legends_constants(self) -> None:
        expected_legends = {
            'pair-ie': 'Pair insertion/extraction',
            'sexy-move': 'Sexy Move',
            'pre-auf': 'Pre-AUF',
            'post-auf': 'Post-AUF',
            'reco-pause': 'Recognition pause',
        }
        self.assertEqual(LEGENDS, expected_legends)

    def test_regex_patterns(self) -> None:
        # Test SPAN_REGEX matches span tags
        test_html = '<span class="test">content</span>'
        matches = SPAN_REGEX.findall(test_html)
        self.assertEqual(matches, ['<span class="test">content</span>'])

        # Test BLOCK_REGEX matches block patterns
        test_block = '[pre-auf]R U[/pre-auf]'
        matches = BLOCK_REGEX.findall(test_block)
        self.assertEqual(matches, [('pre-auf', 'R U', 'pre-auf')])


class TestFormatDelta(unittest.TestCase):
    def test_format_delta_zero(self) -> None:
        result = format_delta(0)
        self.assertEqual(result, '')

    def test_format_delta_positive(self) -> None:
        result = format_delta(1500000000)  # 1.5 seconds
        self.assertEqual(result, '+1.50')

    def test_format_delta_negative(self) -> None:
        result = format_delta(-2500000000)  # -2.5 seconds
        self.assertEqual(result, '-2.50')

    def test_format_delta_small_positive(self) -> None:
        result = format_delta(100000000)  # 0.1 seconds
        self.assertEqual(result, '+0.10')


class TestFormatScore(unittest.TestCase):
    def test_format_score_good(self) -> None:
        result = format_score(15, 'Test: ')
        expected = '<span class="stat-good">Test: 15.00</span>'
        self.assertEqual(result, expected)

    def test_format_score_danger(self) -> None:
        result = format_score(10, 'Score: ')
        expected = '<span class="stat-danger">Score: 10.00</span>'
        self.assertEqual(result, expected)

    def test_format_score_warning(self) -> None:
        result = format_score(5, 'Low: ')
        expected = '<span class="stat-warning">Low: 5.00</span>'
        self.assertEqual(result, expected)

    def test_format_score_no_title(self) -> None:
        result = format_score(20)
        expected = '<span class="stat-good">20.00</span>'
        self.assertEqual(result, expected)

    def test_format_score_boundary_values(self) -> None:
        # Test exact boundary values
        result = format_score(14)
        self.assertIn('stat-good', result)

        result = format_score(13.9)
        self.assertIn('stat-danger', result)

        result = format_score(8)
        self.assertIn('stat-danger', result)

        result = format_score(7.9)
        self.assertIn('stat-warning', result)


class TestFormatLine(unittest.TestCase):
    def test_format_line_empty_value(self) -> None:
        result = format_line('')
        self.assertEqual(result, '')

    def test_format_line_simple_moves(self) -> None:
        result = format_line("R U R'")
        expected = (
            '<span class="move">R</span> '
            '<span class="move">U</span> '
            '<span class="move">R\'</span>'
        )
        self.assertEqual(result, expected)

    def test_format_line_with_block_pattern(self) -> None:
        result = format_line('[pre-auf]R U[/pre-auf]')
        self.assertIn('class="trigger pre-auf ', result)
        self.assertIn('title="Pre-AUF"', result)

    def test_format_line_single_move_in_block(self) -> None:
        result = format_line('[sexy-move]R[/sexy-move]')
        self.assertIn('class="move sexy-move r"', result)
        self.assertIn('title="Sexy Move"', result)

    def test_format_line_mixed_content(self) -> None:
        result = format_line("R [pre-auf]U R'[/pre-auf] D")
        # Should contain both regular moves and block-formatted moves
        self.assertIn('<span class="move">R</span>', result)
        self.assertIn('<span class="move">D</span>', result)
        self.assertIn('trigger pre-auf', result)

    def test_format_line_unknown_markup(self) -> None:
        result = format_line('[unknown-markup]R U[/unknown-markup]')
        self.assertIn('title="Unknown-Markup"', result)

    def test_format_line_move_name_normalization(self) -> None:
        # Test that move names are normalized (lowercase, no quotes/numbers)
        result = format_line("[test]R'2[/test]")
        self.assertIn('class="move test r"', result)


class TestParseCaseName(unittest.TestCase):
    def test_parse_case_name_with_code_and_name(self) -> None:
        code, name, step_type = parse_case_name('OLL01 T-Shape', 'OLL')
        self.assertEqual(code, 'OLL01')
        self.assertEqual(name, 'T-Shape')
        self.assertEqual(step_type, 'OLL')

    def test_parse_case_name_pll_no_space(self) -> None:
        code, name, step_type = parse_case_name('Aa', 'PLL')
        self.assertEqual(code, 'Aa')
        self.assertEqual(name, 'PLL Aa')
        self.assertEqual(step_type, 'PLL')

    def test_parse_case_name_f2l_no_space(self) -> None:
        code, name, step_type = parse_case_name('1', 'F2L')
        self.assertEqual(code, '1')
        self.assertEqual(name, 'F2L 1')
        self.assertEqual(step_type, 'F2L')

    def test_parse_case_name_f2l_substep(self) -> None:
        code, name, step_type = parse_case_name('2', 'F2L-1')
        self.assertEqual(code, '2')
        self.assertEqual(name, 'F2L 2')
        self.assertEqual(step_type, 'F2L')

    def test_parse_case_name_other_step(self) -> None:
        code, name, step_type = parse_case_name('test', 'Cross')
        self.assertEqual(code, 'test')
        self.assertEqual(name, '')
        self.assertEqual(step_type, '')


class TestNormalizeValue(unittest.TestCase):
    def test_normalize_value(self) -> None:
        mock_method_applied = Mock()
        mock_method_applied.normalize_value.return_value = 'good'

        result = normalize_value(15.5, mock_method_applied, 'time', 'test')
        expected = '<span class="metric-good">15.5</span>'
        self.assertEqual(result, expected)

        mock_method_applied.normalize_value.assert_called_once_with(
            'time', 'test', 15.5, '',
        )


class TestNormalizePercent(unittest.TestCase):
    def test_normalize_percent(self) -> None:
        mock_method_applied = Mock()
        mock_method_applied.normalize_value.return_value = 'warning'

        result = normalize_percent(
            75.234, mock_method_applied, 'accuracy', 'test',
        )
        expected = '<span class="metric-warning">75.23%</span>'
        self.assertEqual(result, expected)

        mock_method_applied.normalize_value.assert_called_once_with(
            'accuracy', 'test', 75.234, '',
        )


class TestRichHandler(unittest.TestCase):
    def setUp(self) -> None:
        # Create a mock request, client_address, and server for RichHandler
        self.handler = RichHandler.__new__(RichHandler)
        self.handler.requestline = ''
        self.handler.log_date_time_string = Mock(
            return_value='01/Jan/2023 12:00:00',
        )

    @patch('term_timer.server.app.console')
    def test_log_request_success_code(self, mock_console) -> None:
        self.handler.requestline = 'GET /test HTTP/1.1'
        self.handler.log_request(200, 1024)

        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0][0]
        self.assertIn('[green]200[/green]', call_args)
        self.assertIn('GET /test HTTP/1.1', call_args)
        self.assertIn('1024', call_args)

    @patch('term_timer.server.app.console')
    def test_log_request_error_code(self, mock_console) -> None:
        self.handler.requestline = 'GET /error HTTP/1.1'
        self.handler.log_request(404, 512)

        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0][0]
        self.assertIn('[red]404[/red]', call_args)

    @patch('term_timer.server.app.console')
    def test_log_request_http_status_object(self, mock_console) -> None:
        self.handler.requestline = 'GET /status HTTP/1.1'
        self.handler.log_request(HTTPStatus.OK, 256)

        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0][0]
        self.assertIn('[green]200[/green]', call_args)


class TestView(unittest.TestCase):
    def test_view_abstract_get_context(self) -> None:
        view = View()
        with self.assertRaises(NotImplementedError):
            view.get_context()

    @patch('term_timer.server.app.jinja2_template')
    @patch('term_timer.server.app.gc.collect')
    def test_view_as_view(self, mock_gc_collect, mock_jinja2_template) -> None:
        mock_jinja2_template.return_value = 'rendered_content'

        class TestView(View):
            template_name = 'test.html'

            def get_context(self):
                return {'test': 'value'}

        view = TestView()
        result = view.as_view(debug=True)

        self.assertEqual(result, 'rendered_content')
        mock_gc_collect.assert_called_once()
        mock_jinja2_template.assert_called_once()

    @patch('term_timer.server.app.jinja2_template')
    def test_view_template_context(self, mock_jinja2_template) -> None:
        mock_jinja2_template.return_value = 'template_result'

        view = View()
        view.template('test.html', custom='value')

        # Check that datetime.now is added to context
        call_args = mock_jinja2_template.call_args
        self.assertIn('now', call_args[1])
        self.assertIn('custom', call_args[1])
        self.assertEqual(call_args[1]['custom'], 'value')

        # Verify template filters are set up
        template_settings = call_args[1]['template_settings']
        expected_filters = [
            'format_delta',
            'format_duration',
            'format_grade',
            'format_time',
            'format_score',
            'format_line',
            'parse_case_name',
            'normalize_value',
            'normalize_percent',
            'reconstruction_step',
            'reconstruction_overheads',
            'reconstruction_pauses',
            'optimized_step',
            'prettify',
        ]
        for filter_name in expected_filters:
            self.assertIn(filter_name, template_settings['filters'])


class TestError404View(unittest.TestCase):
    def test_error404_view_get_context(self) -> None:
        mock_error = Mock()
        mock_error.body = 'Page not found'
        view = Error404View(mock_error)

        context = view.get_context()

        expected = {
            'error': mock_error,
            'message': 'Page not found',
        }
        self.assertEqual(context, expected)

    def test_error404_view_template_name(self) -> None:
        view = Error404View(Mock())
        self.assertEqual(view.template_name, '404.html')


class TestError500View(unittest.TestCase):
    def test_error500_view_get_context(self) -> None:
        mock_error = Mock()
        mock_error.body = 'Internal server error'
        mock_error.exception = Exception('Test exception')
        mock_error.traceback = 'Test traceback'
        view = Error500View(mock_error)

        context = view.get_context()

        expected = {
            'error': mock_error,
            'message': 'Internal server error',
            'exception': mock_error.exception,
            'traceback': 'Test traceback',
        }
        self.assertEqual(context, expected)

    def test_error500_view_template_name(self) -> None:
        view = Error500View(Mock())
        self.assertEqual(view.template_name, '500.html')


class TestSessionListView(unittest.TestCase):
    @patch('term_timer.server.app.load_all_solves')
    @patch('term_timer.server.app.Statistics')
    def test_session_list_view_get_context(
        self, mock_statistics, mock_load_solves,
    ):
        # Mock solves data
        mock_solve1 = Mock()
        mock_solve1.session = 'session1'
        mock_solve2 = Mock()
        mock_solve2.session = 'session1'
        mock_solve3 = Mock()
        mock_solve3.session = 'session2'

        # Configure load_all_solves to return different data for each cube
        def load_solves_side_effect(cube, *_args):
            if cube == 2:
                return [mock_solve1]
            if cube == 3:
                return [mock_solve1, mock_solve2, mock_solve3]
            return []

        mock_load_solves.side_effect = load_solves_side_effect
        mock_statistics.return_value = Mock()

        view = SessionListView()
        context = view.get_context()

        self.assertIn('sessions', context)
        sessions = context['sessions']

        # Check that sessions are organized by cube size
        self.assertIn(2, sessions)
        self.assertIn(3, sessions)

        # Check that session1 has 2 solves and session2 has 1 solve for cube 3
        cube3_sessions = sessions[3]
        self.assertEqual(len(cube3_sessions['session1']['solves']), 2)
        self.assertEqual(len(cube3_sessions['session2']['solves']), 1)

    @patch('term_timer.server.app.load_all_solves')
    @patch('term_timer.server.app.Statistics')
    def test_session_list_view_all_sessions(
        self, mock_statistics, mock_load_solves,
    ):
        # Test that 'all' session is created when multiple sessions exist
        mock_solve1 = Mock(session='session1')
        mock_solve2 = Mock(session='session2')
        mock_load_solves.return_value = [mock_solve1, mock_solve2]
        mock_statistics.return_value = Mock()

        view = SessionListView()
        context = view.get_context()

        # Check that 'all' session is created for cube 3 (first cube with data)
        sessions = context['sessions'][3]
        self.assertIn('all', sessions)
        self.assertEqual(len(sessions['all']['solves']), 2)


class TestSessionDetailView(unittest.TestCase):
    @patch('term_timer.server.app.SolvesMethodAggregator')
    @patch('term_timer.server.app.StatisticsReporter')
    @patch('term_timer.server.app.load_all_solves')
    def test_session_detail_view_initialization(
        self, mock_load_solves, _mock_stats_reporter, mock_aggregator,
    ):
        mock_solves = [Mock(), Mock()]
        mock_load_solves.return_value = mock_solves

        mock_aggregator_instance = Mock()
        mock_aggregator_instance.results = {'stack': mock_solves}
        mock_aggregator.return_value = mock_aggregator_instance

        view = SessionDetailView(3, 'test-session', 'cfop', '', '')

        self.assertEqual(view.cube, 3)
        self.assertEqual(view.session, 'test-session')
        self.assertEqual(view.method_name, 'cfop')
        mock_load_solves.assert_called_once_with(3, ['test-session'], [], [])

    @patch('term_timer.server.app.SolvesMethodAggregator')
    @patch('term_timer.server.app.StatisticsReporter')
    @patch('term_timer.server.app.load_all_solves')
    def test_session_detail_view_all_session(
        self, mock_load_solves, _mock_stats_reporter, mock_aggregator,
    ):
        mock_solves = [Mock(), Mock()]
        mock_load_solves.return_value = mock_solves

        mock_aggregator_instance = Mock()
        mock_aggregator_instance.results = {'stack': mock_solves}
        mock_aggregator.return_value = mock_aggregator_instance

        SessionDetailView(3, 'all', '', '', '')

        # Should load all sessions when session is 'all'
        mock_load_solves.assert_called_once_with(3, [], [], [])

    @patch('term_timer.server.app.abort')
    @patch('term_timer.server.app.SolvesMethodAggregator')
    @patch('term_timer.server.app.load_all_solves')
    def test_session_detail_view_no_solves(
        self, mock_load_solves, mock_aggregator, mock_abort,
    ):
        mock_load_solves.return_value = []
        mock_aggregator_instance = Mock()
        mock_aggregator_instance.results = {'stack': []}
        mock_aggregator.return_value = mock_aggregator_instance

        SessionDetailView(3, 'test', '', '', '')

        mock_abort.assert_called_once_with(404, 'No solve to display')

    @patch('term_timer.server.app.SolvesMethodAggregator')
    @patch('term_timer.server.app.StatisticsReporter')
    @patch('term_timer.server.app.load_all_solves')
    def test_session_detail_view_step_case_filtering(
        self, mock_load_solves, _mock_stats_reporter, mock_aggregator,
    ):
        mock_solve = Mock()
        mock_solve.advanced = True
        mock_solve.method_applied.summary = [
            {'name': 'oll', 'case': 'OLL01 T-Shape'},
        ]

        mock_load_solves.return_value = [mock_solve]
        mock_aggregator_instance = Mock()
        mock_aggregator_instance.results = {'stack': [mock_solve]}
        mock_aggregator.return_value = mock_aggregator_instance

        view = SessionDetailView(3, 'test', '', 'oll', 'oll01')

        # Should filter solves based on step and case
        self.assertEqual(view.step, 'oll')
        self.assertEqual(view.case_uid, 'oll01')

    def test_session_detail_view_compute_sessions(self) -> None:
        mock_solve1 = Mock(session='session1')
        mock_solve2 = Mock(session='session1')
        mock_solve3 = Mock(session='session2')

        with (
            patch('term_timer.server.app.load_all_solves'),
            patch('term_timer.server.app.SolvesMethodAggregator'),
            patch('term_timer.server.app.StatisticsReporter'),
        ):
            view = SessionDetailView.__new__(SessionDetailView)
            view.stats = Mock()
            view.stats.stack = [mock_solve1, mock_solve2, mock_solve3]

            sessions = view.compute_sessions()

            expected = {'session1': 2, 'session2': 1}
            self.assertEqual(sessions, expected)

    def test_session_detail_view_compute_trend(self) -> None:
        with (
            patch('term_timer.server.app.load_all_solves'),
            patch('term_timer.server.app.SolvesMethodAggregator'),
            patch('term_timer.server.app.StatisticsReporter'),
        ):
            view = SessionDetailView.__new__(SessionDetailView)
            view.stats = Mock()
            view.stats.stack_time = [
                5000000000,
                6000000000,
                4000000000,
            ]  # 5s, 6s, 4s
            view.stats.ao.return_value = 5000000000

            trend = view.compute_trend()

            self.assertEqual(len(trend['times']), 3)
            self.assertEqual(len(trend['indices']), 3)
            self.assertEqual(trend['times'], [5.0, 6.0, 4.0])
            self.assertEqual(trend['indices'], ['1', '2', '3'])

    def test_session_detail_view_compute_distribution(self) -> None:
        with (
            patch('term_timer.server.app.load_all_solves'),
            patch('term_timer.server.app.SolvesMethodAggregator'),
            patch('term_timer.server.app.StatisticsReporter'),
        ):
            view = SessionDetailView.__new__(SessionDetailView)
            view.stats = Mock()
            view.stats.repartition = [(5, 10), (3, 15), (2, 20)]

            distribution = view.compute_distribution()

            expected = {
                'labels': ['10s', '15s', '20s'],
                'counts': [5, 3, 2],
            }
            self.assertEqual(distribution, expected)

    def test_session_detail_view_compute_punchcard(self) -> None:
        mock_dt = Mock()
        mock_dt.strftime.side_effect = lambda fmt: {
            '%Y': '2023',
            '%Y-%m-%d': '2023-01-15',
        }[fmt]

        mock_solve = Mock()
        mock_solve.datetime.astimezone.return_value = mock_dt

        with (
            patch('term_timer.server.app.load_all_solves'),
            patch('term_timer.server.app.SolvesMethodAggregator'),
            patch('term_timer.server.app.StatisticsReporter'),
        ):
            view = SessionDetailView.__new__(SessionDetailView)
            view.stats = Mock()
            view.stats.stack = [mock_solve, mock_solve]

            punchcard = view.compute_punchcard()

            expected = {'2023': {'2023-01-15': 2}}
            self.assertEqual(punchcard, expected)


class TestSolveDetailView(unittest.TestCase):
    @patch('term_timer.server.app.load_all_solves')
    @patch('term_timer.server.app.abort')
    def test_solve_detail_view_invalid_solve_id(
        self, mock_abort, mock_load_solves,
    ):
        mock_load_solves.return_value = [Mock()]  # Only one solve

        with contextlib.suppress(AttributeError):
            # Request solve 5 (index 4)
            SolveDetailView(3, 'session', 5, '', '')

        mock_abort.assert_called_once_with(404, 'Invalid solve ID')

    @patch('term_timer.server.app.load_all_solves')
    def test_solve_detail_view_initialization(self, mock_load_solves) -> None:
        mock_solve = Mock()
        mock_load_solves.return_value = [mock_solve]

        view = SolveDetailView(3, 'test-session', 1, 'cfop', 'DF')

        self.assertEqual(view.cube, 3)
        self.assertEqual(view.session, 'test-session')
        self.assertEqual(view.solve_id, 1)
        self.assertEqual(view.solve_index, 0)
        self.assertEqual(view.solve, mock_solve)
        self.assertEqual(view.solve.method_name, 'cfop')

    @patch('term_timer.server.app.load_all_solves')
    def test_solve_detail_view_get_context_basic(
            self, mock_load_solves) -> None:
        mock_solve = Mock()
        mock_solve.final_time = 5000000000
        mock_solve.advanced = False
        mock_solve.method_text_builder.return_value = (
            'Cross // Cross\nF2L // F2L'
        )

        mock_load_solves.return_value = [mock_solve]

        view = SolveDetailView(3, 'test', 1, '', '')
        context = view.get_context()

        self.assertEqual(context['cube'], 3)
        self.assertEqual(context['session'], 'test')
        self.assertEqual(context['solve'], mock_solve)
        self.assertEqual(context['solve_id'], 1)
        self.assertEqual(context['rank'], 1)
        self.assertEqual(len(context['scatter']), 0)  # No advanced data

    @patch('term_timer.server.app.load_all_solves')
    def test_solve_detail_view_get_context_advanced(
            self, mock_load_solves) -> None:
        mock_solve = Mock()
        mock_solve.final_time = 5000000000
        mock_solve.advanced = True
        mock_solve.move_times = [(0, 1000), (1, 2000), (2, 3000)]
        mock_solve.method_applied.summary = [
            {
                'type': 'step',
                'index': [0, 1],
                'name': 'Cross',
                'qtm': 8,
                'total': 2000000000,
                'execution': 1500000000,
                'recognition': 500000000,
            },
        ]
        mock_solve.method_text_builder.return_value = (
            'Cross // Cross\nF2L // F2L'
        )

        mock_load_solves.return_value = [mock_solve]

        view = SolveDetailView(3, 'test', 1, '', '')
        context = view.get_context()

        # Should have scatter plot data
        self.assertEqual(len(context['scatter']), 3)
        self.assertEqual(context['scatter'][0]['x'], 1)
        self.assertEqual(context['scatter'][0]['y'], 1.0)  # 1000 / 1000

        # Should have steps data
        self.assertEqual(len(context['steps']), 1)
        self.assertEqual(context['steps'][0]['label'], 'Cross')

        # Should have TPS data
        self.assertEqual(len(context['tps']), 1)


class TestSolveUpdateView(unittest.TestCase):
    @patch('term_timer.server.app.redirect')
    @patch('term_timer.server.app.save_solves')
    @patch('term_timer.server.app.load_all_solves')
    def test_solve_update_view_invalid_id(
        self, mock_load_solves, _mock_save_solves, _mock_redirect,
    ):
        mock_load_solves.return_value = []

        with self.assertRaises(HTTPError):  # abort() raises HTTPError
            SolveUpdateView(3, 'session', 1, 'DNF')

    @patch('term_timer.server.app.redirect')
    @patch('term_timer.server.app.save_solves')
    @patch('term_timer.server.app.load_all_solves')
    def test_solve_update_view_success(
        self, mock_load_solves, mock_save_solves, _mock_redirect,
    ):
        mock_solve = Mock()
        mock_load_solves.return_value = [mock_solve]

        with contextlib.suppress(HTTPError):
            SolveUpdateView(3, 'session', 1, 'DNF')

        self.assertEqual(mock_solve.flag, 'DNF')
        mock_save_solves.assert_called_once_with(3, 'session', [mock_solve])


class TestSolveDeleteView(unittest.TestCase):
    @patch('term_timer.server.app.redirect')
    @patch('term_timer.server.app.save_solves')
    @patch('term_timer.server.app.load_all_solves')
    def test_solve_delete_view_invalid_id(
        self, mock_load_solves, _mock_save_solves, _mock_redirect,
    ):
        mock_load_solves.return_value = []

        with self.assertRaises(HTTPError):  # abort() raises HTTPError
            SolveDeleteView(3, 'session', 1)

    @patch('term_timer.server.app.redirect')
    @patch('term_timer.server.app.save_solves')
    @patch('term_timer.server.app.load_all_solves')
    def test_solve_delete_view_success(
        self, mock_load_solves, mock_save_solves, _mock_redirect,
    ):
        mock_solve1 = Mock()
        mock_solve2 = Mock()
        mock_solves = [mock_solve1, mock_solve2]
        mock_load_solves.return_value = mock_solves

        with contextlib.suppress(HTTPError):
            SolveDeleteView(3, 'session', 2)  # Delete second solve

        # Should remove the solve from the list
        self.assertEqual(len(mock_solves), 1)
        mock_save_solves.assert_called_once_with(3, 'session', [mock_solve1])


class TestServer(unittest.TestCase):
    def setUp(self) -> None:
        self.server = Server()

    @patch.dict('os.environ', {}, clear=True)
    @patch('term_timer.server.app.console')
    def test_run_server(self, mock_console) -> None:
        mock_app = Mock()
        mock_app.run = Mock()

        with patch.object(self.server, 'create_app', return_value=mock_app):
            self.server.run_server('127.0.0.1', 8080, debug=False)

            mock_app.run.assert_called_once_with(
                host='127.0.0.1',
                port=8080,
                quiet=True,
                reloader=False,
                debug=False,
                server='wsgiref',
                handler_class=RichHandler,
            )

            # Should print startup messages
            self.assertEqual(mock_console.print.call_count, 2)

    @patch.dict('os.environ', {'BOTTLE_CHILD': '1'})
    @patch('term_timer.server.app.console')
    def test_run_server_bottle_child(self, mock_console) -> None:
        mock_app = Mock()
        mock_app.run = Mock()

        with patch.object(self.server, 'create_app', return_value=mock_app):
            self.server.run_server('127.0.0.1', 8080, debug=True)

            # Should not print startup messages when BOTTLE_CHILD is set
            mock_console.print.assert_not_called()

    def test_create_app(self) -> None:
        app = self.server.create_app(debug=False)

        self.assertIsInstance(app, Bottle)

        # Test that routes are registered
        route_paths = [route.rule for route in app.routes]
        expected_paths = [
            '/',
            '/<cube:int>/<session:path>/<solve:int>/update/',
            '/<cube:int>/<session:path>/<solve:int>/delete/',
            '/<cube:int>/<session:path>/<solve:int>/',
            '/<cube:int>/<session:path>/',
            '/static/<filepath:path>',
        ]

        for expected_path in expected_paths:
            self.assertIn(expected_path, route_paths)

    def test_create_app_has_hooks(self) -> None:
        app = self.server.create_app(debug=False)

        # Verify that the app has hooks registered
        # Bottle creates a hooks dictionary automatically
        self.assertIsInstance(app, Bottle)
        # Check that the app has the expected number of routes
        self.assertGreater(len(app.routes), 0)

    def test_create_app_error_handlers(self) -> None:
        app = self.server.create_app(debug=False)

        # Check that error handlers are registered
        self.assertIn(404, app.error_handler)
        self.assertIn(500, app.error_handler)
