from datetime import date

from django.db import models
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from school.permissions import HasModuleAccess, IsSchoolAdmin, IsTeacher
from school.views import AdmissionApplicationViewSet as SchoolAdmissionApplicationViewSet
from school.views import AdmissionsPipelineSummaryView as SchoolAdmissionsPipelineSummaryView
from school.serializers import AdmissionApplicationSerializer
from school.models import (
    AcademicYear,
    AdmissionApplication,
    AuditLog,
    FeeStructure,
    SchoolClass,
    SchoolProfile,
    Staff,
    Subject,
    TeacherAssignment,
    Term,
)
from .models import (
    AdmissionApplicationProfile,
    AdmissionAssessment,
    AdmissionDecision,
    AdmissionInquiry,
    AdmissionInterview,
    AdmissionReview,
)
from .serializers import (
    AdmissionApplicationProfileSerializer,
    AdmissionAssessmentSerializer,
    AdmissionDecisionSerializer,
    AdmissionInquirySerializer,
    AdmissionInterviewSerializer,
    AdmissionReviewSerializer,
)


def _split_child_name(child_name: str):
    value = (child_name or "").strip()
    if not value:
        return "", ""
    parts = [p for p in value.split(" ") if p]
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[0], " ".join(parts[1:])


def _write_audit(user, action: str, model_name: str, object_id, details: str = ""):
    AuditLog.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        action=action,
        model_name=model_name,
        object_id=str(object_id),
        details=details or "",
    )


