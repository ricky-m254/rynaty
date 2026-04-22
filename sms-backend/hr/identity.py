from __future__ import annotations

import re
from datetime import date

from django.db import connection
from django.utils import timezone

from school.role_scope import iter_seed_role_names


SUPPORTED_ROLE_NAMES = set(iter_seed_role_names())

STAFF_CATEGORY_ALIASES = {
    "TEACHING": "TEACHING",
    "TEACHER": "TEACHING",
    "ACADEMIC": "TEACHING",
    "ACADEMICSTAFF": "TEACHING",
    "ADMIN": "ADMIN",
    "ADMINISTRATIVE": "ADMIN",
    "SUPPORT": "SUPPORT",
    "OPERATIONS": "OPERATIONS",
    "OPERATIONAL": "OPERATIONS",
    "HOSTEL": "HOSTEL",
    "BOARDING": "HOSTEL",
    "SECURITY": "SECURITY",
    "KITCHEN": "KITCHEN",
    "HEALTH": "HEALTH",
    "MEDICAL": "HEALTH",
}


DEFAULT_ONBOARDING_TASKS = (
    {
        "task_code": "profile.personal_details",
        "task": "Complete personal details",
        "blocks_account_provisioning": True,
    },
    {
        "task_code": "profile.employment_profile",
        "task": "Complete employment profile",
        "blocks_account_provisioning": True,
    },
    {
        "task_code": "contacts.emergency_contact",
        "task": "Add primary emergency contact",
        "blocks_account_provisioning": True,
    },
    {
        "task_code": "documents.qualifications",
        "task": "Capture qualifications and certificates",
        "blocks_account_provisioning": True,
    },
    {
        "task_code": "biometric.enrollment",
        "task": "Link biometric identity",
        "blocks_account_provisioning": True,
    },
    {
        "task_code": "access.system_account",
        "task": "Prepare system account",
        "blocks_account_provisioning": True,
    },
    {
        "task_code": "orientation.induction",
        "task": "Schedule induction/orientation",
        "blocks_account_provisioning": False,
    },
    {
        "task_code": "assets.equipment_issuance",
        "task": "Assign workstation/equipment",
        "blocks_account_provisioning": False,
    },
)


def _normalize_key(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def resolve_tenant_code() -> str:
    tenant = getattr(connection, "tenant", None)
    candidates = (
        getattr(tenant, "schema_name", None),
        getattr(tenant, "subdomain", None),
        getattr(tenant, "name", None),
        getattr(connection, "schema_name", None),
    )
    for candidate in candidates:
        normalized = _normalize_key(candidate)
        if normalized and normalized != "PUBLIC":
            return normalized[:8]
    return "TENANT"


def generate_employee_id() -> str:
    from .models import Employee

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


def generate_staff_id() -> str:
    from .models import Employee

    year = timezone.now().year
    tenant_code = resolve_tenant_code()
    prefix = f"STF-{tenant_code}-{year}-"
    last = (
        Employee.objects.filter(staff_id__startswith=prefix)
        .order_by("-staff_id")
        .values_list("staff_id", flat=True)
        .first()
    )
    if not last:
        sequence = 1
    else:
        try:
            sequence = int(last.split("-")[-1]) + 1
        except (TypeError, ValueError, IndexError):
            sequence = Employee.objects.exclude(staff_id="").count() + 1
    return f"{prefix}{sequence:05d}"


def normalize_staff_category(value: str | None) -> str:
    normalized = _normalize_key(value)
    return STAFF_CATEGORY_ALIASES.get(normalized, "")


def infer_staff_category(position_title: str | None, explicit_value: str | None = None) -> str:
    explicit = normalize_staff_category(explicit_value)
    if explicit:
        return explicit

    title = _normalize_key(position_title)
    if not title:
        return ""

    if any(token in title for token in ("PRINCIPAL", "HEADTEACHER", "DEPUTYPRINCIPAL", "HOD", "TEACHER", "ECD")):
        return "TEACHING"
    if any(token in title for token in ("BURSAR", "ACCOUNTANT", "REGISTRAR")):
        return "ADMIN"
    if any(token in title for token in ("LIBRARIAN", "COUNSELLOR", "COUNSELOR", "LABTECHNICIAN", "ICTTECHNICIAN", "SECRETARY")):
        return "SUPPORT"
    if any(token in title for token in ("HOSTEL", "WARDEN", "MATRON", "PATRON", "BOARDING")):
        return "HOSTEL"
    if any(token in title for token in ("SECURITY", "WATCHMAN", "GUARD", "GATEOFFICER")):
        return "SECURITY"
    if any(token in title for token in ("COOK", "CHEF", "KITCHEN")):
        return "KITCHEN"
    if any(token in title for token in ("NURSE", "MEDICAL")):
        return "HEALTH"
    if any(token in title for token in ("DRIVER", "CARETAKER", "CLEANER", "GROUNDSMAN", "MAINTENANCE", "STORE", "STORES")):
        return "OPERATIONS"
    return ""


def suggest_account_role_name(position_title: str | None, staff_category: str | None = None) -> str:
    title = _normalize_key(position_title)
    category = normalize_staff_category(staff_category)

    suggested = ""
    if any(token in title for token in ("HEADTEACHER", "PRINCIPAL")):
        suggested = "PRINCIPAL"
    elif "DEPUTYPRINCIPAL" in title:
        suggested = "DEPUTY_PRINCIPAL"
    elif "HOD" in title or "HEADOFDEPARTMENT" in title:
        suggested = "HOD"
    elif "BURSAR" in title:
        suggested = "BURSAR"
    elif "ACCOUNTANT" in title:
        suggested = "ACCOUNTANT"
    elif "HROFFICER" in title or "HUMANRESOURCE" in title:
        suggested = "HR_OFFICER"
    elif "REGISTRAR" in title:
        suggested = "REGISTRAR"
    elif "SECRETARY" in title:
        suggested = "SECRETARY"
    elif "LIBRARIAN" in title:
        suggested = "LIBRARIAN"
    elif "NURSE" in title or "MEDICALOFFICER" in title:
        suggested = "NURSE"
    elif any(token in title for token in ("SECURITY", "WATCHMAN", "GUARD")):
        suggested = "SECURITY_GUARD"
    elif any(token in title for token in ("COOK", "CHEF", "KITCHEN")):
        suggested = "COOK"
    elif "STORE" in title:
        suggested = "STORE_CLERK"
    elif category == "TEACHING":
        suggested = "TEACHER"

    return suggested if suggested in SUPPORTED_ROLE_NAMES else ""


def ensure_employment_profile(employee):
    from .models import EmployeeEmploymentProfile

    profile, _ = EmployeeEmploymentProfile.objects.get_or_create(employee=employee)
    return profile


def seed_default_onboarding_tasks(employee, *, assigned_to=None, due_date: date | None = None):
    from .models import OnboardingTask

    existing_codes = set(
        OnboardingTask.objects.filter(employee=employee, is_active=True)
        .exclude(task_code="")
        .values_list("task_code", flat=True)
    )
    created = []
    for task_def in DEFAULT_ONBOARDING_TASKS:
        if task_def["task_code"] in existing_codes:
            continue
        created.append(
            OnboardingTask.objects.create(
                employee=employee,
                task_code=task_def["task_code"],
                task=task_def["task"],
                assigned_to=assigned_to,
                due_date=due_date,
                status="Pending",
                is_required=True,
                blocks_account_provisioning=task_def["blocks_account_provisioning"],
                is_active=True,
            )
        )
    return created
