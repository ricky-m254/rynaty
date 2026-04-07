from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import AccountingPeriod, CashbookEntry, JournalEntry, Module, Role, UserModuleAssignment, UserProfile, VoteHead

from .domain.statutory_rules import (
    apply_statutory_rules,
    build_statutory_snapshot,
    calculate_rule_amount,
    ensure_kenya_first_statutory_defaults,
)
from .models import (
    AttendanceRecord,
    Department,
    Employee,
    EmployeeEmploymentProfile,
    PayrollBatch,
    PayrollDisbursement,
    PayrollFinancePosting,
    PayrollItem,
    PayrollItemBreakdown,
    SalaryComponent,
    Position,
    SalaryStructure,
    StatutoryDeductionBand,
    StatutoryDeductionRule,
)
from .serializers import PayrollItemSerializer
from .views import PayrollBatchViewSet, PayrollItemViewSet

User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django_tenants.utils import schema_context

        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="hr_test_session8",
                name="HR Session 8 Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="hr-session8.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        from django_tenants.utils import schema_context

        self.schema_context = schema_context(self.tenant.schema_name)
        self.schema_context.__enter__()

    def tearDown(self):
        self.schema_context.__exit__(None, None, None)


class HrSession8StatutoryRuleTests(TenantTestBase):
    def test_ensure_kenya_first_statutory_defaults_creates_seed_rules_once(self):
        ensure_kenya_first_statutory_defaults()
        ensure_kenya_first_statutory_defaults()

        self.assertEqual(StatutoryDeductionRule.objects.count(), 4)
        self.assertEqual(StatutoryDeductionBand.objects.filter(rule__code="PAYE").count(), 5)
        self.assertEqual(StatutoryDeductionBand.objects.filter(rule__code="NSSF").count(), 2)

        paye = StatutoryDeductionRule.objects.get(code="PAYE")
        self.assertEqual(paye.relief_amount, Decimal("2400.00"))
        self.assertEqual(paye.base_name, "TAXABLE_PAY")

    def test_calculate_band_rule_applies_progressive_tax_and_relief(self):
        ensure_kenya_first_statutory_defaults()
        paye = StatutoryDeductionRule.objects.prefetch_related("bands").get(code="PAYE")

        result = calculate_rule_amount(paye, Decimal("50000.00"))

        self.assertEqual(result["employee_amount"], Decimal("7383.35"))
        self.assertEqual(result["employer_amount"], Decimal("0.00"))
        self.assertEqual(len(result["applied_bands"]), 3)

    def test_percent_rule_honors_minimum_amount(self):
        ensure_kenya_first_statutory_defaults()
        shif = StatutoryDeductionRule.objects.get(code="SHIF")

        result = calculate_rule_amount(shif, Decimal("1000.00"))

        self.assertEqual(result["employee_amount"], Decimal("300.00"))
        self.assertEqual(result["employer_amount"], Decimal("0.00"))

    def test_apply_statutory_rules_summarizes_employee_and_employer_totals(self):
        ensure_kenya_first_statutory_defaults()

        result = apply_statutory_rules(Decimal("50000.00"))

        self.assertEqual(result["employee_total"], Decimal("12508.35"))
        self.assertEqual(result["employer_total"], Decimal("3750.00"))
        self.assertEqual(len(result["results"]), 4)

    def test_build_statutory_snapshot_includes_band_metadata(self):
        ensure_kenya_first_statutory_defaults()
        rules = StatutoryDeductionRule.objects.prefetch_related("bands").order_by("priority", "code")

        snapshot = build_statutory_snapshot(rules)

        self.assertEqual(len(snapshot), 4)
        self.assertEqual(snapshot[0]["code"], "PAYE")
        self.assertEqual(len(snapshot[0]["bands"]), 5)


