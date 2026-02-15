"""Sessions panel for browsing cube sizes and sessions."""
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Static
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from term_timer.browse.models import discover_cube_groups


class SessionsPanel(VerticalScroll):
    """Panel displaying cube sizes and sessions in a tree structure."""

    DEFAULT_CSS = """
    SessionsPanel {
        width: 1fr;
        border-right: solid $primary;
    }

    SessionsPanel > Static {
        background: $boost;
        padding: 1;
        text-style: bold;
    }

    SessionsPanel Tree {
        padding: 0 1;
    }
    """

    class SessionSelected(Message):
        """Message sent when a session is selected."""

        def __init__(self, cube_size: int, session_name: str) -> None:
            """Initialize message with session info."""
            self.cube_size = cube_size
            self.session_name = session_name
            super().__init__()

    @staticmethod
    def compose() -> ComposeResult:
        """
        Compose the sessions panel.

        Yields:
            Widget components for the sessions panel layout.

        """
        yield Static('Sessions')
        yield Tree('Sessions')

    def on_mount(self) -> None:
        """Load sessions when panel is mounted."""
        self.load_sessions()
        self.call_after_refresh(self.auto_select_default_session)

    def load_sessions(self) -> None:
        """Load and display all cube groups and sessions."""
        tree = self.query_one(Tree)
        tree.clear()
        tree.show_root = False

        cube_groups = discover_cube_groups()

        if not cube_groups:
            tree.root.add_leaf('No sessions found')
            return

        for cube_group in cube_groups:
            # Add cube size node
            cube_label = (
                f'{cube_group.display_name} '
                f'({cube_group.total_solves} solves)'
            )
            cube_node = tree.root.add(
                cube_label,
                data={'type': 'cube', 'cube_size': cube_group.cube_size},
            )

            # Add session nodes
            for session in cube_group.sessions:
                cube_node.add_leaf(
                    session.display_name,
                    data={
                        'type': 'session',
                        'cube_size': session.cube_size,
                        'session_name': session.session_name,
                    },
                )

    def auto_select_default_session(self) -> None:
        """Auto-select the 3x3x3 default session if it exists."""
        tree = self.query_one(Tree)

        # Find the 3x3x3 default session node
        default_node = self.find_session_node(3, 'default')

        if default_node is not None:
            # Ensure the parent node is expanded
            if default_node.parent:
                default_node.parent.expand()
            # Move cursor to the node and select it
            tree.cursor_line = default_node.line
            tree.select_node(default_node)

        elif tree.root.children:
            # If no 3x3x3 default, just expand the first cube group
            tree.root.children[0].expand()

    def find_session_node(
        self,
        cube_size: int,
        session_name: str,
    ) -> TreeNode[dict[str, str | int]] | None:
        """
        Find a session node in the tree by cube size and session name.

        Args:
            cube_size: The cube size to search for.
            session_name: The session name to search for.

        Returns:
            The tree node if found, None otherwise.

        """
        tree = self.query_one(Tree)

        for cube_node in tree.root.children:
            if (
                cube_node.data
                and cube_node.data.get('type') == 'cube'
                and cube_node.data.get('cube_size') == cube_size
            ):
                for session in cube_node.children:
                    if (
                        session.data
                        and session.data.get('type') == 'session'
                        and session.data.get('session_name') == session_name
                    ):
                        return session

        return None

    def on_tree_node_selected(
        self,
        event: Tree.NodeSelected[dict[str, str | int]],
    ) -> None:
        """Handle tree node selection."""
        node = event.node
        if node.data and node.data.get('type') == 'session':
            cube_size = node.data['cube_size']
            session_name = node.data['session_name']
            if isinstance(cube_size, int) and isinstance(session_name, str):
                self.post_message(
                    self.SessionSelected(
                        cube_size=cube_size,
                        session_name=session_name,
                    ),
                )
