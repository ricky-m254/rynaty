"""
Payment models for M-Pesa integration.
Handles transactions, raw callbacks, and payment state management.
"""

import uuid
from decimal import Decimal
from django.db import models, transaction as db_transaction
from django.utils import timezone

from core.models import TenantModel


class Transaction(TenantModel):
    """
    Records all payment transactions in the system.
    
    This is the central record for all money movements.
    Links to ledger entries for balance tracking.
    """
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
        ('REFUNDED', 'Refunded'),
    ]
    
    TYPE_CHOICES = [
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAWAL', 'Withdrawal'),
        ('FEE_PAYMENT', 'Fee Payment'),
        ('REFUND', 'Refund'),
        ('TRANSFER', 'Transfer'),
    ]
    
    # Primary key using UUID for security and scalability
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # User relationship
    user = models.ForeignKey(
        'auth.User', 
        on_delete=models.CASCADE, 
        related_name='transactions',
        help_text='User who initiated or receives this transaction'
    )
    
    # Transaction details
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        help_text='Transaction amount in KES'
    )
    transaction_type = models.CharField(
        max_length=20, 
        choices=TYPE_CHOICES,
        help_text='Type of transaction'
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='PENDING',
        db_index=True
    )
    
    # M-Pesa specific fields
    phone_number = models.CharField(
        max_length=20,
        help_text='Phone number used for M-Pesa'
    )
    mpesa_receipt = models.CharField(
        max_length=50, 
        unique=True, 
        null=True, 
        blank=True,
        db_index=True,
        help_text='M-Pesa receipt number (unique)'
    )
    merchant_request_id = models.CharField(
        max_length=100, 
        blank=True,
        help_text='M-Pesa merchant request ID'
    )
    checkout_request_id = models.CharField(
        max_length=100, 
        blank=True,
        help_text='M-Pesa checkout request ID'
    )
    result_code = models.CharField(
        max_length=10, 
        blank=True,
        help_text='M-Pesa result code'
    )
    result_desc = models.TextField(
        blank=True,
        help_text='M-Pesa result description'
    )
    
    # Linked records
    invoice = models.ForeignKey(
        'billing.Invoice', 
        null=True, 
        on_delete=models.SET_NULL,
        related_name='transactions',
        help_text='Linked invoice if this is a fee payment'
    )
    ledger_entry = models.ForeignKey(
        'ledger.LedgerEntry', 
        null=True, 
        on_delete=models.SET_NULL,
        related_name='source_transaction',
        help_text='Linked ledger entry'
    )
    
    # Metadata
    description = models.TextField(blank=True)
    callback_payload = models.JSONField(
        null=True, 
        blank=True,
        help_text='Raw M-Pesa callback data for audit'
    )
    processed_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text='When transaction was fully processed'
    )
    
    # For refunds
    original_transaction = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='refunds',
        help_text='Original transaction if this is a refund'
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'
        indexes = [
            models.Index(fields=['school', 'user', 'status']),
            models.Index(fields=['school', 'status', 'created_at']),
            models.Index(fields=['mpesa_receipt']),
            models.Index(fields=['merchant_request_id']),
            models.Index(fields=['checkout_request_id']),
            models.Index(fields=['created_at']),
            models.Index(fields=['phone_number', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.transaction_type} - {self.amount} - {self.status}"
    
    @property
    def is_successful(self):
        """Check if transaction completed successfully."""
        return self.status == 'SUCCESS'
    
    @property
    def is_pending(self):
        """Check if transaction is still pending."""
        return self.status in ['PENDING', 'PROCESSING']
    
    @property
    def is_failed(self):
        """Check if transaction failed."""
        return self.status == 'FAILED'
    
    @property
    def can_refund(self):
        """Check if this transaction can be refunded."""
        return (
            self.status == 'SUCCESS' 
            and self.transaction_type == 'DEPOSIT'
            and not self.refunds.filter(status='SUCCESS').exists()
        )
    
    def mark_success(self, receipt, callback_data=None):
        """Mark transaction as successful."""
        with db_transaction.atomic():
            self.mpesa_receipt = receipt
            self.status = 'SUCCESS'
            self.processed_at = timezone.now()
            if callback_data:
                self.callback_payload = callback_data
            self.save()
    
    def mark_failed(self, reason='', callback_data=None):
        """Mark transaction as failed."""
        self.status = 'FAILED'
        self.result_desc = reason
        if callback_data:
            self.callback_payload = callback_data
        self.save()
    
    @classmethod
    def get_pending_for_phone(cls, phone, minutes=5):
        """Get pending transactions for a phone number within time window."""
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(minutes=minutes)
        return cls.objects.filter(
            phone_number=phone,
            status__in=['PENDING', 'PROCESSING'],
            created_at__gte=cutoff
        )
    
    @classmethod
    def get_daily_total_for_user(cls, user, school):
        """Get total successful transactions for user today."""
        return cls.objects.filter(
            school=school,
            user=user,
            status='SUCCESS',
            created_at__date=timezone.now().date()
        ).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0')


class MpesaRawLog(TenantModel):
    """
    Stores raw M-Pesa callbacks for complete audit trail.
    
    This ensures we never lose callback data, even if processing fails.
    """
    
    payload = models.JSONField(
        help_text='Raw callback payload from M-Pesa'
    )
    endpoint = models.CharField(
        max_length=100,
        help_text='Which endpoint received this callback'
    )
    ip_address = models.GenericIPAddressField(
        help_text='IP address of the caller'
    )
    processed = models.BooleanField(
        default=False,
        help_text='Whether this callback was successfully processed'
    )
    processing_error = models.TextField(
        blank=True,
        help_text='Error message if processing failed'
    )
    transaction = models.ForeignKey(
        Transaction,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='raw_logs'
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'M-Pesa Raw Log'
        verbose_name_plural = 'M-Pesa Raw Logs'
        indexes = [
            models.Index(fields=['school', 'processed']),
            models.Index(fields=['endpoint', 'created_at']),
            models.Index(fields=['ip_address']),
        ]
    
    def __str__(self):
        return f"{self.endpoint} - {self.created_at} - Processed: {self.processed}"


class WithdrawalRequest(TenantModel):
    """
    Tracks B2C withdrawal requests (refunds/payouts).
    
    Requires admin approval before processing.
    """
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('PROCESSING', 'Processing'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='withdrawal_requests'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    phone_number = models.CharField(max_length=20)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    
    # Approval
    requested_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='withdrawals_requested'
    )
    approved_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='withdrawals_approved'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # M-Pesa tracking
    conversation_id = models.CharField(max_length=100, blank=True)
    mpesa_receipt = models.CharField(max_length=50, blank=True)
    
    # Linked records
    transaction = models.ForeignKey(
        Transaction,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='withdrawal_request'
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school', 'user', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def approve(self, admin_user):
        """Approve withdrawal request."""
        self.status = 'APPROVED'
        self.approved_by = admin_user
        self.approved_at = timezone.now()
        self.save()
    
    def reject(self, admin_user, reason):
        """Reject withdrawal request."""
        self.status = 'REJECTED'
        self.approved_by = admin_user
        self.approved_at = timezone.now()
        self.rejection_reason = reason
        self.save()
