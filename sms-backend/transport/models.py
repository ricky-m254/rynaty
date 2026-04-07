from django.db import models

class Vehicle(models.Model):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Maintenance', 'Under Maintenance'),
        ('Retired', 'Retired'),
    ]
    registration = models.CharField(max_length=20, unique=True)
    make = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)
    capacity = models.PositiveIntegerField(default=40)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    driver = models.ForeignKey('hr.Employee', null=True, blank=True, on_delete=models.SET_NULL)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.registration} ({self.model})"

class Route(models.Model):
    DIRECTION_CHOICES = [
        ('MORNING', 'Morning Pick-Up'),
        ('EVENING', 'Evening Drop-Off'),
        ('BOTH', 'Both'),
    ]
    name = models.CharField(max_length=150)
    vehicle = models.ForeignKey(Vehicle, null=True, blank=True, on_delete=models.SET_NULL)
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES, default='BOTH')
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class RouteStop(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='stops')
    stop_name = models.CharField(max_length=150)
    sequence = models.PositiveIntegerField(default=1)
    estimated_time = models.CharField(max_length=20, blank=True, help_text="e.g. 07:15")
    landmark = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['sequence']

    def __str__(self):
        return f"{self.stop_name} ({self.route.name})"

class StudentTransport(models.Model):
    student = models.ForeignKey('school.Student', on_delete=models.CASCADE, related_name='transport_assignments')
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    boarding_stop = models.ForeignKey(RouteStop, null=True, blank=True, on_delete=models.SET_NULL)
    is_active = models.BooleanField(default=True)
    term = models.ForeignKey('academics.Term', null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'term')

class TransportIncident(models.Model):
    SEVERITY_CHOICES = [
        ('Minor', 'Minor'),
        ('Major', 'Major'),
        ('Critical', 'Critical'),
    ]
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE)
    incident_date = models.DateField()
    description = models.TextField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='Minor')
    reported_by = models.CharField(max_length=150, blank=True)
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
