from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Q, Sum
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from communication.models import Announcement
from elearning.models import CourseMaterial
from library.models import CirculationTransaction, LibraryMember, LibraryResource
from school.models import (
    AssessmentGrade,
    Assignment,
    AssignmentSubmission,
    AttendanceRecord,
    CalendarEvent,
    Enrollment,
    Invoice,
    Payment,
    Student,
    TermResult,
    UserProfile,
)
from school.permissions import HasModuleAccess


class StudentPortalAccessMixin:
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENT_PORTAL"


def _student_from_request(user):
    profile = (
        UserProfile.objects
        .select_related("role")
        .filter(user=user)
        .first()
    )
    if profile and getattr(profile.role, "name", "") == "STUDENT" and profile.admission_number:
        by_bridge = Student.objects.filter(
            is_active=True,
            admission_number__iexact=profile.admission_number,
        ).first()
        if by_bridge:
            return by_bridge

    by_admission = Student.objects.filter(
        is_active=True,
        admission_number__iexact=user.username,
    ).first()
    if by_admission:
        return by_admission

    return None


def _active_enrollment_for_student(student):
    if not student:
        return None
    return (
        Enrollment.objects.filter(student=student, is_active=True, status="Active")
        .order_by("-id")
        .first()
    )


def _pending_assignments_count(student):
    enrollment = _active_enrollment_for_student(student)
    if not enrollment:
        return 0
    submitted_ids = set(
        AssignmentSubmission.objects.filter(student=student, is_active=True)
        .values_list("assignment_id", flat=True)
    )
    return Assignment.objects.filter(
        class_section=enrollment.school_class, is_active=True
    ).exclude(id__in=submitted_ids).count()


def _student_library_member_ids(student):
    if not student:
        return []

    candidates = {
        student.admission_number,
        f"LIB-STU-{student.id}",
        f"LIB-{student.id}",
        f"LIB-{student.id:03d}",
    }
    return list(
        LibraryMember.objects.filter(
            Q(student=student) | Q(member_id__in=[value for value in candidates if value]),
            member_type="Student",
            is_active=True,
        )
        .values_list("id", flat=True)
        .distinct()
    )


def _student_material_type(material_type: str) -> str:
    mapping = {
        "PDF": "PDF",
        "Video": "VIDEO",
        "Link": "LINK",
        "Presentation": "DOCUMENT",
        "Note": "DOCUMENT",
    }
    return mapping.get(material_type, material_type or "DOCUMENT")


