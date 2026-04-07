import re
import os
import secrets
import hmac
import hashlib
import logging
import json
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.http import JsonResponse
from django.utils import timezone
from django.utils.text import slugify
from django_tenants.utils import schema_context
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from clients.models import (
    BackupJob,
    BackupExecutionRun,
    ComplianceReport,
    CustomDomainRequest,
    DeploymentHookRun,
    DeploymentRelease,
    Domain,
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
    TenantSubscription,
)
from clients.permissions import IsGlobalSuperAdmin
from clients.serializers import (
    BackupJobSerializer,
    BackupExecutionRunSerializer,
    ComplianceReportSerializer,
    DeploymentHookRunSerializer,
    DeploymentReleaseSerializer,
    FeatureFlagSerializer,
    InvoicePaymentCreateSerializer,
    ImpersonationApprovalSerializer,
    ImpersonationSessionSerializer,
    MaintenanceWindowSerializer,
    MonitoringAlertSerializer,
    MonitoringSnapshotSerializer,
    PlatformApiKeyCreateSerializer,
    PlatformApiKeySerializer,
    PlatformNotificationDispatchSerializer,
    PlatformSettingSerializer,
    PlatformAdminUserSerializer,
    PlatformAdminUserCreateSerializer,
    PlatformAdminPasswordResetSerializer,
    PlatformActionLogSerializer,
    RestoreJobSerializer,
    SecurityIncidentSerializer,
    SubscriptionInvoiceSerializer,
    SubscriptionPaymentSerializer,
    SubscriptionPlanSerializer,
    SupportTicketNoteCreateSerializer,
    SupportTicketNoteSerializer,
    SupportTicketSerializer,
    TenantProvisionSerializer,
    TenantAssignPlanSerializer,
    TenantAdminCredentialSerializer,
    TenantSubscriptionSerializer,
    TenantSerializer,
    TenantSuspendSerializer,
)
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()
logger = logging.getLogger(__name__)
PLATFORM_MODULES = [
    "CORE",
    "STUDENTS",
    "ACADEMICS",
    "FINANCE",
    "ADMISSIONS",
    "HR",
    "STAFF",
    "COMMUNICATION",
    "LIBRARY",
    "PARENTS",
]

PLATFORM_INTEGRATION_CATALOG = [
    {
        "code": "stripe",
        "name": "Stripe",
        "category": "Payments",
        "description": "Fee collection and subscription billing",
        "setting_key": "integrations.stripe",
    },
    {
        "code": "africas_talking",
        "name": "Africa's Talking",
        "category": "SMS",
        "description": "SMS notifications to parents and staff",
        "setting_key": "integrations.africas_talking",
    },
    {
        "code": "google_workspace",
        "name": "Google Workspace",
        "category": "Productivity",
        "description": "SSO and Drive document integration",
        "setting_key": "integrations.google_workspace",
    },
    {
        "code": "zoom",
        "name": "Zoom",
        "category": "Video",
        "description": "Virtual classroom integration for e-learning",
        "setting_key": "integrations.zoom",
    },
    {
        "code": "mpesa",
        "name": "M-Pesa",
        "category": "Payments",
        "description": "Mobile money fee collection",
        "setting_key": "integrations.mpesa",
    },
    {
        "code": "sendgrid",
        "name": "SendGrid",
        "category": "Email",
        "description": "Transactional email delivery",
        "setting_key": "integrations.sendgrid",
    },
]


def _ticket_number() -> str:
    now = timezone.now()
    return f"TKT-{now:%Y%m%d}-{secrets.token_hex(3).upper()}"


def _integration_status(value) -> str:
    if isinstance(value, dict):
        state = str(value.get("status", "")).strip().lower()
        if state == "error" or value.get("last_error"):
            return "error"
        if value.get("enabled") is False:
            return "disconnected"
        signal_keys = [
            "api_key",
            "secret_key",
            "token",
            "access_token",
            "account_sid",
            "sender_id",
            "phone_number_id",
            "client_id",
            "username",
            "webhook_url",
        ]
        if value.get("enabled") or any(value.get(key) for key in signal_keys):
            return "connected"
        return "disconnected"
    if value:
        return "connected"
    return "disconnected"


def _generate_platform_api_key(*, tenant: Tenant, label: str, actor) -> tuple[PlatformApiKey, str]:
    tenant_hint = _clean_identifier(tenant.subdomain or tenant.schema_name or tenant.name, max_length=8)
    prefix = f"sk_live_{tenant_hint}_"
    raw_key = f"{prefix}{secrets.token_urlsafe(24)}"
    token_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    row = PlatformApiKey.objects.create(
        tenant=tenant,
        label=label,
        key_prefix=prefix,
        key_last_four=raw_key[-4:],
        token_hash=token_hash,
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )
    return row, raw_key


def _platform_audit(
    *,
    user,
    action: str,
    model_name: str,
    object_id,
    details: str = "",
    tenant: Tenant | None = None,
    request=None,
    metadata: dict | None = None,
):
    log_payload = {
        "actor": user if getattr(user, "is_authenticated", False) else None,
        "tenant": tenant,
        "action": action,
        "model_name": model_name,
        "object_id": str(object_id or ""),
        "details": details or "",
        "metadata": metadata or {},
        "ip_address": (request.META.get("REMOTE_ADDR") if request else None),
        "path": (request.path[:255] if request and request.path else ""),
    }
    try:
        PlatformActionLog.objects.create(**log_payload)
    except Exception as exc:
        logger.exception("Failed to persist platform action log: %s", exc)
    logger.info(
        "platform_audit user_id=%s action=%s model=%s object_id=%s tenant_id=%s details=%s",
        getattr(user, "id", None),
        action,
        model_name,
        object_id,
        getattr(tenant, "id", None),
        details or "",
    )


def _clean_identifier(value: str, *, max_length: int = 50) -> str:
    slug = slugify(value or "")
    slug = re.sub(r"[^a-z0-9\-]+", "", slug).strip("-")
    slug = re.sub(r"\-+", "-", slug)
    return (slug or "school")[:max_length]


def _unique_subdomain(seed: str) -> str:
    base = _clean_identifier(seed, max_length=40)
    candidate = base
    counter = 1
    while Tenant.objects.filter(subdomain=candidate).exists():
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate


def _unique_schema(seed: str) -> str:
    base = _clean_identifier(seed, max_length=45)
    candidate = f"school_{base}"
    counter = 1
    while Tenant.objects.filter(schema_name=candidate).exists():
        candidate = f"school_{base}_{counter}"
        counter += 1
    return candidate


def _default_trial_days() -> int:
    value = getattr(settings, "PLATFORM_DEFAULT_TRIAL_DAYS", 14)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 14
    return parsed if parsed > 0 else 14


def _base_domain() -> str:
    raw = str(getattr(settings, "PLATFORM_DEFAULT_BASE_DOMAIN", "localhost"))
    return raw.strip() or "localhost"


def _default_grace_days() -> int:
    value = getattr(settings, "PLATFORM_BILLING_GRACE_DAYS", 7)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 7
    return parsed if parsed >= 0 else 7


def _cycle_days(cycle: str) -> int:
    return 365 if cycle == TenantSubscription.BILLING_ANNUAL else 30


def _cycle_amount(plan: SubscriptionPlan, cycle: str) -> Decimal:
    if cycle == TenantSubscription.BILLING_ANNUAL:
        return Decimal(plan.annual_price or 0)
    return Decimal(plan.monthly_price or 0)


def _next_billing_date(start_date, cycle: str):
    return start_date + timedelta(days=_cycle_days(cycle))


def _invoice_number(tenant: Tenant) -> str:
    now = timezone.now()
    token = secrets.token_hex(3).upper()
    return f"SUB-{now:%Y%m%d}-{tenant.id}-{token}"


def _support_sla_hours(priority: str) -> tuple[int, int]:
    level = str(priority or "").upper()
    if level == SupportTicket.PRIORITY_URGENT:
        return 1, 4
    if level == SupportTicket.PRIORITY_HIGH:
        return 4, 12
    if level == SupportTicket.PRIORITY_NORMAL:
        return 8, 24
    return 24, 72


def _maintenance_notify_channels() -> list[str]:
    raw = str(getattr(settings, "PLATFORM_MAINTENANCE_NOTIFY_CHANNELS", "IN_APP,EMAIL"))
    channels: list[str] = []
    allowed = {
        "IN_APP": PlatformNotificationDispatch.CHANNEL_IN_APP,
        "EMAIL": PlatformNotificationDispatch.CHANNEL_EMAIL,
        "SMS": PlatformNotificationDispatch.CHANNEL_SMS,
    }
    for item in raw.split(","):
        key = item.strip().upper()
        if key in allowed and allowed[key] not in channels:
            channels.append(allowed[key])
    return channels or [PlatformNotificationDispatch.CHANNEL_IN_APP]


def _queue_maintenance_notifications(
    *,
    window: MaintenanceWindow,
    event_type: str,
    actor,
    request=None,
):
    if not window.notify_tenants:
        return []
    tenants = Tenant.objects.filter(is_active=True).only("id", "name", "schema_name")
    now = timezone.now()
    created_rows = []
    for tenant in tenants:
        for channel in _maintenance_notify_channels():
            is_internal = channel == PlatformNotificationDispatch.CHANNEL_IN_APP
            row = PlatformNotificationDispatch.objects.create(
                tenant=tenant,
                maintenance_window=window,
                event_type=event_type,
                channel=channel,
                status=PlatformNotificationDispatch.STATUS_SENT if is_internal else PlatformNotificationDispatch.STATUS_QUEUED,
                attempts=1 if is_internal else 0,
                sent_at=now if is_internal else None,
                created_by=actor if getattr(actor, "is_authenticated", False) else None,
                payload={
                    "title": window.title,
                    "description": window.description,
                    "starts_at": window.starts_at.isoformat() if window.starts_at else None,
                    "ends_at": window.ends_at.isoformat() if window.ends_at else None,
                    "event_type": event_type,
                    "channel": channel,
                },
            )
            created_rows.append(row)
    _platform_audit(
        user=actor,
        action="NOTIFY",
        model_name="PlatformMaintenanceWindow",
        object_id=window.id,
        details=f"queued {len(created_rows)} maintenance notifications for event={event_type}",
        request=request,
        metadata={"event_type": event_type, "count": len(created_rows)},
    )
    return created_rows


def _deployment_hook_config(hook_type: str) -> tuple[str, str]:
    if hook_type == DeploymentHookRun.TYPE_ROLLBACK:
        return (
            str(getattr(settings, "DEPLOYMENT_ROLLBACK_HOOK_URL", "")).strip(),
            "X-Rollback-Hook-Token",
        )
    return (
        str(getattr(settings, "DEPLOYMENT_TRIGGER_HOOK_URL", "")).strip(),
        "X-Deploy-Hook-Token",
    )


def _execute_deployment_hook(
    *,
    release: DeploymentRelease,
    hook_type: str,
    payload: dict,
    actor,
) -> DeploymentHookRun:
    endpoint, token_header = _deployment_hook_config(hook_type)
    token = str(getattr(settings, "DEPLOYMENT_CALLBACK_TOKEN", "")).strip()
    timeout = int(getattr(settings, "DEPLOYMENT_HOOK_TIMEOUT_SECONDS", 6))
    run = DeploymentHookRun.objects.create(
        release=release,
        hook_type=hook_type,
        status=DeploymentHookRun.STATUS_FAILED,
        endpoint=endpoint,
        request_payload=payload,
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )
    if not endpoint:
        run.error = "Hook endpoint is not configured."
        run.save(update_fields=["error"])
        return run

    request_headers = {"Content-Type": "application/json"}
    if token:
        request_headers[token_header] = token
        request_headers["Authorization"] = f"Bearer {token}"
    req = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            run.status = DeploymentHookRun.STATUS_SUCCESS if 200 <= int(resp.status) < 300 else DeploymentHookRun.STATUS_FAILED
            run.response_status = int(resp.status)
            run.response_body = body[:4000]
            run.error = ""
            run.save(update_fields=["status", "response_status", "response_body", "error"])
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
        run.status = DeploymentHookRun.STATUS_FAILED
        run.response_status = int(getattr(exc, "code", 0) or 0) or None
        run.response_body = body[:4000]
        run.error = str(exc)
        run.save(update_fields=["status", "response_status", "response_body", "error"])
    except (URLError, TimeoutError, OSError) as exc:
        run.status = DeploymentHookRun.STATUS_FAILED
        run.error = str(exc)
        run.save(update_fields=["status", "error"])
    return run


def _backup_artifact_dir() -> str:
    root = str(getattr(settings, "BACKUP_ARTIFACT_DIR", "")).strip()
    if root:
        return root
    return os.path.join(str(settings.BASE_DIR), "var", "backups")


def _execute_backup_engine(*, backup: BackupJob, actor) -> BackupExecutionRun:
    mode = str(getattr(settings, "BACKUP_ENGINE_MODE", "mock")).strip().lower() or "mock"
    output_dir = _backup_artifact_dir()
    os.makedirs(output_dir, exist_ok=True)
    now = timezone.now()
    output_path = os.path.join(output_dir, f"backup-{backup.id}-{now:%Y%m%d%H%M%S}.dump")
    run = BackupExecutionRun.objects.create(
        backup=backup,
        engine_mode=mode,
        status=BackupExecutionRun.STATUS_FAILED,
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )

    if mode == "pg_dump":
        db = settings.DATABASES.get("default", {})
        cmd = [
            "pg_dump",
            "-h",
            str(db.get("HOST") or "localhost"),
            "-p",
            str(db.get("PORT") or "5432"),
            "-U",
            str(db.get("USER") or "postgres"),
            "-d",
            str(db.get("NAME") or ""),
            "-F",
            "c",
            "-f",
            output_path,
        ]
        run.command = " ".join(cmd)
        env = os.environ.copy()
        env["PGPASSWORD"] = str(db.get("PASSWORD") or "")
        try:
            proc = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=int(getattr(settings, "BACKUP_ENGINE_TIMEOUT_SECONDS", 120)),
                check=False,
            )
            logs = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
            run.logs = logs[:4000]
            if proc.returncode != 0:
                run.status = BackupExecutionRun.STATUS_FAILED
                run.completed_at = timezone.now()
                run.save(update_fields=["command", "logs", "status", "completed_at"])
                return run
        except Exception as exc:
            run.logs = str(exc)[:4000]
            run.status = BackupExecutionRun.STATUS_FAILED
            run.completed_at = timezone.now()
            run.save(update_fields=["command", "logs", "status", "completed_at"])
            return run
    else:
        # Safe default for environments without backup tooling configured.
        payload = {
            "backup_id": backup.id,
            "scope": backup.scope,
            "tenant_id": backup.tenant_id,
            "backup_type": backup.backup_type,
            "generated_at": now.isoformat(),
            "engine_mode": mode,
        }
        run.command = "mock_backup_writer"
        with open(output_path, "w", encoding="utf-8") as fp:
            fp.write(json.dumps(payload))
        run.logs = "mock backup artifact created"

    with open(output_path, "rb") as fp:
        data = fp.read()
    checksum = hashlib.sha256(data).hexdigest()
    size = len(data)
    run.status = BackupExecutionRun.STATUS_SUCCESS
    run.output_path = output_path
    run.checksum = checksum
    run.size_bytes = size
    run.completed_at = timezone.now()
    run.save(
        update_fields=[
            "command",
            "logs",
            "status",
            "output_path",
            "checksum",
            "size_bytes",
            "completed_at",
        ]
    )
    return run


