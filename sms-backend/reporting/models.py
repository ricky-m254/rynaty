from django.db import models


class AuditLog(models.Model):
    """
    Unmanaged wrapper for school.AuditLog (pilot migration).
    """
    timestamp = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=50)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=50)
    details = models.TextField(blank=True)
    user_id = models.IntegerField(null=True)
    details = models.TextField(blank=True)

    class Meta:
        managed = False
        db_table = "school_auditlog"
