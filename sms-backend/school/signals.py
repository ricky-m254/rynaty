from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.dateparse import parse_date, parse_datetime
from django.utils import timezone
from decimal import Decimal

import logging

from communication.models import SmsMessage
from communication.services import send_sms_placeholder

from .events import payment_recorded

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


def _payment_sms_recipient(payment):
    student = getattr(payment, "student", None)
    if not student:
        return ""

    student_phone = (getattr(student, "phone", "") or "").strip()
    if student_phone:
        return student_phone

    try:
        guardian = (
            student.guardians.filter(is_active=True)
            .exclude(phone="")
            .order_by("id")
            .first()
        )
    except Exception:
        guardian = None

    return (getattr(guardian, "phone", "") or "").strip() if guardian else ""


def _build_payment_sms_message(payment):
    student = getattr(payment, "student", None)
    student_name = (
        f"{getattr(student, 'first_name', '').strip()} {getattr(student, 'last_name', '').strip()}".strip()
        or getattr(student, "admission_number", "")
        or "student"
    )
    admission_number = (getattr(student, "admission_number", "") or "").strip()
    if admission_number:
        student_label = f"{student_name} ({admission_number})"
    else:
        student_label = student_name

    receipt_number = (getattr(payment, "receipt_number", "") or "").strip()
    if not receipt_number and getattr(payment, "pk", None):
        receipt_number = f"RCT-{payment.pk:06d}"

    reference_number = (getattr(payment, "reference_number", "") or "").strip() or receipt_number
    amount_value = Decimal(str(getattr(payment, "amount", Decimal("0.00")) or Decimal("0.00")))
    amount_text = f"{amount_value:,.2f}"

    return (
        f"Payment received for {student_label}. "
        f"Receipt {receipt_number or 'N/A'}. "
        f"Ref {reference_number or 'N/A'}. "
        f"Amount KES {amount_text}."
    )



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


@receiver(payment_recorded)
def notify_on_payment_recorded(sender, payment_id, skip_notifications=False, **kwargs):
    """Create the financial SMS audit trail after a payment is recorded."""
    try:
        if skip_notifications:
            return
        from .models import Payment

        payment = (
            Payment.objects.select_related("student")
            .prefetch_related("student__guardians")
            .get(pk=payment_id)
        )
        recipient_phone = _payment_sms_recipient(payment)
        if not recipient_phone:
            logger.info("Skipping payment SMS for payment %s because no recipient phone is on file.", payment_id)
            return

        message = _build_payment_sms_message(payment)
        dispatch = send_sms_placeholder(recipient_phone, message, channel="SMS")
        SmsMessage.objects.create(
            recipient_phone=recipient_phone,
            message=message,
            channel="SMS",
            status=dispatch.status if dispatch.status in {"Queued", "Sent", "Delivered", "Failed"} else "Queued",
            provider_id=dispatch.provider_id,
            cost=dispatch.cost,
            sent_at=timezone.now() if dispatch.status in {"Queued", "Sent", "Delivered"} else None,
            failure_reason=dispatch.failure_reason,
        )
    except Exception:
        logger.warning("Caught and logged", exc_info=True)
