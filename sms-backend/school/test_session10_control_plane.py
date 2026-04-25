from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from academics.models import AcademicYear, Term
from clients.models import Domain, Tenant
from school.models import (
    AdmissionSettings,
    GradingScheme,
    InstitutionLifecycleRun,
    InstitutionLifecycleTaskRun,
    InstitutionLifecycleTemplate,
    InstitutionSecurityPolicy,
    Module,
    Role,
    SchoolProfile,
    TenantModule,
    UserProfile,
)
from school.views import (
    ControlPlaneSummaryView,
    LifecycleRunCompleteView,
    LifecycleRunListCreateView,
    LifecycleRunStartView,
    LifecycleTaskCompleteView,
    LifecycleTaskWaiveView,
    LifecycleTemplateListView,
    SchoolProfileView,
    SecurityPolicyView,
    SessionTimeoutSettingsView,
)


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django_tenants.utils import schema_context

        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="school_session10",
                name="Session 10 Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="session10.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        from django_tenants.utils import schema_context

        self.schema_context = schema_context(self.tenant.schema_name)
        self.schema_context.__enter__()

    def tearDown(self):
        self.schema_context.__exit__(None, None, None)

    def ensure_role(self, name, description=""):
        role, _ = Role.objects.get_or_create(name=name, defaults={"description": description})
        return role

    def ensure_module(self, key, name):
        module, _ = Module.objects.get_or_create(key=key, defaults={"name": name, "is_active": True})
        return module


