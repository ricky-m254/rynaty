from django.db import models, transaction
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal

from school.identity import generate_ulid

# ==========================================
# 1. CORE ADMINISTRATION
# ==========================================
class SchoolProfile(models.Model):
    ADMISSION_NUMBER_MODE_CHOICES = [
        ("AUTO", "Auto generate"),
        ("MANUAL", "Manual entry"),
    ]

    school_name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to='school_logos/', blank=True, null=True)
    motto = models.CharField(max_length=255, blank=True, help_text="School motto / tagline")
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email_address = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    county = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='Kenya')

    # --- Branding ---
    primary_color = models.CharField(max_length=16, default='#10b981', help_text="Hex color e.g. #10b981")
    secondary_color = models.CharField(max_length=16, default='#0ea5e9')
    font_family = models.CharField(max_length=50, default='Inter', blank=True)

    # --- Finance Settings ---
    currency = models.CharField(max_length=10, default='KES', help_text="e.g. KES, USD")
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    receipt_prefix = models.CharField(max_length=10, default='RCT-')
    invoice_prefix = models.CharField(max_length=10, default='INV-')
    admission_number_mode = models.CharField(
        max_length=20,
        choices=ADMISSION_NUMBER_MODE_CHOICES,
        default="AUTO",
    )
    admission_number_prefix = models.CharField(max_length=20, default="ADM-")
    admission_number_padding = models.PositiveIntegerField(default=4)

    # --- Locale Settings ---
    timezone = models.CharField(max_length=60, default='Africa/Nairobi', help_text='IANA timezone e.g. Africa/Nairobi')
    language = models.CharField(max_length=10, default='en', help_text='BCP-47 language tag e.g. en, sw')
    default_date_format = models.CharField(max_length=20, default='DD/MM/YYYY')

    # --- Finance Settings ---
    late_fee_grace_days = models.PositiveIntegerField(default=0, help_text='Days after due date before late fee applies')
    late_fee_type = models.CharField(max_length=10, choices=[('FLAT', 'Flat'), ('PERCENT', 'Percent')], default='FLAT')
    late_fee_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    late_fee_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    accepted_payment_methods = models.JSONField(default=list, blank=True, help_text='e.g. ["Cash","MPesa","Bank Transfer"]')

    # --- Communication Settings ---
    smtp_host = models.CharField(max_length=255, blank=True)
    smtp_port = models.PositiveIntegerField(default=587)
    smtp_user = models.CharField(max_length=255, blank=True)
    smtp_password = models.CharField(max_length=255, blank=True)
    smtp_use_tls = models.BooleanField(default=True)
    sms_provider = models.CharField(max_length=50, blank=True, help_text="e.g. africastalking, twilio")
    sms_api_key = models.CharField(max_length=255, blank=True)
    sms_username = models.CharField(max_length=100, blank=True)
    sms_sender_id = models.CharField(max_length=20, blank=True)
    whatsapp_api_key = models.CharField(max_length=255, blank=True)
    whatsapp_phone_id = models.CharField(max_length=100, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.school_name
    
# ... inside Core Administration section ...

ROLE_NAME_CHOICES = [
    ('TENANT_SUPER_ADMIN', 'Tenant Super Admin'),
    ('ADMIN', 'School Administrator'),
    ('PRINCIPAL', 'School Principal'),
    ('DEPUTY_PRINCIPAL', 'Deputy Principal'),
    ('HOD', 'Head of Department'),
    ('ACCOUNTANT', 'Finance Manager'),
    ('BURSAR', 'School Bursar'),
    ('HR_OFFICER', 'HR Officer'),
    ('REGISTRAR', 'Registrar'),
    ('SECRETARY', 'School Secretary'),
    ('TEACHER', 'Teaching Staff'),
    ('LIBRARIAN', 'School Librarian'),
    ('NURSE', 'School Nurse'),
    ('SECURITY', 'Security Staff'),
    ('SECURITY_GUARD', 'Security Guard'),
    ('COOK', 'Kitchen / Cook'),
    ('STORE_CLERK', 'Store Clerk'),
    ('PARENT', 'Parent / Guardian'),
    ('STUDENT', 'Student'),
    ('ALUMNI', 'Alumni'),
]

class Role(models.Model):
    """Defines User Roles within the School."""
    name = models.CharField(max_length=50, unique=True, choices=ROLE_NAME_CHOICES)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class UserProfile(models.Model):
    """Links Django User to a School Role."""
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.PROTECT)
    phone = models.CharField(max_length=20, blank=True)
    admission_number = models.CharField(
        max_length=50, blank=True, null=True, unique=True,
        help_text="Temporary bridge field for student account mapping; not a permanent login identity."
    )
    force_password_change = models.BooleanField(
        default=False,
        help_text="Require the user to change their password before continuing to the portal.",
    )
    photo = models.ImageField(
        upload_to='user_profiles/photos/',
        blank=True,
        null=True,
        help_text="Profile photo for portal display.",
    )
    bio = models.TextField(
        blank=True,
        default="",
        help_text="Short professional bio (teachers/staff).",
    )

    def __str__(self):
        return f"{self.user.username} - {self.role.name}"

class Module(models.Model):
    """Represents a functional module available to a tenant user."""
    key = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.key} - {self.name}"


class UserModuleAssignment(models.Model):
    """Assigns modules to users within a tenant."""
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='module_assignments')
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='user_assignments')
    assigned_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_modules')
    is_active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'module')

    def __str__(self):
        return f"{self.user.username} -> {self.module.key}"


class SubmodulePermission(models.Model):
    """Granular submodule-level permissions per role."""
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='submodule_permissions')
    module_key = models.CharField(max_length=50)
    submodule_key = models.CharField(max_length=100)
    can_view = models.BooleanField(default=True)
    can_create = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    can_approve = models.BooleanField(default=False)

    class Meta:
        unique_together = ('role', 'module_key', 'submodule_key')

    def __str__(self):
        return f"{self.role.name} | {self.module_key}.{self.submodule_key}"



# ──────────────────────────────────────────────────────────────
# Phase 16 Advanced RBAC models  (Prompts 88-91)
# ──────────────────────────────────────────────────────────────

class Permission(models.Model):
    """
    Granular permission — Phase 16 Advanced RBAC (Prompt 88).
    Name format: <domain>.<resource>.<action>
    e.g. finance.invoice.read | academics.attendance.mark
    """
    name = models.CharField(
        max_length=150,
        unique=True,
        help_text="Format: <domain>.<resource>.<action>  e.g. finance.invoice.read"
    )
    module = models.CharField(max_length=50, help_text="Domain/module key e.g. finance")
    action = models.CharField(max_length=50, help_text="Action e.g. read, create, update, delete")
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class RolePermissionGrant(models.Model):
    """
    Many-to-many link between Role and Permission — Phase 16 (Prompt 89).
    Records which permissions a role has by default.
    """
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='permission_grants')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name='role_grants')

    class Meta:
        unique_together = ('role', 'permission')

    def __str__(self) -> str:
        return f"{self.role.name} → {self.permission.name}"


class UserPermissionOverride(models.Model):
    """
    Per-user permission override — Phase 16 Advanced RBAC (Prompt 90).
    Final Permission = Role Permissions + Overrides (overrides take priority).
    is_allowed=True  → GRANT  (even if role doesn't have it)
    is_allowed=False → DENY   (even if role does have it)
    """
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='permission_overrides'
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name='user_overrides'
    )
    is_allowed = models.BooleanField(
        default=True,
        help_text="True = GRANT this permission. False = DENY this permission."
    )
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='granted_overrides'
    )

    class Meta:
        unique_together = ('user', 'permission')

    def __str__(self) -> str:
        action = "GRANT" if self.is_allowed else "DENY"
        return f"{self.user.username} | {action} | {self.permission.name}"

# ──────────────────────────────────────────────────────────────


class TenantModule(models.Model):
    """
    Tenant-scoped module enablement record.
    Tenant isolation is guaranteed by schema-level isolation (django-tenants).
    """
    module = models.OneToOneField(Module, on_delete=models.CASCADE, related_name='tenant_module')
    is_enabled = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'module__key']

    def __str__(self):
        return f"{self.module.key} ({'enabled' if self.is_enabled else 'disabled'})"


class ModuleSetting(models.Model):
    """
    Theme + feature toggles per tenant module.
    Flexible data is stored in JSON for forward compatibility.
    """
    PRESET_DEFAULT = "DEFAULT"
    PRESET_MODERN = "MODERN"
    PRESET_CLASSIC = "CLASSIC"
    PRESET_MINIMAL = "MINIMAL"
    PRESET_DARK = "DARK"
    PRESET_CHOICES = [
        (PRESET_DEFAULT, "Default"),
        (PRESET_MODERN, "Modern"),
        (PRESET_CLASSIC, "Classic"),
        (PRESET_MINIMAL, "Minimal"),
        (PRESET_DARK, "Dark"),
    ]

    SIDEBAR_COLLAPSED = "COLLAPSED"
    SIDEBAR_EXPANDED = "EXPANDED"
    SIDEBAR_ICON_ONLY = "ICON_ONLY"
    SIDEBAR_STYLE_CHOICES = [
        (SIDEBAR_COLLAPSED, "Collapsed"),
        (SIDEBAR_EXPANDED, "Expanded"),
        (SIDEBAR_ICON_ONLY, "Icon-only"),
    ]

    tenant_module = models.OneToOneField(
        TenantModule,
        on_delete=models.CASCADE,
        related_name='settings',
    )
    theme_preset = models.CharField(max_length=20, choices=PRESET_CHOICES, default=PRESET_DEFAULT)
    primary_color = models.CharField(max_length=16, default="#10b981")
    secondary_color = models.CharField(max_length=16, default="#0ea5e9")
    sidebar_style = models.CharField(
        max_length=20,
        choices=SIDEBAR_STYLE_CHOICES,
        default=SIDEBAR_EXPANDED,
    )
    feature_toggles = models.JSONField(default=dict, blank=True)
    config = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_module_settings',
    )
    updated_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_module_settings',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['tenant_module__module__key']

    def __str__(self):
        return f"{self.tenant_module.module.key} settings"


