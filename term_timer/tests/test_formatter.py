"""Tests for formatter."""
import unittest
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import TYPE_CHECKING
from typing import cast
from unittest.mock import MagicMock

from cubing_algs.algorithm import Algorithm
from cubing_algs.parsing import parse_moves
from fsrs import Card
from fsrs import State

from term_timer.constants import DNF
from term_timer.constants import MS_TO_NS_FACTOR
from term_timer.constants import PLUS_TWO
from term_timer.constants import SECOND
from term_timer.formatter import clean_url
from term_timer.formatter import compute_padding
from term_timer.formatter import format_alg_aufs
from term_timer.formatter import format_alg_cubing_url
from term_timer.formatter import format_alg_diff
from term_timer.formatter import format_alg_moves
from term_timer.formatter import format_alg_pauses
from term_timer.formatter import format_alg_triggers
from term_timer.formatter import format_cube_db_url
from term_timer.formatter import format_delta
from term_timer.formatter import format_duration
from term_timer.formatter import format_edge
from term_timer.formatter import format_flag
from term_timer.formatter import format_float
from term_timer.formatter import format_fsrs_due
from term_timer.formatter import format_fsrs_state
from term_timer.formatter import format_grade
from term_timer.formatter import format_metric
from term_timer.formatter import format_score
from term_timer.formatter import format_session_name
from term_timer.formatter import format_term_timer_session_url
from term_timer.formatter import format_time

if TYPE_CHECKING:
    from term_timer.methods.annotations import StepSummary


class TestComputePadding(unittest.TestCase):
    """Tests for compute_padding function."""

    def test_compute_padding_small(self) -> None:
        """Test compute padding small."""
        result = compute_padding(5)
        self.assertEqual(result, 1)

    def test_compute_padding_boundary_ten(self) -> None:
        """Test compute padding boundary ten."""
        result = compute_padding(10)
        self.assertEqual(result, 2)

    def test_compute_padding_medium(self) -> None:
        """Test compute padding medium."""
        result = compute_padding(15)
        self.assertEqual(result, 2)

    def test_compute_padding_boundary_hundred(self) -> None:
        """Test compute padding boundary hundred."""
        result = compute_padding(100)
        self.assertEqual(result, 3)

    def test_compute_padding_large(self) -> None:
        """Test compute padding large."""
        result = compute_padding(150)
        self.assertEqual(result, 3)

    def test_compute_padding_boundary_thousand(self) -> None:
        """Test compute padding boundary thousand."""
        result = compute_padding(1000)
        self.assertEqual(result, 4)

    def test_compute_padding_very_large(self) -> None:
        """Test compute padding very large."""
        result = compute_padding(1500)
        self.assertEqual(result, 4)

    def test_compute_padding_zero(self) -> None:
        """Test compute padding zero."""
        result = compute_padding(0)
        self.assertEqual(result, 1)

    def test_compute_padding_negative(self) -> None:
        """Test compute padding negative."""
        result = compute_padding(-10)
        self.assertEqual(result, 1)

    def test_compute_padding_very_large_value(self) -> None:
        """Test compute padding very large value."""
        result = compute_padding(999999)
        self.assertEqual(result, 4)


class TestFormatFloat(unittest.TestCase):
    """Tests for format_float function."""

    def test_format_float_default_precision(self) -> None:
        """Test format float default precision."""
        result = format_float(12.345)
        self.assertEqual(result, '12.35')

    def test_format_float_custom_precision(self) -> None:
        """Test format float custom precision."""
        result = format_float(12.345678, precision=4)
        self.assertEqual(result, '12.3457')

    def test_format_float_trailing_zeros(self) -> None:
        """Test format float trailing zeros."""
        result = format_float(12.300)
        self.assertEqual(result, '12.3')

    def test_format_float_all_zeros(self) -> None:
        """Test format float all zeros."""
        result = format_float(12.000)
        self.assertEqual(result, '12')

    def test_format_float_zero(self) -> None:
        """Test format float zero."""
        result = format_float(0.0)
        self.assertEqual(result, '0')

    def test_format_float_negative(self) -> None:
        """Test format float negative."""
        result = format_float(-12.345)
        self.assertEqual(result, '-12.35')

    def test_format_float_small_value(self) -> None:
        """Test format float small value."""
        result = format_float(0.001)
        self.assertEqual(result, '0')

    def test_format_float_precision_zero(self) -> None:
        """Test format float precision zero."""
        result = format_float(12.345, precision=0)
        self.assertEqual(result, '12')

    def test_format_float_large_precision(self) -> None:
        """Test format float large precision."""
        result = format_float(1.23456789, precision=8)
        self.assertEqual(result, '1.23456789')


