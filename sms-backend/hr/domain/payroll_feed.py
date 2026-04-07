from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Sum

from ..models import AttendanceRecord, Employee, LeaveRequest, ReturnToWorkReconciliation


def _month_bounds(year: int, month: int):
    month_start = datetime(year, month, 1).date()
    if month == 12:
        month_end = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        month_end = datetime(year, month + 1, 1).date() - timedelta(days=1)
    return month_start, month_end


def _leave_days_in_period(leave_request: LeaveRequest, month_start, month_end) -> Decimal:
    overlap_start = max(leave_request.start_date, month_start)
    overlap_end = min(leave_request.end_date, month_end)
    if overlap_end < overlap_start:
        return Decimal("0.00")
    return Decimal(str((overlap_end - overlap_start).days + 1)).quantize(Decimal("0.01"))


def build_workforce_feed(month: int, year: int, *, employee_id=None):
    month_start, month_end = _month_bounds(year, month)
    employees = Employee.objects.filter(is_active=True).order_by("employee_id", "id")
    if employee_id:
        employees = employees.filter(pk=employee_id)

    rows = []
    for employee in employees:
        attendance = AttendanceRecord.objects.filter(
            employee=employee,
            is_active=True,
            date__gte=month_start,
            date__lte=month_end,
        )
        leave_requests = LeaveRequest.objects.filter(
            employee=employee,
            status="Approved",
            is_active=True,
            start_date__lte=month_end,
            end_date__gte=month_start,
        ).select_related("leave_type")
        open_reconciliations = ReturnToWorkReconciliation.objects.filter(
            employee=employee,
            is_active=True,
            leave_request__start_date__lte=month_end,
            leave_request__end_date__gte=month_start,
            status__in=["PENDING", "REOPENED"],
        )

        leave_by_type = defaultdict(lambda: Decimal("0.00"))
        for leave_request in leave_requests:
            leave_by_type[(leave_request.leave_type_id, leave_request.leave_type.name)] += _leave_days_in_period(
                leave_request,
                month_start,
                month_end,
            )

        blocked_alert_days = attendance.filter(payroll_feed_status="BLOCKED_ALERT").count()
        blocked_reconciliation_days = attendance.filter(payroll_feed_status="BLOCKED_RECONCILIATION").count()
        blocked_leave_days = attendance.filter(payroll_feed_status="BLOCKED_LEAVE").count()
        hold_reconciliations = open_reconciliations.count()
        present_days = attendance.filter(status="Present").count()
        late_days = attendance.filter(status="Late").count()
        half_days = attendance.filter(status="Half-Day").count()
        unpaid_absence_days = Decimal(str(attendance.filter(status="Absent").count())).quantize(Decimal("0.01"))
        approved_leave_total = sum(leave_by_type.values(), Decimal("0.00")).quantize(Decimal("0.01"))
        payable_days = (
            Decimal(str(present_days + late_days + half_days)).quantize(Decimal("0.01"))
            + approved_leave_total
        )
        blocking_reasons = []
        if blocked_alert_days:
            blocking_reasons.append(f"{blocked_alert_days} day(s) blocked by unresolved absence alerts")
        if blocked_reconciliation_days:
            blocking_reasons.append(f"{blocked_reconciliation_days} day(s) blocked by reconciliation holds")
        if blocked_leave_days:
            blocking_reasons.append(f"{blocked_leave_days} leave day(s) still awaiting return reconciliation")
        if hold_reconciliations:
            blocking_reasons.append(f"{hold_reconciliations} return-to-work reconciliation case(s) still open")

        rows.append(
            {
                "employee": employee.id,
                "employee_id": employee.employee_id,
                "employee_name": f"{employee.first_name} {employee.last_name}".strip(),
                "present_days": present_days,
                "late_days": late_days,
                "half_days": half_days,
                "overtime_hours": str((attendance.aggregate(v=Sum("overtime_hours"))["v"] or Decimal("0.00")).quantize(Decimal("0.01"))),
                "approved_leave_days_total": str(approved_leave_total),
                "approved_leave_by_type": [
                    {
                        "leave_type_id": leave_type_id,
                        "leave_type_name": leave_type_name,
                        "days": str(days.quantize(Decimal("0.01"))),
                    }
                    for (leave_type_id, leave_type_name), days in sorted(leave_by_type.items(), key=lambda row: row[0][1])
                ],
                "blocked_alert_days": blocked_alert_days,
                "blocked_reconciliation_days": blocked_reconciliation_days,
                "blocked_leave_days": blocked_leave_days,
                "open_return_reconciliation_count": hold_reconciliations,
                "is_payroll_ready": not blocking_reasons,
                "blocking_reasons": blocking_reasons,
                "unpaid_absence_days": str(unpaid_absence_days),
                "payable_days": str(payable_days),
            }
        )

    return {
        "month": month,
        "year": year,
        "employee_count": len(rows),
        "results": rows,
    }
