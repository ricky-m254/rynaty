from django.db import models
from django.utils import timezone


class Staff(models.Model):
    """
    Unmanaged wrapper for school.Staff (pilot migration).
    """
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    employee_id = models.CharField(max_length=50)
    role = models.CharField(max_length=50)
    phone = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "school_staff"


class Department(models.Model):
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=20, unique=True)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children")
    head = models.ForeignKey("Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="headed_departments")
    school_department = models.OneToOneField(
        "school.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hr_department_profile",
    )
    description = models.TextField(blank=True)
    budget = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Position(models.Model):
    title = models.CharField(max_length=120)
    department = models.ForeignKey("Department", on_delete=models.SET_NULL, null=True, blank=True, related_name="hr_positions")
    description = models.TextField(blank=True)
    responsibilities = models.TextField(blank=True)
    qualifications = models.TextField(blank=True)
    experience_years = models.PositiveIntegerField(default=0)
    salary_min = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    headcount = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class Employee(models.Model):
    GENDER_CHOICES = [("Male", "Male"), ("Female", "Female"), ("Other", "Other")]
    STAFF_CATEGORY_CHOICES = [
        ("TEACHING", "Teaching"),
        ("ADMIN", "Admin"),
        ("SUPPORT", "Support"),
        ("OPERATIONS", "Operations"),
        ("HOSTEL", "Hostel"),
        ("SECURITY", "Security"),
        ("KITCHEN", "Kitchen"),
        ("HEALTH", "Health"),
    ]
    EMPLOYMENT_TYPE_CHOICES = [
        ("Full-time", "Full-time"),
        ("Part-time", "Part-time"),
        ("Contract", "Contract"),
        ("Temporary", "Temporary"),
        ("Intern", "Intern"),
    ]
    STATUS_CHOICES = [
        ("Active", "Active"),
        ("Acting", "Acting"),
        ("On Leave", "On Leave"),
        ("Suspended", "Suspended"),
        ("Terminated", "Terminated"),
        ("Retired", "Retired"),
        ("Archived", "Archived"),
    ]
    EXIT_REASON_CHOICES = [
        ("Resignation", "Resignation"),
        ("Termination", "Termination"),
        ("Retirement", "Retirement"),
        ("Contract End", "Contract End"),
    ]
    MARITAL_STATUS_CHOICES = [
        ("Single", "Single"),
        ("Married", "Married"),
        ("Divorced", "Divorced"),
        ("Widowed", "Widowed"),
    ]
    ONBOARDING_STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("IN_PROGRESS", "In Progress"),
        ("READY_FOR_PROVISIONING", "Ready for Provisioning"),
        ("PROVISIONED", "Provisioned"),
    ]

    user = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)
    employee_id = models.CharField(max_length=50, unique=True, blank=True)
    staff_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, default="Other")
    nationality = models.CharField(max_length=100, blank=True)
    national_id = models.CharField(max_length=100, blank=True)
    personal_email = models.EmailField(blank=True)
    work_email = models.EmailField(blank=True)
    marital_status = models.CharField(max_length=20, choices=MARITAL_STATUS_CHOICES, default="Single")
    photo = models.ImageField(upload_to="hr/employees/photos/", null=True, blank=True)
    blood_group = models.CharField(max_length=10, blank=True)
    medical_conditions = models.TextField(blank=True)

    department = models.ForeignKey("Department", on_delete=models.SET_NULL, null=True, blank=True, related_name="hr_employees")
    position = models.ForeignKey(Position, on_delete=models.SET_NULL, null=True, blank=True, related_name="employees")
    staff_category = models.CharField(max_length=20, choices=STAFF_CATEGORY_CHOICES, blank=True, default="")
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES, default="Full-time")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Active")
    onboarding_status = models.CharField(max_length=30, choices=ONBOARDING_STATUS_CHOICES, default="PENDING")
    account_role_name = models.CharField(max_length=50, blank=True)
    account_provisioned_at = models.DateTimeField(null=True, blank=True)
    join_date = models.DateField(null=True, blank=True)
    probation_end = models.DateField(null=True, blank=True)
    confirmation_date = models.DateField(null=True, blank=True)
    contract_start = models.DateField(null=True, blank=True)
    contract_end = models.DateField(null=True, blank=True)
    reporting_to = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="reportees")
    work_location = models.CharField(max_length=120, blank=True)
    notice_period_days = models.PositiveIntegerField(default=30)
    exit_date = models.DateField(null=True, blank=True)
    exit_reason = models.CharField(max_length=20, choices=EXIT_REASON_CHOICES, blank=True)
    exit_notes = models.TextField(blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="archived_hr_employees",
    )
    archive_reason = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["employee_id", "first_name", "last_name"]

    def __str__(self):
        identifier = self.staff_id or self.employee_id
        return f"{identifier} - {self.first_name} {self.last_name}".strip()


