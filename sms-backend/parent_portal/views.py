from datetime import timedelta, datetime as _datetime, date as _date
from decimal import Decimal
import uuid

from django.conf import settings
from django.contrib.auth import update_session_auth_hash
from django.db.models import Avg, Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
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
from school.services import FinanceService

from .models import ParentStudentLink
from .serializers import ParentProfileSerializer, ParentStudentLinkSerializer


class ParentPortalAccessMixin:
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "PARENTS"
    force_password_change_exempt_views = {"ParentProfileView", "ParentChangePasswordView"}

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        profile = getattr(request.user, "userprofile", None)
        if profile and profile.force_password_change and self.__class__.__name__ not in self.force_password_change_exempt_views:
            raise PermissionDenied("Password change required before accessing this portal area.")


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
        if child:
            return child, children
        # child_id supplied but not matched (e.g. stale frontend cache) — fall back
        return children.first(), children
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
    from django.db.models import Q as _Q
    if not child:
        return []
    candidates = {
        child.admission_number,
        f"LIB-{child.id}",
        f"LIB-{child.id:03d}",
    }
    return list(
        LibraryMember.objects.filter(
            _Q(student=child) | _Q(member_id__in=[v for v in candidates if v]),
            member_type="Student",
            is_active=True,
        ).values_list("id", flat=True).distinct()
    )


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
        def _to_dt(d):
            if isinstance(d, _datetime):
                return d if d.tzinfo else timezone.make_aware(d)
            if isinstance(d, _date):
                return timezone.make_aware(_datetime(d.year, d.month, d.day))
            return d
        activity = sorted(activity, key=lambda item: _to_dt(item["date"]), reverse=True)[:10]
        for item in activity:
            item["date"] = str(item["date"])[:10]
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
        rows = AssessmentGrade.objects.filter(
            student=child,
            is_active=True,
            grade_band__isnull=False,
        ).select_related("assessment", "assessment__subject", "grade_band").order_by("-assessment__date")
        result = []
        for r in rows[:300]:
            grade_label = getattr(r.grade_band, "label", "") or ""
            if not grade_label:
                continue
            result.append({
                "id": r.id,
                "assessment": r.assessment.name,
                "subject": r.assessment.subject.name,
                "category": r.assessment.category,
                "date": r.assessment.date,
                "raw_score": r.raw_score,
                "percentage": r.percentage,
                "grade": grade_label,
            })
        return Response(result)


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

        _GRADE_MAP = {
            "A": "EE", "A-": "EE", "A+": "EE",
            "B+": "ME", "B": "ME", "B-": "ME",
            "C+": "AE", "C": "AE", "C-": "AE",
            "D+": "BE", "D": "BE", "D-": "BE", "E": "BE",
        }

        rows = ReportCard.objects.filter(student=child, is_active=True).select_related("term", "academic_year").order_by("-id")
        seen_terms = set()
        cards = []
        for r in rows:
            dedup_key = (r.term_id, r.academic_year_id)
            if dedup_key in seen_terms:
                continue
            seen_terms.add(dedup_key)
            cards.append({
                "id": r.id,
                "academic_year": r.academic_year.name if r.academic_year_id else "—",
                "term": r.term.name if r.term_id else "—",
                "status": r.status,
                "overall_grade": _GRADE_MAP.get(r.overall_grade or "", r.overall_grade or ""),
                "download_url": f"/api/parent-portal/academics/report-cards/{r.id}/download/",
            })
        return Response(cards)


