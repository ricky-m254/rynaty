"""
Celery tasks for billing and subscription management.
"""

from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from .engine import BillingEngine
from .models import SaaSInvoice, RevenueLog


@shared_task
def generate_monthly_saas_bills():
    """
    Generate monthly subscription invoices for all schools.
    
    Runs on the 1st of each month at midnight.
    """
    invoices = BillingEngine.generate_all_monthly_bills()
    return f"Generated {len(invoices)} invoices"


@shared_task
def suspend_expired_schools():
    """
    Auto-suspend schools with expired subscriptions.
    
    Runs daily at midnight.
    """
    from schools.models import School
    
    expired = School.objects.filter(
        subscription_expires_at__lt=timezone.now(),
        subscription_active=True
    )
    
    suspended_count = 0
    for school in expired:
        school.subscription_active = False
        school.save()
        suspended_count += 1
        
        # Audit log
        from audit.models import AuditLog
        AuditLog.log_system_action(
            school,
            'SCHOOL_SUSPENDED',
            'SCHOOL',
            str(school.id),
            {'reason': 'Subscription expired'}
        )
    
    return f"Suspended {suspended_count} schools"


@shared_task
def send_payment_reminders():
    """
    Send payment reminders for overdue invoices.
    
    Runs daily.
    """
    from django.core.mail import send_mail
    
    overdue = SaaSInvoice.objects.filter(
        status='OVERDUE',
        due_date__lt=timezone.now().date() - timedelta(days=3)
    ).select_related('school')
    
    for invoice in overdue:
        if invoice.school.admin_email:
            send_mail(
                subject='Payment Reminder - Subscription Overdue',
                message=f'''
                Dear {invoice.school.name} Admin,
                
                Your subscription payment of KES {invoice.amount} is overdue.
                Please make payment to avoid service interruption.
                
                Invoice: {invoice.invoice_number}
                Due Date: {invoice.due_date}
                
                Thank you.
                ''',
                from_email='billing@yoursaas.com',
                recipient_list=[invoice.school.admin_email],
                fail_silently=True
            )
    
    return f"Sent {overdue.count()} reminders"


@shared_task
def calculate_mrr():
    """
    Calculate Monthly Recurring Revenue.
    
    Stores for analytics dashboard.
    """
    mrr = BillingEngine.get_mrr()
    
    # Could store in analytics model or cache
    from django.core.cache import cache
    cache.set('mrr', str(mrr), 86400)  # 24 hours
    
    return f"MRR: KES {mrr}"


@shared_task
def generate_revenue_report():
    """
    Generate weekly revenue report.
    
    Can be emailed to admin team.
    """
    from_date = timezone.now() - timedelta(days=7)
    
    report = BillingEngine.get_revenue_summary(days=7)
    
    # Could email this report
    return report
