"""UTC intervals are half-open internally; checkpoints split on milliseconds."""
from datetime import datetime, time, timedelta, timezone

import pytz


TICK = timedelta(milliseconds=1)
CAIRO = pytz.timezone('Africa/Cairo')


def day_bounds(day):
    # Localize each midnight separately: a Cairo DST day is not always 24 hours.
    return tuple(CAIRO.localize(datetime.combine(value, time.min)).astimezone(timezone.utc)
                 for value in (day, day + timedelta(days=1)))


def retrieval_cutoff(delay_hours=12, now=None):
    now = now or datetime.now(timezone.utc)
    midnight, _end = day_bounds(now.astimezone(CAIRO).date())
    cutoff = min(midnight, now - timedelta(hours=delay_hours))
    return cutoff.replace(microsecond=cutoff.microsecond // 1000 * 1000)


def api_stamp(value):
    return value.isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def api_inclusive_end(last_millisecond):
    # ETA timestamps can contain seven fractional digits (.NET DateTime ticks).
    # Include the whole last millisecond, while excluding the next boundary.
    previous = last_millisecond + TICK - timedelta(microseconds=1)
    return previous.strftime('%Y-%m-%dT%H:%M:%S.%f') + '9Z'


def split_interval(start, end):
    """Split inclusive millisecond API bounds, without gaps or overlap."""
    if end - start < TICK:
        raise ValueError('ETA result limit reached within one millisecond')
    midpoint = start + (end - start) / 2
    midpoint = midpoint.replace(microsecond=midpoint.microsecond // 1000 * 1000)
    return (start, midpoint), (midpoint + TICK, end)
