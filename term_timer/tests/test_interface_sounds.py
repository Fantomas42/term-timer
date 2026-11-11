"""Tests for the SoundPlayer class."""
import builtins
import io
import os
import subprocess  # noqa: S404
import sys
import threading
import time
import unittest
from collections.abc import Callable
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import numpy as np

import term_timer.interface.sounds as sounds_mod
from term_timer.interface.sounds import SoundPlayer
from term_timer.interface.sounds import Tone

FADE_THRESHOLD = 0.01

# Seconds a fake slow device blocks whoever calls it
SLOW_DEVICE = 0.5

# Lateness tolerated in the tests of a slow device
SHORT_DELAY = SLOW_DEVICE / 5


@contextmanager
def fake_device(mock_sd: MagicMock) -> Iterator[SoundPlayer]:
    """
    Give a player in audio mode whose audio thread loads a fake device.

    Leaving the context drains the player: every sound posted inside has
    reached the device, or was dropped, once it is left.

    Yields:
        The player, its audio thread not started yet.

    """
    player = SoundPlayer()

    def load_device(loaded: SoundPlayer) -> bool:
        loaded.device = mock_sd
        return True

    with patch.object(sounds_mod, 'TIMER_SOUND', new='audio'), \
            patch.object(SoundPlayer, 'load_device', load_device):
        try:
            yield player
        finally:
            player.drain()


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


class TestLoadDevice(unittest.TestCase):
    """SoundPlayer.load_device() imports sounddevice and probes it."""

    def test_returns_true_when_device_available(self) -> None:
        """Returns True and keeps the module when a device answers."""
        mock_sd = MagicMock()
        mock_sd.query_devices.return_value = {'name': 'default'}
        player = SoundPlayer()

        with patch.dict(sys.modules, {'sounddevice': mock_sd}):
            result = player.load_device()

        self.assertTrue(result)
        self.assertIs(player.device, mock_sd)

    def test_returns_false_when_query_raises(self) -> None:
        """Returns False when query_devices raises any exception."""
        mock_sd = MagicMock()
        mock_sd.query_devices.side_effect = Exception('no device')
        player = SoundPlayer()

        with patch.dict(sys.modules, {'sounddevice': mock_sd}):
            result = player.load_device()

        self.assertFalse(result)
        self.assertIsNone(player.device)

    def test_returns_false_when_portaudio_is_missing(self) -> None:
        """Returns False, with a hint, when the import finds no PortAudio."""
        player = SoundPlayer()
        buf = io.StringIO()

        with patch('sys.stdout', buf), patch.object(
            builtins, '__import__',
            side_effect=OSError('PortAudio library not found'),
        ):
            result = player.load_device()

        self.assertFalse(result)
        self.assertIn('No PortAudio installed', buf.getvalue())

    def test_building_a_player_loads_nothing(self) -> None:
        """A new player has neither a thread nor a device."""
        player = SoundPlayer()

        self.assertIsNone(player.thread)
        self.assertIsNone(player.device)


class TestSoundPlayerPlay(unittest.TestCase):
    """SoundPlayer calls sd.play when audio device is available."""

    def test_play_calls_sd_play_when_available(self) -> None:
        """play() calls sd.play with blocking=False when audio is available."""
        mock_sd = MagicMock()

        with fake_device(mock_sd) as player:
            player.metronome_tick()

        mock_sd.play.assert_called_once()
        _, kwargs = mock_sd.play.call_args
        self.assertFalse(kwargs.get('blocking'))

    def test_play_goes_through_output(self) -> None:
        """play() hands the wave to output(), the only door to the device."""
        mock_sd = MagicMock()

        with patch.object(SoundPlayer, 'output') as output, \
                fake_device(mock_sd) as player:
            player.metronome_tick()

        output.assert_called_once()
        (wave,), _ = output.call_args
        self.assertIs(wave, SoundPlayer.generate_metronome_wave())
        mock_sd.play.assert_not_called()

    def test_each_method_triggers_play(self) -> None:
        """Each named method results in exactly one sd.play call."""
        for method in ('metronome_tick', 'solve_step', 'solve_scrambled',
                       'cube_connected', 'solve_success'):
            mock_sd = MagicMock()

            with fake_device(mock_sd) as player:
                getattr(player, method)()

            self.assertEqual(mock_sd.play.call_count, 1)


