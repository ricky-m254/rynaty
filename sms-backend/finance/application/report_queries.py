from __future__ import annotations

from collections import defaultdict

from django.db.models import Count, Sum
from django.utils import timezone

from school.models import (
    AcademicYear,
    Budget,
    CashbookEntry,
    Expense,
    Invoice,
    InvoiceInstallment,
    Term,
    VoteHead,
    VoteHeadPaymentAllocation,
)
from school.services import FinanceService


def _empty_aging_buckets() -> dict[str, dict[str, float | int]]:
    return {
        "0_30": {"count": 0, "amount": 0.0},
        "31_60": {"count": 0, "amount": 0.0},
        "61_90": {"count": 0, "amount": 0.0},
        "90_plus": {"count": 0, "amount": 0.0},
    }


def _bucket_key_for_overdue_days(overdue_days: int) -> str:
    if overdue_days <= 30:
        return "0_30"
    if overdue_days <= 60:
        return "31_60"
    if overdue_days <= 90:
        return "61_90"
    return "90_plus"


def get_receivables_aging_payload() -> dict[str, object]:
    today = timezone.now().date()
    buckets = _empty_aging_buckets()
    invoices = Invoice.objects.filter(is_active=True).exclude(status="VOID").select_related("student")

    for invoice in invoices:
        FinanceService.sync_invoice_status(invoice)
        balance = float(invoice.balance_due)
        if balance <= 0:
            continue

        overdue_days = max(0, (today - invoice.due_date).days)
        key = _bucket_key_for_overdue_days(overdue_days)
        buckets[key]["count"] += 1
        buckets[key]["amount"] += balance

    for key in buckets:
        buckets[key]["amount"] = round(buckets[key]["amount"], 2)

    return {"as_of": str(today), "buckets": buckets}


def get_overdue_accounts_payload(*, search: str) -> dict[str, object]:
    today = timezone.now().date()
    normalized_search = search.strip().lower()
    rows: list[dict[str, object]] = []
    invoices = (
        Invoice.objects.filter(is_active=True)
        .exclude(status="VOID")
        .select_related("student")
        .order_by("due_date", "id")
    )

    for invoice in invoices:
        FinanceService.sync_invoice_status(invoice)
        balance = float(invoice.balance_due)
        if balance <= 0:
            continue

        overdue_days = max(0, (today - invoice.due_date).days)
        if overdue_days <= 0 and invoice.status not in {"OVERDUE", "PARTIALLY_PAID", "ISSUED", "CONFIRMED"}:
            continue

        student_name = f"{invoice.student.first_name} {invoice.student.last_name}".strip()
        row = {
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number or f"INV-{invoice.id}",
            "student_id": invoice.student_id,
            "student_name": student_name,
            "admission_number": invoice.student.admission_number,
            "due_date": str(invoice.due_date),
            "status": invoice.status,
            "balance_due": round(balance, 2),
            "overdue_days": overdue_days,
        }
        searchable = f"{row['invoice_number']} {row['student_name']} {row['admission_number']}".lower()
        if normalized_search and normalized_search not in searchable:
            continue
        rows.append(row)

    return {"count": len(rows), "results": rows}


def get_installment_aging_payload() -> dict[str, object]:
    today = timezone.now().date()
    buckets = _empty_aging_buckets()
    installments = InvoiceInstallment.objects.select_related("plan__invoice").exclude(status="WAIVED")

    for installment in installments:
        if installment.status == "PAID":
            continue

        overdue_days = max(0, (today - installment.due_date).days)
        key = _bucket_key_for_overdue_days(overdue_days)
        buckets[key]["count"] += 1
        buckets[key]["amount"] += float(installment.amount)

    for key in buckets:
        buckets[key]["amount"] = round(buckets[key]["amount"], 2)

    return {"as_of": str(today), "buckets": buckets}


