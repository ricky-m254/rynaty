from rest_framework import serializers

from clients.models import (
    BackupJob,
    BackupExecutionRun,
    ComplianceReport,
    DeploymentHookRun,
    DeploymentRelease,
    FeatureFlag,
    GlobalSuperAdmin,
    ImpersonationSession,
    MaintenanceWindow,
    MonitoringAlert,
    MonitoringSnapshot,
    PlatformApiKey,
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
    TenantDataImportFile,
    TenantDataImportRequest,
    TenantSubscription,
)


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = [
            "id",
            "code",
            "name",
            "description",
            "monthly_price",
            "annual_price",
            "max_students",
            "max_storage_gb",
            "enabled_modules",
            "is_active",
        ]
        read_only_fields = ["id"]


class TenantSerializer(serializers.ModelSerializer):
    domains = serializers.SerializerMethodField()
    subscription_plan_detail = SubscriptionPlanSerializer(source="subscription_plan", read_only=True)

    class Meta:
        model = Tenant
        fields = [
            "id",
            "schema_name",
            "name",
            "subdomain",
            "custom_domain",
            "contact_name",
            "contact_email",
            "contact_phone",
            "status",
            "subscription_plan",
            "subscription_plan_detail",
            "trial_start",
            "trial_end",
            "activated_at",
            "suspended_at",
            "suspension_reason",
            "max_students",
            "max_storage_gb",
            "is_active",
            "paid_until",
            "created_at",
            "updated_at",
            "domains",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "activated_at",
            "suspended_at",
            "domains",
            "subscription_plan_detail",
        ]

    def get_domains(self, obj: Tenant):
        return list(obj.domains.order_by("-is_primary", "domain").values("id", "domain", "is_primary"))


class TenantProvisionSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    subdomain = serializers.CharField(max_length=100, required=False, allow_blank=True)
    schema_name = serializers.CharField(max_length=63, required=False, allow_blank=True)
    custom_domain = serializers.CharField(max_length=255, required=False, allow_blank=True)
    contact_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    contact_phone = serializers.CharField(max_length=50, required=False, allow_blank=True)
    subscription_plan = serializers.PrimaryKeyRelatedField(
        queryset=SubscriptionPlan.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    trial_days = serializers.IntegerField(required=False, min_value=1, max_value=365)
    max_students = serializers.IntegerField(required=False, min_value=1)
    max_storage_gb = serializers.IntegerField(required=False, min_value=1)

    school_admin_username = serializers.CharField(max_length=150, required=False, allow_blank=True)
    school_admin_email = serializers.EmailField(required=False, allow_blank=True)
    school_admin_password = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)


class TenantSuspendSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


class TenantAssignPlanSerializer(serializers.Serializer):
    subscription_plan = serializers.PrimaryKeyRelatedField(queryset=SubscriptionPlan.objects.filter(is_active=True))
    billing_cycle = serializers.ChoiceField(
        choices=[TenantSubscription.BILLING_MONTHLY, TenantSubscription.BILLING_ANNUAL],
        default=TenantSubscription.BILLING_MONTHLY,
    )
    starts_on = serializers.DateField(required=False)
    grace_period_days = serializers.IntegerField(required=False, min_value=0, max_value=90)


class TenantAdminCredentialSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, required=False, allow_blank=True)
    password = serializers.CharField(min_length=8, trim_whitespace=False)
    email = serializers.EmailField(required=False, allow_blank=True)


class TenantDataImportFileSerializer(serializers.ModelSerializer):
    uploaded_by_username = serializers.CharField(source="uploaded_by.username", read_only=True)
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = TenantDataImportFile
        fields = [
            "id",
            "original_name",
            "content_type",
            "size_bytes",
            "checksum_sha256",
            "uploaded_by",
            "uploaded_by_username",
            "uploaded_at",
            "download_url",
        ]
        read_only_fields = fields

    def get_download_url(self, obj):
        request = self.context.get("request")
        if not getattr(obj, "file", None):
            return ""
        url = obj.file.url
        return request.build_absolute_uri(url) if request else url


class TenantDataImportRequestSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    tenant_schema_name = serializers.CharField(source="tenant.schema_name", read_only=True)
    requested_by_username = serializers.CharField(source="requested_by.username", read_only=True)
    files = TenantDataImportFileSerializer(many=True, read_only=True)
    files_total = serializers.SerializerMethodField()
    total_size_bytes = serializers.SerializerMethodField()
    import_profile_label = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()
    automation_ready = serializers.SerializerMethodField()
    missing_required_files = serializers.SerializerMethodField()
    command_preview = serializers.SerializerMethodField()

    class Meta:
        model = TenantDataImportRequest
        fields = [
            "id",
            "tenant",
            "tenant_name",
            "tenant_schema_name",
            "import_profile",
            "import_profile_label",
            "status",
            "status_label",
            "source_system",
            "source_reference",
            "school_name_override",
            "notes",
            "archive_raw_to_media",
            "requested_by",
            "requested_by_username",
            "processed_at",
            "last_error",
            "result_payload",
            "files_total",
            "total_size_bytes",
            "automation_ready",
            "missing_required_files",
            "command_preview",
            "files",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tenant_name",
            "tenant_schema_name",
            "import_profile_label",
            "status_label",
            "requested_by",
            "requested_by_username",
            "processed_at",
            "last_error",
            "result_payload",
            "files_total",
            "total_size_bytes",
            "automation_ready",
            "missing_required_files",
            "command_preview",
            "files",
            "created_at",
            "updated_at",
        ]

    def _profile_spec(self, obj) -> dict:
        specs = {
            TenantDataImportRequest.PROFILE_LEGACY_WORKBOOK_BUNDLE: {
                "required_files": [
                    "Transact 2023_Backup.xlsx",
                    "Transact 2026_Backup.xlsx",
                ],
                "command_preview": f"python manage.py run_platform_data_import_request --request-id {obj.id}",
            },
            TenantDataImportRequest.PROFILE_MANUAL_ARCHIVE: {
                "required_files": [],
                "command_preview": "",
            },
        }
        return specs.get(obj.import_profile, {"required_files": [], "command_preview": ""})

    def get_files_total(self, obj):
        prefetched = getattr(obj, "_prefetched_objects_cache", {}).get("files")
        return len(prefetched) if prefetched is not None else obj.files.count()

    def get_total_size_bytes(self, obj):
        prefetched = getattr(obj, "_prefetched_objects_cache", {}).get("files")
        if prefetched is not None:
            return sum(getattr(item, "size_bytes", 0) or 0 for item in prefetched)
        return sum(obj.files.values_list("size_bytes", flat=True))

    def get_import_profile_label(self, obj):
        return obj.get_import_profile_display()

    def get_status_label(self, obj):
        return obj.get_status_display()

    def get_missing_required_files(self, obj):
        required = self._profile_spec(obj)["required_files"]
        attached = {row.original_name for row in obj.files.all()}
        return [name for name in required if name not in attached]

    def get_automation_ready(self, obj):
        spec = self._profile_spec(obj)
        if not spec["command_preview"]:
            return False
        return not self.get_missing_required_files(obj)

    def get_command_preview(self, obj):
        if not self.get_automation_ready(obj):
            return ""
        command = self._profile_spec(obj)["command_preview"]
        if obj.archive_raw_to_media:
            command = f"{command} --archive-raw"
        return command


