"""Tests for server app."""
# ruff: noqa: PT019
import contextlib
import unittest
from http import HTTPStatus
from typing import Any
from unittest.mock import Mock
from unittest.mock import patch

from bottle import Bottle
from bottle import HTTPError
from cubing_algs.algorithm import Algorithm

from term_timer.constants import SECOND
from term_timer.constants import SOLVES_DIRECTORY
from term_timer.server.app import RichHandler
from term_timer.server.app import Server
from term_timer.server.filters import BLOCK_REGEX
from term_timer.server.filters import format_delta
from term_timer.server.views import Error404View
from term_timer.server.views import Error500View
from term_timer.server.views import SessionDetailView
from term_timer.server.views import SessionListView
from term_timer.server.views import SolveDeleteView
from term_timer.server.views import SolveDetailView
from term_timer.server.views import SolveUpdateFlagView
from term_timer.server.views.base import View
from term_timer.server.views.solves import SolveLocation
from term_timer.solve import Solve
from term_timer.stats import SolveStatisticsReporter


class TestBlockRegex(unittest.TestCase):
    """Tests for the block markup pattern."""

    def test_block_regex(self) -> None:
        """A block gives its markup, its moves and its closing markup."""
        matches = BLOCK_REGEX.findall('[pre-auf]R U[/pre-auf]')
        self.assertEqual(matches, [('pre-auf', 'R U', 'pre-auf')])


class TestFormatDelta(unittest.TestCase):
    """Tests for format_delta function."""

    def test_format_delta_zero(self) -> None:
        """Test format delta zero."""
        result = format_delta(0)
        self.assertEqual(result, '')

    def test_format_delta_positive(self) -> None:
        """Test format delta positive."""
        result = format_delta(1500000000)  # 1.5 seconds
        self.assertEqual(result, '+1.50')

    def test_format_delta_negative(self) -> None:
        """Test format delta negative."""
        result = format_delta(-2500000000)  # -2.5 seconds
        self.assertEqual(result, '-2.50')

    def test_format_delta_small_positive(self) -> None:
        """Test format delta small positive."""
        result = format_delta(100000000)  # 0.1 seconds
        self.assertEqual(result, '+0.10')


class TestRichHandler(unittest.TestCase):
    """Tests for RichHandler class."""

    def setUp(self) -> None:
        """Test setup."""
        # Create a mock request, client_address, and server for RichHandler
        self.handler = RichHandler.__new__(RichHandler)
        self.handler.requestline = ''

    @patch('term_timer.server.app.console')
    def test_log_request_success_code(self, mock_console: Mock) -> None:
        """Test log request success code."""
        self.handler.requestline = 'GET /test HTTP/1.1'
        self.handler.log_request(200, 1024)

        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0][0]
        self.assertIn('[green]200[/green]', call_args)
        self.assertIn('GET /test HTTP/1.1', call_args)
        self.assertIn('1024', call_args)

    @patch('term_timer.server.app.console')
    def test_log_request_error_code(self, mock_console: Mock) -> None:
        """Test log request error code."""
        self.handler.requestline = 'GET /error HTTP/1.1'
        self.handler.log_request(404, 512)

        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0][0]
        self.assertIn('[red]404[/red]', call_args)

    @patch('term_timer.server.app.console')
    def test_log_request_http_status_object(self, mock_console: Mock) -> None:
        """Test log request http status object."""
        self.handler.requestline = 'GET /status HTTP/1.1'
        self.handler.log_request(HTTPStatus.OK, 256)

        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0][0]
        self.assertIn('[green]200[/green]', call_args)


