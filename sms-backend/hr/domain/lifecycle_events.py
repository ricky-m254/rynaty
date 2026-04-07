from __future__ import annotations

from typing import Any

from django.utils import timezone

from ..models import (
    DisciplinaryCase,
    Employee,
    EmployeeEmploymentProfile,
    ExitCase,
    ExitClearanceItem,
    StaffCareerAction,
    StaffLifecycleEvent,
    StaffTransfer,
)
from .date_utils import current_local_date, serialize_temporal_value


def _serialize_user(user) -> dict[str, Any] | None:
    if not user:
        return None
    return {
        "id": user.id,
        "username": getattr(user, "username", ""),
    }


def build_employee_state_snapshot(employee: Employee) -> dict[str, Any]:
    profile = EmployeeEmploymentProfile.objects.filter(employee_id=employee.id).first()
    return {
        "employee_id": employee.id,
        "employee_code": employee.employee_id,
        "full_name": " ".join(
            part for part in [employee.first_name, employee.middle_name, employee.last_name] if part
        ).strip(),
        "status": employee.status,
        "is_active": employee.is_active,
        "department": {
            "id": employee.department_id,
            "name": employee.department.name if employee.department else "",
        },
        "position": {
            "id": employee.position_id,
            "title": employee.position.title if employee.position else "",
        },
        "employment_type": employee.employment_type,
        "staff_category": employee.staff_category,
        "work_location": employee.work_location,
        "employment_profile": {
            "position_grade": profile.position_grade if profile else "",
            "salary_scale": profile.salary_scale if profile else "",
        },
        "exit_date": serialize_temporal_value(employee.exit_date),
        "exit_reason": employee.exit_reason or "",
        "exit_notes": employee.exit_notes or "",
        "archived_at": serialize_temporal_value(employee.archived_at),
        "archive_reason": employee.archive_reason or "",
        "archived_by": _serialize_user(employee.archived_by),
    }


def build_transfer_target_snapshot(transfer: StaffTransfer) -> dict[str, Any]:
    target_position = transfer.to_position_ref.title if transfer.to_position_ref else transfer.to_position
    return {
        "transfer_id": transfer.id,
        "transfer_type": transfer.transfer_type,
        "status": transfer.status,
        "effective_date": serialize_temporal_value(transfer.effective_date),
        "from_department": {
            "id": transfer.from_department_id,
            "name": transfer.from_department.name if transfer.from_department else "",
        },
        "from_position": transfer.from_position,
        "to_department": {
            "id": transfer.to_department_id,
            "name": transfer.to_department.name if transfer.to_department else "",
        },
        "to_position": {
            "id": transfer.to_position_ref_id,
            "title": target_position or "",
        },
        "destination_school": transfer.destination_school,
        "handover_completed": transfer.handover_completed,
        "clearance_completed": transfer.clearance_completed,
    }


def build_career_action_snapshot(action: StaffCareerAction) -> dict[str, Any]:
    return {
        "career_action_id": action.id,
        "parent_action_id": action.parent_action_id,
        "action_type": action.action_type,
        "status": action.status,
        "effective_date": serialize_temporal_value(action.effective_date),
        "from_department": {
            "id": action.from_department_id,
            "name": action.from_department.name if action.from_department else "",
        },
        "from_position": {
            "id": action.from_position_ref_id,
            "title": action.from_position_title or (action.from_position_ref.title if action.from_position_ref else ""),
        },
        "to_department": {
            "id": action.to_department_id,
            "name": action.to_department.name if action.to_department else "",
        },
        "to_position": {
            "id": action.to_position_ref_id,
            "title": action.to_position_title or (action.to_position_ref.title if action.to_position_ref else ""),
        },
        "target_position_grade": action.target_position_grade or "",
        "target_salary_scale": action.target_salary_scale or "",
        "reason": action.reason or "",
        "notes": action.notes or "",
        "previous_assignment_snapshot": action.previous_assignment_snapshot or {},
    }


def build_disciplinary_case_snapshot(case: DisciplinaryCase) -> dict[str, Any]:
    return {
        "disciplinary_case_id": case.id,
        "case_number": case.case_number,
        "category": case.category,
        "opened_on": serialize_temporal_value(case.opened_on),
        "incident_date": serialize_temporal_value(case.incident_date),
        "summary": case.summary,
        "status": case.status,
        "outcome": case.outcome or "",
        "effective_date": serialize_temporal_value(case.effective_date),
        "details": case.details or "",
        "notes": case.notes or "",
        "opened_by": _serialize_user(case.opened_by),
        "closed_by": _serialize_user(case.closed_by),
    }


def build_exit_clearance_item_snapshot(item: ExitClearanceItem) -> dict[str, Any]:
    return {
        "exit_clearance_item_id": item.id,
        "label": item.label,
        "department_name": item.department_name or "",
        "status": item.status,
        "completed_at": serialize_temporal_value(item.completed_at),
        "completed_by": _serialize_user(item.completed_by),
        "notes": item.notes or "",
        "display_order": item.display_order,
    }


