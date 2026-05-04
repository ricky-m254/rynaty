from rest_framework import serializers
from common.media_urls import AbsoluteURLFileField, build_absolute_media_url, display_media_name, is_image_file
from .read_models import build_delivery_reference_lookup, build_unified_message_reference_lookup
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
    MessageReadReceipt,
    MessageTemplate,
    Notification,
    NotificationPreference,
    PushDevice,
    PushNotificationLog,
    SmsMessage,
    Message,
)


class ConversationSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = Conversation
        fields = "__all__"
        read_only_fields = ["created_by_name", "created_by", "created_at"]


class ConversationParticipantSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = ConversationParticipant
        fields = "__all__"
        read_only_fields = ["user_name", "joined_at"]


class MessageAttachmentSerializer(serializers.ModelSerializer):
    file = AbsoluteURLFileField(read_only=True)
    url = serializers.SerializerMethodField()
    preview_url = serializers.SerializerMethodField()
    is_image = serializers.SerializerMethodField()
    file_extension = serializers.SerializerMethodField()

    def get_url(self, obj):
        return build_absolute_media_url(self.context.get("request"), obj.file)

    def get_preview_url(self, obj):
        return self.get_url(obj) if self.get_is_image(obj) else ""

    def get_is_image(self, obj):
        return is_image_file(obj.file, obj.mime_type)

    def get_file_extension(self, obj):
        file_name = display_media_name(obj.file_name or obj.file)
        if "." not in file_name:
            return ""
        return file_name.rsplit(".", 1)[-1].lower()

    class Meta:
        model = MessageAttachment
        fields = [
            "id",
            "message",
            "file",
            "file_name",
            "file_size",
            "mime_type",
            "uploaded_at",
            "is_active",
            "url",
            "preview_url",
            "is_image",
            "file_extension",
        ]
        read_only_fields = [
            "uploaded_at",
            "file_name",
            "file_size",
            "mime_type",
            "url",
            "preview_url",
            "is_image",
            "file_extension",
        ]


class CommunicationMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source="sender.username", read_only=True)
    attachments = MessageAttachmentSerializer(many=True, read_only=True)
    is_own = serializers.SerializerMethodField()

    def get_is_own(self, obj):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            return obj.sender_id == request.user.id
        return False

    class Meta:
        model = CommunicationMessage
        fields = "__all__"
        read_only_fields = ["sender_name", "sender", "sent_at", "edited_at", "delivery_status", "attachments", "is_own"]


class MessageReadReceiptSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = MessageReadReceipt
        fields = "__all__"
        read_only_fields = ["read_at", "user_name"]


class NotificationSerializer(serializers.ModelSerializer):
    recipient_name = serializers.CharField(source="recipient.username", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = Notification
        fields = "__all__"
        read_only_fields = ["recipient_name", "created_by_name", "sent_at"]


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = "__all__"


class EmailCampaignSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    message_id = serializers.SerializerMethodField()
    message_status = serializers.SerializerMethodField()
    message_kind = serializers.SerializerMethodField()
    message_channels = serializers.SerializerMethodField()
    delivery_summary = serializers.SerializerMethodField()

    def _message_reference(self, obj):
        reference_map = self.context.get("campaign_message_map")
        if reference_map is None:
            reference_map = build_unified_message_reference_lookup(source_type="EmailCampaign", source_ids=[obj.id])
        return reference_map.get(obj.id, {})

    def get_message_id(self, obj):
        return self._message_reference(obj).get("message_id")

    def get_message_status(self, obj):
        return self._message_reference(obj).get("message_status", "")

    def get_message_kind(self, obj):
        return self._message_reference(obj).get("message_kind", "")

    def get_message_channels(self, obj):
        return self._message_reference(obj).get("message_channels", [])

    def get_delivery_summary(self, obj):
        return self._message_reference(obj).get("delivery_summary", {})

    class Meta:
        model = EmailCampaign
        fields = "__all__"
        read_only_fields = ["created_by_name", "created_by", "created_at", "sent_at"]


class EmailRecipientSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)
    message_id = serializers.SerializerMethodField()
    message_status = serializers.SerializerMethodField()
    delivery_id = serializers.SerializerMethodField()
    delivery_status = serializers.SerializerMethodField()
    delivery_channel = serializers.SerializerMethodField()
    delivery_attempts = serializers.SerializerMethodField()
    delivery_last_error = serializers.SerializerMethodField()

    def _delivery_reference(self, obj):
        reference_map = self.context.get("email_recipient_delivery_map")
        if reference_map is None:
            reference_map = build_delivery_reference_lookup(source_type="EmailRecipient", source_ids=[obj.id])
        return reference_map.get(obj.id, {})

    def get_message_id(self, obj):
        return self._delivery_reference(obj).get("message_id")

    def get_message_status(self, obj):
        return self._delivery_reference(obj).get("message_status", "")

    def get_delivery_id(self, obj):
        return self._delivery_reference(obj).get("delivery_id")

    def get_delivery_status(self, obj):
        return self._delivery_reference(obj).get("delivery_status", "")

    def get_delivery_channel(self, obj):
        return self._delivery_reference(obj).get("delivery_channel", "")

    def get_delivery_attempts(self, obj):
        return self._delivery_reference(obj).get("delivery_attempts", 0)

    def get_delivery_last_error(self, obj):
        return self._delivery_reference(obj).get("delivery_last_error", "")

    class Meta:
        model = EmailRecipient
        fields = "__all__"
        read_only_fields = ["user_name", "sent_at", "delivered_at", "opened_at", "open_count", "click_count", "bounce_reason"]


class SmsMessageSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    message_id = serializers.SerializerMethodField()
    message_status = serializers.SerializerMethodField()
    delivery_id = serializers.SerializerMethodField()
    delivery_status = serializers.SerializerMethodField()
    delivery_channel = serializers.SerializerMethodField()
    delivery_attempts = serializers.SerializerMethodField()
    delivery_last_error = serializers.SerializerMethodField()

    def _delivery_reference(self, obj):
        reference_map = self.context.get("sms_delivery_map")
        if reference_map is None:
            reference_map = build_delivery_reference_lookup(source_type="SmsMessage", source_ids=[obj.id])
        return reference_map.get(obj.id, {})

    def get_message_id(self, obj):
        return self._delivery_reference(obj).get("message_id")

    def get_message_status(self, obj):
        return self._delivery_reference(obj).get("message_status", "")

    def get_delivery_id(self, obj):
        return self._delivery_reference(obj).get("delivery_id")

    def get_delivery_status(self, obj):
        return self._delivery_reference(obj).get("delivery_status", "")

    def get_delivery_channel(self, obj):
        return self._delivery_reference(obj).get("delivery_channel", "")

    def get_delivery_attempts(self, obj):
        return self._delivery_reference(obj).get("delivery_attempts", 0)

    def get_delivery_last_error(self, obj):
        return self._delivery_reference(obj).get("delivery_last_error", "")

    class Meta:
        model = SmsMessage
        fields = "__all__"
        read_only_fields = ["created_by_name", "created_by", "created_at", "provider_id", "status", "sent_at", "delivered_at", "failure_reason", "cost"]


class MessageTemplateSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = MessageTemplate
        fields = "__all__"
        read_only_fields = ["created_by_name", "created_by", "created_at"]


class AnnouncementSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = Announcement
        fields = "__all__"
        read_only_fields = ["created_by_name", "created_by", "created_at"]


class CommunicationAlertRuleSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)

    def validate(self, attrs):
        rule_type = attrs.get("rule_type", getattr(self.instance, "rule_type", ""))
        channel = attrs.get("channel", getattr(self.instance, "channel", ""))
        threshold = attrs.get("threshold", getattr(self.instance, "threshold", 1))

        if int(threshold or 0) < 1:
            raise serializers.ValidationError({"threshold": "threshold must be at least 1."})
        if rule_type == CommunicationAlertRule.RULE_GATEWAY_UNCONFIGURED and not str(channel or "").strip():
            raise serializers.ValidationError({"channel": "channel is required for gateway configuration rules."})
        return attrs

    class Meta:
        model = CommunicationAlertRule
        fields = "__all__"
        read_only_fields = ["created_by_name", "created_by", "last_evaluated_at", "created_at", "updated_at"]


class CommunicationAlertEventSerializer(serializers.ModelSerializer):
    rule_name = serializers.CharField(source="rule.name", read_only=True)
    rule_type = serializers.CharField(source="rule.rule_type", read_only=True)
    rule_is_active = serializers.BooleanField(source="rule.is_active", read_only=True)

    class Meta:
        model = CommunicationAlertEvent
        fields = "__all__"
        read_only_fields = [
            "rule_name",
            "rule_type",
            "rule_is_active",
            "event_key",
            "title",
            "details",
            "severity",
            "channel",
            "metadata",
            "first_triggered_at",
            "last_triggered_at",
            "acknowledged_at",
            "resolved_at",
            "created_at",
            "updated_at",
        ]


class CommunicationGatewayProfileSettingsSerializer(serializers.Serializer):
    school_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=20)
    email_address = serializers.EmailField(required=False, allow_blank=True)


