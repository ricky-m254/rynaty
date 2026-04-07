from dataclasses import dataclass
from datetime import datetime, time as dt_time, timedelta
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from ..models import AbsenceAlert, AttendanceRecord, Employee, LeaveRequest, ShiftTemplate, WorkSchedule

WEEKDAY_NAME_MAP = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tues": 1,
    "tuesday": 1,
    "wed": 2,
    "wednesday": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}


@dataclass(frozen=True)
class ResolvedShift:
    schedule: WorkSchedule
    shift_template: Optional[ShiftTemplate]
    shift_start: dt_time
    shift_end: dt_time
    working_days: list
    break_duration_minutes: int
    grace_minutes: int
    requires_biometric_clock: bool
    overtime_eligible: bool


def _normalize_working_days(raw_days) -> set[int]:
    if not raw_days:
        return set()
    normalized = set()
    for value in raw_days:
        if isinstance(value, int) and 0 <= value <= 6:
            normalized.add(value)
            continue
        text = str(value).strip().lower()
        if text.isdigit() and 0 <= int(text) <= 6:
            normalized.add(int(text))
            continue
        day = WEEKDAY_NAME_MAP.get(text)
        if day is not None:
            normalized.add(day)
    return normalized


def _schedule_applies_to_date(schedule: WorkSchedule, on_date) -> bool:
    if schedule.effective_from and on_date < schedule.effective_from:
        return False
    if schedule.effective_to and on_date > schedule.effective_to:
        return False
    weekdays = _normalize_working_days(_resolved_working_days(schedule))
    return not weekdays or on_date.weekday() in weekdays


def _resolved_shift_start(schedule: WorkSchedule):
    return schedule.shift_template.shift_start if schedule.shift_template_id else schedule.shift_start


def _resolved_shift_end(schedule: WorkSchedule):
    return schedule.shift_template.shift_end if schedule.shift_template_id else schedule.shift_end


def _resolved_working_days(schedule: WorkSchedule):
    return schedule.shift_template.working_days if schedule.shift_template_id else schedule.working_days


def _resolved_break_duration(schedule: WorkSchedule) -> int:
    return (
        schedule.shift_template.break_duration_minutes
        if schedule.shift_template_id
        else schedule.break_duration
    )


def _resolved_grace_minutes(schedule: WorkSchedule) -> int:
    return schedule.shift_template.grace_minutes if schedule.shift_template_id else 0


def _resolved_requires_biometric(schedule: WorkSchedule) -> bool:
    return bool(schedule.shift_template.requires_biometric_clock) if schedule.shift_template_id else False


def _resolved_overtime_eligible(schedule: WorkSchedule) -> bool:
    return bool(schedule.shift_template.overtime_eligible) if schedule.shift_template_id else True


def _normalize_datetime_value(value):
    if value is None:
        return None
    if settings.USE_TZ:
        return value if timezone.is_aware(value) else timezone.make_aware(value, timezone.get_current_timezone())
    return value.replace(tzinfo=None) if timezone.is_aware(value) else value


def _combine_date_time(on_date, at_time):
    return _normalize_datetime_value(datetime.combine(on_date, at_time))


def resolve_manager_employee(employee: Employee) -> Optional[Employee]:
    if employee.reporting_to_id and employee.reporting_to.is_active:
        return employee.reporting_to
    if employee.department_id and employee.department and employee.department.head_id and employee.department.head.is_active:
        return employee.department.head
    return None


def resolve_expected_shift(employee: Employee, on_date) -> Optional[ResolvedShift]:
    base_queryset = WorkSchedule.objects.filter(
        is_active=True,
        effective_from__lte=on_date,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=on_date)).select_related("shift_template")

    employee_schedules = base_queryset.filter(employee=employee).order_by("assignment_priority", "-effective_from", "-id")
    for schedule in employee_schedules:
        if _schedule_applies_to_date(schedule, on_date):
            return ResolvedShift(
                schedule=schedule,
                shift_template=schedule.shift_template,
                shift_start=_resolved_shift_start(schedule),
                shift_end=_resolved_shift_end(schedule),
                working_days=list(_resolved_working_days(schedule) or []),
                break_duration_minutes=_resolved_break_duration(schedule),
                grace_minutes=_resolved_grace_minutes(schedule),
                requires_biometric_clock=_resolved_requires_biometric(schedule),
                overtime_eligible=_resolved_overtime_eligible(schedule),
            )

    if not employee.department_id:
        return None

    department_schedules = base_queryset.filter(employee__isnull=True, department=employee.department).order_by(
        "assignment_priority",
        "-effective_from",
        "-id",
    )
    for schedule in department_schedules:
        if _schedule_applies_to_date(schedule, on_date):
            return ResolvedShift(
                schedule=schedule,
                shift_template=schedule.shift_template,
                shift_start=_resolved_shift_start(schedule),
                shift_end=_resolved_shift_end(schedule),
                working_days=list(_resolved_working_days(schedule) or []),
                break_duration_minutes=_resolved_break_duration(schedule),
                grace_minutes=_resolved_grace_minutes(schedule),
                requires_biometric_clock=_resolved_requires_biometric(schedule),
                overtime_eligible=_resolved_overtime_eligible(schedule),
            )

    return None


