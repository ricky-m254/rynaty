from datetime import timedelta
import hashlib
import hmac
import json

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.test import TestCase
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import Module, Role, UserProfile
from school.models import UserModuleAssignment

from .views import (
    CommunicationAnalyticsSummaryView,
    CommunicationMessageViewSet,
    ConversationViewSet,
    EmailCampaignViewSet,
    EmailWebhookView,
    NotificationViewSet,
    PushDeviceViewSet,
    PushSendView,
    SmsWebhookView,
    SmsSendView,
)
from .models import CommunicationMessage, Conversation, EmailRecipient

User = get_user_model()


def as_rows(data):
    return data.get("results", data) if hasattr(data, "get") else data


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant, _ = Tenant.objects.get_or_create(
                schema_name="communication_test",
                defaults={
                    "name": "Communication Test School",
                    "paid_until": "2030-01-01",
                },
            )
            Domain.objects.get_or_create(
                domain="communication.localhost",
                defaults={"tenant": cls.tenant, "is_primary": True},
            )

    def setUp(self):
        self.ctx = schema_context(self.tenant.schema_name)
        self.ctx.__enter__()

    def tearDown(self):
        self.ctx.__exit__(None, None, None)


class CommunicationModuleTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user, _ = User.objects.get_or_create(
            username="comm_admin",
            defaults={"email": "admin@school.local"},
        )
        self.user.set_password("pass1234")
        self.user.save(update_fields=["password"])
        self.user2, _ = User.objects.get_or_create(
            username="teacher1",
            defaults={"email": "teacher@school.local"},
        )
        self.user2.set_password("pass1234")
        self.user2.save(update_fields=["password"])
        role, _ = Role.objects.get_or_create(name="ADMIN", defaults={"description": "School Administrator"})
        UserProfile.objects.get_or_create(user=self.user, defaults={"role": role})
        module, _ = Module.objects.get_or_create(key="COMMUNICATION", defaults={"name": "Communication"})
        UserModuleAssignment.objects.get_or_create(
            user=self.user2,
            module=module,
            defaults={"is_active": True},
        )

    def test_message_list_supports_summary_ordering_and_limit_without_breaking_thread_order(self):
        conversation = Conversation.objects.create(
            conversation_type="Direct",
            title="Activity feed ordering",
            created_by=self.user,
        )
        conversation.participants.create(user=self.user, role="Admin", is_active=True)
        conversation.participants.create(user=self.user2, role="Member", is_active=True)

        older = CommunicationMessage.objects.create(
            conversation=conversation,
            sender=self.user,
            content="Older message",
            delivery_status="Delivered",
        )
        newer = CommunicationMessage.objects.create(
            conversation=conversation,
            sender=self.user2,
            content="Newer message",
            delivery_status="Read",
        )

        CommunicationMessage.objects.filter(pk=older.pk).update(sent_at=timezone.now() - timedelta(minutes=5))
        CommunicationMessage.objects.filter(pk=newer.pk).update(sent_at=timezone.now())

        thread_request = self.factory.get(
            "/api/communication/messages/",
            {"conversation": conversation.id},
        )
        force_authenticate(thread_request, user=self.user)
        thread_response = CommunicationMessageViewSet.as_view({"get": "list"})(thread_request)
        self.assertEqual(thread_response.status_code, 200)
        thread_rows = as_rows(thread_response.data)
        self.assertEqual([row["content"] for row in thread_rows], ["Older message", "Newer message"])

        dashboard_request = self.factory.get(
            "/api/communication/messages/",
            {"ordering": "-created_at", "limit": 1},
        )
        force_authenticate(dashboard_request, user=self.user)
        dashboard_response = CommunicationMessageViewSet.as_view({"get": "list"})(dashboard_request)
        self.assertEqual(dashboard_response.status_code, 200)
        dashboard_rows = as_rows(dashboard_response.data)
        self.assertEqual(len(dashboard_rows), 1)
        self.assertEqual(dashboard_rows[0]["content"], "Newer message")
        self.assertEqual(dashboard_rows[0]["delivery_status"], "Read")
        self.assertEqual(dashboard_rows[0]["sender_name"], "teacher1")

    @override_settings(COMMUNICATION_WEBHOOK_TOKEN="test-webhook-token")
    def test_communication_core_flow(self):
        create_conversation = self.factory.post(
            "/api/communication/conversations/",
            {"conversation_type": "Direct", "title": "DM"},
            format="json",
        )
        force_authenticate(create_conversation, user=self.user)
        conversation_response = ConversationViewSet.as_view({"post": "create"})(create_conversation)
        self.assertEqual(conversation_response.status_code, 201)
        conversation_id = conversation_response.data["id"]

        add_participant = self.factory.post(
            f"/api/communication/conversations/{conversation_id}/participants/",
            {"user": self.user2.id, "role": "Member"},
            format="json",
        )
        force_authenticate(add_participant, user=self.user)
        add_participant_response = ConversationViewSet.as_view({"post": "add_participant"})(add_participant, pk=conversation_id)
        self.assertEqual(add_participant_response.status_code, 200)

        create_message = self.factory.post(
            "/api/communication/messages/",
            {"conversation": conversation_id, "content": "Hello"},
            format="json",
        )
        force_authenticate(create_message, user=self.user)
        message_response = CommunicationMessageViewSet.as_view({"post": "create"})(create_message)
        self.assertEqual(message_response.status_code, 201)
        message_id = message_response.data["id"]

        mark_read = self.factory.post(f"/api/communication/messages/{message_id}/read/", {}, format="json")
        force_authenticate(mark_read, user=self.user)
        read_response = CommunicationMessageViewSet.as_view({"post": "mark_read"})(mark_read, pk=message_id)
        self.assertEqual(read_response.status_code, 200)

        create_notification = self.factory.post(
            "/api/communication/notifications/",
            {"recipient": self.user2.id, "notification_type": "System", "title": "Alert", "message": "Test"},
            format="json",
        )
        force_authenticate(create_notification, user=self.user)
        notification_response = NotificationViewSet.as_view({"post": "create"})(create_notification)
        self.assertEqual(notification_response.status_code, 201)

        create_campaign = self.factory.post(
            "/api/communication/email-campaigns/",
            {"title": "Notice", "subject": "Subject", "body_text": "Body"},
            format="json",
        )
        force_authenticate(create_campaign, user=self.user)
        campaign_response = EmailCampaignViewSet.as_view({"post": "create"})(create_campaign)
        self.assertEqual(campaign_response.status_code, 201)
        campaign_id = campaign_response.data["id"]

        send_campaign = self.factory.post(
            f"/api/communication/email-campaigns/{campaign_id}/send/",
            {"emails": ["parent@school.local"]},
            format="json",
        )
        force_authenticate(send_campaign, user=self.user)
        send_campaign_response = EmailCampaignViewSet.as_view({"post": "send"})(send_campaign, pk=campaign_id)
        self.assertEqual(send_campaign_response.status_code, 200)

        send_sms = self.factory.post(
            "/api/communication/sms/send/",
            {"phones": ["+1555010001"], "message": "Hello parents", "channel": "SMS"},
            format="json",
        )
        force_authenticate(send_sms, user=self.user)
        sms_response = SmsSendView.as_view()(send_sms)
        self.assertEqual(sms_response.status_code, 201)

        analytics = self.factory.get("/api/communication/analytics/summary/")
        force_authenticate(analytics, user=self.user)
        analytics_response = CommunicationAnalyticsSummaryView.as_view()(analytics)
        self.assertEqual(analytics_response.status_code, 200)
        self.assertGreaterEqual(analytics_response.data["total_messages"], 1)

    @override_settings(COMMUNICATION_WEBHOOK_TOKEN="test-webhook-token")
    def test_message_edit_guard_and_sms_webhook_and_push(self):
        create_conversation = self.factory.post(
            "/api/communication/conversations/",
            {"conversation_type": "Direct", "title": "DM2"},
            format="json",
        )
        force_authenticate(create_conversation, user=self.user)
        conversation_response = ConversationViewSet.as_view({"post": "create"})(create_conversation)
        self.assertEqual(conversation_response.status_code, 201)
        conversation_id = conversation_response.data["id"]

        add_participant = self.factory.post(
            f"/api/communication/conversations/{conversation_id}/participants/",
            {"user": self.user2.id, "role": "Member"},
            format="json",
        )
        force_authenticate(add_participant, user=self.user)
        add_participant_response = ConversationViewSet.as_view({"post": "add_participant"})(add_participant, pk=conversation_id)
        self.assertEqual(add_participant_response.status_code, 200)

        create_message = self.factory.post(
            "/api/communication/messages/",
            {"conversation": conversation_id, "content": "Guard test"},
            format="json",
        )
        force_authenticate(create_message, user=self.user)
        message_response = CommunicationMessageViewSet.as_view({"post": "create"})(create_message)
        self.assertEqual(message_response.status_code, 201)
        message_id = message_response.data["id"]

        update_by_other = self.factory.patch(
            f"/api/communication/messages/{message_id}/",
            {"content": "Edited by other"},
            format="json",
        )
        force_authenticate(update_by_other, user=self.user2)
        update_response = CommunicationMessageViewSet.as_view({"patch": "partial_update"})(update_by_other, pk=message_id)
        self.assertEqual(update_response.status_code, 403)

        send_sms = self.factory.post(
            "/api/communication/sms/send/",
            {"phones": ["+1555010002"], "message": "Webhook test", "channel": "SMS"},
            format="json",
        )
        force_authenticate(send_sms, user=self.user)
        sms_response = SmsSendView.as_view()(send_sms)
        self.assertEqual(sms_response.status_code, 201)
        provider_id = sms_response.data[0]["provider_id"]

        sms_webhook = self.factory.post(
            "/api/communication/webhooks/sms/",
            {"provider_id": provider_id, "status": "Delivered"},
            format="json",
            HTTP_X_WEBHOOK_TOKEN="test-webhook-token",
        )
        webhook_response = SmsWebhookView.as_view()(sms_webhook)
        self.assertEqual(webhook_response.status_code, 200)

        register_device = self.factory.post(
            "/api/communication/push/devices/",
            {"token": "token-abc-123", "platform": "Web"},
            format="json",
        )
        force_authenticate(register_device, user=self.user2)
        register_response = PushDeviceViewSet.as_view({"post": "create"})(register_device)
        self.assertEqual(register_response.status_code, 201)

        push_send = self.factory.post(
            "/api/communication/push/send/",
            {"users": [self.user2.id], "title": "Push", "body": "Hello"},
            format="json",
        )
        force_authenticate(push_send, user=self.user)
        push_response = PushSendView.as_view()(push_send)
        self.assertEqual(push_response.status_code, 201)

        invalid_sms_webhook = self.factory.post(
            "/api/communication/webhooks/sms/",
            {"provider_id": provider_id, "status": "Delivered"},
            format="json",
            HTTP_X_WEBHOOK_TOKEN="wrong-token",
        )
        invalid_response = SmsWebhookView.as_view()(invalid_sms_webhook)
        self.assertEqual(invalid_response.status_code, 403)

    @override_settings(
        COMMUNICATION_WEBHOOK_SHARED_SECRET="test-secret",
        COMMUNICATION_WEBHOOK_TOKEN="",
        COMMUNICATION_WEBHOOK_REQUIRE_TIMESTAMP=True,
        COMMUNICATION_WEBHOOK_MAX_AGE_SECONDS=300,
    )
    def test_webhook_signature_with_timestamp_and_strict_status_validation(self):
        send_sms = self.factory.post(
            "/api/communication/sms/send/",
            {"phones": ["+1555010003"], "message": "Signature test", "channel": "SMS"},
            format="json",
        )
        force_authenticate(send_sms, user=self.user)
        sms_response = SmsSendView.as_view()(send_sms)
        self.assertEqual(sms_response.status_code, 201)
        provider_id = sms_response.data[0]["provider_id"]

        sms_payload = {"provider_id": provider_id, "status": "delivered"}
        sms_payload_json = json.dumps(sms_payload, separators=(",", ":"))
        sms_payload_bytes = sms_payload_json.encode("utf-8")
        timestamp = str(int(timezone.now().timestamp()))
        signature = hmac.new(
            b"test-secret",
            f"{timestamp}.{sms_payload_json}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        sms_webhook = self.factory.post(
            "/api/communication/webhooks/sms/",
            sms_payload_json,
            content_type="application/json",
            HTTP_X_WEBHOOK_TIMESTAMP=timestamp,
            HTTP_X_WEBHOOK_SIGNATURE=signature,
        )
        sms_webhook_response = SmsWebhookView.as_view()(sms_webhook)
        self.assertEqual(sms_webhook_response.status_code, 200)

        invalid_status_payload = {"provider_id": provider_id, "status": "mystery"}
        invalid_status_json = json.dumps(invalid_status_payload, separators=(",", ":"))
        invalid_status_bytes = invalid_status_json.encode("utf-8")
        invalid_status_sig = hmac.new(
            b"test-secret",
            f"{timestamp}.{invalid_status_json}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        invalid_status_webhook = self.factory.post(
            "/api/communication/webhooks/sms/",
            invalid_status_json,
            content_type="application/json",
            HTTP_X_WEBHOOK_TIMESTAMP=timestamp,
            HTTP_X_WEBHOOK_SIGNATURE=invalid_status_sig,
        )
        invalid_status_response = SmsWebhookView.as_view()(invalid_status_webhook)
        self.assertEqual(invalid_status_response.status_code, 400)

        create_campaign = self.factory.post(
            "/api/communication/email-campaigns/",
            {"title": "Webhook", "subject": "Subject", "body_text": "Body"},
            format="json",
        )
        force_authenticate(create_campaign, user=self.user)
        campaign_response = EmailCampaignViewSet.as_view({"post": "create"})(create_campaign)
        self.assertEqual(campaign_response.status_code, 201)
        campaign_id = campaign_response.data["id"]

        send_campaign = self.factory.post(
            f"/api/communication/email-campaigns/{campaign_id}/send/",
            {"emails": ["guardian@school.local"]},
            format="json",
        )
        force_authenticate(send_campaign, user=self.user)
        send_response = EmailCampaignViewSet.as_view({"post": "send"})(send_campaign, pk=campaign_id)
        self.assertEqual(send_response.status_code, 200)

        provider_id_email = EmailRecipient.objects.filter(campaign_id=campaign_id).order_by("-id").values_list("provider_id", flat=True).first()
        self.assertTrue(provider_id_email)
        email_payload = {"provider_id": provider_id_email, "status": "open"}
        email_payload_json = json.dumps(email_payload, separators=(",", ":"))
        email_payload_bytes = email_payload_json.encode("utf-8")
        email_sig = hmac.new(
            b"test-secret",
            f"{timestamp}.{email_payload_json}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        email_webhook = self.factory.post(
            "/api/communication/webhooks/email/",
            email_payload_json,
            content_type="application/json",
            HTTP_X_WEBHOOK_TIMESTAMP=timestamp,
            HTTP_X_WEBHOOK_SIGNATURE=email_sig,
        )
        email_webhook_response = EmailWebhookView.as_view()(email_webhook)
        self.assertEqual(email_webhook_response.status_code, 200)

    @override_settings(
        COMMUNICATION_WEBHOOK_TOKEN="",
        COMMUNICATION_WEBHOOK_SHARED_SECRET="",
        COMMUNICATION_WEBHOOK_STRICT_MODE=False,
    )
    def test_webhook_allows_unconfigured_verification_in_non_strict_mode(self):
        send_sms = self.factory.post(
            "/api/communication/sms/send/",
            {"phones": ["+1555010004"], "message": "Non-strict webhook test", "channel": "SMS"},
            format="json",
        )
        force_authenticate(send_sms, user=self.user)
        sms_response = SmsSendView.as_view()(send_sms)
        self.assertEqual(sms_response.status_code, 201)
        provider_id = sms_response.data[0]["provider_id"]

        sms_webhook = self.factory.post(
            "/api/communication/webhooks/sms/",
            {"provider_id": provider_id, "status": "Delivered"},
            format="json",
        )
        webhook_response = SmsWebhookView.as_view()(sms_webhook)
        self.assertEqual(webhook_response.status_code, 200)
