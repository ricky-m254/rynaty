from rest_framework import serializers
from common.media_urls import AbsoluteURLFileField, build_absolute_media_url, display_media_name, is_image_file
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

    class Meta:
        model = EmailCampaign
        fields = "__all__"
        read_only_fields = ["created_by_name", "created_by", "created_at", "sent_at"]


class EmailRecipientSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = EmailRecipient
        fields = "__all__"
        read_only_fields = ["user_name", "sent_at", "delivered_at", "opened_at", "open_count", "click_count", "bounce_reason"]


class SmsMessageSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)

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