class AcademicYear(models.Model):
    name = models.CharField(max_length=50) # e.g., "2023-2024"
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_current:
            AcademicYear.objects.exclude(pk=self.pk).update(is_current=False)

    def __str__(self):
        return self.name

class Term(models.Model):
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    name = models.CharField(max_length=50) # e.g., "Term 1"
    start_date = models.DateField()
    end_date = models.DateField()
    billing_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_current = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_current:
            Term.objects.exclude(pk=self.pk).update(is_current=False)
    
    def __str__(self):
        return f"{self.academic_year.name} - {self.name}"

# ==========================================
# 2. STUDENT MANAGEMENT
# ==========================================
class Student(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    ulid = models.CharField(max_length=26, unique=True, db_index=True, editable=False, default=generate_ulid)
    admission_number = models.CharField(max_length=50, unique=True)
    gender = models.CharField(max_length=10, choices=[('M', 'Male'), ('F', 'Female')])
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    photo = models.ImageField(upload_to='students/photos/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.ulid:
            self.ulid = generate_ulid()
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                normalized_fields = set(update_fields)
                normalized_fields.add("ulid")
                kwargs["update_fields"] = list(normalized_fields)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.admission_number} - {self.first_name} {self.last_name}"

class Guardian(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='guardians')
    name = models.CharField(max_length=255)
    relationship = models.CharField(max_length=50) # Father, Mother, etc.
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)

# ==========================================
# 3. ACADEMIC MANAGEMENT
# ==========================================
class GradeLevel(models.Model):
    name = models.CharField(max_length=50, unique=True)  # e.g., Form 1 / Grade 7
    order = models.PositiveIntegerField(default=1)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class SchoolClass(models.Model):
    # Legacy fields retained for compatibility with existing flows.
    name = models.CharField(max_length=50)
    stream = models.CharField(max_length=50, blank=True) # e.g., "East", "West"
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    grade_level = models.ForeignKey(GradeLevel, on_delete=models.SET_NULL, null=True, blank=True)
    section_name = models.CharField(max_length=50, blank=True)
    class_teacher = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='homeroom_classes')
    room = models.CharField(max_length=100, blank=True)
    capacity = models.PositiveIntegerField(default=40)
    is_active = models.BooleanField(default=True)

    @property
    def display_name(self):
        if self.grade_level and self.section_name:
            return f"{self.grade_level.name} {self.section_name}".strip()
        if self.stream:
            return f"{self.name} {self.stream}".strip()
        return self.name

    def __str__(self):
        return self.display_name

class Enrollment(models.Model):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Completed', 'Completed'),
        ('Withdrawn', 'Withdrawn'),
        ('Transferred', 'Transferred'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    enrollment_date = models.DateField(auto_now_add=True)
    left_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    is_active = models.BooleanField(default=True)


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    head = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Subject(models.Model):
    SUBJECT_TYPE_CHOICES = [
        ('Compulsory', 'Compulsory'),
        ('Elective', 'Elective'),
    ]

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    subject_type = models.CharField(max_length=20, choices=SUBJECT_TYPE_CHOICES, default='Compulsory')
    periods_week = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('code',)

    def __str__(self):
        return f"{self.code} - {self.name}"


class SubjectMapping(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='mappings')
    grade_level = models.ForeignKey(GradeLevel, on_delete=models.CASCADE)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    is_compulsory = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('subject', 'grade_level', 'academic_year')

    def __str__(self):
        return f"{self.subject.code} @ {self.grade_level.name} ({self.academic_year.name})"


class SyllabusTopic(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='syllabus_topics')
    grade_level = models.ForeignKey(GradeLevel, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    topic_name = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=1)
    is_completed = models.BooleanField(default=False)
    completed_date = models.DateField(null=True, blank=True)
    completed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['term_id', 'order', 'id']

    def __str__(self):
        return f"{self.subject.code} {self.topic_name}"


class TeacherAssignment(models.Model):
    teacher = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='teacher_assignments')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    class_section = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE, null=True, blank=True)
    is_primary = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('teacher', 'subject', 'class_section', 'academic_year', 'term')

    def __str__(self):
        return f"{self.teacher.username}: {self.subject.code} @ {self.class_section.display_name}"


class GradingScheme(models.Model):
    name = models.CharField(max_length=100)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default:
            GradingScheme.objects.exclude(pk=self.pk).update(is_default=False)

    def __str__(self):
        return self.name


class GradeBand(models.Model):
    scheme = models.ForeignKey(GradingScheme, on_delete=models.CASCADE, related_name='bands')
    label = models.CharField(max_length=20)
    min_score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    max_score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    grade_point = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    remark = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-min_score', '-max_score', 'id']

    def __str__(self):
        return f"{self.scheme.name} {self.label}"


class Assessment(models.Model):
    CATEGORY_CHOICES = [
        ('Classwork', 'Classwork'),
        ('Homework', 'Homework'),
        ('Test', 'Test'),
        ('Exam', 'Exam'),
        ('Project', 'Project'),
        ('Practical', 'Practical'),
    ]

    name = models.CharField(max_length=150)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='Test')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    class_section = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    max_score = models.DecimalField(max_digits=7, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    weight_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, validators=[MinValueValidator(Decimal('0.00'))])
    date = models.DateField()
    is_published = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.subject.code})"