class ParentReportCardDownloadView(ParentPortalAccessMixin, APIView):
    def get(self, request, card_id):
        child, _ = _pick_child(request)
        from school.models import ReportCard, AssessmentGrade, SchoolProfile

        card = ReportCard.objects.filter(id=card_id, student=child, is_active=True).first() if child else None
        if not card:
            return Response({"error": "Report card not found."}, status=status.HTTP_404_NOT_FOUND)
        profile = SchoolProfile.objects.filter(is_active=True).first()
        school_name = getattr(profile, "school_name", "RynatySchool SmartCampus")
        school_phone = getattr(profile, "phone", "+254 700 000 000")
        school_email = getattr(profile, "email_address", "info@rynatyschool.app")
        student_name = f"{child.first_name} {child.last_name}"
        adm = child.admission_number
        term_name = card.term.name if card.term else "—"
        year_name = card.term.academic_year.name if card.term and card.term.academic_year else "—"
        class_name = card.school_class.name if card.school_class else "—"
        # Get grade breakdown for this card
        grades = AssessmentGrade.objects.filter(
            assessment__term=card.term,
            assessment__school_class=card.school_class,
            student=child,
        ).select_related("assessment__subject").order_by("assessment__subject__name")
        subject_rows = ""
        for g in grades:
            subj = g.assessment.subject.name if g.assessment.subject else "—"
            score = g.marks_obtained or 0
            out_of = g.assessment.max_marks or 100
            pct = round((score / out_of) * 100) if out_of else 0
            grade_letter = "A" if pct >= 80 else "B" if pct >= 65 else "C" if pct >= 50 else "D" if pct >= 40 else "E"
            color = "#166534" if pct >= 80 else "#1e40af" if pct >= 65 else "#92400e" if pct >= 50 else "#991b1b"
            subject_rows += f"<tr><td>{subj}</td><td style='text-align:center'>{score}/{out_of}</td><td style='text-align:center'>{pct}%</td><td style='text-align:center;font-weight:bold;color:{color}'>{grade_letter}</td></tr>"
        if not subject_rows:
            subject_rows = "<tr><td colspan='4' style='text-align:center;color:#888'>No assessment grades found for this term.</td></tr>"
        avg_pct = card.overall_percentage or 0
        html = f"""<!doctype html><html><head><meta charset='UTF-8'>
<title>Report Card — {student_name}</title>
<style>
  body{{font-family:Arial,sans-serif;max-width:720px;margin:40px auto;color:#222;}}
  .header{{text-align:center;border-bottom:3px solid #10b981;padding-bottom:16px;margin-bottom:24px;}}
  .logo{{font-size:24px;font-weight:bold;color:#10b981;}}
  .subtitle{{font-size:14px;color:#666;margin-top:4px;}}
  .info-grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin:20px 0;}}
  .info-box{{background:#f9f9f9;padding:12px;border-radius:6px;}}
  .info-box label{{font-size:11px;color:#666;text-transform:uppercase;}}
  .info-box p{{margin:4px 0 0;font-weight:bold;}}
  table{{width:100%;border-collapse:collapse;margin:16px 0;}}
  th{{background:#10b981;color:white;padding:10px 12px;text-align:left;}}
  td{{padding:10px 12px;border-bottom:1px solid #eee;}}
  .summary{{background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:16px;margin:20px 0;text-align:center;}}
  .avg-pct{{font-size:36px;font-weight:bold;color:#10b981;}}
  .footer{{margin-top:32px;text-align:center;font-size:12px;color:#888;border-top:1px solid #eee;padding-top:12px;}}
  @media print{{body{{margin:20px;}} .no-print{{display:none;}}}}
</style></head><body>
<div class='header'>
  <div class='logo'>{school_name}</div>
  <div class='subtitle'>{school_phone} | {school_email}</div>
  <div style='font-size:18px;font-weight:bold;margin-top:8px'>STUDENT ACADEMIC REPORT CARD</div>
  <div style='font-size:14px;color:#666'>{year_name} &bull; {term_name}</div>
</div>
<div class='info-grid'>
  <div class='info-box'><label>Student Name</label><p>{student_name}</p></div>
  <div class='info-box'><label>Admission No.</label><p>{adm}</p></div>
  <div class='info-box'><label>Class</label><p>{class_name}</p></div>
</div>
<table><thead><tr><th>Subject</th><th style='text-align:center'>Score</th><th style='text-align:center'>Percentage</th><th style='text-align:center'>Grade</th></tr></thead>
<tbody>{subject_rows}</tbody></table>
<div class='summary'>
  <div style='font-size:14px;color:#555;margin-bottom:8px'>Overall Performance</div>
  <div class='avg-pct'>{avg_pct:.1f}%</div>
  <div style='font-size:14px;color:#555;margin-top:4px'>{"Excellent" if avg_pct >= 80 else "Good" if avg_pct >= 65 else "Satisfactory" if avg_pct >= 50 else "Needs Improvement"}</div>
</div>
<div class='no-print' style='text-align:center;margin:20px'>
  <button onclick='window.print()' style='background:#10b981;color:white;border:none;padding:10px 32px;border-radius:6px;font-size:16px;cursor:pointer'>🖨️ Print / Save as PDF</button>
</div>
<div class='footer'>{school_name} &bull; Generated on {timezone.now().strftime('%d %b %Y %H:%M')} &bull; rynatyschool.app</div>
</body></html>"""
        return HttpResponse(html, content_type="text/html")


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
        from school.models import InvoiceLineItem, SchoolProfile
        line_items = InvoiceLineItem.objects.filter(invoice=row)
        profile = SchoolProfile.objects.filter(is_active=True).first()
        school_name = getattr(profile, "school_name", "RynatySchool SmartCampus")
        school_phone = getattr(profile, "phone", "+254 700 000 000")
        school_email = getattr(profile, "email_address", "info@rynatyschool.app")
        currency = getattr(profile, "currency", "KES")
        student_name = f"{row.student.first_name} {row.student.last_name}" if row.student else "—"
        adm = getattr(row.student, "admission_number", "—")
        items_html = "".join([
            f"<tr><td>{li.description or (li.fee_structure.name if li.fee_structure else '—')}</td>"
            f"<td style='text-align:right'>{currency} {li.amount:,.2f}</td></tr>"
            for li in line_items
        ]) or f"<tr><td colspan='2'>Invoice #{row.id}</td></tr>"
        html = f"""<!doctype html><html><head><meta charset='UTF-8'>
<title>Invoice {getattr(profile,'invoice_prefix','INV-')}{row.id}</title>
<style>
  body{{font-family:Arial,sans-serif;max-width:700px;margin:40px auto;color:#222;}}
  .header{{display:flex;justify-content:space-between;align-items:center;border-bottom:3px solid #10b981;padding-bottom:12px;margin-bottom:24px;}}
  .logo{{font-size:22px;font-weight:bold;color:#10b981;}}
  h2{{margin:0;font-size:18px;}}
  .info-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:24px 0;}}
  .info-box{{background:#f9f9f9;padding:12px;border-radius:6px;}}
  .info-box label{{font-size:11px;color:#666;text-transform:uppercase;}}
  .info-box p{{margin:4px 0 0;font-weight:bold;}}
  table{{width:100%;border-collapse:collapse;margin:24px 0;}}
  th{{background:#10b981;color:white;padding:10px 12px;text-align:left;}}
  td{{padding:10px 12px;border-bottom:1px solid #eee;}}
  .total-row{{font-weight:bold;font-size:16px;background:#f0fdf4;}}
  .status-badge{{display:inline-block;padding:4px 12px;border-radius:20px;font-size:13px;font-weight:bold;
    background:{('#dcfce7' if row.status=='PAID' else '#fff3cd' if row.status=='CONFIRMED' else '#fee2e2')};
    color:{('#166534' if row.status=='PAID' else '#92400e' if row.status=='CONFIRMED' else '#991b1b')};}}
  .footer{{margin-top:40px;text-align:center;font-size:12px;color:#888;border-top:1px solid #eee;padding-top:12px;}}
  @media print{{body{{margin:20px;}} .no-print{{display:none;}}}}
</style></head><body>
<div class='header'>
  <div><div class='logo'>{school_name}</div><div style='font-size:12px;color:#666'>{school_phone} | {school_email}</div></div>
  <h2>INVOICE</h2>
</div>
<div class='info-grid'>
  <div class='info-box'><label>Student</label><p>{student_name}</p><p style='font-weight:normal;font-size:13px'>Adm: {adm}</p></div>
  <div class='info-box'><label>Invoice Number</label><p>{getattr(profile,'invoice_prefix','INV-')}{row.id}</p></div>
  <div class='info-box'><label>Invoice Date</label><p>{row.invoice_date or '—'}</p></div>
  <div class='info-box'><label>Due Date</label><p>{row.due_date or '—'}</p></div>
</div>
<p>Status: <span class='status-badge'>{row.status}</span></p>
<table><thead><tr><th>Description</th><th style='text-align:right'>Amount ({currency})</th></tr></thead>
<tbody>{items_html}</tbody>
<tfoot>
  <tr class='total-row'><td>Total Billed</td><td style='text-align:right'>{currency} {row.total_amount:,.2f}</td></tr>
  <tr><td>Amount Paid</td><td style='text-align:right'>{currency} {row.amount_paid:,.2f}</td></tr>
  <tr class='total-row'><td>Balance Due</td><td style='text-align:right'>{currency} {row.balance_due:,.2f}</td></tr>
</tfoot></table>
<div class='no-print' style='text-align:center;margin:20px'>
  <button onclick='window.print()' style='background:#10b981;color:white;border:none;padding:10px 32px;border-radius:6px;font-size:16px;cursor:pointer'>🖨️ Print / Save as PDF</button>
</div>
<div class='footer'>{school_name} &bull; Generated on {timezone.now().strftime('%d %b %Y %H:%M')} &bull; rynatyschool.app</div>
</body></html>"""
        return HttpResponse(html, content_type="text/html")


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
        from school.models import SchoolProfile
        profile = SchoolProfile.objects.filter(is_active=True).first()
        school_name = getattr(profile, "school_name", "RynatySchool SmartCampus")
        school_phone = getattr(profile, "phone", "+254 700 000 000")
        school_email = getattr(profile, "email_address", "info@rynatyschool.app")
        currency = getattr(profile, "currency", "KES")
        receipt_prefix = getattr(profile, "receipt_prefix", "RCT-")
        student_name = f"{row.student.first_name} {row.student.last_name}" if row.student else "—"
        adm = getattr(row.student, "admission_number", "—")
        receipt_no = row.receipt_number or f"{receipt_prefix}{row.id}"
        allocations = row.paymentallocation_set.select_related("invoice").all()
        alloc_rows = "".join([
            f"<tr><td>Invoice #{a.invoice.id if a.invoice else '—'}</td><td style='text-align:right'>{currency} {a.amount_allocated:,.2f}</td></tr>"
            for a in allocations
        ]) or f"<tr><td>Payment</td><td style='text-align:right'>{currency} {row.amount:,.2f}</td></tr>"
        html = f"""<!doctype html><html><head><meta charset='UTF-8'>
<title>Receipt {receipt_no}</title>
<style>
  body{{font-family:Arial,sans-serif;max-width:600px;margin:40px auto;color:#222;}}
  .header{{text-align:center;border-bottom:3px solid #10b981;padding-bottom:16px;margin-bottom:24px;}}
  .logo{{font-size:24px;font-weight:bold;color:#10b981;margin-bottom:4px;}}
  .receipt-no{{font-size:14px;color:#666;}}
  .info-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:20px 0;}}
  .info-box{{background:#f9f9f9;padding:12px;border-radius:6px;}}
  .info-box label{{font-size:11px;color:#666;text-transform:uppercase;}}
  .info-box p{{margin:4px 0 0;font-weight:bold;}}
  .stamp{{text-align:center;margin:24px 0;}}
  .paid-stamp{{display:inline-block;border:4px solid #10b981;color:#10b981;font-size:32px;font-weight:bold;
    padding:8px 32px;border-radius:8px;transform:rotate(-5deg);letter-spacing:4px;}}
  table{{width:100%;border-collapse:collapse;margin:16px 0;}}
  th{{background:#10b981;color:white;padding:8px 12px;text-align:left;}}
  td{{padding:8px 12px;border-bottom:1px solid #eee;}}
  .total-row{{font-weight:bold;background:#f0fdf4;}}
  .footer{{margin-top:32px;text-align:center;font-size:12px;color:#888;border-top:1px solid #eee;padding-top:12px;}}
  @media print{{body{{margin:20px;}} .no-print{{display:none;}}}}
</style></head><body>
<div class='header'>
  <div class='logo'>{school_name}</div>
  <div style='font-size:12px;color:#666'>{school_phone} | {school_email}</div>
  <div class='receipt-no'>OFFICIAL PAYMENT RECEIPT</div>
</div>
<div class='info-grid'>
  <div class='info-box'><label>Student</label><p>{student_name}</p><p style='font-weight:normal;font-size:13px'>Adm: {adm}</p></div>
  <div class='info-box'><label>Receipt No.</label><p>{receipt_no}</p></div>
  <div class='info-box'><label>Payment Date</label><p>{row.payment_date or '—'}</p></div>
  <div class='info-box'><label>Payment Method</label><p>{row.payment_method or '—'}</p></div>
</div>
<div class='stamp'><div class='paid-stamp'>PAID</div></div>
<table><thead><tr><th>Description</th><th style='text-align:right'>Amount ({currency})</th></tr></thead>
<tbody>{alloc_rows}</tbody>
<tfoot><tr class='total-row'><td>Total Received</td><td style='text-align:right'>{currency} {row.amount:,.2f}</td></tr></tfoot>
</table>
{f"<p style='font-size:13px;color:#555'>Ref: {row.reference_number}</p>" if row.reference_number else ""}
{f"<p style='font-size:13px;color:#555'>Notes: {row.notes}</p>" if row.notes else ""}
<div class='no-print' style='text-align:center;margin:20px'>
  <button onclick='window.print()' style='background:#10b981;color:white;border:none;padding:10px 32px;border-radius:6px;font-size:16px;cursor:pointer'>🖨️ Print / Save as PDF</button>
</div>
<div class='footer'>{school_name} &bull; Generated on {timezone.now().strftime('%d %b %Y %H:%M')} &bull; rynatyschool.app</div>
</body></html>"""
        return HttpResponse(html, content_type="text/html")


