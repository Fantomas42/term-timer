"""Data models for browse interface."""
from dataclasses import dataclass

from term_timer.constants import SOLVES_DIRECTORY
from term_timer.in_out import load_solves


@dataclass
class SessionInfo:
    """Information about a solve session."""

    cube_size: int
    session_name: str
    pretty_name: str
    solve_count: int

    @property
    def display_name(self) -> str:
        """Return formatted display name with solve count."""
        return f'{self.pretty_name} ({self.solve_count})'


@dataclass
class CubeGroup:
    """Group of sessions for a specific cube size."""

    cube_size: int
    sessions: list[SessionInfo]

    @property
    def display_name(self) -> str:
        """Return formatted cube size name."""
        return f'{self.cube_size}x{self.cube_size}x{self.cube_size}'

    @property
    def total_solves(self) -> int:
        """Return total solve count across all sessions."""
        return sum(s.solve_count for s in self.sessions)


def parse_session_name(session_name: str) -> str:  # noqa: PLR0911
    """
    Parse session name into pretty format.

    Args:
        session_name: Raw session name from file.

    Returns:
        Pretty formatted session name.

    Examples:
        >>> parse_session_name('default')
        'Default'
        >>> parse_session_name('scrambles-test')
        'Scrambles: test'
        >>> parse_session_name('seed-42')
        'Seed: 42'
        >>> parse_session_name('easy-cross')
        'Easy Cross'
        >>> parse_session_name('iterations-25')
        'Iterations: 25'
        >>> parse_session_name('my-custom-session')
        'My Custom Session'

    """
    if not session_name or session_name == 'default':
        return 'Default'

    # Handle known patterns
    if session_name.startswith('scrambles-'):
        return f'Scrambles: {session_name[10:]}'

    if session_name.startswith('seed-'):
        return f'Seed: {session_name[5:]}'

    if session_name.startswith('iterations-'):
        return f'Iterations: {session_name[11:]}'

    if session_name == 'easy-cross':
        return 'Easy Cross'

    if session_name == 'free-play':
        return 'Free Play'

    # Generic handling: replace hyphens with spaces and title case
    return session_name.replace('-', ' ').title()


def discover_sessions(cube_size: int) -> list[SessionInfo]:
    """
    Discover all sessions for a given cube size.

    Args:
        cube_size: Cube dimension (e.g., 3 for 3x3x3).

    Returns:
        List of SessionInfo objects sorted by session name.

    """
    sessions: list[SessionInfo] = []

    # Check for default session
    default_file = (
        SOLVES_DIRECTORY / f'{cube_size}x{cube_size}x{cube_size}.json'
    )
    if default_file.exists():
        solves = load_solves(cube_size, 'default')
        if solves:
            sessions.append(
                SessionInfo(
                    cube_size=cube_size,
                    session_name='default',
                    pretty_name=parse_session_name('default'),
                    solve_count=len(solves),
                ),
            )

    # Discover named sessions
    prefix = f'{cube_size}x{cube_size}x{cube_size}-'
    for file_path in SOLVES_DIRECTORY.iterdir():
        if file_path.is_file() and file_path.name.startswith(prefix):
            session_name = file_path.name.split(prefix, 1)[1].replace(
                '.json', '',
            )
            solves = load_solves(cube_size, session_name)
            if solves:
                sessions.append(
                    SessionInfo(
                        cube_size=cube_size,
                        session_name=session_name,
                        pretty_name=parse_session_name(session_name),
                        solve_count=len(solves),
                    ),
                )

    return sorted(sessions, key=lambda s: s.session_name)


def discover_cube_groups() -> list[CubeGroup]:
    """
    Discover all cube sizes and their sessions.

    Returns:
        List of CubeGroup objects sorted by cube size.

    """
    cube_sizes: set[int] = set()

    # Scan save directory for all cube sizes
    for file_path in SOLVES_DIRECTORY.iterdir():
        if file_path.is_file() and file_path.suffix == '.json':
            # Extract cube size from filename like "3x3x3.json"
            name_parts = file_path.name.split('x')
            if len(name_parts) >= 3:
                try:
                    cube_size = int(name_parts[0])
                    cube_sizes.add(cube_size)
                except ValueError:
                    continue

    # Build groups with sessions
    groups: list[CubeGroup] = []
    for cube_size in sorted(cube_sizes):
        sessions = discover_sessions(cube_size)
        if sessions:
            groups.append(
                CubeGroup(
                    cube_size=cube_size,
                    sessions=sessions,
                ),
            )

    return groups
