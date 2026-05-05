# Rynaty SMS - Comprehensive Critique & Action Plan

**Project**: School Management System (Multi-tenant SaaS)  
**Stack**: Django (Python) + Express (Node.js) + React + PostgreSQL  
**Date**: 2026-04-25  
**Status**: Active development, needs production hardening

---

## Executive Summary

Your app is architecturally sound but has **critical security gaps**, **clarity issues**, and **testing gaps** that must be fixed before production. The financial/payment system (core revenue driver) lacks test coverage and audit trails.

**Priority Matrix**:
- 🔴 **CRITICAL** (fix before any production use): 5 items
- 🟠 **HIGH** (fix this sprint): 4 items
- 🟡 **MEDIUM** (fix next sprint): 5 items
- 🟢 **LOW** (nice to have): 3 items

---

## 🔴 CRITICAL ISSUES (Fix Immediately)

### 1. Credentials Stored as Plain Text in Database

**Location**: `sms-backend/school/models.py:58-68` (SchoolProfile model)

**Problem**:
```python
smtp_password = models.CharField(max_length=255, blank=True)
sms_api_key = models.CharField(max_length=255, blank=True)
whatsapp_api_key = models.CharField(max_length=255, blank=True)
```
- If your database is compromised, all school SMTP, SMS, WhatsApp credentials are exposed
- School data breach = your company's liability
- **Risk**: Attackers send messages from legitimate school IDs, impersonate school

**Solution Steps**:

**Step 1** - Install encryption package:
```bash
pip install django-encrypted-model-fields
# OR use native Django approach with environment variables
```

**Step 2** - Update SchoolProfile model:
```python
from encrypted_model_fields.fields import EncryptedCharField

class SchoolProfile(models.Model):
    # OLD (remove these):
    # smtp_password = models.CharField(...)
    # sms_api_key = models.CharField(...)
    
    # NEW (add encrypted variants):
    smtp_password_encrypted = EncryptedCharField(blank=True)
    sms_api_key_encrypted = EncryptedCharField(blank=True)
    whatsapp_api_key_encrypted = EncryptedCharField(blank=True)
```

**Step 3** - OR better: Use environment variables per tenant
```python
# Instead of storing in DB, load from Django settings based on tenant
from django.conf import settings

@property
def sms_api_key(self):
    # Get from environment or secrets manager, never from DB
    tenant_id = self.tenant.id  # assuming multi-tenant
    return settings.TENANT_SECRETS.get(f"sms_api_key_{tenant_id}")
```

**Step 4** - Create migration to encrypt existing data
```bash
python manage.py makemigrations --name encrypt_credentials
python manage.py migrate
```

**Verification**: Dump database and verify no API keys in plain text:
```bash
python manage.py dumpdata school.SchoolProfile | grep -i api_key  # Should return nothing
```

**Timeline**: 2-4 hours

---

### 2. No Input Validation on Sensitive Fields

**Location**: `sms-backend/school/models.py` (throughout)

**Problem**:
```python
sms_sender_id = models.CharField(max_length=20, blank=True)
receipt_prefix = models.CharField(max_length=10, default='RCT-')
```
- No validators for format, injection attacks, SQL injection
- School admin could inject malicious values → system failure
- **Risk**: SMS provider rejects requests, or system behaves unexpectedly

**Solution Steps**:

**Step 1** - Add validators to sensitive fields:
```python
from django.core.validators import RegexValidator

SENDER_ID_VALIDATOR = RegexValidator(
    regex=r'^[A-Za-z0-9]{1,20}$',
    message='Sender ID must be alphanumeric, max 20 chars'
)

PREFIX_VALIDATOR = RegexValidator(
    regex=r'^[A-Z0-9\-]{1,10}$',
    message='Prefix must be alphanumeric + hyphens, max 10 chars'
)

class SchoolProfile(models.Model):
    sms_sender_id = models.CharField(
        max_length=20, 
        blank=True,
        validators=[SENDER_ID_VALIDATOR]
    )
    receipt_prefix = models.CharField(
        max_length=10,
        default='RCT-',
        validators=[PREFIX_VALIDATOR]
    )
```

**Step 2** - Add serializer validation in DRF:
```python
from rest_framework import serializers

class SchoolProfileSerializer(serializers.ModelSerializer):
    def validate_tax_percentage(self, value):
        if not 0 <= value <= 100:
            raise serializers.ValidationError("Tax % must be 0-100")
        return value
    
    def validate_late_fee_value(self, value):
        if value < 0:
            raise serializers.ValidationError("Late fee cannot be negative")
        return value

    class Meta:
        model = SchoolProfile
        fields = ['tax_percentage', 'late_fee_value', ...]
```

