"""
Serializers for payment API endpoints.
"""

from rest_framework import serializers
from .models import Transaction, WithdrawalRequest


class STKPushSerializer(serializers.Serializer):
    """
    Serializer for STK Push requests.
    """
    phone = serializers.CharField(
        max_length=20,
        help_text='Phone number in format 254712345678 or 0712345678'
    )
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=1,
        help_text='Amount to charge in KES'
    )
    invoice_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text='Optional invoice ID to link payment to'
    )
    
    def validate_phone(self, value):
        """Normalize phone number to M-Pesa format."""
        phone = str(value).replace('+', '').replace(' ', '').replace('-', '')
        
        if phone.startswith('0'):
            phone = '254' + phone[1:]
        elif phone.startswith('7') or phone.startswith('1'):
            phone = '254' + phone
        
        # Basic validation
        if not phone.startswith('254'):
            raise serializers.ValidationError('Invalid phone number format')
        if len(phone) != 12:
            raise serializers.ValidationError('Phone number must be 12 digits (254...)')
        
        return phone


class TransactionSerializer(serializers.ModelSerializer):
    """
    Serializer for Transaction model.
    """
    invoice_number = serializers.CharField(
        source='invoice.invoice_number',
        read_only=True
    )
    ledger_balance_after = serializers.DecimalField(
        source='ledger_entry.balance_after',
        max_digits=12,
        decimal_places=2,
        read_only=True
    )
    
    class Meta:
        model = Transaction
        fields = [
            'id',
            'amount',
            'transaction_type',
            'status',
            'phone_number',
            'mpesa_receipt',
            'description',
            'invoice_number',
            'ledger_balance_after',
            'created_at',
            'processed_at',
            'result_desc'
        ]
        read_only_fields = fields


class WithdrawalRequestSerializer(serializers.Serializer):
    """
    Serializer for withdrawal requests.
    """
    phone = serializers.CharField(
        max_length=20,
        help_text='Phone number to send money to'
    )
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=10,
        help_text='Amount to withdraw in KES'
    )
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Reason for withdrawal'
    )
    
    def validate_phone(self, value):
        """Normalize phone number."""
        phone = str(value).replace('+', '').replace(' ', '').replace('-', '')
        
        if phone.startswith('0'):
            phone = '254' + phone[1:]
        elif phone.startswith('7') or phone.startswith('1'):
            phone = '254' + phone
        
        if not phone.startswith('254') or len(phone) != 12:
            raise serializers.ValidationError('Invalid phone number format')
        
        return phone
    
    def validate_amount(self, value):
        """Validate withdrawal amount."""
        if value < 10:
            raise serializers.ValidationError('Minimum withdrawal amount is KES 10')
        if value > 150000:
            raise serializers.ValidationError('Maximum withdrawal amount is KES 150,000')
        return value


class AdminAdjustmentSerializer(serializers.Serializer):
    """
    Serializer for admin balance adjustments.
    """
    user_id = serializers.UUIDField(
        help_text='ID of user to adjust balance for'
    )
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='Amount to adjust (positive for credit, negative for debit)'
    )
    reason = serializers.CharField(
        min_length=5,
        help_text='Reason for adjustment (required for audit)'
    )
    
    def validate_reason(self, value):
        """Ensure reason is provided and meaningful."""
        if len(value.strip()) < 5:
            raise serializers.ValidationError('Reason must be at least 5 characters')
        return value.strip()


class MpesaCallbackSerializer(serializers.Serializer):
    """
    Serializer for M-Pesa callback data.
    Used for validation and documentation.
    """
    Body = serializers.DictField()
    
    def validate_Body(self, value):
        """Validate callback body structure."""
        stk_callback = value.get('stkCallback', {})
        if not stk_callback:
            raise serializers.ValidationError('Missing stkCallback in body')
        
        required_fields = ['ResultCode', 'CheckoutRequestID']
        for field in required_fields:
            if field not in stk_callback:
                raise serializers.ValidationError(f'Missing required field: {field}')
        
        return value


class TransactionFilterSerializer(serializers.Serializer):
    """
    Serializer for transaction list filtering.
    """
    status = serializers.ChoiceField(
        choices=['PENDING', 'PROCESSING', 'SUCCESS', 'FAILED', 'ALL'],
        required=False,
        default='ALL'
    )
    transaction_type = serializers.ChoiceField(
        choices=['DEPOSIT', 'WITHDRAWAL', 'FEE_PAYMENT', 'ALL'],
        required=False,
        default='ALL'
    )
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    limit = serializers.IntegerField(
        required=False,
        default=50,
        min_value=1,
        max_value=100
    )
