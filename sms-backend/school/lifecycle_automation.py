from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from .models import (
    AcademicYear,
    InstitutionLifecycleRun,
    InstitutionLifecycleTaskRun,
    InstitutionLifecycleTaskTemplate,
    InstitutionLifecycleTemplate,
    Term,
)


class LifecycleAutomationError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = "lifecycle_error",
        blockers: list[dict[str, Any]] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.blockers = blockers or []
        self.details = details or {}


TEMPLATE_CODE_TENANT_ONBOARDING = "TENANT_ONBOARDING"
TEMPLATE_CODE_TERM_START = "TERM_START"
TEMPLATE_CODE_YEAR_CLOSE = "YEAR_CLOSE"

TERMINAL_RUN_STATUSES = {
    InstitutionLifecycleRun.STATUS_COMPLETED,
    InstitutionLifecycleRun.STATUS_CANCELLED,
}
RESOLVED_TASK_STATUSES = {
    InstitutionLifecycleTaskRun.STATUS_COMPLETED,
    InstitutionLifecycleTaskRun.STATUS_WAIVED,
}
VALIDATION_SECTION_MAP = {
    "SCHOOL_PROFILE_READY": "school_profile",
    "ADMISSION_READY": "admission",
    "ACADEMICS_READY": "academics",
    "GRADING_READY": "grading",
    "FINANCE_READY": "finance",
    "SECURITY_READY": "security",
    "MODULES_READY": "modules",
}


