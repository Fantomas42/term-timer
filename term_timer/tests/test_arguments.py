"""Tests for arguments."""
import unittest
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
from term_timer.arguments import graph_arguments
from term_timer.arguments import import_arguments
from term_timer.arguments import list_arguments
from term_timer.arguments import merge_arguments
from term_timer.arguments import serve_arguments
from term_timer.arguments import set_session_arguments
from term_timer.arguments import solve_arguments
from term_timer.arguments import statistics_arguments
from term_timer.arguments import train_arguments


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
        """Test solve default arguments without a configured device address."""
        with patch('term_timer.arguments.DEVICE_ADDRESS', ''):
            main_parser = ArgumentParser()
            subparsers = main_parser.add_subparsers(dest='command')
            solve_arguments(subparsers)

        args = main_parser.parse_args(['solve'])
        self.assertEqual(args.command, 'solve')
        self.assertEqual(args.solves, 0)
        self.assertEqual(args.cube, 3)
        self.assertFalse(args.bluetooth)
        self.assertFalse(args.free_play)

    def test_solve_default_bluetooth_when_address_configured(self) -> None:
        """Test bluetooth defaults to True when a device address is set."""
        with patch('term_timer.arguments.DEVICE_ADDRESS', 'AA:BB:CC:DD:EE:FF'):
            main_parser = ArgumentParser()
            subparsers = main_parser.add_subparsers(dest='command')
            solve_arguments(subparsers)

        args = main_parser.parse_args(['solve'])
        self.assertTrue(args.bluetooth)

    def test_solve_with_arguments(self) -> None:
        """Test solve enables bluetooth when no address configured."""
        with patch('term_timer.arguments.DEVICE_ADDRESS', ''):
            main_parser = ArgumentParser()
            subparsers = main_parser.add_subparsers(dest='command')
            solve_arguments(subparsers)

        args = main_parser.parse_args(['solve', '10', '-c', '4', '-b', '-f'])
        self.assertEqual(args.solves, 10)
        self.assertEqual(args.cube, 4)
        self.assertTrue(args.bluetooth)
        self.assertTrue(args.free_play)

    def test_solve_disable_bluetooth_when_address_configured(self) -> None:
        """Test -b disables bluetooth when a device address is configured."""
        with patch('term_timer.arguments.DEVICE_ADDRESS', 'AA:BB:CC:DD:EE:FF'):
            main_parser = ArgumentParser()
            subparsers = main_parser.add_subparsers(dest='command')
            solve_arguments(subparsers)

        args = main_parser.parse_args(['solve', '-b'])
        self.assertFalse(args.bluetooth)


class TestTrainArguments(unittest.TestCase):
    """Tests for train command argument parsing."""

    def test_train_parser_creation(self) -> None:
        """Test train parser creation."""
        main_parser = ArgumentParser()
        subparsers = main_parser.add_subparsers()
        parser = train_arguments(subparsers)

        self.assertIsInstance(parser, ArgumentParser)

    def test_train_default_arguments(self) -> None:
        """Test train default arguments without a configured device address."""
        with patch('term_timer.arguments.DEVICE_ADDRESS', ''):
            main_parser = ArgumentParser()
            subparsers = main_parser.add_subparsers(dest='command')
            train_arguments(subparsers)

        args = main_parser.parse_args(['train'])
        self.assertEqual(args.command, 'train')
        self.assertEqual(args.case_codes, [])
        self.assertFalse(args.bluetooth)

    def test_train_enable_bluetooth_without_address(self) -> None:
        """Test -b enables bluetooth on train when no address is configured."""
        with patch('term_timer.arguments.DEVICE_ADDRESS', ''):
            main_parser = ArgumentParser()
            subparsers = main_parser.add_subparsers(dest='command')
            train_arguments(subparsers)

        args = main_parser.parse_args(['train', '-b'])
        self.assertTrue(args.bluetooth)

    def test_train_default_bluetooth_when_address_configured(self) -> None:
        """Test bluetooth defaults to True on train when address is set."""
        with patch('term_timer.arguments.DEVICE_ADDRESS', 'AA:BB:CC:DD:EE:FF'):
            main_parser = ArgumentParser()
            subparsers = main_parser.add_subparsers(dest='command')
            train_arguments(subparsers)

        args = main_parser.parse_args(['train'])
        self.assertTrue(args.bluetooth)

    def test_train_disable_bluetooth_when_address_configured(self) -> None:
        """Test -b disables bluetooth on train when address is configured."""
        with patch('term_timer.arguments.DEVICE_ADDRESS', 'AA:BB:CC:DD:EE:FF'):
            main_parser = ArgumentParser()
            subparsers = main_parser.add_subparsers(dest='command')
            train_arguments(subparsers)

        args = main_parser.parse_args(['train', '-b'])
        self.assertFalse(args.bluetooth)


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
