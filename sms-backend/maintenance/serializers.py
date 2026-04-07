from rest_framework import serializers
from .models import MaintenanceCategory, MaintenanceRequest, MaintenanceChecklist

class MaintenanceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintenanceCategory
        fields = '__all__'

class MaintenanceChecklistSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintenanceChecklist
        fields = '__all__'

class MaintenanceRequestSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    reported_by_name = serializers.SerializerMethodField()
    assigned_to_name = serializers.SerializerMethodField()
    asset_name = serializers.SerializerMethodField()
    checklist_items = MaintenanceChecklistSerializer(many=True, read_only=True)

    class Meta:
        model = MaintenanceRequest
        fields = '__all__'
        extra_kwargs = {
            'reported_by': {'required': False},
        }

    def get_reported_by_name(self, obj):
        return obj.reported_by.username if obj.reported_by_id else ''

    def get_assigned_to_name(self, obj):
        if obj.assigned_to_id:
            return f"{obj.assigned_to.first_name} {obj.assigned_to.last_name}".strip()
        return ''

    def get_asset_name(self, obj):
        return obj.asset.name if obj.asset_id else ''
