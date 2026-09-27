"""Tests for the V2 solve page, its reconstruction tokens and tones."""
import json
import re
import tempfile
import unittest
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import cast
from unittest.mock import patch

from bottle import TEMPLATE_PATH
from bottle import TEMPLATES

from term_timer.constants import TEMPLATES_DIRECTORY
from term_timer.server.app import Server
from term_timer.server.filters import alg_tokens
from term_timer.server.filters import count_tone
from term_timer.server.filters import fluency_tone
from term_timer.server.filters import format_line
from term_timer.server.filters import metric_tone
from term_timer.server.filters import optimized_markup
from term_timer.server.filters import optimized_step
from term_timer.server.filters import overheads_markup
from term_timer.server.filters import pauses_markup
from term_timer.server.filters import reconstruction_markup
from term_timer.server.filters import reconstruction_overheads
from term_timer.server.filters import reconstruction_pauses
from term_timer.server.filters import reconstruction_step
from term_timer.server.filters import split_time
from term_timer.server.views.daily import DailyLocation
from term_timer.server.views.solves import SolveLocation
from term_timer.solve import Solve
from term_timer.tests.test_server_components import V1_TEXT_RE
from term_timer.tests.test_server_components import move_texts
from term_timer.tests.test_server_daily import WSGIClient

if TYPE_CHECKING:
    from term_timer.methods.base import Analyser

SECOND = 1_000_000_000

# The real solve of test_solve_54: 80 moves, CF4OP.
SCRAMBLE = (
    "F2 D2 F2 D' U' L2 B2 L2 B2 U L U' B D R2 U L F2 U R2 U2"
)
MOVES = (
    "L@0 L@88 D@538 F@1108 R@1350 D@2249 F@2608 F@2818 D'@3119 B@3419 "
    "B@3748 D'@5069 L@5428 D@5549 L'@5639 D@5968 B@6329 D'@6689 B'@6959 "
    "D@9388 F'@9718 D@9898 F@10229 D'@10469 F@10798 D@11099 F'@11279 "
    "D'@12328 D'@12598 L@13198 D'@13288 L'@13408 D@13738 D'@14188 "
    "L@14549 D'@14638 D'@14849 L'@14908 D@15208 F'@15419 D'@15659 "
    "F@15930 D@17908 R@18059 D'@18149 R'@18358 D'@18419 B'@18809 "
    "D@18958 B@19078 D'@19529 L@20099 R'@20101 D@20519 B@20609 D'@20699 "
    "B'@21149 D'@21358 R@21508 D@21658 L'@22019 L@24238 D@24329 "
    "L'@24419 D'@24539 L'@24718 F@24838 L@24988 L@25051 D'@25139 "
    "L'@25289 D'@25409 L@25768 D@25919 L'@26008 L@26458 L'@26492 "
    "F'@26818 D'@27148 D'@27359"
)
ADVANCED_TIME = 27357994593

SESSION = 'test'
DAY = '2026-09-25'
ESCAPED_V1_RE = re.compile(r'&lt;(span|div)')


def solve_54() -> Solve:
    """
    Build the advanced solve of the fixture, analysed in CF4OP.

    Returns:
        The solve, its method applied.

    """
    solve = Solve(1751576007, ADVANCED_TIME, SCRAMBLE, moves=MOVES)
    solve.method_name = 'cf4op'
    solve.orientation = 'DF'
    return solve


