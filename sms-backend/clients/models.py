from django.db import models
from django.contrib.auth import get_user_model
from django_tenants.models import TenantMixin, DomainMixin

User = get_user_model()


class SubscriptionPlan(models.Model):
    """Platform-level subscription plan used for tenant onboarding and limits."""

    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    annual_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_students = models.PositiveIntegerField(default=200)
    max_storage_gb = models.PositiveIntegerField(default=5)
    enabled_modules = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class TenantSubscription(models.Model):
    BILLING_MONTHLY = "MONTHLY"
    BILLING_ANNUAL = "ANNUAL"
    BILLING_CHOICES = [
        (BILLING_MONTHLY, "Monthly"),
        (BILLING_ANNUAL, "Annual"),
    ]

    STATUS_TRIAL = "TRIAL"
    STATUS_ACTIVE = "ACTIVE"
    STATUS_SUSPENDED = "SUSPENDED"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_CHOICES = [
        (STATUS_TRIAL, "Trial"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_SUSPENDED, "Suspended"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    tenant = models.ForeignKey("clients.Tenant", on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey("clients.SubscriptionPlan", on_delete=models.PROTECT, related_name="tenant_subscriptions")
    billing_cycle = models.CharField(max_length=20, choices=BILLING_CHOICES, default=BILLING_MONTHLY)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_TRIAL)
    starts_on = models.DateField()
    ends_on = models.DateField(null=True, blank=True)
    trial_end = models.DateField(null=True, blank=True)
    next_billing_date = models.DateField(null=True, blank=True)
    grace_period_days = models.PositiveIntegerField(default=7)
    is_current = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.tenant.schema_name} - {self.plan.code} ({self.billing_cycle})"


class SubscriptionInvoice(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_PAID = "PAID"
    STATUS_OVERDUE = "OVERDUE"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PAID, "Paid"),
        (STATUS_OVERDUE, "Overdue"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    tenant = models.ForeignKey("clients.Tenant", on_delete=models.CASCADE, related_name="subscription_invoices")
    subscription = models.ForeignKey(
        "clients.TenantSubscription",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    invoice_number = models.CharField(max_length=64, unique=True)
    billing_cycle = models.CharField(max_length=20, choices=TenantSubscription.BILLING_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    currency = models.CharField(max_length=10, default="USD")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    period_start = models.DateField()
    period_end = models.DateField()
    issued_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField()
    paid_at = models.DateTimeField(null=True, blank=True)
    external_reference = models.CharField(max_length=128, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-issued_at"]

    def __str__(self):
        return f"{self.invoice_number} - {self.tenant.schema_name}"


class SubscriptionPayment(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_PAID = "PAID"
    STATUS_FAILED = "FAILED"
    STATUS_REFUNDED = "REFUNDED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PAID, "Paid"),
        (STATUS_FAILED, "Failed"),
        (STATUS_REFUNDED, "Refunded"),
    ]

    invoice = models.ForeignKey("clients.SubscriptionInvoice", on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    method = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    paid_at = models.DateTimeField(null=True, blank=True)
    transaction_id = models.CharField(max_length=128, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.amount}"


class Tenant(TenantMixin):
    """
    Represents a School (Tenant).
    Resides in the 'public' schema only.
    """

    STATUS_TRIAL = "TRIAL"
    STATUS_ACTIVE = "ACTIVE"
    STATUS_SUSPENDED = "SUSPENDED"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_ARCHIVED = "ARCHIVED"

    STATUS_CHOICES = [
        (STATUS_TRIAL, "Trial"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_SUSPENDED, "Suspended"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_ARCHIVED, "Archived"),
    ]

    name = models.CharField(max_length=255)
    subdomain = models.CharField(max_length=100, unique=True, null=True, blank=True)
    custom_domain = models.CharField(max_length=255, null=True, blank=True)
    contact_name = models.CharField(max_length=255, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_TRIAL)
    subscription_plan = models.ForeignKey(
        "clients.SubscriptionPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tenants",
    )
    trial_start = models.DateField(null=True, blank=True)
    trial_end = models.DateField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.TextField(blank=True)
    max_students = models.PositiveIntegerField(default=200)
    max_storage_gb = models.PositiveIntegerField(default=5)
    archived_at = models.DateTimeField(null=True, blank=True)
    # schema_name is automatically inherited from TenantMixin
    
    # --- Subscription Flags ---
    is_active = models.BooleanField(default=True, help_text="Controls if the school can access the system")
    paid_until = models.DateField(null=True, blank=True, help_text="Date until subscription is valid")
    
    # --- Auto Schema Handling ---
    auto_create_schema = True
    auto_drop_schema = False  # SAFETY: Never automatically drop a school's database

    # --- Audit ---
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Domain(DomainMixin):
    """
    Represents a Domain linked to a School.
    Maps a URL (e.g., myschool.localhost) to a specific Schema.
    """
    # domain and tenant are inherited from DomainMixin
    pass


class CustomDomainRequest(models.Model):
    """
    Tracks a school's self-service request to connect a custom domain.
    Lives in the public schema alongside Tenant/Domain.
    """
    STATUS_PENDING = "PENDING"
    STATUS_VERIFIED = "VERIFIED"
    STATUS_ACTIVE = "ACTIVE"
    STATUS_FAILED = "FAILED"
    STATUS_REJECTED = "REJECTED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending DNS verification"),
        (STATUS_VERIFIED, "DNS verified — awaiting activation"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_FAILED, "Verification failed"),
        (STATUS_REJECTED, "Rejected by platform"),
    ]

    tenant = models.ForeignKey(
        "clients.Tenant",
        on_delete=models.CASCADE,
        related_name="custom_domain_requests",
    )
    requested_domain = models.CharField(max_length=255)
    verification_token = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    verification_attempts = models.PositiveSmallIntegerField(default=0)
    last_verification_attempt = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    requested_by_username = models.CharField(max_length=150, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.tenant.schema_name} → {self.requested_domain} [{self.status}]"


class SupportTicket(models.Model):
    CATEGORY_TECHNICAL = "TECHNICAL"
    CATEGORY_BILLING = "BILLING"
    CATEGORY_FEATURE = "FEATURE"
    CATEGORY_BUG = "BUG"
    CATEGORY_CHOICES = [
        (CATEGORY_TECHNICAL, "Technical"),
        (CATEGORY_BILLING, "Billing"),
        (CATEGORY_FEATURE, "Feature Request"),
        (CATEGORY_BUG, "Bug"),
    ]

    PRIORITY_LOW = "LOW"
    PRIORITY_NORMAL = "NORMAL"
    PRIORITY_HIGH = "HIGH"
    PRIORITY_URGENT = "URGENT"
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, "Low"),
        (PRIORITY_NORMAL, "Normal"),
        (PRIORITY_HIGH, "High"),
        (PRIORITY_URGENT, "Urgent"),
    ]

    STATUS_OPEN = "OPEN"
    STATUS_IN_PROGRESS = "IN_PROGRESS"
    STATUS_RESOLVED = "RESOLVED"
    STATUS_CLOSED = "CLOSED"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_RESOLVED, "Resolved"),
        (STATUS_CLOSED, "Closed"),
    ]

    ticket_number = models.CharField(max_length=40, unique=True)
    tenant = models.ForeignKey("clients.Tenant", on_delete=models.CASCADE, related_name="support_tickets")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_TECHNICAL)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_NORMAL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    subject = models.CharField(max_length=255)
    description = models.TextField()
    created_by_email = models.EmailField(blank=True)
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_support_tickets",
    )
    first_response_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.ticket_number