class EmployeeEmploymentProfile(models.Model):
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name="employment_profile")
    kra_pin = models.CharField(max_length=100, blank=True)
    nhif_number = models.CharField(max_length=100, blank=True)
    nssf_number = models.CharField(max_length=100, blank=True)
    tsc_number = models.CharField(max_length=100, blank=True)
    bank_name = models.CharField(max_length=180, blank=True)
    bank_branch = models.CharField(max_length=180, blank=True)
    bank_account_name = models.CharField(max_length=180, blank=True)
    bank_account_number = models.CharField(max_length=100, blank=True)
    position_grade = models.CharField(max_length=50, blank=True)
    salary_scale = models.CharField(max_length=50, blank=True)
    probation_months = models.PositiveIntegerField(null=True, blank=True)
    confirmation_due_date = models.DateField(null=True, blank=True)
    employment_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["employee__employee_id"]

    def __str__(self):
        return f"{self.employee.staff_id or self.employee.employee_id} employment profile"


class EmployeeQualification(models.Model):
    QUALIFICATION_TYPE_CHOICES = [
        ("Degree", "Degree"),
        ("Diploma", "Diploma"),
        ("Certificate", "Certificate"),
        ("License", "License"),
        ("Professional", "Professional"),
        ("Registration", "Registration"),
        ("Other", "Other"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="qualifications")
    qualification_type = models.CharField(max_length=20, choices=QUALIFICATION_TYPE_CHOICES, default="Certificate")
    title = models.CharField(max_length=180)
    institution = models.CharField(max_length=180, blank=True)
    field_of_study = models.CharField(max_length=180, blank=True)
    registration_number = models.CharField(max_length=120, blank=True)
    year_obtained = models.PositiveIntegerField(null=True, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    document_file = models.FileField(upload_to="hr/employees/qualifications/", null=True, blank=True)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "-year_obtained", "-id"]

    def __str__(self):
        return f"{self.employee.staff_id or self.employee.employee_id} {self.title}"


class EmergencyContact(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="emergency_contacts")
    name = models.CharField(max_length=120)
    relationship = models.CharField(max_length=60)
    phone_primary = models.CharField(max_length=30)
    phone_alt = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-is_primary", "name"]

    def __str__(self):
        return f"{self.name} ({self.relationship})"


class EmployeeDocument(models.Model):
    DOCUMENT_TYPE_CHOICES = [
        ("Resume", "Resume"),
        ("Certificate", "Certificate"),
        ("License", "License"),
        ("ID", "ID"),
        ("Contract", "Contract"),
        ("Medical", "Medical"),
        ("Other", "Other"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES, default="Other")
    file = models.FileField(upload_to="hr/employees/documents/")
    file_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    uploaded_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hr_uploaded_documents",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.employee.employee_id} {self.document_type}"


class ShiftTemplate(models.Model):
    staff_category = models.CharField(max_length=20, choices=Employee.STAFF_CATEGORY_CHOICES, blank=True, default="")
    department = models.ForeignKey("Department", on_delete=models.SET_NULL, null=True, blank=True, related_name="shift_templates")
    position = models.ForeignKey("Position", on_delete=models.SET_NULL, null=True, blank=True, related_name="shift_templates")
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=40, unique=True)
    shift_start = models.TimeField()
    shift_end = models.TimeField()
    working_days = models.JSONField(default=list)
    break_duration_minutes = models.PositiveIntegerField(default=60)
    grace_minutes = models.PositiveIntegerField(default=15)
    requires_biometric_clock = models.BooleanField(default=False)
    overtime_eligible = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class WorkSchedule(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name="schedules")
    department = models.ForeignKey("Department", on_delete=models.SET_NULL, null=True, blank=True, related_name="hr_schedules")
    shift_template = models.ForeignKey(
        "ShiftTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="schedule_assignments",
    )
    assignment_priority = models.PositiveIntegerField(default=100)
    staff_category_snapshot = models.CharField(max_length=20, choices=Employee.STAFF_CATEGORY_CHOICES, blank=True, default="")
    shift_start = models.TimeField()
    shift_end = models.TimeField()
    working_days = models.JSONField(default=list)
    break_duration = models.PositiveIntegerField(default=60)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AttendanceRecord(models.Model):
    STATUS_CHOICES = [
        ("Present", "Present"),
        ("Absent", "Absent"),
        ("Late", "Late"),
        ("Half-Day", "Half-Day"),
        ("On Leave", "On Leave"),
    ]
    ATTENDANCE_SOURCE_CHOICES = [
        ("MANUAL", "Manual"),
        ("BIOMETRIC", "Biometric"),
        ("BULK", "Bulk"),
        ("RECONCILED", "Reconciled"),
    ]
    ALERT_STATUS_CHOICES = [
        ("NONE", "None"),
        ("OPEN", "Open"),
        ("AUTO_RESOLVED", "Auto Resolved"),
        ("MANUALLY_RESOLVED", "Manually Resolved"),
    ]
    RECONCILIATION_STATUS_CHOICES = [
        ("NOT_REQUIRED", "Not Required"),
        ("PENDING", "Pending"),
        ("COMPLETED", "Completed"),
    ]
    PAYROLL_FEED_STATUS_CHOICES = [
        ("READY", "Ready"),
        ("BLOCKED_ALERT", "Blocked - Alert"),
        ("BLOCKED_RECONCILIATION", "Blocked - Reconciliation"),
        ("BLOCKED_LEAVE", "Blocked - Leave"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="attendance_records")
    shift_template = models.ForeignKey("ShiftTemplate", on_delete=models.SET_NULL, null=True, blank=True, related_name="attendance_records")
    date = models.DateField()
    scheduled_shift_start = models.TimeField(null=True, blank=True)
    scheduled_shift_end = models.TimeField(null=True, blank=True)
    clock_in = models.TimeField(null=True, blank=True)
    clock_out = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Present")
    attendance_source = models.CharField(max_length=20, choices=ATTENDANCE_SOURCE_CHOICES, default="MANUAL")
    alert_status = models.CharField(max_length=20, choices=ALERT_STATUS_CHOICES, default="NONE")
    reconciliation_status = models.CharField(max_length=20, choices=RECONCILIATION_STATUS_CHOICES, default="NOT_REQUIRED")
    payroll_feed_status = models.CharField(max_length=30, choices=PAYROLL_FEED_STATUS_CHOICES, default="READY")
    expected_check_in_deadline = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    hours_worked = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    overtime_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hr_attendance_records",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("employee", "date")
        ordering = ["-date", "-id"]


class AbsenceAlert(models.Model):
    STATUS_CHOICES = [
        ("OPEN", "Open"),
        ("AUTO_RESOLVED", "Auto Resolved"),
        ("ESCALATED", "Escalated"),
        ("MANUALLY_RESOLVED", "Manually Resolved"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="absence_alerts")
    attendance_record = models.ForeignKey(AttendanceRecord, on_delete=models.CASCADE, related_name="absence_alerts")
    shift_template = models.ForeignKey("ShiftTemplate", on_delete=models.SET_NULL, null=True, blank=True, related_name="absence_alerts")
    notified_manager = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_absence_alerts",
    )
    resolved_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_absence_alerts",
    )
    alert_date = models.DateField()
    expected_shift_start = models.TimeField(null=True, blank=True)
    grace_deadline = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="OPEN")
    hr_copied = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-alert_date", "-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "attendance_record"],
                condition=models.Q(is_active=True),
                name="uniq_active_absence_alert_per_attendance",
            )
        ]

    def __str__(self):
        return f"{self.employee.employee_id} {self.alert_date} {self.status}"