def build_exit_case_snapshot(exit_case: ExitCase) -> dict[str, Any]:
    items = [
        build_exit_clearance_item_snapshot(item)
        for item in exit_case.clearance_items.select_related("completed_by").order_by("display_order", "id")
    ]
    return {
        "exit_case_id": exit_case.id,
        "exit_type": exit_case.exit_type,
        "notice_date": serialize_temporal_value(exit_case.notice_date),
        "last_working_date": serialize_temporal_value(exit_case.last_working_date),
        "effective_date": serialize_temporal_value(exit_case.effective_date),
        "reason": exit_case.reason or "",
        "status": exit_case.status,
        "notes": exit_case.notes or "",
        "requested_by": _serialize_user(exit_case.requested_by),
        "completed_by": _serialize_user(exit_case.completed_by),
        "clearance_items": items,
    }


def append_lifecycle_event(
    *,
    employee: Employee,
    event_group: str,
    event_type: str,
    title: str,
    summary: str = "",
    recorded_by=None,
    source_object=None,
    before_snapshot: dict[str, Any] | None = None,
    after_snapshot: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    effective_date=None,
    occurred_at=None,
    status_snapshot: str | None = None,
) -> StaffLifecycleEvent:
    source_model = ""
    source_id = None
    if source_object is not None:
        source_model = source_object._meta.label
        source_id = source_object.pk

    return StaffLifecycleEvent.objects.create(
        employee=employee,
        event_group=event_group,
        event_type=event_type,
        title=title,
        summary=summary,
        status_snapshot=status_snapshot or employee.status,
        effective_date=effective_date,
        occurred_at=occurred_at or timezone.now(),
        recorded_by=recorded_by,
        source_model=source_model,
        source_id=source_id,
        before_snapshot=before_snapshot or {},
        after_snapshot=after_snapshot or {},
        metadata=metadata or {},
    )


def append_transfer_requested_event(transfer: StaffTransfer, *, recorded_by=None) -> StaffLifecycleEvent:
    requested_target = build_transfer_target_snapshot(transfer)
    target_department_name = requested_target["to_department"]["name"] or "Unassigned department"
    target_position_name = requested_target["to_position"]["title"] or "current position"
    summary = (
        f"{transfer.transfer_type} transfer requested to {target_department_name}"
        f" as {target_position_name}."
    )
    return append_lifecycle_event(
        employee=transfer.employee,
        event_group="TRANSFER",
        event_type="TRANSFER_REQUESTED",
        title="Transfer requested",
        summary=summary,
        recorded_by=recorded_by,
        source_object=transfer,
        before_snapshot=build_employee_state_snapshot(transfer.employee),
        after_snapshot=requested_target,
        metadata={
            "reason": transfer.reason,
            "notes": transfer.notes,
        },
        effective_date=transfer.effective_date,
        status_snapshot=transfer.employee.status,
    )


def append_disciplinary_case_opened_event(case: DisciplinaryCase, *, recorded_by=None) -> StaffLifecycleEvent:
    summary = f"Disciplinary case {case.case_number} opened under {case.category}."
    return append_lifecycle_event(
        employee=case.employee,
        event_group="DISCIPLINE",
        event_type="DISCIPLINARY_CASE_OPENED",
        title="Disciplinary case opened",
        summary=summary,
        recorded_by=recorded_by,
        source_object=case,
        before_snapshot=build_employee_state_snapshot(case.employee),
        after_snapshot=build_disciplinary_case_snapshot(case),
        metadata={
            "case": build_disciplinary_case_snapshot(case),
        },
        effective_date=case.opened_on,
        status_snapshot=case.employee.status,
    )


def append_exit_case_created_event(exit_case: ExitCase, *, recorded_by=None) -> StaffLifecycleEvent:
    summary = f"{exit_case.get_exit_type_display()} exit case created."
    return append_lifecycle_event(
        employee=exit_case.employee,
        event_group="EXIT",
        event_type="EXIT_CASE_CREATED",
        title="Exit case created",
        summary=summary,
        recorded_by=recorded_by,
        source_object=exit_case,
        before_snapshot=build_employee_state_snapshot(exit_case.employee),
        after_snapshot=build_exit_case_snapshot(exit_case),
        metadata={"exit_case": build_exit_case_snapshot(exit_case)},
        effective_date=exit_case.effective_date or exit_case.last_working_date or exit_case.notice_date,
        status_snapshot=exit_case.employee.status,
    )


