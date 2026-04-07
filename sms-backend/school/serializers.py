from rest_framework import serializers
from django.db import models
from .security_policy import normalize_allowed_ip_ranges
from .models import (
    Expense, Student, Guardian, Enrollment,
    Invoice, InvoiceLineItem, Payment, PaymentAllocation,
    FeeStructure, SchoolProfile, Guardian,
    FeeAssignment, InvoiceAdjustment, Module, UserModuleAssignment, TenantModule, ModuleSetting,
    AcademicYear, Term, SchoolClass, AdmissionApplication, AdmissionDocument, StudentDocument, AttendanceRecord, BehaviorIncident,
    Budget,
    Department,
    MedicalRecord, ImmunizationRecord, ClinicVisit,
    PaymentReversalRequest, InvoiceInstallmentPlan, InvoiceInstallment, LateFeeRule, FeeReminderLog,
    InvoiceWriteOffRequest,
    ScholarshipAward, OptionalCharge, StudentOptionalCharge,
    AccountingPeriod, ChartOfAccount, JournalEntry, JournalLine,
    PaymentGatewayTransaction, PaymentGatewayWebhookEvent, BankStatementLine,
    VoteHead, VoteHeadPaymentAllocation, CashbookEntry, BalanceCarryForward,
    DispensaryVisit, DispensaryPrescription, DispensaryStock,
    DispensaryDeliveryNote, DispensaryDeliveryItem,
    InstitutionSecurityPolicy,
    InstitutionLifecycleTemplate, InstitutionLifecycleTaskTemplate,
    InstitutionLifecycleRun, InstitutionLifecycleTaskRun,
)
from hr.models import Staff
from hr.models import Department as HrDepartment

# ==========================================
# DEPARTMENT SERIALIZERS
# ==========================================
class DepartmentSerializer(serializers.ModelSerializer):
    """Used by academics module — backed by school.Department."""
    class Meta:
        model = Department
        fields = ['id', 'name', 'description', 'is_active']

class HrDepartmentSerializer(serializers.ModelSerializer):
    """Shared cross-module serializer — backed by hr.Department (single source of truth)."""
    class Meta:
        model = HrDepartment
        fields = ['id', 'name', 'description', 'is_active']

# ==========================================
# ACADEMIC & STUDENT SERIALIZERS    
# ==========================================
class GuardianSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guardian
        fields = ['id', 'name', 'relationship', 'phone', 'email', 'is_active']

class StudentSerializer(serializers.ModelSerializer): 
    admission_number = serializers.CharField(required=False, allow_blank=True)
    guardians = GuardianSerializer(many=True, read_only=True)
    uploaded_documents = serializers.SerializerMethodField()
    class Meta:
        model = Student
        fields = [
            'id', 'ulid', 'admission_number', 'first_name', 'last_name',
            'date_of_birth', 'gender', 'phone', 'email', 'address', 'photo', 'is_active',
            'created_at', 'guardians', 'uploaded_documents',
        ]
        read_only_fields = ['ulid', 'created_at']

    def get_uploaded_documents(self, obj):
        return [
            {
                "id": doc.id,
                "name": doc.file.name,
                "url": doc.file.url,
                "uploaded_at": doc.uploaded_at,
            }
            for doc in obj.uploaded_documents.all()
        ]

class SchoolClassSerializer(serializers.ModelSerializer):
    display_name = serializers.ReadOnlyField()

    class Meta:
        model = SchoolClass
        fields = [
            'id', 'name', 'stream', 'display_name', 'academic_year',
            'grade_level', 'section_name', 'class_teacher', 'room',
            'capacity', 'is_active'
        ]

class SchoolProfileSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = SchoolProfile
        fields = [
            'id',
            'school_name',
            'logo',
            'logo_url',
            'motto',
            'address',
            'phone',
            'email_address',
            'website',
            'county',
            'country',
            'primary_color',
            'secondary_color',
            'font_family',
            'currency',
            'tax_percentage',
            'receipt_prefix',
            'invoice_prefix',
            'admission_number_mode',
            'admission_number_prefix',
            'admission_number_padding',
            'timezone',
            'language',
            'default_date_format',
            'late_fee_grace_days',
            'late_fee_type',
            'late_fee_value',
            'late_fee_max',
            'accepted_payment_methods',
            'smtp_host',
            'smtp_port',
            'smtp_user',
            'smtp_password',
            'smtp_use_tls',
            'sms_provider',
            'sms_api_key',
            'sms_username',
            'sms_sender_id',
            'whatsapp_api_key',
            'whatsapp_phone_id',
            'is_active',
        ]
        read_only_fields = ['id', 'logo_url']
        extra_kwargs = {
            'smtp_password': {'write_only': True},
            'sms_api_key': {'write_only': True},
            'whatsapp_api_key': {'write_only': True},
        }

    def get_logo_url(self, obj):
        request = self.context.get('request')
        if obj.logo and request:
            return request.build_absolute_uri(obj.logo.url)
        return obj.logo.url if obj.logo else None


