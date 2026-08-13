"""Tests for arguments."""
import unittest
from argparse import Namespace
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import Mock
from unittest.mock import patch

from term_timer.argparser import ArgumentParser
from term_timer.arguments import COMMAND_ALIASES
from term_timer.arguments import COMMAND_RESOLUTIONS
from term_timer.arguments import cfop_arguments
from term_timer.arguments import delete_arguments
from term_timer.arguments import detail_arguments
from term_timer.arguments import doctor_arguments
from term_timer.arguments import edit_arguments
from term_timer.arguments import get_arguments
from term_timer.arguments import get_parser
from term_timer.arguments import graph_arguments
from term_timer.arguments import import_arguments
from term_timer.arguments import list_arguments
from term_timer.arguments import merge_arguments
from term_timer.arguments import serve_arguments
from term_timer.arguments import set_session_arguments
from term_timer.arguments import solve_arguments
from term_timer.arguments import statistics_arguments
from term_timer.arguments import train_arguments
from term_timer.config import CubeDevice


@contextmanager
def configured_cubes(
        cubes: dict[str, CubeDevice],
) -> Iterator[None]:
    """
    Pretend the given cubes are the configured ones.

    The registry is read twice: once by the parser being built, once by
    the validation of a selector, which reaches the configuration
    module itself.

    Yields:
        Nothing, once both readings are patched.

    """
    with (
            patch('term_timer.arguments.BLUETOOTH_CUBES', cubes),
            patch('term_timer.config.BLUETOOTH_CUBES', cubes),
    ):
        yield


CUBES = {
    'gan12': CubeDevice(
        label='gan12',
        name='GAN 12 ui FreePlay',
        address='AA:BB:CC:DD:EE:FF',
    ),
    'weilong': CubeDevice(
        label='weilong',
        name='MoYu WeiLong v10 AI',
        address='11:22:33:44:55:77',
    ),
}


class TestCommandAliases(unittest.TestCase):
    """Tests for command aliases and resolutions."""

    def test_command_aliases_structure(self) -> None:
        """Test that COMMAND_ALIASES contains all expected commands."""
        expected_commands = {
            'ghost', 'daily', 'solve', 'list', 'stats', 'graph', 'cfop',
            'detail', 'doctor', 'import', 'serve', 'train', 'edit', 'delete',
            'index', 'scramble', 'browse', 'merge', 'config', 'routine',
            'drill', 'reset',
        }
        self.assertEqual(set(COMMAND_ALIASES.keys()), expected_commands)

    def test_command_resolutions(self) -> None:
        """Test that all aliases correctly resolve to their commands."""
        for command, aliases in COMMAND_ALIASES.items():
            for alias in aliases:
                self.assertEqual(COMMAND_RESOLUTIONS[alias], command)

    def test_solve_aliases(self) -> None:
        """Test that solve command has correct aliases configured."""
        self.assertEqual(COMMAND_ALIASES['solve'], ['sw', 't'])
        self.assertEqual(COMMAND_RESOLUTIONS['sw'], 'solve')
        self.assertEqual(COMMAND_RESOLUTIONS['t'], 'solve')

    def test_ghost_aliases(self) -> None:
        """Test that ghost command has correct aliases configured."""
        self.assertEqual(COMMAND_ALIASES['ghost'], ['gh', 'p'])
        self.assertEqual(COMMAND_RESOLUTIONS['gh'], 'ghost')
        self.assertEqual(COMMAND_RESOLUTIONS['p'], 'ghost')


