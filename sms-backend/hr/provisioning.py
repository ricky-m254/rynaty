from __future__ import annotations

import secrets
import string

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from clockin.models import PersonRegistry
from communication.services import send_email_placeholder
from school.models import Role, UserProfile
from school.role_scope import (
    ROLE_SEED_DESCRIPTION_MAP,
    materialize_role_module_baseline,
    normalize_role_name,
)

from .onboarding import compute_onboarding_summary, sync_onboarding_status


User = get_user_model()


def _employee_display_name(employee) -> str:
    return " ".join(
        part for part in [employee.first_name, employee.middle_name, employee.last_name] if part
    ).strip()


def _employee_person_type(employee) -> str:
    return "TEACHER" if employee.staff_category == "TEACHING" else "STAFF"


def _generate_temporary_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _normalize_username(username: str | None) -> str:
    return str(username or "").strip()


def _resolve_login_username(employee, username: str | None = None) -> str:
    explicit_username = _normalize_username(username)
    if explicit_username:
        return explicit_username
    if employee.work_email:
        return employee.work_email.strip().lower()
    return str(employee.staff_id or employee.employee_id or "").strip().lower()


def _ensure_unique_login_identity(employee, username: str) -> None:
    if not username:
        raise serializers.ValidationError({"username": "A username could not be resolved for this employee."})

    username_conflict = User.objects.filter(username__iexact=username)
    if employee.user_id:
        username_conflict = username_conflict.exclude(pk=employee.user_id)
    if username_conflict.exists():
        raise serializers.ValidationError(
            {"username": "That username is already in use. Choose a different username or work email."}
        )

    work_email = (employee.work_email or "").strip().lower()
    if work_email:
        email_conflict = User.objects.filter(Q(email__iexact=work_email) | Q(username__iexact=work_email))
        if employee.user_id:
            email_conflict = email_conflict.exclude(pk=employee.user_id)
        if email_conflict.exists():
            raise serializers.ValidationError(
                {"work_email": "That work email is already in use by another account."}
            )


def link_employee_biometric(
    employee,
    *,
    fingerprint_id: str = "",
    card_no: str = "",
    dahua_user_id: str = "",
    notes: str = "",
):
    resolved_fingerprint_id = str(fingerprint_id or dahua_user_id or card_no or "").strip()
    if not resolved_fingerprint_id:
        raise serializers.ValidationError(
            {"fingerprint_id": "Provide at least one biometric identifier to create the biometric link."}
        )

    conflict = PersonRegistry.objects.filter(fingerprint_id=resolved_fingerprint_id).exclude(employee=employee).first()
    if conflict is not None:
        raise serializers.ValidationError(
            {"fingerprint_id": "That biometric identifier is already linked to another person."}
        )

    registry = (
        PersonRegistry.objects.filter(employee=employee)
        .order_by("-is_active", "-enrolled_at", "-id")
        .first()
    )
    display_name = _employee_display_name(employee)
    payload = {
        "fingerprint_id": resolved_fingerprint_id,
        "card_no": str(card_no or "").strip(),
        "dahua_user_id": str(dahua_user_id or "").strip(),
        "person_type": _employee_person_type(employee),
        "display_name": display_name,
        "is_active": True,
        "notes": str(notes or "").strip(),
    }

    with transaction.atomic():
        if registry is None:
            registry = PersonRegistry.objects.create(employee=employee, **payload)
        else:
            update_fields: list[str] = []
            for field_name, value in payload.items():
                if getattr(registry, field_name) != value:
                    setattr(registry, field_name, value)
                    update_fields.append(field_name)
            if registry.employee_id != employee.id:
                registry.employee = employee
                update_fields.append("employee")
            if update_fields:
                registry.save(update_fields=update_fields)

    summary = compute_onboarding_summary(employee)
    sync_onboarding_status(employee, summary=summary)
    return registry


def provision_employee_account(
    employee,
    *,
    role_name: str | None = None,
    username: str | None = None,
    assigned_by=None,
    send_welcome_email: bool = True,
) -> dict:
    normalized_role_name = normalize_role_name(role_name) or normalize_role_name(employee.account_role_name)
    if normalized_role_name and normalized_role_name != employee.account_role_name:
        employee.account_role_name = normalized_role_name
        employee.save(update_fields=["account_role_name"])

    summary = compute_onboarding_summary(employee)
    blockers = [
        blocker
        for blocker in summary.get("blockers", [])
        if blocker.get("code") != "account.already_provisioned"
    ]
    if blockers:
        raise serializers.ValidationError(
            {
                "message": "This employee is not ready for account provisioning.",
                "blockers": blockers,
            }
        )

    if employee.user_id:
        raise serializers.ValidationError({"user": "This employee already has a linked user account."})

    resolved_role_name = normalize_role_name(employee.account_role_name)
    if not resolved_role_name:
        raise serializers.ValidationError({"role_name": "Select the account role before provisioning."})

    resolved_username = _resolve_login_username(employee, username)
    _ensure_unique_login_identity(employee, resolved_username)
    temporary_password = _generate_temporary_password()

    with transaction.atomic():
        user = User.objects.create_user(
            username=resolved_username,
            email=(employee.work_email or "").strip().lower(),
            password=temporary_password,
            first_name=employee.first_name,
            last_name=employee.last_name,
            is_active=True,
        )

        role, _ = Role.objects.get_or_create(
            name=resolved_role_name,
            defaults={
                "description": ROLE_SEED_DESCRIPTION_MAP.get(
                    resolved_role_name,
                    resolved_role_name.replace("_", " ").title(),
                )
            },
        )
        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={"role": role, "force_password_change": True},
        )
        profile_updates: list[str] = []
        if profile.role_id != role.id:
            profile.role = role
            profile_updates.append("role")
        if not profile.force_password_change:
            profile.force_password_change = True
            profile_updates.append("force_password_change")
        if profile_updates:
            profile.save(update_fields=profile_updates)

        module_baseline = materialize_role_module_baseline(
            user,
            resolved_role_name,
            assigned_by=assigned_by,
        )

        provisioned_at = timezone.now()
        employee.user = user
        employee.account_role_name = resolved_role_name
        employee.account_provisioned_at = provisioned_at
        employee.save(update_fields=["user", "account_role_name", "account_provisioned_at"])

    summary = compute_onboarding_summary(employee)
    sync_onboarding_status(employee, summary=summary)

    welcome_email = {
        "attempted": False,
        "status": "skipped",
        "failure_reason": "",
    }
    if send_welcome_email and employee.work_email:
        result = send_email_placeholder(
            subject="Your staff account is ready",
            body=(
                f"Hello {employee.first_name},\n\n"
                f"Your account has been provisioned.\n"
                f"Username: {resolved_username}\n"
                f"Temporary password: {temporary_password}\n\n"
                "You will be required to change your password on first login."
            ),
            recipients=[employee.work_email],
        )
        welcome_email = {
            "attempted": True,
            "status": str(result.status or "").strip().lower() or "unknown",
            "failure_reason": result.failure_reason or "",
        }

    return {
        "user": user,
        "profile": profile,
        "temporary_password": temporary_password,
        "username": resolved_username,
        "role_name": resolved_role_name,
        "module_baseline": module_baseline,
        "welcome_email": welcome_email,
    }