class SupportTicketNote(models.Model):
    ticket = models.ForeignKey("clients.SupportTicket", on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    body = models.TextField()
    is_internal = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.ticket.ticket_number} note"


class ImpersonationSession(models.Model):
    STATUS_REQUESTED = "REQUESTED"
    STATUS_APPROVED = "APPROVED"
    STATUS_ACTIVE = "ACTIVE"
    STATUS_ENDED = "ENDED"
    STATUS_REJECTED = "REJECTED"
    STATUS_EXPIRED = "EXPIRED"
    STATUS_CHOICES = [
        (STATUS_REQUESTED, "Requested"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_ENDED, "Ended"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_EXPIRED, "Expired"),
    ]

    tenant = models.ForeignKey("clients.Tenant", on_delete=models.CASCADE, related_name="impersonation_sessions")
    target_username = models.CharField(max_length=150)
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="impersonation_requests")
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="impersonation_approvals",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_REQUESTED)
    reason = models.TextField(blank=True)
    read_only = models.BooleanField(default=True)
    duration_minutes = models.PositiveIntegerField(default=60)
    started_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True)
    session_token = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.tenant.schema_name}::{self.target_username}::{self.status}"


class MonitoringSnapshot(models.Model):
    metric_key = models.CharField(max_length=100)
    tenant = models.ForeignKey("clients.Tenant", on_delete=models.CASCADE, null=True, blank=True, related_name="monitoring_snapshots")
    value = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    captured_at = models.DateTimeField(default=models.functions.Now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-captured_at"]

    def __str__(self):
        return f"{self.metric_key}@{self.captured_at}"


class MonitoringAlert(models.Model):
    SEVERITY_INFO = "INFO"
    SEVERITY_WARNING = "WARNING"
    SEVERITY_CRITICAL = "CRITICAL"
    SEVERITY_CHOICES = [
        (SEVERITY_INFO, "Info"),
        (SEVERITY_WARNING, "Warning"),
        (SEVERITY_CRITICAL, "Critical"),
    ]

    STATUS_OPEN = "OPEN"
    STATUS_ACKNOWLEDGED = "ACKNOWLEDGED"
    STATUS_RESOLVED = "RESOLVED"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_ACKNOWLEDGED, "Acknowledged"),
        (STATUS_RESOLVED, "Resolved"),
    ]

    title = models.CharField(max_length=255)
    metric_key = models.CharField(max_length=100, blank=True)
    tenant = models.ForeignKey("clients.Tenant", on_delete=models.CASCADE, null=True, blank=True, related_name="monitoring_alerts")
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default=SEVERITY_WARNING)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.severity}:{self.title}"


