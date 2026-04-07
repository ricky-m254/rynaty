from collections import Counter

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import connection
from django_tenants.utils import schema_context

from clients.models import Tenant
from school.models import Module, UserModuleAssignment
from school.role_scope import (
    get_role_module_baseline,
    get_user_role_name,
    get_user_scope_profile,
)


User = get_user_model()


class Command(BaseCommand):
    help = "Backfill baseline UserModuleAssignment rows from the Session 5 role scope map."

    def add_arguments(self, parser):
        parser.add_argument("--schema", type=str, default=None, help="Target tenant schema name.")
        parser.add_argument(
            "--all-tenants",
            action="store_true",
            help="Run the backfill for all tenant schemas.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without saving.",
        )

    @staticmethod
    def _table_exists(table_name: str) -> bool:
        return table_name in connection.introspection.table_names()

    def _run_for_schema(self, schema_name: str, dry_run: bool) -> None:
        required_tables = {
            "school_module",
            "school_usermoduleassignment",
            "school_userprofile",
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

        modules = {
            module.key.upper(): module
            for module in Module.objects.filter(is_active=True).order_by("key")
        }
        if not modules:
            self.stdout.write(
                self.style.WARNING(
                    f"[{schema_name}] skipped: no active module definitions found. Run seed_modules first."
                )
            )
            return

        users = list(
            User.objects.filter(is_active=True)
            .select_related("userprofile__role")
            .order_by("username")
        )
        if not users:
            self.stdout.write(self.style.WARNING(f"[{schema_name}] no active users found."))
            return

        assignment_map = {}
        for assignment in UserModuleAssignment.objects.filter(
            user__in=users,
            module__in=modules.values(),
        ).select_related("module", "user"):
            assignment_map.setdefault(assignment.user_id, {})[assignment.module.key.upper()] = assignment

        scoped_users = 0
        portal_only_users = 0
        unresolved_users = []
        missing_module_counts = Counter()
        created = 0
        reactivated = 0
        unchanged = 0

        for user in users:
            role_name = get_user_role_name(user)
            scope_profile = get_user_scope_profile(user)
            if not scope_profile:
                unresolved_users.append(user.username)
                continue

            scoped_users += 1
            desired_keys = get_role_module_baseline(role_name)
            missing_keys = [module_key for module_key in desired_keys if module_key not in modules]
            for module_key in missing_keys:
                missing_module_counts[module_key] += 1

            desired_keys = [module_key for module_key in desired_keys if module_key in modules]
            if not desired_keys:
                portal_only_users += 1
                continue

            existing_by_module = assignment_map.setdefault(user.id, {})
            # Only ensure the required baseline exists; manual extras stay untouched.
            for module_key in desired_keys:
                existing = existing_by_module.get(module_key)
                if existing is None:
                    created += 1
                    if not dry_run:
                        existing = UserModuleAssignment.objects.create(
                            user=user,
                            module=modules[module_key],
                            assigned_by=None,
                            is_active=True,
                        )
                    else:
                        existing = None
                    if existing is not None:
                        existing_by_module[module_key] = existing
                    continue

                if not existing.is_active:
                    reactivated += 1
                    if not dry_run:
                        existing.is_active = True
                        existing.save(update_fields=["is_active"])
                    continue

                unchanged += 1

        mode = "DRY-RUN" if dry_run else "APPLIED"
        self.stdout.write(
            self.style.SUCCESS(
                f"[{schema_name}] {mode}: users={len(users)}, scoped={scoped_users}, "
                f"portal_only={portal_only_users}, created={created}, "
                f"reactivated={reactivated}, unchanged={unchanged}"
            )
        )

        if unresolved_users:
            preview = ", ".join(unresolved_users[:10])
            if len(unresolved_users) > 10:
                preview = f"{preview}, ..."
            self.stdout.write(
                self.style.WARNING(
                    f"[{schema_name}] skipped users without a mapped scope profile: {preview}"
                )
            )

        if missing_module_counts:
            summary = ", ".join(
                f"{module_key} x{count}"
                for module_key, count in sorted(missing_module_counts.items())
            )
            self.stdout.write(
                self.style.WARNING(
                    f"[{schema_name}] baseline modules missing from the schema: {summary}"
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
                    "`python manage.py backfill_role_module_baselines --schema=demo_school` or "
                    "`python manage.py backfill_role_module_baselines --all-tenants`."
                )
            )
