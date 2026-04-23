from decimal import Decimal

from django.db import models
from django.db.models import Sum

from school.models import (
    BalanceCarryForward,
    ChartOfAccount,
    Invoice,
    InvoiceAdjustment,
    InvoiceWriteOffRequest,
    JournalEntry,
    JournalLine,
    Payment,
    PaymentReversalRequest,
    SchoolProfile,
    Student,
)

import logging

logger = logging.getLogger(__name__)


def _role_name(user):
    profile = getattr(user, "userprofile", None)
    role = getattr(profile, "role", None)
    return getattr(role, "name", "")


def is_admin_like(user):
    return _role_name(user) in {
        "ADMIN",
        "TENANT_SUPER_ADMIN",
        "PRINCIPAL",
        "DEPUTY_PRINCIPAL",
        "DIRECTOR",
    }


def approval_threshold():
    return 10000


def get_invoice_queryset(search=None, status_param=None, student=None, date_from=None, date_to=None):
    queryset = Invoice.objects.filter(is_active=True).select_related("student", "term")

    if status_param:
        queryset = queryset.filter(status=status_param)
    if student:
        queryset = queryset.filter(student_id=student)
    if date_from:
        queryset = queryset.filter(invoice_date__gte=date_from)
    if date_to:
        queryset = queryset.filter(invoice_date__lte=date_to)
    if search:
        query = (
            models.Q(student__admission_number__icontains=search)
            | models.Q(student__first_name__icontains=search)
            | models.Q(student__last_name__icontains=search)
        )
        digits = "".join(ch for ch in str(search) if ch.isdigit())
        if digits:
            query |= models.Q(id=int(digits))
        queryset = queryset.filter(query)

    return queryset.order_by("-invoice_date", "-id")


def get_payment_queryset(
    search=None,
    student=None,
    payment_method=None,
    allocation_status=None,
    date_from=None,
    date_to=None,
):
    queryset = Payment.objects.filter(is_active=True).select_related("student").prefetch_related(
        "allocations__invoice",
        "vote_head_allocations__vote_head",
    )

    if student:
        queryset = queryset.filter(student_id=student)
    if payment_method:
        queryset = queryset.filter(payment_method=payment_method)
    if date_from:
        queryset = queryset.filter(payment_date__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(payment_date__date__lte=date_to)
    if search:
        queryset = queryset.filter(
            models.Q(reference_number__icontains=search)
            | models.Q(receipt_number__icontains=search)
            | models.Q(invoice_number__icontains=search)
            | models.Q(payment_method__icontains=search)
            | models.Q(student__first_name__icontains=search)
            | models.Q(student__last_name__icontains=search)
            | models.Q(student__admission_number__icontains=search)
            | models.Q(allocations__invoice__invoice_number__icontains=search)
        ).distinct()
    if allocation_status in {"allocated", "partial", "unallocated"}:
        queryset = queryset.annotate(allocated_total=Sum("allocations__amount_allocated"))
        if allocation_status == "allocated":
            queryset = queryset.filter(allocated_total__gte=models.F("amount"))
        elif allocation_status == "partial":
            queryset = queryset.filter(
                allocated_total__gt=0,
                allocated_total__lt=models.F("amount"),
            )
        elif allocation_status == "unallocated":
            queryset = queryset.filter(
                models.Q(allocated_total__isnull=True) | models.Q(allocated_total=0)
            )

    return queryset.order_by("-payment_date", "-id")


def get_invoice_adjustment_queryset(
    search=None,
    invoice=None,
    min_amount=None,
    max_amount=None,
    date_from=None,
    date_to=None,
    status_filter=None,
):
    queryset = InvoiceAdjustment.objects.all().select_related("adjusted_by", "reviewed_by")

    if search:
        query = models.Q(reason__icontains=search)
        if str(search).isdigit():
            query |= models.Q(invoice_id=int(search))
        queryset = queryset.filter(query)
    if invoice:
        queryset = queryset.filter(invoice_id=invoice)
    if min_amount:
        queryset = queryset.filter(amount__gte=min_amount)
    if max_amount:
        queryset = queryset.filter(amount__lte=max_amount)
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)
    if status_filter:
        queryset = queryset.filter(status=status_filter.upper())

    return queryset.order_by("-created_at", "-id")


