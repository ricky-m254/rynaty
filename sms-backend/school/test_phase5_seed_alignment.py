from django.test import SimpleTestCase

from school.management.commands.seed_default_permissions import (
    ROLE_DEFAULTS,
    TEACHER_PERMISSIONS,
    build_role_defaults,
)
from school.models import Role
from school.role_scope import iter_seed_role_names


class Phase5SeedAlignmentTests(SimpleTestCase):
    def test_seed_role_catalog_matches_model_choices(self):
        choice_names = {name for name, _ in Role._meta.get_field("name").choices}

        self.assertSetEqual(set(iter_seed_role_names()), choice_names)

    def test_new_roles_inherit_defaults_from_scope_bridge(self):
        self.assertEqual(ROLE_DEFAULTS["PRINCIPAL"], ROLE_DEFAULTS["ADMIN"])
        self.assertEqual(ROLE_DEFAULTS["DEPUTY_PRINCIPAL"], ROLE_DEFAULTS["ADMIN"])
        self.assertEqual(ROLE_DEFAULTS["BURSAR"], ROLE_DEFAULTS["ACCOUNTANT"])
        self.assertEqual(ROLE_DEFAULTS["SECURITY_GUARD"], ROLE_DEFAULTS["SECURITY"])

    def test_hod_defaults_extend_teacher_baseline(self):
        self.assertTrue(set(TEACHER_PERMISSIONS).issubset(set(ROLE_DEFAULTS["HOD"])))
        self.assertIn("academics.enrollment.manage", ROLE_DEFAULTS["HOD"])
        self.assertIn("academics.timetable.manage", ROLE_DEFAULTS["HOD"])
        self.assertIn("analytics.report.view", ROLE_DEFAULTS["HOD"])

    def test_specialized_new_roles_have_expected_defaults(self):
        self.assertIn("hr.staff.read", ROLE_DEFAULTS["HR_OFFICER"])
        self.assertIn("admissions.application.manage", ROLE_DEFAULTS["REGISTRAR"])
        self.assertIn("library.classroom.view", ROLE_DEFAULTS["TEACHER"])
        self.assertIn("library.classroom.manage", ROLE_DEFAULTS["TEACHER"])
        self.assertEqual(
            ROLE_DEFAULTS["SECRETARY"],
            [
                "students.student.read",
                "academics.exam.read",
                "communication.message.read",
                "communication.message.send",
                "analytics.report.view",
            ],
        )
        self.assertEqual(ROLE_DEFAULTS["ALUMNI"], ["alumni.record.view"])

    def test_role_defaults_builder_is_deterministic(self):
        self.assertEqual(build_role_defaults(), ROLE_DEFAULTS)
