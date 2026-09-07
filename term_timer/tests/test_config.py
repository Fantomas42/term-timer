"""Tests for config helpers."""
import os
import unittest
from pathlib import Path
from typing import ClassVar
from typing import cast
from unittest.mock import patch

from term_timer.config import CubeDevice
from term_timer.config import env_flag
from term_timer.config import env_string
from term_timer.config import is_cube_address
from term_timer.config import iter_endpoints
from term_timer.config import load_cubes
from term_timer.config import load_default_cube
from term_timer.config import parse_endpoint
from term_timer.config import parse_endpoints
from term_timer.config import parse_series


class TestParseSeries(unittest.TestCase):
    """Tests for parse_series."""

    def test_default_tokens(self) -> None:
        """All four kinds of valid tokens are parsed."""
        self.assertEqual(
            parse_series(['ao5', 'ao12', 'ao100', 'ao1000']),
            [('ao', 5), ('ao', 12), ('ao', 100), ('ao', 1000)],
        )

    def test_all_kinds(self) -> None:
        """Every supported kind is recognised."""
        self.assertEqual(
            parse_series(['mo3', 'ao5', 'mb3', 'mw10']),
            [('mo', 3), ('ao', 5), ('mb', 3), ('mw', 10)],
        )

    def test_order_preserved(self) -> None:
        """The user-provided order is kept as-is."""
        self.assertEqual(
            parse_series(['ao1000', 'ao5', 'ao100', 'ao12']),
            [('ao', 1000), ('ao', 5), ('ao', 100), ('ao', 12)],
        )

    def test_invalid_tokens_ignored(self) -> None:
        """Unrecognised tokens are silently dropped."""
        self.assertEqual(
            parse_series(['ao5', 'foo', 'po12', 'ao', '5', 'ao12']),
            [('ao', 5), ('ao', 12)],
        )

    def test_deduplicate_first_occurrence(self) -> None:
        """Duplicates are dropped on their first occurrence."""
        self.assertEqual(
            parse_series(['ao5', 'ao12', 'ao5', 'ao12']),
            [('ao', 5), ('ao', 12)],
        )

    def test_case_and_whitespace_normalised(self) -> None:
        """Tokens are lowercased and stripped before matching."""
        self.assertEqual(
            parse_series([' AO5 ', 'Ao12']),
            [('ao', 5), ('ao', 12)],
        )

    def test_empty(self) -> None:
        """An empty list yields an empty series."""
        self.assertEqual(parse_series([]), [])

    def test_kinds_restriction(self) -> None:
        """Tokens whose kind is excluded are dropped."""
        self.assertEqual(
            parse_series(
                ['mo3', 'ao5', 'mb3', 'mw10'],
                ('mo', 'ao'),
            ),
            [('mo', 3), ('ao', 5)],
        )

    def test_kinds_restriction_keeps_order(self) -> None:
        """Restricting kinds preserves the order of accepted tokens."""
        self.assertEqual(
            parse_series(
                ['mb3', 'ao12', 'mw5', 'mo3'],
                ('mo', 'ao'),
            ),
            [('ao', 12), ('mo', 3)],
        )


class TestParseEndpoint(unittest.TestCase):
    """Tests for parse_endpoint."""

    def test_ipc_path_expanded(self) -> None:
        """A tilde in a socket path is a home, not a directory."""
        self.assertEqual(
            parse_endpoint('ipc://~/.term_timer/cube.ipc'),
            f'ipc://{ Path.home() / ".term_timer" / "cube.ipc" }',
        )

    def test_other_transports_untouched(self) -> None:
        """Only an ipc address is a path, so only it is expanded."""
        self.assertEqual(
            parse_endpoint('tcp://~host:5555'),
            'tcp://~host:5555',
        )

    def test_surrounding_spaces_ignored(self) -> None:
        """What is typed by hand may be padded."""
        self.assertEqual(
            parse_endpoint(' tcp://127.0.0.1:5555 '),
            'tcp://127.0.0.1:5555',
        )

    def test_transportless_token_refused(self) -> None:
        """What names no transport is no endpoint."""
        for token in ('', '  ', 'cube.ipc', 'tcp://', '://cube'):
            with self.subTest(token=token):
                self.assertEqual(parse_endpoint(token), '')


