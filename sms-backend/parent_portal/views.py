from datetime import timedelta
from decimal import Decimal
import uuid

from django.conf import settings
from django.contrib.auth import update_session_auth_hash
from django.db.models import Avg, Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from communication.models import Announcement, Notification, NotificationPreference
from library.models import CirculationTransaction, LibraryMember
from school.models import (
    AssessmentGrade,
    Assignment,
    AssignmentSubmission,
    AttendanceRecord,
    BehaviorIncident,
    CalendarEvent,
    Enrollment,
    Invoice,
    Message,
    Payment,
    PaymentGatewayTransaction,
    Student,
    TermResult,
)
from school.permissions import HasModuleAccess
from school.permissions import IsSchoolAdmin

from .models import ParentStudentLink
from .serializers import ParentProfileSerializer, ParentStudentLinkSerializer


class ParentPortalAccessMixin:
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "PARENTS"
    allow_force_password_change = False

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        profile = getattr(request.user, "userprofile", None)
        if getattr(profile, "force_password_change", False) and not self.allow_force_password_change:
            raise PermissionDenied("Password change is required before accessing the parent portal.")


def _children_for_parent(user):
    linked_ids = list(
        ParentStudentLink.objects.filter(parent_user=user, is_active=True)
        .values_list("student_id", flat=True)
    )
    if linked_ids:
        return Student.objects.filter(is_active=True, id__in=linked_ids).distinct().order_by("first_name", "last_name")

    if not settings.PARENT_PORTAL_ALLOW_GUARDIAN_FALLBACK:
        return Student.objects.none()

    # Transitional fallback while explicit links are being populated.
    query = Q()
    if user.email:
        query |= Q(guardians__email__iexact=user.email)
    full_name = f"{user.first_name} {user.last_name}".strip()
    if full_name:
        query |= Q(guardians__name__iexact=full_name)
    if user.username:
        query |= Q(guardians__name__icontains=user.username)
    if not query:
        return Student.objects.none()
    return Student.objects.filter(is_active=True).filter(query).distinct().order_by("first_name", "last_name")


def _pick_child(request):
    children = _children_for_parent(request.user)
    child_id = request.query_params.get("child_id") or request.data.get("child_id")
    if child_id:
        child = children.filter(id=child_id).first()
        return child, children
    return children.first(), children


def _active_enrollment(student):
    if not student:
        return None
    return Enrollment.objects.filter(student=student, is_active=True, status="Active").order_by("-id").first()


def _no_linked_child_response():
    return Response({"error": "No linked child found."}, status=status.HTTP_404_NOT_FOUND)


def _no_linked_child_or_enrollment_response():
    return Response({"error": "No linked child or active enrollment."}, status=status.HTTP_404_NOT_FOUND)


def _library_member_ids_for_child(child):
    if not child:
        return []
    candidates = {
        child.admission_number,
        f"LIB-{child.id}",
        f"LIB-{child.id:03d}",
    }
    return [value for value in candidates if value]


def _kpis(child):
    attendance = AttendanceRecord.objects.filter(student=child)
    total_days = attendance.count()
    present = attendance.filter(status="Present").count()
    attendance_rate = round((present / total_days) * 100, 2) if total_days else 0
    billed = Invoice.objects.filter(student=child, is_active=True).aggregate(v=Sum("total_amount")).get("v") or Decimal("0.00")
    paid = Payment.objects.filter(student=child, is_active=True).aggregate(v=Sum("amount")).get("v") or Decimal("0.00")
    avg_score = TermResult.objects.filter(student=child, is_active=True).aggregate(v=Avg("total_score")).get("v") or 0
    upcoming = CalendarEvent.objects.filter(is_active=True, start_date__gte=timezone.now().date()).count()
    return {
        "current_average_grade": round(float(avg_score), 2),
        "attendance_rate": attendance_rate,
        "outstanding_fee_balance": billed - paid,
        "upcoming_events_count": upcoming,
    }


