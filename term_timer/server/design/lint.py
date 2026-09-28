"""
Lint of the V2 stylesheets and templates.

Stylesheets, except the generated theme.css:
- no literal colour (hexadecimal or colour function) in a value;
- no literal font size (px, rem, pt, viewport units), only the scale
  custom properties or sizes relative to the parent (em, %);
- a component or page file only styles selectors starting with its own
  root class, named after the file;
- no selector reaches into another component's classes.

A custom property may hold a size fitted to its container, the hero
time's calc(190cqi / var(--chars)): a size computed from the content is
no step of the scale, and the font-size reading it stays on the rule.

Templates of templates/v2/:
- no inline script, only external ones, JSON data blocks and the import
  map;
- no static file linked by a literal URL: the asset filter versions it,
  but the fonts, whose preload must match the url() of base.css;
- a style attribute only sets custom properties;
- no dict method read as a value: Jinja resolves algorithm.copy to the
  method of the dict before its key, always true;
- no imported macro named like a variable of its page context: the
  macro hides the variable in the whole template. A page is checked
  against the context its view renders, the skeleton every page extends
  against all of them; a component, imported without context, is not.
"""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from typing import get_type_hints
from typing import is_typeddict

from term_timer.constants import TEMPLATES_DIRECTORY
from term_timer.server.design import CSS_DIRECTORY
from term_timer.server.design import THEME_STYLESHEET
from term_timer.server.views.base import View

SCOPED_DIRECTORIES: Final = ('components', 'pages')

COMMENT_RE: Final = re.compile(r'/\*.*?\*/', re.DOTALL)
DECLARATION_RE: Final = re.compile(r'([\w-]+)\s*:\s*([^;{}]+);')
HEX_RE: Final = re.compile(r'#[0-9a-fA-F]{3,8}\b')
COLOUR_FUNCTION_RE: Final = re.compile(
    r'\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch)\(',
)
LITERAL_SIZE_RE: Final = re.compile(
    r'\d(?:\.\d+)?(?:px|rem|pt|vw|vh|vmin|vmax|cqi|cqw)\b',
)
CLASS_RE: Final = re.compile(r'\.(-?[_a-zA-Z][\w-]*)')

SCRIPT_RE: Final = re.compile(
    r'<script\b([^>]*)>(.*?)</script>', re.DOTALL | re.IGNORECASE,
)
STYLE_ATTRIBUTE_RE: Final = re.compile(r'\sstyle="([^"]*)"')
STATIC_LINK_RE: Final = re.compile(r'(?:href|src)="(/static/[^"]*)"')
FONTS_URL: Final = '/static/v2/fonts/'
CUSTOM_PROPERTY_RE: Final = re.compile(r'^\s*--[\w-]+\s*:')
JINJA_RE: Final = re.compile(r'{{.*?}}|{%.*?%}', re.DOTALL)
DICT_METHOD_RE: Final = re.compile(
    r'\b(\w+)\.(clear|copy|get|items|keys|pop|popitem|setdefault|update'
    r'|values)\b(?!\s*\()',
)
MACRO_IMPORT_RE: Final = re.compile(
    r'{%-?\s*from\s+\S+\s+import\s+(.*?)\s*-?%}', re.DOTALL,
)

# Variables every view adds to its context (View.as_view and template).
VIEW_KEYS: Final = frozenset({'DEBUG', 'navigation', 'now'})


@dataclass(frozen=True)
class LintViolation:
    """One broken rule, located in its file."""

    path: Path
    line: int
    message: str

    def __str__(self) -> str:
        """
        Format the violation like a compiler message.

        Returns:
            path:line: message

        """
        return f'{ self.path }:{ self.line }: { self.message }'


def line_of(text: str, position: int) -> int:
    """
    Line number of a character position.

    Returns:
        The 1-based line number.

    """
    return text.count('\n', 0, position) + 1


