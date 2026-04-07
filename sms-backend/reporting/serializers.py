from rest_framework import serializers
from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = [
            "id", "timestamp", "action", "model_name",
            "object_id", "user_id", "details"
        ]
        read_only_fields = fields