def get_payment_reversal_request_queryset(status_param=None, payment_id=None, search=None):
    queryset = PaymentReversalRequest.objects.all().select_related("payment", "requested_by", "reviewed_by")

    if status_param:
        queryset = queryset.filter(status=status_param.upper())
    if payment_id:
        queryset = queryset.filter(payment_id=payment_id)
    if search:
        queryset = queryset.filter(
            models.Q(reason__icontains=search)
            | models.Q(payment__reference_number__icontains=search)
            | models.Q(payment__receipt_number__icontains=search)
            | models.Q(payment__student__admission_number__icontains=search)
            | models.Q(payment__student__first_name__icontains=search)
            | models.Q(payment__student__last_name__icontains=search)
        )

    return queryset.order_by("-requested_at")


def get_invoice_writeoff_request_queryset(status_param=None, invoice=None, search=None):
    queryset = InvoiceWriteOffRequest.objects.all().select_related(
        "invoice__student",
        "requested_by",
        "reviewed_by",
        "applied_adjustment",
    )

    if status_param:
        queryset = queryset.filter(status=status_param.upper())
    if invoice:
        queryset = queryset.filter(invoice_id=invoice)
    if search:
        queryset = queryset.filter(
            models.Q(reason__icontains=search)
            | models.Q(invoice__invoice_number__icontains=search)
            | models.Q(invoice__student__admission_number__icontains=search)
            | models.Q(invoice__student__first_name__icontains=search)
            | models.Q(invoice__student__last_name__icontains=search)
        )

    return queryset.order_by("-requested_at", "-id")


def journal_get_or_create_account(code, name, account_type):
    account, _ = ChartOfAccount.objects.get_or_create(
        code=code,
        defaults={
            "name": name,
            "account_type": account_type,
            "is_active": True,
        },
    )
    return account


def auto_post_journal(entry_key, entry_date, memo, source_type, source_id, lines):
    try:
        if JournalEntry.objects.filter(entry_key=entry_key).exists():
            return
        if any(account is None for account, _, _, _ in lines):
            return

        entry = JournalEntry.objects.create(
            entry_date=entry_date,
            memo=memo,
            source_type=source_type,
            source_id=source_id,
            entry_key=entry_key,
        )
        for account, debit, credit, description in lines:
            JournalLine.objects.create(
                entry=entry,
                account=account,
                debit=debit,
                credit=credit,
                description=description,
            )
    except Exception:
        logger.warning("Caught and logged", exc_info=True)


def resolve_tenant_pdf_meta(request):
    profile = SchoolProfile.objects.filter(is_active=True).first()
    tenant = getattr(request, "tenant", None)
    return {
        "school_name": (profile.school_name if profile else None)
        or getattr(tenant, "name", None)
        or getattr(tenant, "schema_name", "Tenant"),
        "address": profile.address if profile else "",
        "phone": profile.phone if profile else "",
        "logo_path": profile.logo.path if profile and profile.logo else None,
        "schema": getattr(tenant, "schema_name", None),
    }


def safe_cell(value):
    if value is None:
        return ""
    return str(value)


