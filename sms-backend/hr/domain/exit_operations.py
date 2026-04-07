from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from school.models import UserModuleAssignment

from ..models import ExitCase, ExitClearanceItem, StaffLifecycleEvent
from .date_utils import coerce_date_value, current_local_date
from .lifecycle_events import (
    append_archived_event,
    append_clearance_completed_event,
    append_exit_case_created_event,
    append_exit_completed_event,
    build_employee_state_snapshot,
    build_exit_case_snapshot,
)


class ExitWorkflowError(Exception):
    pass


EXIT_REASON_TO_TYPE = {
    "RESIGNATION": "RESIGNATION",
    "RETIREMENT": "RETIREMENT",
    "CONTRACT END": "CONTRACT_END",
    "CONTRACT_END": "CONTRACT_END",
    "TERMINATION": "DISMISSAL",
    "DISMISSAL": "DISMISSAL",
}

EXIT_TYPE_TO_EMPLOYEE_STATE = {
    "RESIGNATION": ("Terminated", "Resignation"),
    "RETIREMENT": ("Retired", "Retirement"),
    "DISMISSAL": ("Terminated", "Termination"),
    "CONTRACT_END": ("Terminated", "Contract End"),
}


def map_legacy_exit_reason_to_type(reason: str | None) -> str:
    normalized = str(reason or "Resignation").strip().replace("-", " ").replace("_", " ").upper()
    return EXIT_REASON_TO_TYPE.get(normalized, "RESIGNATION")


def _get_active_exit_case(employee_id: int) -> ExitCase | None:
    return (
        ExitCase.objects.filter(employee_id=employee_id, status__in=["DRAFT", "CLEARANCE"])
        .order_by("-created_at", "-id")
        .first()
    )


def _clearance_ready(exit_case: ExitCase) -> bool:
    items = list(exit_case.clearance_items.all())
    if not items:
        return False
    return all(item.status in {"CLEARED", "WAIVED"} for item in items)


def _append_clearance_event_if_ready(exit_case: ExitCase, *, recorded_by=None) -> None:
    if not _clearance_ready(exit_case):
        return
    if StaffLifecycleEvent.objects.filter(
        source_model="hr.ExitCase",
        source_id=exit_case.id,
        event_type="CLEARANCE_COMPLETED",
    ).exists():
        return
    append_clearance_completed_event(
        exit_case,
        recorded_by=recorded_by,
        before_snapshot=build_exit_case_snapshot(exit_case),
        after_snapshot=build_exit_case_snapshot(exit_case),
    )


@transaction.atomic
def create_exit_case(*, recorded_by=None, **validated_fields) -> ExitCase:
    validated_fields = dict(validated_fields)
    employee = validated_fields["employee"]
    if employee.status == "Archived":
        raise ExitWorkflowError("Archived employee cannot receive a new exit case.")

    active_case = _get_active_exit_case(employee.id)
    if active_case is not None:
        raise ExitWorkflowError("Employee already has an active exit case.")

    for field_name in ("notice_date", "last_working_date", "effective_date"):
        if field_name not in validated_fields:
            continue
        coerced_value = coerce_date_value(validated_fields[field_name])
        if validated_fields[field_name] not in (None, "") and coerced_value is None:
            raise ExitWorkflowError(f"{field_name} must be a valid date.")
        validated_fields[field_name] = coerced_value

    exit_case = ExitCase.objects.create(requested_by=recorded_by, **validated_fields)
    append_exit_case_created_event(exit_case, recorded_by=recorded_by)
    return exit_case


@transaction.atomic
def start_exit_clearance(exit_case: ExitCase, *, recorded_by=None) -> ExitCase:
    if exit_case.status == "COMPLETED":
        raise ExitWorkflowError("Completed exit case cannot restart clearance.")
    if exit_case.status == "CANCELLED":
        raise ExitWorkflowError("Cancelled exit case cannot start clearance.")
    if exit_case.status == "ARCHIVED":
        raise ExitWorkflowError("Archived exit case cannot start clearance.")
    if exit_case.status == "CLEARANCE":
        return exit_case

    exit_case.status = "CLEARANCE"
    exit_case.save(update_fields=["status"])
    return exit_case


@transaction.atomic
def sync_exit_clearance_item_completion_fields(
    item: ExitClearanceItem,
    *,
    recorded_by=None,
) -> ExitClearanceItem:
    update_fields: list[str] = []
    if item.status in {"CLEARED", "WAIVED"}:
        if item.completed_at is None:
            item.completed_at = timezone.now()
            update_fields.append("completed_at")
        if item.completed_by_id != (recorded_by.id if recorded_by else None):
            item.completed_by = recorded_by
            update_fields.append("completed_by")
    else:
        if item.completed_at is not None:
            item.completed_at = None
            update_fields.append("completed_at")
        if item.completed_by_id is not None:
            item.completed_by = None
            update_fields.append("completed_by")

    if update_fields:
        item.save(update_fields=update_fields)
    return item


