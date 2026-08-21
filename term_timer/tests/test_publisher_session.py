"""
Tests for the publication of the session event stream.

No socket and no cube here: what the emission points owe the protocol is
that they publish, on the right topic, with the payload the specification
names. The publisher itself is tested against real sockets in
``test_publisher``.
"""
import asyncio
import unittest
from datetime import UTC
from datetime import datetime
from random import Random
from typing import Any
from unittest.mock import MagicMock
from unittest.mock import patch

from cubing_algs.algorithm import Algorithm
from cubing_algs.parsing import parse_moves
from fsrs import Card
from fsrs import Rating

from term_timer.constants import DNF
from term_timer.fsrs.storage import CaseTraining
from term_timer.fsrs.storage import Trainings
from term_timer.interface.state import State
from term_timer.publisher import RECORD_TOPIC
from term_timer.publisher import SCRAMBLE_TOPIC
from term_timer.publisher import SESSION_TOPICS
from term_timer.publisher import SOLVE_TOPIC
from term_timer.publisher import STATE_TOPIC
from term_timer.publisher import TRAIN_TOPIC
from term_timer.solve import Solve
from term_timer.tests.test_ghost import make_solve
from term_timer.tests.test_timer import build_timer
from term_timer.trainer import Trainer

Message = tuple[str, dict[str, Any]]


class RecordingPublisher:
    """A publisher writing down what it is handed, and nothing else."""

    def __init__(self, *, active: bool = True) -> None:
        """Prepare an empty recorder, active unless told otherwise."""
        self.active = active
        self.messages: list[Message] = []

    def publish(self, topic: str, data: dict[str, Any]) -> None:
        """
        Record one published message.

        Args:
            topic: Topic of the message.
            data: Payload of the message.

        """
        self.messages.append((topic, data))

    def only(self, topic: str) -> dict[str, Any]:
        """
        Return the payload of the single message of a topic.

        Args:
            topic: Topic expected exactly once.

        Returns:
            The payload published on that topic.

        Raises:
            AssertionError: When the topic was not published exactly once.

        """
        payloads = [data for name, data in self.messages if name == topic]

        if len(payloads) != 1:
            msg = f'Expected one { topic }, got { len(payloads) }'
            raise AssertionError(msg)

        return payloads[0]

    def payloads(self, topic: str) -> list[dict[str, Any]]:
        """
        Return every payload published on a topic, in order.

        Args:
            topic: Topic to collect.

        Returns:
            The payloads published on that topic.

        """
        return [data for name, data in self.messages if name == topic]


