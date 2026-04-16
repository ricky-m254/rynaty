"""
Compliance engine for regulatory and policy enforcement.
"""

from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum

from .models import ComplianceLog, ComplianceRule
from payments.models import Transaction


class ComplianceEngine:
    """
    Engine for running compliance checks.
    
    Ensures the system adheres to:
    - Regulatory requirements
    - School policies
    - Data protection rules
    """
    
    # Default limits (can be overridden by school rules)
    DEFAULT_MAX_TRANSACTION = 150000  # KES
    DEFAULT_MAX_DAILY = 300000  # KES
    DEFAULT_MAX_BALANCE = 500000  # KES
    
    def __init__(self, school):
        """
        Initialize compliance engine.
        
        Args:
            school: School to check compliance for
        """
        self.school = school
        self.rules = self._load_rules()
    
    def _load_rules(self):
        """Load active compliance rules for school."""
        return {
            rule.rule_type: rule
            for rule in ComplianceRule.objects.filter(school=self.school, active=True)
        }
    
    def get_limit(self, rule_type, default):
        """Get limit from rule or use default."""
        rule = self.rules.get(rule_type)
        if rule and rule.threshold:
            return rule.threshold
        return default
    
    def check_transaction_limits(self, user, amount):
        """
        Check if transaction is within allowed limits.
        
        Args:
            user: User making transaction
            amount: Transaction amount
            
        Returns:
            tuple: (is_allowed, reason)
        """
        amount = Decimal(str(amount))
        
        # Check single transaction limit
        max_tx = self.get_limit('MAX_TRANSACTION', self.DEFAULT_MAX_TRANSACTION)
        if amount > max_tx:
            return False, f"Transaction exceeds maximum of KES {max_tx}"
        
        # Check daily volume limit
        max_daily = self.get_limit('MAX_DAILY', self.DEFAULT_MAX_DAILY)
        today_total = Transaction.objects.filter(
            school=self.school,
            user=user,
            created_at__date=timezone.now().date(),
            status='SUCCESS'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        if today_total + amount > max_daily:
            remaining = max_daily - today_total
            return False, f"Daily limit exceeded. Remaining: KES {remaining}"
        
        return True, "Within limits"
    
    def check_balance_limit(self, wallet):
        """
        Check if wallet balance is within allowed limit.
        
        Args:
            wallet: Wallet to check
            
        Returns:
            tuple: (is_allowed, reason)
        """
        max_balance = self.get_limit('MAX_STUDENT_BALANCE', self.DEFAULT_MAX_BALANCE)
        
        if wallet.balance > max_balance:
            return False, f"Balance exceeds maximum of KES {max_balance}"
        
        return True, "Within limits"
    
    def check_receipt_requirement(self, transaction):
        """
        Check if transaction has required M-Pesa receipt.
        
        Args:
            transaction: Transaction to check
            
        Returns:
            tuple: (is_compliant, reason)
        """
        rule = self.rules.get('REQUIRE_RECEIPT')
        if not rule or not rule.config.get('required', True):
            return True, "Receipt not required"
        
        if transaction.status == 'SUCCESS' and not transaction.mpesa_receipt:
            return False, "Successful transaction missing M-Pesa receipt"
        
        return True, "Receipt present"
    
    def run_daily_compliance_check(self):
        """
        Run all compliance checks for the school.
        
        Returns:
            list: List of compliance results
        """
        results = []
        
        # Check data retention
        results.append(self._check_data_retention())
        
        # Check audit completeness
        results.append(self._check_audit_completeness())
        
        # Check reconciliation status
        results.append(self._check_reconciliation_status())
        
        # Check for unreconciled transactions
        results.append(self._check_unreconciled_transactions())
        
        # Check for missing receipts
        results.append(self._check_missing_receipts())
        
        return results
    
    def _check_data_retention(self):
        """Verify data retention policy compliance."""
        policy = getattr(self.school, 'retention_policy', None)
        if not policy:
            return self._log_check('DATA_RETENTION', 'PASS', 
                                 'No retention policy configured')
        
        cutoff = policy.get_retention_date('transaction')
        
        # Check if old data exists
        old_records = Transaction.objects.filter(
            school=self.school,
            created_at__lt=cutoff
        ).exists()
        
        if old_records:
            return self._log_check('DATA_RETENTION', 'PASS',
                                 f'Records retained beyond {policy.transaction_retention_years} years')
        
        return self._log_check('DATA_RETENTION', 'PASS',
                             'Data retention compliant')
    
    def _check_audit_completeness(self):
        """Verify all transactions have audit logs."""
        from .models import AuditLog
        
        yesterday = timezone.now() - timedelta(days=1)
        recent_tx = Transaction.objects.filter(
            school=self.school,
            created_at__gte=yesterday
        )
        
        missing_audit = []
        for tx in recent_tx:
            has_audit = AuditLog.objects.filter(
                school=self.school,
                entity='TRANSACTION',
                entity_id=str(tx.id)
            ).exists()
            
            if not has_audit:
                missing_audit.append(str(tx.id))
        
        if missing_audit:
            return self._log_check('AUDIT_COMPLETENESS', 'FAIL',
                                 f'{len(missing_audit)} transactions missing audit logs',
                                 {'transaction_ids': missing_audit[:10]})
        
        return self._log_check('AUDIT_COMPLETENESS', 'PASS',
                             'All transactions have audit logs')
    
    def _check_reconciliation_status(self):
        """Check for reconciliation mismatches."""
        yesterday = timezone.now() - timedelta(days=1)
        
        # Find transactions where amount doesn't match ledger
        mismatches = []
        transactions = Transaction.objects.filter(
            school=self.school,
            status='SUCCESS',
            created_at__gte=yesterday
        ).select_related('ledger_entry')
        
        for tx in transactions:
            if tx.ledger_entry and tx.amount != abs(tx.ledger_entry.amount):
                mismatches.append({
                    'transaction_id': str(tx.id),
                    'tx_amount': str(tx.amount),
                    'ledger_amount': str(tx.ledger_entry.amount)
                })
        
        if mismatches:
            return self._log_check('RECONCILIATION', 'FAIL',
                                 f'{len(mismatches)} reconciliation mismatches',
                                 {'mismatches': mismatches[:5]})
        
        return self._log_check('RECONCILIATION', 'PASS',
                             'All transactions reconciled')
    
    def _check_unreconciled_transactions(self):
        """Check for successful transactions without M-Pesa receipts."""
        cutoff = timezone.now() - timedelta(hours=1)
        
        unreconciled = Transaction.objects.filter(
            school=self.school,
            status='SUCCESS',
            mpesa_receipt__isnull=True,
            created_at__lte=cutoff
        )
        
        count = unreconciled.count()
        if count > 0:
            return self._log_check('UNRECONCILED_TX', 'WARNING',
                                 f'{count} unreconciled transactions',
                                 {'count': count})
        
        return self._log_check('UNRECONCILED_TX', 'PASS',
                             'No unreconciled transactions')
    
    def _check_missing_receipts(self):
        """Check for successful transactions missing receipts."""
        missing = Transaction.objects.filter(
            school=self.school,
            status='SUCCESS',
            mpesa_receipt__isnull=True
        )
        
        count = missing.count()
        if count > 0:
            return self._log_check('MISSING_RECEIPTS', 'FAIL',
                                 f'{count} successful transactions missing receipts',
                                 {'count': count})
        
        return self._log_check('MISSING_RECEIPTS', 'PASS',
                             'All successful transactions have receipts')
    
    def _log_check(self, rule, status, message, details=None):
        """Log compliance check result."""
        log = ComplianceLog.objects.create(
            school=self.school,
            rule=rule,
            status=status,
            details={
                'message': message,
                **(details or {})
            }
        )
        return {
            'rule': rule,
            'status': status,
            'message': message,
            'log_id': log.id
        }
    
    @classmethod
    def run_all_schools(cls):
        """Run compliance checks for all active schools."""
        from schools.models import School
        
        results = {}
        for school in School.objects.filter(active=True):
            try:
                engine = cls(school)
                results[school.name] = engine.run_daily_compliance_check()
            except Exception as e:
                results[school.name] = [{'error': str(e)}]
        
        return results


class ExportEngine:
    """
    Engine for generating compliance exports.
    
    Creates audit reports for external auditors.
    """
    
    @staticmethod
    def generate_audit_report(school, start_date, end_date, format='csv'):
        """
        Generate audit report for a date range.
        
        Args:
            school: School to generate report for
            start_date: Start of period
            end_date: End of period
            format: 'csv' or 'pdf'
            
        Returns:
            File-like object containing report
        """
        from .models import AuditLog
        from io import StringIO, BytesIO
        import csv
        
        logs = AuditLog.objects.filter(
            school=school,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).order_by('created_at')
        
        if format == 'csv':
            output = StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow([
                'Timestamp', 'Action', 'Entity', 'Entity ID',
                'User', 'IP Address', 'Metadata', 'Entry Hash'
            ])
            
            # Data
            for log in logs:
                writer.writerow([
                    log.created_at.isoformat(),
                    log.action,
                    log.entity,
                    log.entity_id,
                    log.user.username if log.user else 'System',
                    log.ip_address or '',
                    json.dumps(log.metadata),
                    log.entry_hash
                ])
            
            output.seek(0)
            return output
        
        elif format == 'pdf':
            # PDF generation would go here
            # Requires reportlab or similar
            raise NotImplementedError("PDF export not yet implemented")
        
        else:
            raise ValueError(f"Unknown format: {format}")
    
    @staticmethod
    def generate_transaction_report(school, start_date, end_date):
        """
        Generate transaction summary report.
        
        Args:
            school: School to generate report for
            start_date: Start of period
            end_date: End of period
            
        Returns:
            dict: Report data
        """
        transactions = Transaction.objects.filter(
            school=school,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        
        successful = transactions.filter(status='SUCCESS')
        failed = transactions.filter(status='FAILED')
        
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'summary': {
                'total_transactions': transactions.count(),
                'successful_count': successful.count(),
                'failed_count': failed.count(),
                'total_volume': str(successful.aggregate(total=Sum('amount'))['total'] or Decimal('0')),
                'average_amount': str(successful.aggregate(avg=Avg('amount'))['avg'] or Decimal('0'))
            },
            'by_type': list(
                successful.values('transaction_type').annotate(
                    count=Count('id'),
                    total=Sum('amount')
                )
            ),
            'by_day': list(
                successful.extra({'date': 'date(created_at)'})
                .values('date')
                .annotate(count=Count('id'), total=Sum('amount'))
                .order_by('date')
            )
        }
