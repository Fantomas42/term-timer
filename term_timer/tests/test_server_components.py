"""Tests for the components: algorithm tokens, escaping and catalogue."""
import re
import tempfile
import unittest
from pathlib import Path
from typing import TYPE_CHECKING
from typing import cast
from unittest.mock import Mock

from bottle import TEMPLATE_PATH
from bottle import TEMPLATES

from term_timer.constants import STATIC_DIRECTORY
from term_timer.constants import TEMPLATES_DIRECTORY
from term_timer.formatter import format_alg_pauses
from term_timer.formatter import format_grade
from term_timer.server.app import Server
from term_timer.server.filters import DEFAULT_TRIGGER_SLOT
from term_timer.server.filters import TRIGGER_NAMES
from term_timer.server.filters import TRIGGER_SLOTS
from term_timer.server.filters import AlgMove
from term_timer.server.filters import AlgPause
from term_timer.server.filters import AlgToken
from term_timer.server.filters import AlgTrigger
from term_timer.server.filters import alg_text
from term_timer.server.filters import alg_tokens
from term_timer.server.filters import algorithm_tokens
from term_timer.server.filters import grade_tone
from term_timer.server.views.base import View
from term_timer.server.views.styleguide import FIXTURE_RECONSTRUCTION
from term_timer.tests.test_server_daily import WSGIClient
from term_timer.triggers import TRIGGERS

if TYPE_CHECKING:
    from term_timer.methods.annotations import StepSummary


def move_texts(tokens: list[AlgToken]) -> list[str]:
    """
    Every move of the tokens, triggers expanded, pauses as a dot.

    Returns:
        The move texts in order.

    """
    texts: list[str] = []
    for token in tokens:
        if isinstance(token, AlgTrigger):
            texts.extend(move.move for move in token.moves)
        elif isinstance(token, AlgPause):
            texts.append('.')
        else:
            texts.append(token.move)
    return texts


class AlgTokensTestCase(unittest.TestCase):
    """The block markup of the formatters parsed into tokens."""

    def test_empty_value(self) -> None:
        """An empty algorithm has no token."""
        self.assertEqual(alg_tokens(''), [])

    def test_plain_moves(self) -> None:
        """Moves outside any block carry no variant."""
        self.assertEqual(
            alg_tokens("R U R'"),
            [AlgMove('R'), AlgMove('U'), AlgMove("R'")],
        )

    def test_move_variants(self) -> None:
        """Every move block maps to its variant, rotations merged."""
        self.assertEqual(
            alg_tokens(
                '[pre-auf]U[/pre-auf] [slice]M[/slice] [wide]r[/wide]'
                ' [rotation_y]y[/rotation_y] [deletion]D[/deletion]'
                ' [addition]D2[/addition] [post-auf]U2[/post-auf]',
            ),
            [
                AlgMove('U', 'pre-auf'),
                AlgMove('M', 'slice'),
                AlgMove('r', 'wide'),
                AlgMove('y', 'rotation'),
                AlgMove('D', 'deletion'),
                AlgMove('D2', 'addition'),
                AlgMove('U2', 'post-auf'),
            ],
        )

    def test_multiple_moves_in_a_block(self) -> None:
        """Each move of a non-trigger block gets the block variant."""
        self.assertEqual(
            alg_tokens('[pre-auf]R U[/pre-auf]'),
            [AlgMove('R', 'pre-auf'), AlgMove('U', 'pre-auf')],
        )

    def test_unknown_markup_is_a_plain_move(self) -> None:
        """A block that is neither a variant nor a trigger is dropped."""
        self.assertEqual(
            alg_tokens('[unknown-markup]R U[/unknown-markup]'),
            [AlgMove('R'), AlgMove('U')],
        )

    def test_trigger(self) -> None:
        """A trigger keeps its slug, display name, slot and moves."""
        self.assertEqual(
            alg_tokens("F [sexy-move]R U R' U'[/sexy-move] F'"),
            [
                AlgMove('F'),
                AlgTrigger(
                    'sexy-move', 'Sexy Move', 1,
                    (AlgMove('R'), AlgMove('U'), AlgMove("R'"),
                     AlgMove("U'")),
                ),
                AlgMove("F'"),
            ],
        )

    def test_pauses(self) -> None:
        """Execution, recognition and bare pauses are pause tokens."""
        self.assertEqual(
            alg_tokens(
                'R . [pause].[/pause] U [reco-pause].[/reco-pause]',
            ),
            [
                AlgMove('R'),
                AlgPause('execution'),
                AlgPause('execution'),
                AlgMove('U'),
                AlgPause('recognition'),
            ],
        )

    def test_pause_markup_of_the_formatter(self) -> None:
        """The pause markup format_alg_pauses writes is understood."""
        markup = format_alg_pauses(
            "R U . R'",
            Mock(pause_threshold=1),
            cast('StepSummary', {'post_pause': 2}),
            multiple=True,
        )
        self.assertEqual(
            [token.kind for token in alg_tokens(markup)],
            ['move', 'move', 'pause', 'move', 'pause', 'pause'],
        )


