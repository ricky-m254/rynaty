"""
Custom Domain Onboarding Service
Handles token generation, DNS TXT verification, and domain activation.
All operations run in the public schema context.
"""
import secrets
import logging
from datetime import datetime, timezone

from django.db import connection
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)

RESERVED_SUBDOMAINS = frozenset([
    "www", "api", "admin", "platform", "app", "mail", "smtp",
    "ftp", "static", "media", "cdn", "status", "help",
])
BASE_DOMAIN = "smartcampus.co.ke"


def _generate_token() -> str:
    """Generate a 48-char URL-safe token for DNS TXT verification."""
    return "smartcampus-verify=" + secrets.token_urlsafe(32)


def _is_reserved(domain: str) -> bool:
    """Return True if the domain's leftmost label is reserved."""
    label = domain.split(".")[0].lower()
    return label in RESERVED_SUBDOMAINS


def _check_dns_txt(domain: str, expected_token: str) -> bool:
    """
    Look up TXT records for *domain* and return True if any contains
    the expected_token. Returns False on any DNS error.
    """
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, "TXT", lifetime=10)
        for rdata in answers:
            for txt_string in rdata.strings:
                decoded = txt_string.decode("utf-8", errors="ignore")
                if expected_token in decoded:
                    return True
        return False
    except Exception as exc:
        logger.info("DNS TXT check failed for %s: %s", domain, exc)
        return False


def initiate_domain_request(tenant, requested_domain: str, requested_by: str = "") -> dict:
    """
    Create or reset a domain ownership request for *tenant*.
    Returns a dict with request details and DNS instructions.
    """
    from clients.models import CustomDomainRequest, Domain, Tenant

    requested_domain = requested_domain.strip().lower()

    # Strip protocol if accidentally included
    for prefix in ("https://", "http://"):
        if requested_domain.startswith(prefix):
            requested_domain = requested_domain[len(prefix):]
    requested_domain = requested_domain.rstrip("/")

    # Validation
    if _is_reserved(requested_domain):
        raise ValueError(f"'{requested_domain}' uses a reserved name and cannot be registered.")

    if len(requested_domain) > 253:
        raise ValueError("Domain name is too long.")

    # Prevent duplicate across tenants (active/verified)
    conflict = CustomDomainRequest.objects.filter(
        requested_domain=requested_domain,
        status__in=[
            CustomDomainRequest.STATUS_VERIFIED,
            CustomDomainRequest.STATUS_ACTIVE,
        ],
    ).exclude(tenant=tenant).first()
    if conflict:
        raise ValueError("This domain is already in use by another school.")

    # Also check live Domain table
    if Domain.objects.filter(domain=requested_domain).exclude(tenant=tenant).exists():
        raise ValueError("This domain is already assigned to another school.")

    # Cancel any previous PENDING/FAILED request for this tenant
    CustomDomainRequest.objects.filter(
        tenant=tenant,
        status__in=[CustomDomainRequest.STATUS_PENDING, CustomDomainRequest.STATUS_FAILED],
    ).delete()

    token = _generate_token()
    req = CustomDomainRequest.objects.create(
        tenant=tenant,
        requested_domain=requested_domain,
        verification_token=token,
        requested_by_username=requested_by,
    )

    return _request_to_dict(req)


def verify_domain_request(tenant) -> dict:
    """
    Attempt DNS TXT verification for the tenant's active pending request.
    Updates the status and returns the updated dict.
    """
    from clients.models import CustomDomainRequest

    req = CustomDomainRequest.objects.filter(
        tenant=tenant,
        status__in=[CustomDomainRequest.STATUS_PENDING, CustomDomainRequest.STATUS_FAILED],
    ).order_by("-created_at").first()

    if not req:
        raise ValueError("No pending domain verification request found.")

    req.verification_attempts += 1
    req.last_verification_attempt = datetime.now(timezone.utc)

    if _check_dns_txt(req.requested_domain, req.verification_token):
        req.status = CustomDomainRequest.STATUS_VERIFIED
        req.verified_at = datetime.now(timezone.utc)
        req.save(update_fields=[
            "status", "verified_at", "verification_attempts", "last_verification_attempt"
        ])
    else:
        req.status = CustomDomainRequest.STATUS_FAILED
        req.save(update_fields=[
            "status", "verification_attempts", "last_verification_attempt"
        ])

    return _request_to_dict(req)