class TeachingSubstituteAssignment(models.Model):
    absent_employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="teaching_substitute_absences",
    )
    substitute_employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="teaching_substitute_coverages",
    )
    attendance_record = models.ForeignKey(
        AttendanceRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teaching_substitute_assignments",
    )
    assignment_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    class_context = models.CharField(max_length=255, blank=True)
    reason = models.TextField(blank=True)
    assigned_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teaching_substitute_assignments",
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-assignment_date", "-created_at", "-id"]

    def __str__(self):
        return f"{self.absent_employee.employee_id} -> {self.substitute_employee.employee_id} {self.assignment_date}"


class LeaveType(models.Model):
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=30, unique=True)
    is_paid = models.BooleanField(default=True)
    requires_approval = models.BooleanField(default=True)
    requires_document = models.BooleanField(default=False)
    max_days_year = models.PositiveIntegerField(null=True, blank=True)
    notice_days = models.PositiveIntegerField(default=0)
    color = models.CharField(max_length=7, default="#0EA5E9")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class LeavePolicy(models.Model):
    ACCRUAL_METHOD_CHOICES = [
        ("Annual", "Annual"),
        ("Monthly", "Monthly"),
        ("Per-Payroll", "Per-Payroll"),
    ]
    EMPLOYMENT_TYPE_CHOICES = [
        ("Full-time", "Full-time"),
        ("Part-time", "Part-time"),
        ("Contract", "Contract"),
    ]

    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, related_name="policies")
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES, blank=True)
    entitlement_days = models.DecimalField(max_digits=7, decimal_places=2, default=0.00)
    accrual_method = models.CharField(max_length=20, choices=ACCRUAL_METHOD_CHOICES, default="Annual")
    carry_forward_max = models.PositiveIntegerField(default=0)
    effective_from = models.DateField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["leave_type__name", "employment_type", "-effective_from"]

    def __str__(self):
        return f"{self.leave_type.code} {self.employment_type or 'All'}"