class Session10ControlPlaneTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="session10_admin", password="pass1234")
        role = self.ensure_role("ADMIN", "School Administrator")
        UserProfile.objects.create(user=self.user, role=role)

    def _authenticate(self, request):
        request.tenant = self.tenant
        force_authenticate(request, user=self.user)
        return request

    def _seed_ready_control_plane(self):
        SchoolProfile.objects.create(
            school_name="Ready School",
            timezone="Africa/Nairobi",
            language="en",
            phone="+254711111111",
            currency="KES",
            receipt_prefix="RCT-",
            invoice_prefix="INV-",
            accepted_payment_methods=["Cash", "Bank Transfer"],
            admission_number_prefix="ADM-",
            is_active=True,
        )
        AdmissionSettings.objects.update_or_create(
            pk=1,
            defaults={
                "prefix": "ADM-",
                "year": 2026,
                "sequence": 0,
                "padding": 4,
                "include_year": True,
                "reset_policy": "never",
                "transfer_policy": "new",
                "auto_generate": True,
            },
        )
        year = AcademicYear.objects.create(
            name="2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_active=True,
            is_current=True,
        )
        term = Term.objects.create(
            academic_year=year,
            name="Term 1",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 30),
            is_active=True,
            is_current=True,
        )
        GradingScheme.objects.create(name="Default CBE", is_active=True, is_default=True)
        finance_module = self.ensure_module("FINANCE", "Finance")
        TenantModule.objects.create(module=finance_module, is_enabled=True, sort_order=1)
        InstitutionSecurityPolicy.objects.update_or_create(
            pk=1,
            defaults={
                "mfa_mode": "ADMIN_ONLY",
                "mfa_method": "SMS",
                "updated_by": self.user,
            },
        )
        return year, term

    def _create_run(self, payload):
        request = self._authenticate(
            self.factory.post("/api/settings/lifecycle-runs/", payload, format="json")
        )
        response = LifecycleRunListCreateView.as_view()(request)
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def _start_run(self, run_id):
        request = self._authenticate(
            self.factory.post(f"/api/settings/lifecycle-runs/{run_id}/start/", {}, format="json")
        )
        response = LifecycleRunStartView.as_view()(request, run_id=run_id)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def _complete_task(self, run_id, task_id, notes):
        request = self._authenticate(
            self.factory.post(
                f"/api/settings/lifecycle-runs/{run_id}/tasks/{task_id}/complete/",
                {"notes": notes},
                format="json",
            )
        )
        response = LifecycleTaskCompleteView.as_view()(request, run_id=run_id, task_id=task_id)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_security_policy_endpoint_returns_singleton_policy(self):
        request = self._authenticate(self.factory.get("/api/settings/security-policy/"))

        response = SecurityPolicyView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], 1)
        self.assertEqual(response.data["session_timeout_minutes"], 60)
        self.assertEqual(InstitutionSecurityPolicy.objects.count(), 1)

    def test_security_policy_patch_persists_typed_policy(self):
        request = self._authenticate(
            self.factory.patch(
                "/api/settings/security-policy/",
                {
                    "session_timeout_minutes": 45,
                    "mfa_mode": "admin_only",
                    "mfa_method": "totp",
                    "ip_whitelist_enabled": True,
                    "allowed_ip_ranges": "192.168.1.0/24\n10.0.0.1",
                },
                format="json",
            )
        )

        response = SecurityPolicyView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        policy = InstitutionSecurityPolicy.objects.get(pk=1)
        self.assertEqual(policy.session_timeout_minutes, 45)
        self.assertEqual(policy.mfa_mode, "ADMIN_ONLY")
        self.assertEqual(policy.mfa_method, "TOTP")
        self.assertTrue(policy.ip_whitelist_enabled)
        self.assertEqual(policy.allowed_ip_ranges, ["192.168.1.0/24", "10.0.0.1"])
        self.assertEqual(policy.updated_by, self.user)

    def test_session_timeout_endpoint_returns_timeout_to_authenticated_non_admin(self):
        teacher = User.objects.create_user(username="session10_teacher", password="pass1234")
        role = self.ensure_role("TEACHER", "Teacher")
        UserProfile.objects.create(user=teacher, role=role)
        InstitutionSecurityPolicy.objects.update_or_create(
            pk=1,
            defaults={
                "session_timeout_minutes": 45,
                "updated_by": self.user,
            },
        )

        request = self.factory.get("/api/settings/session-timeout/")
        request.tenant = self.tenant
        force_authenticate(request, user=teacher)

        response = SessionTimeoutSettingsView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["session_timeout_minutes"], 45)
        self.assertEqual(response.data["warning_seconds"], 120)

    def test_school_profile_patch_bridges_legacy_security_config_to_security_policy(self):
        SchoolProfile.objects.create(
            school_name="Bridge School",
            timezone="Africa/Nairobi",
            language="en",
            phone="+254700000000",
            accepted_payment_methods=["Cash"],
            is_active=True,
        )

        request = self._authenticate(
            self.factory.patch(
                "/api/school/profile/",
                {
                    "security_config": {
                        "session_timeout": 30,
                        "lockout_duration": 20,
                        "require_special": True,
                        "password_expire_days": 120,
                        "two_factor_enabled": True,
                        "two_factor_method": "email",
                        "allowed_ips": "203.0.113.10\n203.0.113.11",
                    }
                },
                format="json",
            )
        )

        response = SchoolProfileView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        policy = InstitutionSecurityPolicy.objects.get(pk=1)
        self.assertEqual(policy.session_timeout_minutes, 30)
        self.assertEqual(policy.lockout_duration_minutes, 20)
        self.assertTrue(policy.require_special_characters)
        self.assertEqual(policy.password_expiry_days, 120)
        self.assertEqual(policy.mfa_mode, "ADMIN_ONLY")
        self.assertEqual(policy.mfa_method, "EMAIL")
        self.assertEqual(policy.allowed_ip_ranges, ["203.0.113.10", "203.0.113.11"])

    def test_control_plane_summary_reports_missing_core_blockers(self):
        request = self._authenticate(self.factory.get("/api/settings/control-plane/"))

        response = ControlPlaneSummaryView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["overall_status"], "NOT_READY")
        blocker_codes = {blocker["code"] for blocker in response.data["blockers"]}
        self.assertIn("missing_school_profile", blocker_codes)
        self.assertIn("missing_current_academic_year", blocker_codes)
        self.assertIn("missing_current_term", blocker_codes)
        self.assertIn("missing_grading_scheme", blocker_codes)
        self.assertIn("missing_registered_modules", blocker_codes)

    def test_control_plane_summary_turns_ready_when_core_setup_exists(self):
        self._seed_ready_control_plane()

        request = self._authenticate(self.factory.get("/api/settings/control-plane/"))

        response = ControlPlaneSummaryView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["overall_status"], "READY")
        self.assertEqual(response.data["sections"]["security"]["status"], "READY")
        self.assertEqual(response.data["sections"]["modules"]["status"], "READY")
        self.assertEqual(response.data["sections"]["modules"]["data"]["configured_enabled_modules"], 1)
        self.assertEqual(response.data["sections"]["lifecycle"]["status"], "READY")

    def test_lifecycle_templates_endpoint_seeds_default_templates(self):
        request = self._authenticate(self.factory.get("/api/settings/lifecycle-templates/"))

        response = LifecycleTemplateListView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 3)
        codes = {row["code"] for row in response.data["results"]}
        self.assertEqual(codes, {"TENANT_ONBOARDING", "TERM_START", "YEAR_CLOSE"})
        self.assertTrue(
            InstitutionLifecycleTemplate.objects.filter(code="TENANT_ONBOARDING", task_templates__task_code="IDENTITY_LOCALE_BASELINE").exists()
        )

    def test_lifecycle_run_create_builds_ordered_task_runs(self):
        request = self._authenticate(
            self.factory.post(
                "/api/settings/lifecycle-runs/",
                {"template_code": "TENANT_ONBOARDING"},
                format="json",
            )
        )

        response = LifecycleRunListCreateView.as_view()(request)

        self.assertEqual(response.status_code, 201)
        run = InstitutionLifecycleRun.objects.get(pk=response.data["id"])
        task_runs = list(run.task_runs.select_related("template_task").order_by("display_order", "id"))
        self.assertGreater(len(task_runs), 0)
        self.assertEqual(task_runs[0].template_task.task_code, "IDENTITY_LOCALE_BASELINE")
        self.assertEqual(task_runs[-1].template_task.task_code, "READINESS_CONFIRMATION")

    def test_onboarding_run_completion_requires_required_tasks_resolved(self):
        self._seed_ready_control_plane()
        create_request = self._authenticate(
            self.factory.post(
                "/api/settings/lifecycle-runs/",
                {"template_code": "TENANT_ONBOARDING"},
                format="json",
            )
        )
        create_response = LifecycleRunListCreateView.as_view()(create_request)
        run_id = create_response.data["id"]

        start_request = self._authenticate(self.factory.post(f"/api/settings/lifecycle-runs/{run_id}/start/", {}, format="json"))
        LifecycleRunStartView.as_view()(start_request, run_id=run_id)

        complete_request = self._authenticate(
            self.factory.post(f"/api/settings/lifecycle-runs/{run_id}/complete/", {}, format="json")
        )
        complete_response = LifecycleRunCompleteView.as_view()(complete_request, run_id=run_id)

        self.assertEqual(complete_response.status_code, 400)
        self.assertEqual(complete_response.data["code"], "run_incomplete")
        self.assertIn("pending_task_titles", complete_response.data["details"])

    def test_term_start_task_blocks_when_target_term_mismatches_target_year(self):
        current_year, _current_term = self._seed_ready_control_plane()
        next_year = AcademicYear.objects.create(
            name="2027",
            start_date=date(2027, 1, 1),
            end_date=date(2027, 12, 31),
            is_active=True,
            is_current=False,
        )
        create_request = self._authenticate(
            self.factory.post(
                "/api/settings/lifecycle-runs/",
                {
                    "template_code": "TERM_START",
                    "target_academic_year": next_year.id,
                    "target_term": Term.objects.get(is_current=True).id,
                },
                format="json",
            )
        )
        create_response = LifecycleRunListCreateView.as_view()(create_request)
        run_id = create_response.data["id"]
        run = InstitutionLifecycleRun.objects.get(pk=run_id)
        alignment_task = run.task_runs.select_related("template_task").get(template_task__task_code="TARGET_ALIGNMENT")

        start_request = self._authenticate(self.factory.post(f"/api/settings/lifecycle-runs/{run_id}/start/", {}, format="json"))
        LifecycleRunStartView.as_view()(start_request, run_id=run_id)

        task_request = self._authenticate(
            self.factory.post(
                f"/api/settings/lifecycle-runs/{run_id}/tasks/{alignment_task.id}/complete/",
                {"notes": "Attempt alignment"},
                format="json",
            )
        )
        task_response = LifecycleTaskCompleteView.as_view()(task_request, run_id=run_id, task_id=alignment_task.id)

        self.assertEqual(task_response.status_code, 400)
        self.assertEqual(task_response.data["code"], "task_blocked")
        self.assertTrue(any(blocker["code"] == "target_term_year_mismatch" for blocker in task_response.data["blockers"]))
        run.refresh_from_db()
        self.assertEqual(run.status, "BLOCKED")
        self.assertEqual(current_year.name, "2026")

    def test_term_start_run_completion_switches_current_context_and_records_evidence(self):
        current_year, current_term = self._seed_ready_control_plane()
        next_year = AcademicYear.objects.create(
            name="2027",
            start_date=date(2027, 1, 1),
            end_date=date(2027, 12, 31),
            is_active=False,
            is_current=False,
        )
        next_term = Term.objects.create(
            academic_year=next_year,
            name="Term 1",
            start_date=date(2027, 1, 5),
            end_date=date(2027, 4, 30),
            is_active=False,
            is_current=False,
        )
        create_response = self._create_run(
            {
                "template_code": "TERM_START",
                "target_academic_year": next_year.id,
                "target_term": next_term.id,
            }
        )
        run_id = create_response["id"]
        self._start_run(run_id)

        run = InstitutionLifecycleRun.objects.get(pk=run_id)
        for task_run in run.task_runs.select_related("template_task").order_by("display_order", "id"):
            self._complete_task(run_id, task_run.id, f"Completed {task_run.template_task.task_code.lower()}")

        complete_request = self._authenticate(
            self.factory.post(f"/api/settings/lifecycle-runs/{run_id}/complete/", {}, format="json")
        )
        complete_response = LifecycleRunCompleteView.as_view()(complete_request, run_id=run_id)

        self.assertEqual(complete_response.status_code, 200, complete_response.data)
        current_year.refresh_from_db()
        current_term.refresh_from_db()
        next_year.refresh_from_db()
        next_term.refresh_from_db()
        self.assertFalse(current_year.is_current)
        self.assertFalse(current_term.is_current)
        self.assertTrue(next_year.is_current)
        self.assertTrue(next_year.is_active)
        self.assertTrue(next_term.is_current)
        self.assertTrue(next_term.is_active)
        self.assertEqual(complete_response.data["metadata"]["last_execution_effect"]["hook"], "TERM_START")
        self.assertEqual(
            complete_response.data["metadata"]["last_execution_effect"]["current_context"]["term"]["id"],
            next_term.id,
        )

        alignment_task = InstitutionLifecycleTaskRun.objects.get(
            run_id=run_id,
            template_task__task_code="TARGET_ALIGNMENT",
        )
        self.assertTrue(alignment_task.evidence["target_alignment"]["matches"])
        finance_task = InstitutionLifecycleTaskRun.objects.get(
            run_id=run_id,
            template_task__task_code="FINANCE_READY",
        )
        self.assertEqual(finance_task.evidence["control_plane_section"]["section"], "finance")

    def test_year_close_run_completion_sets_next_year_current_and_clears_current_term(self):
        current_year, current_term = self._seed_ready_control_plane()
        next_year = AcademicYear.objects.create(
            name="2027",
            start_date=date(2027, 1, 1),
            end_date=date(2027, 12, 31),
            is_active=True,
            is_current=False,
        )
        create_response = self._create_run(
            {
                "template_code": "YEAR_CLOSE",
                "target_academic_year": next_year.id,
            }
        )
        run_id = create_response["id"]
        self._start_run(run_id)

        run = InstitutionLifecycleRun.objects.get(pk=run_id)
        for task_run in run.task_runs.select_related("template_task").order_by("display_order", "id"):
            if task_run.template_task.waivable and task_run.template_task.task_code == "FINANCE_REVIEW":
                waive_request = self._authenticate(
                    self.factory.post(
                        f"/api/settings/lifecycle-runs/{run_id}/tasks/{task_run.id}/waive/",
                        {"notes": "FY2026 finance close readiness reviewed in the finance close workspace; waiver recorded on this year-close run."},
                        format="json",
                    )
                )
                waive_response = LifecycleTaskWaiveView.as_view()(waive_request, run_id=run_id, task_id=task_run.id)
                self.assertEqual(waive_response.status_code, 200, waive_response.data)
                continue
            self._complete_task(run_id, task_run.id, f"Completed {task_run.template_task.task_code.lower()}")

        complete_request = self._authenticate(
            self.factory.post(f"/api/settings/lifecycle-runs/{run_id}/complete/", {}, format="json")
        )
        complete_response = LifecycleRunCompleteView.as_view()(complete_request, run_id=run_id)

        self.assertEqual(complete_response.status_code, 200, complete_response.data)
        current_year.refresh_from_db()
        current_term.refresh_from_db()
        next_year.refresh_from_db()
        self.assertFalse(current_year.is_current)
        self.assertFalse(current_term.is_current)
        self.assertTrue(next_year.is_current)
        self.assertEqual(complete_response.data["metadata"]["last_execution_effect"]["hook"], "YEAR_CLOSE")
        self.assertTrue(complete_response.data["metadata"]["last_execution_effect"]["changes"]["current_term_cleared"])

        waived_task = InstitutionLifecycleTaskRun.objects.get(
            run_id=run_id,
            template_task__task_code="FINANCE_REVIEW",
        )
        self.assertEqual(waived_task.status, "WAIVED")
        self.assertEqual(waived_task.evidence["action"], "waived")
        self.assertEqual(waived_task.evidence["control_plane_section"]["section"], "finance")

        summary_request = self._authenticate(self.factory.get("/api/settings/control-plane/"))
        summary_response = ControlPlaneSummaryView.as_view()(summary_request)
        self.assertEqual(summary_response.status_code, 200)
        self.assertEqual(summary_response.data["overall_status"], "READY")
        self.assertEqual(summary_response.data["sections"]["academics"]["status"], "READY")
        self.assertTrue(summary_response.data["sections"]["academics"]["data"]["awaiting_term_start"])
        blocker_codes = {blocker["code"] for blocker in summary_response.data["sections"]["academics"]["blockers"]}
        self.assertIn("between_terms_after_year_close", blocker_codes)

    def test_year_close_waivable_tasks_require_notes_and_record_waiver(self):
        next_year, _current_term = self._seed_ready_control_plane()
        next_year = AcademicYear.objects.create(
            name="2027",
            start_date=date(2027, 1, 1),
            end_date=date(2027, 12, 31),
            is_active=True,
            is_current=False,
        )
        create_request = self._authenticate(
            self.factory.post(
                "/api/settings/lifecycle-runs/",
                {"template_code": "YEAR_CLOSE", "target_academic_year": next_year.id},
                format="json",
            )
        )
        create_response = LifecycleRunListCreateView.as_view()(create_request)
        run_id = create_response.data["id"]
        run = InstitutionLifecycleRun.objects.get(pk=run_id)
        task_run = run.task_runs.select_related("template_task").get(template_task__task_code="FINANCE_REVIEW")

        blank_waive_request = self._authenticate(
            self.factory.post(f"/api/settings/lifecycle-runs/{run_id}/tasks/{task_run.id}/waive/", {"notes": ""}, format="json")
        )
        blank_waive_response = LifecycleTaskWaiveView.as_view()(blank_waive_request, run_id=run_id, task_id=task_run.id)
        self.assertEqual(blank_waive_response.status_code, 400)
        self.assertEqual(blank_waive_response.data["code"], "waiver_notes_required")

        waive_request = self._authenticate(
            self.factory.post(
                f"/api/settings/lifecycle-runs/{run_id}/tasks/{task_run.id}/waive/",
                {"notes": "FY2026 finance close readiness evidence lives in the finance close workspace, so this pilot run records a waiver here."},
                format="json",
            )
        )
        waive_response = LifecycleTaskWaiveView.as_view()(waive_request, run_id=run_id, task_id=task_run.id)

        self.assertEqual(waive_response.status_code, 200)
        task_run.refresh_from_db()
        self.assertEqual(task_run.status, "WAIVED")
        self.assertEqual(task_run.waived_by, self.user)
