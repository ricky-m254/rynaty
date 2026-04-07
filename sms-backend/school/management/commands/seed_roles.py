from django.core.management.base import BaseCommand
from django.db import connection
from django_tenants.utils import schema_context

from clients.models import Tenant
from school.models import Role
from school.role_scope import iter_seed_role_definitions


class Command(BaseCommand):
    help = "Creates the default Session 5 role catalog for a tenant schema."

    def add_arguments(self, parser):
        parser.add_argument("--schema", type=str, default=None, help="Target tenant schema name.")
        parser.add_argument(
            "--all-tenants",
            action="store_true",
            help="Seed roles for all tenant schemas.",
        )

    @staticmethod
    def _table_exists(table_name: str) -> bool:
        return table_name in connection.introspection.table_names()

    def _seed_current_schema(self, schema_name: str) -> None:
        if not self._table_exists("school_role"):
            self.stdout.write(
                self.style.WARNING(
                    f"[{schema_name}] skipped: table 'school_role' not found. Run tenant migrations first."
                )
            )
            return

        created_count = 0
        updated_count = 0

        for role_name, description in iter_seed_role_definitions():
            role, created = Role.objects.get_or_create(
                name=role_name,
                defaults={"description": description},
            )
            if created:
                created_count += 1
                continue

            if role.description != description:
                role.description = description
                role.save(update_fields=["description"])
                updated_count += 1

        if created_count == 0 and updated_count == 0:
            self.stdout.write(self.style.WARNING(f"[{schema_name}] roles already aligned."))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"[{schema_name}] roles aligned: created={created_count}, updated={updated_count}"
            )
        )

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
                    self._seed_current_schema(tenant_schema)
            return

        if schema_name:
            with schema_context(schema_name):
                self._seed_current_schema(schema_name)
            return

        current_schema = getattr(connection, "schema_name", "unknown")
        self._seed_current_schema(current_schema)
        if current_schema in ("public", "unknown"):
            self.stdout.write(
                self.style.WARNING(
                    "Tip: run with a tenant schema, e.g. "
                    "`python manage.py seed_roles --schema=demo_school` or "
                    "`python manage.py seed_roles --all-tenants`."
                )
            )