class TestFormatTime(unittest.TestCase):
    """Tests for format_time function."""

    def test_format_time_with_zero(self) -> None:
        """Test format time with zero."""
        self.assertEqual(format_time(0), '      DNF')

    def test_format_time_with_zero_no_dnf(self) -> None:
        """Test format time with zero no dnf."""
        result = format_time(0, allow_dnf=False)
        self.assertEqual(result, '00:00.000')

    def test_format_time_with_milliseconds(self) -> None:
        """Test format time with milliseconds."""
        time_ns = 12345678900
        expected = '00:12.345'
        self.assertEqual(format_time(time_ns), expected)

    def test_format_time_with_minutes(self) -> None:
        """Test format time with minutes."""
        time_ns = 65 * SECOND
        expected = '01:05.000'
        self.assertEqual(format_time(time_ns), expected)

    def test_format_time_with_hours(self) -> None:
        """Test format time with hours."""
        time_ns = 3665 * SECOND
        expected = '01:01:05.000'
        self.assertEqual(format_time(time_ns), expected)

    def test_format_time_exactly_one_minute(self) -> None:
        """Test format time exactly one minute."""
        time_ns = 60 * SECOND
        expected = '01:00.000'
        self.assertEqual(format_time(time_ns), expected)

    def test_format_time_exactly_one_hour(self) -> None:
        """Test format time exactly one hour."""
        time_ns = 3600 * SECOND
        expected = '01:00:00.000'
        self.assertEqual(format_time(time_ns), expected)

    def test_format_time_very_small(self) -> None:
        """Test format time very small."""
        time_ns = 123 * MS_TO_NS_FACTOR
        expected = '00:00.123'
        self.assertEqual(format_time(time_ns), expected)

    def test_format_time_multiple_hours(self) -> None:
        """Test format time multiple hours."""
        time_ns = 7325 * SECOND
        expected = '02:02:05.000'
        self.assertEqual(format_time(time_ns), expected)

    def test_format_time_rounding_milliseconds(self) -> None:
        """Test format time rounding milliseconds."""
        time_ns = 1234567890
        expected = '00:01.234'
        self.assertEqual(format_time(time_ns), expected)


class TestFormatDuration(unittest.TestCase):
    """Tests for format_duration function."""

    def test_format_duration(self) -> None:
        """Test format duration."""
        duration_ns = 12345678900
        expected = '12.35'
        self.assertEqual(format_duration(duration_ns), expected)

    def test_format_duration_zero(self) -> None:
        """Test format duration zero."""
        result = format_duration(0)
        self.assertEqual(result, '0.00')

    def test_format_duration_negative(self) -> None:
        """Test format duration negative."""
        duration_ns = -5 * SECOND
        expected = '-5.00'
        self.assertEqual(format_duration(duration_ns), expected)

    def test_format_duration_small_value(self) -> None:
        """Test format duration small value."""
        duration_ns = 500 * MS_TO_NS_FACTOR
        expected = '0.50'
        self.assertEqual(format_duration(duration_ns), expected)

    def test_format_duration_large_value(self) -> None:
        """Test format duration large value."""
        duration_ns = 300 * SECOND
        expected = '300.00'
        self.assertEqual(format_duration(duration_ns), expected)


class TestFormatEdge(unittest.TestCase):
    """Tests for format_edge function."""

    def test_format_edge(self) -> None:
        """Test format edge."""
        edge_ns = 12

        expected = '+00:12'
        self.assertEqual(format_edge(edge_ns, 605), expected)

        expected = '+0:12'
        self.assertEqual(format_edge(edge_ns, 75), expected)

        expected = '+12s'
        self.assertEqual(format_edge(edge_ns, 59), expected)

    def test_format_edge_minutes(self) -> None:
        """Test format edge minutes."""
        edge_ns = 72

        expected = '+01:12'
        self.assertEqual(format_edge(edge_ns, 605), expected)

        expected = '+1:12'
        self.assertEqual(format_edge(edge_ns, 75), expected)

        expected = '+12s'
        self.assertEqual(format_edge(edge_ns, 59), expected)

    def test_format_edge_dnf(self) -> None:
        """Test format edge dnf."""
        edge_ns = 0

        expected = '+00:00'
        self.assertEqual(format_edge(edge_ns, 605), expected)

    def test_format_edge_small_max_edge(self) -> None:
        """Test format edge small max edge."""
        result = format_edge(30, 59)
        self.assertEqual(result, '+30s')

    def test_format_edge_exactly_sixty(self) -> None:
        """Test format edge exactly sixty."""
        result = format_edge(60, 100)
        self.assertEqual(result, '+1:00')

    def test_format_edge_large_max_edge(self) -> None:
        """Test format edge large max edge."""
        result = format_edge(125, 700)
        self.assertEqual(result, '+02:05')

    def test_format_edge_boundary_600(self) -> None:
        """Test format edge boundary 600."""
        result = format_edge(125, 599)
        self.assertEqual(result, '+2:05')
        result = format_edge(125, 600)
        self.assertEqual(result, '+02:05')

    def test_format_edge_decimals_subsecond(self) -> None:
        """Test format edge with sub-second decimals."""
        self.assertEqual(format_edge(8.5, 11.5, 1), '+08.5s')
        self.assertEqual(format_edge(8.0, 11.5, 1), '+08.0s')
        self.assertEqual(format_edge(11.5, 11.5, 1), '+11.5s')

    def test_format_edge_decimals_zero_unchanged(self) -> None:
        """Test that decimals=0 keeps integer-second formatting."""
        self.assertEqual(format_edge(8.5, 11.5, 0), '+08s')
        self.assertEqual(format_edge(8.5, 11.5), '+08s')


