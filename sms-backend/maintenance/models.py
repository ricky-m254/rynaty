from django.db import models

class MaintenanceCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return str(self.name)

class MaintenanceRequest(models.Model):
    PRIORITY_CHOICES = [
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Urgent', 'Urgent'),
    ]
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Needs Info', 'Clarification Requested'),
        ('In Progress', 'In Progress'),
        ('On Hold', 'On Hold'),
        ('Completed', 'Completed'),
        ('Rejected', 'Rejected'),
    ]
    
    title = models.CharField(max_length=200)
    category = models.ForeignKey(MaintenanceCategory, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='Medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    location = models.CharField(max_length=200, blank=True, help_text="Room, Block, or Area")
    reported_by = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='maintenance_reports')
    assigned_to = models.ForeignKey('hr.Employee', null=True, blank=True, on_delete=models.SET_NULL, related_name='maintenance_tasks')
    asset = models.ForeignKey('assets.Asset', null=True, blank=True, on_delete=models.SET_NULL, related_name='maintenance_requests')
    due_date = models.DateField(null=True, blank=True)
    completed_date = models.DateField(null=True, blank=True)
    cost_estimate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    actual_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.status})"

class MaintenanceChecklist(models.Model):
    request = models.ForeignKey(MaintenanceRequest, on_delete=models.CASCADE, related_name='checklist_items')
    task_description = models.CharField(max_length=300)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.task_description} - {'Done' if self.is_completed else 'Pending'}"
