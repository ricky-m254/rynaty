import re
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from academics.models import AcademicYear, SchoolClass, Term
from clients.models import Domain, Tenant
from school.models import Enrollment, Module, Role, SchoolProfile, Student, UserModuleAssignment, UserProfile
from school.views import FinanceEnrollmentRefView, FinanceStudentRefView, StudentViewSet

User = get_user_model()

ULID_RE = re.compile(r"^[0123456789ABCDEFGHJKMNPQRSTVWXYZ]{26}$")


class TenantPhase4Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="phase4_ulid_test",
                name="Phase 4 ULID Test",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="phase4-ulid.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        self.factory = APIRequestFactory()
        self.schema_context = schema_context(self.tenant.schema_name)
        self.schema_context.__enter__()

    def tearDown(self):
        self.schema_context.__exit__(None, None, None)

    @staticmethod
    def _create_user(username: str, role_name: str, modules: list[str]):
        user = User.objects.create_user(username=username, password="pass1234")
        role, _ = Role.objects.get_or_create(name=role_name, defaults={"description": role_name.title()})
        UserProfile.objects.update_or_create(user=user, defaults={"role": role})
        for key in modules:
            module, _ = Module.objects.get_or_create(key=key, defaults={"name": key.title(), "is_active": True})
            UserModuleAssignment.objects.update_or_create(
                user=user,
                module=module,
                defaults={"is_active": True},
            )
        return user


class Phase4UlidTests(TenantPhase4Base):
    def test_student_create_assigns_ulid_and_ignores_client_value(self):
        admin = self._create_user("phase4_ulid_admin", "ADMIN", ["STUDENTS"])
        SchoolProfile.objects.create(
            school_name="ULID School",
            admission_number_mode="AUTO",
            admission_number_prefix="ADM-",
            admission_number_padding=4,
            is_active=True,
        )

        request = self.factory.post(
            "/api/students/",
            {
                "ulid": "01ARZ3NDEKTSV4RRFFQ69G5FAZ",
                "first_name": "Amina",
                "last_name": "Otieno",
                "date_of_birth": "2012-01-01",
                "gender": "F",
            },
            format="json",
        )
        force_authenticate(request, user=admin)
        response = StudentViewSet.as_view({"post": "create"})(request)

        self.assertEqual(response.status_code, 201)
        student = Student.objects.get(id=response.data["id"])
        self.assertTrue(student.admission_number.startswith("ADM-"))
        self.assertRegex(student.ulid, ULID_RE)
        self.assertEqual(response.data["ulid"], student.ulid)
        self.assertNotEqual(response.data["ulid"], "01ARZ3NDEKTSV4RRFFQ69G5FAZ")

    def test_student_save_restores_missing_ulid(self):
        student = Student.objects.create(
            admission_number="ULID-001",
            first_name="Brian",
            last_name="Ndegwa",
            date_of_birth=date(2012, 7, 7),
            gender="M",
            is_active=True,
        )
        original_ulid = student.ulid

        Student.objects.filter(pk=student.pk).update(ulid=None)
        student.refresh_from_db()
        self.assertIsNone(student.ulid)

        student.first_name = "Brian Updated"
        student.save(update_fields=["first_name"])
        student.refresh_from_db()

        self.assertRegex(student.ulid, ULID_RE)
        self.assertNotEqual(student.ulid, "")
        self.assertNotEqual(student.ulid, original_ulid)

    def test_finance_student_ref_response_includes_ulid(self):
        accountant = self._create_user("phase4_ulid_finance", "ACCOUNTANT", ["FINANCE"])
        student = Student.objects.create(
            admission_number="ULID-002",
            first_name="Carol",
            last_name="Mwangi",
            date_of_birth=date(2011, 4, 4),
            gender="F",
            is_active=True,
        )

        request = self.factory.get("/api/finance/ref/students/")
        force_authenticate(request, user=accountant)
        response = FinanceStudentRefView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        row = next(item for item in response.data if item["id"] == student.id)
        self.assertEqual(row["ulid"], student.ulid)
        self.assertEqual(row["admission_number"], student.admission_number)

    def test_finance_enrollment_ref_response_includes_student_ulid(self):
        accountant = self._create_user("phase4_ulid_enroll", "ACCOUNTANT", ["FINANCE"])
        year = AcademicYear.objects.create(
            name="2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_active=True,
        )
        term = Term.objects.create(
            academic_year=year,
            name="Term 1",
            start_date=date(2026, 1, 10),
            end_date=date(2026, 4, 10),
            is_active=True,
        )
        school_class = SchoolClass.objects.create(name="Grade 7", stream="A", academic_year=year, is_active=True)
        student = Student.objects.create(
            admission_number="ULID-003",
            first_name="David",
            last_name="Kamau",
            date_of_birth=date(2011, 5, 5),
            gender="M",
            is_active=True,
        )
        Enrollment.objects.create(
            student=student,
            school_class=school_class,
            term=term,
            status="Active",
            is_active=True,
        )

        request = self.factory.get("/api/finance/ref/enrollments/")
        force_authenticate(request, user=accountant)
        response = FinanceEnrollmentRefView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        row = next(item for item in response.data if item["student"] == student.id)
        self.assertEqual(row["student_ulid"], student.ulid)
        self.assertEqual(row["student_admission_number"], student.admission_number)
