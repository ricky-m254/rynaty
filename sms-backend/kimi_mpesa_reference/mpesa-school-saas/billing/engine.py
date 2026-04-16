"""
Billing engine for SaaS subscriptions and transaction fees.
Handles automated billing calculations and revenue tracking.
"""

from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum

from .models import SaaSInvoice, RevenueLog, Plan


class BillingEngine:
    """
    Engine for calculating and applying SaaS billing.
    
    Handles:
    - Monthly subscription billing
    - Per-student pricing
    - Transaction fee calculations
    - Revenue tracking
    """
    
    MINIMUM_MONTHLY_CHARGE = Decimal('500.00')  # Minimum bill per school
    
    @staticmethod
    def apply_transaction_fee(school, amount, reference):
        """
        Calculate and record transaction fee from a payment.
        
        Args:
            school: School where transaction occurred
            amount: Transaction amount
            reference: M-Pesa receipt or reference
            
        Returns:
            Decimal: Fee amount taken
        """
        if not school.plan:
            return Decimal('0')
        
        fee_percent = school.plan.transaction_fee_percent
        if fee_percent <= 0:
            return Decimal('0')
        
        fee = (fee_percent / 100) * Decimal(str(amount))
        
        # Record our revenue
        RevenueLog.objects.create(
            school=school,
            amount=fee,
            source='TRANSACTION_FEE',
            description=f'Transaction fee on {reference}',
            metadata={
                'transaction_amount': str(amount),
                'fee_percent': str(fee_percent),
                'reference': reference
            }
        )
        
        return fee
    
    @staticmethod
    def calculate_monthly_bill(school):
        """
        Calculate monthly subscription bill for a school.
        
        Args:
            school: School to bill
            
        Returns:
            dict: Breakdown of charges
        """
        if not school.plan:
            return {
                'base': Decimal('0'),
                'per_student': Decimal('0'),
                'student_count': 0,
                'total': Decimal('0'),
                'plan_name': 'No Plan'
            }
        
        plan = school.plan
        student_count = school.students.count() if hasattr(school, 'students') else 0
        
        base = plan.monthly_price
        per_student = plan.per_student_price * student_count
        total = base + per_student
        
        # Apply minimum charge
        total = max(total, BillingEngine.MINIMUM_MONTHLY_CHARGE)
        
        return {
            'base': base,
            'per_student': per_student,
            'student_count': student_count,
            'total': total,
            'plan_name': plan.name,
            'minimum_applied': total == BillingEngine.MINIMUM_MONTHLY_CHARGE
        }
    
    @classmethod
    def generate_monthly_invoice(cls, school):
        """
        Generate monthly subscription invoice for a school.
        
        Args:
            school: School to invoice
            
        Returns:
            SaaSInvoice: Created invoice
        """
        breakdown = cls.calculate_monthly_bill(school)
        
        # Calculate period
        today = timezone.now().date()
        period_start = today.replace(day=1)
        if today.month == 12:
            period_end = today.replace(year=today.year + 1, month=1, day=1)
        else:
            period_end = today.replace(month=today.month + 1, day=1)
        
        # Generate invoice number
        count = SaaSInvoice.objects.filter(school=school).count() + 1
        invoice_number = f"SAAS-{school.id}-{today.year}-{count:04d}"
        
        # Create line items
        line_items = [
            {
                'description': f"Base Subscription ({breakdown['plan_name']})",
                'amount': str(breakdown['base'])
            }
        ]
        
        if breakdown['per_student'] > 0:
            line_items.append({
                'description': f"Per-student fee ({breakdown['student_count']} students @ {school.plan.per_student_price}/student)",
                'amount': str(breakdown['per_student'])
            })
        
        if breakdown['minimum_applied']:
            line_items.append({
                'description': 'Minimum monthly charge applied',
                'amount': '0'
            })
        
        invoice = SaaSInvoice.objects.create(
            school=school,
            invoice_number=invoice_number,
            amount=breakdown['total'],
            status='PENDING',
            invoice_type='SUBSCRIPTION',
            period_start=period_start,
            period_end=period_end,
            description=f"Monthly subscription for {breakdown['plan_name']} plan",
            line_items=line_items,
            due_date=period_end
        )
        
        return invoice
    
    @classmethod
    def generate_all_monthly_bills(cls):
        """Generate monthly bills for all active schools."""
        from schools.models import School
        
        invoices = []
        for school in School.objects.filter(active=True, subscription_active=True):
            try:
                invoice = cls.generate_monthly_invoice(school)
                invoices.append(invoice)
            except Exception as e:
                # Log error but continue with other schools
                print(f"Failed to generate invoice for {school.name}: {e}")
        
        return invoices
    
    @staticmethod
    def get_revenue_summary(days=30):
        """
        Get revenue summary for the last N days.
        
        Args:
            days: Number of days to summarize
            
        Returns:
            dict: Revenue breakdown
        """
        from_date = timezone.now() - timezone.timedelta(days=days)
        
        total = RevenueLog.objects.filter(
            created_at__gte=from_date
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        by_source = RevenueLog.objects.filter(
            created_at__gte=from_date
        ).values('source').annotate(
            amount=Sum('amount')
        ).order_by('-amount')
        
        by_school = RevenueLog.objects.filter(
            created_at__gte=from_date
        ).values('school__name').annotate(
            amount=Sum('amount')
        ).order_by('-amount')[:10]
        
        return {
            'period_days': days,
            'total_revenue': total,
            'by_source': list(by_source),
            'top_schools': list(by_school)
        }
    
    @staticmethod
    def get_mrr():
        """
        Calculate Monthly Recurring Revenue (MRR).
        
        Returns:
            Decimal: Estimated MRR
        """
        from schools.models import School
        
        total = Decimal('0')
        for school in School.objects.filter(active=True, subscription_active=True):
            if school.plan:
                student_count = school.students.count() if hasattr(school, 'students') else 0
                total += school.plan.calculate_monthly_price(student_count)
        
        return total
    
    @staticmethod
    def get_outstanding_receivables():
        """Get total outstanding SaaS invoices."""
        result = SaaSInvoice.objects.filter(
            status__in=['PENDING', 'OVERDUE']
        ).aggregate(total=Sum('amount'))
        return result['total'] or Decimal('0')


class InvoiceEngine:
    """
    Engine for managing school fee invoices.
    
    Handles:
    - Invoice generation from fee structures
    - Payment application
    - Overdue tracking
    """
    
    @staticmethod
    def generate_term_invoices(school, term, year):
        """
        Generate invoices for all students for a term.
        
        Args:
            school: School
            term: Term name
            year: Academic year
            
        Returns:
            list: Created invoices
        """
        from .models import FeeStructure, Invoice
        
        invoices = []
        
        # Get all fee structures for this term/year
        fee_structures = FeeStructure.objects.filter(
            school=school,
            term=term,
            year=year,
            is_active=True
        )
        
        # Get students (assuming User model has school and role)
        students = school.students.filter(role='STUDENT') if hasattr(school, 'students') else []
        
        for student in students:
            # Find appropriate fee structure
            class_grade = getattr(student, 'class_grade', None)
            if not class_grade:
                continue
            
            fee_structure = fee_structures.filter(class_grade=class_grade).first()
            if not fee_structure:
                continue
            
            # Check if invoice already exists
            existing = Invoice.objects.filter(
                school=school,
                student=student,
                term=term,
                year=year
            ).first()
            
            if existing:
                continue
            
            # Create invoice
            invoice = fee_structure.create_invoice_for_student(student)
            invoices.append(invoice)
        
        return invoices
    
    @staticmethod
    def get_collection_rate(school, term=None, year=None):
        """
        Calculate fee collection rate for a school.
        
        Args:
            school: School to analyze
            term: Optional term filter
            year: Optional year filter
            
        Returns:
            dict: Collection statistics
        """
        from .models import Invoice
        
        qs = Invoice.objects.filter(school=school)
        if term:
            qs = qs.filter(term=term)
        if year:
            qs = qs.filter(year=year)
        
        total_invoiced = qs.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        total_paid = qs.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0')
        
        collection_rate = (total_paid / total_invoiced * 100) if total_invoiced > 0 else 0
        
        return {
            'total_invoiced': total_invoiced,
            'total_paid': total_paid,
            'total_outstanding': total_invoiced - total_paid,
            'collection_rate': round(collection_rate, 2),
            'invoice_count': qs.count(),
            'paid_count': qs.filter(status='PAID').count(),
            'partial_count': qs.filter(status='PARTIAL').count(),
            'unpaid_count': qs.filter(status__in=['UNPAID', 'OVERDUE']).count()
        }
