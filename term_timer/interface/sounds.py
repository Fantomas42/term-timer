"""Sound player with sounddevice/numpy backend and terminal bell fallback."""
# ruff: noqa: T201
import math
from collections.abc import Callable
from functools import lru_cache
from typing import Literal
from typing import NamedTuple

import numpy as np

from term_timer.config import TIMER_SOUND

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except OSError:
    print('No PortAudio installed. Try install libportaudio2 package.')
    SOUNDDEVICE_AVAILABLE = False

SAMPLE_RATE = 44100

PanDirection = Literal['left_to_right', 'right_to_left', 'center']


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
DISCONNECTED_FREQS = (700.0, 500.0, 350.0)
TRIO_DURATIONS = (0.05, 0.05, 0.07)
TRIO_GAP = 0.03
TRIO_VOLUME = 0.25
DISCONNECTED_DURATIONS = (0.05, 0.05, 0.09)
DISCONNECTED_VOLUME = 0.27
NOT_CONNECTED_FREQS = (570.0, 840.0, 200.0)
NOT_CONNECTED_DURATIONS = (0.05, 0.05, 0.17)
NOT_CONNECTED_VOLUME = 0.25
MISSED_FREQS = (400.0, 1200.0, 180.0)
MISSED_DURATIONS = (0.045, 0.045, 0.140)
MISSED_GAP = 0.018
MISSED_VOLUME = 0.27
MISORIENTED_FREQS = (400.0, 1200.0)
MISORIENTED_DURATIONS = (0.045, 0.045)
MISORIENTED_THUD = Tone(110.0, 0.180, 0.30)
THUD_PARTIALS = (
    (1.00, 1.00, 4.0),
    (1.50, 0.70, 7.0),
    (2.10, 0.40, 12.0),
)

CONNECTED_PAN: PanDirection = 'left_to_right'
DISCONNECTED_PAN: PanDirection = 'right_to_left'
NOT_CONNECTED_PAN: PanDirection = 'right_to_left'
MISSED_PAN: PanDirection = 'right_to_left'


