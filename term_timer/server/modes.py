"""Grouping of cube display modes for the selector UI."""
from cubing_algs.display.mode import MODE_CONFIGS

# Display modes grouped by solving stage. Order within a group does not
# matter: modes are sorted alphabetically at render time, so adding a new
# mode only requires dropping its key into the relevant list.
MODE_GROUPS: list[tuple[str, list[str]]] = [
    ('Cross', ['cross', 'cross-bottom', 'cross-top']),
    ('F2L', ['f2l', 'af2l', 'f2l-fr', 'f2l-fl', 'f2l-br', 'f2l-bl']),
    ('Last Layer', ['ll', 'oll', 'pll', 'zbll']),
    ('Corners Last Layer', ['cll', 'ocll', 'coll', 'cpll']),
    ('Edges Last Layer', ['ell', 'eoll', 'epll']),
    ('Last Slot + Last Layer', [
        'ls', 'ls-oll', 'ls-ocll', 'els', 'zbls', 'vls', 'wvls', 'cls',
    ]),
    ('Edge Orientation', ['eo', 'eo-cross', 'eo-line', 'eo-slice', 'eo-edge']),
    ('Roux', ['cmll', 'lse', 'l6eo', 'l10p']),
    ('Render Styles', ['visible', 'dimmed', 'masked', 'hidden', 'oriented']),
]


def get_mode_groups() -> list[tuple[str, list[str]]]:
    """
    Build the grouped display modes for the selector.

    Each group keeps only modes that exist in ``MODE_CONFIGS``, sorted
    alphabetically. Any known mode missing from ``MODE_GROUPS`` is gathered
    into a trailing ``Other`` group so it stays reachable.

    Returns:
        Ordered list of (group label, sorted mode keys) tuples.

    """
    known = set(MODE_CONFIGS)
    seen: set[str] = set()
    groups: list[tuple[str, list[str]]] = []

    for label, modes in MODE_GROUPS:
        available = sorted(mode for mode in modes if mode in known)
        seen.update(available)
        if available:
            groups.append((label, available))

    others = sorted(known - seen)
    if others:
        groups.append(('Other', others))

    return groups
