import argparse
import unittest
from unittest.mock import patch

from term_timer.arguments import COMMAND_ALIASES
from term_timer.arguments import COMMAND_RESOLUTIONS
from term_timer.arguments import cfop_arguments
from term_timer.arguments import delete_arguments
from term_timer.arguments import detail_arguments
from term_timer.arguments import edit_arguments
from term_timer.arguments import get_arguments
from term_timer.arguments import graph_arguments
from term_timer.arguments import import_arguments
from term_timer.arguments import list_arguments
from term_timer.arguments import serve_arguments
from term_timer.arguments import set_session_arguments
from term_timer.arguments import solve_arguments
from term_timer.arguments import statistics_arguments
from term_timer.arguments import train_arguments


class TestCommandAliases(unittest.TestCase):

    def test_command_aliases_structure(self):
        expected_commands = {
            'solve', 'list', 'stats', 'graph', 'cfop', 'detail',
            'import', 'serve', 'train', 'edit', 'delete',
        }
        self.assertEqual(set(COMMAND_ALIASES.keys()), expected_commands)

    def test_command_resolutions(self):
        for command, aliases in COMMAND_ALIASES.items():
            for alias in aliases:
                self.assertEqual(COMMAND_RESOLUTIONS[alias], command)

    def test_solve_aliases(self):
        self.assertEqual(COMMAND_ALIASES['solve'], ['sw', 't'])
        self.assertEqual(COMMAND_RESOLUTIONS['sw'], 'solve')
        self.assertEqual(COMMAND_RESOLUTIONS['t'], 'solve')


class TestSessionArguments(unittest.TestCase):

    def test_set_session_arguments(self):
        parser = argparse.ArgumentParser()
        session = set_session_arguments(parser)

        self.assertIsInstance(session, argparse._ArgumentGroup)  # noqa: SLF001

        # Test default values by parsing empty args
        args = parser.parse_args([])
        self.assertEqual(args.cube, 3)
        self.assertEqual(args.include_sessions, [])
        self.assertEqual(args.exclude_sessions, [])
        self.assertEqual(args.devices, [])


class TestSolveArguments(unittest.TestCase):

    def test_solve_parser_creation(self):
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers()
        parser = solve_arguments(subparsers)

        self.assertIsInstance(parser, argparse.ArgumentParser)
        self.assertEqual(parser.prog.split()[-1], 'solve')

    def test_solve_default_arguments(self):
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        solve_arguments(subparsers)

        args = main_parser.parse_args(['solve'])
        self.assertEqual(args.command, 'solve')
        self.assertEqual(args.solves, 0)
        self.assertEqual(args.cube, 3)
        self.assertFalse(args.bluetooth)
        self.assertFalse(args.free_play)

    def test_solve_with_arguments(self):
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        solve_arguments(subparsers)

        args = main_parser.parse_args(['solve', '10', '-c', '4', '-b', '-f'])
        self.assertEqual(args.solves, 10)
        self.assertEqual(args.cube, 4)
        self.assertTrue(args.bluetooth)
        self.assertTrue(args.free_play)


class TestTrainArguments(unittest.TestCase):

    def test_train_parser_creation(self):
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers()
        parser = train_arguments(subparsers)

        self.assertIsInstance(parser, argparse.ArgumentParser)

    def test_train_default_arguments(self):
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        train_arguments(subparsers)

        args = main_parser.parse_args(['train'])
        self.assertEqual(args.command, 'train')
        self.assertEqual(args.case, [])
        self.assertFalse(args.bluetooth)


class TestListArguments(unittest.TestCase):

    def test_list_default_arguments(self):
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        list_arguments(subparsers)

        args = main_parser.parse_args(['list'])
        self.assertEqual(args.command, 'list')
        self.assertEqual(args.count, 0)
        self.assertEqual(args.sort, 'date')

    def test_list_with_count(self):
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        list_arguments(subparsers)

        args = main_parser.parse_args(['list', '25'])
        self.assertEqual(args.count, 25)


