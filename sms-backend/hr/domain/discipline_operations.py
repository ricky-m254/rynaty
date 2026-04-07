from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from ..models import DisciplinaryCase
from .date_utils import coerce_date_value, current_local_date
from .exit_operations import route_dismissal_to_exit_case
from .lifecycle_events import (
    append_disciplinary_case_closed_event,
    append_disciplinary_case_opened_event,
    build_employee_state_snapshot,
)


class DisciplineWorkflowError(Exception):
    pass


def generate_disciplinary_case_number() -> str:
    year = timezone.now().year
    prefix = f"DISC-{year}-"
    last = (
        DisciplinaryCase.objects.filter(case_number__startswith=prefix)
        .order_by("-case_number")
        .values_list("case_number", flat=True)
        .first()
    )
    if not last:
        sequence = 1
    else:
        try:
            sequence = int(last.split("-")[-1]) + 1
        except (TypeError, ValueError, IndexError):
            sequence = DisciplinaryCase.objects.count() + 1
    return f"{prefix}{sequence:04d}"


@transaction.atomic
def create_disciplinary_case(*, recorded_by=None, **validated_fields) -> DisciplinaryCase:
    validated_fields = dict(validated_fields)
    validated_fields.setdefault("case_number", generate_disciplinary_case_number())
    if "opened_on" in validated_fields:
        opened_on = coerce_date_value(validated_fields["opened_on"])
        if opened_on is None:
            raise DisciplineWorkflowError("opened_on must be a valid date.")
        validated_fields["opened_on"] = opened_on
    else:
        validated_fields["opened_on"] = current_local_date()
    if "incident_date" in validated_fields:
        incident_date = coerce_date_value(validated_fields["incident_date"])
        if incident_date is None:
            raise DisciplineWorkflowError("incident_date must be a valid date.")
        validated_fields["incident_date"] = incident_date
    disciplinary_case = DisciplinaryCase.objects.create(opened_by=recorded_by, **validated_fields)
    append_disciplinary_case_opened_event(disciplinary_case, recorded_by=recorded_by)
    return disciplinary_case


@transaction.atomic
def close_disciplinary_case(
    disciplinary_case: DisciplinaryCase,
    *,
    outcome: str,
    recorded_by=None,
    effective_date=None,
    notes: str = "",
) -> DisciplinaryCase:
    if disciplinary_case.status == "CLOSED":
        raise DisciplineWorkflowError("Disciplinary case is already closed.")

    if disciplinary_case.status == "CANCELLED":
        raise DisciplineWorkflowError("Cancelled disciplinary case cannot be closed.")

    employee = disciplinary_case.employee
    before_snapshot = build_employee_state_snapshot(employee)

    employee_update_fields: list[str] = []
    if outcome == "SUSPENSION" and employee.status != "Suspended":
        employee.status = "Suspended"
        employee_update_fields.append("status")

    if employee_update_fields:
        employee.save(update_fields=employee_update_fields)

    resolved_effective_date = coerce_date_value(effective_date) if effective_date is not None else None
    if effective_date is not None and resolved_effective_date is None:
        raise DisciplineWorkflowError("effective_date must be a valid date.")
    resolved_effective_date = resolved_effective_date or current_local_date()

    note_parts = [disciplinary_case.notes.strip(), notes.strip()]
    if outcome == "DISMISSAL":
        exit_case = route_dismissal_to_exit_case(
            employee=employee,
            reason=disciplinary_case.summary,
            notes=disciplinary_case.details or notes,
            effective_date=resolved_effective_date,
            recorded_by=recorded_by,
        )
        note_parts.append(f"Dismissal routed to exit case {exit_case.id}.")
    disciplinary_case.notes = "\n\n".join(part for part in note_parts if part)

    disciplinary_case.status = "CLOSED"
    disciplinary_case.outcome = outcome
    disciplinary_case.effective_date = resolved_effective_date
    disciplinary_case.closed_by = recorded_by
    update_fields = ["status", "outcome", "effective_date", "closed_by", "notes"]
    disciplinary_case.save(update_fields=update_fields)

    employee.refresh_from_db()
    append_disciplinary_case_closed_event(
        disciplinary_case,
        recorded_by=recorded_by,
        before_snapshot=before_snapshot,
        after_snapshot=build_employee_state_snapshot(employee),
    )
    return disciplinary_case
