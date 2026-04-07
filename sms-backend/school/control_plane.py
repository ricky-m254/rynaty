from __future__ import annotations

from typing import Any

from academics.models import AcademicYear, Term

from .lifecycle_automation import build_lifecycle_section
from .models import (
    AdmissionSettings,
    GradingScheme,
    InstitutionLifecycleRun,
    Module,
    SchoolProfile,
    TenantModule,
)
from .security_policy import get_or_create_security_policy


def _owner(section_key: str, route: str, api_path: str) -> dict[str, str]:
    return {
        "section": section_key,
        "route": route,
        "api_path": api_path,
    }


def _make_blocker(
    section_key: str,
    severity: str,
    code: str,
    message: str,
    *,
    route: str,
    api_path: str,
) -> dict[str, str]:
    return {
        "section": section_key,
        "severity": severity,
        "code": code,
        "message": message,
        "route": route,
        "api_path": api_path,
    }


def _status_for_blockers(blockers: list[dict[str, str]]) -> str:
    severities = {blocker["severity"] for blocker in blockers}
    if "CRITICAL" in severities:
        return "NOT_READY"
    if "WARNING" in severities:
        return "PARTIALLY_READY"
    return "READY"


def _overall_status(section_statuses: list[str]) -> str:
    if "NOT_READY" in section_statuses:
        return "NOT_READY"
    if "PARTIALLY_READY" in section_statuses:
        return "PARTIALLY_READY"
    return "READY"


def _latest_completed_year_close_for_year(current_year: AcademicYear | None) -> InstitutionLifecycleRun | None:
    if current_year is None:
        return None

    latest_run = (
        InstitutionLifecycleRun.objects.filter(
            template__code="YEAR_CLOSE",
            status=InstitutionLifecycleRun.STATUS_COMPLETED,
            target_academic_year_id=current_year.id,
        )
        .order_by("-completed_at", "-id")
        .first()
    )
    if latest_run is None:
        return None

    effect = dict(latest_run.metadata or {}).get("last_execution_effect") or {}
    if effect.get("hook") != "YEAR_CLOSE":
        return None
    if not effect.get("changes", {}).get("current_term_cleared"):
        return None
    return latest_run


def _evaluate_school_profile(profile: SchoolProfile | None) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    route = "/settings/school-profile"
    api_path = "/api/school/profile/"
    if not profile:
        blockers.append(
            _make_blocker(
                "school_profile",
                "CRITICAL",
                "missing_school_profile",
                "School profile has not been initialized.",
                route=route,
                api_path=api_path,
            )
        )
        return {
            "label": "School Profile",
            "status": _status_for_blockers(blockers),
            "owner": _owner("school_profile", route, api_path),
            "data": None,
            "blockers": blockers,
        }

    if not (profile.school_name or "").strip():
        blockers.append(
            _make_blocker(
                "school_profile",
                "CRITICAL",
                "missing_school_name",
                "School name is required for tenant identity.",
                route=route,
                api_path=api_path,
            )
        )
    if not (profile.timezone or "").strip():
        blockers.append(
            _make_blocker(
                "school_profile",
                "CRITICAL",
                "missing_timezone",
                "Timezone must be configured before the tenant can run safely.",
                route=route,
                api_path=api_path,
            )
        )
    if not (profile.language or "").strip():
        blockers.append(
            _make_blocker(
                "school_profile",
                "WARNING",
                "missing_language",
                "Language is blank. Locale defaults may not reflect tenant expectations.",
                route=route,
                api_path=api_path,
            )
        )
    if not (profile.email_address or "").strip() and not (profile.phone or "").strip():
        blockers.append(
            _make_blocker(
                "school_profile",
                "WARNING",
                "missing_contact_channel",
                "Add a school email or phone number so operational contact details are visible.",
                route=route,
                api_path=api_path,
            )
        )

    return {
        "label": "School Profile",
        "status": _status_for_blockers(blockers),
        "owner": _owner("school_profile", route, api_path),
        "data": {
            "school_name": profile.school_name,
            "timezone": profile.timezone,
            "language": profile.language,
            "country": profile.country,
        },
        "blockers": blockers,
    }


