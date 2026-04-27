import json
import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Iterator
import xml.etree.ElementTree as ET

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum
from django.utils import timezone
from django_tenants.utils import schema_context

from school.models import (
    AcademicYear,
    Enrollment,
    FeeStructure,
    GradeLevel,
    Guardian,
    Invoice,
    InvoiceLineItem,
    MediaFile,
    Payment,
    PaymentAllocation,
    SchoolClass,
    SchoolProfile,
    Student,
    Term,
)


NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
REL_NS = {"pr": "http://schemas.openxmlformats.org/package/2006/relationships"}
SCALED_DIVISOR = Decimal("10000")
TWOPLACES = Decimal("0.01")
GRADE_WORDS = {
    "1": "One",
    "2": "Two",
    "3": "Three",
    "4": "Four",
    "5": "Five",
    "6": "Six",
    "7": "Seven",
    "8": "Eight",
    "9": "Nine",
    "10": "Ten",
    "11": "Eleven",
    "12": "Twelve",
}
AGE_HINTS = {
    "One": 14,
    "Two": 15,
    "Three": 16,
    "Four": 17,
    "Five": 11,
    "Six": 12,
    "Seven": 13,
    "Eight": 14,
    "Nine": 15,
    "Ten": 16,
    "Eleven": 17,
    "Twelve": 18,
    "TopClass": 6,
    "Preunit": 5,
}


@dataclass
class StudentSeed:
    admission_number: str
    full_name: str = ""
    grade_label: str = ""
    stream: str = ""
    admission_date: date | None = None
    reference_year: int | None = None
    phone_primary: str = ""
    phone_secondary: str = ""
    boarding_status: str = ""
    school_name: str = ""
    is_active: bool = True
    dob: date | None = None
    gender: str = ""
    source_priority: dict = field(default_factory=dict)
    guardian_rows: list[dict] = field(default_factory=list)

    def update(self, field_name: str, value, priority: int) -> None:
        if value in (None, ""):
            return
        current_priority = self.source_priority.get(field_name, -1)
        if priority >= current_priority:
            setattr(self, field_name, value)
            self.source_priority[field_name] = priority


class LegacyWorkbook:
    def __init__(self, path: Path):
        self.path = path
        self._zip = zipfile.ZipFile(path)
        self._shared_strings = self._load_shared_strings()
        workbook = ET.fromstring(self._zip.read("xl/workbook.xml"))
        rels = ET.fromstring(self._zip.read("xl/_rels/workbook.xml.rels"))
        self._rel_map = {
            rel.attrib["Id"]: self._normalise_target(rel.attrib["Target"])
            for rel in rels.findall("pr:Relationship", REL_NS)
        }
        self._sheet_map = {
            sheet.attrib.get("name", ""): self._rel_map[
                sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            ]
            for sheet in workbook.findall("a:sheets/a:sheet", NS)
        }

    def close(self) -> None:
        self._zip.close()

    def sheet_names(self) -> list[str]:
        return list(self._sheet_map.keys())

    def has_sheet(self, sheet_name: str) -> bool:
        return sheet_name in self._sheet_map

    def iter_rows(self, sheet_name: str) -> Iterator[dict]:
        target = self._sheet_map.get(sheet_name)
        if not target:
            return iter(())
        root = ET.fromstring(self._zip.read(target))
        sheet_data = root.find("a:sheetData", NS)
        if sheet_data is None:
            return iter(())
        headers: list[str] = []
        max_cols = 0
        rows = sheet_data.findall("a:row", NS)
        for row_index, row in enumerate(rows):
            values: dict[int, str] = {}
            for cell in row.findall("a:c", NS):
                ref = cell.attrib.get("r", "")
                col = "".join(ch for ch in ref if ch.isalpha())
                idx = self._column_index(col)
                max_cols = max(max_cols, idx + 1)
                values[idx] = self._cell_value(cell)
            if row_index == 0:
                headers = [values.get(i, "").strip() for i in range(max_cols)]
                continue
            if not headers:
                continue
            yield {
                headers[i] or f"col_{i + 1}": values.get(i, "").strip()
                for i in range(max_cols)
                if headers[i] or values.get(i, "")
            }

    def _load_shared_strings(self) -> list[str]:
        try:
            root = ET.fromstring(self._zip.read("xl/sharedStrings.xml"))
        except KeyError:
            return []
        values: list[str] = []
        for si in root.findall("a:si", NS):
            texts: list[str] = []
            for node in si.iter():
                if node.tag == "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t":
                    texts.append(node.text or "")
            values.append("".join(texts))
        return values

    def _cell_value(self, cell) -> str:
        cell_type = cell.attrib.get("t")
        if cell_type == "inlineStr":
            return "".join(t.text or "" for t in cell.findall(".//a:t", NS))
        value = cell.find("a:v", NS)
        if value is None or value.text is None:
            return ""
        raw = value.text
        if cell_type == "s":
            try:
                return self._shared_strings[int(raw)]
            except (ValueError, IndexError):
                return raw
        return raw

    @staticmethod
    def _column_index(col: str) -> int:
        total = 0
        for ch in col:
            if ch.isalpha():
                total = total * 26 + (ord(ch.upper()) - 64)
        return total - 1

    @staticmethod
    def _normalise_target(target: str) -> str:
        target = target.replace("\\", "/")
        if target.startswith("/"):
            target = target[1:]
        if target.startswith("xl/"):
            return target
        return f"xl/{target}"


