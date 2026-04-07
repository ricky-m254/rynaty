from rest_framework import serializers
from .models import Dormitory, BedSpace, HostelAllocation, HostelAttendance, HostelLeave


class DormitorySerializer(serializers.ModelSerializer):
    warden_name = serializers.SerializerMethodField()

    class Meta:
        model = Dormitory
        fields = '__all__'

    def get_warden_name(self, obj):
        if obj.warden:
            return f"{obj.warden.first_name} {obj.warden.last_name}".strip() or str(obj.warden)
        return None


class BedSpaceSerializer(serializers.ModelSerializer):
    dormitory_name = serializers.CharField(source='dormitory.name', read_only=True)

    class Meta:
        model = BedSpace
        fields = '__all__'


class HostelAllocationSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    dormitory_name = serializers.SerializerMethodField()
    bed_number = serializers.SerializerMethodField()
    term_name = serializers.SerializerMethodField()

    class Meta:
        model = HostelAllocation
        fields = '__all__'

    def get_student_name(self, obj):
        if obj.student:
            return f"{obj.student.first_name} {obj.student.last_name}".strip()
        return None

    def get_dormitory_name(self, obj):
        if obj.bed and obj.bed.dormitory:
            return obj.bed.dormitory.name
        return None

    def get_bed_number(self, obj):
        return obj.bed.bed_number if obj.bed else None

    def get_term_name(self, obj):
        return obj.term.name if obj.term else None


class HostelAttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    recorded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = HostelAttendance
        fields = '__all__'

    def get_student_name(self, obj):
        if obj.student:
            return f"{obj.student.first_name} {obj.student.last_name}".strip()
        return None

    def get_recorded_by_name(self, obj):
        if obj.recorded_by:
            return obj.recorded_by.get_full_name() or obj.recorded_by.username
        return None


class HostelLeaveSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()

    class Meta:
        model = HostelLeave
        fields = '__all__'

    def get_student_name(self, obj):
        if obj.student:
            return f"{obj.student.first_name} {obj.student.last_name}".strip()
        return None

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return obj.approved_by.get_full_name() or obj.approved_by.username
        return None
