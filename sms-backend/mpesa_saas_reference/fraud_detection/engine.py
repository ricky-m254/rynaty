"""
Fraud detection engine for identifying suspicious transactions.
Implements rule-based and risk-scoring detection.
"""

from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, Count

from .models import Alert, RiskScoreLog
from payments.models import Transaction


class FraudDetectionEngine:
    """
    Engine for detecting and preventing fraudulent transactions.
    
    Implements multiple detection rules:
    - Large amount detection
    - Rapid transaction detection (velocity check)
    - Duplicate receipt detection
    - New user risk
    - Phone mismatch detection
    - Overdraft attempt detection
    """
    
    # Thresholds (can be made configurable per school)
    LARGE_AMOUNT_THRESHOLD = 100000  # KES - Flag large transactions
    RAPID_TX_THRESHOLD = 5  # Transactions per minute
    HIGH_RISK_THRESHOLD = 70  # Score to flag
    CRITICAL_RISK_THRESHOLD = 90  # Score to block
    MAX_DAILY_VOLUME = 300000  # Max daily volume per user
    
    def __init__(self, school, user=None):
        """
        Initialize fraud detection engine.
        
        Args:
            school: School context
            user: Optional user being evaluated
        """
        self.school = school
        self.user = user
    
    def check_deposit_risk(self, amount, phone):
        """
        Calculate risk score for a deposit transaction.
        
        Args:
            amount: Transaction amount
            phone: Phone number used
            
        Returns:
            int: Risk score (0-100)
        """
        score = 0
        factors = []
        
        # Factor 1: Large amount
        if amount > self.LARGE_AMOUNT_THRESHOLD:
            score += 40
            factors.append({
                'factor': 'large_amount',
                'weight': 40,
                'details': f'Amount {amount} exceeds threshold {self.LARGE_AMOUNT_THRESHOLD}'
            })
        
        # Factor 2: Rapid transactions (velocity check)
        recent_count = Transaction.objects.filter(
            school=self.school,
            phone_number=phone,
            created_at__gte=timezone.now() - timedelta(minutes=1)
        ).count()
        
        if recent_count > self.RAPID_TX_THRESHOLD:
            score += 30
            factors.append({
                'factor': 'rapid_transactions',
                'weight': 30,
                'details': f'{recent_count} transactions in last minute'
            })
        
        # Factor 3: New user (first transaction)
        if self.user:
            user_tx_count = Transaction.objects.filter(
                school=self.school,
                user=self.user
            ).count()
            
            if user_tx_count == 0:
                score += 20
                factors.append({
                    'factor': 'new_user',
                    'weight': 20,
                    'details': 'First transaction for this user'
                })
            elif user_tx_count < 3:
                score += 10
                factors.append({
                    'factor': 'newish_user',
                    'weight': 10,
                    'details': f'Only {user_tx_count} previous transactions'
                })
        
        # Factor 4: Phone mismatch
        if self.user and hasattr(self.user, 'phone'):
            user_phone = str(self.user.phone).replace('+', '').replace(' ', '')
            tx_phone = str(phone).replace('+', '').replace(' ', '')
            if user_phone != tx_phone:
                score += 10
                factors.append({
                    'factor': 'phone_mismatch',
                    'weight': 10,
                    'details': f'Phone mismatch: user={user_phone}, tx={tx_phone}'
                })
        
        # Factor 5: Daily volume approaching limit
        if self.user:
            daily_total = Transaction.objects.filter(
                school=self.school,
                user=self.user,
                created_at__date=timezone.now().date(),
                status='SUCCESS'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            if daily_total + Decimal(str(amount)) > self.MAX_DAILY_VOLUME:
                score += 25
                factors.append({
                    'factor': 'daily_volume_limit',
                    'weight': 25,
                    'details': f'Daily volume {daily_total} + {amount} exceeds limit'
                })
        
        # Determine action
        action = 'ALLOW'
        if score >= self.CRITICAL_RISK_THRESHOLD:
            action = 'BLOCK'
            self._create_alert(
                'CRITICAL',
                'HIGH_RISK_TRANSACTION_BLOCKED',
                f'High risk transaction blocked: score {score}',
                {'score': score, 'factors': factors, 'amount': str(amount)}
            )
        elif score >= self.HIGH_RISK_THRESHOLD:
            action = 'FLAG'
            self._create_alert(
                'WARNING',
                'ELEVATED_RISK_TRANSACTION',
                f'Elevated risk transaction: score {score}',
                {'score': score, 'factors': factors, 'amount': str(amount)}
            )
        
        # Log risk score
        RiskScoreLog.objects.create(
            school=self.school,
            user=self.user,
            transaction_amount=amount,
            risk_score=score,
            factors=factors,
            action_taken=action
        )
        
        return score
    
    def check_duplicate_receipt(self, receipt):
        """
        Check for duplicate M-Pesa receipts.
        
        Args:
            receipt: M-Pesa receipt number
            
        Returns:
            bool: True if duplicate detected
        """
        if not receipt:
            return False
        
        exists = Transaction.objects.filter(
            school=self.school,
            mpesa_receipt=receipt
        ).exists()
        
        if exists:
            self._create_alert(
                'CRITICAL',
                'DUPLICATE_RECEIPT',
                f'Duplicate M-Pesa receipt detected: {receipt}',
                {'receipt': receipt}
            )
            return True
        
        return False
    
    def check_reconciliation_mismatch(self, mpesa_amount, db_amount, receipt):
        """
        Detect reconciliation mismatches.
        
        Args:
            mpesa_amount: Amount from M-Pesa
            db_amount: Amount in our database
            receipt: Receipt number
            
        Returns:
            bool: True if mismatch detected
        """
        if Decimal(str(mpesa_amount)) != Decimal(str(db_amount)):
            self._create_alert(
                'CRITICAL',
                'RECONCILIATION_MISMATCH',
                f'Amount mismatch for {receipt}: M-Pesa={mpesa_amount}, DB={db_amount}',
                {
                    'receipt': receipt,
                    'mpesa_amount': str(mpesa_amount),
                    'db_amount': str(db_amount)
                }
            )
            return True
        
        return False
    
    def check_overdraft_attempt(self, amount, wallet):
        """
        Detect attempted overdrafts.
        
        Args:
            amount: Amount being requested
            wallet: Wallet being debited
            
        Returns:
            bool: True if overdraft detected
        """
        if Decimal(str(amount)) > wallet.balance:
            self._create_alert(
                'CRITICAL',
                'OVERDRAFT_ATTEMPT',
                f'Overdraft attempt: {amount} > balance {wallet.balance}',
                {
                    'attempted_amount': str(amount),
                    'available_balance': str(wallet.balance),
                    'user_id': str(wallet.user.id)
                }
            )
            return True
        
        return False
    
    def check_suspicious_pattern(self, user, days=7):
        """
        Analyze user's transaction pattern for anomalies.
        
        Args:
            user: User to analyze
            days: Number of days to analyze
            
        Returns:
            list: List of suspicious patterns detected
        """
        patterns = []
        since = timezone.now() - timedelta(days=days)
        
        # Get user's transactions
        transactions = Transaction.objects.filter(
            school=self.school,
            user=user,
            created_at__gte=since
        )
        
        # Pattern 1: Many failed transactions
        failed_count = transactions.filter(status='FAILED').count()
        if failed_count > 10:
            patterns.append({
                'type': 'many_failures',
                'details': f'{failed_count} failed transactions in {days} days'
            })
        
        # Pattern 2: Unusual activity spike
        daily_counts = transactions.filter(
            status='SUCCESS'
        ).extra(
            {'date': 'date(created_at)'}
        ).values('date').annotate(
            count=Count('id'),
            total=Sum('amount')
        ).order_by('date')
        
        if len(daily_counts) >= 3:
            # Check for sudden spike
            recent = daily_counts[-3:]
            avg = sum(d['count'] for d in daily_counts[:-3]) / max(len(daily_counts) - 3, 1)
            recent_avg = sum(d['count'] for d in recent) / 3
            
            if recent_avg > avg * 3:  # 3x normal activity
                patterns.append({
                    'type': 'activity_spike',
                    'details': f'Activity spike: recent avg {recent_avg:.1f} vs normal {avg:.1f}'
                })
        
        # Pattern 3: Round number pattern (possible testing)
        round_amounts = transactions.filter(
            status='SUCCESS',
            amount__in=[1, 10, 100, 1000, 10000]
        ).count()
        
        if round_amounts > 5:
            patterns.append({
                'type': 'round_amount_pattern',
                'details': f'{round_amounts} round-number transactions (possible testing)'
            })
        
        # Create alert if patterns found
        if patterns:
            self._create_alert(
                'WARNING',
                'SUSPICIOUS_PATTERN',
                f'Suspicious patterns detected for user {user}',
                {'patterns': patterns, 'user_id': str(user.id)}
            )
        
        return patterns
    
    def _create_alert(self, level, alert_type, message, metadata=None):
        """
        Create an alert in the system.
        
        Args:
            level: INFO, WARNING, or CRITICAL
            alert_type: Type of alert
            message: Human-readable message
            metadata: Additional data
        """
        Alert.objects.create(
            school=self.school,
            level=level,
            alert_type=alert_type,
            message=message,
            metadata=metadata or {},
            reference=metadata.get('receipt') if metadata else None
        )


class FraudMonitor:
    """
    Background monitoring for fraud patterns.
    
    Runs periodically to detect:
    - Unusual school-wide patterns
    - Potential account takeovers
    - Money laundering indicators
    """
    
    @staticmethod
    def monitor_school(school):
        """
        Run fraud monitoring for a school.
        
        Args:
            school: School to monitor
        """
        engine = FraudDetectionEngine(school)
        
        # Check for unusual transaction volumes
        today = timezone.now().date()
        today_volume = Transaction.objects.filter(
            school=school,
            created_at__date=today,
            status='SUCCESS'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Compare to average
        avg_daily = Transaction.objects.filter(
            school=school,
            created_at__date__lt=today,
            status='SUCCESS'
        ).extra(
            {'date': 'date(created_at)'}
        ).values('date').annotate(
            daily=Sum('amount')
        ).aggregate(avg=Avg('daily'))['avg'] or Decimal('0')
        
        if avg_daily > 0 and today_volume > avg_daily * 5:
            Alert.objects.create(
                school=school,
                level='WARNING',
                alert_type='VOLUME_SPIKE',
                message=f'Unusual transaction volume today: {today_volume} (avg: {avg_daily})',
                metadata={
                    'today_volume': str(today_volume),
                    'average_volume': str(avg_daily)
                }
            )
        
        # Check for multiple failed logins (if you track this)
        # This would integrate with your auth system
        
        return True
