"""Case encoders for identifying OLL, PLL, and F2L patterns."""
from collections.abc import Callable

from cubing_algs.annotations import CubeFacelets
from cubing_algs.annotations import Mask
from cubing_algs.facelets import cubies_to_facelets
from cubing_algs.facelets import facelets_to_cubies
from cubing_algs.solved_state import SOLVED_FACELETS_3x3x3

MASK_CACHE: dict[Mask, tuple[bool, ...]] = {}
CACHE_SIZE_LIMIT = 1000  # Prevent unbounded memory growth


def facelets_masked(facelets: CubeFacelets, mask: Mask) -> CubeFacelets:
    """
    Apply a binary mask to a facelets string.

    Returns a new facelets string where positions with '0' in the mask
    are replaced with '-', and positions with '1' retain their original value.

    Optimized for high-frequency usage with caching and fast string operations.

    Args:
        facelets: The facelets string to mask.
        mask: The binary mask string.

    Returns:
        The masked facelets string with '-' for masked positions.

    """
    if mask in MASK_CACHE:
        translation = MASK_CACHE[mask]
        return ''.join(
            char if keep else '-'
            for char, keep in zip(facelets, translation, strict=True)
        )

    # Build and cache translation for new masks
    translation = tuple(c == '1' for c in mask)

    # Manage cache size to prevent memory bloat
    if len(MASK_CACHE) >= CACHE_SIZE_LIMIT:
        # Remove oldest half of cache entries (batch-FIFO eviction)
        items = list(MASK_CACHE.items())
        MASK_CACHE.clear()
        MASK_CACHE.update(items[CACHE_SIZE_LIMIT // 2:])

    MASK_CACHE[mask] = translation

    return ''.join(
        char if keep else '-'
        for char, keep in zip(facelets, translation, strict=True)
    )


def state_masked(state: CubeFacelets, mask: Mask) -> CubeFacelets:
    """
    Apply a binary mask to a cube state.

    Converts the state to cubies, applies the mask
    to the initial state facelets, then converts back
    to a facelets representation showing only the masked pieces.

    Args:
        state: The cube state string to mask.
        mask: The binary mask string.

    Returns:
        The masked cube state as a facelets string.

    Notes:
        Maybe use a derived of compute_algorithm_mask() in the future.

    """
    return cubies_to_facelets(
        *facelets_to_cubies(state),
        facelets_masked(
            SOLVED_FACELETS_3x3x3,
            mask,
        ),
    )


def oll_case_encoder(facelets: str) -> str:
    """
    Encode OLL case from cube facelets to binary fingerprint.

    Returns:
        21-character binary string representing the OLL pattern.

    """
    facelets_fingerprint = (
        facelets[15:18]
        + facelets[24:36]
        + facelets[42:45]
        + facelets[51:54]
    )

    center = facelets_fingerprint[10]
    fingerprint = [''] * 21
    for i, facelet in enumerate(facelets_fingerprint):
        fingerprint[i] = '1' if facelet == center else '0'

    return ''.join(fingerprint)


def pll_case_encoder(facelets: str) -> str:
    """
    Encode PLL case from cube facelets to numeric fingerprint.

    Returns:
        21-character numeric string representing the PLL pattern.

    """
    facelets_fingerprint = (
        facelets[15:18]
        + facelets[24:27]
        + facelets[42:45]
        + facelets[51:54]
    )
    facelet_encoder: dict[str, str] = {}
    for face in facelets_fingerprint:
        if face not in facelet_encoder:
            facelet_encoder[face] = str(len(facelet_encoder))
        if len(facelet_encoder) == 4:
            break

    fingerprint = [''] * 21
    for i, facelet in enumerate(facelets_fingerprint):
        fingerprint[i] = facelet_encoder[facelet]

    return ''.join(fingerprint)


def f2l_case_encoder(mask: str) -> Callable[[str], str]:
    """
    Create F2L case encoder function with specific mask.

    Returns:
        Encoder function that converts facelets to F2L fingerprint.

    """
    def encoder(facelets: str) -> str:
        facelets_fingerprint = state_masked(facelets, mask)

        facelet_encoder: dict[str, str] = {}
        for face in facelets_fingerprint:
            if face not in facelet_encoder:
                facelet_encoder[face] = str(len(facelet_encoder))

        fingerprint = [''] * 54
        for i, facelet in enumerate(facelets_fingerprint):
            fingerprint[i] = facelet_encoder[facelet]

        return ''.join(fingerprint)

    return encoder