class InstitutionSecurityPolicySerializer(serializers.ModelSerializer):
    updated_by_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = InstitutionSecurityPolicy
        fields = [
            'id',
            'session_timeout_minutes',
            'max_login_attempts',
            'lockout_duration_minutes',
            'min_password_length',
            'require_uppercase',
            'require_numbers',
            'require_special_characters',
            'password_expiry_days',
            'mfa_mode',
            'mfa_method',
            'ip_whitelist_enabled',
            'allowed_ip_ranges',
            'audit_log_retention_days',
            'updated_by',
            'updated_by_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'updated_by', 'updated_by_name', 'created_at', 'updated_at']

    def get_updated_by_name(self, obj):
        user = getattr(obj, 'updated_by', None)
        if not user:
            return None
        return user.get_full_name() or user.username

    def validate_allowed_ip_ranges(self, value):
        return normalize_allowed_ip_ranges(value)

    def validate_mfa_mode(self, value):
        normalized = str(value).upper()
        valid = {choice for choice, _label in InstitutionSecurityPolicy.MFA_MODE_CHOICES}
        if normalized not in valid:
            raise serializers.ValidationError("Unsupported MFA mode.")
        return normalized

    def validate_mfa_method(self, value):
        normalized = str(value).upper()
        valid = {choice for choice, _label in InstitutionSecurityPolicy.MFA_METHOD_CHOICES}
        if normalized not in valid:
            raise serializers.ValidationError("Unsupported MFA method.")
        return normalized


class InstitutionLifecycleTaskTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstitutionLifecycleTaskTemplate
        fields = [
            'id',
            'task_code',
            'title',
            'description',
            'task_group',
            'required',
            'display_order',
            'waivable',
            'validation_key',
        ]
        read_only_fields = fields


class InstitutionLifecycleTemplateSerializer(serializers.ModelSerializer):
    task_templates = InstitutionLifecycleTaskTemplateSerializer(many=True, read_only=True)

    class Meta:
        model = InstitutionLifecycleTemplate
        fields = [
            'id',
            'code',
            'name',
            'description',
            'is_active',
            'task_templates',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class InstitutionLifecycleTaskRunSerializer(serializers.ModelSerializer):
    template_task_id = serializers.IntegerField(source='template_task.id', read_only=True)
    template_task_code = serializers.CharField(source='template_task.task_code', read_only=True)
    template_task_title = serializers.CharField(source='template_task.title', read_only=True)
    template_task_description = serializers.CharField(source='template_task.description', read_only=True)
    template_task_group = serializers.CharField(source='template_task.task_group', read_only=True)
    required = serializers.BooleanField(source='template_task.required', read_only=True)
    waivable = serializers.BooleanField(source='template_task.waivable', read_only=True)
    validation_key = serializers.CharField(source='template_task.validation_key', read_only=True)
    completed_by_name = serializers.CharField(source='completed_by.username', read_only=True)
    waived_by_name = serializers.CharField(source='waived_by.username', read_only=True)

    class Meta:
        model = InstitutionLifecycleTaskRun
        fields = [
            'id',
            'template_task_id',
            'template_task_code',
            'template_task_title',
            'template_task_description',
            'template_task_group',
            'required',
            'waivable',
            'validation_key',
            'status',
            'completed_by',
            'completed_by_name',
            'completed_at',
            'waived_by',
            'waived_by_name',
            'waived_at',
            'notes',
            'evidence',
            'blocker_message',
            'display_order',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class InstitutionLifecycleRunSerializer(serializers.ModelSerializer):
    template_code = serializers.CharField(source='template.code', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True)
    started_by_name = serializers.CharField(source='started_by.username', read_only=True)
    completed_by_name = serializers.CharField(source='completed_by.username', read_only=True)
    target_academic_year_name = serializers.CharField(source='target_academic_year.name', read_only=True)
    target_term_name = serializers.CharField(source='target_term.name', read_only=True)
    target_term_academic_year_id = serializers.IntegerField(source='target_term.academic_year_id', read_only=True)

    class Meta:
        model = InstitutionLifecycleRun
        fields = [
            'id',
            'template',
            'template_code',
            'template_name',
            'status',
            'started_by',
            'started_by_name',
            'completed_by',
            'completed_by_name',
            'started_at',
            'completed_at',
            'target_academic_year',
            'target_academic_year_name',
            'target_term',
            'target_term_name',
            'target_term_academic_year_id',
            'summary',
            'metadata',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class InstitutionLifecycleRunDetailSerializer(InstitutionLifecycleRunSerializer):
    task_runs = InstitutionLifecycleTaskRunSerializer(many=True, read_only=True)

    class Meta(InstitutionLifecycleRunSerializer.Meta):
        fields = InstitutionLifecycleRunSerializer.Meta.fields + ['task_runs']
        read_only_fields = fields

# ==========================================
# FINANCE SERIALIZERS
# ==========================================
class TermSerializer(serializers.ModelSerializer):
    class Meta:
        model = Term
        fields = [
            'id', 'name', 'start_date', 'end_date', 'billing_date',
            'academic_year', 'is_active', 'is_current'
        ]

class FeeStructureSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeStructure
        fields = [
            'id',
            'name',
            'category',
            'amount',
            'academic_year',
            'term',
            'grade_level',
            'billing_cycle',
            'is_mandatory',
            'description',
            'is_active',
        ]

class InvoiceLineItemSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    
    fee_structure = serializers.PrimaryKeyRelatedField(
        queryset=FeeStructure.objects.all()
    )
    
    description = serializers.CharField(allow_blank=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    
    class Meta:
        model = InvoiceLineItem
        fields = ['id', 'fee_structure', 'description', 'amount']
        
class InvoiceSerializer(serializers.ModelSerializer):
    """
    Handles Invoice creation and display.
    Balances are derived (property) and included automatically.
    """
    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all())
    term = serializers.PrimaryKeyRelatedField(queryset=Term.objects.all())
    student_admission_number = serializers.CharField(source='student.admission_number', read_only=True)
    student_full_name = serializers.SerializerMethodField()
    line_items = InvoiceLineItemSerializer(many=True)
    balance_due = serializers.ReadOnlyField() # Derived from model property
    invoice_number = serializers.CharField(read_only=True)

    def get_student_full_name(self, obj):
        if not obj.student:
            return ""
        return f"{obj.student.first_name} {obj.student.last_name}".strip()
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'student', 'student_admission_number', 'term', 
            'invoice_date', 'due_date', 'total_amount', 'status', 
            'balance_due', 'is_active', 'created_at', 'line_items', 'student_full_name'
        ]
        read_only_fields = ['invoice_date', 'created_at',  'total_amount']

        depth = 1

    # Note: Create logic is complex, so we will handle it in the Service Layer, 
    # but we define the structure here.

class PaymentAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentAllocation
        fields = ['id', 'invoice', 'amount_allocated', 'allocated_at']
        read_only_fields = ['allocated_at']

class PaymentSerializer(serializers.ModelSerializer):
    allocations = PaymentAllocationSerializer(many=True, required=False)
    allocated_amount = serializers.SerializerMethodField()
    unallocated_amount = serializers.SerializerMethodField()
    student_name = serializers.CharField(source='student', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'student', 'payment_date', 'amount', 'payment_method', 
            'reference_number', 'receipt_number', 'notes', 'is_active',
            'reversed_at', 'reversal_reason', 'reversed_by', 'allocations',
            'allocated_amount', 'unallocated_amount', 'student_name'
        ]
        read_only_fields = ['payment_date', 'receipt_number', 'reversed_at', 'reversed_by']

    def get_allocated_amount(self, obj):
        total = obj.allocations.aggregate(total=models.Sum('amount_allocated'))['total'] or 0
        return total

    def get_unallocated_amount(self, obj):
        total = obj.allocations.aggregate(total=models.Sum('amount_allocated'))['total'] or 0
        return obj.amount - total

# ... existing imports ...

# ADD THIS CLASS:
class EnrollmentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student', read_only=True)
    class_name = serializers.CharField(source='school_class', read_only=True)
    
    class Meta:
        model = Enrollment
        fields = [
            'id',
            'student',
            'student_name',
            'school_class',
            'class_name',
            'term',
            'enrollment_date',
            'left_date',
            'status',
            'is_active',
        ]

class AdmissionApplicationSerializer(serializers.ModelSerializer):
    applying_for_grade_name = serializers.CharField(source='applying_for_grade.name', read_only=True)
    documents_upload = serializers.ListField(
        child=serializers.FileField(),
        write_only=True,
        required=False
    )
    uploaded_documents = serializers.SerializerMethodField()

    class Meta:
        model = AdmissionApplication
        fields = [
            'id', 'application_number', 'student_first_name', 'student_last_name',
            'student_dob', 'student_gender', 'previous_school', 'applying_for_grade',
            'applying_for_grade_name', 'application_date', 'status',
            'interview_date', 'interview_notes', 'assessment_score',
            'decision', 'decision_date', 'decision_notes', 'student',
            'guardian_name', 'guardian_phone', 'guardian_email', 'notes',
            'documents', 'student_photo', 'documents_upload', 'uploaded_documents', 'created_at'
        ]
        read_only_fields = ['application_number', 'created_at']

    def get_uploaded_documents(self, obj):
        return [
            {
                "id": doc.id,
                "name": doc.file.name,
                "url": doc.file.url
            }
            for doc in obj.uploaded_documents.all()
        ]

    def create(self, validated_data):
        documents_files = validated_data.pop('documents_upload', [])
        instance = super().create(validated_data)

        if documents_files:
            docs_payload = []
            for upload in documents_files:
                doc = AdmissionDocument.objects.create(application=instance, file=upload)
                docs_payload.append({"type": doc.file.name, "received": True})

            if not instance.documents:
                instance.documents = []
            instance.documents.extend(docs_payload)
            instance.save(update_fields=['documents'])

        return instance

class StudentDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentDocument
        fields = ['id', 'student', 'file', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']

class AttendanceRecordSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student', read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = ['id', 'student', 'student_name', 'date', 'status', 'notes', 'recorded_by', 'created_at']
        read_only_fields = ['created_at', 'recorded_by']

class BehaviorIncidentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student', read_only=True)

    class Meta:
        model = BehaviorIncident
        fields = [
            'id', 'student', 'student_name', 'incident_type', 'category',
            'incident_date', 'description', 'severity', 'reported_by', 'created_at'
        ]
        read_only_fields = ['created_at', 'reported_by']


class MedicalRecordSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student', read_only=True)
    last_visit = serializers.SerializerMethodField()

    class Meta:
        model = MedicalRecord
        fields = [
            'id', 'student', 'student_name', 'blood_type', 'allergies',
            'chronic_conditions', 'current_medications', 'doctor_name',
            'doctor_phone', 'notes', 'last_visit', 'updated_at'
        ]
        read_only_fields = ['updated_at']

    def get_last_visit(self, obj):
        visit = obj.student.clinic_visits.order_by('-visit_date', '-created_at').first()
        if not visit:
            return None
        return str(visit.visit_date)


class ImmunizationRecordSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student', read_only=True)
    certificate_url = serializers.SerializerMethodField()

    class Meta:
        model = ImmunizationRecord
        fields = [
            'id', 'student', 'student_name', 'vaccine_name', 'date_administered',
            'booster_due_date', 'certificate', 'certificate_url', 'created_at'
        ]
        read_only_fields = ['created_at']

    def get_certificate_url(self, obj):
        return obj.certificate.url if obj.certificate else None


class ClinicVisitSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student', read_only=True)
    attended_by_name = serializers.CharField(source='attended_by.username', read_only=True)

    class Meta:
        model = ClinicVisit
        fields = [
            'id', 'student', 'student_name', 'visit_date', 'visit_time',
            'complaint', 'treatment', 'attended_by', 'attended_by_name',
            'parent_notified', 'severity', 'created_at'
        ]
        read_only_fields = ['created_at', 'attended_by']

class StaffSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staff
        fields = ['id', 'first_name', 'last_name', 'employee_id', 'role', 'phone', 'is_active', 'created_at']
        read_only_fields = ['created_at']

class FinanceStudentRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = [
            'id', 'ulid', 'admission_number', 'first_name', 'last_name',
            'gender', 'is_active'
        ]

class FinanceEnrollmentRefSerializer(serializers.ModelSerializer):
    student_ulid = serializers.CharField(source='student.ulid', read_only=True)
    student_admission_number = serializers.CharField(source='student.admission_number', read_only=True)
    student_name = serializers.SerializerMethodField()
    class_name = serializers.CharField(source='school_class.name', read_only=True)
    term_name = serializers.CharField(source='term.name', read_only=True)

    class Meta:
        model = Enrollment
        fields = [
            'id', 'student', 'student_ulid', 'student_admission_number', 'student_name',
            'school_class', 'class_name', 'term', 'term_name', 'is_active'
        ]

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"

class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = ['id', 'key', 'name', 'is_active', 'created_at']
        read_only_fields = ['created_at']

class UserModuleAssignmentSerializer(serializers.ModelSerializer):
    module_key = serializers.CharField(source='module.key', read_only=True)
    module_name = serializers.CharField(source='module.name', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    assigned_by_name = serializers.CharField(source='assigned_by.username', read_only=True)

    class Meta:
        model = UserModuleAssignment
        fields = [
            'id', 'user', 'user_name', 'module', 'module_key', 'module_name',
            'assigned_by', 'assigned_by_name', 'is_active', 'assigned_at'
        ]
        read_only_fields = ['assigned_at', 'assigned_by']


class ModuleSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModuleSetting
        fields = [
            'id',
            'theme_preset',
            'primary_color',
            'secondary_color',
            'sidebar_style',
            'feature_toggles',
            'config',
            'updated_at',
        ]
        read_only_fields = ['id', 'updated_at']

    def validate(self, attrs):
        def _is_hex_color(value: str) -> bool:
            if not isinstance(value, str):
                return False
            if not value.startswith('#'):
                return False
            code = value[1:]
            if len(code) not in (3, 6):
                return False
            return all(ch in '0123456789abcdefABCDEF' for ch in code)

        for color_field in ('primary_color', 'secondary_color'):
            if color_field in attrs and not _is_hex_color(attrs[color_field]):
                raise serializers.ValidationError({color_field: 'Use a valid hex color like #10b981.'})

        toggles = attrs.get('feature_toggles')
        if toggles is not None:
            if not isinstance(toggles, dict):
                raise serializers.ValidationError({'feature_toggles': 'feature_toggles must be an object.'})
            allowed = {'analytics', 'reports', 'export', 'ai_assistant'}
            unknown = sorted([key for key in toggles.keys() if key not in allowed])
            if unknown:
                raise serializers.ValidationError(
                    {'feature_toggles': f'Unsupported feature toggles: {", ".join(unknown)}'}
                )
            for key in allowed:
                if key in toggles and not isinstance(toggles[key], bool):
                    raise serializers.ValidationError({'feature_toggles': f'"{key}" must be a boolean.'})

        return attrs


class TenantModuleSerializer(serializers.ModelSerializer):
    module_id = serializers.IntegerField(source='module.id', read_only=True)
    module_key = serializers.CharField(source='module.key', read_only=True)
    module_name = serializers.CharField(source='module.name', read_only=True)
    settings = ModuleSettingSerializer(read_only=True)

    class Meta:
        model = TenantModule
        fields = [
            'id',
            'module_id',
            'module_key',
            'module_name',
            'is_enabled',
            'sort_order',
            'settings',
            'updated_at',
        ]
        read_only_fields = fields


class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = [
            'id',
            'category',
            'amount',
            'expense_date',
            'vendor',
            'payment_method',
            'invoice_number',
            'approval_status',
            'description',
            'is_active',
            'created_at',
        ]
        read_only_fields = ['created_at']


class BudgetSerializer(serializers.ModelSerializer):
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True)
    term_name = serializers.CharField(source='term.name', read_only=True)

    class Meta:
        model = Budget
        fields = [
            'id',
            'name',
            'academic_year',
            'academic_year_name',
            'term',
            'term_name',
            'monthly_budget',
            'quarterly_budget',
            'annual_budget',
            'categories',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

class FeeAssignmentSerializer(serializers.ModelSerializer):
    fee_name = serializers.CharField(source='fee_structure.name', read_only=True)
    student_name = serializers.CharField(source='student', read_only=True)

    class Meta:
        model = FeeAssignment
        fields = [
            'id',
            'student',
            'student_name',
            'fee_structure',
            'fee_name',
            'discount_amount',
            'start_date',
            'end_date',
            'is_active',
        ]

class ScholarshipAwardSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.username', read_only=True)

    class Meta:
        model = ScholarshipAward
        fields = [
            'id',
            'student',
            'student_name',
            'program_name',
            'award_type',
            'amount',
            'percentage',
            'start_date',
            'end_date',
            'status',
            'notes',
            'is_active',
            'created_by',
            'created_by_name',
            'approved_by',
            'approved_by_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_by', 'approved_by', 'created_at', 'updated_at']

class OptionalChargeSerializer(serializers.ModelSerializer):
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True)
    term_name = serializers.CharField(source='term.name', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = OptionalCharge
        fields = [
            'id', 'name', 'description', 'category', 'category_display',
            'amount', 'academic_year', 'academic_year_name',
            'term', 'term_name', 'is_active', 'created_at', 'updated_at'
        ]

class StudentOptionalChargeSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student', read_only=True)
    charge_name = serializers.CharField(source='optional_charge.name', read_only=True)
    charge_amount = serializers.DecimalField(source='optional_charge.amount', max_digits=12, decimal_places=2, read_only=True)
    category = serializers.CharField(source='optional_charge.category', read_only=True)

    class Meta:
        model = StudentOptionalCharge
        fields = [
            'id', 'student', 'student_name', 'optional_charge', 'charge_name',
            'charge_amount', 'category', 'invoice', 'is_paid', 'notes', 'assigned_at'
        ]

class InvoiceAdjustmentSerializer(serializers.ModelSerializer):
    adjusted_by_name = serializers.CharField(source='adjusted_by.username', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.username', read_only=True)
    
    class Meta:
        model = InvoiceAdjustment
        fields = [
            'id',
            'invoice',
            'adjustment_type',
            'amount',
            'reason',
            'adjusted_by',
            'adjusted_by_name',
            'status',
            'reviewed_by',
            'reviewed_by_name',
            'reviewed_at',
            'review_notes',
            'created_at',
        ]
        read_only_fields = ['created_at', 'adjusted_by', 'status', 'reviewed_by', 'reviewed_at', 'review_notes']


class PaymentReversalRequestSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.CharField(source='requested_by.username', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.username', read_only=True)
    payment_reference = serializers.CharField(source='payment.reference_number', read_only=True)
    payment_receipt = serializers.CharField(source='payment.receipt_number', read_only=True)

    class Meta:
        model = PaymentReversalRequest
        fields = [
            'id',
            'payment',
            'payment_reference',
            'payment_receipt',
            'reason',
            'requested_by',
            'requested_by_name',
            'requested_at',
            'status',
            'reviewed_by',
            'reviewed_by_name',
            'reviewed_at',
            'review_notes',
        ]
        read_only_fields = ['requested_by', 'requested_at', 'status', 'reviewed_by', 'reviewed_at']


class InvoiceWriteOffRequestSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.CharField(source='requested_by.username', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.username', read_only=True)
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)
    student_name = serializers.CharField(source='invoice.student', read_only=True)
    adjustment_id = serializers.IntegerField(source='applied_adjustment_id', read_only=True)

    class Meta:
        model = InvoiceWriteOffRequest
        fields = [
            'id',
            'invoice',
            'invoice_number',
            'student_name',
            'amount',
            'reason',
            'requested_by',
            'requested_by_name',
            'requested_at',
            'status',
            'reviewed_by',
            'reviewed_by_name',
            'reviewed_at',
            'review_notes',
            'adjustment_id',
        ]
        read_only_fields = [
            'requested_by', 'requested_at', 'status',
            'reviewed_by', 'reviewed_at', 'review_notes', 'adjustment_id',
        ]


class InvoiceInstallmentSerializer(serializers.ModelSerializer):
    outstanding_amount = serializers.SerializerMethodField()

    class Meta:
        model = InvoiceInstallment
        fields = [
            'id', 'sequence', 'due_date', 'amount', 'collected_amount',
            'outstanding_amount', 'status', 'paid_at', 'late_fee_applied'
        ]
        read_only_fields = ['status', 'paid_at', 'late_fee_applied']

    def get_outstanding_amount(self, obj):
        outstanding = (obj.amount or 0) - (obj.collected_amount or 0)
        return outstanding if outstanding > 0 else 0


class InvoiceInstallmentPlanSerializer(serializers.ModelSerializer):
    installments = InvoiceInstallmentSerializer(many=True, required=False)

    class Meta:
        model = InvoiceInstallmentPlan
        fields = ['id', 'invoice', 'installment_count', 'created_by', 'created_at', 'installments']
        read_only_fields = ['created_by', 'created_at']


class LateFeeRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = LateFeeRule
        fields = ['id', 'grace_days', 'fee_type', 'value', 'max_fee', 'is_active']


class FeeReminderLogSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)

    class Meta:
        model = FeeReminderLog
        fields = ['id', 'invoice', 'invoice_number', 'channel', 'recipient', 'sent_at', 'status', 'message']
        read_only_fields = ['sent_at']


class AccountingPeriodSerializer(serializers.ModelSerializer):
    closed_by_name = serializers.CharField(source='closed_by.username', read_only=True)

    class Meta:
        model = AccountingPeriod
        fields = [
            'id', 'name', 'start_date', 'end_date',
            'is_closed', 'closed_at', 'closed_by', 'closed_by_name', 'created_at',
        ]
        read_only_fields = ['closed_at', 'closed_by', 'created_at']


class ChartOfAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChartOfAccount
        fields = ['id', 'code', 'name', 'account_type', 'is_active', 'created_at']
        read_only_fields = ['created_at']


class JournalLineSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source='account.code', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)
    vote_head_name = serializers.CharField(source='vote_head.name', read_only=True)

    class Meta:
        model = JournalLine
        fields = ['id', 'account', 'account_code', 'account_name', 'vote_head', 'vote_head_name', 'debit', 'credit', 'description']


class JournalEntrySerializer(serializers.ModelSerializer):
    lines = JournalLineSerializer(many=True)
    posted_by_name = serializers.CharField(source='posted_by.username', read_only=True)

    class Meta:
        model = JournalEntry
        fields = [
            'id', 'entry_date', 'memo', 'source_type', 'source_id',
            'entry_key', 'posted_by', 'posted_by_name', 'created_at', 'lines',
        ]
        read_only_fields = ['created_at']


class PaymentGatewayTransactionSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student', read_only=True)
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)

    class Meta:
        model = PaymentGatewayTransaction
        fields = [
            'id', 'provider', 'external_id', 'student', 'student_name', 'invoice', 'invoice_number',
            'amount', 'currency', 'status', 'payload', 'is_reconciled', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'is_reconciled']


class PaymentGatewayWebhookEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentGatewayWebhookEvent
        fields = [
            'id', 'event_id', 'provider', 'event_type', 'signature', 'payload',
            'processed', 'processed_at', 'error', 'received_at'
        ]
        read_only_fields = ['processed', 'processed_at', 'error', 'received_at']


class BankStatementLineSerializer(serializers.ModelSerializer):
    matched_payment_reference = serializers.CharField(source='matched_payment.reference_number', read_only=True)
    matched_gateway_external_id = serializers.CharField(source='matched_gateway_transaction.external_id', read_only=True)

    class Meta:
        model = BankStatementLine
        fields = [
            'id', 'statement_date', 'value_date', 'amount', 'reference', 'narration', 'source',
            'status', 'matched_payment', 'matched_payment_reference',
            'matched_gateway_transaction', 'matched_gateway_external_id', 'imported_at'
        ]
        read_only_fields = ['imported_at']



class VoteHeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoteHead
        fields = ['id', 'name', 'description', 'allocation_percentage', 'is_preloaded', 'is_active', 'order', 'created_at']
        read_only_fields = ['created_at']


class VoteHeadPaymentAllocationSerializer(serializers.ModelSerializer):
    vote_head_name = serializers.CharField(source='vote_head.name', read_only=True)
    receipt_number = serializers.CharField(source='payment.receipt_number', read_only=True)

    class Meta:
        model = VoteHeadPaymentAllocation
        fields = ['id', 'payment', 'vote_head', 'vote_head_name', 'receipt_number', 'amount', 'allocated_at']
        read_only_fields = ['allocated_at']


class CashbookEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = CashbookEntry
        fields = [
            'id', 'book_type', 'entry_date', 'entry_type', 'reference',
            'description', 'amount_in', 'amount_out', 'running_balance',
            'payment', 'expense', 'is_auto', 'created_at'
        ]
        read_only_fields = ['running_balance', 'is_auto', 'created_at']


class BalanceCarryForwardSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    student_admission_number = serializers.CharField(source='student.admission_number', read_only=True)
    from_term_name = serializers.CharField(source='from_term.name', read_only=True)
    to_term_name = serializers.CharField(source='to_term.name', read_only=True)

    class Meta:
        model = BalanceCarryForward
        fields = [
            'id', 'student', 'student_name', 'student_admission_number',
            'from_term', 'from_term_name', 'to_term', 'to_term_name',
            'amount', 'notes', 'created_by', 'created_at'
        ]
        read_only_fields = ['created_by', 'created_at']

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}".strip()


# ==========================================
# DISPENSARY SERIALIZERS
# ==========================================

class DispensaryPrescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DispensaryPrescription
        fields = ['id', 'visit', 'medication_name', 'dosage', 'frequency', 'quantity_dispensed', 'unit', 'notes', 'created_at']
        read_only_fields = ['created_at']


class DispensaryVisitSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    student_admission_number = serializers.CharField(source='student.admission_number', read_only=True)
    attended_by_name = serializers.SerializerMethodField()
    prescriptions = DispensaryPrescriptionSerializer(many=True, read_only=True)

    class Meta:
        model = DispensaryVisit
        fields = [
            'id', 'student', 'student_name', 'student_admission_number',
            'visit_date', 'visit_time', 'complaint', 'diagnosis', 'treatment',
            'attended_by', 'attended_by_name', 'severity', 'parent_notified',
            'referred', 'referred_to', 'follow_up_date', 'notes', 'created_at',
            'prescriptions'
        ]
        read_only_fields = ['created_at']

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}".strip()

    def get_attended_by_name(self, obj):
        if obj.attended_by:
            return f"{obj.attended_by.first_name} {obj.attended_by.last_name}".strip() or obj.attended_by.username
        return ''


class DispensaryStockSerializer(serializers.ModelSerializer):
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = DispensaryStock
        fields = [
            'id', 'medication_name', 'generic_name', 'current_quantity', 'unit',
            'reorder_level', 'expiry_date', 'supplier', 'notes', 'is_low_stock',
            'updated_at', 'created_at'
        ]
        read_only_fields = ['updated_at', 'created_at']


class DispensaryDeliveryItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = DispensaryDeliveryItem
        fields = ['id', 'medication_name', 'quantity', 'unit', 'unit_cost', 'total_cost', 'stock']
        read_only_fields = ['total_cost']


class DispensaryDeliveryNoteSerializer(serializers.ModelSerializer):
    items = DispensaryDeliveryItemSerializer(many=True, read_only=True)
    received_by_name = serializers.SerializerMethodField()
    grand_total = serializers.SerializerMethodField()

    class Meta:
        model = DispensaryDeliveryNote
        fields = [
            'id', 'reference_number', 'supplier', 'delivery_date', 'status',
            'notes', 'finance_expense_id', 'received_by', 'received_by_name',
            'items', 'grand_total', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'received_by_name', 'grand_total']

    def get_received_by_name(self, obj):
        if obj.received_by:
            return f"{obj.received_by.first_name} {obj.received_by.last_name}".strip() or obj.received_by.username
        return ''

    def get_grand_total(self, obj):
        return str(sum(item.total_cost for item in obj.items.all()))


class DispensaryOutsideTreatmentSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()

    class Meta:
        from .models import DispensaryOutsideTreatment
        model = DispensaryOutsideTreatment
        fields = [
            'id', 'patient_name', 'patient_type', 'student', 'student_name',
            'referral_date', 'facility_name', 'reason', 'diagnosis',
            'treatment_given', 'cost', 'follow_up_date', 'notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'student_name']

    def get_student_name(self, obj):
        if obj.student:
            return obj.student.full_name
        return ''


class StudentTransferSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()

    class Meta:
        from .models import StudentTransfer
        model = StudentTransfer
        fields = [
            'id', 'student', 'student_name', 'direction', 'other_school',
            'reason', 'effective_date', 'status',
            'clearance_completed', 'academic_records_issued',
            'transfer_letter_issued', 'fee_balance_cleared',
            'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'student_name']

    def get_student_name(self, obj):
        return obj.student.full_name if obj.student else ''


# ─────────────────────────────────────────────
# TRANSFER SYSTEM SERIALIZERS
# ─────────────────────────────────────────────

class CrossTenantTransferSerializer(serializers.ModelSerializer):
    initiated_by_name   = serializers.SerializerMethodField()
    approved_from_name  = serializers.SerializerMethodField()
    approved_to_name    = serializers.SerializerMethodField()
    entity_name         = serializers.SerializerMethodField()
    status_display      = serializers.SerializerMethodField()
    type_display        = serializers.SerializerMethodField()
    has_package         = serializers.SerializerMethodField()

    class Meta:
        from .models import CrossTenantTransfer
        model = CrossTenantTransfer
        fields = [
            'id', 'transfer_type', 'type_display', 'entity_id', 'entity_name',
            'from_tenant_id', 'to_tenant_id', 'status', 'status_display',
            'reason', 'fee_balance_cleared', 'exam_in_progress', 'mid_term',
            'initiated_by', 'initiated_by_name',
            'approved_from_by', 'approved_from_name',
            'approved_to_by', 'approved_to_name',
            'rejected_by', 'rejection_reason',
            'from_class', 'to_class', 'from_stream', 'to_stream',
            'from_department', 'to_department', 'from_role', 'to_role',
            'effective_date', 'executed_at', 'notes',
            'has_package', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'status', 'initiated_by', 'approved_from_by', 'approved_to_by',
            'rejected_by', 'executed_at', 'created_at', 'updated_at',
            'exam_in_progress', 'mid_term',
        ]

    def get_initiated_by_name(self, obj):
        if obj.initiated_by:
            return obj.initiated_by.get_full_name() or obj.initiated_by.username
        return ''

    def get_approved_from_name(self, obj):
        if obj.approved_from_by:
            return obj.approved_from_by.get_full_name() or obj.approved_from_by.username
        return ''

    def get_approved_to_name(self, obj):
        if obj.approved_to_by:
            return obj.approved_to_by.get_full_name() or obj.approved_to_by.username
        return ''

    def get_entity_name(self, obj):
        try:
            if 'student' in obj.transfer_type:
                from .models import Student
                s = Student.objects.filter(id=obj.entity_id).first()
                if s:
                    return f"{s.first_name} {s.last_name} ({s.admission_number})"
            else:
                try:
                    from hr.models import Employee
                    e = Employee.objects.filter(id=obj.entity_id).first()
                    if e:
                        return f"{e.first_name} {e.last_name} ({e.employee_id})"
                except Exception:
                    pass
        except Exception:
            pass
        return f"Entity #{obj.entity_id}"

    def get_status_display(self, obj):
        return dict(obj.STATUS_CHOICES).get(obj.status, obj.status)

    def get_type_display(self, obj):
        return dict(obj.TYPE_CHOICES).get(obj.transfer_type, obj.transfer_type)

    def get_has_package(self, obj):
        return hasattr(obj, 'package')


class TransferPackageSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import TransferPackage
        model = TransferPackage
        fields = ['id', 'transfer', 'data_snapshot', 'generated_at']
        read_only_fields = ['generated_at']


class StudentHistorySerializer(serializers.ModelSerializer):
    class Meta:
        from .models import StudentHistory
        model = StudentHistory
        fields = ['id', 'student', 'tenant_id', 'school_name', 'class_name', 'stream',
                  'start_date', 'end_date', 'transfer', 'created_at']
        read_only_fields = ['created_at']


class StaffHistorySerializer(serializers.ModelSerializer):
    class Meta:
        from .models import StaffHistory
        model = StaffHistory
        fields = ['id', 'employee_id', 'employee_name', 'tenant_id', 'school_name',
                  'role', 'department', 'start_date', 'end_date', 'transfer', 'created_at']
        read_only_fields = ['created_at']