class AssessmentGrade(models.Model):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='grades')
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    raw_score = models.DecimalField(max_digits=7, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    percentage = models.DecimalField(max_digits=7, decimal_places=2, default=0.00)
    grade_band = models.ForeignKey(GradeBand, on_delete=models.SET_NULL, null=True, blank=True)
    entered_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    entered_at = models.DateTimeField(auto_now=True)
    remarks = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('assessment', 'student')

    def __str__(self):
        return f"{self.assessment_id} - {self.student_id}"


class TermResult(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    class_section = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    total_score = models.DecimalField(max_digits=7, decimal_places=2, default=0.00)
    grade_band = models.ForeignKey(GradeBand, on_delete=models.SET_NULL, null=True, blank=True)
    class_rank = models.PositiveIntegerField(null=True, blank=True)
    is_pass = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'class_section', 'term', 'subject')

    def __str__(self):
        return f"{self.student_id} {self.subject.code} {self.term.name}"


class ReportCard(models.Model):
    STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('Submitted', 'Submitted'),
        ('Approved', 'Approved'),
        ('Published', 'Published'),
        ('Distributed', 'Distributed'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    class_section = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Draft')
    teacher_remarks = models.TextField(blank=True)
    principal_remarks = models.TextField(blank=True)
    class_rank = models.PositiveIntegerField(null=True, blank=True)
    overall_grade = models.CharField(max_length=50, blank=True)
    attendance_days = models.PositiveIntegerField(default=0)
    pdf_file = models.FileField(upload_to='report_cards/', null=True, blank=True)
    approved_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('student', 'class_section', 'term', 'academic_year')

    def __str__(self):
        return f"ReportCard {self.student_id} {self.term.name}"


class Assignment(models.Model):
    STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('Published', 'Published'),
        ('Closed', 'Closed'),
        ('Graded', 'Graded'),
    ]

    title = models.CharField(max_length=255)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    class_section = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    teacher = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    due_date = models.DateTimeField()
    max_score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    publish_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Draft')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class AssignmentSubmission(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_late = models.BooleanField(default=False)
    file = models.FileField(upload_to='assignments/submissions/', null=True, blank=True)
    notes = models.TextField(blank=True)
    score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    feedback = models.TextField(blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)
    graded_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('assignment', 'student')

    def __str__(self):
        return f"{self.assignment_id} - {self.student_id}"


class CalendarEvent(models.Model):
    EVENT_TYPE_CHOICES = [
        ('Holiday', 'Holiday'),
        ('Exam', 'Exam'),
        ('Sports', 'Sports'),
        ('Trip', 'Trip'),
        ('Meeting', 'Meeting'),
        ('Closure', 'Closure'),
        ('Other', 'Other'),
    ]
    SCOPE_CHOICES = [
        ('School-wide', 'School-wide'),
        ('Class-specific', 'Class-specific'),
        ('Staff-only', 'Staff-only'),
    ]

    title = models.CharField(max_length=255)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES, default='Other')
    start_date = models.DateField()
    end_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    description = models.TextField(blank=True)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.SET_NULL, null=True, blank=True)
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default='School-wide')
    class_section = models.ForeignKey(SchoolClass, on_delete=models.SET_NULL, null=True, blank=True)
    is_public = models.BooleanField(default=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class StudentDocument(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='uploaded_documents')
    file = models.FileField(upload_to='students/documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student_id} - {self.file.name}"

# ==========================================
# 2C. ATTENDANCE & BEHAVIOR
# ==========================================
class AttendanceRecord(models.Model):
    STATUS_CHOICES = [
        ('Present', 'Present'),
        ('Absent', 'Absent'),
        ('Late', 'Late'),
        ('Excused', 'Excused'),
        ('Half-Day', 'Half-Day'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'date')

    def __str__(self):
        return f"{self.student.admission_number} {self.date} {self.status}"

class BehaviorIncident(models.Model):
    INCIDENT_TYPES = [
        ('Positive', 'Positive'),
        ('Negative', 'Negative'),
    ]

    SEVERITY_CHOICES = [
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Critical', 'Critical'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    incident_type = models.CharField(max_length=20, choices=INCIDENT_TYPES)
    category = models.CharField(max_length=100)
    incident_date = models.DateField()
    description = models.TextField(blank=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, blank=True)
    reported_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.admission_number} {self.incident_type} {self.category}"

# ==========================================
# 2D. MEDICAL RECORDS
# ==========================================
class MedicalRecord(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='medical_record')
    blood_type = models.CharField(max_length=10, blank=True)
    allergies = models.TextField(blank=True)
    chronic_conditions = models.TextField(blank=True)
    current_medications = models.TextField(blank=True)
    doctor_name = models.CharField(max_length=255, blank=True)
    doctor_phone = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student.admission_number} medical record"


class ImmunizationRecord(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='immunizations')
    vaccine_name = models.CharField(max_length=255)
    date_administered = models.DateField()
    booster_due_date = models.DateField(null=True, blank=True)
    certificate = models.FileField(upload_to='students/immunizations/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.admission_number} {self.vaccine_name}"


class ClinicVisit(models.Model):
    SEVERITY_CHOICES = [
        ('Minor', 'Minor'),
        ('Moderate', 'Moderate'),
        ('Serious', 'Serious'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='clinic_visits')
    visit_date = models.DateField()
    visit_time = models.TimeField(null=True, blank=True)
    complaint = models.TextField(blank=True)
    treatment = models.TextField(blank=True)
    attended_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    parent_notified = models.BooleanField(default=False)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.admission_number} {self.visit_date}"

# ==========================================
# 2B. ADMISSIONS
# ==========================================
class AdmissionApplication(models.Model):
    STATUS_CHOICES = [
        ('Inquiry', 'Inquiry'),
        ('Submitted', 'Submitted'),
        ('Documents Received', 'Documents Received'),
        ('Interview Scheduled', 'Interview Scheduled'),
        ('Assessed', 'Assessed'),
        ('Admitted', 'Admitted'),
        ('Rejected', 'Rejected'),
        ('Enrolled', 'Enrolled'),
        ('Withdrawn', 'Withdrawn'),
    ]

    DECISION_CHOICES = [
        ('Pending', 'Pending'),
        ('Admitted', 'Admitted'),
        ('Rejected', 'Rejected'),
    ]

    application_number = models.CharField(max_length=50, unique=True, blank=True, null=True)
    student_first_name = models.CharField(max_length=100)
    student_last_name = models.CharField(max_length=100)
    student_dob = models.DateField()
    student_gender = models.CharField(max_length=10, choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')])
    previous_school = models.CharField(max_length=255, blank=True)
    applying_for_grade = models.ForeignKey(SchoolClass, on_delete=models.SET_NULL, null=True, blank=True)
    application_date = models.DateField()
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='Submitted')

    interview_date = models.DateField(null=True, blank=True)
    interview_notes = models.TextField(blank=True)
    assessment_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    decision = models.CharField(max_length=20, choices=DECISION_CHOICES, default='Pending')
    decision_date = models.DateField(null=True, blank=True)
    decision_notes = models.TextField(blank=True)

    guardian_name = models.CharField(max_length=255, blank=True)
    guardian_phone = models.CharField(max_length=20, blank=True)
    guardian_email = models.EmailField(blank=True)
    notes = models.TextField(blank=True)

    documents = models.JSONField(default=list, blank=True)
    student_photo = models.ImageField(upload_to='admissions/photos/', blank=True, null=True)
    student = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.application_number:
            # First insert to get PK, then update only the application_number.
            if self._state.adding:
                super().save(*args, **kwargs)
                self.application_number = f"APP-{self.application_date.year}-{self.pk:04d}"
                super().save(update_fields=['application_number'])
                return
            self.application_number = f"APP-{self.application_date.year}-{self.pk:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.application_number} - {self.student_first_name} {self.student_last_name}"

class AdmissionDocument(models.Model):
    application = models.ForeignKey(
        AdmissionApplication,
        on_delete=models.CASCADE,
        related_name='uploaded_documents'
    )
    file = models.FileField(upload_to='admissions/documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.application_id} - {self.file.name}"

# ==========================================
# 4. HUMAN RESOURCE (MINIMAL)
# ==========================================
class Staff(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    employee_id = models.CharField(max_length=50, unique=True)
    role = models.CharField(max_length=50) # Teaching / Non-Teaching
    phone = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.employee_id})"

# ==========================================
# 5. FINANCE (PRIMARY) - IMMUTABLE & AUDITABLE
# ==========================================
class FeeStructure(models.Model):
    name = models.CharField(max_length=100) # e.g., "Term 1 Tuition"
    category = models.CharField(max_length=100, blank=True, default="")
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    grade_level = models.ForeignKey('GradeLevel', on_delete=models.SET_NULL, null=True, blank=True)
    
    # --- Billing Configuration ---
    billing_cycle = models.CharField(
        max_length=20, 
        choices=[('TERMLY', 'Termly'), ('MONTHLY', 'Monthly'), ('ONCE', 'One-Off')],
        default='TERMLY'
    )
    is_mandatory = models.BooleanField(default=True)
    
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - {self.amount}"

class Invoice(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('ISSUED', 'Issued'),
        ('PARTIALLY_PAID', 'Partially Paid'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
        ('VOID', 'Void'),
        ('CONFIRMED', 'Confirmed'),  # backward compatibility
    ]

    student = models.ForeignKey(Student, on_delete=models.DO_NOTHING, related_name='invoices') 
    term = models.ForeignKey(Term, on_delete=models.DO_NOTHING)
    invoice_number = models.CharField(max_length=40, unique=True, null=True, blank=True)
    invoice_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    
    # Financials
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Status
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES,
        default='DRAFT'
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.invoice_number or f'INV-{self.id}'} - {self.student.admission_number}"

    def save(self, *args, **kwargs):
        creating = self.pk is None
        super().save(*args, **kwargs)
        if creating and not self.invoice_number:
            self.invoice_number = f"INV-{self.id:06d}"
            super().save(update_fields=['invoice_number'])

    @property
    def balance_due(self):
        """Derived Balance Rule"""
        paid = self.payments.filter(payment__is_active=True).aggregate(total=models.Sum('amount_allocated'))['total'] or 0
        adjusted = sum(adjustment.signed_amount for adjustment in self.adjustments.all())
        return self.total_amount - paid - adjusted

class InvoiceLineItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='line_items')
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.DO_NOTHING)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    def __str__(self):
        return f"{self.invoice.id} - {self.description}"

class Payment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.DO_NOTHING)
    payment_date = models.DateTimeField(auto_now_add=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=50) # Cash, Bank Transfer, MPesa
    reference_number = models.CharField(max_length=100, unique=True)
    receipt_number = models.CharField(max_length=60, unique=True, null=True, blank=True)
    notes = models.TextField(blank=True)
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversal_reason = models.TextField(blank=True)
    reversed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='reversed_payments')
    
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"PAY-{self.reference_number} - {self.amount}"

    def save(self, *args, **kwargs):
        creating = self.pk is None
        super().save(*args, **kwargs)
        if creating and not self.receipt_number:
            prefix = 'RCT-'
            profile = SchoolProfile.objects.filter(is_active=True).first()
            if profile and profile.receipt_prefix:
                prefix = profile.receipt_prefix
            self.receipt_number = f"{prefix}{self.id:06d}"
            super().save(update_fields=['receipt_number'])
    
# ... (Inside Finance section)

class Expense(models.Model):
    """
    Tracks School Operational Expenses: Salaries, Utilities, Maintenance.
    (Can be used to track purchasing of assets/inventory as 'One-off expenses')
    """
    category = models.CharField(max_length=100, help_text="e.g., Salaries, Utilities, Purchases")
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    expense_date = models.DateField()
    vendor = models.CharField(max_length=150, blank=True)
    payment_method = models.CharField(max_length=50, blank=True)
    invoice_number = models.CharField(max_length=120, blank=True)
    approval_status = models.CharField(
        max_length=30,
        choices=[('Pending', 'Pending'), ('Approved', 'Approved'), ('Rejected', 'Rejected')],
        default='Pending',
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.category} - {self.amount}"

class Budget(models.Model):
    """
    Budget envelope scoped by academic year + term + name (multiple per term allowed).
    """
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    name = models.CharField(max_length=200, default='General Budget')
    monthly_budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    quarterly_budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    annual_budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    categories = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} — {self.academic_year} / {self.term}"

class PaymentAllocation(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='allocations')
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount_allocated = models.DecimalField(max_digits=12, decimal_places=2)
    allocated_at = models.DateTimeField(auto_now_add=True)

class VoteHead(models.Model):
    PRELOADED_NAMES = ['Tuition', 'Exam', 'Medical', 'Activity', 'Boarding/Meals', 'Development', 'Arrears']

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    allocation_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text="Percentage of each payment allocated to this vote head (0 = manual/unallocated)",
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    is_preloaded = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

class VoteHeadPaymentAllocation(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='vote_head_allocations')
    vote_head = models.ForeignKey(VoteHead, on_delete=models.CASCADE, related_name='payment_allocations')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    allocated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('payment', 'vote_head')

    def __str__(self):
        return f"{self.vote_head.name} ← {self.amount} ({self.payment.receipt_number})"