class AlgorithmTokensTestCase(unittest.TestCase):
    """Tokens of a whole algorithm, the default triggers marked."""

    def test_aufs_are_marked(self) -> None:
        """A leading and a trailing U are AUFs by default."""
        tokens = algorithm_tokens("U F R U R' U' F' U2")
        self.assertEqual(tokens[0], AlgMove('U', 'pre-auf'))
        self.assertEqual(tokens[-1], AlgMove('U2', 'post-auf'))
        self.assertEqual(tokens[2].kind, 'trigger')

    def test_aufs_off_for_a_scramble(self) -> None:
        """A scramble has no AUF."""
        tokens = algorithm_tokens("U F R U R' U' F' U2", aufs=False)
        self.assertEqual(tokens[0], AlgMove('U'))
        self.assertEqual(tokens[-1], AlgMove('U2'))

    def test_text_drops_pauses(self) -> None:
        """The copied text is the moves only, triggers expanded."""
        self.assertEqual(
            alg_text(alg_tokens(FIXTURE_RECONSTRUCTION)),
            "U' R U R' U' M' y U U2 R U' R' R U R' U R U2 R' F U2",
        )


class TriggerTableTestCase(unittest.TestCase):
    """Every known trigger has a name and a colour slot."""

    def test_every_trigger_has_a_name(self) -> None:
        """The names come from the same patterns as the triggers."""
        self.assertEqual(set(TRIGGER_NAMES), set(TRIGGERS))

    def test_every_trigger_has_a_slot(self) -> None:
        """No trigger falls back silently to the default slot."""
        self.assertEqual(set(TRIGGER_SLOTS), set(TRIGGERS))
        self.assertTrue(
            set(TRIGGER_SLOTS.values()) <= {1, 2, 3, DEFAULT_TRIGGER_SLOT},
        )


class GradeToneTestCase(unittest.TestCase):
    """Letter grades mapped to the grade tones."""

    def test_plus_grades_share_the_tone(self) -> None:
        """A+ and A are the same tone."""
        self.assertEqual(grade_tone('A+'), 'grade-a')
        self.assertEqual(grade_tone('A'), 'grade-a')
        self.assertEqual(grade_tone('S'), 'grade-s')

    def test_no_grade(self) -> None:
        """Without a grade there is no tone."""
        self.assertEqual(grade_tone(''), '')

    def test_every_grade_has_a_styled_tone(self) -> None:
        """Each grade format_grade can return has its tone in base.css."""
        base = (STATIC_DIRECTORY / 'css' / 'base.css').read_text(
            encoding='utf-8',
        )
        for score in range(25):
            tone = grade_tone(format_grade(score))
            with self.subTest(tone=tone):
                self.assertIn(f'[data-tone="{ tone }"]', base)


