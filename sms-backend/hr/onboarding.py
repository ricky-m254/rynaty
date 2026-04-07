from __future__ import annotations

from typing import Iterable

from .models import EmergencyContact, Employee, EmployeeQualification, OnboardingTask


REQUIRED_IDENTITY_FIELDS: tuple[tuple[str, str], ...] = (
    ("staff_id", "staff_id"),
    ("first_name", "first_name"),
    ("last_name", "last_name"),
    ("staff_category", "staff_category"),
)
REQUIRED_EMPLOYMENT_PROFILE_FIELDS: tuple[tuple[str, str], ...] = (
    ("kra_pin", "kra_pin"),
    ("nhif_number", "nhif_number"),
    ("nssf_number", "nssf_number"),
)
RECOMMENDED_EMPLOYMENT_PROFILE_FIELDS: tuple[tuple[str, str], ...] = (
    ("bank_name", "bank_name"),
    ("bank_account_number", "bank_account_number"),
)
AUTO_READINESS_TASK_MAP = {
    "profile.personal_details": "identity",
    "profile.employment_profile": "employment_profile",
    "contacts.emergency_contact": "emergency_contact",
    "documents.qualifications": "qualifications",
    "biometric.enrollment": "biometric",
    "access.system_account": "account_provisioned",
}
PROVISIONING_ACTION_TASK_CODES = {"access.system_account"}


def _missing_fields(instance, required_fields: Iterable[tuple[str, str]]) -> list[str]:
    missing: list[str] = []
    for attribute_name, label in required_fields:
        value = getattr(instance, attribute_name, None)
        if value in (None, "", []):
            missing.append(label)
    return missing


def get_employee_biometric_record(employee: Employee):
    from clockin.models import PersonRegistry

    return (
        PersonRegistry.objects.filter(employee=employee, is_active=True)
        .order_by("-enrolled_at", "-id")
        .first()
    )


def biometric_record_is_linked(biometric) -> bool:
    return bool(
        biometric
        and any(
            [
                getattr(biometric, "fingerprint_id", ""),
                getattr(biometric, "card_no", ""),
                getattr(biometric, "dahua_user_id", ""),
            ]
        )
    )