DEFAULT_TEMPLATE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "code": TEMPLATE_CODE_TENANT_ONBOARDING,
        "name": "Tenant Onboarding",
        "description": "Guide a new tenant through identity, academics, finance, security, and module readiness.",
        "tasks": (
            {
                "task_code": "IDENTITY_LOCALE_BASELINE",
                "title": "Complete school profile, locale, and contact details",
                "description": "Confirm school identity, timezone, language, and contact channels.",
                "task_group": "Identity and locale",
                "required": True,
                "display_order": 10,
                "waivable": False,
                "validation_key": "SCHOOL_PROFILE_READY",
            },
            {
                "task_code": "ADMISSION_BASELINE",
                "title": "Confirm admission numbering policy",
                "description": "Set the admission prefix, year handling, and numbering sequence policy.",
                "task_group": "Admission baseline",
                "required": True,
                "display_order": 20,
                "waivable": False,
                "validation_key": "ADMISSION_READY",
            },
            {
                "task_code": "ACADEMIC_BASELINE",
                "title": "Confirm academic year and current term baseline",
                "description": "Academic year and term context must be valid before operations begin.",
                "task_group": "Academic baseline",
                "required": True,
                "display_order": 30,
                "waivable": False,
                "validation_key": "ACADEMICS_READY",
            },
            {
                "task_code": "GRADING_BASELINE",
                "title": "Confirm grading baseline",
                "description": "Ensure at least one active grading scheme exists and a default is defined when needed.",
                "task_group": "Academic baseline",
                "required": True,
                "display_order": 40,
                "waivable": False,
                "validation_key": "GRADING_READY",
            },
            {
                "task_code": "FINANCE_BASELINE",
                "title": "Confirm finance defaults",
                "description": "Verify currency, prefixes, payment methods, and default finance policies.",
                "task_group": "Finance configuration",
                "required": True,
                "display_order": 50,
                "waivable": False,
                "validation_key": "FINANCE_READY",
            },
            {
                "task_code": "SECURITY_BASELINE",
                "title": "Confirm institution security policy",
                "description": "Set password, MFA, session, and IP access policy before go-live.",
                "task_group": "Security policy",
                "required": True,
                "display_order": 60,
                "waivable": False,
                "validation_key": "SECURITY_READY",
            },
            {
                "task_code": "MODULE_ENABLEMENT",
                "title": "Confirm enabled tenant modules",
                "description": "Ensure at least one active tenant module is enabled and available.",
                "task_group": "Module readiness",
                "required": True,
                "display_order": 70,
                "waivable": False,
                "validation_key": "MODULES_READY",
            },
            {
                "task_code": "READINESS_CONFIRMATION",
                "title": "Record onboarding confirmation",
                "description": "Capture any final notes before marking onboarding complete.",
                "task_group": "Readiness confirmation",
                "required": True,
                "display_order": 80,
                "waivable": False,
                "validation_key": "",
            },
        ),
    },
    {
        "code": TEMPLATE_CODE_TERM_START,
        "name": "Term Start",
        "description": "Guide safe opening of a selected term with target-year validation and baseline checks.",
        "tasks": (
            {
                "task_code": "TARGET_YEAR_SELECTED",
                "title": "Select target academic year",
                "description": "Choose the academic year this term-start run applies to.",
                "task_group": "Target validation",
                "required": True,
                "display_order": 10,
                "waivable": False,
                "validation_key": "TERM_TARGET_YEAR",
            },
            {
                "task_code": "TARGET_TERM_SELECTED",
                "title": "Select target term",
                "description": "Choose the term that should start.",
                "task_group": "Target validation",
                "required": True,
                "display_order": 20,
                "waivable": False,
                "validation_key": "TERM_TARGET_TERM",
            },
            {
                "task_code": "TARGET_ALIGNMENT",
                "title": "Confirm term belongs to the selected academic year",
                "description": "The selected term must belong to the selected academic year.",
                "task_group": "Target validation",
                "required": True,
                "display_order": 30,
                "waivable": False,
                "validation_key": "TERM_TARGET_ALIGNMENT",
            },
            {
                "task_code": "ACADEMIC_CONTEXT_READY",
                "title": "Confirm academic calendar sanity",
                "description": "Current academic year and term baseline must remain internally consistent.",
                "task_group": "Academic readiness",
                "required": True,
                "display_order": 40,
                "waivable": False,
                "validation_key": "ACADEMICS_READY",
            },
            {
                "task_code": "GRADING_READY",
                "title": "Confirm grading baseline",
                "description": "Grading must be configured before teaching and assessment begin.",
                "task_group": "Academic readiness",
                "required": True,
                "display_order": 50,
                "waivable": False,
                "validation_key": "GRADING_READY",
            },
            {
                "task_code": "FINANCE_READY",
                "title": "Confirm finance term readiness",
                "description": "Finance defaults should be ready for invoicing and term billing workflows.",
                "task_group": "Operational readiness",
                "required": True,
                "display_order": 60,
                "waivable": True,
                "validation_key": "FINANCE_READY",
            },
            {
                "task_code": "MODULES_READY",
                "title": "Confirm module readiness",
                "description": "Tenant module enablement should match the operational term plan.",
                "task_group": "Operational readiness",
                "required": True,
                "display_order": 70,
                "waivable": False,
                "validation_key": "MODULES_READY",
            },
        ),
    },
    {
        "code": TEMPLATE_CODE_YEAR_CLOSE,
        "name": "Year Close",
        "description": "Guide safe year-end review with blocker visibility, next-year readiness, and explicit waivers.",
        "tasks": (
            {
                "task_code": "CLOSE_REVIEW",
                "title": "Review unresolved critical blockers",
                "description": "Year close cannot complete while critical control-plane blockers remain open.",
                "task_group": "Close readiness review",
                "required": True,
                "display_order": 10,
                "waivable": False,
                "validation_key": "YEAR_CLOSE_CRITICAL_REVIEW",
            },
            {
                "task_code": "GRADING_REVIEW",
                "title": "Confirm grading readiness visibility",
                "description": "Check grading and results readiness before closing the year.",
                "task_group": "Academic readiness",
                "required": True,
                "display_order": 20,
                "waivable": True,
                "validation_key": "GRADING_READY",
            },
            {
                "task_code": "FINANCE_REVIEW",
                "title": "Confirm finance close readiness",
                "description": "Review finance baseline and close visibility before year-end.",
                "task_group": "Finance readiness",
                "required": True,
                "display_order": 30,
                "waivable": True,
                "validation_key": "FINANCE_READY",
            },
            {
                "task_code": "NEXT_YEAR_BASELINE",
                "title": "Confirm next academic year baseline",
                "description": "Select the next academic year baseline for rollover readiness.",
                "task_group": "Next-year readiness",
                "required": True,
                "display_order": 40,
                "waivable": False,
                "validation_key": "YEAR_CLOSE_NEXT_YEAR",
            },
            {
                "task_code": "ADMISSION_POLICY_REVIEW",
                "title": "Review admission reset policy",
                "description": "Confirm the admission numbering policy before rollover.",
                "task_group": "Policy confirmation",
                "required": True,
                "display_order": 50,
                "waivable": True,
                "validation_key": "ADMISSION_READY",
            },
        ),
    },
)


def ensure_lifecycle_templates() -> list[InstitutionLifecycleTemplate]:
    templates: list[InstitutionLifecycleTemplate] = []
    for definition in DEFAULT_TEMPLATE_DEFINITIONS:
        template, _ = InstitutionLifecycleTemplate.objects.get_or_create(
            code=definition["code"],
            defaults={
                "name": definition["name"],
                "description": definition["description"],
                "is_active": True,
            },
        )
        update_fields: list[str] = []
        for field in ("name", "description", "is_active"):
            new_value = definition[field] if field != "is_active" else True
            if getattr(template, field) != new_value:
                setattr(template, field, new_value)
                update_fields.append(field)
        if update_fields:
            template.save(update_fields=update_fields + ["updated_at"])

        for task_definition in definition["tasks"]:
            task_template, _ = InstitutionLifecycleTaskTemplate.objects.get_or_create(
                template=template,
                task_code=task_definition["task_code"],
                defaults={
                    "title": task_definition["title"],
                    "description": task_definition["description"],
                    "task_group": task_definition["task_group"],
                    "required": task_definition["required"],
                    "display_order": task_definition["display_order"],
                    "waivable": task_definition["waivable"],
                    "validation_key": task_definition["validation_key"],
                },
            )
            task_update_fields: list[str] = []
            for field in (
                "title",
                "description",
                "task_group",
                "required",
                "display_order",
                "waivable",
                "validation_key",
            ):
                new_value = task_definition[field]
                if getattr(task_template, field) != new_value:
                    setattr(task_template, field, new_value)
                    task_update_fields.append(field)
            if task_update_fields:
                task_template.save(update_fields=task_update_fields + ["updated_at"])

        templates.append(template)

    return list(
        InstitutionLifecycleTemplate.objects.filter(is_active=True).prefetch_related("task_templates").order_by("code")
    )


