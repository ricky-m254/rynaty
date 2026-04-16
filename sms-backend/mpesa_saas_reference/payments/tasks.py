"""
Celery tasks for background payment processing.
Handles reconciliation, timeouts, and scheduled jobs.
"""

from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import Transaction, MpesaRawLog, WithdrawalRequest
from .mpesa_client import MpesaClient
from ledger.models import Wallet
from fraud_detection.engine import FraudDetectionEngine
from audit.models import AuditLog


@shared_task(bind=True, max_retries=3)
def process_mpesa_callback(self, raw_log_id):
    """
    Process M-Pesa callback asynchronously.
    
    This allows the callback endpoint to respond quickly
    while processing happens in background.
    """
    try:
        raw_log = MpesaRawLog.objects.get(id=raw_log_id)
        # Processing logic here
        # This is a backup in case synchronous processing fails
        raw_log.processed = True
        raw_log.save()
    except Exception as exc:
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task
def reconcile_transactions():
    """
    Daily reconciliation job.
    
    Runs at 11 PM daily to:
    - Check for missing receipts
    - Verify transaction amounts match
    - Flag discrepancies
    """
    from schools.models import School
    
    for school in School.objects.filter(active=True):
        try:
            # Get yesterday's transactions
            yesterday = timezone.now() - timedelta(days=1)
            transactions = Transaction.objects.filter(
                school=school,
                created_at__date=yesterday.date()
            )
            
            # Check for successful transactions without receipts
            missing_receipts = transactions.filter(
                status='SUCCESS',
                mpesa_receipt__isnull=True
            )
            
            for tx in missing_receipts:
                # Query M-Pesa for status
                try:
                    mpesa = MpesaClient(school)
                    result = mpesa.query_stk_status(tx.checkout_request_id)
                    
                    # Update transaction if we got a result
                    if result.get('ResultCode') == '0':
                        tx.mpesa_receipt = result.get('MpesaReceiptNumber')
                        tx.save()
                    else:
                        # Flag for manual review
                        FraudDetectionEngine(school, tx.user)._create_alert(
                            'WARNING',
                            'MISSING_RECEIPT',
                            f'Transaction {tx.id} missing receipt after reconciliation',
                            {'transaction_id': str(tx.id)}
                        )
                except Exception as e:
                    print(f"Failed to query M-Pesa for {tx.id}: {e}")
            
            # Verify ledger entries exist for all successful transactions
            missing_ledger = transactions.filter(
                status='SUCCESS',
                ledger_entry__isnull=True
            )
            
            for tx in missing_ledger:
                # Create missing ledger entry
                try:
                    wallet = Wallet.get_or_create_for_user(tx.user, school)
                    ledger_entry = wallet.credit(
                        amount=tx.amount,
                        entry_type='DEPOSIT',
                        reference=tx.mpesa_receipt or str(tx.id),
                        description=f'Reconciliation credit for {tx.id}'
                    )
                    tx.ledger_entry = ledger_entry
                    tx.save()
                    
                    AuditLog.log_system_action(
                        school, 'BALANCE_UPDATED', 'WALLET',
                        str(wallet.id),
                        {'reason': 'Reconciliation', 'transaction_id': str(tx.id)}
                    )
                except Exception as e:
                    print(f"Failed to create ledger entry for {tx.id}: {e}")
            
        except Exception as e:
            print(f"Reconciliation failed for {school.name}: {e}")


@shared_task
def check_pending_transactions():
    """
    Check and timeout old pending transactions.
    
    Runs every 5 minutes to timeout transactions
    that have been pending too long.
    """
    timeout_threshold = timezone.now() - timedelta(minutes=5)
    
    old_pending = Transaction.objects.filter(
        status__in=['PENDING', 'PROCESSING'],
        created_at__lt=timeout_threshold
    )
    
    for tx in old_pending:
        tx.status = 'FAILED'
        tx.result_desc = 'Transaction timed out - no response from M-Pesa'
        tx.save()
        
        # Log the timeout
        AuditLog.log_system_action(
            tx.school,
            'PAYMENT_FAILED',
            'TRANSACTION',
            str(tx.id),
            {'reason': 'timeout'}
        )


@shared_task
def process_approved_withdrawals():
    """
    Process approved withdrawal requests.
    
    Initiates B2C payments for approved withdrawals.
    """
    approved = WithdrawalRequest.objects.filter(
        status='APPROVED'
    ).select_related('user', 'school')
    
    for withdrawal in approved:
        try:
            mpesa = MpesaClient(withdrawal.school)
            
            result = mpesa.b2c_payment(
                phone=withdrawal.phone_number,
                amount=float(withdrawal.amount),
                remarks=f"Withdrawal for {withdrawal.user.get_full_name() or withdrawal.user.email}"
            )
            
            withdrawal.conversation_id = result.get('ConversationID')
            withdrawal.status = 'PROCESSING'
            withdrawal.save()
            
            # Create transaction record
            tx = Transaction.objects.create(
                school=withdrawal.school,
                user=withdrawal.user,
                amount=withdrawal.amount,
                transaction_type='WITHDRAWAL',
                status='PROCESSING',
                phone_number=withdrawal.phone_number,
                description=f'B2C withdrawal of {withdrawal.amount}'
            )
            withdrawal.transaction = tx
            withdrawal.save()
            
        except Exception as e:
            withdrawal.status = 'FAILED'
            withdrawal.save()
            print(f"Failed to process withdrawal {withdrawal.id}: {e}")


@shared_task
def generate_daily_reports():
    """
    Generate daily transaction reports for schools.
    
    Can be sent via email or stored for dashboard.
    """
    from schools.models import School
    from django.core.mail import send_mail
    
    yesterday = timezone.now() - timedelta(days=1)
    
    for school in School.objects.filter(active=True):
        transactions = Transaction.objects.filter(
            school=school,
            created_at__date=yesterday.date(),
            status='SUCCESS'
        )
        
        if not transactions.exists():
            continue
        
        total = transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        count = transactions.count()
        
        # Could send email here
        # send_mail(...)
        
        # Or store for dashboard
        print(f"{school.name}: {count} transactions, KES {total}")


@shared_task
def cleanup_old_raw_logs():
    """
    Clean up old raw callback logs.
    
    Keeps processed logs for 30 days, unprocessed for 90 days.
    """
    cutoff_processed = timezone.now() - timedelta(days=30)
    cutoff_unprocessed = timezone.now() - timedelta(days=90)
    
    # Delete old processed logs
    MpesaRawLog.objects.filter(
        processed=True,
        created_at__lt=cutoff_processed
    ).delete()
    
    # Delete old unprocessed logs
    MpesaRawLog.objects.filter(
        processed=False,
        created_at__lt=cutoff_unprocessed
    ).delete()


@shared_task
def retry_failed_callbacks():
    """
    Retry processing of failed callbacks.
    
    Attempts to process callbacks that failed previously.
    """
    failed_logs = MpesaRawLog.objects.filter(
        processed=False,
        processing_error__isnull=False,
        created_at__gte=timezone.now() - timedelta(hours=24)
    )
    
    for log in failed_logs:
        try:
            # Re-process the callback
            # This would call the same logic as the callback view
            pass
        except Exception as e:
            print(f"Retry failed for log {log.id}: {e}")