class TestFormatDelta(unittest.TestCase):
    """Tests for format_delta function."""

    def test_format_delta_zero(self) -> None:
        """Test format delta zero."""
        self.assertEqual(format_delta(0), '')

    def test_format_delta_positive(self) -> None:
        """Test format delta positive."""
        delta_ns = 1 * SECOND
        expected = '[red]+1.00[/red]'
        self.assertEqual(format_delta(delta_ns), expected)

    def test_format_delta_negative(self) -> None:
        """Test format delta negative."""
        delta_ns = -1 * SECOND
        expected = '[green]-1.00[/green]'
        self.assertEqual(format_delta(delta_ns), expected)

    def test_format_delta_large_positive(self) -> None:
        """Test format delta large positive."""
        delta_ns = 100 * SECOND
        expected = '[red]+100.00[/red]'
        self.assertEqual(format_delta(delta_ns), expected)

    def test_format_delta_small_negative(self) -> None:
        """Test format delta small negative."""
        delta_ns = -50 * MS_TO_NS_FACTOR
        expected = '[green]-0.05[/green]'
        self.assertEqual(format_delta(delta_ns), expected)


class TestFormatScore(unittest.TestCase):
    """Tests for format_score function."""

    def test_format_score_high(self) -> None:
        """Test format score high."""
        result = format_score(16.5)
        self.assertEqual(result, '[green]16.50[/green]')

    def test_format_score_medium(self) -> None:
        """Test format score medium."""
        result = format_score(10.0)
        self.assertEqual(result, '[orange]10.00[/orange]')

    def test_format_score_low(self) -> None:
        """Test format score low."""
        result = format_score(5.0)
        self.assertEqual(result, '[red]5.00[/red]')

    def test_format_score_boundary_fourteen(self) -> None:
        """Test format score boundary fourteen."""
        result = format_score(14.0)
        self.assertEqual(result, '[green]14.00[/green]')
        result = format_score(13.99)
        self.assertEqual(result, '[orange]13.99[/orange]')

    def test_format_score_boundary_eight(self) -> None:
        """Test format score boundary eight."""
        result = format_score(8.0)
        self.assertEqual(result, '[orange]8.00[/orange]')
        result = format_score(7.99)
        self.assertEqual(result, '[red]7.99[/red]')

    def test_format_score_zero(self) -> None:
        """Test format score zero."""
        result = format_score(0.0)
        self.assertEqual(result, '[red]0.00[/red]')

    def test_format_score_negative(self) -> None:
        """Test format score negative."""
        result = format_score(-2.5)
        self.assertEqual(result, '[red]-2.50[/red]')

    def test_format_score_very_high(self) -> None:
        """Test format score very high."""
        result = format_score(25.0)
        self.assertEqual(result, '[green]25.00[/green]')


