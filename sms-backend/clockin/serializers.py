from rest_framework import serializers
from .networking import format_host_for_url, infer_ip_version
from .models import (
    BiometricDevice, SchoolShift, PersonRegistry, ClockEvent,
    SmartPSSSource, SmartPSSImportLog, AttendanceCaptureLog,
)

class BiometricDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = BiometricDevice
        fields = '__all__'
        read_only_fields = ('api_key', 'created_at')

    def validate(self, attrs):
        ip_address = attrs.get('ip_address')
        if ip_address:
            attrs['ip_version'] = infer_ip_version(ip_address, attrs.get('ip_version', 'ipv4'))
        return attrs

    def create(self, validated_data):
        import uuid
        if 'api_key' not in validated_data:
            validated_data['api_key'] = str(uuid.uuid4())
        return super().create(validated_data)

class SchoolShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolShift
        fields = '__all__'

class PersonRegistrySerializer(serializers.ModelSerializer):
    admission_number = serializers.ReadOnlyField(source='student.admission_number')
    employee_id = serializers.ReadOnlyField(source='employee.employee_id')
    student_name = serializers.SerializerMethodField()
    employee_name = serializers.SerializerMethodField()

    class Meta:
        model = PersonRegistry
        fields = '__all__'

    def get_student_name(self, obj):
        if obj.student:
            return f"{obj.student.first_name} {obj.student.last_name}"
        return None

    def get_employee_name(self, obj):
        if obj.employee:
            return f"{obj.employee.first_name} {obj.employee.last_name}"
        return None

class ClockEventSerializer(serializers.ModelSerializer):
    person_display_name = serializers.ReadOnlyField(source='person.display_name')
    device_name = serializers.ReadOnlyField(source='device.name')

    class Meta:
        model = ClockEvent
        fields = '__all__'


class SmartPSSSourceSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    api_url   = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model  = SmartPSSSource
        fields = [
            'id', 'name', 'ip_version', 'host', 'port', 'use_https', 'username', 'password',
            'device_model', 'sync_days_back', 'is_active', 'last_sync_at',
            'last_sync_result', 'notes', 'created_at', 'api_url',
        ]
        read_only_fields = ('created_at', 'last_sync_at', 'last_sync_result')

    def validate_host(self, value):
        cleaned = str(value or '').strip()
        if cleaned.startswith('[') and cleaned.endswith(']'):
            cleaned = cleaned[1:-1].strip()
        return cleaned

    def validate(self, attrs):
        host = attrs.get('host')
        if host:
            attrs['ip_version'] = infer_ip_version(host, attrs.get('ip_version', 'ipv4'))
        return attrs

    def get_api_url(self, obj):
        scheme = 'https' if obj.use_https else 'http'
        return f'{scheme}://{format_host_for_url(obj.host)}:{obj.port}/evo-apigw'


class SmartPSSImportLogSerializer(serializers.ModelSerializer):
    source_name = serializers.ReadOnlyField(source='source.name')

    class Meta:
        model  = SmartPSSImportLog
        fields = '__all__'


class AttendanceCaptureLogSerializer(serializers.ModelSerializer):
    device_name  = serializers.ReadOnlyField(source='device.name')
    device_ctx   = serializers.ReadOnlyField(source='device.use_context')
    person_name  = serializers.ReadOnlyField(source='person.display_name')
    person_type  = serializers.ReadOnlyField(source='person.person_type')

    class Meta:
        model  = AttendanceCaptureLog
        fields = [
            'id', 'device', 'device_name', 'device_ctx',
            'person', 'person_name', 'person_type',
            'method', 'identifier', 'timestamp',
            'status', 'failure_reason', 'created_at',
        ]
        read_only_fields = fields