class PlatformActionLog(models.Model):
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="platform_action_logs")
    tenant = models.ForeignKey("clients.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="platform_action_logs")
    action = models.CharField(max_length=50)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=50, blank=True)
    details = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    path = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["action"]),
            models.Index(fields=["model_name"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.action} {self.model_name}#{self.object_id}"


class MaintenanceWindow(models.Model):
    STATUS_SCHEDULED = "SCHEDULED"
    STATUS_ACTIVE = "ACTIVE"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_CHOICES = [
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SCHEDULED)
    notify_tenants = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="maintenance_windows_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-starts_at"]

    def __str__(self):
        return f"{self.title} ({self.status})"


class DeploymentRelease(models.Model):
    STATUS_PLANNED = "PLANNED"
    STATUS_DEPLOYING = "DEPLOYING"
    STATUS_SUCCESS = "SUCCESS"
    STATUS_FAILED = "FAILED"
    STATUS_ROLLED_BACK = "ROLLED_BACK"
    STATUS_CHOICES = [
        (STATUS_PLANNED, "Planned"),
        (STATUS_DEPLOYING, "Deploying"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
        (STATUS_ROLLED_BACK, "Rolled Back"),
    ]

    version = models.CharField(max_length=100)
    environment = models.CharField(max_length=50, default="production")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PLANNED)
    notes = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    health_summary = models.JSONField(default=dict, blank=True)
    rollback_of = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rollback_children",
    )
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="deployment_releases_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.environment}:{self.version}:{self.status}"


