from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import Module, Role, UserModuleAssignment, UserProfile

from .domain.discipline_operations import create_disciplinary_case
from .models import (
    Department,
    Employee,
    EmployeeEmploymentProfile,
    ExitCase,
    ExitClearanceItem,
    Position,
    DisciplinaryCase,
    StaffCareerAction,
    StaffLifecycleEvent,
    StaffTransfer,
)
from .views import (
    DisciplinaryCaseViewSet,
    EmployeeViewSet,
    ExitCaseViewSet,
    ExitClearanceItemViewSet,
    StaffCareerActionViewSet,
    StaffLifecycleEventViewSet,
    StaffTransferViewSet,
)

User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django_tenants.utils import schema_context

        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="hr_test_session9",
                name="HR Session 9 Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="hr-session9.localhost", tenant=cls.tenant, is_primary=True)

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


class HrSession9LifecycleTransferTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="hr_session9", password="pass1234")
        role = self.ensure_role("ADMIN", "School Administrator")
        UserProfile.objects.create(user=self.user, role=role)
        self.ensure_module("HR", "Human Resources")

        self.from_department = Department.objects.create(name="Academics", code="S9A", is_active=True)
        self.to_department = Department.objects.create(name="Administration", code="S9B", is_active=True)
        self.from_position = Position.objects.create(
            title="Teacher",
            department=self.from_department,
            headcount=2,
            is_active=True,
        )
        self.to_position = Position.objects.create(
            title="Senior Teacher",
            department=self.to_department,
            headcount=1,
            is_active=True,
        )
        self.employee = Employee.objects.create(
            employee_id="EMP-S9-001",
            first_name="Amina",
            last_name="Career",
            gender="Female",
            department=self.from_department,
            position=self.from_position,
            staff_category="TEACHING",
            employment_type="Full-time",
            join_date=date(2026, 1, 10),
            status="Active",
            is_active=True,
        )

    def test_transfer_create_appends_requested_lifecycle_event(self):
        request = self.factory.post(
            "/api/hr/transfers/",
            {
                "employee": self.employee.id,
                "transfer_type": "Internal",
                "to_position_ref": self.to_position.id,
                "effective_date": "2026-05-01",
                "reason": "Department restructuring",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = StaffTransferViewSet.as_view({"post": "create"})(request)

        self.assertEqual(response.status_code, 201)
        transfer = StaffTransfer.objects.get(pk=response.data["id"])
        self.assertEqual(transfer.from_department, self.from_department)
        self.assertEqual(transfer.from_position, "Teacher")
        self.assertEqual(transfer.to_department, self.to_department)
        self.assertEqual(transfer.to_position, "Senior Teacher")

        event = StaffLifecycleEvent.objects.get(source_id=transfer.id, event_type="TRANSFER_REQUESTED")
        self.assertEqual(event.employee, self.employee)
        self.assertEqual(event.before_snapshot["department"]["id"], self.from_department.id)
        self.assertEqual(event.after_snapshot["to_department"]["id"], self.to_department.id)
        self.assertEqual(event.recorded_by, self.user)

    def test_transfer_complete_action_updates_employee_and_appends_completed_event(self):
        transfer = StaffTransfer.objects.create(
            employee=self.employee,
            transfer_type="Internal",
            from_department=self.from_department,
            from_position="Teacher",
            to_department=self.to_department,
            to_position="Senior Teacher",
            to_position_ref=self.to_position,
            effective_date=date(2026, 5, 1),
            status="Pending",
            requested_by=self.user,
        )
        StaffLifecycleEvent.objects.create(
            employee=self.employee,
            event_group="TRANSFER",
            event_type="TRANSFER_REQUESTED",
            title="Transfer requested",
            recorded_by=self.user,
            source_model="hr.StaffTransfer",
            source_id=transfer.id,
        )

        request = self.factory.post(f"/api/hr/transfers/{transfer.id}/complete/", {}, format="json")
        force_authenticate(request, user=self.user)

        response = StaffTransferViewSet.as_view({"post": "complete"})(request, pk=transfer.id)

        self.assertEqual(response.status_code, 200)
        transfer.refresh_from_db()
        self.employee.refresh_from_db()
        self.assertEqual(transfer.status, "Completed")
        self.assertEqual(self.employee.department, self.to_department)
        self.assertEqual(self.employee.position, self.to_position)

        completed_event = StaffLifecycleEvent.objects.get(source_id=transfer.id, event_type="TRANSFER_COMPLETED")
        self.assertEqual(completed_event.before_snapshot["department"]["id"], self.from_department.id)
        self.assertEqual(completed_event.after_snapshot["department"]["id"], self.to_department.id)

    def test_transfer_patch_completed_keeps_legacy_ui_path_working(self):
        transfer = StaffTransfer.objects.create(
            employee=self.employee,
            transfer_type="Internal",
            from_department=self.from_department,
            from_position="Teacher",
            to_department=self.to_department,
            to_position_ref=self.to_position,
            effective_date=date(2026, 5, 1),
            status="Pending",
            requested_by=self.user,
        )
        StaffLifecycleEvent.objects.create(
            employee=self.employee,
            event_group="TRANSFER",
            event_type="TRANSFER_REQUESTED",
            title="Transfer requested",
            recorded_by=self.user,
            source_model="hr.StaffTransfer",
            source_id=transfer.id,
        )

        request = self.factory.patch(
            f"/api/hr/transfers/{transfer.id}/",
            {"status": "Completed"},
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = StaffTransferViewSet.as_view({"patch": "partial_update"})(request, pk=transfer.id)

        self.assertEqual(response.status_code, 200)
        transfer.refresh_from_db()
        self.employee.refresh_from_db()
        self.assertEqual(transfer.status, "Completed")
        self.assertEqual(self.employee.position, self.to_position)
        self.assertTrue(
            StaffLifecycleEvent.objects.filter(source_id=transfer.id, event_type="TRANSFER_COMPLETED").exists()
        )


class HrSession9ArchivedVisibilityTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="hr_session9_archive", password="pass1234")
        role = self.ensure_role("ADMIN", "School Administrator")
        UserProfile.objects.create(user=self.user, role=role)
        self.ensure_module("HR", "Human Resources")

        department = Department.objects.create(name="Operations", code="S9C", is_active=True)
        position = Position.objects.create(title="Officer", department=department, headcount=2, is_active=True)

        self.active_employee = Employee.objects.create(
            employee_id="EMP-S9-ACTIVE",
            first_name="Live",
            last_name="Staff",
            gender="Male",
            department=department,
            position=position,
            status="Active",
            is_active=True,
        )
        self.archived_employee = Employee.objects.create(
            employee_id="EMP-S9-ARCH",
            first_name="Archived",
            last_name="Staff",
            gender="Female",
            department=department,
            position=position,
            status="Archived",
            is_active=False,
            archive_reason="Historical record",
        )
        StaffLifecycleEvent.objects.create(
            employee=self.archived_employee,
            event_group="ARCHIVE",
            event_type="ARCHIVED",
            title="Archived",
            recorded_by=self.user,
            source_model="hr.Employee",
            source_id=self.archived_employee.id,
        )

    def test_employee_list_excludes_archived_by_default_but_can_include_them_explicitly(self):
        list_request = self.factory.get("/api/hr/employees/")
        force_authenticate(list_request, user=self.user)
        list_response = EmployeeViewSet.as_view({"get": "list"})(list_request)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(list_response.data[0]["id"], self.active_employee.id)

        retrieve_request = self.factory.get(f"/api/hr/employees/{self.archived_employee.id}/")
        force_authenticate(retrieve_request, user=self.user)
        retrieve_response = EmployeeViewSet.as_view({"get": "retrieve"})(retrieve_request, pk=self.archived_employee.id)
        self.assertEqual(retrieve_response.status_code, 404)

        include_archived_request = self.factory.get(
            f"/api/hr/employees/{self.archived_employee.id}/?include_archived=1"
        )
        force_authenticate(include_archived_request, user=self.user)
        include_archived_response = EmployeeViewSet.as_view({"get": "retrieve"})(
            include_archived_request,
            pk=self.archived_employee.id,
        )
        self.assertEqual(include_archived_response.status_code, 200)
        self.assertEqual(include_archived_response.data["status"], "Archived")

    def test_timeline_and_lifecycle_event_list_can_load_archived_employee_history(self):
        timeline_request = self.factory.get(f"/api/hr/employees/{self.archived_employee.id}/timeline/")
        force_authenticate(timeline_request, user=self.user)
        timeline_response = EmployeeViewSet.as_view({"get": "timeline"})(
            timeline_request,
            pk=self.archived_employee.id,
        )
        self.assertEqual(timeline_response.status_code, 200)
        self.assertEqual(len(timeline_response.data), 1)
        self.assertEqual(timeline_response.data[0]["event_type"], "ARCHIVED")

        lifecycle_request = self.factory.get(
            f"/api/hr/lifecycle-events/?employee={self.archived_employee.id}&event_group=ARCHIVE"
        )
        force_authenticate(lifecycle_request, user=self.user)
        lifecycle_response = StaffLifecycleEventViewSet.as_view({"get": "list"})(lifecycle_request)
        self.assertEqual(lifecycle_response.status_code, 200)
        self.assertEqual(len(lifecycle_response.data), 1)
        self.assertEqual(lifecycle_response.data[0]["employee"], self.archived_employee.id)


class HrSession9TimelineOrderingTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="hr_session9_timeline", password="pass1234")
        role = self.ensure_role("ADMIN", "School Administrator")
        UserProfile.objects.create(user=self.user, role=role)
        self.ensure_module("HR", "Human Resources")

        department = Department.objects.create(name="Academics", code="S9T", is_active=True)
        position = Position.objects.create(title="Teacher", department=department, headcount=2, is_active=True)
        self.employee = Employee.objects.create(
            employee_id="EMP-S9-TIMELINE",
            first_name="Timeline",
            last_name="Staff",
            gender="Female",
            department=department,
            position=position,
            status="Active",
            is_active=True,
        )
        StaffLifecycleEvent.objects.create(
            employee=self.employee,
            event_group="TRANSFER",
            event_type="TRANSFER_COMPLETED",
            title="Transfer completed",
            effective_date=date(2026, 5, 1),
            recorded_by=self.user,
            source_model="hr.StaffTransfer",
            source_id=101,
        )
        StaffLifecycleEvent.objects.create(
            employee=self.employee,
            event_group="CAREER",
            event_type="PROMOTION_EFFECTIVE",
            title="Promotion effective",
            effective_date=date(2026, 6, 15),
            recorded_by=self.user,
            source_model="hr.StaffCareerAction",
            source_id=201,
        )
        StaffLifecycleEvent.objects.create(
            employee=self.employee,
            event_group="EXIT",
            event_type="EXIT_COMPLETED",
            title="Exit completed",
            effective_date=date(2026, 9, 30),
            recorded_by=self.user,
            source_model="hr.ExitCase",
            source_id=301,
        )

    def test_employee_timeline_returns_events_in_descending_effective_order_with_source_references(self):
        request = self.factory.get(f"/api/hr/employees/{self.employee.id}/timeline/")
        force_authenticate(request, user=self.user)

        response = EmployeeViewSet.as_view({"get": "timeline"})(request, pk=self.employee.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["event_type"] for item in response.data],
            ["EXIT_COMPLETED", "PROMOTION_EFFECTIVE", "TRANSFER_COMPLETED"],
        )
        self.assertEqual(response.data[0]["source_model"], "hr.ExitCase")
        self.assertEqual(response.data[0]["source_id"], 301)
        self.assertEqual(response.data[1]["source_model"], "hr.StaffCareerAction")
        self.assertEqual(response.data[1]["source_id"], 201)
        self.assertEqual(response.data[2]["source_model"], "hr.StaffTransfer")
        self.assertEqual(response.data[2]["source_id"], 101)


