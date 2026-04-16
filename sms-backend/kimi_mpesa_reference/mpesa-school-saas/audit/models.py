"""
Audit and compliance models for tamper-proof logging.
Implements blockchain-style hash chaining for integrity.
"""

import hashlib
import json
from django.db import models
from django.utils import timezone

from core.models import TenantModel


class AuditLog(TenantModel):
    """
    Tamper-proof audit log with hash chaining.
    
    Every entry includes a hash of its contents plus the previous
    entry's hash, creating a chain that detects any modifications.
    """
    
    ACTION_CHOICES = [
        ('PAYMENT_RECEIVED', 'Payment Received'),
        ('PAYMENT_FAILED', 'Payment Failed'),
        ('BALANCE_UPDATED', 'Balance Updated'),
        ('BALANCE_ADJUSTED', 'Balance Adjusted by Admin'),
        ('SCHOOL_SUSPENDED', 'School Suspended'),
        ('SCHOOL_ACTIVATED', 'School Activated'),
        ('STK_PUSH_INITIATED', 'STK Push Initiated'),
        ('STK_PUSH_CALLBACK', 'STK Push Callback Received'),
        ('WITHDRAWAL_REQUESTED', 'Withdrawal Requested'),
        ('WITHDRAWAL_APPROVED', 'Withdrawal Approved'),
        ('WITHDRAWAL_REJECTED', 'Withdrawal Rejected'),
        ('INVOICE_CREATED', 'Invoice Created'),
        ('INVOICE_PAID', 'Invoice Paid'),
        ('INVOICE_CANCELLED', 'Invoice Cancelled'),
        ('USER_LOGIN', 'User Login'),
        ('USER_LOGOUT', 'User Logout'),
        ('USER_CREATED', 'User Created'),
        ('USER_UPDATED', 'User Updated'),
        ('API_REQUEST', 'API Request'),
        ('ADMIN_ACTION', 'Admin Action'),
        ('CONFIG_CHANGED', 'Configuration Changed'),
        ('EXPORT_GENERATED', 'Export Generated'),
    ]
    
    # Who performed the action
    user = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_logs',
        help_text='User who performed the action (null for system)'
    )
    
    # What was done
    action = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES,
        db_index=True
    )
    entity = models.CharField(
        max_length=50,
        help_text='Type of entity affected (TRANSACTION, WALLET, USER, etc)'
    )
    entity_id = models.CharField(
        max_length=100,
        help_text='ID of affected entity'
    )
    
    # Before/after values for traceability
    metadata = models.JSONField(
        default=dict,
        help_text='Additional context (before/after values, etc)'
    )
    
    # Request context
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True
    )
    user_agent = models.TextField(
        blank=True
    )
    request_path = models.CharField(
        max_length=500,
        blank=True
    )
    request_method = models.CharField(
        max_length=10,
        blank=True
    )
    
    # Tamper-proof chain
    entry_hash = models.CharField(
        max_length=64,
        db_index=True,
        help_text='SHA-256 hash of this entry'
    )
    previous_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text='Hash of previous entry in chain'
    )
    
    # For verification
    verified = models.BooleanField(
        default=False,
        help_text='Whether this entry has been verified'
    )
    verified_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school', 'action', 'created_at']),
            models.Index(fields=['entity', 'entity_id']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['created_at']),
            models.Index(fields=['entry_hash']),
        ]
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
    
    def __str__(self):
        return f"{self.action} - {self.entity} - {self.created_at}"
    
    def save(self, *args, **kwargs):
        """Compute hash before saving."""
        if not self.entry_hash:
            self._compute_hash()
        super().save(*args, **kwargs)
    
    def _compute_hash(self):
        """
        Compute SHA-256 hash of entry data.
        
        Includes previous hash to create tamper-evident chain.
        """
        # Get previous hash
        last_entry = AuditLog.objects.filter(
            school=self.school
        ).exclude(id=self.id if self.id else None).first()
        
        self.previous_hash = last_entry.entry_hash if last_entry else '0' * 64
        
        # Create hash from data
        data = {
            'school_id': str(self.school_id) if self.school_id else None,
            'user_id': str(self.user_id) if self.user_id else None,
            'action': self.action,
            'entity': self.entity,
            'entity_id': self.entity_id,
            'metadata': self.metadata,
            'ip_address': str(self.ip_address) if self.ip_address else None,
            'timestamp': self.created_at.isoformat() if self.created_at else timezone.now().isoformat(),
            'previous_hash': self.previous_hash
        }
        
        # Create deterministic JSON string
        hash_input = json.dumps(data, sort_keys=True, separators=(',', ':'))
        self.entry_hash = hashlib.sha256(hash_input.encode()).hexdigest()
    
    def verify_integrity(self):
        """
        Verify this entry's integrity by recomputing hash.
        
        Returns:
            bool: True if integrity verified
        """
        # Store current hash
        stored_hash = self.entry_hash
        
        # Recompute
        self.entry_hash = ''
        self._compute_hash()
        recomputed_hash = self.entry_hash
        
        # Restore
        self.entry_hash = stored_hash
        
        return stored_hash == recomputed_hash
    
    @classmethod
    def log_action(cls, request, action, entity, entity_id, metadata=None):
        """
        Convenience method to log an action from a request.
        
        Args:
            request: Django request object
            action: Action type
            entity: Entity type
            entity_id: Entity ID
            metadata: Additional data
            
        Returns:
            AuditLog: Created log entry
        """
        return cls.objects.create(
            school=getattr(request, 'school', None),
            user=request.user if request.user.is_authenticated else None,
            action=action,
            entity=entity,
            entity_id=entity_id,
            metadata=metadata or {},
            ip_address=cls._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            request_path=request.path[:500],
            request_method=request.method
        )
    
    @classmethod
    def log_system_action(cls, school, action, entity, entity_id, metadata=None):
        """
        Log a system action (no user).
        
        Args:
            school: School context
            action: Action type
            entity: Entity type
            entity_id: Entity ID
            metadata: Additional data
            
        Returns:
            AuditLog: Created log entry
        """
        return cls.objects.create(
            school=school,
            user=None,
            action=action,
            entity=entity,
            entity_id=entity_id,
            metadata=metadata or {}
        )
    
    @staticmethod
    def _get_client_ip(request):
        """Extract client IP from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
    
    @classmethod
    def verify_chain(cls, school):
        """
        Verify integrity of entire audit chain for a school.
        
        Args:
            school: School to verify
            
        Returns:
            tuple: (is_valid, error_message, broken_entry)
        """
        entries = cls.objects.filter(school=school).order_by('created_at')
        previous_hash = '0' * 64
        
        for entry in entries:
            # Check previous hash matches
            if entry.previous_hash != previous_hash:
                return False, f"Chain broken at entry {entry.id}", entry
            
            # Verify entry integrity
            if not entry.verify_integrity():
                return False, f"Entry {entry.id} has been tampered with", entry
            
            previous_hash = entry.entry_hash
        
        return True, "Chain verified", None
    
    @classmethod
    def get_entity_history(cls, school, entity, entity_id):
        """
        Get complete audit history for an entity.
        
        Args:
            school: School context
            entity: Entity type
            entity_id: Entity ID
            
        Returns:
            QuerySet: Audit logs for entity
        """
        return cls.objects.filter(
            school=school,
            entity=entity,
            entity_id=entity_id
        ).order_by('created_at')


class ComplianceRule(models.Model):
    """
    Configurable compliance rules.
    
    Schools can customize rules based on their requirements.
    """
    
    RULE_TYPES = [
        ('MAX_TRANSACTION', 'Maximum Transaction Amount'),
        ('MAX_DAILY', 'Maximum Daily Volume'),
        ('MAX_STUDENT_BALANCE', 'Maximum Student Balance'),
        ('REQUIRE_RECEIPT', 'Require M-Pesa Receipt'),
        ('DATA_RETENTION', 'Data Retention Period'),
    ]
    
    school = models.ForeignKey(
        'schools.School',
        on_delete=models.CASCADE,
        related_name='compliance_rules'
    )
    name = models.CharField(max_length=100)
    rule_type = models.CharField(
        max_length=50,
        choices=RULE_TYPES
    )
    threshold = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )
    config = models.JSONField(
        default=dict,
        help_text='Additional configuration'
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['school', 'rule_type']
        verbose_name = 'Compliance Rule'
        verbose_name_plural = 'Compliance Rules'
    
    def __str__(self):
        return f"{self.rule_type} - {self.school}"


class ComplianceLog(models.Model):
    """
    Log of compliance check results.
    """
    
    STATUS_CHOICES = [
        ('PASS', 'Pass'),
        ('FAIL', 'Fail'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
    ]
    
    school = models.ForeignKey(
        'schools.School',
        on_delete=models.CASCADE,
        related_name='compliance_logs'
    )
    rule = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    details = models.JSONField(default=dict)
    checked_by = models.ForeignKey(
        'auth.User',
        null=True,
        on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Compliance Log'
        verbose_name_plural = 'Compliance Logs'


class DataRetentionPolicy(models.Model):
    """
    Data retention policies per school.
    
    Ensures compliance with data protection regulations.
    """
    
    school = models.OneToOneField(
        'schools.School',
        on_delete=models.CASCADE,
        related_name='retention_policy'
    )
    
    # Retention periods (in years)
    transaction_retention_years = models.IntegerField(default=7)
    audit_retention_years = models.IntegerField(default=7)
    user_data_retention_years = models.IntegerField(default=3)
    
    # Auto-delete settings
    auto_delete_expired = models.BooleanField(default=False)
    notify_before_delete = models.BooleanField(default=True)
    notify_days_before = models.IntegerField(default=30)
    
    last_purged_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Data Retention Policy'
        verbose_name_plural = 'Data Retention Policies'
    
    def get_retention_date(self, data_type='transaction'):
        """Get cutoff date for data retention."""
        years = {
            'transaction': self.transaction_retention_years,
            'audit': self.audit_retention_years,
            'user': self.user_data_retention_years,
        }.get(data_type, 7)
        
        return timezone.now() - timezone.timedelta(days=365 * years)
