from __future__ import annotations

from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.inventory.application.services import (
    InventoryNotFoundError,
    InventoryValidationError,
    StoreDashboardService,
    StoreOrderWorkflowService,
    StoreReportsService,
)
from domains.inventory.infrastructure.django_store_repository import DjangoStoreRepository
from domains.inventory.presentation.serializers import (
    StoreCategorySerializer,
    StoreItemSerializer,
    StoreOrderRequestSerializer,
    StoreSupplierSerializer,
    StoreTransactionSerializer,
)
from school.permissions import HasModuleAccess


def _parse_optional_bool(raw_value: str | None) -> bool | None:
    if raw_value is None:
        return None
    return raw_value.lower() == "true"


class InventoryRepositoryMixin:
    repository_class = DjangoStoreRepository

    def get_repository(self) -> DjangoStoreRepository:
        return self.repository_class()


class StoreCategoryViewSet(InventoryRepositoryMixin, viewsets.ModelViewSet):
    serializer_class = StoreCategorySerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STORE"

    def get_queryset(self):
        return self.get_repository().list_categories(
            item_type=self.request.query_params.get("item_type"),
            is_active=_parse_optional_bool(self.request.query_params.get("is_active")),
        )


class StoreSupplierViewSet(InventoryRepositoryMixin, viewsets.ModelViewSet):
    serializer_class = StoreSupplierSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STORE"

    def get_queryset(self):
        return self.get_repository().list_suppliers(
            is_active=_parse_optional_bool(self.request.query_params.get("is_active")),
            search=self.request.query_params.get("search"),
        )


class StoreItemViewSet(InventoryRepositoryMixin, viewsets.ModelViewSet):
    serializer_class = StoreItemSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STORE"

    def get_queryset(self):
        return self.get_repository().list_items(
            item_type=self.request.query_params.get("item_type") or self.request.query_params.get("type"),
            low_stock=(self.request.query_params.get("low_stock") or "").lower() == "true",
            is_active=_parse_optional_bool(self.request.query_params.get("is_active")),
            search=self.request.query_params.get("search"),
        )


class StoreTransactionViewSet(InventoryRepositoryMixin, viewsets.ModelViewSet):
    serializer_class = StoreTransactionSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STORE"

    def get_queryset(self):
        return self.get_repository().list_transactions(
            item_id=self.request.query_params.get("item"),
            transaction_type=self.request.query_params.get("transaction_type"),
            department=self.request.query_params.get("department"),
            date_from=self.request.query_params.get("date_from"),
            date_to=self.request.query_params.get("date_to"),
        )

    def perform_create(self, serializer):
        serializer.save(performed_by=self.request.user)


class StoreOrderRequestViewSet(InventoryRepositoryMixin, viewsets.ModelViewSet):
    serializer_class = StoreOrderRequestSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STORE"

    def get_queryset(self):
        return self.get_repository().list_orders(
            status=self.request.query_params.get("status"),
            send_to=self.request.query_params.get("send_to"),
        )

    def perform_create(self, serializer):
        order = serializer.save(requested_by=self.request.user)
        service = StoreOrderWorkflowService(self.get_repository())
        service.create_order_items(order=order, payload=self.request.data)

    @action(detail=True, methods=["post"], url_path="generate-expense")
    def generate_expense(self, request, pk=None):
        service = StoreOrderWorkflowService(self.get_repository())
        try:
            payload = service.generate_expense(order_id=int(pk))
        except InventoryNotFoundError as exc:
            return Response({"detail": str(exc)}, status=404)
        except InventoryValidationError as exc:
            return Response({"error": str(exc)}, status=400)
        return Response(payload, status=200)


class StoreOrderReviewView(InventoryRepositoryMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STORE"

    def patch(self, request, pk):
        service = StoreOrderWorkflowService(self.get_repository())
        try:
            payload = service.review_order(
                order_id=pk,
                payload=request.data,
                reviewer=request.user,
            )
        except InventoryNotFoundError as exc:
            return Response({"detail": str(exc)}, status=404)
        except InventoryValidationError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(payload)

    post = patch


class StoreDashboardView(InventoryRepositoryMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STORE"

    def get(self, request):
        service = StoreDashboardService(self.get_repository())
        return Response(service.get_dashboard())


class StoreReportsView(InventoryRepositoryMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STORE"

    def get(self, request):
        service = StoreReportsService(self.get_repository())
        return Response(service.get_reports())
