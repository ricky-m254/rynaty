from django.db import models

class AlumniProfile(models.Model):
    student = models.ForeignKey('school.Student', null=True, blank=True, on_delete=models.SET_NULL)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    graduation_year = models.PositiveIntegerField()
    admission_number = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    current_institution = models.CharField(max_length=200, blank=True)
    current_occupation = models.CharField(max_length=200, blank=True)
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    linkedin_url = models.CharField(max_length=300, blank=True)
    bio = models.TextField(blank=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.graduation_year})"

class AlumniEvent(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    event_date = models.DateField()
    location = models.CharField(max_length=300, blank=True)
    is_virtual = models.BooleanField(default=False)
    meeting_link = models.CharField(max_length=500, blank=True)
    organizer = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class AlumniEventAttendee(models.Model):
    event = models.ForeignKey(AlumniEvent, on_delete=models.CASCADE, related_name='attendees')
    alumni = models.ForeignKey(AlumniProfile, on_delete=models.CASCADE)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('event', 'alumni')

    def __str__(self):
        return f"{self.alumni} attending {self.event}"


class AlumniMentorship(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open / Seeking Mentee'),
        ('matched', 'Matched'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('paused', 'Paused'),
    ]
    mentor = models.ForeignKey(AlumniProfile, on_delete=models.CASCADE, related_name='mentorships_as_mentor')
    mentee_name = models.CharField(max_length=200, blank=True, help_text="Name of student or alumni being mentored")
    mentee_type = models.CharField(max_length=20, choices=[('student', 'Student'), ('alumni', 'Alumni')], default='student')
    industry = models.CharField(max_length=100, blank=True)
    skills_offered = models.TextField(blank=True, help_text="Skills/areas mentor can help with")
    areas_of_interest = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    started_at = models.DateField(null=True, blank=True)
    ended_at = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.mentor} mentoring {self.mentee_name or 'TBD'} ({self.status})"


class AlumniDonation(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money (M-Pesa)'),
        ('cheque', 'Cheque'),
        ('online', 'Online / Card'),
    ]
    STATUS_CHOICES = [
        ('pledged', 'Pledged'),
        ('received', 'Received'),
        ('acknowledged', 'Acknowledged'),
        ('cancelled', 'Cancelled'),
    ]
    alumni = models.ForeignKey(AlumniProfile, on_delete=models.CASCADE, related_name='donations')
    campaign_name = models.CharField(max_length=200, default='General Fund')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default='KES')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='mobile_money')
    donation_date = models.DateField()
    reference = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='received')
    is_anonymous = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.alumni} donated {self.currency} {self.amount} ({self.campaign_name})"