class PlatformNotificationDispatch(models.Model):
    EVENT_MAINTENANCE_SCHEDULED = "MAINTENANCE_SCHEDULED"
    EVENT_MAINTENANCE_STARTED = "MAINTENANCE_STARTED"
    EVENT_MAINTENANCE_COMPLETED = "MAINTENANCE_COMPLETED"
    EVENT_MAINTENANCE_CANCELLED = "MAINTENANCE_CANCELLED"
    EVENT_DEPLOYMENT_STARTED = "DEPLOYMENT_STARTED"
    EVENT_DEPLOYMENT_COMPLETED = "DEPLOYMENT_COMPLETED"
    EVENT_DEPLOYMENT_FAILED = "DEPLOYMENT_FAILED"
    EVENT_CHOICES = [
        (EVENT_MAINTENANCE_SCHEDULED, "Maintenance Scheduled"),
        (EVENT_MAINTENANCE_STARTED, "Maintenance Started"),
        (EVENT_MAINTENANCE_COMPLETED, "Maintenance Completed"),
        (EVENT_MAINTENANCE_CANCELLED, "Maintenance Cancelled"),
        (EVENT_DEPLOYMENT_STARTED, "Deployment Started"),
        (EVENT_DEPLOYMENT_COMPLETED, "Deployment Completed"),
        (EVENT_DEPLOYMENT_FAILED, "Deployment Failed"),
    ]

    CHANNEL_EMAIL = "EMAIL"
    CHANNEL_SMS = "SMS"
    CHANNEL_IN_APP = "IN_APP"
    CHANNEL_CHOICES = [
        (CHANNEL_EMAIL, "Email"),
        (CHANNEL_SMS, "SMS"),
        (CHANNEL_IN_APP, "In-App"),
    ]

    STATUS_QUEUED = "QUEUED"
    STATUS_SENT = "SENT"
    STATUS_FAILED = "FAILED"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_SENT, "Sent"),
        (STATUS_FAILED, "Failed"),
    ]

    tenant = models.ForeignKey(
        "clients.Tenant",
        on_delete=models.CASCADE,
        related_name="notification_dispatches",
        null=True,
        blank=True,
    )
    release = models.ForeignKey(
        "clients.DeploymentRelease",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_dispatches",
    )
    maintenance_window = models.ForeignKey(
        "clients.MaintenanceWindow",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_dispatches",
    )
    event_type = models.CharField(max_length=40, choices=EVENT_CHOICES)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    payload = models.JSONField(default=dict, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="platform_notification_dispatches_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_type"]),
            models.Index(fields=["channel"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.event_type}:{self.channel}:{self.status}"


class DeploymentHookRun(models.Model):
    TYPE_TRIGGER = "TRIGGER"
    TYPE_ROLLBACK = "ROLLBACK"
    TYPE_CHOICES = [
        (TYPE_TRIGGER, "Trigger"),
        (TYPE_ROLLBACK, "Rollback"),
    ]

    STATUS_SUCCESS = "SUCCESS"
    STATUS_FAILED = "FAILED"
    STATUS_CHOICES = [
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    release = models.ForeignKey("clients.DeploymentRelease", on_delete=models.CASCADE, related_name="hook_runs")
    hook_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_FAILED)
    endpoint = models.CharField(max_length=255, blank=True)
    request_payload = models.JSONField(default=dict, blank=True)
    response_status = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    error = models.TextField(blank=True)
    executed_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deployment_hook_runs_created",
    )

    class Meta:
        ordering = ["-executed_at"]
        indexes = [
            models.Index(fields=["hook_type"]),
            models.Index(fields=["status"]),
            models.Index(fields=["executed_at"]),
        ]

    def __str__(self):
        return f"{self.release_id}:{self.hook_type}:{self.status}"


class FeatureFlag(models.Model):
    key = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    is_enabled = models.BooleanField(default=False)
    rollout_percent = models.PositiveIntegerField(default=100)
    target_tenants = models.ManyToManyField("clients.Tenant", blank=True, related_name="feature_flags")
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="feature_flags_updated")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return f"{self.key} ({'ON' if self.is_enabled else 'OFF'})"


