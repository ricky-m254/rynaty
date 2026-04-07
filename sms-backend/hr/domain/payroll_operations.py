from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Prefetch, Q
from django.utils import timezone

from ..models import (
    EmployeeEmploymentProfile,
    PayrollBatch,
    PayrollDisbursement,
    PayrollItem,
    PayrollItemBreakdown,
    SalaryComponent,
    SalaryStructure,
)
from .payroll_feed import build_workforce_feed
from .statutory_rules import (
    apply_statutory_rules_to_bases,
    build_statutory_snapshot,
    ensure_kenya_first_statutory_defaults,
    get_active_statutory_rules,
    round_money,
)

OVERTIME_MONTHLY_DIVISOR = Decimal("173.33")
PROCESS_LOCKED_STATUSES = {
    "Approved",
    "Finance Approved",
    "Paid",
    "Disbursed",
    "Finance Posted",
    "Closed",
}
FINANCE_APPROVAL_READY_STATUSES = {"Draft", "Ready for Finance Approval", "Approved"}
FINANCE_APPROVED_STATUSES = {"Approved", "Finance Approved"}
DISBURSEMENT_STARTABLE_STATUSES = {"Approved", "Finance Approved", "Disbursement In Progress"}
DISBURSEMENT_FINAL_STATUSES = {"Paid", "Disbursed", "Finance Posted", "Closed"}
POSTING_BUCKET_BY_CATEGORY = {
    "TEACHING": "TEACHING_SALARIES",
    "ADMIN": "SUPPORT_SALARIES",
    "SUPPORT": "SUPPORT_SALARIES",
    "OPERATIONS": "OPERATIONS_SALARIES",
    "HOSTEL": "OPERATIONS_SALARIES",
    "SECURITY": "OPERATIONS_SALARIES",
    "KITCHEN": "OPERATIONS_SALARIES",
    "HEALTH": "OPERATIONS_SALARIES",
}
MANDATORY_IDENTIFIER_FIELDS = {
    "PAYE": ("kra_pin", "KRA PIN"),
    "NSSF": ("nssf_number", "NSSF number"),
    "SHIF": ("nhif_number", "SHIF member number"),
}


class PayrollWorkflowError(Exception):
    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        next_month = datetime(year + 1, 1, 1).date()
    else:
        next_month = datetime(year, month + 1, 1).date()
    return (next_month - datetime(year, month, 1).date()).days


def _as_decimal(value) -> Decimal:
    return Decimal(str(value or "0.00"))


def _component_amount(component: SalaryComponent, basic_salary: Decimal) -> Decimal:
    if component.amount_type == "Percentage":
        return round_money((basic_salary * component.amount) / Decimal("100.00"))
    return round_money(component.amount)


def _truncate_reason(text: str) -> str:
    cleaned = text.strip()
    return cleaned if len(cleaned) <= 255 else f"{cleaned[:252]}..."


def _resolve_active_structures(month_start, month_end):
    queryset = (
        SalaryStructure.objects.filter(
            is_active=True,
            employee__is_active=True,
            effective_from__lte=month_end,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=month_start))
        .select_related("employee", "employee__department", "employee__position")
        .prefetch_related(
            Prefetch("components", queryset=SalaryComponent.objects.filter(is_active=True).order_by("name", "id"))
        )
        .order_by("employee_id", "-effective_from", "-id")
    )
    selected = []
    seen_employee_ids = set()
    for structure in queryset:
        if structure.employee_id in seen_employee_ids:
            continue
        selected.append(structure)
        seen_employee_ids.add(structure.employee_id)
    return selected


def _resolve_posting_bucket(employee) -> tuple[str, str | None]:
    bucket = POSTING_BUCKET_BY_CATEGORY.get((employee.staff_category or "").strip().upper(), "")
    if bucket:
        return bucket, None
    return "", "Missing staff category for payroll posting bucket"


def _serialize_component_row(component: SalaryComponent, *, amount: Decimal, basic_salary: Decimal, display_order: int) -> dict:
    return {
        "line_type": "ALLOWANCE" if component.component_type == "Allowance" else "OTHER_DEDUCTION",
        "code": "",
        "name": component.name,
        "base_amount": basic_salary if component.amount_type == "Percentage" else amount,
        "rate": round_money(component.amount if component.amount_type == "Percentage" else Decimal("0.00")),
        "amount": round_money(amount),
        "display_order": display_order,
        "snapshot": {
            "component_id": component.id,
            "amount_type": component.amount_type,
            "component_type": component.component_type,
            "is_taxable": component.is_taxable,
            "is_statutory": component.is_statutory,
        },
    }


