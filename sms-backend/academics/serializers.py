from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from decimal import Decimal

from .models import AcademicYear, Term, GradeLevel, SchoolClass
from school.models import (
    Department,
    Subject,
    SubjectMapping,
    SyllabusTopic,
    Enrollment,
    TeacherAssignment,
    Student,
    GradingScheme,
    GradeBand,
    Assessment,
    AssessmentGrade,
    TermResult,
    ReportCard,
    Assignment,
    AssignmentSubmission,
    CalendarEvent,
)


class AcademicYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicYear
        fields = [
            "id",
            "name",
            "start_date",
            "end_date",
            "is_active",
            "is_current",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({"end_date": "end_date must be on or after start_date."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        instance = super().create(validated_data)
        if instance.is_current:
            AcademicYear.objects.exclude(pk=instance.pk).update(is_current=False)
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        if instance.is_current:
            AcademicYear.objects.exclude(pk=instance.pk).update(is_current=False)
        return instance


class AcademicYearCloneSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=50)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    copy_terms = serializers.BooleanField(default=True)
    copy_classes = serializers.BooleanField(default=True)
    set_current = serializers.BooleanField(default=False)

    def validate(self, attrs):
        if attrs["end_date"] < attrs["start_date"]:
            raise serializers.ValidationError({"end_date": "end_date must be on or after start_date."})
        return attrs


class TermSerializer(serializers.ModelSerializer):
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True)

    class Meta:
        model = Term
        fields = [
            "id",
            "academic_year",
            "academic_year_name",
            "name",
            "start_date",
            "end_date",
            "billing_date",
            "is_active",
            "is_current",
        ]
        read_only_fields = ["id", "academic_year_name"]

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({"end_date": "end_date must be on or after start_date."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        instance = super().create(validated_data)
        if instance.is_current:
            Term.objects.exclude(pk=instance.pk).update(is_current=False)
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        if instance.is_current:
            Term.objects.exclude(pk=instance.pk).update(is_current=False)
        return instance


class GradeLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = GradeLevel
        fields = ["id", "name", "order", "description", "is_active"]
        read_only_fields = ["id"]


class SchoolClassSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True)
    grade_level_name = serializers.CharField(source="grade_level.name", read_only=True)
    class_teacher_name = serializers.CharField(source="class_teacher.username", read_only=True)

    class Meta:
        model = SchoolClass
        fields = [
            "id",
            "academic_year",
            "academic_year_name",
            "grade_level",
            "grade_level_name",
            "name",
            "stream",
            "section_name",
            "display_name",
            "class_teacher",
            "class_teacher_name",
            "room",
            "capacity",
            "is_active",
        ]
        read_only_fields = [
            "id",
            "academic_year_name",
            "grade_level_name",
            "display_name",
            "class_teacher_name",
        ]
        extra_kwargs = {
            # Legacy `name`/`stream` are auto-derived from grade_level/section_name on create.
            "name": {"required": False, "allow_blank": True},
            "stream": {"required": False, "allow_blank": True},
        }

    def get_display_name(self, obj):
        return obj.display_name

    def validate_capacity(self, value):
        if value <= 0:
            raise serializers.ValidationError("capacity must be greater than 0.")
        return value

    def validate(self, attrs):
        if self.instance is None and not attrs.get("grade_level") and not attrs.get("name"):
            raise serializers.ValidationError(
                {"grade_level": "Provide grade_level (preferred) or legacy class name."}
            )
        return attrs

    def _sync_legacy_fields(self, attrs):
        grade_level = attrs.get("grade_level")
        section_name = attrs.get("section_name", "")

        if not attrs.get("name") and grade_level:
            attrs["name"] = grade_level.name
        if "section_name" in attrs and "stream" not in attrs:
            attrs["stream"] = section_name
        return attrs

    def create(self, validated_data):
        validated_data = self._sync_legacy_fields(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data = self._sync_legacy_fields(validated_data)
        return super().update(instance, validated_data)


class DepartmentSerializer(serializers.ModelSerializer):
    head_name = serializers.CharField(source="head.username", read_only=True)

    class Meta:
        model = Department
        fields = ["id", "name", "head", "head_name", "description", "is_active", "created_at"]
        read_only_fields = ["id", "head_name", "created_at"]


class SubjectSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = Subject
        fields = [
            "id",
            "name",
            "code",
            "department",
            "department_name",
            "subject_type",
            "periods_week",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "department_name", "created_at"]


class SubjectMappingSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    subject_code = serializers.CharField(source="subject.code", read_only=True)
    grade_level_name = serializers.CharField(source="grade_level.name", read_only=True)
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True)

    class Meta:
        model = SubjectMapping
        fields = [
            "id",
            "subject",
            "subject_name",
            "subject_code",
            "grade_level",
            "grade_level_name",
            "academic_year",
            "academic_year_name",
            "is_compulsory",
            "is_active",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "subject_name",
            "subject_code",
            "grade_level_name",
            "academic_year_name",
            "created_at",
        ]


class SyllabusTopicSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    grade_level_name = serializers.CharField(source="grade_level.name", read_only=True)
    term_name = serializers.CharField(source="term.name", read_only=True)
    completed_by_name = serializers.CharField(source="completed_by.username", read_only=True)

    class Meta:
        model = SyllabusTopic
        fields = [
            "id",
            "subject",
            "subject_name",
            "grade_level",
            "grade_level_name",
            "term",
            "term_name",
            "topic_name",
            "order",
            "is_completed",
            "completed_date",
            "completed_by",
            "completed_by_name",
            "is_active",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "subject_name",
            "grade_level_name",
            "term_name",
            "completed_by_name",
            "created_at",
        ]

    def update(self, instance, validated_data):
        # Ensure completed_date is aligned when completion flag toggles.
        if "is_completed" in validated_data:
            is_completed = validated_data["is_completed"]
            if is_completed and not validated_data.get("completed_date"):
                validated_data["completed_date"] = timezone.now().date()
            if not is_completed:
                validated_data["completed_date"] = None
                validated_data["completed_by"] = None
        return super().update(instance, validated_data)


class AcademicEnrollmentSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    class_section_name = serializers.CharField(source="school_class.display_name", read_only=True)
    academic_year = serializers.IntegerField(source="school_class.academic_year_id", read_only=True)
    term_name = serializers.CharField(source="term.name", read_only=True)

    class Meta:
        model = Enrollment
        fields = [
            "id",
            "student",
            "student_name",
            "school_class",
            "class_section_name",
            "academic_year",
            "term",
            "term_name",
            "enrollment_date",
            "left_date",
            "status",
            "is_active",
        ]
        read_only_fields = ["id", "student_name", "class_section_name", "academic_year", "term_name", "enrollment_date"]

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}".strip()

    def validate_student(self, value: Student):
        if not value.is_active:
            raise serializers.ValidationError("Student is not active.")
        return value


class TeacherAssignmentSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source="teacher.username", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    class_section_name = serializers.CharField(source="class_section.display_name", read_only=True)
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True)
    term_name = serializers.CharField(source="term.name", read_only=True)

    class Meta:
        model = TeacherAssignment
        fields = [
            "id",
            "teacher",
            "teacher_name",
            "subject",
            "subject_name",
            "class_section",
            "class_section_name",
            "academic_year",
            "academic_year_name",
            "term",
            "term_name",
            "is_primary",
            "is_active",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "teacher_name",
            "subject_name",
            "class_section_name",
            "academic_year_name",
            "term_name",
            "created_at",
        ]