**Step 3** - Test with malicious input:
```python
# In tests:
def test_sender_id_injection():
    profile = SchoolProfile(sms_sender_id="'; DROP TABLE--")
    with pytest.raises(ValidationError):
        profile.full_clean()
```

**Timeline**: 1-2 hours

---

### 3. Financial System Lacks Audit Trail

**Problem**: 
- Users can modify invoices, payments, late fees without record
- Cannot answer: "Who changed what, when, why?"
- **Regulatory Risk**: Schools (and you) may violate accounting standards (IFRS, GAAP)

**Solution Steps**:

**Step 1** - Create audit model:
```python
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User

class AuditLog(models.Model):
    ACTION_CHOICES = [('CREATE', 'Create'), ('UPDATE', 'Update'), ('DELETE', 'Delete')]
    
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    
    old_values = models.JSONField()  # e.g., {"amount": "1000", "status": "pending"}
    new_values = models.JSONField()
    
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()
    
    class Meta:
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['user']),
        ]
```

**Step 2** - Add audit signal to track changes:
```python
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=Invoice)
def audit_invoice_change(sender, instance, created, **kwargs):
    action = 'CREATE' if created else 'UPDATE'
    
    # Get old values (requires tracking in request middleware)
    old_values = getattr(instance, '_old_values', {})
    new_values = model_to_dict(instance)
    
    AuditLog.objects.create(
        user=get_current_user(),  # Requires middleware
        content_type=ContentType.objects.get_for_model(Invoice),
        object_id=instance.id,
        action=action,
        old_values=old_values,
        new_values=new_values,
        ip_address=get_client_ip()  # From request
    )
```

**Step 3** - Add audit query endpoint:
```python
class InvoiceAuditViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, IsSuperAdminOrAccountant]
    
    def list(self, request, invoice_id):
        logs = AuditLog.objects.filter(
            object_id=invoice_id,
            content_type=ContentType.objects.get_for_model(Invoice)
        ).order_by('-timestamp')
        return Response(AuditLogSerializer(logs, many=True).data)
```

**Timeline**: 4-6 hours (complex but critical)

---

### 4. No Rate Limiting on Financial Endpoints

**Problem**:
- Attackers can brute force payment status checks
- Attacker can DOS billing generation
- **Risk**: Service outage during critical payment period (start of term)

**Solution Steps**:

**Step 1** - Install rate limiting:
```bash
pip install django-ratelimit
```

**Step 2** - Add to critical endpoints:
```python
from django_ratelimit.decorators import ratelimit
from rest_framework import viewsets

class InvoiceViewSet(viewsets.ModelViewSet):
    @ratelimit(key='user', rate='100/h', method='GET')
    def list(self, request):
        # 100 reads per hour per user
        return super().list(request)
    
    @ratelimit(key='user', rate='20/h', method='POST')
    def create(self, request):
        # 20 creates per hour per user
        return super().create(request)
    
    @ratelimit(key='user', rate='10/h', method=['PUT', 'PATCH'])
    def update(self, request, pk=None):
        # 10 updates per hour per user
        return super().update(request, pk)

class PaymentViewSet(viewsets.ModelViewSet):
    @ratelimit(key='ip', rate='5/m', method='POST')
    def create(self, request):
        # 5 payment attempts per minute per IP
        # Prevents brute force payment testing
        return super().create(request)
```

**Step 3** - Configure Redis backend (production):
```python
# settings.py
RATELIMIT_CACHE = 'default'  # Use Redis cache

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
    }
}
```

**Timeline**: 1 hour

---

### 5. No Tenant Isolation Test

**Problem**:
- Multi-tenant system but no automated test verifying Tenant A can't see Tenant B's data
- **CATASTROPHIC RISK**: Data breach affects customers, regulatory penalties, business closure

**Solution Steps**:

**Step 1** - Create isolation test:
```python
# sms-backend/school/tests/test_tenant_isolation.py
import pytest
from django.test import TestCase
from school.models import SchoolProfile, Invoice
from django_tenants.test.cases import TenantTestCase

class TenantIsolationTest(TenantTestCase):
    def setUp(self):
        # Create Tenant A
        self.tenant_a = Tenant.objects.create(
            schema_name='tenant_a',
            name='School A'
        )
        # Create Tenant B
        self.tenant_b = Tenant.objects.create(
            schema_name='tenant_b',
            name='School B'
        )
    
    def test_invoice_isolation(self):
        """User in Tenant A should not see Tenant B invoices"""
        # Login as user in tenant_a
        self.client.defaults['HTTP_HOST'] = 'tenant_a.example.com'
        user_a = User.objects.create_user('admin_a', password='pass')
        self.client.login(username='admin_a', password='pass')
        
        # Create invoice in tenant_a
        invoice_a = Invoice.objects.create(
            school=self.tenant_a.school_profile,
            amount=1000
        )
        
        # Switch to tenant_b
        self.client.defaults['HTTP_HOST'] = 'tenant_b.example.com'
        
        # Try to access tenant_a invoice
        response = self.client.get(f'/api/invoices/{invoice_a.id}/')
        self.assertEqual(response.status_code, 404)  # NOT 200
```

