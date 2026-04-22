from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.dateparse import parse_date, parse_datetime

import logging

logger = logging.getLogger(__name__)


def _format_attendance_date(raw_date):
    if hasattr(raw_date, "strftime"):
        return raw_date.strftime("%A, %d %B %Y")

    parsed_date = parse_date(str(raw_date)) if raw_date is not None else None
    if parsed_date is None and raw_date is not None:
        parsed_datetime = parse_datetime(str(raw_date))
        if parsed_datetime is not None:
            parsed_date = parsed_datetime.date()

    if parsed_date is not None:
        return parsed_date.strftime("%A, %d %B %Y")

    return str(raw_date)



@receiver(post_save, sender="school.AttendanceRecord")
def notify_parent_on_absence(sender, instance, created, **kwargs):
    """
    When an AttendanceRecord is saved as Absent or Late, push an in-app
    Notification to every active parent linked to that student.
    Wrapped in try/except so attendance saving never breaks on notification error.
    """
    if instance.status not in ("Absent", "Late"):
        return

    try:
        from communication.models import Notification
        from parent_portal.models import ParentStudentLink

        links = ParentStudentLink.objects.filter(
            student=instance.student,
            is_active=True,
        ).select_related("parent_user", "student")

        if not links.exists():
            return

        student = instance.student
        student_name = (
            f"{student.first_name} {student.last_name}".strip()
            or student.admission_number
        )
        date_str = _format_attendance_date(instance.date)

        if instance.status == "Absent":
            title = f"Absence Alert — {student_name}"
            message = (
                f"{student_name} was marked absent on {date_str}. "
                "If this was unplanned, please contact the school or "
                "submit a leave request from the Attendance section."
            )
            priority = "Important"
        else:
            title = f"Late Arrival — {student_name}"
            message = f"{student_name} arrived late on {date_str}."
            priority = "Informational"

        for link in links:
            # Avoid duplicate notifications for the same student/date/status
            already_sent = Notification.objects.filter(
                recipient=link.parent_user,
                notification_type="Academic",
                title=title,
            ).exists()
            if already_sent:
                continue

            Notification.objects.create(
                recipient=link.parent_user,
                notification_type="Academic",
                title=title,
                message=message,
                priority=priority,
                action_url="/parent/attendance/",
            )

    except Exception:
        logger.warning("Caught and logged", exc_info=True)
