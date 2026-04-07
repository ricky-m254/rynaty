from decimal import Decimal, InvalidOperation

from django.db import models

from school.models import (
    Enrollment,
    FeeAssignment,
    FeeStructure,
    OptionalCharge,
    SchoolClass,
    StudentOptionalCharge,
)
from school.services import FinanceService


def get_fee_structure_queryset(search=None, category=None, is_active=None):
    queryset = FeeStructure.objects.all().select_related("academic_year", "term", "grade_level")

    if search:
        queryset = queryset.filter(name__icontains=search)
    if category:
        queryset = queryset.filter(category__iexact=category)
    if is_active is not None:
        normalized = str(is_active).lower()
        if normalized in ("true", "1"):
            queryset = queryset.filter(is_active=True)
        elif normalized in ("false", "0"):
            queryset = queryset.filter(is_active=False)

    return queryset.order_by("-id")


def get_fee_assignment_queryset(search=None, student=None, fee_structure=None, is_active=None):
    queryset = FeeAssignment.objects.all().select_related("student", "fee_structure")

    if search:
        queryset = queryset.filter(
            models.Q(student__first_name__icontains=search)
            | models.Q(student__last_name__icontains=search)
            | models.Q(student__admission_number__icontains=search)
            | models.Q(fee_structure__name__icontains=search)
        )
    if student:
        queryset = queryset.filter(student_id=student)
    if fee_structure:
        queryset = queryset.filter(fee_structure_id=fee_structure)
    if is_active is not None:
        normalized = str(is_active).lower()
        if normalized in ("true", "1"):
            queryset = queryset.filter(is_active=True)
        elif normalized in ("false", "0"):
            queryset = queryset.filter(is_active=False)

    return queryset.order_by("-id")


def create_fee_assignment(validated_data, user):
    assignment = FinanceService.assign_fee(
        student=validated_data["student"],
        fee_structure=validated_data["fee_structure"],
        discount_amount=validated_data.get("discount_amount", 0),
        user=user,
    )
    assignment.start_date = validated_data.get("start_date")
    assignment.end_date = validated_data.get("end_date")
    assignment.is_active = validated_data.get("is_active", True)
    assignment.save(update_fields=["start_date", "end_date", "is_active"])
    return assignment


def get_optional_charge_queryset(category=None, is_active=None):
    queryset = OptionalCharge.objects.all().select_related("academic_year", "term")

    if category:
        queryset = queryset.filter(category=category)
    if is_active is not None:
        normalized = str(is_active).lower()
        queryset = queryset.filter(is_active=(normalized in ("true", "1")))

    return queryset


def get_student_optional_charge_queryset(student=None, optional_charge=None, is_paid=None):
    queryset = StudentOptionalCharge.objects.all().select_related("student", "optional_charge")

    if student:
        queryset = queryset.filter(student_id=student)
    if optional_charge:
        queryset = queryset.filter(optional_charge_id=optional_charge)
    if is_paid is not None:
        normalized = str(is_paid).lower()
        queryset = queryset.filter(is_paid=(normalized in ("true", "1")))

    return queryset


def assign_fee_structure_to_class(*, class_id, fee_structure_id, term_id=None, discount_amount=0):
    if not class_id:
        raise ValueError("class_id is required.")
    if not fee_structure_id:
        raise ValueError("fee_structure_id is required.")

    school_class = SchoolClass.objects.filter(id=class_id).first()
    if school_class is None:
        raise LookupError("Class not found.")

    fee_structure = FeeStructure.objects.filter(id=fee_structure_id).first()
    if fee_structure is None:
        raise LookupError("Fee structure not found.")

    try:
        discount = Decimal(str(discount_amount or 0))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("discount_amount must be a number.")

    enrollments = Enrollment.objects.filter(school_class_id=school_class.id, is_active=True)
    if term_id:
        enrollments = enrollments.filter(term_id=term_id)

    student_ids = list(enrollments.values_list("student_id", flat=True).distinct())
    if not student_ids:
        return {
            "created": 0,
            "updated": 0,
            "student_count": 0,
            "message": "No enrolled students found in this class/term combination.",
        }

    created_count = 0
    updated_count = 0
    for student_id in student_ids:
        existing = FeeAssignment.objects.filter(
            student_id=student_id,
            fee_structure=fee_structure,
            is_active=True,
        ).first()
        if existing:
            existing.discount_amount = discount
            existing.save(update_fields=["discount_amount"])
            updated_count += 1
        else:
            FeeAssignment.objects.create(
                student_id=student_id,
                fee_structure=fee_structure,
                discount_amount=discount,
                is_active=True,
            )
            created_count += 1

    return {
        "created": created_count,
        "updated": updated_count,
        "student_count": len(student_ids),
        "class_name": school_class.display_name,
        "fee_structure": fee_structure.name,
        "message": f'Assigned "{fee_structure.name}" to {len(student_ids)} students in {school_class.display_name}.',
    }


def assign_optional_charge_to_class(*, class_id, optional_charge_id, term_id=None):
    if not class_id:
        raise ValueError("class_id is required.")
    if not optional_charge_id:
        raise ValueError("optional_charge_id is required.")

    school_class = SchoolClass.objects.filter(id=class_id).first()
    if school_class is None:
        raise LookupError("Class not found.")

    optional_charge = OptionalCharge.objects.filter(id=optional_charge_id).first()
    if optional_charge is None:
        raise LookupError("Optional charge not found.")

    enrollments = Enrollment.objects.filter(school_class_id=school_class.id, is_active=True)
    if term_id:
        enrollments = enrollments.filter(term_id=term_id)

    student_ids = list(enrollments.values_list("student_id", flat=True).distinct())
    if not student_ids:
        return {
            "created": 0,
            "skipped": 0,
            "student_count": 0,
            "message": "No enrolled students found in this class.",
        }

    created_count = 0
    skipped_count = 0
    for student_id in student_ids:
        _, created = StudentOptionalCharge.objects.get_or_create(
            student_id=student_id,
            optional_charge=optional_charge,
        )
        if created:
            created_count += 1
        else:
            skipped_count += 1

    return {
        "created": created_count,
        "skipped": skipped_count,
        "student_count": len(student_ids),
        "message": f"Assigned to {created_count} new students ({skipped_count} already had this charge).",
    }
