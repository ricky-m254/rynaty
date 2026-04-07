from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AdmissionApplicationProfileViewSet,
    AdmissionApplicationViewSet,
    AdmissionAssessmentViewSet,
    AdmissionAnalyticsFunnelView,
    AdmissionAnalyticsSourcesView,
    AdmissionDecisionViewSet,
    AdmissionInterviewViewSet,
    AdmissionInquiryViewSet,
    AdmissionReviewViewSet,
    AdmissionsPipelineSummaryView,
    AdmissionWaitlistQueueView,
    EnrollmentReadyApplicationsView,
    ShortlistedApplicationsView,
)

router = DefaultRouter()
router.register(r"applications", AdmissionApplicationViewSet, basename="admissions_applications")
router.register(r"inquiries", AdmissionInquiryViewSet, basename="admissions_inquiries")
router.register(r"application-profiles", AdmissionApplicationProfileViewSet, basename="admissions_application_profiles")
router.register(r"reviews", AdmissionReviewViewSet, basename="admissions_reviews")
router.register(r"assessments", AdmissionAssessmentViewSet, basename="admissions_assessments")
router.register(r"interviews", AdmissionInterviewViewSet, basename="admissions_interviews")
router.register(r"decisions", AdmissionDecisionViewSet, basename="admissions_decisions")

urlpatterns = [
    path("summary/", AdmissionsPipelineSummaryView.as_view(), name="admissions_summary"),
    path("shortlisted/", ShortlistedApplicationsView.as_view(), name="admissions_shortlisted"),
    path("enrollment/ready/", EnrollmentReadyApplicationsView.as_view(), name="admissions_enrollment_ready"),
    path("waitlist/queue/", AdmissionWaitlistQueueView.as_view(), name="admissions_waitlist_queue"),
    path("analytics/funnel/", AdmissionAnalyticsFunnelView.as_view(), name="admissions_analytics_funnel"),
    path("analytics/sources/", AdmissionAnalyticsSourcesView.as_view(), name="admissions_analytics_sources"),
    path("", include(router.urls)),
]
