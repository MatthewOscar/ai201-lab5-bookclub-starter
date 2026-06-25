"""
services/stats_service.py — BookClub

Computes reading statistics for a user: streak, books finished this month,
and total pages read.
"""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from services import reading_service


def _get_timezone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        raise ValueError(f"Unknown timezone: {timezone_name}") from None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _local_date(value: datetime, local_timezone: ZoneInfo) -> date:
    return _as_utc(value).astimezone(local_timezone).date()


def _count_streak(dates: set[date], today: date) -> int:
    if not dates:
        return 0

    sorted_dates = sorted(dates, reverse=True)

    # Streak must start from today or yesterday — otherwise it has already broken.
    if (today - sorted_dates[0]).days > 1:
        return 0

    streak = 1
    for i in range(len(sorted_dates) - 1):
        delta = (sorted_dates[i] - sorted_dates[i + 1]).days
        if delta == 1:
            streak += 1
        else:
            break

    return streak


def calculate_streak(
    user_id: str, timezone_name: str = "UTC", now: datetime | None = None
) -> int:
    """
    Calculate a user's current reading streak in consecutive days.

    A streak is the number of consecutive calendar days on which the user
    finished at least one book, counting back from today (or yesterday, if
    nothing has been finished today yet).

    Returns 0 if the user has no reading history or if there is a gap of
    more than one day since their most recent finished book.

    Args:
        user_id: ID of the user.
        timezone_name: IANA timezone name used to decide local reading dates.
        now: Current timestamp override for tests.

    Returns:
        The streak count as an integer.
    """
    local_timezone = _get_timezone(timezone_name)
    events = reading_service.get_reading_history(user_id)

    # Collect unique reading dates, most recent first.
    dates = {_local_date(e.finished_at, local_timezone) for e in events}

    current_time = now or datetime.now(timezone.utc)
    today = _local_date(current_time, local_timezone)

    return _count_streak(dates, today)


def books_this_month(user_id: str) -> int:
    """
    Count the number of books the user finished in the current calendar month.

    Args:
        user_id: ID of the user.

    Returns:
        Count of books finished this month.
    """
    events = reading_service.get_reading_history(user_id)
    today = date.today()
    return sum(
        1
        for e in events
        if e.finished_at.year == today.year and e.finished_at.month == today.month
    )


def total_pages_read(user_id: str) -> int:
    """
    Sum the page counts of all books the user has finished.

    Args:
        user_id: ID of the user.

    Returns:
        Total pages read as an integer.
    """
    events = reading_service.get_reading_history(user_id)
    return sum(e.book.pages for e in events)