class Command(BaseCommand):
    help = "Import the legacy Olom Excel workbooks into a tenant schema."

    def add_arguments(self, parser):
        parser.add_argument("--schema-name", default="olom")
        parser.add_argument(
            "--source-dir",
            default=str(Path(__file__).resolve().parents[4] / "olom excel"),
            help="Directory containing the legacy Olom Excel workbooks.",
        )
        parser.add_argument(
            "--archive-raw",
            action="store_true",
            help="Store the source workbooks in tenant media_files for audit/archive purposes.",
        )
        parser.add_argument(
            "--school-name-override",
            default="",
            help="Optional explicit school profile name to preserve instead of inferring from the workbook.",
        )

    def handle(self, *args, **options):
        schema_name = options["schema_name"].strip()
        source_dir = Path(options["source_dir"]).resolve()
        archive_raw = bool(options["archive_raw"])
        school_name_override = (options.get("school_name_override") or "").strip()

        if not source_dir.exists():
            raise CommandError(f"Source directory not found: {source_dir}")

        canonical_files = {
            "statement_snapshot": source_dir / "Transact 2026_Backup.xlsx",
            "current_contacts": source_dir / "Transact 2026_Backup.xlsx",
            "student_roster": source_dir / "Transact 2026_Backup.xlsx",
            "payment_2023": source_dir / "Transact 2023_Backup.xlsx",
            "payment_2025": source_dir / "Transact 2026_Backup.xlsx",
        }
        missing = [str(path) for path in canonical_files.values() if not path.exists()]
        if missing:
            raise CommandError("Missing required source workbook(s): " + ", ".join(sorted(set(missing))))

        summary = {
            "schema": schema_name,
            "source_dir": str(source_dir),
            "students_created": 0,
            "students_updated": 0,
            "guardians_created": 0,
            "invoices_created": 0,
            "placeholder_invoices_created": 0,
            "payments_created": 0,
            "payments_allocated": 0,
            "placeholder_payments_allocated": 0,
            "raw_workbooks_archived": 0,
            "school_name": "",
            "assumptions": [
                "student gender defaults to F when legacy gender is missing",
                "student date_of_birth is approximated from academic level and source year when legacy DOB is missing",
                "legacy payment amount columns are divided by 10,000 based on workbook scaling",
                "statement snapshots from the 2018 and 2025 legacy workbooks are materialized into invoices",
            ],
        }

        with schema_context(schema_name):
            student_seeds = self._build_student_seeds(source_dir)
            summary["school_name"] = self._ensure_school_profile(
                student_seeds,
                school_name_override=school_name_override or None,
            )
            student_map = self._import_students(student_seeds, summary)
            invoice_index: dict[str, list[Invoice]] = defaultdict(list)
            for workbook_name in ("Transact 2022.xlsx", "Transact 2026_Backup.xlsx"):
                partial_index = self._import_statement_invoices(
                    workbook_path=source_dir / workbook_name,
                    student_seeds=student_seeds,
                    student_map=student_map,
                    summary=summary,
                )
                self._merge_invoice_index(invoice_index, partial_index)
            self._ensure_enrollments_for_students(student_seeds, student_map, invoice_index)
            legacy_payments = self._import_payments(source_dir, student_map, invoice_index, summary)
            placeholder_index = self._create_placeholder_invoices_for_unallocated_payments(
                legacy_payments,
                summary,
            )
            self._merge_invoice_index(invoice_index, placeholder_index)
            self._allocate_payments(
                legacy_payments,
                invoice_index,
                summary,
                detail_key="placeholder_payments_allocated",
            )
            if archive_raw:
                summary["raw_workbooks_archived"] = self._archive_workbooks(source_dir)

        self.stdout.write(json.dumps(summary, indent=2, default=str))

    def _build_student_seeds(self, source_dir: Path) -> dict[str, StudentSeed]:
        seeds: dict[str, StudentSeed] = {}
        self._merge_balance_sheet(source_dir / "Transact 2026_Backup.xlsx", "Balances For SMS", seeds, 100)
        self._merge_statement_roster(source_dir / "Transact 2026_Backup.xlsx", "Statement", seeds, 95)
        self._merge_universal_roster(source_dir / "Transact 2026_Backup.xlsx", "Universal Former", seeds, 90)
        self._merge_class_list(source_dir / "Transact 2026_Backup.xlsx", "Class List Processed", seeds, 85)
        self._merge_payment_roster(source_dir / "Transact 2023_Backup.xlsx", "Fees Records OT", seeds, 70)
        self._merge_payment_roster(source_dir / "Transact 2023_Backup.xlsx", "Fees Recs Select", seeds, 70)
        self._merge_payment_roster(source_dir / "Transact 2026_Backup.xlsx", "Fees Records OT", seeds, 75)
        self._merge_payment_roster(source_dir / "Transact 2026_Backup.xlsx", "Fees Records Local", seeds, 80)
        self._merge_payment_roster(source_dir / "Transact 2026_Backup.xlsx", "Fees Recs Select", seeds, 80)
        return seeds

    def _merge_balance_sheet(self, workbook_path: Path, sheet_name: str, seeds: dict[str, StudentSeed], priority: int) -> None:
        workbook = LegacyWorkbook(workbook_path)
        try:
            if not workbook.has_sheet(sheet_name):
                return
            for row in workbook.iter_rows(sheet_name):
                admission_number = self._clean_admission(row.get("ADM No"))
                if not admission_number:
                    continue
                seed = seeds.setdefault(admission_number, StudentSeed(admission_number=admission_number))
                seed.update("full_name", row.get("NAME", ""), priority)
                seed.update("phone_primary", row.get("ContactPhone1", ""), priority)
                seed.update("phone_secondary", row.get("ContactPhone2", ""), priority)
                seed.update("stream", self._clean_stream(row.get("CLASS") or row.get("ClassST")), priority)
                seed.update("grade_label", self._normalise_grade_label(row.get("ClassNumber") or row.get("Term")), priority)
                seed.update("boarding_status", row.get("Boardingstatus", ""), priority)
                seed.update("school_name", row.get("School", ""), priority)
                seed.update("reference_year", self._safe_int(row.get("Year")), priority)
                seed.guardian_rows.append(
                    {
                        "phone": row.get("ContactPhone1", ""),
                        "name": row.get("HomePhone1Name", ""),
                        "relationship": row.get("HomePhone1Relation", ""),
                    }
                )
                seed.guardian_rows.append(
                    {
                        "phone": row.get("ContactPhone2", ""),
                        "name": row.get("HomePhone2Name", ""),
                        "relationship": row.get("HomePhone2Relation", ""),
                    }
                )
        finally:
            workbook.close()

    def _merge_statement_roster(self, workbook_path: Path, sheet_name: str, seeds: dict[str, StudentSeed], priority: int) -> None:
        workbook = LegacyWorkbook(workbook_path)
        try:
            if not workbook.has_sheet(sheet_name):
                return
            for row in workbook.iter_rows(sheet_name):
                admission_number = self._clean_admission(row.get("AdmissionNumber"))
                if not admission_number:
                    continue
                seed = seeds.setdefault(admission_number, StudentSeed(admission_number=admission_number))
                seed.update("full_name", row.get("StudentName", ""), priority)
                seed.update("grade_label", self._normalise_grade_label(row.get("Class")), priority)
                seed.update("reference_year", self._date_part_year(row.get("DateOfIssue")), priority)
        finally:
            workbook.close()

    def _merge_universal_roster(self, workbook_path: Path, sheet_name: str, seeds: dict[str, StudentSeed], priority: int) -> None:
        workbook = LegacyWorkbook(workbook_path)
        try:
            if not workbook.has_sheet(sheet_name):
                return
            for row in workbook.iter_rows(sheet_name):
                admission_number = self._clean_admission(row.get("ADM No"))
                if not admission_number:
                    continue
                seed = seeds.setdefault(admission_number, StudentSeed(admission_number=admission_number))
                seed.update("full_name", row.get("NAME", ""), priority)
                seed.update("grade_label", self._normalise_grade_label(row.get("FORM") or row.get("Frm")), priority)
                seed.update("stream", self._clean_stream(row.get("CLASS")), priority)
                seed.update("boarding_status", row.get("BStatus", ""), priority)
                seed.update("reference_year", self._safe_int(row.get("YearOfStudy")), priority)
                if (row.get("Exclude") or "").strip() == "1":
                    seed.update("is_active", False, priority)
        finally:
            workbook.close()

    def _merge_class_list(self, workbook_path: Path, sheet_name: str, seeds: dict[str, StudentSeed], priority: int) -> None:
        workbook = LegacyWorkbook(workbook_path)
        try:
            if not workbook.has_sheet(sheet_name):
                return
            for row in workbook.iter_rows(sheet_name):
                admission_number = self._clean_admission(row.get("AdmissionNumber"))
                if not admission_number:
                    continue
                seed = seeds.setdefault(admission_number, StudentSeed(admission_number=admission_number))
                seed.update("full_name", row.get("Name", ""), priority)
                seed.update("grade_label", self._normalise_grade_label(row.get("Form") or row.get("Class")), priority)
                seed.update("stream", self._clean_stream(row.get("Stream")), priority)
                seed.update("boarding_status", row.get("Boardingstatus", ""), priority)
                seed.update("reference_year", self._safe_int(row.get("Year of Admission")), priority)
                admission_date = self._parse_datetime(row.get("AdmissionDate"))
                if admission_date:
                    seed.update("admission_date", admission_date.date(), priority)
                left_text = (row.get("Left") or "").strip().lower()
                if left_text and left_text != "present":
                    seed.update("is_active", False, priority)
        finally:
            workbook.close()

    def _merge_payment_roster(self, workbook_path: Path, sheet_name: str, seeds: dict[str, StudentSeed], priority: int) -> None:
        workbook = LegacyWorkbook(workbook_path)
        try:
            if not workbook.has_sheet(sheet_name):
                return
            for row in workbook.iter_rows(sheet_name):
                admission_number = self._clean_admission(row.get("ADM No"))
                if not admission_number:
                    continue
                seed = seeds.setdefault(admission_number, StudentSeed(admission_number=admission_number))
                seed.update("full_name", row.get("NAME", ""), priority)
                seed.update("grade_label", self._normalise_grade_label(row.get("FORM")), priority)
                seed.update("stream", self._clean_stream(row.get("CLASS")), priority)
                seed.update("boarding_status", row.get("BoardingStatus") or row.get("BStatus"), priority)
                seed.update(
                    "reference_year",
                    self._first_non_none_int(
                        self._safe_int(row.get("Acadyear")),
                        self._safe_int(row.get("CashBookYear")),
                        self._date_part_year(row.get("Date")),
                    ),
                    priority,
                )
        finally:
            workbook.close()

    def _ensure_school_profile(
        self,
        seeds: dict[str, StudentSeed],
        *,
        school_name_override: str | None = None,
    ) -> str:
        school_name_counts: dict[str, int] = defaultdict(int)
        for seed in seeds.values():
            if seed.school_name:
                school_name_counts[seed.school_name] += 1
        inferred_school_name = (
            max(school_name_counts, key=school_name_counts.get) if school_name_counts else "Olom School"
        )
        profile, _ = SchoolProfile.objects.get_or_create(
            pk=1,
            defaults={
                "school_name": school_name_override or inferred_school_name,
                "currency": "KES",
                "accepted_payment_methods": ["Cash", "Bank Transfer", "MPesa", "EFT"],
            },
        )
        school_name = school_name_override or self._preferred_school_name(profile.school_name, inferred_school_name)
        changed = False
        if profile.school_name != school_name:
            profile.school_name = school_name
            changed = True
        if profile.currency != "KES":
            profile.currency = "KES"
            changed = True
        if not profile.accepted_payment_methods:
            profile.accepted_payment_methods = ["Cash", "Bank Transfer", "MPesa", "EFT"]
            changed = True
        if changed:
            profile.save()
        return school_name

    def _preferred_school_name(self, current_name: str | None, inferred_name: str) -> str:
        current = (current_name or "").strip()
        if current and current not in {"Olom School", "School"}:
            return current
        return inferred_name

    def _import_students(
        self,
        student_seeds: dict[str, StudentSeed],
        summary: dict,
    ) -> dict[str, Student]:
        student_map: dict[str, Student] = {}
        for admission_number in sorted(student_seeds):
            seed = student_seeds[admission_number]
            student, created, updated = self._upsert_student(seed)
            if created:
                summary["students_created"] += 1
            elif updated:
                summary["students_updated"] += 1

            self._ensure_guardians(student, seed, summary)
            student_map[admission_number] = student
        return student_map

    def _upsert_student(self, seed: StudentSeed) -> tuple[Student, bool, bool]:
        first_name, last_name = self._split_name(seed.full_name, seed.admission_number)
        gender = self._normalise_gender(seed.gender)
        dob = seed.dob or self._approximate_dob(seed)
        student, created = Student.objects.get_or_create(
            admission_number=seed.admission_number,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "gender": gender,
                "date_of_birth": dob,
                "phone": seed.phone_primary,
                "address": seed.school_name,
                "is_active": seed.is_active,
            },
        )
        if created:
            return student, True, False

        updates = []
        if student.first_name != first_name:
            student.first_name = first_name
            updates.append("first_name")
        if student.last_name != last_name:
            student.last_name = last_name
            updates.append("last_name")
        if student.gender != gender:
            student.gender = gender
            updates.append("gender")
        if student.date_of_birth != dob:
            student.date_of_birth = dob
            updates.append("date_of_birth")
        if seed.phone_primary and student.phone != seed.phone_primary:
            student.phone = seed.phone_primary
            updates.append("phone")
        if seed.school_name and student.address != seed.school_name:
            student.address = seed.school_name
            updates.append("address")
        if student.is_active != seed.is_active:
            student.is_active = seed.is_active
            updates.append("is_active")
        if updates:
            student.save(update_fields=updates)
            return student, False, True
        return student, False, False

    def _ensure_guardians(self, student: Student, seed: StudentSeed, summary: dict) -> None:
        seen = set()
        for row in seed.guardian_rows:
            phone = self._normalise_phone(row.get("phone"))
            if not phone or phone in seen:
                continue
            seen.add(phone)
            relationship = (row.get("relationship") or "Guardian").strip() or "Guardian"
            name = (row.get("name") or f"{student.first_name} Guardian").strip()
            _, created = Guardian.objects.get_or_create(
                student=student,
                phone=phone,
                defaults={
                    "name": name[:255],
                    "relationship": relationship[:50],
                    "email": "",
                    "is_active": True,
                },
            )
            if created:
                summary["guardians_created"] += 1

    def _ensure_enrollments_for_students(
        self,
        student_seeds: dict[str, StudentSeed],
        student_map: dict[str, Student],
        invoice_index: dict[str, list[Invoice]],
    ) -> None:
        for admission_number, student in student_map.items():
            seed = student_seeds[admission_number]
            self._ensure_enrollment(student, seed, invoice_index.get(admission_number, []))

    def _ensure_enrollment(self, student: Student, seed: StudentSeed, existing_invoices: list[Invoice]) -> None:
        grade_label = seed.grade_label or "Legacy"
        grade = self._ensure_grade_level(grade_label)
        year_value = seed.reference_year or self._latest_invoice_year(existing_invoices) or 2025
        academic_year = self._ensure_academic_year(year_value)
        term_name = self._pick_term_name(existing_invoices)
        term = self._ensure_term(academic_year, term_name)
        stream = seed.stream or ""
        school_class, _ = SchoolClass.objects.get_or_create(
            name=grade.name,
            stream=stream,
            academic_year=academic_year,
            defaults={
                "grade_level": grade,
                "section_name": stream,
                "is_active": True,
            },
        )
        if school_class.grade_level_id != grade.id or school_class.section_name != stream:
            school_class.grade_level = grade
            school_class.section_name = stream
            school_class.save(update_fields=["grade_level", "section_name"])

        enrollment_defaults = {
            "status": "Active" if seed.is_active else "Completed",
            "is_active": seed.is_active,
        }
        enrollment, created = Enrollment.objects.get_or_create(
            student=student,
            school_class=school_class,
            term=term,
            defaults=enrollment_defaults,
        )
        if not created:
            updates = []
            if enrollment.status != enrollment_defaults["status"]:
                enrollment.status = enrollment_defaults["status"]
                updates.append("status")
            if enrollment.is_active != enrollment_defaults["is_active"]:
                enrollment.is_active = enrollment_defaults["is_active"]
                updates.append("is_active")
            if updates:
                enrollment.save(update_fields=updates)

    def _import_statement_invoices(
        self,
        workbook_path: Path,
        student_seeds: dict[str, StudentSeed],
        student_map: dict[str, Student],
        summary: dict,
    ) -> dict[str, list[Invoice]]:
        workbook = LegacyWorkbook(workbook_path)
        invoice_index: dict[str, list[Invoice]] = defaultdict(list)
        try:
            if not workbook.has_sheet("Statement"):
                return invoice_index
            grouped: dict[tuple[str, int, int], list[dict]] = defaultdict(list)
            for row in workbook.iter_rows("Statement"):
                admission_number = self._clean_admission(row.get("AdmissionNumber"))
                snapshot = self._parse_datetime(row.get("DateOfIssue"))
                if not admission_number or snapshot is None:
                    continue
                year_value = snapshot.year
                for term_number in (1, 2, 3):
                    amount = self._parse_money(row.get(f"ExpectedTerm{term_number}"), scaled=False)
                    if amount <= 0:
                        continue
                    grouped[(admission_number, year_value, term_number)].append(
                        {
                            "amount": amount,
                            "description": self._statement_description(row),
                            "category": (row.get("VoteName") or "Legacy").strip() or "Legacy",
                            "item_name": (row.get("VoteHead") or row.get("VoteName") or "Legacy charge").strip() or "Legacy charge",
                            "due_date": snapshot.date(),
                        }
                    )

            for (admission_number, year_value, term_number), items in grouped.items():
                seed = student_seeds.setdefault(admission_number, StudentSeed(admission_number=admission_number))
                student = student_map.get(admission_number)
                if student is None:
                    student, created, updated = self._upsert_student(seed)
                    student_map[admission_number] = student
                    if created:
                        summary["students_created"] += 1
                    elif updated:
                        summary["students_updated"] += 1
                academic_year = self._ensure_academic_year(year_value)
                term = self._ensure_term(academic_year, f"Term {term_number}")
                invoice_number = f"LEGACY-STMT-{year_value}-{term_number}-{admission_number}"[:40]
                invoice_total = sum((item["amount"] for item in items), Decimal("0.00"))
                due_date = items[0]["due_date"]
                invoice, created = Invoice.objects.get_or_create(
                    invoice_number=invoice_number,
                    defaults={
                        "student": student,
                        "term": term,
                        "total_amount": invoice_total,
                        "due_date": due_date,
                        "status": "ISSUED",
                        "is_active": True,
                    },
                )
                invoice_updates = []
                if invoice.student_id != student.id:
                    invoice.student = student
                    invoice_updates.append("student")
                if invoice.term_id != term.id:
                    invoice.term = term
                    invoice_updates.append("term")
                if invoice.total_amount != invoice_total:
                    invoice.total_amount = invoice_total
                    invoice_updates.append("total_amount")
                if invoice.due_date != due_date:
                    invoice.due_date = due_date
                    invoice_updates.append("due_date")
                if invoice.invoice_date != due_date:
                    invoice.invoice_date = due_date
                    invoice_updates.append("invoice_date")
                if not invoice.is_active:
                    invoice.is_active = True
                    invoice_updates.append("is_active")
                if invoice_updates:
                    invoice.save(update_fields=invoice_updates)

                if created or not invoice.line_items.exists():
                    for item in items:
                        fee_structure = self._ensure_fee_structure(
                            academic_year=academic_year,
                            term=term,
                            name=f"Legacy {item['item_name']}",
                            category=item["category"],
                        )
                        InvoiceLineItem.objects.create(
                            invoice=invoice,
                            fee_structure=fee_structure,
                            description=item["description"][:255],
                            amount=item["amount"],
                        )
                    summary["invoices_created"] += 1
                invoice_index[admission_number].append(invoice)
        finally:
            workbook.close()
        return invoice_index

    def _merge_invoice_index(
        self,
        target: dict[str, list[Invoice]],
        source: dict[str, list[Invoice]],
    ) -> None:
        for admission_number, invoices in source.items():
            target[admission_number].extend(invoices)

    def _import_payments(
        self,
        source_dir: Path,
        student_map: dict[str, Student],
        invoice_index: dict[str, list[Invoice]],
        summary: dict,
    ) -> list[Payment]:
        payment_sources = [
            (source_dir / "Transact 2023_Backup.xlsx", "Fees Records OT", "OT23"),
            (source_dir / "Transact 2023_Backup.xlsx", "Fees Recs Select", "SEL23"),
            (source_dir / "Transact 2026_Backup.xlsx", "Fees Records OT", "OT25"),
            (source_dir / "Transact 2026_Backup.xlsx", "Fees Records Local", "LOC25"),
            (source_dir / "Transact 2026_Backup.xlsx", "Fees Recs Select", "SEL25"),
        ]
        ordered_payments: list[Payment] = []
        for workbook_path, sheet_name, code in payment_sources:
            workbook = LegacyWorkbook(workbook_path)
            try:
                if not workbook.has_sheet(sheet_name):
                    continue
                for row in workbook.iter_rows(sheet_name):
                    admission_number = self._clean_admission(row.get("ADM No"))
                    if not admission_number:
                        continue
                    student = student_map.get(admission_number)
                    if student is None:
                        continue
                    amount = self._parse_money(row.get("Amount"), scaled=True)
                    if amount <= 0:
                        continue
                    legacy_id = (row.get("FeesID") or row.get("ReceiptNo") or "").strip()
                    if not legacy_id:
                        continue
                    reference_number = f"LEGACY-{code}-{legacy_id}"[:100]
                    invoices = sorted(
                        invoice_index.get(admission_number, []),
                        key=lambda inv: (inv.due_date, inv.id),
                    )
                    payment_date = self._payment_datetime(row, invoices)
                    payment_method = (row.get("Mode") or row.get("Source") or "Legacy").strip()[:50] or "Legacy"
                    payment_notes = self._payment_note(workbook_path.name, sheet_name, row)
                    payment, created = Payment.objects.get_or_create(
                        reference_number=reference_number,
                        defaults={
                            "student": student,
                            "amount": amount,
                            "payment_method": payment_method,
                            "notes": payment_notes,
                            "is_active": True,
                        },
                    )
                    if created:
                        payment.payment_date = payment_date
                        payment.save(update_fields=["payment_date"])
                        summary["payments_created"] += 1
                    else:
                        payment_updates = []
                        if payment.student_id != student.id:
                            payment.student = student
                            payment_updates.append("student")
                        if payment.amount != amount:
                            payment.amount = amount
                            payment_updates.append("amount")
                        if payment.payment_method != payment_method:
                            payment.payment_method = payment_method
                            payment_updates.append("payment_method")
                        if payment.notes != payment_notes:
                            payment.notes = payment_notes
                            payment_updates.append("notes")
                        if payment.payment_date != payment_date:
                            payment.payment_date = payment_date
                            payment_updates.append("payment_date")
                        if not payment.is_active:
                            payment.is_active = True
                            payment_updates.append("is_active")
                        if payment_updates:
                            payment.save(update_fields=payment_updates)
                    ordered_payments.append(payment)
            finally:
                workbook.close()

        unique_payments = self._unique_payments(ordered_payments)
        self._allocate_payments(unique_payments, invoice_index, summary)
        return unique_payments

    def _create_placeholder_invoices_for_unallocated_payments(
        self,
        payments: Iterable[Payment],
        summary: dict,
    ) -> dict[str, list[Invoice]]:
        grouped: dict[tuple[str, int, str], dict] = {}
        for payment in self._unique_payments(payments):
            remaining = self._payment_remaining(payment)
            if remaining <= 0:
                continue
            payment_date = payment.payment_date.date()
            year_value = payment_date.year
            term_name = self._term_name_for_date(payment_date)
            key = (payment.student.admission_number, year_value, term_name)
            bucket = grouped.setdefault(
                key,
                {
                    "student": payment.student,
                    "due_date": payment_date,
                    "amount": Decimal("0.00"),
                    "payment_count": 0,
                },
            )
            if payment_date < bucket["due_date"]:
                bucket["due_date"] = payment_date
            bucket["amount"] += remaining
            bucket["payment_count"] += 1

        placeholder_index: dict[str, list[Invoice]] = defaultdict(list)
        for (admission_number, year_value, term_name), payload in grouped.items():
            academic_year = self._ensure_academic_year(year_value)
            term = self._ensure_term(academic_year, term_name)
            invoice_total = payload["amount"].quantize(TWOPLACES)
            term_code = self._term_code(term_name)
            invoice_number = f"LEGACY-PAY-{year_value}-{term_code}-{admission_number}"[:40]
            invoice, created = Invoice.objects.get_or_create(
                invoice_number=invoice_number,
                defaults={
                    "student": payload["student"],
                    "term": term,
                    "total_amount": invoice_total,
                    "due_date": payload["due_date"],
                    "status": "ISSUED",
                    "is_active": True,
                },
            )
            invoice_updates = []
            if invoice.student_id != payload["student"].id:
                invoice.student = payload["student"]
                invoice_updates.append("student")
            if invoice.term_id != term.id:
                invoice.term = term
                invoice_updates.append("term")
            if invoice.total_amount != invoice_total:
                invoice.total_amount = invoice_total
                invoice_updates.append("total_amount")
            if invoice.due_date != payload["due_date"]:
                invoice.due_date = payload["due_date"]
                invoice_updates.append("due_date")
            if invoice.invoice_date != payload["due_date"]:
                invoice.invoice_date = payload["due_date"]
                invoice_updates.append("invoice_date")
            if not invoice.is_active:
                invoice.is_active = True
                invoice_updates.append("is_active")
            if invoice_updates:
                invoice.save(update_fields=invoice_updates)

            fee_structure = self._ensure_fee_structure(
                academic_year=academic_year,
                term=term,
                name="Legacy Placeholder Receivable",
                category="Legacy Placeholder",
            )
            description = (
                f"Legacy placeholder receivable for "
                f"{payload['payment_count']} unmatched payment record(s)"
            )[:255]
            line_item = invoice.line_items.filter(fee_structure=fee_structure).order_by("id").first()
            if line_item is None:
                InvoiceLineItem.objects.create(
                    invoice=invoice,
                    fee_structure=fee_structure,
                    description=description,
                    amount=invoice_total,
                )
            else:
                line_item_updates = []
                if line_item.description != description:
                    line_item.description = description
                    line_item_updates.append("description")
                if line_item.amount != invoice_total:
                    line_item.amount = invoice_total
                    line_item_updates.append("amount")
                if line_item_updates:
                    line_item.save(update_fields=line_item_updates)

            self._sync_invoice_status(invoice)
            if created:
                summary["invoices_created"] += 1
                summary["placeholder_invoices_created"] += 1
            placeholder_index[admission_number].append(invoice)
        return placeholder_index

    def _allocate_payments(
        self,
        payments: Iterable[Payment],
        invoice_index: dict[str, list[Invoice]],
        summary: dict,
        detail_key: str | None = None,
    ) -> None:
        for payment in sorted(self._unique_payments(payments), key=lambda item: (item.payment_date, item.id)):
            remaining = self._payment_remaining(payment)
            if remaining <= 0:
                continue
            invoices = invoice_index.get(payment.student.admission_number, [])
            invoices = sorted(invoices, key=lambda inv: (inv.due_date, inv.id))
            for invoice in invoices:
                balance = invoice.balance_due
                if balance <= 0:
                    continue
                allocate = balance if balance <= remaining else remaining
                _, allocation_created = PaymentAllocation.objects.get_or_create(
                    payment=payment,
                    invoice=invoice,
                    defaults={"amount_allocated": allocate},
                )
                self._sync_invoice_status(invoice)
                if allocation_created:
                    summary["payments_allocated"] += 1
                    if detail_key:
                        summary[detail_key] += 1
                    remaining -= allocate
                if remaining <= 0:
                    break

    def _unique_payments(self, payments: Iterable[Payment]) -> list[Payment]:
        unique: dict[int, Payment] = {}
        for payment in payments:
            unique[payment.id] = payment
        return list(unique.values())

    def _payment_remaining(self, payment: Payment) -> Decimal:
        allocated = payment.allocations.aggregate(total=Sum("amount_allocated"))["total"] or Decimal("0.00")
        return (payment.amount - allocated).quantize(TWOPLACES)

    def _archive_workbooks(self, source_dir: Path) -> int:
        count = 0
        existing = {
            (row.original_name, row.size_bytes)
            for row in MediaFile.objects.filter(module="SETTINGS", file_type="spreadsheet")
        }
        for path in sorted(source_dir.glob("*.xlsx")):
            key = (path.name, path.stat().st_size)
            if key in existing:
                continue
            with path.open("rb") as handle:
                media = MediaFile.objects.create(
                    module="SETTINGS",
                    file_type="spreadsheet",
                    file=File(handle, name=path.name),
                    original_name=path.name,
                    size_bytes=path.stat().st_size,
                    description="Legacy Olom workbook archive",
                )
                media.url = media.file.url if media.file else ""
                media.save(update_fields=["url"])
            count += 1
        return count

    def _ensure_academic_year(self, year_value: int) -> AcademicYear:
        name = str(year_value)
        obj, _ = AcademicYear.objects.get_or_create(
            name=name,
            defaults={
                "start_date": date(year_value, 1, 1),
                "end_date": date(year_value, 12, 31),
                "is_active": year_value >= 2024,
                "is_current": year_value == 2025,
            },
        )
        return obj

    def _ensure_term(self, academic_year: AcademicYear, name: str) -> Term:
        slots = {
            "Term 1": (date(academic_year.start_date.year, 1, 1), date(academic_year.start_date.year, 4, 30)),
            "Term 2": (date(academic_year.start_date.year, 5, 1), date(academic_year.start_date.year, 8, 31)),
            "Term 3": (date(academic_year.start_date.year, 9, 1), date(academic_year.start_date.year, 12, 31)),
        }
        start_date, end_date = slots.get(name, (academic_year.start_date, academic_year.end_date))
        obj, _ = Term.objects.get_or_create(
            academic_year=academic_year,
            name=name,
            defaults={
                "start_date": start_date,
                "end_date": end_date,
                "billing_date": start_date,
                "is_active": True,
                "is_current": academic_year.is_current and name == "Term 2",
            },
        )
        return obj

    def _ensure_grade_level(self, name: str) -> GradeLevel:
        cleaned = name.strip() or "Legacy"
        order = self._grade_order(cleaned)
        obj, _ = GradeLevel.objects.get_or_create(
            name=cleaned,
            defaults={"order": order, "is_active": True},
        )
        if obj.order != order:
            obj.order = order
            obj.save(update_fields=["order"])
        return obj

    def _ensure_fee_structure(self, academic_year: AcademicYear, term: Term, name: str, category: str) -> FeeStructure:
        obj, _ = FeeStructure.objects.get_or_create(
            name=name[:100],
            academic_year=academic_year,
            term=term,
            grade_level=None,
            defaults={
                "category": category[:100],
                "amount": Decimal("0.00"),
                "billing_cycle": "ONCE",
                "is_mandatory": False,
                "description": "Legacy statement import placeholder",
                "is_active": True,
            },
        )
        return obj

    def _statement_description(self, row: dict) -> str:
        vote_name = (row.get("VoteName") or "").strip()
        vote_head = (row.get("VoteHead") or "").strip()
        if vote_name and vote_head:
            return f"{vote_name} - {vote_head}"
        return vote_head or vote_name or "Legacy statement item"

    def _payment_note(self, workbook_name: str, sheet_name: str, row: dict) -> str:
        payload = {
            "source_workbook": workbook_name,
            "source_sheet": sheet_name,
            "legacy_fees_id": row.get("FeesID", ""),
            "legacy_receipt": row.get("ReceiptNo", ""),
            "legacy_mode": row.get("Mode", ""),
            "legacy_source": row.get("Source", ""),
        }
        return json.dumps(payload, sort_keys=True)

    def _payment_datetime(self, row: dict, invoices: list[Invoice]) -> datetime:
        parsed = self._parse_datetime(row.get("Date") or row.get("SlipDate"))
        if parsed:
            return self._aware_datetime(parsed)
        year_hint = self._first_non_none_int(
            self._safe_int(row.get("Acadyear")),
            self._safe_int(row.get("CashBookYear")),
            self._date_part_year(row.get("Date")),
            self._latest_invoice_year(invoices),
        )
        if year_hint is not None:
            return self._aware_datetime(datetime(year_hint, 1, 1))
        if invoices:
            return self._aware_datetime(datetime.combine(invoices[0].due_date, datetime.min.time()))
        return self._aware_datetime(datetime(2025, 1, 1))

    def _aware_datetime(self, value: datetime) -> datetime:
        if timezone.is_naive(value):
            return timezone.make_aware(value, timezone.get_current_timezone())
        return value

    def _term_name_for_date(self, value: date) -> str:
        if value.month <= 4:
            return "Term 1"
        if value.month <= 8:
            return "Term 2"
        return "Term 3"

    def _term_code(self, term_name: str) -> str:
        mapping = {
            "Term 1": "T1",
            "Term 2": "T2",
            "Term 3": "T3",
        }
        return mapping.get(term_name, "TX")

    def _sync_invoice_status(self, invoice: Invoice) -> None:
        balance = invoice.balance_due
        if balance <= 0:
            status_value = "PAID"
        elif balance < invoice.total_amount:
            status_value = "PARTIALLY_PAID"
        else:
            status_value = "ISSUED"
        if invoice.status != status_value:
            invoice.status = status_value
            invoice.save(update_fields=["status"])

    def _split_name(self, full_name: str, admission_number: str) -> tuple[str, str]:
        tokens = [token for token in re.split(r"\s+", (full_name or "").strip()) if token]
        if not tokens:
            return f"Legacy-{admission_number}", "Student"
        if len(tokens) == 1:
            return tokens[0].title(), "Student"
        return tokens[0].title(), " ".join(token.title() for token in tokens[1:])

    def _approximate_dob(self, seed: StudentSeed) -> date:
        base_year = seed.reference_year or 2025
        age_hint = AGE_HINTS.get(seed.grade_label or "", 15)
        return date(max(base_year - age_hint, 1990), 1, 1)

    def _grade_order(self, label: str) -> int:
        cleaned = (label or "").strip()
        if cleaned in GRADE_WORDS.values():
            for key, value in GRADE_WORDS.items():
                if value == cleaned:
                    return int(key)
        digits = re.findall(r"\d+", cleaned)
        if digits:
            return int(digits[0])
        return 999

    def _normalise_grade_label(self, raw_value: str | None) -> str:
        value = (raw_value or "").strip()
        if not value:
            return ""
        value = value.replace("Form ", "").replace("Grade ", "").strip()
        upper = value.upper()
        if upper in {"T1", "T2", "T3"}:
            return ""
        if value in GRADE_WORDS:
            return GRADE_WORDS[value]
        title_value = value.title()
        if title_value in GRADE_WORDS.values():
            return title_value
        return title_value

    def _clean_stream(self, raw_value: str | None) -> str:
        value = (raw_value or "").strip()
        if not value:
            return ""
        if value.isdigit():
            return ""
        return value.title()

    def _normalise_gender(self, raw_value: str | None) -> str:
        value = (raw_value or "").strip().lower()
        if value.startswith("m"):
            return "M"
        if value.startswith("f"):
            return "F"
        return "F"

    def _clean_admission(self, raw_value: str | None) -> str:
        value = (raw_value or "").strip()
        value = value.replace(".0", "") if value.endswith(".0") else value
        return value

    def _normalise_phone(self, raw_value: str | None) -> str:
        value = (raw_value or "").strip()
        if not value:
            return ""
        value = value.replace(" ", "")
        if value.startswith("00"):
            value = "+" + value[2:]
        return value

    def _parse_money(self, raw_value: str | None, *, scaled: bool) -> Decimal:
        raw = (raw_value or "").strip()
        if not raw:
            return Decimal("0.00")
        raw = raw.replace(",", "")
        try:
            amount = Decimal(raw)
        except InvalidOperation:
            return Decimal("0.00")
        if scaled:
            amount = amount / SCALED_DIVISOR
        return amount.quantize(TWOPLACES)

    def _parse_datetime(self, raw_value: str | None) -> datetime | None:
        raw = (raw_value or "").strip()
        if not raw:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None

    def _safe_int(self, raw_value: str | None) -> int | None:
        raw = (raw_value or "").strip()
        if not raw:
            return None
        digits = re.findall(r"\d+", raw)
        if not digits:
            return None
        try:
            return int(digits[0])
        except ValueError:
            return None

    def _first_non_none_int(self, *values: int | None) -> int | None:
        for value in values:
            if value is not None:
                return value
        return None

    def _date_part_year(self, raw_value: str | None) -> int | None:
        parsed = self._parse_datetime(raw_value)
        return parsed.year if parsed else None

    def _latest_invoice_year(self, invoices: Iterable[Invoice]) -> int | None:
        years = [invoice.term.academic_year.start_date.year for invoice in invoices if invoice.term_id]
        return max(years) if years else None

    def _pick_term_name(self, invoices: Iterable[Invoice]) -> str:
        latest = None
        for invoice in invoices:
            if latest is None:
                latest = invoice
                continue
            latest_key = (latest.term.academic_year.start_date, latest.due_date, latest.id)
            invoice_key = (invoice.term.academic_year.start_date, invoice.due_date, invoice.id)
            if invoice_key > latest_key:
                latest = invoice
        return latest.term.name if latest else "Term 2"
