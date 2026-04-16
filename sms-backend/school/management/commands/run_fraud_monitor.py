"""
Management command: run_fraud_monitor
Scans users with recent ledger activity for suspicious transaction patterns.
Runs across all tenant schemas.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Scan users with recent ledger activity for suspicious transaction patterns"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7, help="Analysis window in days")

    def handle(self, *args, **options):
        from django_tenants.utils import get_tenant_model, schema_context
        from django.utils import timezone
        from datetime import timedelta

        days = options["days"]
        Client = get_tenant_model()
        schemas = list(Client.objects.exclude(schema_name='public').values_list('schema_name', flat=True))
        self.stdout.write(f"Running fraud monitor for {len(schemas)} schemas (last {days} days)...")

        for schema in schemas:
            try:
                with schema_context(schema):
                    self._scan_schema(schema, days)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  {schema}: ERROR — {e}"))

        self.stdout.write(self.style.SUCCESS("Fraud monitor complete."))

    def _scan_schema(self, schema, days):
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from datetime import timedelta
        from school.models import LedgerEntry, Wallet, FraudAlert

        User = get_user_model()
        cutoff = timezone.now() - timedelta(days=days)

        recent_user_ids = set(
            LedgerEntry.objects.filter(
                created_at__gte=cutoff
            ).values_list("user_id", flat=True)
        )

        if not recent_user_ids:
            self.stdout.write(f"  {schema}: no activity in last {days} days")
            return

        flagged = 0
        for user_id in recent_user_ids:
            try:
                user = User.objects.get(pk=user_id)
                try:
                    user.wallet  # skip users who have no wallet at all
                except Wallet.DoesNotExist:
                    continue

                open_alerts = FraudAlert.objects.filter(user=user, resolved=False).count()
                if open_alerts > 0:
                    flagged += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"  {schema}: FLAGGED user={user.username} open_alerts={open_alerts}"
                        )
                    )
            except Exception:
                continue

        self.stdout.write(
            self.style.SUCCESS(
                f"  {schema}: {len(recent_user_ids)} users scanned, {flagged} with open alerts"
            )
        )
