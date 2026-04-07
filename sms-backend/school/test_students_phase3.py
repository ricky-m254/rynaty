from django.contrib.auth import get_user_model
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import BehaviorIncident, Module, Role, Student, UserModuleAssignment, UserProfile
from school.views import BehaviorIncidentViewSet


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="students_phase3_test",
                name="Students Phase3 Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="students-phase3.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()

    def tearDown(self):
        self.schema_ctx.__exit__(None, None, None)


class StudentsPhase3BehaviorFilterTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

        students_module = Module.objects.create(key="STUDENTS", name="Students")
        role = Role.objects.create(name="ADMIN", description="Admin")
        self.user = User.objects.create_user(username="students_phase3_admin", password="pass1234")
        UserProfile.objects.create(user=self.user, role=role)
        UserModuleAssignment.objects.create(user=self.user, module=students_module, is_active=True)

        self.student = Student.objects.create(
            admission_number="S-SP3-001",
            first_name="Phase",
            last_name="Three",
            date_of_birth="2012-01-01",
            gender="M",
            is_active=True,
        )
        BehaviorIncident.objects.create(
            student=self.student,
            incident_type="Negative",
            category="Discipline",
            incident_date="2026-02-14",
            severity="Low",
        )
        BehaviorIncident.objects.create(
            student=self.student,
            incident_type="Negative",
            category="Discipline",
            incident_date="2026-02-15",
            severity="High",
        )

    def test_behavior_incident_filters_by_severity(self):
        request = self.factory.get("/api/behavior/incidents/?severity=High")
        force_authenticate(request, user=self.user)
        response = BehaviorIncidentViewSet.as_view({"get": "list"})(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["severity"], "High")