class TestReviewDetailArguments(unittest.TestCase):
    """Tests for the --detail flag of the daily and ghost commands."""

    def test_daily_detail_defaults_to_nothing(self) -> None:
        """A daily command asks for no detail by default."""
        options = get_parser().parse_args(['daily'])

        self.assertEqual(options.detail, [])

    def test_ghost_detail_defaults_to_nothing(self) -> None:
        """A ghost command asks for no detail by default."""
        options = get_parser().parse_args(['ghost'])

        self.assertEqual(options.detail, [])

    def test_daily_detail_takes_several_ids(self) -> None:
        """The daily detail flag collects every id given."""
        options = get_parser().parse_args(['daily', '-n', '1', '3'])

        self.assertEqual(options.detail, [1, 3])

    def test_ghost_detail_keeps_the_reference(self) -> None:
        """The ghost detail flag leaves the reference untouched."""
        options = get_parser().parse_args(['ghost', '70a2', '-n', '2'])

        self.assertEqual(options.reference, '70a2')
        self.assertEqual(options.detail, [2])

    def test_ghost_review_still_takes_the_reference(self) -> None:
        """--review remains a flag, the id it follows is the reference."""
        options = get_parser().parse_args(['ghost', '-r', '5'])

        self.assertTrue(options.review)
        self.assertEqual(options.reference, '5')
        self.assertEqual(options.detail, [])

    def test_detail_requires_an_id(self) -> None:
        """A detail flag given alone is refused, never silently ignored."""
        with self.assertRaises(SystemExit):
            get_parser().parse_args(['daily', '-n'])


class TestRaceCountArguments(unittest.TestCase):
    """Tests for the attempt count of the daily and ghost commands."""

    def test_daily_attempts_default_to_infinite(self) -> None:
        """A daily command runs until the solver quits by default."""
        options = get_parser().parse_args(['daily'])

        self.assertEqual(options.attempts, 0)

    def test_daily_attempts_bound_the_session(self) -> None:
        """The leading positional of daily is its attempt count."""
        options = get_parser().parse_args(['daily', '3'])

        self.assertEqual(options.attempts, 3)

    def test_ghost_attempts_default_to_infinite(self) -> None:
        """A ghost command races until the solver quits by default."""
        options = get_parser().parse_args(['ghost', 'a1b2c3d4'])

        self.assertEqual(options.reference, 'a1b2c3d4')
        self.assertEqual(options.attempts, 0)

    def test_ghost_takes_the_reference_then_the_count(self) -> None:
        """The two positionals of ghost fill from left to right."""
        options = get_parser().parse_args(['ghost', 'a1b2c3d4', '5'])

        self.assertEqual(options.reference, 'a1b2c3d4')
        self.assertEqual(options.attempts, 5)

    def test_ghost_numeric_reference_stays_a_reference(self) -> None:
        """A lone number is the reference, position deciding, not content."""
        options = get_parser().parse_args(['ghost', '42'])

        self.assertEqual(options.reference, '42')
        self.assertEqual(options.attempts, 0)

    def test_attempts_must_be_a_number(self) -> None:
        """A count that is not a number is refused."""
        with self.assertRaises(SystemExit):
            get_parser().parse_args(['daily', 'soon'])


class TestSessionArguments(unittest.TestCase):
    """Tests for session argument parsing."""

    def test_set_session_arguments(self) -> None:
        """Test that session arguments are added with correct defaults."""
        parser = ArgumentParser()
        session = set_session_arguments(parser)

        self.assertIsInstance(session, ArgumentParser._ArgumentGroup)  # noqa: SLF001

        # Test default values by parsing empty args
        args = parser.parse_args([])
        self.assertEqual(args.cube, 3)
        self.assertEqual(args.include_sessions, [])
        self.assertEqual(args.exclude_sessions, [])
        self.assertEqual(args.devices, [])


