from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Prefetch, Q
from django.utils import timezone

from ..models import StatutoryDeductionBand, StatutoryDeductionRule


MONEY_QUANTUM = Decimal("0.01")


KENYA_DEFAULT_RULES = [
    {
        "code": "PAYE",
        "name": "Pay As You Earn",
        "calculation_method": "BAND",
        "base_name": "TAXABLE_PAY",
        "employee_rate": Decimal("0.00"),
        "employer_rate": Decimal("0.00"),
        "fixed_amount": Decimal("0.00"),
        "minimum_amount": Decimal("0.00"),
        "maximum_amount": None,
        "relief_amount": Decimal("2400.00"),
        "is_kenya_default": True,
        "is_mandatory": True,
        "effective_from": date(2023, 7, 1),
        "priority": 100,
        "configuration_notes": (
            "Kenya PAYE monthly bands as published by KRA under the Finance Act 2023, "
            "effective July 1, 2023."
        ),
        "bands": [
            {"lower_bound": Decimal("0.00"), "upper_bound": Decimal("24000.00"), "employee_rate": Decimal("10.00")},
            {"lower_bound": Decimal("24000.00"), "upper_bound": Decimal("32333.00"), "employee_rate": Decimal("25.00")},
            {"lower_bound": Decimal("32333.00"), "upper_bound": Decimal("500000.00"), "employee_rate": Decimal("30.00")},
            {"lower_bound": Decimal("500000.00"), "upper_bound": Decimal("800000.00"), "employee_rate": Decimal("32.50")},
            {"lower_bound": Decimal("800000.00"), "upper_bound": None, "employee_rate": Decimal("35.00")},
        ],
    },
    {
        "code": "NSSF",
        "name": "National Social Security Fund",
        "calculation_method": "BAND",
        "base_name": "PENSIONABLE_PAY",
        "employee_rate": Decimal("0.00"),
        "employer_rate": Decimal("0.00"),
        "fixed_amount": Decimal("0.00"),
        "minimum_amount": Decimal("0.00"),
        "maximum_amount": None,
        "relief_amount": Decimal("0.00"),
        "is_kenya_default": True,
        "is_mandatory": True,
        "effective_from": date(2026, 2, 1),
        "priority": 200,
        "configuration_notes": (
            "Kenya NSSF year 4 contribution rates from February 2026: tier I lower limit "
            "Ksh 9,000 and upper limit Ksh 108,000 at 6% employee and 6% employer."
        ),
        "bands": [
            {
                "lower_bound": Decimal("0.00"),
                "upper_bound": Decimal("9000.00"),
                "employee_rate": Decimal("6.00"),
                "employer_rate": Decimal("6.00"),
            },
            {
                "lower_bound": Decimal("9000.00"),
                "upper_bound": Decimal("108000.00"),
                "employee_rate": Decimal("6.00"),
                "employer_rate": Decimal("6.00"),
            },
        ],
    },
    {
        "code": "SHIF",
        "name": "Social Health Insurance Fund",
        "calculation_method": "PERCENT",
        "base_name": "GROSS_PAY",
        "employee_rate": Decimal("2.75"),
        "employer_rate": Decimal("0.00"),
        "fixed_amount": Decimal("0.00"),
        "minimum_amount": Decimal("300.00"),
        "maximum_amount": None,
        "relief_amount": Decimal("0.00"),
        "is_kenya_default": True,
        "is_mandatory": True,
        "effective_from": date(2024, 10, 1),
        "priority": 300,
        "configuration_notes": (
            "SHA guidance states SHIF contribution is 2.75% of household income with a "
            "minimum monthly premium of Ksh 300."
        ),
        "bands": [],
    },
    {
        "code": "HOUSING_LEVY",
        "name": "Affordable Housing Levy",
        "calculation_method": "PERCENT",
        "base_name": "GROSS_PAY",
        "employee_rate": Decimal("1.50"),
        "employer_rate": Decimal("1.50"),
        "fixed_amount": Decimal("0.00"),
        "minimum_amount": Decimal("0.00"),
        "maximum_amount": None,
        "relief_amount": Decimal("0.00"),
        "is_kenya_default": True,
        "is_mandatory": True,
        "effective_from": date(2024, 3, 19),
        "priority": 400,
        "configuration_notes": (
            "KRA Affordable Housing Levy collection notice: employee 1.5% of gross salary "
            "and employer 1.5% of gross salary from March 19, 2024."
        ),
        "bands": [],
    },
]


