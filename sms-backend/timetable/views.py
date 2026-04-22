from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from django.db.models import Q
from school.permissions import HasModuleAccess, request_has_approval_category
from .models import TimetableSlot, StaffDutySlot, TimetableChangeRequest, LessonCoverage
from .serializers import (
    TimetableSlotSerializer, 
    StaffDutySlotSerializer, 
    TimetableChangeRequestSerializer, 
    LessonCoverageSerializer
)
from clockin.views import _notify_admins

class TimetableModuleMixin:
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "TIMETABLE"

class TimetableSlotViewSet(TimetableModuleMixin, viewsets.ModelViewSet):
    queryset = TimetableSlot.objects.filter(is_active=True)
    serializer_class = TimetableSlotSerializer
    filterset_fields = ['day_of_week', 'teacher', 'school_class', 'term']

class StaffDutySlotViewSet(TimetableModuleMixin, viewsets.ModelViewSet):
    queryset = StaffDutySlot.objects.filter(is_active=True)
    serializer_class = StaffDutySlotSerializer
    filterset_fields = ['day_of_week', 'employee']

class TimetableChangeRequestViewSet(TimetableModuleMixin, viewsets.ModelViewSet):
    queryset = TimetableChangeRequest.objects.all()
    serializer_class = TimetableChangeRequestSerializer
    filterset_fields = ['status', 'requested_by', 'request_type']

    def perform_create(self, serializer):
        instance = serializer.save(requested_by=self.request.user)
        _notify_admins(
            title=f"New Timetable Change Request",
            message=f"New timetable change request from {self.request.user.get_full_name() or self.request.user.username}",
            priority='Important',
            action_url='/modules/timetable/change-requests'
        )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        if not request_has_approval_category(request, "timetable"):
            return Response(
                {"error": "You are not allowed to approve or reject timetable change requests."},
                status=status.HTTP_403_FORBIDDEN,
            )
        instance = self.get_object()
        instance.status = 'Approved'
        instance.reviewed_by = request.user
        instance.reviewed_at = timezone.now()
        instance.review_notes = request.data.get('review_notes', '')
        instance.save()

        # Business Logic for approval
        if instance.request_type == 'SWAP_SLOT' and instance.slot and instance.swap_with_slot:
            t1 = instance.slot.teacher
            t2 = instance.swap_with_slot.teacher
            instance.slot.teacher = t2
            instance.swap_with_slot.teacher = t1
            instance.slot.save()
            instance.swap_with_slot.save()
        elif instance.request_type == 'CHANGE_TIME' and instance.slot:
            instance.slot.start_time = instance.proposed_start_time
            instance.slot.end_time = instance.proposed_end_time
            instance.slot.save()
        elif instance.request_type == 'CHANGE_TEACHER' and instance.slot:
            instance.slot.teacher = instance.proposed_teacher
            instance.slot.save()
        elif instance.request_type == 'DUTY_CHANGE' and instance.duty_slot:
            instance.duty_slot.duty_start = instance.proposed_start_time
            instance.duty_slot.duty_end = instance.proposed_end_time
            instance.duty_slot.save()

        # Notify requester
        from communication.models import Notification
        Notification.objects.create(
            recipient=instance.requested_by,
            notification_type='System',
            title="Timetable Request Approved",
            message="Your timetable change request was approved",
            priority='Important',
            delivery_status='Sent',
        )

        return Response({'status': 'Approved'})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        if not request_has_approval_category(request, "timetable"):
            return Response(
                {"error": "You are not allowed to approve or reject timetable change requests."},
                status=status.HTTP_403_FORBIDDEN,
            )
        instance = self.get_object()
        instance.status = 'Rejected'
        instance.reviewed_by = request.user
        instance.reviewed_at = timezone.now()
        instance.review_notes = request.data.get('review_notes', '')
        instance.save()

        # Notify requester
        from communication.models import Notification
        Notification.objects.create(
            recipient=instance.requested_by,
            notification_type='System',
            title="Timetable Request Rejected",
            message="Your timetable change request was rejected",
            priority='Important',
            delivery_status='Sent',
        )

        return Response({'status': 'Rejected'})

class LessonCoverageViewSet(TimetableModuleMixin, viewsets.ModelViewSet):
    queryset = LessonCoverage.objects.all()
    serializer_class = LessonCoverageSerializer
    filterset_fields = ['date', 'status', 'slot__teacher']

class WeeklyGridView(TimetableModuleMixin, APIView):
    def get(self, request):
        class_id = request.query_params.get('class_id')
        teacher_id = request.query_params.get('teacher_id')
        
        queryset = TimetableSlot.objects.filter(is_active=True)
        if class_id:
            queryset = queryset.filter(school_class_id=class_id)
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)
            
        slots = TimetableSlotSerializer(queryset, many=True).data
        
        # Group by day
        days = {1: [], 2: [], 3: [], 4: [], 5: []}
        for slot in slots:
            days[slot['day_of_week']].append(slot)
            
        return Response(days)

class MyScheduleView(TimetableModuleMixin, APIView):
    def get(self, request):
        user = request.user
        today = timezone.now().date()
        
        slots = TimetableSlot.objects.filter(teacher=user, is_active=True)
        coverage = LessonCoverage.objects.filter(original_teacher=user, date=today)
        
        return Response({
            'slots': TimetableSlotSerializer(slots, many=True).data,
            'coverage_today': LessonCoverageSerializer(coverage, many=True).data
        })

class TodayCoverageView(TimetableModuleMixin, APIView):
    def get(self, request):
        today = timezone.now().date()
        weekday = today.isoweekday() # 1-7
        
        if weekday > 5:
            return Response({'message': 'No lessons today (Weekend)', 'uncovered': []})
            
        slots = TimetableSlot.objects.filter(day_of_week=weekday, is_active=True)
        uncovered = LessonCoverage.objects.filter(date=today, status='Uncovered')
        
        return Response({
            'all_slots_today': TimetableSlotSerializer(slots, many=True).data,
            'uncovered': LessonCoverageSerializer(uncovered, many=True).data
        })