class SolveServerTestCase(unittest.TestCase):
    """A session of three solves served by a normal and a debug app."""

    client: WSGIClient
    debug_client: WSGIClient

    @classmethod
    def setUpClass(cls) -> None:
        """Register the templates and build both applications once."""
        if str(TEMPLATES_DIRECTORY) not in map(str, TEMPLATE_PATH):
            TEMPLATE_PATH.insert(0, TEMPLATES_DIRECTORY)
        TEMPLATES.clear()
        cls.client = WSGIClient(Server.create_app(debug=False))
        cls.debug_client = WSGIClient(Server.create_app(debug=True))

    def setUp(self) -> None:
        """Write the session into temporary solves and daily folders."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)

        self.solves_directory = Path(tmp.name) / 'solves'
        self.daily_directory = self.solves_directory / 'daily'
        self.daily_directory.mkdir(parents=True)

        patchers = [
            patch('term_timer.in_out.DAILY_DIRECTORY', self.daily_directory),
            patch.object(SolveLocation, 'directory', self.solves_directory),
            patch.object(DailyLocation, 'directory', self.daily_directory),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

        solves: list[dict[str, Any]] = [
            {
                'date': 1751570000, 'time': 31 * SECOND,
                'scramble': SCRAMBLE, 'timer': 'csTimer',
                'comment': '<b>cold</b> start',
            },
            {
                'date': 1751576007, 'time': ADVANCED_TIME,
                'scramble': SCRAMBLE, 'moves': MOVES,
                'device': 'GAN12',
            },
            {
                'date': 1751580000, 'time': 40 * SECOND,
                'scramble': SCRAMBLE, 'flag': 'DNF',
            },
        ]
        self.write(self.solves_directory / f'3x3x3-{ SESSION }.json', solves)
        self.write(self.daily_directory / f'3x3x3-{ DAY }.json', solves)

    @staticmethod
    def write(path: Path, solves: list[dict[str, Any]]) -> None:
        """Write a session file."""
        path.write_text(json.dumps(solves), encoding='utf-8')

    def page(self, path: str, *, debug: bool = False) -> str:
        """
        Get a page that must answer 200.

        Returns:
            The body of the page.

        """
        client = self.debug_client if debug else self.client
        status, _headers, body = client.get(path)
        self.assertEqual(status, HTTPStatus.OK, body[:2000])
        return body


class TestAdvancedSolvePage(SolveServerTestCase):
    """The page of a solve recorded by a Bluetooth cube."""

    def setUp(self) -> None:
        """Render the advanced solve once per test."""
        super().setUp()
        self.body = self.page(f'/3/{ SESSION }/2/')

    def test_renders_v2(self) -> None:
        """The V2 skeleton, header and zones are rendered."""
        self.assertIn('/static/v2/css/pages/solve.css', self.body)
        self.assertIn('class="page-header"', self.body)
        for zone in ('summary', 'moves', 'diagnostics', 'charts'):
            self.assertIn(f'data-zone="{ zone }"', self.body)

    def test_breadcrumb(self) -> None:
        """Home, then the session, then the solve itself."""
        self.assertIn('<a href="/">Home</a>', self.body)
        self.assertIn(f'<a href="/3/{ SESSION }/">Test 3x3x3</a>', self.body)
        self.assertIn('aria-current="page">#2</li>', self.body)

    def test_previous_and_next(self) -> None:
        """The neighbour solves are linked and bound to [ and ]."""
        self.assertIn(
            f'href="/3/{ SESSION }/1/" data-key="["', self.body,
        )
        self.assertIn(
            f'href="/3/{ SESSION }/3/" data-key="]"', self.body,
        )

    def test_no_flag_on_an_advanced_solve(self) -> None:
        """The flag cannot be edited, the solve can be deleted."""
        self.assertNotIn('/flag/', self.body)
        self.assertIn(
            f'action="/3/{ SESSION }/2/delete/"'
            ' data-confirm="Permanently delete this solve?"',
            self.body,
        )

    def test_sections_numbered_in_order(self) -> None:
        """Sections are numbered 01, 02... in the document order."""
        numbers = re.findall(
            r'<span class="section-number">(\d+)</span>', self.body,
        )
        self.assertEqual(
            numbers, [f'{ n:02d}' for n in range(1, len(numbers) + 1)],
        )
        self.assertGreaterEqual(len(numbers), 8)

    def test_hero_time(self) -> None:
        """The hero drops the zero minutes and dims the milliseconds."""
        self.assertIn(
            '<div class="solve-hero-time" style="--chars: 6">27'
            '<span class="solve-hero-millis">.357</span>',
            self.body,
        )

    def test_rank_ignores_the_dnf(self) -> None:
        """The fastest valid solve is #1, among the valid solves only."""
        self.assertIn('<b>#1</b> of 2 · top 50%', self.body)

    def test_session_fact_shows_the_cube_size(self) -> None:
        """The cube size is not shadowed by the cube image macro."""
        self.assertIn('<span class="solve-dim">3x3x3</span>', self.body)
        self.assertNotIn('Macro', self.body)

    def test_no_v1_html_escaped(self) -> None:
        """No V1 filter output reaches the page escaped."""
        self.assertIsNone(ESCAPED_V1_RE.search(self.body))

    def test_summary_heads_the_charts_zone(self) -> None:
        """The summary opens the third column, above the charts."""
        zone = self.body.index('data-zone="charts"')
        self.assertLess(
            self.body.index('data-zone="diagnostics"'), zone,
        )
        self.assertLess(zone, self.body.index('id="summary"'))
        self.assertLess(
            self.body.index('id="summary"'), self.body.index('id="charts"'),
        )

    def test_reconstruction_tabs(self) -> None:
        """Time, Percent, Overheads and Optimized, no debug tab."""
        tabs = re.findall(
            r'id="reconstruction-tab-(\w+)"', self.body,
        )
        self.assertEqual(tabs, ['time', 'percent', 'overheads', 'optimized'])

    def test_steps_anchored_once(self) -> None:
        """Each step anchor exists once, in the time panel."""
        anchors = re.findall(r'id="(step-[\w-]+)"', self.body)
        self.assertEqual(len(anchors), len(set(anchors)))
        self.assertIn('step-cross', anchors)
        self.assertIn('step-oll', anchors)

    def test_step_pauses_shown_as_chips(self) -> None:
        """The time panel carries the pauses in the chips."""
        self.assertIn('class="alg-pause"', self.body)

    def test_case_thumbnail(self) -> None:
        """A recognised case is drawn by the cube macro."""
        self.assertRegex(
            self.body, r'<img class="cube" data-size="s" src="/cube/\?',
        )

    def test_charts_have_data(self) -> None:
        """The four charts are drawn by registered kinds, with data."""
        for kind in ('moves-timing', 'steps-tps', 'steps-recognition',
                     'steps-fluency'):
            self.assertIn(f'data-chart="{ kind }"', self.body)
        match = re.search(
            r'<script type="application/json" id="chart-timing-data">'
            r'(.*?)</script>',
            self.body, re.DOTALL,
        )
        self.assertIsNotNone(match)
        data = json.loads(cast('re.Match[str]', match).group(1))
        self.assertEqual(len(data['points']), 80)

    def test_replay_data(self) -> None:
        """The replay reads its moves, timings and step starts as JSON."""
        match = re.search(
            r'<script type="application/json" id="replay-data">'
            r'(.*?)</script>',
            self.body, re.DOTALL,
        )
        self.assertIsNotNone(match)
        data = json.loads(cast('re.Match[str]', match).group(1))
        self.assertEqual(data['puzzle'], '3x3x3')
        self.assertEqual(data['scramble'], SCRAMBLE)
        self.assertIn('Cross', data['index'])
        self.assertTrue(data['timing'])
        self.assertTrue(all(len(item) == 2 for item in data['timing']))

    def test_help_and_confirm_dialogs(self) -> None:
        """The shortcuts help and the confirmation are on the page."""
        self.assertIn('data-help', self.body)
        self.assertIn('data-confirm-dialog', self.body)

    def test_no_inline_script(self) -> None:
        """Every script is external or a JSON data block."""
        for attributes, content in re.findall(
                r'<script([^>]*)>(.*?)</script>', self.body, re.DOTALL):
            if content.strip():
                self.assertIn('application/json', attributes)


