import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django_tenants.utils import schema_context
from school.models import Student, Invoice, Payment, Term, FeeStructure, AcademicYear, InvoiceLineItem
from school.services import FinanceService
from school.serializers import InvoiceSerializer

def debug_payment_flow():
    schema_name = 'demo_school'
    print(f"--- Debugging Payment Balance in '{schema_name}' ---")
    
    with schema_context(schema_name):
        # 1. Setup
        year, _ = AcademicYear.objects.get_or_create(name="2024", defaults={'start_date': '2024-01-01', 'end_date': '2024-12-31'})
        term, _ = Term.objects.get_or_create(name="Debug Term", academic_year=year, defaults={'start_date': '2024-01-01', 'end_date': '2024-03-31'})
        student, _ = Student.objects.get_or_create(admission_number="DBG001", defaults={'first_name': 'Debug', 'last_name': 'User', 'date_of_birth': '2010-01-01', 'gender': 'M'})
        fee, _ = FeeStructure.objects.get_or_create(name="Test Fee", academic_year=year, term=term, defaults={'amount': 1000.00})

        # 2. Create Invoice
        print("\n[A] Creating Invoice...")
        line_items = [{'fee_structure': fee.id, 'amount': 1000.00}]
        invoice = FinanceService.create_invoice(student, term, line_items, '2024-02-01')
        print(f"Invoice #{invoice.id} Created. Total: {invoice.total_amount}")
        print(f"Initial Balance Due: {invoice.balance_due}")

        # 3. Create Payment (Without explicit allocation first)
        print("\n[B] Recording Payment (1000.00)...")
        payment = FinanceService.record_payment(student, 1000.00, 'Cash', f'REF_DBG_{invoice.id}')
        print(f"Payment #{payment.id} Recorded.")

        # 4. Check Balance (Should be UNCHANGED if no allocation happened)
        invoice.refresh_from_db()
        print(f"Balance After Payment (No Allocation): {invoice.balance_due}")
        
        if invoice.balance_due == 1000.00:
            print("=> CONFIRMED: Balance did not change because payment was not allocated.")
        else:
            print("=> SURPRISE: Balance changed automatically?")

        # 5. Allocate Payment
        print("\n[C] Allocating Payment...")
        FinanceService.allocate_payment(payment, invoice, 1000.00)
        
        # 6. Check Balance Again
        invoice.refresh_from_db()
        print(f"Balance After Allocation: {invoice.balance_due}")
        if invoice.balance_due == 0.00:
             print("=> SUCCESS: Allocation cleared the balance.")

if __name__ == "__main__":
    debug_payment_flow()