def compute_onboarding_summary(employee: Employee) -> dict:
    try:
        employment_profile = employee.employment_profile
    except employee._meta.get_field("employment_profile").related_model.DoesNotExist:
        employment_profile = None

    identity_missing = _missing_fields(employee, REQUIRED_IDENTITY_FIELDS)
    identity_complete = not identity_missing

    employment_missing = []
    employment_recommended_missing = []
    if employment_profile is None:
        employment_missing = [label for _, label in REQUIRED_EMPLOYMENT_PROFILE_FIELDS]
        employment_recommended_missing = [label for _, label in RECOMMENDED_EMPLOYMENT_PROFILE_FIELDS]
    else:
        employment_missing = _missing_fields(employment_profile, REQUIRED_EMPLOYMENT_PROFILE_FIELDS)
        employment_recommended_missing = _missing_fields(
            employment_profile,
            RECOMMENDED_EMPLOYMENT_PROFILE_FIELDS,
        )
    employment_complete = not employment_missing

    active_contacts = EmergencyContact.objects.filter(employee=employee, is_active=True)
    primary_contact = active_contacts.filter(is_primary=True).first()
    emergency_contact_complete = primary_contact is not None

    qualifications = EmployeeQualification.objects.filter(employee=employee, is_active=True).order_by(
        "-is_primary",
        "-year_obtained",
        "-id",
    )
    qualification_complete = qualifications.exists()
    primary_qualification = qualifications.filter(is_primary=True).first() or qualifications.first()

    biometric = get_employee_biometric_record(employee)
    biometric_complete = biometric_record_is_linked(biometric)

    role_name = (employee.account_role_name or "").strip().upper()
    role_complete = bool(role_name)

    blocking_tasks = list(
        OnboardingTask.objects.filter(
            employee=employee,
            is_active=True,
            blocks_account_provisioning=True,
        )
        .exclude(status="Completed")
        .exclude(task_code__in=PROVISIONING_ACTION_TASK_CODES)
        .order_by("due_date", "id")
    )
    blockers: list[dict] = []
    if not identity_complete:
        blockers.append(
            {
                "code": "identity.incomplete",
                "message": "Complete the required staff identity fields.",
                "fields": identity_missing,
            }
        )
    if not employment_complete:
        blockers.append(
            {
                "code": "employment_profile.incomplete",
                "message": "Complete the required statutory employment profile fields.",
                "fields": employment_missing,
            }
        )
    if not emergency_contact_complete:
        blockers.append(
            {
                "code": "emergency_contact.missing_primary",
                "message": "Add at least one active primary emergency contact.",
                "fields": ["primary_emergency_contact"],
            }
        )
    if not qualification_complete:
        blockers.append(
            {
                "code": "qualifications.missing",
                "message": "Add at least one active qualification record.",
                "fields": ["qualifications"],
            }
        )
    if not biometric_complete:
        blockers.append(
            {
                "code": "biometric.missing",
                "message": "Link an active biometric identity before provisioning.",
                "fields": ["biometric_link"],
            }
        )
    if not role_complete:
        blockers.append(
            {
                "code": "role_selection.missing",
                "message": "Select the account role to provision for this staff member.",
                "fields": ["account_role_name"],
            }
        )
    if employee.user_id:
        blockers.append(
            {
                "code": "account.already_provisioned",
                "message": "This employee already has a linked user account.",
                "fields": ["user"],
            }
        )

    task_ready_map = {
        "identity": identity_complete,
        "employment_profile": employment_complete,
        "emergency_contact": emergency_contact_complete,
        "qualifications": qualification_complete,
        "biometric": biometric_complete,
        "account_provisioned": bool(employee.user_id or employee.account_provisioned_at),
    }

    return {
        "employee_id": employee.id,
        "staff_id": employee.staff_id,
        "onboarding_status": employee.onboarding_status,
        "suggested_onboarding_status": determine_onboarding_status(employee, blockers=blockers),
        "identity": {
            "is_complete": identity_complete,
            "missing_fields": identity_missing,
        },
        "employment_profile": {
            "id": employment_profile.id if employment_profile else None,
            "is_complete": employment_complete,
            "missing_fields": employment_missing,
            "recommended_missing_fields": employment_recommended_missing,
        },
        "emergency_contacts": {
            "count": active_contacts.count(),
            "has_primary": emergency_contact_complete,
            "primary_contact_id": primary_contact.id if primary_contact else None,
        },
        "qualifications": {
            "count": qualifications.count(),
            "is_complete": qualification_complete,
            "primary_qualification_id": primary_qualification.id if primary_qualification else None,
        },
        "biometric": {
            "is_linked": biometric_complete,
            "registry_id": biometric.id if biometric else None,
            "fingerprint_id": biometric.fingerprint_id if biometric else "",
            "card_no": biometric.card_no if biometric else "",
            "dahua_user_id": biometric.dahua_user_id if biometric else "",
            "enrolled_at": biometric.enrolled_at if biometric else None,
        },
        "role_selection": {
            "is_complete": role_complete,
            "role_name": role_name,
        },
        "task_summary": {
            "total": employee.onboarding_tasks.filter(is_active=True).count(),
            "completed": employee.onboarding_tasks.filter(is_active=True, status="Completed").count(),
            "blocking_pending": len(blocking_tasks),
            "blocking_tasks": [
                {
                    "id": task.id,
                    "task_code": task.task_code,
                    "task": task.task,
                    "status": task.status,
                    "due_date": task.due_date,
                    "is_auto_ready": task_ready_map.get(task.task_code),
                }
                for task in blocking_tasks
            ],
        },
        "blockers": blockers,
        "can_provision_account": not blockers,
    }


def determine_onboarding_status(employee: Employee, *, blockers: list[dict] | None = None) -> str:
    if employee.user_id or employee.account_provisioned_at:
        return "PROVISIONED"
    if blockers is None:
        blockers = compute_onboarding_summary(employee)["blockers"]
    if not blockers:
        return "READY_FOR_PROVISIONING"
    has_checklist = employee.onboarding_tasks.filter(is_active=True).exists()
    if has_checklist or employee.onboarding_status != "PENDING":
        return "IN_PROGRESS"
    return "PENDING"


def sync_onboarding_status(employee: Employee, *, summary: dict | None = None) -> str:
    summary = summary or compute_onboarding_summary(employee)
    target_status = summary.get("suggested_onboarding_status") or determine_onboarding_status(
        employee,
        blockers=summary.get("blockers", []),
    )

    task_updates = []
    for task in employee.onboarding_tasks.filter(is_active=True):
        readiness_key = AUTO_READINESS_TASK_MAP.get(task.task_code)
        if readiness_key is None:
            continue

        should_complete = False
        if readiness_key == "account_provisioned":
            should_complete = bool(employee.user_id or employee.account_provisioned_at)
        else:
            section = summary.get(readiness_key, {})
            if isinstance(section, dict):
                should_complete = bool(
                    section.get("is_complete")
                    or section.get("has_primary")
                    or section.get("is_linked")
                )

        if should_complete and task.status != "Completed":
            task.status = "Completed"
            task.completed_at = employee.account_provisioned_at or task.completed_at
            if task.completed_at is None:
                from django.utils import timezone

                task.completed_at = timezone.now()
            task.save(update_fields=["status", "completed_at"])
            task_updates.append(task.task_code)
        elif not should_complete and task.status == "Completed":
            task.status = "Pending"
            task.completed_at = None
            task.save(update_fields=["status", "completed_at"])
            task_updates.append(task.task_code)

    if employee.onboarding_status != target_status:
        employee.onboarding_status = target_status
        employee.save(update_fields=["onboarding_status"])

    return target_status
