# M-Pesa School Management SaaS - Implementation Guide

## Overview

This package provides a complete, production-ready M-Pesa payment integration for your multi-tenant school management SaaS platform.

## What's Included

### Core Modules

1. **payments/** - M-Pesa integration (STK Push, B2C, callbacks)
2. **ledger/** - Double-entry accounting system
3. **billing/** - Invoicing and SaaS subscription management
4. **audit/** - Tamper-proof audit logging with hash chaining
5. **fraud_detection/** - Real-time fraud detection and alerts
6. **saas_admin/** - Admin dashboard API
7. **core/** - Shared utilities and middleware

### Key Features

- **Multi-tenant architecture** - Data isolation per school
- **M-Pesa STK Push** - Seamless mobile payments
- **B2C withdrawals** - Process refunds and payouts
- **Double-entry ledger** - Financial-grade accounting
- **Fraud detection** - Risk scoring and pattern detection
- **Audit compliance** - Tamper-proof logs with hash chaining
- **SaaS billing** - Automated subscription billing
- **Real-time alerts** - Critical event notifications

## Installation Steps

### 1. Copy Files to Your Project

Copy all directories to your Django project:

```bash
# From this package
cp -r payments ledger billing audit fraud_detection saas_admin core /path/to/your/project/
```

### 2. Update settings.py

Add the settings from `SETTINGS_ADDITIONS.py` to your `settings.py`:

```python
# Add to INSTALLED_APPS
INSTALLED_APPS += [
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_celery_beat',
    'core',
    'payments',
    'ledger',
    'billing',
    'audit',
    'fraud_detection',
    'saas_admin',
]

# Add middleware
MIDDLEWARE += [
    'core.middleware.TenantMiddleware',
]

# Add M-Pesa settings
MPESA_BASE_URL = 'https://sandbox.safaricom.co.ke'
MPESA_CONSUMER_KEY = 'your-key'
MPESA_CONSUMER_SECRET = 'your-secret'
MPESA_SHORTCODE = '174379'
MPESA_PASSKEY = 'your-passkey'
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run Migrations

```bash
python manage.py makemigrations payments ledger billing audit fraud_detection saas_admin
python manage.py migrate
```

### 5. Update URL Configuration

Add to your main `urls.py`:

```python
from django.urls import path, include

urlpatterns = [
    # ... your existing URLs
    path('api/payments/', include('payments.urls')),
    path('api/admin/', include('saas_admin.urls')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
```

### 6. Setup Celery

Create `config/celery.py` (if not exists):

```python
from celery import Celery

app = Celery('yourproject')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
```

In `config/__init__.py`:

```python
from .celery import app as celery_app

__all__ = ('celery_app',)
```

### 7. Start Services

```bash
# Terminal 1: Django server
python manage.py runserver

# Terminal 2: Celery worker
celery -A yourproject worker -l info

# Terminal 3: Celery beat (scheduler)
celery -A yourproject beat -l info
```

## API Endpoints

### Payments

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/payments/stk-push/` | POST | Initiate STK Push |
| `/api/payments/mpesa/callback/` | POST | M-Pesa callback (no auth) |
| `/api/payments/transactions/` | GET | List user transactions |
| `/api/payments/admin/adjust-balance/` | POST | Admin balance adjustment |
| `/api/payments/withdrawal-request/` | POST | Request withdrawal |

### Admin Dashboard

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/admin/overview/` | GET | Dashboard metrics |
| `/api/admin/revenue-chart/` | GET | Revenue chart data |
| `/api/admin/schools/` | GET | List all schools |
| `/api/admin/schools/<id>/toggle/` | POST | Suspend/activate school |
| `/api/admin/alerts/` | GET | Security alerts |
| `/api/admin/audit/` | GET | Audit logs |
| `/api/admin/audit/export/` | GET | Export CSV |

## Usage Examples

### Initiate STK Push

```python
import requests

response = requests.post(
    'https://yourdomain.com/api/payments/stk-push/',
    headers={'Authorization': 'Bearer YOUR_TOKEN'},
    json={
        'phone': '254712345678',
        'amount': 1000,
        'invoice_id': 'optional-invoice-uuid'
    }
)

print(response.json())
# {
#   "success": true,
#   "transaction_id": "uuid",
#   "message": "STK push sent to your phone",
#   "checkout_request_id": "ws_..."
# }
```

### Check Transaction Status

```python
response = requests.get(
    'https://yourdomain.com/api/payments/transactions/',
    headers={'Authorization': 'Bearer YOUR_TOKEN'}
)
```

### Admin Balance Adjustment

```python
response = requests.post(
    'https://yourdomain.com/api/payments/admin/adjust-balance/',
    headers={'Authorization': 'Bearer ADMIN_TOKEN'},
    json={
        'user_id': 'user-uuid',
        'amount': 500,  # Positive for credit, negative for debit
        'reason': 'Correction for overcharge'
    }
)
```

## M-Pesa Configuration

### 1. Register on Daraja Portal

1. Go to [Safaricom Developer Portal](https://developer.safaricom.co.ke)
2. Create an account
3. Create a new app
4. Get Consumer Key and Consumer Secret

### 2. Configure Callback URL

In your Daraja app settings, set:
- **Validation URL**: Not required for STK Push
- **Confirmation URL**: `https://yourdomain.com/api/payments/mpesa/callback/`

### 3. Test in Sandbox

Use the sandbox credentials for testing:
- Shortcode: `174379`
- Test phone: `254708374149`
- Test PIN: Use any PIN

### 4. Go Live

1. Apply for live credentials
2. Update `MPESA_BASE_URL` to `https://api.safaricom.co.ke`
3. Replace sandbox credentials with live credentials

## Database Schema

### Key Tables

- `payments_transaction` - All payment transactions
- `ledger_ledgerentry` - Double-entry ledger records
- `ledger_wallet` - User wallet balances
- `billing_invoice` - School fee invoices
- `billing_saasinvoice` - SaaS subscription invoices
- `audit_auditlog` - Tamper-proof audit logs
- `fraud_detection_alert` - Security alerts

### Indexes

All tables have appropriate indexes for:
- School-scoped queries
- Date range queries
- Status lookups
- User lookups

## Security Considerations

### Production Checklist

- [ ] Use HTTPS only
- [ ] Set `DEBUG = False`
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Enable `SECURE_SSL_REDIRECT`
- [ ] Set strong `SECRET_KEY`
- [ ] Configure CORS properly
- [ ] Enable rate limiting
- [ ] Set up Sentry for error tracking
- [ ] Configure log rotation
- [ ] Enable database connection pooling

### M-Pesa Security

- [ ] Validate callback IPs (Safaricom ranges)
- [ ] Use unique receipt numbers
- [ ] Implement idempotency
- [ ] Encrypt sensitive credentials
- [ ] Log all callbacks
- [ ] Monitor for duplicate receipts

## Troubleshooting

### Common Issues

**STK Push not received on phone**
- Check phone number format (should be 254...)
- Verify M-Pesa credentials
- Check callback URL is accessible
- Review logs for errors

**Callback not processed**
- Verify callback URL is correct
- Check server logs for 500 errors
- Ensure callback endpoint returns 200 quickly
- Check raw logs in `MpesaRawLog` table

**Duplicate transactions**
- Verify idempotency check is working
- Check for race conditions
- Review callback processing logic

**Balance not updating**
- Check ledger entries are created
- Verify atomic transactions
- Review error logs

### Debug Commands

```bash
# Check pending transactions
python manage.py shell -c "from payments.models import Transaction; print(Transaction.objects.filter(status='PENDING').count())"

# Verify audit chain
python manage.py shell -c "from audit.models import AuditLog; print(AuditLog.verify_chain(school_id=1))"

# Check Celery status
celery -A yourproject inspect active
celery -A yourproject inspect scheduled
```

## Support

For issues or questions:
1. Check the logs in `logs/django.log`
2. Review the audit logs in admin dashboard
3. Check M-Pesa raw logs for callback issues
4. Verify Celery tasks are running

## License

This is proprietary software for your SaaS platform.