def _workforce_row_default(employee) -> dict:
    return {
        "employee": employee.id,
        "employee_id": employee.employee_id,
        "employee_name": f"{employee.first_name} {employee.last_name}".strip(),
        "present_days": 0,
        "late_days": 0,
        "half_days": 0,
        "overtime_hours": "0.00",
        "approved_leave_days_total": "0.00",
        "approved_leave_by_type": [],
        "blocked_alert_days": 0,
        "blocked_reconciliation_days": 0,
        "blocked_leave_days": 0,
        "open_return_reconciliation_count": 0,
        "is_payroll_ready": False,
        "blocking_reasons": ["Missing workforce readiness summary for employee"],
        "unpaid_absence_days": "0.00",
        "payable_days": "0.00",
    }


def _required_identifier_reasons(profile, statutory_results: list[dict]) -> list[str]:
    reasons = []
    for result in statutory_results:
        field = MANDATORY_IDENTIFIER_FIELDS.get(result["code"])
        if field is None:
            continue
        if result["employee_amount"] <= Decimal("0.00") and result["employer_amount"] <= Decimal("0.00"):
            continue
        field_name, label = field
        if profile is None or not getattr(profile, field_name, "").strip():
            reasons.append(f"Missing {label} required for {result['name']}")
    return reasons


