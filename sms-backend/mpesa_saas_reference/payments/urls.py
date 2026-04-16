"""
URL configuration for payments app.
"""

from django.urls import path
from .views import (
    STKPushView,
    MpesaCallbackView,
    TransactionListView,
    TransactionDetailView,
    AdminAdjustBalanceView,
    WithdrawalRequestView
)

urlpatterns = [
    # STK Push
    path('stk-push/', STKPushView.as_view(), name='stk-push'),
    
    # M-Pesa Callbacks
    path('mpesa/callback/', MpesaCallbackView.as_view(), name='mpesa-callback'),
    
    # Transactions
    path('transactions/', TransactionListView.as_view(), name='transaction-list'),
    path('transactions/<uuid:transaction_id>/', TransactionDetailView.as_view(), name='transaction-detail'),
    
    # Admin
    path('admin/adjust-balance/', AdminAdjustBalanceView.as_view(), name='adjust-balance'),
    
    # Withdrawals
    path('withdrawal-request/', WithdrawalRequestView.as_view(), name='withdrawal-request'),
]
