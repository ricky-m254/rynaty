from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from ..models import AttendanceRecord, LeaveRequest, ReturnToWorkReconciliation
from .attendance_operations import resolve_manager_employee

DEFAULT_LONG_LEAVE_THRESHOLD_DAYS = Decimal("5.00")


def get_long_leave_threshold_days() -> Decimal:
    return DEFAULT_LONG_LEAVE_THRESHOLD_DAYS


def _iter_dates(start_date, end_date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def _leave_period_state(reconciliation_required: bool):
    if reconciliation_required:
        return "PENDING", "BLOCKED_LEAVE"
    return "NOT_REQUIRED", "READY"


def _materialize_leave_attendance_records(leave_request: LeaveRequest) -> None:
    reconciliation_status, payroll_feed_status = _leave_period_state(leave_request.return_reconciliation_required)
    for on_date in _iter_dates(leave_request.start_date, leave_request.end_date):
        record, _ = AttendanceRecord.objects.get_or_create(
            employee=leave_request.employee,
            date=on_date,
            defaults={
                "status": "On Leave",
                "attendance_source": "RECONCILED",
                "is_active": True,
            },
        )
        record.status = "On Leave"
        record.attendance_source = "RECONCILED"
        record.reconciliation_status = reconciliation_status
        record.payroll_feed_status = payroll_feed_status
        record.resolved_at = timezone.now()
        record.save(
            update_fields=[
                "status",
                "attendance_source",
                "reconciliation_status",
                "payroll_feed_status",
                "resolved_at",
            ]
        )


def _update_leave_attendance_records(leave_request: LeaveRequest, *, reconciliation_status: str, payroll_feed_status: str) -> None:
    AttendanceRecord.objects.filter(
        employee=leave_request.employee,
        date__gte=leave_request.start_date,
        date__lte=leave_request.end_date,
        is_active=True,
        status="On Leave",
    ).update(
        reconciliation_status=reconciliation_status,
        payroll_feed_status=payroll_feed_status,
        attendance_source="RECONCILED",
        resolved_at=timezone.now(),
    )


def initialize_leave_request_state(leave_request: LeaveRequest) -> LeaveRequest:
    threshold = get_long_leave_threshold_days()
    requires_dual = (leave_request.days_requested or Decimal("0.00")) > threshold
    first_approver = resolve_manager_employee(leave_request.employee) if requires_dual else None

    leave_request.long_leave_threshold_days_snapshot = threshold
    leave_request.requires_dual_approval = requires_dual
    leave_request.return_reconciliation_required = requires_dual
    leave_request.approval_stage = "PENDING_MANAGER" if requires_dual else "PENDING_HR"
    leave_request.current_approver = first_approver
    return leave_request


def _ensure_return_reconciliation(leave_request: LeaveRequest) -> ReturnToWorkReconciliation | None:
    if not leave_request.return_reconciliation_required:
        return None
    reconciliation, _ = ReturnToWorkReconciliation.objects.get_or_create(
        leave_request=leave_request,
        defaults={
            "employee": leave_request.employee,
            "expected_return_date": leave_request.end_date + timedelta(days=1),
            "status": "PENDING",
            "is_active": True,
        },
    )
    return reconciliation


@transaction.atomic
def manager_approve_leave(leave_request: LeaveRequest, *, approver_employee=None) -> LeaveRequest:
    if leave_request.status != "Pending":
        raise ValueError("Only pending requests can be approved.")
    if not leave_request.requires_dual_approval:
        raise ValueError("Manager approval is only required for long leave requests.")
    if leave_request.approval_stage != "PENDING_MANAGER":
        raise ValueError("Leave request is not awaiting manager approval.")
    expected_approver = leave_request.current_approver or resolve_manager_employee(leave_request.employee)
    if expected_approver is None:
        raise ValueError("Leave request does not have an assigned manager approver.")
    if approver_employee is None or approver_employee.id != expected_approver.id:
        raise ValueError("Only the assigned manager approver can approve this leave request.")

    leave_request.manager_approved_by = approver_employee
    leave_request.manager_approved_at = timezone.now()
    leave_request.approval_stage = "PENDING_HR"
    leave_request.current_approver = None
    leave_request.rejection_reason = ""
    leave_request.save(
        update_fields=[
            "manager_approved_by",
            "manager_approved_at",
            "approval_stage",
            "current_approver",
            "rejection_reason",
        ]
    )
    return leave_request


@transaction.atomic
def final_approve_leave(leave_request: LeaveRequest, *, approver_employee=None) -> LeaveRequest:
    if leave_request.status != "Pending":
        raise ValueError("Only pending requests can be approved.")
    if leave_request.requires_dual_approval and leave_request.approval_stage != "PENDING_HR":
        raise ValueError("Long leave requires manager approval before HR final approval.")

    days = leave_request.days_requested or Decimal("0.00")
    balance = leave_request.employee.leave_balances.filter(
        leave_type=leave_request.leave_type,
        year=leave_request.start_date.year,
        is_active=True,
    ).first()
    if balance is None:
        raise ValueError("Leave balance is missing for the requested period.")

    balance.pending = max(balance.pending - days, Decimal("0.00"))
    balance.used += days
    balance.available = (balance.opening_balance + balance.accrued) - (balance.used + balance.pending)
    balance.save(update_fields=["pending", "used", "available", "updated_at"])

    now = timezone.now()
    leave_request.status = "Approved"
    leave_request.approval_stage = "APPROVED"
    leave_request.current_approver = None
    leave_request.approved_by = approver_employee
    leave_request.approved_at = now
    leave_request.rejection_reason = ""
    leave_request.hr_approved_by = approver_employee
    leave_request.hr_approved_at = now
    leave_request.save(
        update_fields=[
            "status",
            "approval_stage",
            "current_approver",
            "approved_by",
            "approved_at",
            "rejection_reason",
            "hr_approved_by",
            "hr_approved_at",
        ]
    )

    _materialize_leave_attendance_records(leave_request)
    _ensure_return_reconciliation(leave_request)
    return leave_request


@transaction.atomic
def reject_leave(leave_request: LeaveRequest, *, reason: str) -> LeaveRequest:
    if leave_request.status != "Pending":
        raise ValueError("Only pending requests can be rejected.")
    if not reason.strip():
        raise ValueError("rejection_reason is required.")

    days = leave_request.days_requested or Decimal("0.00")
    balance = leave_request.employee.leave_balances.filter(
        leave_type=leave_request.leave_type,
        year=leave_request.start_date.year,
        is_active=True,
    ).first()
    if balance is None:
        raise ValueError("Leave balance is missing for the requested period.")

    balance.pending = max(balance.pending - days, Decimal("0.00"))
    balance.available = (balance.opening_balance + balance.accrued) - (balance.used + balance.pending)
    balance.save(update_fields=["pending", "available", "updated_at"])

    leave_request.status = "Rejected"
    leave_request.approval_stage = "REJECTED"
    leave_request.current_approver = None
    leave_request.rejection_reason = reason.strip()
    leave_request.save(update_fields=["status", "approval_stage", "current_approver", "rejection_reason"])
    return leave_request


@transaction.atomic
def request_leave_clarification(leave_request: LeaveRequest, *, review_notes: str) -> LeaveRequest:
    if leave_request.status != "Pending":
        raise ValueError("Only pending requests can be sent back for clarification.")
    if not review_notes.strip():
        raise ValueError("review_notes is required.")

    leave_request.status = "Needs Info"
    leave_request.approval_stage = "NEEDS_INFO"
    leave_request.current_approver = None
    leave_request.review_notes = review_notes.strip()
    leave_request.rejection_reason = ""
    leave_request.save(
        update_fields=[
            "status",
            "approval_stage",
            "current_approver",
            "review_notes",
            "rejection_reason",
        ]
    )
    return leave_request


@transaction.atomic
def cancel_leave(leave_request: LeaveRequest) -> LeaveRequest:
    if leave_request.status != "Pending":
        raise ValueError("Only pending requests can be cancelled.")

    days = leave_request.days_requested or Decimal("0.00")
    balance = leave_request.employee.leave_balances.filter(
        leave_type=leave_request.leave_type,
        year=leave_request.start_date.year,
        is_active=True,
    ).first()
    if balance is None:
        raise ValueError("Leave balance is missing for the requested period.")

    balance.pending = max(balance.pending - days, Decimal("0.00"))
    balance.available = (balance.opening_balance + balance.accrued) - (balance.used + balance.pending)
    balance.save(update_fields=["pending", "available", "updated_at"])

    leave_request.status = "Cancelled"
    leave_request.approval_stage = "CANCELLED"
    leave_request.current_approver = None
    leave_request.save(update_fields=["status", "approval_stage", "current_approver"])
    return leave_request


@transaction.atomic
def complete_return_reconciliation(
    reconciliation: ReturnToWorkReconciliation,
    *,
    completed_by,
    actual_return_date,
    attendance_record=None,
    extension_required=False,
    attendance_correction_required=False,
    payroll_hold_required=False,
    substitute_closed=False,
    notes="",
) -> ReturnToWorkReconciliation:
    reconciliation.actual_return_date = actual_return_date
    reconciliation.attendance_record = attendance_record
    reconciliation.status = "COMPLETED"
    reconciliation.extension_required = extension_required
    reconciliation.attendance_correction_required = attendance_correction_required
    reconciliation.payroll_hold_required = payroll_hold_required
    reconciliation.substitute_closed = substitute_closed
    reconciliation.completed_by = completed_by
    reconciliation.completed_at = timezone.now()
    reconciliation.notes = notes
    reconciliation.save(
        update_fields=[
            "actual_return_date",
            "attendance_record",
            "status",
            "extension_required",
            "attendance_correction_required",
            "payroll_hold_required",
            "substitute_closed",
            "completed_by",
            "completed_at",
            "notes",
            "updated_at",
        ]
    )

    _update_leave_attendance_records(
        reconciliation.leave_request,
        reconciliation_status="COMPLETED",
        payroll_feed_status="READY",
    )

    if attendance_record:
        attendance_record.reconciliation_status = "COMPLETED"
        attendance_record.payroll_feed_status = "READY"
        attendance_record.resolved_at = timezone.now()
        attendance_record.save(update_fields=["reconciliation_status", "payroll_feed_status", "resolved_at"])

    return reconciliation


@transaction.atomic
def reopen_return_reconciliation(reconciliation: ReturnToWorkReconciliation, *, notes="") -> ReturnToWorkReconciliation:
    reconciliation.status = "REOPENED"
    reconciliation.notes = notes
    reconciliation.completed_by = None
    reconciliation.completed_at = None
    reconciliation.save(update_fields=["status", "notes", "completed_by", "completed_at", "updated_at"])

    _update_leave_attendance_records(
        reconciliation.leave_request,
        reconciliation_status="PENDING",
        payroll_feed_status="BLOCKED_LEAVE",
    )

    if reconciliation.attendance_record_id:
        record = reconciliation.attendance_record
        record.reconciliation_status = "PENDING"
        record.payroll_feed_status = "BLOCKED_RECONCILIATION"
        record.resolved_at = None
        record.save(update_fields=["reconciliation_status", "payroll_feed_status", "resolved_at"])

    return reconciliation
