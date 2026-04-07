"""
Phase 13 — Prompt 52: Unit tests for EnrollStudentService.
Rules: No database. Uses mock repositories.
"""
import unittest
from unittest.mock import MagicMock
from domains.academics.application.enroll_student_service import EnrollStudentService
from domains.users.domain.entities import Student
from domains.academics.domain.entities import SchoolClass, Enrollment


def _student(id=1):
    return Student(
        id=id, admission_number=f"STM{id:03d}",
        first_name="Test", last_name="User",
    )


def _school_class(id=10):
    return SchoolClass(
        id=id, name="Grade 5A", grade_level="Grade 5",
        capacity=40,
    )


def _enrollment(**kw):
    defaults = dict(id=100, student_id=1, class_id=10, term_id=None, enrollment_date=None)
    defaults.update(kw)
    return Enrollment(**defaults)


class TestEnrollStudentService(unittest.TestCase):

    def setUp(self):
        self.student_repo = MagicMock()
        self.class_repo = MagicMock()
        self.enrollment_repo = MagicMock()
        self.service = EnrollStudentService(
            self.student_repo, self.class_repo, self.enrollment_repo
        )

    def test_enrolls_successfully(self):
        """Happy path: valid student + class, no duplicate."""
        self.student_repo.get_by_id.return_value = _student()
        self.class_repo.get_by_id.return_value = _school_class()
        self.enrollment_repo.exists.return_value = False
        expected = _enrollment()
        self.enrollment_repo.save.return_value = expected

        result = self.service.execute(student_id=1, class_id=10)

        self.student_repo.get_by_id.assert_called_once_with(1)
        self.class_repo.get_by_id.assert_called_once_with(10)
        self.enrollment_repo.exists.assert_called_once_with(1, 10, None)
        self.enrollment_repo.save.assert_called_once()
        self.assertEqual(result.student_id, 1)
        self.assertEqual(result.class_id, 10)

    def test_raises_when_student_not_found(self):
        """Student must exist — otherwise ValueError."""
        self.student_repo.get_by_id.return_value = None
        with self.assertRaises(ValueError) as ctx:
            self.service.execute(student_id=999, class_id=10)
        self.assertIn("999", str(ctx.exception))
        self.enrollment_repo.save.assert_not_called()

    def test_raises_when_class_not_found(self):
        """Class must exist — otherwise ValueError."""
        self.student_repo.get_by_id.return_value = _student()
        self.class_repo.get_by_id.return_value = None
        with self.assertRaises(ValueError) as ctx:
            self.service.execute(student_id=1, class_id=999)
        self.assertIn("999", str(ctx.exception))
        self.enrollment_repo.save.assert_not_called()

    def test_raises_on_duplicate_enrollment(self):
        """Prevent duplicate enrollment (same student + class + term)."""
        self.student_repo.get_by_id.return_value = _student()
        self.class_repo.get_by_id.return_value = _school_class()
        self.enrollment_repo.exists.return_value = True
        with self.assertRaises(ValueError) as ctx:
            self.service.execute(student_id=1, class_id=10, term_id=3)
        self.assertIn("already enrolled", str(ctx.exception))
        self.enrollment_repo.save.assert_not_called()

    def test_passes_term_id_to_exists_check(self):
        """term_id must be included in the duplicate check."""
        self.student_repo.get_by_id.return_value = _student()
        self.class_repo.get_by_id.return_value = _school_class()
        self.enrollment_repo.exists.return_value = False
        self.enrollment_repo.save.return_value = _enrollment(term_id=5)

        self.service.execute(student_id=1, class_id=10, term_id=5)
        self.enrollment_repo.exists.assert_called_once_with(1, 10, 5)

    def test_enrollment_date_stored(self):
        """enrollment_date passed to Enrollment entity."""
        self.student_repo.get_by_id.return_value = _student()
        self.class_repo.get_by_id.return_value = _school_class()
        self.enrollment_repo.exists.return_value = False
        expected = _enrollment(enrollment_date="2025-01-15")
        self.enrollment_repo.save.return_value = expected

        result = self.service.execute(
            student_id=1, class_id=10, enrollment_date="2025-01-15"
        )
        self.assertEqual(result.enrollment_date, "2025-01-15")


if __name__ == "__main__":
    unittest.main()
