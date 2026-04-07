from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from school.models import ChartOfAccount, VoteHead
from school.services import FinanceService

from ..models import PayrollBatch, PayrollFinancePosting
from .payroll_operations import PayrollWorkflowError, build_payroll_exception_summary
from .statutory_rules import round_money

PAYROLL_VOTE_HEADS = {
    "TEACHING_SALARIES": {
        "name": "Teaching Salaries",
        "description": "Payroll teaching salary expense bucket",
        "order": 100,
    },
    "OPERATIONS_SALARIES": {
        "name": "Operations Salaries",
        "description": "Payroll operations salary expense bucket",
        "order": 110,
    },
    "SUPPORT_SALARIES": {
        "name": "Support Salaries",
        "description": "Payroll support salary expense bucket",
        "order": 120,
    },
    "STATUTORY_LIABILITIES": {
        "name": "Statutory Liabilities",
        "description": "Payroll statutory liabilities control bucket",
        "order": 130,
    },
    "NET_PAYROLL_PAYABLE": {
        "name": "Net Payroll Payable",
        "description": "Payroll net pay control bucket",
        "order": 140,
    },
}

PAYROLL_ACCOUNT_DEFINITIONS = {
    "TEACHING_SALARIES": ("5101", "Teaching Salary Expense", "EXPENSE"),
    "OPERATIONS_SALARIES": ("5102", "Operations Salary Expense", "EXPENSE"),
    "SUPPORT_SALARIES": ("5103", "Support Salary Expense", "EXPENSE"),
    "STATUTORY_LIABILITIES": ("2101", "Statutory Liabilities", "LIABILITY"),
    "NET_PAYROLL_PAYABLE": ("2102", "Net Payroll Payable", "LIABILITY"),
    "CASH_BANK": ("1000", "Cash/Bank", "ASSET"),
}

DISBURSEMENT_BOOK_TYPE = {
    "BANK": "BANK",
    "CASH": "CASH",
    "MOBILE": "BANK",
    "MIXED": "BANK",
}


def ensure_payroll_vote_heads() -> dict[str, VoteHead]:
    vote_heads = {}
    for key, config in PAYROLL_VOTE_HEADS.items():
        vote_head, _ = VoteHead.objects.get_or_create(
            name=config["name"],
            defaults={
                "description": config["description"],
                "allocation_percentage": Decimal("0.00"),
                "is_preloaded": False,
                "is_active": True,
                "order": config["order"],
            },
        )
        dirty = []
        if not vote_head.is_active:
            vote_head.is_active = True
            dirty.append("is_active")
        if not vote_head.description:
            vote_head.description = config["description"]
            dirty.append("description")
        if vote_head.order != config["order"]:
            vote_head.order = config["order"]
            dirty.append("order")
        if dirty:
            vote_head.save(update_fields=dirty)
        vote_heads[key] = vote_head
    return vote_heads


def ensure_payroll_accounts() -> dict[str, ChartOfAccount]:
    accounts = {}
    for key, (code, name, account_type) in PAYROLL_ACCOUNT_DEFINITIONS.items():
        account, _ = ChartOfAccount.objects.get_or_create(
            code=code,
            defaults={"name": name, "account_type": account_type, "is_active": True},
        )
        dirty = []
        if account.name != name:
            account.name = name
            dirty.append("name")
        if account.account_type != account_type:
            account.account_type = account_type
            dirty.append("account_type")
        if not account.is_active:
            account.is_active = True
            dirty.append("is_active")
        if dirty:
            account.save(update_fields=dirty)
        accounts[key] = account
    return accounts


def _posting_entry_key(payroll: PayrollBatch, stage: str) -> str:
    return f"hr_payroll:{payroll.year}:{payroll.month:02d}:{payroll.id}:{stage.lower()}"


def _latest_completed_disbursement(payroll: PayrollBatch):
    return payroll.disbursements.filter(status="COMPLETED").order_by("-disbursed_at", "-created_at", "-id").first()