class HrSession9CareerActionTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="hr_session9_career", password="pass1234")
        role = self.ensure_role("ADMIN", "School Administrator")
        UserProfile.objects.create(user=self.user, role=role)
        self.ensure_module("HR", "Human Resources")

        self.academics = Department.objects.create(name="Academics", code="S9D", is_active=True)
        self.leadership = Department.objects.create(name="Leadership", code="S9E", is_active=True)
        self.teacher = Position.objects.create(title="Teacher", department=self.academics, headcount=5, is_active=True)
        self.senior_teacher = Position.objects.create(
            title="Senior Teacher",
            department=self.academics,
            headcount=2,
            is_active=True,
        )
        self.assistant_teacher = Position.objects.create(
            title="Assistant Teacher",
            department=self.academics,
            headcount=4,
            is_active=True,
        )
        self.acting_deputy = Position.objects.create(
            title="Acting Deputy Principal",
            department=self.leadership,
            headcount=1,
            is_active=True,
        )
        self.employee = Employee.objects.create(
            employee_id="EMP-S9-CAREER",
            first_name="Nia",
            last_name="Growth",
            gender="Female",
            department=self.academics,
            position=self.teacher,
            staff_category="TEACHING",
            employment_type="Full-time",
            join_date=date(2026, 1, 10),
            status="Active",
            is_active=True,
        )
        EmployeeEmploymentProfile.objects.create(
            employee=self.employee,
            position_grade="G1",
            salary_scale="S1",
        )

    def test_apply_promotion_updates_live_assignment_and_profile_and_appends_event(self):
        create_request = self.factory.post(
            "/api/hr/career-actions/",
            {
                "employee": self.employee.id,
                "action_type": "PROMOTION",
                "to_position_ref": self.senior_teacher.id,
                "effective_date": "2026-05-01",
                "target_position_grade": "G2",
                "target_salary_scale": "S2",
                "reason": "Expanded leadership responsibilities",
            },
            format="json",
        )
        force_authenticate(create_request, user=self.user)
        create_response = StaffCareerActionViewSet.as_view({"post": "create"})(create_request)

        self.assertEqual(create_response.status_code, 201)
        action = StaffCareerAction.objects.get(pk=create_response.data["id"])
        self.assertEqual(action.from_department, self.academics)
        self.assertEqual(action.from_position_ref, self.teacher)
        self.assertEqual(action.to_department, self.academics)
        self.assertEqual(action.to_position_title, "Senior Teacher")

        apply_request = self.factory.post(f"/api/hr/career-actions/{action.id}/apply/", {}, format="json")
        force_authenticate(apply_request, user=self.user)
        apply_response = StaffCareerActionViewSet.as_view({"post": "apply"})(apply_request, pk=action.id)

        self.assertEqual(apply_response.status_code, 200)
        action.refresh_from_db()
        self.employee.refresh_from_db()
        profile = EmployeeEmploymentProfile.objects.get(employee=self.employee)
        self.assertEqual(action.status, "EFFECTIVE")
        self.assertEqual(self.employee.position, self.senior_teacher)
        self.assertEqual(profile.position_grade, "G2")
        self.assertEqual(profile.salary_scale, "S2")

        event = StaffLifecycleEvent.objects.get(source_id=action.id, event_type="PROMOTION_EFFECTIVE")
        self.assertEqual(event.before_snapshot["position"]["id"], self.teacher.id)
        self.assertEqual(event.after_snapshot["position"]["id"], self.senior_teacher.id)
        self.assertEqual(event.after_snapshot["employment_profile"]["position_grade"], "G2")

    def test_apply_demotion_updates_assignment_and_appends_demotion_event(self):
        self.employee.position = self.senior_teacher
        self.employee.save(update_fields=["position"])

        create_request = self.factory.post(
            "/api/hr/career-actions/",
            {
                "employee": self.employee.id,
                "action_type": "DEMOTION",
                "to_position_ref": self.assistant_teacher.id,
                "effective_date": "2026-06-01",
                "reason": "Role restructuring",
            },
            format="json",
        )
        force_authenticate(create_request, user=self.user)
        create_response = StaffCareerActionViewSet.as_view({"post": "create"})(create_request)
        self.assertEqual(create_response.status_code, 201)
        action = StaffCareerAction.objects.get(pk=create_response.data["id"])

        apply_request = self.factory.post(f"/api/hr/career-actions/{action.id}/apply/", {}, format="json")
        force_authenticate(apply_request, user=self.user)
        apply_response = StaffCareerActionViewSet.as_view({"post": "apply"})(apply_request, pk=action.id)

        self.assertEqual(apply_response.status_code, 200)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.position, self.assistant_teacher)
        self.assertTrue(
            StaffLifecycleEvent.objects.filter(source_id=action.id, event_type="DEMOTION_EFFECTIVE").exists()
        )

    def test_acting_appointment_start_and_end_restore_assignment_and_append_events(self):
        create_request = self.factory.post(
            "/api/hr/career-actions/",
            {
                "employee": self.employee.id,
                "action_type": "ACTING_APPOINTMENT",
                "to_position_ref": self.acting_deputy.id,
                "effective_date": "2026-07-01",
                "reason": "Covering leave period",
            },
            format="json",
        )
        force_authenticate(create_request, user=self.user)
        create_response = StaffCareerActionViewSet.as_view({"post": "create"})(create_request)
        self.assertEqual(create_response.status_code, 201)
        action = StaffCareerAction.objects.get(pk=create_response.data["id"])

        apply_request = self.factory.post(f"/api/hr/career-actions/{action.id}/apply/", {}, format="json")
        force_authenticate(apply_request, user=self.user)
        apply_response = StaffCareerActionViewSet.as_view({"post": "apply"})(apply_request, pk=action.id)

        self.assertEqual(apply_response.status_code, 200)
        action.refresh_from_db()
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.status, "Acting")
        self.assertEqual(self.employee.department, self.leadership)
        self.assertEqual(self.employee.position, self.acting_deputy)
        self.assertEqual(action.previous_assignment_snapshot["position"]["id"], self.teacher.id)
        self.assertTrue(
            StaffLifecycleEvent.objects.filter(source_id=action.id, event_type="ACTING_APPOINTMENT_STARTED").exists()
        )

        end_request = self.factory.post(
            f"/api/hr/career-actions/{action.id}/end-acting/",
            {"effective_date": "2026-07-31", "notes": "Substantive holder returned."},
            format="json",
        )
        force_authenticate(end_request, user=self.user)
        end_response = StaffCareerActionViewSet.as_view({"post": "end_acting"})(end_request, pk=action.id)

        self.assertEqual(end_response.status_code, 200)
        self.employee.refresh_from_db()
        end_action = StaffCareerAction.objects.get(pk=end_response.data["id"])
        self.assertEqual(end_action.action_type, "ACTING_APPOINTMENT_END")
        self.assertEqual(end_action.parent_action, action)
        self.assertEqual(self.employee.status, "Active")
        self.assertEqual(self.employee.department, self.academics)
        self.assertEqual(self.employee.position, self.teacher)
        self.assertTrue(
            StaffLifecycleEvent.objects.filter(source_id=end_action.id, event_type="ACTING_APPOINTMENT_ENDED").exists()
        )

    def test_end_acting_requires_previous_assignment_snapshot(self):
        action = StaffCareerAction.objects.create(
            employee=self.employee,
            action_type="ACTING_APPOINTMENT",
            from_department=self.academics,
            from_position_ref=self.teacher,
            from_position_title="Teacher",
            to_department=self.leadership,
            to_position_ref=self.acting_deputy,
            to_position_title="Acting Deputy Principal",
            effective_date=date(2026, 8, 1),
            status="EFFECTIVE",
            requested_by=self.user,
            applied_by=self.user,
        )

        request = self.factory.post(f"/api/hr/career-actions/{action.id}/end-acting/", {}, format="json")
        force_authenticate(request, user=self.user)
        response = StaffCareerActionViewSet.as_view({"post": "end_acting"})(request, pk=action.id)

        self.assertEqual(response.status_code, 400)
        self.assertIn("prior assignment snapshot", response.data["error"])


