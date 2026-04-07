from rest_framework import serializers

from .models import (
    AcquisitionRequest,
    CirculationRule,
    CirculationTransaction,
    FineRecord,
    InventoryAudit,
    LibraryCategory,
    LibraryMember,
    LibraryResource,
    Reservation,
    ResourceCopy,
)


class LibraryCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = LibraryCategory
        fields = "__all__"


class LibraryResourceSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = LibraryResource
        fields = "__all__"
        read_only_fields = ["total_copies", "available_copies", "created_at"]


class ResourceCopySerializer(serializers.ModelSerializer):
    resource_title = serializers.CharField(source="resource.title", read_only=True)

    class Meta:
        model = ResourceCopy
        fields = "__all__"
        read_only_fields = ["created_at", "resource_title"]


class LibraryMemberSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)
    student_name = serializers.SerializerMethodField()
    student_admission_number = serializers.CharField(source="student.admission_number", read_only=True)

    class Meta:
        model = LibraryMember
        fields = "__all__"
        read_only_fields = ["created_at", "user_name", "total_fines"]

    def get_student_name(self, obj):
        if not obj.student_id:
            return ""
        return f"{obj.student.first_name} {obj.student.last_name}".strip()


class CirculationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CirculationRule
        fields = "__all__"


class CirculationTransactionSerializer(serializers.ModelSerializer):
    copy_accession_number = serializers.CharField(source="copy.accession_number", read_only=True)
    resource_title = serializers.CharField(source="copy.resource.title", read_only=True)
    member_member_id = serializers.CharField(source="member.member_id", read_only=True)
    member_name = serializers.SerializerMethodField()

    def get_member_name(self, obj):
        m = obj.member
        if not m:
            return ""
        if m.student:
            full = f"{m.student.first_name} {m.student.last_name}".strip()
            if full:
                return full
        if m.user:
            full = m.user.get_full_name().strip()
            return full or m.user.username
        return m.member_id

    class Meta:
        model = CirculationTransaction
        fields = "__all__"
        read_only_fields = [
            "created_at",
            "is_overdue",
            "overdue_days",
            "fine_amount",
            "copy_accession_number",
            "resource_title",
            "member_member_id",
            "member_name",
        ]


class ReservationSerializer(serializers.ModelSerializer):
    resource_title = serializers.CharField(source="resource.title", read_only=True)
    member_member_id = serializers.CharField(source="member.member_id", read_only=True)

    class Meta:
        model = Reservation
        fields = "__all__"
        read_only_fields = [
            "reserved_at",
            "ready_at",
            "pickup_deadline",
            "picked_at",
            "cancelled_at",
            "queue_position",
            "resource_title",
            "member_member_id",
        ]


class FineRecordSerializer(serializers.ModelSerializer):
    member_member_id = serializers.CharField(source="member.member_id", read_only=True)
    transaction_copy = serializers.CharField(source="transaction.copy.accession_number", read_only=True)

    class Meta:
        model = FineRecord
        fields = "__all__"
        read_only_fields = ["created_at", "paid_at", "member_member_id", "transaction_copy"]


class InventoryAuditSerializer(serializers.ModelSerializer):
    conducted_by_name = serializers.CharField(source="conducted_by.username", read_only=True)

    class Meta:
        model = InventoryAudit
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "conducted_by", "conducted_by_name"]


class AcquisitionRequestSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.CharField(source="requested_by.username", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.username", read_only=True)

    class Meta:
        model = AcquisitionRequest
        fields = "__all__"
        read_only_fields = [
            "created_at",
            "updated_at",
            "requested_by",
            "requested_by_name",
            "approved_by",
            "approved_by_name",
        ]
