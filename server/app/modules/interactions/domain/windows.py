"""Calendar-month arithmetic for the backfill and retention windows."""

import calendar
from datetime import datetime


def months_before(moment: datetime, months: int) -> datetime:
    """The same time of day `months` calendar months earlier, clamped to the month's end."""
    index = moment.year * 12 + (moment.month - 1) - months
    year, month = divmod(index, 12)
    last_day = calendar.monthrange(year, month + 1)[1]
    return moment.replace(year=year, month=month + 1, day=min(moment.day, last_day))
