"""Seeded scramble series views, readable on a phone."""
import re
import secrets
from random import Random

from bottle import abort
from bottle import redirect
from cubing_algs.algorithm import Algorithm

from term_timer.constants import CUBE_SIZES
from term_timer.constants import MAX_SCRAMBLE_INDEX
from term_timer.constants import SCRAMBLE_SEED_ALPHABET
from term_timer.constants import SCRAMBLE_SEED_LENGTH
from term_timer.scrambler import scrambler
from term_timer.server.annotations import ScrambleDetailContext
from term_timer.server.annotations import ScrambleHomeContext
from term_timer.server.views.base import View

# No '.' to stay clear of the trailing slash hook, nothing to URL-encode.
SEED_RE = re.compile(r'[A-Za-z0-9-]{1,32}')

DEFAULT_CUBE_SIZE = 3


def scramble_url(cube_size: int, seed: str, index: int) -> str:
    """
    Build the URL of one scramble of a seeded series.

    Returns:
        Absolute path of the scramble page.

    """
    return f'/scramble/{ cube_size }/{ seed }/{ index }/'


def is_valid_seed(seed: str) -> bool:
    """
    Tell whether a seed can be carried by a scramble URL.

    Returns:
        True when the seed is made of 1 to 32 letters, digits or dashes.

    """
    return SEED_RE.fullmatch(seed) is not None


class ScrambleHomeView(View):
    """View choosing the cube size and the seed of a scramble series."""

    template_name = 'scramble_home.html'

    def __init__(self, cube_size: str, seed: str) -> None:
        """
        Initialize the scramble home view.

        Args:
            cube_size: Cube size submitted by the form, empty if none.
            seed: Seed submitted by the form, empty if none.

        """
        self.cube_size = cube_size
        self.seed = seed.strip()

    @staticmethod
    def generate_seed() -> str:
        """
        Draw a short seed code, easy to dictate.

        Returns:
            A code of SCRAMBLE_SEED_LENGTH characters of the seed alphabet.

        """
        return ''.join(
            secrets.choice(SCRAMBLE_SEED_ALPHABET)
            for _ in range(SCRAMBLE_SEED_LENGTH)
        )

    def get_context(self) -> ScrambleHomeContext:
        """
        Build context for the scramble home template.

        A submitted form with a valid size and seed redirects to the
        first scramble of the series instead.

        Returns:
            Dictionary with the size selector and the proposed seed.

        """
        valid_size = (
            self.cube_size.isdigit() and int(self.cube_size) in CUBE_SIZES
        )
        cube_size = int(self.cube_size) if valid_size else DEFAULT_CUBE_SIZE

        error = ''
        if self.cube_size or self.seed:
            if valid_size and is_valid_seed(self.seed):
                redirect(scramble_url(cube_size, self.seed, 1), 302)
            error = (
                'Pick a cube size and a seed of 1 to 32 '
                'letters, digits or dashes.'
            )

        return {
            'cube_size': cube_size,
            'seed': self.seed or self.generate_seed(),
            'available_cube_sizes': CUBE_SIZES,
            'error': error,
        }


class ScrambleDetailView(View):
    """View displaying one scramble of a seeded series."""

    template_name = 'scramble.html'

    def __init__(self, cube_size: int, seed: str, index: int) -> None:
        """
        Initialize the scramble detail view.

        Args:
            cube_size: Size of the scrambled cube.
            seed: Seed of the random generator, as with `scramble -r`.
            index: One-based position of the scramble in the series.

        """
        if cube_size not in CUBE_SIZES:
            abort(404, f'No scramble for a { cube_size }x{ cube_size }')
        if not is_valid_seed(seed):
            abort(404, 'Invalid seed')
        if not 1 <= index <= MAX_SCRAMBLE_INDEX:
            abort(404, f'Scramble #{ index } is out of the series')

        self.cube_size = cube_size
        self.seed = seed
        self.index = index

    def get_scramble(self) -> Algorithm:
        """
        Regenerate the scramble at the index of the series.

        Replays the draws of `term-timer scramble -r SEED`, so the n-th
        scramble here is the n-th scramble printed by the command.

        Returns:
            The scramble algorithm.

        """
        rng = Random(self.seed)  # noqa: S311

        scramble = Algorithm()
        for _ in range(self.index):
            scramble, _cube = scrambler(
                cube_size=self.cube_size,
                iterations=0,
                rng=rng,
            )

        return scramble

    def get_context(self) -> ScrambleDetailContext:
        """
        Build context for the scramble template.

        Returns:
            Dictionary with the scramble and its position in the series.

        """
        scramble = self.get_scramble()

        return {
            'cube_size': self.cube_size,
            'seed': self.seed,
            'index': self.index,
            'max_index': MAX_SCRAMBLE_INDEX,
            'scramble': scramble,
            'htm': scramble.metrics.htm,
        }
