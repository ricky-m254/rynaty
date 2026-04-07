from django.core.management.base import BaseCommand
from django.db import connection
from django_tenants.utils import schema_context

from clients.models import Tenant
from school.models import Module, UserModuleAssignment


class Command(BaseCommand):
    help = "Backfill ADMISSIONS module access for users who already have STUDENTS access."

    def add_arguments(self, parser):
        parser.add_argument("--schema", type=str, default=None, help="Target tenant schema name.")
        parser.add_argument(
            "--all-tenants",
            action="store_true",
            help="Run backfill on all tenant schemas.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without saving.",
        )

    @staticmethod
    def _table_exists(table_name: str) -> bool:
        return table_name in connection.introspection.table_names()

    def _run_for_schema(self, schema_name: str, dry_run: bool) -> None:
        if not self._table_exists("school_module") or not self._table_exists("school_usermoduleassignment"):
            self.stdout.write(
                self.style.WARNING(
                    f"[{schema_name}] skipped: required school tables are missing. "
                    "Run tenant migrations first."
                )
            )
            return

        students_module = Module.objects.filter(key="STUDENTS").first()
        admissions_module = Module.objects.filter(key="ADMISSIONS").first()

        if not students_module:
            self.stdout.write(self.style.WARNING(f"[{schema_name}] skipped: STUDENTS module missing."))
            return
        if not admissions_module:
            self.stdout.write(self.style.WARNING(f"[{schema_name}] skipped: ADMISSIONS module missing. Run seed_modules first."))
            return

        student_assignments = UserModuleAssignment.objects.filter(
            module=students_module,
            is_active=True,
        ).select_related("user")

        created = 0
        reactivated = 0
        unchanged = 0

        for student_assignment in student_assignments:
            existing = UserModuleAssignment.objects.filter(
                user=student_assignment.user,
                module=admissions_module,
            ).first()

            if not existing:
                created += 1
                if not dry_run:
                    UserModuleAssignment.objects.create(
                        user=student_assignment.user,
                        module=admissions_module,
                        assigned_by=student_assignment.assigned_by,
                        is_active=True,
                    )
                continue

            if not existing.is_active:
                reactivated += 1
                if not dry_run:
                    existing.is_active = True
                    if existing.assigned_by_id is None:
                        existing.assigned_by = student_assignment.assigned_by
                    existing.save(update_fields=["is_active", "assigned_by"])
                continue

            unchanged += 1

        mode = "DRY-RUN" if dry_run else "APPLIED"
        self.stdout.write(
            self.style.SUCCESS(
                f"[{schema_name}] {mode}: created={created}, reactivated={reactivated}, unchanged={unchanged}"
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
            tenant_schemas = list(Tenant.objects.values_list("schema_name", flat=True))
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
                    "Tip: run with tenant schema, e.g. "
                    "`python manage.py backfill_admissions_module_access --schema=demo_school`."
                )
            )
