from django.core.management import call_command
from django.core.management.base import BaseCommand

from clients.models import Domain, Tenant


class Command(BaseCommand):
    help = "Creates a new school tenant, links its domain, migrates the schema, and seeds the baseline catalog."

    def add_arguments(self, parser):
        parser.add_argument("--schema_name", type=str, help="Schema name (e.g., test_school)")
        parser.add_argument("--name", type=str, help="Display name (e.g., Test High School)")
        parser.add_argument("--domain", type=str, help="Domain (e.g., test.localhost)")

    def handle(self, *args, **options):
        schema_name = options["schema_name"]
        name = options["name"]
        domain = options["domain"]

        if not all([schema_name, name, domain]):
            self.stdout.write(
                self.style.ERROR("Missing arguments. Usage: --schema_name 'x' --name 'y' --domain 'z'")
            )
            return

        try:
            tenant = Tenant.objects.create(
                schema_name=schema_name,
                name=name,
                paid_until="2030-01-01",
            )
            self.stdout.write(self.style.SUCCESS(f"Created tenant '{name}'."))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Error creating tenant: {exc}"))
            return

        try:
            Domain.objects.create(
                domain=domain,
                tenant=tenant,
                is_primary=True,
            )
            self.stdout.write(self.style.SUCCESS(f"Linked domain '{domain}'."))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Error creating domain: {exc}"))
            return

        try:
            self.stdout.write(f"Migrating schema '{schema_name}'...")
            call_command("migrate_schemas", "--schema", schema_name)
            self.stdout.write(self.style.SUCCESS(f"Schema '{schema_name}' migrated successfully."))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Error migrating schema: {exc}"))
            return

        try:
            call_command("seed_roles", f"--schema={schema_name}")
            call_command("seed_modules", f"--schema={schema_name}")
            call_command("seed_default_permissions", f"--schema={schema_name}", "--assign-roles")
            self.stdout.write(
                self.style.SUCCESS(
                    f"Seeded baseline roles, modules, and RBAC defaults for '{schema_name}'."
                )
            )
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Error seeding tenant baseline: {exc}"))
            return

        self.stdout.write(self.style.SUCCESS(f"School '{name}' is ready."))
