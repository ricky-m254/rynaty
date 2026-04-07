from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory

from clients.models import Domain, Tenant
from hr.models import Department, Employee, Position
from communication.models import Notification
from school.models import Role, UserProfile

from .models import BiometricDevice, ClockEvent, PersonRegistry, SchoolShift
from .views import ScanView

User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django_tenants.utils import schema_context

        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="clockin_authority_cleanup",
                name="Clockin Authority Cleanup School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="clockin-authority.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        from django_tenants.utils import schema_context

        self.schema_context = schema_context(self.tenant.schema_name)
        self.schema_context.__enter__()

    def tearDown(self):
        self.schema_context.__exit__(None, None, None)


class ClockInAuthorityCleanupTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.device = BiometricDevice.objects.create(
            name="Gate A",
            device_id="GATE-A",
            api_key="secret-key",
            is_active=True,
        )
        self.department = Department.objects.create(name="Operations", code="OPS", is_active=True)
        self.position = Position.objects.create(title="Officer", department=self.department, headcount=1, is_active=True)
        self.employee = Employee.objects.create(
            employee_id="EMP-CLK-001",
            first_name="Ali",
            last_name="Stone",
            date_of_birth="1992-01-01",
            gender="Other",
            department=self.department,
            position=self.position,
            join_date="2026-01-01",
            status="Active",
            employment_type="Full-time",
            is_active=True,
        )
        self.person = PersonRegistry.objects.create(
            fingerprint_id="FP-001",
            person_type="STAFF",
            employee=self.employee,
            display_name="Ali Stone",
            is_active=True,
        )

    def test_scan_view_routes_attendance_updates_through_shared_service(self):
        request = self.factory.post(
            "/api/clockin/scan/",
            {
                "fingerprint_id": self.person.fingerprint_id,
                "device_id": self.device.device_id,
                "timestamp": "2026-04-03T08:05:00Z",
            },
            format="json",
            HTTP_X_DEVICE_KEY=self.device.api_key,
        )

        with patch(
            "clockin.infrastructure.services.attendance_service.DjangoAttendanceService.update",
            return_value=True,
        ) as attendance_update:
            response = ScanView.as_view()(request)

        self.assertEqual(response.status_code, 201)
        attendance_update.assert_called_once()

        event = ClockEvent.objects.get(person=self.person)
        self.assertTrue(event.attendance_updated)

    def test_scan_view_preserves_raw_scan_retries_without_deduplication(self):
        request_body = {
            "fingerprint_id": self.person.fingerprint_id,
            "device_id": self.device.device_id,
            "timestamp": "2026-04-03T08:05:00Z",
        }

        with patch(
            "clockin.infrastructure.services.attendance_service.DjangoAttendanceService.update",
            return_value=True,
        ) as attendance_update:
            first_response = ScanView.as_view()(
                self.factory.post(
                    "/api/clockin/scan/",
                    request_body,
                    format="json",
                    HTTP_X_DEVICE_KEY=self.device.api_key,
                )
            )
            second_response = ScanView.as_view()(
                self.factory.post(
                    "/api/clockin/scan/",
                    request_body,
                    format="json",
                    HTTP_X_DEVICE_KEY=self.device.api_key,
                )
            )

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 201)
        self.assertEqual(ClockEvent.objects.filter(person=self.person).count(), 2)
        self.assertEqual(attendance_update.call_count, 2)

    def test_scan_view_late_arrival_notifies_admins_through_shared_service(self):
        admin_role, _ = Role.objects.get_or_create(
            name="ADMIN",
            defaults={"description": "School Administrator"},
        )
        admin_user, created = User.objects.get_or_create(username="clockin_admin")
        if created:
            admin_user.set_password("pass1234")
            admin_user.save(update_fields=["password"])
        UserProfile.objects.get_or_create(user=admin_user, defaults={"role": admin_role})
        SchoolShift.objects.create(
            name="Staff Morning Shift",
            person_type="STAFF",
            expected_arrival="08:00:00",
            grace_period_minutes=5,
            is_active=True,
        )

        request = self.factory.post(
            "/api/clockin/scan/",
            {
                "fingerprint_id": self.person.fingerprint_id,
                "device_id": self.device.device_id,
                "timestamp": "2026-04-03T08:10:00Z",
            },
            format="json",
            HTTP_X_DEVICE_KEY=self.device.api_key,
        )

        with patch(
            "clockin.infrastructure.services.attendance_service.DjangoAttendanceService.update",
            return_value=True,
        ):
            response = ScanView.as_view()(request)

        self.assertEqual(response.status_code, 201)

        event = ClockEvent.objects.get(person=self.person)
        self.assertTrue(event.is_late)

        notification = Notification.objects.get(recipient=admin_user)
        self.assertEqual(notification.title, "Late Arrival: Ali Stone")
        self.assertIn("Ali Stone", notification.message)
