from django.contrib import admin
from .models import Staff


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ["first_name", "last_name", "employee_id", "role", "is_active"]
    search_fields = ["employee_id", "first_name", "last_name"]
    list_filter = ["role", "is_active"]