class TenantDataImportRequestCreateSerializer(serializers.Serializer):
    tenant = serializers.PrimaryKeyRelatedField(queryset=Tenant.objects.order_by("name"))
    import_profile = serializers.ChoiceField(
        choices=TenantDataImportRequest.PROFILE_CHOICES,
        default=TenantDataImportRequest.PROFILE_LEGACY_WORKBOOK_BUNDLE,
    )
    source_system = serializers.CharField(max_length=120, required=False, allow_blank=True)
    source_reference = serializers.CharField(max_length=120, required=False, allow_blank=True)
    school_name_override = serializers.CharField(max_length=255, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    archive_raw_to_media = serializers.BooleanField(required=False, default=True)


class TenantDataImportRequestUpdateSerializer(serializers.Serializer):
    import_profile = serializers.ChoiceField(
        choices=TenantDataImportRequest.PROFILE_CHOICES,
        required=False,
    )
    status = serializers.ChoiceField(
        choices=TenantDataImportRequest.STATUS_CHOICES,
        required=False,
    )
    source_system = serializers.CharField(max_length=120, required=False, allow_blank=True)
    source_reference = serializers.CharField(max_length=120, required=False, allow_blank=True)
    school_name_override = serializers.CharField(max_length=255, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    archive_raw_to_media = serializers.BooleanField(required=False)


class TenantSubscriptionSerializer(serializers.ModelSerializer):
    plan_detail = SubscriptionPlanSerializer(source="plan", read_only=True)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)

    class Meta:
        model = TenantSubscription
        fields = [
            "id",
            "tenant",
            "tenant_name",
            "plan",
            "plan_detail",
            "billing_cycle",
            "status",
            "starts_on",
            "ends_on",
            "trial_end",
            "next_billing_date",
            "grace_period_days",
            "is_current",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "plan_detail", "tenant_name"]


class SubscriptionInvoiceSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)

    class Meta:
        model = SubscriptionInvoice
        fields = [
            "id",
            "tenant",
            "tenant_name",
            "subscription",
            "invoice_number",
            "billing_cycle",
            "status",
            "currency",
            "amount",
            "tax_amount",
            "discount_amount",
            "total_amount",
            "period_start",
            "period_end",
            "issued_at",
            "due_date",
            "paid_at",
            "external_reference",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "issued_at", "paid_at", "tenant_name"]


class SubscriptionPaymentSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="invoice.tenant.name", read_only=True)
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)
    transaction_code = serializers.CharField(source="transaction_id", read_only=True)
    invoice_status = serializers.CharField(source="invoice.status", read_only=True)

    class Meta:
        model = SubscriptionPayment
        fields = [
            "id",
            "invoice",
            "invoice_number",
            "tenant_name",
            "amount",
            "method",
            "status",
            "paid_at",
            "transaction_id",
            "transaction_code",
            "invoice_status",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "paid_at"]


class SubscriptionPaymentCreateSerializer(serializers.Serializer):
    invoice = serializers.PrimaryKeyRelatedField(queryset=SubscriptionInvoice.objects.select_related("tenant", "subscription"))
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    method = serializers.CharField(required=False, allow_blank=True, max_length=50, default="M-Pesa")
    status = serializers.ChoiceField(
        choices=SubscriptionPayment.STATUS_CHOICES,
        required=False,
        default=SubscriptionPayment.STATUS_PENDING,
    )
    transaction_id = serializers.CharField(required=False, allow_blank=True, max_length=128)
    external_reference = serializers.CharField(required=False, allow_blank=True, max_length=128)
    metadata = serializers.JSONField(required=False)


class SubscriptionPaymentReviewSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


class InvoicePaymentCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    method = serializers.CharField(required=False, allow_blank=True, max_length=50)
    status = serializers.ChoiceField(
        choices=SubscriptionPayment.STATUS_CHOICES,
        required=False,
        default=SubscriptionPayment.STATUS_PAID,
    )
    transaction_id = serializers.CharField(required=False, allow_blank=True, max_length=128)
    external_reference = serializers.CharField(required=False, allow_blank=True, max_length=128)
    metadata = serializers.JSONField(required=False)


class SupportTicketSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    assigned_to_username = serializers.CharField(source="assigned_to.username", read_only=True)

    class Meta:
        model = SupportTicket
        fields = [
            "id",
            "ticket_number",
            "tenant",
            "tenant_name",
            "category",
            "priority",
            "status",
            "subject",
            "description",
            "created_by_email",
            "assigned_to",
            "assigned_to_username",
            "first_response_at",
            "resolved_at",
            "closed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "ticket_number",
            "status",
            "assigned_to",
            "first_response_at",
            "resolved_at",
            "closed_at",
            "created_at",
            "updated_at",
            "tenant_name",
            "assigned_to_username",
        ]


class SupportTicketNoteSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source="author.username", read_only=True)

    class Meta:
        model = SupportTicketNote
        fields = ["id", "ticket", "author", "author_username", "body", "is_internal", "created_at"]
        read_only_fields = ["id", "author", "author_username", "created_at"]


class SupportTicketNoteCreateSerializer(serializers.Serializer):
    body = serializers.CharField()
    is_internal = serializers.BooleanField(default=True)


