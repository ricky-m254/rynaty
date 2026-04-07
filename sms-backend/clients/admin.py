from django.contrib import admin
from .models import (
    BackupExecutionRun,
    DeploymentHookRun,
    Domain,
    FeatureFlag,
    GlobalSuperAdmin,
    MaintenanceWindow,
    ImpersonationSession,
    BackupJob,
    ComplianceReport,
    DeploymentRelease,
    MonitoringAlert,
    MonitoringSnapshot,
    PlatformNotificationDispatch,
    PlatformActionLog,
    PlatformSetting,
    RestoreJob,
    SecurityIncident,
    SubscriptionInvoice,
    SubscriptionPayment,
    SubscriptionPlan,
    SupportTicket,
    SupportTicketNote,
    Tenant,
    TenantSubscription,
)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'monthly_price', 'annual_price', 'max_students', 'max_storage_gb', 'is_active']
    search_fields = ['code', 'name']

@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['name', 'schema_name', 'subdomain', 'status', 'is_active', 'paid_until']
    search_fields = ['name', 'schema_name', 'subdomain', 'contact_email']


@admin.register(TenantSubscription)
class TenantSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'plan', 'billing_cycle', 'status', 'starts_on', 'next_billing_date', 'is_current']
    search_fields = ['tenant__name', 'tenant__schema_name', 'plan__code']


@admin.register(SubscriptionInvoice)
class SubscriptionInvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'tenant', 'billing_cycle', 'status', 'total_amount', 'due_date', 'issued_at']
    search_fields = ['invoice_number', 'tenant__name', 'tenant__schema_name', 'external_reference']


@admin.register(SubscriptionPayment)
class SubscriptionPaymentAdmin(admin.ModelAdmin):
    list_display = ['invoice', 'amount', 'method', 'status', 'paid_at', 'transaction_id']
    search_fields = ['invoice__invoice_number', 'transaction_id', 'method']


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ['ticket_number', 'tenant', 'category', 'priority', 'status', 'assigned_to', 'created_at']
    search_fields = ['ticket_number', 'subject', 'tenant__name', 'tenant__schema_name']


@admin.register(SupportTicketNote)
class SupportTicketNoteAdmin(admin.ModelAdmin):
    list_display = ['ticket', 'author', 'is_internal', 'created_at']
    search_fields = ['ticket__ticket_number', 'author__username']


@admin.register(ImpersonationSession)
class ImpersonationSessionAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'target_username', 'status', 'requested_by', 'approved_by', 'read_only', 'created_at']
    search_fields = ['tenant__name', 'tenant__schema_name', 'target_username']


@admin.register(MonitoringSnapshot)
class MonitoringSnapshotAdmin(admin.ModelAdmin):
    list_display = ['metric_key', 'tenant', 'value', 'captured_at']
    search_fields = ['metric_key', 'tenant__name', 'tenant__schema_name']


@admin.register(MonitoringAlert)
class MonitoringAlertAdmin(admin.ModelAdmin):
    list_display = ['title', 'metric_key', 'tenant', 'severity', 'status', 'created_at']
    search_fields = ['title', 'metric_key', 'tenant__name', 'tenant__schema_name']


@admin.register(MaintenanceWindow)
class MaintenanceWindowAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'starts_at', 'ends_at', 'notify_tenants']
    search_fields = ['title', 'description']


@admin.register(DeploymentRelease)
class DeploymentReleaseAdmin(admin.ModelAdmin):
    list_display = ['version', 'environment', 'status', 'started_at', 'completed_at', 'created_at']
    search_fields = ['version', 'environment', 'notes']


@admin.register(DeploymentHookRun)
class DeploymentHookRunAdmin(admin.ModelAdmin):
    list_display = ['release', 'hook_type', 'status', 'response_status', 'executed_at']
    search_fields = ['release__version', 'hook_type', 'status', 'endpoint']


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ['key', 'is_enabled', 'rollout_percent', 'updated_at']
    search_fields = ['key', 'description']


@admin.register(BackupJob)
class BackupJobAdmin(admin.ModelAdmin):
    list_display = ['scope', 'tenant', 'backup_type', 'status', 'started_at', 'completed_at']
    search_fields = ['storage_path', 'checksum', 'tenant__name', 'tenant__schema_name']


@admin.register(BackupExecutionRun)
class BackupExecutionRunAdmin(admin.ModelAdmin):
    list_display = ['backup', 'engine_mode', 'status', 'size_bytes', 'started_at', 'completed_at']
    search_fields = ['backup__id', 'engine_mode', 'status', 'output_path']


@admin.register(RestoreJob)
class RestoreJobAdmin(admin.ModelAdmin):
    list_display = ['backup', 'tenant', 'status', 'requested_by', 'approved_by', 'created_at']
    search_fields = ['tenant__name', 'tenant__schema_name', 'notes']


@admin.register(SecurityIncident)
class SecurityIncidentAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'tenant', 'severity', 'status', 'detected_at']
    search_fields = ['title', 'category', 'tenant__name', 'tenant__schema_name']


@admin.register(ComplianceReport)
class ComplianceReportAdmin(admin.ModelAdmin):
    list_display = ['report_type', 'period_start', 'period_end', 'generated_by', 'generated_at']
    search_fields = ['report_type']


@admin.register(PlatformActionLog)
class PlatformActionLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'action', 'model_name', 'object_id', 'tenant', 'actor', 'ip_address']
    search_fields = ['action', 'model_name', 'object_id', 'tenant__name', 'tenant__schema_name', 'actor__username']


@admin.register(PlatformNotificationDispatch)
class PlatformNotificationDispatchAdmin(admin.ModelAdmin):
    list_display = ['event_type', 'channel', 'status', 'tenant', 'release', 'maintenance_window', 'created_at']
    search_fields = ['event_type', 'channel', 'status', 'tenant__name', 'release__version']


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ['domain', 'tenant', 'is_primary']
    search_fields = ['domain']

@admin.register(GlobalSuperAdmin)
class GlobalSuperAdminAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'is_active', 'created_at', 'updated_at']
    search_fields = ['user__username', 'user__email']


@admin.register(PlatformSetting)
class PlatformSettingAdmin(admin.ModelAdmin):
    list_display = ['key', 'is_secret', 'updated_by', 'updated_at']
    search_fields = ['key', 'description']
