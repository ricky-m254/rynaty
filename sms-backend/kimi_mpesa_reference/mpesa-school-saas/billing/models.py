"""
Billing and invoicing system for school fees and SaaS subscriptions.
"""

from decimal import Decimal
from django.db import models, transaction as db_transaction
from django.utils import timezone

from core.models import TenantModel


class Plan(models.Model):
    """
    SaaS subscription plans for schools.
    
    Defines pricing tiers and features available to schools.
    """
    
    name = models.CharField(
        max_length=50,
        help_text='Plan name (e.g., Basic, Pro, Enterprise)'
    )
    slug = models.SlugField(
        unique=True,
        help_text='URL-friendly identifier'
    )
    description = models.TextField(blank=True)
    
    # Pricing
    monthly_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0'),
        help_text='Base monthly subscription price'
    )
    per_student_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0'),
        help_text='Additional price per student per month'
    )
    transaction_fee_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0'),
        help_text='Percentage fee on each transaction (0-100)'
    )
    
    # Limits
    max_students = models.IntegerField(
        default=1000,
        help_text='Maximum number of students allowed'
    )
    max_users = models.IntegerField(
        default=50,
        help_text='Maximum number of staff users'
    )
    
    # Features (JSON for flexibility)
    features = models.JSONField(
        default=dict,
        help_text='Feature flags and configuration'
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(
        default=True,
        help_text='Show this plan on pricing page'
    )
    display_order = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['display_order', 'monthly_price']
        verbose_name = 'Subscription Plan'
        verbose_name_plural = 'Subscription Plans'
    
    def __str__(self):
        return self.name
    
    def calculate_monthly_price(self, student_count):
        """Calculate monthly price based on student count."""
        return self.monthly_price + (self.per_student_price * student_count)


class Invoice(TenantModel):
    """
    School fee invoices for students.
    
    Tracks what students owe and what has been paid.
    """
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SENT', 'Sent'),
        ('UNPAID', 'Unpaid'),
        ('PARTIAL', 'Partially Paid'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
        ('CANCELLED', 'Cancelled'),
        ('REFUNDED', 'Refunded'),
    ]
    
    # Invoice identification
    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text='Unique invoice number (auto-generated)'
    )
    
    # Relationships
    student = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='invoices',
        help_text='Student being billed'
    )
    
    # Period
    term = models.CharField(
        max_length=50,
        help_text='School term (e.g., Term 1, Term 2)'
    )
    year = models.IntegerField(
        help_text='Academic year'
    )
    
    # Amounts
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='Total invoice amount'
    )
    amount_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        help_text='Amount already paid'
    )
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='Remaining balance (auto-calculated)'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        db_index=True
    )
    due_date = models.DateField(
        help_text='Payment due date'
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When invoice was fully paid'
    )
    
    # Line items (structured data)
    line_items = models.JSONField(
        default=list,
        help_text='Breakdown of charges'
    )
    
    # Notes
    notes = models.TextField(blank=True)
    terms = models.TextField(blank=True)
    
    # Metadata
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_by = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='invoices_sent'
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school', 'student', 'status']),
            models.Index(fields=['school', 'status', 'due_date']),
            models.Index(fields=['due_date']),
            models.Index(fields=['year', 'term']),
        ]
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'
    
    def __str__(self):
        return f"{self.invoice_number} - {self.student} - {self.balance}"
    
    def save(self, *args, **kwargs):
        """Auto-calculate balance before saving."""
        self.balance = self.total_amount - self.amount_paid
        
        # Auto-update status based on payment
        if self.balance <= 0:
            self.status = 'PAID'
            if not self.paid_at:
                self.paid_at = timezone.now()
        elif self.amount_paid > 0:
            self.status = 'PARTIAL'
        elif self.status == 'PAID' and self.balance > 0:
            self.status = 'PARTIAL'
        
        super().save(*args, **kwargs)
    
    @db_transaction.atomic
    def apply_payment(self, amount):
        """
        Apply a payment to this invoice.
        
        Args:
            amount: Amount to apply
            
        Returns:
            Updated status
        """
        amount = Decimal(str(amount))
        self.amount_paid += amount
        self.save()  # Triggers balance recalculation
        return self.status
    
    @db_transaction.atomic
    def add_line_item(self, description, amount, category='FEE'):
        """Add a line item to the invoice."""
        if self.status != 'DRAFT':
            raise ValueError("Can only add line items to draft invoices")
        
        self.line_items.append({
            'description': description,
            'amount': str(amount),
            'category': category
        })
        self.total_amount += Decimal(str(amount))
        self.save()
    
    @classmethod
    def generate_invoice_number(cls, school):
        """Generate unique invoice number."""
        prefix = f"INV-{school.id}"
        count = cls.objects.filter(school=school).count() + 1
        return f"{prefix}-{timezone.now().year}-{count:06d}"
    
    @classmethod
    def get_overdue_for_school(cls, school):
        """Get all overdue invoices for a school."""
        return cls.objects.filter(
            school=school,
            due_date__lt=timezone.now().date(),
            status__in=['UNPAID', 'PARTIAL']
        )
    
    @classmethod
    def get_total_outstanding(cls, school):
        """Get total outstanding balance for a school."""
        result = cls.objects.filter(
            school=school,
            status__in=['UNPAID', 'PARTIAL', 'OVERDUE']
        ).aggregate(
            total=models.Sum('balance')
        )
        return result['total'] or Decimal('0')


