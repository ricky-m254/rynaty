from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import Module, Role, UserProfile

from .views import (
    AdmissionApplicationViewSet,
    AdmissionAssessmentViewSet,
    AdmissionAnalyticsFunnelView,
    AdmissionAnalyticsSourcesView,
    AdmissionDecisionViewSet,
    AdmissionInterviewViewSet,
    AdmissionInquiryViewSet,
    AdmissionWaitlistQueueView,
    EnrollmentReadyApplicationsView,
    AdmissionReviewViewSet,
    ShortlistedApplicationsView,
)
from school.models import (
    AcademicYear,
    AuditLog,
    FeeStructure,
    SchoolClass,
    SchoolProfile,
    Staff,
    Subject,
    TeacherAssignment,
    Term,
)


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django_tenants.utils import schema_context

        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="admissions_test",
                name="Admissions Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="admissions.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        from django_tenants.utils import schema_context

        self.schema_context = schema_context(self.tenant.schema_name)
        self.schema_context.__enter__()

    def tearDown(self):
        self.schema_context.__exit__(None, None, None)


class AdmissionsPhaseBTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.today = date.today()
        self.decision_date = self.today.isoformat()
        self.future_offer_deadline = (self.today + timedelta(days=14)).isoformat()
        self.user, _ = User.objects.get_or_create(username="adm_tester")
        self.user.set_password("pass123")
        self.user.save(update_fields=["password"])
        role, _ = Role.objects.get_or_create(name="ADMIN", defaults={"description": "Admin"})
        UserProfile.objects.get_or_create(user=self.user, defaults={"role": role})
        Module.objects.get_or_create(key="ADMISSIONS", defaults={"name": "Admissions"})
        self.year = AcademicYear.objects.create(
            name="2026/2027",
            start_date="2026-01-01",
            end_date="2026-12-31",
            is_active=True,
        )
        self.term = Term.objects.create(
            academic_year=self.year,
            name="Term 1",
            start_date="2026-01-01",
            end_date="2026-04-30",
            is_active=True,
        )
        self.school_class = SchoolClass.objects.create(
            name="Grade 7",
            stream="A",
            academic_year=self.year,
            is_active=True,
        )
        SchoolProfile.objects.create(school_name="Admissions Test School", is_active=True)
        self.subject = Subject.objects.create(name="Mathematics", code="ADM-MATH", is_active=True)
        Staff.objects.get_or_create(
            employee_id="ADM-EMP-001",
            defaults={
                "first_name": "Class",
                "last_name": "Teacher",
                "role": "Teacher",
                "phone": "0700000001",
                "is_active": True,
            },
        )
        TeacherAssignment.objects.create(
            teacher=self.user,
            subject=self.subject,
            class_section=self.school_class,
            academic_year=self.year,
            term=self.term,
            is_primary=True,
            is_active=True,
        )
        FeeStructure.objects.create(
            name="Admissions Test Tuition",
            amount="1000.00",
            academic_year=self.year,
            term=self.term,
            is_active=True,
        )

    def _decision_day(self, offset_days=0):
        return (self.today + timedelta(days=offset_days)).isoformat()

    def _accept_decision_payload(self, application_id, *, with_deadline=False, response_status=None):
        payload = {
            "application": application_id,
            "decision": "Accept",
            "decision_date": self.decision_date,
        }
        if with_deadline:
            payload["offer_deadline"] = self.future_offer_deadline
        if response_status is not None:
            payload["response_status"] = response_status
        return payload

    def test_inquiry_create_and_convert(self):
        create_request = self.factory.post(
            "/api/admissions/inquiries/",
            {
                "parent_name": "Jane Doe",
                "parent_email": "jane@example.com",
                "child_name": "Amy Doe",
                "inquiry_date": "2026-02-14",
                "inquiry_source": "Website",
                "grade_level_interest": self.school_class.id,
                "preferred_start": self.term.id,
            },
            format="json",
        )
        force_authenticate(create_request, user=self.user)
        create_response = AdmissionInquiryViewSet.as_view({"post": "create"})(create_request)
        self.assertEqual(create_response.status_code, 201)
        inquiry_id = create_response.data["id"]

        convert_request = self.factory.post(
            f"/api/admissions/inquiries/{inquiry_id}/convert/",
            {"student_gender": "Female"},
            format="json",
        )
        force_authenticate(convert_request, user=self.user)
        convert_response = AdmissionInquiryViewSet.as_view({"post": "convert"})(convert_request, pk=inquiry_id)
        self.assertEqual(convert_response.status_code, 201)
        self.assertIn("application_id", convert_response.data)

    def test_review_and_shortlist_flow(self):
        create_inquiry = self.factory.post(
            "/api/admissions/inquiries/",
            {
                "parent_name": "Mark Doe",
                "parent_email": "mark@example.com",
                "child_name": "Bella Doe",
                "inquiry_date": "2026-02-14",
                "inquiry_source": "Referral",
                "grade_level_interest": self.school_class.id,
                "preferred_start": self.term.id,
            },
            format="json",
        )
        force_authenticate(create_inquiry, user=self.user)
        inquiry_response = AdmissionInquiryViewSet.as_view({"post": "create"})(create_inquiry)
        self.assertEqual(inquiry_response.status_code, 201)
        inquiry_id = inquiry_response.data["id"]

        convert_request = self.factory.post(
            f"/api/admissions/inquiries/{inquiry_id}/convert/",
            {"student_gender": "Female"},
            format="json",
        )
        force_authenticate(convert_request, user=self.user)
        convert_response = AdmissionInquiryViewSet.as_view({"post": "convert"})(convert_request, pk=inquiry_id)
        self.assertEqual(convert_response.status_code, 201)
        application_id = convert_response.data["application_id"]

        create_review = self.factory.post(
            "/api/admissions/reviews/",
            {
                "application": application_id,
                "academic_score": "78.00",
                "test_score": "66.00",
                "interview_score": "84.00",
                "overall_score": "76.00",
                "recommendation": "Accept",
                "comments": "Good candidate",
            },
            format="json",
        )
        force_authenticate(create_review, user=self.user)
        review_response = AdmissionReviewViewSet.as_view({"post": "create"})(create_review)
        self.assertEqual(review_response.status_code, 201)

        shortlist_request = self.factory.post(
            f"/api/admissions/applications/{application_id}/shortlist/",
            {},
            format="json",
        )
        force_authenticate(shortlist_request, user=self.user)
        shortlist_response = AdmissionApplicationViewSet.as_view({"post": "shortlist"})(
            shortlist_request,
            pk=application_id,
        )
        self.assertEqual(shortlist_response.status_code, 200)
        self.assertTrue(shortlist_response.data["shortlisted"])

        list_shortlisted = self.factory.get("/api/admissions/shortlisted/")
        force_authenticate(list_shortlisted, user=self.user)
        shortlisted_response = ShortlistedApplicationsView.as_view()(list_shortlisted)
        self.assertEqual(shortlisted_response.status_code, 200)
        self.assertTrue(any(item["id"] == application_id for item in shortlisted_response.data))

    def test_assessment_and_interview_flow(self):
        create_inquiry = self.factory.post(
            "/api/admissions/inquiries/",
            {
                "parent_name": "Lucy Doe",
                "parent_email": "lucy@example.com",
                "child_name": "Chris Doe",
                "inquiry_date": "2026-02-14",
                "inquiry_source": "Event",
                "grade_level_interest": self.school_class.id,
                "preferred_start": self.term.id,
            },
            format="json",
        )
        force_authenticate(create_inquiry, user=self.user)
        inquiry_response = AdmissionInquiryViewSet.as_view({"post": "create"})(create_inquiry)
        self.assertEqual(inquiry_response.status_code, 201)
        inquiry_id = inquiry_response.data["id"]

        convert_request = self.factory.post(
            f"/api/admissions/inquiries/{inquiry_id}/convert/",
            {"student_gender": "Male"},
            format="json",
        )
        force_authenticate(convert_request, user=self.user)
        convert_response = AdmissionInquiryViewSet.as_view({"post": "convert"})(convert_request, pk=inquiry_id)
        self.assertEqual(convert_response.status_code, 201)
        application_id = convert_response.data["application_id"]

        create_assessment = self.factory.post(
            "/api/admissions/assessments/",
            {
                "application": application_id,
                "scheduled_at": "2026-03-01T09:00:00Z",
                "venue": "Main Hall",
                "status": "Scheduled",
            },
            format="json",
        )
        force_authenticate(create_assessment, user=self.user)
        assessment_response = AdmissionAssessmentViewSet.as_view({"post": "create"})(create_assessment)
        self.assertEqual(assessment_response.status_code, 201)

        create_interview = self.factory.post(
            "/api/admissions/interviews/",
            {
                "application": application_id,
                "interview_date": "2026-03-03T10:30:00Z",
                "interview_type": "In-person",
                "location": "Board Room",
                "panel": [self.user.id],
                "status": "Scheduled",
            },
            format="json",
        )
        force_authenticate(create_interview, user=self.user)
        interview_response = AdmissionInterviewViewSet.as_view({"post": "create"})(create_interview)
        self.assertEqual(interview_response.status_code, 201)

        interview_id = interview_response.data["id"]
        feedback_request = self.factory.post(
            f"/api/admissions/interviews/{interview_id}/feedback/",
            {
                "feedback": "Candidate communicates clearly.",
                "score": "82.00",
                "mark_completed": True,
            },
            format="json",
        )
        force_authenticate(feedback_request, user=self.user)
        feedback_response = AdmissionInterviewViewSet.as_view({"post": "add_feedback"})(feedback_request, pk=interview_id)
        self.assertEqual(feedback_response.status_code, 200)
        self.assertEqual(feedback_response.data["status"], "Completed")

    def test_decision_and_parent_response_flow(self):
        create_inquiry = self.factory.post(
            "/api/admissions/inquiries/",
            {
                "parent_name": "Peter Doe",
                "parent_email": "peter@example.com",
                "child_name": "Jane Junior",
                "inquiry_date": "2026-02-14",
                "inquiry_source": "Website",
                "grade_level_interest": self.school_class.id,
                "preferred_start": self.term.id,
            },
            format="json",
        )
        force_authenticate(create_inquiry, user=self.user)
        inquiry_response = AdmissionInquiryViewSet.as_view({"post": "create"})(create_inquiry)
        self.assertEqual(inquiry_response.status_code, 201)

        convert_request = self.factory.post(
            f"/api/admissions/inquiries/{inquiry_response.data['id']}/convert/",
            {"student_gender": "Female"},
            format="json",
        )
        force_authenticate(convert_request, user=self.user)
        convert_response = AdmissionInquiryViewSet.as_view({"post": "convert"})(
            convert_request,
            pk=inquiry_response.data["id"],
        )
        self.assertEqual(convert_response.status_code, 201)
        application_id = convert_response.data["application_id"]

        create_decision = self.factory.post(
            "/api/admissions/decisions/",
            {
                **self._accept_decision_payload(application_id),
                "decision_notes": "Strong candidate.",
            },
            format="json",
        )
        force_authenticate(create_decision, user=self.user)
        decision_response = AdmissionDecisionViewSet.as_view({"post": "create"})(create_decision)
        self.assertEqual(decision_response.status_code, 201)
        decision_id = decision_response.data["id"]

        respond_request = self.factory.post(
            f"/api/admissions/decisions/{decision_id}/respond/",
            {"response_status": "Accepted", "response_notes": "Will join"},
            format="json",
        )
        force_authenticate(respond_request, user=self.user)
        respond_response = AdmissionDecisionViewSet.as_view({"post": "respond"})(respond_request, pk=decision_id)
        self.assertEqual(respond_response.status_code, 200)
        self.assertEqual(respond_response.data["response_status"], "Accepted")

        ready_request = self.factory.get("/api/admissions/enrollment/ready/")
        force_authenticate(ready_request, user=self.user)
        ready_response = EnrollmentReadyApplicationsView.as_view()(ready_request)
        self.assertEqual(ready_response.status_code, 200)
        self.assertTrue(any(item["id"] == application_id for item in ready_response.data))

        check_request = self.factory.post(f"/api/admissions/applications/{application_id}/enrollment-check/", {}, format="json")
        force_authenticate(check_request, user=self.user)
        check_response = AdmissionApplicationViewSet.as_view({"post": "enrollment_check"})(check_request, pk=application_id)
        self.assertEqual(check_response.status_code, 200)
        self.assertTrue(check_response.data["eligible"])

    def test_analytics_endpoints(self):
        create_inquiry = self.factory.post(
            "/api/admissions/inquiries/",
            {
                "parent_name": "Analytics Parent",
                "parent_email": "analytics@example.com",
                "child_name": "Analytics Child",
                "inquiry_date": "2026-02-14",
                "inquiry_source": "Website",
                "grade_level_interest": self.school_class.id,
                "preferred_start": self.term.id,
            },
            format="json",
        )
        force_authenticate(create_inquiry, user=self.user)
        AdmissionInquiryViewSet.as_view({"post": "create"})(create_inquiry)

        funnel_request = self.factory.get("/api/admissions/analytics/funnel/")
        force_authenticate(funnel_request, user=self.user)
        funnel_response = AdmissionAnalyticsFunnelView.as_view()(funnel_request)
        self.assertEqual(funnel_response.status_code, 200)
        self.assertIn("counts", funnel_response.data)
        self.assertIn("rates", funnel_response.data)

        source_request = self.factory.get("/api/admissions/analytics/sources/")
        force_authenticate(source_request, user=self.user)
        source_response = AdmissionAnalyticsSourcesView.as_view()(source_request)
        self.assertEqual(source_response.status_code, 200)
        self.assertIn("sources", source_response.data)

    def test_enrollment_requires_accepted_decision_and_response(self):
        create_inquiry = self.factory.post(
            "/api/admissions/inquiries/",
            {
                "parent_name": "Hardening Parent",
                "parent_email": "hardening@example.com",
                "child_name": "Hardening Child",
                "inquiry_date": "2026-02-14",
                "inquiry_source": "Website",
                "grade_level_interest": self.school_class.id,
                "preferred_start": self.term.id,
            },
            format="json",
        )
        force_authenticate(create_inquiry, user=self.user)
        inquiry_response = AdmissionInquiryViewSet.as_view({"post": "create"})(create_inquiry)
        self.assertEqual(inquiry_response.status_code, 201)

        convert_request = self.factory.post(
            f"/api/admissions/inquiries/{inquiry_response.data['id']}/convert/",
            {"student_gender": "Male"},
            format="json",
        )
        force_authenticate(convert_request, user=self.user)
        convert_response = AdmissionInquiryViewSet.as_view({"post": "convert"})(convert_request, pk=inquiry_response.data["id"])
        self.assertEqual(convert_response.status_code, 201)
        application_id = convert_response.data["application_id"]

        enroll_before_decision = self.factory.post(
            f"/api/admissions/applications/{application_id}/enrollment-complete/",
            {
                "school_class": self.school_class.id,
                "term": self.term.id,
                "assign_admission_number": True,
            },
            format="json",
        )
        force_authenticate(enroll_before_decision, user=self.user)
        blocked_response = AdmissionApplicationViewSet.as_view({"post": "enrollment_complete"})(
            enroll_before_decision,
            pk=application_id,
        )
        self.assertEqual(blocked_response.status_code, 400)

        create_decision = self.factory.post(
            "/api/admissions/decisions/",
            self._accept_decision_payload(application_id),
            format="json",
        )
        force_authenticate(create_decision, user=self.user)
        decision_response = AdmissionDecisionViewSet.as_view({"post": "create"})(create_decision)
        self.assertEqual(decision_response.status_code, 201)

        enroll_before_response = self.factory.post(
            f"/api/admissions/applications/{application_id}/enrollment-complete/",
            {
                "school_class": self.school_class.id,
                "term": self.term.id,
                "assign_admission_number": True,
            },
            format="json",
        )
        force_authenticate(enroll_before_response, user=self.user)
        blocked_response_2 = AdmissionApplicationViewSet.as_view({"post": "enrollment_complete"})(
            enroll_before_response,
            pk=application_id,
        )
        self.assertEqual(blocked_response_2.status_code, 400)

        respond_request = self.factory.post(
            f"/api/admissions/decisions/{decision_response.data['id']}/respond/",
            {"response_status": "Accepted"},
            format="json",
        )
        force_authenticate(respond_request, user=self.user)
        respond_response = AdmissionDecisionViewSet.as_view({"post": "respond"})(respond_request, pk=decision_response.data["id"])
        self.assertEqual(respond_response.status_code, 200)

        enroll_after_response = self.factory.post(
            f"/api/admissions/applications/{application_id}/enrollment-complete/",
            {
                "school_class": self.school_class.id,
                "term": self.term.id,
                "assign_admission_number": True,
            },
            format="json",
        )
        force_authenticate(enroll_after_response, user=self.user)
        success_response = AdmissionApplicationViewSet.as_view({"post": "enrollment_complete"})(
            enroll_after_response,
            pk=application_id,
        )
        self.assertEqual(success_response.status_code, 200)

    def test_offer_letter_and_waitlist_queue(self):
        for idx, child_name in enumerate(["WL Child A", "WL Child B"], start=1):
            create_inquiry = self.factory.post(
                "/api/admissions/inquiries/",
                {
                    "parent_name": f"Waitlist Parent {idx}",
                    "parent_email": f"wait{idx}@example.com",
                    "child_name": child_name,
                    "inquiry_date": "2026-02-14",
                    "inquiry_source": "Referral",
                    "grade_level_interest": self.school_class.id,
                    "preferred_start": self.term.id,
                },
                format="json",
            )
            force_authenticate(create_inquiry, user=self.user)
            inquiry_response = AdmissionInquiryViewSet.as_view({"post": "create"})(create_inquiry)
            self.assertEqual(inquiry_response.status_code, 201)

            convert_request = self.factory.post(
                f"/api/admissions/inquiries/{inquiry_response.data['id']}/convert/",
                {"student_gender": "Female"},
                format="json",
            )
            force_authenticate(convert_request, user=self.user)
            convert_response = AdmissionInquiryViewSet.as_view({"post": "convert"})(convert_request, pk=inquiry_response.data["id"])
            self.assertEqual(convert_response.status_code, 201)
            application_id = convert_response.data["application_id"]

            create_decision = self.factory.post(
                "/api/admissions/decisions/",
                {
                    "application": application_id,
                    "decision": "Waitlist",
                    "decision_date": self._decision_day(idx),
                },
                format="json",
            )
            force_authenticate(create_decision, user=self.user)
            decision_response = AdmissionDecisionViewSet.as_view({"post": "create"})(create_decision)
            self.assertEqual(decision_response.status_code, 201)

        create_inquiry_accept = self.factory.post(
            "/api/admissions/inquiries/",
            {
                "parent_name": "Offer Parent",
                "parent_email": "offer@example.com",
                "child_name": "Offer Child",
                "inquiry_date": "2026-02-14",
                "inquiry_source": "Website",
                "grade_level_interest": self.school_class.id,
                "preferred_start": self.term.id,
            },
            format="json",
        )
        force_authenticate(create_inquiry_accept, user=self.user)
        inquiry_accept_response = AdmissionInquiryViewSet.as_view({"post": "create"})(create_inquiry_accept)
        self.assertEqual(inquiry_accept_response.status_code, 201)
        convert_accept_request = self.factory.post(
            f"/api/admissions/inquiries/{inquiry_accept_response.data['id']}/convert/",
            {"student_gender": "Male"},
            format="json",
        )
        force_authenticate(convert_accept_request, user=self.user)
        convert_accept_response = AdmissionInquiryViewSet.as_view({"post": "convert"})(convert_accept_request, pk=inquiry_accept_response.data["id"])
        self.assertEqual(convert_accept_response.status_code, 201)
        accepted_application_id = convert_accept_response.data["application_id"]
        create_accept_decision = self.factory.post(
            "/api/admissions/decisions/",
            self._accept_decision_payload(accepted_application_id),
            format="json",
        )
        force_authenticate(create_accept_decision, user=self.user)
        accept_decision_response = AdmissionDecisionViewSet.as_view({"post": "create"})(create_accept_decision)
        self.assertEqual(accept_decision_response.status_code, 201)

        offer_letter_request = self.factory.get(f"/api/admissions/decisions/{accept_decision_response.data['id']}/offer-letter/")
        force_authenticate(offer_letter_request, user=self.user)
        offer_letter_response = AdmissionDecisionViewSet.as_view({"get": "offer_letter"})(
            offer_letter_request,
            pk=accept_decision_response.data["id"],
        )
        self.assertEqual(offer_letter_response.status_code, 200)
        self.assertEqual(offer_letter_response["Content-Type"], "application/pdf")

        queue_request = self.factory.get("/api/admissions/waitlist/queue/")
        force_authenticate(queue_request, user=self.user)
        queue_response = AdmissionWaitlistQueueView.as_view()(queue_request)
        self.assertEqual(queue_response.status_code, 200)
        self.assertGreaterEqual(queue_response.data["count"], 2)
        self.assertEqual(queue_response.data["items"][0]["queue_position"], 1)

    def test_duplicate_decision_is_blocked(self):
        create_inquiry = self.factory.post(
            "/api/admissions/inquiries/",
            {
                "parent_name": "Dup Parent",
                "parent_email": "dup@example.com",
                "child_name": "Dup Child",
                "inquiry_date": "2026-02-14",
                "inquiry_source": "Website",
                "grade_level_interest": self.school_class.id,
                "preferred_start": self.term.id,
            },
            format="json",
        )
        force_authenticate(create_inquiry, user=self.user)
        inquiry_response = AdmissionInquiryViewSet.as_view({"post": "create"})(create_inquiry)
        self.assertEqual(inquiry_response.status_code, 201)

        convert_request = self.factory.post(
            f"/api/admissions/inquiries/{inquiry_response.data['id']}/convert/",
            {"student_gender": "Female"},
            format="json",
        )
        force_authenticate(convert_request, user=self.user)
        convert_response = AdmissionInquiryViewSet.as_view({"post": "convert"})(convert_request, pk=inquiry_response.data["id"])
        self.assertEqual(convert_response.status_code, 201)
        application_id = convert_response.data["application_id"]

        payload = self._accept_decision_payload(application_id)
        create_decision = self.factory.post("/api/admissions/decisions/", payload, format="json")
        force_authenticate(create_decision, user=self.user)
        first = AdmissionDecisionViewSet.as_view({"post": "create"})(create_decision)
        self.assertEqual(first.status_code, 201)

        create_decision2 = self.factory.post("/api/admissions/decisions/", payload, format="json")
        force_authenticate(create_decision2, user=self.user)
        second = AdmissionDecisionViewSet.as_view({"post": "create"})(create_decision2)
        self.assertEqual(second.status_code, 400)

    def test_response_rules_and_audit_entries(self):
        create_inquiry = self.factory.post(
            "/api/admissions/inquiries/",
            {
                "parent_name": "Rules Parent",
                "parent_email": "rules@example.com",
                "child_name": "Rules Child",
                "inquiry_date": "2026-02-14",
                "inquiry_source": "Website",
                "grade_level_interest": self.school_class.id,
                "preferred_start": self.term.id,
            },
            format="json",
        )
        force_authenticate(create_inquiry, user=self.user)
        inquiry_response = AdmissionInquiryViewSet.as_view({"post": "create"})(create_inquiry)
        self.assertEqual(inquiry_response.status_code, 201)

        convert_request = self.factory.post(
            f"/api/admissions/inquiries/{inquiry_response.data['id']}/convert/",
            {"student_gender": "Male"},
            format="json",
        )
        force_authenticate(convert_request, user=self.user)
        convert_response = AdmissionInquiryViewSet.as_view({"post": "convert"})(convert_request, pk=inquiry_response.data["id"])
        self.assertEqual(convert_response.status_code, 201)
        application_id = convert_response.data["application_id"]

        waitlist_decision = self.factory.post(
            "/api/admissions/decisions/",
            {
                "application": application_id,
                "decision": "Waitlist",
                "decision_date": self._decision_day(1),
            },
            format="json",
        )
        force_authenticate(waitlist_decision, user=self.user)
        waitlist_response = AdmissionDecisionViewSet.as_view({"post": "create"})(waitlist_decision)
        self.assertEqual(waitlist_response.status_code, 201)

        invalid_respond = self.factory.post(
            f"/api/admissions/decisions/{waitlist_response.data['id']}/respond/",
            {"response_status": "Accepted"},
            format="json",
        )
        force_authenticate(invalid_respond, user=self.user)
        invalid_response = AdmissionDecisionViewSet.as_view({"post": "respond"})(invalid_respond, pk=waitlist_response.data["id"])
        self.assertEqual(invalid_response.status_code, 400)

        self.assertTrue(AuditLog.objects.filter(action="CONVERT", model_name="AdmissionInquiry").exists())
        self.assertTrue(AuditLog.objects.filter(action="DECISION_CREATE", model_name="AdmissionDecision").exists())

    def test_contract_validation_score_ranges(self):
        create_inquiry = self.factory.post(
            "/api/admissions/inquiries/",
            {
                "parent_name": "Validation Parent",
                "parent_email": "validation@example.com",
                "child_name": "Validation Child",
                "inquiry_date": "2026-02-14",
                "inquiry_source": "Website",
                "grade_level_interest": self.school_class.id,
                "preferred_start": self.term.id,
            },
            format="json",
        )
        force_authenticate(create_inquiry, user=self.user)
        inquiry_response = AdmissionInquiryViewSet.as_view({"post": "create"})(create_inquiry)
        self.assertEqual(inquiry_response.status_code, 201)

        convert_request = self.factory.post(
            f"/api/admissions/inquiries/{inquiry_response.data['id']}/convert/",
            {"student_gender": "Male"},
            format="json",
        )
        force_authenticate(convert_request, user=self.user)
        convert_response = AdmissionInquiryViewSet.as_view({"post": "convert"})(convert_request, pk=inquiry_response.data["id"])
        self.assertEqual(convert_response.status_code, 201)
        application_id = convert_response.data["application_id"]

        bad_review = self.factory.post(
            "/api/admissions/reviews/",
            {
                "application": application_id,
                "overall_score": "120.00",
                "recommendation": "Accept",
            },
            format="json",
        )
        force_authenticate(bad_review, user=self.user)
        bad_review_response = AdmissionReviewViewSet.as_view({"post": "create"})(bad_review)
        self.assertEqual(bad_review_response.status_code, 400)

        bad_assessment = self.factory.post(
            "/api/admissions/assessments/",
            {
                "application": application_id,
                "scheduled_at": "2026-03-01T09:00:00Z",
                "status": "Completed",
            },
            format="json",
        )
        force_authenticate(bad_assessment, user=self.user)
        bad_assessment_response = AdmissionAssessmentViewSet.as_view({"post": "create"})(bad_assessment)
        self.assertEqual(bad_assessment_response.status_code, 400)

    def test_contract_validation_decision_rules(self):
        create_inquiry = self.factory.post(
            "/api/admissions/inquiries/",
            {
                "parent_name": "Decision Parent",
                "parent_email": "decision@example.com",
                "child_name": "Decision Child",
                "inquiry_date": "2026-02-14",
                "inquiry_source": "Website",
                "grade_level_interest": self.school_class.id,
                "preferred_start": self.term.id,
            },
            format="json",
        )
        force_authenticate(create_inquiry, user=self.user)
        inquiry_response = AdmissionInquiryViewSet.as_view({"post": "create"})(create_inquiry)
        self.assertEqual(inquiry_response.status_code, 201)

        convert_request = self.factory.post(
            f"/api/admissions/inquiries/{inquiry_response.data['id']}/convert/",
            {"student_gender": "Female"},
            format="json",
        )
        force_authenticate(convert_request, user=self.user)
        convert_response = AdmissionInquiryViewSet.as_view({"post": "convert"})(convert_request, pk=inquiry_response.data["id"])
        self.assertEqual(convert_response.status_code, 201)
        application_id = convert_response.data["application_id"]

        bad_offer_for_waitlist = self.factory.post(
            "/api/admissions/decisions/",
            {
                "application": application_id,
                "decision": "Waitlist",
                "decision_date": self.decision_date,
                "offer_deadline": self.future_offer_deadline,
            },
            format="json",
        )
        force_authenticate(bad_offer_for_waitlist, user=self.user)
        bad_offer_response = AdmissionDecisionViewSet.as_view({"post": "create"})(bad_offer_for_waitlist)
        self.assertEqual(bad_offer_response.status_code, 400)

        bad_initial_response = self.factory.post(
            "/api/admissions/decisions/",
            self._accept_decision_payload(application_id, response_status="Accepted"),
            format="json",
        )
        force_authenticate(bad_initial_response, user=self.user)
        bad_initial_response_result = AdmissionDecisionViewSet.as_view({"post": "create"})(bad_initial_response)
        self.assertEqual(bad_initial_response_result.status_code, 400)
