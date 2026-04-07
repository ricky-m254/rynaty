from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import AcademicYear, FeeStructure, Module, Role, SchoolClass, SchoolProfile, Staff, Subject, TeacherAssignment, Term, UserProfile

from .views import AdmissionApplicationViewSet, AdmissionDecisionViewSet, AdmissionInquiryViewSet

User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django_tenants.utils import schema_context

        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="admissions_phase4_cleanup",
                name="Admissions Phase 4 Cleanup School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="admissions-phase4.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        from django_tenants.utils import schema_context

        self.schema_context = schema_context(self.tenant.schema_name)
        self.schema_context.__enter__()

    def tearDown(self):
        self.schema_context.__exit__(None, None, None)


class AdmissionsAuthorityCleanupTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user, _ = User.objects.get_or_create(username="admissions_phase4_admin")
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
        SchoolProfile.objects.create(school_name="Admissions Phase 4 Test School", is_active=True)
        self.subject = Subject.objects.create(name="Mathematics", code="ADM-P4-MATH", is_active=True)
        Staff.objects.get_or_create(
            employee_id="ADM-P4-EMP-001",
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
            name="Admissions Phase 4 Tuition",
            amount="1000.00",
            academic_year=self.year,
            term=self.term,
            is_active=True,
        )

    def test_enrollment_complete_uses_normalized_profile_term_and_application_grade_defaults(self):
        create_inquiry = self.factory.post(
            "/api/admissions/inquiries/",
            {
                "parent_name": "Phase 4 Parent",
                "parent_email": "phase4@example.com",
                "child_name": "Phase Four Child",
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

        create_decision = self.factory.post(
            "/api/admissions/decisions/",
            {
                "application": application_id,
                "decision": "Accept",
                "decision_date": date.today().isoformat(),
                "offer_deadline": (date.today() + timedelta(days=14)).isoformat(),
            },
            format="json",
        )
        force_authenticate(create_decision, user=self.user)
        decision_response = AdmissionDecisionViewSet.as_view({"post": "create"})(create_decision)
        self.assertEqual(decision_response.status_code, 201)

        respond_request = self.factory.post(
            f"/api/admissions/decisions/{decision_response.data['id']}/respond/",
            {"response_status": "Accepted"},
            format="json",
        )
        force_authenticate(respond_request, user=self.user)
        respond_response = AdmissionDecisionViewSet.as_view({"post": "respond"})(respond_request, pk=decision_response.data["id"])
        self.assertEqual(respond_response.status_code, 200)

        enroll_request = self.factory.post(
            f"/api/admissions/applications/{application_id}/enrollment-complete/",
            {
                "assign_admission_number": True,
                "enrollment_date": "2026-03-18",
            },
            format="json",
        )
        force_authenticate(enroll_request, user=self.user)
        enroll_response = AdmissionApplicationViewSet.as_view({"post": "enrollment_complete"})(enroll_request, pk=application_id)

        self.assertEqual(enroll_response.status_code, 200)

        application = AdmissionApplicationViewSet.queryset.get(pk=application_id)
        enrollment = application.student.enrollment_set.get()
        self.assertEqual(enrollment.school_class_id, self.school_class.id)
        self.assertEqual(enrollment.term_id, self.term.id)
