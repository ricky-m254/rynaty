"""
Idempotent management command to eliminate the insecure admin/admin123
tenant account and ensure only the secure credentials work.
Runs unconditionally at every startup via start.sh.
"""
from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context

SCHEMA = "demo_school"
OLD_USERNAME = "admin"
NEW_USERNAME = "Riqs#."
NEW_PASSWORD = "Ointment.54.#"
NEW_EMAIL = "emurithi593@gmail.com"

ALSO_BLOCK = ["admin123", "Admin123", "Admin#123"]  # extra weak passwords to reject


class Command(BaseCommand):
    help = "Eliminate insecure admin/admin123 account and enforce secure credentials (idempotent)"

    def handle(self, *args, **options):
        with schema_context(SCHEMA):
            from django.contrib.auth.models import User
            from django.db import connection

            old_exists = User.objects.filter(username=OLD_USERNAME).exists()
            new_exists = User.objects.filter(username=NEW_USERNAME).exists()

            # ── Step 1: Hard-delete the old insecure account if it exists ──
            if old_exists:
                old_user = User.objects.get(username=OLD_USERNAME)
                uid = old_user.id
                # Delete via raw SQL to avoid cascade into missing tables
                with connection.cursor() as cur:
                    cur.execute(
                        "DELETE FROM token_blacklist_blacklistedtoken WHERE token_id IN "
                        "(SELECT id FROM token_blacklist_outstandingtoken WHERE user_id = %s)", [uid]
                    )
                    cur.execute(
                        "DELETE FROM token_blacklist_outstandingtoken WHERE user_id = %s", [uid]
                    )
                    # Null-out any FK references that allow nulls before hard delete
                    for tbl, col in [
                        ("school_auditlog", "user_id"),
                    ]:
                        try:
                            cur.execute(
                                f"UPDATE {tbl} SET {col} = NULL WHERE {col} = %s", [uid]
                            )
                        except Exception:
                            pass
                    cur.execute("DELETE FROM auth_user WHERE id = %s", [uid])
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[rotate] DELETED insecure account '{OLD_USERNAME}' (id={uid})"
                    )
                )
                old_exists = False

            # ── Step 2: Ensure the secure account exists with correct creds ─
            if not new_exists:
                from django.contrib.auth.models import User
                u = User.objects.create_user(
                    username=NEW_USERNAME,
                    email=NEW_EMAIL,
                    password=NEW_PASSWORD,
                    is_staff=True,
                    is_superuser=True,
                )
                self.stdout.write(
                    self.style.SUCCESS(f"[rotate] Created secure account '{NEW_USERNAME}'")
                )
            else:
                u = User.objects.get(username=NEW_USERNAME)
                changed = False
                if not u.check_password(NEW_PASSWORD):
                    u.set_password(NEW_PASSWORD)
                    changed = True
                if u.email != NEW_EMAIL:
                    u.email = NEW_EMAIL
                    changed = True
                if not u.is_active:
                    u.is_active = True
                    changed = True
                if changed:
                    u.save()
                    self.stdout.write(
                        self.style.SUCCESS(f"[rotate] Updated credentials for '{NEW_USERNAME}'")
                    )
                else:
                    self.stdout.write(f"[rotate] '{NEW_USERNAME}' already correct — no change needed")

            # ── Step 3: Ensure UserProfile exists with TENANT_SUPER_ADMIN ───
            try:
                from school.models import Role, UserProfile
                role = Role.objects.filter(name="TENANT_SUPER_ADMIN").first()
                if role:
                    u = User.objects.get(username=NEW_USERNAME)
                    UserProfile.objects.get_or_create(user=u, defaults={"role": role})
            except Exception:
                pass
