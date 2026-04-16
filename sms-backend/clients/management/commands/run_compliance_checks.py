"""
Management command: run_compliance_checks
Runs compliance checks across all tenant schemas.
Flags schools with overdue invoices, high wallet balances, etc.
Run: python manage.py run_compliance_checks
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run compliance checks across all tenant schemas"

    def add_arguments(self, parser):
        parser.add_argument("--schema", help="Run for a specific schema only")

    def handle(self, *args, **options):
        from clients.models import Tenant
        from django_tenants.utils import schema_context

        schemas = []
        if options["schema"]:
            schemas = [options["schema"]]
        else:
            schemas = list(
                Tenant.objects.exclude(schema_name="public")
                .values_list("schema_name", flat=True)
            )

        self.stdout.write(f"Running compliance checks for {len(schemas)} schemas...")

        for schema_name in schemas:
            try:
                with schema_context(schema_name):
                    self._check_schema(schema_name)
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error in {schema_name}: {e}")
                )

        self.stdout.write(self.style.SUCCESS("Compliance checks complete."))

    def _check_schema(self, schema_name):
        from school.models import Wallet, FraudAlert, Invoice
        from school.compliance import ComplianceEngine
        from decimal import Decimal

        engine = ComplianceEngine()
        issues = []

        # Check 1: Wallets over balance limit
        max_bal = engine.limits.get("MAX_STUDENT_BALANCE", Decimal("100000"))
        over_limit = Wallet.objects.filter(balance__gt=max_bal).count()
        if over_limit > 0:
            issues.append(f"{over_limit} wallets over balance limit {max_bal}")
            FraudAlert.objects.create(
                level="WARNING",
                alert_type="DAILY_VOLUME_LIMIT",
                message=f"{over_limit} wallets exceed max balance {max_bal} in {schema_name}",
                metadata={"schema_name": schema_name, "count": over_limit},
            )

        # Check 2: Overdue invoices (if Invoice model exists)
        try:
            from django.utils import timezone
            overdue = Invoice.objects.filter(
                status__in=["UNPAID", "PARTIAL"],
                due_date__lt=timezone.now().date(),
            ).count()
            if overdue > 10:
                issues.append(f"{overdue} overdue invoices")
        except Exception:
            pass

        if issues:
            self.stdout.write(
                self.style.WARNING(f"  {schema_name}: {', '.join(issues)}")
            )
        else:
            self.stdout.write(f"  {schema_name}: OK")
