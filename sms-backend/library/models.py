from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class LibraryCategory(models.Model):
    name = models.CharField(max_length=120)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class LibraryResource(models.Model):
    TYPE_CHOICES = [
        ("Book", "Book"),
        ("Periodical", "Periodical"),
        ("Multimedia", "Multimedia"),
        ("Digital", "Digital"),
        ("Equipment", "Equipment"),
    ]

    resource_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="Book")
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True)
    authors = models.TextField(blank=True)
    publisher = models.CharField(max_length=255, blank=True)
    publication_year = models.PositiveIntegerField(null=True, blank=True)
    edition = models.CharField(max_length=80, blank=True)
    isbn = models.CharField(max_length=40, blank=True)
    language = models.CharField(max_length=20, default="en")
    classification = models.CharField(max_length=80, blank=True)
    subjects = models.TextField(blank=True)
    description = models.TextField(blank=True)
    digital_url = models.URLField(max_length=1000, blank=True, help_text="Online access link for digital/open-access resources")
    cover_image = models.ImageField(upload_to="library/resources/covers/", null=True, blank=True)
    category = models.ForeignKey(LibraryCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="resources")
    total_copies = models.PositiveIntegerField(default=0)
    available_copies = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["title", "id"]

    def __str__(self):
        return self.title


class ResourceCopy(models.Model):
    STATUS_CHOICES = [
        ("Available", "Available"),
        ("Issued", "Issued"),
        ("Reserved", "Reserved"),
        ("Lost", "Lost"),
        ("Damaged", "Damaged"),
        ("Repair", "Repair"),
    ]
    CONDITION_CHOICES = [
        ("Excellent", "Excellent"),
        ("Good", "Good"),
        ("Fair", "Fair"),
        ("Poor", "Poor"),
    ]

    resource = models.ForeignKey(LibraryResource, on_delete=models.CASCADE, related_name="copies")
    accession_number = models.CharField(max_length=80, unique=True)
    barcode = models.CharField(max_length=80, blank=True, db_index=True)
    rfid_tag = models.CharField(max_length=80, blank=True)
    location = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Available")
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default="Good")
    acquisition_date = models.DateField(null=True, blank=True)
    acquisition_source = models.CharField(max_length=180, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["resource__title", "accession_number", "id"]

    def __str__(self):
        return self.accession_number


class LibraryMember(models.Model):
    TYPE_CHOICES = [
        ("Student", "Student"),
        ("Staff", "Staff"),
        ("Parent", "Parent"),
        ("Alumni", "Alumni"),
        ("External", "External"),
    ]
    STATUS_CHOICES = [
        ("Active", "Active"),
        ("Suspended", "Suspended"),
        ("Expired", "Expired"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="library_memberships")
    student = models.OneToOneField(
        "school.Student",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="library_member_profile",
    )
    member_id = models.CharField(max_length=60, unique=True)
    member_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="Student")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Active")
    join_date = models.DateField(default=timezone.now)
    expiry_date = models.DateField(null=True, blank=True)
    total_fines = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["member_id", "id"]

    def __str__(self):
        return self.member_id


class CirculationRule(models.Model):
    member_type = models.CharField(max_length=20, choices=LibraryMember.TYPE_CHOICES)
    resource_type = models.CharField(max_length=20, choices=LibraryResource.TYPE_CHOICES)
    max_items = models.PositiveIntegerField(default=3)
    loan_period_days = models.PositiveIntegerField(default=14)
    max_renewals = models.PositiveIntegerField(default=2)
    fine_per_day = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("5.00"))
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("member_type", "resource_type")
        ordering = ["member_type", "resource_type", "id"]

    def __str__(self):
        return f"{self.member_type} {self.resource_type}"


