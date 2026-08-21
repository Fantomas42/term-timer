"""Configurable rolling-average series rendering for solves."""
from typing import TYPE_CHECKING

from term_timer.formatter import format_delta
from term_timer.formatter import format_time
from term_timer.interface.console import theme
from term_timer.publisher import PUBLISHER
from term_timer.publisher import RECORD_TOPIC

if TYPE_CHECKING:
    from rich.console import Console as RichConsole

    from term_timer.stats import Statistics

# Generic style used when a series token has no dedicated console style
SERIES_STYLE_FALLBACK = 'average'

# Emoji celebrating a freshly broken record, per series entry, with a
# generic fallback for any size/kind not listed
SERIES_RECORD_EMOJI: dict[tuple[str, int], str] = {
    ('ao', 5): ':boom:',
    ('ao', 12): ':muscle:',
    ('ao', 100): ':crown:',
    ('ao', 1000): ':trophy:',
}
SERIES_RECORD_EMOJI_FALLBACK = ':sparkles:'


class SeriesReporter:
    """
    Mixin rendering configurable rolling-average series for solves.

    Factorises the per-solve display once duplicated between the timer
    and the trainer: the inline ``extra`` stats line and the broken-records
    watch. Both are driven by a configurable series of ``(kind, size)``
    pairs (see ``parse_series``), so the timer, the trainer and the session
    table all render the same averages from a single place.
    """

    if TYPE_CHECKING:
        # Attributes from Console mixin
        console: RichConsole

        # Attributes from Scrambler mixin
        counter: int

    @staticmethod
    def series_style(token: str) -> str:
        """
        Return the console style for a series token, with a fallback.

        Args:
            token: Series token such as ``ao5`` or ``mo3``.

        Returns:
            The dedicated style name when one exists in the theme, otherwise
            the generic ``average`` fallback style.

        """
        return token if token in theme else SERIES_STYLE_FALLBACK

    @staticmethod
    def series_label(kind: str, size: int) -> str:
        """
        Format a human-readable label for a series entry.

        Args:
            kind: Series kind (``mo``, ``ao``, ``mb`` or ``mw``).
            size: Window size of the average.

        Returns:
            Capitalised label such as ``Ao5`` or ``Mo3``.

        """
        return f'{ kind.capitalize() }{ size }'

    @classmethod
    def format_series_line(
            cls,
            stats: 'Statistics',
            series: list[tuple[str, int]],
            *,
            suffix: str = '',
    ) -> str:
        """
        Build the inline per-solve stats line for a configurable series.

        Starts with the delta against the previous solve, then appends each
        series entry whose window is reachable (``total >= size``). An
        optional suffix is appended last (used by the trainer for its speed
        trend).

        Args:
            stats: Statistics for the session up to and including this solve.
            series: Series of ``(kind, size)`` pairs to display.
            suffix: Extra markup appended at the end of the line.

        Returns:
            Rich-formatted line, or an empty string for the first solve.

        """
        if stats.total <= 1:
            return ''

        parts = [format_delta(stats.delta)]

        for kind, size in series:
            if stats.total < size:
                continue

            value = getattr(stats, kind)(size, stats.stack_time)
            token = f'{ kind }{ size }'
            style = cls.series_style(token)
            label = cls.series_label(kind, size)
            parts.append(
                f'[{ style }]{ label } { format_time(value) }[/{ style }]',
            )

        line = ' '.join(parts)
        if suffix:
            line += f' { suffix }'

        return line

    def print_best_record(
            self,
            new_stats: 'Statistics',
            old_stats: 'Statistics',
    ) -> list[tuple[str, int, int]]:
        """
        Print the overall record line when this solve is a new best.

        The single stands apart from the series: it is no rolling
        average, and it is the one record every session watches. It is
        returned in the same shape as the series ones, so that a caller
        publishing records reads a single list built by a single
        comparison.

        Args:
            new_stats: Statistics including the latest solve.
            old_stats: Statistics before the latest solve.

        Returns:
            The ``('single', value, previous)`` triple, empty when the
            solve broke nothing.

        """
        if new_stats.total <= 1 or new_stats.best >= old_stats.best:
            return []

        mc = 9 + len(str(self.counter))

        self.console.print(
            f'[record]:rocket:{ "New PB !".center(mc) }[/record]',
            f'[best]{ format_time(new_stats.best) }[/best]',
            format_delta(new_stats.best - old_stats.best),
        )

        return [('single', new_stats.best, old_stats.best)]

    def print_session_records(
            self,
            new_stats: 'Statistics',
            old_stats: 'Statistics',
            series: list[tuple[str, int]],
    ) -> list[tuple[str, int, int]]:
        """
        Print a record line for each series average beaten by this solve.

        Compares each new rolling average against the session best held
        before the solve and celebrates the ones that improved. The overall
        ``New PB`` line stays outside the series, in ``print_best_record``.

        The broken records are returned rather than only printed, so that
        a caller publishing them on the event stream reads the very same
        comparison the line celebrates, instead of running it twice.

        Args:
            new_stats: Statistics including the latest solve.
            old_stats: Statistics before the latest solve.
            series: Series of ``(kind, size)`` pairs to watch.

        Returns:
            One ``(token, value, previous)`` triple per broken record, in
            the order they are printed.

        """
        records: list[tuple[str, int, int]] = []

        if new_stats.total <= 1:
            return records

        mc = 9 + len(str(self.counter))

        for kind, size in series:
            if new_stats.total < size:
                continue

            value = getattr(new_stats, kind)(size, new_stats.stack_time)
            best = getattr(old_stats, f'best_{ kind }')(size)

            if value <= 0 or value >= best:
                continue

            records.append((f'{ kind }{ size }', value, best))

            emoji = SERIES_RECORD_EMOJI.get(
                (kind, size), SERIES_RECORD_EMOJI_FALLBACK,
            )
            label = f'Best { self.series_label(kind, size) }'
            self.console.print(
                f'[record]{ emoji }{ label.center(mc) }[/record]',
                f'[best]{ format_time(value) }[/best]',
                format_delta(value - best),
            )

        return records

    def publish_records(
            self,
            records: list[tuple[str, int, int]],
            scope: str,
            case: str = '',
    ) -> None:
        """
        Publish the records the attempt just broke.

        The class finding the records is the one publishing them: the
        celebrating lines and the messages read one comparison, run
        once, so a session and a training can never disagree on what
        was broken.

        The scope says what the value was read against. A ``session``
        one compares against the stack the session runs on; a ``case``
        one compares against every timing a trained case ever got, and
        names that case, so two sessions of the same case keep on
        breaking the same records.

        Args:
            records: The ``(kind, value, previous)`` triples broken.
            scope: What the values were read against.
            case: The case the records belong to, on a ``case`` scope.

        """
        for kind, value, previous in records:
            data = {
                'kind': kind,
                'scope': scope,
                'value': value,
                'previous': previous,
                'delta': value - previous,
                'counter': self.counter,
            }

            if case:
                data['case'] = case

            PUBLISHER.publish(RECORD_TOPIC, data)