def _posting_entry_date(payroll: PayrollBatch, *, entry_date: date | None, completed_disbursement) -> date:
    if entry_date:
        return entry_date
    if payroll.payment_date:
        return payroll.payment_date
    if completed_disbursement and completed_disbursement.disbursed_at:
        return completed_disbursement.disbursed_at.date()
    if completed_disbursement and completed_disbursement.scheduled_date:
        return completed_disbursement.scheduled_date
    return timezone.now().date()


def _calculate_accrual_summary(payroll: PayrollBatch) -> dict:
    bucket_totals = defaultdict(lambda: Decimal("0.00"))
    statutory_liability_total = Decimal("0.00")
    net_payable_total = Decimal("0.00")

    items = list(payroll.items.order_by("employee__employee_id", "id"))
    if not items:
        raise PayrollWorkflowError("Payroll batch has no payroll items to post.")

    for item in items:
        bucket_amount = round_money(item.net_payable + item.statutory_deduction_total + item.employer_statutory_total)
        bucket_totals[item.posting_bucket] += bucket_amount
        statutory_liability_total += round_money(item.statutory_deduction_total + item.employer_statutory_total)
        net_payable_total += round_money(item.net_payable)

    bucket_totals = {key: round_money(value) for key, value in bucket_totals.items() if value != Decimal("0.00")}
    statutory_liability_total = round_money(statutory_liability_total)
    net_payable_total = round_money(net_payable_total)
    expense_total = round_money(sum(bucket_totals.values(), Decimal("0.00")))

    return {
        "bucket_totals": bucket_totals,
        "statutory_liability_total": statutory_liability_total,
        "net_payable_total": net_payable_total,
        "expense_total": expense_total,
    }


def _posting_summary_payload(payroll: PayrollBatch) -> dict:
    payload = {
        "payroll_id": payroll.id,
        "status": payroll.status,
        "finance_approved_at": payroll.finance_approved_at.isoformat() if payroll.finance_approved_at else None,
        "disbursed_at": payroll.disbursed_at.isoformat() if payroll.disbursed_at else None,
        "posted_at": payroll.posted_at.isoformat() if payroll.posted_at else None,
        "postings": [],
    }
    for posting in payroll.finance_postings.select_related("journal_entry", "cashbook_entry").order_by("posting_stage", "id"):
        payload["postings"].append(
            {
                "posting_stage": posting.posting_stage,
                "status": posting.status,
                "entry_key": posting.entry_key,
                "journal_entry_id": posting.journal_entry_id,
                "cashbook_entry_id": posting.cashbook_entry_id,
                "posted_at": posting.posted_at.isoformat() if posting.posted_at else None,
                "vote_head_summary": posting.vote_head_summary,
                "error_message": posting.error_message,
            }
        )
    return payload


def build_payroll_posting_summary(payroll: PayrollBatch) -> dict:
    completed_disbursement = _latest_completed_disbursement(payroll)
    exception_summary = build_payroll_exception_summary(payroll)
    payload = _posting_summary_payload(payroll)
    payload.update(
        {
            "has_completed_disbursement": completed_disbursement is not None,
            "latest_disbursement": (
                {
                    "id": completed_disbursement.id,
                    "method": completed_disbursement.method,
                    "status": completed_disbursement.status,
                    "reference": completed_disbursement.reference,
                    "total_amount": str(completed_disbursement.total_amount),
                    "disbursed_at": completed_disbursement.disbursed_at.isoformat() if completed_disbursement.disbursed_at else None,
                }
                if completed_disbursement
                else None
            ),
            "exception_summary": exception_summary,
            "can_post_to_finance": (
                payroll.finance_approved_at is not None
                and completed_disbursement is not None
                and exception_summary["blocked_item_count"] == 0
                and exception_summary["reconciliation"]["is_balanced"]
            ),
        }
    )
    return payload