class ParentDashboardView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        child, children = _pick_child(request)
        if not child:
            return Response({"children": [], "selected_child": None, "kpis": {}, "alerts": [], "recent_activity": []})
        alerts = []
        kpis = _kpis(child)
        if Decimal(kpis["outstanding_fee_balance"]) > 0:
            alerts.append({"type": "Financial", "title": "Outstanding fees", "action": "Pay Now"})
        if kpis["attendance_rate"] < 85:
            alerts.append({"type": "Attendance", "title": "Low attendance warning", "action": "View attendance"})
        activity = []
        for row in AssessmentGrade.objects.filter(student=child, is_active=True).select_related("assessment", "assessment__subject").order_by("-entered_at")[:5]:
            activity.append({"type": "Grade", "message": f"{row.assessment.subject.name}: {row.raw_score}", "date": row.entered_at})
        for row in AttendanceRecord.objects.filter(student=child).order_by("-date")[:5]:
            activity.append({"type": "Attendance", "message": row.status, "date": row.date})
        activity = sorted(activity, key=lambda item: item["date"], reverse=True)[:10]
        return Response(
            {
                "children": [{"id": c.id, "name": f"{c.first_name} {c.last_name}".strip(), "admission_number": c.admission_number} for c in children],
                "selected_child": {"id": child.id, "name": f"{child.first_name} {child.last_name}".strip(), "admission_number": child.admission_number},
                "kpis": kpis,
                "alerts": alerts,
                "recent_activity": activity,
            }
        )


class ParentDashboardKpiView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        child, _ = _pick_child(request)
        if not child:
            return _no_linked_child_response()
        return Response(_kpis(child))


class ParentDashboardAlertsView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        child, _ = _pick_child(request)
        if not child:
            return _no_linked_child_response()
        alerts = []
        kpis = _kpis(child)
        if Decimal(kpis["outstanding_fee_balance"]) > 0:
            alerts.append({"type": "Financial", "title": "Outstanding fees", "action": "Pay Now"})
        if kpis["attendance_rate"] < 85:
            alerts.append({"type": "Attendance", "title": "Low attendance warning", "action": "View attendance"})
        return Response(alerts)


class ParentDashboardActivityView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        child, _ = _pick_child(request)
        if not child:
            return _no_linked_child_response()
        activity = []
        for row in AssessmentGrade.objects.filter(student=child, is_active=True).select_related("assessment", "assessment__subject").order_by("-entered_at")[:10]:
            activity.append({"type": "Grade", "message": f"{row.assessment.subject.name}: {row.raw_score}", "date": row.entered_at})
        return Response(activity)


class ParentDashboardUpcomingView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        child, _ = _pick_child(request)
        if not child:
            return _no_linked_child_response()
        now = timezone.now().date()
        end = now + timedelta(days=7)
        enrollment = _active_enrollment(child)
        events = CalendarEvent.objects.filter(is_active=True, start_date__range=[now, end]).filter(
            Q(scope="School-wide") | Q(scope="Class-specific", class_section_id=getattr(enrollment, "school_class_id", None))
        )
        return Response([{"id": e.id, "title": e.title, "event_type": e.event_type, "start_date": e.start_date, "end_date": e.end_date} for e in events.order_by("start_date")[:50]])


class ParentAcademicsGradesView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        child, _ = _pick_child(request)
        if not child:
            return _no_linked_child_response()
        rows = TermResult.objects.filter(student=child, is_active=True).select_related("subject", "grade_band").order_by("subject__name")
        return Response(
            [
                {
                    "id": r.id,
                    "subject": r.subject.name,
                    "total_score": r.total_score,
                    "grade": getattr(r.grade_band, "label", ""),
                    "class_rank": r.class_rank,
                    "is_pass": r.is_pass,
                    "updated_at": r.updated_at,
                }
                for r in rows
            ]
        )


class ParentAcademicsAssessmentsView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        child, _ = _pick_child(request)
        if not child:
            return _no_linked_child_response()
        rows = AssessmentGrade.objects.filter(student=child, is_active=True).select_related("assessment", "assessment__subject", "grade_band").order_by("-assessment__date")
        return Response(
            [
                {
                    "id": r.id,
                    "assessment": r.assessment.name,
                    "subject": r.assessment.subject.name,
                    "category": r.assessment.category,
                    "date": r.assessment.date,
                    "raw_score": r.raw_score,
                    "percentage": r.percentage,
                    "grade": getattr(r.grade_band, "label", ""),
                }
                for r in rows[:300]
            ]
        )


