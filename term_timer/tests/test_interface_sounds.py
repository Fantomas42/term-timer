"""Tests for the SoundPlayer class."""
from unittest.mock import MagicMock
from unittest.mock import patch

import numpy as np
import pytest

import term_timer.interface.sounds as sounds_mod
from term_timer.interface.sounds import SoundPlayer
from term_timer.interface.sounds import Tone
from term_timer.interface.sounds import _generate_wave
from term_timer.interface.sounds import _probe_audio


def _patch_sd(mock_sd: MagicMock):
    """Patch the module-level sd name, creating it if sounddevice is absent."""
    return patch.object(sounds_mod, 'sd', mock_sd, create=True)


class TestSoundPlayerFallback:
    """SoundPlayer falls back to terminal bell when audio is unavailable."""

    def test_all_methods_use_bell_when_unavailable(self, capsys):
        player = SoundPlayer.__new__(SoundPlayer)
        player._available = False

        for method in ('metronome', 'step', 'countdown', 'scramble', 'generic'):
            getattr(player, method)()

        captured = capsys.readouterr()
        assert captured.out == '\a' * 5

    def test_play_falls_back_to_bell_on_sd_exception(self, capsys):
        mock_sd = MagicMock()
        mock_sd.play.side_effect = Exception('audio error')

        player = SoundPlayer.__new__(SoundPlayer)
        player._available = True

        with _patch_sd(mock_sd):
            player.step()

        captured = capsys.readouterr()
        assert captured.out == '\a'


class TestProbeAudio:
    """_probe_audio() detects device availability."""

    def test_returns_true_when_device_available(self):
        mock_sd = MagicMock()
        mock_sd.query_devices.return_value = {'name': 'default'}

        with _patch_sd(mock_sd):
            with patch.object(sounds_mod, '_SOUNDDEVICE_AVAILABLE', True):
                result = _probe_audio()

        assert result is True

    def test_returns_false_when_query_raises(self):
        mock_sd = MagicMock()
        mock_sd.query_devices.side_effect = Exception('no device')

        with _patch_sd(mock_sd):
            with patch.object(sounds_mod, '_SOUNDDEVICE_AVAILABLE', True):
                result = _probe_audio()

        assert result is False

    def test_returns_false_when_sounddevice_not_available(self):
        with patch.object(sounds_mod, '_SOUNDDEVICE_AVAILABLE', False):
            result = _probe_audio()

        assert result is False


class TestSoundPlayerPlay:
    """SoundPlayer calls sd.play when audio device is available."""

    def test_play_calls_sd_play_when_available(self):
        mock_sd = MagicMock()

        player = SoundPlayer.__new__(SoundPlayer)
        player._available = True

        with _patch_sd(mock_sd):
            player.metronome()

        mock_sd.play.assert_called_once()
        _, kwargs = mock_sd.play.call_args
        assert kwargs.get('blocking') is False

    @pytest.mark.parametrize('method', ['metronome', 'step', 'countdown', 'scramble', 'generic'])
    def test_each_method_triggers_play(self, method):
        mock_sd = MagicMock()

        player = SoundPlayer.__new__(SoundPlayer)
        player._available = True

        with _patch_sd(mock_sd):
            getattr(player, method)()

        mock_sd.play.assert_called_once()


class TestGenerateWave:
    """Wave generation produces correctly shaped float32 arrays."""

    def test_wave_length_matches_duration(self):
        tone = Tone(440.0, 0.1, 0.5)
        wave = _generate_wave(tone)
        assert len(wave) == int(sounds_mod.SAMPLE_RATE * tone.duration)

    def test_wave_dtype_is_float32(self):
        wave = _generate_wave(Tone(440.0, 0.05, 0.3))
        assert wave.dtype == np.float32

    def test_wave_amplitude_within_volume(self):
        tone = Tone(440.0, 0.1, 0.4)
        wave = _generate_wave(tone)
        assert float(wave.max()) <= tone.volume + 1e-6

    def test_fade_out_applied(self):
        wave = _generate_wave(Tone(440.0, 0.5, 1.0))
        assert abs(float(wave[-1])) < 0.01