class ImpersonationSessionSerializer(serializers.ModelSerializer):
    requested_by_username = serializers.CharField(source="requested_by.username", read_only=True)
    approved_by_username = serializers.CharField(source="approved_by.username", read_only=True)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)

    class Meta:
        model = ImpersonationSession
        fields = [
            "id",
            "tenant",
            "tenant_name",
            "target_username",
            "requested_by",
            "requested_by_username",
            "approved_by",
            "approved_by_username",
            "status",
            "reason",
            "read_only",
            "duration_minutes",
            "started_at",
            "expires_at",
            "ended_at",
            "approval_notes",
            "session_token",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "requested_by",
            "approved_by",
            "status",
            "requested_by_username",
            "approved_by_username",
            "started_at",
            "expires_at",
            "ended_at",
            "session_token",
            "created_at",
            "updated_at",
            "tenant_name",
        ]

    def validate_target_username(self, value):
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("target_username cannot be blank.")
        return cleaned

    def validate_duration_minutes(self, value):
        if value < 1 or value > 240:
            raise serializers.ValidationError("duration_minutes must be between 1 and 240.")
        return value


class ImpersonationApprovalSerializer(serializers.Serializer):
    approval_notes = serializers.CharField(required=False, allow_blank=True, max_length=500)


class MonitoringSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonitoringSnapshot
        fields = ["id", "metric_key", "tenant", "value", "payload", "captured_at", "created_at"]
        read_only_fields = ["id", "created_at"]


class MonitoringAlertSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)

    class Meta:
        model = MonitoringAlert
        fields = [
            "id",
            "title",
            "metric_key",
            "tenant",
            "tenant_name",
            "severity",
            "status",
            "details",
            "created_at",
            "acknowledged_at",
            "resolved_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "created_at",
            "acknowledged_at",
            "resolved_at",
            "tenant_name",
        ]


class PlatformActionLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)

    class Meta:
        model = PlatformActionLog
        fields = [
            "id",
            "actor",
            "actor_username",
            "tenant",
            "tenant_name",
            "action",
            "model_name",
            "object_id",
            "details",
            "metadata",
            "ip_address",
            "path",
            "created_at",
        ]
        read_only_fields = fields


class MaintenanceWindowSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = MaintenanceWindow
        fields = [
            "id",
            "title",
            "description",
            "starts_at",
            "ends_at",
            "status",
            "notify_tenants",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "created_by", "created_by_username", "created_at", "updated_at"]


class DeploymentReleaseSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = DeploymentRelease
        fields = [
            "id",
            "version",
            "environment",
            "status",
            "notes",
            "started_at",
            "completed_at",
            "health_summary",
            "rollback_of",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "started_at", "completed_at", "created_by", "created_by_username", "created_at", "updated_at"]


class DeploymentHookRunSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = DeploymentHookRun
        fields = [
            "id",
            "release",
            "hook_type",
            "status",
            "endpoint",
            "request_payload",
            "response_status",
            "response_body",
            "error",
            "executed_at",
            "created_by",
            "created_by_username",
        ]
        read_only_fields = fields


class PlatformNotificationDispatchSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = PlatformNotificationDispatch
        fields = [
            "id",
            "tenant",
            "tenant_name",
            "release",
            "maintenance_window",
            "event_type",
            "channel",
            "status",
            "payload",
            "attempts",
            "last_error",
            "sent_at",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class FeatureFlagSerializer(serializers.ModelSerializer):
    updated_by_username = serializers.CharField(source="updated_by.username", read_only=True)

    class Meta:
        model = FeatureFlag
        fields = [
            "id",
            "key",
            "description",
            "is_enabled",
            "rollout_percent",
            "target_tenants",
            "updated_by",
            "updated_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_by", "updated_by_username", "created_at", "updated_at"]

    def validate_rollout_percent(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("rollout_percent must be between 0 and 100.")
        return value


class BackupJobSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = BackupJob
        fields = [
            "id",
            "scope",
            "tenant",
            "tenant_name",
            "backup_type",
            "status",
            "storage_path",
            "checksum",
            "size_bytes",
            "retention_days",
            "started_at",
            "completed_at",
            "error",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "started_at", "completed_at", "error", "created_by", "created_by_username", "created_at", "updated_at", "tenant_name"]


class BackupExecutionRunSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = BackupExecutionRun
        fields = [
            "id",
            "backup",
            "engine_mode",
            "command",
            "status",
            "output_path",
            "checksum",
            "size_bytes",
            "logs",
            "started_at",
            "completed_at",
            "created_by",
            "created_by_username",
        ]
        read_only_fields = fields


class RestoreJobSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    requested_by_username = serializers.CharField(source="requested_by.username", read_only=True)
    approved_by_username = serializers.CharField(source="approved_by.username", read_only=True)

    class Meta:
        model = RestoreJob
        fields = [
            "id",
            "backup",
            "tenant",
            "tenant_name",
            "status",
            "notes",
            "started_at",
            "completed_at",
            "requested_by",
            "requested_by_username",
            "approved_by",
            "approved_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "started_at",
            "completed_at",
            "requested_by",
            "requested_by_username",
            "approved_by",
            "approved_by_username",
            "created_at",
            "updated_at",
            "tenant_name",
        ]


class SecurityIncidentSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    assigned_to_username = serializers.CharField(source="assigned_to.username", read_only=True)
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = SecurityIncident
        fields = [
            "id",
            "title",
            "category",
            "tenant",
            "tenant_name",
            "severity",
            "status",
            "details",
            "detected_at",
            "resolved_at",
            "assigned_to",
            "assigned_to_username",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "detected_at",
            "resolved_at",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
            "tenant_name",
            "assigned_to_username",
        ]


class ComplianceReportSerializer(serializers.ModelSerializer):
    generated_by_username = serializers.CharField(source="generated_by.username", read_only=True)

    class Meta:
        model = ComplianceReport
        fields = [
            "id",
            "report_type",
            "period_start",
            "period_end",
            "generated_by",
            "generated_by_username",
            "payload",
            "generated_at",
        ]
        read_only_fields = ["id", "generated_by", "generated_by_username", "payload", "generated_at"]


class PlatformSettingSerializer(serializers.ModelSerializer):
    updated_by_username = serializers.CharField(source="updated_by.username", read_only=True)

    class Meta:
        model = PlatformSetting
        fields = [
            "id",
            "key",
            "value",
            "description",
            "is_secret",
            "updated_by",
            "updated_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_by", "updated_by_username", "created_at", "updated_at"]


class PlatformApiKeySerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    key = serializers.SerializerMethodField()

    class Meta:
        model = PlatformApiKey
        fields = [
            "id",
            "tenant",
            "tenant_name",
            "label",
            "key",
            "is_active",
            "last_used_at",
            "revoked_at",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tenant_name",
            "key",
            "is_active",
            "last_used_at",
            "revoked_at",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]

    def get_key(self, obj):
        return f"{obj.key_prefix}••••••••{obj.key_last_four}"


class PlatformApiKeyCreateSerializer(serializers.Serializer):
    tenant = serializers.PrimaryKeyRelatedField(queryset=Tenant.objects.order_by("name"))
    label = serializers.CharField(max_length=120)

    def validate_label(self, value):
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("label cannot be blank.")
        return cleaned


class PlatformAdminUserSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    is_staff = serializers.BooleanField(source="user.is_staff", read_only=True)
    is_superuser = serializers.BooleanField(source="user.is_superuser", read_only=True)

    class Meta:
        model = GlobalSuperAdmin
        fields = [
            "id",
            "user_id",
            "username",
            "email",
            "role",
            "is_active",
            "is_staff",
            "is_superuser",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class PlatformAdminUserCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)
    role = serializers.ChoiceField(
        choices=[
            GlobalSuperAdmin.ROLE_OWNER,
            GlobalSuperAdmin.ROLE_ADMIN,
            GlobalSuperAdmin.ROLE_SUPPORT,
            GlobalSuperAdmin.ROLE_AUDITOR,
        ],
        default=GlobalSuperAdmin.ROLE_ADMIN,
    )
    is_active = serializers.BooleanField(default=True)


class PlatformAdminPasswordResetSerializer(serializers.Serializer):
    password = serializers.CharField(min_length=8, trim_whitespace=False)