class TestIterEndpoints(unittest.TestCase):
    """Tests for iter_endpoints."""

    def test_both_spellings_travel_along(self) -> None:
        """The token as typed, and the endpoint as ZeroMQ reads it."""
        self.assertEqual(
            list(iter_endpoints(['ipc://~/.term_timer/cube.ipc'])),
            [
                (
                    'ipc://~/.term_timer/cube.ipc',
                    f'ipc://{ Path.home() / ".term_timer" / "cube.ipc" }',
                ),
            ],
        )

    def test_the_token_is_yielded_stripped(self) -> None:
        """A line written with spaces is not written back with them."""
        self.assertEqual(
            list(iter_endpoints([' tcp://127.0.0.1:5555 '])),
            [('tcp://127.0.0.1:5555', 'tcp://127.0.0.1:5555')],
        )

    def test_duplicates_are_read_not_written(self) -> None:
        """Two spellings of one endpoint keep the first one only."""
        self.assertEqual(
            [
                token
                for token, _endpoint in iter_endpoints(
                    ['ipc://~/cube.ipc', f'ipc://{ Path.home() }/cube.ipc'],
                )
            ],
            ['ipc://~/cube.ipc'],
        )


class TestParseEndpoints(unittest.TestCase):
    """Tests for parse_endpoints."""

    def test_endpoints_kept_in_order(self) -> None:
        """The order the configuration lists is the binding order."""
        self.assertEqual(
            parse_endpoints(['tcp://127.0.0.1:5555', 'inproc://cube']),
            ['tcp://127.0.0.1:5555', 'inproc://cube'],
        )

    def test_ipc_path_expanded(self) -> None:
        """A tilde in a socket path is a home, not a directory."""
        self.assertEqual(
            parse_endpoints(['ipc://~/.term_timer/cube.ipc']),
            [f'ipc://{ Path.home() / ".term_timer" / "cube.ipc" }'],
        )

    def test_other_transports_untouched(self) -> None:
        """Only an ipc address is a path, so only it is expanded."""
        self.assertEqual(
            parse_endpoints(['tcp://~host:5555']),
            ['tcp://~host:5555'],
        )

    def test_transportless_tokens_ignored(self) -> None:
        """What names no transport never reaches ZeroMQ."""
        self.assertEqual(
            parse_endpoints(['', '  ', 'cube.ipc', 'tcp://', 'ipc://cube']),
            ['ipc://cube'],
        )

    def test_duplicates_dropped(self) -> None:
        """The same endpoint is never bound twice."""
        self.assertEqual(
            parse_endpoints(
                ['tcp://127.0.0.1:5555', ' tcp://127.0.0.1:5555 '],
            ),
            ['tcp://127.0.0.1:5555'],
        )


class TestIsCubeAddress(unittest.TestCase):
    """Tests for is_cube_address."""

    def test_mac_address(self) -> None:
        """A MAC address is recognised, whatever its case."""
        self.assertTrue(is_cube_address('AA:BB:CC:DD:EE:FF'))
        self.assertTrue(is_cube_address('aa:bb:cc:dd:ee:ff'))

    def test_system_uuid(self) -> None:
        """The device UUID macOS exposes instead of a MAC is recognised."""
        self.assertTrue(
            is_cube_address('E4B0C442-98FC-4C1B-9B2A-6F41A1B2C3D4'),
        )

    def test_labels_are_not_addresses(self) -> None:
        """A cube label, or a stray positional, is no address."""
        for value in ('gan12', '10', '', 'AA:BB:CC:DD:EE', 'auto'):
            with self.subTest(value=value):
                self.assertFalse(is_cube_address(value))


