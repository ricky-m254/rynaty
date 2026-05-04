from __future__ import annotations

from .campaign_stats import ensure_campaign_stats, sync_campaign_stats
from .delivery_backbone import ensure_campaign_unified_message
from .dispatch_queue import dispatch_due_email_campaigns, enqueue_email_campaign_delivery
from .models import EmailRecipient


def queue_campaign_recipients(campaign, emails: list[str]) -> dict[str, int]:
    if emails:
        ensure_campaign_unified_message(campaign)
    ensure_campaign_stats(campaign)
    existing = set(campaign.recipients.values_list("email", flat=True))
    queued = 0
    failed = 0
    for email in emails:
        if email in existing:
            continue
        if "@" not in email:
            EmailRecipient.objects.create(
                campaign=campaign,
                email=email,
                status="Failed",
                bounce_reason="Invalid email format.",
            )
            failed += 1
            existing.add(email)
            continue
        EmailRecipient.objects.create(
            campaign=campaign,
            email=email,
            status="Queued",
        )
        queued += 1
        existing.add(email)
    sync_campaign_stats(campaign)
    return {"queued": queued, "failed": failed}


def dispatch_email_campaign(campaign):
    return enqueue_email_campaign_delivery(campaign)