class TestView(unittest.TestCase):
    """Tests for View base class."""

    def test_view_abstract_get_context(self) -> None:
        """Test view abstract get context."""
        view = View()
        with self.assertRaises(NotImplementedError):
            view.get_context()

    @patch('term_timer.server.views.base.jinja2_template')
    @patch('term_timer.server.views.base.gc.collect')
    def test_view_as_view(self, mock_gc_collect: Mock,
                          mock_jinja2_template: Mock) -> None:
        """Test view as view."""
        mock_jinja2_template.return_value = 'rendered_content'

        class TestView(View):
            template_name = 'test.html'

            @staticmethod
            def get_context() -> dict[str, Any]:  # type: ignore[override]
                return {'test': 'value'}

        view = TestView()
        result = view.as_view(debug=True)

        self.assertEqual(result, 'rendered_content')
        mock_gc_collect.assert_called_once()
        mock_jinja2_template.assert_called_once()

    @patch('term_timer.server.views.base.jinja2_template')
    def test_view_template_context(self, mock_jinja2_template: Mock) -> None:
        """Test view template context."""
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
        self.assertTrue(template_settings['autoescape'])
        expected_filters = [
            'asset',
            'format_delta',
            'format_duration',
            'format_grade',
            'alg_tokens',
            'algorithm_tokens',
            'metric_tone',
            'prettify',
        ]
        for filter_name in expected_filters:
            self.assertIn(filter_name, template_settings['filters'])
        for filter_name in ('format_line', 'reconstruction_step'):
            self.assertNotIn(filter_name, template_settings['filters'])


class TestError404View(unittest.TestCase):
    """Tests for Error404View class."""

    def test_error404_view_get_context(self) -> None:
        """Test error404 view get context."""
        mock_error = Mock()
        mock_error.body = 'Page not found'
        view = Error404View(mock_error, '/lost/')

        context = view.get_context()

        self.assertEqual(context['message'], 'Page not found')
        self.assertEqual(context['path'], '/lost/')
        self.assertEqual(
            context['scramble'], Error404View(Mock(), '/lost/').get_scramble(),
        )

    def test_error404_view_template_name(self) -> None:
        """Test error404 view template name."""
        view = Error404View(Mock())
        self.assertEqual(view.template_name, '404.html')


class TestError500View(unittest.TestCase):
    """Tests for Error500View class."""

    def test_error500_view_get_context(self) -> None:
        """Test error500 view get context."""
        mock_error = Mock()
        mock_error.body = 'Internal server error'
        mock_error.exception = Exception('Test exception')
        mock_error.traceback = 'Test traceback'
        view = Error500View(mock_error, '/broken/')

        with self.assertLogs('term_timer.server.views.errors', 'ERROR'):
            context = view.get_context()

        expected = {
            'message': 'Internal server error',
            'exception': mock_error.exception,
            'exception_name': 'Exception',
            'traceback': 'Test traceback',
            'frames': [],
            'path': '/broken/',
        }
        self.assertEqual(context, expected)

    def test_error500_view_template_name(self) -> None:
        """Test error500 view template name."""
        view = Error500View(Mock())
        self.assertEqual(view.template_name, '500.html')


class TestSessionListView(unittest.TestCase):
    """Tests for SessionListView class."""

    @patch(
        'term_timer.server.views.sessions.SessionListView.dashboard',
        return_value={},
    )
    @patch('term_timer.server.views.sessions.DailyListView.banner')
    @patch('term_timer.server.views.sessions.load_all_solves')
    @patch('term_timer.server.views.sessions.Statistics')
    def test_session_list_view_get_context(
            self, mock_statistics: Mock, mock_load_solves: Mock,
            mock_banner: Mock, mock_dashboard: Mock,
    ) -> None:
        """Test session list view get context."""
        # Mock solves data
        mock_solve1 = Mock()
        mock_solve1.session = 'session1'
        mock_solve2 = Mock()
        mock_solve2.session = 'session1'
        mock_solve3 = Mock()
        mock_solve3.session = 'session2'

        # Configure load_all_solves to return different data for each cube
        def load_solves_side_effect(
                cube: int, *_args: Any, **_kwargs: Any,  # noqa: ANN401
        ) -> list[Mock]:
            if cube == 2:
                return [mock_solve1]
            if cube == 3:
                return [mock_solve1, mock_solve2, mock_solve3]
            return []

        mock_load_solves.side_effect = load_solves_side_effect
        mock_statistics.return_value = Mock()

        view = SessionListView()
        context = view.get_context()

        sessions = mock_dashboard.call_args.args[0]
        self.assertEqual(context['daily'], mock_banner.return_value)
        mock_banner.assert_called_once_with(3)

        # Check that sessions are organized by cube size
        self.assertIn(2, sessions)
        self.assertIn(3, sessions)

        # Check that session1 has 2 solves and session2 has 1 solve for cube 3
        cube3_sessions = sessions[3]
        self.assertEqual(len(cube3_sessions['session1']['solves']), 2)
        self.assertEqual(len(cube3_sessions['session2']['solves']), 1)

    @patch(
        'term_timer.server.views.sessions.SessionListView.dashboard',
        return_value={},
    )
    @patch('term_timer.server.views.sessions.DailyListView.banner')
    @patch('term_timer.server.views.sessions.load_all_solves')
    @patch('term_timer.server.views.sessions.Statistics')
    def test_session_list_view_all_sessions(
            self, mock_statistics: Mock, mock_load_solves: Mock,
            _mock_banner: Mock, mock_dashboard: Mock,
    ) -> None:
        """Test session list view all sessions."""
        # Test that 'all' session is created when multiple sessions exist
        mock_solve1 = Mock(session='session1')
        mock_solve2 = Mock(session='session2')
        mock_load_solves.return_value = [mock_solve1, mock_solve2]
        mock_statistics.return_value = Mock()

        SessionListView.get_context()

        # Check that 'all' session is created for cube 3 (first cube with data)
        sessions = mock_dashboard.call_args.args[0][3]
        self.assertIn('all', sessions)
        self.assertEqual(len(sessions['all']['solves']), 2)


