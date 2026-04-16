"""
Fraud detection models for alerts and risk scoring.
"""

from django.db import models
from core.models import TenantModel


class Alert(TenantModel):
    """
    Security and fraud alerts.
    
    Tracks suspicious activities and system warnings.
    """
    
    LEVEL_CHOICES = [
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('CRITICAL', 'Critical'),
    ]
    
    ALERT_TYPES = [
        ('HIGH_RISK_TRANSACTION_BLOCKED', 'High Risk Transaction Blocked'),
        ('ELEVATED_RISK_TRANSACTION', 'Elevated Risk Transaction'),
        ('DUPLICATE_RECEIPT', 'Duplicate Receipt Detected'),
        ('RECONCILIATION_MISMATCH', 'Reconciliation Mismatch'),
        ('OVERDRAFT_ATTEMPT', 'Overdraft Attempt'),
        ('SUSPICIOUS_PATTERN', 'Suspicious Pattern Detected'),
        ('VOLUME_SPIKE', 'Unusual Volume Spike'),
        ('MANY_FAILURES', 'Many Failed Transactions'),
        ('ACTIVITY_SPIKE', 'Activity Spike'),
        ('ROUND_AMOUNT_PATTERN', 'Round Amount Pattern'),
        ('PHONE_MISMATCH', 'Phone Number Mismatch'),
        ('DAILY_VOLUME_LIMIT', 'Daily Volume Limit'),
        ('NEW_USER_LARGE_TX', 'New User Large Transaction'),
    ]
    
    level = models.CharField(
        max_length=20,
        choices=LEVEL_CHOICES,
        db_index=True,
        help_text='Severity level of the alert'
    )
    alert_type = models.CharField(
        max_length=50,
        choices=ALERT_TYPES,
        help_text='Type of alert'
    )
    message = models.TextField(
        help_text='Human-readable alert message'
    )
    reference = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text='Reference to related record (receipt, transaction ID, etc)'
    )
    metadata = models.JSONField(
        default=dict,
        help_text='Additional alert data'
    )
    
    # Resolution tracking
    resolved = models.BooleanField(
        default=False,
        db_index=True
    )
    resolved_by = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='resolved_alerts'
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True
    )
    resolution_notes = models.TextField(
        blank=True,
        help_text='Notes on how alert was resolved'
    )
    
    # Auto-escalation
    escalated = models.BooleanField(
        default=False,
        help_text='Whether alert was escalated'
    )
    escalated_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school', 'level', 'resolved']),
            models.Index(fields=['school', 'alert_type']),
            models.Index(fields=['created_at']),
            models.Index(fields=['reference']),
        ]
        verbose_name = 'Alert'
        verbose_name_plural = 'Alerts'
    
    def __str__(self):
        return f"[{self.level}] {self.alert_type} - {self.school}"
    
    def resolve(self, user, notes=''):
        """Mark alert as resolved."""
        from django.utils import timezone
        self.resolved = True
        self.resolved_by = user
        self.resolved_at = timezone.now()
        self.resolution_notes = notes
        self.save()
    
    def escalate(self):
        """Escalate alert to higher level."""
        from django.utils import timezone
        self.escalated = True
        self.escalated_at = timezone.now()
        self.save()
    
    @classmethod
    def get_unresolved(cls, school=None, level=None):
        """Get unresolved alerts."""
        qs = cls.objects.filter(resolved=False)
        if school:
            qs = qs.filter(school=school)
        if level:
            qs = qs.filter(level=level)
        return qs
    
    @classmethod
    def get_critical_count(cls, school=None):
        """Get count of critical unresolved alerts."""
        qs = cls.objects.filter(level='CRITICAL', resolved=False)
        if school:
            qs = qs.filter(school=school)
        return qs.count()


class RiskScoreLog(TenantModel):
    """
    Log of risk scores for analysis and audit.
    
    Tracks all risk assessments for trend analysis.
    """
    
    ACTION_CHOICES = [
        ('ALLOW', 'Allowed'),
        ('FLAG', 'Flagged'),
        ('BLOCK', 'Blocked'),
    ]
    
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='risk_scores'
    )
    transaction_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )
    risk_score = models.IntegerField(
        help_text='Risk score from 0-100'
    )
    factors = models.JSONField(
        default=list,
        help_text='Factors contributing to risk score'
    )
    action_taken = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES
    )
    
    # Optional reference to transaction
    transaction = models.ForeignKey(
        'payments.Transaction',
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school', 'user', 'created_at']),
            models.Index(fields=['risk_score']),
            models.Index(fields=['action_taken']),
        ]
        verbose_name = 'Risk Score Log'
        verbose_name_plural = 'Risk Score Logs'
    
    def __str__(self):
        return f"Score {self.risk_score} - {self.action_taken} - {self.user}"
    
    @classmethod
    def get_average_risk(cls, school, days=30):
        """Get average risk score for a school."""
        from django.utils import timezone
        from datetime import timedelta
        
        since = timezone.now() - timedelta(days=days)
        result = cls.objects.filter(
            school=school,
            created_at__gte=since
        ).aggregate(avg=models.Avg('risk_score'))
        return result['avg'] or 0
    
    @classmethod
    def get_block_rate(cls, school, days=30):
        """Get percentage of transactions blocked."""
        from django.utils import timezone
        from datetime import timedelta
        
        since = timezone.now() - timedelta(days=days)
        total = cls.objects.filter(school=school, created_at__gte=since).count()
        blocked = cls.objects.filter(
            school=school,
            created_at__gte=since,
            action_taken='BLOCK'
        ).count()
        
        return (blocked / total * 100) if total > 0 else 0


class Whitelist(TenantModel):
    """
    Whitelist for trusted users/phones.
    
    Reduces friction for known good actors.
    """
    
    TYPE_CHOICES = [
        ('PHONE', 'Phone Number'),
        ('USER', 'User'),
        ('IP', 'IP Address'),
    ]
    
    whitelist_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES
    )
    value = models.CharField(
        max_length=100,
        help_text='Phone, user ID, or IP to whitelist'
    )
    reason = models.TextField(
        help_text='Why this was whitelisted'
    )
    whitelisted_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Optional expiration'
    )
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['school', 'whitelist_type', 'value']
        verbose_name = 'Whitelist Entry'
        verbose_name_plural = 'Whitelist Entries'
    
    def is_valid(self):
        """Check if whitelist entry is still valid."""
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True