def get_arrears_payload(*, term_id: str | None, group_by: str) -> dict[str, object]:
    invoices_qs = Invoice.objects.filter(is_active=True).exclude(status__in=["PAID", "VOID"])
    if term_id:
        invoices_qs = invoices_qs.filter(term_id=term_id)

    rows: list[dict[str, object]] = []
    for invoice in invoices_qs.select_related("student", "term"):
        balance = float(invoice.balance_due)
        if balance <= 0:
            continue

        enrollment = invoice.student.enrollment_set.filter(is_active=True).select_related("school_class").first()
        class_name = enrollment.school_class.name if enrollment and enrollment.school_class else "N/A"
        rows.append(
            {
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "student_id": invoice.student.id,
                "student_name": f"{invoice.student.first_name} {invoice.student.last_name}".strip(),
                "admission_number": invoice.student.admission_number,
                "class_name": class_name,
                "term": invoice.term.name if invoice.term else "",
                "total_amount": float(invoice.total_amount),
                "balance_due": balance,
                "due_date": str(invoice.due_date),
                "status": invoice.status,
            }
        )

    if group_by == "class":
        grouped = defaultdict(
            lambda: {"class_name": "", "student_count": 0, "total_balance": 0.0, "invoices": []}
        )
        for row in rows:
            key = row["class_name"]
            grouped[key]["class_name"] = key
            grouped[key]["student_count"] += 1
            grouped[key]["total_balance"] += row["balance_due"]
            grouped[key]["invoices"].append(row)
        return {"group_by": "class", "data": list(grouped.values())}

    return {"group_by": "student", "count": len(rows), "results": rows}


def get_class_balances_payload(*, term_id: str | None) -> dict[str, object]:
    invoices_qs = Invoice.objects.filter(is_active=True)
    if term_id:
        invoices_qs = invoices_qs.filter(term_id=term_id)

    class_data = defaultdict(
        lambda: {
            "class_name": "",
            "student_count": 0,
            "total_billed": 0.0,
            "total_paid": 0.0,
            "total_outstanding": 0.0,
        }
    )

    for invoice in invoices_qs.select_related("student"):
        enrollment = invoice.student.enrollment_set.filter(is_active=True).select_related("school_class").first()
        class_name = enrollment.school_class.name if enrollment and enrollment.school_class else "Unassigned"
        balance = float(invoice.balance_due)
        class_data[class_name]["class_name"] = class_name
        class_data[class_name]["total_billed"] += float(invoice.total_amount)
        class_data[class_name]["total_paid"] += float(invoice.total_amount) - balance
        class_data[class_name]["total_outstanding"] += max(balance, 0)

    student_counts = defaultdict(set)
    for invoice in invoices_qs.select_related("student"):
        enrollment = invoice.student.enrollment_set.filter(is_active=True).select_related("school_class").first()
        class_name = enrollment.school_class.name if enrollment and enrollment.school_class else "Unassigned"
        student_counts[class_name].add(invoice.student_id)

    for class_name, students in student_counts.items():
        class_data[class_name]["student_count"] = len(students)

    return {
        "term_id": term_id,
        "rows": sorted(class_data.values(), key=lambda row: row["class_name"]),
    }


def get_arrears_by_term_payload() -> dict[str, object]:
    invoices_qs = Invoice.objects.filter(is_active=True).exclude(status__in=["PAID", "VOID"])
    term_data = defaultdict(
        lambda: {
            "term_id": None,
            "term_name": "",
            "student_count": 0,
            "total_outstanding": 0.0,
            "invoice_count": 0,
        }
    )

    for invoice in invoices_qs.select_related("term"):
        balance = float(invoice.balance_due)
        if balance <= 0:
            continue
        key = invoice.term_id
        term_data[key]["term_id"] = invoice.term_id
        term_data[key]["term_name"] = invoice.term.name if invoice.term else "N/A"
        term_data[key]["total_outstanding"] += balance
        term_data[key]["invoice_count"] += 1

    student_counts = defaultdict(set)
    for invoice in invoices_qs.select_related("term"):
        if float(invoice.balance_due) > 0:
            student_counts[invoice.term_id].add(invoice.student_id)

    for term_id, students in student_counts.items():
        term_data[term_id]["student_count"] = len(students)

    return {"rows": sorted(term_data.values(), key=lambda row: row["term_name"])}


