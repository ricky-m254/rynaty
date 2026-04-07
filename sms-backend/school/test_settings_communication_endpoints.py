from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import Module, Role, SchoolProfile, UserModuleAssignment, UserProfile
from school.views import SchoolTestEmailView, SchoolTestSmsView


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="settings_comm_test",
                name="Settings Communication Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="settings-comm.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()

    def tearDown(self):
        self.schema_ctx.__exit__(None, None, None)


class SchoolSettingsCommunicationTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

        students_module, _ = Module.objects.get_or_create(key="STUDENTS", defaults={"name": "Students"})
        admin_role, _ = Role.objects.get_or_create(name="ADMIN", defaults={"description": "Admin"})
        self.user = User.objects.create_user(username="settings_comm_admin", password="pass1234")
        UserProfile.objects.create(user=self.user, role=admin_role)
        UserModuleAssignment.objects.create(user=self.user, module=students_module, is_active=True)

        self.profile = SchoolProfile.objects.create(
            school_name="Comm Test School",
            phone="+254700000001",
            email_address="office@example.com",
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="alerts@example.com",
            smtp_use_tls=True,
            sms_provider="africastalking",
            sms_sender_id="SCHOOL",
            is_active=True,
        )

    def test_school_test_email_view_sends_to_profile_smtp_user(self):
        mail.outbox = []
        request = self.factory.post("/api/school/test-email/", {}, format="json")
        force_authenticate(request, user=self.user)
        response = SchoolTestEmailView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["message"], f"Test email sent to {self.profile.smtp_user}.")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.profile.smtp_user])

    def test_school_test_sms_view_uses_school_phone(self):
        request = self.factory.post("/api/school/test-sms/", {}, format="json")
        force_authenticate(request, user=self.user)
        response = SchoolTestSmsView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["message"], f"Test SMS sent to {self.profile.phone}.")
        self.assertIn("provider_id", response.data)