class CashbookEntry(models.Model):
    ENTRY_TYPES = [
        ('OPENING', 'Opening Balance'),
        ('RECEIPT', 'Receipt (Payment In)'),
        ('EXPENSE', 'Expense (Payment Out)'),
        ('ADJUSTMENT', 'Adjustment'),
    ]
    BOOK_TYPES = [
        ('CASH', 'Cashbook'),
        ('BANK', 'Bankbook'),
    ]

    book_type = models.CharField(max_length=10, choices=BOOK_TYPES, default='CASH')
    entry_date = models.DateField()
    entry_type = models.CharField(max_length=15, choices=ENTRY_TYPES)
    reference = models.CharField(max_length=120, blank=True)
    description = models.CharField(max_length=255)
    amount_in = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    amount_out = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    running_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name='cashbook_entries')
    expense = models.ForeignKey(Expense, on_delete=models.SET_NULL, null=True, blank=True, related_name='cashbook_entries')
    is_auto = models.BooleanField(default=False, help_text="Auto-created from payment/expense")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['book_type', 'entry_date', 'created_at']

    def __str__(self):
        return f"{self.book_type} {self.entry_date} {self.entry_type} {self.amount_in or self.amount_out}"

class BalanceCarryForward(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='carry_forwards')
    from_term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='carry_forwards_from')
    to_term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='carry_forwards_to')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'from_term', 'to_term')

    def __str__(self):
        return f"Carry {self.student} {self.from_term}→{self.to_term}: {self.amount}"

# ==========================================
# 6. COMMUNICATION
# ==========================================
class Message(models.Model):
    recipient_type = models.CharField(max_length=20) # STUDENT, GUARDIAN, STAFF
    recipient_id = models.IntegerField() # Generic ID to link to student/staff
    subject = models.CharField(max_length=200)
    body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='SENT') # SENT, FAILED

# ==========================================
# CORE ADMINISTRATION: ROLES & PERMISSIONS
# ==========================================


# ==========================================
# 7. NEW FINANCE MODELS (ENHANCEMENT)
# ==========================================

class FeeAssignment(models.Model):
    """
    Links a Student to a FeeStructure.
    Used for knowing 'Who pays what' before invoicing.
    Essential for Scholarships/Discounts logic.
    """
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fee_assignments')
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.CASCADE)
    
    # Specific discount for this student on this fee
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student} - {self.fee_structure.name}"

class OptionalChargeCategory(models.TextChoices):
    UNIFORM = 'UNIFORM', 'Uniform'
    TRIP = 'TRIP', 'Trip'
    BOOKS = 'BOOKS', 'Books'
    ACTIVITY = 'ACTIVITY', 'Activity'
    TRANSPORT = 'TRANSPORT', 'Transport'
    MEALS = 'MEALS', 'Meals'
    OTHER = 'OTHER', 'Other'

class OptionalCharge(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=OptionalChargeCategory.choices, default=OptionalChargeCategory.OTHER)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    academic_year = models.ForeignKey('AcademicYear', on_delete=models.SET_NULL, null=True, blank=True)
    term = models.ForeignKey('Term', on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['category', 'name']
    def __str__(self):
        return f"{self.name} ({self.get_category_display()}) - {self.amount}"

class StudentOptionalCharge(models.Model):
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='optional_charges')
    optional_charge = models.ForeignKey(OptionalCharge, on_delete=models.CASCADE, related_name='student_assignments')
    invoice = models.ForeignKey('Invoice', on_delete=models.SET_NULL, null=True, blank=True, related_name='optional_charges')
    is_paid = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = [['student', 'optional_charge']]
        ordering = ['-assigned_at']
    def __str__(self):
        return f"{self.student} — {self.optional_charge.name}"

class ScholarshipAward(models.Model):
    AWARD_TYPE_CHOICES = [
        ('FIXED', 'Fixed Amount'),
        ('PERCENT', 'Percentage'),
        ('FULL', 'Full Coverage'),
    ]
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('PAUSED', 'Paused'),
        ('ENDED', 'Ended'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='scholarships')
    program_name = models.CharField(max_length=150)
    award_type = models.CharField(max_length=20, choices=AWARD_TYPE_CHOICES, default='FIXED')
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_scholarships')
    approved_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_scholarships')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student} - {self.program_name}"

class InvoiceAdjustment(models.Model):
    """
    Represents a Credit Note or Waiver.
    Reduces the balance due on an invoice without changing the immutable total_amount.
    """
    TYPE_CHOICES = [
        ('CREDIT', 'Credit'),
        ('DEBIT', 'Debit'),
    ]
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='adjustments')
    adjustment_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='CREDIT')
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    reason = models.TextField()
    adjusted_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='APPROVED')
    reviewed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_invoice_adjustments')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"ADJ-{self.id} - {self.amount}"

    @property
    def signed_amount(self):
        if self.status != 'APPROVED':
            return Decimal('0.00')
        return self.amount if self.adjustment_type == 'CREDIT' else -self.amount


class PaymentReversalRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='reversal_requests')
    reason = models.TextField()
    requested_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='payment_reversal_requests')
    requested_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    reviewed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_payment_reversals')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    def __str__(self):
        return f"REV-{self.id} {self.payment_id} {self.status}"


class InvoiceWriteOffRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='writeoff_requests')
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    reason = models.TextField()
    requested_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='invoice_writeoff_requests')
    requested_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    reviewed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_invoice_writeoffs')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    applied_adjustment = models.ForeignKey('InvoiceAdjustment', on_delete=models.SET_NULL, null=True, blank=True, related_name='source_writeoff_requests')

    class Meta:
        ordering = ['-requested_at', '-id']

    def __str__(self):
        return f"WRO-{self.id} {self.invoice_id} {self.status}"


class InvoiceInstallmentPlan(models.Model):
    invoice = models.OneToOneField(Invoice, on_delete=models.CASCADE, related_name='installment_plan')
    installment_count = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Plan {self.invoice_id} x{self.installment_count}"


class InvoiceInstallment(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
        ('WAIVED', 'Waived'),
    ]
    plan = models.ForeignKey(InvoiceInstallmentPlan, on_delete=models.CASCADE, related_name='installments')
    sequence = models.PositiveIntegerField()
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    collected_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, validators=[MinValueValidator(Decimal('0.00'))])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    paid_at = models.DateTimeField(null=True, blank=True)
    late_fee_applied = models.BooleanField(default=False)

    class Meta:
        unique_together = ('plan', 'sequence')
        ordering = ['sequence']

    def __str__(self):
        return f"{self.plan_id}#{self.sequence} {self.status}"


class LateFeeRule(models.Model):
    FEE_TYPE_CHOICES = [
        ('FLAT', 'Flat'),
        ('PERCENT', 'Percent'),
    ]
    grace_days = models.PositiveIntegerField(default=0)
    fee_type = models.CharField(max_length=20, choices=FEE_TYPE_CHOICES, default='FLAT')
    value = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    max_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"LateFee {self.fee_type} {self.value}"


class FeeReminderLog(models.Model):
    CHANNEL_CHOICES = [
        ('EMAIL', 'Email'),
        ('SMS', 'SMS'),
        ('INAPP', 'InApp'),
    ]
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='reminder_logs')
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default='EMAIL')
    recipient = models.CharField(max_length=255)
    sent_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, default='SENT')
    message = models.TextField(blank=True)


class PaymentGatewayTransaction(models.Model):
    STATUS_CHOICES = [
        ('INITIATED', 'Initiated'),
        ('PENDING', 'Pending'),
        ('SUCCEEDED', 'Succeeded'),
        ('FAILED', 'Failed'),
        ('REFUNDED', 'Refunded'),
    ]

    provider = models.CharField(max_length=40, default='manual')
    external_id = models.CharField(max_length=120, unique=True)
    student = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    currency = models.CharField(max_length=10, default='KES')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    payload = models.JSONField(default=dict, blank=True)
    is_reconciled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.provider}:{self.external_id} {self.status}"


class PaymentGatewayWebhookEvent(models.Model):
    event_id = models.CharField(max_length=120, unique=True)
    provider = models.CharField(max_length=40)
    event_type = models.CharField(max_length=80)
    signature = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-received_at']

    def __str__(self):
        return f"{self.provider}:{self.event_type}:{self.event_id}"


class BankStatementLine(models.Model):
    STATUS_CHOICES = [
        ('UNMATCHED', 'Unmatched'),
        ('MATCHED', 'Matched'),
        ('CLEARED', 'Cleared'),
        ('IGNORED', 'Ignored'),
    ]

    statement_date = models.DateField()
    value_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=160, blank=True)
    narration = models.TextField(blank=True)
    source = models.CharField(max_length=40, default='manual')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='UNMATCHED')
    matched_payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name='statement_matches')
    matched_gateway_transaction = models.ForeignKey(PaymentGatewayTransaction, on_delete=models.SET_NULL, null=True, blank=True, related_name='statement_matches')
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-statement_date', '-id']

    def __str__(self):
        return f"{self.statement_date} {self.amount} {self.status}"


class AccountingPeriod(models.Model):
    name = models.CharField(max_length=100, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_closed = models.BooleanField(default=False)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return self.name


class ChartOfAccount(models.Model):
    TYPE_CHOICES = [
        ('ASSET', 'Asset'),
        ('LIABILITY', 'Liability'),
        ('EQUITY', 'Equity'),
        ('REVENUE', 'Revenue'),
        ('EXPENSE', 'Expense'),
    ]

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120)
    account_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} {self.name}"