def get_financial_summary_payload() -> dict[str, object]:
    return FinanceService.get_summary()


def get_cashbook_summary_payload() -> dict[str, object]:
    result: dict[str, dict[str, float | int]] = {}
    for book_type in ["CASH", "BANK"]:
        entries = CashbookEntry.objects.filter(book_type=book_type).order_by("entry_date", "created_at")
        total_in = entries.aggregate(t=Sum("amount_in"))["t"] or 0
        total_out = entries.aggregate(t=Sum("amount_out"))["t"] or 0
        closing = entries.last()
        opening = entries.filter(entry_type="OPENING").first()
        result[book_type.lower()] = {
            "total_in": float(total_in),
            "total_out": float(total_out),
            "closing_balance": float(closing.running_balance) if closing else 0.0,
            "opening_balance": float(opening.amount_in) if opening else 0.0,
            "entry_count": entries.count(),
        }
    return result


def get_vote_head_allocation_payload(*, date_from: str | None, date_to: str | None) -> dict[str, object]:
    qs = VoteHeadPaymentAllocation.objects.select_related("vote_head", "payment")
    if date_from:
        qs = qs.filter(payment__payment_date__date__gte=date_from)
    if date_to:
        qs = qs.filter(payment__payment_date__date__lte=date_to)

    totals = (
        qs.values("vote_head__id", "vote_head__name")
        .annotate(total_allocated=Sum("amount"), transaction_count=Count("id"))
        .order_by("vote_head__order", "vote_head__name")
    )

    grand_total = sum(float(row["total_allocated"] or 0) for row in totals)

    return {
        "date_from": date_from,
        "date_to": date_to,
        "grand_total": grand_total,
        "rows": [
            {
                "vote_head_id": row["vote_head__id"],
                "vote_head_name": row["vote_head__name"],
                "total_allocated": float(row["total_allocated"] or 0),
                "transaction_count": row["transaction_count"],
                "percentage_of_total": round(float(row["total_allocated"] or 0) / grand_total * 100, 2)
                if grand_total
                else 0,
            }
            for row in totals
        ],
    }


