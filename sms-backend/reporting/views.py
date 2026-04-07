from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response

from school.permissions import HasModuleAccess
from school.permissions import IsSchoolAdmin, IsAccountant
from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogRefView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "REPORTING"

    def get(self, request):
        data = AuditLog.objects.values(
            "id", "timestamp", "action", "model_name", "object_id", "user_id"
        ).order_by("-timestamp")
        return Response(list(data), status=status.HTTP_200_OK)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all().order_by("-timestamp")
    serializer_class = AuditLogSerializer
    permission_classes = [IsSchoolAdmin | IsAccountant, HasModuleAccess]
    module_key = "REPORTING"