class StateTestCase(unittest.TestCase):
    """The nine states of a solve, published where they are set."""

    def setUp(self) -> None:
        """Patch the singleton the state mixin publishes through."""
        self.publisher = RecordingPublisher()

        patcher = patch(
            'term_timer.interface.state.PUBLISHER', self.publisher,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        self.state = State()

    def test_a_transition_is_published(self) -> None:
        """Setting a state broadcasts it on its own topic."""
        self.state.set_state('solving')

        data = self.publisher.only(STATE_TOPIC)

        self.assertEqual(data['state'], 'solving')

    def test_the_previous_state_travels_with_the_new_one(self) -> None:
        """
        A transition is a pair, not a value.

        A subscriber arriving mid-session reads where the session comes
        from without having to remember what it never received.
        """
        self.state.set_state('scrambled')
        self.state.set_state('solving')

        states = [
            (data['previous'], data['state'])
            for data in self.publisher.payloads(STATE_TOPIC)
        ]

        self.assertEqual(states, [('', 'scrambled'), ('scrambled', 'solving')])

    def test_the_given_timestamp_is_the_published_instant(self) -> None:
        """The stopwatch dates its own transitions, the state obeys."""
        self.state.set_state('solving', 1234)

        self.assertEqual(self.publisher.only(STATE_TOPIC)['at'], 1234)

    def test_an_instant_is_taken_when_none_is_given(self) -> None:
        """A transition always carries an instant, dated on the spot."""
        self.state.set_state('init')

        self.assertGreater(self.publisher.only(STATE_TOPIC)['at'], 0)

    def test_the_state_is_still_set_and_signalled(self) -> None:
        """Publication is a side effect, the transition is the job."""
        self.state.set_state('saving')

        self.assertEqual(self.state.state, 'saving')
        self.assertTrue(self.state.state_event.is_set())


class IdleStateTestCase(unittest.TestCase):
    """The real singleton, bound to nothing, on the state path."""

    def test_an_idle_publisher_changes_nothing(self) -> None:
        """A session that publishes nothing runs exactly the same."""
        state = State()

        state.set_state('init')

        self.assertEqual(state.state, 'init')


class ScrambleTestCase(unittest.TestCase):
    """What the solver is shown is what the stream carries."""

    def setUp(self) -> None:
        """Patch the singleton the timer publishes through."""
        self.publisher = RecordingPublisher()

        patcher = patch('term_timer.timer.PUBLISHER', self.publisher)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_drawn_scramble_is_published(self) -> None:
        """The scramble, its oriented reading and the state to reach."""
        timer = build_timer()
        timer.scramble = parse_moves("R U R' U'")
        timer.scramble_oriented = parse_moves("L D L' D'")
        timer.facelets_scrambled = 'U' * 54

        timer.publish_scramble()

        data = self.publisher.only(SCRAMBLE_TOPIC)

        self.assertEqual(data['scramble'], "R U R' U'")
        self.assertEqual(data['oriented'], "L D L' D'")
        self.assertEqual(data['facelets'], 'U' * 54)
        self.assertEqual(data['cube_size'], 3)

    def test_an_imposed_list_says_where_the_attempt_sits(self) -> None:
        """A session running a scramble file publishes its progress."""
        scrambles = [parse_moves('R'), parse_moves('U'), parse_moves('F')]
        timer = build_timer(scrambles=scrambles)
        timer.counter = 2

        timer.publish_scramble()

        data = self.publisher.only(SCRAMBLE_TOPIC)

        self.assertEqual(data['index'], 2)
        self.assertEqual(data['total'], 3)

    def test_an_endless_session_has_no_total(self) -> None:
        """Drawing a scramble every time bounds nothing."""
        timer = build_timer()

        timer.publish_scramble()

        self.assertEqual(self.publisher.only(SCRAMBLE_TOPIC)['total'], 0)


class SolveTestCase(unittest.TestCase):
    """The solve payload, in the spelling the session file uses."""

    def setUp(self) -> None:
        """Patch the singleton the timer publishes through."""
        self.publisher = RecordingPublisher()

        patcher = patch('term_timer.timer.PUBLISHER', self.publisher)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_payload_keeps_the_storage_spelling(self) -> None:
        """
        What is published is what would be written down.

        The recorder of the plan is then a client writing its messages
        to a file, with no field to translate on the way.
        """
        solve = make_solve()
        timer = build_timer()

        timer.publish_solve(solve)

        data = self.publisher.only(SOLVE_TOPIC)

        for key, value in solve.as_save.items():
            self.assertEqual(data[key], value)

    def test_the_payload_carries_what_only_the_session_knows(self) -> None:
        """Where the attempt sits, and whether it counts."""
        timer = build_timer()
        timer.counter = 7

        timer.publish_solve(make_solve())

        data = self.publisher.only(SOLVE_TOPIC)

        self.assertEqual(data['counter'], 7)
        self.assertEqual(data['session'], 'default')
        self.assertEqual(data['cube_size'], 3)
        self.assertTrue(data['free_play'])
        self.assertFalse(data['dnf'])

    def test_a_reconstructed_solve_carries_its_steps(self) -> None:
        """The method breakdown travels with the solve producing it."""
        solve = make_solve(method='cfop')
        timer = build_timer()

        timer.publish_solve(solve)

        steps = self.publisher.only(SOLVE_TOPIC)['steps']

        self.assertTrue(steps)
        for step in steps:
            self.assertEqual(
                set(step),
                {
                    'name', 'type', 'moves', 'case',
                    'qtm', 'total', 'recognition', 'execution',
                },
            )

    def test_a_dnf_carries_no_breakdown(self) -> None:
        """A solve that never ends solved has no step worth reading."""
        solve = make_solve(method='cfop', flag=DNF)
        timer = build_timer()

        timer.publish_solve(solve)

        data = self.publisher.only(SOLVE_TOPIC)

        self.assertTrue(data['dnf'])
        self.assertEqual(data['steps'], [])

    def test_a_keyboard_solve_carries_no_breakdown(self) -> None:
        """Nothing to break down without a reconstruction."""
        solve = make_solve(moves=None)
        timer = build_timer()

        timer.publish_solve(solve)

        self.assertEqual(self.publisher.only(SOLVE_TOPIC)['steps'], [])

    def test_a_silent_session_never_analyses(self) -> None:
        """
        Nobody listening means nothing published, and nothing computed.

        The breakdown is the only expensive part of the payload: a
        session displaying no reconstruction must not pay for one just
        because the code that would publish it exists.
        """
        self.publisher.active = False
        solve = make_solve(method='cfop')
        timer = build_timer()

        timer.publish_solve(solve)

        self.assertEqual(self.publisher.messages, [])
        self.assertNotIn('method_applied', solve.__dict__)


class RecordTestCase(unittest.TestCase):
    """The records a solve breaks, published where they are found."""

    def setUp(self) -> None:
        """Patch the singleton the timer publishes through."""
        self.publisher = RecordingPublisher()

        patcher = patch('term_timer.timer.PUBLISHER', self.publisher)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_record_carries_its_delta(self) -> None:
        """The value, the one it beat, and what separates them."""
        timer = build_timer()
        timer.counter = 3

        timer.publish_records([('single', 8_000, 10_000)])

        data = self.publisher.only(RECORD_TOPIC)

        self.assertEqual(data['kind'], 'single')
        self.assertEqual(data['scope'], 'session')
        self.assertEqual(data['value'], 8_000)
        self.assertEqual(data['previous'], 10_000)
        self.assertEqual(data['delta'], -2_000)
        self.assertEqual(data['counter'], 3)

    def test_every_broken_record_gets_its_message(self) -> None:
        """A solve breaking a single and an average publishes both."""
        timer = build_timer()

        timer.publish_records(
            [('single', 8_000, 10_000), ('ao5', 9_000, 11_000)],
        )

        kinds = [
            data['kind'] for data in self.publisher.payloads(RECORD_TOPIC)
        ]

        self.assertEqual(kinds, ['single', 'ao5'])

    def test_a_new_best_single_is_published_by_the_solve_line(self) -> None:
        """
        The line celebrating a PB and the message announcing it agree.

        Both read the very same comparison, which is why the records are
        returned rather than searched for a second time.
        """
        slower = make_solve(time=20_000_000_000, moves=None)
        faster = make_solve(time=10_000_000_000, moves=None)
        timer = build_timer([slower])
        timer.console = MagicMock()

        with patch('term_timer.timer.SOUND_PLAYER'):
            timer.solve_line(faster)

        records = self.publisher.payloads(RECORD_TOPIC)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['kind'], 'single')
        self.assertEqual(records[0]['value'], 10_000_000_000)
        self.assertEqual(records[0]['previous'], 20_000_000_000)

    def test_a_slower_solve_breaks_nothing(self) -> None:
        """No record, no message."""
        faster = make_solve(time=10_000_000_000, moves=None)
        slower = make_solve(time=20_000_000_000, moves=None)
        timer = build_timer([faster])
        timer.console = MagicMock()

        with patch('term_timer.timer.SOUND_PLAYER'):
            timer.solve_line(slower)

        self.assertEqual(self.publisher.payloads(RECORD_TOPIC), [])

    def test_the_records_are_published_without_the_solve(self) -> None:
        """
        The line reading the records is not the one publishing the solve.

        The records are found the moment the solve is displayed, while
        the solve itself waits for the save prompt to settle it: the two
        topics leave the session at two different instants.
        """
        slower = make_solve(time=20_000_000_000, moves=None)
        faster = make_solve(time=10_000_000_000, moves=None)
        timer = build_timer([slower])
        timer.console = MagicMock()

        with patch('term_timer.timer.SOUND_PLAYER'):
            timer.solve_line(faster)

        self.assertEqual(len(self.publisher.payloads(RECORD_TOPIC)), 1)
        self.assertEqual(self.publisher.payloads(SOLVE_TOPIC), [])


