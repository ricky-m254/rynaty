from django.db import models

class PTMSession(models.Model):
    title = models.CharField(max_length=200)
    date = models.DateField()
    venue = models.CharField(max_length=200, blank=True)
    term = models.ForeignKey('academics.Term', null=True, blank=True, on_delete=models.SET_NULL)
    slot_duration_minutes = models.PositiveIntegerField(default=15)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_virtual = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.date})"

class PTMSlot(models.Model):
    session = models.ForeignKey(PTMSession, on_delete=models.CASCADE, related_name='slots')
    teacher = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='ptm_slots')
    slot_time = models.TimeField()
    is_booked = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.teacher.username} - {self.slot_time}"

class PTMBooking(models.Model):
    STATUS_CHOICES = [('Confirmed','Confirmed'),('Cancelled','Cancelled'),('Completed','Completed')]
    slot = models.ForeignKey(PTMSlot, on_delete=models.CASCADE, related_name='bookings')
    student = models.ForeignKey('school.Student', on_delete=models.CASCADE)
    parent_name = models.CharField(max_length=200)
    parent_phone = models.CharField(max_length=20, blank=True)
    parent_email = models.EmailField(blank=True)
    notes = models.TextField(blank=True)
    meeting_notes = models.TextField(blank=True, help_text="Notes recorded during meeting")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Confirmed')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('slot', 'student')

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.status == 'Confirmed':
            self.slot.is_booked = True
        elif self.status == 'Cancelled':
            # Check if there are other confirmed bookings for this slot (unlikely but safe)
            if not PTMBooking.objects.filter(slot=self.slot, status='Confirmed').exclude(pk=self.pk).exists():
                self.slot.is_booked = False
        self.slot.save()

    def __str__(self):
        return f"{self.student} - {self.slot.slot_time}"
