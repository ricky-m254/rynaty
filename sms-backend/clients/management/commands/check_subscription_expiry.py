"""
check_subscription_expiry â€” Platform tenant billing expiry cron

Runs on a schedule to suspend tenant accounts whose active subscription has
passed its due date or paid-through date.

The command is idempotent and safe to run manually.  It uses a DB-backed lock
in PlatformSetting so multiple workers do not suspend the same tenants twice.
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django_tenants.utils import get_public_schema_name, schema_context

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Suspend tenants whose subscription payment is overdue"

    _LOCK_KEY = "SUBSCRIPTION_EXPIRY_LOCK"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would happen without making changes",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Bypass the concurrency lock (use only for testing)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]

        if dry_run:
            self.stdout.write("âš   DRY RUN â€” no changes will be made.\n")

        with schema_context(get_public_schema_name()):
            if not dry_run and not force and not self._acquire_lock():
                self.stdout.write("âš   Another instance is already running. Use --force to override.\n")
                return

            try:
                self._run(dry_run=dry_run)
            finally:
                if not dry_run and not force:
                    self._release_lock()

    def _run(self, *, dry_run: bool) -> None:
        from clients.models import PlatformActionLog, PlatformSetting, SubscriptionInvoice, Tenant, TenantSubscription
        from clients.platform_email import platform_email

        now = timezone.now()
        today = now.date()

        active_tenants = list(
            Tenant.objects.filter(status=Tenant.STATUS_ACTIVE, is_active=True).order_by("name")
        )

        overdue_rows = []
        for tenant in active_tenants:
            current_subscription = tenant.subscriptions.filter(is_current=True).order_by("-created_at").first()
            latest_unpaid_invoice = None
            if current_subscription:
                latest_unpaid_invoice = (
                    current_subscription.invoices.filter(
                        status__in=[SubscriptionInvoice.STATUS_PENDING, SubscriptionInvoice.STATUS_OVERDUE]
                    )
                    .order_by("-due_date", "-issued_at")
                    .first()
                )
            if latest_unpaid_invoice is None:
                latest_unpaid_invoice = (
                    tenant.subscription_invoices.filter(
                        status__in=[SubscriptionInvoice.STATUS_PENDING, SubscriptionInvoice.STATUS_OVERDUE]
                    )
                    .order_by("-due_date", "-issued_at")
                    .first()
                )

            effective_end = tenant.paid_until or (current_subscription.ends_on if current_subscription else None)
            invoice_overdue = bool(latest_unpaid_invoice and latest_unpaid_invoice.due_date and latest_unpaid_invoice.due_date < today)
            paid_until_expired = bool(effective_end and effective_end < today)

            if invoice_overdue or paid_until_expired:
                overdue_rows.append((tenant, current_subscription, latest_unpaid_invoice))

        self.stdout.write(f"  Active tenants scanned        : {len(active_tenants)}")
        self.stdout.write(f"  Tenants to suspend            : {len(overdue_rows)}")

        suspended = 0
        for tenant, current_subscription, invoice in overdue_rows:
            reason = "Subscription expired"
            if invoice:
                reason = f"Subscription overdue: invoice {invoice.invoice_number} is past due"
            self.stdout.write(f"  â†’ SUSPEND [{tenant.schema_name}] ({reason})")

            if dry_run:
                continue

            try:
                tenant.status = Tenant.STATUS_SUSPENDED
                tenant.is_active = False
                tenant.suspended_at = now
                tenant.suspension_reason = reason
                tenant.save(update_fields=["status", "is_active", "suspended_at", "suspension_reason", "updated_at"])

                if current_subscription and current_subscription.status != TenantSubscription.STATUS_SUSPENDED:
                    current_subscription.status = TenantSubscription.STATUS_SUSPENDED
                    current_subscription.save(update_fields=["status", "updated_at"])

                PlatformActionLog.objects.create(
                    actor=None,
                    tenant=tenant,
                    action="SUSPEND",
                    model_name="Tenant",
                    object_id=str(tenant.id),
                    details=reason,
                    metadata={
                        "reason": reason,
                        "invoice_id": invoice.id if invoice else None,
                        "subscription_id": current_subscription.id if current_subscription else None,
                    },
                )

                platform_email.suspension(tenant, reason=reason)
                suspended += 1
            except Exception as exc:
                logger.error("[check_subscription_expiry] Failed to suspend %s: %s", tenant.schema_name, exc)

        if dry_run:
            self.stdout.write(f"\n  Dry run complete. Would suspend: {len(overdue_rows)}")
        else:
            self.stdout.write(f"\n  Done. Suspended: {suspended}")

    def _acquire_lock(self) -> bool:
        from clients.models import PlatformSetting
        from django.db import transaction

        try:
            with transaction.atomic():
                obj, created = PlatformSetting.objects.get_or_create(
                    key=self._LOCK_KEY,
                    defaults={"value": "0", "description": "Concurrency lock for check_subscription_expiry"},
                )
                if not created and obj.value == "1":
                    return False
                obj.value = "1"
                obj.save(update_fields=["value"])
            return True
        except Exception as exc:
            logger.warning("[check_subscription_expiry] Could not acquire lock: %s â€” proceeding anyway", exc)
            return True

    def _release_lock(self) -> None:
        from clients.models import PlatformSetting

        try:
            PlatformSetting.objects.filter(key=self._LOCK_KEY).update(value="0")
        except Exception as exc:
            logger.warning("[check_subscription_expiry] Could not release lock: %s", exc)
