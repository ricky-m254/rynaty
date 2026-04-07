"""
Management Command: seed_default_permissions
Phase 16 Advanced RBAC - Prompts 88-89.

Usage:
  python manage.py seed_default_permissions
  python manage.py seed_default_permissions --assign-roles
  python manage.py seed_default_permissions --schema=demo_school --assign-roles
  python manage.py seed_default_permissions --all-tenants --assign-roles

Creates all default <domain>.<resource>.<action> permissions
and optionally creates RolePermissionGrant records.
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django_tenants.utils import schema_context

from clients.models import Tenant
from school.role_scope import (
    SCOPE_ACADEMIC_LEAD,
    SCOPE_ACADEMIC_STAFF,
    SCOPE_ALUMNI_PORTAL,
    SCOPE_CATERING_OPERATIONS,
    SCOPE_FINANCE_MANAGER,
    SCOPE_FULL_TENANT_ADMIN,
    SCOPE_HEALTH_OPERATIONS,
    SCOPE_HR_MANAGER,
    SCOPE_LIBRARY_OPERATIONS,
    SCOPE_PARENT_PORTAL,
    SCOPE_REGISTRAR_OPERATIONS,
    SCOPE_SCHOOL_ADMIN,
    SCOPE_SECURITY_OPERATIONS,
    SCOPE_STORE_OPERATIONS,
    SCOPE_STUDENT_PORTAL,
    iter_seed_role_names,
    resolve_scope_profile,
)

DEFAULT_PERMISSIONS = [
    ("students.student.read", "students", "read", "View student list and profiles"),
    ("students.student.create", "students", "create", "Enroll new students"),
    ("students.student.update", "students", "update", "Edit student information"),
    ("students.student.delete", "students", "delete", "Deactivate or delete students"),
    ("finance.invoice.read", "finance", "read", "View invoices and statements"),
    ("finance.invoice.create", "finance", "create", "Generate invoices"),
    ("finance.invoice.update", "finance", "update", "Edit invoice details"),
    ("finance.payment.record", "finance", "record", "Record payments"),
    ("finance.payment.view", "finance", "view", "View payment history"),
    ("finance.report.view", "finance", "view", "View financial reports"),
    ("academics.enrollment.read", "academics", "read", "View class enrollments"),
    ("academics.enrollment.manage", "academics", "manage", "Manage enrollments"),
    ("academics.attendance.mark", "academics", "mark", "Mark attendance"),
    ("academics.attendance.view", "academics", "view", "View attendance records"),
    ("academics.timetable.read", "academics", "read", "View timetables"),
    ("academics.timetable.manage", "academics", "manage", "Create/edit timetables"),
    ("academics.exam.read", "academics", "read", "View examination results"),
    ("academics.exam.manage", "academics", "manage", "Manage exams and results"),
    ("hr.staff.read", "hr", "read", "View staff directory"),
    ("hr.staff.create", "hr", "create", "Add new staff members"),
    ("hr.staff.update", "hr", "update", "Edit staff information"),
    ("hr.staff.delete", "hr", "delete", "Deactivate staff"),
    ("hr.leave.view", "hr", "view", "View leave requests"),
    ("hr.leave.apply", "hr", "apply", "Apply for leave"),
    ("hr.leave.approve", "hr", "approve", "Approve leave requests"),
    ("hr.payroll.view", "hr", "view", "View payroll records"),
    ("hr.payroll.manage", "hr", "manage", "Process payroll"),
    ("transport.vehicle.read", "transport", "read", "View vehicles and routes"),
    ("transport.vehicle.manage", "transport", "manage", "Add/edit vehicles and routes"),
    ("transport.student.assign", "transport", "assign", "Assign students to routes"),
    ("library.book.read", "library", "read", "Browse book catalog"),
    ("library.book.manage", "library", "manage", "Manage book catalog"),
    ("library.circulation.manage", "library", "manage", "Issue and return books"),
    ("hostel.allocation.read", "hostel", "read", "View bed allocations"),
    ("hostel.allocation.manage", "hostel", "manage", "Assign/remove bed allocations"),
    ("admissions.application.read", "admissions", "read", "View admission applications"),
    ("admissions.application.manage", "admissions", "manage", "Process admissions"),
    ("communication.message.send", "communication", "send", "Send messages/announcements"),
    ("communication.message.read", "communication", "read", "Read messages"),
    ("communication.announcement.post", "communication", "post", "Post announcements"),
    ("visitor.checkin.manage", "visitor", "manage", "Manage visitor check-in"),
    ("clockin.attendance.view", "clockin", "view", "View clock-in records"),
    ("clockin.attendance.manage", "clockin", "manage", "Manage clock-in records"),
    ("sports.team.view", "sports", "view", "View sports teams"),
    ("sports.team.manage", "sports", "manage", "Manage sports teams"),
    ("cafeteria.meal.view", "cafeteria", "view", "View cafeteria/meal plans"),
    ("cafeteria.meal.manage", "cafeteria", "manage", "Manage meal plans"),
    ("analytics.report.view", "analytics", "view", "View analytics reports"),
    ("analytics.report.export", "analytics", "export", "Export analytics reports"),
    ("alumni.record.view", "alumni", "view", "View alumni records"),
    ("alumni.record.manage", "alumni", "manage", "Manage alumni records"),
    ("maintenance.request.submit", "maintenance", "submit", "Submit maintenance requests"),
    ("maintenance.request.manage", "maintenance", "manage", "Manage maintenance requests"),
    ("curriculum.content.view", "curriculum", "view", "View curriculum content"),
    ("curriculum.content.manage", "curriculum", "manage", "Manage curriculum content"),
    ("elearning.course.view", "elearning", "view", "View e-learning courses"),
    ("elearning.course.manage", "elearning", "manage", "Manage e-learning courses"),
    ("settings.system.manage", "settings", "manage", "Manage system settings"),
    ("settings.rbac.manage", "settings", "manage", "Manage roles and permissions"),
    ("settings.modules.manage", "settings", "manage", "Enable/disable modules"),
]


def _dedupe_permissions(*groups):
    seen = set()
    ordered = []
    for group in groups:
        for permission_name in group:
            if permission_name in seen:
                continue
            seen.add(permission_name)
            ordered.append(permission_name)
    return ordered


ALL_PERMISSION_NAMES = [name for name, _, _, _ in DEFAULT_PERMISSIONS]
ACCOUNTANT_PERMISSIONS = [
    "finance.invoice.read",
    "finance.invoice.create",
    "finance.invoice.update",
    "finance.payment.record",
    "finance.payment.view",
    "finance.report.view",
    "students.student.read",
]
TEACHER_PERMISSIONS = [
    "students.student.read",
    "academics.enrollment.read",
    "academics.attendance.mark",
    "academics.attendance.view",
    "academics.timetable.read",
    "academics.exam.read",
    "academics.exam.manage",
    "communication.message.send",
    "communication.message.read",
    "library.book.read",
]
PARENT_PERMISSIONS = [
    "students.student.read",
    "finance.invoice.read",
    "finance.payment.view",
    "academics.attendance.view",
    "academics.timetable.read",
    "communication.message.read",
]
STUDENT_PERMISSIONS = [
    "academics.timetable.read",
    "academics.attendance.view",
    "library.book.read",
    "communication.message.read",
    "elearning.course.view",
]

SCOPE_PERMISSION_DEFAULTS = {
    SCOPE_FULL_TENANT_ADMIN: ALL_PERMISSION_NAMES,
    SCOPE_SCHOOL_ADMIN: ALL_PERMISSION_NAMES,
    SCOPE_FINANCE_MANAGER: ACCOUNTANT_PERMISSIONS,
    SCOPE_ACADEMIC_STAFF: TEACHER_PERMISSIONS,
    SCOPE_ACADEMIC_LEAD: _dedupe_permissions(
        TEACHER_PERMISSIONS,
        [
            "academics.enrollment.manage",
            "academics.timetable.manage",
            "communication.announcement.post",
            "analytics.report.view",
        ],
    ),
    SCOPE_HR_MANAGER: [
        "hr.staff.read",
        "hr.staff.create",
        "hr.staff.update",
        "hr.leave.view",
        "hr.leave.apply",
        "hr.leave.approve",
        "hr.payroll.view",
        "clockin.attendance.view",
        "clockin.attendance.manage",
        "communication.message.read",
        "communication.message.send",
    ],
    SCOPE_REGISTRAR_OPERATIONS: [
        "students.student.read",
        "students.student.create",
        "students.student.update",
        "academics.enrollment.read",
        "academics.enrollment.manage",
        "admissions.application.read",
        "admissions.application.manage",
        "communication.message.read",
        "communication.message.send",
    ],
    SCOPE_LIBRARY_OPERATIONS: [
        "library.book.read",
        "library.book.manage",
        "library.circulation.manage",
        "students.student.read",
        "communication.message.read",
    ],
    SCOPE_HEALTH_OPERATIONS: [
        "students.student.read",
        "communication.message.read",
    ],
    SCOPE_SECURITY_OPERATIONS: [
        "visitor.checkin.manage",
        "communication.message.read",
    ],
    SCOPE_CATERING_OPERATIONS: [
        "cafeteria.meal.view",
        "cafeteria.meal.manage",
        "communication.message.read",
    ],
    SCOPE_STORE_OPERATIONS: [
        "communication.message.read",
    ],
    SCOPE_PARENT_PORTAL: PARENT_PERMISSIONS,
    SCOPE_STUDENT_PORTAL: STUDENT_PERMISSIONS,
    SCOPE_ALUMNI_PORTAL: [
        "alumni.record.view",
    ],
}


def build_role_defaults():
    defaults = {}
    for role_name in iter_seed_role_names():
        scope_profile = resolve_scope_profile(role_name)
        defaults[role_name] = list(SCOPE_PERMISSION_DEFAULTS.get(scope_profile, ()))
    return defaults


ROLE_DEFAULTS = build_role_defaults()


class Command(BaseCommand):
    help = "Seed default RBAC permissions (Phase 16 Advanced RBAC)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--assign-roles",
            action="store_true",
            help="Also assign default permissions to built-in roles",
        )
        parser.add_argument("--schema", type=str, default=None, help="Target tenant schema name.")
        parser.add_argument(
            "--all-tenants",
            action="store_true",
            help="Seed permissions for all tenant schemas.",
        )

    @staticmethod
    def _table_exists(table_name: str) -> bool:
        return table_name in connection.introspection.table_names()

    def _seed_current_schema(self, schema_name: str, options):
        if not self._table_exists("school_permission"):
            self.stdout.write(
                self.style.WARNING(
                    f"[{schema_name}] skipped: table 'school_permission' not found. "
                    "Run tenant migrations first."
                )
            )
            return

        self.stdout.write(f"[{schema_name}] Seeding default permissions ...")
        self._seed(options, schema_name)

    def handle(self, *args, **options):
        schema_name = options.get("schema")
        all_tenants = options.get("all_tenants", False)

        if schema_name and all_tenants:
            self.stderr.write(self.style.ERROR("Use either --schema or --all-tenants, not both."))
            return

        if all_tenants:
            tenant_schemas = list(
                Tenant.objects.exclude(schema_name="public").values_list("schema_name", flat=True)
            )
            for tenant_schema in tenant_schemas:
                with schema_context(tenant_schema):
                    self._seed_current_schema(tenant_schema, options)
            return

        if schema_name:
            with schema_context(schema_name):
                self._seed_current_schema(schema_name, options)
            return

        current_schema = getattr(connection, "schema_name", "unknown")
        self._seed_current_schema(current_schema, options)
        if current_schema in ("public", "unknown"):
            self.stdout.write(
                self.style.WARNING(
                    "Tip: run with a tenant schema, e.g. "
                    "`python manage.py seed_default_permissions --schema=demo_school` or "
                    "`python manage.py seed_default_permissions --all-tenants`."
                )
            )

    def _seed(self, options, schema_name: str):
        from school.models import Permission as PermModel

        created_count = 0
        perm_map = {}

        for name, module, action, description in DEFAULT_PERMISSIONS:
            obj, created = PermModel.objects.get_or_create(
                name=name,
                defaults={"module": module, "action": action, "description": description},
            )
            perm_map[name] = obj
            if created:
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"[{schema_name}] Permissions: created={created_count}, "
                f"existing={len(DEFAULT_PERMISSIONS) - created_count}"
            )
        )

        if options.get("assign_roles"):
            self._assign_role_defaults(perm_map, schema_name)

        self.stdout.write(self.style.SUCCESS(f"[{schema_name}] Done - RBAC permissions seeded."))

    def _assign_role_defaults(self, perm_map, schema_name: str):
        from school.models import Role as RoleModel, RolePermissionGrant

        self.stdout.write(f"[{schema_name}] Assigning default permissions to built-in roles ...")
        grants_created = 0

        for role_name, perm_names in ROLE_DEFAULTS.items():
            try:
                role = RoleModel.objects.get(name=role_name)
            except RoleModel.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"[{schema_name}] Role {role_name!r} not found - skipping."))
                continue

            for permission_name in perm_names:
                perm = perm_map.get(permission_name)
                if perm is None:
                    continue
                _, created = RolePermissionGrant.objects.get_or_create(role=role, permission=perm)
                if created:
                    grants_created += 1

        self.stdout.write(
            self.style.SUCCESS(f"[{schema_name}] RolePermissionGrants: {grants_created} new grants added.")
        )
