"""NotificationService — infrastructure adapter for admin notifications."""
from datetime import datetime

import logging

logger = logging.getLogger(__name__)



class DjangoNotificationService:
    def notify_late_arrival(self, person, event_time: datetime, minutes_late: int) -> None:
        try:
            from communication.models import Notification
            from school.models import UserProfile
            t = event_time.strftime('%H:%M')
            for admin in UserProfile.objects.filter(
                role__name__in=['ADMIN', 'TENANT_SUPER_ADMIN'],
                user__is_active=True,
            ).select_related('user'):
                Notification.objects.create(
                    recipient=admin.user,
                    title=f"Late Arrival: {person.display_name}",
                    message=f"{person.display_name} ({person.person_type}) clocked in at {t} — {minutes_late} min(s) late.",
                    priority='Important', action_url='/modules/clockin/dashboard', is_read=False,
                )
            if person.person_type == 'TEACHER' and person.employee_id:
                self._flag_timetable(person.employee_id, event_time, t)
        except Exception as exc:
            print(f"[NotificationService] failed: {exc}")

    @staticmethod
    def _flag_timetable(employee_id, event_time, time_str):
        try:
            from hr.models import Employee
            from timetable.models import TimetableSlot, LessonCoverage
            emp = Employee.objects.filter(pk=employee_id).select_related('user').first()
            if not emp or not emp.user:
                return
            dow = event_time.isoweekday()
            if not (1 <= dow <= 5):
                return
            for slot in TimetableSlot.objects.filter(
                day_of_week=dow, teacher=emp.user,
                start_time__lte=event_time.time(), is_active=True,
            ):
                LessonCoverage.objects.get_or_create(
                    slot=slot, date=event_time.date(),
                    defaults={'original_teacher': emp.user, 'status': 'Uncovered',
                              'auto_flagged': True, 'notes': f'Late arrival at {time_str}'},
                )
        except Exception:
            logger.warning("Caught and logged", exc_info=True)