class TestLoadCubes(unittest.TestCase):
    """Tests for the cubes read from the Bluetooth configuration."""

    def test_cubes_tables(self) -> None:
        """Every cube table is loaded, keyed by a lowercased label."""
        cubes = load_cubes({
            'cubes': {
                'GAN12': {'name': 'GAN 12', 'address': 'AA:BB:CC:DD:EE:FF'},
                'weilong': {'address': '11:22:33:44:55:77'},
            },
        })

        self.assertEqual(list(cubes), ['gan12', 'weilong'])
        self.assertEqual(cubes['gan12'].name, 'GAN 12')
        self.assertEqual(cubes['gan12'].address, 'AA:BB:CC:DD:EE:FF')

    def test_per_cube_overrides(self) -> None:
        """A cube overrides the settings it declares, inherits the rest."""
        with (
                patch('term_timer.config.USE_GYROSCOPE', new=True),
                patch('term_timer.config.ROTATION_THRESHOLD', 75.0),
        ):
            cubes = load_cubes({
                'cubes': {
                    'weilong': {
                        'address': '11:22:33:44:55:77',
                        'use_gyroscope': False,
                        'rotation_threshold': 60.0,
                    },
                    'gan12': {'address': 'AA:BB:CC:DD:EE:FF'},
                },
            })

        self.assertFalse(cubes['weilong'].use_gyroscope)
        self.assertEqual(cubes['weilong'].rotation_threshold, 60.0)
        self.assertTrue(cubes['gan12'].use_gyroscope)
        self.assertEqual(cubes['gan12'].rotation_threshold, 75.0)

    def test_no_cube(self) -> None:
        """A configuration naming no cube loads none."""
        self.assertEqual(load_cubes({'use_gyroscope': True}), {})


class TestLoadDefaultCube(unittest.TestCase):
    """Tests for the cube designated as the default one."""

    CUBES: ClassVar[dict[str, CubeDevice]] = {
        'gan12': CubeDevice(label='gan12', address='AA:BB:CC:DD:EE:FF'),
        'weilong': CubeDevice(label='weilong', address='11:22:33:44:55:77'),
    }

    def test_designated_cube(self) -> None:
        """The designated cube wins, whatever its case."""
        self.assertEqual(
            load_default_cube({'default': 'WeiLong'}, self.CUBES),
            'weilong',
        )

    def test_lone_cube_is_its_own_default(self) -> None:
        """A single cube is the default, keeping a direct connection."""
        cubes = {'gan12': self.CUBES['gan12']}

        self.assertEqual(load_default_cube({}, cubes), 'gan12')

    def test_several_cubes_leave_the_choice_to_the_scan(self) -> None:
        """Several cubes and no designation means no default."""
        self.assertEqual(load_default_cube({}, self.CUBES), '')

    def test_unknown_designation_is_ignored(self) -> None:
        """A default naming no cube falls back on having none."""
        self.assertEqual(
            load_default_cube({'default': 'ghost'}, self.CUBES),
            '',
        )