class TestFormatGrade(unittest.TestCase):
    """Tests for format_grade function."""

    def test_format_grade_s(self) -> None:
        """Test format grade s."""
        self.assertEqual(format_grade(20.0), 'S')
        self.assertEqual(format_grade(25.0), 'S')

    def test_format_grade_a_plus(self) -> None:
        """Test format grade a plus."""
        self.assertEqual(format_grade(18.0), 'A+')
        self.assertEqual(format_grade(19.5), 'A+')

    def test_format_grade_a(self) -> None:
        """Test format grade a."""
        self.assertEqual(format_grade(16.0), 'A')
        self.assertEqual(format_grade(17.5), 'A')

    def test_format_grade_b_plus(self) -> None:
        """Test format grade b plus."""
        self.assertEqual(format_grade(14.0), 'B+')
        self.assertEqual(format_grade(15.5), 'B+')

    def test_format_grade_b(self) -> None:
        """Test format grade b."""
        self.assertEqual(format_grade(12.0), 'B')
        self.assertEqual(format_grade(13.5), 'B')

    def test_format_grade_c_plus(self) -> None:
        """Test format grade c plus."""
        self.assertEqual(format_grade(10.0), 'C+')
        self.assertEqual(format_grade(11.5), 'C+')

    def test_format_grade_c(self) -> None:
        """Test format grade c."""
        self.assertEqual(format_grade(8.0), 'C')
        self.assertEqual(format_grade(9.5), 'C')

    def test_format_grade_d(self) -> None:
        """Test format grade d."""
        self.assertEqual(format_grade(6.0), 'D')
        self.assertEqual(format_grade(7.5), 'D')

    def test_format_grade_e(self) -> None:
        """Test format grade e."""
        self.assertEqual(format_grade(4.0), 'E')
        self.assertEqual(format_grade(5.5), 'E')

    def test_format_grade_f(self) -> None:
        """Test format grade f."""
        self.assertEqual(format_grade(3.0), 'F')
        self.assertEqual(format_grade(0.0), 'F')
        self.assertEqual(format_grade(-1.0), 'F')

    def test_format_grade_boundary_values(self) -> None:
        """Test format grade boundary values."""
        self.assertEqual(format_grade(19.99), 'A+')
        self.assertEqual(format_grade(17.99), 'A')
        self.assertEqual(format_grade(15.99), 'B+')
        self.assertEqual(format_grade(13.99), 'B')
        self.assertEqual(format_grade(11.99), 'C+')
        self.assertEqual(format_grade(9.99), 'C')
        self.assertEqual(format_grade(7.99), 'D')
        self.assertEqual(format_grade(5.99), 'E')
        self.assertEqual(format_grade(3.99), 'F')


class TestFormatFlag(unittest.TestCase):
    """Tests for format_flag function."""

    def test_format_flag_dnf(self) -> None:
        """Test format flag dnf."""
        result = format_flag(DNF)
        self.assertEqual(result, '[dnf]DNF[/dnf]')

    def test_format_flag_plus_two(self) -> None:
        """Test format flag plus two."""
        result = format_flag(PLUS_TWO)
        self.assertEqual(result, '[plus-two]+2[/plus-two]')

    def test_format_flag_empty(self) -> None:
        """Test format flag empty."""
        result = format_flag('')
        self.assertEqual(result, '[result][/result]')


class TestFormatFsrsState(unittest.TestCase):
    """Tests for format_fsrs_state function."""

    def test_format_fsrs_state_without_card(self) -> None:
        """Test format fsrs state of a case never trained."""
        result = format_fsrs_state(None)
        self.assertEqual(result, '[no-ao]N/A[/no-ao]')

    def test_format_fsrs_state_learning(self) -> None:
        """Test format fsrs state of a learning card."""
        result = format_fsrs_state(Card())
        self.assertEqual(result, '[learning]Learning[/learning]')

    def test_format_fsrs_state_review(self) -> None:
        """Test format fsrs state of a review card."""
        now = datetime.now(tz=UTC)
        card = Card(
            state=State.Review,
            stability=15.0,
            difficulty=5.0,
            due=now,
            last_review=now,
        )
        result = format_fsrs_state(card)
        self.assertEqual(result, '[review]Review[/review]')


class TestFormatFsrsDue(unittest.TestCase):
    """Tests for format_fsrs_due function."""

    def test_format_fsrs_due_without_card(self) -> None:
        """Test format fsrs due of a case never trained."""
        result = format_fsrs_due(None)
        self.assertEqual(result, '[no-ao]N/A[/no-ao]')

    def test_format_fsrs_due_past(self) -> None:
        """Test format fsrs due of a card waiting for review."""
        card = Card(due=datetime.now(tz=UTC) - timedelta(days=1))
        result = format_fsrs_due(card)
        self.assertEqual(result, '[warning]Overdue[/warning]')

    def test_format_fsrs_due_future(self) -> None:
        """Test format fsrs due of a card scheduled later."""
        due = datetime.now(tz=UTC) + timedelta(days=3)
        card = Card(due=due)
        result = format_fsrs_due(card)
        self.assertEqual(
            result,
            f'[no-ao]{ due.astimezone().strftime("%Y-%m-%d") }[/no-ao]',
        )


