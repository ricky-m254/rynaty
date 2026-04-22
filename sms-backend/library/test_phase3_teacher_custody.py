from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from library.classroom_custody import ensure_staff_library_member
from library.models import CirculationRule, LibraryResource, ResourceCopy, TeacherClassroomLoan
from library.views import (
    IssueResourceView,
    LibraryReportsTeacherCustodyView,
    ReturnResourceView,
)
from parent_portal.teacher_portal_views import (
    TeacherPortalLibraryIssueView,
    TeacherPortalLibraryReturnView,
    TeacherPortalLibraryView,
)
from school.models import (
    AcademicYear,
    Enrollment,
    GradeLevel,
    Role,
    SchoolClass,
    Student,
    Subject,
    TeacherAssignment,
    Term,
    UserProfile,
)


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django_tenants.utils import schema_context

        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="library_phase3_test",
                name="Library Phase 3 Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="library-phase3.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        from django_tenants.utils import schema_context

        self.schema_context = schema_context(self.tenant.schema_name)
        self.schema_context.__enter__()

    def tearDown(self):
        self.schema_context.__exit__(None, None, None)


class TeacherLibraryCustodyPhase3Tests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

        self.teacher_role, _ = Role.objects.get_or_create(name="TEACHER", defaults={"description": "Teacher"})
        self.librarian_role, _ = Role.objects.get_or_create(name="LIBRARIAN", defaults={"description": "Librarian"})

        self.teacher = User.objects.create_user(
            username="teacher_phase3",
            password="pass1234",
            first_name="Agnes",
            last_name="Kamau",
            email="teacher_phase3@example.com",
        )
        UserProfile.objects.create(user=self.teacher, role=self.teacher_role)

        self.librarian = User.objects.create_user(
            username="librarian_phase3",
            password="pass1234",
            first_name="Joyce",
            last_name="Wangari",
            email="librarian_phase3@example.com",
        )
        UserProfile.objects.create(user=self.librarian, role=self.librarian_role)

        self.year = AcademicYear.objects.create(
            name="2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_active=True,
            is_current=True,
        )
        self.term = Term.objects.create(
            academic_year=self.year,
            name="Term 1",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 30),
            is_active=True,
            is_current=True,
        )
        self.grade = GradeLevel.objects.create(name="Grade 7", order=7, is_active=True)
        self.class_section = SchoolClass.objects.create(
            name="Grade 7",
            stream="Blue",
            academic_year=self.year,
            grade_level=self.grade,
            section_name="Blue",
            is_active=True,
        )
        self.subject = Subject.objects.create(name="Mathematics", code="MAT", is_active=True)
        TeacherAssignment.objects.create(
            teacher=self.teacher,
            subject=self.subject,
            class_section=self.class_section,
            academic_year=self.year,
            term=self.term,
            is_active=True,
        )

        self.student = Student.objects.create(
            first_name="Nina",
            last_name="Otieno",
            date_of_birth=date(2013, 6, 1),
            admission_number="ADM-P3-001",
            gender="F",
            is_active=True,
        )
        Enrollment.objects.create(
            student=self.student,
            school_class=self.class_section,
            term=self.term,
            status="Active",
            is_active=True,
        )
        self.other_student = Student.objects.create(
            first_name="Mark",
            last_name="Were",
            date_of_birth=date(2013, 7, 1),
            admission_number="ADM-P3-002",
            gender="M",
            is_active=True,
        )

        self.resource = LibraryResource.objects.create(resource_type="Book", title="Integrated Science")
        self.copy = ResourceCopy.objects.create(
            resource=self.resource,
            accession_number="ACC-PHASE3-001",
            status="Available",
            is_active=True,
        )
        CirculationRule.objects.create(
            member_type="Staff",
            resource_type="Book",
            max_items=10,
            loan_period_days=21,
            max_renewals=2,
            fine_per_day="5.00",
        )

    def _issue_copy_to_teacher(self):
        teacher_member = ensure_staff_library_member(self.teacher)
        request = self.factory.post(
            "/api/library/circulation/issue/",
            {"member": teacher_member.id, "copy": self.copy.id},
            format="json",
        )
        force_authenticate(request, user=self.librarian)
        response = IssueResourceView.as_view()(request)
        self.assertEqual(response.status_code, 201)
        return teacher_member, response.data["id"]

    def test_teacher_portal_lists_teacher_custody_and_assigned_students(self):
        self._issue_copy_to_teacher()

        request = self.factory.get("/api/teacher-portal/resources/library/")
        force_authenticate(request, user=self.teacher)
        response = TeacherPortalLibraryView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"]["teacher_custody_count"], 1)
        self.assertEqual(len(response.data["held_books"]), 1)
        self.assertEqual(response.data["held_books"][0]["copy_accession_number"], "ACC-PHASE3-001")
        self.assertEqual(response.data["eligible_students"][0]["id"], self.student.id)

    def test_teacher_can_issue_to_assigned_student_and_record_return(self):
        _, teacher_transaction_id = self._issue_copy_to_teacher()

        issue_request = self.factory.post(
            "/api/teacher-portal/resources/library/issue/",
            {
                "copy": self.copy.id,
                "student_id": self.student.id,
                "due_date": (date.today() + timedelta(days=7)).isoformat(),
                "notes": "Class reader set A",
            },
            format="json",
        )
        force_authenticate(issue_request, user=self.teacher)
        issue_response = TeacherPortalLibraryIssueView.as_view()(issue_request)

        self.assertEqual(issue_response.status_code, 201)
        loan_id = issue_response.data["loan"]["id"]
        self.assertEqual(issue_response.data["loan"]["teacher_transaction_id"], teacher_transaction_id)
        self.assertEqual(issue_response.data["loan"]["student_id"], self.student.id)

        dashboard_request = self.factory.get("/api/teacher-portal/resources/library/")
        force_authenticate(dashboard_request, user=self.teacher)
        dashboard_response = TeacherPortalLibraryView.as_view()(dashboard_request)
        self.assertEqual(dashboard_response.data["summary"]["active_student_loans"], 1)
        self.assertEqual(len(dashboard_response.data["held_books"]), 0)

        return_request = self.factory.post(
            "/api/teacher-portal/resources/library/return/",
            {"loan": loan_id, "notes": "Returned during lesson"},
            format="json",
        )
        force_authenticate(return_request, user=self.teacher)
        return_response = TeacherPortalLibraryReturnView.as_view()(return_request)

        self.assertEqual(return_response.status_code, 200)
        self.assertEqual(return_response.data["loan"]["return_destination"], "Teacher")
        self.assertTrue(
            TeacherClassroomLoan.objects.filter(id=loan_id, return_date__isnull=False).exists()
        )

        refresh_request = self.factory.get("/api/teacher-portal/resources/library/")
        force_authenticate(refresh_request, user=self.teacher)
        refresh_response = TeacherPortalLibraryView.as_view()(refresh_request)
        self.assertEqual(refresh_response.data["summary"]["active_student_loans"], 0)
        self.assertEqual(len(refresh_response.data["held_books"]), 1)

    def test_teacher_cannot_issue_to_unassigned_student(self):
        self._issue_copy_to_teacher()

        request = self.factory.post(
            "/api/teacher-portal/resources/library/issue/",
            {"copy": self.copy.id, "student_id": self.other_student.id},
            format="json",
        )
        force_authenticate(request, user=self.teacher)
        response = TeacherPortalLibraryIssueView.as_view()(request)

        self.assertEqual(response.status_code, 403)

    def test_library_return_closes_active_classroom_loan_to_library(self):
        _, teacher_transaction_id = self._issue_copy_to_teacher()

        issue_request = self.factory.post(
            "/api/teacher-portal/resources/library/issue/",
            {"copy": self.copy.id, "student_id": self.student.id},
            format="json",
        )
        force_authenticate(issue_request, user=self.teacher)
        issue_response = TeacherPortalLibraryIssueView.as_view()(issue_request)
        self.assertEqual(issue_response.status_code, 201)
        loan_id = issue_response.data["loan"]["id"]

        return_request = self.factory.post(
            "/api/library/circulation/return/",
            {"transaction": teacher_transaction_id, "condition_at_return": "Good"},
            format="json",
        )
        force_authenticate(return_request, user=self.librarian)
        return_response = ReturnResourceView.as_view()(return_request)

        self.assertEqual(return_response.status_code, 200)
        self.copy.refresh_from_db()
        self.assertEqual(self.copy.status, "Available")
        classroom_loan = TeacherClassroomLoan.objects.get(id=loan_id)
        self.assertEqual(classroom_loan.return_destination, "Library")
        self.assertIsNotNone(classroom_loan.return_date)

    def test_teacher_custody_report_shows_student_holder_chain(self):
        self._issue_copy_to_teacher()

        issue_request = self.factory.post(
            "/api/teacher-portal/resources/library/issue/",
            {"copy": self.copy.id, "student_id": self.student.id},
            format="json",
        )
        force_authenticate(issue_request, user=self.teacher)
        issue_response = TeacherPortalLibraryIssueView.as_view()(issue_request)
        self.assertEqual(issue_response.status_code, 201)

        report_request = self.factory.get("/api/library/reports/teacher-custody/")
        force_authenticate(report_request, user=self.librarian)
        report_response = LibraryReportsTeacherCustodyView.as_view()(report_request)

        self.assertEqual(report_response.status_code, 200)
        self.assertEqual(len(report_response.data), 1)
        report_row = report_response.data[0]
        self.assertEqual(report_row["current_holder"]["holder_type"], "student")
        self.assertEqual(report_row["current_holder"]["student_id"], self.student.id)
        self.assertEqual(report_row["teacher_name"], "Agnes Kamau")