class TestCubeDeviceResolve(unittest.TestCase):
    """Tests for the cube a selector resolves to."""

    CUBES: ClassVar[dict[str, CubeDevice]] = {
        'gan12': CubeDevice(
            label='gan12',
            name='GAN 12',
            address='AA:BB:CC:DD:EE:FF',
        ),
        'weilong': CubeDevice(
            label='weilong',
            address='11:22:33:44:55:77',
            use_gyroscope=False,
        ),
    }

    def test_off_disables_the_cube(self) -> None:
        """The off selector connects to nothing."""
        with patch('term_timer.config.BLUETOOTH_CUBES', self.CUBES):
            self.assertIsNone(CubeDevice.resolve('off'))

    def test_auto_scans_for_any_cube(self) -> None:
        """The auto selector scans without favouring a configured cube."""
        with patch('term_timer.config.BLUETOOTH_CUBES', self.CUBES):
            cube = CubeDevice.resolve('auto')

        self.assertIsNotNone(cube)
        cube = cast('CubeDevice', cube)
        self.assertEqual(cube.address, '')
        self.assertFalse(cube.prefer_known)
        self.assertEqual(cube.scan_addresses, ())

    def test_label_selects_a_configured_cube(self) -> None:
        """A label connects to the cube it names, with its own settings."""
        with patch('term_timer.config.BLUETOOTH_CUBES', self.CUBES):
            cube = CubeDevice.resolve('weilong')

        self.assertIsNotNone(cube)
        cube = cast('CubeDevice', cube)
        self.assertEqual(cube.address, '11:22:33:44:55:77')
        self.assertFalse(cube.use_gyroscope)

    def test_address_reaches_an_unconfigured_cube(self) -> None:
        """A raw address connects to a cube never configured."""
        with patch('term_timer.config.BLUETOOTH_CUBES', self.CUBES):
            cube = CubeDevice.resolve('99:88:77:66:55:44')

        self.assertIsNotNone(cube)
        cube = cast('CubeDevice', cube)
        self.assertEqual(cube.address, '99:88:77:66:55:44')

    def test_nothing_asked_takes_the_default_cube(self) -> None:
        """Asking for nothing connects to the designated cube."""
        with (
                patch('term_timer.config.BLUETOOTH_CUBES', self.CUBES),
                patch('term_timer.config.BLUETOOTH_DEFAULT', 'gan12'),
        ):
            cube = CubeDevice.resolve(None)

        self.assertIsNotNone(cube)
        cube = cast('CubeDevice', cube)
        self.assertEqual(cube.label, 'gan12')

    def test_nothing_asked_scans_the_configured_cubes(self) -> None:
        """Several cubes and no default scans, favouring those configured."""
        with (
                patch('term_timer.config.BLUETOOTH_CUBES', self.CUBES),
                patch('term_timer.config.BLUETOOTH_DEFAULT', ''),
        ):
            cube = CubeDevice.resolve(None)

            self.assertIsNotNone(cube)
            cube = cast('CubeDevice', cube)
            self.assertEqual(cube.address, '')
            self.assertTrue(cube.prefer_known)
            self.assertEqual(
                cube.scan_addresses,
                ('AA:BB:CC:DD:EE:FF', '11:22:33:44:55:77'),
            )

    def test_nothing_asked_without_any_cube_stays_off(self) -> None:
        """No cube configured and nothing asked leaves Bluetooth off."""
        with (
                patch('term_timer.config.BLUETOOTH_CUBES', {}),
                patch('term_timer.config.BLUETOOTH_DEFAULT', ''),
        ):
            self.assertIsNone(CubeDevice.resolve(None))

    def test_adopt_finds_the_cube_behind_an_address(self) -> None:
        """A scanned address is matched back to its configured cube."""
        with patch('term_timer.config.BLUETOOTH_CUBES', self.CUBES):
            cube = CubeDevice.adopt('aa:bb:cc:dd:ee:ff')

            self.assertIsNotNone(cube)
            self.assertEqual(cast('CubeDevice', cube).label, 'gan12')
            self.assertIsNone(CubeDevice.adopt('99:88:77:66:55:44'))


class TestCubeDeviceCleanSelector(unittest.TestCase):
    """Tests for the validation of a cube selector."""

    CUBES: ClassVar[dict[str, CubeDevice]] = {
        'gan12': CubeDevice(label='gan12'),
    }

    def test_keywords_and_labels_are_lowercased(self) -> None:
        """A reserved keyword or a known label is normalised."""
        with patch('term_timer.config.BLUETOOTH_CUBES', self.CUBES):
            self.assertEqual(CubeDevice.clean_selector(' AUTO '), 'auto')
            self.assertEqual(CubeDevice.clean_selector('Off'), 'off')
            self.assertEqual(CubeDevice.clean_selector('GAN12'), 'gan12')

    def test_address_is_kept_as_typed(self) -> None:
        """An address reaches a cube even unconfigured."""
        with patch('term_timer.config.BLUETOOTH_CUBES', self.CUBES):
            self.assertEqual(
                CubeDevice.clean_selector('AA:BB:CC:DD:EE:FF'),
                'AA:BB:CC:DD:EE:FF',
            )

    def test_unknown_selector_is_rejected(self) -> None:
        """A value naming no cube is refused, a stray positional included."""
        with patch('term_timer.config.BLUETOOTH_CUBES', self.CUBES):
            self.assertEqual(CubeDevice.clean_selector('10'), '')
            self.assertEqual(CubeDevice.clean_selector('weilong'), '')