class TestStatisticsArguments(unittest.TestCase):

    def test_stats_parser_creation(self):
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        parser = statistics_arguments(subparsers)

        self.assertIsInstance(parser, argparse.ArgumentParser)

        args = main_parser.parse_args(['stats'])
        self.assertEqual(args.command, 'stats')


class TestGraphArguments(unittest.TestCase):

    def test_graph_parser_creation(self):
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        parser = graph_arguments(subparsers)

        self.assertIsInstance(parser, argparse.ArgumentParser)

        args = main_parser.parse_args(['graph'])
        self.assertEqual(args.command, 'graph')


class TestCfopArguments(unittest.TestCase):

    def test_cfop_default_arguments(self):
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        cfop_arguments(subparsers)

        args = main_parser.parse_args(['cfop'])
        self.assertEqual(args.command, 'cfop')
        self.assertFalse(args.oll)
        self.assertFalse(args.pll)
        self.assertEqual(args.sort, 'count')
        self.assertEqual(args.order, 'asc')

    def test_cfop_with_flags(self):
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        cfop_arguments(subparsers)

        args = main_parser.parse_args(['cfop', '--oll', '-o', 'desc'])
        self.assertTrue(args.oll)
        self.assertEqual(args.order, 'desc')


class TestImportArguments(unittest.TestCase):

    def test_import_with_source(self):
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        import_arguments(subparsers)

        args = main_parser.parse_args(['import', 'file.csv'])
        self.assertEqual(args.command, 'import')
        self.assertEqual(args.source, 'file.csv')


class TestServeArguments(unittest.TestCase):

    def test_serve_default_arguments(self):
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        serve_arguments(subparsers)

        args = main_parser.parse_args(['serve'])
        self.assertEqual(args.command, 'serve')

    def test_serve_with_host_port(self):
        main_parser = argparse.ArgumentParser()
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

    def test_detail_with_solve_ids(self):
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        detail_arguments(subparsers)

        args = main_parser.parse_args(['detail', '1', '2', '3'])
        self.assertEqual(args.command, 'detail')
        self.assertEqual(args.solves, [1, 2, 3])

    def test_detail_with_method(self):
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        detail_arguments(subparsers)

        args = main_parser.parse_args(['detail', '1', '-m', 'cfop'])
        self.assertEqual(args.method, 'cfop')


class TestEditArguments(unittest.TestCase):

    def test_edit_with_solve_and_flag(self):
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        edit_arguments(subparsers)

        args = main_parser.parse_args(['edit', '1', '2', 'DNF'])
        self.assertEqual(args.command, 'edit')
        self.assertEqual(args.solves, [1, 2])
        self.assertEqual(args.flag, 'DNF')


class TestDeleteArguments(unittest.TestCase):

    def test_delete_with_solve_id(self):
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest='command')
        delete_arguments(subparsers)

        args = main_parser.parse_args(['delete', '5'])
        self.assertEqual(args.command, 'delete')
        self.assertEqual(args.solve, 5)


class TestGetArguments(unittest.TestCase):

    @patch('sys.argv', ['term_timer', 'solve'])
    def test_get_arguments_solve(self):
        args = get_arguments()
        self.assertEqual(args.command, 'solve')

    @patch('sys.argv', ['term_timer', 'list', '10'])
    def test_get_arguments_list_with_count(self):
        args = get_arguments()
        self.assertEqual(args.command, 'list')
        self.assertEqual(args.count, 10)

    @patch('sys.argv', ['term_timer'])
    @patch('sys.exit')
    def test_get_arguments_no_command_exits(self, mock_exit):
        get_arguments()
        mock_exit.assert_called_once_with(1)

    @patch('sys.argv', ['term_timer', 'sw'])  # alias for solve
    def test_get_arguments_with_alias(self):
        args = get_arguments()
        self.assertEqual(args.command, 'sw')
