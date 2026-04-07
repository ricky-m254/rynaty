from datetime import date, timedelta

from django.utils import timezone
from rest_framework import serializers

from school.models import AdmissionApplication
from .models import (
    AdmissionApplicationProfile,
    AdmissionAssessment,
    AdmissionDecision,
    AdmissionInquiry,
    AdmissionInterview,
    AdmissionReview,
)

MIN_PERCENT_SCORE = 0
MAX_PERCENT_SCORE = 100


def _validate_percent_score(value, field_label: str):
    if value is None:
        return value
    numeric = float(value)
    if numeric < MIN_PERCENT_SCORE or numeric > MAX_PERCENT_SCORE:
        raise serializers.ValidationError(
            f"{field_label} must be between {MIN_PERCENT_SCORE} and {MAX_PERCENT_SCORE}."
        )
    return value


class AdmissionInquirySerializer(serializers.ModelSerializer):
    grade_level_interest_name = serializers.CharField(source="grade_level_interest.display_name", read_only=True)
    preferred_start_name = serializers.CharField(source="preferred_start.name", read_only=True)
    assigned_counselor_name = serializers.CharField(source="assigned_counselor.username", read_only=True)

    class Meta:
        model = AdmissionInquiry
        fields = [
            "id",
            "parent_name",
            "parent_phone",
            "parent_email",
            "child_name",
            "child_dob",
            "child_age",
            "current_school",
            "grade_level_interest",
            "grade_level_interest_name",
            "inquiry_source",
            "inquiry_date",
            "preferred_start",
            "preferred_start_name",
            "status",
            "assigned_counselor",
            "assigned_counselor_name",
            "notes",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def validate(self, attrs):
        inquiry_date = attrs.get("inquiry_date") or getattr(self.instance, "inquiry_date", None)
        child_dob = attrs.get("child_dob") or getattr(self.instance, "child_dob", None)
        child_age = attrs.get("child_age", getattr(self.instance, "child_age", None))

        if inquiry_date and inquiry_date > date.today():
            raise serializers.ValidationError({"inquiry_date": "Inquiry date cannot be in the future."})
        if child_dob and inquiry_date and child_dob > inquiry_date:
            raise serializers.ValidationError({"child_dob": "Child date of birth cannot be after inquiry date."})
        if child_age is not None and (child_age < 1 or child_age > 25):
            raise serializers.ValidationError({"child_age": "Child age must be between 1 and 25."})
        return attrs


class AdmissionApplicationProfileSerializer(serializers.ModelSerializer):
    application_number = serializers.CharField(source="application.application_number", read_only=True)
    inquiry_child_name = serializers.CharField(source="inquiry.child_name", read_only=True)
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True)
    term_name = serializers.CharField(source="term.name", read_only=True)

    class Meta:
        model = AdmissionApplicationProfile
        fields = [
            "id",
            "application",
            "application_number",
            "inquiry",
            "inquiry_child_name",
            "academic_year",
            "academic_year_name",
            "term",
            "term_name",
            "is_shortlisted",
            "shortlisted_at",
            "special_needs",
            "medical_notes",
            "languages",
            "emergency_contact_name",
            "emergency_contact_phone",
            "parent_id_number",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_application(self, value: AdmissionApplication):
        if self.instance and self.instance.application_id == value.id:
            return value
        if AdmissionApplicationProfile.objects.filter(application=value).exists():
            raise serializers.ValidationError("A normalized profile already exists for this application.")
        return value


class AdmissionReviewSerializer(serializers.ModelSerializer):
    application_number = serializers.CharField(source="application.application_number", read_only=True)
    reviewer_name = serializers.CharField(source="reviewer.username", read_only=True)

    class Meta:
        model = AdmissionReview
        fields = [
            "id",
            "application",
            "application_number",
            "reviewer",
            "reviewer_name",
            "academic_score",
            "test_score",
            "interview_score",
            "overall_score",
            "recommendation",
            "comments",
            "reviewed_at",
        ]
        read_only_fields = ["reviewed_at", "reviewer"]

    def validate(self, attrs):
        values = {
            "academic_score": attrs.get("academic_score"),
            "test_score": attrs.get("test_score"),
            "interview_score": attrs.get("interview_score"),
            "overall_score": attrs.get("overall_score"),
        }
        for key, value in values.items():
            _validate_percent_score(value, key.replace("_", " ").title())
        return attrs


class AdmissionAssessmentSerializer(serializers.ModelSerializer):
    application_number = serializers.CharField(source="application.application_number", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = AdmissionAssessment
        fields = [
            "id",
            "application",
            "application_number",
            "scheduled_at",
            "venue",
            "score",
            "is_pass",
            "status",
            "notes",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_by", "created_at", "updated_at"]

    def validate(self, attrs):
        scheduled_at = attrs.get("scheduled_at") or getattr(self.instance, "scheduled_at", None)
        score = attrs.get("score", getattr(self.instance, "score", None))
        status_value = attrs.get("status", getattr(self.instance, "status", None))

        if scheduled_at and scheduled_at.date() < date(2000, 1, 1):
            raise serializers.ValidationError({"scheduled_at": "Scheduled date is out of allowed range."})
        _validate_percent_score(score, "Score")
        if status_value == "Completed" and score is None:
            raise serializers.ValidationError({"score": "Score is required when assessment status is Completed."})
        return attrs


class AdmissionInterviewSerializer(serializers.ModelSerializer):
    application_number = serializers.CharField(source="application.application_number", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = AdmissionInterview
        fields = [
            "id",
            "application",
            "application_number",
            "interview_date",
            "interview_type",
            "location",
            "panel",
            "status",
            "feedback",
            "score",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_by", "created_at", "updated_at"]

    def validate_panel(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Panel must be a list.")
        for user_id in value:
            if not isinstance(user_id, int):
                raise serializers.ValidationError("Panel members must be integer user IDs.")
        return value

    def validate(self, attrs):
        interview_date = attrs.get("interview_date") or getattr(self.instance, "interview_date", None)
        score = attrs.get("score", getattr(self.instance, "score", None))
        status_value = attrs.get("status", getattr(self.instance, "status", None))
        now = timezone.now()

        if interview_date and interview_date.year < 2000:
            raise serializers.ValidationError({"interview_date": "Interview date is out of allowed range."})
        if interview_date and interview_date > now + timedelta(days=365 * 3):
            raise serializers.ValidationError({"interview_date": "Interview date is too far in the future."})
        _validate_percent_score(score, "Score")
        if status_value == "Completed" and score is None and not attrs.get("feedback", getattr(self.instance, "feedback", "")):
            raise serializers.ValidationError(
                {"status": "Completed interviews should include score or feedback."}
            )
        return attrs


class AdmissionDecisionSerializer(serializers.ModelSerializer):
    application_number = serializers.CharField(source="application.application_number", read_only=True)
    decided_by_name = serializers.CharField(source="decided_by.username", read_only=True)

    class Meta:
        model = AdmissionDecision
        fields = [
            "id",
            "application",
            "application_number",
            "decision",
            "decision_date",
            "decision_notes",
            "offer_deadline",
            "response_status",
            "response_notes",
            "responded_at",
            "decided_by",
            "decided_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["decided_by", "responded_at", "created_at", "updated_at"]

    def validate(self, attrs):
        decision_value = attrs.get("decision") or getattr(self.instance, "decision", None)
        decision_date = attrs.get("decision_date") or getattr(self.instance, "decision_date", None)
        offer_deadline = attrs.get("offer_deadline", getattr(self.instance, "offer_deadline", None))
        response_status = attrs.get("response_status", getattr(self.instance, "response_status", "Pending"))

        if offer_deadline and decision_date and offer_deadline < decision_date:
            raise serializers.ValidationError(
                {"offer_deadline": "Offer deadline cannot be earlier than decision date."}
            )
        if decision_value != "Accept" and offer_deadline:
            raise serializers.ValidationError(
                {"offer_deadline": "Offer deadline is only valid when decision is Accept."}
            )
        if not self.instance and response_status != "Pending":
            raise serializers.ValidationError(
                {"response_status": "Initial response_status must be Pending."}
            )
        return attrs
