from django.contrib.auth import get_user_model
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import Module, Role, UserProfile
from school.views import MessageViewSet

from .models import Message
from .views import LegacyMessageViewSet


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant, _ = Tenant.objects.get_or_create(
                schema_name="communication_phase5_test",
                defaults={
                    "name": "Communication Phase 5 Test School",
                    "paid_until": "2030-01-01",
                },
            )
            Domain.objects.get_or_create(
                domain="communication-phase5.localhost",
                defaults={"tenant": cls.tenant, "is_primary": True},
            )

    def setUp(self):
        self.ctx = schema_context(self.tenant.schema_name)
        self.ctx.__enter__()

    def tearDown(self):
        self.ctx.__exit__(None, None, None)


class CommunicationPhase5ContractTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.admin, _ = User.objects.get_or_create(
            username="comm_phase5_admin",
            defaults={"email": "comm-phase5-admin@school.local"},
        )
        self.admin.set_password("pass1234")
        self.admin.save(update_fields=["password"])

        admin_role, _ = Role.objects.get_or_create(name="ADMIN", defaults={"description": "School Administrator"})
        UserProfile.objects.get_or_create(user=self.admin, defaults={"role": admin_role})
        Module.objects.get_or_create(key="COMMUNICATION", defaults={"name": "Communication"})

    def test_legacy_message_route_is_exposed_under_communication_namespace(self):
        create_request = self.factory.post(
            "/api/communication/legacy-messages/",
            {
                "recipient_type": "STAFF",
                "recipient_id": 0,
                "subject": "Legacy Contract",
                "body": "Legacy message body",
            },
            format="json",
        )
        force_authenticate(create_request, user=self.admin)
        create_response = LegacyMessageViewSet.as_view({"post": "create"})(create_request)
        self.assertEqual(create_response.status_code, 201)
        self.assertTrue(Message.objects.filter(subject="Legacy Contract").exists())

        list_request = self.factory.get("/api/communication/legacy-messages/")
        force_authenticate(list_request, user=self.admin)
        list_response = LegacyMessageViewSet.as_view({"get": "list"})(list_request)
        self.assertEqual(list_response.status_code, 200)
        payload = list_response.data.get("results", list_response.data) if hasattr(list_response.data, "get") else list_response.data
        self.assertTrue(any(item["subject"] == "Legacy Contract" for item in payload))

    def test_school_legacy_message_warning_points_to_communication_legacy_route(self):
        Message.objects.create(
            recipient_type="STAFF",
            recipient_id=0,
            subject="Deprecated Route",
            body="Check warning header",
            status="SENT",
        )

        request = self.factory.get("/api/messages/")
        force_authenticate(request, user=self.admin)
        response = MessageViewSet.as_view({"get": "list"})(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Warning"], "299 - Deprecated; use /api/communication/legacy-messages/")