class TestFormatMetric(unittest.TestCase):
    """Tests for format_metric function."""

    def test_format_metric_tps(self) -> None:
        """Test format metric tps."""
        result = format_metric('tps', 2.1)
        self.assertEqual(result, '2.10 TPS')

    def test_format_metric_fluency(self) -> None:
        """Test format metric fluency."""
        result = format_metric('fluency', 54.0)
        self.assertEqual(result, '54%')

    def test_format_metric_percents(self) -> None:
        """Test format metric percentage metrics."""
        result = format_metric('execution_pause_percent', 20.25)
        self.assertEqual(result, '20.2%')

        result = format_metric('step_recognition_percent', 31.0)
        self.assertEqual(result, '31.0%')

    def test_format_metric_htm(self) -> None:
        """Test format metric htm."""
        result = format_metric('htm', 16.0)
        self.assertEqual(result, '16 HTM')

    def test_format_metric_qtm_counts(self) -> None:
        """Test format metric wasted moves and aufs."""
        result = format_metric('step_missed_moves', 6.0)
        self.assertEqual(result, '6 QTM')

        result = format_metric('aufs', 5.0)
        self.assertEqual(result, '5 QTM')

    def test_format_metric_rotations(self) -> None:
        """Test format metric rotations."""
        result = format_metric('rotations', 6.0)
        self.assertEqual(result, '6 rotations')

    def test_format_metric_unknown(self) -> None:
        """Test format metric fallback without unit."""
        result = format_metric('unknown', 1.5)
        self.assertEqual(result, '1.5')


class TestFormatSessionName(unittest.TestCase):
    """Tests for format_session_name function."""

    def test_format_session_name_with_dashes(self) -> None:
        """Test format session name with dashes."""
        result = format_session_name('my-session-name')
        self.assertEqual(result, 'My Session Name')

    def test_format_session_name_no_dashes(self) -> None:
        """Test format session name no dashes."""
        result = format_session_name('session')
        self.assertEqual(result, 'Session')

    def test_format_session_name_empty(self) -> None:
        """Test format session name empty."""
        result = format_session_name('')
        self.assertEqual(result, '')

    def test_format_session_name_multiple_words(self) -> None:
        """Test format session name multiple words."""
        result = format_session_name('practice-session-3x3x3')
        self.assertEqual(result, 'Practice Session 3X3X3')

    def test_format_session_name_already_formatted(self) -> None:
        """Test format session name already formatted."""
        result = format_session_name('Already Formatted')
        self.assertEqual(result, 'Already Formatted')

    def test_format_session_name_mixed_case(self) -> None:
        """Test format session name mixed case."""
        result = format_session_name('MiXeD-CaSe-NaMe')
        self.assertEqual(result, 'Mixed Case Name')


class TestCleanUrl(unittest.TestCase):
    """Tests for clean_url function."""

    def test_clean_url_spaces(self) -> None:
        """Test clean url spaces."""
        result = clean_url('hello world')
        self.assertEqual(result, 'hello_world')

    def test_clean_url_apostrophe(self) -> None:
        """Test clean url apostrophe."""
        result = clean_url("it's")
        self.assertEqual(result, 'it-s')

    def test_clean_url_slash(self) -> None:
        """Test clean url slash."""
        result = clean_url('path/to/file')
        self.assertEqual(result, 'path%2Fto%2Ffile')

    def test_clean_url_newline(self) -> None:
        """Test clean url newline."""
        result = clean_url('line1\nline2')
        self.assertEqual(result, 'line1%0Aline2')

    def test_clean_url_plus(self) -> None:
        """Test clean url plus."""
        result = clean_url('a+b')
        self.assertEqual(result, 'a%26%232b%3Bb')

    def test_clean_url_auf(self) -> None:
        """Test clean url auf."""
        result = clean_url("R U R'-AUF")
        self.assertEqual(result, 'R_U_R-%26%2345%3BAUF')

    def test_clean_url_empty(self) -> None:
        """Test clean url empty."""
        result = clean_url('')
        self.assertEqual(result, '')

    def test_clean_url_multiple_special_chars(self) -> None:
        """Test clean url multiple special chars."""
        result = clean_url("it's a+ test/file\nwith -AUF")
        expected = 'it-s_a%26%232b%3B_test%2Ffile%0Awith_%26%2345%3BAUF'
        self.assertEqual(result, expected)

    def test_clean_url_no_special_chars(self) -> None:
        """Test clean url no special chars."""
        result = clean_url('normaltext')
        self.assertEqual(result, 'normaltext')