class TestSessionDetailView(unittest.TestCase):
    """Tests for SessionDetailView class."""

    @patch('term_timer.server.views.sessions.SolvesMethodAggregator')
    @patch('term_timer.server.views.sessions.SolveStatisticsReporter')
    @patch('term_timer.server.views.sessions.load_all_solves')
    def test_session_detail_view_initialization(
            self, mock_load_solves: Mock, _mock_stats_reporter: Mock,
            mock_aggregator: Mock) -> None:
        """Test session detail view initialization."""
        mock_solves = [Mock(), Mock()]
        mock_load_solves.return_value = mock_solves

        mock_aggregator_instance = Mock()
        mock_aggregator_instance.results = {'stack': mock_solves}
        mock_aggregator.return_value = mock_aggregator_instance

        view = SessionDetailView(3, 'test-session', 'cfop', '', '')

        self.assertEqual(view.cube, 3)
        self.assertEqual(view.session, 'test-session')
        self.assertEqual(view.method_name, 'cfop')
        mock_load_solves.assert_called_once_with(
            3, ['test-session'], [], [], directory=SolveLocation.directory,
        )

    @staticmethod
    @patch('term_timer.server.views.sessions.SolvesMethodAggregator')
    @patch('term_timer.server.views.sessions.SolveStatisticsReporter')
    @patch('term_timer.server.views.sessions.load_all_solves')
    def test_session_detail_view_all_session(
            mock_load_solves: Mock, _mock_stats_reporter: Mock,
            mock_aggregator: Mock) -> None:
        """Test session detail view all session."""
        mock_solves = [Mock(), Mock()]
        mock_load_solves.return_value = mock_solves

        mock_aggregator_instance = Mock()
        mock_aggregator_instance.results = {'stack': mock_solves}
        mock_aggregator.return_value = mock_aggregator_instance

        SessionDetailView(3, 'all', '', '', '')

        # Should load all sessions when session is 'all'
        mock_load_solves.assert_called_once_with(
            3, [], [], [], directory=SolveLocation.directory,
        )

    @staticmethod
    @patch('term_timer.server.views.sessions.abort')
    @patch('term_timer.server.views.sessions.SolvesMethodAggregator')
    @patch('term_timer.server.views.sessions.load_all_solves')
    def test_session_detail_view_no_solves(
            mock_load_solves: Mock, mock_aggregator: Mock,
            mock_abort: Mock) -> None:
        """Test session detail view no solves."""
        mock_load_solves.return_value = []
        mock_aggregator_instance = Mock()
        mock_aggregator_instance.results = {'stack': []}
        mock_aggregator.return_value = mock_aggregator_instance

        SessionDetailView(3, 'test', '', '', '')

        mock_abort.assert_called_once_with(404, 'No solve to display')

    @patch('term_timer.server.views.sessions.SolvesMethodAggregator')
    @patch('term_timer.server.views.sessions.SolveStatisticsReporter')
    @patch('term_timer.server.views.sessions.load_all_solves')
    def test_session_detail_view_step_case_filtering(
            self, mock_load_solves: Mock, _mock_stats_reporter: Mock,
            mock_aggregator: Mock) -> None:
        """Test session detail view step case filtering."""
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

    def test_session_detail_view_compute_trend(self) -> None:
        """Test session detail view compute trend."""
        with (
            patch('term_timer.server.views.sessions.load_all_solves'),
            patch('term_timer.server.views.sessions.SolvesMethodAggregator'),
            patch('term_timer.server.views.sessions.SolveStatisticsReporter'),
        ):
            view = SessionDetailView.__new__(SessionDetailView)
            view.stats = Mock()
            view.stats.total = 12
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
        """Test session detail view compute distribution."""
        with (
            patch('term_timer.server.views.sessions.load_all_solves'),
            patch('term_timer.server.views.sessions.SolvesMethodAggregator'),
            patch('term_timer.server.views.sessions.SolveStatisticsReporter'),
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
        """Test session detail view compute punchcard."""
        mock_dt = Mock()
        mock_dt.strftime.side_effect = lambda fmt: {
            '%Y': '2023',
            '%Y-%m-%d': '2023-01-15',
        }[fmt]

        mock_solve = Mock()
        mock_solve.datetime.astimezone.return_value = mock_dt

        with (
            patch('term_timer.server.views.sessions.load_all_solves'),
            patch('term_timer.server.views.sessions.SolvesMethodAggregator'),
            patch('term_timer.server.views.sessions.SolveStatisticsReporter'),
        ):
            view = SessionDetailView.__new__(SessionDetailView)
            view.stats = Mock()
            view.stats.stack = [mock_solve, mock_solve]

            punchcard = view.compute_punchcard()

            expected = {'2023': {'2023-01-15': 2}}
            self.assertEqual(punchcard, expected)


class TestSolveDetailView(unittest.TestCase):
    """Tests for SolveDetailView class."""

    @staticmethod
    @patch('term_timer.server.views.solves.load_all_solves')
    @patch('term_timer.server.views.solves.abort')
    def test_solve_detail_view_invalid_solve_id(
            mock_abort: Mock, mock_load_solves: Mock,
    ) -> None:
        """Test solve detail view invalid solve id."""
        mock_load_solves.return_value = [Mock()]  # Only one solve

        with contextlib.suppress(AttributeError):
            # Request solve 5 (index 4)
            SolveDetailView(3, 'session', 5, '', '')

        mock_abort.assert_called_once_with(404, 'Invalid solve ID')

    @patch('term_timer.server.views.solves.load_all_solves')
    def test_solve_detail_view_initialization(
            self, mock_load_solves: Mock) -> None:
        """Test solve detail view initialization."""
        mock_solve = Mock()
        mock_load_solves.return_value = [mock_solve]

        view = SolveDetailView(3, 'test-session', 1, 'cfop', 'DF')

        self.assertEqual(view.cube, 3)
        self.assertEqual(view.session, 'test-session')
        self.assertEqual(view.solve_id, 1)
        self.assertEqual(view.solve_index, 0)
        self.assertEqual(view.solve, mock_solve)
        self.assertEqual(view.solve.method_name, 'cfop')

    @patch('term_timer.server.views.solves.generate_solve_diagnostics')
    @patch('term_timer.server.views.solves.load_all_solves')
    def test_solve_detail_view_get_context_basic(
        self,
        mock_load_solves: Mock,
        _mock_diagnostics: Mock,
    ) -> None:
        """Test solve detail view get context basic."""
        mock_solve = Mock()
        mock_solve.final_time = 5000000000
        mock_solve.advanced = False
        mock_solve.analysable = False
        mock_solve.method_applied = None
        mock_solve.method_text_builder.return_value = (
            'Cross // Cross\nF2L // F2L'
        )
        mock_solve.reconstruction_steps_timing = [
            (0, 1000, 'R'), (1000, 2000, 'U'),
        ]

        mock_load_solves.return_value = [mock_solve]

        view = SolveDetailView(3, 'test', 1, '', '')
        context = view.get_context()

        self.assertEqual(context['cube'], 3)
        self.assertEqual(context['session'], 'test')
        self.assertEqual(context['solve'], mock_solve)
        self.assertEqual(context['solve_id'], 1)
        self.assertEqual(context['rank'], 1)
        self.assertEqual(len(context['scatter']), 0)  # No advanced data

    # The step rows read full step summaries: covered on a real solve
    # by test_server_solve.
    @patch.object(SolveDetailView, 'step_rows', return_value=[])
    @patch('term_timer.server.views.solves.generate_solve_diagnostics')
    @patch('term_timer.server.views.solves.load_all_solves')
    def test_solve_detail_view_get_context_advanced(
        self,
        mock_load_solves: Mock,
        _mock_diagnostics: Mock,
        _mock_step_rows: Mock,
    ) -> None:
        """Test solve detail view get context advanced."""
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
                'moves': Algorithm.parse_moves('R U'),
                'total': 2000000000,
                'execution': 1500000000,
                'recognition': 500000000,
                'moves_prettified': Algorithm.parse_moves('R U'),
            },
        ]
        mock_solve.fluency = 50
        mock_solve.tps = 3
        mock_solve.aufs = 2
        mock_solve.score = 16.0
        mock_solve.execution_pauses = 2
        mock_solve.time = 5000000000
        mock_solve.recognition_time = 2000000000
        mock_solve.method_text_builder.return_value = (
            'Cross // Cross\nF2L // F2L'
        )
        mock_solve.reconstruction_steps_timing = [
            (0, 1000, 'R'), (1000, 2000, 'U'),
        ]

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

        # Should have the replay timings, without their moves
        self.assertEqual(context['replay']['timing'], [(0, 1000), (1000, 2000)])


