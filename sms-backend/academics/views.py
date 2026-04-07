from datetime import timedelta
from django.utils import timezone
from decimal import Decimal
from io import BytesIO

from django.db import transaction
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Avg, Count, Q
from django.http import HttpResponse
from django.core.files.base import ContentFile
from reportlab.pdfgen import canvas
import csv

from school.permissions import HasModuleAccess, IsAcademicStaff
from school.models import Department, Subject, SubjectMapping, SyllabusTopic
from school.models import Enrollment, TeacherAssignment
from school.models import (
    GradingScheme,
    GradeBand,
    Assessment,
    AssessmentGrade,
    TermResult,
    ReportCard,
    AttendanceRecord,
    Assignment,
    AssignmentSubmission,
    CalendarEvent,
)
from .models import AcademicYear, Term, GradeLevel, SchoolClass
from .serializers import (
    AcademicYearSerializer,
    AcademicYearCloneSerializer,
    TermSerializer,
    GradeLevelSerializer,
    SchoolClassSerializer,
    DepartmentSerializer,
    SubjectSerializer,
    SubjectMappingSerializer,
    SyllabusTopicSerializer,
    AcademicEnrollmentSerializer,
    TeacherAssignmentSerializer,
    GradingSchemeSerializer,
    GradeBandSerializer,
    AssessmentSerializer,
    AssessmentGradeSerializer,
    TermResultSerializer,
    ReportCardSerializer,
    AssignmentSerializer,
    AssignmentSubmissionSerializer,
    CalendarEventSerializer,
)


class AcademicsModuleAccessMixin:
    permission_classes = [IsAcademicStaff, HasModuleAccess]
    module_key = "ACADEMICS"


def _apply_is_active_filter(queryset, raw_value):
    if raw_value is None or str(raw_value).strip() == "":
        return queryset

    normalized = str(raw_value).strip().lower()
    if normalized in ("true", "1"):
        return queryset.filter(is_active=True)
    if normalized in ("false", "0"):
        return queryset.filter(is_active=False)
    return queryset


def _is_teacher_only(user):
    if not hasattr(user, "userprofile"):
        return False
    return user.userprofile.role.name == "TEACHER"


def _teacher_assigned_class_ids(user):
    return list(
        TeacherAssignment.objects.filter(teacher=user, is_active=True)
        .values_list("class_section_id", flat=True)
        .distinct()
    )


def _restrict_queryset_to_teacher_assignments(queryset, user, class_field: str):
    if not _is_teacher_only(user):
        return queryset
    class_ids = _teacher_assigned_class_ids(user)
    if not class_ids:
        return queryset.none()
    return queryset.filter(**{f"{class_field}__in": class_ids})


def _enforce_teacher_can_access_class(user, class_section_id: int):
    if not _is_teacher_only(user):
        return
    class_ids = {int(value) for value in _teacher_assigned_class_ids(user)}
    if int(class_section_id) not in class_ids:
        raise PermissionDenied("Teachers can only access assigned classes.")


class AcademicYearViewSet(AcademicsModuleAccessMixin, viewsets.ModelViewSet):
    queryset = AcademicYear.objects.all().order_by("-start_date", "-id")
    serializer_class = AcademicYearSerializer

    @action(detail=True, methods=["post"], url_path="clone-structure")
    @transaction.atomic
    def clone_structure(self, request, pk=None):
        source_year = self.get_object()
        serializer = AcademicYearCloneSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        target_year = AcademicYear.objects.create(
            name=payload["name"],
            start_date=payload["start_date"],
            end_date=payload["end_date"],
            is_active=True,
            is_current=payload["set_current"],
        )
        if target_year.is_current:
            AcademicYear.objects.exclude(pk=target_year.pk).update(is_current=False)

        delta: timedelta = target_year.start_date - source_year.start_date
        cloned_terms = 0
        cloned_classes = 0

        if payload["copy_terms"]:
            source_terms = Term.objects.filter(academic_year=source_year).order_by("id")
            for term in source_terms:
                billing_date = term.billing_date + delta if term.billing_date else None
                Term.objects.create(
                    academic_year=target_year,
                    name=term.name,
                    start_date=term.start_date + delta,
                    end_date=term.end_date + delta,
                    billing_date=billing_date,
                    is_active=term.is_active,
                    is_current=False,
                )
                cloned_terms += 1

        if payload["copy_classes"]:
            source_classes = SchoolClass.objects.filter(academic_year=source_year).order_by("id")
            for school_class in source_classes:
                SchoolClass.objects.create(
                    name=school_class.name,
                    stream=school_class.stream,
                    academic_year=target_year,
                    grade_level=school_class.grade_level,
                    section_name=school_class.section_name,
                    class_teacher=school_class.class_teacher,
                    room=school_class.room,
                    capacity=school_class.capacity,
                    is_active=school_class.is_active,
                )
                cloned_classes += 1

        return Response(
            {
                "message": "Academic structure cloned successfully.",
                "source_year_id": source_year.id,
                "target_year_id": target_year.id,
                "cloned_terms": cloned_terms,
                "cloned_classes": cloned_classes,
            },
            status=status.HTTP_201_CREATED,
        )


class TermViewSet(AcademicsModuleAccessMixin, viewsets.ModelViewSet):
    queryset = Term.objects.select_related("academic_year").all().order_by("-start_date", "-id")
    serializer_class = TermSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        academic_year = self.request.query_params.get("academic_year")
        queryset = _apply_is_active_filter(queryset, self.request.query_params.get("is_active"))
        if academic_year:
            queryset = queryset.filter(academic_year_id=academic_year)
        return queryset


class GradeLevelViewSet(AcademicsModuleAccessMixin, viewsets.ModelViewSet):
    queryset = GradeLevel.objects.all().order_by("order", "name")
    serializer_class = GradeLevelSerializer


