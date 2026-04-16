# M-Pesa Payment Integration - Enterprise Task Guide
## Multi-Tenant School Management SaaS Platform

**Stack:** Django + DRF + PostgreSQL + Redis + Celery  
**Context:** Existing multi-tenant school management system requiring financial-grade payment infrastructure  
**Goal:** Production-ready M-Pesa integration with ledger accounting, fraud detection, audit compliance, and SaaS billing

---

## EXECUTIVE SUMMARY

This task implements a complete financial infrastructure layer for your existing school management SaaS. The system must handle real money with bank-grade reliability, supporting:

- M-Pesa STK Push (deposits)
- M-Pesa B2C (withdrawals/refunds)
- Double-entry ledger accounting
- Multi-tenant data isolation
- Automated SaaS billing
- Real-time fraud detection
- Tamper-proof audit trails
- Regulatory compliance

---

## PHASE 1: CORE INFRASTRUCTURE (Foundation)

### 1.1 Multi-Tenant Middleware & Base Models

**File:** `core/middleware.py`

Implement tenant resolution via subdomain:
```python
class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split('.')[0]
        try:
            request.school = School.objects.get(code=host, active=True)
            request.tenant = request.school
        except School.DoesNotExist:
            request.school = None
            request.tenant = None
        return self.get_response(request)
```

**File:** `core/models.py`

Create abstract base model for all tenant-scoped models:
```python
class TenantModel(models.Model):
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['school', 'created_at']),
        ]

    @classmethod
    def for_school(cls, school):
        return cls.objects.filter(school=school)
```

### 1.2 School Model Extensions

**File:** `schools/models.py` (Extend existing)

Add to your existing School model:
```python
class School(models.Model):
    # Existing fields...
    
    # M-Pesa Configuration (per school)
    mpesa_shortcode = models.CharField(max_length=20, blank=True)
    mpesa_passkey = models.CharField(max_length=255, blank=True)
    mpesa_consumer_key = models.CharField(max_length=255, blank=True)
    mpesa_consumer_secret = models.CharField(max_length=255, blank=True)
    mpesa_environment = models.CharField(
        max_length=10, 
        choices=[('sandbox', 'Sandbox'), ('live', 'Live')],
        default='sandbox'
    )
    
    # SaaS Subscription
    subscription_active = models.BooleanField(default=True)
    subscription_expires_at = models.DateTimeField(null=True, blank=True)
    plan = models.ForeignKey('billing.Plan', on_delete=models.SET_NULL, null=True)
    
    # Billing
    admin_phone = models.CharField(max_length=20, blank=True)
    admin_email = models.EmailField(blank=True)
    
    # Status
    active = models.BooleanField(default=True, db_index=True)
    suspended_reason = models.TextField(blank=True)
    
    def is_subscription_active(self):
        if not self.subscription_active:
            return False
        if self.subscription_expires_at and self.subscription_expires_at < timezone.now():
            return False
        return True
```

### 1.3 Environment Configuration

**File:** `.env.example`

```
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/schoolsaas

# Redis (Celery + Cache)
REDIS_URL=redis://localhost:6379/0

# M-Pesa Master (Fallback)
MPESA_CONSUMER_KEY=your_consumer_key
MPESA_CONSUMER_SECRET=your_consumer_secret
MPESA_SHORTCODE=174379
MPESA_PASSKEY=your_passkey
MPESA_BASE_URL=https://sandbox.safaricom.co.ke

# Security
SECRET_KEY=your_django_secret
JWT_SECRET=your_jwt_secret

# Email (Alerts)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=alerts@yoursaas.com
EMAIL_PASS=your_app_password
```

---

## PHASE 2: LEDGER SYSTEM (Financial Core)

### 2.1 Ledger Models

**File:** `ledger/models.py`

```python
from core.models import TenantModel
from django.db import models, transaction
from decimal import Decimal

class LedgerEntry(TenantModel):
    ENTRY_TYPES = [
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAWAL', 'Withdrawal'),
        ('FEE_PAYMENT', 'Fee Payment'),
        ('REFUND', 'Refund'),
        ('ADMIN_ADJUSTMENT', 'Admin Adjustment'),
        ('TRANSACTION_FEE', 'Transaction Fee'),
        ('SCHOOL_CREDIT', 'School Credit'),
    ]
    
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='ledger_entries')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPES)
    reference = models.CharField(max_length=100, db_index=True)
    description = models.TextField(blank=True)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    
    # For admin adjustments
    adjusted_by = models.ForeignKey('auth.User', null=True, on_delete=models.SET_NULL, related_name='adjustments_made')
    adjustment_reason = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school', 'user', 'created_at']),
            models.Index(fields=['reference']),
        ]

class Wallet(TenantModel):
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    frozen_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    last_activity = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['school', 'user']),
        ]
    
    @transaction.atomic
    def credit(self, amount, entry_type, reference, description='', **kwargs):
        amount = Decimal(str(amount))
        self.balance += amount
        self.save()
        
        return LedgerEntry.objects.create(
            school=self.school,
            user=self.user,
            amount=amount,
            entry_type=entry_type,
            reference=reference,
            description=description,
            balance_after=self.balance,
            **kwargs
        )
    
    @transaction.atomic
    def debit(self, amount, entry_type, reference, description='', **kwargs):
        amount = Decimal(str(amount))
        if self.balance < amount:
            raise ValueError("Insufficient balance")
        
        self.balance -= amount
        self.save()
        
        return LedgerEntry.objects.create(
            school=self.school,
            user=self.user,
            amount=-amount,
            entry_type=entry_type,
            reference=reference,
            description=description,
            balance_after=self.balance,
            **kwargs
        )
    
    @classmethod
    def get_or_create_for_user(cls, user, school):
        wallet, created = cls.objects.get_or_create(
            school=school,
            user=user,
            defaults={'balance': Decimal('0.00')}
        )
        return wallet
```

---

## PHASE 3: M-PESA PAYMENT INTEGRATION

### 3.1 M-Pesa API Client

**File:** `payments/mpesa_client.py`

