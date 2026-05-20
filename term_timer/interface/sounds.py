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
    'LA_3': Tone(440.0, 0.15, 0.4),
    'LA_4': Tone(880.0, 0.10, 0.3),
}

CONNECTED_FREQS = (900.0, 1300.0, 1800.0)
DISCONNECTED_FREQS = (1800.0, 1300.0, 900.0)
TRIO_DURATIONS = (0.05, 0.05, 0.07)
TRIO_GAP = 0.03
TRIO_VOLUME = 0.25


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
    def generate_trio_wave(
        freqs: tuple[float, ...],
        durations: tuple[float, ...],
        gap: float,
        volume: float,
    ) -> np.ndarray:
        """
        Generate a sequence of sine tones separated by silence.

        Returns:
            Float32 array of concatenated beeps with fade-outs.

        """
        parts: list[np.ndarray] = []
        gap_samples = np.zeros(int(SAMPLE_RATE * gap), dtype=np.float32)
        for i, (freq, dur) in enumerate(zip(freqs, durations, strict=True)):
            samples = int(SAMPLE_RATE * dur)
            t = np.linspace(0, dur, samples, endpoint=False)
            wave = volume * np.sin(2 * math.pi * freq * t)
            fade = min(int(SAMPLE_RATE * 0.008), samples // 4)
            wave[-fade:] *= np.linspace(1.0, 0.0, fade)
            parts.append(wave.astype(np.float32))
            if i < len(freqs) - 1:
                parts.append(gap_samples)
        return np.concatenate(parts)

    @staticmethod
    @lru_cache
    def generate_step_wave() -> np.ndarray:
        """
        Generate a triangle-bell ting using additive synthesis.

        Three inharmonic partials (x1, x2.76, x5.40) with differential decay
        rates — higher partials fade faster, giving a bright metallic attack
        followed by a clean fundamental resonance.

        Returns:
            Float32 array of audio samples.

        """
        fundamental = 880.0
        duration = 0.45
        volume = 0.23
        partials = ((1.00, 1.00, 5.0), (2.76, 0.70, 10.0), (5.40, 0.45, 18.0))
        samples = int(SAMPLE_RATE * duration)
        t = np.linspace(0, duration, samples, endpoint=False)
        wave = np.zeros(samples, dtype=np.float64)
        for ratio, amp, decay in partials:
            env = np.exp(-decay * t / duration)
            wave += amp * env * np.sin(2 * math.pi * fundamental * ratio * t)
        result = (volume * wave).astype(np.float32)
        fade = min(int(SAMPLE_RATE * 0.015), samples // 4)
        result[-fade:] *= np.linspace(1.0, 0.0, fade)
        return result

    @staticmethod
    @lru_cache
    def generate_scrambled_wave() -> np.ndarray:
        """
        Generate a confirmation ping using additive synthesis.

        Four inharmonic partials (x1, x2.76, x5.40, x8.93) at 880 Hz with the
        upper partials dominant — bright metallic attack that cuts through.

        Returns:
            Float32 array of audio samples.

        """
        fundamental = 880.0
        duration = 0.55
        volume = 0.20
        partials = (
            (1.00, 0.55, 4.0),
            (2.76, 1.00, 8.0),
            (5.40, 0.80, 14.0),
            (8.93, 0.75, 24.0),
        )
        samples = int(SAMPLE_RATE * duration)
        t = np.linspace(0, duration, samples, endpoint=False)
        wave = np.zeros(samples, dtype=np.float64)
        for ratio, amp, decay in partials:
            env = np.exp(-decay * t / duration)
            wave += amp * env * np.sin(2 * math.pi * fundamental * ratio * t)
        result = (volume * wave).astype(np.float32)
        fade = min(int(SAMPLE_RATE * 0.012), samples // 4)
        result[-fade:] *= np.linspace(1.0, 0.0, fade)
        return result

    @staticmethod
    @lru_cache
    def generate_success_wave() -> np.ndarray:
        """
        Generate an ascending four-note fanfare using additive synthesis.

        Five inharmonic partials (x1, x2.76, x5.40, x8.93, x13) applied to
        E5→G5→C6→E6, staccato tempo (0.07s notes, 0.010s gap, 0.20s last note).

        Returns:
            Float32 array of audio samples.

        """
        partials = (
            (1.00, 0.55, 4.0),
            (2.76, 1.00, 8.0),
            (5.40, 1.20, 8.0),
            (8.93, 1.10, 14.0),
            (13.00, 0.60, 30.0),
        )
        freqs = (659.25, 783.99, 1046.50, 1318.51)
        durs = (0.07, 0.07, 0.07, 0.20)
        volume = 0.22
        gap_samples = np.zeros(int(SAMPLE_RATE * 0.010), dtype=np.float32)
        parts: list[np.ndarray] = []
        for i, (freq, dur) in enumerate(zip(freqs, durs, strict=True)):
            samples = int(SAMPLE_RATE * dur)
            t = np.linspace(0, dur, samples, endpoint=False)
            wave = np.zeros(samples, dtype=np.float64)
            for ratio, amp, decay in partials:
                env = np.exp(-decay * t / dur)
                wave += amp * env * np.sin(2 * math.pi * freq * ratio * t)
            result = (volume * wave).astype(np.float32)
            fade = min(int(SAMPLE_RATE * 0.012), samples // 4)
            result[-fade:] *= np.linspace(1.0, 0.0, fade)
            parts.append(result)
            if i < len(freqs) - 1:
                parts.append(gap_samples)
        return np.concatenate(parts)

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

    def connected(self) -> None:
        """Play an ascending triple beep when a Bluetooth cube connects."""
        if self.available:
            wave = self.generate_trio_wave(
                CONNECTED_FREQS, TRIO_DURATIONS, TRIO_GAP, TRIO_VOLUME,
            )
            sd.play(wave, SAMPLE_RATE, blocking=False)
        else:
            print('\a', end='', flush=True)

    def disconnected(self) -> None:
        """Play a descending triple beep when a Bluetooth cube disconnects."""
        if self.available:
            wave = self.generate_trio_wave(
                DISCONNECTED_FREQS, TRIO_DURATIONS, TRIO_GAP, TRIO_VOLUME,
            )
            sd.play(wave, SAMPLE_RATE, blocking=False)
        else:
            print('\a', end='', flush=True)

    def scrambled(self) -> None:
        """Play a confirmation tone when scramble is finalized."""
        if self.available:
            wave = self.generate_scrambled_wave()
            sd.play(wave, SAMPLE_RATE, blocking=False)
        else:
            print('\a', end='', flush=True)

    def step(self) -> None:
        """Play a higher-pitched beep when a solve step is completed."""
        if self.available:
            wave = self.generate_step_wave()
            sd.play(wave, SAMPLE_RATE, blocking=False)
        else:
            print('\a', end='', flush=True)

    def success(self) -> None:
        """Play a bright tone on solve, training, or drill completion."""
        if self.available:
            wave = self.generate_success_wave()
            sd.play(wave, SAMPLE_RATE, blocking=False)
        else:
            print('\a', end='', flush=True)

    def la_3(self) -> None:
        """Play a LA 3."""
        self.play('LA_3')

    def la_4(self) -> None:
        """Play a LA 4."""
        self.play('LA_4')


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