class AutoescapeTestCase(unittest.TestCase):
    """Every template escapes its values by default."""

    def test_rendering(self) -> None:
        """A page and a component escape a value, never render it raw."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / 'components').mkdir()
        for name in ('probe_escape.html', 'components/probe_escape.html'):
            (root / name).write_text('{{ value }}', encoding='utf-8')
        TEMPLATE_PATH.insert(0, str(root))
        self.addCleanup(TEMPLATE_PATH.remove, str(root))
        self.addCleanup(TEMPLATES.clear)

        value = '<script>alert(1)</script>'
        for name in ('probe_escape.html', 'components/probe_escape.html'):
            with self.subTest(name=name):
                self.assertEqual(
                    View.template(name, value=value),
                    '&lt;script&gt;alert(1)&lt;/script&gt;',
                )


class ComponentCatalogueTestCase(unittest.TestCase):
    """The component catalogue of /styleguide/, rendered by the app."""

    status: int
    body: str

    @classmethod
    def setUpClass(cls) -> None:
        """Render the catalogue once."""
        if str(TEMPLATES_DIRECTORY) not in map(str, TEMPLATE_PATH):
            TEMPLATE_PATH.insert(0, TEMPLATES_DIRECTORY)
        cls.status, _headers, cls.body = WSGIClient(
            Server.create_app(debug=False),
        ).get('/styleguide/')

    def test_page_renders(self) -> None:
        """The catalogue page answers."""
        self.assertEqual(self.status, 200)

    def test_component_sections(self) -> None:
        """Every component has its numbered section."""
        for number, slug in enumerate(
                ('alg', 'stat', 'badge', 'tabs', 'table', 'cube', 'chart',
                 'header', 'dialog', 'punchcard', 'spark'),
                start=1):
            with self.subTest(slug=slug):
                self.assertIn(f'id="component-{ slug }"', self.body)
                self.assertIn(
                    f'<span class="section-number">{ number:02d}</span>',
                    self.body,
                )

    def test_chart_kinds(self) -> None:
        """Every kind of the charts.js registry is shown."""
        for kind in ('moves-timing', 'steps-tps', 'steps-recognition',
                     'steps-fluency', 'form', 'trend', 'distribution',
                     'career'):
            with self.subTest(kind=kind):
                self.assertIn(f'data-chart="{ kind }"', self.body)

    def test_page_header(self) -> None:
        """The header shows its breadcrumb, the current page unlinked."""
        self.assertIn('<h2 class="page-header-title">Solve', self.body)
        self.assertIn('aria-current="page">#1181</li>', self.body)

    def test_catalogue_has_one_title(self) -> None:
        """The catalogue opens on the page header, its only h1."""
        self.assertEqual(self.body.count('<h1'), 1)
        self.assertIn('<h1 class="page-header-title">Design', self.body)
        self.assertNotIn('styleguide-header', self.body)

    def test_dialogs(self) -> None:
        """The help and the confirmation dialogs are rendered."""
        self.assertIn('data-help', self.body)
        self.assertIn('data-confirm-dialog', self.body)

    def test_alg_chips(self) -> None:
        """Triggers, variants and pauses reach the markup."""
        self.assertIn(
            '<span class="alg-trigger" data-slot="1"'
            ' data-name="Sexy Move">',
            self.body,
        )
        self.assertIn('data-variant="pre-auf" title="Pre-AUF"', self.body)
        self.assertIn('data-kind="recognition"', self.body)

    def test_copy_buttons_only_where_asked(self) -> None:
        """The reconstruction fixture has no copy button."""
        self.assertEqual(self.body.count('data-copy-label='), 6)
        self.assertIn('data-copy-key="s"', self.body)

    def test_copy_counts_moves_of_algorithms_only(self) -> None:
        """Only the copy of an algorithm reports its move count."""
        buttons = re.findall(r'<button[^>]*data-copy=[^>]*>', self.body)
        counted = [button for button in buttons if 'data-copy-moves' in button]
        self.assertEqual(len(counted), 4)
        for button in buttons:
            with self.subTest(button=button):
                self.assertEqual(
                    'data-copy-moves' in button,
                    'data-copy-label="command"' not in button,
                )

    def test_values_are_escaped(self) -> None:
        """A value is escaped, a trusted icon is not."""
        self.assertIn('&lt;b&gt;escaped&lt;/b&gt;', self.body)
        self.assertNotIn('<b>escaped</b>', self.body)
        self.assertIn('<svg class="nav-icon" viewBox="0 0 24 24"'
                      ' aria-hidden="true"><rect', self.body)

    def test_cube_url(self) -> None:
        """The cube macro builds an encoded, ordered query string."""
        self.assertIn(
            'src="/cube/?c=3&amp;case=R+U+R%27+U+R+U2+R%27&amp;m=oll'
            '&amp;s=96"',
            self.body,
        )

    def test_charts_and_scripts(self) -> None:
        """Charts carry their kind and JSON data, no inline code."""
        self.assertIn('data-chart="moves-timing"', self.body)
        self.assertIn(
            '<script type="application/json" id="styleguide-tps-data">',
            self.body,
        )
        self.assertIn('/static/js/charts.js', self.body)
        self.assertIn('/static/js/ui.js', self.body)

    def test_new_chart_data(self) -> None:
        """The charts of the dashboard carry their JSON data and options."""
        for chart in ('form', 'trend', 'distribution', 'career'):
            with self.subTest(chart=chart):
                self.assertIn(
                    '<script type="application/json"'
                    f' id="styleguide-{ chart }-data">',
                    self.body,
                )
        self.assertIn('data-ratio="panorama"', self.body)
        self.assertIn('class="chart-key" data-series="dot"', self.body)
        self.assertIn('class="chart-key" data-series="4"', self.body)

    def test_punchcard(self) -> None:
        """Both punchcards: a year of weeks, capped, then filling."""
        self.assertEqual(self.body.count('<figure class="punchcard"'), 2)
        self.assertEqual(self.body.count('class="punchcard" data-fill'), 1)
        self.assertIn('style="--weeks: 53; --recent: 27"', self.body)
        self.assertEqual(
            self.body.count('<span class="punchcard-cell" data-level='),
            2 * (53 * 7 + 5),
        )

    def test_spark_command_lookup(self) -> None:
        """The sparklines, the command to copy and the lookup on /."""
        self.assertEqual(self.body.count('<svg class="spark"'), 2)
        self.assertIn('<svg class="spark" viewBox="0 0 100 24"'
                      ' preserveAspectRatio="none" role="img"'
                      ' aria-label="Last 30 seeded times" data-tone="warn">',
                      self.body)
        self.assertIn('data-copy="term-timer train -s oll"', self.body)
        self.assertIn('data-lookup', self.body)
        self.assertIn('for="lookup-input" data-key="/"', self.body)

    def test_zones(self) -> None:
        """Squares of every zone and a DNF, the large ones linked."""
        self.assertEqual(self.body.count('<span class="zones" data-size='), 3)
        self.assertEqual(self.body.count('data-zone="dnf"'), 4)
        self.assertEqual(
            self.body.count('<a class="zones-item" href="#component-zones"'),
            5,
        )
        self.assertIn('<span class="zones-time">19.590</span>', self.body)
        self.assertIn('class="zones-legend"', self.body)

    def test_diagnostic(self) -> None:
        """Findings toned by severity, command and frequency when given."""
        diagnostics = self.body.split('id="component-diagnostic"', 1)[1]

        for tone in ('bad', 'warn', 'info', 'muted'):
            self.assertIn(f'<li class="diagnostic" data-tone="{ tone }">',
                          diagnostics)
        self.assertEqual(diagnostics.count('% of attempts'), 2)
        self.assertEqual(diagnostics.count('class="diagnostic-impact"'), 3)
        self.assertIn('data-copy="term-timer train -s cross"', diagnostics)

    def test_hero_time(self) -> None:
        """Times fitted on their length, a dash, a DNF, rule and flush."""
        hero = self.body.split('id="component-hero-time"', 1)[1]

        self.assertIn(
            '<div class="hero-time-value" style="--chars: 6">25'
            '<span class="hero-time-millis">.108</span>',
            hero,
        )
        self.assertIn('style="--chars: 8">1:02', hero)
        self.assertIn('<div class="hero-time-value" style="--chars: 2">—',
                      hero)
        self.assertIn('DNF<span class="hero-time-millis"></span>', hero)
        self.assertIn('<div class="hero-time" data-rule>', hero)
        self.assertIn('<div class="hero-time" data-flush>', hero)
        self.assertIn('<div class="hero-time-meta" data-tone="bad">', hero)

    def test_tabs_and_table(self) -> None:
        """Tabs are ARIA tabs; the table is sortable."""
        self.assertIn('role="tablist" aria-label="Reconstruction view"',
                      self.body)
        self.assertEqual(self.body.count('role="tabpanel"'), 3)
        self.assertIn('<table class="table-grid" data-sortable>', self.body)
        self.assertIn('<div class="toast" role="status"', self.body)
