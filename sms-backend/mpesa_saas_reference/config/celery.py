"""
Celery configuration for background task processing.
"""

import os
from celery import Celery
from celery.schedules import crontab

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Create Celery app
app = Celery('schoolsaas')

# Load config from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from installed apps
app.autodiscover_tasks()

# Celery Beat schedule - periodic tasks
app.conf.beat_schedule = {
    # Payment tasks
    'reconcile-transactions': {
        'task': 'payments.tasks.reconcile_transactions',
        'schedule': crontab(hour=23, minute=0),  # Daily at 11 PM
        'options': {'queue': 'payments'}
    },
    'check-pending-transactions': {
        'task': 'payments.tasks.check_pending_transactions',
        'schedule': 300.0,  # Every 5 minutes
        'options': {'queue': 'payments'}
    },
    'process-approved-withdrawals': {
        'task': 'payments.tasks.process_approved_withdrawals',
        'schedule': 600.0,  # Every 10 minutes
        'options': {'queue': 'payments'}
    },
    'cleanup-old-raw-logs': {
        'task': 'payments.tasks.cleanup_old_raw_logs',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
        'options': {'queue': 'maintenance'}
    },
    'retry-failed-callbacks': {
        'task': 'payments.tasks.retry_failed_callbacks',
        'schedule': 1800.0,  # Every 30 minutes
        'options': {'queue': 'payments'}
    },
    
    # Billing tasks
    'generate-monthly-bills': {
        'task': 'billing.tasks.generate_monthly_saas_bills',
        'schedule': crontab(day_of_month=1, hour=0, minute=0),  # Monthly
        'options': {'queue': 'billing'}
    },
    'suspend-expired-schools': {
        'task': 'billing.tasks.suspend_expired_schools',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
        'options': {'queue': 'billing'}
    },
    'send-payment-reminders': {
        'task': 'billing.tasks.send_payment_reminders',
        'schedule': crontab(hour=9, minute=0),  # Daily at 9 AM
        'options': {'queue': 'billing'}
    },
    'calculate-mrr': {
        'task': 'billing.tasks.calculate_mrr',
        'schedule': crontab(hour=1, minute=0),  # Daily at 1 AM
        'options': {'queue': 'analytics'}
    },
    
    # Fraud detection tasks
    'run-compliance-checks': {
        'task': 'audit.tasks.run_compliance_checks',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
        'options': {'queue': 'compliance'}
    },
}

# Celery configuration
app.conf.update(
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Africa/Nairobi',
    enable_utc=True,
    
    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    result_backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    
    # Broker settings
    broker_url=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    broker_connection_retry_on_startup=True,
    
    # Worker settings
    worker_prefetch_multiplier=1,  # Process one task at a time per worker
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks
    
    # Task execution settings
    task_always_eager=False,  # Don't run tasks synchronously in development
    task_store_eager_result=False,
    
    # Retry settings
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    
    # Queue settings
    task_default_queue='default',
    task_queues={
        'default': {'exchange': 'default', 'routing_key': 'default'},
        'payments': {'exchange': 'payments', 'routing_key': 'payments'},
        'billing': {'exchange': 'billing', 'routing_key': 'billing'},
        'analytics': {'exchange': 'analytics', 'routing_key': 'analytics'},
        'compliance': {'exchange': 'compliance', 'routing_key': 'compliance'},
        'maintenance': {'exchange': 'maintenance', 'routing_key': 'maintenance'},
    },
    task_routes={
        'payments.tasks.*': {'queue': 'payments'},
        'billing.tasks.*': {'queue': 'billing'},
        'audit.tasks.*': {'queue': 'compliance'},
    },
)


@app.task(bind=True)
def debug_task(self):
    """Debug task to verify Celery is working."""
    print(f'Request: {self.request!r}')
    return 'Celery is working!'
