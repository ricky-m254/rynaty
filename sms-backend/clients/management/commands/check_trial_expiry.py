"""
check_trial_expiry — Spec §6.3: Trial Expiry Cron

Runs automatically on a schedule (daily at 2 AM UTC recommended).
Safe to run manually at any time — idempotent.

Actions performed:
  1. Suspend all tenants whose trial_end <= today (status = TRIAL only).
  2. Send trial_expired email to each.
  3. Send trial_warning email (7 days notice) to trials expiring soon.

Spec compliance:
  • Uses a DB-level flag (PlatformSetting "TRIAL_EXPIRY_LOCK") to prevent
    double-execution on deployments with multiple workers (equivalent to
    the Redis nx=True lock in the FastAPI spec §6.3).
  • Audit log written for every suspension.
  • Email failures are logged but never abort the process.

Usage:
    python manage.py check_trial_expiry
    python manage.py check_trial_expiry --dry-run    # report only, no writes
    python manage.py check_trial_expiry --warn-days 3   # warn 3 days before
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django_tenants.utils import get_public_schema_name, schema_context

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Suspend expired trials and send warning emails (spec §6.3)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would happen without making changes",
        )
        parser.add_argument(
            "--warn-days",
            type=int,
            default=7,
            help="Send warning email N days before trial ends (default: 7)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Bypass the concurrency lock (use only for testing)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        warn_days = options["warn_days"]
        force = options["force"]

        if dry_run:
            self.stdout.write("⚠  DRY RUN — no changes will be made.\n")

        with schema_context(get_public_schema_name()):
            if not dry_run and not force:
                if not self._acquire_lock():
                    self.stdout.write(
                        "⚠  Another instance is already running. "
                        "Use --force to override.\n"
                    )
                    return

            try:
                self._run(dry_run=dry_run, warn_days=warn_days)
            finally:
                if not dry_run and not force:
                    self._release_lock()

    # ── Main logic ────────────────────────────────────────────────────────────

    def _run(self, *, dry_run: bool, warn_days: int) -> None:
        from clients.models import Tenant, PlatformSetting, PlatformActionLog
        from clients.platform_email import platform_email

        now   = timezone.now()
        today = now.date()
        warn_cutoff = today + timedelta(days=warn_days)

        # 1. Tenants to SUSPEND (trial_end has passed)
        expired = list(
            Tenant.objects.filter(
                status=Tenant.STATUS_TRIAL,
                trial_end__isnull=False,
                trial_end__lte=today,
                is_active=True,
            ).order_by("trial_end")
        )

        # 2. Tenants to WARN (trial_end is within warn_days)
        expiring_soon = list(
            Tenant.objects.filter(
                status=Tenant.STATUS_TRIAL,
                trial_end__isnull=False,
                trial_end__gt=today,
                trial_end__lte=warn_cutoff,
                is_active=True,
            ).order_by("trial_end")
        )

        self.stdout.write(f"  Expired trials to suspend : {len(expired)}")
        self.stdout.write(f"  Trials expiring in {warn_days} days: {len(expiring_soon)}")

        # ── Suspend expired trials ────────────────────────────────────────────
        suspended = 0
        for tenant in expired:
            self.stdout.write(
                f"  → SUSPEND [{tenant.schema_name}] "
                f"(trial ended {tenant.trial_end})"
            )
            if dry_run:
                continue

            try:
                tenant.status = Tenant.STATUS_SUSPENDED
                tenant.is_active = False
                tenant.suspended_at = now
                tenant.suspension_reason = "Trial period ended"
                tenant.save(update_fields=[
                    "status", "is_active", "suspended_at",
                    "suspension_reason", "updated_at",
                ])

                PlatformActionLog.objects.create(
                    actor_role="SYSTEM",
                    action="SUSPEND",
                    model_name="Tenant",
                    object_id=tenant.id,
                    details=f"Auto-suspended: trial ended {tenant.trial_end}",
                    tenant=tenant,
                )

                platform_email.trial_expired(tenant)
                suspended += 1
            except Exception as exc:
                logger.error(
                    "[check_trial_expiry] Failed to suspend %s: %s",
                    tenant.schema_name, exc,
                )

        # ── Send warning emails ───────────────────────────────────────────────
        warned = 0
        for tenant in expiring_soon:
            days_left = (tenant.trial_end - today).days
            self.stdout.write(
                f"  → WARN [{tenant.schema_name}] "
                f"({days_left} day{'s' if days_left != 1 else ''} left)"
            )
            if dry_run:
                continue

            try:
                platform_email.trial_warning(tenant, days_left=days_left)
                warned += 1
            except Exception as exc:
                logger.error(
                    "[check_trial_expiry] Failed to warn %s: %s",
                    tenant.schema_name, exc,
                )

        if not dry_run:
            self.stdout.write(
                f"\n  Done. Suspended: {suspended}, Warned: {warned}"
            )
        else:
            self.stdout.write(
                f"\n  Dry run complete. Would suspend: {len(expired)}, "
                f"Would warn: {len(expiring_soon)}"
            )

    # ── Concurrency lock (DB-backed, spec §6.3 equivalent) ───────────────────

    _LOCK_KEY = "TRIAL_EXPIRY_LOCK"

    def _acquire_lock(self) -> bool:
        from clients.models import PlatformSetting
        from django.db import transaction

        try:
            with transaction.atomic():
                obj, created = PlatformSetting.objects.get_or_create(
                    key=self._LOCK_KEY,
                    defaults={"value": "0", "description": "Concurrency lock for check_trial_expiry"},
                )
                if not created and obj.value == "1":
                    return False
                obj.value = "1"
                obj.save(update_fields=["value"])
            return True
        except Exception as exc:
            logger.warning("[check_trial_expiry] Could not acquire lock: %s — proceeding anyway", exc)
            return True

    def _release_lock(self) -> None:
        from clients.models import PlatformSetting

        try:
            PlatformSetting.objects.filter(key=self._LOCK_KEY).update(value="0")
        except Exception as exc:
            logger.warning("[check_trial_expiry] Could not release lock: %s", exc)
