from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from school.permissions import HasModuleAccess
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