class TestSolveArguments(unittest.TestCase):
    """Tests for solve command argument parsing."""

    def test_solve_parser_creation(self) -> None:
        """Test solve parser creation."""
        main_parser = ArgumentParser()
        subparsers = main_parser.add_subparsers()
        parser = solve_arguments(subparsers)

        self.assertIsInstance(parser, ArgumentParser)
        self.assertEqual(parser.prog.split()[-1], 'solve')

    def test_solve_default_arguments(self) -> None:
        """Test solve default arguments without any configured cube."""
        with configured_cubes({}):
            main_parser = ArgumentParser()
            subparsers = main_parser.add_subparsers(dest='command')
            solve_arguments(subparsers)

            args = main_parser.parse_args(['solve'])

        self.assertEqual(args.command, 'solve')
        self.assertEqual(args.solves, 0)
        self.assertEqual(args.cube, 3)
        self.assertIsNone(args.bluetooth)
        self.assertFalse(args.free_play)

    def test_solve_bare_bluetooth_scans_without_configured_cube(self) -> None:
        """Test a bare -b asks for a scan when no cube is configured."""
        with configured_cubes({}):
            main_parser = ArgumentParser()
            subparsers = main_parser.add_subparsers(dest='command')
            solve_arguments(subparsers)

            args = main_parser.parse_args(['solve', '-b'])

        self.assertEqual(args.bluetooth, 'auto')

    def test_solve_with_arguments(self) -> None:
        """Test solve reads its options around a bare -b."""
        with configured_cubes({}):
            main_parser = ArgumentParser()
            subparsers = main_parser.add_subparsers(dest='command')
            solve_arguments(subparsers)

            args = main_parser.parse_args(
                ['solve', '10', '-c', '4', '-b', '-f'],
            )

        self.assertEqual(args.solves, 10)
        self.assertEqual(args.cube, 4)
        self.assertEqual(args.bluetooth, 'auto')
        self.assertTrue(args.free_play)

    def test_solve_bare_bluetooth_disables_configured_cube(self) -> None:
        """Test a bare -b disables the cube when one is configured."""
        with configured_cubes(CUBES):
            main_parser = ArgumentParser()
            subparsers = main_parser.add_subparsers(dest='command')
            solve_arguments(subparsers)

            args = main_parser.parse_args(['solve', '-b'])

        self.assertEqual(args.bluetooth, 'off')

    def test_solve_selects_a_configured_cube(self) -> None:
        """Test -b selects a cube by label, whatever its case."""
        with configured_cubes(CUBES):
            main_parser = ArgumentParser()
            subparsers = main_parser.add_subparsers(dest='command')
            solve_arguments(subparsers)

            args = main_parser.parse_args(['solve', '-b', 'WeiLong'])

        self.assertEqual(args.bluetooth, 'weilong')

    def test_solve_selects_an_unconfigured_address(self) -> None:
        """Test -b takes a raw address, for a cube never configured."""
        with configured_cubes(CUBES):
            main_parser = ArgumentParser()
            subparsers = main_parser.add_subparsers(dest='command')
            solve_arguments(subparsers)

            args = main_parser.parse_args(['solve', '-b', '11:22:33:44:55:66'])

        self.assertEqual(args.bluetooth, '11:22:33:44:55:66')

    def test_solve_rejects_an_unknown_cube(self) -> None:
        """Test -b refuses a value naming no cube, positional included."""
        with configured_cubes(CUBES):
            main_parser = ArgumentParser()
            subparsers = main_parser.add_subparsers(dest='command')
            solve_arguments(subparsers)

            with self.assertRaises(SystemExit):
                main_parser.parse_args(['solve', '-b', '10'])


