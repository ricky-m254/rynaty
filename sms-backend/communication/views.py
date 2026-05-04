import os

from django.contrib.auth import get_user_model
from django.conf import settings
from django.db.models import Avg, Count, Q
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from school.permissions import HasModuleAccess, IsSchoolAdmin, IsTeacher
from .alert_rules import (
    build_communication_alert_summary,
    evaluate_communication_alert_rules,
    resolve_communication_alert_rule_events,
)
from .campaign_stats import ensure_campaign_stats, sync_campaign_stats
from .delivery_backbone import sync_email_delivery_webhook, sync_sms_delivery_webhook
from .gateway_status import sync_gateway_statuses
from .models import (
    Announcement,
    AnnouncementRead,
    CommunicationAlertEvent,
    CommunicationAlertRule,
    CommunicationMessage,
    Conversation,
    ConversationParticipant,
    EmailCampaign,
    EmailRecipient,
    MessageAttachment,
    MessageDelivery,
    MessageReadReceipt,
    Message,
    MessageTemplate,
    Notification,
    NotificationPreference,
    PushDevice,
    PushNotificationLog,
    SmsMessage,
    UnifiedMessage,
)
from .campaign_dispatch import (
    dispatch_due_email_campaigns,
    dispatch_email_campaign,
    queue_campaign_recipients,
)
from .dispatch_queue import (
    get_dispatch_queue_health_payload,
    queue_direct_emails,
    queue_push_notifications,
    queue_sms_messages,
)
from .gateway_settings import (
    apply_communication_gateway_settings,
    build_communication_gateway_settings_payload,
    run_communication_gateway_test,
)
from .read_models import (
    build_alerts_center_payload,
    build_campaign_performance,
    build_communication_activity_feed,
    build_delivery_reference_lookup,
    build_delivery_history,
    build_gateway_health_payload,
    build_unified_message_reference_lookup,
    build_unified_message_detail,
    build_unified_message_feed,
)
from .realtime import (
    publish_alert_event,
    publish_alert_rule_event,
    publish_delivery_webhook_event,
    publish_message_event,
    publish_notification_bulk_event,
    publish_notification_event,
)
from .serializers import (
    AnnouncementSerializer,
    CommunicationAlertEventSerializer,
    CommunicationGatewaySettingsUpdateSerializer,
    CommunicationGatewayTestRequestSerializer,
    CommunicationAlertRuleSerializer,
    CommunicationMessageSerializer,
    ConversationParticipantSerializer,
    ConversationSerializer,
    EmailCampaignSerializer,
    EmailRecipientSerializer,
    MessageSerializer,
    MessageTemplateSerializer,
    NotificationPreferenceSerializer,
    NotificationSerializer,
    PushDeviceSerializer,
    PushNotificationLogSerializer,
    SmsMessageSerializer,
)
from .services import (
    now_ts,
    render_template_placeholders,
    send_email_placeholder,
    sms_balance_placeholder,
    verify_webhook_request,
)

User = get_user_model()
EMAIL_WEBHOOK_STATUS_MAP = {
    "sent": "Sent",
    "processed": "Sent",
    "queued": "Sent",
    "delivered": "Delivered",
    "open": "Opened",
    "opened": "Opened",
    "click": "Clicked",
    "clicked": "Clicked",
    "bounce": "Bounced",
    "bounced": "Bounced",
    "dropped": "Failed",
    "deferred": "Failed",
    "failed": "Failed",
}
SMS_WEBHOOK_STATUS_MAP = {
    "queued": "Sent",
    "sent": "Sent",
    "submitted": "Sent",
    "accepted": "Sent",
    "delivered": "Delivered",
    "failed": "Failed",
    "undelivered": "Failed",
    "rejected": "Failed",
}


class CommunicationAccessMixin:
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "COMMUNICATION"


class CommunicationAdminAccessMixin(CommunicationAccessMixin):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess, IsSchoolAdmin]


def _is_admin(user):
    return hasattr(user, "userprofile") and user.userprofile.role.name in ["ADMIN", "TENANT_SUPER_ADMIN"]


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _normalize_email_list(raw_values):
    normalized = []
    for value in raw_values or []:
        email = str(value or "").strip()
        if email:
            normalized.append(email)
    return list(dict.fromkeys(normalized))


def _notification_recipient_options(query: str = "", limit: int = 200):
    rows = User.objects.filter(is_active=True).select_related("userprofile__role").order_by("username")
    query_text = str(query or "").strip()
    if query_text:
        rows = rows.filter(
            Q(username__icontains=query_text)
            | Q(email__icontains=query_text)
            | Q(first_name__icontains=query_text)
            | Q(last_name__icontains=query_text)
        )
    payload = []
    for user in rows[:limit]:
        role_name = getattr(getattr(getattr(user, "userprofile", None), "role", None), "name", "")
        payload.append(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.get_full_name().strip(),
                "role_name": role_name,
                "label": " • ".join(part for part in [user.get_full_name().strip() or user.username, role_name, user.email] if part),
            }
        )
    return payload


def _uploaded_message_files(request):
    uploads = []
    for field_name in ("attachments", "files"):
        uploads.extend(request.FILES.getlist(field_name))
    single_upload = request.FILES.get("file")
    if single_upload:
        uploads.append(single_upload)

    seen_ids = set()
    unique_uploads = []
    for upload in uploads:
        marker = id(upload)
        if marker in seen_ids:
            continue
        seen_ids.add(marker)
        unique_uploads.append(upload)
    return unique_uploads


def _message_type_for_uploads(uploads):
    if not uploads:
        return "Text"
    if all((getattr(upload, "content_type", "") or "").startswith("image/") for upload in uploads):
        return "Image"
    return "File"