class TestFormatAlgCubingUrl(unittest.TestCase):
    """Tests for format_alg_cubing_url function."""

    def test_format_alg_cubing_url_basic(self) -> None:
        """Test format alg cubing url basic."""
        result = format_alg_cubing_url('Test', 'R U', "R U R' U'")
        expected = (
            'https://alg.cubing.net/?view=playback'
            '&title=Test'
            '&alg=R_U_R-_U-'
            '&setup=R_U'
        )
        self.assertEqual(result, expected)

    def test_format_alg_cubing_url_empty_setup(self) -> None:
        """Test format alg cubing url empty setup."""
        result = format_alg_cubing_url('OLL', '', "F R U R' U' F'")
        self.assertIn('&setup=', result)
        self.assertIn('&alg=F_R_U_R-_U-_F-', result)

    def test_format_alg_cubing_url_special_chars(self) -> None:
        """Test format alg cubing url special chars."""
        result = format_alg_cubing_url('Test+Case', 'R/U', "R' U'")
        self.assertIn('https://alg.cubing.net/', result)
        self.assertIn('title=Test+Case', result)
        self.assertIn('setup=R%2FU', result)

    def test_format_alg_cubing_url_long_algorithm(self) -> None:
        """Test format alg cubing url long algorithm."""
        alg = "R U R' U' R' F R2 U' R' U' R U R' F'"
        result = format_alg_cubing_url('Long Alg', '', alg)
        self.assertIn('https://alg.cubing.net/', result)
        self.assertIn('title=Long Alg', result)
        self.assertIn('alg=R_U_R-_U-_R-_F_R2_U-_R-_U-_R_U_R-_F-', result)


class TestFormatCubeDbUrl(unittest.TestCase):
    """Tests for format_cube_db_url function."""

    def test_format_cube_db_url_basic(self) -> None:
        """Test format cube db url basic."""
        result = format_cube_db_url('Test', 'R U', "R U R' U'")
        expected = (
            'https://cubedb.net/'
            '?title=Test'
            '&alg=R_U_R-_U-'
            '&scramble=R_U'
        )
        self.assertEqual(result, expected)

    def test_format_cube_db_url_empty_setup(self) -> None:
        """Test format cube db url empty setup."""
        result = format_cube_db_url('PLL', '', "R U R' U'")
        self.assertIn('&scramble=', result)
        self.assertIn('&alg=R_U_R-_U-', result)

    def test_format_cube_db_url_special_chars(self) -> None:
        """Test format cube db url special chars."""
        result = format_cube_db_url('Test/Case', 'R+U', "R' U'")
        self.assertIn('https://cubedb.net/', result)
        self.assertIn('title=Test/Case', result)
        self.assertIn('scramble=R%26%232b%3BU', result)


class TestFormatTermTimerSessionUrl(unittest.TestCase):
    """Tests for format_term_timer_session_url function."""

    def test_format_term_timer_session_url_default(self) -> None:
        """Test format term timer session url default."""
        result = format_term_timer_session_url(3, 'practice')
        expected = 'http://localhost:8333/3/practice/'
        self.assertEqual(result, expected)

    def test_format_term_timer_session_url_different_cube(self) -> None:
        """Test format term timer session url different cube."""
        result = format_term_timer_session_url(4, 'session-name')
        self.assertIn('/4/session-name/', result)

    def test_format_term_timer_session_url_large_cube(self) -> None:
        """Test format term timer session url large cube."""
        result = format_term_timer_session_url(7, 'big-cube')
        self.assertIn('/7/big-cube/', result)

    def test_format_term_timer_session_url_empty_session(self) -> None:
        """Test format term timer session url empty session."""
        result = format_term_timer_session_url(3, '')
        self.assertIn('/3//', result)


class TestFormatAlgDiff(unittest.TestCase):
    """Tests for format_alg_diff function."""

    def test_format_alg_diff_identical(self) -> None:
        """Test format alg diff identical."""
        algo_a = Algorithm(parse_moves("R U R' U'"))
        algo_b = Algorithm(parse_moves("R U R' U'"))
        result = format_alg_diff(algo_a, algo_b)
        self.assertNotIn('[deletion]', result)
        self.assertNotIn('[addition]', result)

    def test_format_alg_diff_deletion(self) -> None:
        """Test format alg diff deletion."""
        algo_a = Algorithm(parse_moves("R U R' U'"))
        algo_b = Algorithm(parse_moves("R U R'"))
        result = format_alg_diff(algo_a, algo_b)
        self.assertIn('[deletion]', result)

    def test_format_alg_diff_insertion(self) -> None:
        """Test format alg diff insertion."""
        algo_a = Algorithm(parse_moves("R U R'"))
        algo_b = Algorithm(parse_moves("R U R' U'"))
        result = format_alg_diff(algo_a, algo_b)
        self.assertIn('[addition]', result)

    def test_format_alg_diff_replacement(self) -> None:
        """Test format alg diff replacement."""
        algo_a = Algorithm(parse_moves('R U'))
        algo_b = Algorithm(parse_moves('L D'))
        result = format_alg_diff(algo_a, algo_b)
        self.assertIn('[deletion]', result)
        self.assertIn('[addition]', result)

    def test_format_alg_diff_empty_to_nonempty(self) -> None:
        """Test format alg diff empty to nonempty."""
        algo_a = Algorithm()
        algo_b = Algorithm(parse_moves('R U'))
        result = format_alg_diff(algo_a, algo_b)
        self.assertIn('[addition]', result)

    def test_format_alg_diff_nonempty_to_empty(self) -> None:
        """Test format alg diff nonempty to empty."""
        algo_a = Algorithm(parse_moves('R U'))
        algo_b = Algorithm()
        result = format_alg_diff(algo_a, algo_b)
        self.assertIn('[deletion]', result)

    def test_format_alg_diff_both_empty(self) -> None:
        """Test format alg diff both empty."""
        algo_a = Algorithm()
        algo_b = Algorithm()
        result = format_alg_diff(algo_a, algo_b)
        self.assertEqual(result, '')


