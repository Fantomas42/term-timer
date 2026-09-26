"""Tests for in out."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from term_timer.fsrs.storage import CaseTraining
from term_timer.fsrs.storage import Trainings
from term_timer.in_out import list_training_steps
from term_timer.in_out import load_all_solves
from term_timer.in_out import load_solves
from term_timer.in_out import load_trainings
from term_timer.in_out import read_trainings
from term_timer.in_out import save_trainings


class TestInOut(unittest.TestCase):
    """Tests for solve loading and saving functionality."""

    def test_load_solves_non_existing_file(self) -> None:
        """Test loading solves from a non-existing file returns empty list."""
        with tempfile.TemporaryDirectory() as tmp:
            solves = load_solves(3, 'default', directory=Path(tmp))

        self.assertEqual(solves, [])


class TestLoadAllSolves(unittest.TestCase):
    """Tests for multi-session loading with device and dedup filters."""

    def setUp(self) -> None:
        """Create a temporary solves directory for fixture files."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)

    def write_session(
            self,
            session: str,
            solves: list[dict[str, object]],
    ) -> None:
        """Write a session JSON fixture into the temporary directory."""
        suffix = f'-{ session }' if session != 'default' else ''
        path = self.directory / f'3x3x3{ suffix }.json'
        path.write_text(json.dumps(solves), encoding='utf-8')

    def test_single_session_devices_filter(self) -> None:
        """A single included session is still filtered by devices."""
        self.write_session('cstimer', [
            {'date': 100, 'time': 10, 'scramble': 'R U',
             'device': 'GAN356 i3'},
            {'date': 200, 'time': 11, 'scramble': 'R U',
             'device': 'MoYu AI'},
        ])

        solves = load_all_solves(
            3, ['cstimer'], [], ['GAN356 i3'],
            directory=self.directory,
        )

        self.assertEqual(len(solves), 1)
        self.assertEqual(solves[0].device, 'GAN356 i3')

    def test_multi_session_devices_filter(self) -> None:
        """Multiple included sessions are filtered by devices."""
        self.write_session('cstimer', [
            {'date': 100, 'time': 10, 'scramble': 'R U',
             'device': 'GAN356 i3'},
        ])
        self.write_session('cubeast', [
            {'date': 200, 'time': 11, 'scramble': 'R U',
             'device': 'MoYu AI'},
            {'date': 300, 'time': 12, 'scramble': 'R U',
             'device': 'GAN356 i3'},
        ])

        solves = load_all_solves(
            3, ['cstimer', 'cubeast'], [], ['GAN356 i3'],
            directory=self.directory,
        )

        self.assertEqual(len(solves), 2)
        self.assertTrue(
            all(solve.device == 'GAN356 i3' for solve in solves),
        )

    def test_deduplication_across_sessions(self) -> None:
        """Two solves sharing the same date collapse into one."""
        self.write_session('cstimer', [
            {'date': 100, 'time': 10, 'scramble': 'R U'},
        ])
        self.write_session('cubeast', [
            {'date': 100, 'time': 10, 'scramble': 'R U'},
            {'date': 200, 'time': 11, 'scramble': 'R U'},
        ])

        solves = load_all_solves(
            3, [], [], [],
            directory=self.directory,
        )

        self.assertEqual(len(solves), 2)
        self.assertEqual([solve.date for solve in solves], [100, 200])

    def test_devices_filter_applied_before_deduplication(self) -> None:
        """On date collision the solve of the requested device survives."""
        self.write_session('cstimer', [
            {'date': 100, 'time': 10, 'scramble': 'R U',
             'device': 'MoYu AI'},
        ])
        self.write_session('cubeast', [
            {'date': 100, 'time': 12, 'scramble': 'R U',
             'device': 'GAN356 i3'},
        ])

        solves = load_all_solves(
            3, [], [], ['GAN356 i3'],
            directory=self.directory,
        )

        self.assertEqual(len(solves), 1)
        self.assertEqual(solves[0].device, 'GAN356 i3')

    def test_result_sorted_by_date(self) -> None:
        """The merged result is sorted chronologically."""
        self.write_session('cstimer', [
            {'date': 300, 'time': 10, 'scramble': 'R U'},
            {'date': 100, 'time': 11, 'scramble': 'R U'},
        ])
        self.write_session('cubeast', [
            {'date': 200, 'time': 12, 'scramble': 'R U'},
        ])

        solves = load_all_solves(
            3, [], [], [],
            directory=self.directory,
        )

        self.assertEqual(
            [solve.date for solve in solves],
            [100, 200, 300],
        )


