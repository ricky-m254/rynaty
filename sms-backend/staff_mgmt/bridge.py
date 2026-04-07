from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from hr.models import AttendanceRecord as HrAttendanceRecord
from hr.models import Department as HrDepartment
from hr.models import Employee
from school.models import Department as SchoolDepartment

from .models import StaffAssignment, StaffAttendance, StaffDepartment, StaffMember


STAFF_TO_HR_EMPLOYMENT_TYPE = {
    "Full-time": "Full-time",
    "Part-time": "Part-time",
    "Contract": "Contract",
    "Visiting": "Temporary",
}

STAFF_TO_HR_STATUS = {
    "Active": "Active",
    "On Leave": "On Leave",
    "Suspended": "Suspended",
    "Resigned": "Terminated",
    "Retired": "Retired",
}


def generate_employee_id() -> str:
    year = timezone.now().year
    prefix = f"EMP-{year}-"
    last = (
        Employee.objects.filter(employee_id__startswith=prefix)
        .order_by("-employee_id")
        .values_list("employee_id", flat=True)
        .first()
    )
    if not last:
        sequence = 1
    else:
        try:
            sequence = int(last.split("-")[-1]) + 1
        except (TypeError, ValueError, IndexError):
            sequence = Employee.objects.count() + 1
    return f"{prefix}{sequence:03d}"


def _normalize_name(value: str) -> str:
    return "".join(char for char in (value or "").lower() if char.isalnum())


def _map_employment_type(value: str) -> str:
    return STAFF_TO_HR_EMPLOYMENT_TYPE.get(value, "Full-time")


def _map_status(value: str) -> str:
    return STAFF_TO_HR_STATUS.get(value, "Active")