```python
import base64
import requests
from datetime import datetime
from django.conf import settings

class MpesaClient:
    def __init__(self, school=None):
        self.school = school
        self.base_url = self._get_config('MPESA_BASE_URL')
        self.consumer_key = self._get_config('MPESA_CONSUMER_KEY')
        self.consumer_secret = self._get_config('MPESA_CONSUMER_SECRET')
        self.shortcode = self._get_config('MPESA_SHORTCODE')
        self.passkey = self._get_config('MPESA_PASSKEY')
    
    def _get_config(self, key):
        if self.school and getattr(self.school, key.lower(), None):
            return getattr(self.school, key.lower())
        return getattr(settings, key)
    
    def get_access_token(self):
        url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        credentials = base64.b64encode(
            f"{self.consumer_key}:{self.consumer_secret}".encode()
        ).decode()
        
        response = requests.get(url, headers={
            'Authorization': f'Basic {credentials}'
        })
        response.raise_for_status()
        return response.json()['access_token']
    
    def generate_password(self):
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password_str = f"{self.shortcode}{self.passkey}{timestamp}"
        password = base64.b64encode(password_str.encode()).decode()
        return password, timestamp
    
    def stk_push(self, phone, amount, account_reference, description="Payment"):
        token = self.get_access_token()
        password, timestamp = self.generate_password()
        
        # Format phone (remove +254, add 254)
        phone = self._format_phone(phone)
        
        payload = {
            'BusinessShortCode': self.shortcode,
            'Password': password,
            'Timestamp': timestamp,
            'TransactionType': 'CustomerPayBillOnline',
            'Amount': int(amount),
            'PartyA': phone,
            'PartyB': self.shortcode,
            'PhoneNumber': phone,
            'CallBackURL': f"{settings.BASE_URL}/api/payments/mpesa/callback/",
            'AccountReference': account_reference[:12],
            'TransactionDesc': description[:13]
        }
        
        response = requests.post(
            f"{self.base_url}/mpesa/stkpush/v1/processrequest",
            json=payload,
            headers={'Authorization': f'Bearer {token}'}
        )
        response.raise_for_status()
        return response.json()
    
    def b2c_payment(self, phone, amount, remarks="Withdrawal"):
        token = self.get_access_token()
        phone = self._format_phone(phone)
        
        payload = {
            'InitiatorName': 'api',
            'SecurityCredential': self._get_security_credential(),
            'CommandID': 'BusinessPayment',
            'Amount': int(amount),
            'PartyA': self.shortcode,
            'PartyB': phone,
            'Remarks': remarks,
            'QueueTimeOutURL': f"{settings.BASE_URL}/api/payments/mpesa/b2c/timeout/",
            'ResultURL': f"{settings.BASE_URL}/api/payments/mpesa/b2c/result/",
            'Occasion': 'Withdrawal'
        }
        
        response = requests.post(
            f"{self.base_url}/mpesa/b2c/v1/paymentrequest",
            json=payload,
            headers={'Authorization': f'Bearer {token}'}
        )
        response.raise_for_status()
        return response.json()
    
    def _format_phone(self, phone):
        phone = str(phone).replace('+', '').replace(' ', '')
        if phone.startswith('0'):
            phone = '254' + phone[1:]
        return phone
    
    def _get_security_credential(self):
        # Implement certificate encryption for production
        return "YOUR_ENCRYPTED_CREDENTIAL"
```

### 3.2 Transaction Models

**File:** `payments/models.py`

```python
from core.models import TenantModel
from django.db import models, transaction as db_transaction
from decimal import Decimal
import uuid

class Transaction(TenantModel):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    TYPE_CHOICES = [
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAWAL', 'Withdrawal'),
        ('FEE_PAYMENT', 'Fee Payment'),
        ('REFUND', 'Refund'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='transactions')
    
    # Payment details
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # M-Pesa specific
    phone_number = models.CharField(max_length=20)
    mpesa_receipt = models.CharField(max_length=50, unique=True, null=True, blank=True)
    merchant_request_id = models.CharField(max_length=100, blank=True)
    checkout_request_id = models.CharField(max_length=100, blank=True)
    result_code = models.CharField(max_length=10, blank=True)
    result_desc = models.TextField(blank=True)
    
    # Linked records
    invoice = models.ForeignKey('billing.Invoice', null=True, on_delete=models.SET_NULL)
    ledger_entry = models.ForeignKey('ledger.LedgerEntry', null=True, on_delete=models.SET_NULL)
    
    # Metadata
    description = models.TextField(blank=True)
    callback_payload = models.JSONField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school', 'user', 'status']),
            models.Index(fields=['mpesa_receipt']),
            models.Index(fields=['merchant_request_id']),
            models.Index(fields=['created_at']),
        ]
    
    @property
    def is_successful(self):
        return self.status == 'SUCCESS'
    
    @property
    def is_pending(self):
        return self.status in ['PENDING', 'PROCESSING']

class MpesaRawLog(TenantModel):
    """Store raw M-Pesa callbacks for audit trail"""
    payload = models.JSONField()
    endpoint = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField()
    processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
```

### 3.3 Payment Views (API Endpoints)

**File:** `payments/views.py`

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import transaction as db_transaction
from django.utils import timezone
import json

from .models import Transaction, MpesaRawLog
from .mpesa_client import MpesaClient
from .serializers import STKPushSerializer, TransactionSerializer
from ledger.models import Wallet
from audit.models import AuditLog
from fraud_detection.engine import FraudDetectionEngine