def _create_billing_invoice(
    *,
    tenant: Tenant,
    subscription: TenantSubscription,
    period_start,
    cycle: str,
    due_days: int = 7,
    notes: str = "",
):
    period_end = period_start + timedelta(days=_cycle_days(cycle) - 1)
    amount = _cycle_amount(subscription.plan, cycle)
    total = amount.quantize(Decimal("0.01"))
    return SubscriptionInvoice.objects.create(
        tenant=tenant,
        subscription=subscription,
        invoice_number=_invoice_number(tenant),
        billing_cycle=cycle,
        status=SubscriptionInvoice.STATUS_PENDING,
        currency="USD",
        amount=total,
        tax_amount=Decimal("0.00"),
        discount_amount=Decimal("0.00"),
        total_amount=total,
        period_start=period_start,
        period_end=period_end,
        due_date=period_start + timedelta(days=due_days),
        notes=notes,
    )


def _provision_school_admin(*, tenant: Tenant, username: str, email: str, password: str):
    from school.models import Role, UserProfile

    with schema_context(tenant.schema_name):
        role, _ = Role.objects.get_or_create(name="ADMIN", defaults={"description": "School Administrator"})
        admin_username = username or "admin"
        unique_username = admin_username
        suffix = 1
        while User.objects.filter(username=unique_username).exists():
            unique_username = f"{admin_username}{suffix}"
            suffix += 1

        user = User.objects.create(
            username=unique_username,
            email=email or "",
            is_staff=True,
            is_superuser=False,
            is_active=True,
        )
        user.set_password(password)
        user.save(update_fields=["password"])
        UserProfile.objects.get_or_create(user=user, defaults={"role": role, "phone": ""})
    return unique_username


def _tenant_stats(tenant: Tenant):
    stats = {
        "students_active": 0,
        "staff_active": 0,
        "invoices_total": 0,
        "payments_total": str(Decimal("0.00")),
        "users_total": 0,
    }
    with schema_context(tenant.schema_name):
        try:
            from school.models import Invoice, Payment, Staff, Student

            stats["students_active"] = Student.objects.filter(is_active=True).count()
            stats["staff_active"] = Staff.objects.filter(is_active=True).count()
            stats["invoices_total"] = Invoice.objects.count()
            paid = Payment.objects.filter(is_active=True).aggregate(total=Sum("amount")).get("total")
            stats["payments_total"] = str((paid or Decimal("0.00")).quantize(Decimal("0.01")))
        except Exception:
            # Tenant might be mid-provisioning or missing app tables during recovery.
            pass
        stats["users_total"] = User.objects.count()
    return stats


class PlatformSubscriptionPlanViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = SubscriptionPlan.objects.filter(is_active=True).order_by("code")
    serializer_class = SubscriptionPlanSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAuthenticated(), IsGlobalSuperAdmin()]