def get_student_ledger_payload(student_id, term_id=None, date_from=None, date_to=None):
    student = Student.objects.filter(id=student_id).first()
    if student is None:
        raise LookupError("Student not found.")

    entries = []

    invoice_queryset = Invoice.objects.filter(student=student, is_active=True)
    if term_id:
        invoice_queryset = invoice_queryset.filter(term_id=term_id)
    if date_from:
        invoice_queryset = invoice_queryset.filter(invoice_date__gte=date_from)
    if date_to:
        invoice_queryset = invoice_queryset.filter(invoice_date__lte=date_to)
    for invoice in invoice_queryset.select_related("term").order_by("invoice_date", "id"):
        entries.append(
            {
                "date": str(invoice.invoice_date),
                "type": "INVOICE",
                "reference": invoice.invoice_number or f"INV-{invoice.id}",
                "description": f"Invoice \u2013 {invoice.term.name if invoice.term else ''}",
                "debit": float(invoice.total_amount),
                "credit": 0.0,
                "term": invoice.term.name if invoice.term else "",
                "status": invoice.status,
                "invoice_id": invoice.id,
            }
        )

    payment_queryset = Payment.objects.filter(student=student, is_active=True)
    if date_from:
        payment_queryset = payment_queryset.filter(payment_date__date__gte=date_from)
    if date_to:
        payment_queryset = payment_queryset.filter(payment_date__date__lte=date_to)
    for payment in payment_queryset.order_by("payment_date", "id"):
        payment_date = payment.payment_date.date() if hasattr(payment.payment_date, "date") else payment.payment_date
        entries.append(
            {
                "date": str(payment_date),
                "type": "PAYMENT",
                "reference": payment.receipt_number or payment.reference_number,
                "description": f"Payment \u2013 {payment.payment_method}",
                "debit": 0.0,
                "credit": float(payment.amount),
                "term": "",
                "status": "REVERSED" if payment.reversed_at else "ACTIVE",
                "payment_id": payment.id,
            }
        )

    adjustment_queryset = InvoiceAdjustment.objects.filter(invoice__student=student)
    if date_from:
        adjustment_queryset = adjustment_queryset.filter(created_at__date__gte=date_from)
    if date_to:
        adjustment_queryset = adjustment_queryset.filter(created_at__date__lte=date_to)
    for adjustment in adjustment_queryset.select_related("invoice").order_by("created_at", "id"):
        signed = float(adjustment.signed_amount)
        adjustment_date = adjustment.created_at.date() if hasattr(adjustment.created_at, "date") else adjustment.created_at
        entries.append(
            {
                "date": str(adjustment_date),
                "type": "ADJUSTMENT",
                "reference": f"ADJ-{adjustment.id}",
                "description": (
                    f"{adjustment.adjustment_type} \u2013 {adjustment.reason[:60] if adjustment.reason else ''}"
                ),
                "debit": max(-signed, 0.0),
                "credit": max(signed, 0.0),
                "term": "",
                "status": "POSTED",
            }
        )

    carry_forward_queryset = BalanceCarryForward.objects.filter(student=student)
    if term_id:
        carry_forward_queryset = carry_forward_queryset.filter(to_term_id=term_id)
    for carry_forward in carry_forward_queryset.select_related("from_term", "to_term").order_by("created_at"):
        carry_forward_date = (
            carry_forward.created_at.date()
            if hasattr(carry_forward.created_at, "date")
            else carry_forward.created_at
        )
        entries.append(
            {
                "date": str(carry_forward_date),
                "type": "CARRY_FORWARD",
                "reference": f"CF-{carry_forward.id}",
                "description": (
                    f"Balance carried forward from {carry_forward.from_term.name} \u2192 {carry_forward.to_term.name}"
                ),
                "debit": float(carry_forward.amount),
                "credit": 0.0,
                "term": carry_forward.to_term.name if carry_forward.to_term else "",
                "status": "POSTED",
            }
        )

    entries.sort(key=lambda entry: entry["date"])

    balance = Decimal("0.00")
    for entry in entries:
        balance += Decimal(str(entry["debit"])) - Decimal(str(entry["credit"]))
        entry["balance"] = float(balance)

    enrollment = student.enrollment_set.filter(is_active=True).select_related("school_class", "term").first()
    student_data = {
        "id": student.id,
        "name": f"{student.first_name} {student.last_name}".strip(),
        "admission_number": student.admission_number,
        "class_name": enrollment.school_class.name if enrollment and enrollment.school_class else "N/A",
        "current_term": enrollment.term.name if enrollment and enrollment.term else "N/A",
    }

    return {
        "student": student_data,
        "entry_count": len(entries),
        "closing_balance": float(balance),
        "entries": entries,
    }