class JournalEntry(models.Model):
    entry_date = models.DateField()
    memo = models.CharField(max_length=255, blank=True)
    source_type = models.CharField(max_length=50, blank=True)
    source_id = models.PositiveIntegerField(null=True, blank=True)
    entry_key = models.CharField(max_length=120, unique=True, null=True, blank=True)
    posted_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-entry_date', '-id']

    def __str__(self):
        return f"JE-{self.id} {self.entry_date}"


class JournalLine(models.Model):
    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey(ChartOfAccount, on_delete=models.PROTECT)
    vote_head = models.ForeignKey('VoteHead', on_delete=models.PROTECT, null=True, blank=True, related_name='journal_lines')
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"JE-{self.entry_id} {self.account.code} D{self.debit} C{self.credit}"


class AuditLog(models.Model):
    """
    Tracks sensitive actions in the system.
    """
    user = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=50) # CREATE, UPDATE, DELETE, VOID
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=50) # Store ID as string to be generic
    details = models.TextField(blank=True) # JSON or text description
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} {self.model_name} - {self.user}"


# ==========================================
# STORE / INVENTORY MODULE
# ==========================================

class StoreCategory(models.Model):
    ITEM_TYPE_CHOICES = [('FOOD', 'Food'), ('OFFICE', 'Office/Stationery'), ('COMBINED', 'Combined')]
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    item_type = models.CharField(max_length=10, choices=ITEM_TYPE_CHOICES, default='OFFICE')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Store Categories'


class StoreSupplier(models.Model):
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    product_types = models.CharField(max_length=300, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class StoreItem(models.Model):
    ITEM_TYPE_CHOICES = [('FOOD', 'Food'), ('OFFICE', 'Office/Stationery'), ('OTHER', 'Other')]
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, blank=True)
    category = models.ForeignKey(StoreCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='items')
    unit = models.CharField(max_length=30, default='pcs')
    item_type = models.CharField(max_length=10, choices=ITEM_TYPE_CHOICES, default='OFFICE')
    current_stock = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reorder_level = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    max_stock = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def is_low_stock(self):
        return self.current_stock <= self.reorder_level

    class Meta:
        ordering = ['name']


class StoreTransaction(models.Model):
    TYPE_CHOICES = [
        ('RECEIPT', 'Stock Receipt'),
        ('ISSUANCE', 'Stock Issuance'),
        ('ADJUSTMENT', 'Adjustment'),
        ('OPENING', 'Opening Stock'),
    ]
    item = models.ForeignKey(StoreItem, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=12, choices=TYPE_CHOICES)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)
    purpose = models.CharField(max_length=255, blank=True)
    performed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            item = self.item
            if self.transaction_type in ('RECEIPT', 'OPENING'):
                item.current_stock += self.quantity
            elif self.transaction_type == 'ISSUANCE':
                item.current_stock = max(item.current_stock - self.quantity, 0)
            elif self.transaction_type == 'ADJUSTMENT':
                item.current_stock = self.quantity
            item.save(update_fields=['current_stock'])

    def __str__(self):
        return f"{self.transaction_type} - {self.item.name} x{self.quantity}"

    class Meta:
        ordering = ['-date', '-created_at']


class StoreOrderRequest(models.Model):
    PROCUREMENT_TYPE_CHOICES = [
        ('LPO', 'Local Purchase Order'),
        ('LSO', 'Local Supply Order'),
    ]
    OFFICE_OWNER_CHOICES = [
        ('FINANCE', 'Finance Office'),
        ('ADMIN', 'Administration'),
    ]
    SEND_TO_CHOICES = [('FINANCE', 'Finance Office'), ('ADMIN', 'Administration'), ('BOTH', 'Finance & Admin')]
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('FULFILLED', 'Fulfilled'),
    ]
    RECEIVING_STATE_CHOICES = [
        ('PENDING', 'Pending'),
        ('PARTIAL', 'Partially Received'),
        ('RECEIVED', 'Received'),
    ]
    request_code = models.CharField(max_length=30, blank=True, unique=True, null=True)
    document_number = models.CharField(max_length=30, blank=True, null=True, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    requested_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='store_requests')
    procurement_type = models.CharField(max_length=3, choices=PROCUREMENT_TYPE_CHOICES, default='LPO')
    office_owner = models.CharField(max_length=10, choices=OFFICE_OWNER_CHOICES, default='FINANCE')
    supplier = models.ForeignKey(
        'StoreSupplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='procurement_orders',
    )
    send_to = models.CharField(max_length=10, choices=SEND_TO_CHOICES, default='FINANCE')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    approval_trail = models.JSONField(default=list, blank=True)
    approved_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    receiving_state = models.CharField(max_length=10, choices=RECEIVING_STATE_CHOICES, default='PENDING')
    received_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_store_requests',
    )
    received_at = models.DateTimeField(null=True, blank=True)
    received_notes = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_store_requests')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    generated_expense = models.ForeignKey('Expense', on_delete=models.SET_NULL, null=True, blank=True, related_name='store_orders')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.procurement_type not in {choice for choice, _ in self.PROCUREMENT_TYPE_CHOICES}:
            self.procurement_type = 'LSO' if self.send_to == 'ADMIN' else 'LPO'
        if self.send_to == 'ADMIN' and self.procurement_type == 'LPO':
            self.procurement_type = 'LSO'
        inferred_office_owner = 'ADMIN' if self.send_to == 'ADMIN' or self.procurement_type == 'LSO' else 'FINANCE'
        if self.office_owner not in {choice for choice, _ in self.OFFICE_OWNER_CHOICES} or self.office_owner != inferred_office_owner:
            self.office_owner = inferred_office_owner
        if not isinstance(self.approval_trail, list):
            self.approval_trail = list(self.approval_trail or [])
        if self.approved_total is None:
            self.approved_total = Decimal('0.00')

        super().save(*args, **kwargs)

        updates = {}
        if not self.request_code:
            year = self.created_at.year if self.created_at else timezone.now().year
            self.request_code = f'REQ-{year}-{self.id:04d}'
            updates['request_code'] = self.request_code
        if not self.document_number:
            year = self.created_at.year if self.created_at else timezone.now().year
            prefix = 'LSO' if self.procurement_type == 'LSO' else 'LPO'
            self.document_number = f'{prefix}-{year}-{self.id:04d}'
            updates['document_number'] = self.document_number
        if updates:
            StoreOrderRequest.objects.filter(pk=self.pk).update(**updates)

    def __str__(self):
        return f"{self.document_number or self.request_code or self.id}: {self.title} ({self.status})"

    class Meta:
        ordering = ['-created_at']


class StoreOrderItem(models.Model):
    order = models.ForeignKey(StoreOrderRequest, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(StoreItem, on_delete=models.SET_NULL, null=True, blank=True)
    item_name = models.CharField(max_length=200, blank=True)
    unit = models.CharField(max_length=30, default='pcs')
    quantity_requested = models.DecimalField(max_digits=12, decimal_places=2)
    quantity_approved = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    quoted_unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    approved_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.item_name or (self.item.name if self.item else 'Item')} x{self.quantity_requested}"


# ==========================================
# DISPENSARY MODULE
# ==========================================

class DispensaryVisit(models.Model):
    SEVERITY_CHOICES = [('MINOR', 'Minor'), ('MODERATE', 'Moderate'), ('SERIOUS', 'Serious')]
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='dispensary_visits')
    visit_date = models.DateField()
    visit_time = models.TimeField(null=True, blank=True)
    complaint = models.TextField()
    diagnosis = models.TextField(blank=True)
    treatment = models.TextField(blank=True)
    attended_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='MINOR')
    parent_notified = models.BooleanField(default=False)
    referred = models.BooleanField(default=False)
    referred_to = models.CharField(max_length=255, blank=True)
    follow_up_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student} - {self.visit_date} ({self.severity})"

    class Meta:
        ordering = ['-visit_date', '-created_at']


class DispensaryPrescription(models.Model):
    visit = models.ForeignKey(DispensaryVisit, on_delete=models.CASCADE, related_name='prescriptions')
    medication_name = models.CharField(max_length=200)
    dosage = models.CharField(max_length=100, blank=True)
    frequency = models.CharField(max_length=100, blank=True)
    quantity_dispensed = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit = models.CharField(max_length=30, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.medication_name} for {self.visit.student}"


class DispensaryStock(models.Model):
    medication_name = models.CharField(max_length=200)
    generic_name = models.CharField(max_length=200, blank=True)
    current_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit = models.CharField(max_length=30, default='tablets')
    reorder_level = models.DecimalField(max_digits=10, decimal_places=2, default=10)
    expiry_date = models.DateField(null=True, blank=True)
    supplier = models.CharField(max_length=200, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_low_stock(self):
        return self.current_quantity <= self.reorder_level

    def __str__(self):
        return self.medication_name

    class Meta:
        ordering = ['medication_name']
        verbose_name_plural = 'Dispensary Stock'


class DispensaryDeliveryNote(models.Model):
    STATUS_CHOICES = [('Pending', 'Pending'), ('Received', 'Received'), ('Cancelled', 'Cancelled')]

    reference_number = models.CharField(max_length=60, blank=True)
    supplier = models.CharField(max_length=200)
    delivery_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    notes = models.TextField(blank=True)
    finance_expense_id = models.PositiveIntegerField(null=True, blank=True)
    received_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='delivery_notes_received')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.reference_number or 'DN'} - {self.supplier} ({self.delivery_date})"

    class Meta:
        ordering = ['-delivery_date', '-created_at']


