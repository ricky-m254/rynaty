"""
Phase 13 — Prompt 51: Unit tests for CreateStudentService.
Rules: No database. Uses mock repository.
"""
import unittest
from unittest.mock import MagicMock, patch
from domains.users.application.create_student_service import CreateStudentService
from domains.users.domain.entities import Student


def _make_student(**kwargs) -> Student:
    defaults = dict(
        id=1,
        admission_number="STM001",
        first_name="Alice",
        last_name="Wanjiku",
        date_of_birth="2010-01-15",
        gender="F",
        grade_level="Grade 5",
        phone=None,
        email=None,
        address=None,
    )
    defaults.update(kwargs)
    return Student(**defaults)


class TestCreateStudentService(unittest.TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.service = CreateStudentService(self.repo)

    def test_creates_student_successfully(self):
        """Happy path: valid data → student saved and returned."""
        expected = _make_student()
        self.repo.exists.return_value = False
        self.repo.save.return_value = expected

        result = self.service.execute(
            admission_number="STM001",
            first_name="Alice",
            last_name="Wanjiku",
            date_of_birth="2010-01-15",
            gender="F",
            grade_level="Grade 5",
        )

        self.repo.exists.assert_called_once_with("STM001")
        self.repo.save.assert_called_once()
        self.assertEqual(result.admission_number, "STM001")
        self.assertEqual(result.first_name, "Alice")

    def test_raises_on_missing_first_name(self):
        """Validation: missing first_name must raise ValueError."""
        self.repo.exists.return_value = False
        with self.assertRaises(ValueError) as ctx:
            self.service.execute(
                admission_number="STM002",
                first_name="",
                last_name="Kamau",
            )
        self.assertIn("first_name", str(ctx.exception).lower())

    def test_raises_on_missing_last_name(self):
        """Validation: missing last_name must raise ValueError."""
        self.repo.exists.return_value = False
        with self.assertRaises(ValueError) as ctx:
            self.service.execute(
                admission_number="STM003",
                first_name="Bob",
                last_name="",
            )
        self.assertIn("last_name", str(ctx.exception).lower())

    def test_raises_on_missing_admission_number(self):
        """Validation: blank admission number must raise ValueError."""
        self.repo.exists.return_value = False
        with self.assertRaises(ValueError) as ctx:
            self.service.execute(
                admission_number="",
                first_name="Carol",
                last_name="Otieno",
            )
        self.assertIn("admission_number", str(ctx.exception).lower())

    def test_raises_on_duplicate_admission_number(self):
        """Duplicate prevention: repo.exists returns True → ValueError."""
        self.repo.exists.return_value = True
        with self.assertRaises(ValueError) as ctx:
            self.service.execute(
                admission_number="STM001",
                first_name="Dan",
                last_name="Mwangi",
            )
        self.assertIn("STM001", str(ctx.exception))
        self.repo.save.assert_not_called()

    def test_strips_whitespace_from_admission_number(self):
        """Leading/trailing spaces stripped before repo call."""
        expected = _make_student(admission_number="STM999")
        self.repo.exists.return_value = False
        self.repo.save.return_value = expected

        self.service.execute(
            admission_number="  STM999  ",
            first_name="Eve",
            last_name="Njoroge",
        )
        self.repo.exists.assert_called_once_with("STM999")

    def test_repo_save_not_called_on_validation_error(self):
        """save() must NOT be called when validation fails."""
        self.repo.exists.return_value = False
        with self.assertRaises(ValueError):
            self.service.execute(
                admission_number="STM010",
                first_name="",
                last_name="Test",
            )
        self.repo.save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