class TestSoundPlayerModes(unittest.TestCase):
    """play() dispatches on the configured sound mode."""

    @staticmethod
    def run_mode(
        mode: str, *, available: bool = True,
    ) -> tuple[MagicMock, SoundPlayer, str]:
        """
        Play one sound under a mode, on a fake device.

        Returns:
            The sounddevice mock, the player, and what stdout received.

        """
        mock_sd = MagicMock()
        buf = io.StringIO()

        with fake_device(mock_sd) as player, \
                patch.object(sounds_mod, 'TIMER_SOUND', new=mode), \
                patch('sys.stdout', buf):
            player.available = available
            player.solve_step()

        return mock_sd, player, buf.getvalue()

    def test_off_stays_silent(self) -> None:
        """The off mode plays nothing, rings nothing, starts no thread."""
        mock_sd, player, output = self.run_mode('off')

        mock_sd.play.assert_not_called()
        self.assertEqual(output, '')
        self.assertIsNone(player.thread)

    def test_audio_plays_wave(self) -> None:
        """The audio mode plays the wave on the device."""
        mock_sd, _, output = self.run_mode('audio')

        mock_sd.play.assert_called_once()
        self.assertEqual(output, '')

    def test_terminal_rings_bell(self) -> None:
        """The terminal mode rings the bell from the caller, no thread."""
        mock_sd, player, output = self.run_mode('terminal')

        mock_sd.play.assert_not_called()
        self.assertEqual(output, '\a')
        self.assertIsNone(player.thread)

    def test_unknown_mode_rings_bell(self) -> None:
        """An unknown mode falls back to the terminal bell."""
        mock_sd, _, output = self.run_mode('bruit')

        mock_sd.play.assert_not_called()
        self.assertEqual(output, '\a')

    def test_audio_without_device_rings_bell(self) -> None:
        """The audio mode rings the bell when no device is available."""
        mock_sd, _, output = self.run_mode('audio', available=False)

        mock_sd.play.assert_not_called()
        self.assertEqual(output, '\a')