def _build_payroll_item(structure: SalaryStructure, *, payroll: PayrollBatch, workforce_row: dict, statutory_rules: list, profile) -> dict:
    basic_salary = round_money(structure.basic_salary)
    allowance_total = Decimal("0.00")
    other_deduction_total = Decimal("0.00")
    taxable_allowances = Decimal("0.00")
    breakdown_specs = []
    display_order = 1

    for component in structure.components.all():
        amount = _component_amount(component, basic_salary)
        if component.component_type == "Allowance":
            allowance_total += amount
            if component.is_taxable:
                taxable_allowances += amount
        elif component.is_statutory:
            continue
        else:
            other_deduction_total += amount
        if component.component_type == "Allowance" or not component.is_statutory:
            breakdown_specs.append(
                _serialize_component_row(component, amount=amount, basic_salary=basic_salary, display_order=display_order)
            )
            display_order += 1

    overtime_hours = round_money(_as_decimal(workforce_row.get("overtime_hours")))
    overtime_rate = round_money(basic_salary / OVERTIME_MONTHLY_DIVISOR) if basic_salary > 0 else Decimal("0.00")
    overtime_amount = round_money(overtime_rate * overtime_hours)
    if overtime_amount > 0:
        allowance_total += overtime_amount
        taxable_allowances += overtime_amount
        breakdown_specs.append(
            {
                "line_type": "ALLOWANCE",
                "code": "OVERTIME",
                "name": "Overtime",
                "base_amount": overtime_hours,
                "rate": Decimal("0.00"),
                "amount": overtime_amount,
                "display_order": display_order,
                "snapshot": {"hours": str(overtime_hours), "hourly_rate_equivalent": str(overtime_rate)},
            }
        )
        display_order += 1

    days_in_month = Decimal(str(_days_in_month(payroll.year, payroll.month)))
    worked_days = round_money(
        Decimal(str(workforce_row.get("present_days", 0)))
        + Decimal(str(workforce_row.get("late_days", 0)))
        + Decimal(str(workforce_row.get("half_days", 0)))
    )
    unpaid_absence_days = round_money(_as_decimal(workforce_row.get("unpaid_absence_days")))
    attendance_deduction_total = (
        round_money((basic_salary / days_in_month) * unpaid_absence_days)
        if days_in_month > 0 and unpaid_absence_days > 0
        else Decimal("0.00")
    )
    if attendance_deduction_total > 0:
        breakdown_specs.append(
            {
                "line_type": "ATTENDANCE_DEDUCTION",
                "code": "ABSENCE",
                "name": "Unpaid absence deduction",
                "base_amount": basic_salary,
                "rate": Decimal("0.00"),
                "amount": attendance_deduction_total,
                "display_order": display_order,
                "snapshot": {"unpaid_absence_days": str(unpaid_absence_days), "days_in_month": str(days_in_month)},
            }
        )
        display_order += 1

    gross_salary = round_money(basic_salary + allowance_total)
    bases = {
        "BASIC_PAY": round_money(basic_salary),
        "GROSS_PAY": round_money(gross_salary),
        "TAXABLE_PAY": round_money(basic_salary + taxable_allowances),
        "PENSIONABLE_PAY": round_money(basic_salary),
    }
    statutory_result = apply_statutory_rules_to_bases(bases, rules=statutory_rules)
    for result in statutory_result["results"]:
        if result["employee_amount"] > Decimal("0.00"):
            breakdown_specs.append(
                {
                    "line_type": "STATUTORY_EMPLOYEE",
                    "code": result["code"],
                    "name": result["name"],
                    "base_amount": result["base_amount"],
                    "rate": result["applied_rate"],
                    "amount": result["employee_amount"],
                    "display_order": display_order,
                    "snapshot": result["snapshot"],
                }
            )
            display_order += 1
        if result["employer_amount"] > Decimal("0.00"):
            breakdown_specs.append(
                {
                    "line_type": "STATUTORY_EMPLOYER",
                    "code": result["code"],
                    "name": f"{result['name']} (Employer)",
                    "base_amount": result["base_amount"],
                    "rate": result["applied_rate"],
                    "amount": result["employer_amount"],
                    "display_order": display_order,
                    "snapshot": result["snapshot"],
                }
            )
            display_order += 1

    posting_bucket, bucket_reason = _resolve_posting_bucket(structure.employee)
    blocking_reasons = list(workforce_row.get("blocking_reasons", []))
    if bucket_reason:
        blocking_reasons.append(bucket_reason)
    blocking_reasons.extend(_required_identifier_reasons(profile, statutory_result["results"]))
    blocking_reasons = list(dict.fromkeys(reason for reason in blocking_reasons if reason))

    total_deductions = round_money(
        attendance_deduction_total + other_deduction_total + statutory_result["employee_total"]
    )
    net_salary = round_money(gross_salary - total_deductions)
    return {
        "basic_salary": basic_salary,
        "total_allowances": round_money(allowance_total),
        "attendance_deduction_total": attendance_deduction_total,
        "statutory_deduction_total": statutory_result["employee_total"],
        "other_deduction_total": round_money(other_deduction_total),
        "employer_statutory_total": statutory_result["employer_total"],
        "total_deductions": total_deductions,
        "gross_salary": gross_salary,
        "net_salary": net_salary,
        "net_payable": net_salary,
        "days_worked": worked_days,
        "overtime_hours": overtime_hours,
        "posting_bucket": posting_bucket,
        "is_blocked": bool(blocking_reasons),
        "block_reason": _truncate_reason("; ".join(blocking_reasons)),
        "calculation_snapshot": {
            "salary_structure": {
                "id": structure.id,
                "effective_from": structure.effective_from.isoformat(),
                "effective_to": structure.effective_to.isoformat() if structure.effective_to else None,
                "currency": structure.currency,
                "pay_frequency": structure.pay_frequency,
            },
            "workforce": workforce_row,
            "bases": {name: str(value) for name, value in bases.items()},
            "statutory": {
                "employee_total": str(statutory_result["employee_total"]),
                "employer_total": str(statutory_result["employer_total"]),
                "results": [
                    {
                        "code": result["code"],
                        "name": result["name"],
                        "base_name": result["base_name"],
                        "base_amount": str(result["base_amount"]),
                        "employee_amount": str(result["employee_amount"]),
                        "employer_amount": str(result["employer_amount"]),
                        "applied_rate": str(result["applied_rate"]),
                    }
                    for result in statutory_result["results"]
                ],
            },
            "blocking_reasons": blocking_reasons,
        },
        "breakdown_specs": breakdown_specs,
        "blocking_reasons": blocking_reasons,
    }


def _list_payroll_items(payroll: PayrollBatch) -> list[PayrollItem]:
    return list(
        payroll.items.select_related("employee", "employee__department", "employee__position").order_by(
            "employee__employee_id",
            "id",
        )
    )