class DispensaryDeliveryItem(models.Model):
    delivery_note = models.ForeignKey(DispensaryDeliveryNote, on_delete=models.CASCADE, related_name='items')
    medication_name = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=30, default='tablets')
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    stock = models.ForeignKey(DispensaryStock, on_delete=models.SET_NULL, null=True, blank=True, related_name='delivery_items')

    def save(self, *args, **kwargs):
        self.total_cost = self.quantity * self.unit_cost
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.medication_name} x{self.quantity}"


class DispensaryOutsideTreatment(models.Model):
    PATIENT_TYPE_CHOICES = [('Student', 'Student'), ('Staff', 'Staff'), ('Other', 'Other')]

    patient_name = models.CharField(max_length=200)
    patient_type = models.CharField(max_length=20, choices=PATIENT_TYPE_CHOICES, default='Student')
    student = models.ForeignKey('Student', on_delete=models.SET_NULL, null=True, blank=True, related_name='outside_treatments')
    referral_date = models.DateField()
    facility_name = models.CharField(max_length=200)
    reason = models.TextField(blank=True)
    diagnosis = models.TextField(blank=True)
    treatment_given = models.TextField(blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    follow_up_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.patient_name} - {self.facility_name} ({self.referral_date})"

    class Meta:
        ordering = ['-referral_date', '-created_at']


class StudentTransfer(models.Model):
    DIRECTION_CHOICES = [
        ('OUT', 'Outgoing (Leaving this school)'),
        ('IN', 'Incoming (Joining from another school)'),
    ]
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    ]

    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='transfers')
    direction = models.CharField(max_length=3, choices=DIRECTION_CHOICES, default='OUT')
    other_school = models.CharField(max_length=255, help_text="Name of the destination or source school")
    reason = models.TextField(blank=True)
    effective_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    clearance_completed = models.BooleanField(default=False, help_text="Clearance form signed")
    academic_records_issued = models.BooleanField(default=False, help_text="Transcripts/report cards issued")
    transfer_letter_issued = models.BooleanField(default=False, help_text="Official transfer letter issued")
    fee_balance_cleared = models.BooleanField(default=False, help_text="All outstanding fees cleared")
    notes = models.TextField(blank=True)
    processed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student} → {self.other_school} ({self.direction})"


# ──────────────────────────────────────────────
# TRANSFER SYSTEM  (Cross-tenant + Internal)
# ──────────────────────────────────────────────

class CrossTenantTransfer(models.Model):
    TYPE_CHOICES = [
        ('student', 'Student Transfer'),
        ('staff',   'Staff Transfer'),
        ('internal_student', 'Internal Student Transfer'),
        ('internal_staff',   'Internal Staff Transfer'),
    ]
    STATUS_CHOICES = [
        ('pending',       'Pending'),
        ('approved_from', 'Approved by Source School'),
        ('approved_to',   'Approved by Destination School'),
        ('rejected',      'Rejected'),
        ('completed',     'Completed'),
        ('cancelled',     'Cancelled'),
    ]

    transfer_type   = models.CharField(max_length=20, choices=TYPE_CHOICES)
    entity_id       = models.IntegerField(help_text='student_id or employee_id')
    from_tenant_id  = models.CharField(max_length=100)
    to_tenant_id    = models.CharField(max_length=100, blank=True)
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reason          = models.TextField(blank=True)
    fee_balance_cleared = models.BooleanField(default=False)
    exam_in_progress    = models.BooleanField(default=False, help_text='Flagged if active exam detected')
    mid_term            = models.BooleanField(default=False, help_text='Flagged if transfer is mid-term')

    initiated_by    = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='initiated_transfers')
    approved_from_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_from_transfers')
    approved_to_by  = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_to_transfers')
    rejected_by     = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='rejected_transfers')
    rejection_reason = models.TextField(blank=True)

    # Internal transfer fields
    from_class      = models.CharField(max_length=100, blank=True)
    to_class        = models.CharField(max_length=100, blank=True)
    from_stream     = models.CharField(max_length=100, blank=True)
    to_stream       = models.CharField(max_length=100, blank=True)
    from_department = models.CharField(max_length=150, blank=True)
    to_department   = models.CharField(max_length=150, blank=True)
    from_role       = models.CharField(max_length=100, blank=True)
    to_role         = models.CharField(max_length=100, blank=True)

    effective_date  = models.DateField(null=True, blank=True)
    executed_at     = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)
    notes           = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Transfer #{self.pk} [{self.transfer_type}] {self.from_tenant_id}→{self.to_tenant_id} ({self.status})"


class TransferPackage(models.Model):
    transfer    = models.OneToOneField(CrossTenantTransfer, on_delete=models.CASCADE, related_name='package')
    data_snapshot = models.JSONField(default=dict, help_text='Full entity data snapshot at time of transfer')
    generated_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Package for Transfer #{self.transfer_id}"


class StudentHistory(models.Model):
    student     = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='school_history')
    tenant_id   = models.CharField(max_length=100)
    school_name = models.CharField(max_length=255, blank=True)
    class_name  = models.CharField(max_length=100, blank=True)
    stream      = models.CharField(max_length=100, blank=True)
    start_date  = models.DateField()
    end_date    = models.DateField(null=True, blank=True)
    transfer    = models.ForeignKey(CrossTenantTransfer, on_delete=models.SET_NULL, null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.student} @ {self.school_name} ({self.start_date}–{self.end_date or 'present'})"


class StaffHistory(models.Model):
    employee_id  = models.IntegerField(help_text='hr.Employee pk')
    employee_name = models.CharField(max_length=255, blank=True)
    tenant_id    = models.CharField(max_length=100)
    school_name  = models.CharField(max_length=255, blank=True)
    role         = models.CharField(max_length=100, blank=True)
    department   = models.CharField(max_length=150, blank=True)
    start_date   = models.DateField()
    end_date     = models.DateField(null=True, blank=True)
    transfer     = models.ForeignKey(CrossTenantTransfer, on_delete=models.SET_NULL, null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"Staff {self.employee_name} @ {self.school_name} ({self.start_date}–{self.end_date or 'present'})"


# ──────────────────────────────────────────────
# SETTINGS & ADMISSION SYSTEM
# ──────────────────────────────────────────────

class AdmissionSettings(models.Model):
    """
    Extended admission-number configuration per tenant.
    Tracks the running sequence for auto-generated numbers and
    holds the transfer-student policy.
    """
    TRANSFER_POLICY_CHOICES = [
        ('new', 'Assign new admission number (store previous)'),
        ('keep', 'Retain old admission number from source school'),
    ]
    RESET_CHOICES = [
        ('never', 'Never reset — numbers keep incrementing'),
        ('yearly', 'Reset sequence each academic year'),
    ]

    prefix          = models.CharField(max_length=20, default='ADM-', help_text='e.g. STM- or 2025/')
    year            = models.PositiveIntegerField(default=2025, help_text='Current academic year used in number')
    sequence        = models.PositiveIntegerField(default=0, help_text='Last used sequence number')
    padding         = models.PositiveIntegerField(default=4, help_text='Zero-pad width e.g. 4 → 0001')
    include_year    = models.BooleanField(default=True, help_text='Include year in format: PREFIX-YEAR-SEQ')
    reset_policy    = models.CharField(max_length=10, choices=RESET_CHOICES, default='never')
    transfer_policy = models.CharField(max_length=10, choices=TRANSFER_POLICY_CHOICES, default='new')
    auto_generate   = models.BooleanField(default=True, help_text='Auto-generate on enrolment (vs. manual entry)')
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Admission Settings'

    def __str__(self):
        return f"AdmissionSettings(prefix={self.prefix}, seq={self.sequence})"

    def generate_next(self) -> str:
        """Return the next admission number and increment the sequence."""
        self.sequence += 1
        self.save(update_fields=['sequence', 'updated_at'])
        seq_str = str(self.sequence).zfill(self.padding)
        if self.include_year:
            return f"{self.prefix}{self.year}-{seq_str}"
        return f"{self.prefix}{seq_str}"


class TenantSettings(models.Model):
    """
    Generic key-value settings store per tenant.
    Complements SchoolProfile for arbitrary, schema-free configuration.
    Values are stored as JSON to support any data type.
    """
    key         = models.CharField(max_length=100, unique=True, help_text='Dot-path key e.g. admission.format')
    value       = models.JSONField(default=None, null=True, blank=True)
    description = models.CharField(max_length=255, blank=True)
    category    = models.CharField(max_length=50, default='general',
                                   help_text='Grouping e.g. general, finance, academic, communication')
    updated_at  = models.DateTimeField(auto_now=True)
    updated_by  = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['category', 'key']
        verbose_name = 'Tenant Setting'
        verbose_name_plural = 'Tenant Settings'

    def __str__(self):
        return f"{self.key} = {self.value}"


class InstitutionSecurityPolicy(models.Model):
    """
    Tenant-scoped singleton-style security policy.
    Schema isolation means a single row per tenant schema is sufficient.
    """

    MFA_MODE_CHOICES = [
        ("DISABLED", "Disabled"),
        ("ADMIN_ONLY", "Admin only"),
        ("ALL_STAFF", "All staff"),
    ]
    MFA_METHOD_CHOICES = [
        ("SMS", "SMS"),
        ("EMAIL", "Email"),
        ("TOTP", "Authenticator app"),
    ]

    session_timeout_minutes = models.PositiveIntegerField(default=60, validators=[MinValueValidator(5)])
    max_login_attempts = models.PositiveIntegerField(default=5, validators=[MinValueValidator(1)])
    lockout_duration_minutes = models.PositiveIntegerField(default=15, validators=[MinValueValidator(1)])
    min_password_length = models.PositiveIntegerField(default=8, validators=[MinValueValidator(6)])
    require_uppercase = models.BooleanField(default=True)
    require_numbers = models.BooleanField(default=True)
    require_special_characters = models.BooleanField(default=False)
    password_expiry_days = models.PositiveIntegerField(default=90)
    mfa_mode = models.CharField(max_length=20, choices=MFA_MODE_CHOICES, default="DISABLED")
    mfa_method = models.CharField(max_length=10, choices=MFA_METHOD_CHOICES, default="SMS")
    ip_whitelist_enabled = models.BooleanField(default=False)
    allowed_ip_ranges = models.JSONField(default=list, blank=True)
    audit_log_retention_days = models.PositiveIntegerField(default=365, validators=[MinValueValidator(30)])
    updated_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_institution_security_policies",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Institution Security Policy"
        verbose_name_plural = "Institution Security Policies"

    def __str__(self):
        return (
            f"InstitutionSecurityPolicy(timeout={self.session_timeout_minutes}m, "
            f"mfa={self.mfa_mode}, ip_whitelist={self.ip_whitelist_enabled})"
        )


class InstitutionLifecycleTemplate(models.Model):
    TEMPLATE_CODE_CHOICES = [
        ("TENANT_ONBOARDING", "Tenant onboarding"),
        ("TERM_START", "Term start"),
        ("YEAR_CLOSE", "Year close"),
    ]

    code = models.CharField(max_length=40, choices=TEMPLATE_CODE_CHOICES, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "Institution Lifecycle Template"
        verbose_name_plural = "Institution Lifecycle Templates"

    def __str__(self):
        return self.name


class InstitutionLifecycleTaskTemplate(models.Model):
    template = models.ForeignKey(
        InstitutionLifecycleTemplate,
        on_delete=models.CASCADE,
        related_name="task_templates",
    )
    task_code = models.CharField(max_length=80)
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    task_group = models.CharField(max_length=80, blank=True)
    required = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    waivable = models.BooleanField(default=False)
    validation_key = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["template_id", "display_order", "id"]
        unique_together = ("template", "task_code")
        verbose_name = "Institution Lifecycle Task Template"
        verbose_name_plural = "Institution Lifecycle Task Templates"

    def __str__(self):
        return f"{self.template.code}:{self.task_code}"


class InstitutionLifecycleRun(models.Model):
    STATUS_DRAFT = "DRAFT"
    STATUS_IN_PROGRESS = "IN_PROGRESS"
    STATUS_BLOCKED = "BLOCKED"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_IN_PROGRESS, "In progress"),
        (STATUS_BLOCKED, "Blocked"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    template = models.ForeignKey(
        InstitutionLifecycleTemplate,
        on_delete=models.PROTECT,
        related_name="runs",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    started_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="started_institution_lifecycle_runs",
    )
    completed_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_institution_lifecycle_runs",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    target_academic_year = models.ForeignKey(
        "AcademicYear",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="institution_lifecycle_runs",
    )
    target_term = models.ForeignKey(
        "Term",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="institution_lifecycle_runs",
    )
    summary = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "Institution Lifecycle Run"
        verbose_name_plural = "Institution Lifecycle Runs"

    def __str__(self):
        return f"{self.template.code} [{self.status}]"


class InstitutionLifecycleTaskRun(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_WAIVED = "WAIVED"
    STATUS_BLOCKED = "BLOCKED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_WAIVED, "Waived"),
        (STATUS_BLOCKED, "Blocked"),
    ]

    run = models.ForeignKey(
        InstitutionLifecycleRun,
        on_delete=models.CASCADE,
        related_name="task_runs",
    )
    template_task = models.ForeignKey(
        InstitutionLifecycleTaskTemplate,
        on_delete=models.PROTECT,
        related_name="task_runs",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    completed_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_institution_lifecycle_task_runs",
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    waived_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="waived_institution_lifecycle_task_runs",
    )
    waived_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    blocker_message = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "id"]
        unique_together = ("run", "template_task")
        verbose_name = "Institution Lifecycle Task Run"
        verbose_name_plural = "Institution Lifecycle Task Runs"

    def __str__(self):
        return f"{self.run_id}:{self.template_task.task_code} [{self.status}]"