def refresh_payroll_feed_status(record: AttendanceRecord) -> str:
    if record.status == "On Leave" and record.reconciliation_status == "PENDING":
        return "BLOCKED_LEAVE"
    if record.reconciliation_status == "PENDING":
        return "BLOCKED_RECONCILIATION"
    if record.alert_status == "OPEN":
        return "BLOCKED_ALERT"
    return "READY"


def apply_shift_context(record: AttendanceRecord, resolved_shift: Optional[ResolvedShift]) -> AttendanceRecord:
    if resolved_shift is None:
        record.shift_template = None
        record.scheduled_shift_start = None
        record.scheduled_shift_end = None
        record.expected_check_in_deadline = None
        record.payroll_feed_status = refresh_payroll_feed_status(record)
        return record

    record.shift_template = resolved_shift.shift_template
    record.scheduled_shift_start = resolved_shift.shift_start
    record.scheduled_shift_end = resolved_shift.shift_end
    record.expected_check_in_deadline = _combine_date_time(record.date, resolved_shift.shift_start) + timedelta(
        minutes=resolved_shift.grace_minutes
    )
    record.payroll_feed_status = refresh_payroll_feed_status(record)
    return record


def _approved_leave_exists(employee: Employee, on_date) -> bool:
    return LeaveRequest.objects.filter(
        employee=employee,
        status="Approved",
        start_date__lte=on_date,
        end_date__gte=on_date,
        is_active=True,
    ).exists()


def _ensure_daily_record(employee: Employee, on_date, *, recorded_by=None, status_value="Present", attendance_source="MANUAL"):
    record, _ = AttendanceRecord.objects.get_or_create(
        employee=employee,
        date=on_date,
        defaults={
            "status": status_value,
            "recorded_by": recorded_by,
            "attendance_source": attendance_source,
            "is_active": True,
        },
    )
    return record


def auto_resolve_alert_for_attendance(record: AttendanceRecord, *, reason="Clock-in captured after alert creation") -> None:
    alert = (
        AbsenceAlert.objects.filter(attendance_record=record, is_active=True, status__in=["OPEN", "ESCALATED"])
        .order_by("-id")
        .first()
    )
    if not alert:
        if record.alert_status == "OPEN":
            record.alert_status = "NONE"
            record.payroll_feed_status = refresh_payroll_feed_status(record)
            record.save(update_fields=["alert_status", "payroll_feed_status"])
        return

    alert.status = "AUTO_RESOLVED"
    alert.resolution_reason = reason
    alert.resolved_at = timezone.now()
    alert.save(update_fields=["status", "resolution_reason", "resolved_at"])

    record.alert_status = "AUTO_RESOLVED"
    record.payroll_feed_status = refresh_payroll_feed_status(record)
    record.save(update_fields=["alert_status", "payroll_feed_status"])


def refresh_record_for_clock_in(
    record: AttendanceRecord,
    *,
    clock_in_time,
    attendance_source="MANUAL",
    recorded_by=None,
) -> AttendanceRecord:
    resolved_shift = resolve_expected_shift(record.employee, record.date)
    apply_shift_context(record, resolved_shift)

    record.clock_in = clock_in_time
    record.recorded_by = recorded_by or record.recorded_by
    record.attendance_source = attendance_source

    if _approved_leave_exists(record.employee, record.date):
        record.status = "On Leave"
    elif record.expected_check_in_deadline:
        clock_in_at = _combine_date_time(record.date, clock_in_time)
        record.status = "Late" if clock_in_at > record.expected_check_in_deadline else "Present"
    else:
        record.status = "Present"

    record.resolved_at = timezone.now()
    record.payroll_feed_status = refresh_payroll_feed_status(record)
    record.save(
        update_fields=[
            "shift_template",
            "scheduled_shift_start",
            "scheduled_shift_end",
            "expected_check_in_deadline",
            "clock_in",
            "recorded_by",
            "attendance_source",
            "status",
            "resolved_at",
            "payroll_feed_status",
        ]
    )
    auto_resolve_alert_for_attendance(record)
    return record


def refresh_record_for_manual_update(record: AttendanceRecord, *, attendance_source="MANUAL") -> AttendanceRecord:
    resolved_shift = resolve_expected_shift(record.employee, record.date)
    apply_shift_context(record, resolved_shift)
    record.attendance_source = attendance_source
    record.payroll_feed_status = refresh_payroll_feed_status(record)
    return record