@transaction.atomic
def complete_exit_case(exit_case: ExitCase, *, recorded_by=None) -> ExitCase:
    if exit_case.status == "COMPLETED":
        raise ExitWorkflowError("Exit case is already completed.")
    if exit_case.status == "CANCELLED":
        raise ExitWorkflowError("Cancelled exit case cannot be completed.")
    if exit_case.status == "ARCHIVED":
        raise ExitWorkflowError("Archived exit case cannot be completed.")
    if exit_case.status != "CLEARANCE":
        raise ExitWorkflowError("Start clearance before completing the exit case.")

    items = list(exit_case.clearance_items.all())
    if not items:
        raise ExitWorkflowError("At least one clearance item is required before exit completion.")
    if any(item.status == "PENDING" for item in items):
        raise ExitWorkflowError("All clearance items must be cleared or waived before exit completion.")

    _append_clearance_event_if_ready(exit_case, recorded_by=recorded_by)

    employee = exit_case.employee
    before_snapshot = build_employee_state_snapshot(employee)
    employee_status, employee_reason = EXIT_TYPE_TO_EMPLOYEE_STATE[exit_case.exit_type]
    effective_date = exit_case.effective_date or exit_case.last_working_date or current_local_date()

    employee.status = employee_status
    employee.exit_date = effective_date
    employee.exit_reason = employee_reason
    employee.exit_notes = exit_case.notes or exit_case.reason or ""
    employee.save(update_fields=["status", "exit_date", "exit_reason", "exit_notes"])

    exit_case.status = "COMPLETED"
    exit_case.completed_by = recorded_by
    if exit_case.effective_date is None:
        exit_case.effective_date = effective_date
        exit_case.save(update_fields=["status", "completed_by", "effective_date"])
    else:
        exit_case.save(update_fields=["status", "completed_by"])

    employee.refresh_from_db()
    exit_case.refresh_from_db()
    append_exit_completed_event(
        exit_case,
        recorded_by=recorded_by,
        before_snapshot=before_snapshot,
        after_snapshot=build_employee_state_snapshot(employee),
    )
    return exit_case


@transaction.atomic
def create_compatibility_exit_case(
    employee,
    *,
    exit_date=None,
    exit_reason: str | None = None,
    exit_notes: str = "",
    recorded_by=None,
) -> ExitCase:
    resolved_exit_date = coerce_date_value(exit_date) if exit_date is not None else None
    if exit_date is not None and resolved_exit_date is None:
        raise ExitWorkflowError("exit_date must be a valid date.")
    effective_date = resolved_exit_date or current_local_date()
    exit_case = create_exit_case(
        recorded_by=recorded_by,
        employee=employee,
        exit_type=map_legacy_exit_reason_to_type(exit_reason),
        last_working_date=effective_date,
        effective_date=effective_date,
        reason=exit_reason or "Resignation",
        notes=exit_notes or "",
    )
    ExitClearanceItem.objects.create(
        exit_case=exit_case,
        label="Legacy exit bridge waiver",
        department_name="HR",
        status="WAIVED",
        completed_at=timezone.now(),
        completed_by=recorded_by,
        notes="Auto-created by Employee.exit compatibility bridge.",
        display_order=0,
    )
    start_exit_clearance(exit_case, recorded_by=recorded_by)
    return complete_exit_case(exit_case, recorded_by=recorded_by)


@transaction.atomic
def route_dismissal_to_exit_case(
    *,
    employee,
    reason: str,
    notes: str = "",
    effective_date=None,
    recorded_by=None,
) -> ExitCase:
    active_case = _get_active_exit_case(employee.id)
    if active_case is not None:
        return active_case

    resolved_effective_date = coerce_date_value(effective_date) if effective_date is not None else None
    if effective_date is not None and resolved_effective_date is None:
        raise ExitWorkflowError("effective_date must be a valid date.")
    effective = resolved_effective_date or current_local_date()
    exit_case = create_exit_case(
        recorded_by=recorded_by,
        employee=employee,
        exit_type="DISMISSAL",
        last_working_date=effective,
        effective_date=effective,
        reason=reason,
        notes=notes,
    )
    ExitClearanceItem.objects.create(
        exit_case=exit_case,
        label="Dismissal clearance",
        department_name="HR",
        status="PENDING",
        notes="Created automatically from disciplinary dismissal outcome.",
        display_order=0,
    )
    return start_exit_clearance(exit_case, recorded_by=recorded_by)


@transaction.atomic
def archive_employee(
    employee,
    *,
    archive_reason: str = "",
    recorded_by=None,
):
    if employee.status == "Archived":
        raise ExitWorkflowError("Employee is already archived.")

    if ExitCase.objects.filter(employee=employee, status__in=["DRAFT", "CLEARANCE"]).exists():
        raise ExitWorkflowError("Resolve active exit cases before archiving the employee.")

    before_snapshot = build_employee_state_snapshot(employee)
    archived_at = timezone.now()

    employee.status = "Archived"
    employee.is_active = False
    employee.archived_at = archived_at
    employee.archived_by = recorded_by
    employee.archive_reason = archive_reason or employee.archive_reason or ""
    employee.save(update_fields=["status", "is_active", "archived_at", "archived_by", "archive_reason"])

    archived_exit_case_ids = list(
        ExitCase.objects.filter(employee=employee, status="COMPLETED").values_list("id", flat=True)
    )
    if archived_exit_case_ids:
        ExitCase.objects.filter(id__in=archived_exit_case_ids).update(status="ARCHIVED")

    locked_user_id = None
    deactivated_module_assignment_count = 0
    if employee.user_id:
        locked_user_id = employee.user_id
        user = employee.user
        if user.is_active:
            user.is_active = False
            user.save(update_fields=["is_active"])
        deactivated_module_assignment_count = UserModuleAssignment.objects.filter(
            user_id=user.id,
            is_active=True,
        ).update(is_active=False)

    employee.refresh_from_db()
    append_archived_event(
        employee,
        recorded_by=recorded_by,
        before_snapshot=before_snapshot,
        after_snapshot=build_employee_state_snapshot(employee),
        metadata={
            "archive_reason": employee.archive_reason,
            "locked_user_id": locked_user_id,
            "deactivated_module_assignment_count": deactivated_module_assignment_count,
            "archived_exit_case_ids": archived_exit_case_ids,
        },
    )
    return employee