def _section_critical_blockers(
    control_plane_summary: dict[str, Any],
    section_keys: list[str],
) -> list[dict[str, Any]]:
    return [
        blocker
        for blocker in control_plane_summary.get("blockers", [])
        if blocker.get("section") in section_keys and blocker.get("severity") == "CRITICAL"
    ]


def _all_critical_blockers(control_plane_summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        blocker
        for blocker in control_plane_summary.get("blockers", [])
        if blocker.get("severity") == "CRITICAL"
    ]


def _target_year_blockers(run: InstitutionLifecycleRun) -> list[dict[str, Any]]:
    if run.target_academic_year_id:
        return []
    return [
        {
            "section": "lifecycle",
            "severity": "CRITICAL",
            "code": "missing_target_academic_year",
            "message": "Select a target academic year before this task can be completed.",
            "route": "/settings/control-plane",
            "api_path": f"/api/settings/lifecycle-runs/{run.id}/",
        }
    ]


def _target_term_blockers(run: InstitutionLifecycleRun) -> list[dict[str, Any]]:
    if run.target_term_id:
        return []
    return [
        {
            "section": "lifecycle",
            "severity": "CRITICAL",
            "code": "missing_target_term",
            "message": "Select a target term before this task can be completed.",
            "route": "/settings/control-plane",
            "api_path": f"/api/settings/lifecycle-runs/{run.id}/",
        }
    ]


def _serialize_academic_year(year: AcademicYear | None) -> dict[str, Any] | None:
    if not year:
        return None
    return {
        "id": year.id,
        "name": year.name,
        "start_date": year.start_date.isoformat(),
        "end_date": year.end_date.isoformat(),
        "is_active": year.is_active,
        "is_current": year.is_current,
    }


def _serialize_term(term: Term | None) -> dict[str, Any] | None:
    if not term:
        return None
    return {
        "id": term.id,
        "name": term.name,
        "academic_year_id": term.academic_year_id,
        "start_date": term.start_date.isoformat(),
        "end_date": term.end_date.isoformat(),
        "billing_date": term.billing_date.isoformat() if term.billing_date else None,
        "is_active": term.is_active,
        "is_current": term.is_current,
    }


def _control_plane_section_snapshot(
    control_plane_summary: dict[str, Any],
    section_key: str,
) -> dict[str, Any] | None:
    section = control_plane_summary.get("sections", {}).get(section_key)
    if not section:
        return None
    blockers = section.get("blockers") or []
    return {
        "section": section_key,
        "label": section.get("label"),
        "status": section.get("status"),
        "data": section.get("data"),
        "blocker_codes": [blocker.get("code") for blocker in blockers if blocker.get("code")],
    }


