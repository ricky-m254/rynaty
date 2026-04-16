"""
M-Pesa API Client for Daraja API integration.
Handles STK Push, B2C, and other M-Pesa operations.
"""

import base64
import json
import requests
from datetime import datetime
from typing import Dict, Optional, Tuple
from django.conf import settings
from django.core.cache import cache


class MpesaError(Exception):
    """Custom exception for M-Pesa API errors."""
    pass


class MpesaClient:
    """
    Client for Safaricom M-Pesa Daraja API.
    
    Supports:
    - STK Push (Lipa Na M-Pesa Online)
    - B2C (Business to Customer) payments
    - Transaction status queries
    - Account balance queries
    
    Usage:
        client = MpesaClient(school)  # or MpesaClient() for default config
        result = client.stk_push(phone='254712345678', amount=100)
    """
    
    SANDBOX_URL = 'https://sandbox.safaricom.co.ke'
    LIVE_URL = 'https://api.safaricom.co.ke'
    
    def __init__(self, school=None):
        """
        Initialize M-Pesa client.
        
        Args:
            school: School instance with M-Pesa config, or None for default
        """
        self.school = school
        self.base_url = self._get_base_url()
        self.consumer_key = self._get_config('MPESA_CONSUMER_KEY')
        self.consumer_secret = self._get_config('MPESA_CONSUMER_SECRET')
        self.shortcode = self._get_config('MPESA_SHORTCODE')
        self.passkey = self._get_config('MPESA_PASSKEY')
        
    def _get_base_url(self) -> str:
        """Get appropriate base URL based on environment."""
        if self.school:
            env = getattr(self.school, 'mpesa_environment', 'sandbox')
            return self.LIVE_URL if env == 'live' else self.SANDBOX_URL
        return getattr(settings, 'MPESA_BASE_URL', self.SANDBOX_URL)
    
    def _get_config(self, key: str) -> str:
        """Get configuration value from school or settings."""
        if self.school:
            school_value = getattr(self.school, key.lower(), None)
            if school_value:
                return school_value
        return getattr(settings, key, '')
    
    def _get_access_token(self) -> str:
        """
        Get OAuth access token from M-Pesa.
        
        Tokens are cached for 50 minutes (they expire after 1 hour).
        """
        cache_key = f'mpesa_token_{self.shortcode}'
        token = cache.get(cache_key)
        
        if token:
            return token
        
        url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        credentials = base64.b64encode(
            f"{self.consumer_key}:{self.consumer_secret}".encode()
        ).decode()
        
        try:
            response = requests.get(
                url, 
                headers={'Authorization': f'Basic {credentials}'},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            token = data['access_token']
            
            # Cache for 50 minutes
            cache.set(cache_key, token, 3000)
            return token
            
        except requests.RequestException as e:
            raise MpesaError(f"Failed to get access token: {str(e)}")
    
    def _generate_password(self) -> Tuple[str, str]:
        """
        Generate password and timestamp for STK Push.
        
        Returns:
            Tuple of (password, timestamp)
        """
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password_str = f"{self.shortcode}{self.passkey}{timestamp}"
        password = base64.b64encode(password_str.encode()).decode()
        return password, timestamp
    
    def _format_phone(self, phone: str) -> str:
        """
        Normalize phone number to M-Pesa format.
        
        Converts:
        - 0712345678 -> 254712345678
        - +254712345678 -> 254712345678
        - 254712345678 -> 254712345678
        """
        phone = str(phone).replace('+', '').replace(' ', '').replace('-', '')
        
        if phone.startswith('0'):
            phone = '254' + phone[1:]
        elif phone.startswith('7') or phone.startswith('1'):
            phone = '254' + phone
            
        return phone
    
    def stk_push(
        self, 
        phone: str, 
        amount: float, 
        account_reference: str,
        description: str = "Payment",
        callback_url: Optional[str] = None
    ) -> Dict:
        """
        Initiate STK Push (Lipa Na M-Pesa Online).
        
        Args:
            phone: Customer phone number
            amount: Amount to charge
            account_reference: Your account/reference number (max 12 chars)
            description: Transaction description (max 13 chars)
            callback_url: Optional custom callback URL
            
        Returns:
            Dict with MerchantRequestID and CheckoutRequestID
            
        Raises:
            MpesaError: If API call fails
        """
        token = self._get_access_token()
        password, timestamp = self._generate_password()
        
        phone = self._format_phone(phone)
        
        # Use provided callback or default
        if not callback_url:
            callback_url = f"{settings.BASE_URL}/api/payments/mpesa/callback/"
        
        payload = {
            'BusinessShortCode': self.shortcode,
            'Password': password,
            'Timestamp': timestamp,
            'TransactionType': 'CustomerPayBillOnline',
            'Amount': int(amount),
            'PartyA': phone,
            'PartyB': self.shortcode,
            'PhoneNumber': phone,
            'CallBackURL': callback_url,
            'AccountReference': account_reference[:12],
            'TransactionDesc': description[:13]
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/mpesa/stkpush/v1/processrequest",
                json=payload,
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                },
                timeout=30
            )
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            raise MpesaError(f"STK Push failed: {str(e)}")
    
    def query_stk_status(self, checkout_request_id: str) -> Dict:
        """
        Query status of an STK Push transaction.
        
        Args:
            checkout_request_id: The CheckoutRequestID from STK push
            
        Returns:
            Dict with transaction status
        """
        token = self._get_access_token()
        password, timestamp = self._generate_password()
        
        payload = {
            'BusinessShortCode': self.shortcode,
            'Password': password,
            'Timestamp': timestamp,
            'CheckoutRequestID': checkout_request_id
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/mpesa/stkpushquery/v1/query",
                json=payload,
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                },
                timeout=30
            )
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            raise MpesaError(f"Status query failed: {str(e)}")
    
    def b2c_payment(
        self,
        phone: str,
        amount: float,
        remarks: str = "Withdrawal",
        occasion: str = "Payment",
        result_url: Optional[str] = None,
        timeout_url: Optional[str] = None
    ) -> Dict:
        """
        Initiate B2C (Business to Customer) payment.
        
        Used for:
        - Refunds
        - Withdrawals
        - Payouts
        
        Args:
            phone: Recipient phone number
            amount: Amount to send
            remarks: Payment remarks
            occasion: Occasion/occasion
            result_url: Callback URL for result
            timeout_url: Callback URL for timeout
            
        Returns:
            Dict with ConversationID and OriginatorConversationID
        """
        token = self._get_access_token()
        phone = self._format_phone(phone)
        
        if not result_url:
            result_url = f"{settings.BASE_URL}/api/payments/mpesa/b2c/result/"
        if not timeout_url:
            timeout_url = f"{settings.BASE_URL}/api/payments/mpesa/b2c/timeout/"
        
        payload = {
            'InitiatorName': 'api',
            'SecurityCredential': self._get_security_credential(),
            'CommandID': 'BusinessPayment',
            'Amount': int(amount),
            'PartyA': self.shortcode,
            'PartyB': phone,
            'Remarks': remarks[:140],
            'QueueTimeOutURL': timeout_url,
            'ResultURL': result_url,
            'Occasion': occasion[:140]
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/mpesa/b2c/v1/paymentrequest",
                json=payload,
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                },
                timeout=30
            )
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            raise MpesaError(f"B2C payment failed: {str(e)}")
    
    def _get_security_credential(self) -> str:
        """
        Get encrypted security credential for B2C.
        
        In production, this should encrypt the initiator password
        using Safaricom's public certificate.
        
        For now, returns from settings.
        """
        return getattr(settings, 'MPESA_SECURITY_CREDENTIAL', '')
    
    def validate_callback_ip(self, ip_address: str) -> bool:
        """
        Validate that callback is from Safaricom IP range.
        
        Args:
            ip_address: IP address to validate
            
        Returns:
            True if valid Safaricom IP
        """
        # Safaricom IP ranges (update as needed)
        valid_ranges = [
            '196.201',
            '196.202',
            '196.203',
        ]
        
        return any(ip_address.startswith(range_) for range_ in valid_ranges)