class TestEnvFlag(unittest.TestCase):
    """Tests for env_flag."""

    VARIABLE = 'TERM_TIMER_TEST_FLAG'

    def assert_flag(self, value: str, *, expected: bool) -> None:
        """Assert the flag carried by a given environment value."""
        with patch.dict(os.environ, {self.VARIABLE: value}):
            self.assertEqual(env_flag(self.VARIABLE), expected)

    def test_unset_variable_uses_default(self) -> None:
        """An absent variable returns the default, False or True."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(self.VARIABLE, None)
            self.assertFalse(env_flag(self.VARIABLE))
            self.assertTrue(env_flag(self.VARIABLE, default=True))

    def test_empty_variable_uses_default(self) -> None:
        """An empty or blank variable is read as unset, not as enabled."""
        for value in ('', '   ', '\t'):
            with self.subTest(value=value), \
                    patch.dict(os.environ, {self.VARIABLE: value}):
                self.assertFalse(env_flag(self.VARIABLE))
                self.assertTrue(env_flag(self.VARIABLE, default=True))

    def test_truthy_spellings(self) -> None:
        """The documented truthy spellings enable the flag."""
        for value in ('1', 'true', 'yes', 'on'):
            with self.subTest(value=value):
                self.assert_flag(value, expected=True)

    def test_falsy_spellings(self) -> None:
        """The documented falsy spellings disable the flag."""
        for value in ('0', 'false', 'no', 'off'):
            with self.subTest(value=value):
                self.assert_flag(value, expected=False)

    def test_falsy_spellings_are_case_insensitive(self) -> None:
        """A falsy spelling really disables whatever its case."""
        for value in ('FALSE', 'No', 'OfF'):
            with self.subTest(value=value):
                self.assert_flag(value, expected=False)

    def test_surrounding_spaces_are_ignored(self) -> None:
        """Padding never turns a falsy spelling into a truthy value."""
        self.assert_flag(' 0 ', expected=False)
        self.assert_flag(' true ', expected=True)

    def test_any_other_value_enables(self) -> None:
        """Anything not spelled falsy counts as enabled."""
        for value in ('2', 'oui', 'disabled'):
            with self.subTest(value=value):
                self.assert_flag(value, expected=True)

    def test_default_only_applies_when_unset(self) -> None:
        """An explicit value always wins over the default."""
        with patch.dict(os.environ, {self.VARIABLE: '0'}):
            self.assertFalse(env_flag(self.VARIABLE, default=True))


class TestEnvString(unittest.TestCase):
    """Tests for env_string."""

    VARIABLE = 'TERM_TIMER_TEST_STRING'

    def test_unset_variable_falls_back(self) -> None:
        """An absent variable leaves the default untouched."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(self.VARIABLE, None)
            self.assertEqual(env_string(self.VARIABLE, 'audio'), 'audio')

    def test_empty_variable_falls_back(self) -> None:
        """An empty variable never blanks the setting."""
        with patch.dict(os.environ, {self.VARIABLE: ''}):
            self.assertEqual(env_string(self.VARIABLE, 'audio'), 'audio')

    def test_value_overrides_default(self) -> None:
        """A defined variable wins over the default."""
        with patch.dict(os.environ, {self.VARIABLE: 'off'}):
            self.assertEqual(env_string(self.VARIABLE, 'audio'), 'off')

    def test_value_is_kept_verbatim(self) -> None:
        """Spacing and case are preserved: they can be meaningful."""
        with patch.dict(os.environ, {self.VARIABLE: '  Go  '}):
            self.assertEqual(env_string(self.VARIABLE, 'Go Go Go:'), '  Go  ')

    def test_unknown_value_is_not_validated(self) -> None:
        """No value is rejected, the consumer decides what to do with it."""
        with patch.dict(os.environ, {self.VARIABLE: 'bruit'}):
            self.assertEqual(env_string(self.VARIABLE, 'audio'), 'bruit')
