"""
Management command: run_fraud_monitor
Runs fraud pattern checks for all users with recent transaction activity.
Run cross-tenant: python manage.py run_fraud_monitor
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
        schemas = Client.objects.exclude(schema_name='public').values_list('schema_name', flat=True)
        self.stdout.write(f"Running fraud monitor for {schemas.count()} schemas (last {days} days)...")

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
        from school.fraud_detection import FraudDetectionEngine
        from school.models import LedgerEntry, Wallet

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
                wallet = Wallet.get_or_create_for_user(user)
                engine = FraudDetectionEngine(user=user)
                engine.check_overdraft_attempt(amount=0, wallet=wallet)
                score, action, factors = engine.check_deposit_risk(amount=0, phone="")
                if action in ("FLAG", "BLOCK"):
                    flagged += 1
                    self.stdout.write(
                        self.style.WARNING(f"  {schema}: FLAGGED user={user.username} score={score}")
                    )
            except Exception:
                continue

        self.stdout.write(
            self.style.SUCCESS(
                f"  {schema}: {len(recent_user_ids)} users scanned, {flagged} flagged"
            )
        )