def get_vote_head_budget_payload(*, date_from: str | None, date_to: str | None) -> dict[str, object]:
    total_annual_budget = float(
        Budget.objects.filter(is_active=True).aggregate(total=Sum("annual_budget"))["total"] or 0
    )

    allocations_qs = VoteHeadPaymentAllocation.objects.select_related("vote_head")
    if date_from:
        allocations_qs = allocations_qs.filter(payment__payment_date__date__gte=date_from)
    if date_to:
        allocations_qs = allocations_qs.filter(payment__payment_date__date__lte=date_to)

    totals = (
        allocations_qs.values(
            "vote_head__id",
            "vote_head__name",
            "vote_head__allocation_percentage",
            "vote_head__order",
        )
        .annotate(actual_collected=Sum("amount"))
        .order_by("vote_head__order", "vote_head__name")
    )

    all_vote_heads = {vote_head.id: vote_head for vote_head in VoteHead.objects.filter(is_active=True)}
    rows: list[dict[str, object]] = []
    seen_ids = set()

    for row in totals:
        vote_head_id = row["vote_head__id"]
        seen_ids.add(vote_head_id)
        allocation_percentage = float(row["vote_head__allocation_percentage"] or 0)
        budgeted_amount = round(total_annual_budget * allocation_percentage / 100, 2)
        actual_collected = round(float(row["actual_collected"] or 0), 2)
        variance = round(actual_collected - budgeted_amount, 2)
        rows.append(
            {
                "vote_head_id": vote_head_id,
                "vote_head_name": row["vote_head__name"],
                "allocation_percentage": allocation_percentage,
                "budgeted_amount": budgeted_amount,
                "actual_collected": actual_collected,
                "variance": variance,
                "utilization_pct": round(actual_collected / budgeted_amount * 100, 2)
                if budgeted_amount > 0
                else None,
                "status": "OVER" if actual_collected > budgeted_amount else "UNDER",
            }
        )

    for vote_head_id, vote_head in all_vote_heads.items():
        if vote_head_id not in seen_ids:
            allocation_percentage = float(vote_head.allocation_percentage or 0)
            budgeted_amount = round(total_annual_budget * allocation_percentage / 100, 2)
            rows.append(
                {
                    "vote_head_id": vote_head.id,
                    "vote_head_name": vote_head.name,
                    "allocation_percentage": allocation_percentage,
                    "budgeted_amount": budgeted_amount,
                    "actual_collected": 0.0,
                    "variance": round(-budgeted_amount, 2),
                    "utilization_pct": 0.0 if budgeted_amount > 0 else None,
                    "status": "UNDER",
                }
            )

    rows.sort(key=lambda row: row["allocation_percentage"], reverse=True)
    total_budgeted = sum(row["budgeted_amount"] for row in rows)
    total_actual = sum(row["actual_collected"] for row in rows)

    return {
        "date_from": date_from,
        "date_to": date_to,
        "total_annual_budget": total_annual_budget,
        "total_budgeted_via_allocation": round(total_budgeted, 2),
        "total_actual_collected": round(total_actual, 2),
        "overall_variance": round(total_actual - total_budgeted, 2),
        "overall_utilization_pct": round(total_actual / total_budgeted * 100, 2) if total_budgeted > 0 else None,
        "rows": rows,
    }


def get_budget_variance_payload(*, academic_year: str | None, term: str | None) -> dict[str, object]:
    budgets_qs = Budget.objects.filter(is_active=True)
    if academic_year:
        budgets_qs = budgets_qs.filter(academic_year_id=academic_year)
    if term:
        budgets_qs = budgets_qs.filter(term_id=term)

    expenses_qs = Expense.objects.all()
    if term:
        try:
            term_obj = Term.objects.get(id=term)
            expenses_qs = expenses_qs.filter(
                expense_date__gte=term_obj.start_date,
                expense_date__lte=term_obj.end_date,
            )
        except Exception:
            pass
    elif academic_year:
        try:
            year_obj = AcademicYear.objects.get(id=academic_year)
            expenses_qs = expenses_qs.filter(
                expense_date__gte=year_obj.start_date,
                expense_date__lte=year_obj.end_date,
            )
        except Exception:
            pass

    expense_by_category = defaultdict(float)
    for expense in expenses_qs:
        expense_by_category[expense.category] += float(expense.amount or 0)

    total_actual = sum(expense_by_category.values())

    rows = []
    for budget in budgets_qs.select_related("academic_year", "term"):
        annual = float(budget.annual_budget or 0)
        monthly = float(budget.monthly_budget or 0)
        quarterly = float(budget.quarterly_budget or 0)
        variance = annual - total_actual
        utilization_pct = round((total_actual / annual * 100), 1) if annual > 0 else None
        rows.append(
            {
                "budget_id": budget.id,
                "academic_year": budget.academic_year.name,
                "term": budget.term.name,
                "monthly_budget": monthly,
                "quarterly_budget": quarterly,
                "annual_budget": annual,
                "total_actual_spend": round(total_actual, 2),
                "variance": round(variance, 2),
                "utilization_pct": utilization_pct,
                "status": "UNDER" if variance >= 0 else "OVER",
            }
        )

    by_category = [
        {"category": category, "actual": round(amount, 2)}
        for category, amount in sorted(expense_by_category.items(), key=lambda item: -item[1])
    ]

    return {
        "rows": rows,
        "by_category": by_category,
        "total_actual": round(total_actual, 2),
    }