class BackupJob(models.Model):
    SCOPE_PLATFORM = "PLATFORM"
    SCOPE_TENANT = "TENANT"
    SCOPE_CHOICES = [
        (SCOPE_PLATFORM, "Platform"),
        (SCOPE_TENANT, "Tenant"),
    ]

    TYPE_FULL = "FULL"
    TYPE_INCREMENTAL = "INCREMENTAL"
    TYPE_CHOICES = [
        (TYPE_FULL, "Full"),
        (TYPE_INCREMENTAL, "Incremental"),
    ]

    STATUS_QUEUED = "QUEUED"
    STATUS_RUNNING = "RUNNING"
    STATUS_SUCCESS = "SUCCESS"
    STATUS_FAILED = "FAILED"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default=SCOPE_PLATFORM)
    tenant = models.ForeignKey("clients.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="backup_jobs")
    backup_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_FULL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    storage_path = models.CharField(max_length=255, blank=True)
    checksum = models.CharField(max_length=128, blank=True)
    size_bytes = models.BigIntegerField(default=0)
    retention_days = models.PositiveIntegerField(default=30)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="backup_jobs_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.scope}:{self.backup_type}:{self.status}"


class BackupExecutionRun(models.Model):
    STATUS_SUCCESS = "SUCCESS"
    STATUS_FAILED = "FAILED"
    STATUS_CHOICES = [
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    backup = models.ForeignKey("clients.BackupJob", on_delete=models.CASCADE, related_name="execution_runs")
    engine_mode = models.CharField(max_length=50, default="mock")
    command = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_FAILED)
    output_path = models.CharField(max_length=255, blank=True)
    checksum = models.CharField(max_length=128, blank=True)
    size_bytes = models.BigIntegerField(default=0)
    logs = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="backup_execution_runs_created",
    )

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["engine_mode"]),
            models.Index(fields=["started_at"]),
        ]

    def __str__(self):
        return f"backup={self.backup_id}:{self.engine_mode}:{self.status}"


class RestoreJob(models.Model):
    STATUS_REQUESTED = "REQUESTED"
    STATUS_APPROVED = "APPROVED"
    STATUS_RUNNING = "RUNNING"
    STATUS_SUCCESS = "SUCCESS"
    STATUS_FAILED = "FAILED"
    STATUS_CHOICES = [
        (STATUS_REQUESTED, "Requested"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    backup = models.ForeignKey("clients.BackupJob", on_delete=models.PROTECT, related_name="restore_jobs")
    tenant = models.ForeignKey("clients.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="restore_jobs")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_REQUESTED)
    notes = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="restore_jobs_requested")
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="restore_jobs_approved")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"restore:{self.id}:{self.status}"


class SecurityIncident(models.Model):
    SEVERITY_LOW = "LOW"
    SEVERITY_MEDIUM = "MEDIUM"
    SEVERITY_HIGH = "HIGH"
    SEVERITY_CRITICAL = "CRITICAL"
    SEVERITY_CHOICES = [
        (SEVERITY_LOW, "Low"),
        (SEVERITY_MEDIUM, "Medium"),
        (SEVERITY_HIGH, "High"),
        (SEVERITY_CRITICAL, "Critical"),
    ]

    STATUS_OPEN = "OPEN"
    STATUS_INVESTIGATING = "INVESTIGATING"
    STATUS_RESOLVED = "RESOLVED"
    STATUS_CLOSED = "CLOSED"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_INVESTIGATING, "Investigating"),
        (STATUS_RESOLVED, "Resolved"),
        (STATUS_CLOSED, "Closed"),
    ]

    title = models.CharField(max_length=255)
    category = models.CharField(max_length=100, blank=True)
    tenant = models.ForeignKey("clients.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="security_incidents")
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default=SEVERITY_MEDIUM)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    details = models.TextField(blank=True)
    detected_at = models.DateTimeField(default=models.functions.Now)
    resolved_at = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="security_incidents_assigned")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="security_incidents_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.severity}:{self.title}"


