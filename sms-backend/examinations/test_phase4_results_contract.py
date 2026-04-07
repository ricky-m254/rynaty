from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import AcademicYear, Module, Role, SchoolClass, Student, Subject, Term, UserProfile

from .models import ExamPaper, ExamResult, ExamSession
from .views import ExamResultViewSet

User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django_tenants.utils import schema_context

        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="exams_phase4_results",
                name="Exams Phase 4 Results School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="exams-phase4-results.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        from django_tenants.utils import schema_context

        self.schema_context = schema_context(self.tenant.schema_name)
        self.schema_context.__enter__()

    def tearDown(self):
        self.schema_context.__exit__(None, None, None)


class ExaminationsResultsContractTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="exams_phase4_admin", password="pass1234")
        role, _ = Role.objects.get_or_create(
            name="ADMIN",
            defaults={"description": "School Administrator"},
        )
        UserProfile.objects.create(user=self.user, role=role)
        Module.objects.get_or_create(key="EXAMINATIONS", defaults={"name": "Examinations"})

        self.year = AcademicYear.objects.create(
            name="2026-2027",
            start_date="2026-01-01",
            end_date="2026-12-31",
            is_active=True,
            is_current=True,
        )
        self.term = Term.objects.create(
            academic_year=self.year,
            name="Term 1",
            start_date="2026-01-01",
            end_date="2026-04-30",
            billing_date="2026-01-10",
            is_active=True,
            is_current=True,
        )
        self.school_class = SchoolClass.objects.create(
            name="Grade 8",
            stream="North",
            academic_year=self.year,
            is_active=True,
        )
        self.subject = Subject.objects.create(name="Mathematics", code="MATH", is_active=True)
        self.student = Student.objects.create(
            admission_number="EXR-001",
            first_name="Amina",
            last_name="Otieno",
            gender="F",
            date_of_birth="2011-02-01",
            is_active=True,
        )
        self.second_student = Student.objects.create(
            admission_number="EXR-002",
            first_name="Brian",
            last_name="Otieno",
            gender="M",
            date_of_birth="2011-03-01",
            is_active=True,
        )
        self.session_one = ExamSession.objects.create(
            name="Mid-Term 2026",
            term=self.term,
            academic_year=self.year,
            start_date="2026-03-01",
            end_date="2026-03-10",
            status="Completed",
        )
        self.session_two = ExamSession.objects.create(
            name="End-Term 2026",
            term=self.term,
            academic_year=self.year,
            start_date="2026-04-01",
            end_date="2026-04-10",
            status="Completed",
        )
        self.paper_one = ExamPaper.objects.create(
            session=self.session_one,
            subject=self.subject,
            school_class=self.school_class,
            exam_date="2026-03-02",
            start_time="08:00:00",
            end_time="10:00:00",
            total_marks=100,
            pass_mark=40,
        )
        self.paper_two = ExamPaper.objects.create(
            session=self.session_two,
            subject=Subject.objects.create(name="English", code="ENG", is_active=True),
            school_class=self.school_class,
            exam_date="2026-04-02",
            start_time="08:00:00",
            end_time="10:00:00",
            total_marks=100,
            pass_mark=50,
        )

    @staticmethod
    def _items(payload):
        if isinstance(payload, list):
            return payload
        return payload.get("results", [])

    def test_exam_result_create_accepts_absent_records_and_returns_paper_context(self):
        request = self.factory.post(
            "/api/examinations/results/",
            {
                "paper": self.paper_one.id,
                "student": self.student.id,
                "marks_obtained": 88,
                "grade": "A",
                "remarks": "Medical leave",
                "is_absent": True,
            },
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = ExamResultViewSet.as_view({"post": "create"})(request)

        self.assertEqual(response.status_code, 201)
        created = ExamResult.objects.get(pk=response.data["id"])
        self.assertTrue(created.is_absent)
        self.assertIsNone(created.marks_obtained)
        self.assertEqual(created.grade, "")
        self.assertEqual(response.data["paper_name"], "Mathematics - Grade 8 North")
        self.assertEqual(response.data["session_name"], self.session_one.name)
        self.assertEqual(response.data["class_name"], "Grade 8 North")

    def test_exam_result_list_filters_by_session(self):
        in_scope = ExamResult.objects.create(
            paper=self.paper_one,
            student=self.student,
            marks_obtained="78.00",
            grade="B",
            remarks="Good work",
            is_absent=False,
        )
        ExamResult.objects.create(
            paper=self.paper_two,
            student=self.second_student,
            marks_obtained="65.00",
            grade="C",
            remarks="Steady",
            is_absent=False,
        )

        request = self.factory.get(f"/api/examinations/results/?session={self.session_one.id}")
        force_authenticate(request, user=self.user)

        response = ExamResultViewSet.as_view({"get": "list"})(request)

        self.assertEqual(response.status_code, 200)
        rows = self._items(response.data)
        self.assertEqual([row["id"] for row in rows], [in_scope.id])
        self.assertEqual(rows[0]["session"], self.session_one.id)
        self.assertEqual(rows[0]["paper_name"], "Mathematics - Grade 8 North")
