import datetime
import math
from email.utils import parsedate_to_datetime


class ReportDeliveryError(ValueError):
    """Transport failure with retry policy independent of its displayed text."""

    def __init__(self, message, *, retryable=False, retry_after=None, status=None, code=None):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after
        self.status = status
        self.code = code


def parse_retry_after(value):
    if not value:
        return None
    try:
        if value.strip().isdigit():
            seconds = int(value.strip())
        else:
            when = parsedate_to_datetime(value)
            if when.tzinfo is None:
                when = when.replace(tzinfo=datetime.timezone.utc)
            seconds = math.ceil(
                (when - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
            )
        # Odoo represents ETA with a datetime/timedelta, so reject overflow.
        datetime.datetime.now() + datetime.timedelta(seconds=seconds)
        return max(0, seconds)
    except (ValueError, TypeError, OverflowError):
        return None