class LeaveBalance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leave_balances")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, related_name="balances")
    year = models.PositiveIntegerField()
    opening_balance = models.DecimalField(max_digits=7, decimal_places=2, default=0.00)
    accrued = models.DecimalField(max_digits=7, decimal_places=2, default=0.00)
    used = models.DecimalField(max_digits=7, decimal_places=2, default=0.00)
    pending = models.DecimalField(max_digits=7, decimal_places=2, default=0.00)
    available = models.DecimalField(max_digits=7, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("employee", "leave_type", "year")
        ordering = ["-year", "leave_type__name"]

    def __str__(self):
        return f"{self.employee.employee_id} {self.leave_type.code} {self.year}"


class LeaveRequest(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Approved", "Approved"),
        ("Needs Info", "Clarification Requested"),
        ("Rejected", "Rejected"),
        ("Cancelled", "Cancelled"),
    ]
    APPROVAL_STAGE_CHOICES = [
        ("PENDING_MANAGER", "Pending Manager"),
        ("PENDING_HR", "Pending HR"),
        ("NEEDS_INFO", "Clarification Requested"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("CANCELLED", "Cancelled"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leave_requests")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, related_name="requests")
    start_date = models.DateField()
    end_date = models.DateField()
    days_requested = models.DecimalField(max_digits=7, decimal_places=2, default=0.00)
    reason = models.TextField(blank=True)
    supporting_doc = models.FileField(upload_to="hr/leave/supporting_docs/", null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    current_approver = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leave_pending_approvals",
    )
    approved_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leave_approved_requests",
    )
    approval_stage = models.CharField(max_length=20, choices=APPROVAL_STAGE_CHOICES, default="PENDING_HR")
    requires_dual_approval = models.BooleanField(default=False)
    manager_approved_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leave_manager_approved_requests",
    )
    manager_approved_at = models.DateTimeField(null=True, blank=True)
    hr_approved_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leave_hr_approved_requests",
    )
    hr_approved_at = models.DateTimeField(null=True, blank=True)
    long_leave_threshold_days_snapshot = models.DecimalField(max_digits=7, decimal_places=2, default=0.00)
    return_reconciliation_required = models.BooleanField(default=False)
    approved_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-submitted_at", "-id"]

    def __str__(self):
        return f"{self.employee.employee_id} {self.leave_type.code} {self.start_date}"


class ReturnToWorkReconciliation(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("COMPLETED", "Completed"),
        ("REOPENED", "Reopened"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="return_to_work_reconciliations")
    leave_request = models.OneToOneField(LeaveRequest, on_delete=models.CASCADE, related_name="return_reconciliation")
    attendance_record = models.ForeignKey(
        AttendanceRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="return_to_work_reconciliations",
    )
    expected_return_date = models.DateField()
    actual_return_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    extension_required = models.BooleanField(default=False)
    attendance_correction_required = models.BooleanField(default=False)
    payroll_hold_required = models.BooleanField(default=False)
    substitute_closed = models.BooleanField(default=False)
    completed_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_return_to_work_reconciliations",
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-expected_return_date", "-updated_at", "-id"]

    def __str__(self):
        return f"{self.employee.employee_id} return {self.expected_return_date}"


class SalaryStructure(models.Model):
    PAY_FREQUENCY_CHOICES = [
        ("Monthly", "Monthly"),
        ("Bi-weekly", "Bi-weekly"),
        ("Weekly", "Weekly"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="salary_structures")
    basic_salary = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=10, default="USD")
    pay_frequency = models.CharField(max_length=20, choices=PAY_FREQUENCY_CHOICES, default="Monthly")
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_from", "-id"]

    def __str__(self):
        return f"{self.employee.employee_id} {self.basic_salary}"


class SalaryComponent(models.Model):
    COMPONENT_TYPE_CHOICES = [("Allowance", "Allowance"), ("Deduction", "Deduction")]
    AMOUNT_TYPE_CHOICES = [("Fixed", "Fixed"), ("Percentage", "Percentage")]

    structure = models.ForeignKey(SalaryStructure, on_delete=models.CASCADE, related_name="components")
    component_type = models.CharField(max_length=20, choices=COMPONENT_TYPE_CHOICES, default="Allowance")
    name = models.CharField(max_length=120)
    amount_type = models.CharField(max_length=20, choices=AMOUNT_TYPE_CHOICES, default="Fixed")
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    is_taxable = models.BooleanField(default=True)
    is_statutory = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return f"{self.name} ({self.component_type})"


class PayrollBatch(models.Model):
    STATUS_CHOICES = [
        ("Draft", "Draft"),
        ("Processing", "Processing"),
        ("Approved", "Approved"),
        ("Ready for Finance Approval", "Ready for Finance Approval"),
        ("Finance Approved", "Finance Approved"),
        ("Disbursement In Progress", "Disbursement In Progress"),
        ("Paid", "Paid"),
        ("Disbursed", "Disbursed"),
        ("Finance Posted", "Finance Posted"),
        ("Closed", "Closed"),
    ]

    month = models.PositiveIntegerField()
    year = models.PositiveIntegerField()
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default="Draft")
    total_gross = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    total_deductions = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    total_net = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    processed_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="hr_payroll_processed")
    approved_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="hr_payroll_approved")
    approved_at = models.DateTimeField(null=True, blank=True)
    finance_approved_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hr_payroll_finance_approved",
    )
    finance_approved_at = models.DateTimeField(null=True, blank=True)
    disbursed_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hr_payroll_disbursed",
    )
    disbursed_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hr_payroll_posted",
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    payment_date = models.DateField(null=True, blank=True)
    exception_count = models.PositiveIntegerField(default=0)
    blocked_item_count = models.PositiveIntegerField(default=0)
    workforce_snapshot = models.JSONField(default=dict, blank=True)
    statutory_snapshot = models.JSONField(default=dict, blank=True)
    approval_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("month", "year")
        ordering = ["-year", "-month", "-id"]

    def __str__(self):
        return f"{self.month}/{self.year} {self.status}"