class TestSolveUpdateFlagView(unittest.TestCase):
    """Tests for SolveUpdateFlagView class."""

    @patch('term_timer.server.views.solves.redirect')
    @patch('term_timer.server.views.solves.save_solves')
    @patch('term_timer.server.views.solves.load_all_solves')
    def test_solve_update_view_invalid_id(
            self, mock_load_solves: Mock, _mock_save_solves: Mock,
            _mock_redirect: Mock) -> None:
        """Test solve update view invalid id."""
        mock_load_solves.return_value = []

        with self.assertRaises(HTTPError):  # abort() raises HTTPError
            SolveUpdateFlagView(3, 'session', 1, 'DNF')

    @patch('term_timer.server.views.solves.redirect')
    @patch('term_timer.server.views.solves.save_solves')
    @patch('term_timer.server.views.solves.load_all_solves')
    def test_solve_update_view_success(
            self, mock_load_solves: Mock, mock_save_solves: Mock,
            _mock_redirect: Mock) -> None:
        """Test solve update view success."""
        mock_solve = Mock()
        mock_solve.advanced = False
        mock_load_solves.return_value = [mock_solve]

        with contextlib.suppress(HTTPError):
            SolveUpdateFlagView(3, 'session', 1, 'DNF')

        self.assertEqual(mock_solve.flag, 'DNF')
        mock_save_solves.assert_called_once_with(
            3, 'session', [mock_solve], SOLVES_DIRECTORY,
        )

    @patch('term_timer.server.views.solves.redirect')
    @patch('term_timer.server.views.solves.save_solves')
    @patch('term_timer.server.views.solves.load_all_solves')
    def test_solve_update_view_advanced_forbidden(
            self, mock_load_solves: Mock, mock_save_solves: Mock,
            _mock_redirect: Mock) -> None:
        """Test flag update is forbidden on an advanced solve."""
        mock_solve = Mock()
        mock_solve.advanced = True
        mock_load_solves.return_value = [mock_solve]

        with self.assertRaises(HTTPError):  # abort() raises HTTPError
            SolveUpdateFlagView(3, 'session', 1, 'DNF')

        mock_save_solves.assert_not_called()