def append_career_action_effective_event(
    action: StaffCareerAction,
    *,
    recorded_by=None,
    before_snapshot: dict[str, Any],
    after_snapshot: dict[str, Any],
) -> StaffLifecycleEvent:
    event_map = {
        "PROMOTION": (
            "PROMOTION_EFFECTIVE",
            "Promotion effective",
            f"Promotion effective to {after_snapshot.get('department', {}).get('name') or 'Unassigned department'}"
            f" as {after_snapshot.get('position', {}).get('title') or 'current position'}.",
        ),
        "DEMOTION": (
            "DEMOTION_EFFECTIVE",
            "Demotion effective",
            f"Demotion effective to {after_snapshot.get('department', {}).get('name') or 'Unassigned department'}"
            f" as {after_snapshot.get('position', {}).get('title') or 'current position'}.",
        ),
        "ACTING_APPOINTMENT": (
            "ACTING_APPOINTMENT_STARTED",
            "Acting appointment started",
            f"Acting appointment started in {after_snapshot.get('department', {}).get('name') or 'Unassigned department'}"
            f" as {after_snapshot.get('position', {}).get('title') or 'current position'}.",
        ),
        "ACTING_APPOINTMENT_END": (
            "ACTING_APPOINTMENT_ENDED",
            "Acting appointment ended",
            f"Acting appointment ended and assignment restored to {after_snapshot.get('department', {}).get('name') or 'Unassigned department'}"
            f" as {after_snapshot.get('position', {}).get('title') or 'current position'}.",
        ),
    }
    event_type, title, summary = event_map[action.action_type]
    return append_lifecycle_event(
        employee=action.employee,
        event_group="CAREER",
        event_type=event_type,
        title=title,
        summary=summary,
        recorded_by=recorded_by,
        source_object=action,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        metadata=build_career_action_snapshot(action),
        effective_date=action.effective_date,
        status_snapshot=action.employee.status,
    )


def append_clearance_completed_event(
    exit_case: ExitCase,
    *,
    recorded_by=None,
    before_snapshot: dict[str, Any],
    after_snapshot: dict[str, Any],
) -> StaffLifecycleEvent:
    summary = f"Exit clearance completed for {exit_case.get_exit_type_display().lower()} case."
    return append_lifecycle_event(
        employee=exit_case.employee,
        event_group="CLEARANCE",
        event_type="CLEARANCE_COMPLETED",
        title="Exit clearance completed",
        summary=summary,
        recorded_by=recorded_by,
        source_object=exit_case,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        metadata={"exit_case": build_exit_case_snapshot(exit_case)},
        effective_date=exit_case.effective_date or exit_case.last_working_date or exit_case.notice_date,
        status_snapshot=exit_case.employee.status,
    )


def append_disciplinary_case_closed_event(
    case: DisciplinaryCase,
    *,
    recorded_by=None,
    before_snapshot: dict[str, Any],
    after_snapshot: dict[str, Any],
) -> StaffLifecycleEvent:
    outcome_label = (case.outcome or "Outcome pending").replace("_", " ").title()
    summary = f"Disciplinary case {case.case_number} closed with outcome: {outcome_label}."
    return append_lifecycle_event(
        employee=case.employee,
        event_group="DISCIPLINE",
        event_type="DISCIPLINARY_CASE_CLOSED",
        title="Disciplinary case closed",
        summary=summary,
        recorded_by=recorded_by,
        source_object=case,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        metadata={
            "case": build_disciplinary_case_snapshot(case),
        },
        effective_date=case.effective_date or case.opened_on,
        status_snapshot=case.employee.status,
    )


def append_exit_completed_event(
    exit_case: ExitCase,
    *,
    recorded_by=None,
    before_snapshot: dict[str, Any],
    after_snapshot: dict[str, Any],
) -> StaffLifecycleEvent:
    summary = f"{exit_case.get_exit_type_display()} exit completed."
    return append_lifecycle_event(
        employee=exit_case.employee,
        event_group="EXIT",
        event_type="EXIT_COMPLETED",
        title="Exit completed",
        summary=summary,
        recorded_by=recorded_by,
        source_object=exit_case,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        metadata={"exit_case": build_exit_case_snapshot(exit_case)},
        effective_date=exit_case.effective_date or exit_case.last_working_date or exit_case.notice_date,
        status_snapshot=exit_case.employee.status,
    )


def append_archived_event(
    employee: Employee,
    *,
    recorded_by=None,
    before_snapshot: dict[str, Any],
    after_snapshot: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> StaffLifecycleEvent:
    summary = "Employee archived and operational access locked."
    return append_lifecycle_event(
        employee=employee,
        event_group="ARCHIVE",
        event_type="ARCHIVED",
        title="Employee archived",
        summary=summary,
        recorded_by=recorded_by,
        source_object=employee,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        metadata=metadata or {},
        effective_date=current_local_date(),
        status_snapshot=employee.status,
    )


def append_transfer_completed_event(
    transfer: StaffTransfer,
    *,
    recorded_by=None,
    before_snapshot: dict[str, Any],
    after_snapshot: dict[str, Any],
) -> StaffLifecycleEvent:
    target_department_name = after_snapshot.get("department", {}).get("name") or "Unassigned department"
    target_position_name = after_snapshot.get("position", {}).get("title") or "current position"
    summary = (
        f"{transfer.transfer_type} transfer completed to {target_department_name}"
        f" as {target_position_name}."
    )
    return append_lifecycle_event(
        employee=transfer.employee,
        event_group="TRANSFER",
        event_type="TRANSFER_COMPLETED",
        title="Transfer completed",
        summary=summary,
        recorded_by=recorded_by,
        source_object=transfer,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        metadata=build_transfer_target_snapshot(transfer),
        effective_date=transfer.effective_date,
        status_snapshot=transfer.employee.status,
    )
