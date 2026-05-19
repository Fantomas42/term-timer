"""Sound player with sounddevice/numpy backend and terminal bell fallback."""
# ruff: noqa: T201
import math
from functools import lru_cache
from typing import NamedTuple

import numpy as np

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except OSError:
    print('No PortAudio installed. Try install libportaudio2 package.')
    SOUNDDEVICE_AVAILABLE = False

SAMPLE_RATE = 44100


class Tone(NamedTuple):
    """Defines the parameters for a single tone."""

    frequency: float
    duration: float
    volume: float = 0.3


TONES: dict[str, Tone] = {
    'LA_3':  Tone(440.0, 0.15, 0.4),
    'LA_4':  Tone(880.0, 0.10, 0.3),
    'step':       Tone(1100.0, 0.10, 0.35),
    'scrambled':  Tone(660.0, 0.25, 0.35),
    'connected':  Tone(523.0, 0.12, 0.25),
    'success':    Tone(1046.0, 0.20, 0.35),
}


class SoundPlayer:
    """Play tones via sounddevice or fall back to terminal bell."""

    def __init__(self) -> None:
        """Initialize and probe audio device availability."""
        self.available = self.probe_audio()

    @staticmethod
    def probe_audio() -> bool:
        """
        Check whether sounddevice has a usable output device.

        Returns:
            True if an output device is available, False otherwise.

        """
        if not SOUNDDEVICE_AVAILABLE:
            return False
        try:
            sd.query_devices(kind='output')
        except Exception:  # noqa: BLE001
            return False
        else:
            return True

    @staticmethod
    @lru_cache
    def generate_wave(tone: Tone) -> np.ndarray:
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

    @staticmethod
    @lru_cache
    def generate_metronome_wave() -> np.ndarray:
        """
        Generate a downward chirp (800→300 Hz) with exponential decay.

        Returns:
            Float32 array of audio samples.

        """
        duration = 0.07
        samples = int(SAMPLE_RATE * duration)
        t = np.linspace(0, duration, samples, endpoint=False)
        freq_t = 800.0 + (300.0 - 800.0) * (t / duration)
        phase = 2 * math.pi * np.cumsum(freq_t) / SAMPLE_RATE
        wave = 0.32 * np.sin(phase)
        env = np.exp(-25.0 * t / duration)
        return (wave * env).astype(np.float32)

    def play(self, name: str) -> None:
        """Play a sound else fallback."""
        if self.available:
            wave = self.generate_wave(TONES[name])
            sd.play(wave, SAMPLE_RATE, blocking=False)
        else:
            print('\a', end='', flush=True)

    def metronome(self) -> None:
        """Play a short neutral tick for metronome beats."""
        if self.available:
            sd.play(
                self.generate_metronome_wave(),
                SAMPLE_RATE,
                blocking=False,
            )
        else:
            print('\a', end='', flush=True)

    def la_3(self) -> None:
        """Play a LA 3."""
        self.play('LA_3')

    def la_4(self) -> None:
        """Play a LA 4."""
        self.play('LA_4')

    def step(self) -> None:
        """Play a higher-pitched beep when a solve step is completed."""
        self.play('step')

    def scrambled(self) -> None:
        """Play a confirmation tone when scramble is finalized."""
        self.play('scrambled')

    def connected(self) -> None:
        """Play a soft chime when a Bluetooth cube connects."""
        self.play('connected')

    def success(self) -> None:
        """Play a bright tone on solve, training, or drill completion."""
        self.play('success')


if __name__ == '__main__':
    import sys
    import time

    player = SoundPlayer()
    names = list(TONES)

    if not player.available:
        print('No audio device found, using terminal bell fallback.')

    if len(sys.argv) > 1:
        name = sys.argv[1]
        if name not in TONES:
            print(f'Unknown sound: {name!r}')
            print(f'Available: {", ".join(names)}')
            sys.exit(1)
        print(f'Playing: {name} (Ctrl+C to quit)')
        try:
            while True:
                player.play(name)
                time.sleep(TONES[name].duration + 1.0)
        except KeyboardInterrupt:
            print('\nDone.')
    else:
        print(f'Playing all sounds: {", ".join(names)} (Ctrl+C to quit)')
        try:
            while True:
                for name in names:
                    print(f'  {name}')
                    player.play(name)
                    time.sleep(TONES[name].duration + 0.3)
                time.sleep(1.0)
        except KeyboardInterrupt:
            print('\nDone.')

SOUND_PLAYER = SoundPlayer()
