"""
Attendance business rules — pure Python, zero framework imports.

Rules owned by this file:
  1. Direction determination (IN/OUT auto-detection)
  2. Late arrival detection
  3. Duplication window check
"""
from datetime import datetime, timedelta, date, time as dtime
from typing import Optional


def determine_event_type(
    direction: str,
    last_event_type: Optional[str],
) -> str:
    """
    Rule: determine whether this scan is a clock-IN or clock-OUT.

    direction values: 'in', 'out', 'auto'
    When 'auto': alternates (IN → OUT → IN …), defaulting to IN on first scan.
    """
    d = direction.lower().strip()
    if d == 'in':
        return 'IN'
    if d == 'out':
        return 'OUT'
    # auto — alternating
    return 'OUT' if last_event_type == 'IN' else 'IN'


def is_late_arrival(
    event_time: datetime,
    expected_arrival: dtime,
    grace_minutes: int,
) -> bool:
    """
    Rule: a clock-IN is late when it occurs after expected_arrival + grace_minutes.
    Both datetimes must be tz-aware or both tz-naive; mixing raises a TypeError.
    """
    event_date = event_time.date()
    deadline = datetime.combine(event_date, expected_arrival) + timedelta(minutes=grace_minutes)

    # Make consistent tz-awareness
    if hasattr(event_time, 'tzinfo') and event_time.tzinfo is not None:
        import datetime as _dt
        if deadline.tzinfo is None:
            import zoneinfo
            # Attach the same tzinfo as event_time by naive comparison
            deadline = deadline.replace(tzinfo=event_time.tzinfo)

    return event_time > deadline


def minutes_late(event_time: datetime, expected_arrival: dtime, grace_minutes: int) -> int:
    """Return how many minutes past the grace deadline the event occurred (0 if not late)."""
    event_date = event_time.date()
    arrival_dt = datetime.combine(event_date, expected_arrival)
    delta = (event_time.replace(tzinfo=None) - arrival_dt).total_seconds() / 60
    return max(0, int(delta) - grace_minutes)


def is_duplicate(
    existing_event_types: list,
    new_event_type: str,
    seconds_window: int = 60,
) -> bool:
    """
    Simple duplication check: if an identical event exists within seconds_window,
    the caller should skip. (Actual timestamp comparison is done in the repository.)
    """
    return False  # Implemented at repository level with DB query