class PayrollItem(models.Model):
    POSTING_BUCKET_CHOICES = [
        ("TEACHING_SALARIES", "Teaching Salaries"),
        ("OPERATIONS_SALARIES", "Operations Salaries"),
        ("SUPPORT_SALARIES", "Support Salaries"),
    ]

    payroll = models.ForeignKey(PayrollBatch, on_delete=models.CASCADE, related_name="items")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="payroll_items")
    basic_salary = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    total_allowances = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    attendance_deduction_total = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    statutory_deduction_total = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    other_deduction_total = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    employer_statutory_total = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    total_deductions = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    gross_salary = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    net_salary = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    net_payable = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    days_worked = models.DecimalField(max_digits=7, decimal_places=2, default=0.00)
    overtime_hours = models.DecimalField(max_digits=7, decimal_places=2, default=0.00)
    posting_bucket = models.CharField(max_length=30, choices=POSTING_BUCKET_CHOICES, blank=True, default="")
    is_blocked = models.BooleanField(default=False)
    block_reason = models.CharField(max_length=255, blank=True)
    calculation_snapshot = models.JSONField(default=dict, blank=True)
    pdf_file = models.FileField(upload_to="hr/payroll/payslips/", null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("payroll", "employee")
        ordering = ["employee__employee_id", "id"]

    def __str__(self):
        return f"{self.payroll_id} {self.employee.employee_id}"


class StatutoryDeductionRule(models.Model):
    RULE_CODE_CHOICES = [
        ("PAYE", "PAYE"),
        ("NSSF", "NSSF"),
        ("SHIF", "SHIF"),
        ("HOUSING_LEVY", "Housing Levy"),
        ("OTHER", "Other"),
    ]
    CALCULATION_METHOD_CHOICES = [
        ("BAND", "Band"),
        ("PERCENT", "Percent"),
        ("FIXED", "Fixed"),
    ]

    code = models.CharField(max_length=30, choices=RULE_CODE_CHOICES, default="OTHER")
    name = models.CharField(max_length=120)
    calculation_method = models.CharField(max_length=20, choices=CALCULATION_METHOD_CHOICES, default="PERCENT")
    base_name = models.CharField(max_length=50, default="GROSS_PAY")
    employee_rate = models.DecimalField(max_digits=7, decimal_places=4, default=0.00)
    employer_rate = models.DecimalField(max_digits=7, decimal_places=4, default=0.00)
    fixed_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    minimum_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    maximum_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    relief_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    is_kenya_default = models.BooleanField(default=False)
    is_mandatory = models.BooleanField(default=True)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    priority = models.PositiveIntegerField(default=0)
    configuration_notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "code", "-effective_from", "id"]

    def __str__(self):
        return f"{self.code} ({self.effective_from})"