class TestFormatAlgTriggers(unittest.TestCase):
    """Tests for format_alg_triggers function."""

    def test_format_alg_triggers_no_triggers(self) -> None:
        """Test format alg triggers no triggers."""
        result = format_alg_triggers("R U R' U'", [])
        self.assertEqual(result, "R U R' U'")

    def test_format_alg_triggers_empty_algorithm(self) -> None:
        """Test format alg triggers empty algorithm."""
        result = format_alg_triggers('', ['sexy-move'])
        self.assertEqual(result, '')

    def test_format_alg_triggers_with_trigger(self) -> None:
        """Test format alg triggers with trigger."""
        result = format_alg_triggers("R U R' U'", ['sexy-move'])
        self.assertIn('sexy-move', result)


class TestFormatAlgAufs(unittest.TestCase):
    """Tests for format_alg_aufs function."""

    def test_format_alg_aufs_no_aufs(self) -> None:
        """Test format alg aufs no aufs."""
        result = format_alg_aufs("R U R' U'", 0, 0)
        self.assertEqual(result, "R U R' U'")

    def test_format_alg_aufs_empty_algorithm(self) -> None:
        """Test format alg aufs empty algorithm."""
        result = format_alg_aufs('', 1, 1)
        self.assertEqual(result, '')

    def test_format_alg_aufs_with_pre_auf(self) -> None:
        """Test format alg aufs with pre auf."""
        result = format_alg_aufs("U R U R' U'", 1, 0)
        self.assertIn('[pre-auf]U[/pre-auf]', result)

    def test_format_alg_aufs_with_post_auf(self) -> None:
        """Test format alg aufs with post auf."""
        result = format_alg_aufs("R U R' U' U", 0, 1)
        self.assertIn('[post-auf]U[/post-auf]', result)

    def test_format_alg_aufs_with_both(self) -> None:
        """Test format alg aufs with both."""
        result = format_alg_aufs("U R U R' U' U'", 1, 1)
        self.assertIn('[pre-auf]', result)
        self.assertIn('[post-auf]', result)

    def test_format_alg_aufs_with_pause_and_pre_auf(self) -> None:
        """Test format alg aufs with pause and pre auf."""
        result = format_alg_aufs("U . R U R'", 1, 0)
        self.assertIn('[pre-auf]U[/pre-auf]', result)
        self.assertIn('.', result)

    def test_format_alg_aufs_with_pause_and_post_auf(self) -> None:
        """Test format alg aufs with pause and post auf."""
        result = format_alg_aufs("R U R' . U'", 0, 1)
        self.assertIn("[post-auf]U'[/post-auf]", result)

    def test_format_alg_aufs_only_pauses_pre_auf(self) -> None:
        """Test format alg aufs only pauses pre auf."""
        result = format_alg_aufs('. . R U', 1, 0)
        self.assertNotIn('[pre-auf]', result)

    def test_format_alg_aufs_multiple_pre_aufs(self) -> None:
        """Test format alg aufs multiple pre aufs."""
        result = format_alg_aufs("U U' R U R'", 2, 0)
        self.assertIn('[pre-auf]U[/pre-auf]', result)
        self.assertIn("[pre-auf]U'[/pre-auf]", result)


