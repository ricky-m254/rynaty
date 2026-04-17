"""
Idempotent management command to seed platform-level demo data.
Runs in the PUBLIC schema context.  Safe to re-run at every startup.

Platform admin password resolution order:
  1. PLATFORM_ADMIN_PASSWORD environment variable (recommended for production)
  2. Hard-coded fallback: PlatformAdmin#2025

Set PLATFORM_ADMIN_PASSWORD in the deployment environment to use a custom
password.  The resolved username + password source are printed at startup so
operators can confirm credentials without reading source code.
"""
import os
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context, get_public_schema_name

_DEFAULT_PLATFORM_PASSWORD = "PlatformAdmin#2025"


class Command(BaseCommand):
    help = "Seed platform super-admin user + demo data for all platform tabs (idempotent)"

    def handle(self, *args, **options):
        public = get_public_schema_name()
        schema = "demo_school"

        # Resolve the platform admin password from the environment or fall back
        # to the hardcoded default.  Log clearly so operators know which is active.
        env_password = os.environ.get("PLATFORM_ADMIN_PASSWORD", "").strip()
        if env_password:
            PLATFORM_ADMIN_PASSWORD = env_password
            pwd_source = "env var PLATFORM_ADMIN_PASSWORD"
        else:
            PLATFORM_ADMIN_PASSWORD = _DEFAULT_PLATFORM_PASSWORD
            pwd_source = "default (set PLATFORM_ADMIN_PASSWORD env var to override)"

        with schema_context(public):
            from django.contrib.auth.models import User
            from clients.models import (
                GlobalSuperAdmin,
                Tenant,
                TenantSubscription,
                SubscriptionPlan,
                SupportTicket,
                DeploymentRelease,
                BackupJob,
                MonitoringSnapshot,
                FeatureFlag,
                SecurityIncident,
                SubscriptionInvoice,
                PlatformSetting,
            )
            from django.utils import timezone

            # ── 1. Platform super-admin user ────────────────────────────────
            platform_admin, created = User.objects.get_or_create(
                username="platform_admin",
                defaults={
                    "email": "platform@rynatyschool.com",
                    "is_staff": True,
                    "is_superuser": True,
                    "is_active": True,
                },
            )
            needs_save = created
            if created:
                platform_admin.set_password(PLATFORM_ADMIN_PASSWORD)
                self.stdout.write("  [platform_admin] Created public-schema user")
            else:
                # Always enforce: account must be active, is_staff, is_superuser
                if not platform_admin.is_active:
                    platform_admin.is_active = True
                    needs_save = True
                if not platform_admin.is_staff:
                    platform_admin.is_staff = True
                    needs_save = True
                if not platform_admin.is_superuser:
                    platform_admin.is_superuser = True
                    needs_save = True
                # Enforce correct password — if it was scrambled, restore it
                if not platform_admin.check_password(PLATFORM_ADMIN_PASSWORD):
                    platform_admin.set_password(PLATFORM_ADMIN_PASSWORD)
                    needs_save = True
                    self.stdout.write("  [platform_admin] Password re-enforced")
            if needs_save:
                platform_admin.save()

            # Always print the credential summary so operators can confirm
            # login details without digging through source code.
            self.stdout.write(
                f"  [platform_admin] username=platform_admin  password-source={pwd_source}"
            )

            gsa, gsa_created = GlobalSuperAdmin.objects.get_or_create(
                user=platform_admin,
                defaults={"role": "OWNER", "is_active": True},
            )
            if not gsa_created and (gsa.role != "OWNER" or not gsa.is_active):
                gsa.role = "OWNER"
                gsa.is_active = True
                gsa.save()
                self.stdout.write("  [platform_admin] GSA record corrected")

            # ── 2. Subscription + invoice for demo tenant ───────────────────
            try:
                tenant = Tenant.objects.get(schema_name=schema)
            except Tenant.DoesNotExist:
                self.stdout.write(f"  [platform seed] {schema} not found — skipping tenant data")
                return

            plan = (
                SubscriptionPlan.objects.filter(name="Professional").first()
                or SubscriptionPlan.objects.first()
            )

            if plan and not TenantSubscription.objects.filter(tenant=tenant, is_current=True).exists():
                today = date.today()
                sub = TenantSubscription.objects.create(
                    tenant=tenant,
                    plan=plan,
                    billing_cycle="MONTHLY",
                    status="ACTIVE",
                    starts_on=today - timedelta(days=90),
                    next_billing_date=today + timedelta(days=30),
                    grace_period_days=7,
                    is_current=True,
                )
                if not SubscriptionInvoice.objects.filter(tenant=tenant).exists():
                    price = plan.monthly_price or Decimal("0")
                    p_start = today - timedelta(days=90)
                    p_end = today - timedelta(days=60)
                    SubscriptionInvoice.objects.create(
                        tenant=tenant,
                        subscription=sub,
                        invoice_number="INV-2025-0001",
                        billing_cycle="MONTHLY",
                        amount=price,
                        tax_amount=Decimal("0"),
                        discount_amount=Decimal("0"),
                        total_amount=price,
                        period_start=p_start,
                        period_end=p_end,
                        status="PAID",
                        due_date=p_end + timedelta(days=7),
                        paid_at=timezone.now() - timedelta(days=55),
                    )
                self.stdout.write(f"  [platform seed] Created subscription + invoice ({plan.name})")

            # ── 3. Support tickets ──────────────────────────────────────────
            if SupportTicket.objects.count() == 0:
                for i, (subj, pri, sts) in enumerate([
                    ("Login page shows blank screen", "HIGH", "OPEN"),
                    ("Report generation too slow", "MEDIUM", "IN_PROGRESS"),
                    ("Fee balance not updating after payment", "HIGH", "OPEN"),
                    ("Cannot upload student photos", "LOW", "RESOLVED"),
                    ("Timetable export to PDF broken", "MEDIUM", "CLOSED"),
                ]):
                    SupportTicket.objects.create(
                        ticket_number=f"TKT-{2025000 + i + 1}",
                        tenant=tenant,
                        subject=subj,
                        description=f"Demo ticket: {subj}",
                        priority=pri,
                        status=sts,
                        created_by_email="admin@demo.co.ke",
                    )
                self.stdout.write(f"  [platform seed] Created {SupportTicket.objects.count()} support tickets")

            # ── 4. Deployment releases ──────────────────────────────────────
            if DeploymentRelease.objects.count() == 0:
                for ver, notes, sts in [
                    ("2.4.1", "Parent portal + CBE grade fixes", "DEPLOYED"),
                    ("2.4.0", "KICD textbook e-learning integration", "DEPLOYED"),
                    ("2.3.5", "Fee management multi-currency support", "DEPLOYED"),
                    ("2.5.0", "Biometric clock-in + mobile sync", "PLANNED"),
                ]:
                    DeploymentRelease.objects.create(
                        version=ver,
                        notes=notes,
                        status=sts,
                        created_by=platform_admin,
                        completed_at=timezone.now() - timedelta(days=30) if sts == "DEPLOYED" else None,
                        started_at=timezone.now() - timedelta(days=31) if sts == "DEPLOYED" else None,
                    )
                self.stdout.write(f"  [platform seed] Created {DeploymentRelease.objects.count()} releases")

            # ── 5. Feature flags ────────────────────────────────────────────
            if FeatureFlag.objects.count() == 0:
                for key, desc, enabled in [
                    ("ai_grade_predictions", "AI-powered grade predictions", True),
                    ("mobile_push_notifications", "Push notifications for mobile app", True),
                    ("parent_chat", "Real-time chat in parent portal", False),
                    ("advanced_analytics", "Advanced cross-tenant analytics", True),
                    ("biometric_integration", "Biometric device clock-in", False),
                ]:
                    FeatureFlag.objects.create(key=key, description=desc, is_enabled=enabled)
                self.stdout.write(f"  [platform seed] Created {FeatureFlag.objects.count()} feature flags")

            # ── 6. Backup jobs ──────────────────────────────────────────────
            if BackupJob.objects.count() == 0:
                for btype, sts in [
                    ("FULL", "SUCCESS"), ("INCREMENTAL", "SUCCESS"),
                    ("FULL", "SUCCESS"), ("FULL", "SUCCESS"),
                    ("INCREMENTAL", "RUNNING"),
                ]:
                    BackupJob.objects.create(
                        scope="TENANT",
                        tenant=tenant,
                        backup_type=btype,
                        status=sts,
                        created_by=platform_admin,
                        started_at=timezone.now() - timedelta(hours=11),
                        completed_at=timezone.now() - timedelta(hours=10) if sts == "SUCCESS" else None,
                        size_bytes=1024 * 1024 * 450 if sts == "SUCCESS" else 0,
                        storage_path=f"backups/demo/{btype.lower()}.tar.gz" if sts == "SUCCESS" else "",
                    )
                self.stdout.write(f"  [platform seed] Created {BackupJob.objects.count()} backup jobs")

            # ── 7. Monitoring snapshots ─────────────────────────────────────
            if MonitoringSnapshot.objects.count() == 0:
                for i in range(8):
                    for metric, val in [
                        ("cpu_usage_pct", 30 + i * 5),
                        ("memory_usage_pct", 45 + i * 3),
                        ("api_response_avg_ms", 120 + i * 15),
                    ]:
                        MonitoringSnapshot.objects.create(
                            tenant=tenant,
                            metric_key=metric,
                            value=Decimal(str(val)),
                            payload={"raw": val},
                            captured_at=timezone.now() - timedelta(hours=i * 2),
                        )
                self.stdout.write(
                    f"  [platform seed] Created {MonitoringSnapshot.objects.count()} monitoring snapshots"
                )

            # ── 8. Security incident ────────────────────────────────────────
            if SecurityIncident.objects.count() == 0:
                SecurityIncident.objects.create(
                    tenant=tenant,
                    severity="LOW",
                    title="Multiple failed login attempts",
                    details="5 failed attempts from IP 41.89.12.45 at 03:14 UTC",
                    status="RESOLVED",
                    created_by=platform_admin,
                    resolved_at=timezone.now() - timedelta(days=2),
                )
                self.stdout.write("  [platform seed] Created security incident")

            # ── 9. Platform settings ────────────────────────────────────────
            for key, val, desc in [
                ("PLATFORM_NAME", "RynatySchool SmartCampus", "Platform display name"),
                ("MAX_TRIAL_DAYS", "30", "Default trial duration in days"),
                ("DEFAULT_GRACE_PERIOD_DAYS", "7", "Days after invoice due before suspension"),
                ("SUPPORT_EMAIL", "support@rynatyschool.com", "Platform support contact"),
                ("MAINTENANCE_MODE", "false", "Platform-wide maintenance mode"),
            ]:
                PlatformSetting.objects.get_or_create(
                    key=key, defaults={"value": val, "description": desc}
                )

            self.stdout.write(self.style.SUCCESS("[seed_platform_data] Done."))