class StatutoryDeductionBand(models.Model):
    rule = models.ForeignKey(StatutoryDeductionRule, on_delete=models.CASCADE, related_name="bands")
    lower_bound = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    upper_bound = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    employee_rate = models.DecimalField(max_digits=7, decimal_places=4, default=0.00)
    employer_rate = models.DecimalField(max_digits=7, decimal_places=4, default=0.00)
    fixed_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    additional_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "id"]

    def __str__(self):
        return f"{self.rule.code} band {self.display_order}"


class PayrollItemBreakdown(models.Model):
    LINE_TYPE_CHOICES = [
        ("ALLOWANCE", "Allowance"),
        ("ATTENDANCE_DEDUCTION", "Attendance Deduction"),
        ("STATUTORY_EMPLOYEE", "Statutory Employee"),
        ("STATUTORY_EMPLOYER", "Statutory Employer"),
        ("OTHER_DEDUCTION", "Other Deduction"),
    ]

    payroll_item = models.ForeignKey(PayrollItem, on_delete=models.CASCADE, related_name="breakdown_rows")
    line_type = models.CharField(max_length=30, choices=LINE_TYPE_CHOICES)
    code = models.CharField(max_length=50, blank=True)
    name = models.CharField(max_length=120)
    base_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    rate = models.DecimalField(max_digits=7, decimal_places=4, default=0.00)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    display_order = models.PositiveIntegerField(default=0)
    snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["display_order", "id"]

    def __str__(self):
        return f"{self.payroll_item_id} {self.line_type} {self.name}"


class PayrollDisbursement(models.Model):
    METHOD_CHOICES = [
        ("BANK", "Bank"),
        ("CASH", "Cash"),
        ("MOBILE", "Mobile"),
        ("MIXED", "Mixed"),
    ]
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("IN_PROGRESS", "In Progress"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
    ]

    payroll = models.ForeignKey(PayrollBatch, on_delete=models.CASCADE, related_name="disbursements")
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default="BANK")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    reference = models.CharField(max_length=120, blank=True)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    scheduled_date = models.DateField(null=True, blank=True)
    disbursed_at = models.DateTimeField(null=True, blank=True)
    disbursed_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="hr_payroll_disbursements")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.payroll_id} {self.status}"


class PayrollFinancePosting(models.Model):
    POSTING_STAGE_CHOICES = [
        ("ACCRUAL", "Accrual"),
        ("DISBURSEMENT", "Disbursement"),
    ]
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("POSTED", "Posted"),
        ("FAILED", "Failed"),
    ]

    payroll = models.ForeignKey(PayrollBatch, on_delete=models.CASCADE, related_name="finance_postings")
    posting_stage = models.CharField(max_length=20, choices=POSTING_STAGE_CHOICES)
    entry_key = models.CharField(max_length=120, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    journal_entry = models.ForeignKey(
        "school.JournalEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hr_payroll_postings",
    )
    cashbook_entry = models.ForeignKey(
        "school.CashbookEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hr_payroll_postings",
    )
    posted_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="hr_payroll_finance_postings")
    posted_at = models.DateTimeField(null=True, blank=True)
    vote_head_summary = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("payroll", "posting_stage")

    def __str__(self):
        return f"{self.payroll_id} {self.posting_stage}"


class JobPosting(models.Model):
    EMPLOYMENT_TYPE_CHOICES = [
        ("Full-time", "Full-time"),
        ("Part-time", "Part-time"),
        ("Contract", "Contract"),
    ]
    STATUS_CHOICES = [("Draft", "Draft"), ("Open", "Open"), ("Closed", "Closed")]

    position = models.ForeignKey(Position, on_delete=models.SET_NULL, null=True, blank=True, related_name="job_postings")
    department = models.ForeignKey("Department", on_delete=models.SET_NULL, null=True, blank=True, related_name="hr_job_postings")
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    requirements = models.TextField(blank=True)
    responsibilities = models.TextField(blank=True)
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES, default="Full-time")
    salary_min = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    deadline = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Draft")
    posted_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="hr_job_postings")
    posted_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.title


class JobApplication(models.Model):
    STATUS_CHOICES = [
        ("New", "New"),
        ("Screening", "Screening"),
        ("Shortlisted", "Shortlisted"),
        ("Interview", "Interview"),
        ("Offer", "Offer"),
        ("Rejected", "Rejected"),
        ("Hired", "Hired"),
    ]

    job_posting = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name="applications")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    resume = models.FileField(upload_to="hr/recruitment/resumes/", null=True, blank=True)
    cover_letter = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="New")
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    applied_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-applied_at", "-id"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.job_posting.title}"


