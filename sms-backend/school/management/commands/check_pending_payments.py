"""
Management command: check_pending_payments
Checks for PaymentGatewayTransactions stuck in PENDING state > 30 minutes.
Run: python manage.py tenant_command check_pending_payments --schema=school1
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = "Flag/expire PaymentGatewayTransactions stuck in PENDING for too long"

    def add_arguments(self, parser):
        parser.add_argument("--minutes", type=int, default=30,
            help="Minutes threshold to consider a transaction stuck (default: 30)")
        parser.add_argument("--expire", action="store_true",
            help="Mark stuck transactions as FAILED")

    def handle(self, *args, **options):
        from school.models import PaymentGatewayTransaction, FraudAlert

        threshold = timezone.now() - timedelta(minutes=options["minutes"])
        stuck = PaymentGatewayTransaction.objects.filter(
            status="PENDING",
            created_at__lt=threshold,
        )

        self.stdout.write(f"Found {stuck.count()} stuck PENDING transactions (>{options['minutes']} min)")

        for tx in stuck:
            self.stdout.write(f"  STUCK: {tx.external_id} | {tx.amount} KES | created {tx.created_at}")
            if options["expire"]:
                tx.status = "FAILED"
                tx.payload["auto_expired"] = True
                tx.payload["expired_at"] = timezone.now().isoformat()
                tx.save(update_fields=["status", "payload", "updated_at"])

                # Log fraud alert for large stuck transactions
                if tx.amount and tx.amount > 10000:
                    FraudAlert.objects.create(
                        level="WARNING",
                        alert_type="MANY_FAILURES",
                        message=f"Large transaction {tx.external_id} auto-expired after {options['minutes']} min",
                        reference=tx.external_id,
                        metadata={"amount": str(tx.amount), "created_at": tx.created_at.isoformat()},
                    )

                self.stdout.write(self.style.WARNING(f"  → Expired: {tx.external_id}"))

        if not options["expire"]:
            self.stdout.write("Dry run — use --expire to actually expire them")
