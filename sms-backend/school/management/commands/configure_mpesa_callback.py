"""
Management command: configure_mpesa_callback

Detects the publicly reachable HTTPS base URL for this deployment and writes it
into TenantSettings (key: ``system.callback_base_url``) for every tenant schema.
The M-Pesa STK push view reads this setting so Safaricom's callback reaches the
correct host regardless of which deploy environment is active.

Priority order for URL detection:
    1. SITE_BASE_URL environment variable (set manually by operator)
    2. First non-empty domain from REPLIT_DOMAINS environment variable
    3. Falls back to empty string — existing TenantSettings value is preserved,
       and the STK push view falls back to request.build_absolute_uri().

Usage:
    python manage.py configure_mpesa_callback
    python manage.py configure_mpesa_callback --schema demo_school
    python manage.py configure_mpesa_callback --all-tenants
"""
import os

from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context

from clients.models import Tenant


def _detect_base_url() -> str:
    """
    Return the public HTTPS base URL (no trailing slash) or empty string.
    Warns if SITE_BASE_URL is set but does not start with https://.
    """
    site_base = os.environ.get("SITE_BASE_URL", "").strip().rstrip("/")
    if site_base:
        if not site_base.startswith("https://"):
            import logging
            logging.getLogger(__name__).warning(
                "SITE_BASE_URL=%r does not start with 'https://'. "
                "Safaricom requires HTTPS for STK push callbacks in production.",
                site_base,
            )
        return site_base

    replit_domains = os.environ.get("REPLIT_DOMAINS", "").strip()
    if replit_domains:
        first_domain = replit_domains.split(",")[0].strip()
        if first_domain:
            return f"https://{first_domain}"

    return ""


def _apply_to_schema(schema_name: str, base_url: str, stdout, style) -> None:
    """
    Write the base URL into TenantSettings for the given schema.
    If base_url is empty, the existing stored value is preserved so that a
    transient detection failure does not overwrite a previously valid setting.
    """
    from school.models import TenantSettings

    try:
        with schema_context(schema_name):
            if not base_url:
                existing = TenantSettings.objects.filter(
                    key="system.callback_base_url"
                ).values_list("value", flat=True).first()
                if existing:
                    stdout.write(
                        f"  [{schema_name}] No URL detected — keeping existing value: {existing!r}"
                    )
                else:
                    stdout.write(
                        style.WARNING(
                            f"  [{schema_name}] No URL detected and no existing value — skipping."
                        )
                    )
                return

            _, created = TenantSettings.objects.update_or_create(
                key="system.callback_base_url",
                defaults={
                    "value": base_url,
                    "category": "system",
                    "description": (
                        "Public HTTPS base URL used for M-Pesa STK callback URL. "
                        "Auto-detected from SITE_BASE_URL or REPLIT_DOMAINS at startup."
                    ),
                },
            )
            action = "Created" if created else "Updated"
            stdout.write(
                style.SUCCESS(
                    f"  [{schema_name}] {action} system.callback_base_url = {base_url!r}"
                )
            )
    except Exception as exc:
        stdout.write(
            style.WARNING(f"  [{schema_name}] Could not update callback base URL: {exc}")
        )


class Command(BaseCommand):
    help = (
        "Detect this deployment's public base URL and store it in TenantSettings "
        "(key: system.callback_base_url) for use by the M-Pesa STK callback."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            default=None,
            help="Target a single tenant schema.",
        )
        parser.add_argument(
            "--all-tenants",
            action="store_true",
            help="Apply to all tenant schemas (default when neither --schema nor --all-tenants is given).",
        )

    def handle(self, *args, **options):
        base_url = _detect_base_url()

        if base_url:
            self.stdout.write(
                self.style.SUCCESS(
                    f"[mpesa-callback] Detected public callback base URL: {base_url}"
                )
            )
            self.stdout.write(
                f"[mpesa-callback] Full callback URL will be: {base_url}/api/finance/mpesa/callback/"
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "[mpesa-callback] No public base URL detected "
                    "(SITE_BASE_URL and REPLIT_DOMAINS are both unset). "
                    "Existing TenantSettings values will be preserved; "
                    "M-Pesa callbacks will fall back to request.build_absolute_uri()."
                )
            )

        schema_name = options.get("schema")
        all_tenants = options.get("all_tenants", False)

        if schema_name and all_tenants:
            self.stderr.write(
                self.style.ERROR("Use either --schema or --all-tenants, not both.")
            )
            return

        if schema_name:
            _apply_to_schema(schema_name, base_url, self.stdout, self.style)
            return

        tenant_schemas = list(
            Tenant.objects.exclude(schema_name="public").values_list(
                "schema_name", flat=True
            )
        )

        if not tenant_schemas:
            self.stdout.write(
                self.style.WARNING("[mpesa-callback] No tenant schemas found; nothing to do.")
            )
            return

        for schema in tenant_schemas:
            _apply_to_schema(schema, base_url, self.stdout, self.style)

        self.stdout.write(
            self.style.SUCCESS(
                f"[mpesa-callback] Done. Updated {len(tenant_schemas)} tenant schema(s)."
            )
        )