class CommunicationEmailGatewaySettingsSerializer(serializers.Serializer):
    sender_email = serializers.EmailField(required=False, allow_blank=True)
    smtp_host = serializers.CharField(required=False, allow_blank=True, max_length=255)
    smtp_port = serializers.IntegerField(required=False, min_value=1)
    smtp_user = serializers.CharField(required=False, allow_blank=True, max_length=255)
    smtp_password = serializers.CharField(required=False, allow_blank=True, max_length=255, write_only=True)
    smtp_use_tls = serializers.BooleanField(required=False)


class CommunicationSmsGatewaySettingsSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(
        required=False,
        choices=["", "africastalking", "twilio", "infobip", "vonage"],
        allow_blank=True,
    )
    username = serializers.CharField(required=False, allow_blank=True, max_length=100)
    sender_id = serializers.CharField(required=False, allow_blank=True, max_length=20)
    api_key = serializers.CharField(required=False, allow_blank=True, max_length=255, write_only=True)


class CommunicationWhatsAppGatewaySettingsSerializer(serializers.Serializer):
    phone_id = serializers.CharField(required=False, allow_blank=True, max_length=100)
    api_key = serializers.CharField(required=False, allow_blank=True, max_length=255, write_only=True)


class CommunicationPushGatewaySettingsSerializer(serializers.Serializer):
    setting_key = serializers.ChoiceField(
        required=False,
        choices=["integrations.push", "integrations.fcm"],
    )
    provider = serializers.ChoiceField(required=False, choices=["fcm"], allow_blank=True)
    enabled = serializers.BooleanField(required=False)
    project_id = serializers.CharField(required=False, allow_blank=True, max_length=255)
    sender_id = serializers.CharField(required=False, allow_blank=True, max_length=255)
    server_key = serializers.CharField(required=False, allow_blank=True, max_length=255, write_only=True)


class CommunicationGatewaySettingsUpdateSerializer(serializers.Serializer):
    profile = CommunicationGatewayProfileSettingsSerializer(required=False)
    email = CommunicationEmailGatewaySettingsSerializer(required=False)
    sms = CommunicationSmsGatewaySettingsSerializer(required=False)
    whatsapp = CommunicationWhatsAppGatewaySettingsSerializer(required=False)
    push = CommunicationPushGatewaySettingsSerializer(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("At least one gateway settings block is required.")
        return attrs


class CommunicationGatewayTestRequestSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(choices=["EMAIL", "SMS", "WHATSAPP", "PUSH"])
    user_id = serializers.IntegerField(required=False, min_value=1)


class AnnouncementReadSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = AnnouncementRead
        fields = "__all__"
        read_only_fields = ["read_at", "user_name"]


class PushDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushDevice
        fields = "__all__"
        read_only_fields = ["user", "last_seen_at", "created_at"]


class PushNotificationLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    message_id = serializers.SerializerMethodField()
    message_status = serializers.SerializerMethodField()
    delivery_id = serializers.SerializerMethodField()
    delivery_status = serializers.SerializerMethodField()
    delivery_channel = serializers.SerializerMethodField()
    delivery_attempts = serializers.SerializerMethodField()
    delivery_last_error = serializers.SerializerMethodField()

    def _delivery_reference(self, obj):
        reference_map = self.context.get("push_delivery_map")
        if reference_map is None:
            reference_map = build_delivery_reference_lookup(source_type="PushNotificationLog", source_ids=[obj.id])
        return reference_map.get(obj.id, {})

    def get_message_id(self, obj):
        return self._delivery_reference(obj).get("message_id")

    def get_message_status(self, obj):
        return self._delivery_reference(obj).get("message_status", "")

    def get_delivery_id(self, obj):
        return self._delivery_reference(obj).get("delivery_id")

    def get_delivery_status(self, obj):
        return self._delivery_reference(obj).get("delivery_status", "")

    def get_delivery_channel(self, obj):
        return self._delivery_reference(obj).get("delivery_channel", "")

    def get_delivery_attempts(self, obj):
        return self._delivery_reference(obj).get("delivery_attempts", 0)

    def get_delivery_last_error(self, obj):
        return self._delivery_reference(obj).get("delivery_last_error", "")

    class Meta:
        model = PushNotificationLog
        fields = "__all__"
        read_only_fields = ["user_name", "created_by_name", "provider_id", "failure_reason", "sent_at", "created_at"]


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = [
            "id",
            "recipient_type",
            "recipient_id",
            "subject",
            "body",
            "sent_at",
            "status",
        ]
        read_only_fields = ["sent_at", "status"]