class SettledSolveTestCase(unittest.TestCase):
    """A solve reaches the stream once the save prompt settled it."""

    def setUp(self) -> None:
        """Patch the singleton the timer publishes through."""
        self.publisher = RecordingPublisher()

        patcher = patch('term_timer.timer.PUBLISHER', self.publisher)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_kept_solve_is_published(self) -> None:
        """An attempt still on the stack is one that happened."""
        solve = make_solve(moves=None)
        timer = build_timer()
        timer.stack = [*timer.stack, solve]

        timer.publish_settled_solve(solve)

        self.assertEqual(len(self.publisher.payloads(SOLVE_TOPIC)), 1)

    def test_a_discarded_solve_never_reaches_the_stream(self) -> None:
        """
        An attempt dropped at the prompt never happened.

        A discard and a retry both pop the solve off the stack, so a
        client writing down what it receives records the session file,
        not the attempts on the way to it.
        """
        solve = make_solve(moves=None)
        timer = build_timer()

        timer.publish_settled_solve(solve)

        self.assertEqual(self.publisher.payloads(SOLVE_TOPIC), [])

    def test_the_flag_set_at_the_prompt_is_the_published_one(self) -> None:
        """
        A manual solve is flagged after it is timed, before it is sent.

        The 'd' and '2' keys of the save prompt are the only place a
        keyboard solve gets its flag: publishing before them announces
        a solve the session file contradicts.
        """
        solve = make_solve(moves=None)
        timer = build_timer()
        timer.stack = [*timer.stack, solve]

        solve.flag = DNF
        timer.publish_settled_solve(solve)

        self.assertTrue(self.publisher.only(SOLVE_TOPIC)['dnf'])

    def test_a_dnf_carries_its_solve_all_the_same(self) -> None:
        """A failed attempt is an attempt, and it is published."""
        solve = make_solve(method='cfop', flag=DNF)
        timer = build_timer()
        timer.stack = [*timer.stack, solve]

        timer.publish_settled_solve(solve)

        self.assertTrue(self.publisher.only(SOLVE_TOPIC)['dnf'])


