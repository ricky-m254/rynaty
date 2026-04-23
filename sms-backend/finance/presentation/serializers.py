from django.db import models
from rest_framework import serializers

from school.models import (
    BalanceCarryForward,
    CashbookEntry,
    Enrollment,
    FeeAssignment,
    FeeReminderLog,
    FeeStructure,
    Invoice,
    InvoiceAdjustment,
    InvoiceInstallment,
    InvoiceInstallmentPlan,
    InvoiceLineItem,
    InvoiceWriteOffRequest,
    OptionalCharge,
    Payment,
    PaymentAllocation,
    PaymentReversalRequest,
    Student,
    StudentOptionalCharge,
    VoteHead,
)
from school.payment_receipts import (
    payment_receipt_number,
    payment_receipt_urls,
    payment_status_label,
    payment_transaction_code,
    payment_vote_head_summary,
)


class FinanceStudentRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = [
            "id",
            "ulid",
            "admission_number",
            "first_name",
            "last_name",
            "gender",
            "is_active",
        ]


class FinanceEnrollmentRefSerializer(serializers.ModelSerializer):
    student_ulid = serializers.CharField(source="student.ulid", read_only=True)
    student_admission_number = serializers.CharField(source="student.admission_number", read_only=True)
    student_name = serializers.SerializerMethodField()
    class_name = serializers.CharField(source="school_class.name", read_only=True)
    term_name = serializers.CharField(source="term.name", read_only=True)

    class Meta:
        model = Enrollment
        fields = [
            "id",
            "student",
            "student_ulid",
            "student_admission_number",
            "student_name",
            "school_class",
            "class_name",
            "term",
            "term_name",
            "is_active",
        ]

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"


class VoteHeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoteHead
        fields = [
            "id",
            "name",
            "description",
            "allocation_percentage",
            "is_preloaded",
            "is_active",
            "order",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class BalanceCarryForwardSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    student_admission_number = serializers.CharField(
        source="student.admission_number",
        read_only=True,
    )
    from_term_name = serializers.CharField(source="from_term.name", read_only=True)
    to_term_name = serializers.CharField(source="to_term.name", read_only=True)

    class Meta:
        model = BalanceCarryForward
        fields = [
            "id",
            "student",
            "student_name",
            "student_admission_number",
            "from_term",
            "from_term_name",
            "to_term",
            "to_term_name",
            "amount",
            "notes",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["created_by", "created_at"]

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}".strip()


class CashbookEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = CashbookEntry
        fields = [
            "id",
            "book_type",
            "entry_date",
            "entry_type",
            "reference",
            "description",
            "amount_in",
            "amount_out",
            "running_balance",
            "payment",
            "expense",
            "is_auto",
            "created_at",
        ]
        read_only_fields = ["running_balance", "is_auto", "created_at"]


class FeeStructureSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeStructure
        fields = [
            "id",
            "name",
            "category",
            "amount",
            "academic_year",
            "term",
            "grade_level",
            "billing_cycle",
            "is_mandatory",
            "description",
            "is_active",
        ]


class FeeAssignmentSerializer(serializers.ModelSerializer):
    fee_name = serializers.CharField(source="fee_structure.name", read_only=True)
    student_name = serializers.CharField(source="student", read_only=True)

    class Meta:
        model = FeeAssignment
        fields = [
            "id",
            "student",
            "student_name",
            "fee_structure",
            "fee_name",
            "discount_amount",
            "start_date",
            "end_date",
            "is_active",
        ]


class OptionalChargeSerializer(serializers.ModelSerializer):
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True)
    term_name = serializers.CharField(source="term.name", read_only=True)
    category_display = serializers.CharField(source="get_category_display", read_only=True)

    class Meta:
        model = OptionalCharge
        fields = [
            "id",
            "name",
            "description",
            "category",
            "category_display",
            "amount",
            "academic_year",
            "academic_year_name",
            "term",
            "term_name",
            "is_active",
            "created_at",
            "updated_at",
        ]


class StudentOptionalChargeSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student", read_only=True)
    charge_name = serializers.CharField(source="optional_charge.name", read_only=True)
    charge_amount = serializers.DecimalField(
        source="optional_charge.amount",
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    category = serializers.CharField(source="optional_charge.category", read_only=True)

    class Meta:
        model = StudentOptionalCharge
        fields = [
            "id",
            "student",
            "student_name",
            "optional_charge",
            "charge_name",
            "charge_amount",
            "category",
            "invoice",
            "is_paid",
            "notes",
            "assigned_at",
        ]


class InvoiceLineItemSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    fee_structure = serializers.PrimaryKeyRelatedField(queryset=FeeStructure.objects.all())
    description = serializers.CharField(allow_blank=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        model = InvoiceLineItem
        fields = ["id", "fee_structure", "description", "amount"]


class InvoiceSerializer(serializers.ModelSerializer):
    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all())
    term = serializers.PrimaryKeyRelatedField(queryset=Invoice._meta.get_field("term").remote_field.model.objects.all())
    student_admission_number = serializers.CharField(source="student.admission_number", read_only=True)
    student_full_name = serializers.SerializerMethodField()
    line_items = InvoiceLineItemSerializer(many=True)
    balance_due = serializers.ReadOnlyField()
    invoice_number = serializers.CharField(read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "invoice_number",
            "student",
            "student_admission_number",
            "term",
            "invoice_date",
            "due_date",
            "total_amount",
            "status",
            "balance_due",
            "is_active",
            "created_at",
            "line_items",
            "student_full_name",
        ]
        read_only_fields = ["invoice_date", "created_at", "total_amount"]
        depth = 1

    def get_student_full_name(self, obj):
        if not obj.student:
            return ""
        return f"{obj.student.first_name} {obj.student.last_name}".strip()


class PaymentAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentAllocation
        fields = ["id", "invoice", "amount_allocated", "allocated_at"]
        read_only_fields = ["allocated_at"]


class PaymentSerializer(serializers.ModelSerializer):
    allocations = PaymentAllocationSerializer(many=True, required=False)
    allocated_amount = serializers.SerializerMethodField()
    unallocated_amount = serializers.SerializerMethodField()
    receipt_no = serializers.SerializerMethodField()
    transaction_code = serializers.SerializerMethodField()
    vote_head_summary = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    receipt_json_url = serializers.SerializerMethodField()
    receipt_pdf_url = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(source="payment_date", read_only=True)
    student_name = serializers.CharField(source="student", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "student",
            "payment_date",
            "created_at",
            "amount",
            "payment_method",
            "reference_number",
            "transaction_code",
            "receipt_number",
            "receipt_no",
            "vote_head_summary",
            "status",
            "notes",
            "is_active",
            "reversed_at",
            "reversal_reason",
            "reversed_by",
            "allocations",
            "allocated_amount",
            "unallocated_amount",
            "receipt_json_url",
            "receipt_pdf_url",
            "student_name",
        ]
        read_only_fields = ["payment_date", "receipt_number", "reversed_at", "reversed_by"]

    def get_allocated_amount(self, obj):
        total = obj.allocations.aggregate(total=models.Sum("amount_allocated"))["total"] or 0
        return total

    def get_unallocated_amount(self, obj):
        total = obj.allocations.aggregate(total=models.Sum("amount_allocated"))["total"] or 0
        return obj.amount - total

    def get_receipt_no(self, obj):
        return payment_receipt_number(obj)

    def get_transaction_code(self, obj):
        return payment_transaction_code(obj)

    def get_vote_head_summary(self, obj):
        return payment_vote_head_summary(obj)

    def get_status(self, obj):
        return payment_status_label(obj)

    def get_receipt_json_url(self, obj):
        request = self.context.get("request")
        return payment_receipt_urls(obj, request=request)["receipt_json_url"]

    def get_receipt_pdf_url(self, obj):
        request = self.context.get("request")
        return payment_receipt_urls(obj, request=request)["receipt_pdf_url"]


class InvoiceAdjustmentSerializer(serializers.ModelSerializer):
    adjusted_by_name = serializers.CharField(source="adjusted_by.username", read_only=True)
    reviewed_by_name = serializers.CharField(source="reviewed_by.username", read_only=True)

    class Meta:
        model = InvoiceAdjustment
        fields = [
            "id",
            "invoice",
            "adjustment_type",
            "amount",
            "reason",
            "adjusted_by",
            "adjusted_by_name",
            "status",
            "reviewed_by",
            "reviewed_by_name",
            "reviewed_at",
            "review_notes",
            "created_at",
        ]
        read_only_fields = [
            "created_at",
            "adjusted_by",
            "status",
            "reviewed_by",
            "reviewed_at",
            "review_notes",
        ]


class PaymentReversalRequestSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.CharField(source="requested_by.username", read_only=True)
    reviewed_by_name = serializers.CharField(source="reviewed_by.username", read_only=True)
    payment_reference = serializers.CharField(source="payment.reference_number", read_only=True)
    payment_receipt = serializers.CharField(source="payment.receipt_number", read_only=True)

    class Meta:
        model = PaymentReversalRequest
        fields = [
            "id",
            "payment",
            "payment_reference",
            "payment_receipt",
            "reason",
            "requested_by",
            "requested_by_name",
            "requested_at",
            "status",
            "reviewed_by",
            "reviewed_by_name",
            "reviewed_at",
            "review_notes",
        ]
        read_only_fields = ["requested_by", "requested_at", "status", "reviewed_by", "reviewed_at"]


class InvoiceWriteOffRequestSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.CharField(source="requested_by.username", read_only=True)
    reviewed_by_name = serializers.CharField(source="reviewed_by.username", read_only=True)
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)
    student_name = serializers.CharField(source="invoice.student", read_only=True)
    adjustment_id = serializers.IntegerField(source="applied_adjustment_id", read_only=True)

    class Meta:
        model = InvoiceWriteOffRequest
        fields = [
            "id",
            "invoice",
            "invoice_number",
            "student_name",
            "amount",
            "reason",
            "requested_by",
            "requested_by_name",
            "requested_at",
            "status",
            "reviewed_by",
            "reviewed_by_name",
            "reviewed_at",
            "review_notes",
            "adjustment_id",
        ]
        read_only_fields = [
            "requested_by",
            "requested_at",
            "status",
            "reviewed_by",
            "reviewed_at",
            "review_notes",
            "adjustment_id",
        ]


class InvoiceInstallmentSerializer(serializers.ModelSerializer):
    outstanding_amount = serializers.SerializerMethodField()

    class Meta:
        model = InvoiceInstallment
        fields = [
            "id",
            "sequence",
            "due_date",
            "amount",
            "collected_amount",
            "outstanding_amount",
            "status",
            "paid_at",
            "late_fee_applied",
        ]
        read_only_fields = ["status", "paid_at", "late_fee_applied"]

    def get_outstanding_amount(self, obj):
        outstanding = (obj.amount or 0) - (obj.collected_amount or 0)
        return outstanding if outstanding > 0 else 0


class InvoiceInstallmentPlanSerializer(serializers.ModelSerializer):
    installments = InvoiceInstallmentSerializer(many=True, required=False)

    class Meta:
        model = InvoiceInstallmentPlan
        fields = ["id", "invoice", "installment_count", "created_by", "created_at", "installments"]
        read_only_fields = ["created_by", "created_at"]


class FeeReminderLogSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)

    class Meta:
        model = FeeReminderLog
        fields = ["id", "invoice", "invoice_number", "channel", "recipient", "sent_at", "status", "message"]
        read_only_fields = ["sent_at"]
