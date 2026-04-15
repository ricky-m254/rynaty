"""
Idempotent management command to ensure the Olom tenant exists with its
production domain (olom.rynatyschool.app).

Strategy (in order):
  1. If any tenant already owns olom.rynatyschool.app → just refresh the admin.
  2. If schema_name='olom' exists → register the domain + refresh admin.
  3. If any non-demo tenant whose schema contains "olom" exists → register domain + admin.
  4. Create a fresh 'olom' tenant (first startup, dev).

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
_DEMO_SCHEMA = os.environ.get("DEMO_SCHEMA_NAME", "demo_school")


class Command(BaseCommand):
    help = "Ensure the olom tenant exists with the correct production domain (idempotent)"

    def handle(self, *args, **options):
        public = get_public_schema_name()

        with schema_context(public):
            from clients.models import Tenant, Domain, TenantSubscription, SubscriptionPlan

            tenant = self._resolve_tenant(Domain, Tenant)
            if tenant is None:
                self.stdout.write("  [olom] Could not resolve or create tenant — skipping.")
                return

            # ── Ensure subdomain slug is set on the tenant ────────────────────
            # This enables X-Tenant-ID: olom header lookups regardless of
            # what the schema_name was auto-generated as (e.g. schema could
            # be 'school_olomrynatyschoolapp' but user types 'olom').
            if not getattr(tenant, "subdomain", None):
                try:
                    tenant.subdomain = "olom"
                    tenant.save(update_fields=["subdomain"])
                    self.stdout.write("  [olom] Set subdomain='olom' on tenant")
                except Exception as e:
                    self.stdout.write(f"  [olom] Could not set subdomain: {e}")

            # ── Ensure olom.rynatyschool.app is registered ────────────────────
            domain_obj, domain_created = Domain.objects.get_or_create(
                domain=_DOMAIN,
                defaults={"tenant": tenant, "is_primary": True},
            )
            if not domain_created and domain_obj.tenant_id != tenant.pk:
                domain_obj.tenant = tenant
                domain_obj.is_primary = True
                domain_obj.save(update_fields=["tenant", "is_primary"])
                self.stdout.write(f"  [olom] Reassigned {_DOMAIN} to tenant '{tenant.schema_name}'")
            elif domain_created:
                self.stdout.write(f"  [olom] Domain {_DOMAIN} registered for '{tenant.schema_name}'")
            else:
                self.stdout.write(f"  [olom] Domain {_DOMAIN} already registered for '{tenant.schema_name}'")

            # ── Ensure a trial subscription exists ────────────────────────────
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
                self.stdout.write(f"  [olom] Subscription upsert skipped: {e}")

        # ── Seed admin user INSIDE the resolved schema ─────────────────────────
        self._seed_admin(tenant.schema_name)
        self.stdout.write("  [olom] Done.")

    # ──────────────────────────────────────────────────────────────────────────
    def _resolve_tenant(self, Domain, Tenant):
        """
        Find an appropriate tenant to own olom.rynatyschool.app.
        Returns a Tenant instance or None.
        """
        # 1. Is the domain already registered for a real (non-demo) tenant?
        existing = Domain.objects.filter(domain=_DOMAIN).select_related("tenant").first()
        if existing:
            if existing.tenant.schema_name not in (_DEMO_SCHEMA, get_public_schema_name()):
                self.stdout.write(
                    f"  [olom] Domain already owned by tenant '{existing.tenant.schema_name}'"
                )
                return existing.tenant
            else:
                # Domain is wrongly parked on demo_school or public — will reassign
                self.stdout.write(
                    f"  [olom] Domain wrongly assigned to '{existing.tenant.schema_name}' "
                    f"— will reassign to correct tenant"
                )

        # 2. Does the 'olom' schema tenant record exist?
        olom_tenant = Tenant.objects.filter(schema_name=_SCHEMA).first()
        if olom_tenant:
            self.stdout.write("  [olom] Found existing 'olom' schema tenant")
            return olom_tenant

        # 3. Any non-demo tenant whose schema_name contains "olom"?
        _pub = get_public_schema_name()
        candidate = (
            Tenant.objects
            .exclude(schema_name=_DEMO_SCHEMA)
            .exclude(schema_name=_pub)
            .filter(schema_name__icontains="olom")
            .order_by("pk")
            .first()
        )
        if candidate:
            self.stdout.write(
                f"  [olom] Using existing tenant '{candidate.schema_name}' "
                f"(schema contains 'olom')"
            )
            return candidate

        # 4. Create a fresh tenant (dev / first production startup)
        self.stdout.write("  [olom] Creating new tenant with schema 'olom'…")
        try:
            tenant = Tenant.objects.create(
                schema_name=_SCHEMA,
                name=_NAME,
                status="TRIAL",
                contact_email=_ADMIN_EMAIL,
                is_active=True,
                auto_create_schema=True,
            )
            self.stdout.write("  [olom] Tenant + schema created.")
            return tenant
        except Exception as e:
            self.stdout.write(f"  [olom] Schema creation failed: {e}")
            return None

    def _seed_admin(self, schema_name):
        """Create / refresh the olom_admin user inside the given tenant schema."""
        with schema_context(schema_name):
            from django.contrib.auth.models import User

            admin_user, created = User.objects.get_or_create(
                username=_ADMIN_USER,
                defaults={
                    "email": _ADMIN_EMAIL,
                    "first_name": "Olom",
                    "last_name": "Admin",
                    "is_staff": True,
                    "is_superuser": False,
                    "is_active": True,
                },
            )
            admin_user.is_active = True
            admin_user.is_staff = True
            admin_user.is_superuser = False   # never grant Django superuser to a school admin
            admin_user.set_password(_ADMIN_PASS)
            admin_user.save()

            if created:
                self.stdout.write(f"  [olom] Admin user '{_ADMIN_USER}' created")
            else:
                self.stdout.write(f"  [olom] Admin user '{_ADMIN_USER}' password refreshed")

            # ── Assign TENANT_SUPER_ADMIN role via FK (not string) ─────────────
            # UserProfile.role is a ForeignKey(Role). If Role objects haven't been
            # seeded yet (first startup), we create the TENANT_SUPER_ADMIN role now;
            # the full seed_default_permissions pass will fill in the rest later.
            try:
                from school.models import UserProfile, Role
                role_obj, role_created = Role.objects.get_or_create(
                    name="TENANT_SUPER_ADMIN",
                    defaults={"description": "Tenant Super Admin"},
                )
                if role_created:
                    self.stdout.write("  [olom] Created TENANT_SUPER_ADMIN Role record")

                profile, profile_created = UserProfile.objects.get_or_create(
                    user=admin_user,
                    defaults={"role": role_obj},
                )
                if not profile_created and profile.role_id != role_obj.pk:
                    profile.role = role_obj
                    profile.save(update_fields=["role"])
                    self.stdout.write("  [olom] Updated olom_admin UserProfile role to TENANT_SUPER_ADMIN")
                else:
                    action = "Created" if profile_created else "Already correct"
                    self.stdout.write(f"  [olom] UserProfile role: {action} (TENANT_SUPER_ADMIN)")
            except Exception as exc:
                self.stdout.write(f"  [olom] WARNING: Could not assign UserProfile role: {exc}")



