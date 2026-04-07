from django.core.management.base import BaseCommand
from django.db import connection
from django_tenants.utils import schema_context

from clients.models import Tenant
from hr.models import Department as HrDepartment
from staff_mgmt.bridge import (
    ensure_school_department_shadow,
    sync_staff_attendance_to_hr,
    sync_staff_department_to_hr,
    sync_staff_member_to_hr,
)
from staff_mgmt.models import StaffAttendance, StaffDepartment, StaffMember


class Command(BaseCommand):
    help = "Repair staff-to-HR bridge links and HR-to-school department shadows for tenant schemas."

    def add_arguments(self, parser):
        parser.add_argument("--schema", type=str, default=None, help="Target tenant schema name.")
        parser.add_argument(
            "--all-tenants",
            action="store_true",
            help="Run the repair for all tenant schemas.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report current bridge gaps without writing changes.",
        )

    @staticmethod
    def _table_exists(table_name: str) -> bool:
        return table_name in connection.introspection.table_names()

    def _run_for_schema(self, schema_name: str, dry_run: bool) -> None:
        required_tables = {
            "staff_mgmt_staffmember",
            "staff_mgmt_staffdepartment",
            "staff_mgmt_staffattendance",
            "hr_department",
            "hr_employee",
            "school_department",
        }
        missing_tables = sorted(table_name for table_name in required_tables if not self._table_exists(table_name))
        if missing_tables:
            self.stdout.write(
                self.style.WARNING(
                    f"[{schema_name}] skipped: required tables missing ({', '.join(missing_tables)}). "
                    "Run tenant migrations first."
                )
            )
            return

        before = {
            "staff_without_hr_employee": StaffMember.objects.filter(is_active=True, hr_employee__isnull=True).count(),
            "departments_without_hr": StaffDepartment.objects.filter(is_active=True, hr_department__isnull=True).count(),
            "attendance_without_hr": StaffAttendance.objects.filter(is_active=True, hr_attendance__isnull=True).count(),
            "hr_departments_without_school_shadow": HrDepartment.objects.filter(
                is_active=True,
                school_department__isnull=True,
            ).count(),
        }

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[{schema_name}] DRY-RUN: "
                    f"staff_without_hr_employee={before['staff_without_hr_employee']}, "
                    f"departments_without_hr={before['departments_without_hr']}, "
                    f"attendance_without_hr={before['attendance_without_hr']}, "
                    f"hr_departments_without_school_shadow={before['hr_departments_without_school_shadow']}"
                )
            )
            return

        counters = {
            "staff_linked": 0,
            "staff_department_refreshed": 0,
            "departments_linked": 0,
            "school_shadows_linked": 0,
            "attendance_linked": 0,
        }

        for department in StaffDepartment.objects.filter(is_active=True).select_related("parent", "head", "hr_department"):
            previous_hr_department_id = department.hr_department_id
            hr_department = sync_staff_department_to_hr(department)
            department.refresh_from_db(fields=["hr_department"])
            if previous_hr_department_id is None and department.hr_department_id:
                counters["departments_linked"] += 1
            previous_shadow_id = hr_department.school_department_id
            ensure_school_department_shadow(hr_department)
            hr_department.refresh_from_db(fields=["school_department"])
            if previous_shadow_id is None and hr_department.school_department_id:
                counters["school_shadows_linked"] += 1

        for hr_department in HrDepartment.objects.filter(is_active=True).select_related("school_department", "head"):
            previous_shadow_id = hr_department.school_department_id
            ensure_school_department_shadow(hr_department)
            hr_department.refresh_from_db(fields=["school_department"])
            if previous_shadow_id is None and hr_department.school_department_id:
                counters["school_shadows_linked"] += 1

        for staff_member in StaffMember.objects.filter(is_active=True).select_related("hr_employee"):
            previous_hr_employee_id = staff_member.hr_employee_id
            previous_department_id = (
                staff_member.hr_employee.department_id if staff_member.hr_employee_id else None
            )
            employee = sync_staff_member_to_hr(staff_member)
            staff_member.refresh_from_db(fields=["hr_employee"])
            if previous_hr_employee_id is None and staff_member.hr_employee_id:
                counters["staff_linked"] += 1
            employee.refresh_from_db(fields=["department"])
            if employee.department_id != previous_department_id:
                counters["staff_department_refreshed"] += 1

        for attendance in StaffAttendance.objects.filter(is_active=True).select_related(
            "staff",
            "staff__hr_employee",
            "hr_attendance",
        ):
            previous_hr_attendance_id = attendance.hr_attendance_id
            sync_staff_attendance_to_hr(attendance)
            attendance.refresh_from_db(fields=["hr_attendance"])
            if previous_hr_attendance_id is None and attendance.hr_attendance_id:
                counters["attendance_linked"] += 1

        after = {
            "staff_without_hr_employee": StaffMember.objects.filter(is_active=True, hr_employee__isnull=True).count(),
            "departments_without_hr": StaffDepartment.objects.filter(is_active=True, hr_department__isnull=True).count(),
            "attendance_without_hr": StaffAttendance.objects.filter(is_active=True, hr_attendance__isnull=True).count(),
            "hr_departments_without_school_shadow": HrDepartment.objects.filter(
                is_active=True,
                school_department__isnull=True,
            ).count(),
        }

        self.stdout.write(
            self.style.SUCCESS(
                f"[{schema_name}] APPLIED: "
                f"staff_linked={counters['staff_linked']}, "
                f"staff_department_refreshed={counters['staff_department_refreshed']}, "
                f"departments_linked={counters['departments_linked']}, "
                f"school_shadows_linked={counters['school_shadows_linked']}, "
                f"attendance_linked={counters['attendance_linked']}"
            )
        )
        self.stdout.write(
            self.style.WARNING(
                f"[{schema_name}] Remaining gaps: "
                f"staff_without_hr_employee={after['staff_without_hr_employee']}, "
                f"departments_without_hr={after['departments_without_hr']}, "
                f"attendance_without_hr={after['attendance_without_hr']}, "
                f"hr_departments_without_school_shadow={after['hr_departments_without_school_shadow']}"
            )
        )

    def handle(self, *args, **options):
        schema_name = options.get("schema")
        all_tenants = options.get("all_tenants", False)
        dry_run = options.get("dry_run", False)

        if schema_name and all_tenants:
            self.stderr.write(self.style.ERROR("Use either --schema or --all-tenants, not both."))
            return

        if all_tenants:
            tenant_schemas = list(
                Tenant.objects.exclude(schema_name="public").values_list("schema_name", flat=True)
            )
            for tenant_schema in tenant_schemas:
                with schema_context(tenant_schema):
                    self._run_for_schema(tenant_schema, dry_run)
            return

        if schema_name:
            with schema_context(schema_name):
                self._run_for_schema(schema_name, dry_run)
            return

        current_schema = getattr(connection, "schema_name", "unknown")
        self._run_for_schema(current_schema, dry_run)
        if current_schema in ("public", "unknown"):
            self.stdout.write(
                self.style.WARNING(
                    "Tip: run with a tenant schema, e.g. "
                    "`python manage.py repair_people_org_bridges --schema=demo_school` or "
                    "`python manage.py repair_people_org_bridges --all-tenants`."
                )
            )