class TestTrainArguments(unittest.TestCase):
    """Tests for train command argument parsing."""

    def test_train_parser_creation(self) -> None:
        """Test train parser creation."""
        main_parser = ArgumentParser()
        subparsers = main_parser.add_subparsers()
        parser = train_arguments(subparsers)

        self.assertIsInstance(parser, ArgumentParser)

    def test_train_default_arguments(self) -> None:
        """Test train default arguments without any configured cube."""
        with configured_cubes({}):
            main_parser = ArgumentParser()
            subparsers = main_parser.add_subparsers(dest='command')
            train_arguments(subparsers)

            args = main_parser.parse_args(['train'])

        self.assertEqual(args.command, 'train')
        self.assertEqual(args.case_codes, [])
        self.assertEqual(args.filters, [])
        self.assertEqual(args.states, [])
        self.assertEqual(args.oldest, 0)
        self.assertEqual(args.slowest, 0)
        self.assertEqual(args.random, 0)
        self.assertEqual(args.new_cases, 5)
        self.assertFalse(args.show_breakdown)
        self.assertIsNone(args.bluetooth)

    @staticmethod
    def train_args(argv: list[str]) -> Namespace:
        """
        Parse train arguments without any configured cube.

        Returns:
            Namespace of the parsed arguments.

        """
        with configured_cubes({}):
            main_parser = ArgumentParser()
            subparsers = main_parser.add_subparsers(dest='command')
            train_arguments(subparsers)

            return main_parser.parse_args(argv)

    def test_train_selection_counts(self) -> None:
        """Test --oldest, --slowest and --random values and constants."""
        self.assertEqual(self.train_args(['train', '-d']).oldest, 5)
        self.assertEqual(self.train_args(['train', '-d', '3']).oldest, 3)
        self.assertEqual(self.train_args(['train', '-t']).slowest, 5)
        self.assertEqual(self.train_args(['train', '-t', '3']).slowest, 3)
        self.assertEqual(self.train_args(['train', '-n']).random, -1)
        self.assertEqual(self.train_args(['train', '-n', '3']).random, 3)
        self.assertEqual(self.train_args(['train', '-m', '2']).new_cases, 2)

    def test_train_explain_flag(self) -> None:
        """Test --explain arms the FSRS rating breakdown display."""
        self.assertTrue(self.train_args(['train', '-x']).show_breakdown)
        self.assertTrue(self.train_args(['train', '--explain']).show_breakdown)

    def test_train_selection_modes_are_exclusive(self) -> None:
        """Test --cases, --oldest, --slowest and --random exclude each other."""
        for argv in (
                ['train', '-c', 'Aa', '-d', '3'],
                ['train', '-d', '3', '-t', '3'],
                ['train', '-t', '3', '-n'],
        ):
            with self.subTest(argv=argv), self.assertRaises(SystemExit):
                self.train_args(argv)

    def test_train_single_state(self) -> None:
        """Test --state accepts a single card state."""
        args = self.train_args(['train', '-e', 'review'])

        self.assertEqual(args.states, ['review'])

    def test_train_multiple_states(self) -> None:
        """Test --state accepts several card states."""
        args = self.train_args(['train', '--state', 'learning', 'relearning'])

        self.assertEqual(args.states, ['learning', 'relearning'])

    def test_train_rejects_an_unknown_state(self) -> None:
        """Test --state refuses a value naming no card state."""
        with self.assertRaises(SystemExit):
            self.train_args(['train', '-e', 'mastered'])

    def test_train_state_combines_with_cases_and_filters(self) -> None:
        """Test --state is compatible with --cases and --filter."""
        args = self.train_args(
            ['train', '-c', 'Aa', '-e', 'review'],
        )
        self.assertEqual(args.case_codes, ['Aa'])
        self.assertEqual(args.states, ['review'])

        args = self.train_args(
            ['train', '-i', 'Dot', '-e', 'stable'],
        )
        self.assertEqual(args.filters, ['Dot'])
        self.assertEqual(args.states, ['stable'])

    def test_train_bare_bluetooth_scans_without_configured_cube(self) -> None:
        """Test a bare -b asks for a scan on train with no cube configured."""
        with configured_cubes({}):
            main_parser = ArgumentParser()
            subparsers = main_parser.add_subparsers(dest='command')
            train_arguments(subparsers)

            args = main_parser.parse_args(['train', '-b'])

        self.assertEqual(args.bluetooth, 'auto')

    def test_train_bare_bluetooth_disables_configured_cube(self) -> None:
        """Test a bare -b disables the cube on train when one is configured."""
        with configured_cubes(CUBES):
            main_parser = ArgumentParser()
            subparsers = main_parser.add_subparsers(dest='command')
            train_arguments(subparsers)

            args = main_parser.parse_args(['train', '-b'])

        self.assertEqual(args.bluetooth, 'off')

    def test_train_selects_a_configured_cube(self) -> None:
        """Test -b selects a cube by label on train."""
        with configured_cubes(CUBES):
            main_parser = ArgumentParser()
            subparsers = main_parser.add_subparsers(dest='command')
            train_arguments(subparsers)

            args = main_parser.parse_args(['train', '-b', 'gan12'])

        self.assertEqual(args.bluetooth, 'gan12')


class TestListArguments(unittest.TestCase):
    """Tests for list command argument parsing."""

    def test_list_default_arguments(self) -> None:
        """Test list default arguments."""
        main_parser = ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        list_arguments(subparsers)

        args = main_parser.parse_args(['list'])
        self.assertEqual(args.command, 'list')
        self.assertEqual(args.count, 0)
        self.assertEqual(args.sort, 'date')

    def test_list_with_count(self) -> None:
        """Test list with count."""
        main_parser = ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        list_arguments(subparsers)

        args = main_parser.parse_args(['list', '25'])
        self.assertEqual(args.count, 25)


