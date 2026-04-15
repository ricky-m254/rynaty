"""
Management command: diagnose_tenant

Runs a comprehensive health check on a tenant schema and prints a
colour-coded report.  Call this whenever a tenant reports 403 errors,
missing roles, empty dropdowns, or "No assigned modules."

Usage:
    python manage.py diagnose_tenant --schema_name olom
    python manage.py diagnose_tenant --schema_name school_olomrynatyschoolapp
    python manage.py diagnose_tenant --all-tenants
"""
from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context, get_public_schema_name


OK = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
WARN = "\033[93m⚠\033[0m"


class Command(BaseCommand):
    help = "Health-check a tenant schema and report misconfigurations"

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--schema_name", type=str, help="Schema to diagnose")
        group.add_argument("--all-tenants", action="store_true", help="Diagnose all non-public tenants")

    def handle(self, *args, **options):
        from clients.models import Tenant

        if options["all_tenants"]:
            public = get_public_schema_name()
            tenants = Tenant.objects.exclude(schema_name=public).order_by("schema_name")
            for tenant in tenants:
                self._diagnose(tenant.schema_name)
        else:
            self._diagnose(options["schema_name"])

    def _diagnose(self, schema_name):
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"  Diagnosing schema: {schema_name}")
        self.stdout.write(f"{'='*60}")

        issues = []

        try:
            with schema_context(schema_name):
                self._check_roles(schema_name, issues)
                self._check_modules(schema_name, issues)
                self._check_admin_users(schema_name, issues)
                self._check_school_profile(schema_name, issues)
                self._check_academic_structure(schema_name, issues)
                self._check_tenant_modules(schema_name, issues)
        except Exception as exc:
            self.stdout.write(f"  {FAIL} FATAL: could not enter schema context: {exc}")
            return

        self.stdout.write("")
        if issues:
            self.stdout.write(f"  {FAIL} {len(issues)} issue(s) found:")
            for i, issue in enumerate(issues, 1):
                self.stdout.write(f"     {i}. {issue}")
            self.stdout.write("")
            self.stdout.write(f"  Quick fixes:")
            self.stdout.write(f"    python manage.py seed_school_data --schema_name {schema_name}")
            self.stdout.write(f"    python manage.py seed_default_permissions --assign-roles --all-tenants")
            self.stdout.write(f"    python manage.py seed_modules --all-tenants")
            self.stdout.write(f"  See the diagnose-tenant skill for detailed fixes.")
        else:
            self.stdout.write(f"  {OK} All checks passed — tenant looks healthy.")

    def _check_roles(self, schema_name, issues):
        from school.models import Role
        count = Role.objects.count()
        if count == 0:
            self.stdout.write(f"  {FAIL} Roles: 0 (not seeded — run seed_default_permissions --assign-roles --all-tenants)")
            issues.append("No Role objects in schema — seed_default_permissions has not run.")
        elif count < 10:
            self.stdout.write(f"  {WARN} Roles: {count} (expected 19 — partially seeded?)")
            issues.append(f"Only {count} roles found, expected 19.")
        else:
            self.stdout.write(f"  {OK} Roles: {count} seeded")

    def _check_modules(self, schema_name, issues):
        from school.models import Module
        count = Module.objects.count()
        if count == 0:
            self.stdout.write(f"  {FAIL} Modules: 0 (run seed_modules --all-tenants)")
            issues.append("No Module objects — seed_modules has not run.")
        elif count < 20:
            self.stdout.write(f"  {WARN} Modules: {count} (expected 28)")
            issues.append(f"Only {count} modules found, expected 28.")
        else:
            self.stdout.write(f"  {OK} Modules: {count} seeded")

    def _check_admin_users(self, schema_name, issues):
        from django.contrib.auth.models import User
        from school.models import UserProfile, Role
        from school.role_scope import get_user_scope_profile, ADMIN_SCOPE_PROFILES

        admin_roles = {"TENANT_SUPER_ADMIN", "ADMIN", "PRINCIPAL"}
        admin_users = User.objects.filter(
            is_active=True,
            userprofile__role__name__in=admin_roles,
        ).select_related("userprofile__role").distinct()

        if not admin_users.exists():
            self.stdout.write(f"  {FAIL} Admin users: NONE with admin role")
            issues.append("No active users with TENANT_SUPER_ADMIN / ADMIN / PRINCIPAL role.")

            # Show all users and their profile status
            all_users = User.objects.filter(is_active=True)
            for u in all_users[:10]:
                profile = getattr(u, "userprofile", None)
                if profile is None:
                    detail = "no UserProfile"
                    issues.append(f"  User '{u.username}' has no UserProfile — run seed_olom_tenant or fix manually.")
                else:
                    role = profile.role
                    if role is None:
                        detail = "UserProfile exists but role=NULL"
                        issues.append(f"  User '{u.username}' UserProfile.role is NULL — assign TENANT_SUPER_ADMIN Role FK.")
                    else:
                        detail = f"role={role.name!r}"
                self.stdout.write(f"     User '{u.username}': {detail}")
            return

        for u in admin_users:
            profile = u.userprofile
            role = profile.role
            scope = get_user_scope_profile(u)
            is_admin_scope = scope in ADMIN_SCOPE_PROFILES

            role_name = role.name if role else "NULL"
            scope_str = scope or "NULL"
            symbol = OK if is_admin_scope else FAIL

            self.stdout.write(
                f"  {symbol} User '{u.username}': role={role_name!r} → scope={scope_str!r} "
                f"{'(admin ✓)' if is_admin_scope else '(NOT in ADMIN_SCOPE — will 403!)'}"
            )
            if not is_admin_scope:
                issues.append(
                    f"User '{u.username}' scope={scope_str!r} not in ADMIN_SCOPE_PROFILES — "
                    f"all admin endpoints will return 403."
                )

    def _check_school_profile(self, schema_name, issues):
        from school.models import SchoolProfile
        profile = SchoolProfile.objects.filter(is_active=True).first()
        if not profile:
            self.stdout.write(f"  {FAIL} SchoolProfile: MISSING")
            issues.append("No SchoolProfile — school settings pages will show errors.")
        else:
            self.stdout.write(f"  {OK} SchoolProfile: {profile.school_name!r}")

    def _check_academic_structure(self, schema_name, issues):
        from school.models import GradeLevel, Subject, AcademicYear, Department
        gl_count = GradeLevel.objects.filter(is_active=True).count()
        subj_count = Subject.objects.filter(is_active=True).count()
        ay = AcademicYear.objects.filter(is_current=True).first()
        dept_count = Department.objects.count()

        symbol = OK if gl_count > 0 else FAIL
        self.stdout.write(f"  {symbol} GradeLevels: {gl_count}")
        if gl_count == 0:
            issues.append("No GradeLevels — academic dropdowns will be empty.")

        symbol = OK if subj_count > 0 else WARN
        self.stdout.write(f"  {symbol} Subjects: {subj_count}")
        if subj_count == 0:
            issues.append("No Subjects — timetable, curriculum, and exam views will be empty.")

        symbol = OK if dept_count > 0 else WARN
        self.stdout.write(f"  {symbol} Departments: {dept_count}")

        symbol = OK if ay else WARN
        self.stdout.write(f"  {symbol} Current AcademicYear: {ay.name if ay else 'NONE'}")
        if not ay:
            issues.append("No current AcademicYear — academic and finance features may error.")

    def _check_tenant_modules(self, schema_name, issues):
        from school.models import TenantModule
        total = TenantModule.objects.count()
        enabled = TenantModule.objects.filter(is_enabled=True).count()
        if total == 0:
            self.stdout.write(f"  {FAIL} TenantModules: 0 (run seed_modules --all-tenants)")
            issues.append("No TenantModule records — module-gated views will block all access.")
        elif enabled == 0:
            self.stdout.write(f"  {FAIL} TenantModules: {total} exist but 0 enabled")
            issues.append(f"{total} TenantModules exist but none are enabled.")
        else:
            self.stdout.write(f"  {OK} TenantModules: {enabled}/{total} enabled")
