"""Date utilities for Amazing Marvin MCP.

Limitation: these helpers use the host's local calendar date and do NOT honor
Marvin's profile-level rollover hour (the hour at which "today" rolls to the
next day, e.g. 4 AM for users who work late) or the user's configured work-week
start. On accounts that customize these settings, the values returned here can
disagree with Marvin's logical "today" by one day around the rollover hour, and
week boundaries computed from these dates won't match what the client shows.
Productivity summary date ranges driven by `get_today` / `get_yesterday` are
the most likely place this drift surfaces. A rollover-aware implementation
would need to read ProfileItems (`profile.rollover`, `profile.weekStart`) and
apply them — kept out of scope here to avoid making date math depend on a
profile fetch on every call.
"""

from datetime import datetime, timedelta


class DateUtils:
    """Utility class for date operations.

    See module docstring for the rollover/weekStart limitation.
    """

    DATE_FORMAT = "%Y-%m-%d"

    @staticmethod
    def format_date(date: datetime) -> str:
        """Format datetime to YYYY-MM-DD string."""
        return date.strftime(DateUtils.DATE_FORMAT)

    @staticmethod
    def parse_date(date_str: str) -> datetime:
        """Parse YYYY-MM-DD string to datetime."""
        return datetime.strptime(date_str, DateUtils.DATE_FORMAT)

    @staticmethod
    def get_today() -> str:
        """Get today's local-calendar date as YYYY-MM-DD.

        Does not apply Marvin's profile.rollover hour — see module docstring.
        """
        return DateUtils.format_date(datetime.now())

    @staticmethod
    def get_yesterday() -> str:
        """Get yesterday's local-calendar date as YYYY-MM-DD.

        Does not apply Marvin's profile.rollover hour — see module docstring.
        """
        yesterday = datetime.now() - timedelta(days=1)
        return DateUtils.format_date(yesterday)

    @staticmethod
    def generate_date_range(
        days: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> tuple[list[str], datetime, datetime]:
        """Generate a list of dates and start/end datetime objects based on inputs.

        Args:
            days: Number of days to look back from today
            start_date: Start date in YYYY-MM-DD format (overrides days parameter)
            end_date: End date in YYYY-MM-DD format (defaults to today if start_date provided)

        Returns:
            Tuple of (date_list, start_datetime, end_datetime)
        """
        if start_date:
            # Use explicit date range
            start = DateUtils.parse_date(start_date)
            end = DateUtils.parse_date(end_date) if end_date else datetime.now()

            # Generate list of dates in range
            date_list = []
            current = start
            while current <= end:
                date_list.append(DateUtils.format_date(current))
                current += timedelta(days=1)
        else:
            # Use days parameter (default behavior)
            if days is None:
                days = 7
            today = datetime.now()
            date_list = []
            for i in range(days):
                date = today - timedelta(days=i)
                date_list.append(DateUtils.format_date(date))
            start = today - timedelta(days=days - 1)
            end = today

        return date_list, start, end
