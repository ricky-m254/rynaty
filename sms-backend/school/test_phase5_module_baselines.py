from django.test import SimpleTestCase

from school.role_scope import (
    get_role_module_baseline,
    get_scope_module_baseline,
    SCOPE_SCHOOL_ADMIN,
)


class Phase5ModuleBaselineTests(SimpleTestCase):
    def test_school_admin_baseline_uses_available_module_order(self):
        available_modules = ["REPORTING", "FINANCE", "ACADEMICS", "HR"]

        baseline = get_scope_module_baseline(
            SCOPE_SCHOOL_ADMIN,
            available_module_keys=available_modules,
        )

        self.assertEqual(baseline, tuple(available_modules))

    def test_finance_scope_baseline_is_explicit(self):
        baseline = get_role_module_baseline("BURSAR")

        self.assertEqual(
            baseline,
            ("FINANCE", "STUDENTS", "REPORTING", "COMMUNICATION"),
        )

    def test_portal_roles_remain_exception_based(self):
        self.assertEqual(get_role_module_baseline("PARENT"), ())
        self.assertEqual(get_role_module_baseline("STUDENT"), ())

    def test_alumni_role_gets_alumni_module_baseline(self):
        self.assertEqual(get_role_module_baseline("ALUMNI"), ("ALUMNI",))

    def test_available_module_filter_drops_missing_entries(self):
        baseline = get_role_module_baseline(
            "REGISTRAR",
            available_module_keys=["STUDENTS", "ADMISSIONS", "COMMUNICATION"],
        )

        self.assertEqual(baseline, ("ADMISSIONS", "STUDENTS", "COMMUNICATION"))
