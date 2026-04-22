from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from school.permissions import HasModuleAccess, request_has_approval_category
from .models import MaintenanceCategory, MaintenanceRequest, MaintenanceChecklist
from .serializers import MaintenanceCategorySerializer, MaintenanceRequestSerializer, MaintenanceChecklistSerializer

class MaintenanceCategoryViewSet(viewsets.ModelViewSet):
    queryset = MaintenanceCategory.objects.all().order_by('name')
    serializer_class = MaintenanceCategorySerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "MAINTENANCE"

class MaintenanceRequestViewSet(viewsets.ModelViewSet):
    queryset = MaintenanceRequest.objects.all().order_by('-created_at')
    serializer_class = MaintenanceRequestSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "MAINTENANCE"
    filterset_fields = ['category', 'priority', 'status', 'reported_by', 'assigned_to', 'asset']

    def perform_create(self, serializer):
        serializer.save(reported_by=self.request.user)

    def _approval_status_guard(self, request):
        target_status = str(request.data.get("status") or "").strip()
        if target_status not in {"Approved", "Rejected"}:
            return None
        if request_has_approval_category(request, "maintenance"):
            return None
        return Response(
            {"error": "You are not allowed to approve or reject maintenance requests."},
            status=status.HTTP_403_FORBIDDEN,
        )

    def update(self, request, *args, **kwargs):
        guarded_response = self._approval_status_guard(request)
        if guarded_response is not None:
            return guarded_response
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        guarded_response = self._approval_status_guard(request)
        if guarded_response is not None:
            return guarded_response
        return super().partial_update(request, *args, **kwargs)

class MaintenanceChecklistViewSet(viewsets.ModelViewSet):
    queryset = MaintenanceChecklist.objects.all().order_by('id')
    serializer_class = MaintenanceChecklistSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "MAINTENANCE"
    filterset_fields = ['request', 'is_completed']

class MaintenanceDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "MAINTENANCE"

    def get(self, request):
        total_requests = MaintenanceRequest.objects.count()
        pending = MaintenanceRequest.objects.filter(status='Pending').count()
        in_progress = MaintenanceRequest.objects.filter(status='In Progress').count()
        completed = MaintenanceRequest.objects.filter(status='Completed').count()
        high_priority_open = MaintenanceRequest.objects.filter(priority__in=['High', 'Urgent']).exclude(status='Completed').count()

        return Response({
            "total_requests": total_requests,
            "pending_requests": pending,
            "in_progress": in_progress,
            "completed_requests": completed,
            "high_priority_open": high_priority_open
        })
