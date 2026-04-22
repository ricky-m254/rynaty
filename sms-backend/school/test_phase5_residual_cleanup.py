from datetime import date
import io

from django.contrib.auth import get_user_model
from django.test import TestCase
from django_tenants.utils import schema_context

from cafeteria.models import MealPlan, StudentMealEnrollment, WeeklyMenu
from clients.models import Domain, Tenant
from communication.models import Notification
from parent_portal.models import ParentStudentLink
from school.management.commands.seed_kenya_school import Command
from school.models import AttendanceRecord, Student


User = get_user_model()


class ResidualCleanupTenantBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="residual_cleanup_test",
                name="Residual Cleanup Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="residual-cleanup.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.schema_ctx = schema_context(self.tenant.schema_name)
        self.schema_ctx.__enter__()

    def tearDown(self):
        self.schema_ctx.__exit__(None, None, None)


class CafeteriaSeedRegressionTests(ResidualCleanupTenantBase):
    def test_seed_cafeteria_reuses_duplicate_enrollments(self):
        student = Student.objects.create(
            admission_number="RCL-CAF-001",
            first_name="Cafeteria",
            last_name="Reuse",
            date_of_birth=date(2012, 1, 1),
            gender="F",
            is_active=True,
        )
        full_board = MealPlan.objects.create(
            name="Full Board",
            description="Existing full board",
            price_per_day=450,
            is_active=True,
        )
        lunch_only = MealPlan.objects.create(
            name="Lunch Only",
            description="Existing lunch only",
            price_per_day=180,
            is_active=True,
        )
        MealPlan.objects.create(
            name="Breakfast & Lunch",
            description="Existing breakfast and lunch",
            price_per_day=320,
            is_active=True,
        )
        StudentMealEnrollment.objects.create(student=student, meal_plan=full_board, is_active=True)
        StudentMealEnrollment.objects.create(student=student, meal_plan=lunch_only, is_active=True)

        command = Command()
        command.stdout = io.StringIO()

        command._seed_cafeteria([student])

        self.assertEqual(StudentMealEnrollment.objects.filter(student=student, is_active=True).count(), 1)
        self.assertEqual(StudentMealEnrollment.objects.filter(student=student).count(), 2)
        self.assertEqual(WeeklyMenu.objects.count(), 1)


class AttendanceSignalRegressionTests(ResidualCleanupTenantBase):
    def test_absence_signal_handles_string_batch_dates(self):
        student = Student.objects.create(
            admission_number="RCL-ATT-001",
            first_name="Attendance",
            last_name="Signal",
            date_of_birth=date(2012, 2, 2),
            gender="M",
            is_active=True,
        )
        parent = User.objects.create_user(username="rcl_parent", password="pass1234")
        recorder = User.objects.create_user(username="rcl_recorder", password="pass1234")
        ParentStudentLink.objects.create(parent_user=parent, student=student, is_active=True)

        AttendanceRecord.objects.update_or_create(
            student=student,
            date="2026-04-22",
            defaults={
                "status": "Absent",
                "notes": "Missing from class",
                "recorded_by": recorder,
            },
        )

        notification = Notification.objects.get(recipient=parent, notification_type="Academic")
        self.assertIn("Absence Alert", notification.title)
        self.assertIn(student.first_name, notification.message)