class HrSession8PayrollSchemaTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.department = Department.objects.create(name="Support", code="SUP8", is_active=True)
        self.position = Position.objects.create(title="Support Officer", department=self.department, headcount=1, is_active=True)
        self.employee = Employee.objects.create(
            employee_id="EMP-S8-001",
            first_name="Sana",
            last_name="Payroll",
            date_of_birth=date(1991, 1, 1),
            gender="Female",
            department=self.department,
            position=self.position,
            staff_category="SUPPORT",
            employment_type="Full-time",
            join_date=date(2026, 1, 1),
            status="Active",
        )

    def test_payroll_batch_supports_session8_fields(self):
        payroll = PayrollBatch.objects.create(
            month=4,
            year=2026,
            status="Ready for Finance Approval",
            exception_count=2,
            blocked_item_count=1,
            workforce_snapshot={"source": "session7"},
            statutory_snapshot={"rules": ["PAYE"]},
            approval_notes="Awaiting finance review",
        )

        self.assertEqual(payroll.status, "Ready for Finance Approval")
        self.assertEqual(payroll.exception_count, 2)
        self.assertEqual(payroll.workforce_snapshot["source"], "session7")

    def test_payroll_support_models_can_store_traceability_records(self):
        payroll = PayrollBatch.objects.create(month=5, year=2026, status="Draft")
        item = PayrollItem.objects.create(
            payroll=payroll,
            employee=self.employee,
            basic_salary="1000.00",
            attendance_deduction_total="25.00",
            statutory_deduction_total="75.00",
            other_deduction_total="10.00",
            employer_statutory_total="40.00",
            total_allowances="100.00",
            total_deductions="110.00",
            gross_salary="1100.00",
            net_salary="990.00",
            net_payable="990.00",
            posting_bucket="SUPPORT_SALARIES",
            is_blocked=True,
            block_reason="Missing KRA PIN",
            calculation_snapshot={"month": 5, "year": 2026},
        )
        PayrollItemBreakdown.objects.create(
            payroll_item=item,
            line_type="STATUTORY_EMPLOYEE",
            code="SHIF",
            name="Social Health Insurance Fund",
            base_amount="1000.00",
            rate="2.75",
            amount="300.00",
            snapshot={"minimum_applied": True},
        )
        PayrollDisbursement.objects.create(
            payroll=payroll,
            method="BANK",
            status="DRAFT",
            total_amount="990.00",
        )
        PayrollFinancePosting.objects.create(
            payroll=payroll,
            posting_stage="ACCRUAL",
            entry_key="payroll-accrual-2026-05",
            status="PENDING",
            vote_head_summary={"SUPPORT_SALARIES": "1100.00"},
        )

        item.refresh_from_db()
        self.assertEqual(item.breakdown_rows.count(), 1)
        self.assertTrue(item.is_blocked)
        self.assertEqual(payroll.disbursements.count(), 1)
        self.assertEqual(payroll.finance_postings.count(), 1)


