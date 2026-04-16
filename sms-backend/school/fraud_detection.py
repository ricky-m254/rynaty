"""
Fraud Detection Engine for SmartCampus.
Rule-based risk scoring for M-Pesa transactions.
Adapted for django-tenants: no school FK, uses tenant schema isolation.
"""
from decimal import Decimal
from datetime import timedelta

from django.utils import timezone
from django.db.models import Sum, Count, Avg


class FraudDetectionEngine:
    """
    Detects suspicious M-Pesa transactions using rule-based scoring.

    Rules:
    - Large amount (>100k KES): +40
    - Rapid velocity (>5 tx/min from same phone): +30
    - New user (first tx): +20 / newish (<3): +10
    - Daily volume limit exceeded: +25
    - Duplicate receipt: auto-block
    - Overdraft attempt: auto-block

    Thresholds:
    - score >= 90 → BLOCK
    - score >= 70 → FLAG
    - score < 70 → ALLOW
    """

    LARGE_AMOUNT_THRESHOLD = Decimal('100000')
    RAPID_TX_THRESHOLD = 5  # per minute
    HIGH_RISK_THRESHOLD = 70
    CRITICAL_RISK_THRESHOLD = 90
    MAX_DAILY_VOLUME = Decimal('300000')

    def __init__(self, user=None):
        self.user = user

    def check_deposit_risk(self, amount, phone):
        """
        Calculate risk score for a deposit. Returns (score, action, factors).
        """
        from school.models import MpesaTransaction, FraudAlert, RiskScoreLog

        amount = Decimal(str(amount))
        score = 0
        factors = []

        # Factor 1: Large amount
        if amount > self.LARGE_AMOUNT_THRESHOLD:
            score += 40
            factors.append({'factor': 'large_amount', 'weight': 40,
                'details': f'Amount {amount} > threshold {self.LARGE_AMOUNT_THRESHOLD}'})

        # Factor 2: Velocity check
        try:
            recent_count = MpesaTransaction.objects.filter(
                phone_number=phone,
                created_at__gte=timezone.now() - timedelta(minutes=1)
            ).count()
            if recent_count > self.RAPID_TX_THRESHOLD:
                score += 30
                factors.append({'factor': 'rapid_transactions', 'weight': 30,
                    'details': f'{recent_count} tx in last minute from {phone}'})
        except Exception:
            pass

        # Factor 3: New user
        if self.user:
            try:
                user_tx_count = MpesaTransaction.objects.filter(
                    user=self.user, status='SUCCESS'
                ).count()
                if user_tx_count == 0:
                    score += 20
                    factors.append({'factor': 'new_user', 'weight': 20,
                        'details': 'First successful transaction'})
                elif user_tx_count < 3:
                    score += 10
                    factors.append({'factor': 'newish_user', 'weight': 10,
                        'details': f'Only {user_tx_count} previous transactions'})
            except Exception:
                pass

        # Factor 4: Daily volume
        if self.user:
            try:
                daily_total = MpesaTransaction.objects.filter(
                    user=self.user,
                    created_at__date=timezone.now().date(),
                    status='SUCCESS'
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

                if daily_total + amount > self.MAX_DAILY_VOLUME:
                    score += 25
                    factors.append({'factor': 'daily_volume_limit', 'weight': 25,
                        'details': f'Daily {daily_total} + {amount} > {self.MAX_DAILY_VOLUME}'})
            except Exception:
                pass

        # Determine action
        action = 'ALLOW'
        alert = None
        if score >= self.CRITICAL_RISK_THRESHOLD:
            action = 'BLOCK'
            alert = self._create_alert('CRITICAL', 'HIGH_RISK_TRANSACTION_BLOCKED',
                f'High risk transaction blocked: score {score}',
                {'score': score, 'factors': factors, 'amount': str(amount)})
        elif score >= self.HIGH_RISK_THRESHOLD:
            action = 'FLAG'
            alert = self._create_alert('WARNING', 'ELEVATED_RISK_TRANSACTION',
                f'Elevated risk transaction: score {score}',
                {'score': score, 'factors': factors, 'amount': str(amount)})

        # Log risk score
        try:
            RiskScoreLog.objects.create(
                user=self.user,
                transaction_amount=amount,
                risk_score=score,
                factors=factors,
                action_taken=action,
                alert=alert,
            )
        except Exception:
            pass

        return score, action, factors

    def check_duplicate_receipt(self, receipt):
        """Returns True if duplicate receipt detected."""
        if not receipt:
            return False
        from school.models import MpesaTransaction
        exists = MpesaTransaction.objects.filter(mpesa_receipt_number=receipt).exists()
        if exists:
            self._create_alert('CRITICAL', 'DUPLICATE_RECEIPT',
                f'Duplicate M-Pesa receipt: {receipt}', {'receipt': receipt})
            return True
        return False

    def check_reconciliation_mismatch(self, mpesa_amount, db_amount, receipt):
        """Detects amount mismatches between M-Pesa and DB."""
        if Decimal(str(mpesa_amount)) != Decimal(str(db_amount)):
            self._create_alert('CRITICAL', 'RECONCILIATION_MISMATCH',
                f'Amount mismatch for {receipt}: M-Pesa={mpesa_amount}, DB={db_amount}',
                {'receipt': receipt, 'mpesa_amount': str(mpesa_amount), 'db_amount': str(db_amount)})
            return True
        return False

    def check_overdraft_attempt(self, amount, wallet):
        """Returns True if overdraft attempted."""
        if Decimal(str(amount)) > wallet.balance:
            self._create_alert('CRITICAL', 'OVERDRAFT_ATTEMPT',
                f'Overdraft attempt: {amount} > balance {wallet.balance}',
                {'attempted_amount': str(amount), 'available_balance': str(wallet.balance)})
            return True
        return False

    def is_whitelisted(self, phone=None, ip=None):
        """Check if phone or IP is whitelisted."""
        from school.models import FraudWhitelist
        if phone:
            entry = FraudWhitelist.objects.filter(
                whitelist_type='PHONE', value=phone, is_active=True
            ).first()
            if entry and entry.is_valid():
                return True
        if ip:
            entry = FraudWhitelist.objects.filter(
                whitelist_type='IP', value=ip, is_active=True
            ).first()
            if entry and entry.is_valid():
                return True
        return False

    def _create_alert(self, level, alert_type, message, metadata=None):
        from school.models import FraudAlert
        try:
            return FraudAlert.objects.create(
                level=level,
                alert_type=alert_type,
                message=message,
                reference=metadata.get('receipt', '') if metadata else '',
                metadata=metadata or {},
                user=self.user,
            )
        except Exception:
            return None
