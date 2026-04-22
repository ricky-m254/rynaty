from __future__ import annotations

from django.contrib.auth import get_user_model

from hr.models import Employee
from school.models import Student

from .models import CirculationTransaction, LibraryMember, TeacherClassroomLoan


User = get_user_model()


def member_display_name(member: LibraryMember | None) -> str:
    if not member:
        return ""
    if member.student_id and member.student:
        return f"{member.student.first_name} {member.student.last_name}".strip()
    if member.user_id and member.user:
        return member.user.get_full_name().strip() or member.user.username
    return member.member_id


def ensure_staff_library_member(user: User | None) -> LibraryMember | None:
    if not user:
        return None

    existing = (
        LibraryMember.objects.filter(user=user, member_type="Staff")
        .order_by("-is_active", "-id")
        .first()
    )
    if existing:
        updates: list[str] = []
        if not existing.is_active:
            existing.is_active = True
            updates.append("is_active")
        if existing.status != "Active":
            existing.status = "Active"
            updates.append("status")
        if updates:
            existing.save(update_fields=updates)
        return existing

    employee = Employee.objects.filter(user=user).only("id").order_by("-id").first()
    member_code = f"LIB-HR-{employee.id}" if employee else f"LIB-USR-{user.id}"
    member, _ = LibraryMember.objects.get_or_create(
        member_id=member_code,
        defaults={
            "member_type": "Staff",
            "status": "Active",
            "user": user,
            "is_active": True,
        },
    )
    updates: list[str] = []
    if member.user_id != user.id:
        member.user = user
        updates.append("user")
    if member.member_type != "Staff":
        member.member_type = "Staff"
        updates.append("member_type")
    if member.status != "Active":
        member.status = "Active"
        updates.append("status")
    if not member.is_active:
        member.is_active = True
        updates.append("is_active")
    if updates:
        member.save(update_fields=updates)
    return member


def ensure_student_library_member(student: Student | None) -> LibraryMember | None:
    if not student:
        return None

    member_code = f"LIB-STU-{student.id}"
    member = (
        LibraryMember.objects.filter(student=student).first()
        or LibraryMember.objects.filter(member_id=member_code).first()
    )
    if member is None:
        return LibraryMember.objects.create(
            member_id=member_code,
            member_type="Student",
            status="Active",
            student=student,
            is_active=True,
        )

    updates: list[str] = []
    if member.student_id != student.id:
        member.student = student
        updates.append("student")
    if member.member_type != "Student":
        member.member_type = "Student"
        updates.append("member_type")
    if member.status != "Active":
        member.status = "Active"
        updates.append("status")
    if not member.is_active:
        member.is_active = True
        updates.append("is_active")
    if updates:
        member.save(update_fields=updates)
    return member


def get_active_classroom_loan(copy_id: int) -> TeacherClassroomLoan | None:
    return (
        TeacherClassroomLoan.objects.select_related(
            "copy",
            "copy__resource",
            "teacher_member",
            "teacher_member__user",
            "teacher_member__student",
            "student_member",
            "student_member__user",
            "student_member__student",
        )
        .filter(copy_id=copy_id, return_date__isnull=True, is_active=True)
        .order_by("-issue_date", "-id")
        .first()
    )


def get_active_teacher_transaction(
    *,
    copy_id: int,
    teacher_member: LibraryMember | None = None,
) -> CirculationTransaction | None:
    queryset = (
        CirculationTransaction.objects.select_related(
            "copy",
            "copy__resource",
            "member",
            "member__user",
            "member__student",
        )
        .filter(
            copy_id=copy_id,
            transaction_type="Issue",
            return_date__isnull=True,
            is_active=True,
            member__member_type="Staff",
        )
        .order_by("-issue_date", "-id")
    )
    if teacher_member is not None:
        queryset = queryset.filter(member=teacher_member)
    return queryset.first()


def serialize_classroom_loan(loan: TeacherClassroomLoan) -> dict:
    return {
        "id": loan.id,
        "teacher_transaction_id": loan.teacher_transaction_id,
        "copy_id": loan.copy_id,
        "copy_accession_number": loan.copy.accession_number if loan.copy_id else "",
        "resource_id": loan.copy.resource_id if loan.copy_id else None,
        "resource_title": loan.copy.resource.title if loan.copy_id else "",
        "teacher_member_id": loan.teacher_member_id,
        "teacher_member_code": loan.teacher_member.member_id if loan.teacher_member_id else "",
        "teacher_name": member_display_name(loan.teacher_member),
        "student_member_id": loan.student_member_id,
        "student_member_code": loan.student_member.member_id if loan.student_member_id else "",
        "student_id": loan.student_member.student_id if loan.student_member_id else None,
        "student_name": member_display_name(loan.student_member),
        "issue_date": loan.issue_date,
        "due_date": loan.due_date,
        "return_date": loan.return_date,
        "return_destination": loan.return_destination,
        "notes": loan.notes,
    }


def get_copy_custody_snapshot(copy) -> dict:
    teacher_txn = get_active_teacher_transaction(copy_id=copy.id)
    if teacher_txn is None:
        return {
            "holder_type": "library",
            "holder_name": "Library",
            "teacher_transaction_id": None,
            "classroom_loan_id": None,
            "teacher_member_id": None,
            "teacher_name": "",
            "student_member_id": None,
            "student_id": None,
            "student_name": "",
        }

    active_loan = get_active_classroom_loan(copy.id)
    if active_loan is None:
        return {
            "holder_type": "teacher",
            "holder_name": member_display_name(teacher_txn.member),
            "teacher_transaction_id": teacher_txn.id,
            "classroom_loan_id": None,
            "teacher_member_id": teacher_txn.member_id,
            "teacher_name": member_display_name(teacher_txn.member),
            "student_member_id": None,
            "student_id": None,
            "student_name": "",
        }

    return {
        "holder_type": "student",
        "holder_name": member_display_name(active_loan.student_member),
        "teacher_transaction_id": teacher_txn.id,
        "classroom_loan_id": active_loan.id,
        "teacher_member_id": active_loan.teacher_member_id,
        "teacher_name": member_display_name(active_loan.teacher_member),
        "student_member_id": active_loan.student_member_id,
        "student_id": active_loan.student_member.student_id if active_loan.student_member_id else None,
        "student_name": member_display_name(active_loan.student_member),
        "student_due_date": active_loan.due_date,
    }
