"""Sound player with sounddevice/numpy backend and terminal bell fallback."""
# ruff: noqa: T201, BLE001
import logging
import math
from typing import NamedTuple

import numpy as np

try:
    import sounddevice as sd
    _SOUNDDEVICE_AVAILABLE = True
except ImportError:
    _SOUNDDEVICE_AVAILABLE = False

logger = logging.getLogger(__name__)


SAMPLE_RATE = 44100


class Tone(NamedTuple):
    """Defines the parameters for a single tone."""

    frequency: float
    duration: float
    volume: float = 0.3


TONES: dict[str, Tone] = {
    'metronome': Tone(800.0, 0.05, 0.2),
    'step':      Tone(1100.0, 0.10, 0.35),
    'countdown': Tone(440.0, 0.15, 0.4),
    'scramble':  Tone(660.0, 0.25, 0.35),
    'generic':   Tone(880.0, 0.10, 0.3),
}


def _probe_audio() -> bool:
    """
    Check whether sounddevice has a usable output device.

    Returns:
        True if an output device is available, False otherwise.

    """
    if not _SOUNDDEVICE_AVAILABLE:
        return False
    try:
        sd.query_devices(kind='output')
    except Exception:
        return False
    else:
        return True


def _generate_wave(tone: Tone) -> np.ndarray:
    """
    Generate a sine wave with a short fade-out to avoid clicking.

    Returns:
        Float32 array of audio samples.

    """
    samples = int(SAMPLE_RATE * tone.duration)
    t = np.linspace(0, tone.duration, samples, endpoint=False)
    wave = tone.volume * np.sin(2 * math.pi * tone.frequency * t)
    fade = min(int(SAMPLE_RATE * 0.01), samples // 4)
    wave[-fade:] *= np.linspace(1.0, 0.0, fade)
    return wave.astype(np.float32)


class SoundPlayer:
    """Play tones via sounddevice or fall back to terminal bell."""

    def __init__(self) -> None:
        """Initialize and probe audio device availability."""
        self._available = _probe_audio()

    def _play(self, name: str) -> None:
        if self._available:
            try:
                wave = _generate_wave(TONES[name])
                sd.play(wave, SAMPLE_RATE, blocking=False)
            except Exception:
                logger.debug('sounddevice playback failed, using terminal bell')
            else:
                return
        print('\a', end='', flush=True)

    def metronome(self) -> None:
        """Play a short neutral tick for metronome beats."""
        self._play('metronome')

    def step(self) -> None:
        """Play a higher-pitched beep when a solve step is completed."""
        self._play('step')

    def countdown(self) -> None:
        """Play a low urgent beep for inspection countdown warnings."""
        self._play('countdown')

    def scramble(self) -> None:
        """Play a confirmation tone when scramble is finalized."""
        self._play('scramble')

    def generic(self) -> None:
        """Play a generic beep for miscellaneous notifications."""
        self._play('generic')
