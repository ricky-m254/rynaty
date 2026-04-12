"""
Idempotent management command to rotate the insecure default admin/admin123
tenant account to the secure credentials.  Runs at every startup via start.sh.
"""
from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context


SCHEMA = "demo_school"
OLD_USERNAME = "admin"
NEW_USERNAME = "Riqs#."
NEW_PASSWORD = "Ointment.54.#"
NEW_EMAIL = "emurithi593@gmail.com"


class Command(BaseCommand):
    help = "Rotate insecure default admin credentials (idempotent)"

    def handle(self, *args, **options):
        with schema_context(SCHEMA):
            from django.contrib.auth.models import User

            # If old insecure user still exists, rename + re-credential it
            if User.objects.filter(username=OLD_USERNAME).exists():
                u = User.objects.get(username=OLD_USERNAME)
                u.username = NEW_USERNAME
                u.email = NEW_EMAIL
                u.set_password(NEW_PASSWORD)
                u.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[rotate_admin_credentials] Rotated '{OLD_USERNAME}' → '{NEW_USERNAME}'"
                    )
                )
                return

            # New username already exists — make sure password/email are correct
            if User.objects.filter(username=NEW_USERNAME).exists():
                u = User.objects.get(username=NEW_USERNAME)
                changed = False
                if not u.check_password(NEW_PASSWORD):
                    u.set_password(NEW_PASSWORD)
                    changed = True
                if u.email != NEW_EMAIL:
                    u.email = NEW_EMAIL
                    changed = True
                if changed:
                    u.save()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"[rotate_admin_credentials] Updated credentials for '{NEW_USERNAME}'"
                        )
                    )
                else:
                    self.stdout.write(f"[rotate_admin_credentials] '{NEW_USERNAME}' already correct — no change")
                return

            self.stdout.write(
                f"[rotate_admin_credentials] Neither '{OLD_USERNAME}' nor '{NEW_USERNAME}' found in {SCHEMA} — skipping"
            )