def activate_domain_request(request_id: int, platform_admin_username: str = "") -> dict:
    """
    Platform admin activates a VERIFIED domain — creates the Domain record
    and updates the tenant's custom_domain field.
    """
    from clients.models import CustomDomainRequest, Domain

    req = CustomDomainRequest.objects.select_related("tenant").get(pk=request_id)
    if req.status != CustomDomainRequest.STATUS_VERIFIED:
        raise ValueError(f"Request is '{req.status}', must be VERIFIED to activate.")

    tenant = req.tenant

    # Remove any prior custom_domain entry for this tenant
    Domain.objects.filter(tenant=tenant, is_primary=False).exclude(
        domain__endswith=BASE_DOMAIN
    ).delete()

    # Create new Domain record
    Domain.objects.get_or_create(
        domain=req.requested_domain,
        defaults={"tenant": tenant, "is_primary": False},
    )

    # Update tenant custom_domain field
    tenant.custom_domain = req.requested_domain
    tenant.save(update_fields=["custom_domain"])

    req.status = CustomDomainRequest.STATUS_ACTIVE
    req.activated_at = datetime.now(timezone.utc)
    req.notes = f"Activated by {platform_admin_username}" if platform_admin_username else req.notes
    req.save(update_fields=["status", "activated_at", "notes"])

    return _request_to_dict(req)


def reject_domain_request(request_id: int, reason: str = "", platform_admin_username: str = "") -> dict:
    """Platform admin rejects a domain request."""
    from clients.models import CustomDomainRequest

    req = CustomDomainRequest.objects.get(pk=request_id)
    req.status = CustomDomainRequest.STATUS_REJECTED
    req.rejected_at = datetime.now(timezone.utc)
    req.rejection_reason = reason
    req.notes = f"Rejected by {platform_admin_username}" if platform_admin_username else req.notes
    req.save(update_fields=["status", "rejected_at", "rejection_reason", "notes"])
    return _request_to_dict(req)


def get_current_request(tenant) -> dict | None:
    """Return the most recent domain request for the tenant, or None."""
    from clients.models import CustomDomainRequest
    req = CustomDomainRequest.objects.filter(tenant=tenant).order_by("-created_at").first()
    return _request_to_dict(req) if req else None


def _request_to_dict(req) -> dict:
    return {
        "id": req.pk,
        "tenant_schema": req.tenant.schema_name,
        "tenant_name": req.tenant.name,
        "requested_domain": req.requested_domain,
        "verification_token": req.verification_token,
        "status": req.status,
        "status_display": req.get_status_display(),
        "verification_attempts": req.verification_attempts,
        "last_verification_attempt": req.last_verification_attempt.isoformat() if req.last_verification_attempt else None,
        "verified_at": req.verified_at.isoformat() if req.verified_at else None,
        "activated_at": req.activated_at.isoformat() if req.activated_at else None,
        "rejected_at": req.rejected_at.isoformat() if req.rejected_at else None,
        "rejection_reason": req.rejection_reason,
        "requested_by_username": req.requested_by_username,
        "created_at": req.created_at.isoformat(),
        "dns_instructions": {
            "record_type": "TXT",
            "host": "@",
            "value": req.verification_token,
            "ttl": 300,
            "note": (
                f"Add a TXT record on {req.requested_domain} with the value above. "
                "DNS propagation can take up to 48 hours, but usually completes in minutes."
            ),
        },
    }
