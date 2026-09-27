"""Main navigation of the V2 pages."""
import re
from dataclasses import dataclass
from dataclasses import field
from typing import ClassVar

from term_timer.server.annotations import NavigationItem


@dataclass(frozen=True)
class NavigationEntry:
    """One destination of the main navigation."""

    label: str
    icon: str
    url: str
    active: re.Pattern[str]
    debug_only: bool = field(default=False, kw_only=True)

    def is_active(self, path: str) -> bool:
        """
        Whether the request path belongs to this destination.

        Returns:
            True when the path matches the active pattern.

        """
        return bool(self.active.match(path))


class Navigation:
    """The main navigation, with its active entry for a request path."""

    entries: ClassVar[tuple[NavigationEntry, ...]] = (
        NavigationEntry(
            'Sessions', 'sessions', '/', re.compile(r'/(?:$|\d+/)'),
        ),
        NavigationEntry('Daily', 'daily', '/daily/3/', re.compile(r'/daily/')),
        NavigationEntry(
            'Training', 'training', '/training/', re.compile(r'/training/'),
        ),
        NavigationEntry(
            'Academy', 'academy', '/academy/', re.compile(r'/academy/'),
        ),
        NavigationEntry(
            'Scramble', 'scramble', '/scramble/', re.compile(r'/scramble/'),
        ),
        NavigationEntry(
            'Design', 'styleguide', '/styleguide/v2/',
            re.compile(r'/styleguide/'), debug_only=True,
        ),
    )

    @classmethod
    def items(cls, path: str, *, debug: bool) -> list[NavigationItem]:
        """
        Visible entries, the first one matching the path marked active.

        Args:
            path: Path of the current request.
            debug: Whether the debug-only entries are shown.

        Returns:
            The entries to render, in menu order.

        """
        visible = [
            entry for entry in cls.entries
            if debug or not entry.debug_only
        ]
        active = next(
            (entry for entry in visible if entry.is_active(path)),
            None,
        )
        return [
            {
                'label': entry.label,
                'icon': entry.icon,
                'url': entry.url,
                'active': entry is active,
            }
            for entry in visible
        ]
