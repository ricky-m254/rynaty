from django.urls import path

from .student_portal_views import MyInvoicesView, MyPaymentsView, StudentFinanceReceiptView

urlpatterns = [
    path("my-invoices/", MyInvoicesView.as_view()),
    path("my-payments/", MyPaymentsView.as_view()),
    path("finance/payments/<int:payment_id>/receipt/", StudentFinanceReceiptView.as_view()),
]
