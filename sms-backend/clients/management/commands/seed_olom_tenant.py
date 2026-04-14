"""
Idempotent management command to ensure the Olom tenant exists with its
production domain (olom.rynatyschool.app).

Safe to re-run at every startup — all operations are get_or_create / update.
"""
import os

from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context, get_public_schema_name


_SCHEMA = "olom"
_NAME = "Olom School"
_DOMAIN = "olom.rynatyschool.app"
_ADMIN_USER = "olom_admin"
_ADMIN_PASS = "OlomAdmin#2025!"
_ADMIN_EMAIL = "admin@olom.rynatyschool.app"


class Command(BaseCommand):
    help = "Ensure the olom tenant exists with the correct production domain (idempotent)"

    def handle(self, *args, **options):
        public = get_public_schema_name()

        with schema_context(public):
            from clients.models import Tenant, Domain, TenantSubscription, SubscriptionPlan

            # ── 1. Ensure the Tenant record exists ────────────────────────────
            tenant, tenant_created = Tenant.objects.get_or_create(
                schema_name=_SCHEMA,
                defaults={
                    "name": _NAME,
                    "status": "TRIAL",
                    "contact_email": _ADMIN_EMAIL,
                    "is_active": True,
                    "auto_create_schema": True,
                },
            )
            if tenant_created:
                self.stdout.write(f"  [olom] Tenant created (schema provisioning triggered)")
            else:
                self.stdout.write(f"  [olom] Tenant already exists — skipping creation")

            # ── 2. Ensure the primary domain is registered ────────────────────
            domain_obj, domain_created = Domain.objects.get_or_create(
                domain=_DOMAIN,
                defaults={"tenant": tenant, "is_primary": True},
            )
            if not domain_created and domain_obj.tenant_id != tenant.pk:
                domain_obj.tenant = tenant
                domain_obj.is_primary = True
                domain_obj.save(update_fields=["tenant", "is_primary"])
                self.stdout.write(f"  [olom] Reassigned {_DOMAIN} to olom tenant")
            elif domain_created:
                self.stdout.write(f"  [olom] Domain {_DOMAIN} registered")
            else:
                self.stdout.write(f"  [olom] Domain {_DOMAIN} already registered")

            # ── 3. Ensure a subscription exists ───────────────────────────────
            try:
                from django.utils import timezone
                from datetime import timedelta
                plan = SubscriptionPlan.objects.filter(is_active=True).first()
                if plan:
                    TenantSubscription.objects.get_or_create(
                        tenant=tenant,
                        defaults={
                            "plan": plan,
                            "status": "TRIAL",
                            "starts_on": timezone.now().date(),
                            "trial_end": timezone.now().date() + timedelta(days=14),
                        },
                    )
            except Exception as e:
                self.stdout.write(f"  [olom] Subscription creation skipped: {e}")

        # ── 4. Seed admin user INSIDE the olom schema ─────────────────────────
        with schema_context(_SCHEMA):
            from django.contrib.auth.models import User
            try:
                from school.models import Staff
                has_staff = True
            except Exception:
                has_staff = False

            admin_user, admin_created = User.objects.get_or_create(
                username=_ADMIN_USER,
                defaults={
                    "email": _ADMIN_EMAIL,
                    "first_name": "Olom",
                    "last_name": "Admin",
                    "is_staff": True,
                    "is_active": True,
                },
            )
            needs_save = admin_created
            if admin_created:
                admin_user.set_password(_ADMIN_PASS)
                self.stdout.write(f"  [olom] Admin user '{_ADMIN_USER}' created")
            else:
                if not admin_user.is_active:
                    admin_user.is_active = True
                    needs_save = True
                if not admin_user.is_staff:
                    admin_user.is_staff = True
                    needs_save = True
                # Always re-enforce the known-good password
                admin_user.set_password(_ADMIN_PASS)
                needs_save = True
                self.stdout.write(f"  [olom] Admin user '{_ADMIN_USER}' password refreshed")
            if needs_save:
                admin_user.save()

            # Assign TENANT_SUPER_ADMIN role if the profile model is present
            try:
                from school.models import UserProfile
                profile, _ = UserProfile.objects.get_or_create(
                    user=admin_user,
                    defaults={"role": "TENANT_SUPER_ADMIN"},
                )
                if profile.role != "TENANT_SUPER_ADMIN":
                    profile.role = "TENANT_SUPER_ADMIN"
                    profile.save(update_fields=["role"])
            except Exception:
                pass

        self.stdout.write("  [olom] Done.")
