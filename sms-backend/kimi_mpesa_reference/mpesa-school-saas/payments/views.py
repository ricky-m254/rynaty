"""
Payment API views for M-Pesa integration.
Handles STK Push, callbacks, and transaction management.
"""

import json
from decimal import Decimal
from django.db import transaction as db_transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .models import Transaction, MpesaRawLog, WithdrawalRequest
from .mpesa_client import MpesaClient, MpesaError
from .serializers import (
    STKPushSerializer, TransactionSerializer, 
    WithdrawalRequestSerializer, AdminAdjustmentSerializer
)
from ledger.models import Wallet
from audit.models import AuditLog
from fraud_detection.engine import FraudDetectionEngine


class STKPushView(APIView):
    """
    Initiate M-Pesa STK Push to customer's phone.
    
    POST /api/payments/stk-push/
    {
        "phone": "254712345678",
        "amount": 1000,
        "invoice_id": "optional-invoice-uuid"
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        school = getattr(request, 'school', None)
        
        # Validate school subscription
        if not school:
            return Response(
                {'error': 'School context required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not school.is_subscription_active():
            return Response(
                {'error': 'School subscription is inactive or expired'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validate input
        serializer = STKPushSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        phone = serializer.validated_data['phone']
        amount = serializer.validated_data['amount']
        invoice_id = serializer.validated_data.get('invoice_id')
        
        # Run fraud detection
        fraud_engine = FraudDetectionEngine(school, request.user)
        risk_score = fraud_engine.check_deposit_risk(amount, phone)
        
        if risk_score >= 90:
            return Response(
                {
                    'error': 'Transaction blocked due to high risk',
                    'risk_score': risk_score,
                    'code': 'HIGH_RISK'
                }, 
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
                description=f'STK Push deposit of KES {amount}'
            )
            
            if invoice_id:
                try:
                    from billing.models import Invoice
                    invoice = Invoice.objects.get(id=invoice_id, school=school)
                    tx.invoice = invoice
                    tx.save()
                except Exception:
                    pass  # Invoice not found, continue without link
        
        # Initiate M-Pesa STK Push
        try:
            mpesa = MpesaClient(school)
            account_ref = f"S{school.id}U{request.user.id}"
            
            response = mpesa.stk_push(
                phone=phone,
                amount=amount,
                account_reference=account_ref,
                description=f"Deposit"
            )
            
            # Update transaction with M-Pesa IDs
            tx.merchant_request_id = response.get('MerchantRequestID')
            tx.checkout_request_id = response.get('CheckoutRequestID')
            tx.status = 'PROCESSING'
            tx.save()
            
            # Audit log
            AuditLog.log_action(
                request, 'STK_PUSH_INITIATED', 'TRANSACTION', 
                str(tx.id), {
                    'amount': str(amount), 
                    'phone': phone,
                    'checkout_request_id': tx.checkout_request_id
                }
            )
            
            return Response({
                'success': True,
                'transaction_id': str(tx.id),
                'message': 'STK push sent to your phone. Please check your phone and enter PIN.',
                'checkout_request_id': tx.checkout_request_id,
                'merchant_request_id': tx.merchant_request_id,
                'risk_score': risk_score if risk_score > 0 else None
            })
            
        except MpesaError as e:
            tx.status = 'FAILED'
            tx.result_desc = str(e)
            tx.save()
            return Response(
                {'error': f'M-Pesa request failed: {str(e)}'}, 
                status=status.HTTP_502_BAD_GATEWAY
            )


@method_decorator(csrf_exempt, name='dispatch')
class MpesaCallbackView(APIView):
    """
    Handle M-Pesa STK Push callbacks.
    
    This endpoint receives the result of STK Push requests.
    It MUST return 200 OK quickly to avoid M-Pesa retries.
    """
    authentication_classes = []
    permission_classes = []
    
    def post(self, request):
        # Log raw callback immediately
        ip = self._get_client_ip(request)
        raw_log = MpesaRawLog.objects.create(
            school=None,  # Will be determined later
            payload=request.data,
            endpoint='stk_callback',
            ip_address=ip
        )
        
        # Validate callback IP (optional but recommended)
        # mpesa = MpesaClient()
        # if not mpesa.validate_callback_ip(ip):
        #     raw_log.processing_error = "Invalid callback IP"
        #     raw_log.save()
        #     return Response({'status': 'ok'})
        
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
                raw_log.processing_error = f"Transaction not found: {checkout_request_id}"
                raw_log.save()
                return Response({'status': 'ok'})  # Still return OK
            
            # Update raw log with school reference
            raw_log.school = tx.school
            raw_log.transaction = tx
            raw_log.save()
            
            # Update transaction with callback data
            tx.callback_payload = data
            tx.result_code = str(result_code)
            tx.result_desc = result_desc
            
            # Handle failed transaction
            if result_code != 0:
                tx.status = 'FAILED'
                tx.save()
                return Response({'status': 'ok'})
            
            # Extract payment details from callback metadata
            metadata = callback.get('CallbackMetadata', {}).get('Item', [])
            
            amount = next(
                (item.get('Value') for item in metadata if item.get('Name') == 'Amount'), 
                0
            )
            phone = next(
                (item.get('Value') for item in metadata if item.get('Name') == 'PhoneNumber'), 
                ''
            )
            receipt = next(
                (item.get('Value') for item in metadata if item.get('Name') == 'MpesaReceiptNumber'), 
                ''
            )
            transaction_date = next(
                (item.get('Value') for item in metadata if item.get('Name') == 'TransactionDate'), 
                ''
            )
            
            # CRITICAL: Idempotency check - prevent double credit
            if receipt and Transaction.objects.filter(
                mpesa_receipt=receipt
            ).exclude(id=tx.id).exists():
                tx.status = 'FAILED'
                tx.result_desc = 'Duplicate receipt number detected'
                tx.save()
                
                # Create fraud alert
                fraud_engine = FraudDetectionEngine(tx.school, tx.user)
                fraud_engine.check_duplicate_receipt(receipt)
                
                return Response({'status': 'duplicate'})
            
            # Process successful payment atomically
            with db_transaction.atomic():
                # Update transaction
                tx.amount = Decimal(str(amount))
                tx.phone_number = phone
                tx.mpesa_receipt = receipt
                tx.status = 'SUCCESS'
                tx.processed_at = timezone.now()
                tx.save()
                
                # Credit user's wallet
                wallet = Wallet.get_or_create_for_user(tx.user, tx.school)
                ledger_entry = wallet.credit(
                    amount=amount,
                    entry_type='DEPOSIT',
                    reference=receipt,
                    description=f'M-Pesa deposit (Receipt: {receipt})'
                )
                tx.ledger_entry = ledger_entry
                tx.save()
                
                # Apply payment to invoice if linked
                if tx.invoice:
                    tx.invoice.apply_payment(amount)
                
                # Apply SaaS transaction fee
                from billing.engine import BillingEngine
                BillingEngine.apply_transaction_fee(tx.school, amount, receipt)
                
                # Mark raw log as processed
                raw_log.processed = True
                raw_log.save()
            
            # Audit log
            AuditLog.objects.create(
                school=tx.school,
                action='PAYMENT_RECEIVED',
                entity='TRANSACTION',
                entity_id=str(tx.id),
                metadata={
                    'amount': str(amount),
                    'receipt': receipt,
                    'phone': phone
                },
                ip_address=ip
            )
            
            return Response({'status': 'ok'})
            
        except Exception as e:
            raw_log.processing_error = str(e)
            raw_log.save()
            # Still return OK to prevent M-Pesa retries
            return Response({'status': 'error', 'message': str(e)}, status=200)
    
    def _get_client_ip(self, request):
        """Extract client IP from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class TransactionListView(APIView):
    """
    List user's transactions.
    
    GET /api/payments/transactions/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        school = getattr(request, 'school', None)
        if not school:
            return Response(
                {'error': 'School context required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get transactions for user in school
        transactions = Transaction.objects.filter(
            school=school,
            user=request.user
        ).select_related('invoice', 'ledger_entry').order_by('-created_at')[:50]
        
        serializer = TransactionSerializer(transactions, many=True)
        return Response(serializer.data)


class TransactionDetailView(APIView):
    """
    Get details of a specific transaction.
    
    GET /api/payments/transactions/<id>/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, transaction_id):
        school = getattr(request, 'school', None)
        if not school:
            return Response(
                {'error': 'School context required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            tx = Transaction.objects.get(
                id=transaction_id,
                school=school,
                user=request.user
            )
            serializer = TransactionSerializer(tx)
            return Response(serializer.data)
        except Transaction.DoesNotExist:
            return Response(
                {'error': 'Transaction not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )


class AdminAdjustBalanceView(APIView):
    """
    Admin endpoint for manual balance adjustments.
    
    POST /api/payments/admin/adjust-balance/
    {
        "user_id": "user-uuid",
        "amount": 1000,
        "reason": "Correction for overcharge"
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        school = getattr(request, 'school', None)
        if not school:
            return Response(
                {'error': 'School context required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check admin permissions
        if request.user.role not in ['ADMIN', 'BURSAR', 'SUPERADMIN']:
            return Response(
                {'error': 'Permission denied. Admin or Bursar access required.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = AdminAdjustmentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        user_id = serializer.validated_data['user_id']
        amount = serializer.validated_data['amount']
        reason = serializer.validated_data['reason']
        
        # Get target user
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            target_user = User.objects.get(id=user_id)
            
            # Verify user belongs to same school
            if hasattr(target_user, 'school') and target_user.school != school:
                return Response(
                    {'error': 'User does not belong to this school'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get or create wallet
        wallet = Wallet.get_or_create_for_user(target_user, school)
        
        # Perform adjustment atomically
        with db_transaction.atomic():
            if amount > 0:
                # Credit
                entry = wallet.credit(
                    amount=amount,
                    entry_type='ADMIN_ADJUSTMENT',
                    reference=f"ADJ-{timezone.now().timestamp()}",
                    description=reason,
                    adjusted_by=request.user,
                    adjustment_reason=reason
                )
            else:
                # Debit
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
                    'target_user': str(target_user.id),
                    'target_user_email': target_user.email
                }
            )
        
        return Response({
            'success': True,
            'message': f'Balance adjusted by KES {amount}',
            'new_balance': str(wallet.balance),
            'ledger_entry_id': str(entry.id),
            'adjusted_user': target_user.get_full_name() or target_user.email
        })


class WithdrawalRequestView(APIView):
    """
    Request a withdrawal (B2C payment).
    
    POST /api/payments/withdrawal-request/
    {
        "phone": "254712345678",
        "amount": 1000,
        "reason": "Refund for cancelled service"
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        school = getattr(request, 'school', None)
        if not school:
            return Response(
                {'error': 'School context required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = WithdrawalRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        phone = serializer.validated_data['phone']
        amount = serializer.validated_data['amount']
        reason = serializer.validated_data.get('reason', '')
        
        # Check wallet balance
        wallet = Wallet.get_or_create_for_user(request.user, school)
        if wallet.balance < amount:
            return Response(
                {
                    'error': 'Insufficient balance',
                    'balance': str(wallet.balance),
                    'requested': str(amount)
                }, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create withdrawal request
        withdrawal = WithdrawalRequest.objects.create(
            school=school,
            user=request.user,
            amount=amount,
            phone_number=phone,
            requested_by=request.user,
            status='PENDING'
        )
        
        # Freeze the amount
        wallet.frozen_balance += amount
        wallet.save()
        
        # Audit log
        AuditLog.log_action(
            request, 'WITHDRAWAL_REQUESTED', 'WITHDRAWAL', 
            str(withdrawal.id), {
                'amount': str(amount),
                'phone': phone,
                'reason': reason
            }
        )
        
        return Response({
            'success': True,
            'message': 'Withdrawal request submitted for approval',
            'request_id': str(withdrawal.id),
            'status': 'PENDING'
        })