def reconcile_payroll_batch(payroll: PayrollBatch) -> dict:
    items = _list_payroll_items(payroll)
    item_totals = {
        "gross": round_money(sum((item.gross_salary for item in items), Decimal("0.00"))),
        "deductions": round_money(sum((item.total_deductions for item in items), Decimal("0.00"))),
        "net": round_money(sum((item.net_payable for item in items), Decimal("0.00"))),
    }
    batch_totals = {
        "gross": round_money(payroll.total_gross),
        "deductions": round_money(payroll.total_deductions),
        "net": round_money(payroll.total_net),
    }
    return {
        "item_count": len(items),
        "item_totals": {key: str(value) for key, value in item_totals.items()},
        "batch_totals": {key: str(value) for key, value in batch_totals.items()},
        "is_balanced": item_totals == batch_totals,
    }


def build_payroll_exception_summary(payroll: PayrollBatch) -> dict:
    blocked_items = []
    workforce_blockers = 0
    identifier_blockers = 0
    missing_bucket_blockers = 0

    for item in _list_payroll_items(payroll):
        blocking_reasons = list(item.calculation_snapshot.get("blocking_reasons") or [])
        if not blocking_reasons and item.block_reason:
            blocking_reasons = [item.block_reason]
        missing_bucket = not bool(item.posting_bucket)
        workforce_blocked = any(
            "Missing workforce readiness summary" in reason or "blocked by unresolved" in reason
            for reason in blocking_reasons
        )
        identifier_blocked = any(reason.startswith("Missing ") for reason in blocking_reasons)
        if workforce_blocked:
            workforce_blockers += 1
        if identifier_blocked:
            identifier_blockers += 1
        if missing_bucket:
            missing_bucket_blockers += 1
        if item.is_blocked or blocking_reasons or missing_bucket:
            blocked_items.append(
                {
                    "payroll_item_id": item.id,
                    "employee": item.employee_id,
                    "employee_id": item.employee.employee_id,
                    "employee_name": f"{item.employee.first_name} {item.employee.last_name}".strip(),
                    "posting_bucket": item.posting_bucket,
                    "is_blocked": item.is_blocked,
                    "block_reason": item.block_reason,
                    "blocking_reasons": blocking_reasons,
                    "missing_posting_bucket": missing_bucket,
                }
            )

    reconciliation = reconcile_payroll_batch(payroll)
    exception_count = sum(len(item["blocking_reasons"]) for item in blocked_items)
    return {
        "payroll_id": payroll.id,
        "status": payroll.status,
        "blocked_item_count": len(blocked_items),
        "exception_count": exception_count,
        "workforce_blocker_count": workforce_blockers,
        "missing_identifier_count": identifier_blockers,
        "missing_bucket_count": missing_bucket_blockers,
        "reconciliation": reconciliation,
        "items": blocked_items,
    }


def _finance_approval_failures(payroll: PayrollBatch, *, summary: dict | None = None) -> list[str]:
    exception_summary = summary or build_payroll_exception_summary(payroll)
    errors = []
    if exception_summary["reconciliation"]["item_count"] == 0:
        errors.append("Payroll batch has no payroll items to finance approve.")
    if exception_summary["workforce_blocker_count"] > 0:
        errors.append("Resolve unresolved workforce readiness blockers before finance approval.")
    if exception_summary["missing_identifier_count"] > 0:
        errors.append("Resolve missing mandatory statutory identifiers before finance approval.")
    if exception_summary["missing_bucket_count"] > 0:
        errors.append("Resolve missing payroll posting buckets before finance approval.")
    if exception_summary["blocked_item_count"] > 0 and not errors:
        errors.append("Resolve blocked payroll items before finance approval.")
    if not exception_summary["reconciliation"]["is_balanced"]:
        errors.append("Payroll batch totals do not reconcile with payroll item totals.")
    return errors


