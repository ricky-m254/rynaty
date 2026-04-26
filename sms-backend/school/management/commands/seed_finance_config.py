"""
seed_finance_config
-------------------
Fills realistic finance and M-Pesa settings for one or all tenant schemas.

Usage:
    python manage.py seed_finance_config                   # all tenants
    python manage.py seed_finance_config --schema demo_school

What it does:
    1. SchoolProfile  — currency, tax, prefixes, late-fee policy,
                        accepted payment methods
    2. TenantSettings — integrations.mpesa with Safaricom Daraja 2.0
                        sandbox credentials (shortcode + passkey are
                        always the same for Safaricom sandbox;
                        consumer_key / consumer_secret must be replaced
                        with real app credentials from
                        developer.safaricom.co.ke)
    3. LateFeeRule    — two tiered rules (7-day / 30-day)
    4. Callback URL   — system.callback_base_url from SITE_BASE_URL env

Idempotent: safe to run multiple times.  Existing M-Pesa credentials
(consumer_key / consumer_secret) are preserved if already set.
"""

import os
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import connection


FINANCE_DEFAULTS = {
    "currency": "KES",
    "tax_percentage": Decimal("0.00"),
    "receipt_prefix": "RYNT-RCT-",
    "invoice_prefix": "RYNT-INV-",
    "late_fee_grace_days": 7,
    "late_fee_type": "FLAT",
    "late_fee_value": Decimal("500.00"),
    "late_fee_max": Decimal("2000.00"),
    "accepted_payment_methods": [
        "Cash",
        "MPesa",
        "Bank Transfer",
        "Cheque",
        "Card",
    ],
}

MPESA_SANDBOX_DEFAULTS = {
    "environment": "sandbox",
    "shortcode": "174379",
    "passkey": "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919",
}

LATE_FEE_RULES = [
    {
        "grace_days": 7,
        "fee_type": "FLAT",
        "value": Decimal("500.00"),
        "max_fee": Decimal("2000.00"),
        "is_active": True,
    },
    {
        "grace_days": 30,
        "fee_type": "PERCENT",
        "value": Decimal("2.00"),
        "max_fee": Decimal("5000.00"),
        "is_active": True,
    },
]


class Command(BaseCommand):
    help = "Seed realistic finance & M-Pesa configuration for tenant schemas."

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            default=None,
            help="Specific schema to seed (default: all tenant schemas).",
        )
        parser.add_argument(
            "--force-mpesa",
            action="store_true",
            default=False,
            help="Overwrite consumer_key/secret even if already set.",
        )

    def handle(self, *args, **options):
        from django_tenants.utils import get_public_schema_name, schema_context
        from clients.models import Tenant

        target = options["schema"]
        force_mpesa = options["force_mpesa"]

        if target:
            schemas = [target]
        else:
            connection.set_schema_to_public()
            public = get_public_schema_name()
            schemas = list(
                Tenant.objects.exclude(schema_name=public)
                .values_list("schema_name", flat=True)
            )

        for schema in schemas:
            self.stdout.write(f"[seed_finance_config] Schema: {schema}")
            try:
                with schema_context(schema):
                    self._seed_finance(schema)
                    self._seed_mpesa(schema, force_mpesa)
                    self._seed_late_fee_rules(schema)
                    self._seed_callback_url(schema)
            except Exception as exc:
                self.stderr.write(
                    self.style.ERROR(
                        f"  ERROR on schema {schema!r}: {exc}"
                    )
                )

        self.stdout.write(self.style.SUCCESS("[seed_finance_config] Done."))

    def _seed_finance(self, schema):
        from school.models import SchoolProfile

        sp = SchoolProfile.objects.first()
        if not sp:
            self.stdout.write(f"  [{schema}] No SchoolProfile — skipping finance fields")
            return

        changed = []
        for field, value in FINANCE_DEFAULTS.items():
            current = getattr(sp, field)
            if current != value:
                setattr(sp, field, value)
                changed.append(field)

        if changed:
            sp.save(update_fields=changed)
            self.stdout.write(
                self.style.SUCCESS(f"  [{schema}] SchoolProfile updated: {', '.join(changed)}")
            )
        else:
            self.stdout.write(f"  [{schema}] SchoolProfile already up-to-date")

    def _seed_mpesa(self, schema, force_mpesa):
        from school.models import TenantSettings
        from school.tenant_secrets import merge_tenant_setting_secrets, sanitize_tenant_setting_value_for_storage

        obj, created = TenantSettings.objects.get_or_create(
            key="integrations.mpesa",
            defaults={
                "value": {},
                "description": "M-Pesa STK Push credentials (Daraja 2.0)",
                "category": "finance",
            },
        )

        existing = merge_tenant_setting_secrets("integrations.mpesa", obj.value) if isinstance(obj.value, dict) else {}
        updated = dict(existing)

        for k, v in MPESA_SANDBOX_DEFAULTS.items():
            updated[k] = v

        has_creds = existing.get("consumer_key") and existing.get("consumer_secret")
        if not has_creds or force_mpesa:
            updated["consumer_key"] = existing.get("consumer_key", "")
            updated["consumer_secret"] = existing.get("consumer_secret", "")
            if not has_creds:
                self.stdout.write(
                    f"  [{schema}] M-Pesa: sandbox shortcode/passkey seeded. "
                    "Add consumer_key + consumer_secret from developer.safaricom.co.ke to go live."
                )

        if updated != existing or created:
            obj.value = sanitize_tenant_setting_value_for_storage("integrations.mpesa", updated)
            obj.save(update_fields=["value"])
            status = "created" if created else "updated"
            self.stdout.write(
                self.style.SUCCESS(f"  [{schema}] TenantSettings integrations.mpesa {status}")
            )
        else:
            self.stdout.write(f"  [{schema}] M-Pesa settings already up-to-date")

    def _seed_late_fee_rules(self, schema):
        from school.models import LateFeeRule

        if LateFeeRule.objects.exists():
            self.stdout.write(
                f"  [{schema}] LateFeeRules already exist ({LateFeeRule.objects.count()}) — skipping"
            )
            return

        for rule in LATE_FEE_RULES:
            LateFeeRule.objects.create(**rule)

        self.stdout.write(
            self.style.SUCCESS(
                f"  [{schema}] Created {len(LATE_FEE_RULES)} tiered LateFeeRules"
            )
        )

    def _seed_callback_url(self, schema):
        from school.models import TenantSettings

        base = os.environ.get("SITE_BASE_URL", "").rstrip("/")
        if not base:
            replit_domains = os.environ.get("REPLIT_DOMAINS", "")
            first_domain = next(
                (d.strip() for d in replit_domains.split(",") if d.strip()), ""
            )
            if first_domain:
                base = f"https://{first_domain}"

        if not base:
            self.stdout.write(
                f"  [{schema}] No SITE_BASE_URL / REPLIT_DOMAINS — callback URL skipped"
            )
            return

        callback_url = f"{base}/api/finance/mpesa/callback/"
        obj, created = TenantSettings.objects.get_or_create(
            key="system.callback_base_url",
            defaults={"value": base, "category": "system"},
        )
        if not created and obj.value != base:
            obj.value = base
            obj.save(update_fields=["value"])
            self.stdout.write(
                self.style.SUCCESS(
                    f"  [{schema}] callback_base_url updated → {callback_url}"
                )
            )
        elif created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"  [{schema}] callback_base_url set → {callback_url}"
                )
            )
        else:
            self.stdout.write(
                f"  [{schema}] callback_base_url already correct ({callback_url})"
            )
