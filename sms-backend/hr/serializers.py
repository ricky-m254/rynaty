from decimal import Decimal

from rest_framework import serializers
from school.role_scope import iter_seed_role_names, normalize_role_name

from .identity import normalize_staff_category
from .models import (
    Staff,
    Department,
    Position,
    Employee,
    EmployeeEmploymentProfile,
    EmployeeQualification,
    EmergencyContact,
    EmployeeDocument,
    ShiftTemplate,
    AttendanceRecord,
    AbsenceAlert,
    TeachingSubstituteAssignment,
    WorkSchedule,
    LeaveType,
    LeavePolicy,
    LeaveBalance,
    LeaveRequest,
    ReturnToWorkReconciliation,
    SalaryStructure,
    SalaryComponent,
    StatutoryDeductionRule,
    StatutoryDeductionBand,
    PayrollBatch,
    PayrollItem,
    PayrollItemBreakdown,
    PayrollDisbursement,
    PayrollFinancePosting,
    JobPosting,
    JobApplication,
    Interview,
    OnboardingTask,
    PerformanceGoal,
    PerformanceReview,
    TrainingProgram,
    TrainingEnrollment,
    StaffLifecycleEvent,
    StaffCareerAction,
    DisciplinaryCase,
    ExitCase,
    ExitClearanceItem,
    StaffTransfer,
)

SUPPORTED_ROLE_NAMES = set(iter_seed_role_names())


class StaffSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staff
        fields = [
            "id", "first_name", "last_name", "employee_id",
            "role", "phone", "is_active", "created_at"
        ]
        read_only_fields = ["created_at"]