class TrainingTestCase(unittest.TestCase):
    """A saved training attempt, with the card it just moved."""

    def setUp(self) -> None:
        """Patch the singleton the trainer publishes through."""
        self.publisher = RecordingPublisher()

        patcher = patch('term_timer.trainer.PUBLISHER', self.publisher)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.trainer = Trainer(
            step='oll',
            case_codes=[],
            oldest=0,
            slowest=0,
            random=0,
            new_cases_limit=5,
            filters=[],
            states=[],
            free_play=False,
            show_solution=False,
            show_breakdown=False,
            show_cube=False,
            metronome=0,
            orientation='DF',
            rng=Random(),  # noqa: S311
        )
        self.case = self.trainer.cases[0].case
        self.solve = Solve(0, 1_000_000_000, Algorithm(), moves='R@0 U@100')

    def test_the_attempt_names_its_case(self) -> None:
        """Step, family and code, so a subscriber knows what was drilled."""
        self.trainer.publish_training(
            self.case, self.solve, Rating.Good, dnf=False,
        )

        data = self.publisher.only(TRAIN_TOPIC)

        self.assertEqual(data['step'], self.trainer.step_label)
        self.assertEqual(data['case'], self.case.code)
        self.assertEqual(data['family'], self.case.family)
        self.assertEqual(data['algorithm'], str(self.solve.reconstruction))
        self.assertNotIn('@', data['algorithm'])

    def test_the_applied_rating_is_published(self) -> None:
        """The rating is the one saved, not the one previewed."""
        self.trainer.publish_training(
            self.case, self.solve, Rating.Again, dnf=True,
        )

        data = self.publisher.only(TRAIN_TOPIC)

        self.assertEqual(data['rating'], 'Again')
        self.assertTrue(data['dnf'])

    def test_a_skipped_rating_leaves_the_field_empty(self) -> None:
        """A free play or manual skip rates nothing, and says so."""
        self.trainer.publish_training(
            self.case, self.solve, None, dnf=False,
        )

        self.assertEqual(self.publisher.only(TRAIN_TOPIC)['rating'], '')

    def test_the_card_state_and_due_date_travel_along(self) -> None:
        """
        The schedule is the point of a training session.

        A hook posting "next review" needs the date the file was just
        written with, not one it would have to recompute.
        """
        card = Card()
        self.trainer.trainings.cases[self.case.code] = CaseTraining(
            code=self.case.code,
            last_date=0,
            timings=[],
            fsrs_card=card,
        )

        self.trainer.publish_training(
            self.case, self.solve, Rating.Good, dnf=False,
        )

        data = self.publisher.only(TRAIN_TOPIC)

        self.assertEqual(data['due'], card.due)
        self.assertEqual(data['state'], card.state.name)

    def test_an_untracked_case_carries_no_schedule(self) -> None:
        """A case FSRS never saw has no card to report."""
        self.trainer.trainings.cases.pop(self.case.code, None)

        self.trainer.publish_training(
            self.case, self.solve, None, dnf=False,
        )

        data = self.publisher.only(TRAIN_TOPIC)

        self.assertIsNone(data['due'])
        self.assertEqual(data['state'], '')

    def test_a_silent_session_publishes_nothing(self) -> None:
        """Nobody listening, nothing looked up."""
        self.publisher.active = False

        self.trainer.publish_training(
            self.case, self.solve, Rating.Good, dnf=False,
        )

        self.assertEqual(self.publisher.messages, [])

    def test_a_dnf_clears_what_a_discard_left_pending(self) -> None:
        """
        A DNF records no timing, so it breaks no record.

        The records of a discarded attempt were never published, and a
        DNF must not be the one publishing them: it never ran the
        comparison they come from.
        """
        self.trainer.pending_records = [('single', 8_000, 10_000)]
        self.trainer.console = MagicMock()

        with patch('term_timer.trainer.SOUND_PLAYER'):
            self.trainer.dnf_line()

        self.assertEqual(self.trainer.pending_records, [])

    def test_a_training_record_is_scoped_to_its_case(self) -> None:
        """
        A training record beats the history of one case, not a session.

        The pool it is read against is every timing that case ever got,
        so the case travels along and the scope says so: two sessions of
        the same case keep on breaking the same records.
        """
        self.trainer.counter = 4
        self.trainer.pending_records = [('single', 8_000, 10_000)]

        self.trainer.publish_records(self.case)

        data = self.publisher.only(RECORD_TOPIC)

        self.assertEqual(data['kind'], 'single')
        self.assertEqual(data['scope'], 'case')
        self.assertEqual(data['case'], self.case.code)
        self.assertEqual(data['value'], 8_000)
        self.assertEqual(data['previous'], 10_000)
        self.assertEqual(data['delta'], -2_000)
        self.assertEqual(data['counter'], 4)

    def test_every_broken_training_record_gets_its_message(self) -> None:
        """A case beating a single and an average publishes both."""
        self.trainer.pending_records = [
            ('single', 8_000, 10_000), ('ao5', 9_000, 11_000),
        ]

        self.trainer.publish_records(self.case)

        kinds = [
            data['kind'] for data in self.publisher.payloads(RECORD_TOPIC)
        ]

        self.assertEqual(kinds, ['single', 'ao5'])

    def test_a_free_play_attempt_says_it_leaves_nothing(self) -> None:
        """
        Free play writes no training file, but it happened.

        The flag is what tells a subscriber whether the attempt left
        anything behind: a client recording a session must not mistake
        a free play run for a drilled one.
        """
        self.trainer.free_play = True

        self.trainer.publish_training(
            self.case, self.solve, None, dnf=False,
        )

        data = self.publisher.only(TRAIN_TOPIC)

        self.assertTrue(data['free_play'])
        self.assertEqual(data['rating'], '')

    def test_a_drilled_attempt_is_not_free_play(self) -> None:
        """The recorded attempts say so too, from the first version."""
        self.trainer.publish_training(
            self.case, self.solve, Rating.Good, dnf=False,
        )

        self.assertFalse(self.publisher.only(TRAIN_TOPIC)['free_play'])

    def test_records_are_published_once(self) -> None:
        """
        A discarded attempt must not republish what it did not keep.

        The records wait on the instance for the save to happen, so
        they are handed over and dropped, never left for the next one.
        """
        self.trainer.pending_records = [('single', 8_000, 10_000)]

        self.trainer.publish_records(self.case)
        self.trainer.publish_records(self.case)

        self.assertEqual(len(self.publisher.payloads(RECORD_TOPIC)), 1)
        self.assertEqual(self.trainer.pending_records, [])


