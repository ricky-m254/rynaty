"""
Management command: reconcile_transactions
Reconciles wallet balances against ledger entries for all users.
Run: python manage.py tenant_command reconcile_transactions --schema=school1
"""
from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.utils import timezone


class Command(BaseCommand):
    help = "Reconcile wallet balances against ledger entries"

    def add_arguments(self, parser):
        parser.add_argument("--fix", action="store_true", help="Auto-fix mismatches by recalculating from ledger")
        parser.add_argument("--dry-run", action="store_true", help="Report only, do not fix")

    def handle(self, *args, **options):
        from school.models import Wallet, LedgerEntry, LedgerReconciliation

        self.stdout.write("Starting ledger reconciliation...")
        mismatches = []
        checked = 0

        for wallet in Wallet.objects.select_related("user"):
            ledger_bal = LedgerEntry.objects.filter(user=wallet.user).aggregate(
                total=Sum("amount")
            )["total"] or 0

            diff = abs(float(wallet.balance) - float(ledger_bal))
            if diff > 0.01:
                mismatches.append({
                    "user_id": wallet.user_id,
                    "username": wallet.user.username,
                    "wallet_balance": str(wallet.balance),
                    "ledger_balance": str(ledger_bal),
                    "difference": str(float(wallet.balance) - float(ledger_bal)),
                })
                self.stdout.write(
                    self.style.WARNING(
                        f"MISMATCH: user={wallet.user.username} wallet={wallet.balance} ledger={ledger_bal}"
                    )
                )
                if options["fix"] and not options["dry_run"]:
                    from decimal import Decimal
                    wallet.balance = Decimal(str(ledger_bal))
                    wallet.save(update_fields=["balance"])
                    self.stdout.write(self.style.SUCCESS(f"  → Fixed: balance set to {ledger_bal}"))
            checked += 1

        LedgerReconciliation.objects.create(
            status="BALANCED" if not mismatches else "MISMATCH",
            start_date=timezone.now().date(),
            end_date=timezone.now().date(),
            total_entries=LedgerEntry.objects.count(),
            discrepancies=mismatches,
            completed_at=timezone.now(),
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Reconciliation complete. Checked: {checked}, Mismatches: {len(mismatches)}"
            )
        )
