"""Calendar of the solves per day, laid out for the punchcard component."""
from collections import Counter
from collections.abc import Iterable
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import Final

from term_timer.server.annotations import ActivityCalendarData
from term_timer.server.annotations import ActivityCell
from term_timer.server.annotations import ActivityMonth

# Solves a day above which a cell heats up one level, from 1 to 4.
HEAT_EDGES: Final = (0, 3, 8, 15)

# Weeks of a calendar: a year, or at least half a year for a short span.
YEAR_WEEKS: Final = 53
HALF_YEAR_WEEKS: Final = 26

DAYS_IN_WEEK: Final = 7
# A month is labelled on the week holding its first day.
MONTH_START_DAYS: Final = 7


class ActivityCalendar:
    """Weeks of seven days, Monday first, each day heated by its count."""

    def __init__(self, counts: dict[date, int]) -> None:
        """
        Keep the number of solves of each day.

        Args:
            counts: Solves per day, days without solve absent.

        """
        self.counts = counts

    @classmethod
    def from_moments(cls, moments: Iterable[datetime]) -> 'ActivityCalendar':
        """
        Count the solves of each local day.

        Args:
            moments: When each solve was done.

        Returns:
            The calendar of these solves.

        """
        return cls(Counter(moment.astimezone().date() for moment in moments))

    @staticmethod
    def span_weeks(first: date, last: date) -> int:
        """
        Count the weeks a period spans, between half a year and a year.

        Returns:
            The number of weeks of its calendar.

        """
        weeks = (last - first).days // DAYS_IN_WEEK + 2
        return max(HALF_YEAR_WEEKS, min(YEAR_WEEKS, weeks))

    @staticmethod
    def level(count: int) -> int:
        """
        Heat level of a day.

        Returns:
            0 without solve, up to 4 above the last edge.

        """
        return sum(count > edge for edge in HEAT_EDGES)

    def layout(self, end: date,
               weeks: int = YEAR_WEEKS) -> ActivityCalendarData:
        """
        Lay the days on the weeks ending with the week of the end day.

        The days after the end, in its week, are marked out of range by a
        level of -1.

        Args:
            end: Last day shown.
            weeks: Number of weeks shown.

        Returns:
            The weeks of cells, the month labels, the totals over the
            shown days and the number of weeks kept on a narrow screen.

        """
        start = end - timedelta(days=end.weekday(), weeks=weeks - 1)
        grid: list[list[ActivityCell]] = []
        months: list[ActivityMonth] = []
        total = active = 0

        for week in range(weeks):
            monday = start + timedelta(weeks=week)
            cells: list[ActivityCell] = []
            for offset in range(DAYS_IN_WEEK):
                day = monday + timedelta(days=offset)
                count = self.counts.get(day, 0) if day <= end else 0
                total += count
                active += bool(count)
                cells.append({
                    'day': day,
                    'count': count,
                    'level': self.level(count) if day <= end else -1,
                })
            grid.append(cells)
            if monday.day <= MONTH_START_DAYS:
                months.append({'week': week + 1, 'label': f'{ monday:%b}'})

        return {
            'weeks': grid,
            'months': months,
            'total': total,
            'active': active,
            'recent': weeks - weeks // 2,
        }