@transaction.atomic
def finance_approve_payroll(
    payroll: PayrollBatch,
    *,
    approved_by,
    approval_notes: str = "",
    legacy_status: bool = False,
) -> PayrollBatch:
    if payroll.status in {"Disbursement In Progress", *DISBURSEMENT_FINAL_STATUSES}:
        raise PayrollWorkflowError("Payroll has already moved beyond finance approval.")
    if payroll.status not in FINANCE_APPROVAL_READY_STATUSES:
        raise PayrollWorkflowError("Payroll is not in a state that can be finance approved.")
    if payroll.status in FINANCE_APPROVED_STATUSES and payroll.finance_approved_at:
        raise PayrollWorkflowError("Payroll is already finance approved.")

    exception_summary = build_payroll_exception_summary(payroll)
    errors = _finance_approval_failures(payroll, summary=exception_summary)
    if errors:
        raise PayrollWorkflowError(
            "Payroll cannot be finance approved until all blockers are cleared.",
            details={"errors": errors, "exception_summary": exception_summary},
        )

    now = timezone.now()
    payroll.blocked_item_count = exception_summary["blocked_item_count"]
    payroll.exception_count = exception_summary["exception_count"]
    payroll.finance_approved_by = approved_by
    payroll.finance_approved_at = now
    payroll.approval_notes = approval_notes.strip()
    payroll.status = "Approved" if legacy_status else "Finance Approved"

    update_fields = [
        "blocked_item_count",
        "exception_count",
        "finance_approved_by",
        "finance_approved_at",
        "approval_notes",
        "status",
    ]
    if payroll.approved_by_id is None:
        payroll.approved_by = approved_by
        payroll.approved_at = now
        update_fields.extend(["approved_by", "approved_at"])
    payroll.save(update_fields=update_fields)
    return payroll


def _current_disbursement(payroll: PayrollBatch) -> PayrollDisbursement | None:
    return payroll.disbursements.order_by("-created_at", "-id").first()


@transaction.atomic
def start_payroll_disbursement(
    payroll: PayrollBatch,
    *,
    method: str = "BANK",
    scheduled_date: date | None = None,
    reference: str = "",
    notes: str = "",
) -> tuple[PayrollBatch, PayrollDisbursement]:
    if payroll.status in DISBURSEMENT_FINAL_STATUSES:
        raise PayrollWorkflowError("Payroll has already been disbursed.")
    if payroll.status not in DISBURSEMENT_STARTABLE_STATUSES and payroll.finance_approved_at is None:
        raise PayrollWorkflowError("Finance approval is required before disbursement can start.")

    exception_summary = build_payroll_exception_summary(payroll)
    errors = _finance_approval_failures(payroll, summary=exception_summary)
    if errors:
        raise PayrollWorkflowError(
            "Payroll cannot move into disbursement until the batch is finance safe.",
            details={"errors": errors, "exception_summary": exception_summary},
        )

    disbursement = _current_disbursement(payroll)
    if disbursement and disbursement.status == "COMPLETED":
        raise PayrollWorkflowError("Payroll disbursement is already completed.")
    if disbursement is None:
        disbursement = PayrollDisbursement.objects.create(
            payroll=payroll,
            method=method,
            status="IN_PROGRESS",
            total_amount=payroll.total_net,
            scheduled_date=scheduled_date,
            reference=reference.strip(),
            notes=notes.strip(),
        )
    else:
        disbursement.method = method
        disbursement.status = "IN_PROGRESS"
        disbursement.total_amount = payroll.total_net
        disbursement.scheduled_date = scheduled_date
        disbursement.reference = reference.strip()
        disbursement.notes = notes.strip()
        disbursement.save(
            update_fields=[
                "method",
                "status",
                "total_amount",
                "scheduled_date",
                "reference",
                "notes",
                "updated_at",
            ]
        )

    payroll.status = "Disbursement In Progress"
    payroll.save(update_fields=["status"])
    return payroll, disbursement


@transaction.atomic
def mark_payroll_disbursed(
    payroll: PayrollBatch,
    *,
    disbursed_by,
    disbursed_at=None,
    reference: str = "",
    notes: str = "",
) -> tuple[PayrollBatch, PayrollDisbursement]:
    if payroll.status in DISBURSEMENT_FINAL_STATUSES:
        raise PayrollWorkflowError("Payroll has already been disbursed.")
    if payroll.status != "Disbursement In Progress":
        raise PayrollWorkflowError("Start disbursement before marking the batch as disbursed.")

    disbursement = _current_disbursement(payroll)
    if disbursement is None:
        raise PayrollWorkflowError("No payroll disbursement record exists for this batch.")

    completed_at = disbursed_at or timezone.now()
    disbursement.status = "COMPLETED"
    disbursement.total_amount = payroll.total_net
    disbursement.disbursed_by = disbursed_by
    disbursement.disbursed_at = completed_at
    if reference:
        disbursement.reference = reference.strip()
    if notes:
        disbursement.notes = notes.strip()
    disbursement.save(
        update_fields=[
            "status",
            "total_amount",
            "disbursed_by",
            "disbursed_at",
            "reference",
            "notes",
            "updated_at",
        ]
    )

    payroll.status = "Disbursed"
    payroll.disbursed_by = disbursed_by
    payroll.disbursed_at = completed_at
    payroll.save(update_fields=["status", "disbursed_by", "disbursed_at"])
    return payroll, disbursement