class ComplianceReport(models.Model):
    TYPE_AUDIT = "AUDIT"
    TYPE_ACCESS = "ACCESS"
    TYPE_SECURITY = "SECURITY"
    TYPE_BACKUP = "BACKUP"
    TYPE_CHOICES = [
        (TYPE_AUDIT, "Audit"),
        (TYPE_ACCESS, "Access"),
        (TYPE_SECURITY, "Security"),
        (TYPE_BACKUP, "Backup"),
    ]

    report_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    period_start = models.DateField()
    period_end = models.DateField()
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="compliance_reports_generated")
    payload = models.JSONField(default=dict, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-generated_at"]

    def __str__(self):
        return f"{self.report_type}:{self.period_start}:{self.period_end}"


class PlatformSetting(models.Model):
    key = models.CharField(max_length=120, unique=True)
    value = models.JSONField(default=dict, blank=True)
    description = models.TextField(blank=True)
    is_secret = models.BooleanField(default=False)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="platform_settings_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return self.key


class PlatformApiKey(models.Model):
    tenant = models.ForeignKey("clients.Tenant", on_delete=models.CASCADE, related_name="platform_api_keys")
    label = models.CharField(max_length=120)
    key_prefix = models.CharField(max_length=40)
    key_last_four = models.CharField(max_length=8)
    token_hash = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="platform_api_keys_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "is_active"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.tenant.schema_name}:{self.label}"


class GlobalSuperAdmin(models.Model):
    """Global platform owner. Lives in public schema only."""
    ROLE_OWNER = "OWNER"
    ROLE_ADMIN = "ADMIN"
    ROLE_SUPPORT = "SUPPORT"
    ROLE_AUDITOR = "AUDITOR"
    ROLE_CHOICES = [
        (ROLE_OWNER, "Owner"),
        (ROLE_ADMIN, "Admin"),
        (ROLE_SUPPORT, "Support"),
        (ROLE_AUDITOR, "Auditor"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='global_admin')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_ADMIN)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return self.user.username


# ==========================================
# REVENUE LOG — SaaS Platform Revenue (Phase 7)
# ==========================================

class RevenueLog(models.Model):
    """
    Track platform revenue from transaction fees and subscriptions.
    Stored in public schema (clients app). Links to Tenant by schema_name.
    """
    SOURCE_CHOICES = [
        ('TRANSACTION_FEE', 'Transaction Fee'),
        ('SUBSCRIPTION', 'Subscription'),
        ('SETUP_FEE', 'Setup Fee'),
        ('CUSTOM', 'Custom'),
    ]

    schema_name = models.CharField(max_length=63, db_index=True,
        help_text='Tenant schema this revenue came from')
    school_name = models.CharField(max_length=200, blank=True,
        help_text='School name for display')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)
    mpesa_receipt = models.CharField(max_length=50, blank=True, db_index=True)
    subscription = models.ForeignKey('TenantSubscription', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='revenue_logs')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['schema_name', 'source', 'created_at']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = 'Revenue Log'

    def __str__(self):
        return f"{self.source}: {self.amount} from {self.schema_name}"

    @classmethod
    def record_transaction_fee(cls, schema_name, school_name, fee_amount, mpesa_receipt='', metadata=None):
        return cls.objects.create(
            schema_name=schema_name,
            school_name=school_name,
            amount=fee_amount,
            source='TRANSACTION_FEE',
            description=f'Transaction fee from {mpesa_receipt or "payment"}',
            mpesa_receipt=mpesa_receipt,
            metadata=metadata or {},
        )

    @classmethod
    def get_total_revenue(cls, start_date=None, end_date=None):
        from django.db.models import Sum
        qs = cls.objects.all()
        if start_date:
            qs = qs.filter(created_at__date__gte=start_date)
        if end_date:
            qs = qs.filter(created_at__date__lte=end_date)
        return qs.aggregate(total=Sum('amount'))['total'] or 0

    @classmethod
    def get_revenue_by_school(cls, start_date=None, end_date=None):
        from django.db.models import Sum
        qs = cls.objects.all()
        if start_date:
            qs = qs.filter(created_at__date__gte=start_date)
        if end_date:
            qs = qs.filter(created_at__date__lte=end_date)
        return qs.values('schema_name', 'school_name').annotate(total=Sum('amount')).order_by('-total')