class HrSession8PayrollProcessingTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="hr_session8_payroll", password="pass1234")
        self.bursar_user = User.objects.create_user(username="session8_bursar", password="pass1234")
        role, _ = Role.objects.get_or_create(
            name="ADMIN",
            defaults={"description": "School Administrator"},
        )
        bursar_role, _ = Role.objects.get_or_create(
            name="BURSAR",
            defaults={"description": "School Bursar"},
        )
        UserProfile.objects.create(user=self.user, role=role)
        UserProfile.objects.create(user=self.bursar_user, role=bursar_role)
        self.hr_module, _ = Module.objects.get_or_create(key="HR", defaults={"name": "Human Resources"})
        self.finance_module, _ = Module.objects.get_or_create(key="FINANCE", defaults={"name": "Finance"})
        UserModuleAssignment.objects.create(user=self.bursar_user, module=self.finance_module, is_active=True)

        self.department = Department.objects.create(name="Teaching", code="TCH8", is_active=True)
        self.position = Position.objects.create(title="Teacher", department=self.department, headcount=3, is_active=True)
        self.employee = Employee.objects.create(
            employee_id="EMP-S8-PROC-001",
            first_name="Tari",
            last_name="Ready",
            date_of_birth=date(1990, 1, 1),
            gender="Female",
            department=self.department,
            position=self.position,
            staff_category="TEACHING",
            employment_type="Full-time",
            join_date=date(2025, 1, 1),
            status="Active",
        )
        EmployeeEmploymentProfile.objects.create(
            employee=self.employee,
            kra_pin="A123456789Z",
            nssf_number="NSSF-S8-001",
            nhif_number="SHIF-S8-001",
        )
        SalaryStructure.objects.create(
            employee=self.employee,
            basic_salary="50000.00",
            currency="KES",
            pay_frequency="Monthly",
            effective_from=date(2026, 1, 1),
            is_active=True,
        )
        for day in range(1, 6):
            AttendanceRecord.objects.create(
                employee=self.employee,
                date=date(2026, 4, day),
                status="Present",
                overtime_hours="1.50" if day == 1 else "0.00",
                is_active=True,
            )

    def _process_payroll(self, *, month=4, year=2026, payment_date="2026-04-30"):
        request = self.factory.post(
            "/api/hr/payrolls/process/",
            {"month": month, "year": year, "payment_date": payment_date},
            format="json",
        )
        force_authenticate(request, user=self.user)
        return PayrollBatchViewSet.as_view({"post": "process"})(request)

    def _finance_approve_and_disburse(self, payroll_id: int):
        finance_request = self.factory.post(
            f"/api/hr/payrolls/{payroll_id}/finance-approve/",
            {"approval_notes": "Finance gate passed"},
            format="json",
        )
        force_authenticate(finance_request, user=self.user)
        finance_response = PayrollBatchViewSet.as_view({"post": "finance_approve"})(finance_request, pk=payroll_id)

        start_request = self.factory.post(
            f"/api/hr/payrolls/{payroll_id}/start-disbursement/",
            {
                "method": "BANK",
                "scheduled_date": "2026-04-30",
                "reference": "BANK-RUN-APR",
                "notes": "Submitted to bank",
            },
            format="json",
        )
        force_authenticate(start_request, user=self.user)
        start_response = PayrollBatchViewSet.as_view({"post": "start_disbursement"})(start_request, pk=payroll_id)

        mark_request = self.factory.post(
            f"/api/hr/payrolls/{payroll_id}/mark-disbursed/",
            {
                "reference": "BANK-RUN-APR-COMPLETE",
                "notes": "Bank confirmed release",
                "disbursed_at": "2026-04-30T10:15:00+03:00",
            },
            format="json",
        )
        force_authenticate(mark_request, user=self.user)
        mark_response = PayrollBatchViewSet.as_view({"post": "mark_disbursed"})(mark_request, pk=payroll_id)
        return finance_response, start_response, mark_response

    def test_process_creates_snapshot_driven_payroll_items_for_clean_employee(self):
        response = self._process_payroll()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "Ready for Finance Approval")
        self.assertEqual(response.data["blocked_item_count"], 0)
        self.assertEqual(len(response.data["items"]), 1)

        payroll = PayrollBatch.objects.get(pk=response.data["id"])
        item = payroll.items.get(employee=self.employee)

        self.assertEqual(item.posting_bucket, "TEACHING_SALARIES")
        self.assertFalse(item.is_blocked)
        self.assertGreater(item.statutory_deduction_total, Decimal("0.00"))
        self.assertGreater(item.net_payable, Decimal("0.00"))
        self.assertEqual(payroll.status, "Ready for Finance Approval")
        self.assertEqual(payroll.workforce_snapshot["results"][0]["employee"], self.employee.id)
        self.assertEqual(payroll.statutory_snapshot["rules"][0]["code"], "PAYE")
        self.assertTrue(item.breakdown_rows.filter(line_type="STATUTORY_EMPLOYEE", code="PAYE").exists())

    def test_process_keeps_batch_in_draft_when_workforce_or_identifier_blockers_exist(self):
        blocked_employee = Employee.objects.create(
            employee_id="EMP-S8-PROC-002",
            first_name="Bora",
            last_name="Blocked",
            date_of_birth=date(1992, 2, 2),
            gender="Male",
            department=self.department,
            position=self.position,
            staff_category="TEACHING",
            employment_type="Full-time",
            join_date=date(2025, 1, 1),
            status="Active",
        )
        SalaryStructure.objects.create(
            employee=blocked_employee,
            basic_salary="42000.00",
            currency="KES",
            pay_frequency="Monthly",
            effective_from=date(2026, 1, 1),
            is_active=True,
        )
        AttendanceRecord.objects.create(
            employee=blocked_employee,
            date=date(2026, 4, 7),
            status="Absent",
            payroll_feed_status="BLOCKED_ALERT",
            is_active=True,
        )

        response = self._process_payroll()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "Draft")
        self.assertEqual(response.data["blocked_item_count"], 1)

        payroll = PayrollBatch.objects.get(pk=response.data["id"])
        blocked_item = payroll.items.get(employee=blocked_employee)
        self.assertTrue(blocked_item.is_blocked)
        self.assertIn("absence alerts", blocked_item.block_reason)
        self.assertIn("KRA PIN", blocked_item.block_reason)
        self.assertEqual(payroll.exception_count, 4)
        self.assertEqual(
            payroll.workforce_snapshot["results"][1]["blocking_reasons"][0],
            "1 day(s) blocked by unresolved absence alerts",
        )

    def test_finance_approve_rejects_batches_with_unresolved_exceptions(self):
        blocked_employee = Employee.objects.create(
            employee_id="EMP-S8-PROC-003",
            first_name="Kito",
            last_name="Exception",
            date_of_birth=date(1993, 3, 3),
            gender="Male",
            department=self.department,
            position=self.position,
            staff_category="",
            employment_type="Full-time",
            join_date=date(2025, 1, 1),
            status="Active",
        )
        SalaryStructure.objects.create(
            employee=blocked_employee,
            basic_salary="42000.00",
            currency="KES",
            pay_frequency="Monthly",
            effective_from=date(2026, 1, 1),
            is_active=True,
        )
        AttendanceRecord.objects.create(
            employee=blocked_employee,
            date=date(2026, 4, 9),
            status="Absent",
            payroll_feed_status="BLOCKED_ALERT",
            is_active=True,
        )

        process_response = self._process_payroll()
        payroll_id = process_response.data["id"]

        exceptions_request = self.factory.get(f"/api/hr/payrolls/{payroll_id}/exceptions/")
        force_authenticate(exceptions_request, user=self.user)
        exceptions_response = PayrollBatchViewSet.as_view({"get": "exceptions"})(exceptions_request, pk=payroll_id)
        self.assertEqual(exceptions_response.status_code, 200)
        self.assertEqual(exceptions_response.data["blocked_item_count"], 1)
        self.assertEqual(exceptions_response.data["missing_bucket_count"], 1)

        request = self.factory.post(
            f"/api/hr/payrolls/{payroll_id}/finance-approve/",
            {"approval_notes": "Finance review"},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = PayrollBatchViewSet.as_view({"post": "finance_approve"})(request, pk=payroll_id)

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Resolve unresolved workforce readiness blockers before finance approval.",
            response.data["errors"],
        )
        self.assertIn(
            "Resolve missing mandatory statutory identifiers before finance approval.",
            response.data["errors"],
        )
        self.assertIn(
            "Resolve missing payroll posting buckets before finance approval.",
            response.data["errors"],
        )

        payroll = PayrollBatch.objects.get(pk=payroll_id)
        self.assertEqual(payroll.status, "Draft")
        self.assertIsNone(payroll.finance_approved_at)

    def test_finance_approve_rejects_unreconciled_batch_totals(self):
        process_response = self._process_payroll()
        payroll_id = process_response.data["id"]
        payroll = PayrollBatch.objects.get(pk=payroll_id)
        payroll.total_net = Decimal("1.00")
        payroll.save(update_fields=["total_net"])

        request = self.factory.post(
            f"/api/hr/payrolls/{payroll_id}/finance-approve/",
            {"approval_notes": "Check totals"},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = PayrollBatchViewSet.as_view({"post": "finance_approve"})(request, pk=payroll_id)

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Payroll batch totals do not reconcile with payroll item totals.",
            response.data["errors"],
        )

    def test_disbursement_workflow_requires_finance_approval_and_stamps_completion(self):
        process_response = self._process_payroll()
        payroll_id = process_response.data["id"]

        premature_start_request = self.factory.post(
            f"/api/hr/payrolls/{payroll_id}/start-disbursement/",
            {"method": "BANK"},
            format="json",
        )
        force_authenticate(premature_start_request, user=self.user)
        premature_start_response = PayrollBatchViewSet.as_view({"post": "start_disbursement"})(
            premature_start_request,
            pk=payroll_id,
        )
        self.assertEqual(premature_start_response.status_code, 400)
        self.assertEqual(
            premature_start_response.data["error"],
            "Finance approval is required before disbursement can start.",
        )

        finance_request = self.factory.post(
            f"/api/hr/payrolls/{payroll_id}/finance-approve/",
            {"approval_notes": "Finance gate passed"},
            format="json",
        )
        force_authenticate(finance_request, user=self.user)
        finance_response = PayrollBatchViewSet.as_view({"post": "finance_approve"})(finance_request, pk=payroll_id)
        self.assertEqual(finance_response.status_code, 200)
        self.assertEqual(finance_response.data["status"], "Finance Approved")
        self.assertEqual(finance_response.data["finance_approved_by"], self.user.id)

        start_request = self.factory.post(
            f"/api/hr/payrolls/{payroll_id}/start-disbursement/",
            {
                "method": "BANK",
                "scheduled_date": "2026-04-30",
                "reference": "BANK-RUN-APR",
                "notes": "Submitted to bank",
            },
            format="json",
        )
        force_authenticate(start_request, user=self.user)
        start_response = PayrollBatchViewSet.as_view({"post": "start_disbursement"})(start_request, pk=payroll_id)

        self.assertEqual(start_response.status_code, 200)
        self.assertEqual(start_response.data["status"], "Disbursement In Progress")
        self.assertEqual(len(start_response.data["disbursements"]), 1)
        self.assertEqual(start_response.data["disbursements"][0]["status"], "IN_PROGRESS")

        disbursements_request = self.factory.get(f"/api/hr/payrolls/{payroll_id}/disbursements/")
        force_authenticate(disbursements_request, user=self.user)
        disbursements_response = PayrollBatchViewSet.as_view({"get": "disbursement_records"})(
            disbursements_request,
            pk=payroll_id,
        )
        self.assertEqual(disbursements_response.status_code, 200)
        self.assertEqual(disbursements_response.data["count"], 1)
        self.assertEqual(disbursements_response.data["results"][0]["status"], "IN_PROGRESS")

        mark_request = self.factory.post(
            f"/api/hr/payrolls/{payroll_id}/mark-disbursed/",
            {
                "reference": "BANK-RUN-APR-COMPLETE",
                "notes": "Bank confirmed release",
                "disbursed_at": "2026-04-30T10:15:00+03:00",
            },
            format="json",
        )
        force_authenticate(mark_request, user=self.user)
        mark_response = PayrollBatchViewSet.as_view({"post": "mark_disbursed"})(mark_request, pk=payroll_id)

        self.assertEqual(mark_response.status_code, 200)
        self.assertEqual(mark_response.data["status"], "Disbursed")
        self.assertEqual(mark_response.data["disbursed_by"], self.user.id)

        payroll = PayrollBatch.objects.get(pk=payroll_id)
        disbursement = payroll.disbursements.get()
        self.assertEqual(payroll.status, "Disbursed")
        self.assertEqual(disbursement.status, "COMPLETED")
        self.assertEqual(disbursement.reference, "BANK-RUN-APR-COMPLETE")
        self.assertEqual(disbursement.disbursed_by_id, self.user.id)
        self.assertIsNotNone(payroll.disbursed_at)

        reprocess_request = self.factory.post(f"/api/hr/payrolls/{payroll_id}/reprocess/", {}, format="json")
        force_authenticate(reprocess_request, user=self.user)
        reprocess_response = PayrollBatchViewSet.as_view({"post": "reprocess"})(reprocess_request, pk=payroll_id)
        self.assertEqual(reprocess_response.status_code, 400)

    def test_post_to_finance_creates_journals_vote_head_lines_and_cashbook_entry(self):
        process_response = self._process_payroll()
        payroll_id = process_response.data["id"]
        finance_response, start_response, mark_response = self._finance_approve_and_disburse(payroll_id)
        self.assertEqual(finance_response.status_code, 200)
        self.assertEqual(start_response.status_code, 200)
        self.assertEqual(mark_response.status_code, 200)

        posting_request = self.factory.post(
            f"/api/hr/payrolls/{payroll_id}/post-to-finance/",
            {"entry_date": "2026-04-30"},
            format="json",
        )
        force_authenticate(posting_request, user=self.user)
        posting_response = PayrollBatchViewSet.as_view({"post": "post_to_finance"})(posting_request, pk=payroll_id)

        self.assertEqual(posting_response.status_code, 200)
        self.assertEqual(posting_response.data["status"], "Finance Posted")
        self.assertEqual(len(posting_response.data["finance_postings"]), 2)
        self.assertEqual(posting_response.data["posting_summary"]["can_post_to_finance"], True)

        payroll = PayrollBatch.objects.get(pk=payroll_id)
        accrual_posting = payroll.finance_postings.get(posting_stage="ACCRUAL")
        disbursement_posting = payroll.finance_postings.get(posting_stage="DISBURSEMENT")

        self.assertEqual(accrual_posting.status, "POSTED")
        self.assertEqual(disbursement_posting.status, "POSTED")
        self.assertIsNotNone(accrual_posting.journal_entry_id)
        self.assertIsNotNone(disbursement_posting.journal_entry_id)
        self.assertIsNotNone(disbursement_posting.cashbook_entry_id)
        self.assertEqual(disbursement_posting.cashbook_entry.amount_out, payroll.total_net)

        accrual_entry = JournalEntry.objects.get(pk=accrual_posting.journal_entry_id)
        self.assertTrue(accrual_entry.lines.filter(vote_head__name="Teaching Salaries", debit__gt=0).exists())
        self.assertTrue(accrual_entry.lines.filter(vote_head__name="Statutory Liabilities", credit__gt=0).exists())
        self.assertTrue(accrual_entry.lines.filter(vote_head__name="Net Payroll Payable", credit__gt=0).exists())

        self.assertTrue(VoteHead.objects.filter(name="Teaching Salaries", is_active=True).exists())
        self.assertTrue(VoteHead.objects.filter(name="Statutory Liabilities", is_active=True).exists())
        self.assertTrue(CashbookEntry.objects.filter(pk=disbursement_posting.cashbook_entry_id, book_type="BANK").exists())

    def test_post_to_finance_is_idempotent_for_repeated_requests(self):
        process_response = self._process_payroll()
        payroll_id = process_response.data["id"]
        self._finance_approve_and_disburse(payroll_id)

        first_request = self.factory.post(
            f"/api/hr/payrolls/{payroll_id}/post-to-finance/",
            {"entry_date": "2026-04-30"},
            format="json",
        )
        force_authenticate(first_request, user=self.user)
        first_response = PayrollBatchViewSet.as_view({"post": "post_to_finance"})(first_request, pk=payroll_id)
        self.assertEqual(first_response.status_code, 200)

        journal_count = JournalEntry.objects.count()
        cashbook_count = CashbookEntry.objects.count()

        second_request = self.factory.post(
            f"/api/hr/payrolls/{payroll_id}/post-to-finance/",
            {"entry_date": "2026-04-30"},
            format="json",
        )
        force_authenticate(second_request, user=self.user)
        second_response = PayrollBatchViewSet.as_view({"post": "post_to_finance"})(second_request, pk=payroll_id)

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(JournalEntry.objects.count(), journal_count)
        self.assertEqual(CashbookEntry.objects.count(), cashbook_count)
        self.assertEqual(PayrollFinancePosting.objects.filter(payroll_id=payroll_id).count(), 2)

    def test_post_to_finance_respects_closed_accounting_periods(self):
        AccountingPeriod.objects.create(
            name="Apr 2026",
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 30),
            is_closed=True,
        )
        process_response = self._process_payroll()
        payroll_id = process_response.data["id"]
        self._finance_approve_and_disburse(payroll_id)

        posting_request = self.factory.post(
            f"/api/hr/payrolls/{payroll_id}/post-to-finance/",
            {"entry_date": "2026-04-30"},
            format="json",
        )
        force_authenticate(posting_request, user=self.user)
        posting_response = PayrollBatchViewSet.as_view({"post": "post_to_finance"})(posting_request, pk=payroll_id)

        self.assertEqual(posting_response.status_code, 400)
        self.assertIn("closed", posting_response.data["error"].lower())

    def test_bursar_with_finance_module_can_run_finance_stage_actions_without_hr_module(self):
        process_response = self._process_payroll()
        payroll_id = process_response.data["id"]

        list_request = self.factory.get("/api/hr/payrolls/")
        force_authenticate(list_request, user=self.bursar_user)
        list_response = PayrollBatchViewSet.as_view({"get": "list"})(list_request)
        self.assertEqual(list_response.status_code, 200)

        exceptions_request = self.factory.get(f"/api/hr/payrolls/{payroll_id}/exceptions/")
        force_authenticate(exceptions_request, user=self.bursar_user)
        exceptions_response = PayrollBatchViewSet.as_view({"get": "exceptions"})(exceptions_request, pk=payroll_id)
        self.assertEqual(exceptions_response.status_code, 200)

        finance_request = self.factory.post(
            f"/api/hr/payrolls/{payroll_id}/finance-approve/",
            {"approval_notes": "Finance gate passed"},
            format="json",
        )
        force_authenticate(finance_request, user=self.bursar_user)
        finance_response = PayrollBatchViewSet.as_view({"post": "finance_approve"})(finance_request, pk=payroll_id)
        self.assertEqual(finance_response.status_code, 200)
        self.assertEqual(finance_response.data["finance_approved_by"], self.bursar_user.id)

        start_request = self.factory.post(
            f"/api/hr/payrolls/{payroll_id}/start-disbursement/",
            {
                "method": "BANK",
                "scheduled_date": "2026-04-30",
                "reference": "BURSAR-BANK-RUN-APR",
                "notes": "Submitted by bursar",
            },
            format="json",
        )
        force_authenticate(start_request, user=self.bursar_user)
        start_response = PayrollBatchViewSet.as_view({"post": "start_disbursement"})(start_request, pk=payroll_id)
        self.assertEqual(start_response.status_code, 200)

        mark_request = self.factory.post(
            f"/api/hr/payrolls/{payroll_id}/mark-disbursed/",
            {
                "reference": "BURSAR-BANK-RUN-APR-DONE",
                "notes": "Released by bursar",
                "disbursed_at": "2026-04-30T10:15:00+03:00",
            },
            format="json",
        )
        force_authenticate(mark_request, user=self.bursar_user)
        mark_response = PayrollBatchViewSet.as_view({"post": "mark_disbursed"})(mark_request, pk=payroll_id)
        self.assertEqual(mark_response.status_code, 200)
        self.assertEqual(mark_response.data["disbursed_by"], self.bursar_user.id)

        posting_summary_request = self.factory.get(f"/api/hr/payrolls/{payroll_id}/posting-summary/")
        force_authenticate(posting_summary_request, user=self.bursar_user)
        posting_summary_response = PayrollBatchViewSet.as_view({"get": "posting_summary"})(
            posting_summary_request,
            pk=payroll_id,
        )
        self.assertEqual(posting_summary_response.status_code, 200)

        posting_request = self.factory.post(
            f"/api/hr/payrolls/{payroll_id}/post-to-finance/",
            {"entry_date": "2026-04-30"},
            format="json",
        )
        force_authenticate(posting_request, user=self.bursar_user)
        posting_response = PayrollBatchViewSet.as_view({"post": "post_to_finance"})(posting_request, pk=payroll_id)
        self.assertEqual(posting_response.status_code, 200)
        self.assertEqual(posting_response.data["posted_by"], self.bursar_user.id)

        bank_file_request = self.factory.get(f"/api/hr/payrolls/{payroll_id}/bank-file/")
        force_authenticate(bank_file_request, user=self.bursar_user)
        bank_file_response = PayrollBatchViewSet.as_view({"get": "bank_file"})(bank_file_request, pk=payroll_id)
        self.assertEqual(bank_file_response.status_code, 200)

        tax_report_request = self.factory.get("/api/hr/payrolls/tax-report/?month=4&year=2026")
        force_authenticate(tax_report_request, user=self.bursar_user)
        tax_report_response = PayrollBatchViewSet.as_view({"get": "tax_report"})(tax_report_request)
        self.assertEqual(tax_report_response.status_code, 200)

    def test_payslip_snapshot_remains_stable_after_later_salary_component_edits(self):
        process_response = self._process_payroll()
        payroll = PayrollBatch.objects.get(pk=process_response.data["id"])
        item = payroll.items.get(employee=self.employee)
        structure = SalaryStructure.objects.get(employee=self.employee, is_active=True)

        SalaryComponent.objects.create(
            structure=structure,
            component_type="Allowance",
            name="Late Added Transport",
            amount_type="Fixed",
            amount="999.00",
            is_taxable=False,
            is_statutory=False,
            is_active=True,
        )

        serialized = PayrollItemSerializer(item).data
        component_names = [component["name"] for component in serialized["components"]]

        self.assertIn("Pay As You Earn", component_names)
        self.assertNotIn("Late Added Transport", component_names)
        self.assertEqual(serialized["currency"], "KES")
        self.assertEqual(serialized["pay_frequency"], "Monthly")

        pdf_request = self.factory.get(f"/api/hr/payslips/{item.id}/pdf/")
        force_authenticate(pdf_request, user=self.user)
        pdf_response = PayrollItemViewSet.as_view({"get": "pdf"})(pdf_request, pk=item.id)

        self.assertEqual(pdf_response.status_code, 200)
        pdf_html = pdf_response.content.decode("utf-8")
        self.assertIn("Pay As You Earn", pdf_html)
        self.assertIn("Social Health Insurance Fund", pdf_html)
        self.assertNotIn("Late Added Transport", pdf_html)
