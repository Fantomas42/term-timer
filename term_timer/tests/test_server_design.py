"""Tests for the V2 design system: theme, generator and lint."""
import tempfile
import unittest
from pathlib import Path

from term_timer.server.design import THEME_FILE
from term_timer.server.design import THEME_STYLESHEET
from term_timer.server.design import DesignTheme
from term_timer.server.design.__main__ import check
from term_timer.server.design.__main__ import generate
from term_timer.server.design.lint import DesignLint

MINIMAL_THEME = """
[palette]
black = '#000000'
white = '#ffffff'
grey = '#777777'

[roles]
bg = 'black'
text = 'white'
faint = 'grey'

[type.fluid]
min-size = 16
max-size = 22
min-viewport = 390
max-viewport = 3440

[type.families]
font-sans = 'sans-serif'

[type.scale]
step-0 = '1rem'

[space]
space-1 = '0.25rem'

[line]
hairline = '1px'

[motion]
fast = '120ms'

[[contrast]]
text = 'text'
background = 'bg'
level = 'text'
"""


class DesignThemeTestCase(unittest.TestCase):
    """Theme loading, contrast measure and stylesheet rendering."""

    def load(self, source: str) -> DesignTheme:
        """
        Load a theme written in a temporary file.

        Returns:
            The loaded theme.

        """
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / 'theme.toml'
        path.write_text(source, encoding='utf-8')
        return DesignTheme.load(path)

    def test_committed_stylesheet_is_generated_from_the_theme(self) -> None:
        """The committed theme.css is exactly the generator output."""
        self.assertEqual(
            THEME_STYLESHEET.read_text(encoding='utf-8'),
            DesignTheme.load().stylesheet(),
        )

    def test_theme_contrasts_pass(self) -> None:
        """Every declared pair of the real theme reaches its level."""
        failing = [
            (check.text, check.background, round(check.ratio, 2))
            for check in DesignTheme.load().contrast_checks()
            if not check.passed
        ]
        self.assertEqual(failing, [])

    def test_contrast_ratio_bounds(self) -> None:
        """Black on white is 21:1, a colour on itself 1:1."""
        self.assertAlmostEqual(
            DesignTheme.contrast_ratio('#000000', '#ffffff'), 21.0,
        )
        self.assertAlmostEqual(
            DesignTheme.contrast_ratio('#777777', '#777777'), 1.0,
        )

    def test_root_size_is_linear_between_bounds(self) -> None:
        """The clamp reaches 16px at 390px wide and 22px at 3440px."""
        self.assertEqual(
            self.load(MINIMAL_THEME).root_size(),
            'clamp(16px, 15.23px + 0.1967vw, 22px)',
        )

    def test_roles_resolve_to_palette_variables(self) -> None:
        """A role is rendered as a reference to its palette colour."""
        stylesheet = self.load(MINIMAL_THEME).stylesheet()
        self.assertIn('--bg: var(--black);', stylesheet)
        self.assertIn('--black: #000000;', stylesheet)
        self.assertIn(
            '@layer theme, base, layout, components, pages;', stylesheet,
        )

    def test_unknown_palette_colour_is_rejected(self) -> None:
        """A role naming a missing colour fails at load time."""
        source = MINIMAL_THEME.replace("text = 'white'", "text = 'snow'")
        with self.assertRaisesRegex(ValueError, 'snow'):
            self.load(source)

    def test_unknown_contrast_level_is_rejected(self) -> None:
        """A contrast pair must use a known level."""
        source = MINIMAL_THEME.replace("level = 'text'", "level = 'huge'")
        with self.assertRaisesRegex(ValueError, 'huge'):
            self.load(source)