class TestSolvePageVariants(SolveServerTestCase):
    """Plain solves, debug, V1 and daily renderings."""

    def test_plain_solve(self) -> None:
        """A timer-only solve: flag actions, no analysis nor replay."""
        body = self.page(f'/3/{ SESSION }/1/')
        self.assertIn(f'action="/3/{ SESSION }/1/flag/"', body)
        self.assertIn('name="flag" value="DNF"', body)
        self.assertNotIn('data-zone="diagnostics"', body)
        self.assertNotIn('data-zone="charts"', body)
        self.assertNotIn('replay-data', body)
        self.assertNotIn(f'href="/3/{ SESSION }/0/"', body)

    def test_comment_escaped(self) -> None:
        """The comment is escaped by the V2 page."""
        body = self.page(f'/3/{ SESSION }/1/')
        self.assertIn('&lt;b&gt;cold&lt;/b&gt; start', body)
        self.assertNotIn('<b>cold</b>', body)

    def test_dnf_has_no_rank(self) -> None:
        """A DNF is not ranked, first nor last."""
        body = self.page(f'/3/{ SESSION }/3/')
        self.assertIsNone(
            re.search(r'<b>#\d+</b> of', body),
        )
        self.assertIn('<div class="solve-hero-time"', body)

    def test_dnf_not_ranked_in_the_v1(self) -> None:
        """The V1 page ranks the valid solves only, the DNF unranked."""
        body = self.page(f'/3/{ SESSION }/3/?v1')
        self.assertNotRegex(body, r'#\d+\s*</div>')
        body = self.page(f'/3/{ SESSION }/2/?v1')
        self.assertRegex(body, r'stat-best">[^<]*27\.357')

    def test_dnf_solve(self) -> None:
        """A DNF offers OK and +2, not DNF again, and no next solve."""
        body = self.page(f'/3/{ SESSION }/3/')
        self.assertIn('name="flag" value=""', body)
        self.assertIn('name="flag" value="+2"', body)
        self.assertNotIn('name="flag" value="DNF"', body)
        self.assertNotIn('data-key="]"', body)

    def test_debug_tabs(self) -> None:
        """Debug adds the raw and issues tabs and the raw moves."""
        body = self.page(f'/3/{ SESSION }/2/', debug=True)
        tabs = re.findall(r'id="reconstruction-tab-(\w+)"', body)
        self.assertEqual(tabs[-2:], ['raw', 'issues'])
        self.assertIn('id="raw-moves"', body)

    def test_v1_kept_for_comparison(self) -> None:
        """?v1 renders the V1 page at the same URL."""
        body = self.page(f'/3/{ SESSION }/2/?v1')
        self.assertIn('/static/css/style.css', body)
        self.assertNotIn('/static/v2/css/pages/solve.css', body)

    def test_daily_breadcrumb(self) -> None:
        """A daily attempt goes back to the daily hub and its day."""
        body = self.page(f'/daily/3/{ DAY }/2/')
        self.assertIn('<a href="/daily/3/">Daily 3x3x3</a>', body)
        self.assertIn(f'<a href="/daily/3/{ DAY }/">{ DAY }</a>', body)
        self.assertIn(
            f'action="/daily/3/{ DAY }/2/delete/"', body,
        )