class SoundPlayer:  # noqa: PLR0904
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
    def bell() -> None:
        """Emit the terminal bell character."""
        print('\a', end='', flush=True)

    def play(self, get_wave: Callable[[], np.ndarray]) -> None:
        """
        Dispatch audio output according to the configured sound mode.

        Generates and plays audio when mode is 'audio' and a device is
        available, falls back to terminal bell for 'terminal' mode or when
        no audio device is present, and does nothing when mode is 'off'.

        """
        if TIMER_SOUND == 'off':
            return
        if TIMER_SOUND == 'audio' and self.available:
            sd.play(get_wave(), SAMPLE_RATE, blocking=False)
        else:
            self.bell()

    @staticmethod
    def apply_sine_pan(mono: np.ndarray, direction: PanDirection) -> np.ndarray:
        """
        Apply a sine-eased equal-power stereo pan sweep to a mono signal.

        Returns:
            Float32 stereo (N, 2) array.

        """
        t = np.linspace(0.0, 1.0, len(mono), dtype=np.float32)
        if direction == 'left_to_right':
            pan = (1.0 - np.cos(math.pi * t)) / 2.0
        else:
            pan = (1.0 + np.cos(math.pi * t)) / 2.0
        angle = pan * (math.pi / 2)
        return np.stack(
            [mono * np.cos(angle), mono * np.sin(angle)], axis=1,
        ).astype(np.float32)

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
        pan_direction: PanDirection = 'center',
    ) -> np.ndarray:
        """
        Generate a sequence of sine tones separated by silence.

        When pan_direction is 'left_to_right' or 'right_to_left', applies a
        sine-eased stereo sweep and returns a (N, 2) float32 array. Otherwise
        returns a mono (N,) float32 array.

        Returns:
            Float32 array of concatenated beeps, mono or stereo.

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
        mono = np.concatenate(parts)
        if pan_direction == 'center':
            return mono
        return SoundPlayer.apply_sine_pan(mono, pan_direction)

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
        A sine-eased stereo sweep from left to right is applied over the full
        duration.

        Returns:
            Float32 stereo (N, 2) array of audio samples.

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
        mono = np.concatenate(parts)
        return SoundPlayer.apply_sine_pan(mono, 'left_to_right')

    @staticmethod
    @lru_cache
    def generate_save_confirmed_wave() -> np.ndarray:
        """
        Generate a high bell ting using additive synthesis.

        Four inharmonic partials (x1, x2.76, x5.40, x8.93) at 1200 Hz with
        differential decay rates — bright metallic attack with clean ring.

        Returns:
            Float32 array of audio samples.

        """
        fundamental = 1200.0
        duration = 0.32
        volume = 0.20
        partials = (
            (1.00, 1.00, 4.0),
            (2.76, 0.80, 10.0),
            (5.40, 0.50, 18.0),
            (8.93, 0.25, 30.0),
        )
        samples = int(SAMPLE_RATE * duration)
        t = np.linspace(0, duration, samples, endpoint=False)
        wave = np.zeros(samples, dtype=np.float64)
        for ratio, amp, decay in partials:
            env = np.exp(-decay * t / duration)
            wave += amp * env * np.sin(2 * math.pi * fundamental * ratio * t)
        result = (volume * wave).astype(np.float32)
        attack = min(int(SAMPLE_RATE * 0.004), samples // 8)
        result[:attack] *= np.linspace(0.0, 1.0, attack).astype(np.float32)
        fade = min(int(SAMPLE_RATE * 0.010), samples // 4)
        result[-fade:] *= np.linspace(1.0, 0.0, fade).astype(np.float32)
        return result

    @staticmethod
    @lru_cache
    def generate_save_discarded_wave() -> np.ndarray:
        """
        Generate a low buzz thud using additive synthesis.

        Three partials (x1, x1.5, x2.1) at 220 Hz with slow decay —
        heavy, rounded low-end thud.

        Returns:
            Float32 array of audio samples.

        """
        fundamental = 220.0
        duration = 0.28
        volume = 0.30
        partials = (
            (1.00, 1.00, 3.5),
            (1.50, 0.80, 6.0),
            (2.10, 0.55, 11.0),
        )
        samples = int(SAMPLE_RATE * duration)
        t = np.linspace(0, duration, samples, endpoint=False)
        wave = np.zeros(samples, dtype=np.float64)
        for ratio, amp, decay in partials:
            env = np.exp(-decay * t / duration)
            wave += amp * env * np.sin(2 * math.pi * fundamental * ratio * t)
        result = (volume * wave).astype(np.float32)
        attack = min(int(SAMPLE_RATE * 0.004), samples // 8)
        result[:attack] *= np.linspace(0.0, 1.0, attack).astype(np.float32)
        fade = min(int(SAMPLE_RATE * 0.010), samples // 4)
        result[-fade:] *= np.linspace(1.0, 0.0, fade).astype(np.float32)
        return result

    @staticmethod
    @lru_cache
    def generate_thud_wave(
        tone: Tone,
        partials: tuple[tuple[float, float, float], ...],
    ) -> np.ndarray:
        """
        Generate a rounded low thud using additive synthesis.

        Sums sine partials with individual exponential decay rates for a
        muffled, dying-out character.

        Returns:
            Float32 array of audio samples.

        """
        samples = int(SAMPLE_RATE * tone.duration)
        t = np.linspace(0, tone.duration, samples, endpoint=False)
        wave = np.zeros(samples, dtype=np.float64)
        for ratio, amp, decay in partials:
            env = np.exp(-decay * t / tone.duration)
            wave += amp * env * np.sin(
                2 * math.pi * tone.frequency * ratio * t,
            )
        result = (tone.volume * wave).astype(np.float32)
        fade = min(int(SAMPLE_RATE * 0.008), samples // 4)
        result[-fade:] *= np.linspace(1.0, 0.0, fade)
        return result

    @staticmethod
    @lru_cache
    def generate_misoriented_wave() -> np.ndarray:
        """
        Generate a klaxon variant ending on a muffled low thud.

        Same two opening tones as the missed klaxon (400 then 1200 Hz) but
        the final note is a rounded 110 Hz thud — a duller close that marks
        a wrong-direction turn apart from a wrong-face turn. The same
        right-to-left stereo sweep as the missed klaxon is applied over the
        full duration.

        Returns:
            Float32 stereo (N, 2) array of audio samples.

        """
        klaxon = SoundPlayer.generate_trio_wave(
            MISORIENTED_FREQS,
            MISORIENTED_DURATIONS,
            MISSED_GAP,
            MISSED_VOLUME,
        )
        thud = SoundPlayer.generate_thud_wave(MISORIENTED_THUD, THUD_PARTIALS)
        gap = np.zeros(int(SAMPLE_RATE * MISSED_GAP), dtype=np.float32)
        mono = np.concatenate([klaxon, gap, thud])
        return SoundPlayer.apply_sine_pan(mono, MISSED_PAN)

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

    @staticmethod
    @lru_cache
    def generate_failed_wave() -> np.ndarray:
        """
        Generate a descending four-note minor fanfare using additive synthesis.

        Same five inharmonic partials as success but applied to E5→C5→Ab4→Eb4
        (one octave lower, Ab minor descent) with a decrescendo volume envelope
        and 0.040s gaps — slow, sombre mirror of the success sound. A
        sine-eased stereo sweep from right to left is applied over the full
        duration.

        Returns:
            Float32 stereo (N, 2) array of audio samples.

        """
        partials = (
            (1.00, 0.55, 4.0),
            (2.76, 1.00, 8.0),
            (5.40, 1.20, 8.0),
            (8.93, 1.10, 14.0),
            (13.00, 0.60, 30.0),
        )
        freqs = (659.25, 523.25, 415.30, 311.13)
        durs = (0.07, 0.07, 0.07, 0.20)
        vols = (0.28, 0.22, 0.17, 0.14)
        gap_samples = np.zeros(int(SAMPLE_RATE * 0.040), dtype=np.float32)
        parts: list[np.ndarray] = []
        for i, (freq, dur, vol) in enumerate(
            zip(freqs, durs, vols, strict=True),
        ):
            samples = int(SAMPLE_RATE * dur)
            t = np.linspace(0, dur, samples, endpoint=False)
            wave = np.zeros(samples, dtype=np.float64)
            for ratio, amp, decay in partials:
                env = np.exp(-decay * t / dur)
                wave += amp * env * np.sin(2 * math.pi * freq * ratio * t)
            result = (vol * wave).astype(np.float32)
            fade = min(int(SAMPLE_RATE * 0.012), samples // 4)
            result[-fade:] *= np.linspace(1.0, 0.0, fade)
            parts.append(result)
            if i < len(freqs) - 1:
                parts.append(gap_samples)
        mono = np.concatenate(parts)
        return SoundPlayer.apply_sine_pan(mono, 'right_to_left')

    def play_tone(self, name: str) -> None:
        """Play a named tone."""
        tone = TONES[name]
        self.play(lambda: self.generate_wave(tone))

    def metronome_tick(self) -> None:
        """Play a short neutral tick for metronome beats."""
        self.play(self.generate_metronome_wave)

    def cube_connected(self) -> None:
        """Play an ascending triple beep when a Bluetooth cube connects."""
        self.play(
            lambda: self.generate_trio_wave(
                CONNECTED_FREQS,
                TRIO_DURATIONS,
                TRIO_GAP,
                TRIO_VOLUME,
                CONNECTED_PAN,
            ),
        )

    def cube_not_connected(self) -> None:
        """Play a low descending beep when Bluetooth cube is unavailable."""
        self.play(
            lambda: self.generate_trio_wave(
                NOT_CONNECTED_FREQS,
                NOT_CONNECTED_DURATIONS,
                TRIO_GAP,
                NOT_CONNECTED_VOLUME,
                NOT_CONNECTED_PAN,
            ),
        )

    def cube_disconnected(self) -> None:
        """Play a descending triple beep when a Bluetooth cube disconnects."""
        self.play(
            lambda: self.generate_trio_wave(
                DISCONNECTED_FREQS,
                DISCONNECTED_DURATIONS,
                TRIO_GAP,
                DISCONNECTED_VOLUME,
                DISCONNECTED_PAN,
            ),
        )

    def solve_scrambled(self) -> None:
        """Play a confirmation tone when scramble is finalized."""
        self.play(self.generate_scrambled_wave)

    def solve_step(self) -> None:
        """Play a higher-pitched beep when a solve step is completed."""
        self.play(self.generate_step_wave)

    def solve_success(self) -> None:
        """Play a bright tone on solve, training, or drill completion."""
        self.play(self.generate_success_wave)

    def solve_failed(self) -> None:
        """Play a sombre descending tone on failed solve or drill."""
        self.play(self.generate_failed_wave)

    def save_confirmed(self) -> None:
        """Play a high bell ting when results are saved."""
        self.play(self.generate_save_confirmed_wave)

    def save_discarded(self) -> None:
        """Play a low buzz thud when results are discarded."""
        self.play(self.generate_save_discarded_wave)

    def cube_move_missed(self) -> None:
        """Play a short klaxon buzz when a move is executed incorrectly."""
        self.play(
            lambda: self.generate_trio_wave(
                MISSED_FREQS,
                MISSED_DURATIONS,
                MISSED_GAP,
                MISSED_VOLUME,
                MISSED_PAN,
            ),
        )

    def cube_move_misoriented(self) -> None:
        """Play a muffled klaxon when a face is turned the wrong way."""
        self.play(self.generate_misoriented_wave)

    def la_3(self) -> None:
        """Play a LA 3."""
        self.play_tone('LA_3')

    def la_4(self) -> None:
        """Play a LA 4."""
        self.play_tone('LA_4')


SOUND_PLAYER = SoundPlayer()

if __name__ == '__main__':
    import sys
    import time

    sounds = [
        'cube_connected',
        'cube_not_connected',
        'cube_disconnected',
        'cube_move_missed',
        'cube_move_misoriented',
        'solve_scrambled',
        'solve_step',
        'solve_success',
        'solve_failed',
        'save_confirmed',
        'save_discarded',
        'metronome_tick',
        'la_3',
        'la_4',
    ]

    if not SOUND_PLAYER.available:
        print('No audio device found, using terminal bell fallback.')

    if len(sys.argv) > 1:
        name = sys.argv[1]
        if name not in sounds:
            print(f'Unknown sound: {name!r}')
            print(f'Available: {", ".join(sounds)}')
            sys.exit(1)
        method = getattr(SOUND_PLAYER, name)
        print(f'Playing: {name} (Ctrl+C to quit)')
        try:
            while True:
                method()
                time.sleep(1.5)
        except KeyboardInterrupt:
            print('\nDone.')
    else:
        print(f'Playing all sounds: {", ".join(sounds)} (Ctrl+C to quit)')
        try:
            while True:
                for name in sounds:
                    print(f'  {name}')
                    getattr(SOUND_PLAYER, name)()
                    time.sleep(1.5)
                time.sleep(1.0)
        except KeyboardInterrupt:
            print('\nDone.')
