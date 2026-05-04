from __future__ import annotations

from decimal import Decimal

from django.db import connection
from django.db.models import DecimalField, ExpressionWrapper, F, Sum, Value, Window
from django.db.models.functions import Coalesce

from school.models import JournalLine


MONEY_FIELD = DecimalField(max_digits=12, decimal_places=2)
ZERO_MONEY = Decimal("0.00")
ZERO_MONEY_VALUE = Value(ZERO_MONEY, output_field=MONEY_FIELD)


def _base_journal_lines(*, date_from=None, date_to=None, account_id=None):
    queryset = JournalLine.objects.all()
    if account_id is not None:
        queryset = queryset.filter(account_id=account_id)
    if date_from:
        queryset = queryset.filter(entry__entry_date__gte=date_from)
    if date_to:
        queryset = queryset.filter(entry__entry_date__lte=date_to)
    return queryset


def get_trial_balance_payload(date_from=None, date_to=None) -> dict[str, object]:
    rows = []
    aggregates = (
        _base_journal_lines(date_from=date_from, date_to=date_to)
        .values(
            "account_id",
            "account__code",
            "account__name",
            "account__account_type",
        )
        .annotate(
            debit_total=Coalesce(Sum("debit"), ZERO_MONEY_VALUE),
            credit_total=Coalesce(Sum("credit"), ZERO_MONEY_VALUE),
        )
        .order_by("account__code")
    )

    for aggregate in aggregates:
        rows.append(
            {
                "account_id": aggregate["account_id"],
                "code": aggregate["account__code"],
                "name": aggregate["account__name"],
                "type": aggregate["account__account_type"],
                "debit": float(aggregate["debit_total"] or 0),
                "credit": float(aggregate["credit_total"] or 0),
            }
        )

    total_debit = round(sum(row["debit"] for row in rows), 2)
    total_credit = round(sum(row["credit"] for row in rows), 2)
    return {
        "rows": rows,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "is_balanced": round(total_debit - total_credit, 2) == 0,
    }


def _serialize_ledger_row(row: dict[str, object], *, running_balance) -> dict[str, object]:
    return {
        "entry_id": row["entry_id"],
        "entry_date": row["entry__entry_date"],
        "memo": row["entry__memo"],
        "source_type": row["entry__source_type"],
        "source_id": row["entry__source_id"],
        "debit": float(row["debit"] or 0),
        "credit": float(row["credit"] or 0),
        "running_balance": round(float(running_balance or 0), 2),
    }


def get_account_ledger_payload(account_id, date_from=None, date_to=None) -> dict[str, object]:
    value_fields = (
        "entry_id",
        "entry__entry_date",
        "entry__memo",
        "entry__source_type",
        "entry__source_id",
        "debit",
        "credit",
    )
    delta_expression = ExpressionWrapper(F("debit") - F("credit"), output_field=MONEY_FIELD)
    base_queryset = _base_journal_lines(
        account_id=account_id,
        date_from=date_from,
        date_to=date_to,
    ).order_by("entry__entry_date", "id")

    rows = []
    if connection.features.supports_over_clause:
        queryset = (
            base_queryset.annotate(
                running_balance_amount=Window(
                    expression=Sum(delta_expression),
                    order_by=[F("entry__entry_date").asc(), F("id").asc()],
                )
            )
            .values(*value_fields, "running_balance_amount")
        )
        for row in queryset:
            rows.append(
                _serialize_ledger_row(
                    row,
                    running_balance=row["running_balance_amount"],
                )
            )
    else:
        running_balance = Decimal("0.00")
        for row in base_queryset.values(*value_fields):
            running_balance += (row["debit"] or ZERO_MONEY) - (row["credit"] or ZERO_MONEY)
            rows.append(_serialize_ledger_row(row, running_balance=running_balance))

    return {
        "account_id": int(account_id),
        "rows": rows,
        "closing_balance": rows[-1]["running_balance"] if rows else 0.0,
    }
