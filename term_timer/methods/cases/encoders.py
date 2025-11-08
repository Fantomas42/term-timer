"""Case encoders for identifying OLL, PLL, and F2L patterns."""

from collections.abc import Callable

from cubing_algs.masks import state_masked


def oll_case_encoder(facelets: str) -> str:
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
    def encoder(facelets: str) -> str:
        facelets_fingerprint = state_masked(facelets, mask)

        facelet_encoder: dict[str, str] = {}
        for face in facelets_fingerprint:
            if face not in facelet_encoder:
                facelet_encoder[face] = str(len(facelet_encoder))
            if len(facelet_encoder) == 9:
                break

        fingerprint = [''] * 54
        for i, facelet in enumerate(facelets_fingerprint):
            fingerprint[i] = facelet_encoder[facelet]

        return ''.join(fingerprint)

    return encoder