def _evaluate_admission(profile: SchoolProfile | None) -> dict[str, Any]:
    settings_obj, _ = AdmissionSettings.objects.get_or_create(pk=1)
    blockers: list[dict[str, str]] = []
    route = "/settings/admission"
    api_path = "/api/settings/admission/"

    if not (settings_obj.prefix or "").strip():
        blockers.append(
            _make_blocker(
                "admission",
                "CRITICAL",
                "missing_admission_prefix",
                "Admission prefix is blank.",
                route=route,
                api_path=api_path,
            )
        )
    if settings_obj.padding < 1:
        blockers.append(
            _make_blocker(
                "admission",
                "CRITICAL",
                "invalid_admission_padding",
                "Admission padding must be at least 1.",
                route=route,
                api_path=api_path,
            )
        )
    if profile and profile.admission_number_prefix != settings_obj.prefix:
        blockers.append(
            _make_blocker(
                "admission",
                "WARNING",
                "legacy_admission_prefix_drift",
                "School profile legacy admission prefix is out of sync with AdmissionSettings.",
                route=route,
                api_path=api_path,
            )
        )

    return {
        "label": "Admission",
        "status": _status_for_blockers(blockers),
        "owner": _owner("admission", route, api_path),
        "data": {
            "prefix": settings_obj.prefix,
            "year": settings_obj.year,
            "padding": settings_obj.padding,
            "auto_generate": settings_obj.auto_generate,
        },
        "blockers": blockers,
    }


def _evaluate_academics() -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    route = "/settings/academics"
    api_path = "/api/settings/control-plane/"
    current_year = AcademicYear.objects.filter(is_current=True, is_active=True).first()
    current_term = Term.objects.filter(is_current=True, is_active=True).select_related("academic_year").first()
    rollover_run = _latest_completed_year_close_for_year(current_year)

    if not current_year:
        blockers.append(
            _make_blocker(
                "academics",
                "CRITICAL",
                "missing_current_academic_year",
                "No current academic year is configured.",
                route=route,
                api_path=api_path,
            )
        )
    if not current_term:
        if rollover_run:
            blockers.append(
                _make_blocker(
                    "academics",
                    "INFO",
                    "between_terms_after_year_close",
                    "No current term is configured yet. This is expected immediately after year close until term start is run.",
                    route=route,
                    api_path=api_path,
                )
            )
        else:
            blockers.append(
                _make_blocker(
                    "academics",
                    "CRITICAL",
                    "missing_current_term",
                    "No current term is configured.",
                    route=route,
                    api_path=api_path,
                )
            )
    if current_year and current_term and current_term.academic_year_id != current_year.id:
        blockers.append(
            _make_blocker(
                "academics",
                "CRITICAL",
                "term_year_mismatch",
                "The current term does not belong to the current academic year.",
                route=route,
                api_path=api_path,
            )
        )
    if current_year and current_year.start_date > current_year.end_date:
        blockers.append(
            _make_blocker(
                "academics",
                "CRITICAL",
                "invalid_academic_year_dates",
                "The current academic year has an invalid date range.",
                route=route,
                api_path=api_path,
            )
        )
    if current_term and current_term.start_date > current_term.end_date:
        blockers.append(
            _make_blocker(
                "academics",
                "CRITICAL",
                "invalid_term_dates",
                "The current term has an invalid date range.",
                route=route,
                api_path=api_path,
            )
        )

    return {
        "label": "Academics",
        "status": _status_for_blockers(blockers),
        "owner": _owner("academics", route, api_path),
        "data": {
            "current_academic_year": current_year.name if current_year else None,
            "current_term": current_term.name if current_term else None,
            "awaiting_term_start": bool(rollover_run and not current_term),
        },
        "blockers": blockers,
    }


