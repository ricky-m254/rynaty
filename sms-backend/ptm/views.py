from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from school.permissions import HasModuleAccess
from .models import PTMSession, PTMSlot, PTMBooking
from .serializers import (
    PTMSessionSerializer,
    PTMSlotSerializer,
    PTMBookingSerializer,
)


def _notify_ptm_booking(booking, actor):
    if booking.status != "Confirmed":
        return

    from communication.models import Notification
    from parent_portal.models import ParentStudentLink

    student_name = f"{booking.student.first_name} {booking.student.last_name}".strip()
    teacher_name = booking.slot.teacher.get_username()
    session = booking.slot.session
    slot_time = booking.slot.slot_time.strftime("%I:%M %p").lstrip("0")
    date_label = session.date.isoformat()

    teacher_message = (
        f"{booking.parent_name} booked a PTM meeting for {student_name} "
        f"on {date_label} at {slot_time} for {session.title}."
    )
    parent_message = (
        f"Your PTM meeting with {teacher_name} for {student_name} "
        f"is confirmed for {date_label} at {slot_time} ({session.title})."
    )

    Notification.objects.create(
        recipient=booking.slot.teacher,
        notification_type="Event",
        title="PTM booking confirmed",
        message=teacher_message,
        priority="Important",
        action_url="/modules/ptm/bookings",
        created_by=actor,
    )

    parent_links = (
        ParentStudentLink.objects.filter(student=booking.student, is_active=True, parent_user__isnull=False)
        .select_related("parent_user")
        .order_by("-is_primary", "-id")
    )
    seen_parent_ids = set()
    for link in parent_links:
        if not link.parent_user_id or link.parent_user_id in seen_parent_ids:
            continue
        seen_parent_ids.add(link.parent_user_id)
        Notification.objects.create(
            recipient=link.parent_user,
            notification_type="Event",
            title="PTM booking confirmed",
            message=parent_message,
            priority="Important",
            action_url="/modules/parent-portal/dashboard",
            created_by=actor,
        )


class PTMSessionViewSet(viewsets.ModelViewSet):
    queryset = PTMSession.objects.all().order_by('-date')
    serializer_class = PTMSessionSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "PTM"

class PTMSlotViewSet(viewsets.ModelViewSet):
    queryset = PTMSlot.objects.all()
    serializer_class = PTMSlotSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "PTM"
    filterset_fields = ['session', 'teacher', 'is_booked']

class PTMBookingViewSet(viewsets.ModelViewSet):
    queryset = PTMBooking.objects.all()
    serializer_class = PTMBookingSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "PTM"
    filterset_fields = ['slot', 'student', 'status']

    def perform_create(self, serializer):
        booking = serializer.save()
        _notify_ptm_booking(booking, self.request.user)

class PTMDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "PTM"

    def get(self, request):
        from django.utils import timezone
        today = timezone.now().date()
        upcoming_session_queryset = PTMSession.objects.filter(date__gte=today).order_by('date')
        upcoming_sessions = upcoming_session_queryset[:5]
        total_sessions = PTMSession.objects.count()
        upcoming_session_count = upcoming_session_queryset.count()
        total_slots = PTMSlot.objects.filter(session__in=upcoming_session_queryset).count()
        booked_slots = PTMSlot.objects.filter(session__in=upcoming_session_queryset, is_booked=True).count()

        return Response({
            'total_sessions': total_sessions,
            'upcoming_session_count': upcoming_session_count,
            'upcoming_sessions': PTMSessionSerializer(upcoming_sessions, many=True).data,
            'total_slots': total_slots,
            'booked_slots': booked_slots,
            'available_slots': total_slots - booked_slots
        })

class MyPTMSlotsView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "PTM"

    def get(self, request):
        slots = PTMSlot.objects.filter(teacher=request.user)
        return Response(PTMSlotSerializer(slots, many=True).data)
