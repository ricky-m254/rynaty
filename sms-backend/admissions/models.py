from django.conf import settings
from django.db import models

from school.models import AcademicYear, AdmissionApplication, SchoolClass, Term


class AdmissionInquiry(models.Model):
    SOURCE_CHOICES = [
        ("Website", "Website"),
        ("Referral", "Referral"),
        ("Advertisement", "Advertisement"),
        ("Walk-in", "Walk-in"),
        ("Event", "Event"),
        ("Other", "Other"),
    ]

    STATUS_CHOICES = [
        ("New", "New"),
        ("Contacted", "Contacted"),
        ("Interested", "Interested"),
        ("Applied", "Applied"),
        ("Lost", "Lost"),
    ]

    parent_name = models.CharField(max_length=255)
    parent_phone = models.CharField(max_length=30, blank=True)
    parent_email = models.EmailField(blank=True)
    child_name = models.CharField(max_length=255)
    child_dob = models.DateField(null=True, blank=True)
    child_age = models.PositiveIntegerField(null=True, blank=True)
    current_school = models.CharField(max_length=255, blank=True)
    grade_level_interest = models.ForeignKey(SchoolClass, on_delete=models.SET_NULL, null=True, blank=True)
    inquiry_source = models.CharField(max_length=30, choices=SOURCE_CHOICES, default="Website")
    inquiry_date = models.DateField()
    preferred_start = models.ForeignKey(Term, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="New")
    assigned_counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admissions_inquiries_assigned",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-inquiry_date", "-created_at"]

    def __str__(self):
        return f"{self.child_name} ({self.status})"


class AdmissionApplicationProfile(models.Model):
    application = models.OneToOneField(
        AdmissionApplication,
        on_delete=models.CASCADE,
        related_name="normalized_profile",
    )
    inquiry = models.ForeignKey(AdmissionInquiry, on_delete=models.SET_NULL, null=True, blank=True, related_name="applications")
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.SET_NULL, null=True, blank=True)
    term = models.ForeignKey(Term, on_delete=models.SET_NULL, null=True, blank=True)
    is_shortlisted = models.BooleanField(default=False)
    shortlisted_at = models.DateTimeField(null=True, blank=True)
    special_needs = models.TextField(blank=True)
    medical_notes = models.TextField(blank=True)
    languages = models.CharField(max_length=255, blank=True)
    emergency_contact_name = models.CharField(max_length=255, blank=True)
    emergency_contact_phone = models.CharField(max_length=30, blank=True)
    parent_id_number = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"ApplicationProfile<{self.application_id}>"


class AdmissionReview(models.Model):
    RECOMMENDATION_CHOICES = [
        ("Accept", "Accept"),
        ("Reject", "Reject"),
        ("Waitlist", "Waitlist"),
        ("Further Review", "Further Review"),
    ]

    application = models.ForeignKey(AdmissionApplication, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admissions_reviews",
    )
    academic_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    test_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    interview_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    overall_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    recommendation = models.CharField(max_length=20, choices=RECOMMENDATION_CHOICES, default="Further Review")
    comments = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-reviewed_at"]

    def __str__(self):
        return f"Review<{self.application_id}>:{self.recommendation}"


class AdmissionAssessment(models.Model):
    STATUS_CHOICES = [
        ("Scheduled", "Scheduled"),
        ("Completed", "Completed"),
        ("Missed", "Missed"),
    ]

    application = models.ForeignKey(AdmissionApplication, on_delete=models.CASCADE, related_name="assessments")
    scheduled_at = models.DateTimeField()
    venue = models.CharField(max_length=255, blank=True)
    score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    is_pass = models.BooleanField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Scheduled")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admissions_assessments_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-scheduled_at", "-created_at"]

    def __str__(self):
        return f"Assessment<{self.application_id}>:{self.status}"


class AdmissionInterview(models.Model):
    INTERVIEW_TYPE_CHOICES = [
        ("Phone", "Phone"),
        ("Video", "Video"),
        ("In-person", "In-person"),
    ]
    STATUS_CHOICES = [
        ("Scheduled", "Scheduled"),
        ("Completed", "Completed"),
        ("Cancelled", "Cancelled"),
        ("No-show", "No-show"),
    ]

    application = models.ForeignKey(AdmissionApplication, on_delete=models.CASCADE, related_name="interviews")
    interview_date = models.DateTimeField()
    interview_type = models.CharField(max_length=20, choices=INTERVIEW_TYPE_CHOICES, default="In-person")
    location = models.CharField(max_length=255, blank=True)
    panel = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Scheduled")
    feedback = models.TextField(blank=True)
    score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admissions_interviews_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-interview_date", "-created_at"]

    def __str__(self):
        return f"Interview<{self.application_id}>:{self.status}"


class AdmissionDecision(models.Model):
    DECISION_CHOICES = [
        ("Accept", "Accept"),
        ("Reject", "Reject"),
        ("Waitlist", "Waitlist"),
    ]
    RESPONSE_CHOICES = [
        ("Pending", "Pending"),
        ("Accepted", "Accepted"),
        ("Declined", "Declined"),
    ]

    application = models.OneToOneField(AdmissionApplication, on_delete=models.CASCADE, related_name="decision_record")
    decision = models.CharField(max_length=20, choices=DECISION_CHOICES)
    decision_date = models.DateField()
    decision_notes = models.TextField(blank=True)
    offer_deadline = models.DateField(null=True, blank=True)
    response_status = models.CharField(max_length=20, choices=RESPONSE_CHOICES, default="Pending")
    response_notes = models.TextField(blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admissions_decisions_made",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-decision_date", "-created_at"]

    def __str__(self):
        return f"Decision<{self.application_id}>:{self.decision}/{self.response_status}"