class TestTrainingsSolution(unittest.TestCase):
    """Tests for the custom per-case solution persistence."""

    def test_as_save_includes_solution_when_set(self) -> None:
        """A non-empty solution is serialized under the solution key."""
        case = CaseTraining(
            code='Sune',
            last_date=1700000000,
            timings=[1234],
            solution="R U R' U R U2 R'",
        )

        self.assertEqual(case.as_save['solution'], "R U R' U R U2 R'")

    def test_as_save_omits_empty_solution(self) -> None:
        """An empty solution leaves the solution key out of the payload."""
        case = CaseTraining(
            code='Sune',
            last_date=1700000000,
            timings=[1234],
        )

        self.assertNotIn('solution', case.as_save)

    def test_load_trainings_reads_solution(self) -> None:
        """load_trainings deserializes the solution key into the case."""
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / 'CFOP').mkdir()
            (directory / 'CFOP' / 'OLL.json').write_text(
                json.dumps(
                    {
                        'Sune': {
                            'last_date': 1700000000,
                            'timings': [1234],
                            'solution': "R U R' U R U2 R'",
                        },
                    },
                ),
                encoding='utf-8',
            )

            with patch('term_timer.in_out.TRAININGS_DIRECTORY', directory):
                trainings = load_trainings('CFOP', 'OLL')

            self.assertEqual(
                trainings.cases['Sune'].solution,
                "R U R' U R U2 R'",
            )

    def test_solution_survives_save_round_trip(self) -> None:
        """A manually-added solution is preserved across save/load."""
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)

            trainings = Trainings(
                method='CFOP',
                step='OLL',
                cases={
                    'Sune': CaseTraining(
                        code='Sune',
                        last_date=1700000000,
                        timings=[1234],
                        solution="R U R' U R U2 R'",
                    ),
                },
            )

            with patch('term_timer.in_out.TRAININGS_DIRECTORY', directory):
                save_trainings(trainings)
                reloaded = load_trainings('CFOP', 'OLL')

            self.assertEqual(
                reloaded.cases['Sune'].solution,
                "R U R' U R U2 R'",
            )


class TestReadTrainings(unittest.TestCase):
    """read_trainings is the side-effect free, fault tolerant reader."""

    def setUp(self) -> None:
        """Point the trainings directory at a temporary folder."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name) / 'trainings'

        patcher = patch(
            'term_timer.in_out.TRAININGS_DIRECTORY', self.directory,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, content: str) -> None:
        """Write the raw content of the CFOP/OLL training file."""
        (self.directory / 'CFOP').mkdir(parents=True, exist_ok=True)
        (self.directory / 'CFOP' / 'OLL.json').write_text(
            content, encoding='utf-8',
        )

    def test_missing_file(self) -> None:
        """A missing file is None, and no directory gets created."""
        self.assertIsNone(read_trainings('CFOP', 'OLL'))
        self.assertFalse(self.directory.exists())

    def test_truncated_file(self) -> None:
        """A file cut in the middle of a write is None, not an error."""
        self.write('{"27": {"last_date": 17000')

        self.assertIsNone(read_trainings('CFOP', 'OLL'))

    def test_malformed_entry(self) -> None:
        """Valid JSON missing a mandatory key is None, not an error."""
        self.write(json.dumps({'27': {'timings': [1234]}}))

        self.assertIsNone(read_trainings('CFOP', 'OLL'))

    def test_valid_file_matches_load_trainings(self) -> None:
        """A valid file reads exactly as load_trainings loads it."""
        self.write(json.dumps({
            '27': {
                'last_date': 1700000000,
                'timings': [1234, 2345],
                'solution': "R U R' U R U2 R'",
            },
        }))

        self.assertEqual(
            read_trainings('CFOP', 'OLL'),
            load_trainings('CFOP', 'OLL'),
        )


class TestListTrainingSteps(unittest.TestCase):
    """list_training_steps finds the trained steps of a method."""

    def test_missing_directory(self) -> None:
        """No trainings directory means no step, and nothing created."""
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'trainings'
            with patch('term_timer.in_out.TRAININGS_DIRECTORY', directory):
                self.assertEqual(list_training_steps('CFOP'), [])
            self.assertFalse(directory.exists())

    def test_steps_sorted(self) -> None:
        """Every JSON file is a step, listed by name."""
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / 'CFOP').mkdir()
            for name in ('PLL.json', 'F2L.json', 'OLL.json', 'notes.txt'):
                (directory / 'CFOP' / name).write_text('{}', encoding='utf-8')

            with patch('term_timer.in_out.TRAININGS_DIRECTORY', directory):
                self.assertEqual(
                    list_training_steps('CFOP'), ['F2L', 'OLL', 'PLL'],
                )