class TestFormatAlgPauses(unittest.TestCase):
    """Tests for format_alg_pauses function."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.solve = MagicMock()
        self.solve.pause_threshold = 1000 * MS_TO_NS_FACTOR
        self.step: StepSummary = cast('StepSummary', {
            'type': 'step',
            'name': 'Test',
            'moves': Algorithm(),
            'moves_reoriented': Algorithm(),
            'moves_humanized': Algorithm(),
            'moves_prettified': Algorithm(),
            'times': [],
            'index': [],
            'qtm': 0,
            'total': 0,
            'execution': 0,
            'recognition': 0,
            'post_pause': 0,
            'aufs': [],
            'total_percent': 0.0,
            'execution_percent': 0.0,
            'recognition_percent': 0.0,
            'step_execution_percent': 0.0,
            'step_recognition_percent': 0.0,
            'increment': 0,
            'case': '',
            'case_infos': [],
            'facelets': '',
        })

    def test_format_alg_pauses_no_pauses(self) -> None:
        """Test format alg pauses no pauses."""
        result = format_alg_pauses("R U R' U'", self.solve, self.step)
        self.assertEqual(result, "R U R' U'")

    def test_format_alg_pauses_with_pause_markers(self) -> None:
        """Test format alg pauses with pause markers."""
        result = format_alg_pauses("R . U R'", self.solve, self.step)
        self.assertIn('[pause].[/pause]', result)

    def test_format_alg_pauses_with_post_pause(self) -> None:
        """Test format alg pauses with post pause."""
        self.step['post_pause'] = 1000 * MS_TO_NS_FACTOR
        result = format_alg_pauses('R U', self.solve, self.step)
        self.assertIn('[reco-pause].[/reco-pause]', result)

    def test_format_alg_pauses_multiple_post_pauses(self) -> None:
        """Test format alg pauses multiple post pauses."""
        self.step['post_pause'] = 3000 * MS_TO_NS_FACTOR
        result = format_alg_pauses('R U', self.solve, self.step, multiple=True)
        self.assertEqual(result.count('[reco-pause].[/reco-pause]'), 3)

    def test_format_alg_pauses_multiple_post_pauses_single(self) -> None:
        """Test format alg pauses multiple post pauses single."""
        self.step['post_pause'] = 3000 * MS_TO_NS_FACTOR
        result = format_alg_pauses('R U', self.solve, self.step, multiple=False)
        self.assertEqual(result.count('[reco-pause].[/reco-pause]'), 1)

    def test_format_alg_pauses_combined(self) -> None:
        """Test format alg pauses combined."""
        self.step['post_pause'] = 1000 * MS_TO_NS_FACTOR
        result = format_alg_pauses('R . U', self.solve, self.step)
        self.assertIn('[pause].[/pause]', result)
        self.assertIn('[reco-pause].[/reco-pause]', result)


class TestFormatAlgMoves(unittest.TestCase):
    """Tests for format_alg_moves function."""

    def test_format_alg_moves_empty(self) -> None:
        """Test format alg moves empty."""
        result = format_alg_moves('')
        self.assertEqual(result, '')

    def test_format_alg_moves_normal_moves(self) -> None:
        """Test format alg moves normal moves."""
        result = format_alg_moves('R U D L')
        self.assertEqual(result, 'R U D L')

    def test_format_alg_moves_wide_moves(self) -> None:
        """Test format alg moves wide moves."""
        result = format_alg_moves('r u')
        self.assertIn('[wide]r[/wide]', result)
        self.assertIn('[wide]u[/wide]', result)

    def test_format_alg_moves_slice_moves(self) -> None:
        """Test format alg moves slice moves."""
        result = format_alg_moves('M E S')
        self.assertIn('[slice]M[/slice]', result)
        self.assertIn('[slice]E[/slice]', result)
        self.assertIn('[slice]S[/slice]', result)

    def test_format_alg_moves_rotations(self) -> None:
        """Test format alg moves rotations."""
        result = format_alg_moves('x y z')
        self.assertIn('[rotation_x]x[/rotation_x]', result)
        self.assertIn('[rotation_y]y[/rotation_y]', result)
        self.assertIn('[rotation_z]z[/rotation_z]', result)

    def test_format_alg_moves_mixed(self) -> None:
        """Test format alg moves mixed."""
        result = format_alg_moves('R r M x U')
        self.assertIn('R', result)
        self.assertIn('[wide]r[/wide]', result)
        self.assertIn('[slice]M[/slice]', result)
        self.assertIn('[rotation_x]x[/rotation_x]', result)
        self.assertIn('U', result)

    def test_format_alg_moves_with_modifiers(self) -> None:
        """Test format alg moves with modifiers."""
        result = format_alg_moves("R' R2 r' r2")
        self.assertIn("R'", result)
        self.assertIn('R2', result)
        self.assertIn("[wide]r'[/wide]", result)
        self.assertIn('[wide]r2[/wide]', result)