def _calculate_hours_worked(clock_in, clock_out) -> Decimal:
    if not clock_in or not clock_out:
        return Decimal("0.00")
    start = datetime.combine(timezone.now().date(), clock_in)
    end = datetime.combine(timezone.now().date(), clock_out)
    seconds = max(0, int((end - start).total_seconds()))
    hours = (Decimal(seconds) / Decimal("3600")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return hours


def _candidate_employee_qs(staff_member: StaffMember):
    queryset = Employee.objects.all()
    if staff_member.user_id:
        user_matches = queryset.filter(user_id=staff_member.user_id)
        if user_matches.count() == 1:
            return user_matches
    if staff_member.staff_id:
        employee_id_matches = queryset.filter(employee_id=staff_member.staff_id)
        if employee_id_matches.count() == 1:
            return employee_id_matches
    name_matches = queryset.filter(
        first_name__iexact=staff_member.first_name,
        last_name__iexact=staff_member.last_name,
    )
    if staff_member.middle_name:
        name_matches = name_matches.filter(middle_name__iexact=staff_member.middle_name)
    if staff_member.join_date:
        name_matches = name_matches.filter(join_date=staff_member.join_date)
    if staff_member.date_of_birth:
        name_matches = name_matches.filter(date_of_birth=staff_member.date_of_birth)
    return name_matches


def _find_matching_employee(staff_member: StaffMember) -> Employee | None:
    if staff_member.hr_employee_id:
        return staff_member.hr_employee
    candidates = list(_candidate_employee_qs(staff_member)[:2])
    if len(candidates) != 1:
        return None
    candidate = candidates[0]
    profile = getattr(candidate, "staff_mgmt_profile", None)
    if profile and profile.pk != staff_member.pk:
        return None
    return candidate


def _find_matching_hr_department(staff_department: StaffDepartment) -> HrDepartment | None:
    if staff_department.hr_department_id:
        return staff_department.hr_department
    if staff_department.code:
        exact_code = HrDepartment.objects.filter(code=staff_department.code)
        if exact_code.count() == 1:
            candidate = exact_code.first()
            profile = getattr(candidate, "staff_mgmt_profile", None)
            if not profile or profile.pk == staff_department.pk:
                return candidate
    normalized_name = _normalize_name(staff_department.name)
    if not normalized_name:
        return None
    candidates = [
        department
        for department in HrDepartment.objects.all().select_related("staff_mgmt_profile")
        if _normalize_name(department.name) == normalized_name
    ]
    if len(candidates) != 1:
        return None
    candidate = candidates[0]
    profile = getattr(candidate, "staff_mgmt_profile", None)
    if profile and profile.pk != staff_department.pk:
        return None
    return candidate


def ensure_school_department_shadow(hr_department: HrDepartment) -> SchoolDepartment:
    school_department = hr_department.school_department
    target_name = (hr_department.name or "").strip()
    head_user = hr_department.head.user if hr_department.head and hr_department.head.user_id else None

    if school_department is None:
        school_department = (
            SchoolDepartment.objects.filter(name__iexact=target_name, hr_department_profile__isnull=True).first()
            if target_name
            else None
        )
        if school_department is None:
            school_department = SchoolDepartment.objects.create(
                name=target_name or hr_department.code,
                description=hr_department.description or "",
                head=head_user,
                is_active=hr_department.is_active,
            )

    update_fields = []
    if target_name and school_department.name != target_name:
        collision = SchoolDepartment.objects.filter(name__iexact=target_name).exclude(pk=school_department.pk).exists()
        if not collision:
            school_department.name = target_name
            update_fields.append("name")
    if school_department.description != (hr_department.description or ""):
        school_department.description = hr_department.description or ""
        update_fields.append("description")
    if school_department.head_id != (head_user.id if head_user else None):
        school_department.head = head_user
        update_fields.append("head")
    if school_department.is_active != hr_department.is_active:
        school_department.is_active = hr_department.is_active
        update_fields.append("is_active")
    if update_fields:
        school_department.save(update_fields=update_fields)

    if hr_department.school_department_id != school_department.id:
        hr_department.school_department = school_department
        hr_department.save(update_fields=["school_department"])

    return school_department


def _preferred_assignment(staff_member: StaffMember) -> StaffAssignment | None:
    return (
        StaffAssignment.objects.filter(staff=staff_member, is_active=True)
        .select_related("department__hr_department__school_department")
        .order_by("-is_primary", "-effective_from", "-id")
        .first()
    )


@transaction.atomic
def sync_staff_department_to_hr(staff_department: StaffDepartment, sync_head: bool = True) -> HrDepartment:
    if staff_department.parent_id and not staff_department.parent.hr_department_id:
        sync_staff_department_to_hr(staff_department.parent, sync_head=False)

    hr_department = _find_matching_hr_department(staff_department) or HrDepartment()
    if not hr_department.pk:
        hr_department.code = staff_department.code
    hr_department.name = staff_department.name
    hr_department.code = staff_department.code
    hr_department.description = staff_department.description or ""
    hr_department.is_active = staff_department.is_active
    hr_department.parent = staff_department.parent.hr_department if staff_department.parent_id and staff_department.parent.hr_department_id else None

    if sync_head and staff_department.head_id:
        hr_department.head = sync_staff_member_to_hr(staff_department.head, sync_department=False)
    elif sync_head:
        hr_department.head = None

    hr_department.save()
    ensure_school_department_shadow(hr_department)

    if staff_department.hr_department_id != hr_department.id:
        staff_department.hr_department = hr_department
        staff_department.save(update_fields=["hr_department"])

    return hr_department


def refresh_staff_member_department(staff_member: StaffMember) -> Employee | None:
    if not staff_member.hr_employee_id:
        return None
    employee = staff_member.hr_employee
    assignment = _preferred_assignment(staff_member)
    hr_department = None
    if assignment:
        hr_department = sync_staff_department_to_hr(assignment.department, sync_head=False)
    if employee.department_id != (hr_department.id if hr_department else None):
        employee.department = hr_department
        employee.save(update_fields=["department"])
    return employee


@transaction.atomic
def sync_staff_member_to_hr(staff_member: StaffMember, sync_department: bool = True) -> Employee:
    employee = _find_matching_employee(staff_member) or Employee(employee_id=generate_employee_id())
    employee.user = staff_member.user
    employee.first_name = staff_member.first_name
    employee.middle_name = staff_member.middle_name
    employee.last_name = staff_member.last_name
    employee.date_of_birth = staff_member.date_of_birth
    employee.gender = staff_member.gender or "Other"
    employee.nationality = staff_member.nationality or ""
    if staff_member.photo:
        employee.photo = staff_member.photo
    employee.employment_type = _map_employment_type(staff_member.employment_type)
    employee.status = _map_status(staff_member.status)
    employee.join_date = staff_member.join_date
    employee.exit_date = staff_member.exit_date
    employee.is_active = staff_member.is_active
    employee.save()

    if staff_member.hr_employee_id != employee.id:
        staff_member.hr_employee = employee
        staff_member.save(update_fields=["hr_employee"])

    if sync_department:
        refresh_staff_member_department(staff_member)

    return employee


@transaction.atomic
def sync_staff_assignment_to_hr(assignment: StaffAssignment) -> tuple[Employee, HrDepartment]:
    employee = sync_staff_member_to_hr(assignment.staff, sync_department=False)
    hr_department = sync_staff_department_to_hr(assignment.department)
    if assignment.is_active:
        refresh_staff_member_department(assignment.staff)
    return employee, hr_department


@transaction.atomic
def sync_staff_attendance_to_hr(staff_attendance: StaffAttendance, recorded_by=None) -> HrAttendanceRecord:
    employee = sync_staff_member_to_hr(staff_attendance.staff)
    hr_defaults = {
        "status": staff_attendance.status,
        "clock_in": staff_attendance.clock_in,
        "clock_out": staff_attendance.clock_out,
        "hours_worked": _calculate_hours_worked(staff_attendance.clock_in, staff_attendance.clock_out),
        "overtime_hours": Decimal("0.00"),
        "notes": staff_attendance.notes or "",
        "recorded_by": recorded_by or staff_attendance.marked_by,
        "is_active": staff_attendance.is_active,
    }
    hr_attendance, _ = HrAttendanceRecord.objects.update_or_create(
        employee=employee,
        date=staff_attendance.date,
        defaults=hr_defaults,
    )

    update_fields = []
    if staff_attendance.hr_attendance_id != hr_attendance.id:
        staff_attendance.hr_attendance = hr_attendance
        update_fields.append("hr_attendance")
    if recorded_by and staff_attendance.marked_by_id != recorded_by.id:
        staff_attendance.marked_by = recorded_by
        update_fields.append("marked_by")
    if update_fields:
        staff_attendance.save(update_fields=update_fields)

    return hr_attendance


@transaction.atomic
def upsert_staff_attendance(staff_member: StaffMember, date_value, defaults: dict, recorded_by=None) -> tuple[StaffAttendance, bool]:
    attendance, was_created = StaffAttendance.objects.update_or_create(
        staff=staff_member,
        date=date_value,
        defaults={
            **defaults,
            "marked_by": recorded_by,
            "is_active": True,
        },
    )
    sync_staff_attendance_to_hr(attendance, recorded_by=recorded_by)
    return attendance, was_created


def reconciliation_snapshot(limit: int = 25) -> dict:
    unmapped_staff_qs = StaffMember.objects.filter(is_active=True, hr_employee__isnull=True).order_by("staff_id", "id")
    unmapped_department_qs = StaffDepartment.objects.filter(is_active=True, hr_department__isnull=True).order_by("name", "id")
    unmapped_attendance_qs = StaffAttendance.objects.filter(is_active=True, hr_attendance__isnull=True).order_by("-date", "-id")

    duplicate_staff_candidates = []
    for staff_member in StaffMember.objects.filter(is_active=True).order_by("staff_id", "id")[: limit * 4]:
        candidates = _candidate_employee_qs(staff_member)
        candidate_ids = list(candidates.values_list("id", flat=True)[:3])
        if len(candidate_ids) > 1:
            duplicate_staff_candidates.append(
                {
                    "staff": staff_member.id,
                    "staff_id": staff_member.staff_id,
                    "candidate_employee_ids": candidate_ids,
                }
            )
        if len(duplicate_staff_candidates) >= limit:
            break

    duplicate_department_candidates = []
    hr_departments = list(HrDepartment.objects.all())
    for staff_department in StaffDepartment.objects.filter(is_active=True).order_by("name", "id")[: limit * 4]:
        candidates = []
        if staff_department.code:
            candidates = list(HrDepartment.objects.filter(code=staff_department.code).values_list("id", flat=True)[:3])
        if len(candidates) <= 1:
            normalized_name = _normalize_name(staff_department.name)
            candidates = [
                department.id
                for department in hr_departments
                if normalized_name and _normalize_name(department.name) == normalized_name
            ][:3]
        if len(candidates) > 1:
            duplicate_department_candidates.append(
                {
                    "department": staff_department.id,
                    "code": staff_department.code,
                    "candidate_department_ids": candidates,
                }
            )
        if len(duplicate_department_candidates) >= limit:
            break

    return {
        "unmapped_staff_members": {
            "count": unmapped_staff_qs.count(),
            "rows": list(unmapped_staff_qs.values("id", "staff_id", "first_name", "last_name")[:limit]),
        },
        "unmapped_departments": {
            "count": unmapped_department_qs.count(),
            "rows": list(unmapped_department_qs.values("id", "name", "code")[:limit]),
        },
        "unmapped_attendance": {
            "count": unmapped_attendance_qs.count(),
            "rows": list(unmapped_attendance_qs.values("id", "staff_id", "date", "status")[:limit]),
        },
        "duplicate_staff_candidates": duplicate_staff_candidates,
        "duplicate_department_candidates": duplicate_department_candidates,
        "legacy_attendance_without_canonical_hr_record": unmapped_attendance_qs.count(),
    }