class Interview(models.Model):
    INTERVIEW_TYPE_CHOICES = [("Phone", "Phone"), ("Video", "Video"), ("In-person", "In-person")]
    STATUS_CHOICES = [("Scheduled", "Scheduled"), ("Completed", "Completed"), ("Cancelled", "Cancelled"), ("No-show", "No-show")]

    application = models.ForeignKey(JobApplication, on_delete=models.CASCADE, related_name="interviews")
    interview_date = models.DateTimeField()
    interview_type = models.CharField(max_length=20, choices=INTERVIEW_TYPE_CHOICES, default="In-person")
    location = models.CharField(max_length=255, blank=True)
    interviewers = models.JSONField(default=list)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Scheduled")
    feedback = models.TextField(blank=True)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    created_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="hr_interviews")
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-interview_date", "-id"]


class OnboardingTask(models.Model):
    STATUS_CHOICES = [("Pending", "Pending"), ("In Progress", "In Progress"), ("Completed", "Completed")]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="onboarding_tasks")
    task_code = models.CharField(max_length=100, blank=True, default="")
    task = models.CharField(max_length=255)
    assigned_to = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="hr_onboarding_tasks")
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    is_required = models.BooleanField(default=True)
    blocks_account_provisioning = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["status", "due_date", "id"]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.task}"


class PerformanceGoal(models.Model):
    STATUS_CHOICES = [
        ("Not Started", "Not Started"),
        ("In Progress", "In Progress"),
        ("Achieved", "Achieved"),
        ("Not Achieved", "Not Achieved"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="performance_goals")
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    target_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Not Started")
    weight = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class PerformanceReview(models.Model):
    STATUS_CHOICES = [("Draft", "Draft"), ("Submitted", "Submitted"), ("Acknowledged", "Acknowledged")]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="performance_reviews")
    reviewer = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviews_given")
    review_period = models.CharField(max_length=50)
    overall_rating = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    strengths = models.TextField(blank=True)
    areas_improvement = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Draft")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class TrainingProgram(models.Model):
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    trainer = models.CharField(max_length=120, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    capacity = models.PositiveIntegerField(default=0)
    cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date", "-id"]


class TrainingEnrollment(models.Model):
    STATUS_CHOICES = [("Enrolled", "Enrolled"), ("Attended", "Attended"), ("Completed", "Completed"), ("Cancelled", "Cancelled")]

    program = models.ForeignKey(TrainingProgram, on_delete=models.CASCADE, related_name="enrollments")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="training_enrollments")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Enrolled")
    completion_date = models.DateField(null=True, blank=True)
    certificate = models.FileField(upload_to="hr/training/certificates/", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("program", "employee")
        ordering = ["-created_at", "-id"]


class StaffLifecycleEvent(models.Model):
    EVENT_GROUP_CHOICES = [
        ("TRANSFER", "Transfer"),
        ("CAREER", "Career"),
        ("DISCIPLINE", "Discipline"),
        ("EXIT", "Exit"),
        ("CLEARANCE", "Clearance"),
        ("ARCHIVE", "Archive"),
    ]

    employee = models.ForeignKey("Employee", on_delete=models.CASCADE, related_name="lifecycle_events")
    event_group = models.CharField(max_length=20, choices=EVENT_GROUP_CHOICES)
    event_type = models.CharField(max_length=80)
    title = models.CharField(max_length=160)
    summary = models.TextField(blank=True)
    status_snapshot = models.CharField(max_length=40, blank=True)
    effective_date = models.DateField(null=True, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    recorded_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_staff_lifecycle_events",
    )
    source_model = models.CharField(max_length=120, blank=True)
    source_id = models.PositiveBigIntegerField(null=True, blank=True)
    before_snapshot = models.JSONField(default=dict, blank=True)
    after_snapshot = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_date", "-occurred_at", "-id"]

    def __str__(self):
        return f"{self.employee} | {self.event_type}"


class StaffCareerAction(models.Model):
    ACTION_TYPE_CHOICES = [
        ("PROMOTION", "Promotion"),
        ("DEMOTION", "Demotion"),
        ("ACTING_APPOINTMENT", "Acting Appointment"),
        ("ACTING_APPOINTMENT_END", "Acting Appointment End"),
    ]
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("SCHEDULED", "Scheduled"),
        ("EFFECTIVE", "Effective"),
        ("CANCELLED", "Cancelled"),
    ]

    employee = models.ForeignKey("Employee", on_delete=models.CASCADE, related_name="career_actions")
    parent_action = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="follow_up_actions",
    )
    action_type = models.CharField(max_length=30, choices=ACTION_TYPE_CHOICES)
    from_department = models.ForeignKey(
        "Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="career_actions_from",
    )
    from_position_ref = models.ForeignKey(
        "Position",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="career_actions_from",
    )
    from_position_title = models.CharField(max_length=150, blank=True)
    to_department = models.ForeignKey(
        "Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="career_actions_to",
    )
    to_position_ref = models.ForeignKey(
        "Position",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="career_actions_to",
    )
    to_position_title = models.CharField(max_length=150, blank=True)
    target_position_grade = models.CharField(max_length=50, blank=True)
    target_salary_scale = models.CharField(max_length=50, blank=True)
    reason = models.TextField(blank=True)
    effective_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    previous_assignment_snapshot = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    requested_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_staff_career_actions",
    )
    applied_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applied_staff_career_actions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-effective_date", "-created_at", "-id"]

    def __str__(self):
        return f"{self.employee} | {self.action_type} | {self.status}"


