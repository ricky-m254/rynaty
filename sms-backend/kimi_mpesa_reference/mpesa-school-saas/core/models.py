"""
Core models and base classes for multi-tenant architecture.
"""

from django.db import models


class TenantModel(models.Model):
    """
    Abstract base model for all tenant-scoped models.
    
    All models that belong to a specific school should inherit from this.
    This ensures proper data isolation and indexing.
    """
    
    school = models.ForeignKey(
        'schools.School', 
        on_delete=models.CASCADE, 
        db_index=True,
        help_text='The school this record belongs to'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['school', 'created_at']),
            models.Index(fields=['school', 'updated_at']),
        ]

    @classmethod
    def for_school(cls, school):
        """Get all records for a specific school."""
        return cls.objects.filter(school=school)
    
    @classmethod
    def for_request(cls, request):
        """Get all records for the current request's school."""
        if hasattr(request, 'school') and request.school:
            return cls.for_school(request.school)
        return cls.objects.none()


class TimeStampedModel(models.Model):
    """
    Abstract base model with automatic timestamp fields.
    Use for non-tenant models that still need timestamps.
    """
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    """
    Abstract base model with soft delete functionality.
    Records are marked as deleted but not actually removed.
    """
    
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        'auth.User', 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        related_name='deleted_%(class)s'
    )

    class Meta:
        abstract = True
    
    def soft_delete(self, user=None):
        """Mark record as deleted without removing from database."""
        from django.utils import timezone
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])
    
    def restore(self):
        """Restore a soft-deleted record."""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])
    
    @classmethod
    def active(cls):
        """Get only non-deleted records."""
        return cls.objects.filter(is_deleted=False)
    
    @classmethod
    def deleted(cls):
        """Get only deleted records."""
        return cls.objects.filter(is_deleted=True)
