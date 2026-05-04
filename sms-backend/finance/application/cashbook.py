from decimal import Decimal

from django.db import transaction

from school.models import CashbookEntry


def get_cashbook_queryset(book_type=None, date_from=None, date_to=None):
    queryset = CashbookEntry.objects.all()
    if book_type:
        queryset = queryset.filter(book_type=book_type.upper())
    if date_from:
        queryset = queryset.filter(entry_date__gte=date_from)
    if date_to:
        queryset = queryset.filter(entry_date__lte=date_to)
    return queryset.order_by("book_type", "entry_date", "created_at")


def recompute_running_balances(book_type):
    with transaction.atomic():
        entries = list(
            CashbookEntry.objects.select_for_update().filter(book_type=book_type).order_by(
                "entry_date",
                "created_at",
                "id",
            )
        )
        balance = Decimal("0.00")
        for entry in entries:
            balance += (entry.amount_in or Decimal("0.00")) - (
                entry.amount_out or Decimal("0.00")
            )
            entry.running_balance = balance
        if entries:
            CashbookEntry.objects.bulk_update(entries, ["running_balance"])
