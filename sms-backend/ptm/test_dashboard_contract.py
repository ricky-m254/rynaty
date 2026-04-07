from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import Role, UserProfile

from .models import PTMSession, PTMSlot
from .views import PTMDashboardView


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant, _ = Tenant.objects.get_or_create(
                schema_name="ptm_dashboard_contract",
                defaults={
                    "name": "PTM Dashboard Contract School",
                    "paid_until": "2030-01-01",
                },
            )
            Domain.objects.get_or_create(
                domain="ptm-dashboard.localhost",
                defaults={"tenant": cls.tenant, "is_primary": True},
            )

    def setUp(self):
        self.ctx = schema_context(self.tenant.schema_name)
        self.ctx.__enter__()

    def tearDown(self):
        self.ctx.__exit__(None, None, None)


class PTMDashboardContractTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

        self.admin, _ = User.objects.get_or_create(username="ptm_dashboard_admin")
        admin_role, _ = Role.objects.get_or_create(
            name="ADMIN",
            defaults={"description": "School Administrator"},
        )
        UserProfile.objects.get_or_create(user=self.admin, defaults={"role": admin_role})

        self.teacher, _ = User.objects.get_or_create(
            username="ptm_dashboard_teacher",
            defaults={"email": "teacher@ptm-dashboard.local"},
        )
        teacher_role, _ = Role.objects.get_or_create(
            name="TEACHER",
            defaults={"description": "Teacher"},
        )
        UserProfile.objects.get_or_create(user=self.teacher, defaults={"role": teacher_role})

    def _create_session(self, *, title, session_date, booked):
        session = PTMSession.objects.create(
            title=title,
            date=session_date,
            venue="Main Hall",
            slot_duration_minutes=15,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )
        PTMSlot.objects.create(
            session=session,
            teacher=self.teacher,
            slot_time=time(9, 0),
            is_booked=booked,
        )
        PTMSlot.objects.create(
            session=session,
            teacher=self.teacher,
            slot_time=time(9, 15),
            is_booked=False,
        )
        return session

    def test_dashboard_returns_upcoming_counts_and_preview_list(self):
        today = date.today()
        for index in range(6):
            self._create_session(
                title=f"Session {index + 1}",
                session_date=today + timedelta(days=index + 1),
                booked=index % 2 == 0,
            )

        self._create_session(
            title="Past Session",
            session_date=today - timedelta(days=1),
            booked=True,
        )

        request = self.factory.get("/api/ptm/dashboard/")
        force_authenticate(request, user=self.admin)
        response = PTMDashboardView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_sessions"], 7)
        self.assertEqual(response.data["upcoming_session_count"], 6)
        self.assertEqual(response.data["total_slots"], 12)
        self.assertEqual(response.data["booked_slots"], 3)
        self.assertEqual(response.data["available_slots"], 9)
        self.assertEqual(len(response.data["upcoming_sessions"]), 5)
        self.assertEqual(
            [session["title"] for session in response.data["upcoming_sessions"]],
            ["Session 1", "Session 2", "Session 3", "Session 4", "Session 5"],
        )