def _upsert_posting_record(
    payroll: PayrollBatch,
    *,
    stage: str,
    entry_key: str,
    journal_entry,
    cashbook_entry,
    posted_by,
    vote_head_summary: dict,
):
    posting = PayrollFinancePosting.objects.filter(payroll=payroll, posting_stage=stage).first()
    now = timezone.now()
    if posting is None:
        posting = PayrollFinancePosting.objects.create(
            payroll=payroll,
            posting_stage=stage,
            entry_key=entry_key,
            status="POSTED",
            journal_entry=journal_entry,
            cashbook_entry=cashbook_entry,
            posted_by=posted_by,
            posted_at=now,
            vote_head_summary=vote_head_summary,
        )
        return posting

    update_fields = []
    if posting.entry_key != entry_key:
        posting.entry_key = entry_key
        update_fields.append("entry_key")
    if posting.status != "POSTED":
        posting.status = "POSTED"
        update_fields.append("status")
    if posting.journal_entry_id != getattr(journal_entry, "id", None):
        posting.journal_entry = journal_entry
        update_fields.append("journal_entry")
    if posting.cashbook_entry_id != getattr(cashbook_entry, "id", None):
        posting.cashbook_entry = cashbook_entry
        update_fields.append("cashbook_entry")
    if posting.posted_by_id is None:
        posting.posted_by = posted_by
        update_fields.append("posted_by")
    if posting.posted_at is None:
        posting.posted_at = now
        update_fields.append("posted_at")
    if posting.vote_head_summary != vote_head_summary:
        posting.vote_head_summary = vote_head_summary
        update_fields.append("vote_head_summary")
    if posting.error_message:
        posting.error_message = ""
        update_fields.append("error_message")
    if update_fields:
        posting.save(update_fields=update_fields)
    return posting


def _validate_postable_payroll(payroll: PayrollBatch):
    if payroll.finance_approved_at is None:
        raise PayrollWorkflowError("Payroll must be finance approved before it can post to finance.")
    if payroll.status not in {"Disbursed", "Finance Posted"}:
        raise PayrollWorkflowError("Payroll must be disbursed before it can post to finance.")

    completed_disbursement = _latest_completed_disbursement(payroll)
    if completed_disbursement is None:
        raise PayrollWorkflowError("A completed payroll disbursement record is required before finance posting.")

    exception_summary = build_payroll_exception_summary(payroll)
    if exception_summary["blocked_item_count"] > 0:
        raise PayrollWorkflowError(
            "Resolve blocked payroll items before finance posting.",
            details={"exception_summary": exception_summary},
        )
    if not exception_summary["reconciliation"]["is_balanced"]:
        raise PayrollWorkflowError(
            "Payroll batch totals do not reconcile with payroll item totals.",
            details={"exception_summary": exception_summary},
        )

    return completed_disbursement, exception_summary