class DesignLint:
    """Check the V2 stylesheets and templates against the design rules."""

    def __init__(self, css_directory: Path = CSS_DIRECTORY,
                 templates_directory: Path = TEMPLATES_DIRECTORY,
                 contexts: dict[str, frozenset[str]] | None = None) -> None:
        """
        Locate the files to check.

        Args:
            css_directory: Root of the V2 stylesheets.
            templates_directory: Root of the templates.
            contexts: Variables each page receives, by template name; by
                default read from the views.

        """
        self.css_directory = css_directory
        self.templates_directory = templates_directory
        if contexts is None:
            contexts = self.view_contexts()
        self.contexts = contexts

    @staticmethod
    def view_contexts() -> dict[str, frozenset[str]]:
        """
        Variables each V2 page receives from its views.

        A page gets the keys of the context type its views return, and
        those every view adds; the skeleton, extended by every page, gets
        them all.

        Returns:
            The context keys by template name.

        """
        contexts: dict[str, set[str]] = {}
        views = [View]
        while views:
            view = views.pop()
            views.extend(view.__subclasses__())
            context = get_type_hints(view.get_context).get('return')
            if (not view.template_name or context is None
                    or not is_typeddict(context)):
                continue
            keys = contexts.setdefault(view.template_name, set(VIEW_KEYS))
            keys.update(context.__required_keys__)
            keys.update(context.__optional_keys__)
        contexts['v2/skeleton.html'] = set().union(*contexts.values())
        return {name: frozenset(keys) for name, keys in contexts.items()}

    def component_roots(self) -> set[str]:
        """
        Root classes of the components, named after their files.

        Returns:
            The set of root class names.

        """
        return {
            path.stem
            for path in (self.css_directory / 'components').glob('*.css')
        }

    def stylesheets(self) -> list[Path]:
        """
        V2 stylesheets to check, the generated theme excluded.

        Returns:
            The sorted list of paths.

        """
        return sorted(
            path for path in self.css_directory.rglob('*.css')
            if path.name != THEME_STYLESHEET.name
        )

    def templates(self) -> list[Path]:
        """
        V2 templates to check.

        Returns:
            The sorted list of paths.

        """
        return sorted((self.templates_directory / 'v2').rglob('*.html'))

    def run(self) -> list[LintViolation]:
        """
        Check every V2 stylesheet and template.

        Returns:
            All violations found, file by file.

        """
        roots = self.component_roots()
        violations: list[LintViolation] = []
        for path in self.stylesheets():
            violations.extend(self.check_stylesheet(
                path, path.read_text(encoding='utf-8'), roots,
            ))
        for path in self.templates():
            text = path.read_text(encoding='utf-8')
            violations.extend(self.check_template(path, text))
            violations.extend(self.check_expressions(
                path, text, self.page_context(path),
            ))
        return violations

    @staticmethod
    def scope_of(path: Path) -> str:
        """
        Root class a stylesheet is restricted to, if any.

        Returns:
            The file stem for a component or page file, else ''.

        """
        if path.parent.name in SCOPED_DIRECTORIES:
            return path.stem
        return ''

    @staticmethod
    def blank_comments(text: str) -> str:
        """
        Replace comments by spaces, keeping every position and line.

        Returns:
            The text without comment content.

        """
        return COMMENT_RE.sub(
            lambda match: re.sub(r'[^\n]', ' ', match.group()), text,
        )

    def check_stylesheet(self, path: Path, text: str,
                         roots: set[str]) -> list[LintViolation]:
        """
        Check the values and selectors of one stylesheet.

        Returns:
            The violations found in the stylesheet.

        """
        text = self.blank_comments(text)
        violations = self.check_values(path, text)
        violations.extend(self.check_selectors(path, text, roots))
        return violations

    @staticmethod
    def check_values(path: Path, text: str) -> list[LintViolation]:
        """
        Forbid literal colours and literal font sizes.

        Returns:
            The violations found in the declarations.

        """
        violations: list[LintViolation] = []
        for match in DECLARATION_RE.finditer(text):
            name, value = match.group(1), match.group(2)
            line = line_of(text, match.start())
            if HEX_RE.search(value) or COLOUR_FUNCTION_RE.search(value):
                violations.append(LintViolation(
                    path, line, f'literal colour in { name }: { value }',
                ))
            if name in {'font', 'font-size'} and LITERAL_SIZE_RE.search(
                    value):
                violations.append(LintViolation(
                    path, line,
                    f'font size off the scale in { name }: { value }',
                ))
        return violations

    def check_selectors(self, path: Path, text: str,
                        roots: set[str]) -> list[LintViolation]:
        """
        Enforce the scoping of component and page selectors.

        Returns:
            The violations found in the selectors.

        """
        scope = self.scope_of(path)
        violations: list[LintViolation] = []
        blocks: list[str] = []
        start = 0
        for position, character in enumerate(text):
            if character == '}':
                if blocks:
                    blocks.pop()
                start = position + 1
            elif character == ';':
                start = position + 1
            elif character == '{':
                prelude = text[start:position].strip()
                start = position + 1
                if prelude.startswith('@'):
                    blocks.append(prelude.split()[0])
                    continue
                blocks.append('rule')
                if '@keyframes' in blocks:
                    continue
                line = line_of(text, position)
                violations.extend(
                    LintViolation(path, line, message)
                    for message in self.selector_errors(
                        prelude, scope, roots,
                    )
                )
        return violations

    @staticmethod
    def owns(root: str, name: str) -> bool:
        """
        Whether a class belongs to a component root.

        Returns:
            True for the root class itself or one of its sub-classes.

        """
        return name == root or name.startswith(f'{ root }-')

    def selector_errors(self, prelude: str, scope: str,
                        roots: set[str]) -> list[str]:
        """
        Check one selector list against the scope of its file.

        Returns:
            One message per broken rule.

        """
        errors: list[str] = []
        for part in prelude.split(','):
            selector = part.strip()
            classes = CLASS_RE.findall(selector)
            if scope and not (
                    classes and selector.startswith(f'.{ classes[0] }')
                    and self.owns(scope, classes[0])):
                errors.append(
                    f'selector outside its root .{ scope }: { selector }',
                )
            foreign = [
                name for name in classes
                if not (scope and self.owns(scope, name))
                and any(self.owns(root, name) for root in roots)
            ]
            errors.extend(
                f'context selector reaching into .{ name }: { selector }'
                for name in foreign
            )
        return errors

    @staticmethod
    def check_template(path: Path, text: str) -> list[LintViolation]:
        """
        Forbid inline scripts and style attributes setting real properties.

        Returns:
            The violations found in the template.

        """
        violations: list[LintViolation] = []
        for match in SCRIPT_RE.finditer(text):
            attributes, body = match.group(1), match.group(2)
            if 'src=' in attributes:
                continue
            if 'application/json' in attributes:
                continue
            if 'importmap' in attributes:
                continue
            if body.strip():
                violations.append(LintViolation(
                    path, line_of(text, match.start()), 'inline script',
                ))
        violations.extend(
            LintViolation(
                path, line_of(text, match.start()),
                f'static file linked unversioned: { match.group(1) }',
            )
            for match in STATIC_LINK_RE.finditer(text)
            if not match.group(1).startswith(FONTS_URL)
        )
        for match in STYLE_ATTRIBUTE_RE.finditer(text):
            declarations = [
                part for part in match.group(1).split(';') if part.strip()
            ]
            if not all(CUSTOM_PROPERTY_RE.match(part)
                       for part in declarations):
                violations.append(LintViolation(
                    path, line_of(text, match.start()),
                    f'style attribute beyond custom properties:'
                    f' { match.group(1) }',
                ))
        return violations

    def page_context(self, path: Path) -> frozenset[str]:
        """
        Variables a template receives when it is rendered.

        Returns:
            The keys of its page context; none for a component, or for a
            template without a known view (only the skeleton sees all).

        """
        name = path.relative_to(self.templates_directory).as_posix()
        return self.contexts.get(name, frozenset())

    @staticmethod
    def check_expressions(path: Path, text: str,
                          context: frozenset[str]) -> list[LintViolation]:
        """
        Forbid dict methods read as values and macros hiding the context.

        Returns:
            The violations found in the Jinja tags of the template.

        """
        violations: list[LintViolation] = []
        for tag in JINJA_RE.finditer(text):
            line = line_of(text, tag.start())
            violations.extend(
                LintViolation(
                    path, line,
                    f'dict method read as a value: { match.group() }',
                )
                for match in DICT_METHOD_RE.finditer(tag.group())
            )
        for match in MACRO_IMPORT_RE.finditer(text):
            line = line_of(text, match.start())
            for imported in match.group(1).split(','):
                bound = imported.split(' as ')[-1].strip()
                if bound in context:
                    violations.append(LintViolation(
                        path, line,
                        f'macro import shadows the context variable'
                        f' { bound }',
                    ))
        return violations