class GradingSchemeSerializer(serializers.ModelSerializer):
    class Meta:
        model = GradingScheme
        fields = ["id", "name", "is_default", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class GradeBandSerializer(serializers.ModelSerializer):
    scheme_name = serializers.CharField(source="scheme.name", read_only=True)

    class Meta:
        model = GradeBand
        fields = [
            "id",
            "scheme",
            "scheme_name",
            "label",
            "min_score",
            "max_score",
            "grade_point",
            "remark",
            "is_active",
        ]
        read_only_fields = ["id", "scheme_name"]

    def validate(self, attrs):
        min_score = attrs.get("min_score", getattr(self.instance, "min_score", None))
        max_score = attrs.get("max_score", getattr(self.instance, "max_score", None))
        if min_score is not None and max_score is not None and Decimal(min_score) > Decimal(max_score):
            raise serializers.ValidationError({"max_score": "max_score must be greater than or equal to min_score."})
        return attrs


class AssessmentSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    class_section_name = serializers.CharField(source="class_section.display_name", read_only=True)
    term_name = serializers.CharField(source="term.name", read_only=True)

    class Meta:
        model = Assessment
        fields = [
            "id",
            "name",
            "category",
            "subject",
            "subject_name",
            "class_section",
            "class_section_name",
            "term",
            "term_name",
            "max_score",
            "weight_percent",
            "date",
            "is_published",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "subject_name", "class_section_name", "term_name", "created_at"]


class AssessmentGradeSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    assessment_name = serializers.CharField(source="assessment.name", read_only=True)
    grade_band_label = serializers.CharField(source="grade_band.label", read_only=True)

    class Meta:
        model = AssessmentGrade
        fields = [
            "id",
            "assessment",
            "assessment_name",
            "student",
            "student_name",
            "raw_score",
            "percentage",
            "grade_band",
            "grade_band_label",
            "entered_by",
            "entered_at",
            "remarks",
            "is_active",
        ]
        read_only_fields = [
            "id",
            "assessment_name",
            "student_name",
            "percentage",
            "grade_band",
            "grade_band_label",
            "entered_at",
        ]

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}".strip()

    def validate_raw_score(self, value):
        assessment = self.initial_data.get("assessment") or getattr(self.instance, "assessment_id", None)
        if assessment:
            try:
                assessment_obj = Assessment.objects.get(pk=assessment)
                if Decimal(value) > Decimal(assessment_obj.max_score):
                    raise serializers.ValidationError("raw_score cannot exceed assessment max_score.")
            except Assessment.DoesNotExist:
                pass
        return value


class TermResultSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    class_section_name = serializers.CharField(source="class_section.display_name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    term_name = serializers.CharField(source="term.name", read_only=True)
    grade_band_label = serializers.CharField(source="grade_band.label", read_only=True)

    class Meta:
        model = TermResult
        fields = [
            "id",
            "student",
            "student_name",
            "class_section",
            "class_section_name",
            "term",
            "term_name",
            "subject",
            "subject_name",
            "total_score",
            "grade_band",
            "grade_band_label",
            "class_rank",
            "is_pass",
            "is_active",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "student_name",
            "class_section_name",
            "term_name",
            "subject_name",
            "grade_band_label",
            "updated_at",
        ]

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}".strip()


class ReportCardSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    class_section_name = serializers.CharField(source="class_section.display_name", read_only=True)
    term_name = serializers.CharField(source="term.name", read_only=True)
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.username", read_only=True)
    pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = ReportCard
        fields = [
            "id",
            "student",
            "student_name",
            "class_section",
            "class_section_name",
            "term",
            "term_name",
            "academic_year",
            "academic_year_name",
            "status",
            "teacher_remarks",
            "principal_remarks",
            "class_rank",
            "overall_grade",
            "attendance_days",
            "pdf_file",
            "pdf_url",
            "approved_by",
            "approved_by_name",
            "approved_at",
            "published_at",
            "created_at",
            "is_active",
        ]
        read_only_fields = [
            "id",
            "student_name",
            "class_section_name",
            "term_name",
            "academic_year_name",
            "pdf_file",
            "pdf_url",
            "approved_by_name",
            "approved_at",
            "published_at",
            "created_at",
        ]

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}".strip()

    def get_pdf_url(self, obj):
        if not obj.pdf_file:
            return ""
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.pdf_file.url)
        return obj.pdf_file.url


class AssignmentSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    class_section_name = serializers.CharField(source="class_section.display_name", read_only=True)
    teacher_name = serializers.CharField(source="teacher.username", read_only=True)

    class Meta:
        model = Assignment
        fields = [
            "id",
            "title",
            "subject",
            "subject_name",
            "class_section",
            "class_section_name",
            "teacher",
            "teacher_name",
            "description",
            "due_date",
            "max_score",
            "publish_date",
            "status",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "subject_name", "class_section_name", "teacher_name", "created_at"]


class AssignmentSubmissionSerializer(serializers.ModelSerializer):
    assignment_title = serializers.CharField(source="assignment.title", read_only=True)
    student_name = serializers.SerializerMethodField()
    graded_by_name = serializers.CharField(source="graded_by.username", read_only=True)

    class Meta:
        model = AssignmentSubmission
        fields = [
            "id",
            "assignment",
            "assignment_title",
            "student",
            "student_name",
            "submitted_at",
            "is_late",
            "file",
            "notes",
            "score",
            "feedback",
            "graded_at",
            "graded_by",
            "graded_by_name",
            "is_active",
        ]
        read_only_fields = [
            "id",
            "assignment_title",
            "student_name",
            "submitted_at",
            "is_late",
            "graded_at",
            "graded_by_name",
        ]

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}".strip()


class CalendarEventSerializer(serializers.ModelSerializer):
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True)
    term_name = serializers.CharField(source="term.name", read_only=True)
    class_section_name = serializers.CharField(source="class_section.display_name", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = CalendarEvent
        fields = [
            "id",
            "title",
            "event_type",
            "start_date",
            "end_date",
            "start_time",
            "end_time",
            "description",
            "academic_year",
            "academic_year_name",
            "term",
            "term_name",
            "scope",
            "class_section",
            "class_section_name",
            "is_public",
            "created_by",
            "created_by_name",
            "created_at",
            "is_active",
        ]
        read_only_fields = [
            "id",
            "academic_year_name",
            "term_name",
            "class_section_name",
            "created_by_name",
            "created_at",
        ]

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({"end_date": "end_date must be on or after start_date."})
        scope = attrs.get("scope", getattr(self.instance, "scope", None))
        class_section = attrs.get("class_section", getattr(self.instance, "class_section", None))
        if scope == "Class-specific" and not class_section:
            raise serializers.ValidationError({"class_section": "class_section is required for Class-specific scope."})
        return attrs
