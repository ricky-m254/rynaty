"""
Management command: seed_school_data

Seeds minimal school profile and academic structure for any tenant schema
that is missing it. Fully idempotent — safe to run on every startup.

Usage:
    python manage.py seed_school_data --all-tenants
    python manage.py seed_school_data --schema_name demo_school
"""
import re
from datetime import date

from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context, get_public_schema_name

_STUDENT_USERNAME_RE = re.compile(r"^stm\d|^adm[-_]?\d", re.IGNORECASE)


CBC_GRADE_LEVELS = [
    ("Grade 7", 7),
    ("Grade 8", 8),
    ("Grade 9", 9),
    ("Grade 10", 10),
]

CBC_DEPARTMENTS = [
    ("Languages", "Language and Communication"),
    ("Mathematics", "Mathematical Sciences"),
    ("Sciences", "Natural Sciences"),
    ("Humanities", "Humanities and Social Studies"),
    ("Technology", "ICT and Technology"),
    ("Arts", "Creative Arts and Sports"),
]

CBC_SUBJECTS = [
    ("English", "ENG", "Languages"),
    ("Kiswahili", "KIS", "Languages"),
    ("Mathematics", "MAT", "Mathematics"),
    ("Integrated Science", "ISC", "Sciences"),
    ("Social Studies", "SST", "Humanities"),
    ("Religious Education", "CRE", "Humanities"),
    ("Business Studies", "BST", "Humanities"),
    ("Agriculture and Nutrition", "AGR", "Sciences"),
    ("Pre-Technical Studies", "PTS", "Technology"),
    ("Creative Arts and Sports", "CAS", "Arts"),
]

CURRENT_YEAR_NAME = "2025-2026"
TERMS = [
    ("Term 1", date(2025, 1, 6), date(2025, 4, 4)),
    ("Term 2", date(2025, 5, 5), date(2025, 8, 8)),
    ("Term 3", date(2025, 9, 1), date(2025, 11, 28)),
]