class MediaFile(models.Model):
    """Tracks uploaded media/document files per module."""
    MODULE_CHOICES = [
        ('STUDENTS', 'Students'),
        ('ADMISSIONS', 'Admissions'),
        ('ACADEMICS', 'Academics'),
        ('STAFF', 'Staff'),
        ('HR', 'Human Resources'),
        ('FINANCE', 'Finance'),
        ('LIBRARY', 'Library'),
        ('TRANSPORT', 'Transport'),
        ('HOSTEL', 'Hostel'),
        ('ASSETS', 'Inventory & Assets'),
        ('CLOCKIN', 'Clock-In'),
        ('BRANDING', 'Branding'),
        ('COMMUNICATION', 'Communication'),
        ('REPORTING', 'Reporting'),
        ('SETTINGS', 'Settings'),
        ('OTHER', 'Other'),
    ]
    FILE_TYPE_CHOICES = [
        ('image', 'Image'),
        ('pdf', 'PDF'),
        ('doc', 'Document'),
        ('spreadsheet', 'Spreadsheet'),
        ('json', 'JSON'),
        ('xml', 'XML'),
        ('archive', 'Archive'),
        ('other', 'Other'),
    ]

    module      = models.CharField(max_length=30, choices=MODULE_CHOICES, default='OTHER')
    file_type   = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES, default='other')
    file        = models.FileField(upload_to='media_files/%Y/%m/')
    original_name = models.CharField(max_length=255, blank=True)
    size_bytes  = models.PositiveIntegerField(default=0)
    url         = models.URLField(blank=True, help_text='Absolute URL populated on save')
    uploaded_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=255, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.module} / {self.original_name or self.file.name}"


# ==========================================
# LEDGER SYSTEM (Phase 2)
# ==========================================

class Wallet(models.Model):
    """Per-user wallet. Tenant-isolated via django-tenants schema."""
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    frozen_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    last_activity = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['user'])]
        verbose_name = 'Wallet'

    def __str__(self):
        return f"{self.user} — Balance: {self.balance}"

    @property
    def available_balance(self):
        return self.balance - self.frozen_balance

    @transaction.atomic
    def credit(self, amount, entry_type, reference, description='', adjusted_by=None, adjustment_reason=''):
        from decimal import Decimal as _D
        amount = _D(str(amount))
        if amount <= 0:
            raise ValueError("Credit amount must be positive")
        self.balance += amount
        self.save()
        return LedgerEntry.objects.create(
            user=self.user,
            amount=amount,
            entry_type=entry_type,
            reference=reference,
            description=description,
            balance_after=self.balance,
            adjusted_by=adjusted_by,
            adjustment_reason=adjustment_reason,
        )

    @transaction.atomic
    def debit(self, amount, entry_type, reference, description='', adjusted_by=None, adjustment_reason=''):
        from decimal import Decimal as _D
        amount = _D(str(amount))
        if amount <= 0:
            raise ValueError("Debit amount must be positive")
        if self.balance < amount:
            raise ValueError(f"Insufficient balance: {self.balance} < {amount}")
        self.balance -= amount
        self.save()
        return LedgerEntry.objects.create(
            user=self.user,
            amount=-amount,
            entry_type=entry_type,
            reference=reference,
            description=description,
            balance_after=self.balance,
            adjusted_by=adjusted_by,
            adjustment_reason=adjustment_reason,
        )

    @transaction.atomic
    def freeze(self, amount):
        from decimal import Decimal as _D
        amount = _D(str(amount))
        if self.available_balance < amount:
            raise ValueError("Insufficient available balance to freeze")
        self.frozen_balance += amount
        self.save()

    @transaction.atomic
    def unfreeze(self, amount):
        from decimal import Decimal as _D
        amount = _D(str(amount))
        if self.frozen_balance < amount:
            raise ValueError("Cannot unfreeze more than frozen amount")
        self.frozen_balance -= amount
        self.save()

    @classmethod
    def get_or_create_for_user(cls, user):
        wallet, _ = cls.objects.get_or_create(user=user, defaults={'balance': Decimal('0.00')})
        return wallet


class LedgerEntry(models.Model):
    """Double-entry ledger record — source of truth for all balance changes."""
    ENTRY_TYPES = [
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAWAL', 'Withdrawal'),
        ('FEE_PAYMENT', 'Fee Payment'),
        ('REFUND', 'Refund'),
        ('ADMIN_ADJUSTMENT', 'Admin Adjustment'),
        ('TRANSACTION_FEE', 'Transaction Fee'),
        ('SCHOOL_CREDIT', 'School Credit'),
        ('SCHOOL_FEE', 'School Fee'),
        ('PENALTY', 'Penalty'),
        ('DISCOUNT', 'Discount'),
    ]

    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='ledger_entries')
    amount = models.DecimalField(max_digits=12, decimal_places=2,
        help_text='Positive = credit, negative = debit')
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPES)
    reference = models.CharField(max_length=100, db_index=True,
        help_text='M-Pesa receipt, invoice number, etc')
    description = models.TextField(blank=True)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    adjusted_by = models.ForeignKey('auth.User', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='ledger_adjustments_made')
    adjustment_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['reference']),
            models.Index(fields=['entry_type', 'created_at']),
        ]
        verbose_name = 'Ledger Entry'

    def __str__(self):
        sign = '+' if self.amount > 0 else ''
        return f"{self.entry_type}: {sign}{self.amount} (bal: {self.balance_after})"

    @property
    def is_credit(self):
        return self.amount > 0

    @property
    def is_debit(self):
        return self.amount < 0


