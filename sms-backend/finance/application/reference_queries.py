from __future__ import annotations

from dataclasses import dataclass

from academics.models import SchoolClass
from school.models import Enrollment, Student


DEFAULT_LIMIT = 50
MAX_LIMIT = 200


@dataclass(frozen=True)
class QueryPage:
    count: int
    next_offset: int | None
    results: list[object]


def _resolve_ordering(requested: str | None, *, allowed: set[str], default: str, direction: str | None) -> str:
    field = requested if requested in allowed else default
    if direction == "desc":
        return f"-{field}"
    return field


def get_student_reference_queryset(
    *,
    is_active: str | None,
    class_id: str | None,
    term_id: str | None,
    order_by: str | None,
    order_dir: str | None,
):
    ordering = _resolve_ordering(
        order_by,
        allowed={"id", "admission_number", "first_name", "last_name"},
        default="admission_number",
        direction=order_dir,
    )

    queryset = Student.objects.all()
    if is_active is None or is_active.lower() == "true":
        queryset = queryset.filter(is_active=True)
    elif is_active.lower() == "false":
        queryset = queryset.filter(is_active=False)

    if class_id or term_id:
        enrollments = Enrollment.objects.filter(is_active=True)
        if class_id:
            enrollments = enrollments.filter(school_class_id=class_id)
        if term_id:
            enrollments = enrollments.filter(term_id=term_id)
        queryset = queryset.filter(id__in=enrollments.values_list("student_id", flat=True))

    return queryset.order_by(ordering)


def get_enrollment_reference_queryset(
    *,
    is_active: str | None,
    class_id: str | None,
    term_id: str | None,
    student_id: str | None,
    order_by: str | None,
    order_dir: str | None,
):
    ordering = _resolve_ordering(
        order_by,
        allowed={"id", "student_id", "school_class_id", "term_id"},
        default="id",
        direction=order_dir,
    )

    queryset = Enrollment.objects.all()
    if is_active is None or is_active.lower() == "true":
        queryset = queryset.filter(is_active=True)
    elif is_active.lower() == "false":
        queryset = queryset.filter(is_active=False)

    if class_id:
        queryset = queryset.filter(school_class_id=class_id)
    if term_id:
        queryset = queryset.filter(term_id=term_id)
    if student_id:
        queryset = queryset.filter(student_id=student_id)

    return queryset.order_by(ordering)


def paginate_queryset(queryset, *, limit: str | None, offset: str | None) -> QueryPage | None:
    if limit is None and offset is None:
        return None

    try:
        limit_value = int(limit) if limit is not None else DEFAULT_LIMIT
        offset_value = int(offset) if offset is not None else 0
    except ValueError as exc:
        raise ValueError("limit and offset must be integers") from exc

    limit_value = min(limit_value, MAX_LIMIT)
    total = queryset.count()
    page = list(queryset[offset_value:offset_value + limit_value])
    next_offset = offset_value + limit_value
    if next_offset >= total:
        next_offset = None

    return QueryPage(count=total, next_offset=next_offset, results=page)


def list_class_references(*, term_id: str | None) -> list[dict[str, object]]:
    queryset = SchoolClass.objects.filter(is_active=True).order_by("name")
    rows: list[dict[str, object]] = []

    for school_class in queryset:
        enrollment_queryset = Enrollment.objects.filter(
            school_class_id=school_class.id,
            is_active=True,
        )
        if term_id:
            enrollment_queryset = enrollment_queryset.filter(term_id=term_id)

        rows.append(
            {
                "id": school_class.id,
                "name": school_class.display_name,
                "stream": school_class.stream,
                "student_count": enrollment_queryset.count(),
            }
        )

    return rows