class TestSolveDeleteView(unittest.TestCase):
    """Tests for SolveDeleteView class."""

    @patch('term_timer.server.views.solves.redirect')
    @patch('term_timer.server.views.solves.save_solves')
    @patch('term_timer.server.views.solves.load_all_solves')
    def test_solve_delete_view_invalid_id(
            self, mock_load_solves: Mock, _mock_save_solves: Mock,
            _mock_redirect: Mock) -> None:
        """Test solve delete view invalid id."""
        mock_load_solves.return_value = []

        with self.assertRaises(HTTPError):  # abort() raises HTTPError
            SolveDeleteView(3, 'session', 1)

    @patch('term_timer.server.views.solves.redirect')
    @patch('term_timer.server.views.solves.save_solves')
    @patch('term_timer.server.views.solves.load_all_solves')
    def test_solve_delete_view_success(
            self, mock_load_solves: Mock, mock_save_solves: Mock,
            _mock_redirect: Mock) -> None:
        """Test solve delete view success."""
        mock_solve1 = Mock()
        mock_solve2 = Mock()
        mock_solves = [mock_solve1, mock_solve2]
        mock_load_solves.return_value = mock_solves

        with contextlib.suppress(HTTPError):
            SolveDeleteView(3, 'session', 2)  # Delete second solve

        # Should remove the solve from the list
        self.assertEqual(len(mock_solves), 1)
        mock_save_solves.assert_called_once_with(
            3, 'session', [mock_solve1], SOLVES_DIRECTORY,
        )