class SchoolClassViewSet(AcademicsModuleAccessMixin, viewsets.ModelViewSet):
    queryset = (
        SchoolClass.objects.select_related("academic_year", "grade_level", "class_teacher")
        .all()
        .order_by("name", "stream", "id")
    )
    serializer_class = SchoolClassSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        academic_year = self.request.query_params.get("academic_year")
        grade_level = self.request.query_params.get("grade_level")
        if academic_year:
            queryset = queryset.filter(academic_year_id=academic_year)
        if grade_level:
            queryset = queryset.filter(grade_level_id=grade_level)
        return queryset


class DepartmentViewSet(AcademicsModuleAccessMixin, viewsets.ModelViewSet):
    queryset = Department.objects.filter(is_active=True).order_by("name", "id")
    serializer_class = DepartmentSerializer


class SubjectViewSet(AcademicsModuleAccessMixin, viewsets.ModelViewSet):
    queryset = Subject.objects.select_related("department").filter(is_active=True).order_by("name", "id")
    serializer_class = SubjectSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        department = self.request.query_params.get("department")
        grade_level = self.request.query_params.get("grade_level")
        if department:
            queryset = queryset.filter(department_id=department)
        if grade_level:
            queryset = queryset.filter(mappings__grade_level_id=grade_level, mappings__is_active=True).distinct()
        return queryset


class SubjectMappingViewSet(AcademicsModuleAccessMixin, viewsets.ModelViewSet):
    queryset = (
        SubjectMapping.objects.select_related("subject", "grade_level", "academic_year")
        .filter(is_active=True)
        .order_by("-created_at", "-id")
    )
    serializer_class = SubjectMappingSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        subject = self.request.query_params.get("subject")
        grade_level = self.request.query_params.get("grade_level")
        academic_year = self.request.query_params.get("academic_year")
        if subject:
            queryset = queryset.filter(subject_id=subject)
        if grade_level:
            queryset = queryset.filter(grade_level_id=grade_level)
        if academic_year:
            queryset = queryset.filter(academic_year_id=academic_year)
        return queryset


