from django.conf import settings
from django.db import models


class ParentStudentLink(models.Model):
    parent_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="parent_student_links",
    )
    student = models.ForeignKey(
        "school.Student",
        on_delete=models.CASCADE,
        related_name="parent_links",
    )
    guardian = models.ForeignKey(
        "school.Guardian",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="parent_links",
    )
    relationship = models.CharField(max_length=80, blank=True)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_parent_student_links",
    )

    class Meta:
        ordering = ["-is_primary", "-created_at", "-id"]
        unique_together = ("parent_user", "student")

    def __str__(self):
        return f"{self.parent_user_id} -> {self.student_id}"

