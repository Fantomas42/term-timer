"""Styleguide view rendering the live design-token catalogue."""
import re

from term_timer.constants import STATIC_DIRECTORY
from term_timer.server.annotations import StyleguideContext
from term_timer.server.annotations import StyleguideGroup
from term_timer.server.annotations import StyleguideToken
from term_timer.server.views.base import View

STYLESHEET = STATIC_DIRECTORY / 'css' / 'style.css'

BANNER_RE = re.compile(r'/\*\s*(.+?)\s*\*/')
TOKEN_RE = re.compile(
    r'^\s*(--[\w-]+)\s*:\s*([^;]+);'
    r'\s*(?:/\*\s*(.*?)\s*\*/)?',
)


def parse_root_groups(css_text: str) -> list[StyleguideGroup]:
    """
    Parse the :root block into titled groups of design tokens.

    Comment banners inside :root become group titles; every following
    custom-property declaration is collected into the current group, with
    any trailing comment kept as the token note.

    Args:
        css_text: Full content of the stylesheet.

    Returns:
        Ordered list of token groups as found in the :root block.

    """
    lines = css_text.splitlines()

    start = next(
        (i for i, line in enumerate(lines) if ':root' in line),
        -1,
    )
    if start < 0:
        return []

    groups: list[StyleguideGroup] = []
    current: StyleguideGroup = {'title': 'Tokens', 'tokens': []}
    depth = 0

    for index in range(start, len(lines)):
        line = lines[index]
        depth += line.count('{') - line.count('}')

        token_match = TOKEN_RE.match(line)
        if token_match:
            token: StyleguideToken = {
                'name': token_match.group(1),
                'value': token_match.group(2).strip(),
                'note': (token_match.group(3) or '').strip(),
            }
            current['tokens'].append(token)
            continue

        banner_match = BANNER_RE.search(line)
        if banner_match:
            title = banner_match.group(1).strip(' ─-')
            if title:
                if current['tokens']:
                    groups.append(current)
                current = {'title': title, 'tokens': []}

        if depth == 0 and index > start:
            break

    if current['tokens']:
        groups.append(current)

    return groups


class StyleguideView(View):
    """View rendering the design-token and component catalogue."""

    template_name = 'styleguide.html'

    @staticmethod
    def get_context() -> StyleguideContext:
        """
        Build context for the styleguide template.

        Returns:
            Dictionary with token groups parsed from the stylesheet.

        """
        css_text = STYLESHEET.read_text(encoding='utf-8')

        return {
            'token_groups': parse_root_groups(css_text),
        }