class DesignCommandTestCase(unittest.TestCase):
    """The generate and check commands."""

    def setUp(self) -> None:
        """Work in a temporary folder."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.target = self.folder / 'theme.css'

    def test_generate_then_check(self) -> None:
        """A freshly generated stylesheet passes the check."""
        self.assertEqual(generate(THEME_FILE, self.target), 0)
        self.assertEqual(check(THEME_FILE, self.target), 0)

    def test_check_detects_a_stale_stylesheet(self) -> None:
        """A hand-edited stylesheet fails the check."""
        generate(THEME_FILE, self.target)
        self.target.write_text(
            self.target.read_text(encoding='utf-8') + '/* edit */',
            encoding='utf-8',
        )
        self.assertEqual(check(THEME_FILE, self.target), 1)

    def test_generate_refuses_a_failing_contrast(self) -> None:
        """Under its level, a pair blocks the generation."""
        source = self.folder / 'theme.toml'
        source.write_text(
            MINIMAL_THEME.replace("text = 'text'", "text = 'faint'"),
            encoding='utf-8',
        )
        self.assertEqual(generate(source, self.target), 1)
        self.assertFalse(self.target.exists())


class DesignLintTestCase(unittest.TestCase):
    """The rules enforced on the V2 stylesheets and templates."""

    def setUp(self) -> None:
        """Build an empty V2 tree in a temporary folder."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.css = root / 'css'
        self.templates = root / 'templates'
        (self.css / 'components').mkdir(parents=True)
        (self.css / 'pages').mkdir()
        (self.templates / 'v2').mkdir(parents=True)
        self.write(self.css / 'components' / 'alg.css', '.alg {}')

    @staticmethod
    def write(path: Path, content: str) -> None:
        """Write a fixture file."""
        path.write_text(content, encoding='utf-8')

    def messages(self) -> list[str]:
        """
        Run the lint on the temporary tree.

        Returns:
            The violation messages.

        """
        lint = DesignLint(self.css, self.templates)
        return [violation.message for violation in lint.run()]

    def test_real_tree_is_clean(self) -> None:
        """The shipped V2 stylesheets and templates follow the rules."""
        self.assertEqual([str(v) for v in DesignLint().run()], [])

    def test_theme_stylesheet_may_hold_literals(self) -> None:
        """Only the generated theme.css defines raw colours."""
        self.write(self.css / 'theme.css', ':root { --x: #ffffff; }')
        self.assertEqual(self.messages(), [])

    def test_literal_colours_are_rejected(self) -> None:
        """Hexadecimal colours and colour functions are forbidden."""
        self.write(
            self.css / 'base.css',
            'a { color: #fff; background: rgb(0 0 0 / 0.5); }',
        )
        self.assertEqual(len(self.messages()), 2)

    def test_colour_mix_keyword_is_allowed(self) -> None:
        """An interpolation space named in color-mix is not a colour."""
        self.write(
            self.css / 'base.css',
            'a { background: color-mix(in oklab, var(--x) 10%, transparent); }',
        )
        self.assertEqual(self.messages(), [])

    def test_font_sizes_come_from_the_scale(self) -> None:
        """Literal sizes are rejected, scale variables and em accepted."""
        self.write(
            self.css / 'base.css',
            'a { font-size: 14px; }\n'
            'b { font: 600 1.2rem / 1 var(--font-sans); }\n'
            'i { font-size: var(--step-0); }\n'
            'kbd { font-size: 0.75em; }\n',
        )
        self.assertEqual(len(self.messages()), 2)

    def test_component_selectors_start_with_their_root(self) -> None:
        """A component file only styles its own root class."""
        self.write(
            self.css / 'components' / 'alg.css',
            '.alg, .alg-move:hover, .alg[data-size="s"] {}\n'
            '.algorithm {}\n'
            '[data-tone="good"] {}\n',
        )
        self.assertEqual(
            self.messages(),
            [
                'selector outside its root .alg: .algorithm',
                'selector outside its root .alg: [data-tone="good"]',
            ],
        )

    def test_context_selectors_between_components_are_rejected(self) -> None:
        """A component never styles another component's classes."""
        self.write(
            self.css / 'components' / 'step.css',
            '.step .alg-move {}',
        )
        self.assertEqual(
            self.messages(),
            ['context selector reaching into .alg-move: .step .alg-move'],
        )

    def test_keyframes_and_at_rules_are_skipped(self) -> None:
        """Keyframe steps are no selectors; media blocks are traversed."""
        self.write(
            self.css / 'components' / 'alg.css',
            '@keyframes alg-flash { 0% { opacity: 0; } to { opacity: 1; } }\n'
            '@media (max-width: 40rem) { .alg { gap: 0; } p { gap: 0; } }\n',
        )
        self.assertEqual(
            self.messages(), ['selector outside its root .alg: p'],
        )

    def test_inline_scripts_are_rejected(self) -> None:
        """External scripts and JSON data pass, inline code does not."""
        self.write(
            self.templates / 'v2' / 'page.html',
            '<script src="/static/v2/js/charts.js" type="module"></script>\n'
            '<script type="application/json">{"a": 1}</script>\n'
            '<script>new Chart(ctx, {});</script>\n',
        )
        self.assertEqual(self.messages(), ['inline script'])

    def test_style_attributes_only_set_custom_properties(self) -> None:
        """A style attribute may pass values, never style directly."""
        self.write(
            self.templates / 'v2' / 'skeleton.html',
            '<div style="--share: 12%; --reco: 3%"></div>\n'
            '<div style="width: 12%"></div>\n',
        )
        self.assertEqual(
            self.messages(),
            ['style attribute beyond custom properties: width: 12%'],
        )
