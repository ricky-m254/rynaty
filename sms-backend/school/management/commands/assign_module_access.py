from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import connection
from django_tenants.utils import schema_context

from clients.models import Tenant
from school.models import Module, UserModuleAssignment


User = get_user_model()


class Command(BaseCommand):
    help = "Assign module access to selected users or all active users in tenant schema."

    def add_arguments(self, parser):
        parser.add_argument("--schema", type=str, default=None, help="Target tenant schema name.")
        parser.add_argument(
            "--all-tenants",
            action="store_true",
            help="Run assignment for all tenant schemas.",
        )
        parser.add_argument(
            "--usernames",
            type=str,
            default="",
            help="Comma-separated usernames (e.g. admin,teacher1).",
        )
        parser.add_argument(
            "--all-active-users",
            action="store_true",
            help="Target all active users in schema.",
        )
        parser.add_argument(
            "--include-students",
            action="store_true",
            help="Assign STUDENTS module in addition to ADMISSIONS.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without writing.",
        )

    @staticmethod
    def _table_exists(table_name: str) -> bool:
        return table_name in connection.introspection.table_names()

    @staticmethod
    def _parse_usernames(raw: str):
        if not raw:
            return []
        return [value.strip() for value in raw.split(",") if value.strip()]

    def _resolve_users(self, usernames, all_active_users):
        if all_active_users:
            return User.objects.filter(is_active=True).order_by("username"), []

        if not usernames:
            return User.objects.none(), []

        user_qs = User.objects.filter(username__in=usernames).order_by("username")
        found = set(user_qs.values_list("username", flat=True))
        missing = sorted(set(usernames) - found)
        return user_qs, missing

    def _assign_for_schema(self, schema_name: str, usernames, all_active_users, include_students: bool, dry_run: bool):
        if not self._table_exists("school_module") or not self._table_exists("school_usermoduleassignment"):
            self.stdout.write(
                self.style.WARNING(
                    f"[{schema_name}] skipped: required school tables missing. Run tenant migrations first."
                )
            )
            return

        users, missing_users = self._resolve_users(usernames, all_active_users)
        if missing_users:
            self.stdout.write(self.style.WARNING(f"[{schema_name}] usernames not found: {', '.join(missing_users)}"))

        user_count = users.count()
        if user_count == 0:
            self.stdout.write(self.style.WARNING(f"[{schema_name}] no target users resolved."))
            return

        module_keys = ["ADMISSIONS"]
        if include_students:
            module_keys.append("STUDENTS")

        modules = {m.key: m for m in Module.objects.filter(key__in=module_keys)}
        missing_modules = [key for key in module_keys if key not in modules]
        if missing_modules:
            self.stdout.write(
                self.style.WARNING(
                    f"[{schema_name}] missing module definitions: {', '.join(missing_modules)}. "
                    "Run `python manage.py seed_modules --schema=<schema>` first."
                )
            )
            return

        summary = {}
        for module_key in module_keys:
            module = modules[module_key]
            created = 0
            reactivated = 0
            unchanged = 0

            for user in users:
                existing = UserModuleAssignment.objects.filter(user=user, module=module).first()
                if not existing:
                    created += 1
                    if not dry_run:
                        UserModuleAssignment.objects.create(
                            user=user,
                            module=module,
                            assigned_by=None,
                            is_active=True,
                        )
                    continue

                if not existing.is_active:
                    reactivated += 1
                    if not dry_run:
                        existing.is_active = True
                        existing.save(update_fields=["is_active"])
                    continue

                unchanged += 1

            summary[module_key] = {
                "created": created,
                "reactivated": reactivated,
                "unchanged": unchanged,
            }

        mode = "DRY-RUN" if dry_run else "APPLIED"
        self.stdout.write(self.style.SUCCESS(f"[{schema_name}] {mode}: users={user_count}"))
        for key, stats in summary.items():
            self.stdout.write(
                self.style.SUCCESS(
                    f"[{schema_name}] {key}: created={stats['created']}, "
                    f"reactivated={stats['reactivated']}, unchanged={stats['unchanged']}"
                )
            )

    def handle(self, *args, **options):
        schema_name = options.get("schema")
        all_tenants = options.get("all_tenants", False)
        usernames = self._parse_usernames(options.get("usernames", ""))
        all_active_users = options.get("all_active_users", False)
        include_students = options.get("include_students", False)
        dry_run = options.get("dry_run", False)

        if schema_name and all_tenants:
            self.stderr.write(self.style.ERROR("Use either --schema or --all-tenants, not both."))
            return

        if not all_active_users and not usernames:
            self.stderr.write(
                self.style.ERROR(
                    "Choose target users with either --all-active-users or --usernames=user1,user2."
                )
            )
            return

        if all_tenants:
            tenant_schemas = list(Tenant.objects.values_list("schema_name", flat=True))
            for tenant_schema in tenant_schemas:
                with schema_context(tenant_schema):
                    self._assign_for_schema(
                        tenant_schema,
                        usernames=usernames,
                        all_active_users=all_active_users,
                        include_students=include_students,
                        dry_run=dry_run,
                    )
            return

        if schema_name:
            with schema_context(schema_name):
                self._assign_for_schema(
                    schema_name,
                    usernames=usernames,
                    all_active_users=all_active_users,
                    include_students=include_students,
                    dry_run=dry_run,
                )
            return

        current_schema = getattr(connection, "schema_name", "unknown")
        self._assign_for_schema(
            current_schema,
            usernames=usernames,
            all_active_users=all_active_users,
            include_students=include_students,
            dry_run=dry_run,
        )
        if current_schema in ("public", "unknown"):
            self.stdout.write(
                self.style.WARNING(
                    "Tip: run with tenant schema, e.g. "
                    "`python manage.py assign_module_access --schema=demo_school --all-active-users`."
                )
            )