class HrSession9DisciplinaryCaseTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="hr_session9_discipline", password="pass1234")
        role = self.ensure_role("ADMIN", "School Administrator")
        UserProfile.objects.create(user=self.user, role=role)
        self.ensure_module("HR", "Human Resources")

        self.department = Department.objects.create(name="Operations", code="S9F", is_active=True)
        self.position = Position.objects.create(title="Officer", department=self.department, headcount=3, is_active=True)
        self.employee = Employee.objects.create(
            employee_id="EMP-S9-DISC",
            first_name="Kato",
            last_name="Conduct",
            gender="Male",
            department=self.department,
            position=self.position,
            staff_category="OPERATIONS",
            employment_type="Full-time",
            join_date=date(2026, 1, 10),
            status="Active",
            is_active=True,
        )

    def test_create_case_appends_opened_lifecycle_event(self):
        request = self.factory.post(
            "/api/hr/disciplinary-cases/",
            {
                "employee": self.employee.id,
                "category": "Conduct",
                "opened_on": "2026-08-01",
                "incident_date": "2026-07-29",
                "summary": "Breach of reporting protocol",
                "details": "Employee failed to follow the escalation route.",
                "notes": "Investigate supervisor statements.",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = DisciplinaryCaseViewSet.as_view({"post": "create"})(request)

        self.assertEqual(response.status_code, 201)
        disciplinary_case = DisciplinaryCase.objects.get(pk=response.data["id"])
        self.assertTrue(disciplinary_case.case_number.startswith("DISC-"))
        self.assertEqual(disciplinary_case.status, "OPEN")

        event = StaffLifecycleEvent.objects.get(
            source_id=disciplinary_case.id,
            event_type="DISCIPLINARY_CASE_OPENED",
        )
        self.assertEqual(event.employee, self.employee)
        self.assertEqual(event.metadata["case"]["case_number"], disciplinary_case.case_number)

    def test_close_case_with_suspension_updates_employee_and_appends_closed_event(self):
        disciplinary_case = create_disciplinary_case(
            recorded_by=self.user,
            employee=self.employee,
            category="Attendance",
            opened_on=date(2026, 8, 5),
            incident_date=date(2026, 8, 4),
            summary="Repeated missed shift check-ins",
            details="Three unresolved alert incidents within one week.",
            notes="Reviewed with HR.",
        )

        request = self.factory.post(
            f"/api/hr/disciplinary-cases/{disciplinary_case.id}/close/",
            {
                "outcome": "SUSPENSION",
                "effective_date": "2026-08-07",
                "notes": "Seven-day unpaid suspension.",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = DisciplinaryCaseViewSet.as_view({"post": "close"})(request, pk=disciplinary_case.id)

        self.assertEqual(response.status_code, 200)
        disciplinary_case.refresh_from_db()
        self.employee.refresh_from_db()
        self.assertEqual(disciplinary_case.status, "CLOSED")
        self.assertEqual(disciplinary_case.outcome, "SUSPENSION")
        self.assertEqual(self.employee.status, "Suspended")

        event = StaffLifecycleEvent.objects.get(
            source_id=disciplinary_case.id,
            event_type="DISCIPLINARY_CASE_CLOSED",
        )
        self.assertEqual(event.before_snapshot["status"], "Active")
        self.assertEqual(event.after_snapshot["status"], "Suspended")
        self.assertEqual(event.metadata["case"]["outcome"], "SUSPENSION")

    def test_close_case_with_dismissal_routes_into_exit_case(self):
        disciplinary_case = create_disciplinary_case(
            recorded_by=self.user,
            employee=self.employee,
            category="Gross Misconduct",
            opened_on=date(2026, 8, 10),
            incident_date=date(2026, 8, 9),
            summary="Severe policy breach",
            details="Incident escalated for formal review.",
        )

        request = self.factory.post(
            f"/api/hr/disciplinary-cases/{disciplinary_case.id}/close/",
            {
                "outcome": "DISMISSAL",
                "effective_date": "2026-08-12",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = DisciplinaryCaseViewSet.as_view({"post": "close"})(request, pk=disciplinary_case.id)

        self.assertEqual(response.status_code, 200)
        disciplinary_case.refresh_from_db()
        exit_case = ExitCase.objects.get(employee=self.employee, exit_type="DISMISSAL")
        self.assertEqual(disciplinary_case.status, "CLOSED")
        self.assertEqual(disciplinary_case.outcome, "DISMISSAL")
        self.assertEqual(exit_case.status, "CLEARANCE")
        self.assertTrue(
            ExitClearanceItem.objects.filter(exit_case=exit_case, status="PENDING").exists()
        )
        self.assertIn(f"exit case {exit_case.id}", disciplinary_case.notes.lower())
        self.assertEqual(self.employee.status, "Active")


class HrSession9ExitWorkflowTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="hr_session9_exit", password="pass1234")
        role = self.ensure_role("ADMIN", "School Administrator")
        UserProfile.objects.create(user=self.user, role=role)
        self.ensure_module("HR", "Human Resources")

        self.department = Department.objects.create(name="Finance", code="S9G", is_active=True)
        self.position = Position.objects.create(title="Accountant", department=self.department, headcount=2, is_active=True)
        self.employee = Employee.objects.create(
            employee_id="EMP-S9-EXIT",
            first_name="Ayo",
            last_name="Depart",
            gender="Female",
            department=self.department,
            position=self.position,
            staff_category="ADMIN",
            employment_type="Full-time",
            join_date=date(2026, 1, 10),
            status="Active",
            is_active=True,
        )

    def test_exit_completion_requires_clearance_items_to_be_resolved(self):
        create_request = self.factory.post(
            "/api/hr/exits/",
            {
                "employee": self.employee.id,
                "exit_type": "RESIGNATION",
                "notice_date": "2026-08-01",
                "last_working_date": "2026-08-31",
                "effective_date": "2026-08-31",
                "reason": "Personal reasons",
                "notes": "Handover in progress.",
            },
            format="json",
        )
        force_authenticate(create_request, user=self.user)
        create_response = ExitCaseViewSet.as_view({"post": "create"})(create_request)

        self.assertEqual(create_response.status_code, 201)
        exit_case = ExitCase.objects.get(pk=create_response.data["id"])
        self.assertEqual(exit_case.status, "DRAFT")
        self.assertTrue(
            StaffLifecycleEvent.objects.filter(source_id=exit_case.id, event_type="EXIT_CASE_CREATED").exists()
        )

        start_request = self.factory.post(f"/api/hr/exits/{exit_case.id}/start-clearance/", {}, format="json")
        force_authenticate(start_request, user=self.user)
        start_response = ExitCaseViewSet.as_view({"post": "start_clearance"})(start_request, pk=exit_case.id)
        self.assertEqual(start_response.status_code, 200)
        exit_case.refresh_from_db()
        self.assertEqual(exit_case.status, "CLEARANCE")

        item_request = self.factory.post(
            "/api/hr/exit-clearance-items/",
            {
                "exit_case": exit_case.id,
                "label": "Laptop return",
                "department_name": "ICT",
                "status": "PENDING",
                "notes": "Awaiting device inspection.",
                "display_order": 1,
            },
            format="json",
        )
        force_authenticate(item_request, user=self.user)
        item_response = ExitClearanceItemViewSet.as_view({"post": "create"})(item_request)
        self.assertEqual(item_response.status_code, 201)
        item = ExitClearanceItem.objects.get(pk=item_response.data["id"])

        complete_request = self.factory.post(f"/api/hr/exits/{exit_case.id}/complete/", {}, format="json")
        force_authenticate(complete_request, user=self.user)
        blocked_response = ExitCaseViewSet.as_view({"post": "complete"})(complete_request, pk=exit_case.id)
        self.assertEqual(blocked_response.status_code, 400)
        self.assertIn("cleared or waived", blocked_response.data["error"])

        patch_request = self.factory.patch(
            f"/api/hr/exit-clearance-items/{item.id}/",
            {"status": "CLEARED", "notes": "Device returned."},
            format="json",
        )
        force_authenticate(patch_request, user=self.user)
        patch_response = ExitClearanceItemViewSet.as_view({"patch": "partial_update"})(patch_request, pk=item.id)
        self.assertEqual(patch_response.status_code, 200)

        complete_request = self.factory.post(f"/api/hr/exits/{exit_case.id}/complete/", {}, format="json")
        force_authenticate(complete_request, user=self.user)
        complete_response = ExitCaseViewSet.as_view({"post": "complete"})(complete_request, pk=exit_case.id)

        self.assertEqual(complete_response.status_code, 200)
        exit_case.refresh_from_db()
        self.employee.refresh_from_db()
        self.assertEqual(exit_case.status, "COMPLETED")
        self.assertEqual(self.employee.status, "Terminated")
        self.assertEqual(str(self.employee.exit_date), "2026-08-31")
        self.assertEqual(self.employee.exit_reason, "Resignation")
        self.assertTrue(
            StaffLifecycleEvent.objects.filter(source_id=exit_case.id, event_type="CLEARANCE_COMPLETED").exists()
        )
        self.assertTrue(
            StaffLifecycleEvent.objects.filter(source_id=exit_case.id, event_type="EXIT_COMPLETED").exists()
        )

    def test_employee_exit_compatibility_bridge_creates_completed_exit_case(self):
        request = self.factory.post(
            f"/api/hr/employees/{self.employee.id}/exit/",
            {"exit_date": "2026-09-15", "exit_reason": "Resignation", "exit_notes": "Left by request"},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = EmployeeViewSet.as_view({"post": "exit"})(request, pk=self.employee.id)

        self.assertEqual(response.status_code, 200)
        self.employee.refresh_from_db()
        exit_case = ExitCase.objects.get(employee=self.employee)
        self.assertEqual(exit_case.status, "COMPLETED")
        self.assertEqual(self.employee.status, "Terminated")
        self.assertEqual(str(self.employee.exit_date), "2026-09-15")
        self.assertEqual(self.employee.exit_reason, "Resignation")
        self.assertTrue(
            ExitClearanceItem.objects.filter(exit_case=exit_case, status="WAIVED").exists()
        )


class HrSession9ArchiveWorkflowTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="hr_session9_archive_flow", password="pass1234")
        role = self.ensure_role("ADMIN", "School Administrator")
        UserProfile.objects.create(user=self.user, role=role)
        self.hr_module = self.ensure_module("HR", "Human Resources")
        self.finance_module = self.ensure_module("FINANCE", "Finance")

        self.linked_user = User.objects.create_user(username="archivable.staff", password="pass1234")
        self.department = Department.objects.create(name="Administration", code="S9H", is_active=True)
        self.position = Position.objects.create(
            title="Administrator",
            department=self.department,
            headcount=1,
            is_active=True,
        )
        self.employee = Employee.objects.create(
            user=self.linked_user,
            employee_id="EMP-S9-ARCHIVE",
            first_name="Sade",
            last_name="Archive",
            gender="Female",
            department=self.department,
            position=self.position,
            staff_category="ADMIN",
            employment_type="Full-time",
            join_date=date(2026, 1, 10),
            status="Active",
            is_active=True,
        )
        UserModuleAssignment.objects.create(user=self.linked_user, module=self.hr_module, is_active=True)
        UserModuleAssignment.objects.create(user=self.linked_user, module=self.finance_module, is_active=True)

    def test_archive_action_sets_archived_state_and_locks_access(self):
        exit_request = self.factory.post(
            f"/api/hr/employees/{self.employee.id}/exit/",
            {"exit_date": "2026-10-01", "exit_reason": "Resignation", "exit_notes": "Completed handover"},
            format="json",
        )
        force_authenticate(exit_request, user=self.user)
        exit_response = EmployeeViewSet.as_view({"post": "exit"})(exit_request, pk=self.employee.id)
        self.assertEqual(exit_response.status_code, 200)

        archive_request = self.factory.post(
            f"/api/hr/employees/{self.employee.id}/archive/",
            {"archive_reason": "Finalized after clearance and separation."},
            format="json",
        )
        force_authenticate(archive_request, user=self.user)
        archive_response = EmployeeViewSet.as_view({"post": "archive"})(archive_request, pk=self.employee.id)

        self.assertEqual(archive_response.status_code, 200)
        self.employee.refresh_from_db()
        self.linked_user.refresh_from_db()
        exit_case = ExitCase.objects.get(employee=self.employee)
        self.assertEqual(self.employee.status, "Archived")
        self.assertFalse(self.employee.is_active)
        self.assertEqual(self.employee.archived_by, self.user)
        self.assertEqual(self.employee.archive_reason, "Finalized after clearance and separation.")
        self.assertIsNotNone(self.employee.archived_at)
        self.assertFalse(self.linked_user.is_active)
        self.assertEqual(exit_case.status, "ARCHIVED")
        self.assertFalse(
            UserModuleAssignment.objects.filter(user=self.linked_user, is_active=True).exists()
        )
        archived_event = StaffLifecycleEvent.objects.get(
            employee=self.employee,
            event_type="ARCHIVED",
        )
        self.assertEqual(archived_event.event_group, "ARCHIVE")
        self.assertEqual(archived_event.recorded_by, self.user)
        self.assertEqual(
            archived_event.metadata["deactivated_module_assignment_count"],
            2,
        )

    def test_archive_action_refuses_to_run_twice(self):
        self.employee.status = "Archived"
        self.employee.is_active = False
        self.employee.save(update_fields=["status", "is_active"])

        archive_request = self.factory.post(
            f"/api/hr/employees/{self.employee.id}/archive/",
            {"archive_reason": "Second archive should fail."},
            format="json",
        )
        force_authenticate(archive_request, user=self.user)
        archive_response = EmployeeViewSet.as_view({"post": "archive"})(archive_request, pk=self.employee.id)

        self.assertEqual(archive_response.status_code, 400)
        self.assertIn("already archived", archive_response.data["error"].lower())

    def test_archive_action_refuses_employee_with_active_exit_case(self):
        create_request = self.factory.post(
            "/api/hr/exits/",
            {
                "employee": self.employee.id,
                "exit_type": "RESIGNATION",
                "notice_date": "2026-10-01",
                "last_working_date": "2026-10-31",
                "effective_date": "2026-10-31",
                "reason": "Pending separation workflow",
            },
            format="json",
        )
        force_authenticate(create_request, user=self.user)
        create_response = ExitCaseViewSet.as_view({"post": "create"})(create_request)
        self.assertEqual(create_response.status_code, 201)

        archive_request = self.factory.post(
            f"/api/hr/employees/{self.employee.id}/archive/",
            {"archive_reason": "Should not archive while exit is incomplete."},
            format="json",
        )
        force_authenticate(archive_request, user=self.user)
        archive_response = EmployeeViewSet.as_view({"post": "archive"})(archive_request, pk=self.employee.id)

        self.assertEqual(archive_response.status_code, 400)
        self.assertIn("active exit cases", archive_response.data["error"].lower())
