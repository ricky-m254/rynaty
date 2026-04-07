import os
import django
from decimal import Decimal
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django_tenants.utils import schema_context
from school.models import (
    Student, Invoice, Payment, Term, FeeStructure, AcademicYear, 
    InvoiceLineItem, FeeAssignment, InvoiceAdjustment, AuditLog, SchoolProfile
)
from school.services import FinanceService
from django.contrib.auth.models import User

def test_finance_enhanced():
    schema_name = 'demo_school' 
    print(f"--- Testing Enhanced Finance Module in '{schema_name}' ---")
    
    with schema_context(schema_name):
        # 0. Setup User & Data
        admin_user, _ = User.objects.get_or_create(username='admin_test')
        year, _ = AcademicYear.objects.get_or_create(name="2024", defaults={'start_date': '2024-01-01', 'end_date': '2024-12-31'})
        term, _ = Term.objects.get_or_create(name="Term 2", academic_year=year, defaults={'start_date': '2024-05-01', 'end_date': '2024-08-31'})
        student, _ = Student.objects.get_or_create(admission_number="FIN_TEST_01", defaults={'first_name': 'Finance', 'last_name': 'Tester', 'date_of_birth': '2010-01-01', 'gender': 'F'})
        fee, _ = FeeStructure.objects.get_or_create(name="Boarding Fee", academic_year=year, term=term, defaults={'amount': 20000.00, 'billing_cycle': 'TERMLY'})

        # 1. Test Fee Assignment
        print("\n[1] Testing Fee Assignment...")
        assignment = FinanceService.assign_fee(student, fee, discount_amount=Decimal('5000.00'), user=admin_user)
        print(f"Assigned Fee: {assignment}")
        
        # Verify Audit Log
        log = AuditLog.objects.filter(model_name="FeeAssignment", object_id=str(assignment.id)).first()
        if log:
            print(f"✅ Audit Log found: {log.details}")
        else:
            print("❌ Audit Log MISSING for FeeAssignment")

        # 2. Test Invoice Creation & Balance
        print("\n[2] Testing Invoice & Balance...")
        # Create invoice properly via Service 
        # (Note: In a real app, we'd use the assignment to auto-generate, but here we manually add line items for the test)
        line_items = [{'fee_structure': fee.id, 'amount': 20000.00}]
        invoice = FinanceService.create_invoice(student, term, line_items, '2024-06-01')
        print(f"Invoice Total: {invoice.total_amount}. Balance Due: {invoice.balance_due}")
        assert invoice.balance_due == 20000.00

        # 3. Test Invoice Adjustment (Waiver)
        print("\n[3] Testing Adjustment (Credit Note)...")
        # Apply Waiver of 5000
        adj = FinanceService.create_adjustment(invoice, Decimal('5000.00'), "Scholarship Credit", user=admin_user)
        print(f"Adjustment applied: {adj.amount}")
        
        # Re-fetch Invoice to check computed property
        invoice.refresh_from_db()
        print(f"New Balance Due: {invoice.balance_due}")
        assert invoice.balance_due == 15000.00
        
        # Verify Audit Log for Adjustment
        log_adj = AuditLog.objects.filter(model_name="InvoiceAdjustment", object_id=str(adj.id)).first()
        if log_adj:
             print(f"✅ Audit Log found: {log_adj.details}")
        else:
             print("❌ Audit Log MISSING for Adjustment")

        # 4. Test Payment Allocation against Adjusted Balance
        print("\n[4] Testing Payment against Adjusted Balance...")
        payment = FinanceService.record_payment(student, 15000.00, 'Bank', 'REF_FIN_02')
        alloc = FinanceService.allocate_payment(payment, invoice, 15000.00)
        
        invoice.refresh_from_db()
        print(f"Final Balance: {invoice.balance_due}")
        assert invoice.balance_due == 0.00
        print("✅ Invoice Fully Paid (after adjustment)")

        # 5. Test School Profile
        print("\n[5] Testing School Profile Settings...")
        profile, _ = SchoolProfile.objects.get_or_create(school_name="Demo School")
        profile.currency = "USD"
        profile.save()
        print(f"School Currency: {profile.currency}")
        assert profile.currency == "USD"

if __name__ == "__main__":
    try:
        test_finance_enhanced()
    except Exception as e:
        print(f"Global Error: {e}")
        import traceback
        traceback.print_exc()
