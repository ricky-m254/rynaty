from django.db import models


class StaffMember(models.Model):
    STAFF_TYPE_CHOICES = [
        ("Teaching", "Teaching"),
        ("Administrative", "Administrative"),
        ("Support", "Support"),
        ("Non-Teaching", "Non-Teaching"),
    ]
    EMPLOYMENT_TYPE_CHOICES = [
        ("Full-time", "Full-time"),
        ("Part-time", "Part-time"),
        ("Contract", "Contract"),
        ("Visiting", "Visiting"),
    ]
    STATUS_CHOICES = [
        ("Active", "Active"),
        ("On Leave", "On Leave"),
        ("Suspended", "Suspended"),
        ("Resigned", "Resigned"),
        ("Retired", "Retired"),
    ]
    GENDER_CHOICES = [("Male", "Male"), ("Female", "Female"), ("Other", "Other")]

    user = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)
    hr_employee = models.OneToOneField(
        "hr.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_mgmt_profile",
    )
    staff_id = models.CharField(max_length=50, unique=True, blank=True)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    photo = models.ImageField(upload_to="staff/photos/", null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, default="Other")
    nationality = models.CharField(max_length=100, blank=True)
    phone_primary = models.CharField(max_length=30, blank=True)
    phone_alternate = models.CharField(max_length=30, blank=True)
    email_personal = models.EmailField(blank=True)
    email_work = models.EmailField(blank=True)
    address_current = models.TextField(blank=True)
    address_permanent = models.TextField(blank=True)
    staff_type = models.CharField(max_length=20, choices=STAFF_TYPE_CHOICES, default="Teaching")
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES, default="Full-time")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Active")
    join_date = models.DateField(null=True, blank=True)
    exit_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["staff_id", "first_name", "last_name"]

    def __str__(self):
        return f"{self.staff_id} - {self.first_name} {self.last_name}".strip()


class StaffQualification(models.Model):
    QUALIFICATION_TYPE_CHOICES = [
        ("Degree", "Degree"),
        ("Diploma", "Diploma"),
        ("Certificate", "Certificate"),
        ("License", "License"),
    ]

    staff = models.ForeignKey(StaffMember, on_delete=models.CASCADE, related_name="qualifications")
    qualification_type = models.CharField(max_length=20, choices=QUALIFICATION_TYPE_CHOICES, default="Degree")
    title = models.CharField(max_length=180)
    institution = models.CharField(max_length=180, blank=True)
    field_of_study = models.CharField(max_length=180, blank=True)
    year_obtained = models.PositiveIntegerField(null=True, blank=True)
    certificate_file = models.FileField(upload_to="staff/qualifications/", null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-year_obtained", "-id"]


class StaffEmergencyContact(models.Model):
    staff = models.ForeignKey(StaffMember, on_delete=models.CASCADE, related_name="emergency_contacts")
    name = models.CharField(max_length=120)
    relationship = models.CharField(max_length=80, blank=True)
    phone_primary = models.CharField(max_length=30)
    phone_alt = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-is_primary", "name"]


class StaffDepartment(models.Model):
    DEPARTMENT_TYPE_CHOICES = [
        ("Academic", "Academic"),
        ("Administrative", "Administrative"),
        ("Support", "Support"),
    ]

    hr_department = models.OneToOneField(
        "hr.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_mgmt_profile",
    )
    name = models.CharField(max_length=140)
    code = models.CharField(max_length=30, unique=True)
    department_type = models.CharField(max_length=20, choices=DEPARTMENT_TYPE_CHOICES, default="Academic")
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children")
    head = models.ForeignKey(StaffMember, on_delete=models.SET_NULL, null=True, blank=True, related_name="headed_departments")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]


class StaffRole(models.Model):
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=40, unique=True)
    level = models.PositiveIntegerField(default=1)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["level", "name"]


class StaffAssignment(models.Model):
    staff = models.ForeignKey(StaffMember, on_delete=models.CASCADE, related_name="assignments")
    department = models.ForeignKey(StaffDepartment, on_delete=models.CASCADE, related_name="assignments")
    role = models.ForeignKey(StaffRole, on_delete=models.CASCADE, related_name="assignments")
    is_primary = models.BooleanField(default=False)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-effective_from", "-id"]


class StaffAttendance(models.Model):
    STATUS_CHOICES = [
        ("Present", "Present"),
        ("Absent", "Absent"),
        ("Late", "Late"),
        ("Half-Day", "Half-Day"),
        ("On Leave", "On Leave"),
    ]

    hr_attendance = models.OneToOneField(
        "hr.AttendanceRecord",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_mgmt_profile",
    )
    staff = models.ForeignKey(StaffMember, on_delete=models.CASCADE, related_name="attendance_records")
    date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Present")
    clock_in = models.TimeField(null=True, blank=True)
    clock_out = models.TimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    marked_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="staff_attendance_marked")
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("staff", "date")
        ordering = ["-date", "-id"]


class StaffObservation(models.Model):
    STATUS_CHOICES = [("Draft", "Draft"), ("Submitted", "Submitted"), ("Acknowledged", "Acknowledged")]

    staff = models.ForeignKey(StaffMember, on_delete=models.CASCADE, related_name="observations")
    observer = models.ForeignKey(StaffMember, on_delete=models.SET_NULL, null=True, blank=True, related_name="observations_given")
    observation_date = models.DateTimeField()
    class_observed = models.ForeignKey("school.SchoolClass", on_delete=models.SET_NULL, null=True, blank=True)
    lesson_topic = models.CharField(max_length=180, blank=True)
    overall_rating = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    strengths = models.TextField(blank=True)
    areas_improvement = models.TextField(blank=True)
    recommendations = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Draft")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-observation_date", "-id"]


class StaffAppraisal(models.Model):
    STATUS_CHOICES = [("Draft", "Draft"), ("Submitted", "Submitted"), ("Approved", "Approved"), ("Acknowledged", "Acknowledged")]

    staff = models.ForeignKey(StaffMember, on_delete=models.CASCADE, related_name="appraisals")
    appraiser = models.ForeignKey(StaffMember, on_delete=models.SET_NULL, null=True, blank=True, related_name="appraisals_given")
    appraisal_period = models.CharField(max_length=60)
    self_rating = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    supervisor_rating = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    overall_rating = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    strengths = models.TextField(blank=True)
    areas_development = models.TextField(blank=True)
    goals_next_period = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Draft")
    appraisal_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class StaffDocument(models.Model):
    DOCUMENT_TYPE_CHOICES = [
        ("Contract", "Contract"),
        ("Certificate", "Certificate"),
        ("License", "License"),
        ("ID", "ID"),
        ("Medical", "Medical"),
        ("Performance", "Performance"),
        ("Other", "Other"),
    ]
    VERIFICATION_CHOICES = [("Pending", "Pending"), ("Verified", "Verified"), ("Rejected", "Rejected")]

    staff = models.ForeignKey(StaffMember, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES, default="Other")
    title = models.CharField(max_length=180)
    file = models.FileField(upload_to="staff/documents/")
    file_size = models.PositiveIntegerField(default=0)
    mime_type = models.CharField(max_length=100, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_CHOICES, default="Pending")
    verified_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="staff_documents_verified")
    notes = models.TextField(blank=True)
    uploaded_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="staff_documents_uploaded")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-uploaded_at", "-id"]