def _build_task_evidence(
    run: InstitutionLifecycleRun,
    task_run: InstitutionLifecycleTaskRun,
    *,
    control_plane_summary: dict[str, Any],
    action: str,
    notes: str = "",
    provided_evidence: dict[str, Any] | None = None,
    blockers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    validation_key = (task_run.template_task.validation_key or "").strip().upper()
    payload = dict(provided_evidence or {})
    payload.update(
        {
            "captured_at": timezone.now().isoformat(),
            "action": action,
            "template_code": run.template.code,
            "run_id": run.id,
            "task_code": task_run.template_task.task_code,
            "task_title": task_run.template_task.title,
            "validation_key": validation_key or None,
            "notes_present": bool(notes.strip()),
        }
    )
    if run.target_academic_year_id:
        payload["target_academic_year"] = _serialize_academic_year(run.target_academic_year)
    if run.target_term_id:
        payload["target_term"] = _serialize_term(run.target_term)

    section_key = VALIDATION_SECTION_MAP.get(validation_key)
    if section_key:
        payload["control_plane_section"] = _control_plane_section_snapshot(control_plane_summary, section_key)
    elif validation_key == "TERM_TARGET_ALIGNMENT":
        payload["target_alignment"] = {
            "matches": bool(
                run.target_term_id
                and run.target_academic_year_id
                and run.target_term.academic_year_id == run.target_academic_year_id
            ),
            "target_academic_year": _serialize_academic_year(run.target_academic_year),
            "target_term": _serialize_term(run.target_term),
        }
    elif validation_key == "YEAR_CLOSE_CRITICAL_REVIEW":
        critical_blockers = _all_critical_blockers(control_plane_summary)
        payload["critical_blocker_count"] = len(critical_blockers)
        payload["critical_blocker_codes"] = [
            blocker.get("code") for blocker in critical_blockers if blocker.get("code")
        ]

    if blockers is not None:
        payload["blockers"] = blockers
    return payload


def _record_execution_effect(
    run: InstitutionLifecycleRun,
    effect: dict[str, Any],
) -> None:
    metadata = dict(run.metadata or {})
    history = metadata.get("execution_effects")
    if not isinstance(history, list):
        history = []
    history.append(effect)
    metadata["execution_effects"] = history[-10:]
    metadata["last_execution_effect"] = effect
    run.metadata = metadata


def _apply_term_start_effects(run: InstitutionLifecycleRun) -> dict[str, Any]:
    if not run.target_academic_year_id or not run.target_term_id:
        raise LifecycleAutomationError(
            "Term start requires both a target academic year and a target term.",
            code="missing_term_start_target",
        )
    if run.target_term.academic_year_id != run.target_academic_year_id:
        raise LifecycleAutomationError(
            "The selected term does not belong to the selected academic year.",
            code="target_term_year_mismatch",
        )

    previous_year = AcademicYear.objects.filter(is_current=True).first()
    previous_term = Term.objects.select_related("academic_year").filter(is_current=True).first()
    target_year = run.target_academic_year
    target_term = run.target_term

    year_changes: list[str] = []
    if not target_year.is_active:
        target_year.is_active = True
        year_changes.append("is_active")
    if not target_year.is_current:
        target_year.is_current = True
        year_changes.append("is_current")
    if year_changes:
        target_year.save(update_fields=year_changes)

    term_changes: list[str] = []
    if not target_term.is_active:
        target_term.is_active = True
        term_changes.append("is_active")
    if not target_term.is_current:
        target_term.is_current = True
        term_changes.append("is_current")
    if term_changes:
        target_term.save(update_fields=term_changes)

    return {
        "hook": "TERM_START",
        "applied_at": timezone.now().isoformat(),
        "previous_context": {
            "academic_year": _serialize_academic_year(previous_year),
            "term": _serialize_term(previous_term),
        },
        "current_context": {
            "academic_year": _serialize_academic_year(target_year),
            "term": _serialize_term(target_term),
        },
        "changes": {
            "academic_year_activated": "is_active" in year_changes,
            "academic_year_set_current": "is_current" in year_changes,
            "term_activated": "is_active" in term_changes,
            "term_set_current": "is_current" in term_changes,
        },
    }


def _apply_year_close_effects(run: InstitutionLifecycleRun) -> dict[str, Any]:
    target_year = run.target_academic_year
    if not target_year:
        raise LifecycleAutomationError(
            "Year close requires a next academic year baseline.",
            code="missing_target_academic_year",
        )

    closing_year = AcademicYear.objects.filter(is_current=True).first()
    closing_term = Term.objects.select_related("academic_year").filter(is_current=True).first()
    if closing_year and closing_year.id == target_year.id:
        raise LifecycleAutomationError(
            "The selected next academic year must be different from the current academic year.",
            code="next_year_matches_current_year",
        )

    closing_term_cleared = False
    if closing_term and closing_term.is_current:
        closing_term.is_current = False
        closing_term.save(update_fields=["is_current"])
        closing_term_cleared = True

    prepared_year_changes: list[str] = []
    if not target_year.is_active:
        target_year.is_active = True
        prepared_year_changes.append("is_active")
    if not target_year.is_current:
        target_year.is_current = True
        prepared_year_changes.append("is_current")
    if prepared_year_changes:
        target_year.save(update_fields=prepared_year_changes)

    return {
        "hook": "YEAR_CLOSE",
        "applied_at": timezone.now().isoformat(),
        "closed_context": {
            "academic_year": _serialize_academic_year(closing_year),
            "term": _serialize_term(closing_term),
        },
        "prepared_next_year": _serialize_academic_year(target_year),
        "changes": {
            "current_term_cleared": closing_term_cleared,
            "next_year_activated": "is_active" in prepared_year_changes,
            "next_year_set_current": "is_current" in prepared_year_changes,
        },
    }


def _apply_completion_effects(run: InstitutionLifecycleRun) -> dict[str, Any] | None:
    if run.template.code == TEMPLATE_CODE_TERM_START:
        return _apply_term_start_effects(run)
    if run.template.code == TEMPLATE_CODE_YEAR_CLOSE:
        return _apply_year_close_effects(run)
    return None


def evaluate_validation_key(
    run: InstitutionLifecycleRun,
    validation_key: str,
    *,
    control_plane_summary: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    key = (validation_key or "").strip().upper()
    if not key:
        return []

    summary = control_plane_summary
    if summary is None:
        from .control_plane import build_control_plane_summary

        summary = build_control_plane_summary()

    if key == "SCHOOL_PROFILE_READY":
        return _section_critical_blockers(summary, ["school_profile"])
    if key == "ADMISSION_READY":
        return _section_critical_blockers(summary, ["admission"])
    if key == "ACADEMICS_READY":
        return _section_critical_blockers(summary, ["academics"])
    if key == "GRADING_READY":
        return _section_critical_blockers(summary, ["grading"])
    if key == "FINANCE_READY":
        return _section_critical_blockers(summary, ["finance"])
    if key == "SECURITY_READY":
        return _section_critical_blockers(summary, ["security"])
    if key == "MODULES_READY":
        return _section_critical_blockers(summary, ["modules"])
    if key == "TERM_TARGET_YEAR":
        blockers = _target_year_blockers(run)
        if blockers:
            return blockers
        if run.target_academic_year and run.target_academic_year.start_date > run.target_academic_year.end_date:
            return [
                {
                    "section": "lifecycle",
                    "severity": "CRITICAL",
                    "code": "invalid_target_academic_year_dates",
                    "message": "The selected academic year has an invalid date range.",
                    "route": "/settings/control-plane",
                    "api_path": f"/api/settings/lifecycle-runs/{run.id}/",
                }
            ]
        return []
    if key == "TERM_TARGET_TERM":
        blockers = _target_term_blockers(run)
        if blockers:
            return blockers
        if run.target_term and run.target_term.start_date > run.target_term.end_date:
            return [
                {
                    "section": "lifecycle",
                    "severity": "CRITICAL",
                    "code": "invalid_target_term_dates",
                    "message": "The selected term has an invalid date range.",
                    "route": "/settings/control-plane",
                    "api_path": f"/api/settings/lifecycle-runs/{run.id}/",
                }
            ]
        return []
    if key == "TERM_TARGET_ALIGNMENT":
        if run.target_term_id and run.target_academic_year_id and run.target_term.academic_year_id == run.target_academic_year_id:
            return []
        return [
            {
                "section": "lifecycle",
                "severity": "CRITICAL",
                "code": "target_term_year_mismatch",
                "message": "The selected term does not belong to the selected academic year.",
                "route": "/settings/control-plane",
                "api_path": f"/api/settings/lifecycle-runs/{run.id}/",
            }
        ]
    if key == "YEAR_CLOSE_CRITICAL_REVIEW":
        return _all_critical_blockers(summary)
    if key == "YEAR_CLOSE_NEXT_YEAR":
        blockers = _target_year_blockers(run)
        if blockers:
            return blockers
        current_year = AcademicYear.objects.filter(is_current=True).first()
        if current_year and run.target_academic_year_id == current_year.id:
            return [
                {
                    "section": "lifecycle",
                    "severity": "CRITICAL",
                    "code": "next_year_matches_current_year",
                    "message": "The selected next academic year must be different from the current academic year.",
                    "route": "/settings/control-plane",
                    "api_path": f"/api/settings/lifecycle-runs/{run.id}/",
                }
            ]
        if run.target_academic_year and run.target_academic_year.start_date > run.target_academic_year.end_date:
            return [
                {
                    "section": "lifecycle",
                    "severity": "CRITICAL",
                    "code": "invalid_target_academic_year_dates",
                    "message": "The selected next academic year has an invalid date range.",
                    "route": "/settings/control-plane",
                    "api_path": f"/api/settings/lifecycle-runs/{run.id}/",
                }
            ]
        return []
    return []


def _sync_task_run(
    task_run: InstitutionLifecycleTaskRun,
    control_plane_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    if task_run.status in RESOLVED_TASK_STATUSES:
        return []

    blockers = evaluate_validation_key(
        task_run.run,
        task_run.template_task.validation_key,
        control_plane_summary=control_plane_summary,
    )
    next_status = (
        InstitutionLifecycleTaskRun.STATUS_BLOCKED
        if blockers
        else InstitutionLifecycleTaskRun.STATUS_PENDING
    )
    blocker_message = " ".join(blocker["message"] for blocker in blockers)
    update_fields: list[str] = []
    if task_run.status != next_status:
        task_run.status = next_status
        update_fields.append("status")
    if task_run.blocker_message != blocker_message:
        task_run.blocker_message = blocker_message
        update_fields.append("blocker_message")
    if update_fields:
        task_run.save(update_fields=update_fields + ["updated_at"])
    return blockers


def _refresh_run_summary(
    run: InstitutionLifecycleRun,
    *,
    control_plane_summary: dict[str, Any],
    task_blockers: list[dict[str, Any]],
) -> None:
    tasks = list(run.task_runs.select_related("template_task"))
    status_counts = {
        InstitutionLifecycleTaskRun.STATUS_PENDING: 0,
        InstitutionLifecycleTaskRun.STATUS_COMPLETED: 0,
        InstitutionLifecycleTaskRun.STATUS_WAIVED: 0,
        InstitutionLifecycleTaskRun.STATUS_BLOCKED: 0,
    }
    for task_run in tasks:
        status_counts[task_run.status] = status_counts.get(task_run.status, 0) + 1

    summary_payload = {
        "task_counts": status_counts,
        "critical_blocker_count": len(task_blockers),
        "control_plane_overall_status": control_plane_summary.get("overall_status"),
        "last_refreshed_at": timezone.now().isoformat(),
    }
    desired_status = run.status
    if run.status not in TERMINAL_RUN_STATUSES:
        if run.started_at:
            desired_status = (
                InstitutionLifecycleRun.STATUS_BLOCKED
                if status_counts[InstitutionLifecycleTaskRun.STATUS_BLOCKED] > 0
                else InstitutionLifecycleRun.STATUS_IN_PROGRESS
            )
        else:
            desired_status = InstitutionLifecycleRun.STATUS_DRAFT

    update_fields: list[str] = []
    if run.summary != summary_payload:
        run.summary = summary_payload
        update_fields.append("summary")
    if run.status != desired_status:
        run.status = desired_status
        update_fields.append("status")
    if update_fields:
        run.save(update_fields=update_fields + ["updated_at"])


def refresh_lifecycle_run(run: InstitutionLifecycleRun) -> InstitutionLifecycleRun:
    from .control_plane import build_control_plane_summary

    control_plane_summary = build_control_plane_summary()
    task_blockers: list[dict[str, Any]] = []
    for task_run in run.task_runs.select_related("template_task").order_by("display_order", "id"):
        task_blockers.extend(_sync_task_run(task_run, control_plane_summary))
    _refresh_run_summary(
        run,
        control_plane_summary=control_plane_summary,
        task_blockers=task_blockers,
    )
    return run


def _assert_no_duplicate_completed_run(
    template: InstitutionLifecycleTemplate,
    *,
    target_academic_year: AcademicYear | None,
    target_term: Term | None,
) -> None:
    queryset = InstitutionLifecycleRun.objects.filter(
        template=template,
        status=InstitutionLifecycleRun.STATUS_COMPLETED,
    )
    if template.code == TEMPLATE_CODE_TENANT_ONBOARDING and queryset.exists():
        raise LifecycleAutomationError(
            "Tenant onboarding already has a completed run for this tenant.",
            code="duplicate_completed_run",
        )
    if template.code == TEMPLATE_CODE_TERM_START and target_term and queryset.filter(target_term=target_term).exists():
        raise LifecycleAutomationError(
            "A completed term-start run already exists for the selected term.",
            code="duplicate_completed_run",
        )
    if template.code == TEMPLATE_CODE_YEAR_CLOSE and target_academic_year and queryset.filter(
        target_academic_year=target_academic_year
    ).exists():
        raise LifecycleAutomationError(
            "A completed year-close run already exists for the selected academic year.",
            code="duplicate_completed_run",
        )


@transaction.atomic
def create_lifecycle_run(
    *,
    template_code: str,
    target_academic_year_id: int | None = None,
    target_term_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> InstitutionLifecycleRun:
    ensure_lifecycle_templates()
    template = InstitutionLifecycleTemplate.objects.filter(code=template_code, is_active=True).first()
    if not template:
        raise LifecycleAutomationError("Lifecycle template not found.", code="template_not_found")

    target_academic_year = None
    if target_academic_year_id:
        target_academic_year = AcademicYear.objects.filter(pk=target_academic_year_id).first()
        if not target_academic_year:
            raise LifecycleAutomationError("Target academic year not found.", code="target_academic_year_not_found")

    target_term = None
    if target_term_id:
        target_term = Term.objects.filter(pk=target_term_id).first()
        if not target_term:
            raise LifecycleAutomationError("Target term not found.", code="target_term_not_found")

    _assert_no_duplicate_completed_run(
        template,
        target_academic_year=target_academic_year,
        target_term=target_term,
    )

    run = InstitutionLifecycleRun.objects.create(
        template=template,
        status=InstitutionLifecycleRun.STATUS_DRAFT,
        target_academic_year=target_academic_year,
        target_term=target_term,
        metadata=metadata or {},
    )
    task_runs = [
        InstitutionLifecycleTaskRun(
            run=run,
            template_task=task_template,
            display_order=task_template.display_order,
            status=InstitutionLifecycleTaskRun.STATUS_PENDING,
        )
        for task_template in template.task_templates.order_by("display_order", "id")
    ]
    InstitutionLifecycleTaskRun.objects.bulk_create(task_runs)
    return refresh_lifecycle_run(run)


@transaction.atomic
def start_lifecycle_run(run: InstitutionLifecycleRun, *, started_by=None) -> InstitutionLifecycleRun:
    if run.status in TERMINAL_RUN_STATUSES:
        raise LifecycleAutomationError("This lifecycle run is already in a terminal state.", code="terminal_run")
    if run.started_at is None:
        run.started_at = timezone.now()
    if started_by is not None and run.started_by_id != getattr(started_by, "id", None):
        run.started_by = started_by
    run.status = InstitutionLifecycleRun.STATUS_IN_PROGRESS
    run.save(update_fields=["started_at", "started_by", "status", "updated_at"])
    return refresh_lifecycle_run(run)


@transaction.atomic
def complete_task_run(
    run: InstitutionLifecycleRun,
    task_run: InstitutionLifecycleTaskRun,
    *,
    completed_by=None,
    notes: str = "",
    evidence: dict[str, Any] | None = None,
) -> InstitutionLifecycleRun:
    if task_run.run_id != run.id:
        raise LifecycleAutomationError("Task does not belong to the requested run.", code="task_run_mismatch")
    if run.status in TERMINAL_RUN_STATUSES:
        raise LifecycleAutomationError("Cannot update tasks on a terminal lifecycle run.", code="terminal_run")

    from .control_plane import build_control_plane_summary

    control_plane_summary = build_control_plane_summary()
    blockers = evaluate_validation_key(
        run,
        task_run.template_task.validation_key,
        control_plane_summary=control_plane_summary,
    )
    if blockers:
        task_run.status = InstitutionLifecycleTaskRun.STATUS_BLOCKED
        task_run.blocker_message = " ".join(blocker["message"] for blocker in blockers)
        task_run.notes = notes
        task_run.evidence = _build_task_evidence(
            run,
            task_run,
            control_plane_summary=control_plane_summary,
            action="blocked",
            notes=notes,
            provided_evidence=evidence,
            blockers=blockers,
        )
        task_run.save(update_fields=["status", "blocker_message", "notes", "evidence", "updated_at"])
        refreshed = refresh_lifecycle_run(run)
        raise LifecycleAutomationError(
            "This task is blocked until its critical readiness issues are resolved.",
            code="task_blocked",
            blockers=blockers,
            details={"run_id": refreshed.id, "task_run_id": task_run.id},
        )

    update_fields = ["status", "blocker_message", "notes", "evidence", "updated_at"]
    task_run.status = InstitutionLifecycleTaskRun.STATUS_COMPLETED
    task_run.blocker_message = ""
    task_run.notes = notes
    task_run.evidence = _build_task_evidence(
        run,
        task_run,
        control_plane_summary=control_plane_summary,
        action="completed",
        notes=notes,
        provided_evidence=evidence,
    )
    task_run.completed_at = timezone.now()
    task_run.waived_at = None
    task_run.waived_by = None
    update_fields.extend(["completed_at", "waived_at", "waived_by"])
    if completed_by is not None:
        task_run.completed_by = completed_by
        update_fields.append("completed_by")
    task_run.save(update_fields=update_fields)
    return refresh_lifecycle_run(run)


@transaction.atomic
def waive_task_run(
    run: InstitutionLifecycleRun,
    task_run: InstitutionLifecycleTaskRun,
    *,
    waived_by=None,
    notes: str = "",
) -> InstitutionLifecycleRun:
    if task_run.run_id != run.id:
        raise LifecycleAutomationError("Task does not belong to the requested run.", code="task_run_mismatch")
    if not task_run.template_task.waivable:
        raise LifecycleAutomationError("This task cannot be waived.", code="task_not_waivable")
    if run.status in TERMINAL_RUN_STATUSES:
        raise LifecycleAutomationError("Cannot update tasks on a terminal lifecycle run.", code="terminal_run")
    if not notes.strip():
        raise LifecycleAutomationError("Waiver notes are required.", code="waiver_notes_required")

    from .control_plane import build_control_plane_summary

    control_plane_summary = build_control_plane_summary()
    blockers = evaluate_validation_key(
        run,
        task_run.template_task.validation_key,
        control_plane_summary=control_plane_summary,
    )
    task_run.status = InstitutionLifecycleTaskRun.STATUS_WAIVED
    task_run.notes = notes
    task_run.evidence = _build_task_evidence(
        run,
        task_run,
        control_plane_summary=control_plane_summary,
        action="waived",
        notes=notes,
        blockers=blockers,
    )
    task_run.blocker_message = ""
    task_run.completed_at = None
    task_run.completed_by = None
    task_run.waived_at = timezone.now()
    if waived_by is not None:
        task_run.waived_by = waived_by
    task_run.save(
        update_fields=[
            "status",
            "notes",
            "evidence",
            "blocker_message",
            "completed_at",
            "completed_by",
            "waived_at",
            "waived_by",
            "updated_at",
        ]
    )
    return refresh_lifecycle_run(run)


@transaction.atomic
def complete_lifecycle_run(run: InstitutionLifecycleRun, *, completed_by=None) -> InstitutionLifecycleRun:
    if run.status == InstitutionLifecycleRun.STATUS_COMPLETED:
        raise LifecycleAutomationError("This lifecycle run is already completed.", code="already_completed")
    if run.status == InstitutionLifecycleRun.STATUS_CANCELLED:
        raise LifecycleAutomationError("This lifecycle run has been cancelled.", code="terminal_run")

    refreshed = refresh_lifecycle_run(run)
    unresolved_tasks = list(
        refreshed.task_runs.select_related("template_task").filter(
            template_task__required=True,
            status__in=[
                InstitutionLifecycleTaskRun.STATUS_PENDING,
                InstitutionLifecycleTaskRun.STATUS_BLOCKED,
            ],
        )
    )
    if unresolved_tasks:
        raise LifecycleAutomationError(
            "All required lifecycle tasks must be completed or waived before the run can finish.",
            code="run_incomplete",
            details={
                "pending_task_ids": [task.id for task in unresolved_tasks],
                "pending_task_titles": [task.template_task.title for task in unresolved_tasks],
            },
        )

    critical_blockers = refreshed.summary.get("critical_blocker_count", 0)
    if critical_blockers:
        refreshed.status = InstitutionLifecycleRun.STATUS_BLOCKED
        refreshed.save(update_fields=["status", "updated_at"])
        raise LifecycleAutomationError(
            "Critical control-plane blockers still exist, so this lifecycle run cannot be completed.",
            code="critical_blockers_remaining",
        )

    if refreshed.started_at is None:
        refreshed.started_at = timezone.now()
        if completed_by is not None:
            refreshed.started_by = completed_by

    execution_effect = _apply_completion_effects(refreshed)
    if execution_effect:
        _record_execution_effect(refreshed, execution_effect)

    refreshed.status = InstitutionLifecycleRun.STATUS_COMPLETED
    refreshed.completed_at = timezone.now()
    if completed_by is not None:
        refreshed.completed_by = completed_by
    refreshed.save(
        update_fields=[
            "started_at",
            "started_by",
            "metadata",
            "status",
            "completed_at",
            "completed_by",
            "updated_at",
        ]
    )
    return refresh_lifecycle_run(refreshed)


def build_lifecycle_section() -> dict[str, Any]:
    templates = ensure_lifecycle_templates()
    blockers: list[dict[str, Any]] = []
    route = "/settings/control-plane"
    api_path = "/api/settings/lifecycle-runs/"
    latest_runs: list[dict[str, Any]] = []

    for template in templates:
        latest_run = (
            template.runs.select_related("target_academic_year", "target_term").order_by("-created_at", "-id").first()
        )
        if latest_run:
            latest_runs.append(
                {
                    "id": latest_run.id,
                    "template_code": template.code,
                    "template_name": template.name,
                    "status": latest_run.status,
                    "target_academic_year": latest_run.target_academic_year.name if latest_run.target_academic_year else None,
                    "target_term": latest_run.target_term.name if latest_run.target_term else None,
                    "completed_at": latest_run.completed_at.isoformat() if latest_run.completed_at else None,
                }
            )
        if latest_run and latest_run.status == InstitutionLifecycleRun.STATUS_BLOCKED:
            blockers.append(
                {
                    "section": "lifecycle",
                    "severity": "WARNING",
                    "code": f"blocked_{template.code.lower()}_run",
                    "message": f"The latest {template.name.lower()} run is blocked.",
                    "route": route,
                    "api_path": api_path,
                }
            )

    if not InstitutionLifecycleRun.objects.filter(
        template__code=TEMPLATE_CODE_TENANT_ONBOARDING,
        status=InstitutionLifecycleRun.STATUS_COMPLETED,
    ).exists():
        blockers.append(
            {
                "section": "lifecycle",
                "severity": "INFO",
                "code": "onboarding_not_completed",
                "message": "No completed tenant onboarding run exists yet.",
                "route": route,
                "api_path": api_path,
            }
        )

    section_status = "READY"
    severities = {blocker["severity"] for blocker in blockers}
    if "CRITICAL" in severities:
        section_status = "NOT_READY"
    elif "WARNING" in severities:
        section_status = "PARTIALLY_READY"

    return {
        "label": "Lifecycle Automation",
        "status": section_status,
        "owner": {
            "section": "lifecycle",
            "route": route,
            "api_path": api_path,
        },
        "data": {
            "template_count": len(templates),
            "run_count": InstitutionLifecycleRun.objects.count(),
            "latest_runs": latest_runs,
        },
        "blockers": blockers,
    }