class SyllabusTopicViewSet(AcademicsModuleAccessMixin, viewsets.ModelViewSet):
    queryset = (
        SyllabusTopic.objects.select_related("subject", "grade_level", "term", "completed_by")
        .filter(is_active=True)
        .order_by("term_id", "order", "id")
    )
    serializer_class = SyllabusTopicSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        subject = self.request.query_params.get("subject")
        grade_level = self.request.query_params.get("grade_level")
        term = self.request.query_params.get("term")
        if subject:
            queryset = queryset.filter(subject_id=subject)
        if grade_level:
            queryset = queryset.filter(grade_level_id=grade_level)
        if term:
            queryset = queryset.filter(term_id=term)
        return queryset

    @action(detail=True, methods=["patch"], url_path="complete")
    def complete(self, request, pk=None):
        topic = self.get_object()
        serializer = self.get_serializer(
            topic,
            data={
                "is_completed": True,
                "completed_by": request.user.id,
                "completed_date": request.data.get("completed_date"),
            },
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(completed_by=request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SyllabusProgressView(AcademicsModuleAccessMixin, APIView):
    def get(self, request):
        queryset = SyllabusTopic.objects.filter(is_active=True)
        subject = request.query_params.get("subject")
        grade_level = request.query_params.get("grade_level")
        term = request.query_params.get("term")

        if subject:
            queryset = queryset.filter(subject_id=subject)
        if grade_level:
            queryset = queryset.filter(grade_level_id=grade_level)
        if term:
            queryset = queryset.filter(term_id=term)

        grouped = (
            queryset.values("subject_id", "subject__name", "grade_level_id", "grade_level__name", "term_id", "term__name")
            .annotate(
                total_topics=Count("id"),
                completed_topics=Count("id", filter=Q(is_completed=True)),
            )
            .order_by("subject__name", "grade_level__name", "term__name")
        )
        data = []
        for row in grouped:
            total = row["total_topics"] or 0
            completed = row["completed_topics"] or 0
            progress = round((completed / total) * 100, 2) if total else 0.0
            data.append(
                {
                    "subject_id": row["subject_id"],
                    "subject_name": row["subject__name"],
                    "grade_level_id": row["grade_level_id"],
                    "grade_level_name": row["grade_level__name"],
                    "term_id": row["term_id"],
                    "term_name": row["term__name"],
                    "total_topics": total,
                    "completed_topics": completed,
                    "completion_percent": progress,
                }
            )
        return Response(data, status=status.HTTP_200_OK)


class AcademicEnrollmentViewSet(AcademicsModuleAccessMixin, viewsets.ModelViewSet):
    queryset = Enrollment.objects.select_related("student", "school_class", "term").all().order_by("-id")
    serializer_class = AcademicEnrollmentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        class_section = self.request.query_params.get("class_section")
        academic_year = self.request.query_params.get("academic_year")
        term = self.request.query_params.get("term")
        status_value = self.request.query_params.get("status")

        if class_section:
            queryset = queryset.filter(school_class_id=class_section)
        if academic_year:
            queryset = queryset.filter(school_class__academic_year_id=academic_year)
        if term:
            queryset = queryset.filter(term_id=term)
        if status_value:
            queryset = queryset.filter(status=status_value)
        return queryset

    @action(detail=False, methods=["post"], url_path="bulk-promote")
    @transaction.atomic
    def bulk_promote(self, request):
        from_year = request.data.get("from_academic_year")
        to_year = request.data.get("to_academic_year")
        from_term = request.data.get("from_term")
        to_term = request.data.get("to_term")

        if not all([from_year, to_year, from_term, to_term]):
            return Response(
                {"error": "from_academic_year, to_academic_year, from_term and to_term are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        source_enrollments = Enrollment.objects.select_related("school_class__grade_level").filter(
            school_class__academic_year_id=from_year,
            term_id=from_term,
            is_active=True,
            status="Active",
        )
        promoted = 0
        skipped = 0
        for enrollment in source_enrollments:
            source_class = enrollment.school_class
            if not source_class.grade_level:
                skipped += 1
                continue
            next_grade = (
                GradeLevel.objects.filter(order=source_class.grade_level.order + 1, is_active=True)
                .order_by("id")
                .first()
            )
            if not next_grade:
                skipped += 1
                continue
            target_class = (
                SchoolClass.objects.filter(
                    academic_year_id=to_year,
                    grade_level=next_grade,
                    section_name=source_class.section_name,
                    is_active=True,
                )
                .order_by("id")
                .first()
            )
            if not target_class:
                target_class = (
                    SchoolClass.objects.filter(
                        academic_year_id=to_year,
                        grade_level=next_grade,
                        is_active=True,
                    )
                    .order_by("id")
                    .first()
                )
            if not target_class:
                skipped += 1
                continue

            exists = Enrollment.objects.filter(
                student=enrollment.student,
                school_class_id=target_class.id,
                term_id=to_term,
                is_active=True,
            ).exists()
            if exists:
                skipped += 1
                continue

            Enrollment.objects.create(
                student=enrollment.student,
                school_class_id=target_class.id,
                term_id=to_term,
                status="Active",
                is_active=True,
            )
            enrollment.status = "Completed"
            enrollment.left_date = timezone.now().date()
            enrollment.save(update_fields=["status", "left_date"])
            promoted += 1

        return Response(
            {"message": "Bulk promotion completed.", "promoted": promoted, "skipped": skipped},
            status=status.HTTP_200_OK,
        )


class TeacherAssignmentViewSet(AcademicsModuleAccessMixin, viewsets.ModelViewSet):
    queryset = (
        TeacherAssignment.objects.select_related("teacher", "subject", "class_section", "academic_year", "term")
        .filter(is_active=True)
        .order_by("-id")
    )
    serializer_class = TeacherAssignmentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        class_section = self.request.query_params.get("class_section")
        academic_year = self.request.query_params.get("academic_year")
        term = self.request.query_params.get("term")
        subject = self.request.query_params.get("subject")
        teacher = self.request.query_params.get("teacher")
        if class_section:
            queryset = queryset.filter(class_section_id=class_section)
        if academic_year:
            queryset = queryset.filter(academic_year_id=academic_year)
        if term:
            queryset = queryset.filter(term_id=term)
        if subject:
            queryset = queryset.filter(subject_id=subject)
        if teacher:
            queryset = queryset.filter(teacher_id=teacher)
        return queryset

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


def _resolve_grade_band(percentage: Decimal, scheme: GradingScheme | None):
    if scheme is None:
        return None
    return (
        GradeBand.objects.filter(
            scheme=scheme,
            is_active=True,
            min_score__lte=percentage,
            max_score__gte=percentage,
        )
        .order_by("-min_score", "-max_score", "id")
        .first()
    )


class GradingSchemeViewSet(AcademicsModuleAccessMixin, viewsets.ModelViewSet):
    queryset = GradingScheme.objects.filter(is_active=True).order_by("name", "id")
    serializer_class = GradingSchemeSerializer


class GradeBandViewSet(AcademicsModuleAccessMixin, viewsets.ModelViewSet):
    queryset = GradeBand.objects.select_related("scheme").filter(is_active=True).order_by("-min_score", "-id")
    serializer_class = GradeBandSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        scheme = self.request.query_params.get("scheme")
        if scheme:
            queryset = queryset.filter(scheme_id=scheme)
        return queryset


class AssessmentViewSet(AcademicsModuleAccessMixin, viewsets.ModelViewSet):
    queryset = (
        Assessment.objects.select_related("subject", "class_section", "term")
        .filter(is_active=True)
        .order_by("-date", "-id")
    )
    serializer_class = AssessmentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        class_section = self.request.query_params.get("class_section")
        subject = self.request.query_params.get("subject")
        term = self.request.query_params.get("term")
        if class_section:
            queryset = queryset.filter(class_section_id=class_section)
        if subject:
            queryset = queryset.filter(subject_id=subject)
        if term:
            queryset = queryset.filter(term_id=term)
        queryset = _restrict_queryset_to_teacher_assignments(queryset, self.request.user, "class_section_id")
        return queryset

    def perform_create(self, serializer):
        class_section_id = serializer.validated_data["class_section"].id
        _enforce_teacher_can_access_class(self.request.user, class_section_id)
        serializer.save()

    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, pk=None):
        assessment = self.get_object()
        assessment.is_published = True
        assessment.save(update_fields=["is_published"])
        return Response({"message": "Assessment published."}, status=status.HTTP_200_OK)


class AssessmentGradeViewSet(AcademicsModuleAccessMixin, viewsets.ModelViewSet):
    queryset = (
        AssessmentGrade.objects.select_related("assessment", "student", "grade_band")
        .filter(is_active=True)
        .order_by("-entered_at", "-id")
    )
    serializer_class = AssessmentGradeSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        student = self.request.query_params.get("student")
        assessment = self.request.query_params.get("assessment")
        if student:
            queryset = queryset.filter(student_id=student)
        if assessment:
            queryset = queryset.filter(assessment_id=assessment)
        queryset = _restrict_queryset_to_teacher_assignments(queryset, self.request.user, "assessment__class_section_id")
        return queryset

    def perform_create(self, serializer):
        assessment = serializer.validated_data["assessment"]
        _enforce_teacher_can_access_class(self.request.user, assessment.class_section_id)
        raw_score = Decimal(serializer.validated_data["raw_score"])
        percentage = (raw_score / Decimal(assessment.max_score) * Decimal("100.00")) if Decimal(assessment.max_score) > 0 else Decimal("0.00")
        scheme = GradingScheme.objects.filter(is_default=True, is_active=True).first() or GradingScheme.objects.filter(is_active=True).first()
        band = _resolve_grade_band(percentage, scheme)
        serializer.save(
            entered_by=self.request.user,
            percentage=round(percentage, 2),
            grade_band=band,
        )

    def perform_update(self, serializer):
        assessment = serializer.validated_data.get("assessment", serializer.instance.assessment)
        _enforce_teacher_can_access_class(self.request.user, assessment.class_section_id)
        raw_score = Decimal(serializer.validated_data.get("raw_score", serializer.instance.raw_score))
        percentage = (raw_score / Decimal(assessment.max_score) * Decimal("100.00")) if Decimal(assessment.max_score) > 0 else Decimal("0.00")
        scheme = GradingScheme.objects.filter(is_default=True, is_active=True).first() or GradingScheme.objects.filter(is_active=True).first()
        band = _resolve_grade_band(percentage, scheme)
        serializer.save(
            entered_by=self.request.user,
            percentage=round(percentage, 2),
            grade_band=band,
        )

    @action(detail=False, methods=["post"], url_path="bulk")
    def bulk(self, request):
        assessment_id = request.data.get("assessment")
        rows = request.data.get("grades", [])
        if not assessment_id or not isinstance(rows, list) or len(rows) == 0:
            return Response({"error": "assessment and grades[] are required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            assessment = Assessment.objects.get(pk=assessment_id, is_active=True)
        except Assessment.DoesNotExist:
            return Response({"error": "Assessment not found."}, status=status.HTTP_404_NOT_FOUND)

        scheme = GradingScheme.objects.filter(is_default=True, is_active=True).first() or GradingScheme.objects.filter(is_active=True).first()
        created = 0
        updated = 0
        for row in rows:
            student_id = row.get("student")
            raw_score = Decimal(str(row.get("raw_score", "0")))
            if raw_score > Decimal(assessment.max_score):
                return Response({"error": f"raw_score cannot exceed max_score ({assessment.max_score})."}, status=status.HTTP_400_BAD_REQUEST)
            percentage = (raw_score / Decimal(assessment.max_score) * Decimal("100.00")) if Decimal(assessment.max_score) > 0 else Decimal("0.00")
            band = _resolve_grade_band(percentage, scheme)
            obj, was_created = AssessmentGrade.objects.update_or_create(
                assessment=assessment,
                student_id=student_id,
                defaults={
                    "raw_score": raw_score,
                    "percentage": round(percentage, 2),
                    "grade_band": band,
                    "entered_by": request.user,
                    "remarks": row.get("remarks", ""),
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
        return Response({"message": "Bulk grades saved.", "created": created, "updated": updated}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="import-template")
    def import_template(self, request):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="grade_import_template.csv"'
        writer = csv.writer(response)
        writer.writerow(["student", "raw_score", "remarks"])
        writer.writerow([1, 75, ""])
        return response

    @action(detail=False, methods=["post"], url_path="import")
    def import_rows(self, request):
        assessment_id = request.data.get("assessment")
        rows = request.data.get("rows", [])
        request.data["grades"] = rows
        request.data["assessment"] = assessment_id
        return self.bulk(request)


class TermResultViewSet(AcademicsModuleAccessMixin, viewsets.ReadOnlyModelViewSet):
    queryset = (
        TermResult.objects.select_related("student", "class_section", "term", "subject", "grade_band")
        .filter(is_active=True)
        .order_by("-updated_at", "-id")
    )
    serializer_class = TermResultSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        student = self.request.query_params.get("student")
        class_section = self.request.query_params.get("class_section")
        term = self.request.query_params.get("term")
        subject = self.request.query_params.get("subject")
        if student:
            queryset = queryset.filter(student_id=student)
        if class_section:
            queryset = queryset.filter(class_section_id=class_section)
        if term:
            queryset = queryset.filter(term_id=term)
        if subject:
            queryset = queryset.filter(subject_id=subject)
        return queryset

    @action(detail=False, methods=["post"], url_path="compute")
    @transaction.atomic
    def compute(self, request):
        class_section_id = request.data.get("class_section")
        term_id = request.data.get("term")
        if not class_section_id or not term_id:
            return Response({"error": "class_section and term are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            school_class = SchoolClass.objects.get(pk=class_section_id)
            term = Term.objects.get(pk=term_id)
        except (SchoolClass.DoesNotExist, Term.DoesNotExist):
            return Response({"error": "class_section or term not found."}, status=status.HTTP_404_NOT_FOUND)

        scheme_id = request.data.get("grading_scheme")
        scheme = None
        if scheme_id:
            scheme = GradingScheme.objects.filter(pk=scheme_id, is_active=True).first()
        if scheme is None:
            scheme = GradingScheme.objects.filter(is_default=True, is_active=True).first() or GradingScheme.objects.filter(is_active=True).first()

        assessments = Assessment.objects.filter(
            class_section_id=school_class.id,
            term_id=term.id,
            is_active=True,
        )
        if not assessments.exists():
            return Response({"message": "No assessments found for class/term.", "computed": 0}, status=status.HTTP_200_OK)

        # student_id -> subject_id -> totals
        aggregates: dict[int, dict[int, dict[str, Decimal]]] = {}
        for assessment in assessments:
            grades = AssessmentGrade.objects.filter(assessment=assessment, is_active=True)
            for grade in grades:
                student_map = aggregates.setdefault(grade.student_id, {})
                subj_map = student_map.setdefault(assessment.subject_id, {"weighted": Decimal("0.00"), "weight": Decimal("0.00")})
                weight = Decimal(assessment.weight_percent or 0)
                if weight > 0:
                    subj_map["weighted"] += Decimal(grade.percentage) * weight / Decimal("100.00")
                    subj_map["weight"] += weight
                else:
                    subj_map["weighted"] += Decimal(grade.percentage)
                    subj_map["weight"] += Decimal("1.00")

        computed = 0
        # subject-specific ranking bucket
        rank_bucket: dict[int, list[tuple[int, Decimal]]] = {}
        staged_rows: list[TermResult] = []

        for student_id, subjects_map in aggregates.items():
            for subject_id, metrics in subjects_map.items():
                weight = metrics["weight"]
                total = (metrics["weighted"] / weight * Decimal("100.00") / Decimal("100.00")) if weight > 0 else Decimal("0.00")
                total = round(total, 2)
                band = _resolve_grade_band(total, scheme)
                is_pass = total >= Decimal("50.00")
                obj, _ = TermResult.objects.update_or_create(
                    student_id=student_id,
                    class_section_id=school_class.id,
                    term_id=term.id,
                    subject_id=subject_id,
                    defaults={
                        "total_score": total,
                        "grade_band": band,
                        "is_pass": is_pass,
                        "is_active": True,
                    },
                )
                staged_rows.append(obj)
                rank_bucket.setdefault(subject_id, []).append((obj.id, total))
                computed += 1

        # assign ranks per subject (desc total)
        for subject_id, rows in rank_bucket.items():
            rows_sorted = sorted(rows, key=lambda x: x[1], reverse=True)
            rank = 1
            for term_result_id, _ in rows_sorted:
                TermResult.objects.filter(pk=term_result_id).update(class_rank=rank)
                rank += 1

        return Response({"message": "Term results computed.", "computed": computed}, status=status.HTTP_200_OK)


def _build_report_card_pdf(report_card: ReportCard) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)

    y = 800
    pdf.setTitle(f"Report Card - {report_card.student.admission_number}")
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, y, "Student Report Card")
    y -= 24

    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, y, f"Student: {report_card.student.first_name} {report_card.student.last_name}")
    y -= 16
    pdf.drawString(40, y, f"Admission #: {report_card.student.admission_number}")
    y -= 16
    pdf.drawString(40, y, f"Class: {report_card.class_section.display_name}")
    y -= 16
    pdf.drawString(40, y, f"Term: {report_card.term.name} | Academic Year: {report_card.academic_year.name}")
    y -= 16
    pdf.drawString(40, y, f"Status: {report_card.status} | Overall Grade: {report_card.overall_grade or '--'}")
    y -= 20

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(40, y, "Subject")
    pdf.drawString(280, y, "Score")
    pdf.drawString(360, y, "Grade")
    pdf.drawString(440, y, "Rank")
    y -= 14
    pdf.setFont("Helvetica", 10)

    term_results = (
        TermResult.objects.select_related("subject", "grade_band")
        .filter(
            student_id=report_card.student_id,
            class_section_id=report_card.class_section_id,
            term_id=report_card.term_id,
            is_active=True,
        )
        .order_by("subject__name")
    )

    for row in term_results:
        if y < 60:
            pdf.showPage()
            y = 800
            pdf.setFont("Helvetica", 10)
        pdf.drawString(40, y, row.subject.name[:40])
        pdf.drawString(280, y, str(row.total_score))
        pdf.drawString(360, y, row.grade_band.label if row.grade_band else "--")
        pdf.drawString(440, y, str(row.class_rank or "--"))
        y -= 14

    y -= 10
    pdf.drawString(40, y, f"Attendance Days: {report_card.attendance_days}")
    y -= 16
    pdf.drawString(40, y, f"Class Rank: {report_card.class_rank or '--'}")
    y -= 16
    pdf.drawString(40, y, f"Teacher Remarks: {report_card.teacher_remarks or '--'}")
    y -= 16
    pdf.drawString(40, y, f"Principal Remarks: {report_card.principal_remarks or '--'}")

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


class ReportCardViewSet(AcademicsModuleAccessMixin, viewsets.ModelViewSet):
    queryset = (
        ReportCard.objects.select_related("student", "class_section", "term", "academic_year", "approved_by")
        .filter(is_active=True)
        .order_by("-created_at", "-id")
    )
    serializer_class = ReportCardSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        class_section = self.request.query_params.get("class_section")
        term = self.request.query_params.get("term")
        status_value = self.request.query_params.get("status")
        student = self.request.query_params.get("student")
        if class_section:
            queryset = queryset.filter(class_section_id=class_section)
        if term:
            queryset = queryset.filter(term_id=term)
        if status_value:
            queryset = queryset.filter(status=status_value)
        if student:
            queryset = queryset.filter(student_id=student)
        return queryset

    @action(detail=False, methods=["post"], url_path="generate")
    @transaction.atomic
    def generate(self, request):
        class_section_id = request.data.get("class_section")
        term_id = request.data.get("term")
        if not class_section_id or not term_id:
            return Response({"error": "class_section and term are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            school_class = SchoolClass.objects.get(pk=class_section_id)
            term = Term.objects.get(pk=term_id)
        except (SchoolClass.DoesNotExist, Term.DoesNotExist):
            return Response({"error": "class_section or term not found."}, status=status.HTTP_404_NOT_FOUND)

        academic_year_id = term.academic_year_id

        enrolled_ids = list(
            Enrollment.objects.filter(school_class_id=class_section_id, term_id=term_id, is_active=True)
            .values_list("student_id", flat=True)
            .distinct()
        )
        result_ids = list(
            TermResult.objects.filter(class_section_id=class_section_id, term_id=term_id, is_active=True)
            .values_list("student_id", flat=True)
            .distinct()
        )
        student_ids = sorted(set(enrolled_ids + result_ids))
        if not student_ids:
            return Response({"message": "No students found for class/term.", "generated": 0}, status=status.HTTP_200_OK)

        score_rows = (
            TermResult.objects.filter(class_section_id=class_section_id, term_id=term_id, is_active=True)
            .values("student_id")
            .annotate(avg_score=Avg("total_score"))
            .order_by("-avg_score", "student_id")
        )
        rank_map: dict[int, int] = {}
        rank = 1
        for row in score_rows:
            rank_map[row["student_id"]] = rank
            rank += 1

        created = 0
        updated = 0
        for student_id in student_ids:
            avg_score = (
                TermResult.objects.filter(
                    student_id=student_id,
                    class_section_id=class_section_id,
                    term_id=term_id,
                    is_active=True,
                ).aggregate(v=Avg("total_score"))["v"]
                or Decimal("0.00")
            )
            avg_score = round(Decimal(avg_score), 2)
            attendance_days = AttendanceRecord.objects.filter(
                student_id=student_id,
                date__gte=term.start_date,
                date__lte=term.end_date,
                status__in=["Present", "Half-Day"],
            ).count()

            obj, was_created = ReportCard.objects.update_or_create(
                student_id=student_id,
                class_section_id=class_section_id,
                term_id=term_id,
                academic_year_id=academic_year_id,
                defaults={
                    "status": "Draft",
                    "class_rank": rank_map.get(student_id),
                    "overall_grade": str(avg_score),
                    "attendance_days": attendance_days,
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

            pdf_bytes = _build_report_card_pdf(obj)
            file_name = f"report_card_{obj.student_id}_{obj.term_id}_{obj.class_section_id}.pdf"
            obj.pdf_file.save(file_name, ContentFile(pdf_bytes), save=True)

        return Response(
            {
                "message": "Report cards generated.",
                "generated": created + updated,
                "created": created,
                "updated": updated,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        report_card = self.get_object()
        report_card.status = "Approved"
        report_card.approved_by = request.user
        report_card.approved_at = timezone.now()
        report_card.save(update_fields=["status", "approved_by", "approved_at"])
        return Response({"message": "Report card approved."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, pk=None):
        report_card = self.get_object()
        report_card.status = "Published"
        report_card.published_at = timezone.now()
        report_card.save(update_fields=["status", "published_at"])
        return Response({"message": "Report card published."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="distribute")
    def distribute(self, request):
        report_card_ids = request.data.get("report_card_ids", [])
        queryset = ReportCard.objects.filter(is_active=True, status="Published")
        if isinstance(report_card_ids, list) and report_card_ids:
            queryset = queryset.filter(id__in=report_card_ids)
        updated = queryset.update(status="Distributed")
        return Response({"message": "Report cards distributed.", "count": updated}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="pdf")
    def pdf(self, request, pk=None):
        report_card = self.get_object()
        pdf_bytes = _build_report_card_pdf(report_card)
        file_name = f"report_card_{report_card.student_id}_{report_card.term_id}_{report_card.class_section_id}.pdf"
        if not report_card.pdf_file:
            report_card.pdf_file.save(file_name, ContentFile(pdf_bytes), save=True)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{file_name}"'
        return response


class AssignmentViewSet(AcademicsModuleAccessMixin, viewsets.ModelViewSet):
    queryset = (
        Assignment.objects.select_related("subject", "class_section", "teacher")
        .filter(is_active=True)
        .order_by("-created_at", "-id")
    )
    serializer_class = AssignmentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        class_section = self.request.query_params.get("class_section")
        subject = self.request.query_params.get("subject")
        status_value = self.request.query_params.get("status")
        if class_section:
            queryset = queryset.filter(class_section_id=class_section)
        if subject:
            queryset = queryset.filter(subject_id=subject)
        if status_value:
            queryset = queryset.filter(status=status_value)
        queryset = _restrict_queryset_to_teacher_assignments(queryset, self.request.user, "class_section_id")
        return queryset

    def perform_create(self, serializer):
        class_section_id = serializer.validated_data["class_section"].id
        _enforce_teacher_can_access_class(self.request.user, class_section_id)
        serializer.save(teacher=self.request.user)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])

    @action(detail=True, methods=["get"], url_path="submissions")
    def submissions(self, request, pk=None):
        assignment = self.get_object()
        queryset = (
            AssignmentSubmission.objects.select_related("student", "graded_by")
            .filter(assignment=assignment, is_active=True)
            .order_by("-submitted_at", "-id")
        )
        serializer = AssignmentSubmissionSerializer(queryset, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="stats")
    def stats(self, request, pk=None):
        assignment = self.get_object()
        submissions = AssignmentSubmission.objects.filter(assignment=assignment, is_active=True)
        submitted = submissions.count()
        graded = submissions.filter(score__isnull=False).count()
        average_score = submissions.aggregate(v=Avg("score"))["v"]
        if average_score is None:
            average_score = Decimal("0.00")
        class_size = (
            Enrollment.objects.filter(school_class_id=assignment.class_section_id, is_active=True)
            .values("student_id")
            .distinct()
            .count()
        )
        submission_rate = round((submitted / class_size) * 100, 2) if class_size else 0.0
        return Response(
            {
                "assignment_id": assignment.id,
                "submitted_count": submitted,
                "graded_count": graded,
                "class_size": class_size,
                "submission_rate_percent": submission_rate,
                "average_score": round(Decimal(average_score), 2),
            },
            status=status.HTTP_200_OK,
        )


class AssignmentSubmissionViewSet(AcademicsModuleAccessMixin, viewsets.ModelViewSet):
    queryset = (
        AssignmentSubmission.objects.select_related("assignment", "student", "graded_by")
        .filter(is_active=True)
        .order_by("-submitted_at", "-id")
    )
    serializer_class = AssignmentSubmissionSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        assignment = self.request.query_params.get("assignment")
        student = self.request.query_params.get("student")
        if assignment:
            queryset = queryset.filter(assignment_id=assignment)
        if student:
            queryset = queryset.filter(student_id=student)
        queryset = _restrict_queryset_to_teacher_assignments(queryset, self.request.user, "assignment__class_section_id")
        return queryset

    def perform_create(self, serializer):
        assignment = serializer.validated_data["assignment"]
        _enforce_teacher_can_access_class(self.request.user, assignment.class_section_id)
        is_late = timezone.now() > assignment.due_date
        serializer.save(is_late=is_late)

    @action(detail=True, methods=["patch"], url_path="grade")
    def grade(self, request, pk=None):
        submission = self.get_object()
        payload = {
            "score": request.data.get("score"),
            "feedback": request.data.get("feedback", ""),
            "graded_by": request.user.id,
            "graded_at": timezone.now(),
        }
        serializer = self.get_serializer(submission, data=payload, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(graded_by=request.user, graded_at=timezone.now())
        return Response(serializer.data, status=status.HTTP_200_OK)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class CalendarEventViewSet(AcademicsModuleAccessMixin, viewsets.ModelViewSet):
    queryset = (
        CalendarEvent.objects.select_related("academic_year", "term", "class_section", "created_by")
        .filter(is_active=True)
        .order_by("start_date", "id")
    )
    serializer_class = CalendarEventSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        academic_year = self.request.query_params.get("academic_year")
        term = self.request.query_params.get("term")
        event_type = self.request.query_params.get("event_type")
        if academic_year:
            queryset = queryset.filter(academic_year_id=academic_year)
        if term:
            queryset = queryset.filter(term_id=term)
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        events = self.get_queryset()
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//SMS//Academics Calendar//EN",
        ]
        for event in events:
            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:academics-calendar-{event.id}@sms",
                    f"SUMMARY:{event.title}",
                    f"DTSTART;VALUE=DATE:{event.start_date.strftime('%Y%m%d')}",
                    f"DTEND;VALUE=DATE:{event.end_date.strftime('%Y%m%d')}",
                    f"DESCRIPTION:{event.description or ''}",
                    "END:VEVENT",
                ]
            )
        lines.append("END:VCALENDAR")
        response = HttpResponse("\r\n".join(lines), content_type="text/calendar")
        response["Content-Disposition"] = 'attachment; filename="academic_calendar.ics"'
        return response


class AnalyticsSummaryView(AcademicsModuleAccessMixin, APIView):
    def get(self, request):
        term_id = request.query_params.get("term")
        queryset = TermResult.objects.filter(is_active=True)
        if term_id:
            queryset = queryset.filter(term_id=term_id)
        avg_score = queryset.aggregate(v=Avg("total_score"))["v"] or Decimal("0.00")
        total_rows = queryset.count()
        pass_rows = queryset.filter(is_pass=True).count()
        pass_rate = round((pass_rows / total_rows) * 100, 2) if total_rows else 0.0
        grade_distribution = (
            queryset.values("grade_band__label")
            .annotate(count=Count("id"))
            .order_by("grade_band__label")
        )
        return Response(
            {
                "average_score": round(Decimal(avg_score), 2),
                "pass_rate_percent": pass_rate,
                "total_results": total_rows,
                "at_risk_students": queryset.values("student_id").annotate(fails=Count("id", filter=Q(is_pass=False))).filter(fails__gte=2).count(),
                "grade_distribution": [
                    {"grade_band": row["grade_band__label"] or "Unbanded", "count": row["count"]}
                    for row in grade_distribution
                ],
            },
            status=status.HTTP_200_OK,
        )


class AnalyticsClassPerformanceView(AcademicsModuleAccessMixin, APIView):
    def get(self, request):
        term_id = request.query_params.get("term")
        queryset = TermResult.objects.filter(is_active=True)
        if term_id:
            queryset = queryset.filter(term_id=term_id)
        rows = (
            queryset.values("class_section_id", "class_section__name", "class_section__section_name")
            .annotate(
                average_score=Avg("total_score"),
                pass_count=Count("id", filter=Q(is_pass=True)),
                total_count=Count("id"),
            )
            .order_by("-average_score")
        )
        data = []
        for row in rows:
            total = row["total_count"] or 0
            pass_rate = round((row["pass_count"] / total) * 100, 2) if total else 0.0
            class_name = f'{row["class_section__name"]} {row["class_section__section_name"]}'.strip()
            data.append(
                {
                    "class_section_id": row["class_section_id"],
                    "class_name": class_name,
                    "average_score": round(Decimal(row["average_score"] or 0), 2),
                    "pass_rate_percent": pass_rate,
                    "total_results": total,
                }
            )
        return Response(data, status=status.HTTP_200_OK)


class AnalyticsSubjectPerformanceView(AcademicsModuleAccessMixin, APIView):
    def get(self, request):
        term_id = request.query_params.get("term")
        queryset = TermResult.objects.filter(is_active=True)
        if term_id:
            queryset = queryset.filter(term_id=term_id)
        rows = (
            queryset.values("subject_id", "subject__name", "subject__code")
            .annotate(
                average_score=Avg("total_score"),
                pass_count=Count("id", filter=Q(is_pass=True)),
                total_count=Count("id"),
            )
            .order_by("-average_score")
        )
        data = []
        for row in rows:
            total = row["total_count"] or 0
            pass_rate = round((row["pass_count"] / total) * 100, 2) if total else 0.0
            data.append(
                {
                    "subject_id": row["subject_id"],
                    "subject_name": row["subject__name"],
                    "subject_code": row["subject__code"],
                    "average_score": round(Decimal(row["average_score"] or 0), 2),
                    "pass_rate_percent": pass_rate,
                    "total_results": total,
                }
            )
        return Response(data, status=status.HTTP_200_OK)


class AnalyticsAtRiskView(AcademicsModuleAccessMixin, APIView):
    def get(self, request):
        term_id = request.query_params.get("term")
        queryset = TermResult.objects.filter(is_active=True, is_pass=False)
        if term_id:
            queryset = queryset.filter(term_id=term_id)
        rows = (
            queryset.values("student_id", "student__admission_number", "student__first_name", "student__last_name")
            .annotate(failing_subjects=Count("subject_id", distinct=True), avg_score=Avg("total_score"))
            .filter(failing_subjects__gte=2)
            .order_by("avg_score")
        )
        data = [
            {
                "student_id": row["student_id"],
                "admission_number": row["student__admission_number"],
                "student_name": f'{row["student__first_name"]} {row["student__last_name"]}'.strip(),
                "failing_subjects": row["failing_subjects"],
                "average_score": round(Decimal(row["avg_score"] or 0), 2),
            }
            for row in rows
        ]
        return Response(data, status=status.HTTP_200_OK)


class AnalyticsStudentProfileView(AcademicsModuleAccessMixin, APIView):
    def get(self, request, student_id: int):
        term_id = request.query_params.get("term")
        result_qs = TermResult.objects.filter(student_id=student_id, is_active=True).select_related("subject", "term", "class_section", "grade_band")
        if term_id:
            result_qs = result_qs.filter(term_id=term_id)
        if not result_qs.exists():
            return Response({"error": "No academic results found for this student."}, status=status.HTTP_404_NOT_FOUND)
        attendance_qs = AttendanceRecord.objects.filter(student_id=student_id)
        if term_id:
            term = Term.objects.filter(pk=term_id).first()
            if term:
                attendance_qs = attendance_qs.filter(date__gte=term.start_date, date__lte=term.end_date)
        attendance_total = attendance_qs.count()
        attendance_present = attendance_qs.filter(status__in=["Present", "Half-Day"]).count()
        attendance_rate = round((attendance_present / attendance_total) * 100, 2) if attendance_total else 0.0
        return Response(
            {
                "student_id": student_id,
                "average_score": round(Decimal(result_qs.aggregate(v=Avg("total_score"))["v"] or 0), 2),
                "attendance_rate_percent": attendance_rate,
                "results": [
                    {
                        "term": row.term.name,
                        "class_section": row.class_section.display_name,
                        "subject": row.subject.name,
                        "total_score": str(row.total_score),
                        "grade_band": row.grade_band.label if row.grade_band else "",
                        "class_rank": row.class_rank,
                        "is_pass": row.is_pass,
                    }
                    for row in result_qs.order_by("term_id", "subject__name")
                ],
            },
            status=status.HTTP_200_OK,
        )


class AnalyticsTeacherPerformanceView(AcademicsModuleAccessMixin, APIView):
    def get(self, request, teacher_id: int):
        term_id = request.query_params.get("term")
        assignments = TeacherAssignment.objects.filter(teacher_id=teacher_id, is_active=True)
        if term_id:
            assignments = assignments.filter(Q(term_id=term_id) | Q(term__isnull=True))
        if not assignments.exists():
            return Response({"error": "No teacher assignments found."}, status=status.HTTP_404_NOT_FOUND)
        performance = []
        for assignment in assignments:
            result_qs = TermResult.objects.filter(
                class_section_id=assignment.class_section_id,
                subject_id=assignment.subject_id,
                is_active=True,
            )
            if term_id:
                result_qs = result_qs.filter(term_id=term_id)
            avg_score = result_qs.aggregate(v=Avg("total_score"))["v"] or Decimal("0.00")
            total = result_qs.count()
            pass_count = result_qs.filter(is_pass=True).count()
            pass_rate = round((pass_count / total) * 100, 2) if total else 0.0
            performance.append(
                {
                    "class_section_id": assignment.class_section_id,
                    "class_name": assignment.class_section.display_name,
                    "subject_id": assignment.subject_id,
                    "subject_name": assignment.subject.name,
                    "average_score": round(Decimal(avg_score), 2),
                    "pass_rate_percent": pass_rate,
                    "total_results": total,
                }
            )
        return Response(
            {
                "teacher_id": teacher_id,
                "assignment_count": assignments.count(),
                "performance": performance,
            },
            status=status.HTTP_200_OK,
        )


class AnalyticsTrendView(AcademicsModuleAccessMixin, APIView):
    def get(self, request):
        queryset = (
            TermResult.objects.filter(is_active=True)
            .values("term_id", "term__name")
            .annotate(average_score=Avg("total_score"), pass_count=Count("id", filter=Q(is_pass=True)), total_count=Count("id"))
            .order_by("term_id")
        )
        data = []
        for row in queryset:
            total = row["total_count"] or 0
            pass_rate = round((row["pass_count"] / total) * 100, 2) if total else 0.0
            data.append(
                {
                    "term_id": row["term_id"],
                    "term_name": row["term__name"],
                    "average_score": round(Decimal(row["average_score"] or 0), 2),
                    "pass_rate_percent": pass_rate,
                    "total_results": total,
                }
            )
        return Response(data, status=status.HTTP_200_OK)


class AcademicYearsRefView(AcademicsModuleAccessMixin, APIView):
    def get(self, request):
        data = (
            AcademicYear.objects.values(
                "id", "name", "start_date", "end_date", "is_active", "is_current"
            )
            .order_by("start_date")
        )
        return Response(list(data), status=status.HTTP_200_OK)


class TermsRefView(AcademicsModuleAccessMixin, APIView):
    def get(self, request):
        queryset = _apply_is_active_filter(Term.objects.all(), request.query_params.get("is_active"))
        data = (
            queryset.values(
                "id",
                "name",
                "start_date",
                "end_date",
                "billing_date",
                "academic_year_id",
                "is_active",
                "is_current",
            )
            .order_by("start_date")
        )
        return Response(list(data), status=status.HTTP_200_OK)


class ClassesRefView(AcademicsModuleAccessMixin, APIView):
    def get(self, request):
        classes = (
            SchoolClass.objects.select_related("grade_level")
            .all()
            .order_by("name", "stream", "id")
        )
        data = [
            {
                "id": school_class.id,
                "name": school_class.name,
                "stream": school_class.stream,
                "academic_year_id": school_class.academic_year_id,
                "grade_level_id": school_class.grade_level_id,
                "section_name": school_class.section_name,
                "display_name": school_class.display_name,
                "is_active": school_class.is_active,
            }
            for school_class in classes
        ]
        return Response(data, status=status.HTTP_200_OK)