class Command(BaseCommand):
    help = "Seed minimal school profile and academic structure for tenant schemas (idempotent)"

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--schema_name", type=str, help="Single schema to seed")
        group.add_argument("--all-tenants", action="store_true", help="Seed all non-public tenant schemas")

    def handle(self, *args, **options):
        from clients.models import Tenant

        public = get_public_schema_name()
        if options["all_tenants"]:
            tenants = Tenant.objects.exclude(schema_name=public).order_by("schema_name")
            for tenant in tenants:
                self._seed(tenant.schema_name, tenant_name=tenant.name)
        else:
            schema = options["schema_name"]
            tenant = Tenant.objects.filter(schema_name=schema).first()
            tenant_name = tenant.name if tenant else schema
            self._seed(schema, tenant_name=tenant_name)

    def _seed(self, schema_name, tenant_name="School"):
        tag = f"[{schema_name}]"
        self.stdout.write(f"{tag} Seeding school data...")
        try:
            with schema_context(schema_name):
                self._school_profile(tag, tenant_name)
                self._grade_levels(tag)
                self._academic_year(tag)
                self._departments_and_subjects(tag)
                self._repair_missing_user_profiles(tag)
        except Exception as exc:
            self.stdout.write(f"{tag} ERROR: {exc}")

    def _school_profile(self, tag, tenant_name):
        from school.models import SchoolProfile
        profile, created = SchoolProfile.objects.get_or_create(
            is_active=True,
            defaults={
                "school_name": tenant_name,
                "motto": "Excellence in Education",
                "address": "Nairobi, Kenya",
                "phone": "+254 700 000 000",
                "country": "Kenya",
                "county": "Nairobi",
                "currency": "KES",
                "timezone": "Africa/Nairobi",
                "language": "en",
                "primary_color": "#10b981",
                "secondary_color": "#0d1117",
                "admission_number_mode": "AUTO",
                "admission_number_prefix": "ADM-",
                "receipt_prefix": "RCT-",
                "invoice_prefix": "INV-",
            },
        )
        action = "created" if created else "exists"
        self.stdout.write(f"{tag}   SchoolProfile: {action} ({profile.school_name!r})")

    def _grade_levels(self, tag):
        from school.models import GradeLevel
        created_count = 0
        for name, order in CBC_GRADE_LEVELS:
            _, c = GradeLevel.objects.get_or_create(name=name, defaults={"order": order, "is_active": True})
            if c:
                created_count += 1
        total = len(CBC_GRADE_LEVELS)
        self.stdout.write(f"{tag}   GradeLevels: {created_count} created, {total - created_count} existed")

    def _academic_year(self, tag):
        from school.models import AcademicYear, Term

        year, ay_created = AcademicYear.objects.get_or_create(
            name=CURRENT_YEAR_NAME,
            defaults={
                "start_date": date(2025, 1, 1),
                "end_date": date(2025, 12, 31),
                "is_active": True,
                "is_current": True,
            },
        )
        if not year.is_current:
            AcademicYear.objects.filter(pk=year.pk).update(is_current=True)
            AcademicYear.objects.exclude(pk=year.pk).update(is_current=False)
            self.stdout.write(f"{tag}   AcademicYear '{CURRENT_YEAR_NAME}': marked as current")
        else:
            action = "created" if ay_created else "already current"
            self.stdout.write(f"{tag}   AcademicYear '{CURRENT_YEAR_NAME}': {action}")

        t_created = 0
        for tname, tstart, tend in TERMS:
            _, c = Term.objects.get_or_create(
                academic_year=year,
                name=tname,
                defaults={"start_date": tstart, "end_date": tend, "is_active": True, "is_current": (tname == "Term 2")},
            )
            if c:
                t_created += 1
        self.stdout.write(f"{tag}   Terms: {t_created} created, {len(TERMS) - t_created} existed")

    def _departments_and_subjects(self, tag):
        from school.models import Department, Subject

        dept_map = {}
        dept_created = 0
        for dname, ddesc in CBC_DEPARTMENTS:
            dept, c = Department.objects.get_or_create(name=dname, defaults={"description": ddesc})
            dept_map[dname] = dept
            if c:
                dept_created += 1
        self.stdout.write(f"{tag}   Departments: {dept_created} created, {len(CBC_DEPARTMENTS) - dept_created} existed")

        subj_created = 0
        for sname, scode, sdept in CBC_SUBJECTS:
            _, c = Subject.objects.get_or_create(
                code=scode,
                defaults={
                    "name": sname,
                    "department": dept_map.get(sdept),
                    "is_active": True,
                    "subject_type": "Compulsory",
                },
            )
            if c:
                subj_created += 1
        self.stdout.write(f"{tag}   Subjects: {subj_created} created, {len(CBC_SUBJECTS) - subj_created} existed")

    def _repair_missing_user_profiles(self, tag):
        """
        Detect ALL active users with no UserProfile and create the missing rows
        using a deterministic role-inference chain (evaluated in priority order):

          1. is_superuser=True                          → TENANT_SUPER_ADMIN
          2. _STUDENT_USERNAME_RE match (stm<digit> or
             adm<sep?><digit>)                          → STUDENT
             • matches stm2025001, STM2025001, adm001
             • does NOT match "admin" / "administrator"
          3. All others (staff fallback)                → ADMIN

        Every active user without a profile will receive one. Callers that seed
        specific users with dedicated roles afterwards will not be affected because
        get_or_create is used (existing rows are never overwritten).

        Fully idempotent — safe to run multiple times.
        """
        from django.contrib.auth import get_user_model
        from school.models import Role, UserProfile

        User = get_user_model()

        users_without_profile = (
            User.objects
            .filter(is_active=True)
            .exclude(userprofile__isnull=False)
        )

        if not users_without_profile.exists():
            self.stdout.write(f"{tag}   UserProfile repair: all users have profiles")
            return

        role_cache = {r.name: r for r in Role.objects.all()}
        student_role = role_cache.get("STUDENT")
        super_admin_role = role_cache.get("TENANT_SUPER_ADMIN")
        admin_role = role_cache.get("ADMIN")

        repaired = 0
        for user in users_without_profile:
            if user.is_superuser and super_admin_role:
                assigned_role = super_admin_role
            elif _STUDENT_USERNAME_RE.match(user.username) and student_role:
                assigned_role = student_role
            else:
                assigned_role = admin_role

            if assigned_role:
                _, created = UserProfile.objects.get_or_create(
                    user=user, defaults={"role": assigned_role}
                )
                if created:
                    repaired += 1
            else:
                self.stdout.write(
                    f"{tag}   UserProfile repair WARNING: no roles found — "
                    "run seed_roles first."
                )
                break

        if repaired:
            self.stdout.write(
                f"{tag}   UserProfile repair: {repaired} profile(s) auto-created"
            )
        else:
            self.stdout.write(f"{tag}   UserProfile repair: all users have profiles")
