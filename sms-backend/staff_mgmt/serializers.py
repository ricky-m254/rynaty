from rest_framework import serializers
from .models import (
    StaffMember,
    StaffQualification,
    StaffEmergencyContact,
    StaffDepartment,
    StaffRole,
    StaffAssignment,
    StaffAttendance,
    StaffObservation,
    StaffAppraisal,
    StaffDocument,
)


class StaffMemberSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    hr_employee = serializers.IntegerField(source="hr_employee_id", read_only=True)
    hr_employee_id = serializers.CharField(source="hr_employee.employee_id", read_only=True)

    class Meta:
        model = StaffMember
        fields = [
            "id",
            "user",
            "hr_employee",
            "hr_employee_id",
            "staff_id",
            "first_name",
            "middle_name",
            "last_name",
            "full_name",
            "photo",
            "date_of_birth",
            "gender",
            "nationality",
            "phone_primary",
            "phone_alternate",
            "email_personal",
            "email_work",
            "address_current",
            "address_permanent",
            "staff_type",
            "employment_type",
            "status",
            "join_date",
            "exit_date",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["staff_id", "full_name", "hr_employee", "hr_employee_id", "created_at", "updated_at"]

    def get_full_name(self, obj):
        employee = getattr(obj, "hr_employee", None)
        if employee:
            return " ".join(part for part in [employee.first_name, employee.middle_name, employee.last_name] if part).strip()
        return " ".join(part for part in [obj.first_name, obj.middle_name, obj.last_name] if part).strip()

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        employee = getattr(instance, "hr_employee", None)
        if not employee:
            return representation
        representation["user"] = employee.user_id
        representation["first_name"] = employee.first_name
        representation["middle_name"] = employee.middle_name
        representation["last_name"] = employee.last_name
        representation["full_name"] = " ".join(
            part for part in [employee.first_name, employee.middle_name, employee.last_name] if part
        ).strip()
        representation["date_of_birth"] = employee.date_of_birth.isoformat() if employee.date_of_birth else None
        representation["gender"] = employee.gender
        representation["nationality"] = employee.nationality
        representation["join_date"] = employee.join_date.isoformat() if employee.join_date else None
        representation["exit_date"] = employee.exit_date.isoformat() if employee.exit_date else None
        representation["is_active"] = employee.is_active
        return representation


class StaffQualificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffQualification
        fields = "__all__"


class StaffEmergencyContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffEmergencyContact
        fields = "__all__"


class StaffDepartmentSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source="parent.name", read_only=True)
    head_name = serializers.SerializerMethodField()
    hr_department = serializers.IntegerField(source="hr_department_id", read_only=True)
    school_department = serializers.IntegerField(source="hr_department.school_department_id", read_only=True)

    class Meta:
        model = StaffDepartment
        fields = [
            "id",
            "hr_department",
            "school_department",
            "name",
            "code",
            "department_type",
            "parent",
            "parent_name",
            "head",
            "head_name",
            "description",
            "is_active",
        ]
        read_only_fields = ["hr_department", "school_department", "parent_name", "head_name"]

    def get_head_name(self, obj):
        department = getattr(obj, "hr_department", None)
        if department and department.head:
            return f"{department.head.first_name} {department.head.last_name}".strip()
        if not obj.head:
            return ""
        return f"{obj.head.first_name} {obj.head.last_name}".strip()

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        department = getattr(instance, "hr_department", None)
        if not department:
            return representation
        representation["name"] = department.name
        representation["code"] = department.code
        representation["description"] = department.description
        representation["is_active"] = department.is_active
        representation["parent_name"] = department.parent.name if department.parent else ""
        if department.parent:
            parent_profile = getattr(department.parent, "staff_mgmt_profile", None)
            if parent_profile:
                representation["parent"] = parent_profile.id
        if department.head:
            head_profile = getattr(department.head, "staff_mgmt_profile", None)
            if head_profile:
                representation["head"] = head_profile.id
            representation["head_name"] = f"{department.head.first_name} {department.head.last_name}".strip()
        else:
            representation["head"] = None
            representation["head_name"] = ""
        return representation


class StaffRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffRole
        fields = "__all__"


class StaffAssignmentSerializer(serializers.ModelSerializer):
    staff_name = serializers.SerializerMethodField()
    department_name = serializers.CharField(source="department.name", read_only=True)
    role_name = serializers.CharField(source="role.name", read_only=True)

    class Meta:
        model = StaffAssignment
        fields = [
            "id",
            "staff",
            "staff_name",
            "department",
            "department_name",
            "role",
            "role_name",
            "is_primary",
            "effective_from",
            "effective_to",
            "is_active",
        ]
        read_only_fields = ["staff_name", "department_name", "role_name"]

    def get_staff_name(self, obj):
        return f"{obj.staff.first_name} {obj.staff.last_name}".strip()


class StaffAttendanceSerializer(serializers.ModelSerializer):
    staff_name = serializers.SerializerMethodField()
    hr_attendance = serializers.IntegerField(source="hr_attendance_id", read_only=True)
    hr_employee_id = serializers.CharField(source="staff.hr_employee.employee_id", read_only=True)

    class Meta:
        model = StaffAttendance
        fields = [
            "id",
            "hr_attendance",
            "hr_employee_id",
            "staff",
            "staff_name",
            "date",
            "status",
            "clock_in",
            "clock_out",
            "notes",
            "marked_by",
            "created_at",
            "is_active",
        ]
        read_only_fields = ["staff_name", "hr_attendance", "hr_employee_id", "marked_by", "created_at"]

    def get_staff_name(self, obj):
        employee = getattr(obj.staff, "hr_employee", None)
        if employee:
            return f"{employee.first_name} {employee.last_name}".strip()
        return f"{obj.staff.first_name} {obj.staff.last_name}".strip()

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        attendance = getattr(instance, "hr_attendance", None)
        if not attendance:
            return representation
        representation["status"] = attendance.status
        representation["clock_in"] = attendance.clock_in.isoformat() if attendance.clock_in else None
        representation["clock_out"] = attendance.clock_out.isoformat() if attendance.clock_out else None
        representation["notes"] = attendance.notes
        representation["is_active"] = attendance.is_active
        return representation


class StaffObservationSerializer(serializers.ModelSerializer):
    staff_name = serializers.SerializerMethodField()
    observer_name = serializers.SerializerMethodField()

    class Meta:
        model = StaffObservation
        fields = "__all__"
        read_only_fields = ["staff_name", "observer_name", "created_at"]

    def get_staff_name(self, obj):
        return f"{obj.staff.first_name} {obj.staff.last_name}".strip()

    def get_observer_name(self, obj):
        if not obj.observer:
            return ""
        return f"{obj.observer.first_name} {obj.observer.last_name}".strip()


class StaffAppraisalSerializer(serializers.ModelSerializer):
    staff_name = serializers.SerializerMethodField()
    appraiser_name = serializers.SerializerMethodField()

    class Meta:
        model = StaffAppraisal
        fields = "__all__"
        read_only_fields = ["staff_name", "appraiser_name", "created_at"]

    def get_staff_name(self, obj):
        return f"{obj.staff.first_name} {obj.staff.last_name}".strip()

    def get_appraiser_name(self, obj):
        if not obj.appraiser:
            return ""
        return f"{obj.appraiser.first_name} {obj.appraiser.last_name}".strip()


class StaffDocumentSerializer(serializers.ModelSerializer):
    staff_name = serializers.SerializerMethodField()
    uploaded_by_name = serializers.CharField(source="uploaded_by.username", read_only=True)
    verified_by_name = serializers.CharField(source="verified_by.username", read_only=True)

    class Meta:
        model = StaffDocument
        fields = "__all__"
        read_only_fields = ["staff_name", "uploaded_by_name", "verified_by_name", "uploaded_at"]

    def get_staff_name(self, obj):
        return f"{obj.staff.first_name} {obj.staff.last_name}".strip()
