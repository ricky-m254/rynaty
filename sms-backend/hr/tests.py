from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import Module, Role, UserProfile

from .models import (
    AttendanceRecord,
    Department,
    Employee,
    EmployeeEmploymentProfile,
    EmployeeDocument,
    EmergencyContact,
    ExitCase,
    ExitClearanceItem,
    Interview,
    JobApplication,
    JobPosting,
    LeaveBalance,
    LeaveType,
    OnboardingTask,
    PerformanceGoal,
    PerformanceReview,
    PayrollBatch,
    PayrollItem,
    Position,
    SalaryStructure,
    StaffLifecycleEvent,
    TrainingEnrollment,
    TrainingProgram,
)
from .views import (
    AttendanceViewSet,
    DepartmentViewSet,
    EmployeeDocumentViewSet,
    EmployeeViewSet,
    EmergencyContactViewSet,
    HrAnalyticsAttendanceView,
    HrAnalyticsDiversityView,
    HrAnalyticsHeadcountView,
    HrAnalyticsLeaveView,
    HrAnalyticsPayrollCostsView,
    HrAnalyticsTurnoverView,
    InterviewViewSet,
    JobApplicationViewSet,
    JobPostingViewSet,
    LeaveBalanceView,
    LeavePolicyViewSet,
    LeaveRequestViewSet,
    LeaveTypeViewSet,
    OnboardingChecklistView,
    OnboardingTaskViewSet,
    PerformanceGoalViewSet,
    PerformanceReviewViewSet,
    PayrollBatchViewSet,
    PayrollItemViewSet,
    LeaveCalendarView,
    PositionViewSet,
    SalaryComponentViewSet,
    SalaryStructureViewSet,
    TrainingEnrollmentViewSet,
    TrainingProgramViewSet,
)

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

    def ensure_role(self, name, description=""):
        role, _ = Role.objects.get_or_create(
            name=name,
            defaults={"description": description},
        )
        return role

    def ensure_module(self, key, name):
        module, _ = Module.objects.get_or_create(
            key=key,
            defaults={"name": name},
        )
        return module


class HrEmployeeDirectoryTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="hr_admin", password="pass1234")
        role = self.ensure_role("ADMIN", "School Administrator")
        UserProfile.objects.create(user=self.user, role=role)
        self.ensure_module("HR", "Human Resources")

        self.department = Department.objects.create(name="Academic", code="ACAD", is_active=True)
        self.position = Position.objects.create(title="Teacher", department=self.department, headcount=2, is_active=True)

    def test_employee_create_confirm_and_exit(self):
        create_request = self.factory.post(
            "/api/hr/employees/",
            {
                "first_name": "Jane",
                "middle_name": "",
                "last_name": "Doe",
                "date_of_birth": "1990-01-01",
                "gender": "Female",
                "nationality": "Kenyan",
                "national_id": "ID-100",
                "marital_status": "Single",
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
        force_authenticate(create_request, user=self.user)
        create_response = EmployeeViewSet.as_view({"post": "create"})(create_request)
        self.assertEqual(create_response.status_code, 201)
        employee_id = create_response.data["id"]
        self.assertTrue(create_response.data["employee_id"].startswith("EMP-"))

        confirm_request = self.factory.post(
            f"/api/hr/employees/{employee_id}/confirm/",
            {"confirmation_date": "2026-04-01"},
            format="json",
        )
        force_authenticate(confirm_request, user=self.user)
        confirm_response = EmployeeViewSet.as_view({"post": "confirm"})(confirm_request, pk=employee_id)
        self.assertEqual(confirm_response.status_code, 200)

        employee = Employee.objects.get(pk=employee_id)
        self.assertEqual(str(employee.confirmation_date), "2026-04-01")
        self.assertEqual(employee.status, "Active")

        exit_request = self.factory.post(
            f"/api/hr/employees/{employee_id}/exit/",
            {"exit_date": "2026-07-31", "exit_reason": "Resignation", "exit_notes": "Left by request"},
            format="json",
        )
        force_authenticate(exit_request, user=self.user)
        exit_response = EmployeeViewSet.as_view({"post": "exit"})(exit_request, pk=employee_id)
        self.assertEqual(exit_response.status_code, 200)

        employee.refresh_from_db()
        self.assertEqual(employee.status, "Terminated")
        self.assertEqual(str(employee.exit_date), "2026-07-31")
        self.assertEqual(employee.exit_reason, "Resignation")
        exit_case = ExitCase.objects.get(employee=employee)
        self.assertEqual(exit_case.status, "COMPLETED")
        self.assertTrue(ExitClearanceItem.objects.filter(exit_case=exit_case, status="WAIVED").exists())
        self.assertTrue(
            StaffLifecycleEvent.objects.filter(
                employee=employee,
                source_model="hr.ExitCase",
                source_id=exit_case.id,
                event_type="EXIT_COMPLETED",
            ).exists()
        )

    def test_emergency_contacts_primary_enforced_and_expiring_documents(self):
        employee = Employee.objects.create(
            first_name="Jane",
            last_name="Doe",
            date_of_birth="1990-01-01",
            gender="Female",
            join_date="2026-01-10",
            department=self.department,
            position=self.position,
            status="Active",
        )

        first_contact_request = self.factory.post(
            "/api/hr/emergency-contacts/",
            {
                "employee": employee.id,
                "name": "Mary Doe",
                "relationship": "Sister",
                "phone_primary": "0700000001",
                "is_primary": True,
            },
            format="json",
        )
        force_authenticate(first_contact_request, user=self.user)
        first_contact_response = EmergencyContactViewSet.as_view({"post": "create"})(first_contact_request)
        self.assertEqual(first_contact_response.status_code, 201)

        second_contact_request = self.factory.post(
            "/api/hr/emergency-contacts/",
            {
                "employee": employee.id,
                "name": "John Doe",
                "relationship": "Brother",
                "phone_primary": "0700000002",
                "is_primary": True,
            },
            format="json",
        )
        force_authenticate(second_contact_request, user=self.user)
        second_contact_response = EmergencyContactViewSet.as_view({"post": "create"})(second_contact_request)
        self.assertEqual(second_contact_response.status_code, 201)

        primary_contacts = EmergencyContact.objects.filter(employee=employee, is_primary=True, is_active=True)
        self.assertEqual(primary_contacts.count(), 1)

        file_obj = SimpleUploadedFile("contract.pdf", b"pdf-bytes", content_type="application/pdf")
        document = EmployeeDocument.objects.create(
            employee=employee,
            document_type="Contract",
            file=file_obj,
            file_name="contract.pdf",
            expiry_date="2026-02-15",
            uploaded_by=self.user,
            is_active=True,
        )

        expiring_request = self.factory.get(f"/api/hr/documents/expiring/?days=365&employee={employee.id}")
        force_authenticate(expiring_request, user=self.user)
        expiring_response = EmployeeDocumentViewSet.as_view({"get": "expiring"})(expiring_request)
        self.assertEqual(expiring_response.status_code, 200)
        self.assertEqual(len(expiring_response.data), 1)
        self.assertEqual(expiring_response.data[0]["id"], document.id)


class HrDepartmentsPositionsTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="hr_org", password="pass1234")
        role = self.ensure_role("ADMIN", "School Administrator")
        UserProfile.objects.create(user=self.user, role=role)
        self.ensure_module("HR", "Human Resources")

    def test_department_org_chart_and_position_vacancies(self):
        department = Department.objects.create(name="Finance", code="FIN", is_active=True)
        position = Position.objects.create(title="Accountant", department=department, headcount=2, is_active=True)

        Employee.objects.create(
            first_name="Sam",
            last_name="Hill",
            date_of_birth="1989-01-01",
            gender="Male",
            department=department,
            position=position,
            join_date="2026-01-01",
            status="Active",
        )

        org_request = self.factory.get("/api/hr/departments/org-chart/")
        force_authenticate(org_request, user=self.user)
        org_response = DepartmentViewSet.as_view({"get": "org_chart"})(org_request)
        self.assertEqual(org_response.status_code, 200)
        self.assertEqual(len(org_response.data), 1)
        self.assertEqual(org_response.data[0]["employee_count"], 1)

        vacancies_request = self.factory.get(f"/api/hr/positions/{position.id}/vacancies/")
        force_authenticate(vacancies_request, user=self.user)
        vacancies_response = PositionViewSet.as_view({"get": "vacancies"})(vacancies_request, pk=position.id)
        self.assertEqual(vacancies_response.status_code, 200)
        self.assertEqual(vacancies_response.data["headcount"], 2)
        self.assertEqual(vacancies_response.data["filled"], 1)
        self.assertEqual(vacancies_response.data["vacancies"], 1)


class HrAttendanceTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="hr_attendance", password="pass1234")
        role = self.ensure_role("ADMIN", "School Administrator")
        UserProfile.objects.create(user=self.user, role=role)
        self.ensure_module("HR", "Human Resources")

        self.department = Department.objects.create(name="Operations", code="OPS", is_active=True)
        self.position = Position.objects.create(title="Officer", department=self.department, headcount=1, is_active=True)
        self.employee = Employee.objects.create(
            first_name="Ali",
            last_name="Stone",
            date_of_birth="1992-01-01",
            gender="Other",
            department=self.department,
            position=self.position,
            join_date="2026-01-01",
            status="Active",
        )

    def test_clock_in_out_and_summary(self):
        clock_in_request = self.factory.post(
            "/api/hr/attendance/clock-in/",
            {"employee": self.employee.id, "date": "2026-02-01", "clock_in": "08:00:00"},
            format="json",
        )
        force_authenticate(clock_in_request, user=self.user)
        clock_in_response = AttendanceViewSet.as_view({"post": "clock_in"})(clock_in_request)
        self.assertEqual(clock_in_response.status_code, 200)

        clock_out_request = self.factory.post(
            "/api/hr/attendance/clock-out/",
            {"employee": self.employee.id, "date": "2026-02-01", "clock_out": "17:30:00"},
            format="json",
        )
        force_authenticate(clock_out_request, user=self.user)
        clock_out_response = AttendanceViewSet.as_view({"post": "clock_out"})(clock_out_request)
        self.assertEqual(clock_out_response.status_code, 200)

        record = AttendanceRecord.objects.get(employee=self.employee, date="2026-02-01")
        self.assertEqual(str(record.hours_worked), "9.50")
        self.assertEqual(str(record.overtime_hours), "1.50")

        summary_request = self.factory.get("/api/hr/attendance/summary/?month=2&year=2026")
        force_authenticate(summary_request, user=self.user)
        summary_response = AttendanceViewSet.as_view({"get": "summary"})(summary_request)
        self.assertEqual(summary_response.status_code, 200)
        self.assertEqual(summary_response.data["total_records"], 1)
        self.assertEqual(summary_response.data["present_count"], 1)


class HrLeaveManagementTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="hr_leave", password="pass1234")
        role = self.ensure_role("ADMIN", "School Administrator")
        UserProfile.objects.create(user=self.user, role=role)
        self.ensure_module("HR", "Human Resources")

        self.department = Department.objects.create(name="HR", code="HRD", is_active=True)
        self.position = Position.objects.create(title="Officer", department=self.department, headcount=2, is_active=True)
        self.employee = Employee.objects.create(
            employee_id="EMP-LV-001",
            first_name="Liam",
            last_name="Moe",
            date_of_birth="1991-01-01",
            gender="Male",
            department=self.department,
            position=self.position,
            join_date="2026-01-01",
            status="Active",
            employment_type="Full-time",
        )
        self.approver_employee = Employee.objects.create(
            user=self.user,
            employee_id="EMP-LV-002",
            first_name="Admin",
            last_name="User",
            date_of_birth="1988-01-01",
            gender="Female",
            department=self.department,
            position=self.position,
            join_date="2025-01-01",
            status="Active",
            employment_type="Full-time",
        )

    def test_leave_flow_balance_and_calendar(self):
        leave_type_request = self.factory.post(
            "/api/hr/leave-types/",
            {
                "name": "Annual Leave",
                "code": "ANNUAL",
                "is_paid": True,
                "requires_approval": True,
                "requires_document": False,
                "max_days_year": 30,
                "notice_days": 7,
                "color": "#16A34A",
                "is_active": True,
            },
            format="json",
        )
        force_authenticate(leave_type_request, user=self.user)
        leave_type_response = LeaveTypeViewSet.as_view({"post": "create"})(leave_type_request)
        self.assertEqual(leave_type_response.status_code, 201)
        leave_type_id = leave_type_response.data["id"]

        leave_policy_request = self.factory.post(
            "/api/hr/leave-policies/",
            {
                "leave_type": leave_type_id,
                "employment_type": "Full-time",
                "entitlement_days": "24.00",
                "accrual_method": "Annual",
                "carry_forward_max": 5,
                "effective_from": "2026-01-01",
                "is_active": True,
            },
            format="json",
        )
        force_authenticate(leave_policy_request, user=self.user)
        leave_policy_response = LeavePolicyViewSet.as_view({"post": "create"})(leave_policy_request)
        self.assertEqual(leave_policy_response.status_code, 201)

        leave_request_payload = {
            "employee": self.employee.id,
            "leave_type": leave_type_id,
            "start_date": "2026-03-02",
            "end_date": "2026-03-06",
            "reason": "Family trip",
        }
        create_leave_request = self.factory.post("/api/hr/leave-requests/", leave_request_payload, format="json")
        force_authenticate(create_leave_request, user=self.user)
        create_leave_response = LeaveRequestViewSet.as_view({"post": "create"})(create_leave_request)
        self.assertEqual(create_leave_response.status_code, 201)
        leave_request_id = create_leave_response.data["id"]
        self.assertEqual(create_leave_response.data["days_requested"], "5.00")

        balance_request = self.factory.get(f"/api/hr/leave-balance/{self.employee.id}/?year=2026")
        force_authenticate(balance_request, user=self.user)
        balance_response = LeaveBalanceView.as_view()(balance_request, employee_id=self.employee.id)
        self.assertEqual(balance_response.status_code, 200)
        self.assertEqual(len(balance_response.data), 1)
        self.assertEqual(balance_response.data[0]["pending"], "5.00")
        self.assertEqual(balance_response.data[0]["used"], "0.00")

        approve_request = self.factory.post(f"/api/hr/leave-requests/{leave_request_id}/approve/", {}, format="json")
        force_authenticate(approve_request, user=self.user)
        approve_response = LeaveRequestViewSet.as_view({"post": "approve"})(approve_request, pk=leave_request_id)
        self.assertEqual(approve_response.status_code, 200)

        balance_request = self.factory.get(f"/api/hr/leave-balance/{self.employee.id}/?year=2026")
        force_authenticate(balance_request, user=self.user)
        balance_response = LeaveBalanceView.as_view()(balance_request, employee_id=self.employee.id)
        self.assertEqual(balance_response.status_code, 200)
        self.assertEqual(balance_response.data[0]["pending"], "0.00")
        self.assertEqual(balance_response.data[0]["used"], "5.00")

        calendar_request = self.factory.get("/api/hr/leave-calendar/?start_date=2026-03-01&end_date=2026-03-31")
        force_authenticate(calendar_request, user=self.user)
        calendar_response = LeaveCalendarView.as_view()(calendar_request)
        self.assertEqual(calendar_response.status_code, 200)
        self.assertEqual(len(calendar_response.data), 1)
        self.assertEqual(calendar_response.data[0]["status"], "Approved")


class HrPayrollTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="hr_payroll", password="pass1234")
        role = self.ensure_role("ADMIN", "School Administrator")
        UserProfile.objects.create(user=self.user, role=role)
        self.ensure_module("HR", "Human Resources")

        self.department = Department.objects.create(name="Finance", code="FIN", is_active=True)
        self.position = Position.objects.create(title="Officer", department=self.department, headcount=5, is_active=True)
        self.employee = Employee.objects.create(
            employee_id="EMP-PR-001",
            first_name="Pia",
            last_name="Ray",
            date_of_birth="1990-01-01",
            gender="Female",
            department=self.department,
            position=self.position,
            staff_category="ADMIN",
            join_date="2026-01-01",
            status="Active",
            employment_type="Full-time",
        )
        EmployeeEmploymentProfile.objects.create(
            employee=self.employee,
            kra_pin="A123456789Z",
            nssf_number="NSSF-PR-001",
            nhif_number="SHIF-PR-001",
        )

    def test_payroll_process_approve_bankfile_and_payslip_email(self):
        create_structure_request = self.factory.post(
            "/api/hr/salary-structures/",
            {
                "employee": self.employee.id,
                "basic_salary": "1000.00",
                "currency": "USD",
                "pay_frequency": "Monthly",
                "effective_from": "2026-01-01",
            },
            format="json",
        )
        force_authenticate(create_structure_request, user=self.user)
        create_structure_response = SalaryStructureViewSet.as_view({"post": "create"})(create_structure_request)
        self.assertEqual(create_structure_response.status_code, 201)
        structure_id = create_structure_response.data["id"]

        allowance_request = self.factory.post(
            "/api/hr/salary-components/",
            {
                "structure": structure_id,
                "component_type": "Allowance",
                "name": "Housing",
                "amount_type": "Fixed",
                "amount": "100.00",
                "is_taxable": True,
                "is_statutory": False,
            },
            format="json",
        )
        force_authenticate(allowance_request, user=self.user)
        allowance_response = SalaryComponentViewSet.as_view({"post": "create"})(allowance_request)
        self.assertEqual(allowance_response.status_code, 201)

        deduction_request = self.factory.post(
            "/api/hr/salary-components/",
            {
                "structure": structure_id,
                "component_type": "Deduction",
                "name": "Tax",
                "amount_type": "Percentage",
                "amount": "10.00",
                "is_taxable": True,
                "is_statutory": True,
            },
            format="json",
        )
        force_authenticate(deduction_request, user=self.user)
        deduction_response = SalaryComponentViewSet.as_view({"post": "create"})(deduction_request)
        self.assertEqual(deduction_response.status_code, 201)

        for day in range(1, 21):
            AttendanceRecord.objects.create(
                employee=self.employee,
                date=f"2026-04-{day:02d}",
                clock_in="08:00:00",
                clock_out="17:00:00",
                status="Present",
                hours_worked="9.00",
                overtime_hours="1.00",
                recorded_by=self.user,
                is_active=True,
            )

        process_request = self.factory.post(
            "/api/hr/payrolls/process/",
            {"month": 4, "year": 2026, "payment_date": "2026-04-30"},
            format="json",
        )
        force_authenticate(process_request, user=self.user)
        process_response = PayrollBatchViewSet.as_view({"post": "process"})(process_request)
        self.assertEqual(process_response.status_code, 200)
        payroll_id = process_response.data["id"]
        self.assertEqual(process_response.data["status"], "Ready for Finance Approval")
        self.assertEqual(len(process_response.data["items"]), 1)

        payroll = PayrollBatch.objects.get(pk=payroll_id)
        self.assertGreater(payroll.total_gross, 0)
        self.assertGreater(payroll.total_net, 0)

        approve_request = self.factory.post(f"/api/hr/payrolls/{payroll_id}/approve/", {}, format="json")
        force_authenticate(approve_request, user=self.user)
        approve_response = PayrollBatchViewSet.as_view({"post": "approve"})(approve_request, pk=payroll_id)
        self.assertEqual(approve_response.status_code, 200)

        payroll.refresh_from_db()
        self.assertEqual(payroll.status, "Approved")
        self.assertEqual(payroll.approved_by_id, self.user.id)

        bank_request = self.factory.get(f"/api/hr/payrolls/{payroll_id}/bank-file/")
        force_authenticate(bank_request, user=self.user)
        bank_response = PayrollBatchViewSet.as_view({"get": "bank_file"})(bank_request, pk=payroll_id)
        self.assertEqual(bank_response.status_code, 200)
        self.assertIn("employee_id,employee_name,net_salary", bank_response.content.decode())

        tax_request = self.factory.get("/api/hr/payrolls/tax-report/?month=4&year=2026")
        force_authenticate(tax_request, user=self.user)
        tax_response = PayrollBatchViewSet.as_view({"get": "tax_report"})(tax_request)
        self.assertEqual(tax_response.status_code, 200)
        self.assertIn("estimated_tax", tax_response.content.decode())

        payslip = PayrollItem.objects.filter(payroll=payroll, employee=self.employee, is_active=True).first()
        self.assertIsNotNone(payslip)

        payslip_pdf_request = self.factory.get(f"/api/hr/payslips/{payslip.id}/pdf/")
        force_authenticate(payslip_pdf_request, user=self.user)
        payslip_pdf_response = PayrollItemViewSet.as_view({"get": "pdf"})(payslip_pdf_request, pk=payslip.id)
        self.assertEqual(payslip_pdf_response.status_code, 200)

        email_request = self.factory.post("/api/hr/payslips/email/", {"payslip_ids": [payslip.id]}, format="json")
        force_authenticate(email_request, user=self.user)
        email_response = PayrollItemViewSet.as_view({"post": "email"})(email_request)
        self.assertEqual(email_response.status_code, 200)

        payslip.refresh_from_db()
        self.assertIsNotNone(payslip.sent_at)

    def test_approved_payroll_cannot_reprocess(self):
        structure = SalaryStructure.objects.create(
            employee=self.employee,
            basic_salary="1200.00",
            currency="USD",
            pay_frequency="Monthly",
            effective_from="2026-01-01",
            is_active=True,
        )
        self.assertIsNotNone(structure.id)

        process_request = self.factory.post("/api/hr/payrolls/process/", {"month": 5, "year": 2026}, format="json")
        force_authenticate(process_request, user=self.user)
        process_response = PayrollBatchViewSet.as_view({"post": "process"})(process_request)
        self.assertEqual(process_response.status_code, 200)
        payroll_id = process_response.data["id"]

        approve_request = self.factory.post(f"/api/hr/payrolls/{payroll_id}/approve/", {}, format="json")
        force_authenticate(approve_request, user=self.user)
        approve_response = PayrollBatchViewSet.as_view({"post": "approve"})(approve_request, pk=payroll_id)
        self.assertEqual(approve_response.status_code, 200)

        reprocess_request = self.factory.post(f"/api/hr/payrolls/{payroll_id}/reprocess/", {}, format="json")
        force_authenticate(reprocess_request, user=self.user)
        reprocess_response = PayrollBatchViewSet.as_view({"post": "reprocess"})(reprocess_request, pk=payroll_id)
        self.assertEqual(reprocess_response.status_code, 400)


class HrRecruitmentOnboardingTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="hr_recruit", password="pass1234")
        role = self.ensure_role("ADMIN", "School Administrator")
        UserProfile.objects.create(user=self.user, role=role)
        self.ensure_module("HR", "Human Resources")

        self.department = Department.objects.create(name="Academic", code="ACADEM", is_active=True)
        self.position = Position.objects.create(title="Science Teacher", department=self.department, headcount=4, is_active=True)

    def test_recruitment_to_onboarding_flow(self):
        posting_request = self.factory.post(
            "/api/hr/job-postings/",
            {
                "position": self.position.id,
                "department": self.department.id,
                "title": "Biology Teacher",
                "description": "Teach senior classes",
                "requirements": "B.Ed and 3 years experience",
                "responsibilities": "Lesson planning and grading",
                "employment_type": "Full-time",
                "salary_min": "900.00",
                "salary_max": "1200.00",
                "deadline": "2026-06-30",
            },
            format="json",
        )
        force_authenticate(posting_request, user=self.user)
        posting_response = JobPostingViewSet.as_view({"post": "create"})(posting_request)
        self.assertEqual(posting_response.status_code, 201)
        posting_id = posting_response.data["id"]

        publish_request = self.factory.post(f"/api/hr/job-postings/{posting_id}/publish/", {}, format="json")
        force_authenticate(publish_request, user=self.user)
        publish_response = JobPostingViewSet.as_view({"post": "publish"})(publish_request, pk=posting_id)
        self.assertEqual(publish_response.status_code, 200)

        application_request = self.factory.post(
            "/api/hr/applications/",
            {
                "job_posting": posting_id,
                "first_name": "Nora",
                "last_name": "Lane",
                "email": "nora@example.com",
                "phone": "0700000999",
                "cover_letter": "Experienced teacher",
            },
            format="json",
        )
        force_authenticate(application_request, user=self.user)
        application_response = JobApplicationViewSet.as_view({"post": "create"})(application_request)
        self.assertEqual(application_response.status_code, 201)
        application_id = application_response.data["id"]

        shortlist_request = self.factory.post(f"/api/hr/applications/{application_id}/shortlist/", {}, format="json")
        force_authenticate(shortlist_request, user=self.user)
        shortlist_response = JobApplicationViewSet.as_view({"post": "shortlist"})(shortlist_request, pk=application_id)
        self.assertEqual(shortlist_response.status_code, 200)

        interview_request = self.factory.post(
            "/api/hr/interviews/",
            {
                "application": application_id,
                "interview_date": "2026-06-10T10:00:00Z",
                "interview_type": "Video",
                "location": "https://meet.example.com/abc",
                "interviewers": [self.user.id],
            },
            format="json",
        )
        force_authenticate(interview_request, user=self.user)
        interview_response = InterviewViewSet.as_view({"post": "create"})(interview_request)
        self.assertEqual(interview_response.status_code, 201)
        interview_id = interview_response.data["id"]

        feedback_request = self.factory.post(
            f"/api/hr/interviews/{interview_id}/feedback/",
            {"feedback": "Strong communication skills.", "score": "4.50", "status": "Completed"},
            format="json",
        )
        force_authenticate(feedback_request, user=self.user)
        feedback_response = InterviewViewSet.as_view({"post": "feedback"})(feedback_request, pk=interview_id)
        self.assertEqual(feedback_response.status_code, 200)

        hire_request = self.factory.post(
            f"/api/hr/applications/{application_id}/hire/",
            {"join_date": "2026-07-01", "gender": "Female", "marital_status": "Single"},
            format="json",
        )
        force_authenticate(hire_request, user=self.user)
        hire_response = JobApplicationViewSet.as_view({"post": "hire"})(hire_request, pk=application_id)
        self.assertEqual(hire_response.status_code, 200)
        employee_id = hire_response.data["employee_id"]

        employee = Employee.objects.get(pk=employee_id)
        self.assertEqual(employee.position_id, self.position.id)
        self.assertEqual(employee.department_id, self.department.id)

        checklist_request = self.factory.get(f"/api/hr/onboarding/{employee_id}/")
        force_authenticate(checklist_request, user=self.user)
        checklist_response = OnboardingChecklistView.as_view()(checklist_request, employee_id=employee_id)
        self.assertEqual(checklist_response.status_code, 200)
        self.assertGreaterEqual(len(checklist_response.data), 1)

        task_id = checklist_response.data[0]["id"]
        complete_request = self.factory.patch(
            f"/api/hr/onboarding/{task_id}/complete/",
            {"notes": "Completed on day one"},
            format="json",
        )
        force_authenticate(complete_request, user=self.user)
        complete_response = OnboardingTaskViewSet.as_view({"patch": "complete"})(complete_request, pk=task_id)
        self.assertEqual(complete_response.status_code, 200)

        task = OnboardingTask.objects.get(pk=task_id)
        self.assertEqual(task.status, "Completed")
        self.assertIsNotNone(task.completed_at)


class HrPerformanceTrainingAnalyticsTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="hr_perf", password="pass1234")
        role = self.ensure_role("ADMIN", "School Administrator")
        UserProfile.objects.create(user=self.user, role=role)
        self.ensure_module("HR", "Human Resources")

        self.department = Department.objects.create(name="Academics", code="HRA", is_active=True)
        self.position = Position.objects.create(title="Teacher", department=self.department, headcount=10, is_active=True)
        self.employee = Employee.objects.create(
            employee_id="EMP-PF-001",
            first_name="Ava",
            last_name="Mills",
            date_of_birth="1992-01-01",
            gender="Female",
            department=self.department,
            position=self.position,
            join_date="2026-01-01",
            status="Active",
            employment_type="Full-time",
            is_active=True,
        )
        self.reviewer = Employee.objects.create(
            employee_id="EMP-PF-002",
            first_name="Ken",
            last_name="Ray",
            date_of_birth="1985-02-01",
            gender="Male",
            department=self.department,
            position=self.position,
            join_date="2024-01-01",
            status="Active",
            employment_type="Full-time",
            is_active=True,
        )

    def test_performance_training_and_analytics(self):
        goal_request = self.factory.post(
            "/api/hr/performance-goals/",
            {
                "employee": self.employee.id,
                "title": "Improve class average by 8%",
                "description": "Term target",
                "target_date": "2026-09-01",
                "status": "In Progress",
                "weight": "40.00",
            },
            format="json",
        )
        force_authenticate(goal_request, user=self.user)
        goal_response = PerformanceGoalViewSet.as_view({"post": "create"})(goal_request)
        self.assertEqual(goal_response.status_code, 201)
        self.assertTrue(PerformanceGoal.objects.filter(id=goal_response.data["id"]).exists())

        review_request = self.factory.post(
            "/api/hr/performance-reviews/",
            {
                "employee": self.employee.id,
                "reviewer": self.reviewer.id,
                "review_period": "Q3 2026",
                "overall_rating": "4.20",
                "strengths": "Strong lesson delivery",
                "areas_improvement": "Assessment turnaround",
                "status": "Draft",
            },
            format="json",
        )
        force_authenticate(review_request, user=self.user)
        review_response = PerformanceReviewViewSet.as_view({"post": "create"})(review_request)
        self.assertEqual(review_response.status_code, 201)
        review_id = review_response.data["id"]

        submit_request = self.factory.post(f"/api/hr/performance-reviews/{review_id}/submit/", {}, format="json")
        force_authenticate(submit_request, user=self.user)
        submit_response = PerformanceReviewViewSet.as_view({"post": "submit"})(submit_request, pk=review_id)
        self.assertEqual(submit_response.status_code, 200)
        review = PerformanceReview.objects.get(pk=review_id)
        self.assertEqual(review.status, "Submitted")
        self.assertIsNotNone(review.reviewed_at)

        program_request = self.factory.post(
            "/api/hr/training-programs/",
            {
                "title": "STEM Pedagogy Workshop",
                "description": "Instructional coaching",
                "trainer": "Dr. Labs",
                "start_date": "2026-08-01",
                "end_date": "2026-08-03",
                "capacity": 30,
                "cost": "120.00",
            },
            format="json",
        )
        force_authenticate(program_request, user=self.user)
        program_response = TrainingProgramViewSet.as_view({"post": "create"})(program_request)
        self.assertEqual(program_response.status_code, 201)
        program_id = program_response.data["id"]

        enrollment_request = self.factory.post(
            "/api/hr/training-enrollments/",
            {
                "program": program_id,
                "employee": self.employee.id,
                "status": "Completed",
                "completion_date": "2026-08-03",
            },
            format="json",
        )
        force_authenticate(enrollment_request, user=self.user)
        enrollment_response = TrainingEnrollmentViewSet.as_view({"post": "create"})(enrollment_request)
        self.assertEqual(enrollment_response.status_code, 201)
        self.assertTrue(TrainingEnrollment.objects.filter(id=enrollment_response.data["id"]).exists())

        AttendanceRecord.objects.create(
            employee=self.employee,
            date="2026-08-05",
            status="Present",
            clock_in="08:00:00",
            clock_out="17:00:00",
            hours_worked="9.00",
            overtime_hours="1.00",
            recorded_by=self.user,
            is_active=True,
        )

        balance = LeaveBalance.objects.create(
            employee=self.employee,
            leave_type=LeaveType.objects.create(name="Annual", code="ANL-TEST", is_active=True),
            year=2026,
            opening_balance="0.00",
            accrued="24.00",
            used="4.00",
            pending="2.00",
            available="18.00",
            is_active=True,
        )
        self.assertIsNotNone(balance.id)

        PayrollBatch.objects.create(
            month=8,
            year=2026,
            status="Approved",
            total_gross="1500.00",
            total_deductions="300.00",
            total_net="1200.00",
            is_active=True,
        )

        for view_cls in [
            HrAnalyticsHeadcountView,
            HrAnalyticsTurnoverView,
            HrAnalyticsAttendanceView,
            HrAnalyticsLeaveView,
            HrAnalyticsDiversityView,
            HrAnalyticsPayrollCostsView,
        ]:
            req = self.factory.get("/api/hr/analytics/test/")
            force_authenticate(req, user=self.user)
            res = view_cls.as_view()(req)
            self.assertEqual(res.status_code, 200)
