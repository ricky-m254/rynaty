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
from .models import (
    Announcement,
    AnnouncementRead,
    CommunicationMessage,
    Conversation,
    ConversationParticipant,
    EmailCampaign,
    EmailRecipient,
    MessageAttachment,
    MessageReadReceipt,
    Message,
    MessageTemplate,
    Notification,
    NotificationPreference,
    PushDevice,
    PushNotificationLog,
    SmsMessage,
)
from .serializers import (
    AnnouncementSerializer,
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
    send_push_placeholder,
    send_sms_placeholder,
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


def _is_admin(user):
    return hasattr(user, "userprofile") and user.userprofile.role.name in ["ADMIN", "TENANT_SUPER_ADMIN"]


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

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.sender_id != self.request.user.id and not _is_admin(self.request.user):
            raise PermissionDenied("Only sender or admin can edit this message.")
        serializer.save(is_edited=True, edited_at=now_ts())

    def perform_destroy(self, instance):
        if instance.sender_id != self.request.user.id and not _is_admin(self.request.user):
            raise PermissionDenied("Only sender or admin can delete this message.")
        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=["is_deleted", "is_active"])

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
        return super().get_queryset().filter(recipient=self.request.user)

    def perform_create(self, serializer):
        recipient = serializer.validated_data.get("recipient") or self.request.user
        if recipient != self.request.user and not _is_admin(self.request.user):
            raise PermissionDenied("Only admins can create notifications for other users.")
        serializer.save(created_by=self.request.user, recipient=recipient)

    @action(detail=True, methods=["patch"], url_path="read")
    def read(self, request, pk=None):
        row = self.get_object()
        row.is_read = True
        row.read_at = now_ts()
        row.save(update_fields=["is_read", "read_at"])
        return Response({"message": "Notification marked as read."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        updated = self.get_queryset().filter(is_read=False).update(is_read=True, read_at=now_ts())
        return Response({"updated": updated}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({"unread_count": count}, status=status.HTTP_200_OK)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


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

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

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
        recipients = request.data.get("emails") or []
        recipients = [email.strip() for email in recipients if isinstance(email, str) and email.strip()]
        recipients = list(dict.fromkeys(recipients))
        if not recipients:
            return Response({"error": "emails list is required"}, status=status.HTTP_400_BAD_REQUEST)
        campaign.status = "Sending"
        campaign.save(update_fields=["status"])
        queued = 0
        for email in recipients:
            if "@" not in email:
                EmailRecipient.objects.create(
                    campaign=campaign,
                    email=email,
                    status="Failed",
                    bounce_reason="Invalid email format.",
                )
                queued += 1
                continue
            result = send_email_placeholder(subject=campaign.subject, body=campaign.body_text or campaign.body_html, recipients=[email], from_email=campaign.sender_email or None)
            EmailRecipient.objects.create(
                campaign=campaign,
                email=email,
                provider_id=result.provider_id,
                status="Sent" if result.status == "Sent" else "Failed",
                sent_at=now_ts() if result.status == "Sent" else None,
                bounce_reason=result.failure_reason,
            )
            queued += 1
        campaign.status = "Sent"
        campaign.sent_at = now_ts()
        campaign.save(update_fields=["status", "sent_at"])
        return Response({"queued": queued, "status": campaign.status}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="stats")
    def stats(self, request, pk=None):
        campaign = self.get_object()
        recipients = campaign.recipients.all()
        payload = {
            "campaign_id": campaign.id,
            "total": recipients.count(),
            "sent": recipients.filter(status="Sent").count(),
            "delivered": recipients.filter(status="Delivered").count(),
            "opened": recipients.filter(status="Opened").count(),
            "clicked": recipients.filter(status="Clicked").count(),
            "bounced": recipients.filter(status="Bounced").count(),
            "failed": recipients.filter(status="Failed").count(),
        }
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="recipients")
    def recipients(self, request, pk=None):
        campaign = self.get_object()
        return Response(EmailRecipientSerializer(campaign.recipients.all(), many=True).data, status=status.HTTP_200_OK)


class SmsGatewayView(CommunicationAccessMixin, APIView):
    def get(self, request):
        rows = SmsMessage.objects.filter(is_active=True).order_by("-created_at")
        return Response(SmsMessageSerializer(rows, many=True).data, status=status.HTTP_200_OK)


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
        created = []
        for phone in phones:
            row = SmsMessage.objects.create(
                recipient_phone=phone,
                message=message,
                channel=channel,
                created_by=request.user,
            )
            result = send_sms_placeholder(phone=phone, message=message, channel=channel)
            row.status = result.status
            row.provider_id = result.provider_id
            row.failure_reason = result.failure_reason
            row.cost = result.cost
            row.sent_at = now_ts() if result.status == "Sent" else None
            row.save(update_fields=["status", "provider_id", "failure_reason", "cost", "sent_at"])
            created.append(row)
        return Response(SmsMessageSerializer(created, many=True).data, status=status.HTTP_201_CREATED)


class SmsStatusView(CommunicationAccessMixin, APIView):
    def get(self, request, pk):
        row = SmsMessage.objects.filter(id=pk, is_active=True).first()
        if not row:
            return Response({"error": "SMS record not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(SmsMessageSerializer(row).data, status=status.HTTP_200_OK)


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

    def perform_update(self, serializer):
        serializer.save(last_seen_at=now_ts())

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class PushSendView(CommunicationAccessMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess, IsSchoolAdmin]
    module_key = "COMMUNICATION"

    def post(self, request):
        user_ids = request.data.get("users") or []
        title = (request.data.get("title") or "").strip()
        body = (request.data.get("body") or "").strip()
        if not user_ids or not title or not body:
            return Response({"error": "users, title and body are required"}, status=status.HTTP_400_BAD_REQUEST)
        logs = []
        for user_id in user_ids:
            devices = PushDevice.objects.filter(user_id=user_id, is_active=True)
            if not devices.exists():
                logs.append(
                    PushNotificationLog.objects.create(
                        user_id=user_id,
                        title=title,
                        body=body,
                        status="Failed",
                        failure_reason="No active push device for user.",
                        created_by=request.user,
                    )
                )
                continue
            device = devices.first()
            result = send_push_placeholder(token=device.token, title=title, body=body)
            logs.append(
                PushNotificationLog.objects.create(
                    user_id=user_id,
                    title=title,
                    body=body,
                    status=result.status,
                    provider_id=result.provider_id,
                    failure_reason=result.failure_reason,
                    sent_at=now_ts() if result.status == "Sent" else None,
                    created_by=request.user,
                )
            )
        return Response(PushNotificationLogSerializer(logs, many=True).data, status=status.HTTP_201_CREATED)


class PushLogView(CommunicationAccessMixin, APIView):
    def get(self, request):
        if _is_admin(request.user):
            rows = PushNotificationLog.objects.all().order_by("-created_at")[:200]
        else:
            rows = PushNotificationLog.objects.filter(user=request.user).order_by("-created_at")[:200]
        return Response(PushNotificationLogSerializer(rows, many=True).data, status=status.HTTP_200_OK)


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
        return Response({"message": "SMS webhook processed."}, status=status.HTTP_200_OK)


class MessageTemplateViewSet(CommunicationAccessMixin, viewsets.ModelViewSet):
    serializer_class = MessageTemplateSerializer
    queryset = MessageTemplate.objects.filter(is_active=True).order_by("name")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

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


class CommunicationAnalyticsEngagementView(CommunicationAccessMixin, APIView):
    def get(self, request):
        top_users = (
            CommunicationMessage.objects.filter(is_active=True, sender__isnull=False)
            .values("sender_id", "sender__username")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )
        avg_response = (
            CommunicationMessage.objects.filter(is_active=True)
            .exclude(reply_to__isnull=True)
            .aggregate(avg=Avg("id"))
        )
        return Response(
            {
                "top_users": list(top_users),
                "average_response_time_proxy": avg_response["avg"] or 0,
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
            email_result = send_email_placeholder(subject=subject, body=message, recipients=parent_emails)
        for phone in parent_phones:
            row = SmsMessage.objects.create(
                recipient_phone=phone,
                message=message,
                channel="SMS",
                created_by=request.user,
            )
            result = send_sms_placeholder(phone=phone, message=message, channel="SMS")
            row.status = result.status
            row.provider_id = result.provider_id
            row.failure_reason = result.failure_reason
            row.cost = result.cost
            row.sent_at = now_ts() if result.status == "Sent" else None
            row.save(update_fields=["status", "provider_id", "failure_reason", "cost", "sent_at"])
            sms_results.append(row.id)
        return Response(
            {
                "template": self.template_name,
                "email_status": email_result.status if email_result else "Skipped",
                "sms_records": sms_results,
            },
            status=status.HTTP_200_OK,
        )


class ParentReportCardNotifyView(ParentNotifyView):
    template_name = "report-card-notify"


class ParentFeeReminderView(ParentNotifyView):
    template_name = "fee-reminder"


class ParentAttendanceAlertView(ParentNotifyView):
    template_name = "attendance-alert"


class ParentMeetingInviteView(ParentNotifyView):
    template_name = "meeting-invite"
