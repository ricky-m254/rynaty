from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from communication.services import DispatchResult
from clockin.models import PersonRegistry
from school.models import Module, Role, UserProfile

from .identity import ensure_employment_profile, seed_default_onboarding_tasks
from .models import (
    Department,
    Employee,
    EmployeeEmploymentProfile,
    EmployeeQualification,
    EmergencyContact,
    JobApplication,
    JobPosting,
    OnboardingTask,
    Position,
)
from .views import EmployeeViewSet, JobApplicationViewSet, OnboardingChecklistView
from .views import EmployeeEmploymentProfileViewSet, EmployeeQualificationViewSet

User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django_tenants.utils import schema_context

        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="hr_test",
                name="HR Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="hr.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        from django_tenants.utils import schema_context

        self.schema_context = schema_context(self.tenant.schema_name)
        self.schema_context.__enter__()

    def tearDown(self):
        self.schema_context.__exit__(None, None, None)


class HrSession6IdentityBackboneTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="hr_session6", password="pass1234")
        role, _ = Role.objects.get_or_create(
            name="ADMIN",
            defaults={"description": "School Administrator"},
        )
        Role.objects.get_or_create(
            name="TEACHER",
            defaults={"description": "Teaching Staff"},
        )
        UserProfile.objects.create(user=self.user, role=role)
        for key, name in [
            ("HR", "Human Resources"),
            ("ACADEMICS", "Academics"),
            ("STUDENTS", "Students"),
            ("TIMETABLE", "Timetable"),
            ("EXAMINATIONS", "Examinations"),
            ("CURRICULUM", "Curriculum"),
            ("ELEARNING", "E-Learning"),
            ("COMMUNICATION", "Communication"),
        ]:
            Module.objects.get_or_create(key=key, defaults={"name": name})

        self.department = Department.objects.create(name="Academic", code="ACAS6", is_active=True)
        self.position = Position.objects.create(title="Science Teacher", department=self.department, headcount=2, is_active=True)
        Role.objects.get_or_create(
            name="HOD",
            defaults={"description": "Head of Department"},
        )

    def _create_employee(self, **overrides):
        defaults = {
            "employee_id": overrides.pop("employee_id", "EMP-2026-001"),
            "staff_id": overrides.pop("staff_id", "STF-HRTEST-2026-00001"),
            "first_name": overrides.pop("first_name", "Nora"),
            "last_name": overrides.pop("last_name", "Lane"),
            "date_of_birth": overrides.pop("date_of_birth", date(1990, 1, 1)),
            "gender": overrides.pop("gender", "Female"),
            "personal_email": overrides.pop("personal_email", "nora@example.com"),
            "work_email": overrides.pop("work_email", "nora.staff@example.com"),
            "department": overrides.pop("department", self.department),
            "position": overrides.pop("position", self.position),
            "staff_category": overrides.pop("staff_category", "TEACHING"),
            "employment_type": overrides.pop("employment_type", "Full-time"),
            "status": overrides.pop("status", "Active"),
            "onboarding_status": overrides.pop("onboarding_status", "IN_PROGRESS"),
            "account_role_name": overrides.pop("account_role_name", "TEACHER"),
            "join_date": overrides.pop("join_date", date(2026, 7, 1)),
            "notice_period_days": overrides.pop("notice_period_days", 30),
            "is_active": overrides.pop("is_active", True),
        }
        defaults.update(overrides)
        employee = Employee.objects.create(**defaults)
        ensure_employment_profile(employee)
        seed_default_onboarding_tasks(employee, assigned_to=self.user, due_date=employee.join_date)
        return employee

    def _make_employee_ready_for_provisioning(self, employee):
        profile = employee.employment_profile
        profile.kra_pin = "A123456789Z"
        profile.nhif_number = "NHIF-001"
        profile.nssf_number = "NSSF-001"
        profile.save(update_fields=["kra_pin", "nhif_number", "nssf_number"])

        EmergencyContact.objects.create(
            employee=employee,
            name="Janet Lane",
            relationship="Sister",
            phone_primary="0700000001",
            is_primary=True,
            is_active=True,
        )
        EmployeeQualification.objects.create(
            employee=employee,
            qualification_type="Degree",
            title="Bachelor of Education",
            institution="Kenyatta University",
            year_obtained=2015,
            is_primary=True,
            is_active=True,
        )

    def test_employee_create_generates_staff_id_profile_and_inferred_identity_fields(self):
        request = self.factory.post(
            "/api/hr/employees/",
            {
                "first_name": "Jane",
                "last_name": "Doe",
                "date_of_birth": "1990-01-01",
                "gender": "Female",
                "department": self.department.id,
                "position": self.position.id,
                "employment_type": "Full-time",
                "status": "Active",
                "join_date": "2026-01-10",
                "notice_period_days": 30,
                "is_active": True,
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = EmployeeViewSet.as_view({"post": "create"})(request)
        self.assertEqual(response.status_code, 201)

        employee = Employee.objects.get(pk=response.data["id"])
        self.assertRegex(employee.employee_id, r"^EMP-\d{4}-\d{3}$")
        self.assertRegex(employee.staff_id, r"^STF-HRTEST-\d{4}-\d{5}$")
        self.assertEqual(employee.staff_category, "TEACHING")
        self.assertEqual(employee.account_role_name, "TEACHER")
        self.assertEqual(employee.onboarding_status, "PENDING")
        self.assertTrue(EmployeeEmploymentProfile.objects.filter(employee=employee).exists())

    def test_hire_flow_creates_richer_onboarding_shell(self):
        posting = JobPosting.objects.create(
            position=self.position,
            department=self.department,
            title="Biology Teacher",
            description="Teach senior classes",
            requirements="B.Ed and 3 years experience",
            responsibilities="Lesson planning and grading",
            employment_type="Full-time",
            status="Open",
            is_active=True,
        )
        application = JobApplication.objects.create(
            job_posting=posting,
            first_name="Nora",
            last_name="Lane",
            email="nora@example.com",
            phone="0700000999",
            cover_letter="Experienced teacher",
            is_active=True,
        )

        request = self.factory.post(
            f"/api/hr/applications/{application.id}/hire/",
            {
                "join_date": "2026-07-01",
                "gender": "Female",
                "marital_status": "Single",
                "staff_category": "TEACHING",
                "work_email": "nora.staff@example.com",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = JobApplicationViewSet.as_view({"post": "hire"})(request, pk=application.id)
        self.assertEqual(response.status_code, 200)

        employee = Employee.objects.get(pk=response.data["employee_id"])
        self.assertEqual(employee.position_id, self.position.id)
        self.assertEqual(employee.department_id, self.department.id)
        self.assertEqual(employee.personal_email, "nora@example.com")
        self.assertEqual(employee.work_email, "nora.staff@example.com")
        self.assertEqual(employee.staff_category, "TEACHING")
        self.assertEqual(employee.account_role_name, "TEACHER")
        self.assertEqual(employee.onboarding_status, "IN_PROGRESS")
        self.assertTrue(EmployeeEmploymentProfile.objects.filter(employee=employee).exists())

        tasks = list(OnboardingTask.objects.filter(employee=employee, is_active=True).order_by("id"))
        self.assertEqual(len(tasks), 8)
        self.assertEqual({task.task_code for task in tasks}, {
            "profile.personal_details",
            "profile.employment_profile",
            "contacts.emergency_contact",
            "documents.qualifications",
            "biometric.enrollment",
            "access.system_account",
            "orientation.induction",
            "assets.equipment_issuance",
        })
        self.assertTrue(
            OnboardingTask.objects.filter(
                employee=employee,
                task_code="access.system_account",
                blocks_account_provisioning=True,
                is_required=True,
            ).exists()
        )
        self.assertTrue(
            OnboardingTask.objects.filter(
                employee=employee,
                task_code="orientation.induction",
                blocks_account_provisioning=False,
                is_required=True,
            ).exists()
        )

        checklist_request = self.factory.get(f"/api/hr/onboarding/{employee.id}/")
        force_authenticate(checklist_request, user=self.user)
        checklist_response = OnboardingChecklistView.as_view()(checklist_request, employee_id=employee.id)
        self.assertEqual(checklist_response.status_code, 200)
        first_task = checklist_response.data[0]
        self.assertIn("task_code", first_task)
        self.assertIn("is_required", first_task)
        self.assertIn("blocks_account_provisioning", first_task)

    def test_hire_rejects_invalid_staff_category(self):
        posting = JobPosting.objects.create(
            position=self.position,
            department=self.department,
            title="Biology Teacher",
            employment_type="Full-time",
            status="Open",
            is_active=True,
        )
        application = JobApplication.objects.create(
            job_posting=posting,
            first_name="Nora",
            last_name="Lane",
            email="nora@example.com",
            is_active=True,
        )

        request = self.factory.post(
            f"/api/hr/applications/{application.id}/hire/",
            {"staff_category": "not-a-real-category"},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = JobApplicationViewSet.as_view({"post": "hire"})(request, pk=application.id)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "Unsupported staff_category.")
        self.assertFalse(Employee.objects.filter(first_name="Nora", last_name="Lane").exists())

    def test_hire_allows_explicit_role_override(self):
        posting = JobPosting.objects.create(
            position=self.position,
            department=self.department,
            title="Biology Teacher",
            employment_type="Full-time",
            status="Open",
            is_active=True,
        )
        application = JobApplication.objects.create(
            job_posting=posting,
            first_name="Nora",
            last_name="Lane",
            email="nora@example.com",
            is_active=True,
        )

        request = self.factory.post(
            f"/api/hr/applications/{application.id}/hire/",
            {"account_role_name": "HOD"},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = JobApplicationViewSet.as_view({"post": "hire"})(request, pk=application.id)

        self.assertEqual(response.status_code, 200)
        employee = Employee.objects.get(pk=response.data["employee_id"])
        self.assertEqual(employee.account_role_name, "HOD")

    def test_employment_profile_create_updates_existing_shell_and_advances_summary(self):
        employee = self._create_employee()

        request = self.factory.post(
            "/api/hr/employment-profiles/",
            {
                "employee": employee.id,
                "kra_pin": "A123456789Z",
                "nhif_number": "NHIF-001",
                "nssf_number": "NSSF-001",
                "bank_name": "KCB",
                "bank_account_number": "0001234567",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = EmployeeEmploymentProfileViewSet.as_view({"post": "create"})(request)

        self.assertEqual(response.status_code, 200)
        profile = EmployeeEmploymentProfile.objects.get(employee=employee)
        self.assertEqual(profile.kra_pin, "A123456789Z")
        summary_request = self.factory.get(f"/api/hr/employees/{employee.id}/onboarding-summary/")
        force_authenticate(summary_request, user=self.user)
        summary_response = EmployeeViewSet.as_view({"get": "onboarding_summary"})(summary_request, pk=employee.id)
        self.assertTrue(summary_response.data["employment_profile"]["is_complete"])

    def test_qualification_viewset_updates_counts_and_primary_flag(self):
        employee = self._create_employee()

        first_request = self.factory.post(
            "/api/hr/qualifications/",
            {
                "employee": employee.id,
                "qualification_type": "Degree",
                "title": "Bachelor of Education",
                "institution": "KU",
                "year_obtained": 2015,
                "is_primary": True,
            },
            format="json",
        )
        force_authenticate(first_request, user=self.user)
        first_response = EmployeeQualificationViewSet.as_view({"post": "create"})(first_request)
        self.assertEqual(first_response.status_code, 201)

        second_request = self.factory.post(
            "/api/hr/qualifications/",
            {
                "employee": employee.id,
                "qualification_type": "Certificate",
                "title": "CBE Orientation",
                "institution": "KICD",
                "year_obtained": 2024,
                "is_primary": True,
            },
            format="json",
        )
        force_authenticate(second_request, user=self.user)
        second_response = EmployeeQualificationViewSet.as_view({"post": "create"})(second_request)
        self.assertEqual(second_response.status_code, 201)

        qualifications = list(EmployeeQualification.objects.filter(employee=employee, is_active=True).order_by("id"))
        self.assertEqual(len(qualifications), 2)
        self.assertFalse(qualifications[0].is_primary)
        self.assertTrue(qualifications[1].is_primary)

    def test_onboarding_summary_endpoint_reports_backend_blockers(self):
        employee = self._create_employee()

        request = self.factory.get(f"/api/hr/employees/{employee.id}/onboarding-summary/")
        force_authenticate(request, user=self.user)
        response = EmployeeViewSet.as_view({"get": "onboarding_summary"})(request, pk=employee.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["onboarding_status"], "IN_PROGRESS")
        self.assertFalse(response.data["can_provision_account"])
        blocker_codes = {blocker["code"] for blocker in response.data["blockers"]}
        self.assertEqual(
            blocker_codes,
            {
                "employment_profile.incomplete",
                "emergency_contact.missing_primary",
                "qualifications.missing",
                "biometric.missing",
            },
        )
        self.assertEqual(response.data["task_summary"]["blocking_pending"], 4)

    def test_link_biometric_endpoint_creates_registry_and_advances_readiness(self):
        employee = self._create_employee()
        self._make_employee_ready_for_provisioning(employee)

        request = self.factory.post(
            f"/api/hr/employees/{employee.id}/link-biometric/",
            {
                "fingerprint_id": "BIO-1001",
                "card_no": "CARD-1001",
                "dahua_user_id": "DAHUA-1001",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = EmployeeViewSet.as_view({"post": "link_biometric"})(request, pk=employee.id)

        self.assertEqual(response.status_code, 200)
        registry = PersonRegistry.objects.get(employee=employee)
        self.assertEqual(registry.fingerprint_id, "BIO-1001")
        self.assertEqual(registry.person_type, "TEACHER")
        self.assertTrue(response.data["summary"]["biometric"]["is_linked"])
        self.assertTrue(response.data["summary"]["can_provision_account"])
        self.assertEqual(response.data["summary"]["onboarding_status"], "READY_FOR_PROVISIONING")
        biometric_task = OnboardingTask.objects.get(employee=employee, task_code="biometric.enrollment")
        self.assertEqual(biometric_task.status, "Completed")

    def test_link_biometric_blocks_duplicate_identifier(self):
        first_employee = self._create_employee()
        self._make_employee_ready_for_provisioning(first_employee)
        PersonRegistry.objects.create(
            employee=first_employee,
            fingerprint_id="BIO-DUPLICATE",
            card_no="CARD-1",
            dahua_user_id="DUP-1",
            person_type="TEACHER",
            display_name="Nora Lane",
            is_active=True,
        )

        second_employee = self._create_employee(
            employee_id="EMP-2026-002",
            staff_id="STF-HRTEST-2026-00002",
            first_name="Maya",
            last_name="Cole",
            personal_email="maya@example.com",
            work_email="maya.staff@example.com",
        )
        self._make_employee_ready_for_provisioning(second_employee)

        request = self.factory.post(
            f"/api/hr/employees/{second_employee.id}/link-biometric/",
            {"fingerprint_id": "BIO-DUPLICATE"},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = EmployeeViewSet.as_view({"post": "link_biometric"})(request, pk=second_employee.id)

        self.assertEqual(response.status_code, 400)
        self.assertIn("fingerprint_id", response.data)

    def test_provision_account_rejects_when_blockers_remain(self):
        employee = self._create_employee()

        request = self.factory.post(
            f"/api/hr/employees/{employee.id}/provision-account/",
            {},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = EmployeeViewSet.as_view({"post": "provision_account"})(request, pk=employee.id)

        self.assertEqual(response.status_code, 400)
        self.assertIn("blockers", response.data)
        self.assertFalse(User.objects.filter(username__iexact=employee.work_email).exists())

    @patch(
        "hr.provisioning.send_email_placeholder",
        return_value=DispatchResult(status="Failed", provider_id="", failure_reason="SMTP offline"),
    )
    def test_provision_account_creates_user_profile_and_module_baselines(self, mocked_email):
        employee = self._create_employee()
        self._make_employee_ready_for_provisioning(employee)
        PersonRegistry.objects.create(
            employee=employee,
            fingerprint_id="BIO-PROVISION",
            card_no="CARD-PROVISION",
            dahua_user_id="DAHUA-PROVISION",
            person_type="TEACHER",
            display_name="Nora Lane",
            is_active=True,
        )

        request = self.factory.post(
            f"/api/hr/employees/{employee.id}/provision-account/",
            {},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = EmployeeViewSet.as_view({"post": "provision_account"})(request, pk=employee.id)

        self.assertEqual(response.status_code, 200)
        employee.refresh_from_db()
        self.assertIsNotNone(employee.user)
        self.assertIsNotNone(employee.account_provisioned_at)
        self.assertEqual(employee.onboarding_status, "PROVISIONED")
        self.assertEqual(employee.user.username, "nora.staff@example.com")
        self.assertTrue(employee.user.check_password(response.data["temporary_password"]))

        profile = UserProfile.objects.get(user=employee.user)
        self.assertEqual(profile.role.name, "TEACHER")
        self.assertTrue(profile.force_password_change)

        assigned_keys = sorted(employee.user.module_assignments.filter(is_active=True).values_list("module__key", flat=True))
        self.assertEqual(
            assigned_keys,
            sorted(
                [
                    "ACADEMICS",
                    "COMMUNICATION",
                    "CURRICULUM",
                    "ELEARNING",
                    "EXAMINATIONS",
                    "STUDENTS",
                    "TIMETABLE",
                ]
            ),
        )
        self.assertEqual(response.data["module_baseline"]["scope_profile"], "ACADEMIC_STAFF")
        self.assertEqual(response.data["summary"]["onboarding_status"], "PROVISIONED")
        self.assertEqual(response.data["welcome_email"]["status"], "failed")
        self.assertEqual(response.data["welcome_email"]["failure_reason"], "SMTP offline")
        mocked_email.assert_called_once()

        account_task = OnboardingTask.objects.get(employee=employee, task_code="access.system_account")
        self.assertEqual(account_task.status, "Completed")
