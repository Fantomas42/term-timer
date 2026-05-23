"""Tests for the SoundPlayer class."""
import io
import unittest
from contextlib import AbstractContextManager
from unittest.mock import MagicMock
from unittest.mock import patch

import numpy as np

import term_timer.interface.sounds as sounds_mod
from term_timer.interface.sounds import SoundPlayer
from term_timer.interface.sounds import Tone

FADE_THRESHOLD = 0.01


def _patch_sd(mock_sd: MagicMock) -> AbstractContextManager[MagicMock]:
    """
    Patch the module-level sd name, creating it if sounddevice is absent.

    Returns:
        Context manager that patches sd in the sounds module.

    """
    return patch.object(sounds_mod, 'sd', mock_sd, create=True)


class TestSoundPlayerFallback(unittest.TestCase):
    """SoundPlayer falls back to terminal bell when audio is unavailable."""

    def test_all_methods_use_bell_when_unavailable(self) -> None:
        """All sound methods print a bell char when audio is unavailable."""
        player = SoundPlayer.__new__(SoundPlayer)
        player.available = False

        methods = ('metronome_tick', 'solve_step', 'solve_scrambled',
                   'cube_connected', 'solve_success')
        buf = io.StringIO()
        with patch('sys.stdout', buf):
            for method in methods:
                getattr(player, method)()

        self.assertEqual(buf.getvalue(), '\a' * 5)


class TestProbeAudio(unittest.TestCase):
    """SoundPlayer.probe_audio() detects device availability."""

    def test_returns_true_when_device_available(self) -> None:
        """Returns True when sounddevice reports a valid output device."""
        mock_sd = MagicMock()
        mock_sd.query_devices.return_value = {'name': 'default'}

        with _patch_sd(mock_sd), \
                patch.object(sounds_mod, 'SOUNDDEVICE_AVAILABLE', new=True):
            result = SoundPlayer.probe_audio()

        self.assertTrue(result)

    def test_returns_false_when_query_raises(self) -> None:
        """Returns False when query_devices raises any exception."""
        mock_sd = MagicMock()
        mock_sd.query_devices.side_effect = Exception('no device')

        with _patch_sd(mock_sd), \
                patch.object(sounds_mod, 'SOUNDDEVICE_AVAILABLE', new=True):
            result = SoundPlayer.probe_audio()

        self.assertFalse(result)

    def test_returns_false_when_sounddevice_not_available(self) -> None:
        """Returns False when sounddevice import failed."""
        with patch.object(sounds_mod, 'SOUNDDEVICE_AVAILABLE', new=False):
            result = SoundPlayer.probe_audio()

        self.assertFalse(result)


class TestSoundPlayerPlay(unittest.TestCase):
    """SoundPlayer calls sd.play when audio device is available."""

    def test_play_calls_sd_play_when_available(self) -> None:
        """play() calls sd.play with blocking=False when audio is available."""
        mock_sd = MagicMock()

        player = SoundPlayer.__new__(SoundPlayer)
        player.available = True

        with _patch_sd(mock_sd):
            player.metronome_tick()

        mock_sd.play.assert_called_once()
        _, kwargs = mock_sd.play.call_args
        self.assertFalse(kwargs.get('blocking'))

    def test_each_method_triggers_play(self) -> None:
        """Each named method results in exactly one sd.play call."""
        for method in ('metronome_tick', 'solve_step', 'solve_scrambled',
                       'cube_connected', 'solve_success'):
            mock_sd = MagicMock()
            player = SoundPlayer.__new__(SoundPlayer)
            player.available = True

            with _patch_sd(mock_sd):
                getattr(player, method)()

            self.assertEqual(mock_sd.play.call_count, 1)


class TestGenerateWave(unittest.TestCase):
    """Wave generation produces correctly shaped float32 arrays."""

    def test_wave_length_matches_duration(self) -> None:
        """Wave length equals sample_rate * duration."""
        tone = Tone(440.0, 0.1, 0.5)
        wave = SoundPlayer.generate_wave(tone)
        self.assertEqual(len(wave), int(sounds_mod.SAMPLE_RATE * tone.duration))

    def test_wave_dtype_is_float32(self) -> None:
        """Generated wave array has dtype float32."""
        wave = SoundPlayer.generate_wave(Tone(440.0, 0.05, 0.3))
        self.assertEqual(wave.dtype, np.float32)

    def test_wave_amplitude_within_volume(self) -> None:
        """Peak amplitude does not exceed the specified volume."""
        tone = Tone(440.0, 0.1, 0.4)
        wave = SoundPlayer.generate_wave(tone)
        self.assertLessEqual(float(wave.max()), tone.volume + 1e-6)

    def test_fade_out_applied(self) -> None:
        """Last sample is near zero due to fade-out."""
        wave = SoundPlayer.generate_wave(Tone(440.0, 0.5, 1.0))
        self.assertLess(abs(float(wave[-1])), FADE_THRESHOLD)