def _to_decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def round_money(value) -> Decimal:
    return _to_decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _apply_min_max(amount: Decimal, rule: StatutoryDeductionRule) -> Decimal:
    normalized = round_money(amount)
    minimum_amount = round_money(rule.minimum_amount)
    if minimum_amount > 0 and normalized > 0 and normalized < minimum_amount:
        normalized = minimum_amount
    maximum_amount = getattr(rule, "maximum_amount", None)
    if maximum_amount is not None:
        max_value = round_money(maximum_amount)
        if max_value > 0 and normalized > max_value:
            normalized = max_value
    return normalized


def _iter_bands(rule: StatutoryDeductionRule):
    band_manager = getattr(rule, "bands", None)
    if band_manager is None:
        return []
    if hasattr(band_manager, "all"):
        return list(band_manager.filter(is_active=True).order_by("display_order", "id"))
    return list(band_manager)


def get_active_statutory_rules(*, as_of_date: date | None = None):
    effective_date = as_of_date or timezone.now().date()
    return (
        StatutoryDeductionRule.objects.filter(
            is_active=True,
            effective_from__lte=effective_date,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=effective_date))
        .prefetch_related(
            Prefetch(
                "bands",
                queryset=StatutoryDeductionBand.objects.filter(is_active=True).order_by("display_order", "id"),
            )
        )
        .order_by("priority", "code", "-effective_from", "id")
    )


def calculate_rule_amount(rule: StatutoryDeductionRule, base_amount) -> dict:
    base_value = max(_to_decimal(base_amount), Decimal("0.00"))
    employee_amount = Decimal("0.00")
    employer_amount = Decimal("0.00")
    applied_bands = []
    applied_rate = _to_decimal(rule.employee_rate)

    if rule.calculation_method == "FIXED":
        employee_amount = _to_decimal(rule.fixed_amount)
        employer_amount = _to_decimal(rule.fixed_amount) if _to_decimal(rule.employer_rate) > 0 else Decimal("0.00")
        applied_rate = Decimal("0.00")
    elif rule.calculation_method == "PERCENT":
        employee_amount = base_value * _to_decimal(rule.employee_rate) / Decimal("100.00")
        employer_amount = base_value * _to_decimal(rule.employer_rate) / Decimal("100.00")
        applied_rate = _to_decimal(rule.employee_rate)
    elif rule.calculation_method == "BAND":
        max_band_rate = Decimal("0.00")
        for band in _iter_bands(rule):
            lower_bound = _to_decimal(band.lower_bound)
            upper_bound = _to_decimal(band.upper_bound) if band.upper_bound is not None else None
            if base_value <= lower_bound:
                continue
            cap = base_value if upper_bound is None else min(base_value, upper_bound)
            band_base = cap - lower_bound
            if band_base <= 0:
                continue

            band_employee = band_base * _to_decimal(band.employee_rate) / Decimal("100.00")
            band_employer = band_base * _to_decimal(band.employer_rate) / Decimal("100.00")
            if _to_decimal(band.fixed_amount):
                band_employee += _to_decimal(band.fixed_amount)
            if _to_decimal(band.additional_amount):
                band_employee += _to_decimal(band.additional_amount)

            employee_amount += band_employee
            employer_amount += band_employer
            max_band_rate = max(max_band_rate, _to_decimal(band.employee_rate))
            applied_bands.append(
                {
                    "display_order": band.display_order,
                    "lower_bound": str(round_money(lower_bound)),
                    "upper_bound": str(round_money(upper_bound)) if upper_bound is not None else None,
                    "band_base": str(round_money(band_base)),
                    "employee_rate": str(_to_decimal(band.employee_rate)),
                    "employer_rate": str(_to_decimal(band.employer_rate)),
                    "employee_amount": str(round_money(band_employee)),
                    "employer_amount": str(round_money(band_employer)),
                }
            )
        applied_rate = max_band_rate

    employee_amount = _apply_min_max(employee_amount, rule)
    employer_amount = _apply_min_max(employer_amount, rule)
    relief_amount = round_money(rule.relief_amount)
    if relief_amount > 0:
        employee_amount = max(employee_amount - relief_amount, Decimal("0.00"))

    return {
        "code": rule.code,
        "name": rule.name,
        "base_name": rule.base_name,
        "base_amount": round_money(base_value),
        "employee_amount": round_money(employee_amount),
        "employer_amount": round_money(employer_amount),
        "applied_rate": round_money(applied_rate),
        "relief_amount": relief_amount,
        "applied_bands": applied_bands,
        "snapshot": {
            "code": rule.code,
            "name": rule.name,
            "calculation_method": rule.calculation_method,
            "base_name": rule.base_name,
            "employee_rate": str(_to_decimal(rule.employee_rate)),
            "employer_rate": str(_to_decimal(rule.employer_rate)),
            "fixed_amount": str(round_money(rule.fixed_amount)),
            "minimum_amount": str(round_money(rule.minimum_amount)),
            "maximum_amount": str(round_money(rule.maximum_amount)) if rule.maximum_amount is not None else None,
            "relief_amount": str(relief_amount),
            "effective_from": rule.effective_from.isoformat(),
            "effective_to": rule.effective_to.isoformat() if rule.effective_to else None,
            "bands": applied_bands,
        },
    }