class DisciplinaryCase(models.Model):
    STATUS_CHOICES = [
        ("OPEN", "Open"),
        ("CLOSED", "Closed"),
        ("CANCELLED", "Cancelled"),
    ]
    OUTCOME_CHOICES = [
        ("ADVISORY", "Advisory"),
        ("WARNING", "Warning"),
        ("SUSPENSION", "Suspension"),
        ("DISMISSAL", "Dismissal"),
        ("EXONERATED", "Exonerated"),
    ]

    employee = models.ForeignKey("Employee", on_delete=models.CASCADE, related_name="disciplinary_cases")
    case_number = models.CharField(max_length=50, unique=True)
    category = models.CharField(max_length=80)
    opened_on = models.DateField(default=timezone.localdate)
    incident_date = models.DateField(null=True, blank=True)
    summary = models.CharField(max_length=255)
    details = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="OPEN")
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES, blank=True, default="")
    effective_date = models.DateField(null=True, blank=True)
    opened_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="opened_hr_disciplinary_cases",
    )
    closed_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_hr_disciplinary_cases",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-opened_on", "-created_at", "-id"]

    def __str__(self):
        return f"{self.case_number} | {self.employee}"


class ExitCase(models.Model):
    EXIT_TYPE_CHOICES = [
        ("RESIGNATION", "Resignation"),
        ("RETIREMENT", "Retirement"),
        ("DISMISSAL", "Dismissal"),
        ("CONTRACT_END", "Contract End"),
    ]
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("CLEARANCE", "Clearance"),
        ("COMPLETED", "Completed"),
        ("ARCHIVED", "Archived"),
        ("CANCELLED", "Cancelled"),
    ]

    employee = models.ForeignKey("Employee", on_delete=models.CASCADE, related_name="exit_cases")
    exit_type = models.CharField(max_length=20, choices=EXIT_TYPE_CHOICES)
    notice_date = models.DateField(null=True, blank=True)
    last_working_date = models.DateField(null=True, blank=True)
    effective_date = models.DateField(null=True, blank=True)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    requested_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_hr_exit_cases",
    )
    completed_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_hr_exit_cases",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-effective_date", "-created_at", "-id"]

    def __str__(self):
        return f"{self.employee} | {self.exit_type} | {self.status}"


class ExitClearanceItem(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("CLEARED", "Cleared"),
        ("WAIVED", "Waived"),
    ]

    exit_case = models.ForeignKey("ExitCase", on_delete=models.CASCADE, related_name="clearance_items")
    label = models.CharField(max_length=160)
    department_name = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_hr_exit_clearance_items",
    )
    notes = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "id"]

    def __str__(self):
        return f"{self.exit_case_id} | {self.label} | {self.status}"


class StaffTransfer(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    ]
    TRANSFER_TYPE_CHOICES = [
        ('Internal', 'Internal (Same School)'),
        ('External', 'External (Different School/County)'),
    ]

    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='transfers')
    transfer_type = models.CharField(max_length=20, choices=TRANSFER_TYPE_CHOICES, default='Internal')
    from_department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True, related_name='transfers_out')
    from_position = models.CharField(max_length=150, blank=True)
    to_department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True, related_name='transfers_in')
    to_position = models.CharField(max_length=150, blank=True)
    to_position_ref = models.ForeignKey(
        'Position',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff_transfer_targets',
    )
    destination_school = models.CharField(max_length=255, blank=True, help_text="For External transfers")
    reason = models.TextField(blank=True)
    effective_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    handover_completed = models.BooleanField(default=False)
    clearance_completed = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    requested_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='staff_transfers_requested')
    approved_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='staff_transfers_approved')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employee} ({self.transfer_type}) – {self.status}"
