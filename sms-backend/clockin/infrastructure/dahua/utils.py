"""
Dahua time and event utilities — extracted from views.py _parse_dahua_time.
"""
from datetime import datetime
from django.utils import timezone


def parse_device_time(time_str: str) -> datetime:
    """Parse Dahua/SmartPSS time strings to tz-aware datetime."""
    if not time_str:
        return timezone.now()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ'):
        try:
            dt = datetime.strptime(time_str.strip(), fmt)
            return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
        except ValueError:
            continue
    return timezone.now()


def normalise_direction(raw_direction) -> str:
    """Convert Dahua Direction field (0/1/string) to 'in'|'out'|'auto'."""
    d = str(raw_direction).lower().strip()
    if d in ('0', 'in', 'entry', 'enter'):
        return 'in'
    if d in ('1', 'out', 'exit'):
        return 'out'
    return 'auto'