@transaction.atomic
def evaluate_absence_alert(employee: Employee, on_date, *, triggered_at=None):
    triggered_at = _normalize_datetime_value(triggered_at or timezone.now())
    record = _ensure_daily_record(employee, on_date, status_value="Present", attendance_source="MANUAL")
    resolved_shift = resolve_expected_shift(employee, on_date)
    apply_shift_context(record, resolved_shift)

    if resolved_shift is None:
        record.alert_status = "NONE"
        record.payroll_feed_status = refresh_payroll_feed_status(record)
        record.save(
            update_fields=[
                "shift_template",
                "scheduled_shift_start",
                "scheduled_shift_end",
                "expected_check_in_deadline",
                "alert_status",
                "payroll_feed_status",
            ]
        )
        return {"record": record, "alert": None, "created": False, "reason": "unscheduled"}

    if _approved_leave_exists(employee, on_date):
        record.status = "On Leave"
        record.alert_status = "NONE"
        record.payroll_feed_status = refresh_payroll_feed_status(record)
        record.resolved_at = timezone.now()
        record.save(
            update_fields=[
                "shift_template",
                "scheduled_shift_start",
                "scheduled_shift_end",
                "expected_check_in_deadline",
                "status",
                "alert_status",
                "payroll_feed_status",
                "resolved_at",
            ]
        )
        return {"record": record, "alert": None, "created": False, "reason": "approved_leave"}

    if record.clock_in:
        refresh_record_for_clock_in(
            record,
            clock_in_time=record.clock_in,
            attendance_source=record.attendance_source or "MANUAL",
            recorded_by=record.recorded_by,
        )
        return {"record": record, "alert": None, "created": False, "reason": "already_clocked_in"}

    if record.expected_check_in_deadline and triggered_at <= record.expected_check_in_deadline:
        record.alert_status = "NONE"
        record.payroll_feed_status = refresh_payroll_feed_status(record)
        record.save(
            update_fields=[
                "shift_template",
                "scheduled_shift_start",
                "scheduled_shift_end",
                "expected_check_in_deadline",
                "alert_status",
                "payroll_feed_status",
            ]
        )
        return {"record": record, "alert": None, "created": False, "reason": "before_deadline"}

    record.status = "Absent"
    record.alert_status = "OPEN"
    record.resolved_at = None
    record.payroll_feed_status = refresh_payroll_feed_status(record)
    record.save(
        update_fields=[
            "shift_template",
            "scheduled_shift_start",
            "scheduled_shift_end",
            "expected_check_in_deadline",
            "status",
            "alert_status",
            "resolved_at",
            "payroll_feed_status",
        ]
    )

    manager = resolve_manager_employee(employee)
    alert = AbsenceAlert.objects.filter(attendance_record=record, is_active=True).order_by("-id").first()
    created = False
    if alert is None:
        alert = AbsenceAlert.objects.create(
            employee=employee,
            attendance_record=record,
            shift_template=record.shift_template,
            notified_manager=manager,
            alert_date=record.date,
            expected_shift_start=record.scheduled_shift_start,
            grace_deadline=record.expected_check_in_deadline or triggered_at,
            status="OPEN",
            hr_copied=manager is None,
            is_active=True,
        )
        created = True
    else:
        changed = []
        if alert.shift_template_id != (record.shift_template_id or None):
            alert.shift_template = record.shift_template
            changed.append("shift_template")
        if alert.notified_manager_id != (manager.id if manager else None):
            alert.notified_manager = manager
            changed.append("notified_manager")
        if alert.expected_shift_start != record.scheduled_shift_start:
            alert.expected_shift_start = record.scheduled_shift_start
            changed.append("expected_shift_start")
        if alert.grace_deadline != (record.expected_check_in_deadline or alert.grace_deadline):
            alert.grace_deadline = record.expected_check_in_deadline or alert.grace_deadline
            changed.append("grace_deadline")
        if alert.status != "OPEN":
            alert.status = "OPEN"
            changed.append("status")
        should_copy_hr = manager is None or alert.hr_copied
        if alert.hr_copied != should_copy_hr:
            alert.hr_copied = should_copy_hr
            changed.append("hr_copied")
        if changed:
            alert.save(update_fields=changed)

    return {"record": record, "alert": alert, "created": created, "reason": "alert_open"}


@transaction.atomic
def manually_resolve_alert(alert: AbsenceAlert, *, resolved_by, reason="", notes="", attendance_status=None) -> AbsenceAlert:
    alert.status = "MANUALLY_RESOLVED"
    alert.resolved_by = resolved_by
    alert.resolution_reason = reason
    alert.notes = notes
    alert.resolved_at = timezone.now()
    alert.save(update_fields=["status", "resolved_by", "resolution_reason", "notes", "resolved_at"])

    record = alert.attendance_record
    if attendance_status:
        record.status = attendance_status
    record.alert_status = "MANUALLY_RESOLVED"
    record.resolved_at = timezone.now()
    record.payroll_feed_status = refresh_payroll_feed_status(record)
    update_fields = ["alert_status", "resolved_at", "payroll_feed_status"]
    if attendance_status:
        update_fields.append("status")
    record.save(update_fields=update_fields)
    return alert


@transaction.atomic
def escalate_alert(alert: AbsenceAlert, *, notes="") -> AbsenceAlert:
    alert.status = "ESCALATED"
    alert.hr_copied = True
    if notes:
        alert.notes = notes
        alert.save(update_fields=["status", "hr_copied", "notes"])
    else:
        alert.save(update_fields=["status", "hr_copied"])
    return alert