class ConversationViewSet(CommunicationAccessMixin, viewsets.ModelViewSet):
    serializer_class = ConversationSerializer
    queryset = Conversation.objects.filter(is_active=True).order_by("-created_at")

    def get_queryset(self):
        user = self.request.user
        if _is_admin(user):
            return super().get_queryset()
        return (
            super().get_queryset()
            .filter(participants__user=user, participants__is_active=True)
            .distinct()
        )

    def perform_create(self, serializer):
        conversation = serializer.save(created_by=self.request.user)
        ConversationParticipant.objects.get_or_create(
            conversation=conversation,
            user=self.request.user,
            defaults={"role": "Admin", "is_active": True},
        )

    @action(detail=True, methods=["post"], url_path="participants")
    def add_participant(self, request, pk=None):
        if not ConversationParticipant.objects.filter(conversation_id=pk, user=request.user, role="Admin", is_active=True).exists() and not _is_admin(request.user):
            return Response({"error": "Only conversation admins can add participants."}, status=status.HTTP_403_FORBIDDEN)
        user_id = request.data.get("user")
        role = request.data.get("role", "Member")
        if not user_id:
            return Response({"error": "user is required"}, status=status.HTTP_400_BAD_REQUEST)
        participant, _ = ConversationParticipant.objects.update_or_create(
            conversation_id=pk,
            user_id=user_id,
            defaults={"role": role, "is_active": True},
        )
        return Response(ConversationParticipantSerializer(participant).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["delete"], url_path=r"participants/(?P<user_id>\d+)")
    def remove_participant(self, request, pk=None, user_id=None):
        if not ConversationParticipant.objects.filter(conversation_id=pk, user=request.user, role="Admin", is_active=True).exists() and not _is_admin(request.user):
            return Response({"error": "Only conversation admins can remove participants."}, status=status.HTTP_403_FORBIDDEN)
        updated = ConversationParticipant.objects.filter(conversation_id=pk, user_id=user_id).update(is_active=False)
        if not updated:
            return Response({"error": "participant not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CommunicationMessageViewSet(CommunicationAccessMixin, viewsets.ModelViewSet):
    serializer_class = CommunicationMessageSerializer
    queryset = CommunicationMessage.objects.filter(is_active=True).order_by("-sent_at")
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _summary_limit(self):
        limit_raw = self.request.query_params.get("limit")
        try:
            limit = int(limit_raw) if limit_raw is not None else 20
        except (TypeError, ValueError):
            limit = 20
        return max(1, min(limit, 100))

    def _is_activity_feed_request(self):
        if self.request.query_params.get("conversation"):
            return False
        return bool(self.request.query_params.get("ordering") or self.request.query_params.get("limit"))

    def get_queryset(self):
        qs = super().get_queryset()
        conversation = self.request.query_params.get("conversation")
        if conversation:
            qs = qs.filter(conversation_id=conversation)
        if not _is_admin(self.request.user):
            qs = qs.filter(conversation__participants__user=self.request.user, conversation__participants__is_active=True).distinct()
        ordering = (self.request.query_params.get("ordering") or "").strip()
        ordering_map = {
            "created_at": ("sent_at", "id"),
            "-created_at": ("-sent_at", "-id"),
            "sent_at": ("sent_at", "id"),
            "-sent_at": ("-sent_at", "-id"),
        }
        if ordering in ordering_map:
            qs = qs.order_by(*ordering_map[ordering])
        elif conversation:
            qs = qs.order_by("sent_at", "id")
        else:
            qs = qs.order_by("-sent_at", "-id")

        limit_raw = self.request.query_params.get("limit")
        if limit_raw:
            try:
                limit = int(limit_raw)
            except (TypeError, ValueError):
                limit = None
            if limit and limit > 0:
                qs = qs[: min(limit, 100)]

        return qs

    def list(self, request, *args, **kwargs):
        if self._is_activity_feed_request():
            limit = self._summary_limit()
            ordering = str(request.query_params.get("ordering") or "").strip()
            descending = ordering not in {"created_at", "sent_at"}
            message_rows = CommunicationMessage.objects.filter(is_active=True, is_deleted=False).select_related("sender", "conversation")
            if not _is_admin(request.user):
                message_rows = message_rows.filter(
                    conversation__participants__user=request.user,
                    conversation__participants__is_active=True,
                ).distinct()
            message_rows = message_rows.order_by("-sent_at", "-id")[:limit]
            payload = build_communication_activity_feed(
                conversation_messages=message_rows,
                limit=limit,
                descending=descending,
            )
            page = self.paginate_queryset(payload)
            if page is not None:
                return self.get_paginated_response(page)
            return Response(payload, status=status.HTTP_200_OK)
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        uploads = _uploaded_message_files(self.request)
        content = (serializer.validated_data.get("content") or "").strip()
        if not content and not uploads:
            raise ValidationError({"content": "Message content or at least one attachment is required."})

        user = self.request.user
        conversation = serializer.validated_data.get("conversation")
        is_participant = ConversationParticipant.objects.filter(conversation=conversation, user=user, is_active=True).exists()
        if not is_participant:
            if _is_admin(user):
                ConversationParticipant.objects.get_or_create(
                    conversation=conversation,
                    user=user,
                    defaults={"role": "Admin", "is_active": True},
                )
            else:
                raise PermissionDenied("You are not an active participant in this conversation.")
        message = serializer.save(
            sender=user,
            content=content,
            delivery_status="Sent",
            message_type=_message_type_for_uploads(uploads),
        )

        for upload in uploads:
            MessageAttachment.objects.create(
                message=message,
                file=upload,
                file_name=os.path.basename(upload.name or "attachment"),
                file_size=getattr(upload, "size", 0) or 0,
                mime_type=(getattr(upload, "content_type", "") or "").strip(),
            )
        publish_message_event(message, event_type="message.created")

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.sender_id != self.request.user.id and not _is_admin(self.request.user):
            raise PermissionDenied("Only sender or admin can edit this message.")
        message = serializer.save(is_edited=True, edited_at=now_ts())
        publish_message_event(message, event_type="message.updated")

    def perform_destroy(self, instance):
        if instance.sender_id != self.request.user.id and not _is_admin(self.request.user):
            raise PermissionDenied("Only sender or admin can delete this message.")
        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=["is_deleted", "is_active"])
        publish_message_event(instance, event_type="message.deleted")

    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, pk=None):
        message = self.get_object()
        MessageReadReceipt.objects.update_or_create(
            message=message,
            user=request.user,
            defaults={"read_at": now_ts()},
        )
        ConversationParticipant.objects.filter(conversation=message.conversation, user=request.user).update(last_read_at=now_ts())
        if message.delivery_status != "Read":
            message.delivery_status = "Read"
            message.save(update_fields=["delivery_status"])
        publish_message_event(message, event_type="message.read")
        return Response({"message": "Message marked as read."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        conversation_ids = ConversationParticipant.objects.filter(user=request.user, is_active=True).values_list("conversation_id", flat=True)
        read_ids = MessageReadReceipt.objects.filter(user=request.user).values_list("message_id", flat=True)
        count = CommunicationMessage.objects.filter(
            conversation_id__in=conversation_ids,
            is_active=True,
            is_deleted=False,
        ).exclude(sender=request.user).exclude(id__in=read_ids).count()
        return Response({"unread_count": count}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="search")
    def search(self, request):
        query = (request.data.get("query") or "").strip()
        if not query:
            return Response([], status=status.HTTP_200_OK)
        rows = self.get_queryset().filter(content__icontains=query)[:100]
        return Response(self.get_serializer(rows, many=True).data, status=status.HTTP_200_OK)


class LegacyMessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    queryset = Message.objects.all().order_by("-sent_at", "-id")
    permission_classes = [IsSchoolAdmin | IsTeacher, HasModuleAccess]
    module_key = "COMMUNICATION"


class NotificationViewSet(CommunicationAccessMixin, viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    queryset = Notification.objects.filter(is_active=True).order_by("-sent_at")

    def get_queryset(self):
        queryset = super().get_queryset()
        if _is_admin(self.request.user) and _parse_bool(self.request.query_params.get("scope")):
            recipient_id = self.request.query_params.get("recipient_id")
            if recipient_id:
                queryset = queryset.filter(recipient_id=recipient_id)
        else:
            queryset = queryset.filter(recipient=self.request.user)
        notification_type = (self.request.query_params.get("notification_type") or "").strip()
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        is_read = self.request.query_params.get("is_read")
        if is_read is not None and str(is_read).strip() != "":
            queryset = queryset.filter(is_read=_parse_bool(is_read))
        return queryset

    def create(self, request, *args, **kwargs):
        serializer_data = request.data.copy()
        if not serializer_data.get("recipient"):
            serializer_data["recipient"] = request.user.id
        serializer = self.get_serializer(data=serializer_data)
        serializer.is_valid(raise_exception=True)
        recipient_ids = request.data.get("recipient_ids") or request.data.get("recipients") or []
        if hasattr(request.data, "getlist") and not recipient_ids:
            recipient_ids = request.data.getlist("recipient_ids") or request.data.getlist("recipients")
        if isinstance(recipient_ids, str):
            recipient_ids = [recipient_ids]
        if not recipient_ids:
            single_recipient = serializer.validated_data.get("recipient") or request.user
            recipient_ids = [single_recipient.id]
        try:
            recipient_ids = [int(value) for value in recipient_ids]
        except (TypeError, ValueError):
            raise ValidationError({"recipient_ids": "Recipient IDs must be integers."})

        if not _is_admin(request.user) and any(recipient_id != request.user.id for recipient_id in recipient_ids):
            raise PermissionDenied("Only admins can create notifications for other users.")

        recipients = list(User.objects.filter(id__in=recipient_ids, is_active=True))
        if len(recipients) != len(set(recipient_ids)):
            raise ValidationError({"recipient_ids": "One or more recipients were not found."})

        created = []
        for recipient in recipients:
            created.append(
                Notification.objects.create(
                    recipient=recipient,
                    notification_type=serializer.validated_data.get("notification_type", "System"),
                    title=serializer.validated_data["title"],
                    message=serializer.validated_data["message"],
                    priority=serializer.validated_data.get("priority", "Informational"),
                    action_url=serializer.validated_data.get("action_url", ""),
                    created_by=request.user,
                )
            )

        payload = {
            "created": len(created),
            "results": self.get_serializer(created, many=True).data,
        }
        for row in created:
            publish_notification_event(row, event_type="notification.created")
        status_code = status.HTTP_201_CREATED
        return Response(payload, status=status_code)

    def perform_create(self, serializer):
        recipient = serializer.validated_data.get("recipient") or self.request.user
        if recipient != self.request.user and not _is_admin(self.request.user):
            raise PermissionDenied("Only admins can create notifications for other users.")
        serializer.save(created_by=self.request.user, recipient=recipient)

    @action(detail=False, methods=["get"], url_path="recipients")
    def recipients(self, request):
        if not _is_admin(request.user):
            raise PermissionDenied("Only admins can browse notification recipients.")
        query = request.query_params.get("q", "")
        return Response({"results": _notification_recipient_options(query)}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["patch"], url_path="read")
    def read(self, request, pk=None):
        row = self.get_object()
        row.is_read = True
        row.read_at = now_ts()
        row.save(update_fields=["is_read", "read_at"])
        publish_notification_event(row, event_type="notification.read")
        return Response({"message": "Notification marked as read."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        updated = self.get_queryset().filter(is_read=False).update(is_read=True, read_at=now_ts())
        if updated:
            publish_notification_bulk_event(
                event_type="notification.read_all",
                user_id=request.user.id,
                updated=updated,
            )
        return Response({"updated": updated}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({"unread_count": count}, status=status.HTTP_200_OK)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        publish_notification_event(instance, event_type="notification.deleted")


class NotificationPreferenceView(CommunicationAccessMixin, APIView):
    def get(self, request):
        for ntype, _ in Notification.TYPE_CHOICES:
            NotificationPreference.objects.get_or_create(
                user=request.user,
                notification_type=ntype,
                defaults={
                    "channel_in_app": True,
                    "channel_email": True,
                    "channel_sms": False,
                    "channel_push": False,
                },
            )
        rows = NotificationPreference.objects.filter(user=request.user).order_by("notification_type")
        return Response(NotificationPreferenceSerializer(rows, many=True).data, status=status.HTTP_200_OK)

    def patch(self, request):
        notification_type = request.data.get("notification_type")
        if not notification_type:
            return Response({"error": "notification_type is required"}, status=status.HTTP_400_BAD_REQUEST)
        defaults = {
            "channel_in_app": request.data.get("channel_in_app", True),
            "channel_email": request.data.get("channel_email", True),
            "channel_sms": request.data.get("channel_sms", False),
            "channel_push": request.data.get("channel_push", False),
            "quiet_hours_start": request.data.get("quiet_hours_start"),
            "quiet_hours_end": request.data.get("quiet_hours_end"),
        }
        row, _ = NotificationPreference.objects.update_or_create(
            user=request.user,
            notification_type=notification_type,
            defaults=defaults,
        )
        return Response(NotificationPreferenceSerializer(row).data, status=status.HTTP_200_OK)


class EmailCampaignViewSet(CommunicationAccessMixin, viewsets.ModelViewSet):
    serializer_class = EmailCampaignSerializer
    queryset = EmailCampaign.objects.filter(is_active=True).order_by("-created_at")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if getattr(self, "action", "") in {"list", "retrieve"}:
            if getattr(self, "action", "") == "retrieve":
                campaign_ids = [self.kwargs.get("pk")]
            else:
                campaign_ids = list(self.get_queryset().values_list("id", flat=True)[:200])
            context["campaign_message_map"] = build_unified_message_reference_lookup(
                source_type="EmailCampaign",
                source_ids=[campaign_id for campaign_id in campaign_ids if campaign_id],
            )
        return context

    def perform_create(self, serializer):
        scheduled_at = serializer.validated_data.get("scheduled_at")
        status_value = "Scheduled" if scheduled_at and scheduled_at > now_ts() else serializer.validated_data.get("status", "Draft")
        campaign = serializer.save(created_by=self.request.user, status=status_value)
        ensure_campaign_stats(campaign)

    @action(detail=True, methods=["post"], url_path="test")
    def test(self, request, pk=None):
        campaign = self.get_object()
        email = request.data.get("email") or request.user.email
        if not email:
            return Response({"error": "email is required"}, status=status.HTTP_400_BAD_REQUEST)
        result = send_email_placeholder(subject=campaign.subject, body=campaign.body_text or campaign.body_html, recipients=[email], from_email=campaign.sender_email or None)
        return Response({"status": result.status, "provider_id": result.provider_id, "reason": result.failure_reason}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="send")
    def send(self, request, pk=None):
        campaign = self.get_object()
        recipients = _normalize_email_list(request.data.get("emails") or [])
        if recipients:
            queue_result = queue_campaign_recipients(campaign, recipients)
        else:
            queue_result = {"queued": 0, "failed": 0}

        if not campaign.recipients.filter(status="Queued").exists() and not queue_result["failed"]:
            return Response({"error": "emails list is required"}, status=status.HTTP_400_BAD_REQUEST)

        force_send = _parse_bool(request.data.get("force_send"))
        if campaign.scheduled_at and campaign.scheduled_at > now_ts() and not force_send:
            campaign.status = "Scheduled"
            campaign.save(update_fields=["status"])
            message_id = campaign.unified_messages.order_by("-id").values_list("id", flat=True).first()
            return Response(
                {
                    "message_id": message_id,
                    "queued": queue_result["queued"],
                    "failed": queue_result["failed"],
                    "status": campaign.status,
                    "scheduled_at": campaign.scheduled_at,
                },
                status=status.HTTP_202_ACCEPTED,
            )

        dispatch_result = dispatch_email_campaign(campaign)
        return Response(
            {
                "message_id": dispatch_result.get("message_id"),
                "queued": dispatch_result["queued"],
                "failed": queue_result["failed"],
                "processed": dispatch_result["processed"],
                "status": campaign.status,
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=False, methods=["post"], url_path="dispatch-due")
    def dispatch_due(self, request):
        return Response(dispatch_due_email_campaigns(), status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="stats")
    def stats(self, request, pk=None):
        campaign = self.get_object()
        reference = build_unified_message_reference_lookup(source_type="EmailCampaign", source_ids=[campaign.id]).get(campaign.id, {})
        stats = campaign.stats_snapshot if hasattr(campaign, "stats_snapshot") else ensure_campaign_stats(campaign)
        payload = {
            "campaign_id": campaign.id,
            "message_id": reference.get("message_id"),
            "message_status": reference.get("message_status", ""),
            "message_kind": reference.get("message_kind", ""),
            "message_channels": reference.get("message_channels", []),
            "delivery_summary": reference.get("delivery_summary", {}),
            "total": stats.total_recipients,
            "queued": stats.queued_recipients,
            "sent": stats.successful_recipients,
            "delivered": stats.delivered_recipients,
            "opened": stats.opened_recipients,
            "clicked": stats.clicked_recipients,
            "bounced": stats.bounced_recipients,
            "failed": stats.failed_recipients,
            "open_events": stats.open_events,
            "click_events": stats.click_events,
            "delivery_rate": float(stats.delivery_rate),
            "open_rate": float(stats.open_rate),
            "click_rate": float(stats.click_rate),
            "last_event_at": stats.last_event_at,
            "last_synced_at": stats.last_synced_at,
        }
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="recipients")
    def recipients(self, request, pk=None):
        campaign = self.get_object()
        rows = list(campaign.recipients.all())
        context = self.get_serializer_context()
        context["email_recipient_delivery_map"] = build_delivery_reference_lookup(
            source_type="EmailRecipient",
            source_ids=[row.id for row in rows],
        )
        return Response(EmailRecipientSerializer(rows, many=True, context=context).data, status=status.HTTP_200_OK)


class SmsGatewayView(CommunicationAccessMixin, APIView):
    def get(self, request):
        rows = list(SmsMessage.objects.filter(is_active=True).order_by("-created_at"))
        context = {
            "request": request,
            "sms_delivery_map": build_delivery_reference_lookup(
                source_type="SmsMessage",
                source_ids=[row.id for row in rows],
            ),
        }
        return Response(SmsMessageSerializer(rows, many=True, context=context).data, status=status.HTTP_200_OK)


class SmsSendView(CommunicationAccessMixin, APIView):
    def post(self, request):
        phones = request.data.get("phones") or []
        message = (request.data.get("message") or "").strip()
        channel = request.data.get("channel", "SMS")
        if channel not in ["SMS", "WhatsApp"]:
            return Response({"error": "channel must be SMS or WhatsApp"}, status=status.HTTP_400_BAD_REQUEST)
        phones = [phone.strip() for phone in phones if isinstance(phone, str) and phone.strip()]
        phones = list(dict.fromkeys(phones))
        if not phones or not message:
            return Response({"error": "phones and message are required"}, status=status.HTTP_400_BAD_REQUEST)
        queue_result = queue_sms_messages(
            phones=phones,
            message=message,
            channel=channel,
            created_by=request.user,
        )
        rows = list(queue_result["rows"])
        context = {
            "request": request,
            "sms_delivery_map": build_delivery_reference_lookup(
                source_type="SmsMessage",
                source_ids=[row.id for row in rows],
            ),
        }
        return Response(SmsMessageSerializer(rows, many=True, context=context).data, status=status.HTTP_202_ACCEPTED)


class SmsStatusView(CommunicationAccessMixin, APIView):
    def get(self, request, pk):
        row = SmsMessage.objects.filter(id=pk, is_active=True).first()
        if not row:
            return Response({"error": "SMS record not found"}, status=status.HTTP_404_NOT_FOUND)
        context = {
            "request": request,
            "sms_delivery_map": build_delivery_reference_lookup(source_type="SmsMessage", source_ids=[row.id]),
        }
        return Response(SmsMessageSerializer(row, context=context).data, status=status.HTTP_200_OK)


class SmsBalanceView(CommunicationAccessMixin, APIView):
    def get(self, request):
        return Response(sms_balance_placeholder(), status=status.HTTP_200_OK)


class PushDeviceViewSet(CommunicationAccessMixin, viewsets.ModelViewSet):
    serializer_class = PushDeviceSerializer
    queryset = PushDevice.objects.filter(is_active=True).order_by("-last_seen_at")

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, last_seen_at=now_ts())
        sync_gateway_statuses(channels=["PUSH"])

    def perform_update(self, serializer):
        serializer.save(last_seen_at=now_ts())
        sync_gateway_statuses(channels=["PUSH"])

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        sync_gateway_statuses(channels=["PUSH"])


class PushSendView(CommunicationAccessMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess, IsSchoolAdmin]
    module_key = "COMMUNICATION"

    def post(self, request):
        user_ids = request.data.get("users") or []
        title = (request.data.get("title") or "").strip()
        body = (request.data.get("body") or "").strip()
        if not user_ids or not title or not body:
            return Response({"error": "users, title and body are required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            normalized_user_ids = [int(user_id) for user_id in user_ids]
        except (TypeError, ValueError):
            return Response({"error": "users must contain integer IDs"}, status=status.HTTP_400_BAD_REQUEST)
        queue_result = queue_push_notifications(
            user_ids=normalized_user_ids,
            title=title,
            body=body,
            created_by=request.user,
        )
        rows = list(queue_result["logs"])
        context = {
            "request": request,
            "push_delivery_map": build_delivery_reference_lookup(
                source_type="PushNotificationLog",
                source_ids=[row.id for row in rows],
            ),
        }
        return Response(PushNotificationLogSerializer(rows, many=True, context=context).data, status=status.HTTP_202_ACCEPTED)


class PushLogView(CommunicationAccessMixin, APIView):
    def get(self, request):
        if _is_admin(request.user):
            rows = list(PushNotificationLog.objects.all().order_by("-created_at")[:200])
        else:
            rows = list(PushNotificationLog.objects.filter(user=request.user).order_by("-created_at")[:200])
        context = {
            "request": request,
            "push_delivery_map": build_delivery_reference_lookup(
                source_type="PushNotificationLog",
                source_ids=[row.id for row in rows],
            ),
        }
        return Response(PushNotificationLogSerializer(rows, many=True, context=context).data, status=status.HTTP_200_OK)


class EmailWebhookView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        verified, reason = verify_webhook_request(request.body, request.headers)
        strict_mode = bool(getattr(settings, "COMMUNICATION_WEBHOOK_STRICT_MODE", True))
        verification_unconfigured = reason == "Webhook verification is not configured."
        if not verified and not (verification_unconfigured and not strict_mode):
            return Response({"error": reason}, status=status.HTTP_403_FORBIDDEN)
        provider_id = request.data.get("provider_id")
        status_value = str(request.data.get("status") or "").strip()
        if not provider_id or not status_value:
            return Response({"error": "provider_id and status are required"}, status=status.HTTP_400_BAD_REQUEST)
        row = EmailRecipient.objects.filter(provider_id=provider_id).order_by("-id").first()
        if not row:
            return Response({"error": "recipient record not found"}, status=status.HTTP_404_NOT_FOUND)
        normalized = EMAIL_WEBHOOK_STATUS_MAP.get(status_value.lower())
        if not normalized:
            return Response({"error": f"Unsupported email status: {status_value}"}, status=status.HTTP_400_BAD_REQUEST)

        row.status = normalized
        if normalized == "Delivered":
            row.delivered_at = now_ts()
        if normalized == "Opened":
            row.opened_at = row.opened_at or now_ts()
            row.open_count += 1
        if normalized == "Clicked":
            row.click_count += 1
        if normalized in ["Bounced", "Failed"]:
            row.bounce_reason = request.data.get("reason", row.bounce_reason)
        row.save()
        sync_email_delivery_webhook(row, normalized, reason=str(request.data.get("reason") or row.bounce_reason or ""))
        sync_campaign_stats(row.campaign)
        sync_gateway_statuses(channels=["EMAIL"])
        publish_delivery_webhook_event(
            channel="email",
            source_type="EmailRecipient",
            source_id=row.id,
            payload={
                "provider_id": row.provider_id,
                "status": normalized,
                "reason": str(request.data.get("reason") or row.bounce_reason or ""),
                "email": row.email,
                "campaign_id": row.campaign_id,
            },
        )
        return Response({"message": "Email webhook processed."}, status=status.HTTP_200_OK)


class SmsWebhookView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        verified, reason = verify_webhook_request(request.body, request.headers)
        strict_mode = bool(getattr(settings, "COMMUNICATION_WEBHOOK_STRICT_MODE", True))
        verification_unconfigured = reason == "Webhook verification is not configured."
        if not verified and not (verification_unconfigured and not strict_mode):
            return Response({"error": reason}, status=status.HTTP_403_FORBIDDEN)
        provider_id = request.data.get("provider_id")
        status_value = str(request.data.get("status") or "").strip()
        if not provider_id or not status_value:
            return Response({"error": "provider_id and status are required"}, status=status.HTTP_400_BAD_REQUEST)
        row = SmsMessage.objects.filter(provider_id=provider_id).order_by("-id").first()
        if not row:
            return Response({"error": "sms record not found"}, status=status.HTTP_404_NOT_FOUND)
        normalized = SMS_WEBHOOK_STATUS_MAP.get(status_value.lower())
        if not normalized:
            return Response({"error": f"Unsupported sms status: {status_value}"}, status=status.HTTP_400_BAD_REQUEST)

        row.status = normalized
        if normalized == "Delivered":
            row.delivered_at = now_ts()
        if normalized == "Failed":
            row.failure_reason = request.data.get("reason", row.failure_reason)
        row.save()
        sync_sms_delivery_webhook(row, normalized, reason=str(request.data.get("reason") or row.failure_reason or ""))
        sync_gateway_statuses(channels=["WHATSAPP" if row.channel == "WhatsApp" else "SMS"])
        publish_delivery_webhook_event(
            channel="whatsapp" if row.channel == "WhatsApp" else "sms",
            source_type="SmsMessage",
            source_id=row.id,
            payload={
                "provider_id": row.provider_id,
                "status": normalized,
                "reason": str(request.data.get("reason") or row.failure_reason or ""),
                "channel": row.channel,
                "recipient_phone": row.recipient_phone,
            },
        )
        return Response({"message": "SMS webhook processed."}, status=status.HTTP_200_OK)


class MessageTemplateViewSet(CommunicationAccessMixin, viewsets.ModelViewSet):
    serializer_class = MessageTemplateSerializer
    queryset = MessageTemplate.objects.filter(is_active=True).order_by("name")

    def perform_create(self, serializer):
        row = serializer.save(created_by=self.request.user)
        publish_alert_rule_event(
            rule_id=row.id,
            event_type="alert.rule.created",
            payload={
                "rule_id": row.id,
                "name": row.name,
                "rule_type": row.rule_type,
                "severity": row.severity,
                "channel": row.channel,
                "threshold": row.threshold,
                "is_active": row.is_active,
            },
        )

    @action(detail=True, methods=["post"], url_path="preview")
    def preview(self, request, pk=None):
        row = self.get_object()
        sample = request.data.get("sample") or {}
        rendered_subject = render_template_placeholders(row.subject, sample)
        rendered_body = render_template_placeholders(row.body, sample)
        return Response({"subject": rendered_subject, "body": rendered_body}, status=status.HTTP_200_OK)


class AnnouncementViewSet(CommunicationAccessMixin, viewsets.ModelViewSet):
    serializer_class = AnnouncementSerializer
    queryset = Announcement.objects.filter(is_active=True).order_by("-publish_at")

    def get_queryset(self):
        now = now_ts()
        return super().get_queryset().filter(publish_at__lte=now).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])

    @action(detail=True, methods=["post"], url_path="read")
    def read(self, request, pk=None):
        row = self.get_object()
        AnnouncementRead.objects.update_or_create(announcement=row, user=request.user, defaults={"read_at": now_ts()})
        return Response({"message": "Announcement marked as read."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="stats")
    def stats(self, request, pk=None):
        row = self.get_object()
        readers = AnnouncementRead.objects.filter(announcement=row).count()
        return Response({"announcement_id": row.id, "read_count": readers}, status=status.HTTP_200_OK)


class CommunicationAlertRuleViewSet(CommunicationAdminAccessMixin, viewsets.ModelViewSet):
    serializer_class = CommunicationAlertRuleSerializer
    queryset = CommunicationAlertRule.objects.all().order_by("name", "id")

    def get_queryset(self):
        queryset = super().get_queryset()
        include_inactive = _parse_bool(self.request.query_params.get("include_inactive"))
        rule_type = str(self.request.query_params.get("rule_type") or "").strip().upper()
        severity = str(self.request.query_params.get("severity") or "").strip().upper()
        channel = str(self.request.query_params.get("channel") or "").strip().upper()
        if not include_inactive:
            queryset = queryset.filter(is_active=True)
        if rule_type:
            queryset = queryset.filter(rule_type=rule_type)
        if severity:
            queryset = queryset.filter(severity=severity)
        if channel:
            queryset = queryset.filter(channel=channel)
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        was_active = serializer.instance.is_active
        row = serializer.save()
        if was_active and not row.is_active:
            resolve_communication_alert_rule_events(row, reason="Rule deactivated.")
        publish_alert_rule_event(
            rule_id=row.id,
            event_type="alert.rule.updated",
            payload={
                "rule_id": row.id,
                "name": row.name,
                "rule_type": row.rule_type,
                "severity": row.severity,
                "channel": row.channel,
                "threshold": row.threshold,
                "is_active": row.is_active,
            },
        )

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        resolve_communication_alert_rule_events(instance, reason="Rule archived.")
        publish_alert_rule_event(
            rule_id=instance.id,
            event_type="alert.rule.archived",
            payload={"rule_id": instance.id, "is_active": False},
        )

    @action(detail=False, methods=["post"], url_path="evaluate")
    def evaluate(self, request):
        raw_rule_ids = request.data.get("rule_ids") or []
        rule_ids = []
        for value in raw_rule_ids:
            try:
                rule_ids.append(int(value))
            except (TypeError, ValueError):
                continue
        result = evaluate_communication_alert_rules(rule_ids=rule_ids or None)
        return Response(result, status=status.HTTP_200_OK)


class CommunicationAlertEventViewSet(CommunicationAdminAccessMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = CommunicationAlertEventSerializer
    queryset = CommunicationAlertEvent.objects.select_related("rule").all().order_by("-last_triggered_at", "-id")

    def get_queryset(self):
        queryset = super().get_queryset()
        status_value = str(self.request.query_params.get("status") or "").strip().upper()
        severity = str(self.request.query_params.get("severity") or "").strip().upper()
        channel = str(self.request.query_params.get("channel") or "").strip().upper()
        rule_id = self.request.query_params.get("rule_id")
        if status_value:
            queryset = queryset.filter(status=status_value)
        if severity:
            queryset = queryset.filter(severity=severity)
        if channel:
            queryset = queryset.filter(channel=channel)
        if rule_id:
            queryset = queryset.filter(rule_id=rule_id)
        return queryset

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        return Response(build_communication_alert_summary(), status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="acknowledge")
    def acknowledge(self, request, pk=None):
        event = self.get_object()
        if event.status != CommunicationAlertEvent.STATUS_OPEN:
            return Response({"detail": "Only open alerts can be acknowledged."}, status=status.HTTP_400_BAD_REQUEST)
        event.status = CommunicationAlertEvent.STATUS_ACKNOWLEDGED
        event.acknowledged_at = now_ts()
        event.save(update_fields=["status", "acknowledged_at"])
        publish_alert_event(event, event_type="alert.event.acknowledged")
        return Response(self.get_serializer(event).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="resolve")
    def resolve(self, request, pk=None):
        event = self.get_object()
        if event.status == CommunicationAlertEvent.STATUS_RESOLVED:
            return Response({"detail": "Alert is already resolved."}, status=status.HTTP_400_BAD_REQUEST)
        event.status = CommunicationAlertEvent.STATUS_RESOLVED
        event.resolved_at = now_ts()
        event.save(update_fields=["status", "resolved_at"])
        publish_alert_event(event, event_type="alert.event.resolved")
        return Response(self.get_serializer(event).data, status=status.HTTP_200_OK)


class CommunicationAlertsFeedView(CommunicationAdminAccessMixin, APIView):
    def get(self, request):
        try:
            alert_limit = int(request.query_params.get("alert_limit", 20) or 20)
        except (TypeError, ValueError):
            alert_limit = 20
        try:
            announcement_limit = int(request.query_params.get("announcement_limit", 20) or 20)
        except (TypeError, ValueError):
            announcement_limit = 20
        try:
            reminder_limit = int(request.query_params.get("reminder_limit", 10) or 10)
        except (TypeError, ValueError):
            reminder_limit = 10
        return Response(
            build_alerts_center_payload(
                alert_limit=alert_limit,
                announcement_limit=announcement_limit,
                reminder_limit=reminder_limit,
            ),
            status=status.HTTP_200_OK,
        )


class CommunicationGatewaySettingsView(CommunicationAdminAccessMixin, APIView):
    def get(self, request):
        return Response(build_communication_gateway_settings_payload(request=request), status=status.HTTP_200_OK)

    def patch(self, request):
        serializer = CommunicationGatewaySettingsUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = apply_communication_gateway_settings(serializer.validated_data, request=request)
        return Response(payload, status=status.HTTP_200_OK)


class CommunicationGatewayTestView(CommunicationAdminAccessMixin, APIView):
    def post(self, request):
        serializer = CommunicationGatewayTestRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = run_communication_gateway_test(
            channel=serializer.validated_data["channel"],
            request=request,
            target_user_id=serializer.validated_data.get("user_id"),
        )
        if not result["ok"]:
            return Response({"error": result["error"]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result["payload"], status=status.HTTP_200_OK)


class CommunicationAnalyticsSummaryView(CommunicationAccessMixin, APIView):
    def get(self, request):
        total_messages = CommunicationMessage.objects.filter(is_active=True).count()
        total_notifications = Notification.objects.filter(is_active=True).count()
        total_emails = EmailRecipient.objects.count()
        total_sms = SmsMessage.objects.filter(is_active=True).count()
        total_push = PushNotificationLog.objects.count()
        return Response(
            {
                "total_messages": total_messages,
                "total_notifications": total_notifications,
                "total_emails": total_emails,
                "total_sms": total_sms,
                "total_push_notifications": total_push,
                "total_unified_messages": UnifiedMessage.objects.count(),
                "total_message_deliveries": MessageDelivery.objects.count(),
                "dispatch_queue": get_dispatch_queue_health_payload(),
                "gateway_health": build_gateway_health_payload(),
                "alerts": build_communication_alert_summary(limit=5),
            },
            status=status.HTTP_200_OK,
        )


class CommunicationAnalyticsByChannelView(CommunicationAccessMixin, APIView):
    def get(self, request):
        return Response(
            {
                "in_app_messages": CommunicationMessage.objects.filter(is_active=True).count(),
                "email_messages": EmailRecipient.objects.count(),
                "sms_messages": SmsMessage.objects.filter(channel="SMS", is_active=True).count(),
                "whatsapp_messages": SmsMessage.objects.filter(channel="WhatsApp", is_active=True).count(),
                "push_notifications": PushNotificationLog.objects.count(),
            },
            status=status.HTTP_200_OK,
        )


class CommunicationAnalyticsDeliveryRateView(CommunicationAccessMixin, APIView):
    def get(self, request):
        email_total = EmailRecipient.objects.count()
        email_success = EmailRecipient.objects.filter(status__in=["Sent", "Delivered", "Opened", "Clicked"]).count()
        sms_total = SmsMessage.objects.filter(channel="SMS", is_active=True).count()
        sms_success = SmsMessage.objects.filter(channel="SMS", status__in=["Sent", "Delivered"], is_active=True).count()
        whatsapp_total = SmsMessage.objects.filter(channel="WhatsApp", is_active=True).count()
        whatsapp_success = SmsMessage.objects.filter(channel="WhatsApp", status__in=["Sent", "Delivered"], is_active=True).count()
        return Response(
            {
                "email_delivery_rate": round((email_success / email_total) * 100, 2) if email_total else 0,
                "sms_delivery_rate": round((sms_success / sms_total) * 100, 2) if sms_total else 0,
                "whatsapp_delivery_rate": round((whatsapp_success / whatsapp_total) * 100, 2) if whatsapp_total else 0,
            },
            status=status.HTTP_200_OK,
        )


class CommunicationAnalyticsDeliveryHistoryView(CommunicationAccessMixin, APIView):
    def get(self, request):
        try:
            limit = int(request.query_params.get("limit", 50) or 50)
        except (TypeError, ValueError):
            limit = 50
        channel = str(request.query_params.get("channel") or "").strip().upper() or None
        status_filter = str(request.query_params.get("status") or "").strip() or None
        rows = build_delivery_history(limit=limit, channel=channel, status=status_filter)
        return Response({"count": len(rows), "results": rows}, status=status.HTTP_200_OK)


class CommunicationAnalyticsCampaignPerformanceView(CommunicationAccessMixin, APIView):
    def get(self, request):
        try:
            limit = int(request.query_params.get("limit", 20) or 20)
        except (TypeError, ValueError):
            limit = 20
        rows = build_campaign_performance(limit=limit)
        return Response({"count": len(rows), "results": rows}, status=status.HTTP_200_OK)


class CommunicationAnalyticsGatewayHealthView(CommunicationAccessMixin, APIView):
    def get(self, request):
        return Response(build_gateway_health_payload(), status=status.HTTP_200_OK)


class CommunicationUnifiedMessageListView(CommunicationAccessMixin, APIView):
    def get(self, request):
        try:
            limit = int(request.query_params.get("limit", 50) or 50)
        except (TypeError, ValueError):
            limit = 50
        rows = build_unified_message_feed(
            limit=limit,
            status=str(request.query_params.get("status") or "").strip() or None,
            kind=str(request.query_params.get("kind") or "").strip().upper() or None,
            channel=str(request.query_params.get("channel") or "").strip().upper() or None,
            source_type=str(request.query_params.get("source_type") or "").strip() or None,
        )
        return Response({"count": len(rows), "results": rows}, status=status.HTTP_200_OK)


class CommunicationUnifiedMessageDetailView(CommunicationAccessMixin, APIView):
    def get(self, request, pk):
        row = build_unified_message_detail(pk)
        if row is None:
            return Response({"error": "Unified message not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(row, status=status.HTTP_200_OK)


class CommunicationAnalyticsEngagementView(CommunicationAccessMixin, APIView):
    def get(self, request):
        top_users = (
            CommunicationMessage.objects.filter(is_active=True, sender__isnull=False)
            .values("sender_id", "sender__username")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )
        reply_rows = (
            CommunicationMessage.objects.filter(is_active=True, reply_to__isnull=False)
            .select_related("reply_to")
            .only("sent_at", "reply_to__sent_at")
        )
        deltas = []
        for row in reply_rows:
            if row.sent_at and getattr(row.reply_to, "sent_at", None) and row.sent_at >= row.reply_to.sent_at:
                deltas.append((row.sent_at - row.reply_to.sent_at).total_seconds())
        average_seconds = sum(deltas) / len(deltas) if deltas else 0
        return Response(
            {
                "top_users": list(top_users),
                "average_response_time_minutes": round(average_seconds / 60, 2) if average_seconds else 0,
                "average_response_time_label": "Actual average reply lag between a message and its reply.",
                "sample_size": len(deltas),
            },
            status=status.HTTP_200_OK,
        )


class ParentNotifyView(CommunicationAccessMixin, APIView):
    template_name = ""

    def post(self, request):
        parent_emails = request.data.get("emails") or []
        parent_phones = request.data.get("phones") or []
        subject = request.data.get("subject") or "School Notification"
        message = request.data.get("message") or ""
        email_result = None
        sms_results = []
        if parent_emails:
            email_result = queue_direct_emails(
                subject=subject,
                body=message,
                recipients=[str(email).strip() for email in parent_emails if str(email).strip()],
                created_by=request.user,
            )
        if parent_phones:
            sms_queue = queue_sms_messages(
                phones=[str(phone).strip() for phone in parent_phones if str(phone).strip()],
                message=message,
                channel="SMS",
                created_by=request.user,
            )
            sms_results = [row.id for row in sms_queue["rows"]]
        return Response(
            {
                "template": self.template_name,
                "email_status": "Queued" if email_result and email_result["queued"] else "Skipped",
                "email_message_id": email_result.get("message_id") if email_result else None,
                "email_queued": email_result["queued"] if email_result else 0,
                "sms_records": sms_results,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class ParentReportCardNotifyView(ParentNotifyView):
    template_name = "report-card-notify"


class ParentFeeReminderView(ParentNotifyView):
    template_name = "fee-reminder"


class ParentAttendanceAlertView(ParentNotifyView):
    template_name = "attendance-alert"


class ParentMeetingInviteView(ParentNotifyView):
    template_name = "meeting-invite"