class DiscardedTrainingRecordTestCase(unittest.IsolatedAsyncioTestCase):
    """The records of a thrown away attempt never reach the stream."""

    CASE_CODE = 'T'

    def setUp(self) -> None:
        """Patch the singleton the trainer publishes through."""
        self.publisher = RecordingPublisher()

        patcher = patch('term_timer.trainer.PUBLISHER', self.publisher)
        patcher.start()
        self.addCleanup(patcher.stop)

    def make_trainer(self) -> Trainer:
        """
        Build a no-Bluetooth PLL trainer with one rated case.

        Returns:
            A Trainer ready to run the save prompt on CASE_CODE.

        """
        empty = Trainings(method='CFOP', step='PLL', cases={})
        with patch(
            'term_timer.trainer.load_trainings', return_value=empty,
        ):
            trainer = Trainer(
                step='pll',
                case_codes=[self.CASE_CODE],
                oldest=0,
                slowest=0,
                random=0,
                new_cases_limit=5,
                filters=[],
                states=[],
                free_play=False,
                show_solution=False,
                show_breakdown=False,
                show_cube=False,
                metronome=0,
                orientation='DF',
                rng=Random(),  # noqa: S311
            )
        trainer.bluetooth_interface = None
        trainer.console = MagicMock()
        date = int(datetime.now(tz=UTC).timestamp())
        trainer.trainings.add_timing(self.CASE_CODE, 2000, date)
        return trainer

    async def save(self, trainer: Trainer, char: str) -> None:
        """
        Run the save prompt of one attempt, answering with a fixed key.

        Args:
            trainer: The trainer running the attempt.
            char: The key answering the prompt.

        """
        case = next(
            tc.case for tc in trainer.cases if tc.case.code == self.CASE_CODE
        )
        solve = Solve(
            date=datetime.now(tz=UTC).timestamp(),
            time=2_000_000_000,
            scramble="R U R' U'",
            moves=None,
        )

        async def fake_getch(_mode: str, *_: object) -> str:
            await asyncio.sleep(0)
            return char

        with (
            patch('term_timer.trainer.save_trainings'),
            patch('term_timer.trainer.SOUND_PLAYER'),
            patch.object(
                trainer.fsrs_scheduler, 'update_card',
                MagicMock(return_value=Card()),
            ),
            patch.object(trainer, 'getch', side_effect=fake_getch),
        ):
            await trainer.save_training(case, solve)

    async def test_a_discarded_attempt_drops_its_records(self) -> None:
        """
        What the thrown away attempt broke goes with it.

        The records are read against a timing the discard pops, so the
        attempt that never was must not leave them for the next save to
        publish under its own counter.
        """
        trainer = self.make_trainer()
        trainer.pending_records = [('single', 8_000, 10_000)]

        await self.save(trainer, 'z')

        self.assertEqual(trainer.pending_records, [])
        self.assertEqual(self.publisher.payloads(RECORD_TOPIC), [])

    async def test_a_dropped_record_never_reaches_the_next_attempt(
            self,
    ) -> None:
        """A saved attempt breaking nothing publishes nothing."""
        trainer = self.make_trainer()
        trainer.pending_records = [('single', 8_000, 10_000)]

        await self.save(trainer, 'z')
        await self.save(trainer, ' ')

        self.assertEqual(self.publisher.payloads(RECORD_TOPIC), [])


class SessionTopicsTestCase(unittest.TestCase):
    """The emission points and the declared namespace agree."""

    def test_every_wired_topic_is_declared(self) -> None:
        """A topic published without being declared escapes the rules."""
        wired = {
            STATE_TOPIC, SCRAMBLE_TOPIC, SOLVE_TOPIC,
            RECORD_TOPIC, TRAIN_TOPIC,
        }

        self.assertTrue(wired.issubset(set(SESSION_TOPICS)))


if __name__ == '__main__':
    unittest.main()
