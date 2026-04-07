from django.urls import path

from .student_portal_views import MyInvoicesView, MyPaymentsView

urlpatterns = [
    path("my-invoices/", MyInvoicesView.as_view()),
    path("my-payments/", MyPaymentsView.as_view()),
]
