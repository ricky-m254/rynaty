from rest_framework import serializers
from django.contrib.auth.models import User
from .models import TimetableSlot, StaffDutySlot, TimetableChangeRequest, LessonCoverage

class TimetableSlotSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    class_name = serializers.CharField(source='school_class.display_name', read_only=True)

    class Meta:
        model = TimetableSlot
        fields = '__all__'

class StaffDutySlotSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.__str__', read_only=True)

    class Meta:
        model = StaffDutySlot
        fields = '__all__'

class TimetableChangeRequestSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.CharField(source='requested_by.get_full_name', read_only=True)
    slot_display = serializers.CharField(source='slot.__str__', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.get_full_name', read_only=True)

    class Meta:
        model = TimetableChangeRequest
        fields = '__all__'

class LessonCoverageSerializer(serializers.ModelSerializer):
    slot_display = serializers.CharField(source='slot.__str__', read_only=True)
    original_teacher_name = serializers.CharField(source='original_teacher.get_full_name', read_only=True)
    covering_teacher_name = serializers.CharField(source='covering_teacher.get_full_name', read_only=True)

    class Meta:
        model = LessonCoverage
        fields = '__all__'
