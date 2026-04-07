from __future__ import annotations

from datetime import date, datetime
from typing import Any

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime


def current_local_date() -> date:
    return timezone.now().date()


def coerce_date_value(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        parsed_datetime = parse_datetime(normalized)
        if parsed_datetime is not None:
            return parsed_datetime.date()
        parsed_date = parse_date(normalized)
        if parsed_date is not None:
            return parsed_date
    return None


def serialize_temporal_value(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    coerced_date = coerce_date_value(value)
    if coerced_date is not None:
        return coerced_date.isoformat()
    return str(value)
