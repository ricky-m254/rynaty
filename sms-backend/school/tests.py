from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Tenant, Domain
from .models import (
    Role, UserProfile, Module, UserModuleAssignment,
    Student, Enrollment, Budget, SchoolProfile, AdmissionApplication
)
from academics.models import AcademicYear, Term, SchoolClass
from communication.models import Message
from reporting.models import AuditLog
from hr.models import Staff
from .views import (
    DashboardRoutingView, DashboardSummaryView,
    FinanceStudentRefView, FinanceEnrollmentRefView, BudgetViewSet, StudentViewSet, AdmissionApplicationViewSet
)
from library.models import LibraryMember
from academics.views import AcademicYearsRefView, TermsRefView, ClassesRefView
from hr.views import StaffRefView
from hr.views import StaffViewSet
from communication.views import CommunicationMessageViewSet
from reporting.views import AuditLogRefView
from reporting.views import AuditLogViewSet


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django_tenants.utils import schema_context
        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="test_school",
                name="Test School",
                paid_until="2030-01-01"
            )
            Domain.objects.create(domain="test.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        # Ensure tests run inside tenant schema
        from django_tenants.utils import schema_context
        self.schema_context = schema_context(self.tenant.schema_name)
        self.schema_context.__enter__()

    def tearDown(self):
        self.schema_context.__exit__(None, None, None)


class DashboardViewsTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="john", password="pass1234")
        role = Role.objects.create(name="ACCOUNTANT", description="Finance Manager")
        UserProfile.objects.create(user=self.user, role=role)

        self.finance = Module.objects.create(key="FINANCE", name="Finance")
        self.students = Module.objects.create(key="STUDENTS", name="Students")
        UserModuleAssignment.objects.create(user=self.user, module=self.finance)

    def test_dashboard_routing_single_module(self):
        request = self.factory.get("/api/dashboard/routing/")
        force_authenticate(request, user=self.user)
        response = DashboardRoutingView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["module_count"], 1)
        self.assertEqual(response.data["target"], "MODULE")
        self.assertEqual(response.data["target_module"], "FINANCE")

    def test_dashboard_summary_includes_finance_block(self):
        request = self.factory.get("/api/dashboard/summary/")
        force_authenticate(request, user=self.user)
        response = DashboardSummaryView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("FINANCE", response.data["modules"])
        self.assertIn("finance", response.data["summary"])


class FinanceReferenceTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="acc", password="pass1234")
        role = Role.objects.create(name="ACCOUNTANT", description="Finance Manager")
        UserProfile.objects.create(user=self.user, role=role)

        finance = Module.objects.create(key="FINANCE", name="Finance")
        UserModuleAssignment.objects.create(user=self.user, module=finance)

        year = AcademicYear.objects.create(
            name="2025-2026", start_date="2025-01-01", end_date="2025-12-31"
        )
        term = Term.objects.create(
            academic_year=year, name="Term 1", start_date="2025-01-01", end_date="2025-04-30"
        )
        school_class = SchoolClass.objects.create(
            name="Grade 1", stream="A", academic_year=year
        )

        self.s1 = Student.objects.create(
            admission_number="ST001",
            first_name="Alice",
            last_name="Zephyr",
            gender="F",
            date_of_birth="2010-01-01"
        )
        self.s2 = Student.objects.create(
            admission_number="ST002",
            first_name="Bob",
            last_name="Yellow",
            gender="M",
            date_of_birth="2010-01-02"
        )
        Enrollment.objects.create(student=self.s1, school_class_id=school_class.id, term_id=term.id)
        Enrollment.objects.create(student=self.s2, school_class_id=school_class.id, term_id=term.id)

        self.term = term
        self.school_class = school_class

    def test_finance_student_ref_pagination(self):
        request = self.factory.get("/api/finance/ref/students/?limit=1&offset=0")
        force_authenticate(request, user=self.user)
        response = FinanceStudentRefView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 1)

    def test_finance_student_ref_ordering(self):
        request = self.factory.get("/api/finance/ref/students/?order_by=last_name&order_dir=desc")
        force_authenticate(request, user=self.user)
        response = FinanceStudentRefView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["last_name"], "Zephyr")

    def test_finance_enrollment_ref_filters(self):
        request = self.factory.get(
            f"/api/finance/ref/enrollments/?class_id={self.school_class.id}&term_id={self.term.id}"
        )
        force_authenticate(request, user=self.user)
        response = FinanceEnrollmentRefView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_finance_student_ref_limit_cap(self):
        extra_students = []
        for i in range(1, 206):
            extra_students.append(Student(
                admission_number=f"STX{i:03d}",
                first_name="Extra",
                last_name=f"Student{i:03d}",
                gender="M",
                date_of_birth="2010-01-03"
            ))
        Student.objects.bulk_create(extra_students)

        request = self.factory.get("/api/finance/ref/students/?limit=500&offset=0")
        force_authenticate(request, user=self.user)
        response = FinanceStudentRefView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 207)
        self.assertEqual(len(response.data["results"]), 200)
        self.assertEqual(response.data["next_offset"], 200)

    def test_finance_enrollment_ref_limit_cap(self):
        extra_enrollments = []
        for i in range(1, 205):
            s = Student.objects.create(
                admission_number=f"STY{i:03d}",
                first_name="Extra",
                last_name=f"Enroll{i:03d}",
                gender="F",
                date_of_birth="2010-01-04"
            )
            extra_enrollments.append(Enrollment(
                student=s,
                school_class_id=self.school_class.id,
                term_id=self.term.id
            ))
        Enrollment.objects.bulk_create(extra_enrollments)

        request = self.factory.get("/api/finance/ref/enrollments/?limit=500&offset=0")
        force_authenticate(request, user=self.user)
        response = FinanceEnrollmentRefView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 206)
        self.assertEqual(len(response.data["results"]), 200)
        self.assertEqual(response.data["next_offset"], 200)


class FinanceBudgetApiTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="budget_user", password="pass1234")
        role = Role.objects.create(name="ACCOUNTANT", description="Finance Manager")
        UserProfile.objects.create(user=self.user, role=role)
        finance = Module.objects.create(key="FINANCE", name="Finance")
        UserModuleAssignment.objects.create(user=self.user, module=finance)

        self.year = AcademicYear.objects.create(
            name="2026-2027", start_date="2026-01-01", end_date="2026-12-31"
        )
        self.term = Term.objects.create(
            academic_year=self.year, name="Term 1", start_date="2026-01-01", end_date="2026-04-30"
        )

    def test_create_and_filter_budgets(self):
        create_request = self.factory.post(
            "/api/finance/budgets/",
            {
                "academic_year": self.year.id,
                "term": self.term.id,
                "monthly_budget": "10000.00",
                "quarterly_budget": "30000.00",
                "annual_budget": "120000.00",
                "categories": [],
                "is_active": True,
            },
            format="json",
        )
        force_authenticate(create_request, user=self.user)
        create_response = BudgetViewSet.as_view({"post": "create"})(create_request)
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(Budget.objects.count(), 1)

        list_request = self.factory.get(
            f"/api/finance/budgets/?academic_year={self.year.id}&term={self.term.id}"
        )
        force_authenticate(list_request, user=self.user)
        list_response = BudgetViewSet.as_view({"get": "list"})(list_request)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data["count"], 1)
        self.assertEqual(len(list_response.data["results"]), 1)


class AdmissionNumberAndLibrarySyncTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="tenant_admin", password="pass1234")
        role = Role.objects.create(name="ADMIN", description="School Administrator")
        UserProfile.objects.create(user=self.user, role=role)
        students_module = Module.objects.create(key="STUDENTS", name="Students")
        UserModuleAssignment.objects.create(user=self.user, module=students_module, is_active=True)

        self.year = AcademicYear.objects.create(
            name="2026-2027", start_date="2026-01-01", end_date="2026-12-31"
        )
        self.term = Term.objects.create(
            academic_year=self.year, name="Term 1", start_date="2026-01-01", end_date="2026-04-30"
        )
        self.school_class = SchoolClass.objects.create(
            name="Grade 7", stream="A", academic_year=self.year
        )

    def test_student_create_auto_assigns_admission_number_and_library_member(self):
        SchoolProfile.objects.create(
            school_name="Auto Mode School",
            admission_number_mode="AUTO",
            admission_number_prefix="ADM-",
            admission_number_padding=4,
            is_active=True,
        )
        request = self.factory.post(
            "/api/students/",
            {
                "first_name": "Auto",
                "last_name": "Student",
                "date_of_birth": "2012-01-01",
                "gender": "M",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = StudentViewSet.as_view({"post": "create"})(request)
        self.assertEqual(response.status_code, 201)
        student = Student.objects.get(id=response.data["id"])
        self.assertTrue(student.admission_number.startswith("ADM-"))
        self.assertTrue(LibraryMember.objects.filter(student=student, is_active=True).exists())

    def test_manual_mode_requires_admission_number(self):
        SchoolProfile.objects.create(
            school_name="Manual Mode School",
            admission_number_mode="MANUAL",
            admission_number_prefix="ADM-",
            admission_number_padding=4,
            is_active=True,
        )
        request = self.factory.post(
            "/api/students/",
            {
                "first_name": "Manual",
                "last_name": "Student",
                "date_of_birth": "2012-01-01",
                "gender": "F",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = StudentViewSet.as_view({"post": "create"})(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn("admission_number", response.data)

    def test_enroll_auto_assigns_admission_number_and_library_member(self):
        SchoolProfile.objects.create(
            school_name="Enrollment School",
            admission_number_mode="AUTO",
            admission_number_prefix="ENR-",
            admission_number_padding=3,
            is_active=True,
        )
        application = AdmissionApplication.objects.create(
            student_first_name="Enroll",
            student_last_name="Candidate",
            student_dob=date(2012, 2, 2),
            student_gender="Male",
            previous_school="",
            applying_for_grade_id=self.school_class.id,
            application_date=date(2026, 1, 5),
            guardian_name="Parent One",
            guardian_phone="0700000000",
            guardian_email="parent@example.com",
            status="Submitted",
        )
        request = self.factory.post(
            f"/api/admissions/applications/{application.id}/enroll/",
            {
                "school_class": self.school_class.id,
                "term": self.term.id,
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = AdmissionApplicationViewSet.as_view({"post": "enroll"})(request, pk=application.id)
        self.assertEqual(response.status_code, 200)
        student = Student.objects.get(id=response.data["student_id"])
        self.assertTrue(student.admission_number.startswith("ENR-"))
        self.assertTrue(LibraryMember.objects.filter(student=student, is_active=True).exists())

class ModuleContractsTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user, _ = User.objects.get_or_create(username="admin")
        self.user.set_password("pass1234")
        self.user.save(update_fields=["password"])
        role, _ = Role.objects.get_or_create(name="ADMIN", defaults={"description": "School Administrator"})
        UserProfile.objects.get_or_create(user=self.user, defaults={"role": role})

        for key, name in [
            ("ACADEMICS", "Academics"),
            ("HR", "Human Resources"),
            ("COMMUNICATION", "Communication"),
            ("REPORTING", "Reporting and Analytics"),
        ]:
            module, _ = Module.objects.get_or_create(key=key, defaults={"name": name})
            UserModuleAssignment.objects.get_or_create(user=self.user, module=module)

        year = AcademicYear.objects.create(
            name="2025-2026", start_date="2025-01-01", end_date="2025-12-31"
        )
        Term.objects.create(
            academic_year=year, name="Term 1", start_date="2025-01-01", end_date="2025-04-30"
        )
        SchoolClass.objects.create(
            name="Grade 1", stream="A", academic_year=year
        )
        Staff.objects.get_or_create(
            employee_id="EMP001",
            defaults={
                "first_name": "Jane",
                "last_name": "Doe",
                "role": "Admin",
                "phone": "123",
            },
        )
        Message.objects.create(
            recipient_type="STUDENT", recipient_id=1, subject="Hello", body="Body"
        )
        AuditLog.objects.create(
            user_id=self.user.id, action="CREATE", model_name="Test", object_id="1", details="ok"
        )

    def test_academics_contracts(self):
        request = self.factory.get("/api/academics/ref/academic-years/")
        force_authenticate(request, user=self.user)
        response = AcademicYearsRefView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 1)

        request = self.factory.get("/api/academics/ref/terms/")
        force_authenticate(request, user=self.user)
        response = TermsRefView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 1)

        request = self.factory.get("/api/academics/ref/classes/")
        force_authenticate(request, user=self.user)
        response = ClassesRefView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 1)

    def test_hr_contracts(self):
        request = self.factory.get("/api/hr/ref/staff/")
        force_authenticate(request, user=self.user)
        response = StaffRefView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 1)

        request = self.factory.get("/api/hr/staff/")
        force_authenticate(request, user=self.user)
        response = StaffViewSet.as_view({"get": "list"})(request)
        self.assertEqual(response.status_code, 200)

    def test_communication_contracts(self):
        request = self.factory.get("/api/communication/messages/")
        force_authenticate(request, user=self.user)
        response = CommunicationMessageViewSet.as_view({"get": "list"})(request)
        self.assertEqual(response.status_code, 200)

    def test_reporting_contracts(self):
        request = self.factory.get("/api/reporting/ref/audit-logs/")
        force_authenticate(request, user=self.user)
        response = AuditLogRefView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 1)

        request = self.factory.get("/api/reporting/audit-logs/")
        force_authenticate(request, user=self.user)
        response = AuditLogViewSet.as_view({"get": "list"})(request)
        self.assertEqual(response.status_code, 200)
