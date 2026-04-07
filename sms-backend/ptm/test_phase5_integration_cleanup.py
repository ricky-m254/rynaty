from datetime import date, timedelta, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from communication.models import Notification
from parent_portal.models import ParentStudentLink
from school.models import Role, Student, UserProfile

from .models import PTMBooking, PTMSession, PTMSlot
from .views import PTMBookingViewSet


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant, _ = Tenant.objects.get_or_create(
                schema_name="ptm_phase5_test",
                defaults={
                    "name": "PTM Phase 5 Test School",
                    "paid_until": "2030-01-01",
                },
            )
            Domain.objects.get_or_create(
                domain="ptm-phase5.localhost",
                defaults={"tenant": cls.tenant, "is_primary": True},
            )

    def setUp(self):
        self.ctx = schema_context(self.tenant.schema_name)
        self.ctx.__enter__()

    def tearDown(self):
        self.ctx.__exit__(None, None, None)


class PTMPhase5IntegrationTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

        self.admin, _ = User.objects.get_or_create(username="ptm_phase5_admin")
        self.admin.set_password("pass1234")
        self.admin.save(update_fields=["password"])
        admin_role, _ = Role.objects.get_or_create(name="ADMIN", defaults={"description": "School Administrator"})
        UserProfile.objects.get_or_create(user=self.admin, defaults={"role": admin_role})

        self.teacher, _ = User.objects.get_or_create(
            username="ptm_phase5_teacher",
            defaults={"email": "teacher@ptm.local"},
        )
        teacher_role, _ = Role.objects.get_or_create(name="TEACHER", defaults={"description": "Teacher"})
        UserProfile.objects.get_or_create(user=self.teacher, defaults={"role": teacher_role})

        self.parent, _ = User.objects.get_or_create(
            username="ptm_phase5_parent",
            defaults={"email": "parent@ptm.local"},
        )
        parent_role, _ = Role.objects.get_or_create(name="PARENT", defaults={"description": "Parent"})
        UserProfile.objects.get_or_create(user=self.parent, defaults={"role": parent_role})

        self.student = Student.objects.create(
            admission_number="PTM-PHASE5-001",
            first_name="Amina",
            last_name="Otieno",
            gender="F",
            date_of_birth="2012-03-15",
        )
        ParentStudentLink.objects.create(
            parent_user=self.parent,
            student=self.student,
            relationship="Parent",
            is_primary=True,
            is_active=True,
            created_by=self.admin,
        )
        self.session = PTMSession.objects.create(
            title="Term 2 PTM",
            date=date.today() + timedelta(days=7),
            venue="Main Hall",
            slot_duration_minutes=15,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )
        self.slot = PTMSlot.objects.create(
            session=self.session,
            teacher=self.teacher,
            slot_time=time(9, 15),
            is_booked=False,
        )

    def test_confirmed_booking_notifies_teacher_and_linked_parent(self):
        request = self.factory.post(
            "/api/ptm/bookings/",
            {
                "slot": self.slot.id,
                "student": self.student.id,
                "parent_name": "Mercy Otieno",
                "parent_phone": "+254700000001",
                "parent_email": "mercy@example.com",
                "status": "Confirmed",
            },
            format="json",
        )
        force_authenticate(request, user=self.admin)
        response = PTMBookingViewSet.as_view({"post": "create"})(request)

        self.assertEqual(response.status_code, 201)
        self.assertTrue(PTMBooking.objects.filter(slot=self.slot, student=self.student).exists())
        self.assertEqual(Notification.objects.count(), 2)

        teacher_notification = Notification.objects.get(recipient=self.teacher)
        self.assertEqual(teacher_notification.notification_type, "Event")
        self.assertEqual(teacher_notification.action_url, "/modules/ptm/bookings")
        self.assertIn("PTM booking confirmed", teacher_notification.title)
        self.assertIn("Mercy Otieno", teacher_notification.message)
        self.assertIn("Amina Otieno", teacher_notification.message)

        parent_notification = Notification.objects.get(recipient=self.parent)
        self.assertEqual(parent_notification.notification_type, "Event")
        self.assertEqual(parent_notification.action_url, "/modules/parent-portal/dashboard")
        self.assertIn("PTM booking confirmed", parent_notification.title)
        self.assertIn("ptm_phase5_teacher", parent_notification.message)
        self.assertIn("Amina Otieno", parent_notification.message)
