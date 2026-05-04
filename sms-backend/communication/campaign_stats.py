from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Max, Q, Sum

from .models import CampaignStats, EmailCampaign
from .services import now_ts

EMAIL_SUCCESS_STATUSES = {"Sent", "Delivered", "Opened", "Clicked"}
EMAIL_DELIVERED_STATUSES = {"Delivered", "Opened", "Clicked"}
EMAIL_OPENED_STATUSES = {"Opened", "Clicked"}
EMAIL_FAILED_STATUSES = {"Failed", "Bounced"}


def _rate(numerator: int, denominator: int) -> Decimal:
    if not denominator:
        return Decimal("0.00")
    return (Decimal(numerator) * Decimal("100.00") / Decimal(denominator)).quantize(Decimal("0.01"))


def sync_campaign_stats(campaign: EmailCampaign):
    metrics = campaign.recipients.aggregate(
        total_recipients=Count("id"),
        queued_recipients=Count("id", filter=Q(status="Queued")),
        successful_recipients=Count("id", filter=Q(status__in=EMAIL_SUCCESS_STATUSES)),
        delivered_recipients=Count("id", filter=Q(status__in=EMAIL_DELIVERED_STATUSES)),
        opened_recipients=Count("id", filter=Q(status__in=EMAIL_OPENED_STATUSES)),
        clicked_recipients=Count("id", filter=Q(status="Clicked")),
        bounced_recipients=Count("id", filter=Q(status="Bounced")),
        failed_recipients=Count("id", filter=Q(status__in=EMAIL_FAILED_STATUSES)),
        open_events=Sum("open_count"),
        click_events=Sum("click_count"),
        latest_sent_at=Max("sent_at"),
        latest_delivered_at=Max("delivered_at"),
        latest_opened_at=Max("opened_at"),
    )
    total_recipients = metrics["total_recipients"] or 0
    successful_recipients = metrics["successful_recipients"] or 0
    opened_recipients = metrics["opened_recipients"] or 0
    clicked_recipients = metrics["clicked_recipients"] or 0
    last_event_at = max(
        [
            value
            for value in [
                metrics.get("latest_sent_at"),
                metrics.get("latest_delivered_at"),
                metrics.get("latest_opened_at"),
                campaign.sent_at,
            ]
            if value
        ],
        default=None,
    )

    defaults = {
        "unified_message": campaign.unified_messages.order_by("-id").first(),
        "total_recipients": total_recipients,
        "queued_recipients": metrics["queued_recipients"] or 0,
        "successful_recipients": successful_recipients,
        "delivered_recipients": metrics["delivered_recipients"] or 0,
        "opened_recipients": opened_recipients,
        "clicked_recipients": clicked_recipients,
        "bounced_recipients": metrics["bounced_recipients"] or 0,
        "failed_recipients": metrics["failed_recipients"] or 0,
        "open_events": metrics["open_events"] or 0,
        "click_events": metrics["click_events"] or 0,
        "delivery_rate": _rate(successful_recipients, total_recipients),
        "open_rate": _rate(opened_recipients, total_recipients),
        "click_rate": _rate(clicked_recipients, total_recipients),
        "last_event_at": last_event_at,
        "last_synced_at": now_ts(),
    }
    stats, _created = CampaignStats.objects.update_or_create(campaign=campaign, defaults=defaults)
    return stats


def ensure_campaign_stats(campaign: EmailCampaign):
    stats = CampaignStats.objects.filter(campaign=campaign).first()
    if stats is not None:
        return stats
    return sync_campaign_stats(campaign)