class DepartmentSerializer(serializers.ModelSerializer):
    head_name = serializers.SerializerMethodField()
    parent_name = serializers.CharField(source="parent.name", read_only=True)
    school_department = serializers.IntegerField(source="school_department_id", read_only=True)

    class Meta:
        model = Department
        fields = [
            "id",
            "name",
            "code",
            "parent",
            "parent_name",
            "description",
            "head",
            "head_name",
            "budget",
            "school_department",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["created_at", "head_name", "parent_name", "school_department"]

    def get_head_name(self, obj):
        if not obj.head:
            return ""
        return f"{obj.head.first_name} {obj.head.last_name}".strip()


class PositionSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = Position
        fields = [
            "id",
            "title",
            "department",
            "department_name",
            "description",
            "responsibilities",
            "qualifications",
            "experience_years",
            "salary_min",
            "salary_max",
            "headcount",
            "is_active",
        ]
        read_only_fields = ["department_name"]


class EmployeeSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    department_name = serializers.CharField(source="department.name", read_only=True)
    position_title = serializers.CharField(source="position.title", read_only=True)
    reporting_to_name = serializers.SerializerMethodField()
    has_biometric_link = serializers.SerializerMethodField()
    has_primary_emergency_contact = serializers.SerializerMethodField()
    qualification_count = serializers.SerializerMethodField()
    archived_by_name = serializers.CharField(source="archived_by.username", read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id",
            "user",
            "employee_id",
            "staff_id",
            "first_name",
            "middle_name",
            "last_name",
            "full_name",
            "date_of_birth",
            "gender",
            "nationality",
            "national_id",
            "personal_email",
            "work_email",
            "marital_status",
            "photo",
            "blood_group",
            "medical_conditions",
            "department",
            "department_name",
            "position",
            "position_title",
            "staff_category",
            "employment_type",
            "status",
            "onboarding_status",
            "account_role_name",
            "account_provisioned_at",
            "has_biometric_link",
            "has_primary_emergency_contact",
            "qualification_count",
            "join_date",
            "probation_end",
            "confirmation_date",
            "contract_start",
            "contract_end",
            "reporting_to",
            "reporting_to_name",
            "work_location",
            "notice_period_days",
            "exit_date",
            "exit_reason",
            "exit_notes",
            "archived_at",
            "archived_by",
            "archived_by_name",
            "archive_reason",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "employee_id",
            "staff_id",
            "full_name",
            "department_name",
            "position_title",
            "reporting_to_name",
            "onboarding_status",
            "account_provisioned_at",
            "has_biometric_link",
            "has_primary_emergency_contact",
            "qualification_count",
            "archived_at",
            "archived_by",
            "archived_by_name",
            "archive_reason",
            "created_at",
            "updated_at",
        ]

    def get_full_name(self, obj):
        return " ".join(part for part in [obj.first_name, obj.middle_name, obj.last_name] if part).strip()

    def get_reporting_to_name(self, obj):
        if not obj.reporting_to:
            return ""
        return f"{obj.reporting_to.first_name} {obj.reporting_to.last_name}".strip()

    def get_has_biometric_link(self, obj):
        from .onboarding import biometric_record_is_linked, get_employee_biometric_record

        return biometric_record_is_linked(get_employee_biometric_record(obj))

    def get_has_primary_emergency_contact(self, obj):
        return obj.emergency_contacts.filter(is_active=True, is_primary=True).exists()

    def get_qualification_count(self, obj):
        return obj.qualifications.filter(is_active=True).count()

    def validate_staff_category(self, value):
        normalized = normalize_staff_category(value)
        if value and not normalized:
            raise serializers.ValidationError("Unsupported staff category.")
        return normalized

    def validate_account_role_name(self, value):
        normalized = normalize_role_name(value)
        if normalized and normalized not in SUPPORTED_ROLE_NAMES:
            raise serializers.ValidationError("Unsupported role name.")
        return normalized or ""


class EmployeeArchiveSerializer(serializers.Serializer):
    archive_reason = serializers.CharField(required=False, allow_blank=True)


class EmployeeEmploymentProfileSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeEmploymentProfile
        fields = [
            "id",
            "employee",
            "employee_name",
            "kra_pin",
            "nhif_number",
            "nssf_number",
            "tsc_number",
            "bank_name",
            "bank_branch",
            "bank_account_name",
            "bank_account_number",
            "position_grade",
            "salary_scale",
            "probation_months",
            "confirmation_due_date",
            "employment_notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["employee_name", "created_at", "updated_at"]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()


class EmployeeQualificationSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeQualification
        fields = [
            "id",
            "employee",
            "employee_name",
            "qualification_type",
            "title",
            "institution",
            "field_of_study",
            "registration_number",
            "year_obtained",
            "issue_date",
            "expiry_date",
            "document_file",
            "is_primary",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["employee_name", "created_at"]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()


class EmergencyContactSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()

    class Meta:
        model = EmergencyContact
        fields = [
            "id",
            "employee",
            "employee_name",
            "name",
            "relationship",
            "phone_primary",
            "phone_alt",
            "address",
            "is_primary",
            "is_active",
        ]
        read_only_fields = ["employee_name"]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()


class EmployeeDocumentSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    uploaded_by_name = serializers.CharField(source="uploaded_by.username", read_only=True)

    class Meta:
        model = EmployeeDocument
        fields = [
            "id",
            "employee",
            "employee_name",
            "document_type",
            "file",
            "file_name",
            "description",
            "issue_date",
            "expiry_date",
            "uploaded_by",
            "uploaded_by_name",
            "uploaded_at",
            "is_active",
        ]
        read_only_fields = ["employee_name", "uploaded_by_name", "uploaded_at"]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()


class ShiftTemplateSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    position_title = serializers.CharField(source="position.title", read_only=True)

    class Meta:
        model = ShiftTemplate
        fields = [
            "id",
            "name",
            "code",
            "staff_category",
            "department",
            "department_name",
            "position",
            "position_title",
            "shift_start",
            "shift_end",
            "working_days",
            "break_duration_minutes",
            "grace_minutes",
            "requires_biometric_clock",
            "overtime_eligible",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["department_name", "position_title", "created_at"]


class AttendanceRecordSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    recorded_by_name = serializers.CharField(source="recorded_by.username", read_only=True)
    shift_template_name = serializers.CharField(source="shift_template.name", read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = [
            "id",
            "employee",
            "employee_name",
            "shift_template",
            "shift_template_name",
            "date",
            "scheduled_shift_start",
            "scheduled_shift_end",
            "clock_in",
            "clock_out",
            "status",
            "attendance_source",
            "alert_status",
            "reconciliation_status",
            "payroll_feed_status",
            "expected_check_in_deadline",
            "resolved_at",
            "hours_worked",
            "overtime_hours",
            "notes",
            "recorded_by",
            "recorded_by_name",
            "created_at",
            "is_active",
        ]
        read_only_fields = [
            "employee_name",
            "shift_template",
            "shift_template_name",
            "scheduled_shift_start",
            "scheduled_shift_end",
            "attendance_source",
            "alert_status",
            "reconciliation_status",
            "payroll_feed_status",
            "expected_check_in_deadline",
            "resolved_at",
            "recorded_by_name",
            "created_at",
            "hours_worked",
            "overtime_hours",
        ]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()


class WorkScheduleSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    department_name = serializers.CharField(source="department.name", read_only=True)
    shift_template_name = serializers.CharField(source="shift_template.name", read_only=True)

    class Meta:
        model = WorkSchedule
        fields = [
            "id",
            "employee",
            "employee_name",
            "department",
            "department_name",
            "shift_template",
            "shift_template_name",
            "assignment_priority",
            "staff_category_snapshot",
            "shift_start",
            "shift_end",
            "working_days",
            "break_duration",
            "effective_from",
            "effective_to",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["employee_name", "department_name", "created_at"]
        extra_kwargs = {
            "shift_start": {"required": False},
            "shift_end": {"required": False},
            "working_days": {"required": False},
            "break_duration": {"required": False},
        }

    def get_employee_name(self, obj):
        if not obj.employee:
            return ""
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()

    def validate(self, attrs):
        employee = attrs.get("employee", getattr(self.instance, "employee", None))
        department = attrs.get("department", getattr(self.instance, "department", None))
        shift_template = attrs.get("shift_template", getattr(self.instance, "shift_template", None))

        if not employee and not department:
            raise serializers.ValidationError("employee or department is required.")

        if shift_template:
            attrs.setdefault("shift_start", shift_template.shift_start)
            attrs.setdefault("shift_end", shift_template.shift_end)
            attrs.setdefault("working_days", shift_template.working_days)
            attrs.setdefault("break_duration", shift_template.break_duration_minutes)
            if not attrs.get("staff_category_snapshot"):
                if employee and employee.staff_category:
                    attrs["staff_category_snapshot"] = employee.staff_category
                elif shift_template.staff_category:
                    attrs["staff_category_snapshot"] = shift_template.staff_category
        else:
            shift_start = attrs.get("shift_start", getattr(self.instance, "shift_start", None))
            shift_end = attrs.get("shift_end", getattr(self.instance, "shift_end", None))
            if not shift_start or not shift_end:
                raise serializers.ValidationError("shift_start and shift_end are required when shift_template is not set.")

        if not attrs.get("staff_category_snapshot") and employee and employee.staff_category:
            attrs["staff_category_snapshot"] = employee.staff_category

        return attrs


class AbsenceAlertSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    shift_template_name = serializers.CharField(source="shift_template.name", read_only=True)
    notified_manager_name = serializers.SerializerMethodField()
    resolved_by_name = serializers.CharField(source="resolved_by.username", read_only=True)

    class Meta:
        model = AbsenceAlert
        fields = [
            "id",
            "employee",
            "employee_name",
            "attendance_record",
            "shift_template",
            "shift_template_name",
            "alert_date",
            "expected_shift_start",
            "grace_deadline",
            "status",
            "notified_manager",
            "notified_manager_name",
            "hr_copied",
            "resolved_by",
            "resolved_by_name",
            "resolved_at",
            "resolution_reason",
            "notes",
            "created_at",
            "is_active",
        ]
        read_only_fields = [
            "employee_name",
            "shift_template_name",
            "notified_manager_name",
            "resolved_by_name",
            "created_at",
        ]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()

    def get_notified_manager_name(self, obj):
        if not obj.notified_manager_id:
            return ""
        return f"{obj.notified_manager.first_name} {obj.notified_manager.last_name}".strip()


class AbsenceAlertResolveSerializer(serializers.Serializer):
    resolution_reason = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    attendance_status = serializers.ChoiceField(choices=AttendanceRecord.STATUS_CHOICES, required=False)


class AbsenceAlertEscalateSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True)


class AbsenceAlertEvaluateSerializer(serializers.Serializer):
    employee = serializers.IntegerField(required=True)
    date = serializers.DateField(required=True)
    triggered_at = serializers.DateTimeField(required=False)


class TeachingSubstituteAssignmentSerializer(serializers.ModelSerializer):
    absent_employee_name = serializers.SerializerMethodField()
    substitute_employee_name = serializers.SerializerMethodField()
    assigned_by_name = serializers.CharField(source="assigned_by.username", read_only=True)

    class Meta:
        model = TeachingSubstituteAssignment
        fields = [
            "id",
            "absent_employee",
            "absent_employee_name",
            "substitute_employee",
            "substitute_employee_name",
            "attendance_record",
            "assignment_date",
            "start_time",
            "end_time",
            "class_context",
            "reason",
            "assigned_by",
            "assigned_by_name",
            "notes",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["absent_employee_name", "substitute_employee_name", "assigned_by", "assigned_by_name", "created_at"]

    def get_absent_employee_name(self, obj):
        return f"{obj.absent_employee.first_name} {obj.absent_employee.last_name}".strip()

    def get_substitute_employee_name(self, obj):
        return f"{obj.substitute_employee.first_name} {obj.substitute_employee.last_name}".strip()

    def validate(self, attrs):
        absent_employee = attrs.get("absent_employee", getattr(self.instance, "absent_employee", None))
        substitute_employee = attrs.get("substitute_employee", getattr(self.instance, "substitute_employee", None))
        attendance_record = attrs.get("attendance_record", getattr(self.instance, "attendance_record", None))
        assignment_date = attrs.get("assignment_date", getattr(self.instance, "assignment_date", None))

        if absent_employee and absent_employee.staff_category != "TEACHING":
            raise serializers.ValidationError("Teaching substitute handling is only available for teaching staff.")
        if substitute_employee and substitute_employee.staff_category != "TEACHING":
            raise serializers.ValidationError("Substitute employee must be teaching staff.")
        if absent_employee and substitute_employee and absent_employee.id == substitute_employee.id:
            raise serializers.ValidationError("Substitute employee must be different from the absent employee.")
        if attendance_record:
            if absent_employee and attendance_record.employee_id != absent_employee.id:
                raise serializers.ValidationError("attendance_record must belong to the absent employee.")
            if assignment_date and attendance_record.date != assignment_date:
                raise serializers.ValidationError("assignment_date must match attendance_record.date.")
        return attrs


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = [
            "id",
            "name",
            "code",
            "is_paid",
            "requires_approval",
            "requires_document",
            "max_days_year",
            "notice_days",
            "color",
            "is_active",
        ]


class LeavePolicySerializer(serializers.ModelSerializer):
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)

    class Meta:
        model = LeavePolicy
        fields = [
            "id",
            "leave_type",
            "leave_type_name",
            "employment_type",
            "entitlement_days",
            "accrual_method",
            "carry_forward_max",
            "effective_from",
            "is_active",
        ]
        read_only_fields = ["leave_type_name"]


class LeaveBalanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)

    class Meta:
        model = LeaveBalance
        fields = [
            "id",
            "employee",
            "employee_name",
            "leave_type",
            "leave_type_name",
            "year",
            "opening_balance",
            "accrued",
            "used",
            "pending",
            "available",
            "updated_at",
        ]
        read_only_fields = ["employee_name", "leave_type_name", "updated_at"]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)
    approved_by_name = serializers.SerializerMethodField()
    current_approver_name = serializers.SerializerMethodField()
    manager_approved_by_name = serializers.SerializerMethodField()
    hr_approved_by_name = serializers.SerializerMethodField()
    return_reconciliation_status = serializers.SerializerMethodField()

    class Meta:
        model = LeaveRequest
        fields = [
            "id",
            "employee",
            "employee_name",
            "leave_type",
            "leave_type_name",
            "start_date",
            "end_date",
            "days_requested",
            "reason",
            "supporting_doc",
            "status",
            "approval_stage",
            "requires_dual_approval",
            "long_leave_threshold_days_snapshot",
            "return_reconciliation_required",
            "return_reconciliation_status",
            "current_approver",
            "current_approver_name",
            "manager_approved_by",
            "manager_approved_by_name",
            "manager_approved_at",
            "approved_by",
            "approved_by_name",
            "hr_approved_by",
            "hr_approved_by_name",
            "hr_approved_at",
            "approved_at",
            "review_notes",
            "rejection_reason",
            "submitted_at",
            "is_active",
        ]
        read_only_fields = [
            "employee_name",
            "leave_type_name",
            "approval_stage",
            "requires_dual_approval",
            "long_leave_threshold_days_snapshot",
            "return_reconciliation_required",
            "return_reconciliation_status",
            "current_approver_name",
            "manager_approved_by_name",
            "approved_by_name",
            "hr_approved_by_name",
            "manager_approved_at",
            "hr_approved_at",
            "approved_at",
            "review_notes",
            "submitted_at",
        ]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()

    def get_approved_by_name(self, obj):
        if not obj.approved_by:
            return ""
        return f"{obj.approved_by.first_name} {obj.approved_by.last_name}".strip()

    def get_manager_approved_by_name(self, obj):
        if not obj.manager_approved_by:
            return ""
        return f"{obj.manager_approved_by.first_name} {obj.manager_approved_by.last_name}".strip()

    def get_hr_approved_by_name(self, obj):
        if not obj.hr_approved_by:
            return ""
        return f"{obj.hr_approved_by.first_name} {obj.hr_approved_by.last_name}".strip()

    def get_current_approver_name(self, obj):
        if not obj.current_approver:
            return ""
        return f"{obj.current_approver.first_name} {obj.current_approver.last_name}".strip()

    def get_return_reconciliation_status(self, obj):
        try:
            reconciliation = obj.return_reconciliation
        except ReturnToWorkReconciliation.DoesNotExist:
            return ""
        return reconciliation.status


class LeaveRejectSerializer(serializers.Serializer):
    rejection_reason = serializers.CharField(required=True, allow_blank=False)


class ReturnToWorkReconciliationSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    leave_request_status = serializers.CharField(source="leave_request.status", read_only=True)
    completed_by_name = serializers.CharField(source="completed_by.username", read_only=True)

    class Meta:
        model = ReturnToWorkReconciliation
        fields = [
            "id",
            "employee",
            "employee_name",
            "leave_request",
            "leave_request_status",
            "attendance_record",
            "expected_return_date",
            "actual_return_date",
            "status",
            "extension_required",
            "attendance_correction_required",
            "payroll_hold_required",
            "substitute_closed",
            "completed_by",
            "completed_by_name",
            "completed_at",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "employee_name",
            "leave_request_status",
            "completed_by",
            "completed_by_name",
            "completed_at",
            "created_at",
            "updated_at",
        ]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()

    def validate(self, attrs):
        employee = attrs.get("employee", getattr(self.instance, "employee", None))
        leave_request = attrs.get("leave_request", getattr(self.instance, "leave_request", None))
        attendance_record = attrs.get("attendance_record", getattr(self.instance, "attendance_record", None))

        if employee and leave_request and leave_request.employee_id != employee.id:
            raise serializers.ValidationError("leave_request must belong to employee.")
        if employee and attendance_record and attendance_record.employee_id != employee.id:
            raise serializers.ValidationError("attendance_record must belong to employee.")
        return attrs


class ReturnToWorkCompleteSerializer(serializers.Serializer):
    actual_return_date = serializers.DateField(required=True)
    attendance_record = serializers.IntegerField(required=False)
    extension_required = serializers.BooleanField(required=False, default=False)
    attendance_correction_required = serializers.BooleanField(required=False, default=False)
    payroll_hold_required = serializers.BooleanField(required=False, default=False)
    substitute_closed = serializers.BooleanField(required=False, default=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class ReturnToWorkReopenSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True)


class SalaryComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalaryComponent
        fields = [
            "id",
            "structure",
            "component_type",
            "name",
            "amount_type",
            "amount",
            "is_taxable",
            "is_statutory",
            "is_active",
        ]


class SalaryStructureSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    components = SalaryComponentSerializer(many=True, read_only=True)

    class Meta:
        model = SalaryStructure
        fields = [
            "id",
            "employee",
            "employee_name",
            "basic_salary",
            "currency",
            "pay_frequency",
            "effective_from",
            "effective_to",
            "is_active",
            "created_at",
            "components",
        ]
        read_only_fields = ["employee_name", "created_at", "components"]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()


class StatutoryDeductionBandSerializer(serializers.ModelSerializer):
    class Meta:
        model = StatutoryDeductionBand
        fields = [
            "id",
            "rule",
            "lower_bound",
            "upper_bound",
            "employee_rate",
            "employer_rate",
            "fixed_amount",
            "additional_amount",
            "display_order",
            "is_active",
        ]


class StatutoryDeductionRuleSerializer(serializers.ModelSerializer):
    bands = StatutoryDeductionBandSerializer(many=True, read_only=True)

    class Meta:
        model = StatutoryDeductionRule
        fields = [
            "id",
            "code",
            "name",
            "calculation_method",
            "base_name",
            "employee_rate",
            "employer_rate",
            "fixed_amount",
            "minimum_amount",
            "maximum_amount",
            "relief_amount",
            "is_kenya_default",
            "is_mandatory",
            "effective_from",
            "effective_to",
            "priority",
            "configuration_notes",
            "is_active",
            "created_at",
            "updated_at",
            "bands",
        ]
        read_only_fields = ["created_at", "updated_at", "bands"]


class PayrollItemBreakdownSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollItemBreakdown
        fields = [
            "id",
            "payroll_item",
            "line_type",
            "code",
            "name",
            "base_amount",
            "rate",
            "amount",
            "display_order",
            "snapshot",
        ]


class PayrollDisbursementSerializer(serializers.ModelSerializer):
    disbursed_by_name = serializers.CharField(source="disbursed_by.username", read_only=True)

    class Meta:
        model = PayrollDisbursement
        fields = [
            "id",
            "payroll",
            "method",
            "status",
            "reference",
            "total_amount",
            "scheduled_date",
            "disbursed_at",
            "disbursed_by",
            "disbursed_by_name",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["disbursed_by_name", "created_at", "updated_at"]


class PayrollFinancePostingSerializer(serializers.ModelSerializer):
    posted_by_name = serializers.CharField(source="posted_by.username", read_only=True)

    class Meta:
        model = PayrollFinancePosting
        fields = [
            "id",
            "payroll",
            "posting_stage",
            "entry_key",
            "status",
            "journal_entry",
            "cashbook_entry",
            "posted_by",
            "posted_by_name",
            "posted_at",
            "vote_head_summary",
            "error_message",
            "created_at",
        ]
        read_only_fields = ["posted_by_name", "created_at"]


class PayrollItemSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    employee_id_str = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    position_name = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    pay_frequency = serializers.SerializerMethodField()
    components = serializers.SerializerMethodField()
    breakdown_rows = PayrollItemBreakdownSerializer(many=True, read_only=True)
    payroll_month = serializers.IntegerField(source="payroll.month", read_only=True)
    payroll_year = serializers.IntegerField(source="payroll.year", read_only=True)
    payroll_payment_date = serializers.DateField(source="payroll.payment_date", read_only=True)

    class Meta:
        model = PayrollItem
        fields = [
            "id",
            "payroll",
            "payroll_month",
            "payroll_year",
            "payroll_payment_date",
            "employee",
            "employee_name",
            "employee_id_str",
            "department_name",
            "position_name",
            "currency",
            "pay_frequency",
            "basic_salary",
            "total_allowances",
            "attendance_deduction_total",
            "statutory_deduction_total",
            "other_deduction_total",
            "employer_statutory_total",
            "total_deductions",
            "gross_salary",
            "net_salary",
            "net_payable",
            "days_worked",
            "overtime_hours",
            "posting_bucket",
            "is_blocked",
            "block_reason",
            "calculation_snapshot",
            "components",
            "breakdown_rows",
            "pdf_file",
            "sent_at",
            "is_active",
        ]
        read_only_fields = [
            "employee_name",
            "employee_id_str",
            "department_name",
            "position_name",
            "currency",
            "pay_frequency",
            "basic_salary",
            "total_allowances",
            "attendance_deduction_total",
            "statutory_deduction_total",
            "other_deduction_total",
            "employer_statutory_total",
            "total_deductions",
            "gross_salary",
            "net_salary",
            "net_payable",
            "days_worked",
            "overtime_hours",
            "posting_bucket",
            "is_blocked",
            "block_reason",
            "calculation_snapshot",
            "components",
            "breakdown_rows",
            "payroll_month",
            "payroll_year",
            "payroll_payment_date",
            "pdf_file",
            "sent_at",
        ]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()

    def get_employee_id_str(self, obj):
        return obj.employee.employee_id

    def get_department_name(self, obj):
        if obj.employee.department:
            return obj.employee.department.name
        return ""

    def get_position_name(self, obj):
        if obj.employee.position:
            return obj.employee.position.title
        return ""

    def get_currency(self, obj):
        snapshot_currency = obj.calculation_snapshot.get("salary_structure", {}).get("currency")
        if snapshot_currency:
            return snapshot_currency
        structure = obj.employee.salary_structures.filter(is_active=True).order_by("-effective_from").first()
        return structure.currency if structure else "KES"

    def get_pay_frequency(self, obj):
        snapshot_frequency = obj.calculation_snapshot.get("salary_structure", {}).get("pay_frequency")
        if snapshot_frequency:
            return snapshot_frequency
        structure = obj.employee.salary_structures.filter(is_active=True).order_by("-effective_from").first()
        return structure.pay_frequency if structure else "Monthly"

    def get_components(self, obj):
        breakdown_rows = list(obj.breakdown_rows.all())
        if breakdown_rows:
            components = []
            for row in breakdown_rows:
                if row.line_type == "STATUTORY_EMPLOYER":
                    continue
                component_type = "Allowance" if row.line_type == "ALLOWANCE" else "Deduction"
                amount_type = row.snapshot.get("amount_type")
                if not amount_type:
                    amount_type = "Percentage" if Decimal(str(row.rate or 0)) > Decimal("0.00") else "Fixed"
                components.append(
                    {
                        "name": row.name,
                        "component_type": component_type,
                        "amount_type": amount_type,
                        "amount": float(row.amount),
                        "is_taxable": bool(row.snapshot.get("is_taxable", row.code in {"PAYE", "SHIF", "NSSF", "HOUSING_LEVY"})),
                    }
                )
            return components

        structure = obj.employee.salary_structures.filter(is_active=True).order_by("-effective_from").first()
        if not structure:
            return []
        return [
            {
                "name": c.name,
                "component_type": c.component_type,
                "amount_type": c.amount_type,
                "amount": float(c.amount if c.amount_type == "Fixed" else c.amount * float(obj.basic_salary) / 100),
                "is_taxable": c.is_taxable,
            }
            for c in structure.components.filter(is_active=True)
        ]


class PayrollBatchSerializer(serializers.ModelSerializer):
    items = PayrollItemSerializer(many=True, read_only=True)
    disbursements = PayrollDisbursementSerializer(many=True, read_only=True)
    finance_postings = PayrollFinancePostingSerializer(many=True, read_only=True)
    bucket_totals = serializers.SerializerMethodField()
    statutory_totals = serializers.SerializerMethodField()

    class Meta:
        model = PayrollBatch
        fields = [
            "id",
            "month",
            "year",
            "status",
            "total_gross",
            "total_deductions",
            "total_net",
            "processed_by",
            "approved_by",
            "approved_at",
            "finance_approved_by",
            "finance_approved_at",
            "disbursed_by",
            "disbursed_at",
            "posted_by",
            "posted_at",
            "payment_date",
            "exception_count",
            "blocked_item_count",
            "workforce_snapshot",
            "statutory_snapshot",
            "approval_notes",
            "bucket_totals",
            "statutory_totals",
            "created_at",
            "is_active",
            "items",
            "disbursements",
            "finance_postings",
        ]
        read_only_fields = [
            "total_gross",
            "total_deductions",
            "total_net",
            "processed_by",
            "approved_by",
            "approved_at",
            "finance_approved_by",
            "finance_approved_at",
            "disbursed_by",
            "disbursed_at",
            "posted_by",
            "posted_at",
            "exception_count",
            "blocked_item_count",
            "workforce_snapshot",
            "statutory_snapshot",
            "bucket_totals",
            "statutory_totals",
            "created_at",
            "items",
            "disbursements",
            "finance_postings",
        ]

    def get_bucket_totals(self, obj):
        totals = {}
        for item in obj.items.all():
            if not item.posting_bucket:
                continue
            bucket_total = item.net_payable + item.statutory_deduction_total + item.employer_statutory_total
            totals[item.posting_bucket] = str(Decimal(totals.get(item.posting_bucket, "0.00")) + bucket_total)
        return totals

    def get_statutory_totals(self, obj):
        employee_total = Decimal("0.00")
        employer_total = Decimal("0.00")
        for item in obj.items.all():
            employee_total += item.statutory_deduction_total
            employer_total += item.employer_statutory_total
        return {
            "employee_total": str(employee_total),
            "employer_total": str(employer_total),
            "liability_total": str(employee_total + employer_total),
        }


class JobPostingSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    position_title = serializers.CharField(source="position.title", read_only=True)
    posted_by_name = serializers.CharField(source="posted_by.username", read_only=True)

    class Meta:
        model = JobPosting
        fields = [
            "id",
            "position",
            "position_title",
            "department",
            "department_name",
            "title",
            "description",
            "requirements",
            "responsibilities",
            "employment_type",
            "salary_min",
            "salary_max",
            "deadline",
            "status",
            "posted_by",
            "posted_by_name",
            "posted_at",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["position_title", "department_name", "posted_by", "posted_by_name", "posted_at", "created_at"]


class JobApplicationSerializer(serializers.ModelSerializer):
    applicant_name = serializers.SerializerMethodField()
    job_title = serializers.CharField(source="job_posting.title", read_only=True)

    class Meta:
        model = JobApplication
        fields = [
            "id",
            "job_posting",
            "job_title",
            "first_name",
            "last_name",
            "applicant_name",
            "email",
            "phone",
            "resume",
            "cover_letter",
            "status",
            "rating",
            "notes",
            "applied_at",
            "is_active",
        ]
        read_only_fields = ["job_title", "applicant_name", "applied_at"]

    def get_applicant_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()


class InterviewSerializer(serializers.ModelSerializer):
    applicant_name = serializers.SerializerMethodField()
    job_title = serializers.CharField(source="application.job_posting.title", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = Interview
        fields = [
            "id",
            "application",
            "applicant_name",
            "job_title",
            "interview_date",
            "interview_type",
            "location",
            "interviewers",
            "status",
            "feedback",
            "score",
            "created_by",
            "created_by_name",
            "created_at",
            "is_active",
        ]
        read_only_fields = ["applicant_name", "job_title", "created_by", "created_by_name", "created_at"]

    def get_applicant_name(self, obj):
        return f"{obj.application.first_name} {obj.application.last_name}".strip()


class OnboardingTaskSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    assigned_to_name = serializers.CharField(source="assigned_to.username", read_only=True)

    class Meta:
        model = OnboardingTask
        fields = [
            "id",
            "employee",
            "employee_name",
            "task_code",
            "task",
            "assigned_to",
            "assigned_to_name",
            "due_date",
            "status",
            "is_required",
            "blocks_account_provisioning",
            "completed_at",
            "notes",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["employee_name", "assigned_to_name", "completed_at", "created_at"]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()


class BiometricLinkSerializer(serializers.Serializer):
    fingerprint_id = serializers.CharField(required=False, allow_blank=True, max_length=100)
    card_no = serializers.CharField(required=False, allow_blank=True, max_length=100)
    dahua_user_id = serializers.CharField(required=False, allow_blank=True, max_length=100)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if not any(
            [
                (attrs.get("fingerprint_id") or "").strip(),
                (attrs.get("card_no") or "").strip(),
                (attrs.get("dahua_user_id") or "").strip(),
            ]
        ):
            raise serializers.ValidationError("Provide at least one biometric identifier.")
        return attrs


class ProvisionAccountSerializer(serializers.Serializer):
    role_name = serializers.CharField(required=False, allow_blank=True, max_length=50)
    username = serializers.CharField(required=False, allow_blank=True, max_length=150)
    send_welcome_email = serializers.BooleanField(required=False, default=True)

    def validate_role_name(self, value):
        normalized = normalize_role_name(value)
        if normalized and normalized not in SUPPORTED_ROLE_NAMES:
            raise serializers.ValidationError("Unsupported role name.")
        return normalized or ""

    def validate_username(self, value):
        return str(value or "").strip()


class PerformanceGoalSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()

    class Meta:
        model = PerformanceGoal
        fields = [
            "id",
            "employee",
            "employee_name",
            "title",
            "description",
            "target_date",
            "status",
            "weight",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["employee_name", "created_at"]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()


class PerformanceReviewSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    reviewer_name = serializers.SerializerMethodField()

    class Meta:
        model = PerformanceReview
        fields = [
            "id",
            "employee",
            "employee_name",
            "reviewer",
            "reviewer_name",
            "review_period",
            "overall_rating",
            "strengths",
            "areas_improvement",
            "status",
            "reviewed_at",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["employee_name", "reviewer_name", "reviewed_at", "created_at"]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()

    def get_reviewer_name(self, obj):
        if not obj.reviewer:
            return ""
        return f"{obj.reviewer.first_name} {obj.reviewer.last_name}".strip()


class TrainingProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingProgram
        fields = [
            "id",
            "title",
            "description",
            "trainer",
            "start_date",
            "end_date",
            "capacity",
            "cost",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class TrainingEnrollmentSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    program_title = serializers.CharField(source="program.title", read_only=True)

    class Meta:
        model = TrainingEnrollment
        fields = [
            "id",
            "program",
            "program_title",
            "employee",
            "employee_name",
            "status",
            "completion_date",
            "certificate",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["employee_name", "program_title", "created_at"]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()


class StaffLifecycleEventSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    recorded_by_name = serializers.CharField(source="recorded_by.username", read_only=True)

    class Meta:
        model = StaffLifecycleEvent
        fields = [
            "id",
            "employee",
            "employee_name",
            "event_group",
            "event_type",
            "title",
            "summary",
            "status_snapshot",
            "effective_date",
            "occurred_at",
            "recorded_by",
            "recorded_by_name",
            "source_model",
            "source_id",
            "before_snapshot",
            "after_snapshot",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()


class StaffCareerActionSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    parent_action_type = serializers.CharField(source="parent_action.action_type", read_only=True)
    from_department_name = serializers.CharField(source="from_department.name", read_only=True)
    from_position_ref_title = serializers.CharField(source="from_position_ref.title", read_only=True)
    to_department_name = serializers.CharField(source="to_department.name", read_only=True)
    to_position_ref_title = serializers.CharField(source="to_position_ref.title", read_only=True)
    requested_by_name = serializers.CharField(source="requested_by.username", read_only=True)
    applied_by_name = serializers.CharField(source="applied_by.username", read_only=True)

    class Meta:
        model = StaffCareerAction
        fields = [
            "id",
            "employee",
            "employee_name",
            "parent_action",
            "parent_action_type",
            "action_type",
            "from_department",
            "from_department_name",
            "from_position_ref",
            "from_position_ref_title",
            "from_position_title",
            "to_department",
            "to_department_name",
            "to_position_ref",
            "to_position_ref_title",
            "to_position_title",
            "target_position_grade",
            "target_salary_scale",
            "reason",
            "effective_date",
            "status",
            "previous_assignment_snapshot",
            "notes",
            "requested_by",
            "requested_by_name",
            "applied_by",
            "applied_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "employee_name",
            "parent_action",
            "parent_action_type",
            "from_department_name",
            "from_position_ref_title",
            "to_department_name",
            "to_position_ref_title",
            "previous_assignment_snapshot",
            "requested_by",
            "requested_by_name",
            "applied_by",
            "applied_by_name",
            "created_at",
            "updated_at",
        ]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        employee = attrs.get("employee", getattr(instance, "employee", None))
        action_type = attrs.get("action_type", getattr(instance, "action_type", ""))
        to_department = attrs.get("to_department", getattr(instance, "to_department", None))
        to_position_ref = attrs.get("to_position_ref", getattr(instance, "to_position_ref", None))
        status_value = attrs.get("status", getattr(instance, "status", "DRAFT"))

        if action_type == "ACTING_APPOINTMENT_END":
            raise serializers.ValidationError({"action_type": "Use the end-acting action endpoint."})

        if status_value == "EFFECTIVE":
            raise serializers.ValidationError({"status": "Use the apply action endpoint to make a career action effective."})

        if action_type in {"PROMOTION", "DEMOTION"} and not to_position_ref:
            raise serializers.ValidationError({"to_position_ref": "Target position is required for promotion or demotion."})

        if action_type == "ACTING_APPOINTMENT" and not (to_department or to_position_ref):
            raise serializers.ValidationError(
                {"to_department": "Provide a target department or position for the acting appointment."}
            )

        if employee and attrs.get("from_department") is None and not getattr(instance, "from_department_id", None):
            attrs["from_department"] = employee.department

        if employee and attrs.get("from_position_ref") is None and not getattr(instance, "from_position_ref_id", None):
            attrs["from_position_ref"] = employee.position

        if employee and not attrs.get("from_position_title") and not getattr(instance, "from_position_title", "") and employee.position:
            attrs["from_position_title"] = employee.position.title

        if to_position_ref and not attrs.get("to_position_title"):
            attrs["to_position_title"] = to_position_ref.title

        if to_position_ref and to_department and to_position_ref.department_id and to_department.id != to_position_ref.department_id:
            raise serializers.ValidationError(
                {"to_position_ref": "Target position must belong to the target department."}
            )

        if to_position_ref and not to_department and to_position_ref.department_id:
            attrs["to_department"] = to_position_ref.department

        return attrs


class StaffCareerActionEndActingSerializer(serializers.Serializer):
    effective_date = serializers.DateField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class DisciplinaryCaseSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    opened_by_name = serializers.CharField(source="opened_by.username", read_only=True)
    closed_by_name = serializers.CharField(source="closed_by.username", read_only=True)

    class Meta:
        model = DisciplinaryCase
        fields = [
            "id",
            "employee",
            "employee_name",
            "case_number",
            "category",
            "opened_on",
            "incident_date",
            "summary",
            "details",
            "status",
            "outcome",
            "effective_date",
            "opened_by",
            "opened_by_name",
            "closed_by",
            "closed_by_name",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "employee_name",
            "case_number",
            "status",
            "outcome",
            "effective_date",
            "opened_by",
            "opened_by_name",
            "closed_by",
            "closed_by_name",
            "created_at",
            "updated_at",
        ]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()


class DisciplinaryCaseCloseSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(choices=DisciplinaryCase.OUTCOME_CHOICES)
    effective_date = serializers.DateField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class ExitCaseSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    requested_by_name = serializers.CharField(source="requested_by.username", read_only=True)
    completed_by_name = serializers.CharField(source="completed_by.username", read_only=True)

    class Meta:
        model = ExitCase
        fields = [
            "id",
            "employee",
            "employee_name",
            "exit_type",
            "notice_date",
            "last_working_date",
            "effective_date",
            "reason",
            "status",
            "requested_by",
            "requested_by_name",
            "completed_by",
            "completed_by_name",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "employee_name",
            "status",
            "requested_by",
            "requested_by_name",
            "completed_by",
            "completed_by_name",
            "created_at",
            "updated_at",
        ]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()


class ExitClearanceItemSerializer(serializers.ModelSerializer):
    completed_by_name = serializers.CharField(source="completed_by.username", read_only=True)
    exit_case_status = serializers.CharField(source="exit_case.status", read_only=True)

    class Meta:
        model = ExitClearanceItem
        fields = [
            "id",
            "exit_case",
            "exit_case_status",
            "label",
            "department_name",
            "status",
            "completed_at",
            "completed_by",
            "completed_by_name",
            "notes",
            "display_order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "exit_case_status",
            "completed_at",
            "completed_by",
            "completed_by_name",
            "created_at",
            "updated_at",
        ]


class StaffTransferSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    from_department_name = serializers.SerializerMethodField()
    to_department_name = serializers.SerializerMethodField()
    to_position_ref_title = serializers.CharField(source="to_position_ref.title", read_only=True)

    class Meta:
        model = StaffTransfer
        fields = [
            'id', 'employee', 'employee_name', 'transfer_type',
            'from_department', 'from_department_name', 'from_position',
            'to_department', 'to_department_name', 'to_position',
            'to_position_ref', 'to_position_ref_title',
            'destination_school', 'reason', 'effective_date', 'status',
            'handover_completed', 'clearance_completed',
            'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'created_at',
            'updated_at',
            'employee_name',
            'from_department_name',
            'to_department_name',
            'to_position_ref_title',
        ]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip()

    def get_from_department_name(self, obj):
        return obj.from_department.name if obj.from_department else ''

    def get_to_department_name(self, obj):
        return obj.to_department.name if obj.to_department else ''

    def validate(self, attrs):
        employee = attrs.get("employee") or getattr(self.instance, "employee", None)
        to_position_ref = attrs.get("to_position_ref") or getattr(self.instance, "to_position_ref", None)
        to_department = attrs.get("to_department", getattr(self.instance, "to_department", None))

        if employee and attrs.get("from_department") is None and not getattr(self.instance, "from_department_id", None):
            attrs["from_department"] = employee.department

        if employee and not attrs.get("from_position") and not getattr(self.instance, "from_position", "") and employee.position:
            attrs["from_position"] = employee.position.title

        if to_position_ref and not attrs.get("to_position"):
            attrs["to_position"] = to_position_ref.title

        if to_position_ref and to_department and to_position_ref.department_id and to_department.id != to_position_ref.department_id:
            raise serializers.ValidationError({"to_position_ref": "Target position must belong to the target department."})

        if to_position_ref and not to_department and to_position_ref.department_id:
            attrs["to_department"] = to_position_ref.department

        return attrs