class LedgerReconciliation(models.Model):
    """Records of reconciliation runs."""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'), ('IN_PROGRESS', 'In Progress'),
        ('BALANCED', 'Balanced'), ('MISMATCH', 'Mismatch Found'), ('ERROR', 'Error'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    start_date = models.DateField()
    end_date = models.DateField()
    total_entries = models.IntegerField(default=0)
    total_credits = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    total_debits = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    discrepancies = models.JSONField(default=list)
    notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Ledger Reconciliation'


# ==========================================
# FRAUD DETECTION SYSTEM (Phase 5)
# ==========================================

class FraudAlert(models.Model):
    """Security and fraud alerts. Tenant-isolated via schema."""
    LEVEL_CHOICES = [('INFO', 'Info'), ('WARNING', 'Warning'), ('CRITICAL', 'Critical')]
    ALERT_TYPES = [
        ('HIGH_RISK_TRANSACTION_BLOCKED', 'High Risk Transaction Blocked'),
        ('ELEVATED_RISK_TRANSACTION', 'Elevated Risk Transaction'),
        ('DUPLICATE_RECEIPT', 'Duplicate Receipt Detected'),
        ('RECONCILIATION_MISMATCH', 'Reconciliation Mismatch'),
        ('OVERDRAFT_ATTEMPT', 'Overdraft Attempt'),
        ('SUSPICIOUS_PATTERN', 'Suspicious Pattern Detected'),
        ('VOLUME_SPIKE', 'Unusual Volume Spike'),
        ('MANY_FAILURES', 'Many Failed Transactions'),
        ('ACTIVITY_SPIKE', 'Activity Spike'),
        ('ROUND_AMOUNT_PATTERN', 'Round Amount Pattern'),
        ('PHONE_MISMATCH', 'Phone Number Mismatch'),
        ('DAILY_VOLUME_LIMIT', 'Daily Volume Limit Exceeded'),
        ('NEW_USER_LARGE_TX', 'New User Large Transaction'),
        ('MISSING_RECEIPT', 'Missing M-Pesa Receipt'),
    ]

    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, db_index=True)
    alert_type = models.CharField(max_length=50, choices=ALERT_TYPES)
    message = models.TextField()
    reference = models.CharField(max_length=100, blank=True, db_index=True)
    metadata = models.JSONField(default=dict)
    user = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='fraud_alerts')
    resolved = models.BooleanField(default=False, db_index=True)
    resolved_by = models.ForeignKey('auth.User', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='resolved_fraud_alerts')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    escalated = models.BooleanField(default=False)
    escalated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['level', 'resolved']),
            models.Index(fields=['alert_type']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = 'Fraud Alert'

    def __str__(self):
        return f"[{self.level}] {self.alert_type}"

    def resolve(self, user, notes=''):
        from django.utils import timezone as tz
        self.resolved = True
        self.resolved_by = user
        self.resolved_at = tz.now()
        self.resolution_notes = notes
        self.save()

    def escalate(self):
        from django.utils import timezone as tz
        self.escalated = True
        self.escalated_at = tz.now()
        self.save()


class RiskScoreLog(models.Model):
    """Log of fraud risk scores for all evaluated transactions."""
    ACTION_CHOICES = [('ALLOW', 'Allowed'), ('FLAG', 'Flagged'), ('BLOCK', 'Blocked')]

    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='risk_scores')
    transaction_amount = models.DecimalField(max_digits=12, decimal_places=2)
    risk_score = models.IntegerField(help_text='0-100')
    factors = models.JSONField(default=list)
    action_taken = models.CharField(max_length=20, choices=ACTION_CHOICES)
    alert = models.ForeignKey(FraudAlert, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['risk_score']),
            models.Index(fields=['action_taken']),
        ]
        verbose_name = 'Risk Score Log'

    def __str__(self):
        return f"Score {self.risk_score} — {self.action_taken} — {self.user}"


class FraudWhitelist(models.Model):
    """Trusted phones/users/IPs that bypass fraud checks."""
    TYPE_CHOICES = [('PHONE', 'Phone Number'), ('USER', 'User'), ('IP', 'IP Address')]

    whitelist_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    value = models.CharField(max_length=100)
    reason = models.TextField()
    whitelisted_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['whitelist_type', 'value']
        verbose_name = 'Fraud Whitelist Entry'

    def is_valid(self):
        from django.utils import timezone as tz
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < tz.now():
            return False
        return True


# ==========================================
# TAMPER-PROOF AUDIT LOG (Phase 6)
# ==========================================

class FinanceAuditLog(models.Model):
    """
    Tamper-proof financial audit log with SHA-256 hash chain.
    Every entry's hash links to the previous entry, making modification detectable.
    """
    ACTION_CHOICES = [
        ('PAYMENT_RECEIVED', 'Payment Received'),
        ('PAYMENT_FAILED', 'Payment Failed'),
        ('BALANCE_UPDATED', 'Balance Updated'),
        ('BALANCE_ADJUSTED', 'Balance Adjusted by Admin'),
        ('STK_PUSH_INITIATED', 'STK Push Initiated'),
        ('STK_PUSH_CALLBACK', 'STK Push Callback Received'),
        ('WALLET_CREDITED', 'Wallet Credited'),
        ('WALLET_DEBITED', 'Wallet Debited'),
        ('WITHDRAWAL_REQUESTED', 'Withdrawal Requested'),
        ('WITHDRAWAL_APPROVED', 'Withdrawal Approved'),
        ('INVOICE_CREATED', 'Invoice Created'),
        ('INVOICE_PAID', 'Invoice Paid'),
        ('INVOICE_CANCELLED', 'Invoice Cancelled'),
        ('FRAUD_ALERT_RAISED', 'Fraud Alert Raised'),
        ('FRAUD_ALERT_RESOLVED', 'Fraud Alert Resolved'),
        ('ADMIN_ACTION', 'Admin Action'),
        ('EXPORT_GENERATED', 'Export Generated'),
    ]

    user = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='finance_audit_logs')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, db_index=True)
    entity = models.CharField(max_length=50, help_text='TRANSACTION, WALLET, INVOICE, etc')
    entity_id = models.CharField(max_length=100)
    metadata = models.JSONField(default=dict)

    # Request context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_path = models.CharField(max_length=500, blank=True)
    request_method = models.CharField(max_length=10, blank=True)

    # Tamper-proof chain
    entry_hash = models.CharField(max_length=64, db_index=True)
    previous_hash = models.CharField(max_length=64, blank=True)

    created_at = models.DateTimeField(null=True, blank=True,
        help_text="Explicitly set before save to ensure hash stability")

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['entity', 'entity_id']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = 'Finance Audit Log'

    def __str__(self):
        return f"{self.action} — {self.entity} — {self.created_at}"

    def save(self, *args, **kwargs):
        from django.utils import timezone as tz
        if not self.created_at:
            self.created_at = tz.now()
        if not self.entry_hash:
            self._compute_hash()
        super().save(*args, **kwargs)

    def _compute_hash(self):
        import hashlib
        import json as _json
        from django.utils import timezone as tz

        last = FinanceAuditLog.objects.exclude(pk=self.pk if self.pk else None).first()
        self.previous_hash = last.entry_hash if last else '0' * 64

        ts = self.created_at.isoformat() if self.created_at else tz.now().isoformat()
        data = {
            'user_id': str(self.user_id) if self.user_id else None,
            'action': self.action,
            'entity': self.entity,
            'entity_id': self.entity_id,
            'metadata': self.metadata,
            'ip_address': str(self.ip_address) if self.ip_address else None,
            'timestamp': ts,
            'previous_hash': self.previous_hash,
        }
        self.entry_hash = hashlib.sha256(
            _json.dumps(data, sort_keys=True, separators=(',', ':')).encode()
        ).hexdigest()

    def verify_integrity(self):
        import hashlib
        import json as _json
        ts = self.created_at.isoformat() if self.created_at else ''
        data = {
            'user_id': str(self.user_id) if self.user_id else None,
            'action': self.action,
            'entity': self.entity,
            'entity_id': self.entity_id,
            'metadata': self.metadata,
            'ip_address': str(self.ip_address) if self.ip_address else None,
            'timestamp': ts,
            'previous_hash': self.previous_hash,
        }
        recomputed = hashlib.sha256(
            _json.dumps(data, sort_keys=True, separators=(',', ':')).encode()
        ).hexdigest()
        return recomputed == self.entry_hash

    @classmethod
    def log_action(cls, action, entity, entity_id, metadata=None, request=None, user=None):
        ip = None
        ua = ''
        path = ''
        method = ''
        if request:
            xff = request.META.get('HTTP_X_FORWARDED_FOR')
            ip = xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR')
            ua = request.META.get('HTTP_USER_AGENT', '')[:500]
            path = request.path[:500]
            method = request.method
            if user is None and hasattr(request, 'user') and request.user.is_authenticated:
                user = request.user
        return cls.objects.create(
            user=user,
            action=action,
            entity=entity,
            entity_id=str(entity_id),
            metadata=metadata or {},
            ip_address=ip,
            user_agent=ua,
            request_path=path,
            request_method=method,
        )

    @classmethod
    def verify_chain(cls):
        entries = cls.objects.order_by('created_at')
        previous_hash = '0' * 64
        for entry in entries:
            if entry.previous_hash != previous_hash:
                return False, f"Chain broken at entry {entry.id}", entry
            if not entry.verify_integrity():
                return False, f"Entry {entry.id} has been tampered with", entry
            previous_hash = entry.entry_hash
        return True, "Chain verified", None
