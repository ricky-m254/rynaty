# Quick Start Guide for Replit Agent

## What This Package Contains

This is a **complete, production-ready M-Pesa payment system** for your multi-tenant school management SaaS.

## File Structure

```
mpesa-school-saas/
├── TASK.md                    # Main implementation guide (READ THIS FIRST)
├── README.md                  # Full documentation
├── QUICKSTART.md             # This file
├── DEPLOYMENT_GUIDE.md       # Production deployment
├── SETTINGS_ADDITIONS.py     # Django settings to add
├── PROJECT_URLS.py           # URL configuration example
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variables template
│
├── core/                     # Shared utilities & middleware
│   ├── __init__.py
│   ├── apps.py
│   ├── middleware.py         # Tenant resolution
│   └── models.py             # Base models
│
├── payments/                 # M-Pesa integration
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py             # Transaction, MpesaRawLog
│   ├── mpesa_client.py       # Daraja API client
│   ├── views.py              # API endpoints
│   ├── serializers.py        # DRF serializers
│   ├── urls.py               # URL routes
│   └── tasks.py              # Celery background jobs
│
├── ledger/                   # Double-entry accounting
│   ├── __init__.py
│   ├── apps.py
│   └── models.py             # LedgerEntry, Wallet
│
├── billing/                  # Invoicing & subscriptions
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py             # Invoice, SaaSInvoice, Plan
│   ├── engine.py             # Billing calculations
│   └── tasks.py              # Billing jobs
│
├── audit/                    # Compliance & audit logs
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py             # AuditLog (tamper-proof)
│   └── compliance.py         # Compliance engine
│
├── fraud_detection/          # Security & fraud detection
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py             # Alert, RiskScoreLog
│   └── engine.py             # Fraud detection rules
│
├── saas_admin/               # Admin dashboard API
│   ├── __init__.py
│   ├── apps.py
│   ├── views.py              # Admin endpoints
│   └── urls.py               # Admin routes
│
└── config/                   # Celery configuration
    └── celery.py
```

## Implementation Order

Follow this exact order:

### Phase 1: Foundation (Day 1)
1. ✅ Copy all files to your project
2. ✅ Add settings from `SETTINGS_ADDITIONS.py`
3. ✅ Add URLs from `PROJECT_URLS.py`
4. ✅ Install requirements: `pip install -r requirements.txt`
5. ✅ Run migrations

### Phase 2: Core Payments (Day 1-2)
1. ✅ Configure M-Pesa credentials in `.env`
2. ✅ Test STK Push endpoint
3. ✅ Test callback handling
4. ✅ Verify ledger entries are created

### Phase 3: Billing (Day 2-3)
1. ✅ Create subscription plans
2. ✅ Test invoice generation
3. ✅ Set up Celery beat for monthly billing

### Phase 4: Security (Day 3-4)
1. ✅ Enable fraud detection
2. ✅ Configure audit logging
3. ✅ Set up compliance checks

### Phase 5: Admin Dashboard (Day 4-5)
1. ✅ Build React/Vue dashboard using admin API
2. ✅ Add charts for revenue/schools
3. ✅ Add alert management UI

## Critical Files to Modify

### 1. Your `settings.py`
```python
# Add these imports at top
import os
from datetime import timedelta

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

# Add M-Pesa settings
MPESA_BASE_URL = os.getenv('MPESA_BASE_URL')
MPESA_CONSUMER_KEY = os.getenv('MPESA_CONSUMER_KEY')
MPESA_CONSUMER_SECRET = os.getenv('MPESA_CONSUMER_SECRET')
MPESA_SHORTCODE = os.getenv('MPESA_SHORTCODE')
MPESA_PASSKEY = os.getenv('MPESA_PASSKEY')

# Celery
CELERY_BROKER_URL = os.getenv('REDIS_URL')
```

### 2. Your `urls.py`
```python
urlpatterns = [
    # ... existing URLs
    path('api/payments/', include('payments.urls')),
    path('api/admin/', include('saas_admin.urls')),
]
```

### 3. Your School Model
Add these fields to your existing School model:
```python
class School(models.Model):
    # ... existing fields
    
    # M-Pesa config
    mpesa_shortcode = models.CharField(max_length=20, blank=True)
    mpesa_passkey = models.CharField(max_length=255, blank=True)
    mpesa_consumer_key = models.CharField(max_length=255, blank=True)
    mpesa_consumer_secret = models.CharField(max_length=255, blank=True)
    mpesa_environment = models.CharField(
        max_length=10,
        choices=[('sandbox', 'Sandbox'), ('live', 'Live')],
        default='sandbox'
    )
    
    # Subscription
    subscription_active = models.BooleanField(default=True)
    subscription_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Admin contact
    admin_phone = models.CharField(max_length=20, blank=True)
    admin_email = models.EmailField(blank=True)
    
    def is_subscription_active(self):
        if not self.subscription_active:
            return False
        if self.subscription_expires_at and self.subscription_expires_at < timezone.now():
            return False
        return True
```

## Testing Checklist

### API Tests
```bash
# 1. Test STK Push
curl -X POST https://yourdomain.com/api/payments/stk-push/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"phone": "254712345678", "amount": 100}'

# 2. Check transactions
curl https://yourdomain.com/api/payments/transactions/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# 3. Check admin dashboard
curl https://yourdomain.com/api/admin/overview/ \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

### Database Verification
```sql
-- Check transactions
SELECT status, COUNT(*) FROM payments_transaction GROUP BY status;

-- Check ledger entries
SELECT entry_type, SUM(amount) FROM ledger_ledgerentry GROUP BY entry_type;

-- Check audit logs
SELECT action, COUNT(*) FROM audit_auditlog GROUP BY action;
```

## Common Issues & Fixes

### Issue: "No module named 'payments'"
**Fix**: Make sure `payments/` directory is at project root and `__init__.py` exists

### Issue: "Cannot import name 'TenantMiddleware'"
**Fix**: Add `core.middleware.TenantMiddleware` to MIDDLEWARE in settings

### Issue: Callback not processing
**Fix**: 
1. Check callback URL is publicly accessible
2. Verify `MpesaRawLog` entries are created
3. Check logs for processing errors

### Issue: Balance not updating
**Fix**: 
1. Check ledger entries are created
2. Verify atomic transaction blocks
3. Check for exceptions in callback processing

## Next Steps After Implementation

1. **Register on Daraja Portal** - Get M-Pesa credentials
2. **Configure Callback URL** - Point to your production URL
3. **Test in Sandbox** - Use test credentials
4. **Go Live** - Apply for production credentials
5. **Monitor** - Set up alerts and dashboards

## Support Resources

- M-Pesa Daraja Docs: https://developer.safaricom.co.ke/docs
- Django Celery: https://docs.celeryq.dev/en/stable/django/
- DRF: https://www.django-rest-framework.org/

---

**This is a complete, enterprise-grade financial system. Take time to understand each component before deploying to production.**