class AdmissionApplicationViewSet(SchoolAdmissionApplicationViewSet):
    module_key = "ADMISSIONS"

    @staticmethod
    def _build_enrollment_payload(application: AdmissionApplication, request_data=None):
        if hasattr(request_data, "copy"):
            payload = request_data.copy()
        elif hasattr(request_data, "items"):
            payload = dict(request_data.items())
        elif isinstance(request_data, dict):
            payload = dict(request_data)
        else:
            payload = {}

        profile = getattr(application, "normalized_profile", None)
        if not payload.get("school_class") and application.applying_for_grade_id:
            payload["school_class"] = application.applying_for_grade_id
        if not payload.get("term") and profile and profile.term_id:
            payload["term"] = profile.term_id
        return payload

    @staticmethod
    def _enrollment_precheck(application: AdmissionApplication, request_data=None):
        decision_record = getattr(application, "decision_record", None)
        if not decision_record:
            return False, "Admission decision is required before enrollment."
        if decision_record.decision != "Accept":
            return False, "Only accepted applications can be enrolled."
        if decision_record.response_status != "Accepted":
            return False, "Parent acceptance is required before enrollment."
        if decision_record.offer_deadline and date.today() > decision_record.offer_deadline:
            return False, "Offer deadline has passed."
        if not SchoolProfile.objects.filter(is_active=True).exists():
            return False, "School profile must be configured before enrollment."
        if not AcademicYear.objects.filter(is_active=True).exists():
            return False, "At least one active academic year is required before enrollment."
        if not Term.objects.filter(is_active=True).exists():
            return False, "At least one active term is required before enrollment."
        if not Subject.objects.filter(is_active=True).exists():
            return False, "At least one active subject is required before enrollment."
        if not Staff.objects.filter(is_active=True).exists():
            return False, "At least one active staff account is required before enrollment."
        if not TeacherAssignment.objects.filter(is_active=True).exists():
            return False, "Teacher assignments are required before enrollment."

        target_term_id = None
        target_class_id = None
        if hasattr(request_data, "get"):
            target_term_id = request_data.get("term")
            target_class_id = request_data.get("school_class")
        if target_class_id and not SchoolClass.objects.filter(id=target_class_id, is_active=True).exists():
            return False, "Target class must exist and be active before enrollment."
        if target_term_id and not FeeStructure.objects.filter(term_id=target_term_id, is_active=True).exists():
            return False, "Fee structures must be configured for the enrollment term before enrollment."
        return True, None

    @action(detail=True, methods=["post"], url_path="shortlist")
    def shortlist(self, request, pk=None):
        application = self.get_object()
        profile, _ = AdmissionApplicationProfile.objects.get_or_create(application=application)
        profile.is_shortlisted = True
        profile.shortlisted_at = timezone.now()
        profile.save(update_fields=["is_shortlisted", "shortlisted_at"])
        return Response(
            {
                "application_id": application.id,
                "application_number": application.application_number,
                "shortlisted": True,
                "shortlisted_at": profile.shortlisted_at,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="enrollment-check")
    def enrollment_check(self, request, pk=None):
        application = self.get_object()
        decision_record = getattr(application, "decision_record", None)
        deadline_valid = bool(
            not decision_record
            or not decision_record.offer_deadline
            or date.today() <= decision_record.offer_deadline
        )
        checks = {
            "application_exists": True,
            "decision_is_accept": bool(decision_record and decision_record.decision == "Accept"),
            "response_is_accepted": bool(decision_record and decision_record.response_status == "Accepted"),
            "offer_deadline_valid": deadline_valid,
            "has_grade_target": bool(application.applying_for_grade_id),
            "has_guardian_contact": bool(application.guardian_name or application.guardian_phone or application.guardian_email),
        }
        eligible = all(checks.values())
        return Response(
            {
                "application_id": application.id,
                "application_number": application.application_number,
                "eligible": eligible,
                "checks": checks,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="enroll")
    def enroll(self, request, pk=None):
        application = self.get_object()
        resolved_payload = self._build_enrollment_payload(application, request.data)
        ok, reason = self._enrollment_precheck(application, resolved_payload)
        if not ok:
            return Response({"error": reason}, status=status.HTTP_400_BAD_REQUEST)
        request._full_data = resolved_payload
        response = super().enroll(request, pk=pk)
        if response.status_code == status.HTTP_200_OK:
            _write_audit(
                request.user,
                "ENROLL",
                "AdmissionApplication",
                application.id,
                f"Enrollment completed for {application.application_number}.",
            )
        return response

    @action(detail=True, methods=["post"], url_path="enrollment-complete")
    def enrollment_complete(self, request, pk=None):
        return self.enroll(request, pk=pk)


class AdmissionsPipelineSummaryView(SchoolAdmissionsPipelineSummaryView):
    module_key = "ADMISSIONS"


class AdmissionInquiryViewSet(viewsets.ModelViewSet):
    queryset = AdmissionInquiry.objects.all().order_by("-inquiry_date", "-created_at")
    serializer_class = AdmissionInquirySerializer
    permission_classes = [IsSchoolAdmin | IsTeacher, HasModuleAccess]
    module_key = "ADMISSIONS"

    def get_queryset(self):
        queryset = super().get_queryset()
        status_param = self.request.query_params.get("status")
        source = self.request.query_params.get("source")
        search = self.request.query_params.get("search")
        if status_param:
            queryset = queryset.filter(status=status_param)
        if source:
            queryset = queryset.filter(inquiry_source=source)
        if search:
            queryset = queryset.filter(
                models.Q(parent_name__icontains=search)
                | models.Q(child_name__icontains=search)
                | models.Q(parent_email__icontains=search)
                | models.Q(parent_phone__icontains=search)
            )
        return queryset

    @action(detail=True, methods=["post"], url_path="mark-lost")
    def mark_lost(self, request, pk=None):
        inquiry = self.get_object()
        inquiry.status = "Lost"
        inquiry.save(update_fields=["status"])
        return Response(self.get_serializer(inquiry).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="convert")
    def convert(self, request, pk=None):
        inquiry = self.get_object()
        if inquiry.status == "Lost":
            return Response({"error": "Cannot convert a lost inquiry."}, status=status.HTTP_400_BAD_REQUEST)

        first_name, last_name = _split_child_name(inquiry.child_name)
        if not first_name:
            return Response({"error": "Inquiry child name is required."}, status=status.HTTP_400_BAD_REQUEST)

        student_gender = request.data.get("student_gender", "Other")
        if student_gender not in ("Male", "Female", "Other"):
            return Response({"error": "student_gender must be Male, Female, or Other."}, status=status.HTTP_400_BAD_REQUEST)

        raw_application_date = request.data.get("application_date")
        if raw_application_date:
            if isinstance(raw_application_date, date):
                application_date = raw_application_date
            else:
                application_date = parse_date(str(raw_application_date))
                if not application_date:
                    return Response(
                        {"error": "application_date must be a valid YYYY-MM-DD date."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
        else:
            application_date = inquiry.inquiry_date or date.today()

        application = AdmissionApplication.objects.create(
            student_first_name=first_name,
            student_last_name=last_name,
            student_dob=inquiry.child_dob or date(2015, 1, 1),
            student_gender=student_gender,
            previous_school=inquiry.current_school or "",
            applying_for_grade_id=inquiry.grade_level_interest_id,
            application_date=application_date,
            guardian_name=inquiry.parent_name,
            guardian_phone=inquiry.parent_phone or "",
            guardian_email=inquiry.parent_email or "",
            notes=inquiry.notes or "",
            status="Submitted",
        )

        AdmissionApplicationProfile.objects.get_or_create(
            application=application,
            defaults={
                "inquiry": inquiry,
                "term_id": inquiry.preferred_start_id,
            },
        )

        inquiry.status = "Applied"
        inquiry.save(update_fields=["status"])
        _write_audit(
            request.user,
            "CONVERT",
            "AdmissionInquiry",
            inquiry.id,
            f"Converted inquiry {inquiry.id} to application {application.application_number}.",
        )

        return Response(
            {
                "inquiry_id": inquiry.id,
                "application_id": application.id,
                "application_number": application.application_number,
            },
            status=status.HTTP_201_CREATED,
        )


class AdmissionApplicationProfileViewSet(viewsets.ModelViewSet):
    queryset = AdmissionApplicationProfile.objects.all().order_by("-created_at")
    serializer_class = AdmissionApplicationProfileSerializer
    permission_classes = [IsSchoolAdmin | IsTeacher, HasModuleAccess]
    module_key = "ADMISSIONS"

    def get_queryset(self):
        queryset = super().get_queryset()
        application_id = self.request.query_params.get("application")
        inquiry_id = self.request.query_params.get("inquiry")
        if application_id:
            queryset = queryset.filter(application_id=application_id)
        if inquiry_id:
            queryset = queryset.filter(inquiry_id=inquiry_id)
        return queryset


class AdmissionReviewViewSet(viewsets.ModelViewSet):
    queryset = AdmissionReview.objects.all().order_by("-reviewed_at")
    serializer_class = AdmissionReviewSerializer
    permission_classes = [IsSchoolAdmin | IsTeacher, HasModuleAccess]
    module_key = "ADMISSIONS"

    def get_queryset(self):
        queryset = super().get_queryset()
        application_id = self.request.query_params.get("application")
        recommendation = self.request.query_params.get("recommendation")
        if application_id:
            queryset = queryset.filter(application_id=application_id)
        if recommendation:
            queryset = queryset.filter(recommendation=recommendation)
        return queryset

    def perform_create(self, serializer):
        serializer.save(reviewer=self.request.user)


class ShortlistedApplicationsView(APIView):
    permission_classes = [IsSchoolAdmin | IsTeacher, HasModuleAccess]
    module_key = "ADMISSIONS"

    def get(self, request):
        queryset = AdmissionApplication.objects.filter(normalized_profile__is_shortlisted=True).order_by("-created_at")
        serializer = AdmissionApplicationSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdmissionAssessmentViewSet(viewsets.ModelViewSet):
    queryset = AdmissionAssessment.objects.all().order_by("-scheduled_at", "-created_at")
    serializer_class = AdmissionAssessmentSerializer
    permission_classes = [IsSchoolAdmin | IsTeacher, HasModuleAccess]
    module_key = "ADMISSIONS"

    def get_queryset(self):
        queryset = super().get_queryset()
        application_id = self.request.query_params.get("application")
        status_param = self.request.query_params.get("status")
        if application_id:
            queryset = queryset.filter(application_id=application_id)
        if status_param:
            queryset = queryset.filter(status=status_param)
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class AdmissionInterviewViewSet(viewsets.ModelViewSet):
    queryset = AdmissionInterview.objects.all().order_by("-interview_date", "-created_at")
    serializer_class = AdmissionInterviewSerializer
    permission_classes = [IsSchoolAdmin | IsTeacher, HasModuleAccess]
    module_key = "ADMISSIONS"

    def get_queryset(self):
        queryset = super().get_queryset()
        application_id = self.request.query_params.get("application")
        status_param = self.request.query_params.get("status")
        interview_type = self.request.query_params.get("interview_type")
        if application_id:
            queryset = queryset.filter(application_id=application_id)
        if status_param:
            queryset = queryset.filter(status=status_param)
        if interview_type:
            queryset = queryset.filter(interview_type=interview_type)
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="feedback")
    def add_feedback(self, request, pk=None):
        interview = self.get_object()
        interview.feedback = request.data.get("feedback", interview.feedback)
        if "score" in request.data:
            interview.score = request.data.get("score")
        if request.data.get("mark_completed"):
            interview.status = "Completed"
        interview.save(update_fields=["feedback", "score", "status", "updated_at"])
        return Response(self.get_serializer(interview).data, status=status.HTTP_200_OK)


class AdmissionDecisionViewSet(viewsets.ModelViewSet):
    queryset = AdmissionDecision.objects.all().order_by("-decision_date", "-created_at")
    serializer_class = AdmissionDecisionSerializer
    permission_classes = [IsSchoolAdmin | IsTeacher, HasModuleAccess]
    module_key = "ADMISSIONS"

    def get_queryset(self):
        queryset = super().get_queryset()
        application_id = self.request.query_params.get("application")
        decision = self.request.query_params.get("decision")
        response_status = self.request.query_params.get("response_status")
        if application_id:
            queryset = queryset.filter(application_id=application_id)
        if decision:
            queryset = queryset.filter(decision=decision)
        if response_status:
            queryset = queryset.filter(response_status=response_status)
        return queryset

    def perform_create(self, serializer):
        application = serializer.validated_data.get("application")
        if application and AdmissionDecision.objects.filter(application=application).exists():
            raise ValidationError({"application": "A decision already exists for this application."})
        record = serializer.save(decided_by=self.request.user)
        application = record.application
        status_map = {"Accept": "Admitted", "Reject": "Rejected", "Waitlist": "Submitted"}
        decision_map = {"Accept": "Admitted", "Reject": "Rejected", "Waitlist": "Pending"}
        application.status = status_map.get(record.decision, application.status)
        application.decision = decision_map.get(record.decision, application.decision)
        application.decision_date = record.decision_date
        application.decision_notes = record.decision_notes
        application.save(update_fields=["status", "decision", "decision_date", "decision_notes"])
        _write_audit(
            self.request.user,
            "DECISION_CREATE",
            "AdmissionDecision",
            record.id,
            f"Decision {record.decision} for application {application.application_number}.",
        )

    def perform_update(self, serializer):
        record = serializer.save()
        application = record.application
        status_map = {"Accept": "Admitted", "Reject": "Rejected", "Waitlist": application.status}
        decision_map = {"Accept": "Admitted", "Reject": "Rejected", "Waitlist": "Pending"}
        application.status = status_map.get(record.decision, application.status)
        application.decision = decision_map.get(record.decision, application.decision)
        application.decision_date = record.decision_date
        application.decision_notes = record.decision_notes
        application.save(update_fields=["status", "decision", "decision_date", "decision_notes"])
        _write_audit(
            self.request.user,
            "DECISION_UPDATE",
            "AdmissionDecision",
            record.id,
            f"Decision updated to {record.decision} for application {application.application_number}.",
        )

    @action(detail=True, methods=["post"], url_path="respond")
    def respond(self, request, pk=None):
        record = self.get_object()
        response_status = request.data.get("response_status")
        if response_status not in ("Accepted", "Declined"):
            return Response(
                {"error": "response_status must be Accepted or Declined."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if record.decision != "Accept":
            return Response(
                {"error": "Parent response is only allowed for accepted offers."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if record.response_status in ("Accepted", "Declined"):
            return Response(
                {"error": "Parent response has already been recorded for this offer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if response_status == "Accepted" and record.offer_deadline and date.today() > record.offer_deadline:
            return Response(
                {"error": "Offer acceptance deadline has passed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        record.response_status = response_status
        record.response_notes = request.data.get("response_notes", record.response_notes)
        record.responded_at = timezone.now()
        record.save(update_fields=["response_status", "response_notes", "responded_at", "updated_at"])
        application = record.application
        if response_status == "Declined":
            application.status = "Rejected"
            application.decision = "Rejected"
            application.save(update_fields=["status", "decision"])
        _write_audit(
            request.user,
            "DECISION_RESPONSE",
            "AdmissionDecision",
            record.id,
            f"Parent response set to {response_status} for application {application.application_number}.",
        )

        return Response(self.get_serializer(record).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="offer-letter")
    def offer_letter(self, request, pk=None):
        record = self.get_object()
        if record.decision != "Accept":
            return Response({"error": "Offer letter is only available for accepted decisions."}, status=status.HTTP_400_BAD_REQUEST)

        application = record.application
        school_name = getattr(getattr(request, "tenant", None), "name", "School")
        file_name = f"offer_letter_{application.application_number or application.id}.pdf"

        try:
            from io import BytesIO
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
        except Exception:
            return Response(
                {"error": "PDF export dependency missing. Install reportlab."},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )

        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        y = 800
        lines = [
            f"{school_name}",
            "Admission Offer Letter",
            "",
            f"Application Number: {application.application_number or application.id}",
            f"Student: {application.student_first_name} {application.student_last_name}",
            f"Decision Date: {record.decision_date}",
            f"Offer Deadline: {record.offer_deadline or '-'}",
            "",
            "Congratulations. You have been offered admission subject to enrollment completion.",
        ]
        if record.decision_notes:
            lines.extend(["", f"Notes: {record.decision_notes}"])

        for line in lines:
            pdf.drawString(60, y, str(line))
            y -= 22
        pdf.showPage()
        pdf.save()
        pdf_data = buffer.getvalue()
        buffer.close()

        response = HttpResponse(pdf_data, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{file_name}"'
        return response


class EnrollmentReadyApplicationsView(APIView):
    permission_classes = [IsSchoolAdmin | IsTeacher, HasModuleAccess]
    module_key = "ADMISSIONS"

    def get(self, request):
        queryset = AdmissionApplication.objects.filter(
            decision_record__decision="Accept",
            decision_record__response_status="Accepted",
        ).exclude(status="Enrolled").order_by("-created_at")
        serializer = AdmissionApplicationSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdmissionWaitlistQueueView(APIView):
    permission_classes = [IsSchoolAdmin | IsTeacher, HasModuleAccess]
    module_key = "ADMISSIONS"

    def get(self, request):
        queryset = AdmissionDecision.objects.filter(decision="Waitlist").select_related("application").order_by(
            "decision_date",
            "created_at",
            "id",
        )
        rows = []
        for idx, item in enumerate(queryset, start=1):
            app = item.application
            rows.append(
                {
                    "queue_position": idx,
                    "decision_id": item.id,
                    "application_id": app.id,
                    "application_number": app.application_number,
                    "student_name": f"{app.student_first_name} {app.student_last_name}".strip(),
                    "decision_date": item.decision_date,
                    "response_status": item.response_status,
                }
            )
        return Response({"count": len(rows), "items": rows}, status=status.HTTP_200_OK)


class AdmissionAnalyticsFunnelView(APIView):
    permission_classes = [IsSchoolAdmin | IsTeacher, HasModuleAccess]
    module_key = "ADMISSIONS"

    @staticmethod
    def _rate(numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return round((numerator / denominator) * 100, 2)

    def get(self, request):
        inquiries_total = AdmissionInquiry.objects.count()
        inquiries_applied = AdmissionInquiry.objects.filter(status="Applied").count()
        applications_total = AdmissionApplication.objects.count()
        shortlisted_total = AdmissionApplicationProfile.objects.filter(is_shortlisted=True).count()
        accepted_total = AdmissionDecision.objects.filter(decision="Accept").count()
        enrolled_total = AdmissionApplication.objects.filter(status="Enrolled").count()

        data = {
            "counts": {
                "inquiries_total": inquiries_total,
                "inquiries_applied": inquiries_applied,
                "applications_total": applications_total,
                "shortlisted_total": shortlisted_total,
                "accepted_total": accepted_total,
                "enrolled_total": enrolled_total,
            },
            "rates": {
                "inquiry_to_application_pct": self._rate(applications_total, inquiries_total),
                "application_to_shortlist_pct": self._rate(shortlisted_total, applications_total),
                "shortlist_to_accept_pct": self._rate(accepted_total, shortlisted_total),
                "accept_to_enroll_pct": self._rate(enrolled_total, accepted_total),
            },
        }
        return Response(data, status=status.HTTP_200_OK)


class AdmissionAnalyticsSourcesView(APIView):
    permission_classes = [IsSchoolAdmin | IsTeacher, HasModuleAccess]
    module_key = "ADMISSIONS"

    @staticmethod
    def _rate(numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return round((numerator / denominator) * 100, 2)

    def get(self, request):
        rows = (
            AdmissionInquiry.objects.values("inquiry_source")
            .annotate(total=models.Count("id"), applied=models.Count("id", filter=models.Q(status="Applied")))
            .order_by("inquiry_source")
        )
        sources = [
            {
                "source": row["inquiry_source"],
                "total": row["total"],
                "applied": row["applied"],
                "conversion_pct": self._rate(row["applied"], row["total"]),
            }
            for row in rows
        ]
        return Response({"sources": sources}, status=status.HTTP_200_OK)
