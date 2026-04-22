from rest_framework import serializers

from school.models import (
    StoreCategory,
    StoreItem,
    StoreOrderItem,
    StoreOrderRequest,
    StoreSupplier,
    StoreTransaction,
)


class StoreCategorySerializer(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = StoreCategory
        fields = ["id", "name", "description", "item_type", "is_active", "item_count", "created_at"]

    def get_item_count(self, obj):
        return obj.items.filter(is_active=True).count()


class StoreSupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreSupplier
        fields = [
            "id",
            "name",
            "contact_person",
            "phone",
            "email",
            "address",
            "product_types",
            "is_active",
            "created_at",
        ]


class StoreItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = StoreItem
        fields = [
            "id",
            "name",
            "sku",
            "category",
            "category_name",
            "unit",
            "item_type",
            "current_stock",
            "reorder_level",
            "max_stock",
            "cost_price",
            "is_active",
            "is_low_stock",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["current_stock"]


class StoreTransactionSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.name", read_only=True)
    item_unit = serializers.CharField(source="item.unit", read_only=True)
    performed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = StoreTransaction
        fields = [
            "id",
            "item",
            "item_name",
            "item_unit",
            "transaction_type",
            "quantity",
            "reference",
            "department",
            "purpose",
            "performed_by",
            "performed_by_name",
            "date",
            "notes",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def get_performed_by_name(self, obj):
        if obj.performed_by:
            return (
                f"{obj.performed_by.first_name} {obj.performed_by.last_name}".strip()
                or obj.performed_by.username
            )
        return ""


class StoreOrderItemSerializer(serializers.ModelSerializer):
    item_name_display = serializers.SerializerMethodField()

    class Meta:
        model = StoreOrderItem
        fields = [
            "id",
            "item",
            "item_name",
            "item_name_display",
            "unit",
            "quantity_requested",
            "quantity_approved",
            "quoted_unit_price",
            "approved_total",
            "notes",
        ]

    def get_item_name_display(self, obj):
        if obj.item:
            return obj.item.name
        return obj.item_name


class StoreOrderRequestSerializer(serializers.ModelSerializer):
    items = StoreOrderItemSerializer(many=True, read_only=True)
    supplier_name = serializers.SerializerMethodField()
    requested_by_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()
    received_by_name = serializers.SerializerMethodField()
    generated_expense_id = serializers.SerializerMethodField()
    procurement_type_label = serializers.CharField(source="get_procurement_type_display", read_only=True)
    office_owner_label = serializers.CharField(source="get_office_owner_display", read_only=True)
    receiving_state_label = serializers.CharField(source="get_receiving_state_display", read_only=True)

    class Meta:
        model = StoreOrderRequest
        fields = [
            "id",
            "request_code",
            "document_number",
            "title",
            "description",
            "requested_by",
            "requested_by_name",
            "supplier",
            "supplier_name",
            "procurement_type",
            "procurement_type_label",
            "office_owner",
            "office_owner_label",
            "send_to",
            "status",
            "approved_total",
            "receiving_state",
            "receiving_state_label",
            "received_by",
            "received_by_name",
            "received_at",
            "received_notes",
            "approval_trail",
            "notes",
            "reviewed_by",
            "reviewed_by_name",
            "reviewed_at",
            "generated_expense_id",
            "created_at",
            "updated_at",
            "items",
        ]
        read_only_fields = [
            "request_code",
            "document_number",
            "requested_by",
            "status",
            "approved_total",
            "receiving_state",
            "received_by",
            "received_at",
            "received_notes",
            "approval_trail",
            "reviewed_by",
            "reviewed_at",
            "generated_expense_id",
            "created_at",
            "updated_at",
        ]

    def get_generated_expense_id(self, obj):
        return obj.generated_expense_id

    def get_requested_by_name(self, obj):
        if obj.requested_by:
            return (
                f"{obj.requested_by.first_name} {obj.requested_by.last_name}".strip()
                or obj.requested_by.username
            )
        return ""

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return (
                f"{obj.reviewed_by.first_name} {obj.reviewed_by.last_name}".strip()
                or obj.reviewed_by.username
            )
        return ""

    def get_received_by_name(self, obj):
        if obj.received_by:
            return (
                f"{obj.received_by.first_name} {obj.received_by.last_name}".strip()
                or obj.received_by.username
            )
        return ""

    def get_supplier_name(self, obj):
        if obj.supplier:
            return obj.supplier.name
        return ""