class TestReconstructionMarkup(unittest.TestCase):
    """The markup feeds the V1 HTML and the V2 tokens alike."""

    def setUp(self) -> None:
        """Analyse the fixture solve."""
        self.solve = solve_54()
        method_applied = cast('Analyser', self.solve.method_applied)
        self.steps = [
            step for step in method_applied.summary
            if step['type'] != 'virtual'
        ]

    def assert_same_moves(self, markup: str, html: str) -> None:
        """Tokens of the markup list the moves of the V1 HTML."""
        self.assertEqual(
            move_texts(alg_tokens(markup)),
            ' '.join(V1_TEXT_RE.findall(html)).split(),
        )

    def test_v1_filters_wrap_the_markup(self) -> None:
        """Each V1 filter is format_line over its markup."""
        for step in self.steps:
            with self.subTest(step=step['name']):
                self.assertEqual(
                    reconstruction_step(step),
                    format_line(reconstruction_markup(step)),
                )
                self.assertEqual(
                    reconstruction_pauses(step, self.solve),
                    format_line(pauses_markup(step, self.solve)),
                )
                self.assertEqual(
                    reconstruction_overheads(step, self.solve),
                    format_line(overheads_markup(step, self.solve)),
                )
                self.assertEqual(
                    optimized_step(step)[0],
                    format_line(optimized_markup(step)[0]),
                )

    def test_tokens_match_the_v1_html(self) -> None:
        """The V2 tokens show the moves the V1 HTML shows."""
        for step in self.steps:
            with self.subTest(step=step['name']):
                self.assert_same_moves(
                    reconstruction_markup(step), reconstruction_step(step),
                )
                self.assert_same_moves(
                    pauses_markup(step, self.solve),
                    reconstruction_pauses(step, self.solve),
                )
                self.assert_same_moves(
                    overheads_markup(step, self.solve),
                    reconstruction_overheads(step, self.solve),
                )
                self.assert_same_moves(
                    optimized_markup(step)[0], optimized_step(step)[0],
                )


class TestSplitTime(unittest.TestCase):
    """The hero time split into its head and its milliseconds."""

    def test_zero_units_dropped(self) -> None:
        """Zero minutes go, the leading zero of the head too."""
        self.assertEqual(split_time(25_108_000_000), ('25', '.108'))
        self.assertEqual(split_time(5_108_000_000), ('5', '.108'))
        self.assertEqual(split_time(62_345_000_000), ('1:02', '.345'))
        self.assertEqual(
            split_time(3_723_000_000_000), ('1:02:03', '.000'),
        )

    def test_dnf(self) -> None:
        """A zero time is a DNF, without milliseconds."""
        self.assertEqual(split_time(0), ('DNF', ''))


class TestTones(unittest.TestCase):
    """Tones of the metrics, counts and fluency."""

    def test_metric_tone(self) -> None:
        """The normalize_value statuses map onto the tones."""
        method_applied = cast('Analyser', solve_54().method_applied)
        for status, tone in (('success', 'good'), ('caution', 'warn'),
                             ('warning', 'bad'), ('', '')):
            with (self.subTest(status=status),
                  patch.object(method_applied, 'normalize_value',
                               return_value=status)):
                self.assertEqual(
                    metric_tone(1, method_applied, 'moves', 'OLL'), tone,
                )

    def test_count_tone(self) -> None:
        """None is good, up to the bad count warns, above is bad."""
        self.assertEqual(count_tone(0, 2), 'good')
        self.assertEqual(count_tone(2, 2), 'warn')
        self.assertEqual(count_tone(3, 2), 'bad')

    def test_fluency_tone(self) -> None:
        """Good from 75, caution from 50."""
        self.assertEqual(fluency_tone(75), 'good')
        self.assertEqual(fluency_tone(74), 'warn')
        self.assertEqual(fluency_tone(50), 'warn')
        self.assertEqual(fluency_tone(49), 'bad')
