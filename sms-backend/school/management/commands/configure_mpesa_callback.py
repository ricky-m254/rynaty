"""
Management command: configure_mpesa_callback

Detects the publicly reachable HTTPS base URL for this deployment and writes it
into TenantSettings (key: ``system.callback_base_url``) for every tenant schema.
The M-Pesa STK push view reads this setting so Safaricom's callback reaches the
correct host regardless of which deploy environment is active.

DEFAULT BEHAVIOUR (safe for startup scripts)
    Any tenant that already has a non-empty ``system.callback_base_url`` value is
    skipped.  This preserves URLs that an admin has set manually via the
    Settings → Integrations → M-Pesa UI.  Only schemas with no existing value
    are written.

Use ``--force`` to override all existing values (e.g. after a domain migration).

Priority order for URL detection:
    1. SITE_BASE_URL environment variable (set manually by operator)
    2. First non-empty domain from REPLIT_DOMAINS environment variable
    3. Falls back to empty string — existing TenantSettings value is preserved,
       and the STK push view falls back to request.build_absolute_uri().

Usage:
    python manage.py configure_mpesa_callback
    python manage.py configure_mpesa_callback --schema demo_school
    python manage.py configure_mpesa_callback --all-tenants
    python manage.py configure_mpesa_callback --force
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


def _apply_to_schema(
    schema_name: str,
    base_url: str,
    stdout,
    style,
    force: bool = False,
) -> None:
    """
    Write the base URL into TenantSettings for the given schema.

    Default (force=False):
        Skip if the schema already has a non-empty system.callback_base_url,
        preserving values set by admins via the Settings UI.
        If base_url is also empty, keep the existing value (transient failure
        protection).

    force=True:
        Overwrite any existing value unconditionally. Use only when
        intentionally migrating to a new domain.
    """
    from school.models import TenantSettings

    try:
        with schema_context(schema_name):
            existing = TenantSettings.objects.filter(
                key="system.callback_base_url"
            ).values_list("value", flat=True).first()

            if not base_url:
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

            if not force and existing:
                stdout.write(
                    f"  [{schema_name}] Skipped: existing value kept: {existing!r} "
                    "(use --force to overwrite)"
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
        "(key: system.callback_base_url) for use by the M-Pesa STK callback. "
        "Existing admin-set values are preserved by default (use --force to overwrite)."
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
        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Overwrite any existing system.callback_base_url value, including those "
                "set manually by an admin. Use only after an intentional domain migration."
            ),
        )

    def handle(self, *args, **options):
        base_url = _detect_base_url()
        force = options.get("force", False)

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

        if force:
            self.stdout.write(
                self.style.WARNING(
                    "[mpesa-callback] --force is set: existing values will be overwritten."
                )
            )
        else:
            self.stdout.write(
                "[mpesa-callback] Existing admin-set values will be preserved "
                "(pass --force to override)."
            )

        schema_name = options.get("schema")
        all_tenants = options.get("all_tenants", False)

        if schema_name and all_tenants:
            self.stderr.write(
                self.style.ERROR("Use either --schema or --all-tenants, not both.")
            )
            return

        if schema_name:
            _apply_to_schema(schema_name, base_url, self.stdout, self.style, force=force)
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
            _apply_to_schema(schema, base_url, self.stdout, self.style, force=force)

        self.stdout.write(
            self.style.SUCCESS(
                f"[mpesa-callback] Done. Processed {len(tenant_schemas)} tenant schema(s)."
            )
        )
