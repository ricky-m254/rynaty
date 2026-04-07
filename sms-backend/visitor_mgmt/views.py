from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from school.permissions import HasModuleAccess
from .models import Visitor, AuthorizedPickup, StudentPickupLog
from .serializers import VisitorSerializer, AuthorizedPickupSerializer, StudentPickupLogSerializer

class VisitorViewSet(viewsets.ModelViewSet):
    queryset = Visitor.objects.all()
    serializer_class = VisitorSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "VISITOR_MGMT"
    filterset_fields = ['status', 'date', 'visitor_type']

    @action(detail=True, methods=['post'])
    def sign_out(self, request, pk=None):
        visitor = self.get_object()
        visitor.sign_out_time = timezone.now()
        visitor.status = 'Out'
        visitor.save()
        return Response(self.get_serializer(visitor).data)

class AuthorizedPickupViewSet(viewsets.ModelViewSet):
    queryset = AuthorizedPickup.objects.all()
    serializer_class = AuthorizedPickupSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "VISITOR_MGMT"
    filterset_fields = ['student', 'is_active']

class StudentPickupLogViewSet(viewsets.ModelViewSet):
    queryset = StudentPickupLog.objects.all()
    serializer_class = StudentPickupLogSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "VISITOR_MGMT"
    filterset_fields = ['date', 'student']

class VisitorDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "VISITOR_MGMT"

    def get(self, request):
        today = timezone.now().date()
        today_visitors = Visitor.objects.filter(date=today)
        return Response({
            "visitors_in": today_visitors.filter(status='In').count(),
            "visitors_out": today_visitors.filter(status='Out').count(),
        })