@transaction.atomic
def rebuild_payroll_batch(payroll: PayrollBatch, *, processed_by, payment_date: date | None = None) -> PayrollBatch:
    effective_payment_date = payment_date or payroll.payment_date
    update_fields = ["status", "processed_by"]
    payroll.status = "Processing"
    payroll.processed_by = processed_by
    if effective_payment_date:
        payroll.payment_date = effective_payment_date
        update_fields.append("payment_date")
    payroll.save(update_fields=update_fields)

    PayrollItem.objects.filter(payroll=payroll).delete()
    ensure_kenya_first_statutory_defaults()

    month_start = datetime(payroll.year, payroll.month, 1).date()
    month_end = datetime(payroll.year, payroll.month, _days_in_month(payroll.year, payroll.month)).date()
    structures = _resolve_active_structures(month_start, month_end)
    profiles = {profile.employee_id: profile for profile in EmployeeEmploymentProfile.objects.filter(employee_id__in=[row.employee_id for row in structures])}
    workforce_payload = build_workforce_feed(payroll.month, payroll.year)
    workforce_lookup = {row["employee"]: row for row in workforce_payload["results"]}
    statutory_rules = list(get_active_statutory_rules(as_of_date=effective_payment_date or month_end))

    total_gross = Decimal("0.00")
    total_deductions = Decimal("0.00")
    total_net = Decimal("0.00")
    blocked_item_count = 0
    exception_count = 0
    processed_workforce_rows = []

    for structure in structures:
        workforce_row = workforce_lookup.get(structure.employee_id) or _workforce_row_default(structure.employee)
        processed_workforce_rows.append(workforce_row)
        payload = _build_payroll_item(
            structure,
            payroll=payroll,
            workforce_row=workforce_row,
            statutory_rules=statutory_rules,
            profile=profiles.get(structure.employee_id),
        )
        item = PayrollItem.objects.create(payroll=payroll, employee=structure.employee, is_active=True, **{key: payload[key] for key in [
            "basic_salary",
            "total_allowances",
            "attendance_deduction_total",
            "statutory_deduction_total",
            "other_deduction_total",
            "employer_statutory_total",
            "total_deductions",
            "gross_salary",
            "net_salary",
            "net_payable",
            "days_worked",
            "overtime_hours",
            "posting_bucket",
            "is_blocked",
            "block_reason",
            "calculation_snapshot",
        ]})
        PayrollItemBreakdown.objects.bulk_create(
            [
                PayrollItemBreakdown(payroll_item=item, **row)
                for row in payload["breakdown_specs"]
            ]
        )
        total_gross += payload["gross_salary"]
        total_deductions += payload["total_deductions"]
        total_net += payload["net_payable"]
        if payload["is_blocked"]:
            blocked_item_count += 1
            exception_count += len(payload["blocking_reasons"])

    payroll.total_gross = round_money(total_gross)
    payroll.total_deductions = round_money(total_deductions)
    payroll.total_net = round_money(total_net)
    payroll.blocked_item_count = blocked_item_count
    payroll.exception_count = exception_count
    payroll.workforce_snapshot = {
        "month": payroll.month,
        "year": payroll.year,
        "employee_count": len(processed_workforce_rows),
        "source_employee_count": workforce_payload["employee_count"],
        "generated_at": timezone.now().isoformat(),
        "results": processed_workforce_rows,
    }
    payroll.statutory_snapshot = {
        "as_of_date": (effective_payment_date or month_end).isoformat(),
        "rules": build_statutory_snapshot(statutory_rules),
    }
    payroll.status = "Ready for Finance Approval" if blocked_item_count == 0 else "Draft"
    payroll.save(
        update_fields=[
            "total_gross",
            "total_deductions",
            "total_net",
            "blocked_item_count",
            "exception_count",
            "workforce_snapshot",
            "statutory_snapshot",
            "status",
        ]
    )
    return payroll
