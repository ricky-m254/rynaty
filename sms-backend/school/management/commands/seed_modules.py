from django.core.management.base import BaseCommand
from django.db import connection
from django_tenants.utils import schema_context
from clients.models import Tenant
from school.models import Module, TenantModule

ALL_MODULES = [
    ('CORE',         'Core Administration',              1),
    ('STUDENTS',     'Students',                         2),
    ('ADMISSIONS',   'Admissions',                       3),
    ('FINANCE',      'Finance',                          4),
    ('ACADEMICS',    'Academics',                        5),
    ('HR',           'Human Resources',                  6),
    ('STAFF',        'Staff Management',                 7),
    ('PARENTS',      'Parent Portal',                    8),
    ('LIBRARY',      'Library Management',               9),
    ('ASSETS',       'Assets and Inventory',            10),
    ('COMMUNICATION','Communication',                   11),
    ('REPORTING',    'Reporting and Analytics',         12),
    ('STORE',        'Store & Inventory',               13),
    ('DISPENSARY',   'Dispensary',                      14),
    ('TRANSPORT',    'Transport Management',            15),
    ('VISITOR_MGMT', 'Visitor Management & Gate Security', 16),
    ('EXAMINATIONS', 'Examinations',                   17),
    ('ALUMNI',       'Alumni Management',               18),
    ('HOSTEL',       'Hostel & Boarding',               19),
    ('PTM',          'Parent-Teacher Meetings',         20),
    ('SPORTS',       'Sports & Extracurricular',        21),
    ('CAFETERIA',    'Cafeteria & Food Service',        22),
    ('CURRICULUM',   'Curriculum & Lesson Planning',    23),
    ('MAINTENANCE',  'Maintenance Requests',            24),
    ('ELEARNING',    'E-Learning / LMS',               25),
    ('ANALYTICS',    'Executive Analytics Dashboard',   26),
    ('CLOCKIN',      'Clock-In & Biometric Attendance', 27),
    ('TIMETABLE',    'School Timetable',               28),
]


class Command(BaseCommand):
    help = 'Seeds default modules and activates them (TenantModule) for a tenant schema'

    def add_arguments(self, parser):
        parser.add_argument("--schema", type=str, default=None, help="Target tenant schema name.")
        parser.add_argument(
            "--all-tenants",
            action="store_true",
            help="Seed modules for all tenant schemas.",
        )

    @staticmethod
    def _table_exists(table_name: str) -> bool:
        return table_name in connection.introspection.table_names()

    def _seed_current_schema(self, schema_name: str) -> None:
        if not self._table_exists("school_module"):
            self.stdout.write(
                self.style.WARNING(
                    f"[{schema_name}] skipped: table 'school_module' not found. "
                    "Run tenant migrations first."
                )
            )
            return

        modules_created = 0
        tenant_modules_created = 0

        for key, name, sort_order in ALL_MODULES:
            module, was_created = Module.objects.get_or_create(
                key=key,
                defaults={'name': name, 'is_active': True},
            )
            if was_created:
                modules_created += 1
                self.stdout.write(self.style.SUCCESS(f"[{schema_name}] Created module: {key}"))

            tm, tm_created = TenantModule.objects.get_or_create(
                module=module,
                defaults={'is_enabled': True, 'sort_order': sort_order},
            )
            if tm_created:
                tenant_modules_created += 1
            elif tm.sort_order == 0 and sort_order != 0:
                tm.sort_order = sort_order
                tm.save(update_fields=['sort_order'])

        if modules_created == 0:
            self.stdout.write(self.style.WARNING(f"[{schema_name}] All {len(ALL_MODULES)} modules already existed."))
        else:
            self.stdout.write(self.style.SUCCESS(f"[{schema_name}] Created {modules_created} new Module records."))

        if tenant_modules_created == 0:
            self.stdout.write(self.style.WARNING(
                f"[{schema_name}] All {TenantModule.objects.count()} TenantModule activations already existed."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"[{schema_name}] Activated {tenant_modules_created} new TenantModule records "
                f"(total active: {TenantModule.objects.filter(is_enabled=True).count()})."
            ))

    def handle(self, *args, **options):
        schema_name = options.get("schema")
        all_tenants = options.get("all_tenants", False)

        if schema_name and all_tenants:
            self.stderr.write(self.style.ERROR("Use either --schema or --all-tenants, not both."))
            return

        if all_tenants:
            tenant_schemas = list(
                Tenant.objects.exclude(schema_name='public').values_list("schema_name", flat=True)
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
                    "`python manage.py seed_modules --schema=demo_school` or "
                    "`python manage.py seed_modules --all-tenants`."
                )
            )