class StudentDashboardView(StudentPortalAccessMixin, APIView):
    def get(self, request):
        student = _student_from_request(request.user)
        if not student:
            return Response({
                "student": None,
                "kpis": {"attendance_rate": 0, "current_average_grade": "—",
                         "pending_assignments": 0, "upcoming_events": 0},
                "recent_grades": [],
                "upcoming_assignments": [],
                "announcements": [],
            })

        enrollment = _active_enrollment_for_student(student)

        att = AttendanceRecord.objects.filter(student=student)
        total = att.count()
        present = att.filter(status="Present").count()
        att_rate = round((present / total) * 100, 2) if total else 0

        avg = (
            TermResult.objects.filter(student=student, is_active=True)
            .aggregate(v=Avg("total_score"))
            .get("v")
        ) or 0

        upcoming_events = CalendarEvent.objects.filter(
            is_active=True, start_date__gte=timezone.now().date()
        ).count()

        pending_count = _pending_assignments_count(student)

        recent_grades = []
        for g in (
            AssessmentGrade.objects.filter(student=student, is_active=True)
            .select_related("assessment", "assessment__subject", "grade_band")
            .order_by("-entered_at")[:5]
        ):
            recent_grades.append({
                "subject": g.assessment.subject.name,
                "assessment": g.assessment.name,
                "grade": getattr(g.grade_band, "label", str(g.raw_score or "")),
            })

        upcoming_assignments = []
        if enrollment:
            submitted_ids = set(
                AssignmentSubmission.objects.filter(student=student, is_active=True)
                .values_list("assignment_id", flat=True)
            )
            for a in (
                Assignment.objects.filter(
                    class_section=enrollment.school_class,
                    is_active=True,
                )
                .exclude(id__in=submitted_ids)
                .select_related("subject")
                .order_by("due_date")[:5]
            ):
                upcoming_assignments.append({
                    "title": a.title,
                    "subject": a.subject.name,
                    "due_date": str(a.due_date) if a.due_date else None,
                })

        announcements = []
        for ann in Announcement.objects.filter(is_active=True).order_by("-created_at")[:5]:
            announcements.append({
                "title": ann.title,
                "content": getattr(ann, "body", getattr(ann, "content", "")),
                "created_at": ann.created_at,
            })

        class_section_name = None
        if enrollment:
            try:
                class_section_name = enrollment.school_class.name
            except Exception:
                pass

        return Response({
            "student": {
                "first_name": student.first_name,
                "last_name": student.last_name,
                "admission_number": student.admission_number,
                "class_section": class_section_name,
            },
            "kpis": {
                "attendance_rate": att_rate,
                "current_average_grade": str(round(float(avg), 1)) if avg else "—",
                "pending_assignments": pending_count,
                "upcoming_events": upcoming_events,
            },
            "recent_grades": recent_grades,
            "upcoming_assignments": upcoming_assignments,
            "announcements": announcements,
        })


class StudentAcademicsGradesView(StudentPortalAccessMixin, APIView):
    def get(self, request):
        student = _student_from_request(request.user)
        if not student:
            return Response({"grades": [], "report_cards": []})

        grades = []
        for g in (
            AssessmentGrade.objects.filter(student=student, is_active=True)
            .select_related("assessment", "assessment__subject", "grade_band")
            .order_by("-assessment__date")[:300]
        ):
            grades.append({
                "subject": g.assessment.subject.name,
                "assessment": g.assessment.name,
                "score": g.raw_score,
                "max_score": g.assessment.max_marks if hasattr(g.assessment, "max_marks") else None,
                "grade": getattr(g.grade_band, "label", ""),
                "date": str(g.assessment.date) if g.assessment.date else None,
                "remarks": g.remarks if hasattr(g, "remarks") else None,
            })

        return Response({"grades": grades})


class StudentReportCardsView(StudentPortalAccessMixin, APIView):
    def get(self, request):
        student = _student_from_request(request.user)
        if not student:
            return Response({"report_cards": []})

        from school.models import ReportCard

        _GRADE_MAP = {
            "A": "EE", "A-": "EE", "A+": "EE",
            "B+": "ME", "B": "ME", "B-": "ME",
            "C+": "AE", "C": "AE", "C-": "AE",
            "D+": "BE", "D": "BE", "D-": "BE", "E": "BE",
        }

        cards = []
        for r in ReportCard.objects.filter(student=student, is_active=True).select_related("term", "academic_year").order_by("-created_at"):
            raw_grade = r.overall_grade or ""
            cbe_grade = _GRADE_MAP.get(raw_grade, raw_grade)
            cards.append({
                "id": r.id,
                "academic_year": r.academic_year.name if r.academic_year_id else "—",
                "term": r.term.name if r.term_id else "—",
                "status": r.status,
                "overall_grade": cbe_grade,
            })

        return Response({"report_cards": cards})


class StudentAttendanceSummaryView(StudentPortalAccessMixin, APIView):
    def get(self, request):
        student = _student_from_request(request.user)
        if not student:
            return Response({"total_days": 0, "present": 0, "absent": 0, "late": 0, "attendance_rate": 0})

        rows = AttendanceRecord.objects.filter(student=student)
        total = rows.count()
        present = rows.filter(status="Present").count()
        absent = rows.filter(status="Absent").count()
        late = rows.filter(status="Late").count()
        return Response({
            "total_days": total,
            "present": present,
            "absent": absent,
            "late": late,
            "attendance_rate": round((present / total) * 100, 2) if total else 0,
        })


