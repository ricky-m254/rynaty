from django.db import models
from django.utils import timezone

class Visitor(models.Model):
    VISITOR_TYPE_CHOICES = [
        ('Parent', 'Parent'),
        ('Contractor', 'Contractor'),
        ('Official', 'Official'),
        ('Other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('In', 'Signed In'),
        ('Out', 'Signed Out'),
    ]
    full_name = models.CharField(max_length=200)
    id_number = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    visitor_type = models.CharField(max_length=20, choices=VISITOR_TYPE_CHOICES, default='Other')
    purpose = models.TextField()
    host_name = models.CharField(max_length=200, blank=True, help_text="Person/dept being visited")
    badge_number = models.CharField(max_length=20, blank=True)
    sign_in_time = models.DateTimeField(auto_now_add=True)
    sign_out_time = models.DateTimeField(null=True, blank=True)
    date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='In')
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.full_name} - {self.date}"

class AuthorizedPickup(models.Model):
    student = models.ForeignKey('school.Student', on_delete=models.CASCADE, related_name='authorized_pickups')
    guardian_name = models.CharField(max_length=200)
    relationship = models.CharField(max_length=100)
    id_number = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    photo_url = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.guardian_name} ({self.student.full_name})"

class StudentPickupLog(models.Model):
    student = models.ForeignKey('school.Student', on_delete=models.CASCADE)
    picked_up_by = models.ForeignKey(AuthorizedPickup, null=True, blank=True, on_delete=models.SET_NULL)
    unauthorized_name = models.CharField(max_length=200, blank=True, help_text="If not in authorized list")
    pickup_time = models.DateTimeField(auto_now_add=True)
    date = models.DateField(auto_now_add=True)
    authorized = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.student.full_name} picked up at {self.pickup_time}"