class TestSoundPlayerThread(unittest.TestCase):
    """The audio device is driven by one thread, off the caller's path."""

    def test_play_does_not_wait_for_a_slow_device(self) -> None:
        """play() returns at once while the device blocks its caller."""
        released = threading.Event()
        player = SoundPlayer()
        self.addCleanup(player.drain)
        self.addCleanup(released.set)

        def slow_output(_player: SoundPlayer, _wave: np.ndarray) -> None:
            released.wait(SLOW_DEVICE)

        with patch.object(sounds_mod, 'TIMER_SOUND', new='audio'), \
                patch.object(SoundPlayer, 'load_device', return_value=True), \
                patch.object(SoundPlayer, 'output', slow_output):
            start = time.monotonic()
            player.metronome_tick()
            elapsed = time.monotonic() - start

        self.assertLess(elapsed, SLOW_DEVICE / 10)

    def test_sounds_keep_their_order_on_a_single_thread(self) -> None:
        """Sounds posted by several threads are played by one, in order."""
        played: list[tuple[int, int]] = []

        def recording_output(_player: SoundPlayer, wave: np.ndarray) -> None:
            played.append((threading.get_ident(), len(wave)))

        def give(wave: np.ndarray) -> Callable[[], np.ndarray]:
            return lambda: wave

        waves = [np.zeros(size, dtype=np.float32) for size in range(1, 7)]

        with patch.object(SoundPlayer, 'output', recording_output), \
                fake_device(MagicMock()) as player:
            for first, second in zip(waves[::2], waves[1::2], strict=True):
                player.play(give(first))
                poster = threading.Thread(
                    target=player.play, args=(give(second),),
                )
                poster.start()
                poster.join()

        self.assertEqual([size for _, size in played], [1, 2, 3, 4, 5, 6])
        threads = {ident for ident, _ in played}
        self.assertEqual(len(threads), 1)
        self.assertNotIn(threading.get_ident(), threads)

    def test_late_sound_is_dropped(self) -> None:
        """A sound that waited too long behind a slow device is dropped."""
        played: list[int] = []

        def slow_output(_player: SoundPlayer, wave: np.ndarray) -> None:
            played.append(len(wave))
            time.sleep(SLOW_DEVICE)

        with patch.object(sounds_mod, 'SOUND_MAX_DELAY', new=SHORT_DELAY), \
                patch.object(SoundPlayer, 'output', slow_output), \
                fake_device(MagicMock()) as player:
            player.play(lambda: np.zeros(1, dtype=np.float32))
            player.play(lambda: np.zeros(2, dtype=np.float32))

        self.assertEqual(played, [1])

    def test_first_sound_survives_a_slow_loading(self) -> None:
        """The loading of the device never counts as lateness."""
        mock_sd = MagicMock()
        player = SoundPlayer()

        def slow_load(loaded: SoundPlayer) -> bool:
            time.sleep(SLOW_DEVICE)
            loaded.device = mock_sd
            return True

        with patch.object(sounds_mod, 'TIMER_SOUND', new='audio'), \
                patch.object(sounds_mod, 'SOUND_MAX_DELAY', new=SHORT_DELAY), \
                patch.object(SoundPlayer, 'load_device', slow_load):
            player.solve_step()
            player.drain()

        self.assertEqual(mock_sd.play.call_count, 1)

    def test_warm_up_loads_the_device_without_playing(self) -> None:
        """warm_up() gets the device loaded ahead of the first sound."""
        mock_sd = MagicMock()

        with fake_device(mock_sd) as player:
            player.warm_up()
            loaded = player.ready.wait(SLOW_DEVICE)

        self.assertTrue(loaded)
        mock_sd.play.assert_not_called()

    def test_first_sound_after_a_warm_up_skips_the_loading(self) -> None:
        """Once warmed up, a sound reaches the device without loading it."""
        mock_sd = MagicMock()
        player = SoundPlayer()
        self.addCleanup(player.drain)
        played = threading.Event()
        mock_sd.play.side_effect = lambda *_args, **_kwargs: played.set()

        def slow_load(loaded: SoundPlayer) -> bool:
            time.sleep(SLOW_DEVICE)
            loaded.device = mock_sd
            return True

        with patch.object(sounds_mod, 'TIMER_SOUND', new='audio'), \
                patch.object(SoundPlayer, 'load_device', slow_load):
            player.warm_up()
            player.ready.wait(SLOW_DEVICE * 2)
            start = time.monotonic()
            player.solve_step()
            played.wait(SLOW_DEVICE * 2)
            elapsed = time.monotonic() - start

        self.assertTrue(played.is_set())
        self.assertLess(elapsed, SLOW_DEVICE / 2)

    def test_warm_up_starts_nothing_out_of_audio_mode(self) -> None:
        """Without the audio mode, warm_up() neither loads nor rings."""
        for mode in ('off', 'terminal'):
            with self.subTest(mode=mode):
                player = SoundPlayer()

                with patch.object(sounds_mod, 'TIMER_SOUND', new=mode), \
                        patch.object(SoundPlayer, 'bell') as bell:
                    player.warm_up()

                self.assertIsNone(player.thread)
                bell.assert_not_called()

    def test_failing_device_falls_back_to_bell(self) -> None:
        """A device failing in the thread rings the bell from then on."""
        mock_sd = MagicMock()
        mock_sd.play.side_effect = RuntimeError('device unplugged')
        buf = io.StringIO()

        with fake_device(mock_sd) as player, patch('sys.stdout', buf), \
                self.assertLogs(sounds_mod.logger, 'ERROR'):
            player.solve_step()
            player.ready.wait()
            while player.available:
                time.sleep(0.001)
            player.solve_step()

        self.assertEqual(mock_sd.play.call_count, 1)
        self.assertEqual(buf.getvalue(), '\a\a')

    def test_missing_device_rings_bell_for_queued_sounds(self) -> None:
        """Sounds queued before the device is found missing ring the bell."""
        player = SoundPlayer()
        buf = io.StringIO()

        with patch.object(sounds_mod, 'TIMER_SOUND', new='audio'), \
                patch.object(SoundPlayer, 'load_device', return_value=False), \
                patch('sys.stdout', buf):
            player.solve_step()
            player.drain()
            player.solve_step()

        self.assertFalse(player.available)
        self.assertEqual(buf.getvalue(), '\a\a')

    def test_drain_waits_for_the_end_of_the_last_sound(self) -> None:
        """drain() lets the device finish, then the thread ends."""
        mock_sd = MagicMock()

        with fake_device(mock_sd) as player:
            player.solve_success()

        mock_sd.wait.assert_called_once()
        thread = player.thread
        self.assertTrue(thread is not None and not thread.is_alive())

    def test_drain_without_any_sound_does_nothing(self) -> None:
        """drain() on a player that never played starts no thread."""
        player = SoundPlayer()
        player.drain()

        self.assertIsNone(player.thread)

    def test_only_this_module_knows_sounddevice(self) -> None:
        """No other module of the package can call the device directly."""
        package = Path(sounds_mod.__file__).parent.parent
        users = sorted(
            str(path.relative_to(package))
            for path in package.rglob('*.py')
            if path.relative_to(package).parts[0] not in {'poc', 'tests'}
            and 'sounddevice' in path.read_text(encoding='utf-8')
        )

        self.assertEqual(users, ['interface/sounds.py'])


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