class TestServer(unittest.TestCase):
    """Tests for Server class."""

    def setUp(self) -> None:
        """Test setup."""
        self.server = Server()

    @patch.dict('os.environ', {}, clear=True)
    @patch('term_timer.server.app.console')
    def test_run_server(self, mock_console: Mock) -> None:
        """Test run server."""
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
    def test_run_server_bottle_child(self, mock_console: Mock) -> None:
        """Test run server bottle child."""
        mock_app = Mock()
        mock_app.run = Mock()

        with patch.object(self.server, 'create_app', return_value=mock_app):
            self.server.run_server('127.0.0.1', 8080, debug=True)

            # Should not print startup messages when BOTTLE_CHILD is set
            mock_console.print.assert_not_called()

    def test_create_app(self) -> None:
        """Test create app."""
        app = self.server.create_app(debug=False)

        self.assertIsInstance(app, Bottle)

        # Test that routes are registered
        route_paths = [route.rule for route in app.routes]
        expected_paths = [
            '/',
            '/<cube:int>/<session:path>/<solve:int>/flag/',
            '/<cube:int>/<session:path>/<solve:int>/comment/',
            '/<cube:int>/<session:path>/<solve:int>/delete/',
            '/<cube:int>/<session:path>/<solve:int>/',
            '/<cube:int>/<session:path>/',
            '/static/<filepath:path>',
        ]

        for expected_path in expected_paths:
            self.assertIn(expected_path, route_paths)

    def test_create_app_has_hooks(self) -> None:
        """Test create app has hooks."""
        app = self.server.create_app(debug=False)

        # Verify that the app has hooks registered
        # Bottle creates a hooks dictionary automatically
        self.assertIsInstance(app, Bottle)
        # Check that the app has the expected number of routes
        self.assertGreater(len(app.routes), 0)

    def test_create_app_error_handlers(self) -> None:
        """Test create app error handlers."""
        app = self.server.create_app(debug=False)

        # Check that error handlers are registered
        self.assertIn(404, app.error_handler)
        self.assertIn(500, app.error_handler)


class TestComputeTrend(unittest.TestCase):
    """Tests for SessionDetailView.compute_trend series filtering."""

    def setUp(self) -> None:
        """Build a stats reporter with 12 solves."""
        solves = [
            Solve(
                (i + 1) * 1000000000000,
                (10 + i) * SECOND,
                'F R U', '',
            )
            for i in range(12)
        ]
        self.view = object.__new__(SessionDetailView)
        self.view.stats = SolveStatisticsReporter(3, solves)

    def test_only_returns_series_with_enough_solves(self) -> None:
        """Series whose size exceeds the total are dropped."""
        with patch(
                'term_timer.server.views.sessions.STATS_GRAPH_SERIES',
                [('ao', 5), ('ao', 12), ('ao', 100), ('ao', 1000)],
        ):
            trend = self.view.compute_trend()

        tokens = [serie['token'] for serie in trend['series']]
        self.assertEqual(tokens, ['ao5', 'ao12'])

    def test_series_order_preserved(self) -> None:
        """Returned series keep the configured order."""
        with patch(
                'term_timer.server.views.sessions.STATS_GRAPH_SERIES',
                [('ao', 12), ('ao', 5)],
        ):
            trend = self.view.compute_trend()

        tokens = [serie['token'] for serie in trend['series']]
        self.assertEqual(tokens, ['ao12', 'ao5'])

    def test_series_data_length_matches_indices(self) -> None:
        """Each series produces one data point per solve."""
        with patch(
                'term_timer.server.views.sessions.STATS_GRAPH_SERIES',
                [('ao', 5)],
        ):
            trend = self.view.compute_trend()

        self.assertEqual(len(trend['indices']), 12)
        self.assertEqual(len(trend['series'][0]['data']), 12)