class StudentAttendanceCalendarView(StudentPortalAccessMixin, APIView):
    def get(self, request):
        student = _student_from_request(request.user)
        if not student:
            return Response([])

        rows = AttendanceRecord.objects.filter(student=student).order_by("-date")[:180]
        return Response([
            {"id": r.id, "date": r.date, "status": r.status, "notes": r.notes}
            for r in rows
        ])


class StudentAssignmentsView(StudentPortalAccessMixin, APIView):
    def get(self, request):
        student = _student_from_request(request.user)
        if not student:
            return Response([])

        enrollment = _active_enrollment_for_student(student)
        if not enrollment:
            return Response([])

        submission_map = {
            s.assignment_id: s
            for s in AssignmentSubmission.objects.filter(student=student, is_active=True)
        }

        rows = Assignment.objects.filter(
            class_section=enrollment.school_class, is_active=True
        ).select_related("subject").order_by("-due_date")[:200]

        return Response([
            {
                "id": a.id,
                "title": a.title,
                "subject": a.subject.name,
                "due_date": a.due_date,
                "description": a.description,
                "status": "SUBMITTED" if a.id in submission_map else "PENDING",
                "submission_date": getattr(submission_map.get(a.id), "submitted_at", None),
                "submission_grade": getattr(submission_map.get(a.id), "score", None),
            }
            for a in rows
        ])


class StudentLibraryView(StudentPortalAccessMixin, APIView):
    def get(self, request):
        student = _student_from_request(request.user)
        empty_payload = {
            "stats": {
                "available_resources": 0,
                "currently_borrowed": 0,
                "overdue": 0,
                "due_soon": 0,
            },
            "resources": [],
            "borrowed": [],
        }
        if not student:
            return Response(empty_payload)

        member_ids = _student_library_member_ids(student)
        today = timezone.localdate()
        due_soon_end = today + timedelta(days=3)

        resources = (
            LibraryResource.objects.filter(is_active=True)
            .select_related("category")
            .order_by("title", "id")[:100]
        )

        transactions_qs = CirculationTransaction.objects.none()
        if member_ids:
            transactions_qs = (
                CirculationTransaction.objects.filter(member_id__in=member_ids, is_active=True)
                .select_related("copy", "copy__resource", "member")
                .order_by("-issue_date", "-id")
            )

        borrowings = []
        for row in transactions_qs[:50]:
            borrowings.append({
                "id": row.id,
                "resource_title": row.copy.resource.title if row.copy_id and row.copy.resource_id else "",
                "borrow_date": row.issue_date,
                "due_date": row.due_date or row.issue_date.date(),
                "return_date": row.return_date,
                "status": "RETURNED" if row.return_date else "ISSUED",
            })

        currently_borrowed = transactions_qs.filter(return_date__isnull=True).count()
        overdue = transactions_qs.filter(return_date__isnull=True, due_date__lt=today).count()
        due_soon = transactions_qs.filter(
            return_date__isnull=True,
            due_date__gte=today,
            due_date__lte=due_soon_end,
        ).count()

        return Response({
            "stats": {
                "available_resources": LibraryResource.objects.filter(
                    is_active=True,
                    available_copies__gt=0,
                ).count(),
                "currently_borrowed": currently_borrowed,
                "overdue": overdue,
                "due_soon": due_soon,
            },
            "resources": [
                {
                    "id": resource.id,
                    "title": resource.title,
                    "author": resource.authors,
                    "isbn": resource.isbn,
                    "category_name": resource.category.name if resource.category_id else None,
                    "available_copies": resource.available_copies,
                    "total_copies": resource.total_copies,
                    "cover_image": resource.cover_image.url if resource.cover_image else None,
                    "resource_type": resource.resource_type,
                }
                for resource in resources
            ],
            "borrowed": borrowings,
        })