class TestStatisticsArguments(unittest.TestCase):
    """Tests for statistics command argument parsing."""

    def test_stats_parser_creation(self) -> None:
        """Test stats parser creation."""
        main_parser = ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        parser = statistics_arguments(subparsers)

        self.assertIsInstance(parser, ArgumentParser)

        args = main_parser.parse_args(['stats'])
        self.assertEqual(args.command, 'stats')


class TestGraphArguments(unittest.TestCase):
    """Tests for graph command argument parsing."""

    def test_graph_parser_creation(self) -> None:
        """Test graph parser creation."""
        main_parser = ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        parser = graph_arguments(subparsers)

        self.assertIsInstance(parser, ArgumentParser)

        args = main_parser.parse_args(['graph'])
        self.assertEqual(args.command, 'graph')


class TestCfopArguments(unittest.TestCase):
    """Tests for CFOP command argument parsing."""

    def test_cfop_default_arguments(self) -> None:
        """Test cfop default arguments."""
        main_parser = ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        cfop_arguments(subparsers)

        args = main_parser.parse_args(['cfop'])
        self.assertEqual(args.command, 'cfop')
        self.assertFalse(args.oll)
        self.assertFalse(args.pll)
        self.assertEqual(args.sort, 'count')
        self.assertEqual(args.order, 'asc')

    def test_cfop_with_flags(self) -> None:
        """Test cfop with flags."""
        main_parser = ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        cfop_arguments(subparsers)

        args = main_parser.parse_args(['cfop', '--oll', '-o', 'desc'])
        self.assertTrue(args.oll)
        self.assertEqual(args.order, 'desc')


class TestDoctorArguments(unittest.TestCase):
    """Tests for doctor command argument parsing."""

    def test_doctor_default_arguments(self) -> None:
        """Test doctor default arguments."""
        main_parser = ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        doctor_arguments(subparsers)

        args = main_parser.parse_args(['doctor'])
        self.assertEqual(args.command, 'doctor')
        self.assertEqual(args.count, 50)
        self.assertFalse(args.trend)
        self.assertEqual(args.cube, 3)

    def test_doctor_with_flags(self) -> None:
        """Test doctor with count, method and trend flags."""
        main_parser = ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        doctor_arguments(subparsers)

        args = main_parser.parse_args(
            ['doctor', '-n', '20', '-m', 'cfop', '-t'],
        )
        self.assertEqual(args.count, 20)
        self.assertEqual(args.method, 'cfop')
        self.assertTrue(args.trend)


class TestImportArguments(unittest.TestCase):
    """Tests for import command argument parsing."""

    def test_import_with_source(self) -> None:
        """Test import with source."""
        main_parser = ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        import_arguments(subparsers)

        args = main_parser.parse_args(['import', 'file.csv'])
        self.assertEqual(args.command, 'import')
        self.assertEqual(args.source, 'file.csv')


class TestServeArguments(unittest.TestCase):
    """Tests for serve command argument parsing."""

    def test_serve_default_arguments(self) -> None:
        """Test serve default arguments."""
        main_parser = ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        serve_arguments(subparsers)

        args = main_parser.parse_args(['serve'])
        self.assertEqual(args.command, 'serve')

    def test_serve_with_host_port(self) -> None:
        """Test serve with host port."""
        main_parser = ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        serve_arguments(subparsers)

        args = main_parser.parse_args(
            [
                'serve',
                '--host', '0.0.0.0',  # noqa: S104
                '--port', '9000'],
        )
        self.assertEqual(args.host, '0.0.0.0')  # noqa: S104
        self.assertEqual(args.port, 9000)


class TestDetailArguments(unittest.TestCase):
    """Tests for detail command argument parsing."""

    def test_detail_with_solve_ids(self) -> None:
        """Test detail with solve ids."""
        main_parser = ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        detail_arguments(subparsers)

        args = main_parser.parse_args(['detail', '1', '2', '3'])
        self.assertEqual(args.command, 'detail')
        self.assertEqual(args.solves, [1, 2, 3])

    def test_detail_with_method(self) -> None:
        """Test detail with method."""
        main_parser = ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        detail_arguments(subparsers)

        args = main_parser.parse_args(['detail', '1', '-m', 'cfop'])
        self.assertEqual(args.method, 'cfop')


