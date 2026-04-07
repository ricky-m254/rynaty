from django.db.models import Count
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from school.permissions import HasModuleAccess
from .models import Dormitory, BedSpace, HostelAllocation, HostelAttendance, HostelLeave
from .serializers import (
    DormitorySerializer,
    BedSpaceSerializer,
    HostelAllocationSerializer,
    HostelAttendanceSerializer,
    HostelLeaveSerializer,
)

class DormitoryViewSet(viewsets.ModelViewSet):
    queryset = Dormitory.objects.all()
    serializer_class = DormitorySerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "HOSTEL"

class BedSpaceViewSet(viewsets.ModelViewSet):
    queryset = BedSpace.objects.all()
    serializer_class = BedSpaceSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "HOSTEL"
    filterset_fields = ['dormitory', 'is_occupied', 'is_active']

class HostelAllocationViewSet(viewsets.ModelViewSet):
    queryset = HostelAllocation.objects.all()
    serializer_class = HostelAllocationSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "HOSTEL"
    filterset_fields = ['term', 'status', 'bed__dormitory']

class HostelAttendanceViewSet(viewsets.ModelViewSet):
    queryset = HostelAttendance.objects.all()
    serializer_class = HostelAttendanceSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "HOSTEL"
    filterset_fields = ['date', 'roll_call_time', 'status']

class HostelLeaveViewSet(viewsets.ModelViewSet):
    queryset = HostelLeave.objects.all()
    serializer_class = HostelLeaveSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "HOSTEL"
    filterset_fields = ['status']

class HostelDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "HOSTEL"

    def get(self, request):
        # total beds, occupied, available per dormitory
        dormitories = Dormitory.objects.all()
        dorm_summary = []
        for dorm in dormitories:
            total_beds = dorm.beds.count()
            occupied_beds = dorm.beds.filter(is_occupied=True).count()
            dorm_summary.append({
                'id': dorm.id,
                'name': dorm.name,
                'total_beds': total_beds,
                'occupied_beds': occupied_beds,
                'available_beds': total_beds - occupied_beds
            })

        # tonight's attendance summary
        from django.utils import timezone
        today = timezone.now().date()
        attendance_today = HostelAttendance.objects.filter(date=today, roll_call_time='Night')
        attendance_summary = attendance_today.values('status').annotate(count=Count('status'))

        return Response({
            'dormitory_summary': dorm_summary,
            'tonight_attendance': attendance_summary,
            'total_active_allocations': HostelAllocation.objects.filter(status='Active').count()
        })