class ParentAcademicsAnalysisView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        child, _ = _pick_child(request)
        if not child:
            return _no_linked_child_response()
        rows = TermResult.objects.filter(student=child, is_active=True).select_related("subject")
        subjects = [{"subject": r.subject.name, "score": r.total_score, "is_pass": r.is_pass} for r in rows]
        avg_score = rows.aggregate(v=Avg("total_score")).get("v") or 0
        return Response({"subjects": subjects, "average": round(float(avg_score), 2)})


class ParentReportCardsView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        child, _ = _pick_child(request)
        if not child:
            return _no_linked_child_response()
        from school.models import ReportCard

        rows = ReportCard.objects.filter(student=child, is_active=True).select_related("term", "academic_year").order_by("-created_at")
        return Response(
            [
                {
                    "id": r.id,
                    "academic_year": r.academic_year.name,
                    "term": r.term.name,
                    "status": r.status,
                    "overall_grade": r.overall_grade,
                    "download_url": f"/api/parent-portal/academics/report-cards/{r.id}/download/",
                }
                for r in rows
            ]
        )


class ParentReportCardDownloadView(ParentPortalAccessMixin, APIView):
    def get(self, request, card_id):
        child, _ = _pick_child(request)
        from school.models import ReportCard

        card = ReportCard.objects.filter(id=card_id, student=child, is_active=True).first() if child else None
        if not card:
            return Response({"error": "Report card not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"download_url": card.pdf_file.url if card.pdf_file else None, "message": "PDF not generated yet." if not card.pdf_file else "OK"})


class ParentAttendanceCalendarView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        child, _ = _pick_child(request)
        if not child:
            return _no_linked_child_response()
        rows = AttendanceRecord.objects.filter(student=child).order_by("-date")[:180]
        return Response([{"id": r.id, "date": r.date, "status": r.status, "notes": r.notes} for r in rows])


class ParentAttendanceSummaryView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        child, _ = _pick_child(request)
        if not child:
            return _no_linked_child_response()
        rows = AttendanceRecord.objects.filter(student=child)
        total = rows.count()
        present = rows.filter(status="Present").count()
        absent = rows.filter(status="Absent").count()
        late = rows.filter(status="Late").count()
        return Response({"total_days": total, "present": present, "absent": absent, "late": late, "attendance_rate": round((present / total) * 100, 2) if total else 0})


class ParentLeaveRequestView(ParentPortalAccessMixin, APIView):
    def post(self, request):
        child, _ = _pick_child(request)
        if not child:
            return _no_linked_child_response()
        Message.objects.create(
            recipient_type="STAFF",
            recipient_id=0,
            subject=f"Parent Leave Request: {child.first_name} {child.last_name}",
            body=f"From {request.data.get('start_date')} to {request.data.get('end_date')}. Reason: {request.data.get('reason', '')}",
            status="SENT",
        )
        return Response({"status": "Pending", "message": "Leave request submitted."}, status=status.HTTP_201_CREATED)


class ParentBehaviorIncidentsView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        child, _ = _pick_child(request)
        if not child:
            return _no_linked_child_response()
        rows = BehaviorIncident.objects.filter(student=child).order_by("-incident_date", "-id")[:200]
        return Response(
            [
                {
                    "id": r.id,
                    "incident_date": r.incident_date,
                    "incident_type": r.incident_type,
                    "category": r.category,
                    "severity": r.severity,
                    "description": r.description,
                }
                for r in rows
            ]
        )


class ParentBehaviorAcknowledgeView(ParentPortalAccessMixin, APIView):
    def post(self, request, incident_id):
        child, _ = _pick_child(request)
        row = BehaviorIncident.objects.filter(id=incident_id, student=child).first() if child else None
        if not row:
            return Response({"error": "Incident not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"message": "Incident acknowledged."})


class ParentFinanceSummaryView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        child, _ = _pick_child(request)
        if not child:
            return _no_linked_child_response()
        invoices = Invoice.objects.filter(student=child, is_active=True)
        billed = invoices.aggregate(v=Sum("total_amount")).get("v") or Decimal("0.00")
        paid = Payment.objects.filter(student=child, is_active=True).aggregate(v=Sum("amount")).get("v") or Decimal("0.00")
        return Response({"student_id": child.id, "total_billed": billed, "total_paid": paid, "outstanding_balance": billed - paid, "invoice_count": invoices.count()})


class ParentFinanceInvoicesView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        child, _ = _pick_child(request)
        if not child:
            return _no_linked_child_response()
        rows = Invoice.objects.filter(student=child, is_active=True).order_by("-invoice_date", "-id")
        return Response(
            [
                {
                    "id": r.id,
                    "invoice_date": r.invoice_date,
                    "due_date": r.due_date,
                    "total_amount": r.total_amount,
                    "status": r.status,
                    "balance_due": r.balance_due,
                    "download_url": f"/api/parent-portal/finance/invoices/{r.id}/download/",
                }
                for r in rows
            ]
        )


class ParentFinanceInvoiceDownloadView(ParentPortalAccessMixin, APIView):
    def get(self, request, invoice_id):
        child, _ = _pick_child(request)
        row = Invoice.objects.filter(id=invoice_id, student=child, is_active=True).first() if child else None
        if not row:
            return Response({"error": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)
        payload = [
            "field,value",
            f"invoice_id,{row.id}",
            f"student_id,{row.student_id}",
            f"invoice_date,{row.invoice_date}",
            f"due_date,{row.due_date}",
            f"status,{row.status}",
            f"total_amount,{row.total_amount}",
            f"amount_paid,{row.amount_paid}",
            f"balance_due,{row.balance_due}",
        ]
        response = HttpResponse("\n".join(payload), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="invoice_{row.id}.csv"'
        return response


class ParentFinancePaymentsView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        child, _ = _pick_child(request)
        if not child:
            return _no_linked_child_response()
        rows = Payment.objects.filter(student=child, is_active=True).order_by("-payment_date", "-id")
        return Response(
            [
                {
                    "id": r.id,
                    "payment_date": r.payment_date,
                    "amount": r.amount,
                    "payment_method": r.payment_method,
                    "reference_number": r.reference_number,
                    "receipt_url": f"/api/parent-portal/finance/payments/{r.id}/receipt/",
                }
                for r in rows
            ]
        )


class ParentFinanceReceiptView(ParentPortalAccessMixin, APIView):
    def get(self, request, payment_id):
        child, _ = _pick_child(request)
        row = Payment.objects.filter(id=payment_id, student=child, is_active=True).first() if child else None
        if not row:
            return Response({"error": "Payment not found."}, status=status.HTTP_404_NOT_FOUND)
        payload = [
            "field,value",
            f"payment_id,{row.id}",
            f"student_id,{row.student_id}",
            f"payment_date,{row.payment_date}",
            f"amount,{row.amount}",
            f"payment_method,{row.payment_method}",
            f"reference_number,{row.reference_number}",
            f"receipt_number,{row.receipt_number or ''}",
            f"notes,{(row.notes or '').replace(',', ' ')}",
        ]
        response = HttpResponse("\n".join(payload), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="receipt_{row.id}.csv"'
        return response


class ParentFinancePayView(ParentPortalAccessMixin, APIView):
    def post(self, request):
        child, _ = _pick_child(request)
        if not child:
            return _no_linked_child_response()

        amount = Decimal(str(request.data.get("amount") or "0"))
        if amount <= 0:
            return Response({"error": "Amount must be greater than zero."}, status=status.HTTP_400_BAD_REQUEST)

        method = (request.data.get("payment_method") or "Online").strip()
        invoice_id = request.data.get("invoice_id")

        # ── M-Pesa STK Push path ──────────────────────────────────────────
        if method.lower() in ("mpesa", "m-pesa", "mobile money"):
            phone = (request.data.get("phone") or "").strip()
            if not phone:
                return Response(
                    {"error": "Phone number is required for M-Pesa payment."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            from school.mpesa import initiate_stk_push, MpesaError
            callback_url = request.build_absolute_uri("/api/finance/mpesa/callback/")
            reference = f"FEES-{uuid.uuid4().hex[:6].upper()}"
            try:
                result = initiate_stk_push(
                    phone=phone,
                    amount=amount,
                    account_ref=reference,
                    callback_url=callback_url,
                    description="School Fees",
                )
            except MpesaError as exc:
                return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

            tx = PaymentGatewayTransaction.objects.create(
                provider="mpesa",
                external_id=result["checkout_request_id"],
                student=child,
                invoice_id=invoice_id,
                amount=amount,
                currency="KES",
                status="PENDING",
                payload={
                    "checkout_request_id": result["checkout_request_id"],
                    "merchant_request_id": result["merchant_request_id"],
                    "phone": phone,
                    "reference": reference,
                    "source": "parent_portal",
                    "initiated_by_user_id": request.user.id,
                    "initiated_by_username": request.user.username,
                },
            )
            return Response(
                {
                    "payment_id": tx.id,
                    "checkout_request_id": result["checkout_request_id"],
                    "reference_number": reference,
                    "payment_method": "M-Pesa",
                    "status": "PENDING",
                    "message": result["customer_message"] or "STK push sent. Please check your phone and enter your M-Pesa PIN.",
                },
                status=status.HTTP_201_CREATED,
            )

        # ── All other payment methods (manual / bank / cash) ─────────────
        reference_number = f"PPORT-{uuid.uuid4().hex[:8].upper()}"
        row = PaymentGatewayTransaction.objects.create(
            provider="parent_portal",
            external_id=reference_number,
            student=child,
            invoice_id=invoice_id,
            amount=amount,
            currency="KES",
            status="INITIATED",
            payload={
                "source": "parent_portal",
                "payment_method": method,
                "initiated_by_user_id": request.user.id,
                "initiated_by_username": request.user.username,
            },
        )
        return Response(
            {
                "payment_id": row.id,
                "reference_number": row.external_id,
                "payment_method": method,
                "status": "Initiated",
            },
            status=status.HTTP_201_CREATED,
        )


class ParentMpesaStatusView(ParentPortalAccessMixin, APIView):
    """
    GET /api/parent-portal/finance/mpesa-status/?checkout_request_id=xxx
    Parent polls this after initiating an STK push to check if payment succeeded.
    """
    def get(self, request):
        checkout_id = request.query_params.get("checkout_request_id", "").strip()
        if not checkout_id:
            return Response({"error": "checkout_request_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        child, _ = _pick_child(request)
        tx = PaymentGatewayTransaction.objects.filter(
            provider="mpesa",
            external_id=checkout_id,
            student=child,
        ).first()
        if not tx:
            return Response({"error": "Transaction not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            "transaction_id": tx.id,
            "status": tx.status,
            "amount": str(tx.amount),
            "mpesa_receipt": tx.payload.get("mpesa_receipt"),
            "message": (
                "Payment confirmed." if tx.status == "SUCCEEDED"
                else "Payment failed. Please try again." if tx.status == "FAILED"
                else "Waiting for M-Pesa confirmation..."
            ),
            "updated_at": tx.updated_at,
        })


class ParentFinanceStatementView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        child, _ = _pick_child(request)
        if not child:
            return _no_linked_child_response()
        invoices = Invoice.objects.filter(student=child, is_active=True).order_by("invoice_date", "id")
        payments = Payment.objects.filter(student=child, is_active=True).order_by("payment_date", "id")
        billed = invoices.aggregate(v=Sum("total_amount")).get("v") or Decimal("0.00")
        paid = payments.aggregate(v=Sum("amount")).get("v") or Decimal("0.00")
        return Response(
            {
                "invoices": [{"id": r.id, "date": r.invoice_date, "amount": r.total_amount, "status": r.status} for r in invoices],
                "payments": [{"id": r.id, "date": r.payment_date, "amount": r.amount, "reference": r.reference_number} for r in payments],
                "summary": {"billed": billed, "paid": paid, "balance": billed - paid},
            }
        )


class ParentMessagesView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        rows = Message.objects.filter(recipient_type="STAFF").order_by("-sent_at")[:100]
        return Response([{"id": r.id, "subject": r.subject, "body": r.body, "sent_at": r.sent_at, "status": r.status} for r in rows])

    def post(self, request):
        subject = (request.data.get("subject") or "").strip()
        body = (request.data.get("body") or "").strip()
        if not subject or not body:
            return Response({"error": "subject and body are required"}, status=status.HTTP_400_BAD_REQUEST)
        row = Message.objects.create(recipient_type="STAFF", recipient_id=0, subject=subject, body=body, status="SENT")
        return Response({"id": row.id, "subject": row.subject, "body": row.body, "sent_at": row.sent_at, "status": row.status}, status=status.HTTP_201_CREATED)


class ParentAnnouncementsView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        now = timezone.now()
        rows = Announcement.objects.filter(is_active=True, publish_at__lte=now).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now)).order_by("-publish_at")[:200]
        return Response([{"id": r.id, "title": r.title, "body": r.body, "priority": r.priority, "publish_at": r.publish_at} for r in rows])


class ParentNotificationsView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        rows = Notification.objects.filter(recipient=request.user, is_active=True).order_by("-sent_at")[:200]
        return Response([{"id": r.id, "notification_type": r.notification_type, "title": r.title, "message": r.message, "is_read": r.is_read, "sent_at": r.sent_at} for r in rows])


class ParentNotificationReadView(ParentPortalAccessMixin, APIView):
    def patch(self, request, notification_id):
        row = Notification.objects.filter(id=notification_id, recipient=request.user, is_active=True).first()
        if not row:
            return Response({"error": "Notification not found."}, status=status.HTTP_404_NOT_FOUND)
        row.is_read = True
        row.read_at = timezone.now()
        row.save(update_fields=["is_read", "read_at"])
        return Response({"message": "Notification marked as read."})


class ParentNotificationPreferencesView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        rows = NotificationPreference.objects.filter(user=request.user).order_by("notification_type")
        return Response(
            [
                {
                    "id": r.id,
                    "notification_type": r.notification_type,
                    "channel_in_app": r.channel_in_app,
                    "channel_email": r.channel_email,
                    "channel_sms": r.channel_sms,
                    "channel_push": r.channel_push,
                }
                for r in rows
            ]
        )

    def patch(self, request):
        ntype = request.data.get("notification_type")
        if not ntype:
            return Response({"error": "notification_type is required"}, status=status.HTTP_400_BAD_REQUEST)
        row, _ = NotificationPreference.objects.update_or_create(
            user=request.user,
            notification_type=ntype,
            defaults={
                "channel_in_app": bool(request.data.get("channel_in_app", True)),
                "channel_email": bool(request.data.get("channel_email", True)),
                "channel_sms": bool(request.data.get("channel_sms", False)),
                "channel_push": bool(request.data.get("channel_push", False)),
            },
        )
        return Response({"id": row.id, "notification_type": row.notification_type, "channel_in_app": row.channel_in_app, "channel_email": row.channel_email, "channel_sms": row.channel_sms, "channel_push": row.channel_push})


class ParentTimetableView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        child, _ = _pick_child(request)
        enrollment = _active_enrollment(child)
        if not child or not enrollment:
            return _no_linked_child_or_enrollment_response()
        rows = AssessmentGrade.objects.filter(student=child, is_active=True).select_related("assessment", "assessment__subject").order_by("-assessment__date")
        return Response([{"assessment": r.assessment.name, "subject": r.assessment.subject.name, "date": r.assessment.date, "category": r.assessment.category} for r in rows[:100]])


class ParentTimetableExportView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        child, _ = _pick_child(request)
        enrollment = _active_enrollment(child)
        if not child or not enrollment:
            return _no_linked_child_or_enrollment_response()
        rows = (
            AssessmentGrade.objects.filter(student=child, is_active=True)
            .select_related("assessment", "assessment__subject")
            .order_by("-assessment__date")[:200]
        )
        payload = ["assessment,subject,date,category"]
        payload.extend(
            f"{r.assessment.name},{r.assessment.subject.name},{r.assessment.date},{r.assessment.category}"
            for r in rows
        )
        response = HttpResponse("\n".join(payload), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="timetable_{child.id}.csv"'
        return response


class ParentCalendarView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        child, _ = _pick_child(request)
        enrollment = _active_enrollment(child)
        rows = CalendarEvent.objects.filter(is_active=True).filter(
            Q(scope="School-wide") | Q(scope="Class-specific", class_section_id=getattr(enrollment, "school_class_id", None))
        )
        return Response([{"id": r.id, "title": r.title, "event_type": r.event_type, "start_date": r.start_date, "end_date": r.end_date} for r in rows.order_by("start_date", "id")[:300]])


class ParentAssignmentsView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        child, _ = _pick_child(request)
        enrollment = _active_enrollment(child)
        if not child or not enrollment:
            return _no_linked_child_or_enrollment_response()
        rows = Assignment.objects.filter(class_section=enrollment.school_class, is_active=True).select_related("subject").order_by("-due_date")
        submission_map = {s.assignment_id: s for s in AssignmentSubmission.objects.filter(student=child, is_active=True)}
        return Response(
            [
                {
                    "id": r.id,
                    "title": r.title,
                    "subject": r.subject.name,
                    "due_date": r.due_date,
                    "status": r.status,
                    "submitted": bool(submission_map.get(r.id)),
                    "score": getattr(submission_map.get(r.id), "score", None),
                }
                for r in rows[:200]
            ]
        )


class ParentAssignmentSubmitView(ParentPortalAccessMixin, APIView):
    def post(self, request, assignment_id):
        child, _ = _pick_child(request)
        assignment = Assignment.objects.filter(id=assignment_id, is_active=True).first()
        if not child or not assignment:
            return Response({"error": "Assignment or child not found."}, status=status.HTTP_404_NOT_FOUND)
        row, _ = AssignmentSubmission.objects.update_or_create(
            assignment=assignment,
            student=child,
            defaults={"notes": request.data.get("notes", ""), "is_late": timezone.now() > assignment.due_date},
        )
        return Response({"id": row.id, "submitted_at": row.submitted_at, "is_late": row.is_late}, status=status.HTTP_201_CREATED)


class ParentEventsView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        rows = CalendarEvent.objects.filter(is_active=True, is_public=True).order_by("start_date", "id")[:200]
        return Response([{"id": r.id, "title": r.title, "event_type": r.event_type, "start_date": r.start_date, "end_date": r.end_date} for r in rows])


class ParentEventRsvpView(ParentPortalAccessMixin, APIView):
    def post(self, request, event_id):
        row = CalendarEvent.objects.filter(id=event_id, is_active=True).first()
        if not row:
            return Response({"error": "Event not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"message": "RSVP recorded.", "event_id": row.id, "status": request.data.get("status", "Yes")})


class ParentLibraryBorrowingsView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        child, _ = _pick_child(request)
        if not child:
            return _no_linked_child_response()
        member_ids = _library_member_ids_for_child(child)
        member_lookup = set(
            LibraryMember.objects.filter(member_type="Student", member_id__in=member_ids, is_active=True).values_list("id", flat=True)
        )
        if not member_lookup:
            return Response([])
        rows = (
            CirculationTransaction.objects.filter(
                member_id__in=member_lookup,
                is_active=True,
                return_date__isnull=True,
                transaction_type__in=["Issue", "Renew"],
            )
            .select_related("copy", "copy__resource", "member")
            .order_by("-issue_date", "-id")[:200]
        )
        return Response(
            [
                {
                    "id": row.id,
                    "member_id": row.member.member_id,
                    "resource_title": row.copy.resource.title,
                    "accession_number": row.copy.accession_number,
                    "issue_date": row.issue_date,
                    "due_date": row.due_date,
                    "renewal_count": row.renewal_count,
                }
                for row in rows
            ]
        )


class ParentLibraryHistoryView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        child, _ = _pick_child(request)
        if not child:
            return _no_linked_child_response()
        member_ids = _library_member_ids_for_child(child)
        member_lookup = set(
            LibraryMember.objects.filter(member_type="Student", member_id__in=member_ids, is_active=True).values_list("id", flat=True)
        )
        if not member_lookup:
            return Response([])
        rows = (
            CirculationTransaction.objects.filter(member_id__in=member_lookup, is_active=True)
            .select_related("copy", "copy__resource", "member")
            .order_by("-issue_date", "-id")[:300]
        )
        return Response(
            [
                {
                    "id": row.id,
                    "member_id": row.member.member_id,
                    "resource_title": row.copy.resource.title,
                    "accession_number": row.copy.accession_number,
                    "transaction_type": row.transaction_type,
                    "issue_date": row.issue_date,
                    "due_date": row.due_date,
                    "return_date": row.return_date,
                    "fine_amount": row.fine_amount,
                }
                for row in rows
            ]
        )


class ParentProfileView(ParentPortalAccessMixin, APIView):
    allow_force_password_change = True

    def get(self, request):
        return Response(ParentProfileSerializer(request.user).data)

    def patch(self, request):
        serializer = ParentProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ParentChangePasswordView(ParentPortalAccessMixin, APIView):
    allow_force_password_change = True

    def post(self, request):
        current_password = request.data.get("current_password") or ""
        new_password = request.data.get("new_password") or ""
        if not request.user.check_password(current_password):
            return Response({"error": "Current password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)
        if len(new_password) < 8:
            return Response({"error": "New password must be at least 8 characters."}, status=status.HTTP_400_BAD_REQUEST)
        request.user.set_password(new_password)
        request.user.save(update_fields=["password"])
        profile = getattr(request.user, "userprofile", None)
        if profile is not None and profile.force_password_change:
            profile.force_password_change = False
            profile.save(update_fields=["force_password_change"])
        if hasattr(getattr(request, "_request", request), "session"):
            update_session_auth_hash(request, request.user)
        return Response({"message": "Password changed successfully."})


class ParentLinkAdminListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess, IsSchoolAdmin]
    module_key = "PARENTS"

    def get(self, request):
        rows = ParentStudentLink.objects.filter(is_active=True).select_related("parent_user", "student", "guardian").order_by("-is_primary", "-id")
        return Response(ParentStudentLinkSerializer(rows, many=True).data)

    def post(self, request):
        serializer = ParentStudentLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = serializer.save(created_by=request.user)
        return Response(ParentStudentLinkSerializer(row).data, status=status.HTTP_201_CREATED)


class ParentLinkAdminDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess, IsSchoolAdmin]
    module_key = "PARENTS"

    def patch(self, request, link_id):
        row = ParentStudentLink.objects.filter(id=link_id).first()
        if not row:
            return Response({"error": "Link not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = ParentStudentLinkSerializer(row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, link_id):
        row = ParentStudentLink.objects.filter(id=link_id).first()
        if not row:
            return Response({"error": "Link not found."}, status=status.HTTP_404_NOT_FOUND)
        row.is_active = False
        row.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class ParentHealthView(APIView):
    """Parent-facing health/medical data for linked student."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from school.models import MedicalRecord, ImmunizationRecord, ClinicVisit
        child, children = _pick_child(request)
        if not child:
            return _no_linked_child_response()

        medical = MedicalRecord.objects.filter(student=child).values(
            'id', 'blood_type', 'allergies', 'chronic_conditions',
            'disability', 'emergency_contact_name', 'emergency_contact_phone',
            'created_at', 'updated_at'
        ).first()

        immunizations = list(ImmunizationRecord.objects.filter(student=child).values(
            'id', 'vaccine_name', 'date_administered', 'dose_number',
            'administered_by', 'notes', 'next_due_date'
        ).order_by('-date_administered')[:20])

        clinic_visits = list(ClinicVisit.objects.filter(student=child).values(
            'id', 'visit_date', 'complaint', 'diagnosis', 'treatment',
            'referred_to_hospital', 'notes', 'created_at'
        ).order_by('-visit_date')[:20])

        return Response({
            "child_id": child.id,
            "child_name": child.full_name,
            "medical_record": medical,
            "immunizations": immunizations,
            "clinic_visits": clinic_visits,
            "children": [{"id": c.id, "name": c.full_name} for c in children],
        })


class ParentTransportView(APIView):
    """Parent-facing transport data for linked student."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from transport.models import StudentTransport, Vehicle
        child, children = _pick_child(request)
        if not child:
            return _no_linked_child_response()

        assignment = StudentTransport.objects.filter(student=child, is_active=True).select_related(
            'route', 'route__vehicle', 'route__vehicle__driver',
            'boarding_stop',
        ).first()

        if not assignment:
            return Response({
                "child_id": child.id,
                "child_name": child.full_name,
                "assignment": None,
                "children": [{"id": c.id, "name": c.full_name} for c in children],
            })

        route = assignment.route
        vehicle = route.vehicle if route else None
        driver = vehicle.driver if vehicle else None

        stops = list(route.stops.values('id', 'stop_name', 'sequence', 'estimated_time', 'landmark').order_by('sequence')) if route else []

        return Response({
            "child_id": child.id,
            "child_name": child.full_name,
            "assignment": {
                "id": assignment.id,
                "route_name": route.name if route else None,
                "route_direction": route.direction if route else None,
                "boarding_stop": assignment.boarding_stop.stop_name if assignment.boarding_stop else None,
                "boarding_time": assignment.boarding_stop.estimated_time if assignment.boarding_stop else None,
                "vehicle_registration": vehicle.registration if vehicle else None,
                "vehicle_make": vehicle.make if vehicle else None,
                "vehicle_model": vehicle.model if vehicle else None,
                "vehicle_capacity": vehicle.capacity if vehicle else None,
                "driver_name": f"{driver.first_name} {driver.last_name}".strip() if driver else None,
                "driver_phone": driver.phone if driver else None,
            },
            "route_stops": stops,
            "children": [{"id": c.id, "name": c.full_name} for c in children],
        })