def _evaluate_grading() -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    route = "/settings/academics"
    api_path = "/api/academics/grading-schemes/"
    active_count = GradingScheme.objects.filter(is_active=True).count()
    default_scheme = GradingScheme.objects.filter(is_active=True, is_default=True).first()

    if active_count == 0:
        blockers.append(
            _make_blocker(
                "grading",
                "CRITICAL",
                "missing_grading_scheme",
                "No active grading scheme is configured.",
                route=route,
                api_path=api_path,
            )
        )
    elif not default_scheme:
        blockers.append(
            _make_blocker(
                "grading",
                "WARNING",
                "missing_default_grading_scheme",
                "There is no default grading scheme. The system may fall back to the first active scheme.",
                route=route,
                api_path=api_path,
            )
        )

    return {
        "label": "Grading",
        "status": _status_for_blockers(blockers),
        "owner": _owner("grading", route, api_path),
        "data": {
            "active_scheme_count": active_count,
            "default_scheme": default_scheme.name if default_scheme else None,
        },
        "blockers": blockers,
    }


def _evaluate_finance(profile: SchoolProfile | None) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    route = "/settings/finance"
    api_path = "/api/settings/finance/"

    if not profile:
        blockers.append(
            _make_blocker(
                "finance",
                "CRITICAL",
                "missing_finance_profile",
                "Finance defaults cannot be evaluated until SchoolProfile exists.",
                route=route,
                api_path=api_path,
            )
        )
        return {
            "label": "Finance",
            "status": _status_for_blockers(blockers),
            "owner": _owner("finance", route, api_path),
            "data": None,
            "blockers": blockers,
        }

    if not (profile.currency or "").strip():
        blockers.append(
            _make_blocker(
                "finance",
                "CRITICAL",
                "missing_currency",
                "Currency must be configured for finance operations.",
                route=route,
                api_path=api_path,
            )
        )
    if not (profile.receipt_prefix or "").strip():
        blockers.append(
            _make_blocker(
                "finance",
                "WARNING",
                "missing_receipt_prefix",
                "Receipt prefix is blank.",
                route=route,
                api_path=api_path,
            )
        )
    if not (profile.invoice_prefix or "").strip():
        blockers.append(
            _make_blocker(
                "finance",
                "WARNING",
                "missing_invoice_prefix",
                "Invoice prefix is blank.",
                route=route,
                api_path=api_path,
            )
        )
    if not profile.accepted_payment_methods:
        blockers.append(
            _make_blocker(
                "finance",
                "WARNING",
                "missing_payment_methods",
                "No accepted payment methods are configured.",
                route=route,
                api_path=api_path,
            )
        )

    return {
        "label": "Finance",
        "status": _status_for_blockers(blockers),
        "owner": _owner("finance", route, api_path),
        "data": {
            "currency": profile.currency,
            "receipt_prefix": profile.receipt_prefix,
            "invoice_prefix": profile.invoice_prefix,
            "accepted_payment_methods_count": len(profile.accepted_payment_methods or []),
        },
        "blockers": blockers,
    }


def _evaluate_security() -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    route = "/settings/security"
    api_path = "/api/settings/security-policy/"
    policy = get_or_create_security_policy()

    if policy.ip_whitelist_enabled and not policy.allowed_ip_ranges:
        blockers.append(
            _make_blocker(
                "security",
                "CRITICAL",
                "missing_allowed_ip_ranges",
                "IP whitelist is enabled but no allowed IP ranges are configured.",
                route=route,
                api_path=api_path,
            )
        )
    if policy.mfa_mode == "DISABLED":
        blockers.append(
            _make_blocker(
                "security",
                "WARNING",
                "mfa_disabled",
                "Multi-factor authentication is disabled.",
                route=route,
                api_path=api_path,
            )
        )

    return {
        "label": "Security",
        "status": _status_for_blockers(blockers),
        "owner": _owner("security", route, api_path),
        "data": {
            "session_timeout_minutes": policy.session_timeout_minutes,
            "mfa_mode": policy.mfa_mode,
            "mfa_method": policy.mfa_method,
            "ip_whitelist_enabled": policy.ip_whitelist_enabled,
            "allowed_ip_ranges_count": len(policy.allowed_ip_ranges or []),
        },
        "blockers": blockers,
    }


