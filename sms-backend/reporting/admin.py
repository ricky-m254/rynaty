from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["timestamp", "action", "model_name", "object_id", "user_id"]
    list_filter = ["action", "model_name"]
    search_fields = ["object_id", "details"]
    readonly_fields = ["timestamp", "action", "model_name", "object_id", "details", "user_id"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
