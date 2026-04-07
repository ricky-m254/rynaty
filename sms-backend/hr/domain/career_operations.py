from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from ..identity import ensure_employment_profile
from ..models import Department, Position, StaffCareerAction, StaffTransfer
from .lifecycle_events import (
    append_career_action_effective_event,
    append_transfer_completed_event,
    build_employee_state_snapshot,
)


class CareerWorkflowError(Exception):
    pass


TRANSFER_TERMINAL_STATUSES = {"Completed", "Rejected", "Cancelled"}
TERMINAL_EMPLOYEE_STATUSES = {"Archived", "Terminated", "Retired"}


def _resolve_department_id(snapshot: dict) -> int | None:
    department_id = snapshot.get("department", {}).get("id")
    if department_id and Department.objects.filter(pk=department_id).exists():
        return department_id
    return None


def _resolve_position_id(snapshot: dict) -> int | None:
    position_id = snapshot.get("position", {}).get("id")
    if position_id and Position.objects.filter(pk=position_id).exists():
        return position_id
    return None


def sync_transfer_assignment_fields(transfer: StaffTransfer) -> StaffTransfer:
    update_fields: list[str] = []
    employee = transfer.employee

    if transfer.from_department_id is None and employee.department_id:
        transfer.from_department_id = employee.department_id
        update_fields.append("from_department")

    if not transfer.from_position and employee.position_id:
        transfer.from_position = employee.position.title
        update_fields.append("from_position")

    if transfer.to_position_ref_id:
        target_position_title = transfer.to_position_ref.title
        if not transfer.to_position:
            transfer.to_position = target_position_title
            update_fields.append("to_position")
        if transfer.to_department_id is None and transfer.to_position_ref.department_id:
            transfer.to_department_id = transfer.to_position_ref.department_id
            update_fields.append("to_department")

    if update_fields:
        transfer.save(update_fields=update_fields)
    return transfer


def sync_career_action_assignment_fields(action: StaffCareerAction) -> StaffCareerAction:
    update_fields: list[str] = []
    employee = action.employee

    if action.action_type != "ACTING_APPOINTMENT_END":
        if action.from_department_id is None and employee.department_id:
            action.from_department_id = employee.department_id
            update_fields.append("from_department")

        if action.from_position_ref_id is None and employee.position_id:
            action.from_position_ref_id = employee.position_id
            update_fields.append("from_position_ref")

        if not action.from_position_title and employee.position_id:
            action.from_position_title = employee.position.title
            update_fields.append("from_position_title")

    if action.to_position_ref_id:
        if not action.to_position_title:
            action.to_position_title = action.to_position_ref.title
            update_fields.append("to_position_title")
        if action.to_department_id is None and action.to_position_ref.department_id:
            action.to_department_id = action.to_position_ref.department_id
            update_fields.append("to_department")

    if update_fields:
        action.save(update_fields=update_fields)
    return action


@transaction.atomic
def complete_transfer(transfer: StaffTransfer, *, recorded_by=None) -> StaffTransfer:
    transfer = sync_transfer_assignment_fields(transfer)
    if transfer.status == "Completed":
        raise CareerWorkflowError("Transfer is already completed.")
    if transfer.status in {"Rejected", "Cancelled"}:
        raise CareerWorkflowError(f"{transfer.status} transfer cannot be completed.")

    employee = transfer.employee
    before_snapshot = build_employee_state_snapshot(employee)

    employee_update_fields: list[str] = []
    if transfer.to_department_id and transfer.to_department_id != employee.department_id:
        employee.department_id = transfer.to_department_id
        employee_update_fields.append("department")

    if transfer.to_position_ref_id and transfer.to_position_ref_id != employee.position_id:
        employee.position_id = transfer.to_position_ref_id
        employee_update_fields.append("position")

    if employee_update_fields:
        employee.save(update_fields=employee_update_fields)
        employee.refresh_from_db()

    transfer.status = "Completed"
    transfer.save(update_fields=["status"])

    append_transfer_completed_event(
        transfer,
        recorded_by=recorded_by,
        before_snapshot=before_snapshot,
        after_snapshot=build_employee_state_snapshot(employee),
    )
    return transfer


