from django.contrib import admin

from .models import (
    AdmissionApplicationProfile,
    AdmissionAssessment,
    AdmissionDecision,
    AdmissionInquiry,
    AdmissionInterview,
    AdmissionReview,
)


@admin.register(AdmissionInquiry)
class AdmissionInquiryAdmin(admin.ModelAdmin):
    list_display = ("child_name", "parent_name", "status", "inquiry_source", "inquiry_date")
    search_fields = ("child_name", "parent_name", "parent_email", "parent_phone")
    list_filter = ("status", "inquiry_source", "inquiry_date")


@admin.register(AdmissionApplicationProfile)
class AdmissionApplicationProfileAdmin(admin.ModelAdmin):
    list_display = ("application", "inquiry", "academic_year", "term", "is_shortlisted", "shortlisted_at", "created_at")
    search_fields = ("application__application_number", "inquiry__child_name")
    list_filter = ("academic_year", "term")


@admin.register(AdmissionReview)
class AdmissionReviewAdmin(admin.ModelAdmin):
    list_display = ("application", "reviewer", "overall_score", "recommendation", "reviewed_at")
    search_fields = ("application__application_number", "reviewer__username")
    list_filter = ("recommendation",)


@admin.register(AdmissionAssessment)
class AdmissionAssessmentAdmin(admin.ModelAdmin):
    list_display = ("application", "scheduled_at", "status", "score", "is_pass")
    search_fields = ("application__application_number",)
    list_filter = ("status",)


@admin.register(AdmissionInterview)
class AdmissionInterviewAdmin(admin.ModelAdmin):
    list_display = ("application", "interview_date", "interview_type", "status", "score")
    search_fields = ("application__application_number",)
    list_filter = ("status", "interview_type")


@admin.register(AdmissionDecision)
class AdmissionDecisionAdmin(admin.ModelAdmin):
    list_display = ("application", "decision", "decision_date", "response_status", "offer_deadline")
    search_fields = ("application__application_number",)
    list_filter = ("decision", "response_status")
