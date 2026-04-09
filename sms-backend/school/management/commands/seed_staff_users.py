"""
seed_staff_users.py
Creates Django auth login accounts for all staff role types in a tenant schema.
Idempotent — safe to run multiple times.

Roles created:
  admin / admin123                (TENANT_SUPER_ADMIN — already exists)
  principal / principal123        (PRINCIPAL)
  deputy / deputy123              (DEPUTY_PRINCIPAL)
  bursar / bursar123              (BURSAR / ACCOUNTANT)
  accountant / accountant123      (ACCOUNTANT)
  hr / hr123                      (HR_OFFICER)
  registrar / registrar123        (REGISTRAR)
  librarian / librarian123        (LIBRARIAN)
  teacher1 / teacher123           (TEACHER — from Kenya seed)
  nurse / nurse123                (NURSE)
  security / security123          (SECURITY)
  hod / hod123                    (HOD)
  store_clerk / store123          (STORE_CLERK)
  alumnicoord / alumni123         (ALUMNI coordinator)
"""
from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context


STAFF_ACCOUNTS = [
    # (username, password, first_name, last_name, email, role_name)
    ("principal",   "principal123",  "James",   "Kariuki",   "principal@stmarys.ac.ke",   "PRINCIPAL"),
    ("deputy",      "deputy123",     "Grace",   "Wanjiku",   "deputy@stmarys.ac.ke",      "DEPUTY_PRINCIPAL"),
    ("bursar",      "bursar123",     "Samuel",  "Otieno",    "bursar@stmarys.ac.ke",      "BURSAR"),
    ("accountant",  "accountant123", "Faith",   "Njoroge",   "accountant@stmarys.ac.ke",  "ACCOUNTANT"),
    ("hr",          "hr123",         "David",   "Mwangi",    "hr@stmarys.ac.ke",          "HR_OFFICER"),
    ("registrar",   "registrar123",  "Mary",    "Achieng",   "registrar@stmarys.ac.ke",   "REGISTRAR"),
    ("librarian",   "librarian123",  "Joyce",   "Wangari",   "librarian@stmarys.ac.ke",   "LIBRARIAN"),
    ("nurse",       "nurse123",      "Esther",  "Chepkoech", "nurse@stmarys.ac.ke",       "NURSE"),
    ("security",    "security123",   "John",    "Kamau",     "security@stmarys.ac.ke",    "SECURITY"),
    ("hod.math",    "hod123",        "Peter",   "Ndirangu",  "hod.math@stmarys.ac.ke",   "HOD"),
    ("hod.science", "hod123",        "Ruth",    "Adhiambo",  "hod.science@stmarys.ac.ke", "HOD"),
    ("store_clerk", "store123",      "Kevin",   "Waweru",    "store@stmarys.ac.ke",       "STORE_CLERK"),
    ("alumnicoord", "alumni123",     "Alice",   "Nyambura",  "alumni@stmarys.ac.ke",      "ALUMNI"),
    ("teacher1",    "teacher123",    "Agnes",   "Kamau",     "teacher1@stmarys.ac.ke",    "TEACHER"),
    ("teacher2",    "teacher123",    "Beatrice","Njeri",     "teacher2@stmarys.ac.ke",    "TEACHER"),
    ("teacher3",    "teacher123",    "Daniel",  "Otieno",    "teacher3@stmarys.ac.ke",    "TEACHER"),
    ("teacher4",    "teacher123",    "Priscilla","Chebet",   "teacher4@stmarys.ac.ke",    "TEACHER"),
    ("teacher5",    "teacher123",    "Collins", "Omondi",    "teacher5@stmarys.ac.ke",    "TEACHER"),
]


class Command(BaseCommand):
    help = "Create login accounts for all staff role types in a tenant schema."

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema_name",
            type=str,
            default="demo_school",
            help="Tenant schema name",
        )

    def handle(self, *args, **options):
        schema = options["schema_name"]
        self.stdout.write(f"[seed_staff_users] Seeding staff user accounts in schema: {schema}")

        with schema_context(schema):
            from django.contrib.auth import get_user_model
            from school.models import Role, UserProfile
            from school.role_scope import materialize_role_module_baseline

            User = get_user_model()
            created = 0
            updated = 0

            for username, password, first_name, last_name, email, role_name in STAFF_ACCOUNTS:
                role = Role.objects.filter(name=role_name).first()
                if not role:
                    self.stdout.write(
                        self.style.WARNING(f"  Role '{role_name}' not found — skipping {username}")
                    )
                    continue

                user, user_created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": email,
                        "is_active": True,
                        "is_staff": role_name in ("TENANT_SUPER_ADMIN", "ADMIN", "PRINCIPAL"),
                    },
                )
                if user_created:
                    user.set_password(password)
                    user.save()
                    created += 1
                else:
                    if not user.check_password(password):
                        user.set_password(password)
                        user.save()
                        updated += 1

                profile = UserProfile.objects.filter(user=user).first()
                if profile is None:
                    try:
                        profile = UserProfile.objects.create(
                            user=user,
                            role=role,
                            force_password_change=False,
                        )
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f"  Profile create failed for {username}: {e}"))
                        continue
                else:
                    if profile.role_id != role.id:
                        profile.role = role
                        profile.save(update_fields=["role"])

                # Ensure every staff member has the module assignments for their role.
                try:
                    materialize_role_module_baseline(user, role_name)
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"  Module assignment failed for {username}: {e}"))

            self.stdout.write(
                self.style.SUCCESS(
                    f"[seed_staff_users] Done — {created} created, {updated} updated."
                )
            )