**Step 2** - Run in CI/CD:
```bash
pytest sms-backend/school/tests/test_tenant_isolation.py -v
```

**Step 3** - Add to pre-merge checklist
- Any PR touching authentication or tenant logic must pass this test

**Timeline**: 2 hours

---

## 🟠 HIGH PRIORITY ISSUES (This Sprint)

### 6. Credentials Encryption Implementation

**What**: Complete the encrypted fields setup from issue #1  
**Why**: Protect API keys if DB is compromised  
**How**: Use `django-encrypted-model-fields` + rotate keys quarterly  
**Owner**: Backend team  
**Timeline**: 4 hours  
**Acceptance**: `python manage.py dumpdata` shows no plain-text API keys

---

### 7. TypeScript Strictness Not Enforced

**Location**: `tsconfig.base.json`

**Problem**:
```json
"strictFunctionTypes": false,
"noUnusedLocals": false
```
- Dead code accumulates silently
- Type mismatches slip through
- React components can accept wrong prop types

**Solution**:

**Step 1** - Enable strict mode:
```json
{
  "compilerOptions": {
    "strict": true,
    "strictFunctionTypes": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true
  }
}
```

**Step 2** - Add pre-commit hook:
```bash
# .husky/pre-commit
#!/bin/sh
pnpm run typecheck || exit 1
```

**Step 3** - Run linter on CI:
```yaml
# .github/workflows/typecheck.yml
name: TypeScript Check
on: [push, pull_request]
jobs:
  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: pnpm/action-setup@v2
      - run: pnpm install
      - run: pnpm run typecheck
```

**Timeline**: 2 hours

---

### 8. Missing Mutations in React Query Client

**Location**: `lib/api-client-react/src/generated/api.ts`

**Problem**:
- Only read operations visible (useQuery, getHealthCheck)
- No mutations for creating/updating invoices, payments
- Financial operations need strong types + error handling

**Solution**:

**Step 1** - Check Orval config to generate mutations:
```yaml
# orval.config.yaml
generate:
  client: react-query
  target: ./lib/api-client-react/src/generated/api.ts
  httpClient: custom  # Your customFetch
  prettier: true
  mutationSuffix: useMutation  # Generate useCreateInvoice, etc
```

**Step 2** - Regenerate:
```bash
pnpm exec orval --config orval.config.yaml
```

**Step 3** - Use in React:
```typescript
import { useCreateInvoice } from '@workspace/api-client-react'

function CreateInvoiceForm() {
  const mutation = useCreateInvoice()
  
  const handleSubmit = async (data) => {
    try {
      await mutation.mutateAsync(data)
    } catch (error) {
      // Type-safe error handling
      toast.error(error.data?.message || 'Failed to create invoice')
    }
  }
}
```

**Timeline**: 2 hours

---

### 9. No CI/CD Pipeline