class StudentELearningView(StudentPortalAccessMixin, APIView):
    def get(self, request):
        from django.db.models import Q as _Q
        student = _student_from_request(request.user)
        if not student:
            return Response({"materials": []})

        enrollment = _active_enrollment_for_student(student)

        class_filter = _Q(course__school_class__isnull=True)
        if enrollment and enrollment.school_class_id:
            class_filter |= _Q(course__school_class_id=enrollment.school_class_id)

        rows = (
            CourseMaterial.objects.filter(
                class_filter,
                is_active=True,
                course__is_published=True,
            )
            .select_related("course", "course__subject", "course__school_class")
            .order_by("-created_at", "sequence")[:300]
        )

        return Response({
            "materials": [
                {
                    "id": row.id,
                    "title": row.title,
                    "subject": row.course.subject.name if row.course and row.course.subject_id else row.course.title,
                    "type": _student_material_type(row.material_type),
                    "description": row.content or None,
                    "file_url": row.file_url or None,
                    "external_url": row.link_url or None,
                    "created_at": row.created_at,
                    "grade_level": row.course.school_class.display_name if row.course and row.course.school_class_id else None,
                }
                for row in rows
            ]
        })


class StudentTimetableView(StudentPortalAccessMixin, APIView):
    def get(self, request):
        student = _student_from_request(request.user)
        if not student:
            return Response([])

        enrollment = _active_enrollment_for_student(student)
        if not enrollment or not enrollment.school_class_id:
            return Response([])

        from timetable.models import TimetableSlot

        rows = (
            TimetableSlot.objects.filter(
                school_class_id=enrollment.school_class_id,
                is_active=True,
            )
            .select_related("subject", "teacher", "school_class")
            .order_by("day_of_week", "period_number", "start_time", "id")
        )

        return Response([
            {
                "id": r.id,
                "day": r.get_day_of_week_display(),
                "start_time": r.start_time,
                "end_time": r.end_time,
                "subject": getattr(r.subject, "name", ""),
                "teacher": (
                    r.teacher.get_full_name().strip() or r.teacher.username
                    if r.teacher_id
                    else None
                ),
                "room": r.room or None,
                "class_name": getattr(r.school_class, "display_name", ""),
                "period_number": r.period_number,
            }
            for r in rows
        ])


class MyInvoicesView(StudentPortalAccessMixin, APIView):
    def get(self, request):
        student = _student_from_request(request.user)
        if not student:
            return Response([])

        rows = Invoice.objects.filter(student=student, is_active=True).order_by("-invoice_date", "-id")
        return Response([
            {
                "id": r.id,
                "invoice_number": getattr(r, "invoice_number", f"INV-{r.id}"),
                "description": getattr(r, "description", ""),
                "amount": r.total_amount,
                "amount_paid": r.amount_paid if hasattr(r, "amount_paid") else 0,
                "balance": r.balance if hasattr(r, "balance") else r.total_amount,
                "status": r.status,
                "invoice_date": r.invoice_date,
                "due_date": getattr(r, "due_date", None),
                "term": r.term.name if hasattr(r, "term") and r.term else None,
                "academic_year": r.academic_year.name if hasattr(r, "academic_year") and r.academic_year else None,
            }
            for r in rows[:100]
        ])


class MyPaymentsView(StudentPortalAccessMixin, APIView):
    def get(self, request):
        student = _student_from_request(request.user)
        if not student:
            return Response([])

        rows = Payment.objects.filter(student=student, is_active=True).order_by("-payment_date", "-id")
        return Response([
            {
                "id": r.id,
                "amount_paid": r.amount,
                "payment_date": r.payment_date,
                "payment_method": r.payment_method,
                "transaction_reference": getattr(r, "reference_number", getattr(r, "transaction_reference", "")),
                "notes": getattr(r, "notes", ""),
            }
            for r in rows[:200]
        ])