@transaction.atomic
def apply_career_action(action: StaffCareerAction, *, recorded_by=None) -> StaffCareerAction:
    action = sync_career_action_assignment_fields(action)
    employee = action.employee

    if employee.status in TERMINAL_EMPLOYEE_STATUSES:
        raise CareerWorkflowError("Terminal employee states cannot receive career actions.")

    if action.action_type == "ACTING_APPOINTMENT_END":
        raise CareerWorkflowError("Use the end-acting action for acting appointment completion.")

    if action.status == "EFFECTIVE":
        raise CareerWorkflowError("Career action is already effective.")

    if action.status == "CANCELLED":
        raise CareerWorkflowError("Cancelled career action cannot be applied.")

    if action.action_type in {"PROMOTION", "DEMOTION"} and employee.status == "Acting":
        raise CareerWorkflowError("End the current acting appointment before applying another career action.")

    if action.action_type in {"PROMOTION", "DEMOTION"} and not action.to_position_ref_id:
        raise CareerWorkflowError("Target position is required for promotion or demotion.")

    if action.action_type == "ACTING_APPOINTMENT" and not (action.to_department_id or action.to_position_ref_id):
        raise CareerWorkflowError("Acting appointment requires a target department or target position.")

    before_snapshot = build_employee_state_snapshot(employee)
    employee_update_fields: list[str] = []

    if action.to_department_id and action.to_department_id != employee.department_id:
        employee.department_id = action.to_department_id
        employee_update_fields.append("department")

    if action.to_position_ref_id and action.to_position_ref_id != employee.position_id:
        employee.position_id = action.to_position_ref_id
        employee_update_fields.append("position")

    action_update_fields = ["status", "applied_by"]
    if action.action_type == "ACTING_APPOINTMENT":
        action.previous_assignment_snapshot = before_snapshot
        action_update_fields.append("previous_assignment_snapshot")
        if employee.status != "Acting":
            employee.status = "Acting"
            employee_update_fields.append("status")
    else:
        profile_update_fields: list[str] = []
        if action.target_position_grade or action.target_salary_scale:
            profile = ensure_employment_profile(employee)
            if action.target_position_grade and profile.position_grade != action.target_position_grade:
                profile.position_grade = action.target_position_grade
                profile_update_fields.append("position_grade")
            if action.target_salary_scale and profile.salary_scale != action.target_salary_scale:
                profile.salary_scale = action.target_salary_scale
                profile_update_fields.append("salary_scale")
            if profile_update_fields:
                profile.save(update_fields=profile_update_fields)

    if employee_update_fields:
        employee.save(update_fields=employee_update_fields)

    action.status = "EFFECTIVE"
    action.applied_by = recorded_by
    action.save(update_fields=action_update_fields)

    employee.refresh_from_db()
    append_career_action_effective_event(
        action,
        recorded_by=recorded_by,
        before_snapshot=before_snapshot,
        after_snapshot=build_employee_state_snapshot(employee),
    )
    return action


@transaction.atomic
def end_acting_appointment(
    action: StaffCareerAction,
    *,
    recorded_by=None,
    effective_date=None,
    notes: str = "",
) -> StaffCareerAction:
    if action.action_type != "ACTING_APPOINTMENT":
        raise CareerWorkflowError("Only acting appointments can be ended through this action.")

    if action.status != "EFFECTIVE":
        raise CareerWorkflowError("Acting appointment must be effective before it can be ended.")

    if not action.previous_assignment_snapshot:
        raise CareerWorkflowError("Acting appointment cannot end without a stored prior assignment snapshot.")

    if action.follow_up_actions.filter(action_type="ACTING_APPOINTMENT_END", status="EFFECTIVE").exists():
        raise CareerWorkflowError("Acting appointment has already been ended.")

    employee = action.employee
    before_snapshot = build_employee_state_snapshot(employee)
    previous_snapshot = action.previous_assignment_snapshot or {}

    employee_update_fields: list[str] = []
    restored_department_id = _resolve_department_id(previous_snapshot)
    restored_position_id = _resolve_position_id(previous_snapshot)

    if restored_department_id != employee.department_id:
        employee.department_id = restored_department_id
        employee_update_fields.append("department")

    if restored_position_id != employee.position_id:
        employee.position_id = restored_position_id
        employee_update_fields.append("position")

    restored_status = previous_snapshot.get("status") or "Active"
    if restored_status == "Acting":
        restored_status = "Active"
    if employee.status != "Acting":
        restored_status = employee.status
    if restored_status != employee.status:
        employee.status = restored_status
        employee_update_fields.append("status")

    previous_profile_snapshot = previous_snapshot.get("employment_profile") or {}
    profile_update_fields: list[str] = []
    if previous_profile_snapshot:
        profile = ensure_employment_profile(employee)
        restored_position_grade = previous_profile_snapshot.get("position_grade", "")
        restored_salary_scale = previous_profile_snapshot.get("salary_scale", "")
        if profile.position_grade != restored_position_grade:
            profile.position_grade = restored_position_grade
            profile_update_fields.append("position_grade")
        if profile.salary_scale != restored_salary_scale:
            profile.salary_scale = restored_salary_scale
            profile_update_fields.append("salary_scale")
        if profile_update_fields:
            profile.save(update_fields=profile_update_fields)

    if employee_update_fields:
        employee.save(update_fields=employee_update_fields)

    employee.refresh_from_db()
    after_snapshot = build_employee_state_snapshot(employee)

    end_action = StaffCareerAction.objects.create(
        employee=employee,
        parent_action=action,
        action_type="ACTING_APPOINTMENT_END",
        from_department_id=before_snapshot.get("department", {}).get("id") or None,
        from_position_ref_id=before_snapshot.get("position", {}).get("id") or None,
        from_position_title=before_snapshot.get("position", {}).get("title") or "",
        to_department_id=restored_department_id,
        to_position_ref_id=restored_position_id,
        to_position_title=after_snapshot.get("position", {}).get("title") or previous_snapshot.get("position", {}).get("title") or "",
        target_position_grade=after_snapshot.get("employment_profile", {}).get("position_grade", ""),
        target_salary_scale=after_snapshot.get("employment_profile", {}).get("salary_scale", ""),
        reason=action.reason,
        effective_date=effective_date or timezone.now().date(),
        status="EFFECTIVE",
        previous_assignment_snapshot=previous_snapshot,
        notes=notes,
        requested_by=action.requested_by or recorded_by,
        applied_by=recorded_by,
    )

    append_career_action_effective_event(
        end_action,
        recorded_by=recorded_by,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    )
    return end_action