class TestNumpyThreads(unittest.TestCase):
    """
    The numpy imported for the sounds starts no BLAS thread pool.

    The waves are elementwise arithmetic, no BLAS routine ever runs, yet
    OpenBLAS starts one spinning thread per core at import time: 1.6s of
    CPU at every command on a 20 cores machine.
    """

    @staticmethod
    def run_python(code: str, **env: str) -> str:
        """
        Run code in a fresh interpreter, without inherited BLAS setting.

        Returns:
            The stripped standard output.

        """
        environ = {
            key: value
            for key, value in os.environ.items()
            if key != 'OPENBLAS_NUM_THREADS'
        }
        environ.update(env)
        result = subprocess.run(  # noqa: S603
            [sys.executable, '-c', code],
            capture_output=True,
            check=True,
            env=environ,
            text=True,
        )
        return result.stdout.strip()

    def test_blas_limited_to_one_thread(self) -> None:
        """Importing the package caps OpenBLAS to a single thread."""
        output = self.run_python(
            'import os, term_timer; '
            'print(os.environ["OPENBLAS_NUM_THREADS"])',
        )
        self.assertEqual(output, '1')

    def test_explicit_setting_is_kept(self) -> None:
        """A thread count exported by the user wins over the default."""
        output = self.run_python(
            'import os, term_timer; '
            'print(os.environ["OPENBLAS_NUM_THREADS"])',
            OPENBLAS_NUM_THREADS='4',
        )
        self.assertEqual(output, '4')

    @unittest.skipUnless(
        Path('/proc/self/task').is_dir(), 'needs /proc to count threads',
    )
    def test_sounds_import_starts_no_thread(self) -> None:
        """Importing the sounds leaves the process single threaded."""
        output = self.run_python(
            'import os, term_timer.interface.sounds; '
            'print(len(os.listdir("/proc/self/task")))',
        )
        self.assertEqual(output, '1')