class ParentFinancePayView(ParentPortalAccessMixin, APIView):
    def post(self, request):
        child, _ = _pick_child(request)
        if not child:
            return _no_linked_child_response()

        try:
            amount = Decimal(str(request.data.get("amount") or "0"))
        except Exception:
            amount = Decimal("0")
        if amount <= 0:
            return Response({"error": "Amount must be greater than zero."}, status=status.HTTP_400_BAD_REQUEST)

        method = (request.data.get("payment_method") or "Online").strip()
        invoice_id = request.data.get("invoice_id")
        invoice = None
        if invoice_id:
            invoice = Invoice.objects.filter(id=invoice_id, student=child, is_active=True).exclude(status="VOID").first()
            if not invoice:
                return Response({"error": "Invoice not found for the selected child."}, status=status.HTTP_404_NOT_FOUND)
            outstanding = Decimal(str(invoice.balance_due or "0"))
            if outstanding <= 0:
                return Response(
                    {"error": "This invoice has no outstanding balance."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if amount > outstanding:
                return Response(
                    {"error": f"Amount KES {amount} exceeds outstanding balance of KES {outstanding}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # ── M-Pesa STK Push path ──────────────────────────────────────────
        if method.lower() in ("mpesa", "m-pesa", "mobile money"):
            phone = (request.data.get("phone") or "").strip()
            if not phone:
                return Response(
                    {"error": "Phone number is required for M-Pesa payment."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            from school.mpesa import initiate_stk_push, MpesaError
            callback_url, _ = FinanceService.resolve_public_url(
                "/api/finance/mpesa/callback/",
                request=request,
            )
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
                invoice_id=invoice.id if invoice else invoice_id,
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
        if method.lower() in ("stripe", "card", "online", "online payment"):
            from school.stripe import StripeError

            try:
                checkout = FinanceService.create_stripe_checkout_transaction(
                    request=request,
                    student=child,
                    amount=amount,
                    initiated_by=request.user,
                    invoice=invoice,
                    source="parent_portal",
                    notes=request.data.get("notes") or f"Parent portal payment for {child.first_name} {child.last_name}",
                    description=request.data.get("description") or "School Fees",
                    reference=request.data.get("reference"),
                    success_url=request.data.get("success_url") or "/modules/parent-portal/finance?stripe=success&session_id={CHECKOUT_SESSION_ID}",
                    cancel_url=request.data.get("cancel_url") or "/modules/parent-portal/finance?stripe=cancel",
                    customer_email=request.data.get("customer_email") or request.user.email,
                    extra_payload={
                        "portal_type": "parent",
                    },
                )
            except (StripeError, ValueError) as exc:
                return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

            tx = checkout["transaction"]
            session = checkout["session"]
            return Response(
                {
                    "payment_id": tx.id,
                    "transaction_id": tx.id,
                    "checkout_session_id": session.get("id"),
                    "checkout_url": session.get("url"),
                    "reference_number": checkout["reference"],
                    "reference": checkout["reference"],
                    "payment_method": "Stripe",
                    "status": tx.status,
                    "payment_status": session.get("payment_status"),
                    "configured_mode": session.get("configured_mode"),
                    "message": "Redirect to the hosted Stripe Checkout page to complete payment.",
                },
                status=status.HTTP_201_CREATED,
            )

        reference_number = f"PPORT-{uuid.uuid4().hex[:8].upper()}"
        row = PaymentGatewayTransaction.objects.create(
            provider="parent_portal",
            external_id=reference_number,
            student=child,
            invoice_id=invoice.id if invoice else invoice_id,
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
                "reference": row.external_id,
                "payment_method": method,
                "status": row.status,
                "message": (
                    f"Bank transfer initiated. Use reference {row.external_id} when sending funds. "
                    "Your balance will update after the school reconciles the transfer."
                    if method.lower() in ("bank transfer", "bank", "wire transfer")
                    else f"{method} payment request recorded with reference {row.external_id}. "
                    "It will reflect once the school confirms settlement."
                ),
                "requires_manual_confirmation": True,
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


class ParentFeeStatementDownloadView(ParentPortalAccessMixin, APIView):
    """Returns a printable HTML fee statement for the selected child."""
    def get(self, request):
        child, _ = _pick_child(request)
        if not child:
            return _no_linked_child_response()
        from school.models import InvoiceLineItem, SchoolProfile
        invoices = Invoice.objects.filter(student=child, is_active=True).order_by("invoice_date", "id")
        payments = Payment.objects.filter(student=child, is_active=True).order_by("payment_date", "id")
        billed = invoices.aggregate(v=Sum("total_amount")).get("v") or Decimal("0.00")
        paid = payments.aggregate(v=Sum("amount")).get("v") or Decimal("0.00")
        balance = billed - paid
        profile = SchoolProfile.objects.filter(is_active=True).first()
        school_name = getattr(profile, "school_name", "RynatySchool SmartCampus")
        school_phone = getattr(profile, "phone", "+254 700 000 000")
        school_email = getattr(profile, "email_address", "info@rynatyschool.app")
        currency = getattr(profile, "currency", "KES")
        student_name = f"{child.first_name} {child.last_name}"
        adm = child.admission_number
        _inv_parts = []
        for r in invoices:
            _bg = "#dcfce7" if r.status == "PAID" else "#fef3c7"
            _inv_parts.append(
                f"<tr><td>{r.invoice_date or '—'}</td><td>Invoice #{r.id}</td>"
                f"<td style='text-align:right'>{currency} {r.total_amount:,.2f}</td>"
                f"<td style='text-align:right'>{currency} {r.amount_paid:,.2f}</td>"
                f"<td><span style='padding:2px 8px;border-radius:10px;font-size:12px;background:{_bg};'>{r.status}</span></td></tr>"
            )
        inv_rows = "".join(_inv_parts) or "<tr><td colspan='5' style='text-align:center;color:#888'>No invoices found.</td></tr>"
        pmt_rows = "".join([
            f"<tr><td>{r.payment_date or '—'}</td><td>{r.reference_number or '—'}</td>"
            f"<td>{r.payment_method or '—'}</td>"
            f"<td style='text-align:right;color:#166534'>{currency} {r.amount:,.2f}</td></tr>"
            for r in payments
        ]) or "<tr><td colspan='4' style='text-align:center;color:#888'>No payments recorded.</td></tr>"
        bal_color = "#991b1b" if balance > 0 else "#166534"
        html = f"""<!doctype html><html><head><meta charset='UTF-8'>
<title>Fee Statement — {student_name}</title>
<style>
  body{{font-family:Arial,sans-serif;max-width:760px;margin:40px auto;color:#222;}}
  .header{{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:3px solid #10b981;padding-bottom:12px;margin-bottom:24px;}}
  .logo{{font-size:22px;font-weight:bold;color:#10b981;}}
  h2{{margin:0;font-size:18px;color:#333;}}
  .info-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:20px 0;}}
  .info-box{{background:#f9f9f9;padding:12px;border-radius:6px;}}
  .info-box label{{font-size:11px;color:#666;text-transform:uppercase;}}
  .info-box p{{margin:4px 0 0;font-weight:bold;}}
  h3{{color:#10b981;border-bottom:2px solid #d1fae5;padding-bottom:6px;margin-top:28px;}}
  table{{width:100%;border-collapse:collapse;margin:12px 0;}}
  th{{background:#10b981;color:white;padding:8px 12px;text-align:left;font-size:13px;}}
  td{{padding:8px 12px;border-bottom:1px solid #eee;font-size:13px;}}
  .summary-box{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin:24px 0;}}
  .sbox{{padding:16px;border-radius:8px;text-align:center;}}
  .sbox label{{font-size:11px;color:#555;text-transform:uppercase;display:block;margin-bottom:6px;}}
  .sbox span{{font-size:22px;font-weight:bold;}}
  .footer{{margin-top:32px;text-align:center;font-size:12px;color:#888;border-top:1px solid #eee;padding-top:12px;}}
  @media print{{body{{margin:20px;}} .no-print{{display:none;}}}}
</style></head><body>
<div class='header'>
  <div><div class='logo'>{school_name}</div><div style='font-size:12px;color:#666'>{school_phone} | {school_email}</div></div>
  <h2>STUDENT FEE STATEMENT</h2>
</div>
<div class='info-grid'>
  <div class='info-box'><label>Student</label><p>{student_name}</p></div>
  <div class='info-box'><label>Admission No.</label><p>{adm}</p></div>
</div>
<div class='summary-box'>
  <div class='sbox' style='background:#fef3c7'><label>Total Billed</label><span style='color:#92400e'>{currency} {billed:,.2f}</span></div>
  <div class='sbox' style='background:#d1fae5'><label>Total Paid</label><span style='color:#065f46'>{currency} {paid:,.2f}</span></div>
  <div class='sbox' style='background:{"#fee2e2" if balance>0 else "#d1fae5"}'><label>Outstanding Balance</label><span style='color:{bal_color}'>{currency} {balance:,.2f}</span></div>
</div>
<h3>Invoices</h3>
<table><thead><tr><th>Date</th><th>Description</th><th style='text-align:right'>Amount</th><th style='text-align:right'>Paid</th><th>Status</th></tr></thead>
<tbody>{inv_rows}</tbody></table>
<h3>Payments</h3>
<table><thead><tr><th>Date</th><th>Reference</th><th>Method</th><th style='text-align:right'>Amount</th></tr></thead>
<tbody>{pmt_rows}</tbody></table>
<div class='no-print' style='text-align:center;margin:24px'>
  <button onclick='window.print()' style='background:#10b981;color:white;border:none;padding:10px 32px;border-radius:6px;font-size:16px;cursor:pointer'>🖨️ Print / Save as PDF</button>
</div>
<div class='footer'>{school_name} &bull; Generated on {timezone.now().strftime('%d %b %Y %H:%M')} &bull; rynatyschool.app</div>
</body></html>"""
        return HttpResponse(html, content_type="text/html")


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
    """Returns the weekly timetable (schedule) for the child's class."""
    def get(self, request):
        from timetable.models import TimetableSlot
        child, _ = _pick_child(request)
        enrollment = _active_enrollment(child)
        if not child or not enrollment:
            return _no_linked_child_or_enrollment_response()
        rows = (
            TimetableSlot.objects.filter(
                school_class=enrollment.school_class,
                is_active=True,
            )
            .select_related("subject", "teacher")
            .order_by("day_of_week", "period_number")
        )
        DAY_NAMES = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday"}
        return Response([
            {
                "id": r.id,
                "day_of_week": r.day_of_week,
                "day_name": DAY_NAMES.get(r.day_of_week, str(r.day_of_week)),
                "period_number": r.period_number,
                "start_time": r.start_time,
                "end_time": r.end_time,
                "subject": r.subject.name if r.subject else None,
                "teacher": f"{r.teacher.first_name} {r.teacher.last_name}".strip() if r.teacher else None,
                "room": r.room,
            }
            for r in rows[:200]
        ])


# Alias — frontend calls academics/schedule/ for the weekly timetable
ParentScheduleView = ParentTimetableView


class ParentTimetableExportView(ParentPortalAccessMixin, APIView):
    def get(self, request):
        from timetable.models import TimetableSlot
        child, _ = _pick_child(request)
        enrollment = _active_enrollment(child)
        if not child or not enrollment:
            return _no_linked_child_or_enrollment_response()
        rows = (
            TimetableSlot.objects.filter(
                school_class=enrollment.school_class,
                is_active=True,
            )
            .select_related("subject", "teacher")
            .order_by("day_of_week", "period_number")[:200]
        )
        DAY_NAMES = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday"}
        payload = ["day,period,start_time,end_time,subject,teacher,room"]
        payload.extend(
            f"{DAY_NAMES.get(r.day_of_week,'')},{r.period_number},{r.start_time},{r.end_time},"
            f"{r.subject.name if r.subject else ''},{(r.teacher.get_full_name() if r.teacher else '')},{r.room}"
            for r in rows
        )
        response = HttpResponse("\n".join(payload), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="schedule_{child.id}.csv"'
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
        if not child:
            return _no_linked_child_response()
        enrollment = _active_enrollment(child)
        if not enrollment:
            return Response([])
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
        member_lookup = set(member_ids)
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
        member_lookup = set(member_ids)
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
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        return Response(
            ParentProfileSerializer(request.user, context={"request": request}).data
        )

    def patch(self, request):
        user = request.user
        profile = getattr(user, "userprofile", None)

        serializer = ParentProfileSerializer(
            user, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        if profile:
            profile_fields = []
            if "phone" in request.data:
                profile.phone = (request.data.get("phone") or "").strip()
                profile_fields.append("phone")
            if "photo" in request.FILES:
                profile.photo = request.FILES["photo"]
                profile_fields.append("photo")
            if profile_fields:
                profile.save(update_fields=profile_fields)

        return Response(
            ParentProfileSerializer(user, context={"request": request}).data
        )


class ParentChangePasswordView(ParentPortalAccessMixin, APIView):
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
            'current_medications', 'doctor_name', 'doctor_phone',
            'notes', 'updated_at'
        ).first()

        immunizations = list(ImmunizationRecord.objects.filter(student=child).values(
            'id', 'vaccine_name', 'date_administered', 'booster_due_date', 'created_at'
        ).order_by('-date_administered')[:20])

        clinic_visits = list(ClinicVisit.objects.filter(student=child).values(
            'id', 'visit_date', 'visit_time', 'complaint', 'treatment',
            'severity', 'parent_notified', 'created_at'
        ).order_by('-visit_date')[:20])

        return Response({
            "child_id": child.id,
            "child_name": f"{child.first_name} {child.last_name}".strip(),
            "medical_record": medical,
            "immunizations": immunizations,
            "clinic_visits": clinic_visits,
            "children": [{"id": c.id, "name": f"{c.first_name} {c.last_name}".strip()} for c in children],
        })


class ParentAttendanceRecentView(ParentPortalAccessMixin, APIView):
    """Returns the 30 most recent attendance records for the linked child."""
    def get(self, request):
        child, _ = _pick_child(request)
        if not child:
            return _no_linked_child_response()
        rows = AttendanceRecord.objects.filter(student=child).order_by("-date")[:30]
        return Response([
            {
                "id": r.id,
                "date": r.date,
                "status": r.status,
                "notes": r.notes,
            }
            for r in rows
        ])


class ParentHealthRecordsView(ParentPortalAccessMixin, APIView):
    """Health/medical records for linked child (alias of ParentHealthView for /health/records/)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from school.models import MedicalRecord, ImmunizationRecord, ClinicVisit
        child, children = _pick_child(request)
        if not child:
            return _no_linked_child_response()
        medical = MedicalRecord.objects.filter(student=child).values(
            "id", "blood_type", "allergies", "chronic_conditions",
            "current_medications", "doctor_name", "doctor_phone",
            "notes", "updated_at",
        ).first()
        immunizations = list(ImmunizationRecord.objects.filter(student=child).values(
            "id", "vaccine_name", "date_administered", "booster_due_date", "created_at",
        ).order_by("-date_administered")[:20])
        return Response({
            "child_id": child.id,
            "child_name": f"{child.first_name} {child.last_name}".strip(),
            "medical_record": medical,
            "immunizations": immunizations,
        })


class ParentHealthVisitsView(ParentPortalAccessMixin, APIView):
    """Clinic visit history for the linked child."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from school.models import ClinicVisit
        child, _ = _pick_child(request)
        if not child:
            return _no_linked_child_response()
        visits = list(ClinicVisit.objects.filter(student=child).values(
            "id", "visit_date", "visit_time", "complaint",
            "treatment", "severity", "parent_notified", "created_at",
        ).order_by("-visit_date")[:50])
        return Response(visits)


class ParentConversationsView(ParentPortalAccessMixin, APIView):
    """Message threads / conversations for the parent."""
    def get(self, request):
        rows = Message.objects.filter(
            Q(recipient_id=request.user.id, recipient_type="PARENT")
            | Q(recipient_type="STAFF")
        ).order_by("-sent_at")[:50]
        return Response([
            {
                "id": r.id,
                "subject": r.subject,
                "body": r.body,
                "sent_at": r.sent_at,
                "status": r.status,
            }
            for r in rows
        ])

    def post(self, request):
        subject = (request.data.get("subject") or "").strip()
        body = (request.data.get("body") or "").strip()
        if not subject or not body:
            return Response({"error": "subject and body are required"}, status=status.HTTP_400_BAD_REQUEST)
        row = Message.objects.create(
            recipient_type="STAFF",
            recipient_id=0,
            subject=subject,
            body=body,
            status="SENT",
        )
        return Response(
            {"id": row.id, "subject": row.subject, "body": row.body, "sent_at": row.sent_at, "status": row.status},
            status=status.HTTP_201_CREATED,
        )


class ParentProfileSettingsView(ParentPortalAccessMixin, APIView):
    """Combined profile settings: notification preferences + profile info."""
    def get(self, request):
        prefs = NotificationPreference.objects.filter(user=request.user).order_by("notification_type")
        return Response({
            "profile": ParentProfileSerializer(request.user).data,
            "notification_preferences": [
                {
                    "id": p.id,
                    "notification_type": p.notification_type,
                    "channel_in_app": p.channel_in_app,
                    "channel_email": p.channel_email,
                    "channel_sms": p.channel_sms,
                    "channel_push": p.channel_push,
                }
                for p in prefs
            ],
        })

    def patch(self, request):
        serializer = ParentProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


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
                "child_name": f"{child.first_name} {child.last_name}".strip(),
                "assignment": None,
                "children": [{"id": c.id, "name": f"{c.first_name} {c.last_name}".strip()} for c in children],
            })

        route = assignment.route
        vehicle = route.vehicle if route else None
        driver = vehicle.driver if vehicle else None

        stops = list(route.stops.values('id', 'stop_name', 'sequence', 'estimated_time', 'landmark').order_by('sequence')) if route else []

        return Response({
            "child_id": child.id,
            "child_name": f"{child.first_name} {child.last_name}".strip(),
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
            "children": [{"id": c.id, "name": f"{c.first_name} {c.last_name}".strip()} for c in children],
        })