class CirculationTransaction(models.Model):
    TYPE_CHOICES = [
        ("Issue", "Issue"),
        ("Return", "Return"),
        ("Renew", "Renew"),
        ("Lost", "Lost"),
        ("Damage", "Damage"),
    ]
    RETURN_CONDITION_CHOICES = [
        ("Excellent", "Excellent"),
        ("Good", "Good"),
        ("Damaged", "Damaged"),
    ]

    copy = models.ForeignKey(ResourceCopy, on_delete=models.CASCADE, related_name="transactions")
    member = models.ForeignKey(LibraryMember, on_delete=models.CASCADE, related_name="transactions")
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="Issue")
    issue_date = models.DateTimeField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True)
    return_date = models.DateTimeField(null=True, blank=True)
    renewal_count = models.PositiveIntegerField(default=0)
    is_overdue = models.BooleanField(default=False)
    overdue_days = models.PositiveIntegerField(default=0)
    fine_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    fine_paid = models.BooleanField(default=False)
    condition_at_return = models.CharField(max_length=20, choices=RETURN_CONDITION_CHOICES, blank=True)
    notes = models.TextField(blank=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="library_transactions_issued",
    )
    returned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="library_transactions_returned",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issue_date", "-id"]


class TeacherClassroomLoan(models.Model):
    RETURN_DESTINATION_CHOICES = [
        ("Teacher", "Teacher"),
        ("Library", "Library"),
    ]

    teacher_transaction = models.ForeignKey(
        CirculationTransaction,
        on_delete=models.CASCADE,
        related_name="classroom_loans",
    )
    copy = models.ForeignKey(
        ResourceCopy,
        on_delete=models.CASCADE,
        related_name="classroom_loans",
    )
    teacher_member = models.ForeignKey(
        LibraryMember,
        on_delete=models.CASCADE,
        related_name="teacher_classroom_loans",
    )
    student_member = models.ForeignKey(
        LibraryMember,
        on_delete=models.CASCADE,
        related_name="student_classroom_loans",
    )
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teacher_classroom_loans_issued",
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teacher_classroom_loans_received",
    )
    issue_date = models.DateTimeField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True)
    return_date = models.DateTimeField(null=True, blank=True)
    return_destination = models.CharField(
        max_length=20,
        choices=RETURN_DESTINATION_CHOICES,
        blank=True,
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issue_date", "-id"]


class Reservation(models.Model):
    STATUS_CHOICES = [
        ("Waiting", "Waiting"),
        ("Ready", "Ready"),
        ("Picked", "Picked"),
        ("Cancelled", "Cancelled"),
        ("Expired", "Expired"),
    ]

    resource = models.ForeignKey(LibraryResource, on_delete=models.CASCADE, related_name="reservations")
    member = models.ForeignKey(LibraryMember, on_delete=models.CASCADE, related_name="reservations")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Waiting")
    reserved_at = models.DateTimeField(auto_now_add=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    pickup_deadline = models.DateField(null=True, blank=True)
    picked_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    queue_position = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["resource_id", "queue_position", "id"]


class FineRecord(models.Model):
    TYPE_CHOICES = [
        ("Overdue", "Overdue"),
        ("Lost", "Lost"),
        ("Damage", "Damage"),
        ("Late Pickup", "Late Pickup"),
        ("Other", "Other"),
    ]
    STATUS_CHOICES = [("Pending", "Pending"), ("Paid", "Paid"), ("Waived", "Waived")]

    member = models.ForeignKey(LibraryMember, on_delete=models.CASCADE, related_name="fines")
    transaction = models.ForeignKey(CirculationTransaction, on_delete=models.SET_NULL, null=True, blank=True, related_name="fines")
    fine_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="Overdue")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    waiver_reason = models.TextField(blank=True)
    waived_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class InventoryAudit(models.Model):
    STATUS_CHOICES = [
        ("In Progress", "In Progress"),
        ("Completed", "Completed"),
    ]

    audit_date = models.DateField(default=timezone.now)
    conducted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="library_inventory_audits",
    )
    total_expected = models.PositiveIntegerField(default=0)
    total_found = models.PositiveIntegerField(default=0)
    missing_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="In Progress")
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-audit_date", "-id"]


class AcquisitionRequest(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Approved", "Approved"),
        ("Rejected", "Rejected"),
        ("Ordered", "Ordered"),
        ("Received", "Received"),
    ]

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="library_acquisition_requests",
    )
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255, blank=True)
    isbn = models.CharField(max_length=40, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    justification = models.TextField(blank=True)
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="library_acquisition_requests_approved",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at", "-id"]
