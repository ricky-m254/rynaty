from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

class Dormitory(models.Model):
    GENDER_CHOICES = [('Male','Male'),('Female','Female'),('Mixed','Mixed')]
    name = models.CharField(max_length=100, unique=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, default='Male')
    capacity = models.PositiveIntegerField(default=50)
    warden = models.ForeignKey('hr.Employee', null=True, blank=True, on_delete=models.SET_NULL)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.name

class BedSpace(models.Model):
    dormitory = models.ForeignKey(Dormitory, on_delete=models.CASCADE, related_name='beds')
    bed_number = models.CharField(max_length=20)
    is_occupied = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('dormitory', 'bed_number')

    def __str__(self):
        return f"{self.dormitory.name} - {self.bed_number}"

class HostelAllocation(models.Model):
    STATUS_CHOICES = [('Active','Active'),('Checked Out','Checked Out')]
    student = models.ForeignKey('school.Student', on_delete=models.CASCADE, related_name='hostel_allocations')
    bed = models.ForeignKey(BedSpace, on_delete=models.SET_NULL, null=True)
    term = models.ForeignKey('academics.Term', null=True, blank=True, on_delete=models.SET_NULL)
    check_in_date = models.DateField()
    check_out_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.bed:
            if self.status == 'Active':
                self.bed.is_occupied = True
            elif self.status == 'Checked Out':
                self.bed.is_occupied = False
            self.bed.save()

    def __str__(self):
        return f"{self.student} - {self.bed}"

class HostelAttendance(models.Model):
    TIME_CHOICES = [('Morning','Morning'),('Evening','Evening'),('Night','Night')]
    STATUS_CHOICES = [('Present','Present'),('Absent','Absent'),('Leave','On Leave')]
    student = models.ForeignKey('school.Student', on_delete=models.CASCADE)
    date = models.DateField()
    roll_call_time = models.CharField(max_length=20, choices=TIME_CHOICES, default='Night')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Present')
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'date', 'roll_call_time')

class HostelLeave(models.Model):
    STATUS_CHOICES = [('Pending','Pending'),('Approved','Approved'),('Rejected','Rejected')]
    student = models.ForeignKey('school.Student', on_delete=models.CASCADE)
    leave_from = models.DateField()
    leave_to = models.DateField()
    reason = models.TextField()
    approved_by = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
