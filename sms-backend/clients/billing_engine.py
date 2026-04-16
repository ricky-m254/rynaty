"""
SaaS Billing Engine for SmartCampus platform.
Calculates transaction fees, manages subscription billing.
"""
from decimal import Decimal
from django.utils import timezone


# Default SaaS transaction fee (% of payment amount)
DEFAULT_TRANSACTION_FEE_PERCENT = Decimal('1.5')  # 1.5%
MINIMUM_FEE = Decimal('5.00')  # KES minimum per transaction
MAXIMUM_FEE = Decimal('500.00')  # KES maximum per transaction


class BillingEngine:
    """
    Calculates and records SaaS fees for each tenant's transactions.
    """

    def __init__(self, schema_name, school_name='', fee_percent=None):
        self.schema_name = schema_name
        self.school_name = school_name
        self.fee_percent = fee_percent or DEFAULT_TRANSACTION_FEE_PERCENT

    def calculate_transaction_fee(self, amount):
        """Calculate platform fee for a transaction amount."""
        amount = Decimal(str(amount))
        fee = (amount * self.fee_percent / 100).quantize(Decimal('0.01'))
        fee = max(fee, MINIMUM_FEE)
        fee = min(fee, MAXIMUM_FEE)
        return fee

    def record_transaction_fee(self, amount, mpesa_receipt='', metadata=None):
        """Record a transaction fee in RevenueLog."""
        from clients.models import RevenueLog
        fee = self.calculate_transaction_fee(amount)
        return RevenueLog.record_transaction_fee(
            schema_name=self.schema_name,
            school_name=self.school_name,
            fee_amount=fee,
            mpesa_receipt=mpesa_receipt,
            metadata=metadata or {'transaction_amount': str(amount), 'fee_percent': str(self.fee_percent)},
        )

    @classmethod
    def get_fee_percent_for_tenant(cls, schema_name):
        """Get fee % from TenantSubscription plan, or default."""
        try:
            from clients.models import TenantSubscription, Tenant
            tenant = Tenant.objects.filter(schema_name=schema_name).first()
            if not tenant:
                return DEFAULT_TRANSACTION_FEE_PERCENT
            sub = TenantSubscription.objects.filter(tenant=tenant, is_active=True).first()
            if sub and sub.plan:
                # SubscriptionPlan has a transaction_fee_percent if we add it
                fee_pct = getattr(sub.plan, 'transaction_fee_percent', DEFAULT_TRANSACTION_FEE_PERCENT)
                if fee_pct:
                    return Decimal(str(fee_pct))
        except Exception:
            pass
        return DEFAULT_TRANSACTION_FEE_PERCENT

    @classmethod
    def for_tenant(cls, schema_name, school_name=''):
        """Create BillingEngine for a specific tenant."""
        fee_percent = cls.get_fee_percent_for_tenant(schema_name)
        return cls(schema_name=schema_name, school_name=school_name, fee_percent=fee_percent)
