"""
Compliance Engine for SmartCampus Finance.
Validates transactions against configurable school-level rules.
"""
from decimal import Decimal
from django.utils import timezone


# Default compliance limits (can be overridden per-school via TenantSettings)
DEFAULT_LIMITS = {
    'MAX_TRANSACTION': Decimal('200000'),   # KES per transaction
    'MAX_DAILY_VOLUME': Decimal('500000'),  # KES per day per student
    'MAX_STUDENT_BALANCE': Decimal('100000'),  # Max wallet balance
    'REQUIRE_RECEIPT': True,
    'DATA_RETENTION_YEARS': 7,
}


class ComplianceEngine:
    """
    Validates financial operations for regulatory compliance.
    """

    def __init__(self, limits=None):
        self.limits = limits or DEFAULT_LIMITS

    def check_transaction_limit(self, amount):
        """Returns (pass, message)"""
        amount = Decimal(str(amount))
        max_tx = self.limits.get('MAX_TRANSACTION', Decimal('200000'))
        if amount > max_tx:
            return False, f"Transaction amount {amount} exceeds max allowed {max_tx}"
        return True, "OK"

    def check_daily_volume(self, user, amount):
        """Check if this payment would exceed daily volume limit."""
        from django.db.models import Sum
        from school.models import Payment
        amount = Decimal(str(amount))
        max_daily = self.limits.get('MAX_DAILY_VOLUME', Decimal('500000'))
        today_total = Payment.objects.filter(
            student=user, date=timezone.now().date()
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        if today_total + amount > max_daily:
            return False, f"Daily volume {today_total} + {amount} > limit {max_daily}"
        return True, "OK"

    def check_receipt_required(self, receipt):
        """Check if receipt is present when required."""
        if self.limits.get('REQUIRE_RECEIPT', True) and not receipt:
            return False, "M-Pesa receipt is required"
        return True, "OK"

    def check_wallet_balance_limit(self, current_balance, credit_amount):
        """Check wallet won't exceed max balance."""
        max_balance = self.limits.get('MAX_STUDENT_BALANCE', Decimal('100000'))
        if current_balance + Decimal(str(credit_amount)) > max_balance:
            return False, f"Wallet balance would exceed max {max_balance}"
        return True, "OK"

    def run_all_checks(self, user, amount, receipt=None, current_wallet_balance=None):
        """
        Run all compliance checks. Returns (passed, errors).
        """
        errors = []
        amount = Decimal(str(amount))

        ok, msg = self.check_transaction_limit(amount)
        if not ok:
            errors.append({'rule': 'MAX_TRANSACTION', 'message': msg})

        ok, msg = self.check_receipt_required(receipt)
        if not ok:
            errors.append({'rule': 'REQUIRE_RECEIPT', 'message': msg})

        if current_wallet_balance is not None:
            ok, msg = self.check_wallet_balance_limit(current_wallet_balance, amount)
            if not ok:
                errors.append({'rule': 'MAX_STUDENT_BALANCE', 'message': msg})

        return len(errors) == 0, errors