class STKPushView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        school = request.school
        
        # Check subscription
        if not school or not school.is_subscription_active():
            return Response(
                {'error': 'School subscription inactive'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = STKPushSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        phone = serializer.validated_data['phone']
        amount = serializer.validated_data['amount']
        invoice_id = serializer.validated_data.get('invoice_id')
        
        # Fraud check
        fraud_engine = FraudDetectionEngine(school, request.user)
        risk_score = fraud_engine.check_deposit_risk(amount, phone)
        
        if risk_score > 80:
            return Response(
                {'error': 'Transaction blocked due to high risk'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Create pending transaction
        with db_transaction.atomic():
            tx = Transaction.objects.create(
                school=school,
                user=request.user,
                phone_number=phone,
                amount=amount,
                transaction_type='DEPOSIT',
                status='PENDING',
                invoice_id=invoice_id,
                description=f'STK Push deposit of {amount}'
            )
        
        # Initiate M-Pesa STK Push
        try:
            mpesa = MpesaClient(school)
            account_ref = f"SCH{school.id}U{request.user.id}"
            
            response = mpesa.stk_push(
                phone=phone,
                amount=amount,
                account_reference=account_ref,
                description=f"Deposit for {request.user.get_full_name()}"
            )
            
            # Update transaction with M-Pesa IDs
            tx.merchant_request_id = response.get('MerchantRequestID')
            tx.checkout_request_id = response.get('CheckoutRequestID')
            tx.status = 'PROCESSING'
            tx.save()
            
            # Audit log
            AuditLog.log_action(
                request, 'STK_PUSH_INITIATED', 'TRANSACTION', 
                str(tx.id), {'amount': str(amount), 'phone': phone}
            )
            
            return Response({
                'success': True,
                'transaction_id': str(tx.id),
                'message': 'STK push sent to your phone',
                'checkout_request_id': tx.checkout_request_id
            })
            
        except Exception as e:
            tx.status = 'FAILED'
            tx.result_desc = str(e)
            tx.save()
            return Response(
                {'error': f'M-Pesa request failed: {str(e)}'}, 
                status=status.HTTP_502_BAD_GATEWAY
            )

class MpesaCallbackView(APIView):
    authentication_classes = []
    permission_classes = []
    
    def post(self, request):
        # Log raw callback first
        ip = self._get_client_ip(request)
        raw_log = MpesaRawLog.objects.create(
            school=None,  # Will be determined from callback
            payload=request.data,
            endpoint='stk_callback',
            ip_address=ip
        )
        
        try:
            data = request.data
            callback = data.get('Body', {}).get('stkCallback', {})
            
            result_code = callback.get('ResultCode')
            result_desc = callback.get('ResultDesc')
            merchant_request_id = callback.get('MerchantRequestID')
            checkout_request_id = callback.get('CheckoutRequestID')
            
            # Find transaction
            try:
                tx = Transaction.objects.get(
                    checkout_request_id=checkout_request_id,
                    merchant_request_id=merchant_request_id
                )
            except Transaction.DoesNotExist:
                raw_log.processing_error = "Transaction not found"
                raw_log.save()
                return Response({'status': 'ok'})
            
            # Update raw log with school
            raw_log.school = tx.school
            raw_log.processed = True
            raw_log.save()
            
            # Update transaction
            tx.callback_payload = data
            tx.result_code = str(result_code)
            tx.result_desc = result_desc
            
            if result_code != 0:
                tx.status = 'FAILED'
                tx.save()
                return Response({'status': 'ok'})
            
            # Extract payment details
            metadata = callback.get('CallbackMetadata', {}).get('Item', [])
            amount = next((i['Value'] for i in metadata if i['Name'] == 'Amount'), 0)
            phone = next((i['Value'] for i in metadata if i['Name'] == 'PhoneNumber'), '')
            receipt = next((i['Value'] for i in metadata if i['Name'] == 'MpesaReceiptNumber'), '')
            
            # Idempotency check - CRITICAL
            if Transaction.objects.filter(mpesa_receipt=receipt).exclude(id=tx.id).exists():
                tx.status = 'FAILED'
                tx.result_desc = 'Duplicate receipt number'
                tx.save()
                return Response({'status': 'duplicate'})
            
            # Process successful payment atomically
            with db_transaction.atomic():
                tx.amount = amount
                tx.phone_number = phone
                tx.mpesa_receipt = receipt
                tx.status = 'SUCCESS'
                tx.processed_at = timezone.now()
                tx.save()
                
                # Credit wallet
                wallet = Wallet.get_or_create_for_user(tx.user, tx.school)
                ledger_entry = wallet.credit(
                    amount=amount,
                    entry_type='DEPOSIT',
                    reference=receipt,
                    description=f'M-Pesa deposit ({receipt})'
                )
                tx.ledger_entry = ledger_entry
                tx.save()
                
                # Apply to invoice if linked
                if tx.invoice:
                    tx.invoice.apply_payment(amount)
                
                # Apply SaaS transaction fee
                from billing.engine import BillingEngine
                BillingEngine.apply_transaction_fee(tx.school, amount, receipt)
            
            return Response({'status': 'ok'})
            
        except Exception as e:
            raw_log.processing_error = str(e)
            raw_log.save()
            return Response({'status': 'error'}, status=500)
    
    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')

class TransactionListView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        transactions = Transaction.for_school(request.school).filter(
            user=request.user
        )[:50]
        serializer = TransactionSerializer(transactions, many=True)
        return Response(serializer.data)

class AdminAdjustBalanceView(APIView):
    """Admin endpoint for manual balance adjustments"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        if request.user.role not in ['ADMIN', 'BURSAR']:
            return Response({'error': 'Permission denied'}, status=403)
        
        user_id = request.data.get('user_id')
        amount = Decimal(str(request.data.get('amount', 0)))
        reason = request.data.get('reason', '')
        
        if not reason:
            return Response({'error': 'Reason required'}, status=400)
        
        try:
            user = User.objects.get(id=user_id, school=request.school)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)
        
        wallet = Wallet.get_or_create_for_user(user, request.school)
        
        with db_transaction.atomic():
            if amount > 0:
                entry = wallet.credit(
                    amount=amount,
                    entry_type='ADMIN_ADJUSTMENT',
                    reference=f"ADJ-{timezone.now().timestamp()}",
                    description=reason,
                    adjusted_by=request.user,
                    adjustment_reason=reason
                )
            else:
                entry = wallet.debit(
                    amount=abs(amount),
                    entry_type='ADMIN_ADJUSTMENT',
                    reference=f"ADJ-{timezone.now().timestamp()}",
                    description=reason,
                    adjusted_by=request.user,
                    adjustment_reason=reason
                )
            
            # Audit log
            AuditLog.log_action(
                request, 'BALANCE_ADJUSTED', 'WALLET', 
                str(wallet.id), {
                    'amount': str(amount),
                    'reason': reason,
                    'target_user': str(user.id)
                }
            )
        
        return Response({
            'success': True,
            'new_balance': str(wallet.balance),
            'ledger_entry_id': str(entry.id)
        })
```

---

## PHASE 4: BILLING & INVOICE SYSTEM

### 4.1 Billing Models

**File:** `billing/models.py`

```python
from core.models import TenantModel
from django.db import models, transaction as db_transaction
from decimal import Decimal

class Plan(models.Model):
    """SaaS subscription plans"""
    name = models.CharField(max_length=50)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2)
    per_student_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    transaction_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))
    max_students = models.IntegerField(default=1000)
    features = models.JSONField(default=dict)
    
    def __str__(self):
        return self.name

class Invoice(TenantModel):
    STATUS_CHOICES = [
        ('UNPAID', 'Unpaid'),
        ('PARTIAL', 'Partially Paid'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    student = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='invoices')
    term = models.CharField(max_length=50)
    year = models.IntegerField()
    
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    balance = models.DecimalField(max_digits=12, decimal_places=2)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='UNPAID')
    due_date = models.DateField()
    
    # Line items (JSON for flexibility)
    line_items = models.JSONField(default=list)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school', 'student', 'status']),
            models.Index(fields=['due_date']),
        ]
    
    def save(self, *args, **kwargs):
        self.balance = self.total_amount - self.amount_paid
        super().save(*args, **kwargs)
    
    def apply_payment(self, amount):
        with db_transaction.atomic():
            self.amount_paid += Decimal(str(amount))
            self.balance = self.total_amount - self.amount_paid
            
            if self.amount_paid >= self.total_amount:
                self.status = 'PAID'
            elif self.amount_paid > 0:
                self.status = 'PARTIAL'
            
            self.save()
            return self.status

class SaaSInvoice(models.Model):
    """Invoices WE send to schools"""
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, default='PENDING')
    invoice_type = models.CharField(max_length=20)  # SUBSCRIPTION, USAGE, FEES
    period_start = models.DateField()
    period_end = models.DateField()
    paid_at = models.DateTimeField(null=True)
    
    class Meta:
        ordering = ['-created_at']

class RevenueLog(models.Model):
    """Track OUR revenue"""
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    source = models.CharField(max_length=20)  # TRANSACTION_FEE, SUBSCRIPTION
    transaction = models.ForeignKey('payments.Transaction', null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
```

### 4.2 Billing Engine

**File:** `billing/engine.py`

```python
from decimal import Decimal
from django.utils import timezone
from .models import RevenueLog, SaaSInvoice
from ledger.models import Wallet

class BillingEngine:
    @staticmethod
    def apply_transaction_fee(school, amount, reference):
        """Take % fee from each transaction"""
        if not school.plan:
            return
        
        fee_percent = school.plan.transaction_fee_percent
        if fee_percent <= 0:
            return
        
        fee = (fee_percent / 100) * Decimal(str(amount))
        
        # Log our revenue
        RevenueLog.objects.create(
            school=school,
            amount=fee,
            source='TRANSACTION_FEE'
        )
        
        # School's net credit
        net_amount = Decimal(str(amount)) - fee
        
        return fee
    
    @staticmethod
    def generate_monthly_bills():
        """Generate subscription invoices for all schools"""
        from schools.models import School
        from celery import shared_task
        
        for school in School.objects.filter(active=True):
            plan = school.plan
            if not plan:
                continue
            
            student_count = school.students.count()
            amount = plan.monthly_price + (student_count * plan.per_student_price)
            
            # Minimum monthly guarantee
            amount = max(amount, Decimal('500'))
            
            SaaSInvoice.objects.create(
                school=school,
                amount=amount,
                invoice_type='SUBSCRIPTION',
                period_start=timezone.now().replace(day=1),
                period_end=timezone.now()
            )
```

---

## PHASE 5: FRAUD DETECTION & ALERTS

### 5.1 Alert Models

**File:** `fraud_detection/models.py`

```python
from core.models import TenantModel
from django.db import models

class Alert(TenantModel):
    LEVEL_CHOICES = [
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('CRITICAL', 'Critical'),
    ]
    
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES)
    alert_type = models.CharField(max_length=50)  # DUPLICATE_RECEIPT, LARGE_TX, RAPID_TX, etc
    message = models.TextField()
    reference = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict)
    resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey('auth.User', null=True, on_delete=models.SET_NULL)
    resolved_at = models.DateTimeField(null=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school', 'level', 'resolved']),
            models.Index(fields=['created_at']),
        ]

class RiskScoreLog(TenantModel):
    """Track risk scores for analysis"""
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    transaction_amount = models.DecimalField(max_digits=12, decimal_places=2)
    risk_score = models.IntegerField()
    factors = models.JSONField(default=list)
    action_taken = models.CharField(max_length=50)  # ALLOWED, BLOCKED, FLAGGED
```

### 5.2 Fraud Detection Engine

**File:** `fraud_detection/engine.py`

```python
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from .models import Alert, RiskScoreLog
from payments.models import Transaction

class FraudDetectionEngine:
    LARGE_AMOUNT_THRESHOLD = 100000  # KES
    RAPID_TX_THRESHOLD = 5  # transactions per minute
    HIGH_RISK_THRESHOLD = 70
    CRITICAL_RISK_THRESHOLD = 90
    
    def __init__(self, school, user):
        self.school = school
        self.user = user
    
    def check_deposit_risk(self, amount, phone):
        """Calculate risk score for deposit"""
        score = 0
        factors = []
        
        # Factor 1: Large amount
        if amount > self.LARGE_AMOUNT_THRESHOLD:
            score += 40
            factors.append('large_amount')
        
        # Factor 2: Rapid transactions
        recent_count = Transaction.objects.filter(
            school=self.school,
            phone_number=phone,
            created_at__gte=timezone.now() - timedelta(minutes=1)
        ).count()
        
        if recent_count > self.RAPID_TX_THRESHOLD:
            score += 30
            factors.append('rapid_transactions')
        
        # Factor 3: New user (first transaction)
        user_tx_count = Transaction.objects.filter(
            school=self.school,
            user=self.user
        ).count()
        
        if user_tx_count == 0:
            score += 20
            factors.append('new_user')
        
        # Factor 4: Phone mismatch
        if self.user.phone != phone:
            score += 10
            factors.append('phone_mismatch')
        
        # Log risk score
        action = 'ALLOWED'
        if score >= self.CRITICAL_RISK_THRESHOLD:
            action = 'BLOCKED'
            self._create_alert('CRITICAL', 'HIGH_RISK_TRANSACTION', 
                             f'High risk transaction blocked: score {score}', 
                             factors)
        elif score >= self.HIGH_RISK_THRESHOLD:
            action = 'FLAGGED'
            self._create_alert('WARNING', 'ELEVATED_RISK',
                             f'Elevated risk transaction: score {score}',
                             factors)
        
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
        """Check for duplicate M-Pesa receipts"""
        if Transaction.objects.filter(
            school=self.school,
            mpesa_receipt=receipt
        ).exists():
            self._create_alert(
                'CRITICAL',
                'DUPLICATE_RECEIPT',
                f'Duplicate receipt detected: {receipt}',
                {'receipt': receipt}
            )
            return True
        return False
    
    def check_reconciliation_mismatch(self, mpesa_amount, db_amount, receipt):
        """Detect reconciliation mismatches"""
        if Decimal(str(mpesa_amount)) != Decimal(str(db_amount)):
            self._create_alert(
                'CRITICAL',
                'RECONCILIATION_MISMATCH',
                f'Amount mismatch for {receipt}: M-Pesa={mpesa_amount}, DB={db_amount}',
                {'receipt': receipt, 'mpesa_amount': str(mpesa_amount), 'db_amount': str(db_amount)}
            )
            return True
        return False
    
    def check_overdraft_attempt(self, amount, wallet):
        """Detect attempted overdrafts"""
        if Decimal(str(amount)) > wallet.balance:
            self._create_alert(
                'CRITICAL',
                'OVERDRAFT_ATTEMPT',
                f'Overdraft attempt: {amount} > balance {wallet.balance}',
                {'attempted': str(amount), 'balance': str(wallet.balance)}
            )
            return True
        return False
    
    def _create_alert(self, level, alert_type, message, metadata=None):
        Alert.objects.create(
            school=self.school,
            level=level,
            alert_type=alert_type,
            message=message,
            metadata=metadata or {}
        )
```

---

## PHASE 6: AUDIT & COMPLIANCE SYSTEM

### 6.1 Audit Models

**File:** `audit/models.py`

```python
from core.models import TenantModel
from django.db import models
import hashlib
import json

class AuditLog(TenantModel):
    """Tamper-proof audit trail"""
    ACTION_CHOICES = [
        ('PAYMENT_RECEIVED', 'Payment Received'),
        ('BALANCE_UPDATED', 'Balance Updated'),
        ('SCHOOL_SUSPENDED', 'School Suspended'),
        ('STK_PUSH_INITIATED', 'STK Push Initiated'),
        ('BALANCE_ADJUSTED', 'Balance Adjusted'),
        ('WITHDRAWAL_APPROVED', 'Withdrawal Approved'),
        ('INVOICE_CREATED', 'Invoice Created'),
        ('INVOICE_PAID', 'Invoice Paid'),
        ('USER_LOGIN', 'User Login'),
        ('USER_LOGOUT', 'User Logout'),
    ]
    
    user = models.ForeignKey('auth.User', null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    entity = models.CharField(max_length=50)  # TRANSACTION, WALLET, USER, etc
    entity_id = models.CharField(max_length=100)
    
    # Before/after values for traceability
    metadata = models.JSONField(default=dict)
    
    # Request info
    ip_address = models.GenericIPAddressField(null=True)
    user_agent = models.TextField(blank=True)
    
    # Tamper-proof chain
    entry_hash = models.CharField(max_length=64, db_index=True)
    previous_hash = models.CharField(max_length=64, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school', 'action']),
            models.Index(fields=['entity', 'entity_id']),
            models.Index(fields=['created_at']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.entry_hash:
            self._compute_hash()
        super().save(*args, **kwargs)
    
    def _compute_hash(self):
        """Compute SHA-256 hash of entry for tamper detection"""
        # Get previous hash
        last_entry = AuditLog.objects.filter(school=self.school).first()
        self.previous_hash = last_entry.entry_hash if last_entry else '0' * 64
        
        # Create hash from data
        data = {
            'school_id': str(self.school_id),
            'user_id': str(self.user_id) if self.user else None,
            'action': self.action,
            'entity': self.entity,
            'entity_id': self.entity_id,
            'metadata': self.metadata,
            'timestamp': self.created_at.isoformat() if self.created_at else None,
            'previous_hash': self.previous_hash
        }
        
        hash_input = json.dumps(data, sort_keys=True)
        self.entry_hash = hashlib.sha256(hash_input.encode()).hexdigest()
    
    @classmethod
    def log_action(cls, request, action, entity, entity_id, metadata=None):
        """Convenience method to log actions"""
        return cls.objects.create(
            school=request.school,
            user=request.user if request.user.is_authenticated else None,
            action=action,
            entity=entity,
            entity_id=entity_id,
            metadata=metadata or {},
            ip_address=cls._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
    
    @staticmethod
    def _get_client_ip(request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')
    
    @classmethod
    def verify_chain(cls, school):
        """Verify integrity of audit chain for a school"""
        entries = cls.objects.filter(school=school).order_by('created_at')
        previous_hash = '0' * 64
        
        for entry in entries:
            if entry.previous_hash != previous_hash:
                return False, f"Chain broken at entry {entry.id}"
            previous_hash = entry.entry_hash
        
        return True, "Chain verified"

class ComplianceRule(models.Model):
    """Configurable compliance rules"""
    name = models.CharField(max_length=100)
    rule_type = models.CharField(max_length=50)
    threshold = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    active = models.BooleanField(default=True)
    
class ComplianceLog(models.Model):
    """Track compliance check results"""
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE)
    rule = models.CharField(max_length=100)
    status = models.CharField(max_length=20)  # PASS, FAIL
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
```

### 6.2 Compliance Engine

**File:** `audit/compliance.py`

```python
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from .models import ComplianceLog
from payments.models import Transaction

class ComplianceEngine:
    MAX_TRANSACTION_LIMIT = 150000  # Daily limit per user
    MAX_DAILY_VOLUME = 300000
    
    def __init__(self, school):
        self.school = school
    
    def check_transaction_limits(self, user, amount):
        """Check if transaction exceeds regulatory limits"""
        amount = Decimal(str(amount))
        
        # Single transaction limit
        if amount > self.MAX_TRANSACTION_LIMIT:
            return False, f"Transaction exceeds limit of {self.MAX_TRANSACTION_LIMIT}"
        
        # Daily volume limit
        today_total = Transaction.objects.filter(
            school=self.school,
            user=user,
            created_at__date=timezone.now().date(),
            status='SUCCESS'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
        
        if today_total + amount > self.MAX_DAILY_VOLUME:
            return False, f"Daily volume limit exceeded"
        
        return True, "Within limits"
    
    def run_daily_compliance_check(self):
        """Run all compliance checks and log results"""
        checks = [
            self._check_data_retention(),
            self._check_audit_completeness(),
            self._check_reconciliation_status(),
        ]
        
        return all(checks)
    
    def _check_data_retention(self):
        """Verify 7-year retention policy"""
        cutoff = timezone.now() - timedelta(days=7*365)
        old_records = Transaction.objects.filter(
            school=self.school,
            created_at__lt=cutoff
        ).exists()
        
        if old_records:
            ComplianceLog.objects.create(
                school=self.school,
                rule='DATA_RETENTION',
                status='PASS',
                details={'message': 'Records retained beyond 7 years'}
            )
        
        return True
    
    def _check_audit_completeness(self):
        """Verify all transactions have audit logs"""
        from audit.models import AuditLog
        
        recent_tx = Transaction.objects.filter(
            school=self.school,
            created_at__gte=timezone.now() - timedelta(days=1)
        )
        
        for tx in recent_tx:
            has_audit = AuditLog.objects.filter(
                school=self.school,
                entity='TRANSACTION',
                entity_id=str(tx.id)
            ).exists()
            
            if not has_audit:
                ComplianceLog.objects.create(
                    school=self.school,
                    rule='AUDIT_COMPLETENESS',
                    status='FAIL',
                    details={'transaction_id': str(tx.id), 'error': 'Missing audit log'}
                )
                return False
        
        return True
    
    def _check_reconciliation_status(self):
        """Check for unreconciled transactions"""
        unreconciled = Transaction.objects.filter(
            school=self.school,
            status='SUCCESS',
            mpesa_receipt__isnull=True
        ).exists()
        
        if unreconciled:
            ComplianceLog.objects.create(
                school=self.school,
                rule='RECONCILIATION',
                status='FAIL',
                details={'error': 'Unreconciled transactions found'}
            )
            return False
        
        return True
```

---

## PHASE 7: CELERY TASKS (Background Jobs)

### 7.1 Task Definitions

**File:** `payments/tasks.py`

```python
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from .models import Transaction
from .mpesa_client import MpesaClient
from fraud_detection.engine import FraudDetectionEngine
from audit.compliance import ComplianceEngine

@shared_task
def reconcile_transactions():
    """Daily reconciliation job"""
    from schools.models import School
    
    for school in School.objects.filter(active=True):
        try:
            # Fetch M-Pesa statement (implement based on API availability)
            mpesa = MpesaClient(school)
            # statement = mpesa.get_statement()
            
            # Check for missing transactions
            recent_tx = Transaction.objects.filter(
                school=school,
                created_at__gte=timezone.now() - timedelta(days=1),
                status='SUCCESS'
            )
            
            for tx in recent_tx:
                if not tx.mpesa_receipt:
                    FraudDetectionEngine(school, tx.user)._create_alert(
                        'WARNING',
                        'MISSING_RECEIPT',
                        f'Transaction {tx.id} missing M-Pesa receipt',
                        {'transaction_id': str(tx.id)}
                    )
                    
        except Exception as e:
            print(f"Reconciliation failed for {school.name}: {e}")

@shared_task
def check_pending_transactions():
    """Check and timeout old pending transactions"""
    timeout = timezone.now() - timedelta(minutes=5)
    
    old_pending = Transaction.objects.filter(
        status='PENDING',
        created_at__lt=timeout
    )
    
    for tx in old_pending:
        tx.status = 'FAILED'
        tx.result_desc = 'Transaction timed out'
        tx.save()

@shared_task
def generate_monthly_saas_bills():
    """Generate monthly subscription invoices"""
    from billing.engine import BillingEngine
    BillingEngine.generate_monthly_bills()

@shared_task
def suspend_expired_schools():
    """Auto-suspend schools with expired subscriptions"""
    from schools.models import School
    
    expired = School.objects.filter(
        subscription_expires_at__lt=timezone.now(),
        subscription_active=True
    )
    
    for school in expired:
        school.subscription_active = False
        school.save()
        
        from audit.models import AuditLog
        AuditLog.objects.create(
            school=school,
            action='SCHOOL_SUSPENDED',
            entity='SCHOOL',
            entity_id=str(school.id),
            metadata={'reason': 'Subscription expired'}
        )

@shared_task
def run_compliance_checks():
    """Daily compliance verification"""
    from schools.models import School
    
    for school in School.objects.filter(active=True):
        engine = ComplianceEngine(school)
        engine.run_daily_compliance_check()
```

### 7.2 Celery Configuration

**File:** `config/celery.py`

```python
from celery import Celery
from celery.schedules import crontab

app = Celery('schoolsaas')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

app.conf.beat_schedule = {
    'reconcile-transactions': {
        'task': 'payments.tasks.reconcile_transactions',
        'schedule': crontab(hour=23, minute=0),  # Daily at 11 PM
    },
    'check-pending-transactions': {
        'task': 'payments.tasks.check_pending_transactions',
        'schedule': 300.0,  # Every 5 minutes
    },
    'generate-monthly-bills': {
        'task': 'payments.tasks.generate_monthly_saas_bills',
        'schedule': crontab(day_of_month=1, hour=0, minute=0),  # Monthly
    },
    'suspend-expired-schools': {
        'task': 'payments.tasks.suspend_expired_schools',
        'schedule': crontab(hour=0, minute=0),  # Daily
    },
    'run-compliance-checks': {
        'task': 'payments.tasks.run_compliance_checks',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
}
```

---

## PHASE 8: ADMIN DASHBOARD API

### 8.1 Admin Views

**File:** `saas_admin/views.py`

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import BasePermission
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta

from payments.models import Transaction
from billing.models import RevenueLog, SaaSInvoice
from schools.models import School
from fraud_detection.models import Alert
from audit.models import AuditLog

class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_superuser

class DashboardOverview(APIView):
    permission_classes = [IsSuperAdmin]
    
    def get(self, request):
        # Revenue metrics
        total_revenue = RevenueLog.objects.aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        monthly_revenue = RevenueLog.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=30)
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # School metrics
        total_schools = School.objects.count()
        active_schools = School.objects.filter(active=True).count()
        
        # Transaction metrics
        total_transactions = Transaction.objects.count()
        today_transactions = Transaction.objects.filter(
            created_at__date=timezone.now().date()
        ).count()
        
        # Pending alerts
        pending_alerts = Alert.objects.filter(resolved=False).count()
        critical_alerts = Alert.objects.filter(level='CRITICAL', resolved=False).count()
        
        return Response({
            'revenue': {
                'total': str(total_revenue),
                'monthly': str(monthly_revenue),
            },
            'schools': {
                'total': total_schools,
                'active': active_schools,
            },
            'transactions': {
                'total': total_transactions,
                'today': today_transactions,
            },
            'alerts': {
                'pending': pending_alerts,
                'critical': critical_alerts,
            }
        })

class RevenueChart(APIView):
    permission_classes = [IsSuperAdmin]
    
    def get(self, request):
        days = int(request.query_params.get('days', 30))
        
        data = []
        for i in range(days):
            date = timezone.now().date() - timedelta(days=i)
            daily = RevenueLog.objects.filter(
                created_at__date=date
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            data.append({
                'date': date.isoformat(),
                'amount': str(daily)
            })
        
        return Response(list(reversed(data)))

class SchoolList(APIView):
    permission_classes = [IsSuperAdmin]
    
    def get(self, request):
        schools = School.objects.all().values(
            'id', 'name', 'code', 'active', 'subscription_active',
            'subscription_expires_at'
        )
        
        result = []
        for school in schools:
            school_data = dict(school)
            school_data['revenue'] = str(
                RevenueLog.objects.filter(school_id=school['id']).aggregate(
                    total=Sum('amount')
                )['total'] or 0
            )
            school_data['transaction_count'] = Transaction.objects.filter(
                school_id=school['id']
            ).count()
            result.append(school_data)
        
        return Response(result)

class ToggleSchool(APIView):
    permission_classes = [IsSuperAdmin]
    
    def post(self, request, school_id):
        try:
            school = School.objects.get(id=school_id)
            school.active = not school.active
            school.save()
            
            AuditLog.objects.create(
                school=school,
                user=request.user,
                action='SCHOOL_SUSPENDED' if not school.active else 'SCHOOL_ACTIVATED',
                entity='SCHOOL',
                entity_id=str(school.id)
            )
            
            return Response({'status': 'updated', 'active': school.active})
        except School.DoesNotExist:
            return Response({'error': 'School not found'}, status=404)

class AlertList(APIView):
    permission_classes = [IsSuperAdmin]
    
    def get(self, request):
        alerts = Alert.objects.select_related('school').order_by('-created_at')[:100]
        
        result = []
        for alert in alerts:
            result.append({
                'id': alert.id,
                'school': alert.school.name if alert.school else None,
                'level': alert.level,
                'type': alert.alert_type,
                'message': alert.message,
                'resolved': alert.resolved,
                'created_at': alert.created_at.isoformat()
            })
        
        return Response(result)

class AuditTrailView(APIView):
    permission_classes = [IsSuperAdmin]
    
    def get(self, request):
        school_id = request.query_params.get('school')
        
        logs = AuditLog.objects.all()
        if school_id:
            logs = logs.filter(school_id=school_id)
        
        logs = logs.order_by('-created_at')[:100]
        
        result = []
        for log in logs:
            result.append({
                'id': log.id,
                'school': log.school.name if log.school else None,
                'action': log.action,
                'entity': log.entity,
                'entity_id': log.entity_id,
                'metadata': log.metadata,
                'ip_address': log.ip_address,
                'created_at': log.created_at.isoformat(),
                'entry_hash': log.entry_hash[:16] + '...'
            })
        
        return Response(result)

class ExportAuditCSV(APIView):
    permission_classes = [IsSuperAdmin]
    
    def get(self, request):
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="audit_log.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Timestamp', 'School', 'User', 'Action', 'Entity', 'Entity ID', 'IP Address'])
        
        logs = AuditLog.objects.order_by('-created_at')[:10000]
        for log in logs:
            writer.writerow([
                log.created_at.isoformat(),
                log.school.name if log.school else 'N/A',
                log.user.username if log.user else 'System',
                log.action,
                log.entity,
                log.entity_id,
                log.ip_address
            ])
        
        return response
```

---

## PHASE 9: URLS & SERIALIZERS

### 9.1 URL Configuration

**File:** `payments/urls.py`

```python
from django.urls import path
from .views import (
    STKPushView, MpesaCallbackView, TransactionListView,
    AdminAdjustBalanceView
)

urlpatterns = [
    path('stk-push/', STKPushView.as_view(), name='stk-push'),
    path('mpesa/callback/', MpesaCallbackView.as_view(), name='mpesa-callback'),
    path('transactions/', TransactionListView.as_view(), name='transactions'),
    path('admin/adjust-balance/', AdminAdjustBalanceView.as_view(), name='adjust-balance'),
]
```

**File:** `saas_admin/urls.py`

```python
from django.urls import path
from .views import (
    DashboardOverview, RevenueChart, SchoolList, ToggleSchool,
    AlertList, AuditTrailView, ExportAuditCSV
)

urlpatterns = [
    path('overview/', DashboardOverview.as_view(), name='admin-overview'),
    path('revenue-chart/', RevenueChart.as_view(), name='revenue-chart'),
    path('schools/', SchoolList.as_view(), name='school-list'),
    path('schools/<int:school_id>/toggle/', ToggleSchool.as_view(), name='toggle-school'),
    path('alerts/', AlertList.as_view(), name='alert-list'),
    path('audit/', AuditTrailView.as_view(), name='audit-trail'),
    path('audit/export/', ExportAuditCSV.as_view(), name='export-audit'),
]
```

### 9.2 Serializers

**File:** `payments/serializers.py`

```python
from rest_framework import serializers
from .models import Transaction

class STKPushSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=1)
    invoice_id = serializers.UUIDField(required=False, allow_null=True)
    
    def validate_phone(self, value):
        # Normalize phone number
        phone = value.replace('+', '').replace(' ', '')
        if phone.startswith('0'):
            phone = '254' + phone[1:]
        return phone

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            'id', 'amount', 'transaction_type', 'status',
            'phone_number', 'mpesa_receipt', 'description',
            'created_at', 'processed_at'
        ]
```

---

## PHASE 10: INSTALLATION & SETUP

### 10.1 Requirements

**File:** `requirements.txt`

```
Django>=4.2.0,<5.0
djangorestframework>=3.14.0
django-cors-headers>=4.0.0
celery>=5.3.0
redis>=4.5.0
psycopg2-binary>=2.9.0
requests>=2.31.0
python-decouple>=3.8
gunicorn>=21.0.0
whitenoise>=6.5.0
drf-spectacular>=0.26.0
reportlab>=4.0.0
```

### 10.2 Django Settings Additions

Add to your `settings.py`:

```python
INSTALLED_APPS = [
    # ... existing apps
    'rest_framework',
    'corsheaders',
    'core',
    'payments',
    'ledger',
    'billing',
    'audit',
    'fraud_detection',
    'saas_admin',
]

MIDDLEWARE = [
    # ... existing middleware
    'core.middleware.TenantMiddleware',
]

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# Celery
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# M-Pesa
MPESA_BASE_URL = os.getenv('MPESA_BASE_URL', 'https://sandbox.safaricom.co.ke')
MPESA_CONSUMER_KEY = os.getenv('MPESA_CONSUMER_KEY', '')
MPESA_CONSUMER_SECRET = os.getenv('MPESA_CONSUMER_SECRET', '')
MPESA_SHORTCODE = os.getenv('MPESA_SHORTCODE', '174379')
MPESA_PASSKEY = os.getenv('MPESA_PASSKEY', '')
BASE_URL = os.getenv('BASE_URL', 'https://yourdomain.com')
```

### 10.3 Migration Commands

```bash
python manage.py makemigrations payments ledger billing audit fraud_detection saas_admin
python manage.py migrate
```

---

## CRITICAL IMPLEMENTATION NOTES

### Security Checklist
- [ ] Validate M-Pesa callback IP (Safaricom IPs only)
- [ ] Use HTTPS for all callbacks
- [ ] Implement rate limiting on STK push endpoint
- [ ] Encrypt sensitive data (passkeys, secrets)
- [ ] Use atomic transactions for all balance updates
- [ ] Never trust frontend for balance calculations

### Performance Checklist
- [ ] Add database indexes (provided in models)
- [ ] Use select_related/prefetch_related in queries
- [ ] Cache frequently accessed data
- [ ] Use Celery for background jobs
- [ ] Implement connection pooling

### Reliability Checklist
- [ ] Idempotency on all callbacks (duplicate prevention)
- [ ] Retry logic for failed M-Pesa calls
- [ ] Dead letter queue for failed jobs
- [ ] Comprehensive logging
- [ ] Health check endpoints

### Compliance Checklist
- [ ] 7-year data retention
- [ ] Tamper-proof audit logs
- [ ] Export functionality for auditors
- [ ] Role-based access control
- [ ] Data encryption at rest

---

## TESTING STRATEGY

### Unit Tests
```python
# payments/tests.py
from django.test import TestCase
from .models import Transaction
from ledger.models import Wallet

class PaymentFlowTest(TestCase):
    def test_successful_deposit_updates_balance(self):
        # Create test data
        # Simulate callback
        # Assert balance updated
        # Assert ledger entry created
        pass
    
    def test_duplicate_receipt_blocked(self):
        # Test idempotency
        pass
    
    def test_insufficient_balance_raises_error(self):
        # Test wallet debit validation
        pass
```

### Integration Tests
- Test full STK push → Callback → Balance update flow
- Test B2C withdrawal flow
- Test reconciliation job
- Test fraud detection rules

---

## DEPLOYMENT CHECKLIST

1. **Environment Setup**
   - [ ] PostgreSQL database
   - [ ] Redis server
   - [ ] SSL certificates

2. **M-Pesa Configuration**
   - [ ] Register on Daraja portal
   - [ ] Get consumer key/secret
   - [ ] Configure shortcode and passkey
   - [ ] Set callback URLs

3. **Application Deploy**
   - [ ] Set environment variables
   - [ ] Run migrations
   - [ ] Start Celery worker
   - [ ] Start Celery beat
   - [ ] Configure nginx

4. **Monitoring**
   - [ ] Set up error tracking (Sentry)
   - [ ] Configure log aggregation
   - [ ] Set up alerts for critical errors

---

## NEXT STEPS AFTER IMPLEMENTATION

1. **Load Testing**: Test with simulated high volume
2. **Security Audit**: Penetration testing
3. **Compliance Review**: Legal/finance review
4. **Documentation**: API docs for schools
5. **Support Training**: Train support team on system

---

**END OF TASK SPECIFICATION**

This specification provides a complete, production-ready financial infrastructure for your school management SaaS. Follow each phase sequentially and ensure all security and compliance checks are implemented before going live.