@transaction.atomic
def post_payroll_to_finance(
    payroll: PayrollBatch,
    *,
    posted_by,
    entry_date: date | None = None,
) -> PayrollBatch:
    completed_disbursement, _ = _validate_postable_payroll(payroll)
    accounts = ensure_payroll_accounts()
    vote_heads = ensure_payroll_vote_heads()
    accrual_summary = _calculate_accrual_summary(payroll)
    posting_date = _posting_entry_date(payroll, entry_date=entry_date, completed_disbursement=completed_disbursement)

    accrual_lines = []
    vote_head_summary = {}
    for bucket_key, amount in accrual_summary["bucket_totals"].items():
        if amount <= Decimal("0.00"):
            continue
        accrual_lines.append(
            {
                "account": accounts[bucket_key],
                "vote_head": vote_heads[bucket_key],
                "debit": amount,
                "credit": Decimal("0.00"),
                "description": f"Payroll accrual {vote_heads[bucket_key].name}",
            }
        )
        vote_head_summary[bucket_key] = str(amount)
    if accrual_summary["statutory_liability_total"] > Decimal("0.00"):
        accrual_lines.append(
            {
                "account": accounts["STATUTORY_LIABILITIES"],
                "vote_head": vote_heads["STATUTORY_LIABILITIES"],
                "debit": Decimal("0.00"),
                "credit": accrual_summary["statutory_liability_total"],
                "description": "Payroll statutory liabilities",
            }
        )
        vote_head_summary["STATUTORY_LIABILITIES"] = str(accrual_summary["statutory_liability_total"])
    if accrual_summary["net_payable_total"] > Decimal("0.00"):
        accrual_lines.append(
            {
                "account": accounts["NET_PAYROLL_PAYABLE"],
                "vote_head": vote_heads["NET_PAYROLL_PAYABLE"],
                "debit": Decimal("0.00"),
                "credit": accrual_summary["net_payable_total"],
                "description": "Payroll net payable",
            }
        )
        vote_head_summary["NET_PAYROLL_PAYABLE"] = str(accrual_summary["net_payable_total"])

    accrual_entry = FinanceService._post_journal(
        entry_date=posting_date,
        memo=f"Payroll accrual {payroll.month:02d}/{payroll.year}",
        lines=accrual_lines,
        source_type="HRPayrollAccrual",
        source_id=payroll.id,
        posted_by=posted_by,
        entry_key=_posting_entry_key(payroll, "ACCRUAL"),
    )
    _upsert_posting_record(
        payroll,
        stage="ACCRUAL",
        entry_key=_posting_entry_key(payroll, "ACCRUAL"),
        journal_entry=accrual_entry,
        cashbook_entry=None,
        posted_by=posted_by,
        vote_head_summary=vote_head_summary,
    )

    disbursement_entry = FinanceService._post_journal(
        entry_date=posting_date,
        memo=f"Payroll disbursement {payroll.month:02d}/{payroll.year}",
        lines=[
            {
                "account": accounts["NET_PAYROLL_PAYABLE"],
                "vote_head": vote_heads["NET_PAYROLL_PAYABLE"],
                "debit": accrual_summary["net_payable_total"],
                "credit": Decimal("0.00"),
                "description": "Clear payroll net payable",
            },
            {
                "account": accounts["CASH_BANK"],
                "debit": Decimal("0.00"),
                "credit": accrual_summary["net_payable_total"],
                "description": "Payroll cash/bank outflow",
            },
        ],
        source_type="HRPayrollDisbursement",
        source_id=payroll.id,
        posted_by=posted_by,
        entry_key=_posting_entry_key(payroll, "DISBURSEMENT"),
    )

    disbursement_posting = PayrollFinancePosting.objects.filter(
        payroll=payroll,
        posting_stage="DISBURSEMENT",
    ).first()
    cashbook_entry = disbursement_posting.cashbook_entry if disbursement_posting else None
    if cashbook_entry is None:
        cashbook_entry = FinanceService.record_cashbook_entry(
            book_type=DISBURSEMENT_BOOK_TYPE.get(completed_disbursement.method, "BANK"),
            entry_date=posting_date,
            entry_type="EXPENSE",
            reference=_posting_entry_key(payroll, "DISBURSEMENT"),
            description=(
                f"Payroll disbursement {payroll.month:02d}/{payroll.year}"
                + (f" ({completed_disbursement.reference})" if completed_disbursement.reference else "")
            ),
            amount_out=accrual_summary["net_payable_total"],
            is_auto=True,
        )

    _upsert_posting_record(
        payroll,
        stage="DISBURSEMENT",
        entry_key=_posting_entry_key(payroll, "DISBURSEMENT"),
        journal_entry=disbursement_entry,
        cashbook_entry=cashbook_entry,
        posted_by=posted_by,
        vote_head_summary={
            "NET_PAYROLL_PAYABLE": str(accrual_summary["net_payable_total"]),
            "book_type": DISBURSEMENT_BOOK_TYPE.get(completed_disbursement.method, "BANK"),
            "disbursement_method": completed_disbursement.method,
            "disbursement_reference": completed_disbursement.reference,
        },
    )

    if payroll.status != "Finance Posted":
        payroll.status = "Finance Posted"
    if payroll.posted_by_id is None:
        payroll.posted_by = posted_by
    if payroll.posted_at is None:
        payroll.posted_at = timezone.now()
    payroll.save(update_fields=["status", "posted_by", "posted_at"])
    return payroll
