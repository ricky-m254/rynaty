from __future__ import annotations

"""
Compatibility contract helpers for parent and student communication surfaces.

These functions normalize legacy message rows and communication payloads into a
stable API shape so portal UIs do not need to guess between `sent_at` vs
`created_at` or `body` vs `content`.
"""

from collections.abc import Iterable

from django.db.models import Q
from django.utils import timezone

from communication.models import Announcement, Notification
from school.models import Message


def active_announcements_queryset():
    now = timezone.now()
    return (
        Announcement.objects.filter(is_active=True, publish_at__lte=now)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .order_by("-publish_at", "-id")
    )


def _raw_filter_values(filters: dict, *keys: str) -> list:
    values = []
    for key in keys:
        raw = filters.get(key)
        if raw in (None, "", []):
            continue
        if isinstance(raw, (list, tuple, set)):
            values.extend(list(raw))
        else:
            values.append(raw)
    return values


def _int_set(values: Iterable) -> set[int]:
    result: set[int] = set()
    for value in values:
        try:
            result.add(int(value))
        except (TypeError, ValueError):
            continue
    return result


def _text_set(values: Iterable) -> set[str]:
    result: set[str] = set()
    for value in values:
        text = str(value or "").strip().casefold()
        if text:
            result.add(text)
    return result


def _matches_int_filters(filters: dict, keys: tuple[str, ...], candidates: set[int]) -> bool:
    if not candidates:
        return False
    return bool(_int_set(_raw_filter_values(filters, *keys)) & candidates)


def _matches_text_filters(filters: dict, keys: tuple[str, ...], candidates: set[str]) -> bool:
    if not candidates:
        return False
    return bool(_text_set(_raw_filter_values(filters, *keys)) & candidates)


def _announcement_visible_for_audience(
    announcement: Announcement,
    *,
    audience: str,
    user_id: int | None,
    student_ids: set[int],
    admission_numbers: set[str],
    class_ids: set[int],
    class_names: set[str],
) -> bool:
    audience_type = str(getattr(announcement, "audience_type", "") or "All").strip()
    if audience_type == "All":
        return True
    if audience_type == audience:
        return True
    if audience_type in {"Staff", "Department"}:
        return False

    filters = getattr(announcement, "audience_filter", None) or {}
    if audience_type == "Class":
        return _matches_int_filters(
            filters,
            ("class_id", "class_ids", "school_class_id", "school_class_ids"),
            class_ids,
        ) or _matches_text_filters(
            filters,
            ("class_name", "class_names", "class_section", "class_sections"),
            class_names,
        )

    if audience_type == "Custom":
        user_candidates = {user_id} if user_id is not None else set()
        return any(
            (
                _matches_int_filters(
                    filters,
                    ("user_id", "user_ids", "recipient_user_id", "recipient_user_ids"),
                    user_candidates,
                ),
                _matches_int_filters(filters, ("parent_user_id", "parent_user_ids"), user_candidates),
                _matches_int_filters(filters, ("student_id", "student_ids"), student_ids),
                _matches_text_filters(filters, ("admission_number", "admission_numbers"), admission_numbers),
                _matches_int_filters(
                    filters,
                    ("class_id", "class_ids", "school_class_id", "school_class_ids"),
                    class_ids,
                ),
                _matches_text_filters(
                    filters,
                    ("class_name", "class_names", "class_section", "class_sections"),
                    class_names,
                ),
            )
        )

    return False


def announcement_visible_for_parent(
    announcement: Announcement,
    *,
    user_id: int | None,
    student_ids: set[int],
    admission_numbers: set[str],
    class_ids: set[int],
    class_names: set[str],
) -> bool:
    return _announcement_visible_for_audience(
        announcement,
        audience="Parents",
        user_id=user_id,
        student_ids=student_ids,
        admission_numbers=admission_numbers,
        class_ids=class_ids,
        class_names=class_names,
    )


def announcement_visible_for_student(
    announcement: Announcement,
    *,
    user_id: int | None,
    student_ids: set[int],
    admission_numbers: set[str],
    class_ids: set[int],
    class_names: set[str],
) -> bool:
    return _announcement_visible_for_audience(
        announcement,
        audience="Students",
        user_id=user_id,
        student_ids=student_ids,
        admission_numbers=admission_numbers,
        class_ids=class_ids,
        class_names=class_names,
    )


def serialize_parent_legacy_message(row: Message) -> dict:
    created_at = row.sent_at
    return {
        "id": row.id,
        "subject": row.subject,
        "body": row.body,
        "content": row.body,
        "sent_at": row.sent_at,
        "created_at": created_at,
        "status": row.status,
    }


def serialize_parent_announcement(row: Announcement) -> dict:
    created_at = row.publish_at
    return {
        "id": row.id,
        "title": row.title,
        "body": row.body,
        "content": row.body,
        "priority": row.priority,
        "audience_type": row.audience_type,
        "is_pinned": row.is_pinned,
        "publish_at": row.publish_at,
        "created_at": created_at,
    }


def serialize_parent_notification(row: Notification) -> dict:
    created_at = row.sent_at
    return {
        "id": row.id,
        "notification_type": row.notification_type,
        "title": row.title,
        "message": row.message,
        "body": row.message,
        "is_read": row.is_read,
        "sent_at": row.sent_at,
        "created_at": created_at,
    }