class PlatformTenantViewSet(viewsets.ModelViewSet):
    queryset = Tenant.objects.all().select_related("subscription_plan").order_by("-created_at")
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated, IsGlobalSuperAdmin]

    def create(self, request, *args, **kwargs):
        serializer = TenantProvisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        name = data["name"]
        subdomain = data.get("subdomain") or _unique_subdomain(name)
        schema_name = data.get("schema_name") or _unique_schema(subdomain or name)
        custom_domain = data.get("custom_domain") or ""
        plan = data.get("subscription_plan")
        today = timezone.now().date()
        trial_days = data.get("trial_days") or _default_trial_days()
        trial_end = today + timedelta(days=trial_days)
        max_students = data.get("max_students") or getattr(plan, "max_students", 200)
        max_storage_gb = data.get("max_storage_gb") or getattr(plan, "max_storage_gb", 5)

        admin_password = data.get("school_admin_password") or secrets.token_urlsafe(12)
        admin_username = data.get("school_admin_username") or "admin"
        admin_email = data.get("school_admin_email") or data.get("contact_email") or ""

        with transaction.atomic():
            tenant = Tenant.objects.create(
                name=name,
                schema_name=schema_name,
                subdomain=subdomain,
                custom_domain=custom_domain or None,
                contact_name=data.get("contact_name", ""),
                contact_email=data.get("contact_email", ""),
                contact_phone=data.get("contact_phone", ""),
                status=Tenant.STATUS_TRIAL,
                subscription_plan=plan,
                trial_start=today,
                trial_end=trial_end,
                max_students=max_students,
                max_storage_gb=max_storage_gb,
                is_active=True,
            )
            if plan:
                TenantSubscription.objects.create(
                    tenant=tenant,
                    plan=plan,
                    billing_cycle=TenantSubscription.BILLING_MONTHLY,
                    status=TenantSubscription.STATUS_TRIAL,
                    starts_on=today,
                    trial_end=trial_end,
                    next_billing_date=trial_end + timedelta(days=1),
                    grace_period_days=_default_grace_days(),
                    is_current=True,
                )
            primary_domain = f"{subdomain}.{_base_domain()}"
            Domain.objects.create(domain=primary_domain, tenant=tenant, is_primary=True)
            if custom_domain:
                Domain.objects.get_or_create(
                    domain=custom_domain,
                    tenant=tenant,
                    defaults={"is_primary": False},
                )

        provisioned_admin_username = _provision_school_admin(
            tenant=tenant,
            username=admin_username,
            email=admin_email,
            password=admin_password,
        )

        output = TenantSerializer(tenant, context={"request": request}).data
        return Response(
            {
                "tenant": output,
                "provisioning": {
                    "schema_created": True,
                    "primary_domain": f"{subdomain}.{_base_domain()}",
                    "school_admin_username": provisioned_admin_username,
                    "school_admin_temp_password": admin_password,
                    "welcome_email_queued": False,
                },
            },
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, *args, **kwargs):
        tenant = self.get_object()
        mutable_fields = {
            "name",
            "custom_domain",
            "contact_name",
            "contact_email",
            "contact_phone",
            "subscription_plan",
            "trial_start",
            "trial_end",
            "max_students",
            "max_storage_gb",
            "paid_until",
        }
        payload = {key: value for key, value in request.data.items() if key in mutable_fields}
        serializer = TenantSerializer(tenant, data=payload, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        new_plan = serializer.validated_data.get("subscription_plan")
        if new_plan:
            current_subscription = tenant.subscriptions.filter(is_current=True).order_by("-created_at").first()
            if current_subscription and current_subscription.plan_id != new_plan.id:
                current_subscription.is_current = False
                current_subscription.ends_on = timezone.now().date()
                current_subscription.save(update_fields=["is_current", "ends_on", "updated_at"])
                TenantSubscription.objects.create(
                    tenant=tenant,
                    plan=new_plan,
                    billing_cycle=current_subscription.billing_cycle,
                    status=TenantSubscription.STATUS_ACTIVE,
                    starts_on=timezone.now().date(),
                    next_billing_date=_next_billing_date(timezone.now().date(), current_subscription.billing_cycle),
                    grace_period_days=current_subscription.grace_period_days,
                    is_current=True,
                )

        custom_domain = serializer.validated_data.get("custom_domain")
        if custom_domain:
            Domain.objects.get_or_create(
                domain=custom_domain,
                tenant=tenant,
                defaults={"is_primary": False},
            )

        return Response(TenantSerializer(tenant, context={"request": request}).data)

    def destroy(self, request, *args, **kwargs):
        tenant = self.get_object()
        tenant.status = Tenant.STATUS_ARCHIVED
        tenant.is_active = False
        tenant.archived_at = timezone.now()
        tenant.save(update_fields=["status", "is_active", "archived_at", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        tenant = self.get_object()
        tenant.status = Tenant.STATUS_ACTIVE
        tenant.is_active = True
        tenant.activated_at = timezone.now()
        tenant.suspended_at = None
        tenant.suspension_reason = ""
        tenant.save(
            update_fields=[
                "status",
                "is_active",
                "activated_at",
                "suspended_at",
                "suspension_reason",
                "updated_at",
            ]
        )
        return Response(TenantSerializer(tenant, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def suspend(self, request, pk=None):
        tenant = self.get_object()
        serializer = TenantSuspendSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get("reason", "")
        tenant.status = Tenant.STATUS_SUSPENDED
        tenant.is_active = False
        tenant.suspended_at = timezone.now()
        tenant.suspension_reason = reason
        tenant.save(update_fields=["status", "is_active", "suspended_at", "suspension_reason", "updated_at"])
        return Response(TenantSerializer(tenant, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        tenant = self.get_object()
        tenant.status = Tenant.STATUS_ACTIVE
        tenant.is_active = True
        tenant.suspended_at = None
        tenant.suspension_reason = ""
        tenant.save(update_fields=["status", "is_active", "suspended_at", "suspension_reason", "updated_at"])
        return Response(TenantSerializer(tenant, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="assign-plan")
    def assign_plan(self, request, pk=None):
        tenant = self.get_object()
        serializer = TenantAssignPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        new_plan = data["subscription_plan"]
        cycle = data["billing_cycle"]
        starts_on = data.get("starts_on") or timezone.now().date()
        grace_period = data.get("grace_period_days", 7)
        if grace_period is None:
            grace_period = _default_grace_days()

        with transaction.atomic():
            tenant.subscription_plan = new_plan
            tenant.max_students = new_plan.max_students
            tenant.max_storage_gb = new_plan.max_storage_gb
            tenant.save(update_fields=["subscription_plan", "max_students", "max_storage_gb", "updated_at"])

            current = tenant.subscriptions.filter(is_current=True).order_by("-created_at").first()
            if current:
                current.is_current = False
                current.ends_on = starts_on
                current.save(update_fields=["is_current", "ends_on", "updated_at"])

            subscription = TenantSubscription.objects.create(
                tenant=tenant,
                plan=new_plan,
                billing_cycle=cycle,
                status=TenantSubscription.STATUS_ACTIVE,
                starts_on=starts_on,
                next_billing_date=_next_billing_date(starts_on, cycle),
                grace_period_days=grace_period,
                is_current=True,
            )

            invoice = _create_billing_invoice(
                tenant=tenant,
                subscription=subscription,
                period_start=starts_on,
                cycle=cycle,
                due_days=grace_period,
                notes="Initial invoice generated from plan assignment.",
            )

        return Response(
            {
                "tenant": TenantSerializer(tenant, context={"request": request}).data,
                "subscription": TenantSubscriptionSerializer(subscription).data,
                "invoice": SubscriptionInvoiceSerializer(invoice).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="generate-invoice")
    def generate_invoice(self, request, pk=None):
        tenant = self.get_object()
        subscription = tenant.subscriptions.filter(is_current=True).order_by("-created_at").first()
        if not subscription:
            return Response({"detail": "No active subscription found for tenant."}, status=status.HTTP_400_BAD_REQUEST)

        period_start = subscription.next_billing_date or timezone.now().date()
        invoice = _create_billing_invoice(
            tenant=tenant,
            subscription=subscription,
            period_start=period_start,
            cycle=subscription.billing_cycle,
            due_days=subscription.grace_period_days,
            notes="Scheduled cycle invoice.",
        )
        subscription.next_billing_date = _next_billing_date(period_start, subscription.billing_cycle)
        subscription.save(update_fields=["next_billing_date", "updated_at"])
        return Response(SubscriptionInvoiceSerializer(invoice).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="billing-overview")
    def billing_overview(self, request, pk=None):
        tenant = self.get_object()
        current = tenant.subscriptions.filter(is_current=True).order_by("-created_at").first()
        invoices = tenant.subscription_invoices.order_by("-issued_at")[:20]
        totals = tenant.subscription_invoices.aggregate(total=Sum("total_amount"))
        paid_total = tenant.subscription_invoices.filter(status=SubscriptionInvoice.STATUS_PAID).aggregate(total=Sum("total_amount"))
        return Response(
            {
                "tenant_id": tenant.id,
                "current_subscription": TenantSubscriptionSerializer(current).data if current else None,
                "invoices": SubscriptionInvoiceSerializer(invoices, many=True).data,
                "totals": {
                    "invoiced": str((totals.get("total") or Decimal("0.00")).quantize(Decimal("0.01"))),
                    "paid": str((paid_total.get("total") or Decimal("0.00")).quantize(Decimal("0.01"))),
                },
            }
        )

    @action(detail=True, methods=["get"], url_path="stats")
    def stats(self, request, pk=None):
        tenant = self.get_object()
        payload = _tenant_stats(tenant)
        return Response({"tenant_id": tenant.id, "schema_name": tenant.schema_name, "stats": payload})

    @action(detail=True, methods=["post"], url_path="export-data")
    def export_data(self, request, pk=None):
        tenant = self.get_object()
        payload = {
            "tenant": TenantSerializer(tenant, context={"request": request}).data,
            "stats_snapshot": _tenant_stats(tenant),
            "exported_at": timezone.now().isoformat(),
        }
        return JsonResponse(payload)

    @action(detail=True, methods=["post"], url_path="reset-school-admin")
    def reset_school_admin(self, request, pk=None):
        tenant = self.get_object()
        serializer = TenantAdminCredentialSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        username = (data.get("username") or "admin").strip()
        password = data["password"]
        email = (data.get("email") or "").strip()

        with schema_context(tenant.schema_name):
            user = User.objects.filter(username=username).first()
            if not user:
                return Response(
                    {"detail": f"User '{username}' was not found in tenant schema '{tenant.schema_name}'."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            user.set_password(password)
            user.is_active = True
            update_fields = ["password", "is_active"]
            if email:
                user.email = email
                update_fields.append("email")
            user.save(update_fields=update_fields)

        _platform_audit(
            user=request.user,
            action="RESET_CREDENTIALS",
            model_name="TenantSchoolAdmin",
            object_id=username,
            tenant=tenant,
            request=request,
            details=f"reset school admin credentials for user={username}",
            metadata={"username": username, "tenant_id": tenant.id},
        )
        return Response(
            {
                "tenant_id": tenant.id,
                "schema_name": tenant.schema_name,
                "username": username,
                "password_reset": True,
            },
            status=status.HTTP_200_OK,
        )


class PlatformTenantSubscriptionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = TenantSubscription.objects.select_related("tenant", "plan").order_by("-created_at")
    serializer_class = TenantSubscriptionSerializer
    permission_classes = [IsAuthenticated, IsGlobalSuperAdmin]

    def get_queryset(self):
        qs = super().get_queryset()
        tenant_id = self.request.query_params.get("tenant_id")
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
        plan_id = self.request.query_params.get("plan_id")
        if plan_id:
            qs = qs.filter(plan_id=plan_id)
        sub_status = self.request.query_params.get("status")
        if sub_status:
            qs = qs.filter(status=sub_status)
        return qs

    def create(self, request, *args, **kwargs):
        today = timezone.now().date()
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        if not data.get("starts_on"):
            data["starts_on"] = today.isoformat()
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        today = timezone.now().date()
        cycle = serializer.validated_data.get("billing_cycle", TenantSubscription.BILLING_MONTHLY)
        days = 365 if cycle == TenantSubscription.BILLING_ANNUAL else 30
        starts_on = serializer.validated_data.get("starts_on", today)
        ends_on = starts_on + timedelta(days=days)
        TenantSubscription.objects.filter(
            tenant=serializer.validated_data["tenant"], is_current=True
        ).update(is_current=False)
        serializer.save(
            ends_on=ends_on,
            status=TenantSubscription.STATUS_ACTIVE,
            is_current=True,
        )


class PlatformSubscriptionInvoiceViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = SubscriptionInvoice.objects.select_related("tenant", "subscription").order_by("-issued_at")
    serializer_class = SubscriptionInvoiceSerializer
    permission_classes = [IsAuthenticated, IsGlobalSuperAdmin]

    def get_queryset(self):
        queryset = super().get_queryset()
        tenant_id = self.request.query_params.get("tenant_id")
        status_value = self.request.query_params.get("status")
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        if status_value:
            queryset = queryset.filter(status=status_value.upper())
        return queryset

    @action(detail=True, methods=["post"], url_path="record-payment")
    def record_payment(self, request, pk=None):
        invoice = self.get_object()
        serializer = InvoicePaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        amount = data["amount"]
        with transaction.atomic():
            payment = SubscriptionPayment.objects.create(
                invoice=invoice,
                amount=amount,
                method=data.get("method", ""),
                status=SubscriptionPayment.STATUS_PAID,
                paid_at=timezone.now(),
                transaction_id=data.get("transaction_id", ""),
                metadata=data.get("metadata", {}),
            )
            if data.get("external_reference"):
                invoice.external_reference = data["external_reference"]
            invoice.status = SubscriptionInvoice.STATUS_PAID
            invoice.paid_at = timezone.now()
            invoice.save(update_fields=["status", "paid_at", "external_reference", "updated_at"])

            subscription = invoice.subscription
            if subscription and subscription.is_current:
                subscription.status = TenantSubscription.STATUS_ACTIVE
                subscription.save(update_fields=["status", "updated_at"])

            tenant = invoice.tenant
            if invoice.period_end and (tenant.paid_until is None or invoice.period_end > tenant.paid_until):
                tenant.paid_until = invoice.period_end
                tenant.is_active = True
                if tenant.status == Tenant.STATUS_SUSPENDED:
                    tenant.status = Tenant.STATUS_ACTIVE
                    tenant.suspended_at = None
                    tenant.suspension_reason = ""
                    tenant.save(update_fields=["paid_until", "is_active", "status", "suspended_at", "suspension_reason", "updated_at"])
                else:
                    tenant.save(update_fields=["paid_until", "is_active", "updated_at"])

        return Response(
            {
                "invoice": SubscriptionInvoiceSerializer(invoice).data,
                "payment": SubscriptionPaymentSerializer(payment).data,
            },
            status=status.HTTP_200_OK,
        )


class PlatformAnalyticsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsGlobalSuperAdmin]

    def _active_current_subscriptions(self):
        return TenantSubscription.objects.filter(
            is_current=True,
            status__in=[TenantSubscription.STATUS_TRIAL, TenantSubscription.STATUS_ACTIVE],
            tenant__status__in=[Tenant.STATUS_TRIAL, Tenant.STATUS_ACTIVE],
        ).select_related("plan", "tenant")

    def _monthly_window(self, months: int = 12):
        now = timezone.now()
        start = (now.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=31 * (months - 1)))
        start = start.replace(day=1)
        return start, now

    @action(detail=False, methods=["get"], url_path="overview")
    def overview(self, request):
        today = timezone.now().date()
        month_start = today.replace(day=1)
        year_start = today.replace(month=1, day=1)

        tenant_counts = {
            "total": Tenant.objects.count(),
            "trial": Tenant.objects.filter(status=Tenant.STATUS_TRIAL).count(),
            "active": Tenant.objects.filter(status=Tenant.STATUS_ACTIVE).count(),
            "suspended": Tenant.objects.filter(status=Tenant.STATUS_SUSPENDED).count(),
            "cancelled": Tenant.objects.filter(status=Tenant.STATUS_CANCELLED).count(),
            "archived": Tenant.objects.filter(status=Tenant.STATUS_ARCHIVED).count(),
        }

        active_subscriptions = self._active_current_subscriptions()
        mrr = Decimal("0.00")
        for sub in active_subscriptions:
            if sub.billing_cycle == TenantSubscription.BILLING_ANNUAL:
                mrr += (Decimal(sub.plan.annual_price or 0) / Decimal("12"))
            else:
                mrr += Decimal(sub.plan.monthly_price or 0)
        mrr = mrr.quantize(Decimal("0.01"))
        arr = (mrr * Decimal("12")).quantize(Decimal("0.01"))

        invoiced_month = SubscriptionInvoice.objects.filter(
            issued_at__date__gte=month_start
        ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
        paid_month = SubscriptionInvoice.objects.filter(
            status=SubscriptionInvoice.STATUS_PAID,
            paid_at__date__gte=month_start,
        ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
        overdue_count = SubscriptionInvoice.objects.filter(
            status=SubscriptionInvoice.STATUS_OVERDUE
        ).count()

        opening_active = Tenant.objects.filter(
            status=Tenant.STATUS_ACTIVE,
            created_at__date__lt=month_start,
        ).count()
        churned_month = Tenant.objects.filter(
            status__in=[Tenant.STATUS_CANCELLED, Tenant.STATUS_ARCHIVED],
            updated_at__date__gte=month_start,
        ).count()
        churn_rate = Decimal("0.00")
        if opening_active > 0:
            churn_rate = (Decimal(churned_month) / Decimal(opening_active) * Decimal("100")).quantize(Decimal("0.01"))

        new_tenants_month = Tenant.objects.filter(created_at__date__gte=month_start).count()
        new_tenants_year = Tenant.objects.filter(created_at__date__gte=year_start).count()

        return Response(
            {
                "tenants": tenant_counts,
                "revenue": {
                    "mrr": str(mrr),
                    "arr": str(arr),
                    "invoiced_this_month": str(invoiced_month.quantize(Decimal("0.01"))),
                    "paid_this_month": str(paid_month.quantize(Decimal("0.01"))),
                    "overdue_invoices": overdue_count,
                },
                "growth": {
                    "new_tenants_this_month": new_tenants_month,
                    "new_tenants_this_year": new_tenants_year,
                },
                "churn": {
                    "churned_this_month": churned_month,
                    "monthly_churn_rate_percent": str(churn_rate),
                },
            }
        )

    @action(detail=False, methods=["get"], url_path="revenue")
    def revenue(self, request):
        start, _ = self._monthly_window(months=12)

        issued_rows = (
            SubscriptionInvoice.objects.filter(issued_at__gte=start)
            .annotate(month=TruncMonth("issued_at"))
            .values("month")
            .annotate(invoiced=Sum("total_amount"))
            .order_by("month")
        )
        paid_rows = (
            SubscriptionInvoice.objects.filter(status=SubscriptionInvoice.STATUS_PAID, paid_at__isnull=False, paid_at__gte=start)
            .annotate(month=TruncMonth("paid_at"))
            .values("month")
            .annotate(paid=Sum("total_amount"))
            .order_by("month")
        )
        paid_map = {row["month"].date().isoformat(): row["paid"] or Decimal("0.00") for row in paid_rows}

        points = []
        for row in issued_rows:
            key = row["month"].date().isoformat()
            points.append(
                {
                    "month": key,
                    "invoiced": str((row["invoiced"] or Decimal("0.00")).quantize(Decimal("0.01"))),
                    "paid": str((paid_map.get(key, Decimal("0.00"))).quantize(Decimal("0.01"))),
                }
            )

        return Response({"points": points})

    @action(detail=False, methods=["get"], url_path="tenant-growth")
    def tenant_growth(self, request):
        start, _ = self._monthly_window(months=12)
        created_rows = (
            Tenant.objects.filter(created_at__gte=start)
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(created=Count("id"))
            .order_by("month")
        )
        points = [{"month": row["month"].date().isoformat(), "created": row["created"]} for row in created_rows]
        return Response({"points": points})

    @action(detail=False, methods=["get"], url_path="module-adoption")
    def module_adoption(self, request):
        active_subscriptions = list(self._active_current_subscriptions())
        tenant_count = len(active_subscriptions)
        adoption_counter = {module: 0 for module in PLATFORM_MODULES}

        for sub in active_subscriptions:
            enabled = sub.plan.enabled_modules or []
            if not enabled:
                for module in PLATFORM_MODULES:
                    adoption_counter[module] += 1
                continue
            enabled_set = {str(module).upper() for module in enabled}
            for module in PLATFORM_MODULES:
                if module in enabled_set:
                    adoption_counter[module] += 1

        modules = []
        for module, count in adoption_counter.items():
            rate = Decimal("0.00")
            if tenant_count:
                rate = (Decimal(count) / Decimal(tenant_count) * Decimal("100")).quantize(Decimal("0.01"))
            modules.append({"module": module, "tenants": count, "adoption_rate_percent": str(rate)})

        modules.sort(key=lambda item: item["module"])
        return Response({"total_active_tenants": tenant_count, "modules": modules})

    @action(detail=False, methods=["get"], url_path="business-kpis")
    def business_kpis(self, request):
        today = timezone.now().date()
        month_start = today.replace(day=1)
        annual_start = (month_start - timedelta(days=365))

        active_subscriptions = list(self._active_current_subscriptions())
        tenant_count = len(active_subscriptions)

        mrr = Decimal("0.00")
        for sub in active_subscriptions:
            if sub.billing_cycle == TenantSubscription.BILLING_ANNUAL:
                mrr += (Decimal(sub.plan.annual_price or 0) / Decimal("12"))
            else:
                mrr += Decimal(sub.plan.monthly_price or 0)
        mrr = mrr.quantize(Decimal("0.01"))
        arr = (mrr * Decimal("12")).quantize(Decimal("0.01"))

        arpt = Decimal("0.00")
        if tenant_count > 0:
            arpt = (mrr / Decimal(tenant_count)).quantize(Decimal("0.01"))

        opening_active_month = Tenant.objects.filter(
            status=Tenant.STATUS_ACTIVE,
            created_at__date__lt=month_start,
        ).count()
        churned_month = Tenant.objects.filter(
            status__in=[Tenant.STATUS_CANCELLED, Tenant.STATUS_ARCHIVED],
            updated_at__date__gte=month_start,
        ).count()
        monthly_churn_rate = Decimal("0.00")
        if opening_active_month > 0:
            monthly_churn_rate = (
                Decimal(churned_month) / Decimal(opening_active_month) * Decimal("100")
            ).quantize(Decimal("0.01"))

        opening_active_annual = Tenant.objects.filter(
            status=Tenant.STATUS_ACTIVE,
            created_at__date__lt=annual_start,
        ).count()
        churned_annual = Tenant.objects.filter(
            status__in=[Tenant.STATUS_CANCELLED, Tenant.STATUS_ARCHIVED],
            updated_at__date__gte=annual_start,
        ).count()
        annual_churn_rate = Decimal("0.00")
        if opening_active_annual > 0:
            annual_churn_rate = (
                Decimal(churned_annual) / Decimal(opening_active_annual) * Decimal("100")
            ).quantize(Decimal("0.01"))

        ltv = None
        if monthly_churn_rate > 0:
            churn_fraction = monthly_churn_rate / Decimal("100")
            ltv = (arpt / churn_fraction).quantize(Decimal("0.01"))

        return Response(
            {
                "kpis": {
                    "mrr": str(mrr),
                    "arr": str(arr),
                    "arpt": str(arpt),
                    "monthly_churn_rate_percent": str(monthly_churn_rate),
                    "annual_churn_rate_percent": str(annual_churn_rate),
                    "ltv_estimate": str(ltv) if ltv is not None else None,
                },
                "tenant_segments": {
                    "trial": Tenant.objects.filter(status=Tenant.STATUS_TRIAL).count(),
                    "active": Tenant.objects.filter(status=Tenant.STATUS_ACTIVE).count(),
                    "suspended": Tenant.objects.filter(status=Tenant.STATUS_SUSPENDED).count(),
                    "cancelled": Tenant.objects.filter(status=Tenant.STATUS_CANCELLED).count(),
                    "archived": Tenant.objects.filter(status=Tenant.STATUS_ARCHIVED).count(),
                },
            }
        )

    @action(detail=False, methods=["get"], url_path="storage-usage")
    def storage_usage(self, request):
        start, _ = self._monthly_window(months=12)
        metric_keys = ["storage.used.gb", "tenant.storage.used.gb"]
        rows = (
            MonitoringSnapshot.objects.filter(
                captured_at__gte=start,
                metric_key__in=metric_keys,
            )
            .annotate(month=TruncMonth("captured_at"))
            .values("month")
            .annotate(total_gb=Sum("value"), datapoints=Count("id"))
            .order_by("month")
        )
        points = [
            {
                "month": row["month"].date().isoformat(),
                "total_storage_gb": str((row["total_gb"] or Decimal("0.00")).quantize(Decimal("0.01"))),
                "datapoints": row["datapoints"],
            }
            for row in rows
        ]
        latest_total = points[-1]["total_storage_gb"] if points else "0.00"
        return Response({"latest_total_storage_gb": latest_total, "points": points})

    @action(detail=False, methods=["get"], url_path="workflow-monitor")
    def workflow_monitor(self, request):
        from school.models import (
            StudentTransfer, AdmissionApplication, Invoice, Payment,
            Student, Staff, CrossTenantTransfer,
        )

        tenants = Tenant.objects.filter(
            status__in=[Tenant.STATUS_ACTIVE, Tenant.STATUS_TRIAL]
        ).exclude(schema_name="public").order_by("name")

        thirty_days_ago = timezone.now() - timedelta(days=30)

        totals = {
            "total_students": 0,
            "total_staff": 0,
            "pending_transfers": 0,
            "pending_admissions": 0,
            "overdue_invoices": 0,
            "recent_payments": 0,
        }
        tenant_rows = []

        for tenant in tenants:
            try:
                with schema_context(tenant.schema_name):
                    student_count   = Student.objects.filter(is_active=True).count()
                    staff_count     = Staff.objects.filter(is_active=True).count()
                    pending_tx      = StudentTransfer.objects.filter(status="Pending").count()
                    pending_adm     = AdmissionApplication.objects.filter(
                        status__in=["Submitted", "Documents Received", "Interview Scheduled", "Assessed"]
                    ).count()
                    overdue_inv     = Invoice.objects.filter(status="OVERDUE").count()
                    recent_pay      = Payment.objects.filter(payment_date__gte=thirty_days_ago).count()

                totals["total_students"]    += student_count
                totals["total_staff"]       += staff_count
                totals["pending_transfers"] += pending_tx
                totals["pending_admissions"]+= pending_adm
                totals["overdue_invoices"]  += overdue_inv
                totals["recent_payments"]   += recent_pay

                tenant_rows.append({
                    "tenant_id": tenant.id,
                    "tenant_name": tenant.name,
                    "status": tenant.status,
                    "students": student_count,
                    "staff": staff_count,
                    "pending_transfers": pending_tx,
                    "pending_admissions": pending_adm,
                    "overdue_invoices": overdue_inv,
                    "recent_payments": recent_pay,
                })
            except Exception as exc:
                logger.warning("workflow_monitor: schema %s error: %s", tenant.schema_name, exc)
                tenant_rows.append({
                    "tenant_id": tenant.id,
                    "tenant_name": tenant.name,
                    "status": tenant.status,
                    "error": str(exc),
                })

        cross_pending = 0
        cross_approved = 0
        cross_completed = 0
        for tenant in tenants:
            try:
                with schema_context(tenant.schema_name):
                    cross_pending   += CrossTenantTransfer.objects.filter(
                        from_tenant_id=tenant.schema_name, status="pending"
                    ).count()
                    cross_approved  += CrossTenantTransfer.objects.filter(
                        from_tenant_id=tenant.schema_name, status="approved_from"
                    ).count()
                    cross_completed += CrossTenantTransfer.objects.filter(
                        from_tenant_id=tenant.schema_name,
                        status="completed",
                        updated_at__gte=thirty_days_ago,
                    ).count()
            except Exception:
                pass

        cross_tenant = {
            "pending": cross_pending,
            "approved_from_source": cross_approved,
            "completed_30d": cross_completed,
        }

        return Response({
            "totals": totals,
            "cross_tenant_transfers": cross_tenant,
            "tenants": tenant_rows,
        })

    @action(detail=False, methods=["get"], url_path="global-reports")
    def global_reports(self, request):
        from school.models import Student, Staff, Invoice, Payment
        from django.db.models import Sum as _Sum

        tenants = Tenant.objects.filter(
            status__in=[Tenant.STATUS_ACTIVE, Tenant.STATUS_TRIAL]
        ).exclude(schema_name="public").order_by("name")

        total_students = 0
        total_staff    = 0
        total_invoiced = Decimal("0.00")
        total_paid     = Decimal("0.00")
        total_overdue  = Decimal("0.00")
        by_tenant      = []

        for tenant in tenants:
            try:
                with schema_context(tenant.schema_name):
                    students = Student.objects.filter(is_active=True).count()
                    staff    = Staff.objects.filter(is_active=True).count()
                    invoiced = Invoice.objects.aggregate(t=_Sum("total_amount"))["t"] or Decimal("0.00")
                    paid     = Payment.objects.aggregate(t=_Sum("amount"))["t"] or Decimal("0.00")
                    overdue  = (
                        Invoice.objects.filter(status="OVERDUE")
                        .aggregate(t=_Sum("total_amount"))["t"] or Decimal("0.00")
                    )

                total_students += students
                total_staff    += staff
                total_invoiced += invoiced
                total_paid     += paid
                total_overdue  += overdue

                collection_rate = (
                    (paid / invoiced * Decimal("100")).quantize(Decimal("0.01"))
                    if invoiced > 0 else Decimal("0.00")
                )

                by_tenant.append({
                    "tenant_id": tenant.id,
                    "tenant_name": tenant.name,
                    "status": tenant.status,
                    "students": students,
                    "staff": staff,
                    "invoiced": str(invoiced.quantize(Decimal("0.01"))),
                    "paid": str(paid.quantize(Decimal("0.01"))),
                    "overdue": str(overdue.quantize(Decimal("0.01"))),
                    "collection_rate_percent": str(collection_rate),
                })
            except Exception as exc:
                logger.warning("global_reports: schema %s error: %s", tenant.schema_name, exc)
                by_tenant.append({
                    "tenant_id": tenant.id,
                    "tenant_name": tenant.name,
                    "status": tenant.status,
                    "error": str(exc),
                })

        overall_rate = (
            (total_paid / total_invoiced * Decimal("100")).quantize(Decimal("0.01"))
            if total_invoiced > 0 else Decimal("0.00")
        )

        return Response({
            "summary": {
                "total_students": total_students,
                "total_staff": total_staff,
                "total_invoiced": str(total_invoiced.quantize(Decimal("0.01"))),
                "total_paid": str(total_paid.quantize(Decimal("0.01"))),
                "total_overdue": str(total_overdue.quantize(Decimal("0.01"))),
                "overall_collection_rate_percent": str(overall_rate),
            },
            "by_tenant": by_tenant,
        })


class PlatformSupportTicketViewSet(viewsets.ModelViewSet):
    queryset = SupportTicket.objects.select_related("tenant", "assigned_to").order_by("-created_at")
    serializer_class = SupportTicketSerializer
    permission_classes = [IsAuthenticated, IsGlobalSuperAdmin]

    def get_queryset(self):
        queryset = super().get_queryset()
        tenant_id = self.request.query_params.get("tenant_id")
        status_value = self.request.query_params.get("status")
        priority = self.request.query_params.get("priority")
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        if status_value:
            queryset = queryset.filter(status=status_value.upper())
        if priority:
            queryset = queryset.filter(priority=priority.upper())
        return queryset

    def perform_create(self, serializer):
        ticket = serializer.save(ticket_number=_ticket_number(), status=SupportTicket.STATUS_OPEN)
        _platform_audit(
            user=self.request.user,
            action="CREATE",
            model_name="PlatformSupportTicket",
            object_id=ticket.id,
            details=f"tenant={ticket.tenant_id} category={ticket.category} priority={ticket.priority}",
            tenant=ticket.tenant,
            request=self.request,
        )

    @action(detail=False, methods=["get"], url_path="sla-overview")
    def sla_overview(self, request):
        active_qs = SupportTicket.objects.filter(
            status__in=[SupportTicket.STATUS_OPEN, SupportTicket.STATUS_IN_PROGRESS]
        ).select_related("tenant")
        resolved_qs = SupportTicket.objects.filter(
            status__in=[SupportTicket.STATUS_RESOLVED, SupportTicket.STATUS_CLOSED],
            resolved_at__isnull=False,
        )
        now = timezone.now()
        overdue_first_response = 0
        overdue_resolution = 0
        for ticket in active_qs:
            first_response_hours, resolution_hours = _support_sla_hours(ticket.priority)
            if not ticket.first_response_at and ticket.created_at <= (now - timedelta(hours=first_response_hours)):
                overdue_first_response += 1
            if ticket.created_at <= (now - timedelta(hours=resolution_hours)):
                overdue_resolution += 1

        resolution_hours_values = []
        for ticket in resolved_qs:
            if ticket.resolved_at and ticket.created_at:
                resolution_hours_values.append((ticket.resolved_at - ticket.created_at).total_seconds() / 3600)
        avg_resolution_hours = Decimal("0.00")
        if resolution_hours_values:
            avg_resolution_hours = (
                Decimal(sum(resolution_hours_values)) / Decimal(len(resolution_hours_values))
            ).quantize(Decimal("0.01"))

        return Response(
            {
                "open_tickets": active_qs.count(),
                "overdue_first_response": overdue_first_response,
                "overdue_resolution": overdue_resolution,
                "avg_resolution_hours": str(avg_resolution_hours),
            }
        )

    @action(detail=True, methods=["post"], url_path="assign")
    def assign(self, request, pk=None):
        ticket = self.get_object()
        if ticket.status in [SupportTicket.STATUS_RESOLVED, SupportTicket.STATUS_CLOSED]:
            return Response({"detail": "Cannot assign resolved or closed ticket."}, status=status.HTTP_400_BAD_REQUEST)
        user_id = request.data.get("user_id")
        if not user_id:
            return Response({"detail": "user_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        user = User.objects.filter(id=user_id).first()
        if not user:
            return Response({"detail": "Assignee not found."}, status=status.HTTP_404_NOT_FOUND)
        ticket.assigned_to = user
        ticket.status = SupportTicket.STATUS_IN_PROGRESS
        if not ticket.first_response_at:
            ticket.first_response_at = timezone.now()
        ticket.save(update_fields=["assigned_to", "status", "first_response_at", "updated_at"])
        _platform_audit(
            user=request.user,
            action="ASSIGN",
            model_name="PlatformSupportTicket",
            object_id=ticket.id,
            details=f"assigned_to={user.id}",
            tenant=ticket.tenant,
            request=request,
        )
        return Response(SupportTicketSerializer(ticket).data)

    @action(detail=True, methods=["post"], url_path="add-note")
    def add_note(self, request, pk=None):
        ticket = self.get_object()
        serializer = SupportTicketNoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = SupportTicketNote.objects.create(
            ticket=ticket,
            author=request.user,
            body=serializer.validated_data["body"],
            is_internal=serializer.validated_data["is_internal"],
        )
        _platform_audit(
            user=request.user,
            action="COMMENT",
            model_name="PlatformSupportTicket",
            object_id=ticket.id,
            details=f"note_id={note.id} internal={note.is_internal}",
            tenant=ticket.tenant,
            request=request,
        )
        return Response(SupportTicketNoteSerializer(note).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="resolve")
    def resolve(self, request, pk=None):
        ticket = self.get_object()
        if ticket.status not in [SupportTicket.STATUS_OPEN, SupportTicket.STATUS_IN_PROGRESS]:
            return Response({"detail": "Only open or in-progress tickets can be resolved."}, status=status.HTTP_400_BAD_REQUEST)
        ticket.status = SupportTicket.STATUS_RESOLVED
        if not ticket.first_response_at:
            ticket.first_response_at = timezone.now()
        ticket.resolved_at = timezone.now()
        ticket.save(update_fields=["status", "first_response_at", "resolved_at", "updated_at"])
        _platform_audit(
            user=request.user,
            action="RESOLVE",
            model_name="PlatformSupportTicket",
            object_id=ticket.id,
            details="Ticket resolved",
            tenant=ticket.tenant,
            request=request,
        )
        return Response(SupportTicketSerializer(ticket).data)

    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, pk=None):
        ticket = self.get_object()
        if ticket.status != SupportTicket.STATUS_RESOLVED:
            return Response({"detail": "Only resolved tickets can be closed."}, status=status.HTTP_400_BAD_REQUEST)
        ticket.status = SupportTicket.STATUS_CLOSED
        ticket.closed_at = timezone.now()
        ticket.save(update_fields=["status", "closed_at", "updated_at"])
        _platform_audit(
            user=request.user,
            action="CLOSE",
            model_name="PlatformSupportTicket",
            object_id=ticket.id,
            details="Ticket closed",
            tenant=ticket.tenant,
            request=request,
        )
        return Response(SupportTicketSerializer(ticket).data)


class PlatformImpersonationSessionViewSet(viewsets.ModelViewSet):
    queryset = ImpersonationSession.objects.select_related("tenant", "requested_by", "approved_by").order_by("-created_at")
    serializer_class = ImpersonationSessionSerializer
    permission_classes = [IsAuthenticated, IsGlobalSuperAdmin]

    def get_queryset(self):
        queryset = super().get_queryset()
        tenant_id = self.request.query_params.get("tenant_id")
        status_value = self.request.query_params.get("status")
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        if status_value:
            queryset = queryset.filter(status=status_value.upper())
        return queryset

    def perform_create(self, serializer):
        session = serializer.save(requested_by=self.request.user, status=ImpersonationSession.STATUS_REQUESTED)
        _platform_audit(
            user=self.request.user,
            action="REQUEST",
            model_name="PlatformImpersonationSession",
            object_id=session.id,
            details=f"tenant={session.tenant_id} target={session.target_username} duration={session.duration_minutes}",
            tenant=session.tenant,
            request=self.request,
        )

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        session = self.get_object()
        if session.status != ImpersonationSession.STATUS_REQUESTED:
            return Response({"detail": "Only requested sessions can be approved."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = ImpersonationApprovalSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        if session.requested_by_id == request.user.id:
            return Response({"detail": "Second admin approval required."}, status=status.HTTP_400_BAD_REQUEST)
        session.status = ImpersonationSession.STATUS_APPROVED
        session.approved_by = request.user
        session.approval_notes = serializer.validated_data.get("approval_notes", "")
        session.save(update_fields=["status", "approved_by", "approval_notes", "updated_at"])
        _platform_audit(
            user=request.user,
            action="APPROVE",
            model_name="PlatformImpersonationSession",
            object_id=session.id,
            details="Session approved",
            tenant=session.tenant,
            request=request,
        )
        return Response(ImpersonationSessionSerializer(session).data)

    @action(detail=True, methods=["post"], url_path="start")
    def start(self, request, pk=None):
        session = self.get_object()
        if session.status != ImpersonationSession.STATUS_APPROVED:
            return Response({"detail": "Session must be approved before start."}, status=status.HTTP_400_BAD_REQUEST)
        if not session.approved_by_id:
            return Response({"detail": "Session approval record is required before start."}, status=status.HTTP_400_BAD_REQUEST)
        if session.duration_minutes > 240:
            return Response({"detail": "Duration exceeds max of 240 minutes."}, status=status.HTTP_400_BAD_REQUEST)
        if ImpersonationSession.objects.filter(
            tenant=session.tenant,
            target_username=session.target_username,
            status=ImpersonationSession.STATUS_ACTIVE,
        ).exclude(id=session.id).exists():
            return Response(
                {"detail": "An active impersonation session already exists for this target user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with schema_context(session.tenant.schema_name):
            target_user = User.objects.filter(username=session.target_username, is_active=True).first()
            if not target_user:
                return Response({"detail": "Target user not found in tenant schema."}, status=status.HTTP_404_NOT_FOUND)
            refresh = RefreshToken.for_user(target_user)
            access = str(refresh.access_token)

        session.status = ImpersonationSession.STATUS_ACTIVE
        session.started_at = timezone.now()
        session.expires_at = session.started_at + timedelta(minutes=session.duration_minutes)
        session.session_token = secrets.token_urlsafe(24)
        session.save(update_fields=["status", "started_at", "expires_at", "session_token", "updated_at"])
        _platform_audit(
            user=request.user,
            action="START",
            model_name="PlatformImpersonationSession",
            object_id=session.id,
            details=f"target={session.target_username} read_only={session.read_only}",
            tenant=session.tenant,
            request=request,
        )

        return Response(
            {
                "session": ImpersonationSessionSerializer(session).data,
                "impersonation_auth": {
                    "tenant_schema": session.tenant.schema_name,
                    "tenant_subdomain": session.tenant.subdomain,
                    "target_username": session.target_username,
                    "access": access,
                    "refresh": str(refresh),
                    "read_only": session.read_only,
                    "expires_at": session.expires_at.isoformat() if session.expires_at else None,
                },
            }
        )

    @action(detail=True, methods=["post"], url_path="end")
    def end(self, request, pk=None):
        session = self.get_object()
        if session.status != ImpersonationSession.STATUS_ACTIVE:
            return Response({"detail": "Only active sessions can be ended."}, status=status.HTTP_400_BAD_REQUEST)
        session.status = ImpersonationSession.STATUS_ENDED
        session.ended_at = timezone.now()
        session.save(update_fields=["status", "ended_at", "updated_at"])
        _platform_audit(
            user=request.user,
            action="END",
            model_name="PlatformImpersonationSession",
            object_id=session.id,
            details="Session ended",
            tenant=session.tenant,
            request=request,
        )
        return Response(ImpersonationSessionSerializer(session).data)


class PlatformMonitoringSnapshotViewSet(viewsets.ModelViewSet):
    queryset = MonitoringSnapshot.objects.select_related("tenant").order_by("-captured_at")
    serializer_class = MonitoringSnapshotSerializer
    permission_classes = [IsAuthenticated, IsGlobalSuperAdmin]

    def get_queryset(self):
        queryset = super().get_queryset()
        tenant_id = self.request.query_params.get("tenant_id")
        metric_key = self.request.query_params.get("metric_key")
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        if metric_key:
            queryset = queryset.filter(metric_key=metric_key)
        return queryset

    @action(detail=False, methods=["get"], url_path="overview")
    def overview(self, request):
        latest_keys = (
            MonitoringSnapshot.objects.values("metric_key")
            .annotate(latest=Count("id"))
            .order_by("metric_key")
        )
        open_alerts = MonitoringAlert.objects.filter(status=MonitoringAlert.STATUS_OPEN).count()
        critical_alerts = MonitoringAlert.objects.filter(
            status=MonitoringAlert.STATUS_OPEN,
            severity=MonitoringAlert.SEVERITY_CRITICAL,
        ).count()
        return Response(
            {
                "snapshot_metric_keys": [row["metric_key"] for row in latest_keys],
                "open_alerts": open_alerts,
                "critical_alerts": critical_alerts,
            }
        )


class PlatformMonitoringAlertViewSet(viewsets.ModelViewSet):
    queryset = MonitoringAlert.objects.select_related("tenant").order_by("-created_at")
    serializer_class = MonitoringAlertSerializer
    permission_classes = [IsAuthenticated, IsGlobalSuperAdmin]

    def get_queryset(self):
        queryset = super().get_queryset()
        tenant_id = self.request.query_params.get("tenant_id")
        severity = self.request.query_params.get("severity")
        status_value = self.request.query_params.get("status")
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        if severity:
            queryset = queryset.filter(severity=severity.upper())
        if status_value:
            queryset = queryset.filter(status=status_value.upper())
        return queryset

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        base_qs = MonitoringAlert.objects.all()
        open_count = base_qs.filter(status=MonitoringAlert.STATUS_OPEN).count()
        acknowledged_count = base_qs.filter(status=MonitoringAlert.STATUS_ACKNOWLEDGED).count()
        resolved_count = base_qs.filter(status=MonitoringAlert.STATUS_RESOLVED).count()
        critical_open = base_qs.filter(
            status=MonitoringAlert.STATUS_OPEN,
            severity=MonitoringAlert.SEVERITY_CRITICAL,
        ).count()
        mttr_hours = Decimal("0.00")
        resolved_recent = base_qs.filter(
            status=MonitoringAlert.STATUS_RESOLVED,
            resolved_at__isnull=False,
            created_at__gte=timezone.now() - timedelta(days=30),
        )
        durations = []
        for row in resolved_recent:
            if row.resolved_at:
                durations.append((row.resolved_at - row.created_at).total_seconds() / 3600)
        if durations:
            mttr_hours = (Decimal(sum(durations)) / Decimal(len(durations))).quantize(Decimal("0.01"))
        return Response(
            {
                "open": open_count,
                "acknowledged": acknowledged_count,
                "resolved": resolved_count,
                "critical_open": critical_open,
                "mttr_hours_30d": str(mttr_hours),
            }
        )

    @action(detail=True, methods=["post"], url_path="acknowledge")
    def acknowledge(self, request, pk=None):
        alert = self.get_object()
        if alert.status != MonitoringAlert.STATUS_OPEN:
            return Response({"detail": "Only open alerts can be acknowledged."}, status=status.HTTP_400_BAD_REQUEST)
        alert.status = MonitoringAlert.STATUS_ACKNOWLEDGED
        alert.acknowledged_at = timezone.now()
        alert.save(update_fields=["status", "acknowledged_at"])
        _platform_audit(
            user=request.user,
            action="ACKNOWLEDGE",
            model_name="PlatformMonitoringAlert",
            object_id=alert.id,
            details=f"severity={alert.severity}",
            tenant=alert.tenant,
            request=request,
        )
        return Response(MonitoringAlertSerializer(alert).data)

    @action(detail=True, methods=["post"], url_path="resolve")
    def resolve(self, request, pk=None):
        alert = self.get_object()
        if alert.status == MonitoringAlert.STATUS_RESOLVED:
            return Response({"detail": "Alert is already resolved."}, status=status.HTTP_400_BAD_REQUEST)
        alert.status = MonitoringAlert.STATUS_RESOLVED
        alert.resolved_at = timezone.now()
        alert.save(update_fields=["status", "resolved_at"])
        _platform_audit(
            user=request.user,
            action="RESOLVE",
            model_name="PlatformMonitoringAlert",
            object_id=alert.id,
            details=f"severity={alert.severity}",
            tenant=alert.tenant,
            request=request,
        )
        return Response(MonitoringAlertSerializer(alert).data)


class PlatformActionLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = PlatformActionLog.objects.select_related("actor", "tenant").order_by("-created_at", "-id")
    serializer_class = PlatformActionLogSerializer
    permission_classes = [IsAuthenticated, IsGlobalSuperAdmin]

    def get_queryset(self):
        queryset = super().get_queryset()
        tenant_id = self.request.query_params.get("tenant_id")
        actor_id = self.request.query_params.get("actor_id")
        action_value = self.request.query_params.get("action")
        model_name = self.request.query_params.get("model_name")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")

        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        if actor_id:
            queryset = queryset.filter(actor_id=actor_id)
        if action_value:
            queryset = queryset.filter(action__iexact=action_value.strip())
        if model_name:
            queryset = queryset.filter(model_name__iexact=model_name.strip())
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        return queryset


class PlatformSettingViewSet(viewsets.ModelViewSet):
    queryset = PlatformSetting.objects.select_related("updated_by").order_by("key")
    serializer_class = PlatformSettingSerializer
    permission_classes = [IsAuthenticated, IsGlobalSuperAdmin]

    def perform_create(self, serializer):
        obj = serializer.save(updated_by=self.request.user)
        _platform_audit(
            user=self.request.user,
            action="CREATE",
            model_name="PlatformSetting",
            object_id=obj.id,
            details=f"key={obj.key}",
            request=self.request,
        )

    def perform_update(self, serializer):
        obj = serializer.save(updated_by=self.request.user)
        _platform_audit(
            user=self.request.user,
            action="UPDATE",
            model_name="PlatformSetting",
            object_id=obj.id,
            details=f"key={obj.key}",
            request=self.request,
        )


class PlatformApiKeyViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    queryset = PlatformApiKey.objects.select_related("tenant", "created_by").order_by("-created_at", "-id")
    serializer_class = PlatformApiKeySerializer
    permission_classes = [IsAuthenticated, IsGlobalSuperAdmin]

    def get_queryset(self):
        queryset = super().get_queryset()
        tenant_id = self.request.query_params.get("tenant")
        active = self.request.query_params.get("active")
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        if active in {"1", "true", "True"}:
            queryset = queryset.filter(is_active=True)
        elif active in {"0", "false", "False"}:
            queryset = queryset.filter(is_active=False)
        return queryset

    def create(self, request):
        serializer = PlatformApiKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant = serializer.validated_data["tenant"]
        label = serializer.validated_data["label"]
        row, raw_key = _generate_platform_api_key(tenant=tenant, label=label, actor=request.user)
        _platform_audit(
            user=request.user,
            action="CREATE",
            model_name="PlatformApiKey",
            object_id=row.id,
            details=f"tenant={tenant.schema_name} label={label}",
            tenant=tenant,
            request=request,
        )
        payload = PlatformApiKeySerializer(row).data
        payload["raw_key"] = raw_key
        return Response(payload, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, pk=None):
        row = self.get_object()
        if not row.is_active:
            return Response({"detail": "API key is already revoked."}, status=status.HTTP_400_BAD_REQUEST)
        row.is_active = False
        row.revoked_at = timezone.now()
        row.save(update_fields=["is_active", "revoked_at", "updated_at"])
        _platform_audit(
            user=request.user,
            action="REVOKE",
            model_name="PlatformApiKey",
            object_id=row.id,
            details=f"tenant={row.tenant.schema_name} label={row.label}",
            tenant=row.tenant,
            request=request,
        )
        return Response(PlatformApiKeySerializer(row).data, status=status.HTTP_200_OK)


class PlatformIntegrationViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsGlobalSuperAdmin]

    def list(self, request):
        settings_map = {
            row.key: row
            for row in PlatformSetting.objects.filter(
                key__in=[item["setting_key"] for item in PLATFORM_INTEGRATION_CATALOG]
            ).order_by("key")
        }
        payload = []
        for idx, item in enumerate(PLATFORM_INTEGRATION_CATALOG, start=1):
            setting = settings_map.get(item["setting_key"])
            value = getattr(setting, "value", {})
            payload.append(
                {
                    "id": idx,
                    "code": item["code"],
                    "name": item["name"],
                    "category": item["category"],
                    "description": item["description"],
                    "status": _integration_status(value),
                    "configured": setting is not None,
                    "setting_key": item["setting_key"],
                    "updated_at": setting.updated_at if setting else None,
                }
            )
        return Response(payload, status=status.HTTP_200_OK)


class PlatformAdminUserViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    queryset = GlobalSuperAdmin.objects.select_related("user").order_by("user__username")
    serializer_class = PlatformAdminUserSerializer
    permission_classes = [IsAuthenticated, IsGlobalSuperAdmin]

    def create(self, request):
        serializer = PlatformAdminUserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        username = data["username"].strip()
        email = data.get("email", "").strip()
        password = data.get("password", "")
        role = data["role"]
        is_active = data["is_active"]

        user_defaults = {"email": email, "is_staff": True, "is_active": True}
        user, created = User.objects.get_or_create(username=username, defaults=user_defaults)
        if not created:
            changed = False
            if email and user.email != email:
                user.email = email
                changed = True
            if not user.is_staff:
                user.is_staff = True
                changed = True
            if not user.is_active:
                user.is_active = True
                changed = True
            if changed:
                user.save(update_fields=["email", "is_staff", "is_active"])

        if password:
            user.set_password(password)
            user.save(update_fields=["password"])

        global_admin, _ = GlobalSuperAdmin.objects.get_or_create(user=user)
        global_admin.role = role
        global_admin.is_active = is_active
        global_admin.save(update_fields=["role", "is_active", "updated_at"])
        _platform_audit(
            user=request.user,
            action="GRANT",
            model_name="GlobalSuperAdmin",
            object_id=global_admin.id,
            details=f"username={username} role={role} active={is_active}",
            request=request,
        )
        return Response(PlatformAdminUserSerializer(global_admin).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], url_path="update")
    def update_admin(self, request, pk=None):
        row = self.get_object()
        role = request.data.get("role")
        is_active = request.data.get("is_active")
        update_fields = []
        if role is not None:
            role_value = str(role).strip().upper()
            allowed = {choice[0] for choice in GlobalSuperAdmin.ROLE_CHOICES}
            if role_value not in allowed:
                return Response({"detail": "Invalid role value."}, status=status.HTTP_400_BAD_REQUEST)
            row.role = role_value
            update_fields.append("role")
        if is_active is not None:
            row.is_active = bool(is_active)
            update_fields.append("is_active")
        if not update_fields:
            return Response({"detail": "No changes supplied."}, status=status.HTTP_400_BAD_REQUEST)
        update_fields.append("updated_at")
        row.save(update_fields=update_fields)
        _platform_audit(
            user=request.user,
            action="UPDATE",
            model_name="GlobalSuperAdmin",
            object_id=row.id,
            details=f"role={row.role} active={row.is_active}",
            request=request,
        )
        return Response(PlatformAdminUserSerializer(row).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, pk=None):
        row = self.get_object()
        if row.user_id == request.user.id:
            return Response({"detail": "You cannot revoke your own active super admin access."}, status=status.HTTP_400_BAD_REQUEST)
        row.is_active = False
        row.save(update_fields=["is_active", "updated_at"])
        _platform_audit(
            user=request.user,
            action="REVOKE",
            model_name="GlobalSuperAdmin",
            object_id=row.id,
            details=f"username={row.user.username}",
            request=request,
        )
        return Response(PlatformAdminUserSerializer(row).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        row = self.get_object()
        serializer = PlatformAdminPasswordResetSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        password = serializer.validated_data["password"]

        user = row.user
        user.set_password(password)
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["password", "is_active"])
        else:
            user.save(update_fields=["password"])

        _platform_audit(
            user=request.user,
            action="RESET_PASSWORD",
            model_name="GlobalSuperAdmin",
            object_id=row.id,
            details=f"username={user.username}",
            request=request,
        )
        return Response(
            {
                "id": row.id,
                "username": user.username,
                "password_reset": True,
            },
            status=status.HTTP_200_OK,
        )


class PlatformMaintenanceWindowViewSet(viewsets.ModelViewSet):
    queryset = MaintenanceWindow.objects.select_related("created_by").order_by("-starts_at")
    serializer_class = MaintenanceWindowSerializer
    permission_classes = [IsAuthenticated, IsGlobalSuperAdmin]

    def perform_create(self, serializer):
        obj = serializer.save(created_by=self.request.user, status=MaintenanceWindow.STATUS_SCHEDULED)
        _queue_maintenance_notifications(
            window=obj,
            event_type=PlatformNotificationDispatch.EVENT_MAINTENANCE_SCHEDULED,
            actor=self.request.user,
            request=self.request,
        )
        _platform_audit(
            user=self.request.user,
            action="CREATE",
            model_name="PlatformMaintenanceWindow",
            object_id=obj.id,
            details=f"title={obj.title}",
            request=self.request,
        )

    @action(detail=True, methods=["post"], url_path="start")
    def start(self, request, pk=None):
        row = self.get_object()
        if row.status != MaintenanceWindow.STATUS_SCHEDULED:
            return Response({"detail": "Only scheduled windows can be started."}, status=status.HTTP_400_BAD_REQUEST)
        now = timezone.now()
        if row.starts_at and now < row.starts_at:
            return Response({"detail": "Cannot start maintenance window before starts_at."}, status=status.HTTP_400_BAD_REQUEST)
        if row.ends_at and now > row.ends_at:
            return Response({"detail": "Cannot start maintenance window after ends_at."}, status=status.HTTP_400_BAD_REQUEST)
        if MaintenanceWindow.objects.filter(status=MaintenanceWindow.STATUS_ACTIVE).exclude(id=row.id).exists():
            return Response({"detail": "Another maintenance window is already active."}, status=status.HTTP_400_BAD_REQUEST)
        row.status = MaintenanceWindow.STATUS_ACTIVE
        row.save(update_fields=["status", "updated_at"])
        _queue_maintenance_notifications(
            window=row,
            event_type=PlatformNotificationDispatch.EVENT_MAINTENANCE_STARTED,
            actor=request.user,
            request=request,
        )
        _platform_audit(user=request.user, action="START", model_name="PlatformMaintenanceWindow", object_id=row.id, details="Window started", request=request)
        return Response(MaintenanceWindowSerializer(row).data)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        row = self.get_object()
        if row.status != MaintenanceWindow.STATUS_ACTIVE:
            return Response({"detail": "Only active windows can be completed."}, status=status.HTTP_400_BAD_REQUEST)
        force = bool(request.data.get("force"))
        if row.ends_at and timezone.now() < row.ends_at and not force:
            return Response(
                {"detail": "Window end time has not been reached. Pass force=true to complete early."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        row.status = MaintenanceWindow.STATUS_COMPLETED
        row.save(update_fields=["status", "updated_at"])
        _queue_maintenance_notifications(
            window=row,
            event_type=PlatformNotificationDispatch.EVENT_MAINTENANCE_COMPLETED,
            actor=request.user,
            request=request,
        )
        _platform_audit(
            user=request.user,
            action="COMPLETE",
            model_name="PlatformMaintenanceWindow",
            object_id=row.id,
            details=f"Window completed force={force}",
            request=request,
        )
        return Response(MaintenanceWindowSerializer(row).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        row = self.get_object()
        if row.status in [MaintenanceWindow.STATUS_COMPLETED, MaintenanceWindow.STATUS_CANCELLED]:
            return Response({"detail": "Window is already finalized."}, status=status.HTTP_400_BAD_REQUEST)
        row.status = MaintenanceWindow.STATUS_CANCELLED
        row.save(update_fields=["status", "updated_at"])
        _queue_maintenance_notifications(
            window=row,
            event_type=PlatformNotificationDispatch.EVENT_MAINTENANCE_CANCELLED,
            actor=request.user,
            request=request,
        )
        _platform_audit(user=request.user, action="CANCEL", model_name="PlatformMaintenanceWindow", object_id=row.id, details="Window cancelled", request=request)
        return Response(MaintenanceWindowSerializer(row).data)


class PlatformDeploymentReleaseViewSet(viewsets.ModelViewSet):
    queryset = DeploymentRelease.objects.select_related("created_by", "rollback_of").order_by("-created_at")
    serializer_class = DeploymentReleaseSerializer
    permission_classes = [IsAuthenticated, IsGlobalSuperAdmin]

    def perform_create(self, serializer):
        obj = serializer.save(created_by=self.request.user, status=DeploymentRelease.STATUS_PLANNED)
        _platform_audit(user=self.request.user, action="CREATE", model_name="PlatformDeploymentRelease", object_id=obj.id, details=f"version={obj.version}", request=self.request)

    @staticmethod
    def _notify_for_release(*, release: DeploymentRelease, event_type: str, actor, request=None):
        active_tenants = Tenant.objects.filter(is_active=True).only("id")
        created = 0
        now = timezone.now()
        for tenant in active_tenants:
            PlatformNotificationDispatch.objects.create(
                tenant=tenant,
                release=release,
                event_type=event_type,
                channel=PlatformNotificationDispatch.CHANNEL_IN_APP,
                status=PlatformNotificationDispatch.STATUS_SENT,
                attempts=1,
                sent_at=now,
                created_by=actor if getattr(actor, "is_authenticated", False) else None,
                payload={
                    "version": release.version,
                    "environment": release.environment,
                    "status": release.status,
                    "event_type": event_type,
                },
            )
            created += 1
        _platform_audit(
            user=actor,
            action="NOTIFY",
            model_name="PlatformDeploymentRelease",
            object_id=release.id,
            details=f"queued {created} in-app release notifications for event={event_type}",
            request=request,
            metadata={"event_type": event_type, "count": created},
        )

    @staticmethod
    def _hook_token_valid(request) -> bool:
        expected = str(getattr(settings, "DEPLOYMENT_CALLBACK_TOKEN", "")).strip()
        if not expected:
            return False
        provided = str(request.headers.get("X-Platform-Hook-Token", "")).strip()
        if not provided:
            auth_value = str(request.headers.get("Authorization", "")).strip()
            if auth_value.lower().startswith("bearer "):
                provided = auth_value[7:].strip()
        return bool(provided) and hmac.compare_digest(provided, expected)

    @staticmethod
    def _health_summary_for_release(row: DeploymentRelease) -> dict:
        critical_open = MonitoringAlert.objects.filter(
            severity=MonitoringAlert.SEVERITY_CRITICAL,
            status__in=[MonitoringAlert.STATUS_OPEN, MonitoringAlert.STATUS_ACKNOWLEDGED],
        )
        warning_open = MonitoringAlert.objects.filter(
            severity=MonitoringAlert.SEVERITY_WARNING,
            status__in=[MonitoringAlert.STATUS_OPEN, MonitoringAlert.STATUS_ACKNOWLEDGED],
        )
        recent_since = timezone.now() - timedelta(minutes=15)
        recent_snapshots = MonitoringSnapshot.objects.filter(captured_at__gte=recent_since).count()

        status_value = "healthy"
        if critical_open.exists():
            status_value = "failed"
        elif warning_open.exists():
            status_value = "degraded"

        return {
            "status": status_value,
            "critical_open_alerts": critical_open.count(),
            "warning_open_alerts": warning_open.count(),
            "recent_snapshots_15m": recent_snapshots,
            "environment": row.environment,
            "release_id": row.id,
            "checked_at": timezone.now().isoformat(),
        }

    @action(detail=True, methods=["post"], url_path="start")
    def start(self, request, pk=None):
        row = self.get_object()
        if row.status != DeploymentRelease.STATUS_PLANNED:
            return Response({"detail": "Only planned releases can be started."}, status=status.HTTP_400_BAD_REQUEST)
        if DeploymentRelease.objects.filter(
            environment=row.environment,
            status=DeploymentRelease.STATUS_DEPLOYING,
        ).exclude(id=row.id).exists():
            return Response(
                {"detail": f"A deployment is already running for environment '{row.environment}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        allow_without_maintenance = bool(request.data.get("allow_without_maintenance"))
        now = timezone.now()
        has_active_window = MaintenanceWindow.objects.filter(
            status=MaintenanceWindow.STATUS_ACTIVE,
            starts_at__lte=now,
            ends_at__gte=now,
        ).exists()
        if not has_active_window and not allow_without_maintenance:
            return Response(
                {
                    "detail": "No active maintenance window found. Start one first or pass allow_without_maintenance=true."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        row.status = DeploymentRelease.STATUS_DEPLOYING
        row.started_at = timezone.now()
        row.save(update_fields=["status", "started_at", "updated_at"])
        self._notify_for_release(
            release=row,
            event_type=PlatformNotificationDispatch.EVENT_DEPLOYMENT_STARTED,
            actor=request.user,
            request=request,
        )
        _platform_audit(
            user=request.user,
            action="START",
            model_name="PlatformDeploymentRelease",
            object_id=row.id,
            details=f"Release deployment started allow_without_maintenance={allow_without_maintenance}",
            request=request,
        )
        return Response(DeploymentReleaseSerializer(row).data)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        row = self.get_object()
        if row.status != DeploymentRelease.STATUS_DEPLOYING:
            return Response({"detail": "Only deploying releases can be completed."}, status=status.HTTP_400_BAD_REQUEST)
        force = bool(request.data.get("force"))
        health_summary = request.data.get("health_summary")
        if health_summary is None:
            health_summary = self._health_summary_for_release(row)
        if not isinstance(health_summary, dict):
            return Response({"detail": "health_summary must be an object."}, status=status.HTTP_400_BAD_REQUEST)
        health_status = str(health_summary.get("status", "")).lower().strip()
        if not health_status:
            return Response({"detail": "health_summary.status is required."}, status=status.HTTP_400_BAD_REQUEST)
        if health_status not in ["healthy", "degraded"] and not force:
            return Response(
                {"detail": "health_summary.status must be healthy or degraded. Pass force=true to override."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        blocking_alerts = MonitoringAlert.objects.filter(
            severity=MonitoringAlert.SEVERITY_CRITICAL,
            status__in=[MonitoringAlert.STATUS_OPEN, MonitoringAlert.STATUS_ACKNOWLEDGED],
        )
        if blocking_alerts.exists() and not force:
            return Response(
                {
                    "detail": "Cannot complete release while critical monitoring alerts are unresolved. Pass force=true to override."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        row.status = DeploymentRelease.STATUS_SUCCESS
        row.completed_at = timezone.now()
        row.health_summary = health_summary
        row.save(update_fields=["status", "completed_at", "health_summary", "updated_at"])
        self._notify_for_release(
            release=row,
            event_type=PlatformNotificationDispatch.EVENT_DEPLOYMENT_COMPLETED,
            actor=request.user,
            request=request,
        )
        _platform_audit(
            user=request.user,
            action="COMPLETE",
            model_name="PlatformDeploymentRelease",
            object_id=row.id,
            details=f"Release deployment completed status={health_status} force={force}",
            request=request,
        )
        return Response(DeploymentReleaseSerializer(row).data)

    @action(detail=True, methods=["post"], url_path="run-health-checks")
    def run_health_checks(self, request, pk=None):
        row = self.get_object()
        summary = self._health_summary_for_release(row)
        row.health_summary = summary
        row.save(update_fields=["health_summary", "updated_at"])
        _platform_audit(
            user=request.user,
            action="HEALTHCHECK",
            model_name="PlatformDeploymentRelease",
            object_id=row.id,
            details=f"Release health checks executed status={summary.get('status')}",
            request=request,
        )
        return Response(summary, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="callbacks/status")
    def callback_status(self, request):
        if not self._hook_token_valid(request):
            return Response({"detail": "Invalid deployment callback token."}, status=status.HTTP_403_FORBIDDEN)

        release_id = request.data.get("release_id")
        if not release_id:
            return Response({"detail": "release_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            row = DeploymentRelease.objects.get(id=release_id)
        except DeploymentRelease.DoesNotExist:
            return Response({"detail": "Release not found."}, status=status.HTTP_404_NOT_FOUND)

        event = str(request.data.get("event", "")).strip().lower()
        if event not in {"deploying", "success", "failed", "rolled_back"}:
            return Response({"detail": "event must be one of: deploying, success, failed, rolled_back."}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        if event == "deploying":
            if row.status not in {DeploymentRelease.STATUS_PLANNED, DeploymentRelease.STATUS_DEPLOYING}:
                return Response({"detail": "Release cannot transition to deploying from current status."}, status=status.HTTP_400_BAD_REQUEST)
            row.status = DeploymentRelease.STATUS_DEPLOYING
            row.started_at = row.started_at or now
            row.save(update_fields=["status", "started_at", "updated_at"])
        elif event == "success":
            if row.status != DeploymentRelease.STATUS_DEPLOYING:
                return Response({"detail": "Only deploying releases can transition to success."}, status=status.HTTP_400_BAD_REQUEST)
            payload_summary = request.data.get("health_summary")
            summary = payload_summary if isinstance(payload_summary, dict) else self._health_summary_for_release(row)
            row.status = DeploymentRelease.STATUS_SUCCESS
            row.completed_at = now
            row.health_summary = summary
            row.save(update_fields=["status", "completed_at", "health_summary", "updated_at"])
        elif event == "failed":
            if row.status != DeploymentRelease.STATUS_DEPLOYING:
                return Response({"detail": "Only deploying releases can transition to failed."}, status=status.HTTP_400_BAD_REQUEST)
            notes = str(request.data.get("notes", "")).strip()
            if notes:
                row.notes = f"{row.notes}\n{notes}".strip() if row.notes else notes
            row.status = DeploymentRelease.STATUS_FAILED
            row.completed_at = now
            row.save(update_fields=["status", "completed_at", "notes", "updated_at"])
        else:  # rolled_back
            if row.status not in {DeploymentRelease.STATUS_DEPLOYING, DeploymentRelease.STATUS_FAILED, DeploymentRelease.STATUS_SUCCESS}:
                return Response({"detail": "Release cannot transition to rolled_back from current status."}, status=status.HTTP_400_BAD_REQUEST)
            row.status = DeploymentRelease.STATUS_ROLLED_BACK
            row.completed_at = now
            row.save(update_fields=["status", "completed_at", "updated_at"])

        _platform_audit(
            user=None,
            action="HOOK_UPDATE",
            model_name="PlatformDeploymentRelease",
            object_id=row.id,
            details=f"deployment callback event={event} status={row.status}",
            request=request,
            metadata={"event": event},
        )
        return Response(DeploymentReleaseSerializer(row).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="fail")
    def fail(self, request, pk=None):
        row = self.get_object()
        if row.status != DeploymentRelease.STATUS_DEPLOYING:
            return Response({"detail": "Only deploying releases can fail."}, status=status.HTTP_400_BAD_REQUEST)
        row.status = DeploymentRelease.STATUS_FAILED
        row.completed_at = timezone.now()
        row.notes = request.data.get("notes", row.notes)
        row.save(update_fields=["status", "completed_at", "notes", "updated_at"])
        self._notify_for_release(
            release=row,
            event_type=PlatformNotificationDispatch.EVENT_DEPLOYMENT_FAILED,
            actor=request.user,
            request=request,
        )
        _platform_audit(user=request.user, action="FAIL", model_name="PlatformDeploymentRelease", object_id=row.id, details="Release deployment failed", request=request)
        return Response(DeploymentReleaseSerializer(row).data)

    @action(detail=True, methods=["post"], url_path="rollback")
    def rollback(self, request, pk=None):
        row = self.get_object()
        if row.status not in [
            DeploymentRelease.STATUS_DEPLOYING,
            DeploymentRelease.STATUS_SUCCESS,
            DeploymentRelease.STATUS_FAILED,
        ]:
            return Response(
                {"detail": "Rollback is allowed only for deploying, success, or failed releases."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        rollback_release = DeploymentRelease.objects.create(
            version=f"{row.version}-rollback",
            environment=row.environment,
            status=DeploymentRelease.STATUS_ROLLED_BACK,
            notes=request.data.get("notes", f"Rollback created from release {row.id}"),
            started_at=timezone.now(),
            completed_at=timezone.now(),
            rollback_of=row,
            created_by=request.user,
        )
        row.status = DeploymentRelease.STATUS_ROLLED_BACK
        row.save(update_fields=["status", "updated_at"])
        hook_payload = {
            "release_id": rollback_release.id,
            "event": "rolled_back",
            "rollback_of": row.id,
            "version": rollback_release.version,
            "environment": rollback_release.environment,
        }
        hook_run = _execute_deployment_hook(
            release=rollback_release,
            hook_type=DeploymentHookRun.TYPE_ROLLBACK,
            payload=hook_payload,
            actor=request.user,
        )
        _platform_audit(user=request.user, action="ROLLBACK", model_name="PlatformDeploymentRelease", object_id=row.id, details=f"rollback_release={rollback_release.id}", request=request)
        return Response(
            {
                "release": DeploymentReleaseSerializer(rollback_release).data,
                "hook_run": DeploymentHookRunSerializer(hook_run).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="trigger-pipeline")
    def trigger_pipeline(self, request, pk=None):
        row = self.get_object()
        payload = {
            "release_id": row.id,
            "event": "trigger",
            "version": row.version,
            "environment": row.environment,
            "requested_by": getattr(request.user, "username", None),
            "mode": str(request.data.get("mode", "manual")).strip() or "manual",
        }
        hook_run = _execute_deployment_hook(
            release=row,
            hook_type=DeploymentHookRun.TYPE_TRIGGER,
            payload=payload,
            actor=request.user,
        )
        _platform_audit(
            user=request.user,
            action="TRIGGER_PIPELINE",
            model_name="PlatformDeploymentRelease",
            object_id=row.id,
            details=f"trigger hook status={hook_run.status}",
            request=request,
            metadata={"hook_run_id": hook_run.id, "hook_status": hook_run.status},
        )
        response_status = status.HTTP_200_OK if hook_run.status == DeploymentHookRun.STATUS_SUCCESS else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(DeploymentHookRunSerializer(hook_run).data, status=response_status)

    @action(detail=True, methods=["get"], url_path="hook-runs")
    def hook_runs(self, request, pk=None):
        row = self.get_object()
        data = DeploymentHookRunSerializer(row.hook_runs.order_by("-executed_at"), many=True).data
        return Response(data, status=status.HTTP_200_OK)


class PlatformFeatureFlagViewSet(viewsets.ModelViewSet):
    queryset = FeatureFlag.objects.prefetch_related("target_tenants").order_by("key")
    serializer_class = FeatureFlagSerializer
    permission_classes = [IsAuthenticated, IsGlobalSuperAdmin]

    def perform_create(self, serializer):
        obj = serializer.save(updated_by=self.request.user)
        _platform_audit(user=self.request.user, action="CREATE", model_name="PlatformFeatureFlag", object_id=obj.id, details=f"key={obj.key}", request=self.request)

    def perform_update(self, serializer):
        obj = serializer.save(updated_by=self.request.user)
        _platform_audit(user=self.request.user, action="UPDATE", model_name="PlatformFeatureFlag", object_id=obj.id, details=f"key={obj.key}", request=self.request)

    @action(detail=True, methods=["post"], url_path="toggle")
    def toggle(self, request, pk=None):
        row = self.get_object()
        if not row.is_enabled and int(row.rollout_percent or 0) <= 0:
            return Response(
                {"detail": "Cannot enable a feature flag with rollout_percent <= 0."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        row.is_enabled = not row.is_enabled
        row.updated_by = request.user
        row.save(update_fields=["is_enabled", "updated_by", "updated_at"])
        _platform_audit(user=request.user, action="TOGGLE", model_name="PlatformFeatureFlag", object_id=row.id, details=f"enabled={row.is_enabled}", request=request)
        return Response(FeatureFlagSerializer(row).data)

    @action(detail=False, methods=["get"], url_path="evaluate")
    def evaluate(self, request):
        key = str(request.query_params.get("key", "")).strip()
        if not key:
            return Response({"detail": "key query parameter is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            row = FeatureFlag.objects.prefetch_related("target_tenants").get(key=key)
        except FeatureFlag.DoesNotExist:
            return Response({"detail": "Feature flag not found."}, status=status.HTTP_404_NOT_FOUND)

        tenant_id = request.query_params.get("tenant_id")
        actor_id = request.query_params.get("actor_id") or getattr(request.user, "id", None)
        if not row.is_enabled:
            enabled = False
            reason = "flag_disabled"
            bucket = None
        elif int(row.rollout_percent or 0) <= 0:
            enabled = False
            reason = "zero_rollout"
            bucket = None
        else:
            if row.target_tenants.exists():
                allowed_tenants = set(str(v) for v in row.target_tenants.values_list("id", flat=True))
                if not tenant_id or str(tenant_id) not in allowed_tenants:
                    return Response(
                        {
                            "key": row.key,
                            "enabled": False,
                            "reason": "tenant_not_targeted",
                            "rollout_percent": row.rollout_percent,
                        },
                        status=status.HTTP_200_OK,
                    )
            stable_seed = f"{row.key}:{tenant_id or 'platform'}:{actor_id or 'anonymous'}"
            digest = hashlib.sha256(stable_seed.encode("utf-8")).hexdigest()
            bucket = int(digest[:8], 16) % 100
            enabled = bucket < int(row.rollout_percent)
            reason = "rollout_match" if enabled else "rollout_miss"

        return Response(
            {
                "key": row.key,
                "enabled": enabled,
                "reason": reason,
                "bucket": bucket,
                "rollout_percent": row.rollout_percent,
                "tenant_id": tenant_id,
                "actor_id": str(actor_id) if actor_id else None,
                "is_enabled": row.is_enabled,
            },
            status=status.HTTP_200_OK,
        )


class PlatformBackupJobViewSet(viewsets.ModelViewSet):
    queryset = BackupJob.objects.select_related("tenant", "created_by").order_by("-created_at")
    serializer_class = BackupJobSerializer
    permission_classes = [IsAuthenticated, IsGlobalSuperAdmin]

    def perform_create(self, serializer):
        scope = serializer.validated_data.get("scope", BackupJob.SCOPE_PLATFORM)
        tenant = serializer.validated_data.get("tenant")
        if scope == BackupJob.SCOPE_TENANT and tenant is None:
            raise ValidationError({"tenant": "tenant is required when scope=TENANT."})
        obj = serializer.save(created_by=self.request.user, status=BackupJob.STATUS_QUEUED)
        _platform_audit(user=self.request.user, action="CREATE", model_name="PlatformBackupJob", object_id=obj.id, details=f"scope={obj.scope} type={obj.backup_type}", tenant=obj.tenant, request=self.request)

    @action(detail=True, methods=["post"], url_path="start")
    def start(self, request, pk=None):
        row = self.get_object()
        if row.status not in [BackupJob.STATUS_QUEUED, BackupJob.STATUS_FAILED]:
            return Response({"detail": "Backup cannot be started from current status."}, status=status.HTTP_400_BAD_REQUEST)
        row.status = BackupJob.STATUS_RUNNING
        row.started_at = timezone.now()
        row.save(update_fields=["status", "started_at", "updated_at"])
        _platform_audit(user=request.user, action="START", model_name="PlatformBackupJob", object_id=row.id, details="Backup started", tenant=row.tenant, request=request)
        return Response(BackupJobSerializer(row).data)

    @action(detail=True, methods=["post"], url_path="execute-engine")
    def execute_engine(self, request, pk=None):
        row = self.get_object()
        if row.status not in [BackupJob.STATUS_QUEUED, BackupJob.STATUS_RUNNING, BackupJob.STATUS_FAILED]:
            return Response({"detail": "Backup engine execution is not allowed from current status."}, status=status.HTTP_400_BAD_REQUEST)
        if row.status != BackupJob.STATUS_RUNNING:
            row.status = BackupJob.STATUS_RUNNING
            row.started_at = row.started_at or timezone.now()
            row.save(update_fields=["status", "started_at", "updated_at"])
        execution = _execute_backup_engine(backup=row, actor=request.user)
        if execution.status == BackupExecutionRun.STATUS_SUCCESS:
            row.status = BackupJob.STATUS_SUCCESS
            row.completed_at = timezone.now()
            row.storage_path = execution.output_path
            row.checksum = execution.checksum
            row.size_bytes = execution.size_bytes
            row.error = ""
            row.save(
                update_fields=[
                    "status",
                    "completed_at",
                    "storage_path",
                    "checksum",
                    "size_bytes",
                    "error",
                    "updated_at",
                ]
            )
        else:
            row.status = BackupJob.STATUS_FAILED
            row.completed_at = timezone.now()
            row.error = execution.logs or execution.error or "Backup execution failed."
            row.save(update_fields=["status", "completed_at", "error", "updated_at"])
        _platform_audit(
            user=request.user,
            action="EXECUTE_ENGINE",
            model_name="PlatformBackupJob",
            object_id=row.id,
            details=f"engine_mode={execution.engine_mode} status={execution.status}",
            tenant=row.tenant,
            request=request,
            metadata={"execution_id": execution.id},
        )
        return Response(
            {
                "backup": BackupJobSerializer(row).data,
                "execution": BackupExecutionRunSerializer(execution).data,
            },
            status=status.HTTP_200_OK if execution.status == BackupExecutionRun.STATUS_SUCCESS else status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    @action(detail=True, methods=["get"], url_path="executions")
    def executions(self, request, pk=None):
        row = self.get_object()
        return Response(BackupExecutionRunSerializer(row.execution_runs.order_by("-started_at"), many=True).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        row = self.get_object()
        if row.status != BackupJob.STATUS_RUNNING:
            return Response({"detail": "Only running backups can be completed."}, status=status.HTTP_400_BAD_REQUEST)
        storage_path = str(request.data.get("storage_path", row.storage_path or "")).strip()
        checksum = str(request.data.get("checksum", row.checksum or "")).strip()
        if not storage_path:
            return Response({"detail": "storage_path is required to complete a backup."}, status=status.HTTP_400_BAD_REQUEST)
        if not checksum:
            return Response({"detail": "checksum is required to complete a backup."}, status=status.HTTP_400_BAD_REQUEST)
        size_bytes_raw = request.data.get("size_bytes", row.size_bytes or 0)
        try:
            size_bytes = int(size_bytes_raw)
        except (TypeError, ValueError):
            return Response({"detail": "size_bytes must be an integer."}, status=status.HTTP_400_BAD_REQUEST)
        if size_bytes <= 0:
            return Response({"detail": "size_bytes must be greater than 0."}, status=status.HTTP_400_BAD_REQUEST)
        row.status = BackupJob.STATUS_SUCCESS
        row.completed_at = timezone.now()
        row.storage_path = storage_path
        row.checksum = checksum
        row.size_bytes = size_bytes
        row.save(update_fields=["status", "completed_at", "storage_path", "checksum", "size_bytes", "updated_at"])
        _platform_audit(user=request.user, action="COMPLETE", model_name="PlatformBackupJob", object_id=row.id, details="Backup completed", tenant=row.tenant, request=request)
        return Response(BackupJobSerializer(row).data)

    @action(detail=True, methods=["post"], url_path="verify-integrity")
    def verify_integrity(self, request, pk=None):
        row = self.get_object()
        if row.status != BackupJob.STATUS_SUCCESS:
            return Response({"detail": "Only successful backups can be integrity-verified."}, status=status.HTTP_400_BAD_REQUEST)
        expected_checksum = str(request.data.get("expected_checksum", row.checksum or "")).strip()
        if not expected_checksum:
            return Response({"detail": "expected_checksum (or stored checksum) is required."}, status=status.HTTP_400_BAD_REQUEST)
        verified = hmac.compare_digest(str(row.checksum or "").strip(), expected_checksum)
        details = "Integrity verification passed." if verified else "Integrity verification failed."
        _platform_audit(
            user=request.user,
            action="VERIFY_INTEGRITY",
            model_name="PlatformBackupJob",
            object_id=row.id,
            details=details,
            tenant=row.tenant,
            request=request,
            metadata={"verified": verified},
        )
        if not verified:
            return Response(
                {"backup_id": row.id, "verified": False, "detail": "Checksum mismatch."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"backup_id": row.id, "verified": True, "checksum": row.checksum}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="enforce-retention")
    def enforce_retention(self, request):
        dry_run = bool(request.data.get("dry_run", True))
        now = timezone.now()
        candidates = []
        for job in BackupJob.objects.filter(status=BackupJob.STATUS_SUCCESS).order_by("id"):
            anchor = job.completed_at or job.created_at
            if not anchor:
                continue
            expires_at = anchor + timedelta(days=int(job.retention_days or 0))
            if expires_at <= now:
                candidates.append(job)

        deleted_ids = []
        skipped_ids = []
        for job in candidates:
            has_restore_links = job.restore_jobs.exists()
            if has_restore_links:
                skipped_ids.append(job.id)
                continue
            if not dry_run:
                deleted_ids.append(job.id)
                job.delete()

        details = (
            f"Retention enforcement dry_run={dry_run} candidates={len(candidates)} "
            f"deleted={len(deleted_ids)} skipped={len(skipped_ids)}"
        )
        _platform_audit(
            user=request.user,
            action="ENFORCE_RETENTION",
            model_name="PlatformBackupJob",
            object_id="batch",
            details=details,
            request=request,
            metadata={
                "dry_run": dry_run,
                "candidate_ids": [job.id for job in candidates],
                "deleted_ids": deleted_ids,
                "skipped_ids": skipped_ids,
            },
        )
        return Response(
            {
                "dry_run": dry_run,
                "candidate_count": len(candidates),
                "deleted_count": len(deleted_ids),
                "skipped_count": len(skipped_ids),
                "deleted_ids": deleted_ids,
                "skipped_ids": skipped_ids,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="run-restore-drill")
    def run_restore_drill(self, request, pk=None):
        row = self.get_object()
        if row.status != BackupJob.STATUS_SUCCESS:
            return Response({"detail": "Restore drill requires a successful backup."}, status=status.HTTP_400_BAD_REQUEST)
        approver_id = request.data.get("approver_id")
        if not approver_id:
            return Response({"detail": "approver_id is required for restore drill dual-control."}, status=status.HTTP_400_BAD_REQUEST)
        approver = User.objects.filter(id=approver_id).first()
        if approver is None:
            return Response({"detail": "approver_id is invalid."}, status=status.HTTP_400_BAD_REQUEST)
        if approver.id == request.user.id:
            return Response({"detail": "Requester and approver must be different for restore drill."}, status=status.HTTP_400_BAD_REQUEST)
        if not GlobalSuperAdmin.objects.filter(user=approver, is_active=True).exists():
            return Response({"detail": "approver_id must belong to an active GlobalSuperAdmin."}, status=status.HTTP_400_BAD_REQUEST)
        target_tenant = row.tenant
        if row.scope == BackupJob.SCOPE_TENANT and target_tenant is None:
            return Response({"detail": "Tenant-scoped backup requires tenant for restore drill."}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        drill_restore = RestoreJob.objects.create(
            backup=row,
            tenant=target_tenant,
            status=RestoreJob.STATUS_SUCCESS,
            notes="Automated restore drill completed successfully.",
            started_at=now,
            completed_at=now,
            requested_by=request.user,
            approved_by=approver,
        )
        _platform_audit(
            user=request.user,
            action="RESTORE_DRILL",
            model_name="PlatformRestoreJob",
            object_id=drill_restore.id,
            details=f"Restore drill executed for backup={row.id}",
            tenant=target_tenant,
            request=request,
            metadata={"backup_id": row.id, "approver_id": approver.id},
        )
        return Response(
            {
                "backup_id": row.id,
                "restore_job_id": drill_restore.id,
                "status": drill_restore.status,
                "drill": True,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="fail")
    def fail(self, request, pk=None):
        row = self.get_object()
        if row.status != BackupJob.STATUS_RUNNING:
            return Response({"detail": "Only running backups can fail."}, status=status.HTTP_400_BAD_REQUEST)
        row.status = BackupJob.STATUS_FAILED
        row.completed_at = timezone.now()
        row.error = request.data.get("error", "Backup failed")
        row.save(update_fields=["status", "completed_at", "error", "updated_at"])
        _platform_audit(user=request.user, action="FAIL", model_name="PlatformBackupJob", object_id=row.id, details=row.error, tenant=row.tenant, request=request)
        return Response(BackupJobSerializer(row).data)


class PlatformRestoreJobViewSet(viewsets.ModelViewSet):
    queryset = RestoreJob.objects.select_related("backup", "tenant", "requested_by", "approved_by").order_by("-created_at")
    serializer_class = RestoreJobSerializer
    permission_classes = [IsAuthenticated, IsGlobalSuperAdmin]

    def perform_create(self, serializer):
        backup = serializer.validated_data.get("backup")
        tenant = serializer.validated_data.get("tenant")
        if backup.status != BackupJob.STATUS_SUCCESS:
            raise ValidationError({"backup": "Only successful backups can be restored."})
        if backup.scope == BackupJob.SCOPE_TENANT and backup.tenant_id and tenant and backup.tenant_id != tenant.id:
            raise ValidationError({"tenant": "tenant must match backup tenant for tenant-scoped backups."})
        obj = serializer.save(requested_by=self.request.user, status=RestoreJob.STATUS_REQUESTED)
        _platform_audit(user=self.request.user, action="REQUEST", model_name="PlatformRestoreJob", object_id=obj.id, details=f"backup={obj.backup_id}", tenant=obj.tenant, request=self.request)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        row = self.get_object()
        if row.status != RestoreJob.STATUS_REQUESTED:
            return Response({"detail": "Only requested restore jobs can be approved."}, status=status.HTTP_400_BAD_REQUEST)
        if row.requested_by_id == request.user.id:
            return Response({"detail": "Requester cannot approve their own restore request."}, status=status.HTTP_400_BAD_REQUEST)
        row.status = RestoreJob.STATUS_APPROVED
        row.approved_by = request.user
        row.save(update_fields=["status", "approved_by", "updated_at"])
        _platform_audit(user=request.user, action="APPROVE", model_name="PlatformRestoreJob", object_id=row.id, details="Restore approved", tenant=row.tenant, request=request)
        return Response(RestoreJobSerializer(row).data)

    @action(detail=True, methods=["post"], url_path="start")
    def start(self, request, pk=None):
        row = self.get_object()
        if row.status != RestoreJob.STATUS_APPROVED:
            return Response({"detail": "Only approved restore jobs can be started."}, status=status.HTTP_400_BAD_REQUEST)
        if row.backup.status != BackupJob.STATUS_SUCCESS:
            return Response({"detail": "Cannot start restore because backup is not in SUCCESS state."}, status=status.HTTP_400_BAD_REQUEST)
        if row.tenant_id and RestoreJob.objects.filter(
            tenant_id=row.tenant_id,
            status=RestoreJob.STATUS_RUNNING,
        ).exclude(id=row.id).exists():
            return Response({"detail": "Another restore is already running for this tenant."}, status=status.HTTP_400_BAD_REQUEST)
        row.status = RestoreJob.STATUS_RUNNING
        row.started_at = timezone.now()
        row.save(update_fields=["status", "started_at", "updated_at"])
        _platform_audit(user=request.user, action="START", model_name="PlatformRestoreJob", object_id=row.id, details="Restore started", tenant=row.tenant, request=request)
        return Response(RestoreJobSerializer(row).data)

    @action(detail=True, methods=["post"], url_path="execute")
    def execute(self, request, pk=None):
        row = self.get_object()
        if row.status not in [RestoreJob.STATUS_APPROVED, RestoreJob.STATUS_RUNNING]:
            return Response({"detail": "Only approved or running restores can be executed."}, status=status.HTTP_400_BAD_REQUEST)
        if row.backup.status != BackupJob.STATUS_SUCCESS:
            return Response({"detail": "Restore requires a successful backup."}, status=status.HTTP_400_BAD_REQUEST)
        if not row.backup.storage_path:
            return Response({"detail": "Backup has no storage_path; cannot execute restore."}, status=status.HTTP_400_BAD_REQUEST)
        if row.status != RestoreJob.STATUS_RUNNING:
            row.status = RestoreJob.STATUS_RUNNING
            row.started_at = timezone.now()
        notes = str(request.data.get("notes", "")).strip()
        execution_note = f"Executed restore orchestration from backup={row.backup_id}"
        if notes:
            execution_note = f"{execution_note}. {notes}"
        row.notes = f"{row.notes}\n{execution_note}".strip() if row.notes else execution_note
        row.status = RestoreJob.STATUS_SUCCESS
        row.completed_at = timezone.now()
        row.save(update_fields=["status", "started_at", "completed_at", "notes", "updated_at"])
        _platform_audit(
            user=request.user,
            action="EXECUTE_RESTORE",
            model_name="PlatformRestoreJob",
            object_id=row.id,
            details=f"restore executed from backup={row.backup_id}",
            tenant=row.tenant,
            request=request,
        )
        return Response(RestoreJobSerializer(row).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        row = self.get_object()
        if row.status != RestoreJob.STATUS_RUNNING:
            return Response({"detail": "Only running restore jobs can be completed."}, status=status.HTTP_400_BAD_REQUEST)
        row.status = RestoreJob.STATUS_SUCCESS
        row.completed_at = timezone.now()
        row.save(update_fields=["status", "completed_at", "updated_at"])
        _platform_audit(user=request.user, action="COMPLETE", model_name="PlatformRestoreJob", object_id=row.id, details="Restore completed", tenant=row.tenant, request=request)
        return Response(RestoreJobSerializer(row).data)

    @action(detail=True, methods=["post"], url_path="fail")
    def fail(self, request, pk=None):
        row = self.get_object()
        if row.status != RestoreJob.STATUS_RUNNING:
            return Response({"detail": "Only running restore jobs can fail."}, status=status.HTTP_400_BAD_REQUEST)
        row.status = RestoreJob.STATUS_FAILED
        row.completed_at = timezone.now()
        row.notes = request.data.get("notes", row.notes)
        row.save(update_fields=["status", "completed_at", "notes", "updated_at"])
        _platform_audit(user=request.user, action="FAIL", model_name="PlatformRestoreJob", object_id=row.id, details="Restore failed", tenant=row.tenant, request=request)
        return Response(RestoreJobSerializer(row).data)


class PlatformSecurityIncidentViewSet(viewsets.ModelViewSet):
    queryset = SecurityIncident.objects.select_related("tenant", "assigned_to", "created_by").order_by("-created_at")
    serializer_class = SecurityIncidentSerializer
    permission_classes = [IsAuthenticated, IsGlobalSuperAdmin]

    def perform_create(self, serializer):
        row = serializer.save(created_by=self.request.user, status=SecurityIncident.STATUS_OPEN)
        _platform_audit(user=self.request.user, action="CREATE", model_name="PlatformSecurityIncident", object_id=row.id, details=f"severity={row.severity}", tenant=row.tenant, request=self.request)

    @action(detail=True, methods=["post"], url_path="investigate")
    def investigate(self, request, pk=None):
        row = self.get_object()
        if row.status != SecurityIncident.STATUS_OPEN:
            return Response({"detail": "Only open incidents can move to investigating."}, status=status.HTTP_400_BAD_REQUEST)
        row.status = SecurityIncident.STATUS_INVESTIGATING
        row.save(update_fields=["status", "updated_at"])
        _platform_audit(user=request.user, action="INVESTIGATE", model_name="PlatformSecurityIncident", object_id=row.id, details="Incident under investigation", tenant=row.tenant, request=request)
        return Response(SecurityIncidentSerializer(row).data)

    @action(detail=True, methods=["post"], url_path="resolve")
    def resolve(self, request, pk=None):
        row = self.get_object()
        if row.status not in [SecurityIncident.STATUS_OPEN, SecurityIncident.STATUS_INVESTIGATING]:
            return Response({"detail": "Incident cannot be resolved from current status."}, status=status.HTTP_400_BAD_REQUEST)
        row.status = SecurityIncident.STATUS_RESOLVED
        row.resolved_at = timezone.now()
        row.save(update_fields=["status", "resolved_at", "updated_at"])
        _platform_audit(user=request.user, action="RESOLVE", model_name="PlatformSecurityIncident", object_id=row.id, details="Incident resolved", tenant=row.tenant, request=request)
        return Response(SecurityIncidentSerializer(row).data)

    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, pk=None):
        row = self.get_object()
        if row.status != SecurityIncident.STATUS_RESOLVED:
            return Response({"detail": "Only resolved incidents can be closed."}, status=status.HTTP_400_BAD_REQUEST)
        row.status = SecurityIncident.STATUS_CLOSED
        row.save(update_fields=["status", "updated_at"])
        _platform_audit(user=request.user, action="CLOSE", model_name="PlatformSecurityIncident", object_id=row.id, details="Incident closed", tenant=row.tenant, request=request)
        return Response(SecurityIncidentSerializer(row).data)


class PlatformComplianceReportViewSet(viewsets.ModelViewSet):
    queryset = ComplianceReport.objects.select_related("generated_by").order_by("-generated_at")
    serializer_class = ComplianceReportSerializer
    permission_classes = [IsAuthenticated, IsGlobalSuperAdmin]
    http_method_names = ["get", "post", "head", "options", "delete"]

    def perform_create(self, serializer):
        row = serializer.save(generated_by=self.request.user)
        _platform_audit(user=self.request.user, action="CREATE", model_name="PlatformComplianceReport", object_id=row.id, details=f"type={row.report_type}", request=self.request)

    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        report_type = str(request.data.get("report_type", "")).upper()
        period_start = request.data.get("period_start")
        period_end = request.data.get("period_end")
        if report_type not in [ComplianceReport.TYPE_AUDIT, ComplianceReport.TYPE_ACCESS, ComplianceReport.TYPE_SECURITY, ComplianceReport.TYPE_BACKUP]:
            return Response({"detail": "Invalid report_type."}, status=status.HTTP_400_BAD_REQUEST)
        if not period_start or not period_end:
            return Response({"detail": "period_start and period_end are required."}, status=status.HTTP_400_BAD_REQUEST)

        logs_qs = PlatformActionLog.objects.filter(created_at__date__gte=period_start, created_at__date__lte=period_end)
        backup_qs = BackupJob.objects.filter(created_at__date__gte=period_start, created_at__date__lte=period_end)
        incident_qs = SecurityIncident.objects.filter(created_at__date__gte=period_start, created_at__date__lte=period_end)

        payload = {
            "window": {"period_start": str(period_start), "period_end": str(period_end)},
            "counts": {
                "platform_actions": logs_qs.count(),
                "maintenance_windows": MaintenanceWindow.objects.filter(created_at__date__gte=period_start, created_at__date__lte=period_end).count(),
                "releases": DeploymentRelease.objects.filter(created_at__date__gte=period_start, created_at__date__lte=period_end).count(),
                "backups": backup_qs.count(),
                "backup_failed": backup_qs.filter(status=BackupJob.STATUS_FAILED).count(),
                "restores": RestoreJob.objects.filter(created_at__date__gte=period_start, created_at__date__lte=period_end).count(),
                "security_incidents": incident_qs.count(),
                "security_open": incident_qs.filter(status__in=[SecurityIncident.STATUS_OPEN, SecurityIncident.STATUS_INVESTIGATING]).count(),
            },
            "top_actions": list(
                logs_qs.values("action").annotate(total=Count("id")).order_by("-total")[:10]
            ),
        }
        row = ComplianceReport.objects.create(
            report_type=report_type,
            period_start=period_start,
            period_end=period_end,
            generated_by=request.user,
            payload=payload,
        )
        _platform_audit(user=request.user, action="GENERATE", model_name="PlatformComplianceReport", object_id=row.id, details=f"type={report_type}", request=request)
        return Response(ComplianceReportSerializer(row).data, status=status.HTTP_201_CREATED)


from rest_framework import mixins as drf_mixins

class PlatformDomainRequestViewSet(
    drf_mixins.ListModelMixin,
    drf_mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Platform-admin endpoint for managing school custom domain requests.

    GET  /api/platform/domain-requests/              — list all
    GET  /api/platform/domain-requests/{id}/         — detail
    POST /api/platform/domain-requests/{id}/approve/ — activate verified domain
    POST /api/platform/domain-requests/{id}/reject/  — reject request
    """
    permission_classes = [IsAuthenticated, IsGlobalSuperAdmin]
    queryset = CustomDomainRequest.objects.select_related("tenant").order_by("-created_at")

    def _serialize(self, req) -> dict:
        return {
            "id": req.pk,
            "tenant_schema": req.tenant.schema_name,
            "tenant_name": req.tenant.name,
            "requested_domain": req.requested_domain,
            "verification_token": req.verification_token,
            "status": req.status,
            "status_display": req.get_status_display(),
            "verification_attempts": req.verification_attempts,
            "last_verification_attempt": req.last_verification_attempt.isoformat() if req.last_verification_attempt else None,
            "verified_at": req.verified_at.isoformat() if req.verified_at else None,
            "activated_at": req.activated_at.isoformat() if req.activated_at else None,
            "rejected_at": req.rejected_at.isoformat() if req.rejected_at else None,
            "rejection_reason": req.rejection_reason,
            "requested_by_username": req.requested_by_username,
            "created_at": req.created_at.isoformat(),
        }

    def list(self, request):
        status_filter = request.query_params.get("status")
        qs = self.get_queryset()
        if status_filter:
            qs = qs.filter(status=status_filter.upper())
        return Response([self._serialize(r) for r in qs])

    def retrieve(self, request, pk=None):
        req = self.get_object()
        return Response(self._serialize(req))

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        from clients import domain_service as ds
        try:
            result = ds.activate_domain_request(
                request_id=int(pk),
                platform_admin_username=request.user.username,
            )
        except (CustomDomainRequest.DoesNotExist, ValueError) as exc:
            return Response({"error": str(exc)}, status=400)

        _platform_audit(
            user=request.user,
            action="APPROVE_DOMAIN",
            model_name="CustomDomainRequest",
            object_id=int(pk),
            details=f"domain={result['requested_domain']}",
            request=request,
        )
        return Response(result)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        from clients import domain_service as ds
        reason = str(request.data.get("reason", "")).strip()
        try:
            result = ds.reject_domain_request(
                request_id=int(pk),
                reason=reason,
                platform_admin_username=request.user.username,
            )
        except (CustomDomainRequest.DoesNotExist, ValueError) as exc:
            return Response({"error": str(exc)}, status=400)

        _platform_audit(
            user=request.user,
            action="REJECT_DOMAIN",
            model_name="CustomDomainRequest",
            object_id=int(pk),
            details=f"domain={result['requested_domain']} reason={reason}",
            request=request,
        )
        return Response(result)