class TestEditArguments(unittest.TestCase):
    """Tests for edit command argument parsing."""

    def test_edit_with_solve_and_flag(self) -> None:
        """Test edit with solve and flag."""
        main_parser = ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        edit_arguments(subparsers)

        args = main_parser.parse_args(['edit', '1', '2', '-f', 'DNF'])
        self.assertEqual(args.command, 'edit')
        self.assertEqual(args.solves, [1, 2])
        self.assertEqual(args.flag, 'DNF')

    def test_edit_with_solve_and_comment(self) -> None:
        """Test edit with solve and comment."""
        main_parser = ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        edit_arguments(subparsers)

        args = main_parser.parse_args(['edit', '1', '2', '-m', 'Comment'])
        self.assertEqual(args.command, 'edit')
        self.assertEqual(args.solves, [1, 2])
        self.assertEqual(args.comment, 'Comment')

    def test_edit_with_solve_flag_and_comment(self) -> None:
        """Test edit with solve, flag and comment."""
        main_parser = ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        edit_arguments(subparsers)

        args = main_parser.parse_args(
            ['edit', '1', '2', '-f', 'DNF', '-m', 'Comment'],
        )
        self.assertEqual(args.command, 'edit')
        self.assertEqual(args.solves, [1, 2])
        self.assertEqual(args.flag, 'DNF')
        self.assertEqual(args.comment, 'Comment')


class TestDeleteArguments(unittest.TestCase):
    """Tests for delete command argument parsing."""

    def test_delete_with_solve_id(self) -> None:
        """Test delete with solve id."""
        main_parser = ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        delete_arguments(subparsers)

        args = main_parser.parse_args(['delete', '5'])
        self.assertEqual(args.command, 'delete')
        self.assertEqual(args.solve, 5)


class TestMergeArguments(unittest.TestCase):
    """Tests for merge command argument parsing."""

    def test_merge_parser_creation(self) -> None:
        """Test merge parser creation."""
        main_parser = ArgumentParser()
        subparsers = main_parser.add_subparsers()
        parser = merge_arguments(subparsers)
        self.assertIsInstance(parser, ArgumentParser)

    def test_merge_with_sessions(self) -> None:
        """Test merge with session names."""
        main_parser = ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        merge_arguments(subparsers)

        args = main_parser.parse_args(['merge', 'session1', 'session2'])
        self.assertEqual(args.command, 'merge')
        self.assertEqual(args.sessions, ['session1', 'session2'])

    def test_merge_with_multiple_sessions(self) -> None:
        """Test merge with multiple session names."""
        main_parser = ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        merge_arguments(subparsers)

        args = main_parser.parse_args([
            'merge',
            'default',
            'session1',
            'session2',
            'session3',
        ])
        self.assertEqual(
            args.sessions,
            ['default', 'session1', 'session2', 'session3'],
        )

    def test_merge_alias_mg(self) -> None:
        """Test merge with 'mg' alias."""
        main_parser = ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        merge_arguments(subparsers)

        args = main_parser.parse_args(['mg', 'session1', 'session2'])
        self.assertEqual(args.command, 'mg')
        self.assertEqual(args.sessions, ['session1', 'session2'])


class TestGetArguments(unittest.TestCase):
    """Tests for get_arguments function."""

    @patch('sys.argv', ['term_timer', 'solve'])
    def test_get_arguments_solve(self) -> None:
        """Test get arguments solve."""
        args = get_arguments()
        self.assertEqual(args.command, 'solve')

    @patch('sys.argv', ['term_timer', 'list', '10'])
    def test_get_arguments_list_with_count(self) -> None:
        """Test get arguments list with count."""
        args = get_arguments()
        self.assertEqual(args.command, 'list')
        self.assertEqual(args.count, 10)

    @staticmethod
    @patch('sys.argv', ['term_timer'])
    @patch('sys.exit')
    def test_get_arguments_no_command_exits(mock_exit: Mock) -> None:
        """Test get arguments no command exits."""
        get_arguments()
        mock_exit.assert_called_once_with(1)

    @patch('sys.argv', ['term_timer', 'sw'])  # alias for solve
    def test_get_arguments_with_alias(self) -> None:
        """Test get arguments with alias."""
        args = get_arguments()
        self.assertEqual(args.command, 'sw')
