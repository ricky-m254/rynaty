"""
Ledger system for double-entry accounting.
All balance changes must go through the ledger.
"""

from decimal import Decimal
from django.db import models, transaction as db_transaction
from django.utils import timezone

from core.models import TenantModel


class LedgerEntry(TenantModel):
    """
    Double-entry ledger record for all financial transactions.
    
    This is the source of truth for all balance changes.
    Every credit or debit creates a ledger entry.
    """
    
    ENTRY_TYPES = [
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAWAL', 'Withdrawal'),
        ('FEE_PAYMENT', 'Fee Payment'),
        ('REFUND', 'Refund'),
        ('ADMIN_ADJUSTMENT', 'Admin Adjustment'),
        ('TRANSACTION_FEE', 'Transaction Fee'),
        ('SCHOOL_CREDIT', 'School Credit'),
        ('SCHOOL_FEE', 'School Fee'),
        ('PENALTY', 'Penalty'),
        ('DISCOUNT', 'Discount'),
    ]
    
    # User whose account is affected
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='ledger_entries',
        help_text='User whose account this entry affects'
    )
    
    # Entry details
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='Amount (positive for credit, negative for debit)'
    )
    entry_type = models.CharField(
        max_length=20,
        choices=ENTRY_TYPES,
        help_text='Type of ledger entry'
    )
    reference = models.CharField(
        max_length=100,
        db_index=True,
        help_text='External reference (M-Pesa receipt, invoice number, etc)'
    )
    description = models.TextField(
        blank=True,
        help_text='Human-readable description'
    )
    
    # Running balance after this entry
    balance_after = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='Wallet balance after this entry'
    )
    
    # For admin adjustments
    adjusted_by = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='adjustments_made',
        help_text='Admin who made the adjustment'
    )
    adjustment_reason = models.TextField(
        blank=True,
        help_text='Reason for admin adjustment'
    )
    
    # Linked records
    transaction = models.ForeignKey(
        'payments.Transaction',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='ledger_entries'
    )
    invoice = models.ForeignKey(
        'billing.Invoice',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='ledger_entries'
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Ledger Entry'
        verbose_name_plural = 'Ledger Entries'
        indexes = [
            models.Index(fields=['school', 'user', 'created_at']),
            models.Index(fields=['school', 'entry_type', 'created_at']),
            models.Index(fields=['reference']),
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        sign = '+' if self.amount > 0 else ''
        return f"{self.entry_type}: {sign}{self.amount} (Balance: {self.balance_after})"
    
    @property
    def is_credit(self):
        """Check if this is a credit entry."""
        return self.amount > 0
    
    @property
    def is_debit(self):
        """Check if this is a debit entry."""
        return self.amount < 0
    
    @classmethod
    def get_balance_for_user(cls, user, school):
        """Calculate current balance from ledger entries."""
        result = cls.objects.filter(
            school=school,
            user=user
        ).aggregate(
            total=models.Sum('amount')
        )
        return result['total'] or Decimal('0')
    
    @classmethod
    def get_entries_for_period(cls, school, start_date, end_date):
        """Get all entries for a date range."""
        return cls.objects.filter(
            school=school,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).order_by('created_at')


class Wallet(TenantModel):
    """
    User wallet for tracking balances.
    
    The balance is derived from ledger entries, but cached here
    for performance. The ledger remains the source of truth.
    """
    
    user = models.OneToOneField(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='wallet',
        help_text='User who owns this wallet'
    )
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Current available balance'
    )
    frozen_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Amount frozen (e.g., pending withdrawals)'
    )
    last_activity = models.DateTimeField(
        auto_now=True,
        help_text='Last time wallet was modified'
    )
    
    class Meta:
        verbose_name = 'Wallet'
        verbose_name_plural = 'Wallets'
        indexes = [
            models.Index(fields=['school', 'user']),
            models.Index(fields=['balance']),
        ]
    
    def __str__(self):
        return f"{self.user} - Balance: {self.balance}"
    
    @property
    def available_balance(self):
        """Get balance available for use (excluding frozen)."""
        return self.balance - self.frozen_balance
    
    @db_transaction.atomic
    def credit(self, amount, entry_type, reference, description='', **kwargs):
        """
        Credit (add) funds to wallet.
        
        Args:
            amount: Amount to credit
            entry_type: Type of ledger entry
            reference: External reference
            description: Human-readable description
            **kwargs: Additional fields for ledger entry
            
        Returns:
            LedgerEntry instance
        """
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Credit amount must be positive")
        
        # Update balance
        self.balance += amount
        self.save()
        
        # Create ledger entry
        return LedgerEntry.objects.create(
            school=self.school,
            user=self.user,
            amount=amount,
            entry_type=entry_type,
            reference=reference,
            description=description,
            balance_after=self.balance,
            **kwargs
        )
    
    @db_transaction.atomic
    def debit(self, amount, entry_type, reference, description='', **kwargs):
        """
        Debit (subtract) funds from wallet.
        
        Args:
            amount: Amount to debit
            entry_type: Type of ledger entry
            reference: External reference
            description: Human-readable description
            **kwargs: Additional fields for ledger entry
            
        Returns:
            LedgerEntry instance
            
        Raises:
            ValueError: If insufficient balance
        """
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Debit amount must be positive")
        
        if self.balance < amount:
            raise ValueError(
                f"Insufficient balance: {self.balance} < {amount}"
            )
        
        # Update balance
        self.balance -= amount
        self.save()
        
        # Create ledger entry (negative amount)
        return LedgerEntry.objects.create(
            school=self.school,
            user=self.user,
            amount=-amount,
            entry_type=entry_type,
            reference=reference,
            description=description,
            balance_after=self.balance,
            **kwargs
        )
    
    @db_transaction.atomic
    def freeze(self, amount):
        """Freeze amount (e.g., for pending withdrawal)."""
        amount = Decimal(str(amount))
        if self.available_balance < amount:
            raise ValueError("Insufficient available balance to freeze")
        
        self.frozen_balance += amount
        self.save()
    
    @db_transaction.atomic
    def unfreeze(self, amount):
        """Unfreeze amount."""
        amount = Decimal(str(amount))
        if self.frozen_balance < amount:
            raise ValueError("Cannot unfreeze more than frozen amount")
        
        self.frozen_balance -= amount
        self.save()
    
    @db_transaction.atomic
    def reconcile(self):
        """
        Reconcile wallet balance with ledger.
        
        Returns True if balanced, raises error if mismatch.
        """
        ledger_balance = LedgerEntry.objects.filter(
            school=self.school,
            user=self.user
        ).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0')
        
        if ledger_balance != self.balance:
            raise ValueError(
                f"Wallet balance mismatch: Wallet={self.balance}, Ledger={ledger_balance}"
            )
        
        return True
    
    @classmethod
    def get_or_create_for_user(cls, user, school):
        """Get existing wallet or create new one for user."""
        wallet, created = cls.objects.get_or_create(
            school=school,
            user=user,
            defaults={'balance': Decimal('0.00')}
        )
        return wallet
    
    @classmethod
    def get_total_balance_for_school(cls, school):
        """Get total of all wallet balances in a school."""
        result = cls.objects.filter(school=school).aggregate(
            total=models.Sum('balance')
        )
        return result['total'] or Decimal('0')


class LedgerReconciliation(TenantModel):
    """
    Record of reconciliation runs.
    
    Tracks when ledger was reconciled and any discrepancies found.
    """
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('BALANCED', 'Balanced'),
        ('MISMATCH', 'Mismatch Found'),
        ('ERROR', 'Error'),
    ]
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    start_date = models.DateField(
        help_text='Start of reconciliation period'
    )
    end_date = models.DateField(
        help_text='End of reconciliation period'
    )
    total_entries = models.IntegerField(default=0)
    total_credits = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0')
    )
    total_debits = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0')
    )
    discrepancies = models.JSONField(
        default=list,
        help_text='List of any discrepancies found'
    )
    notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Ledger Reconciliation'
        verbose_name_plural = 'Ledger Reconciliations'