class SaaSInvoice(models.Model):
    """
    Invoices WE send to schools for our SaaS services.
    
    This is how we bill schools for using our platform.
    """
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SENT', 'Sent'),
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    TYPE_CHOICES = [
        ('SUBSCRIPTION', 'Monthly Subscription'),
        ('USAGE', 'Usage Based'),
        ('TRANSACTION_FEES', 'Transaction Fees'),
        ('SETUP', 'Setup Fee'),
        ('CUSTOM', 'Custom'),
    ]
    
    school = models.ForeignKey(
        'schools.School',
        on_delete=models.CASCADE,
        related_name='saas_invoices'
    )
    invoice_number = models.CharField(
        max_length=50,
        unique=True
    )
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    invoice_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES
    )
    
    # Period
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Details
    description = models.TextField(blank=True)
    line_items = models.JSONField(default=list)
    
    # Payment tracking
    paid_at = models.DateTimeField(null=True, blank=True)
    paid_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )
    mpesa_receipt = models.CharField(max_length=50, blank=True)
    
    # Due date
    due_date = models.DateField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'SaaS Invoice'
        verbose_name_plural = 'SaaS Invoices'
    
    def __str__(self):
        return f"{self.invoice_number} - {self.school.name} - {self.amount}"


class RevenueLog(models.Model):
    """
    Track OUR revenue from transaction fees and subscriptions.
    
    This is our income, not school income.
    """
    
    SOURCE_CHOICES = [
        ('TRANSACTION_FEE', 'Transaction Fee'),
        ('SUBSCRIPTION', 'Subscription'),
        ('SETUP_FEE', 'Setup Fee'),
        ('CUSTOM', 'Custom'),
    ]
    
    school = models.ForeignKey(
        'schools.School',
        on_delete=models.CASCADE,
        related_name='revenue_generated'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    
    # Linked records
    transaction = models.ForeignKey(
        'payments.Transaction',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='revenue_logs'
    )
    saas_invoice = models.ForeignKey(
        SaaSInvoice,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )
    
    # Details
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school', 'source', 'created_at']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = 'Revenue Log'
        verbose_name_plural = 'Revenue Logs'
    
    def __str__(self):
        return f"{self.source}: {self.amount} from {self.school.name}"
    
    @classmethod
    def get_total_revenue(cls, start_date=None, end_date=None):
        """Get total revenue for a date range."""
        qs = cls.objects.all()
        if start_date:
            qs = qs.filter(created_at__date__gte=start_date)
        if end_date:
            qs = qs.filter(created_at__date__lte=end_date)
        
        result = qs.aggregate(total=models.Sum('amount'))
        return result['total'] or Decimal('0')
    
    @classmethod
    def get_revenue_by_school(cls, start_date=None, end_date=None):
        """Get revenue breakdown by school."""
        qs = cls.objects.all()
        if start_date:
            qs = qs.filter(created_at__date__gte=start_date)
        if end_date:
            qs = qs.filter(created_at__date__lte=end_date)
        
        return qs.values('school__name').annotate(
            total=models.Sum('amount')
        ).order_by('-total')


class FeeStructure(TenantModel):
    """
    Define fee structures for different classes/grades.
    
    Allows schools to set up standard fees per class.
    """
    
    name = models.CharField(max_length=100)
    class_grade = models.CharField(
        max_length=50,
        help_text='Class or grade this applies to'
    )
    
    # Fee breakdown
    tuition_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    exam_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    activity_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    library_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    transport_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    other_fees = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    
    # Term and year
    term = models.CharField(max_length=50)
    year = models.IntegerField()
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-year', 'term', 'class_grade']
        unique_together = ['school', 'class_grade', 'term', 'year']
        verbose_name = 'Fee Structure'
        verbose_name_plural = 'Fee Structures'
    
    @property
    def total_fee(self):
        """Calculate total fee."""
        return (
            self.tuition_fee + self.exam_fee + self.activity_fee +
            self.library_fee + self.transport_fee + self.other_fees
        )
    
    def create_invoice_for_student(self, student):
        """Create invoice for a student based on this fee structure."""
        line_items = [
            {'description': 'Tuition Fee', 'amount': str(self.tuition_fee), 'category': 'TUITION'},
            {'description': 'Exam Fee', 'amount': str(self.exam_fee), 'category': 'EXAM'},
            {'description': 'Activity Fee', 'amount': str(self.activity_fee), 'category': 'ACTIVITY'},
            {'description': 'Library Fee', 'amount': str(self.library_fee), 'category': 'LIBRARY'},
        ]
        
        if self.transport_fee > 0:
            line_items.append({
                'description': 'Transport Fee',
                'amount': str(self.transport_fee),
                'category': 'TRANSPORT'
            })
        
        if self.other_fees > 0:
            line_items.append({
                'description': 'Other Fees',
                'amount': str(self.other_fees),
                'category': 'OTHER'
            })
        
        return Invoice.objects.create(
            school=self.school,
            student=student,
            invoice_number=Invoice.generate_invoice_number(self.school),
            term=self.term,
            year=self.year,
            total_amount=self.total_fee,
            balance=self.total_fee,
            line_items=line_items,
            due_date=timezone.now().date() + timezone.timedelta(days=30)
        )
