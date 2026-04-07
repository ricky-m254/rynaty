from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class TimetableSlot(models.Model):
    DAY_CHOICES = [
        (1, 'Monday'),
        (2, 'Tuesday'),
        (3, 'Wednesday'),
        (4, 'Thursday'),
        (5, 'Friday'),
    ]
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    period_number = models.PositiveIntegerField(default=1)
    start_time = models.TimeField()
    end_time = models.TimeField()
    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='timetable_slots')
    subject = models.ForeignKey('school.Subject', on_delete=models.SET_NULL, null=True, blank=True)
    school_class = models.ForeignKey('school.SchoolClass', on_delete=models.SET_NULL, null=True, blank=True)
    room = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    term = models.ForeignKey('school.Term', on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['day_of_week', 'period_number']

    def __str__(self):
        return f"{self.get_day_of_week_display()} Period {self.period_number} - {self.subject}"

class StaffDutySlot(models.Model):
    DAY_CHOICES = [
        (1, 'Monday'),
        (2, 'Tuesday'),
        (3, 'Wednesday'),
        (4, 'Thursday'),
        (5, 'Friday'),
    ]
    employee = models.ForeignKey('hr.Employee', on_delete=models.CASCADE, related_name='duty_slots')
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    duty_start = models.TimeField()
    duty_end = models.TimeField()
    location = models.CharField(max_length=150, blank=True)
    description = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    term = models.ForeignKey('school.Term', on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['day_of_week', 'duty_start']

    def __str__(self):
        return f"{self.employee} - {self.get_day_of_week_display()} duty"

class TimetableChangeRequest(models.Model):
    TYPE_CHOICES = [
        ('SWAP_SLOT', 'Swap Two Periods'),
        ('CHANGE_TIME', 'Change Lesson Time'),
        ('CHANGE_TEACHER', 'Reassign Teacher'),
        ('DUTY_CHANGE', 'Staff Duty Change'),
    ]
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]
    request_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='timetable_requests')
    slot = models.ForeignKey(TimetableSlot, on_delete=models.SET_NULL, null=True, blank=True)
    duty_slot = models.ForeignKey(StaffDutySlot, on_delete=models.SET_NULL, null=True, blank=True)
    swap_with_slot = models.ForeignKey(TimetableSlot, on_delete=models.SET_NULL, null=True, blank=True, related_name='swap_requests')
    proposed_day = models.IntegerField(null=True, blank=True)
    proposed_start_time = models.TimeField(null=True, blank=True)
    proposed_end_time = models.TimeField(null=True, blank=True)
    proposed_teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='proposed_for_slots')
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_requests')
    review_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

class LessonCoverage(models.Model):
    STATUS_CHOICES = [
        ('Uncovered', 'Uncovered'),
        ('Covered', 'Covered'),
        ('Cancelled', 'Cancelled'),
    ]
    slot = models.ForeignKey(TimetableSlot, on_delete=models.CASCADE, related_name='coverages')
    date = models.DateField()
    original_teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='coverages_as_original')
    covering_teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='coverages_as_cover')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Uncovered')
    notes = models.TextField(blank=True)
    auto_flagged = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('slot', 'date')
        ordering = ['-date']