def build_statutory_snapshot(rules) -> list[dict]:
    snapshot = []
    for rule in rules:
        snapshot.append(
            {
                "code": rule.code,
                "name": rule.name,
                "calculation_method": rule.calculation_method,
                "base_name": rule.base_name,
                "employee_rate": str(_to_decimal(rule.employee_rate)),
                "employer_rate": str(_to_decimal(rule.employer_rate)),
                "fixed_amount": str(round_money(rule.fixed_amount)),
                "minimum_amount": str(round_money(rule.minimum_amount)),
                "maximum_amount": str(round_money(rule.maximum_amount)) if rule.maximum_amount is not None else None,
                "relief_amount": str(round_money(rule.relief_amount)),
                "effective_from": rule.effective_from.isoformat(),
                "effective_to": rule.effective_to.isoformat() if rule.effective_to else None,
                "priority": rule.priority,
                "bands": [
                    {
                        "lower_bound": str(round_money(band.lower_bound)),
                        "upper_bound": str(round_money(band.upper_bound)) if band.upper_bound is not None else None,
                        "employee_rate": str(_to_decimal(band.employee_rate)),
                        "employer_rate": str(_to_decimal(band.employer_rate)),
                        "fixed_amount": str(round_money(band.fixed_amount)),
                        "additional_amount": str(round_money(band.additional_amount)),
                        "display_order": band.display_order,
                    }
                    for band in _iter_bands(rule)
                ],
            }
        )
    return snapshot


def apply_statutory_rules_to_bases(base_amounts: dict[str, Decimal], *, as_of_date: date | None = None, rules=None) -> dict:
    active_rules = list(rules) if rules is not None else list(get_active_statutory_rules(as_of_date=as_of_date))
    normalized_bases = {key: round_money(value) for key, value in (base_amounts or {}).items()}
    fallback_base = normalized_bases.get("GROSS_PAY", Decimal("0.00"))
    results = []
    for rule in active_rules:
        base_amount = normalized_bases.get(rule.base_name, fallback_base)
        results.append(calculate_rule_amount(rule, base_amount))
    employee_total = sum((result["employee_amount"] for result in results), Decimal("0.00"))
    employer_total = sum((result["employer_amount"] for result in results), Decimal("0.00"))
    return {
        "base_amounts": {name: round_money(value) for name, value in normalized_bases.items()},
        "employee_total": round_money(employee_total),
        "employer_total": round_money(employer_total),
        "results": results,
        "snapshot": build_statutory_snapshot(active_rules),
    }


def apply_statutory_rules(base_amount, *, as_of_date: date | None = None, rules=None) -> dict:
    result = apply_statutory_rules_to_bases(
        {
            "BASIC_PAY": base_amount,
            "GROSS_PAY": base_amount,
            "TAXABLE_PAY": base_amount,
            "PENSIONABLE_PAY": base_amount,
        },
        as_of_date=as_of_date,
        rules=rules,
    )
    result["base_amount"] = round_money(base_amount)
    return result


def ensure_kenya_first_statutory_defaults():
    created_or_existing = []
    for definition in KENYA_DEFAULT_RULES:
        bands = definition["bands"]
        defaults = {key: value for key, value in definition.items() if key != "bands"}
        rule, _ = StatutoryDeductionRule.objects.get_or_create(
            code=definition["code"],
            effective_from=definition["effective_from"],
            defaults=defaults,
        )
        for index, band in enumerate(bands, start=1):
            StatutoryDeductionBand.objects.get_or_create(
                rule=rule,
                display_order=band.get("display_order", index),
                defaults={
                    "lower_bound": band["lower_bound"],
                    "upper_bound": band["upper_bound"],
                    "employee_rate": band.get("employee_rate", Decimal("0.00")),
                    "employer_rate": band.get("employer_rate", Decimal("0.00")),
                    "fixed_amount": band.get("fixed_amount", Decimal("0.00")),
                    "additional_amount": band.get("additional_amount", Decimal("0.00")),
                    "is_active": True,
                },
            )
        created_or_existing.append(rule)
    return created_or_existing