**Location**: `.github/workflows/` (doesn't exist)

**Problem**:
- Code merges without tests passing
- Quality gates not enforced
- Deploy manually (error-prone)

**Solution**:

**Step 1** - Create GitHub Actions workflow:
```yaml
# .github/workflows/test-and-lint.yml
name: Test & Lint

on: [push, pull_request]

jobs:
  typescript:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: pnpm/action-setup@v2
      - run: pnpm install
      - run: pnpm run typecheck
      - run: pnpm run lint  # Need to add this script
      - run: pnpm run build

  python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r sms-backend/requirements.txt
      - run: pip install black ruff pytest
      - run: black --check sms-backend/
      - run: ruff check sms-backend/
      - run: pytest sms-backend/ --cov
```

**Step 2** - Add lint scripts to package.json:
```json
{
  "scripts": {
    "lint": "eslint lib/ artifacts/ --ext .ts,.tsx",
    "format": "prettier --write ."
  }
}
```

**Step 3** - Protect main branch:
- Require all status checks to pass before merge
- Require code review from 1+ maintainer

**Timeline**: 3 hours

---

### 10. Unclear Architecture: Django + Express

**Problem**:
- Why do you have BOTH Django REST Framework AND Express?
- Django can serve the React app's API directly
- Express adds complexity, operational overhead, maintenance burden

**Options**:

**Option A - Keep Both (if you have good reason)**:
- Document in ARCHITECTURE.md why
- Example: "Express is BFF for mobile, Django for admin"
- Then: add API contract tests between layers

**Option B - Remove Express, use Django**:
- Generate React Query hooks from Django's OpenAPI schema (drf-spectacular)
- Simpler deploy (one backend service)
- Better performance (no extra hop)

**Option C - Keep Express but consolidate it**:
- Make Express the sole backend
- Rewrite critical Django logic in Node.js
- Use Prisma/Drizzle for ORM

**Recommendation**: Do Option A - Keep both but document why, add integration tests

**Timeline**: 1 hour (documentation) + 4 hours (testing)

---

## 🟡 MEDIUM PRIORITY (Next Sprint)

### 11. Database N+1 Query Problems

**Problem**: Django views likely fetch related objects inefficiently

**Example**:
```python
# BAD - causes N+1 queries
invoices = Invoice.objects.all()  # 1 query
for invoice in invoices:
    print(invoice.student.name)  # N queries
```

**Solution**:
```python
# GOOD - single query with JOIN
invoices = Invoice.objects.select_related('student').all()  # 1 query
for invoice in invoices:
    print(invoice.student.name)  # No additional queries
```

**How to find**:
```bash
pip install django-debug-toolbar
# Add to INSTALLED_APPS, run dev server, inspect query count
```

**Timeline**: 2-3 hours

---

### 12. Test Coverage for Financial Flows

**Problem**: 
- Payment calculations (late fees, tax, discounts) untested
- Risk: Billing bugs go to production
- Impact: Wrong invoices sent to schools

**Solution**:
```python
# sms-backend/finance/tests/test_invoicing.py
import pytest
from finance.models import Invoice
from school.models import SchoolProfile

@pytest.mark.django_db
class TestInvoiceCalculation:
    def test_invoice_with_late_fee(self):
        """Late invoice should include late fee"""
        school = SchoolProfile.objects.create(
            school_name="Test School",
            late_fee_value=100,
            late_fee_type='FLAT'
        )
        invoice = Invoice.objects.create(
            school=school,
            amount=1000,
            due_date=timezone.now() - timedelta(days=5)  # 5 days late
        )
        
        total = invoice.get_total_with_fees()
        assert total == 1100  # 1000 + 100 late fee
    
    def test_invoice_with_tax(self):
        school = SchoolProfile.objects.create(
            school_name="Test",
            tax_percentage=16
        )
        invoice = Invoice.objects.create(
            school=school,
            amount=1000
        )
        
        total = invoice.get_total_with_tax()
        assert total == 1160  # 1000 + 16%
    
    def test_late_fee_percentage(self):
        school = SchoolProfile.objects.create(
            school_name="Test",
            late_fee_value=5,
            late_fee_type='PERCENT',
            late_fee_max=500
        )
        invoice = Invoice.objects.create(
            school=school,
            amount=10000,
            due_date=timezone.now() - timedelta(days=10)
        )
        
        fee = invoice.calculate_late_fee()
        assert fee == 500  # 5% = 500, capped at max
```

**Timeline**: 4-6 hours

---

### 13. React Bundle Size Audit

**Problem**:
- 55+ Radix UI components imported in package.json
- Likely shipping code for 40 components never used

**Solution**:
```bash
# Analyze bundle
npm install --save-dev webpack-bundle-analyzer

# Add to Vite config
import { BundleAnalyzerPlugin } from 'webpack-bundle-analyzer'

# Run build + analyze
npm run build && npm run analyze
```

**Expected outcome**:
- Remove unused component imports
- Bundle size drops from ~150KB to ~80KB (gzip)
- Faster page load, better mobile experience

**Timeline**: 2 hours

---

### 14. Error Boundary in React

**Problem**:
- If a component crashes, entire app crashes
- Users see blank page

**Solution**:
```typescript
// lib/components/ErrorBoundary.tsx
import { Component, ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error) {
    console.error('Error caught:', error)
    // Send to error tracking (Sentry)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center h-screen">
          <div className="text-center">
            <h1 className="text-2xl font-bold">Something went wrong</h1>
            <p className="text-gray-600">{this.state.error?.message}</p>
            <button onClick={() => window.location.reload()}>
              Reload Page
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
```

**Use in App.tsx**:
```typescript
export default function App() {
  return (
    <ErrorBoundary>
      <div className="min-h-screen...">
        {/* App content */}
      </div>
    </ErrorBoundary>
  )
}
```

**Timeline**: 1 hour

---

### 15. Document Architecture Decisions

**Files to create**:

**1. ARCHITECTURE.md**
```markdown
# Architecture Overview

## Components
- **Django**: Core business logic, multi-tenant, ORM
- **Express**: API gateway (optional, clarify if needed)
- **React**: Frontend for schools and admins
- **PostgreSQL**: Primary database with tenant schemas

## Data Flow
School Admin → React App → Express/Django API → PostgreSQL

## Tenant Isolation
- Each school = separate PostgreSQL schema (django-tenants)
- Row-level security + schema isolation
- No cross-tenant queries possible

## Authentication
- JWT tokens from Django
- Bearer token in React Query requests
```

**2. DEPLOYMENT.md**
```markdown
# Deployment Guide

## Prerequisites
- Python 3.11+
- PostgreSQL 13+
- Node 18+
- pnpm 9+

## Local Development
```bash
cd sms-backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

# In another terminal
cd artifacts/rynaty-space
pnpm install
pnpm run dev
```

## Production Deploy
[Instructions for Docker, Kubernetes, etc]
```

**3. TESTING.md**
```markdown
# Testing Strategy

## Unit Tests
- Django models: Test calculation logic
- React components: Test user interactions

## Integration Tests
- API endpoints: Test request/response
- Tenant isolation: Verify data boundaries

## E2E Tests
- Full invoice workflow: Create → Pay → Reconcile
```

**Timeline**: 2-3 hours

---

## 🟢 LOW PRIORITY (Nice to Have)

### 16. Add Sentry for Error Tracking

Track production errors without manual user reports

```python
# pip install sentry-sdk
import sentry_sdk

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    environment="production",
    traces_sample_rate=0.1,
)
```

**Timeline**: 1 hour

---

### 17. Add Stripe/M-Pesa Integration Tests

Mock payment provider to test payment flows

```python
@mock.patch('stripe.Charge.create')
def test_payment_with_stripe(mock_charge):
    mock_charge.return_value = {'id': 'ch_123', 'amount': 10000}
    result = process_payment(amount=10000)
    assert result.status == 'success'
```

**Timeline**: 3 hours

---

### 18. Performance Monitoring

Add APM (Application Performance Monitoring)

```python
# pip install django-silk
INSTALLED_APPS = [
    'silk',
]

# Access at /silk/ to see slow queries
```

**Timeline**: 1 hour

---

## Summary: Implementation Roadmap

### **Week 1 (CRITICAL - Do This First)**
- [ ] Move API keys to encrypted fields (#1)
- [ ] Add input validators (#2)
- [ ] Set up audit trail (#3)
- [ ] Add rate limiting (#4)
- [ ] Write tenant isolation test (#5)

### **Week 2 (HIGH - This Sprint)**
- [ ] Complete encryption implementation (#6)
- [ ] Fix TypeScript strictness (#7)
- [ ] Generate React mutations (#8)
- [ ] Set up CI/CD (#9)
- [ ] Document architecture (#10 part)

### **Week 3 (MEDIUM - Next Sprint)**
- [ ] Fix N+1 queries (#11)
- [ ] Write financial tests (#12)
- [ ] Audit bundle size (#13)
- [ ] Add error boundary (#14)
- [ ] Complete documentation (#15)

### **Week 4+ (LOW - Polish)**
- [ ] Add Sentry (#16)
- [ ] Integration tests (#17)
- [ ] APM setup (#18)

---

## Checklist Before Production

- [ ] All CRITICAL issues fixed
- [ ] CI/CD passing on all commits
- [ ] Financial flow tests passing (>80% coverage)
- [ ] Tenant isolation test passing
- [ ] Security audit completed (credentials encrypted, no SQL injection)
- [ ] Load testing done (500+ concurrent users)
- [ ] Backup/disaster recovery plan documented
- [ ] Monitoring + alerting set up (Sentry, DataDog, etc)
- [ ] README + Architecture docs completed
- [ ] Legal review: Terms of Service, Privacy Policy
- [ ] Compliance: GDPR (data export/deletion), Kenya DPA

---

## Questions to Clarify

1. **Why both Django + Express?** (Blocker for architecture decisions)
2. **Which payment provider is live?** (M-Pesa? Stripe?)
3. **How many schools/users are you targeting in 6 months?** (Affects scaling decisions)
4. **Is financial audit trail a regulatory requirement?** (IFRS/GAAP compliance)
5. **Who has database access?** (Risk assessment for credential storage)

---

**Next Step**: Pick the top 5 CRITICAL issues and create a sprint. Track completion in GitHub Issues or Linear.