def _evaluate_modules() -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    route = "/settings/modules"
    api_path = "/api/tenant/modules"
    from .services import TenantModuleSettingsService

    tenant_modules = TenantModuleSettingsService.list_modules_for_tenant(user=None)
    registered_modules = len(tenant_modules)
    enabled_module_rows = [
        tenant_module
        for tenant_module in tenant_modules
        if tenant_module.is_enabled and getattr(tenant_module.module, "is_active", False)
    ]
    enabled_modules = len(enabled_module_rows)
    configured_enabled_modules = 0
    invalid_module_keys: list[str] = []

    if registered_modules == 0:
        blockers.append(
            _make_blocker(
                "modules",
                "CRITICAL",
                "missing_registered_modules",
                "No active modules are registered for this tenant.",
                route=route,
                api_path=api_path,
            )
        )
    elif enabled_modules == 0:
        blockers.append(
            _make_blocker(
                "modules",
                "CRITICAL",
                "missing_enabled_modules",
                "No tenant modules are enabled yet.",
                route=route,
                api_path=api_path,
            )
        )
    else:
        for tenant_module in enabled_module_rows:
            settings_obj = getattr(tenant_module, "settings", None)
            feature_toggles = getattr(settings_obj, "feature_toggles", None)
            config = getattr(settings_obj, "config", None)
            module_key = tenant_module.module.key
            if (
                settings_obj is not None
                and isinstance(feature_toggles, dict)
                and isinstance(config, dict)
                and config.get("module_key") == module_key
                and isinstance(config.get("version"), int)
                and config.get("version") >= 1
            ):
                configured_enabled_modules += 1
                continue
            invalid_module_keys.append(module_key)

        for module_key in invalid_module_keys:
            blockers.append(
                _make_blocker(
                    "modules",
                    "WARNING",
                    f"module_settings_not_ready_{module_key.lower()}",
                    f"Module settings baseline for {module_key} needs attention.",
                    route=route,
                    api_path=api_path,
                )
            )

    return {
        "label": "Modules",
        "status": _status_for_blockers(blockers),
        "owner": _owner("modules", route, api_path),
        "data": {
            "registered_modules": registered_modules,
            "enabled_modules": enabled_modules,
            "configured_enabled_modules": configured_enabled_modules,
            "enabled_module_keys": [tenant_module.module.key for tenant_module in enabled_module_rows[:8]],
        },
        "blockers": blockers,
    }


def build_control_plane_summary() -> dict[str, Any]:
    profile = SchoolProfile.objects.filter(is_active=True).first()
    sections = {
        "school_profile": _evaluate_school_profile(profile),
        "admission": _evaluate_admission(profile),
        "academics": _evaluate_academics(),
        "grading": _evaluate_grading(),
        "finance": _evaluate_finance(profile),
        "security": _evaluate_security(),
        "modules": _evaluate_modules(),
        "lifecycle": build_lifecycle_section(),
    }
    all_blockers: list[dict[str, str]] = []
    section_statuses: list[str] = []
    for section in sections.values():
        all_blockers.extend(section["blockers"])
        section_statuses.append(section["status"])

    severity_counts = {"CRITICAL": 0, "WARNING": 0, "INFO": 0}
    for blocker in all_blockers:
        severity_counts[blocker["severity"]] = severity_counts.get(blocker["severity"], 0) + 1

    return {
        "overall_status": _overall_status(section_statuses),
        "summary_counts": {
            "sections": len(sections),
            "critical_blockers": severity_counts["CRITICAL"],
            "warning_blockers": severity_counts["WARNING"],
            "info_blockers": severity_counts["INFO"],
        },
        "sections": sections,
        "blockers": all_blockers,
    }
