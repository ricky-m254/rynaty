from django.contrib import admin

from .models import ParentStudentLink


@admin.register(ParentStudentLink)
class ParentStudentLinkAdmin(admin.ModelAdmin):
    list_display = ("parent_user", "student", "guardian", "relationship", "is_primary", "is_active", "created_at")
    list_filter = ("is_primary", "is_active", "relationship")
    search_fields = ("parent_user__username", "parent_user__email", "student__admission_number", "student__first_name", "student__last_name")

