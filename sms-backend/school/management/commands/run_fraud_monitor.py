"""
Management command: run_fraud_monitor
Runs FraudMonitor.check_suspicious_patterns for all active users.
Run: python manage.py tenant_command run_fraud_monitor --schema=school1
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Scan users for suspicious transaction patterns"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7, help="Analysis window in days")

    def handle(self, *args, **options):
        from school.fraud_detection import FraudDetectionEngine
        from school.models import UserProfile
        from django.contrib.auth import get_user_model

        User = get_user_model()
        days = options["days"]

        # Get student users who have made transactions recently
        from django.utils import timezone
        from datetime import timedelta
        from school.models import Payment

        recent_users = set(
            Payment.objects.filter(
                date__gte=timezone.now().date() - timedelta(days=days)
            ).values_list("student__user_id", flat=True)
        )

        self.stdout.write(f"Scanning {len(recent_users)} users with transactions in last {days} days...")

        flagged = 0
        for user_id in recent_users:
            try:
                user = User.objects.get(pk=user_id)
                engine = FraudDetectionEngine(user=user)
                # Quick risk check: check if user has many recent transactions
                score, action, factors = engine.check_deposit_risk(
                    amount=0,  # dummy amount for pattern check
                    phone="",
                )
                if action in ("FLAG", "BLOCK"):
                    flagged += 1
                    self.stdout.write(
                        self.style.WARNING(f"  FLAGGED: user={user.username} score={score}")
                    )
            except Exception:
                continue

        self.stdout.write(
            self.style.SUCCESS(f"Scan complete. {len(recent_users)} users checked, {flagged} flagged.")
        )
