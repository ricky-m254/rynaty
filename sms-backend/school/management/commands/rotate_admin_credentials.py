"""
Idempotent management command to neutralise the insecure admin/admin123
tenant account. Rather than hard-deleting (which breaks FK constraints),
we deactivate it and scramble its password to an unguessable random string.
Runs unconditionally at every startup via start.sh.
"""
import logging
import secrets

from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)

SCHEMA       = "demo_school"
OLD_USERNAME = "admin"
NEW_USERNAME = "Riqs#."
NEW_PASSWORD = "Ointment.54.#"
NEW_EMAIL    = "emurithi593@gmail.com"


class Command(BaseCommand):
    help = "Neutralise insecure admin/admin123 and enforce secure credentials (idempotent)"

    def handle(self, *args, **options):
        with schema_context(SCHEMA):
            from django.contrib.auth.models import User

            # ── Step 1: Neutralise every variant of the old insecure account ─
            # We deactivate + scramble password instead of deleting so FK
            # constraints (library, auditlog, etc.) are never violated.
            for old_name in [OLD_USERNAME, "Admin", "admin123", "ADMIN"]:
                try:
                    old = User.objects.get(username=old_name)
                    old.is_active = False
                    old.set_password(secrets.token_hex(32))   # unguessable
                    old.save()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"[rotate] Neutralised '{old_name}' — deactivated + password scrambled"
                        )
                    )
                except User.DoesNotExist:
                    pass
                except Exception as exc:
                    self.stdout.write(f"[rotate] Warning neutralising '{old_name}': {exc}")

            # ── Step 2: Ensure the secure account exists with correct creds ──
            u, created = User.objects.get_or_create(
                username=NEW_USERNAME,
                defaults={
                    "email": NEW_EMAIL,
                    "is_staff": True,
                    "is_superuser": True,
                    "is_active": True,
                },
            )
            changed = created
            if not u.check_password(NEW_PASSWORD):
                u.set_password(NEW_PASSWORD)
                changed = True
            if u.email != NEW_EMAIL:
                u.email = NEW_EMAIL
                changed = True
            if not u.is_active:
                u.is_active = True
                changed = True
            if not u.is_staff:
                u.is_staff = True
                changed = True
            if not u.is_superuser:
                u.is_superuser = True
                changed = True
            if changed:
                u.save()
                action = "Created" if created else "Updated"
                self.stdout.write(
                    self.style.SUCCESS(f"[rotate] {action} secure account '{NEW_USERNAME}'")
                )
            else:
                self.stdout.write(f"[rotate] '{NEW_USERNAME}' already correct — no change needed")

            # ── Step 3: Ensure UserProfile with TENANT_SUPER_ADMIN role ─────
            try:
                from school.models import Role, UserProfile
                role = Role.objects.filter(name="TENANT_SUPER_ADMIN").first()
                if not role:
                    # Roles are seeded by seed_default_permissions which runs after
                    # this command at startup.  Log a warning but don't fail hard —
                    # the role will exist by the time the first login is attempted.
                    self.stdout.write(
                        self.style.WARNING(
                            f"[rotate] TENANT_SUPER_ADMIN role not found yet for schema '{SCHEMA}' "
                            "(will be created by seed_default_permissions)"
                        )
                    )
                else:
                    profile, p_created = UserProfile.objects.get_or_create(
                        user=u, defaults={"role": role}
                    )
                    if not p_created and profile.role != role:
                        profile.role = role
                        profile.save()
                        self.stdout.write(f"[rotate] Corrected UserProfile role → TENANT_SUPER_ADMIN for '{NEW_USERNAME}'")
                    elif p_created:
                        self.stdout.write(f"[rotate] Created UserProfile (TENANT_SUPER_ADMIN) for '{NEW_USERNAME}'")
                    # Always emit a confirmation line so the log shows the final state.
                    actual_role = profile.role.name if profile.role else "None"
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"[rotate] UserProfile OK — '{NEW_USERNAME}' role={actual_role} "
                            f"schema={SCHEMA}"
                        )
                    )
            except Exception as exc:
                # Use ERROR (not just WARNING) so this is never silently missed.
                logger.error(
                    "[rotate] Failed to verify/create UserProfile for '%s' on schema '%s': %s",
                    NEW_USERNAME, SCHEMA, exc, exc_info=True,
                )
                self.stderr.write(
                    self.style.ERROR(
                        f"[rotate] ERROR: Could not ensure UserProfile for '{NEW_USERNAME}': {exc}"
                    )
                )
