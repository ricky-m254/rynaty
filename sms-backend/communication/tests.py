from datetime import timedelta
import hashlib
import hmac
from io import StringIO
import json
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import urlencode
from asgiref.sync import async_to_sync
from asgiref.testing import ApplicationCommunicator
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core import mail

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.test import TestCase
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework_simplejwt.tokens import RefreshToken

from clients.models import Domain, Tenant
from config.asgi import application as asgi_application
from school.models import Module, Role, SchoolProfile, TenantSettings, UserProfile
from school.models import UserModuleAssignment
from school.tenant_secrets import (
    get_tenant_secret,
    resolve_school_profile_secret,
    set_tenant_secret,
    store_school_profile_secrets,
    tenant_setting_secret_key,
)

from .campaign_stats import sync_campaign_stats
from .delivery_backbone import ensure_unified_message
from .gateway_status import sync_gateway_statuses
from .views import (
    CommunicationAlertEventViewSet,
    CommunicationAlertsFeedView,
    CommunicationAlertRuleViewSet,
    CommunicationGatewaySettingsView,
    CommunicationGatewayTestView,
    CommunicationAnalyticsSummaryView,
    CommunicationAnalyticsCampaignPerformanceView,
    CommunicationAnalyticsDeliveryHistoryView,
    CommunicationAnalyticsEngagementView,
    CommunicationAnalyticsGatewayHealthView,
    CommunicationMessageViewSet,
    CommunicationUnifiedMessageDetailView,
    CommunicationUnifiedMessageListView,
    ConversationViewSet,
    EmailCampaignViewSet,
    EmailWebhookView,
    NotificationViewSet,
    ParentFeeReminderView,
    PushDeviceViewSet,
    PushLogView,
    PushSendView,
    SmsStatusView,
    SmsWebhookView,
    SmsSendView,
)
from .models import (
    Announcement,
    CampaignStats,
    CommunicationAlertEvent,
    CommunicationAlertRule,
    CommunicationDispatchTask,
    CommunicationMessage,
    CommunicationRealtimeEvent,
    CommunicationRealtimePresence,
    Conversation,
    EmailCampaign,
    EmailRecipient,
    GatewayStatus,
    MessageDelivery,
    MessageTemplate,
    PushDevice,
    PushNotificationLog,
    SmsMessage,
    UnifiedMessage,
)

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

    def _run_due_campaign_command(self):
        stdout = StringIO()
        call_command(
            "dispatch_due_email_campaigns",
            schema_name=self.tenant.schema_name,
            stdout=stdout,
        )
        return stdout.getvalue()

    def _run_dispatch_queue_worker(self):
        stdout = StringIO()
        call_command(
            "process_communication_dispatch_queue",
            schema_name=self.tenant.schema_name,
            stdout=stdout,
        )
        return stdout.getvalue()

    def _run_backfill_command(self):
        stdout = StringIO()
        call_command(
            "backfill_communication_backbone",
            schema_name=self.tenant.schema_name,
            stdout=stdout,
        )
        return stdout.getvalue()

    def _run_alert_rule_evaluator_command(self):
        stdout = StringIO()
        call_command(
            "evaluate_communication_alert_rules",
            schema_name=self.tenant.schema_name,
            stdout=stdout,
        )
        return stdout.getvalue()

    def _run_rollout_verifier_command(self, **options):
        stdout = StringIO()
        call_command(
            "verify_communication_rollout",
            stdout=stdout,
            **options,
        )
        return stdout.getvalue()

    def _run_deployment_finalizer_command(self, **options):
        stdout = StringIO()
        call_command(
            "finalize_communication_deployment",
            stdout=stdout,
            **options,
        )
        return stdout.getvalue()

    def _configure_sms_transport(self, mock_post, provider_id="ATPid-live-001"):
        profile = SchoolProfile.objects.create(
            school_name="Communication School",
            phone="+254700000001",
            sms_provider="africastalking",
            sms_username="sandbox",
            sms_sender_id="SCHOOL",
            is_active=True,
        )
        store_school_profile_secrets(profile, {"sms_api_key": "sms-secret-123"}, updated_by=self.user)
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {
            "SMSMessageData": {
                "Recipients": [
                    {
                        "status": "Success",
                        "messageId": provider_id,
                        "cost": "KES 0.8000",
                    }
                ]
            }
        }

    def _make_access_token(self, user):
        token = RefreshToken.for_user(user).access_token
        token["tenant_id"] = self.tenant.schema_name
        return str(token)

    def _websocket_scope(self, path, token, *, last_event_id=0):
        query = urlencode({"token": token, "last_event_id": last_event_id})
        return {
            "type": "websocket",
            "path": path,
            "query_string": query.encode("utf-8"),
            "headers": [(b"host", b"communication.localhost")],
        }

    def _create_additional_tenant(self, schema_name: str):
        with schema_context("public"):
            tenant, _ = Tenant.objects.get_or_create(
                schema_name=schema_name,
                defaults={
                    "name": f"{schema_name} School",
                    "paid_until": "2030-01-01",
                },
            )
            Domain.objects.get_or_create(
                domain=f"{schema_name}.localhost",
                defaults={"tenant": tenant, "is_primary": True},
            )
        return tenant

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
        self.assertEqual(dashboard_rows[0]["channel"], "MESSAGE")

    def test_message_list_summary_mode_blends_unified_backbone_and_announcements(self):
        conversation = Conversation.objects.create(
            conversation_type="Direct",
            title="Activity feed blend",
            created_by=self.user,
        )
        conversation.participants.create(user=self.user, role="Admin", is_active=True)
        conversation.participants.create(user=self.user2, role="Member", is_active=True)

        chat_message = CommunicationMessage.objects.create(
            conversation=conversation,
            sender=self.user2,
            content="Chat activity row",
            delivery_status="Delivered",
        )
        CommunicationMessage.objects.filter(pk=chat_message.pk).update(sent_at=timezone.now() - timedelta(minutes=30))

        unified_message = ensure_unified_message(
            message_key="activity-feed-sms-1",
            kind="DIRECT",
            source_type="SmsBatch",
            title="Fee reminder SMS",
            body="Please clear your balance by Friday.",
            created_by=self.user,
            metadata={"channel": "SMS"},
        )
        UnifiedMessage.objects.filter(pk=unified_message.pk).update(
            created_at=timezone.now() - timedelta(minutes=15),
            updated_at=timezone.now() - timedelta(minutes=15),
        )

        Announcement.objects.create(
            title="Parents meeting schedule",
            body="Parents meeting starts at 4 PM in the main hall.",
            priority="Important",
            audience_type="All",
            publish_at=timezone.now() - timedelta(minutes=5),
            created_by=self.user,
            is_active=True,
        )

        request = self.factory.get(
            "/api/communication/messages/",
            {"ordering": "-created_at", "limit": 3},
        )
        force_authenticate(request, user=self.user)
        response = CommunicationMessageViewSet.as_view({"get": "list"})(request)
        self.assertEqual(response.status_code, 200)

        rows = as_rows(response.data)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["source_type"], "Announcement")
        self.assertEqual(rows[0]["title"], "Parents meeting schedule")
        self.assertEqual(rows[0]["channel"], "ANNOUNCEMENT")
        self.assertEqual(rows[1]["source_type"], "SmsBatch")
        self.assertEqual(rows[1]["channel"], "SMS")
        self.assertEqual(rows[1]["subject"], "Fee reminder SMS")
        self.assertEqual(rows[2]["source_type"], "CommunicationMessage")
        self.assertEqual(rows[2]["channel"], "MESSAGE")
        self.assertEqual(rows[2]["content"], "Chat activity row")

    def test_message_create_accepts_attachments_and_returns_absolute_urls(self):
        conversation = Conversation.objects.create(
            conversation_type="Direct",
            title="Attachment thread",
            created_by=self.user,
        )
        conversation.participants.create(user=self.user, role="Admin", is_active=True)
        conversation.participants.create(user=self.user2, role="Member", is_active=True)

        upload = SimpleUploadedFile(
            "notice.png",
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR",
            content_type="image/png",
        )
        request = self.factory.post(
            "/api/communication/messages/",
            {"conversation": str(conversation.id), "content": "See attachment", "attachments": upload},
            format="multipart",
        )
        force_authenticate(request, user=self.user)
        response = CommunicationMessageViewSet.as_view({"post": "create"})(request)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["message_type"], "Image")
        self.assertEqual(len(response.data["attachments"]), 1)
        attachment = response.data["attachments"][0]
        self.assertEqual(attachment["file_name"], "notice.png")
        self.assertTrue(attachment["is_image"])
        self.assertTrue(attachment["url"].startswith("http://testserver/"))
        self.assertTrue(attachment["preview_url"].startswith("http://testserver/"))

    def test_message_create_requires_text_or_attachment(self):
        conversation = Conversation.objects.create(
            conversation_type="Direct",
            title="Empty guard",
            created_by=self.user,
        )
        conversation.participants.create(user=self.user, role="Admin", is_active=True)
        conversation.participants.create(user=self.user2, role="Member", is_active=True)

        request = self.factory.post(
            "/api/communication/messages/",
            {"conversation": conversation.id, "content": "   "},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = CommunicationMessageViewSet.as_view({"post": "create"})(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get("error", {}).get("code"), "VALIDATION_ERROR")
        self.assertEqual(
            response.data.get("error", {}).get("details", {}).get("content"),
            "Message content or at least one attachment is required.",
        )

    def test_admin_can_bulk_create_and_audit_notifications(self):
        user3, _ = User.objects.get_or_create(
            username="parent_ops",
            defaults={"email": "parent.ops@school.local"},
        )
        user3.set_password("pass1234")
        user3.save(update_fields=["password"])
        role, _ = Role.objects.get_or_create(name="PARENT", defaults={"description": "Parent"})
        UserProfile.objects.get_or_create(user=user3, defaults={"role": role})

        create_notification = self.factory.post(
            "/api/communication/notifications/",
            {
                "recipient_ids": [self.user2.id, user3.id],
                "notification_type": "System",
                "title": "Bulk Alert",
                "message": "Test broadcast",
            },
            format="json",
        )
        force_authenticate(create_notification, user=self.user)
        response = NotificationViewSet.as_view({"post": "create"})(create_notification)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["created"], 2)

        list_request = self.factory.get("/api/communication/notifications/", {"scope": "true"})
        force_authenticate(list_request, user=self.user)
        list_response = NotificationViewSet.as_view({"get": "list"})(list_request)
        self.assertEqual(list_response.status_code, 200)
        self.assertGreaterEqual(len(as_rows(list_response.data)), 2)

        recipient_request = self.factory.get("/api/communication/notifications/recipients/", {"q": "teach"})
        force_authenticate(recipient_request, user=self.user)
        recipient_response = NotificationViewSet.as_view({"get": "recipients"})(recipient_request)
        self.assertEqual(recipient_response.status_code, 200)
        self.assertTrue(any(row["username"] == "teacher1" for row in recipient_response.data["results"]))

    def test_scheduled_campaign_is_queued_then_dispatched_when_due(self):
        scheduled_at = timezone.now() + timedelta(hours=2)
        create_campaign = self.factory.post(
            "/api/communication/email-campaigns/",
            {
                "title": "Scheduled notice",
                "subject": "Later subject",
                "body_text": "Later body",
                "scheduled_at": scheduled_at.isoformat(),
            },
            format="json",
        )
        force_authenticate(create_campaign, user=self.user)
        campaign_response = EmailCampaignViewSet.as_view({"post": "create"})(create_campaign)
        self.assertEqual(campaign_response.status_code, 201)
        self.assertEqual(campaign_response.data["status"], "Scheduled")
        campaign_id = campaign_response.data["id"]

        queue_request = self.factory.post(
            f"/api/communication/email-campaigns/{campaign_id}/send/",
            {"emails": ["guardian1@school.local", "guardian2@school.local"]},
            format="json",
        )
        force_authenticate(queue_request, user=self.user)
        queue_response = EmailCampaignViewSet.as_view({"post": "send"})(queue_request, pk=campaign_id)
        self.assertEqual(queue_response.status_code, 202)
        self.assertEqual(queue_response.data["status"], "Scheduled")
        self.assertEqual(queue_response.data["queued"], 2)
        self.assertEqual(EmailRecipient.objects.filter(campaign_id=campaign_id, status="Queued").count(), 2)

        EmailCampaign.objects.filter(id=campaign_id).update(scheduled_at=timezone.now() - timedelta(minutes=1))
        dispatch_request = self.factory.post("/api/communication/email-campaigns/dispatch-due/", {}, format="json")
        force_authenticate(dispatch_request, user=self.user)
        dispatch_response = EmailCampaignViewSet.as_view({"post": "dispatch_due"})(dispatch_request)
        self.assertEqual(dispatch_response.status_code, 200)
        self.assertEqual(dispatch_response.data["dispatched"], 1)
        self.assertEqual(CommunicationDispatchTask.objects.filter(source_type="EmailRecipient").count(), 2)
        self._run_dispatch_queue_worker()
        self.assertEqual(EmailRecipient.objects.filter(campaign_id=campaign_id, status="Sent").count(), 2)

    def test_dispatch_due_email_campaigns_command_processes_due_campaigns(self):
        campaign = EmailCampaign.objects.create(
            title="Command notice",
            subject="Command subject",
            body_text="Command body",
            status="Scheduled",
            scheduled_at=timezone.now() - timedelta(minutes=5),
            created_by=self.user,
        )
        EmailRecipient.objects.create(campaign=campaign, email="guardian1@school.local", status="Queued")
        EmailRecipient.objects.create(campaign=campaign, email="guardian2@school.local", status="Queued")

        stdout = StringIO()
        call_command(
            "dispatch_due_email_campaigns",
            schema_name=self.tenant.schema_name,
            stdout=stdout,
        )

        campaign.refresh_from_db()
        self.assertEqual(campaign.status, "Sending")
        self.assertEqual(CommunicationDispatchTask.objects.filter(source_type="EmailRecipient").count(), 2)
        self._run_dispatch_queue_worker()
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, "Sent")
        self.assertEqual(EmailRecipient.objects.filter(campaign=campaign, status="Sent").count(), 2)
        self.assertIn("dispatched=1", stdout.getvalue())

    def test_dispatch_due_email_campaigns_command_all_tenants_processes_each_schema(self):
        second_tenant = self._create_additional_tenant("communication_test_two")
        current_campaign = EmailCampaign.objects.create(
            title="Primary tenant due",
            subject="Primary subject",
            body_text="Primary body",
            status="Scheduled",
            scheduled_at=timezone.now() - timedelta(minutes=5),
            created_by=self.user,
        )
        EmailRecipient.objects.create(campaign=current_campaign, email="primary@school.local")

        with schema_context(second_tenant.schema_name):
            second_user, _ = User.objects.get_or_create(
                username="comm_admin_two",
                defaults={"email": "admin-two@school.local"},
            )
            second_campaign = EmailCampaign.objects.create(
                title="Secondary tenant due",
                subject="Secondary subject",
                body_text="Secondary body",
                status="Scheduled",
                scheduled_at=timezone.now() - timedelta(minutes=5),
                created_by=second_user,
            )
            EmailRecipient.objects.create(campaign=second_campaign, email="secondary@school.local")
            second_campaign_id = second_campaign.id

        stdout = StringIO()
        call_command("dispatch_due_email_campaigns", all_tenants=True, stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("Running across 2 tenant schema(s).", output)
        self.assertIn(f"[{self.tenant.schema_name}] dispatched=1", output)
        self.assertIn(f"[{second_tenant.schema_name}] dispatched=1", output)

        current_campaign.refresh_from_db()
        self.assertEqual(current_campaign.status, "Sending")
        self.assertEqual(CommunicationDispatchTask.objects.filter(source_type="EmailRecipient").count(), 1)

        with schema_context(second_tenant.schema_name):
            second_campaign = EmailCampaign.objects.get(id=second_campaign_id)
            self.assertEqual(second_campaign.status, "Sending")
            self.assertEqual(CommunicationDispatchTask.objects.filter(source_type="EmailRecipient").count(), 1)

    def test_campaign_dispatch_creates_unified_message_and_fans_out_deliveries(self):
        campaign = EmailCampaign.objects.create(
            title="Unified campaign",
            subject="Unified subject",
            body_text="Unified campaign body",
            status="Scheduled",
            scheduled_at=timezone.now() - timedelta(minutes=5),
            created_by=self.user,
        )
        first = EmailRecipient.objects.create(campaign=campaign, email="guardian1@school.local", status="Queued")
        second = EmailRecipient.objects.create(campaign=campaign, email="guardian2@school.local", status="Queued")

        self._run_due_campaign_command()

        unified_message = UnifiedMessage.objects.get(source_type="EmailCampaign", source_id=campaign.id)
        deliveries = list(MessageDelivery.objects.filter(unified_message=unified_message).order_by("source_id"))
        self.assertEqual(unified_message.kind, "CAMPAIGN")
        self.assertEqual(unified_message.status, "Queued")
        self.assertEqual([delivery.source_id for delivery in deliveries], [first.id, second.id])
        self.assertTrue(all(delivery.status == "Queued" for delivery in deliveries))
        self.assertTrue(all(delivery.channel == "EMAIL" for delivery in deliveries))
        self.assertEqual(CommunicationDispatchTask.objects.filter(delivery__unified_message=unified_message).count(), 2)

        self._run_dispatch_queue_worker()

        unified_message.refresh_from_db()
        deliveries = list(MessageDelivery.objects.filter(unified_message=unified_message).order_by("source_id"))
        self.assertEqual(unified_message.status, "Sent")
        self.assertTrue(all(delivery.status == "Sent" for delivery in deliveries))
        self.assertTrue(all(delivery.provider_id.startswith("email-local-") for delivery in deliveries))

    def test_failed_sms_dispatch_retries_then_marks_row_failed(self):
        send_sms = self.factory.post(
            "/api/communication/sms/send/",
            {"phones": ["+1555010777"], "message": "Retry me", "channel": "SMS"},
            format="json",
        )
        force_authenticate(send_sms, user=self.user)
        response = SmsSendView.as_view()(send_sms)

        self.assertEqual(response.status_code, 202)
        sms_row = SmsMessage.objects.get(id=response.data[0]["id"])
        task = CommunicationDispatchTask.objects.get(source_type="SmsMessage", source_id=sms_row.id)
        task.max_attempts = 2
        task.save(update_fields=["max_attempts"])

        self._run_dispatch_queue_worker()
        sms_row.refresh_from_db()
        task.refresh_from_db()
        self.assertEqual(sms_row.status, "Queued")
        self.assertEqual(task.status, "Queued")
        self.assertEqual(task.attempts, 1)

        task.available_at = timezone.now() - timedelta(seconds=1)
        task.save(update_fields=["available_at"])
        self._run_dispatch_queue_worker()
        sms_row.refresh_from_db()
        task.refresh_from_db()
        self.assertEqual(sms_row.status, "Failed")
        self.assertEqual(task.status, "Failed")
        self.assertEqual(task.attempts, 2)

    @override_settings(COMMUNICATION_WEBHOOK_TOKEN="test-webhook-token")
    @patch("communication.services.requests.post")
    def test_sms_delivery_backbone_tracks_worker_and_webhook_states(self, mock_post):
        self._configure_sms_transport(mock_post, provider_id="ATPid-unified-001")
        send_sms = self.factory.post(
            "/api/communication/sms/send/",
            {"phones": ["+1555010555"], "message": "Unified SMS", "channel": "SMS"},
            format="json",
        )
        force_authenticate(send_sms, user=self.user)
        response = SmsSendView.as_view()(send_sms)

        self.assertEqual(response.status_code, 202)
        sms_row = SmsMessage.objects.get(id=response.data[0]["id"])
        task = CommunicationDispatchTask.objects.get(source_type="SmsMessage", source_id=sms_row.id)
        delivery = MessageDelivery.objects.get(source_type="SmsMessage", source_id=sms_row.id)
        unified_message = UnifiedMessage.objects.get(id=delivery.unified_message_id)

        self.assertEqual(task.delivery_id, delivery.id)
        self.assertEqual(delivery.status, "Queued")
        self.assertEqual(unified_message.status, "Queued")

        self._run_dispatch_queue_worker()

        sms_row.refresh_from_db()
        delivery.refresh_from_db()
        unified_message.refresh_from_db()
        self.assertEqual(sms_row.status, "Sent")
        self.assertEqual(delivery.status, "Sent")
        self.assertEqual(delivery.provider_id, sms_row.provider_id)
        self.assertEqual(delivery.attempts, 1)
        self.assertEqual(unified_message.status, "Sent")

        sms_webhook = self.factory.post(
            "/api/communication/webhooks/sms/",
            {"provider_id": sms_row.provider_id, "status": "Delivered"},
            format="json",
            HTTP_X_WEBHOOK_TOKEN="test-webhook-token",
        )
        webhook_response = SmsWebhookView.as_view()(sms_webhook)

        self.assertEqual(webhook_response.status_code, 200)
        sms_row.refresh_from_db()
        delivery.refresh_from_db()
        self.assertEqual(sms_row.status, "Delivered")
        self.assertEqual(delivery.status, "Delivered")
        self.assertIsNotNone(delivery.delivered_at)

    def test_unified_message_detail_exposes_campaign_fanout(self):
        campaign = EmailCampaign.objects.create(
            title="Detail campaign",
            subject="Detail subject",
            body_text="Detail body text",
            status="Draft",
            created_by=self.user,
        )
        send_request = self.factory.post(
            f"/api/communication/email-campaigns/{campaign.id}/send/",
            {"emails": ["guardian1@school.local", "guardian2@school.local"]},
            format="json",
        )
        force_authenticate(send_request, user=self.user)
        send_response = EmailCampaignViewSet.as_view({"post": "send"})(send_request, pk=campaign.id)

        self.assertEqual(send_response.status_code, 202)
        message_id = send_response.data["message_id"]
        self.assertTrue(message_id)

        detail_request = self.factory.get(f"/api/communication/unified-messages/{message_id}/")
        force_authenticate(detail_request, user=self.user)
        detail_response = CommunicationUnifiedMessageDetailView.as_view()(detail_request, pk=message_id)

        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.data["id"], message_id)
        self.assertEqual(detail_response.data["kind"], "CAMPAIGN")
        self.assertEqual(detail_response.data["source_type"], "EmailCampaign")
        self.assertEqual(detail_response.data["campaign_id"], campaign.id)
        self.assertEqual(detail_response.data["delivery_count"], 2)
        self.assertEqual(detail_response.data["delivery_status"]["queued"], 2)
        self.assertEqual(detail_response.data["channels"], ["email"])
        self.assertEqual(len(detail_response.data["deliveries"]), 2)
        self.assertTrue(all(row["channel"] == "EMAIL" for row in detail_response.data["deliveries"]))
        self.assertTrue(all(row["source_type"] == "EmailRecipient" for row in detail_response.data["deliveries"]))

    @patch("communication.services.requests.post")
    def test_unified_message_list_filters_by_channel_and_status(self, mock_post):
        self._configure_sms_transport(mock_post, provider_id="ATPid-unified-filter-001")
        send_sms = self.factory.post(
            "/api/communication/sms/send/",
            {"phones": ["+1555010111"], "message": "Feed SMS", "channel": "SMS"},
            format="json",
        )
        force_authenticate(send_sms, user=self.user)
        sms_response = SmsSendView.as_view()(send_sms)

        self.assertEqual(sms_response.status_code, 202)
        self._run_dispatch_queue_worker()

        notify_request = self.factory.post(
            "/api/communication/parent/fee-reminder/",
            {"emails": ["parent1@school.local"], "subject": "Fee Reminder", "message": "Queued email"},
            format="json",
        )
        force_authenticate(notify_request, user=self.user)
        notify_response = ParentFeeReminderView.as_view()(notify_request)

        self.assertEqual(notify_response.status_code, 202)

        sms_list_request = self.factory.get(
            "/api/communication/unified-messages/",
            {"channel": "sms", "status": "Sent"},
        )
        force_authenticate(sms_list_request, user=self.user)
        sms_list_response = CommunicationUnifiedMessageListView.as_view()(sms_list_request)

        self.assertEqual(sms_list_response.status_code, 200)
        self.assertEqual(sms_list_response.data["count"], 1)
        sms_row = sms_list_response.data["results"][0]
        self.assertEqual(sms_row["source_type"], "SmsBatch")
        self.assertEqual(sms_row["status"], "Sent")
        self.assertEqual(sms_row["delivery_status"]["sent"], 1)
        self.assertEqual(sms_row["channels"], ["sms"])

        email_list_request = self.factory.get(
            "/api/communication/unified-messages/",
            {"channel": "email", "status": "Queued"},
        )
        force_authenticate(email_list_request, user=self.user)
        email_list_response = CommunicationUnifiedMessageListView.as_view()(email_list_request)

        self.assertEqual(email_list_response.status_code, 200)
        self.assertGreaterEqual(email_list_response.data["count"], 1)
        self.assertTrue(any(row["source_type"] == "DirectEmailBatch" for row in email_list_response.data["results"]))

    def test_existing_campaign_routes_expose_unified_backbone_references(self):
        campaign = EmailCampaign.objects.create(
            title="Legacy campaign bridge",
            subject="Bridge subject",
            body_text="Bridge body",
            status="Draft",
            created_by=self.user,
        )
        send_request = self.factory.post(
            f"/api/communication/email-campaigns/{campaign.id}/send/",
            {"emails": ["guardian1@school.local", "guardian2@school.local"]},
            format="json",
        )
        force_authenticate(send_request, user=self.user)
        send_response = EmailCampaignViewSet.as_view({"post": "send"})(send_request, pk=campaign.id)

        self.assertEqual(send_response.status_code, 202)
        message_id = send_response.data["message_id"]
        self.assertTrue(message_id)

        retrieve_request = self.factory.get(f"/api/communication/email-campaigns/{campaign.id}/")
        force_authenticate(retrieve_request, user=self.user)
        retrieve_response = EmailCampaignViewSet.as_view({"get": "retrieve"})(retrieve_request, pk=campaign.id)

        self.assertEqual(retrieve_response.status_code, 200)
        self.assertEqual(retrieve_response.data["message_id"], message_id)
        self.assertEqual(retrieve_response.data["message_status"], "Queued")
        self.assertEqual(retrieve_response.data["message_kind"], "CAMPAIGN")
        self.assertEqual(retrieve_response.data["message_channels"], ["email"])
        self.assertEqual(retrieve_response.data["delivery_summary"]["total"], 2)
        self.assertEqual(retrieve_response.data["delivery_summary"]["queued"], 2)

        recipients_request = self.factory.get(f"/api/communication/email-campaigns/{campaign.id}/recipients/")
        force_authenticate(recipients_request, user=self.user)
        recipients_response = EmailCampaignViewSet.as_view({"get": "recipients"})(recipients_request, pk=campaign.id)

        self.assertEqual(recipients_response.status_code, 200)
        self.assertEqual(len(recipients_response.data), 2)
        self.assertTrue(all(row["message_id"] == message_id for row in recipients_response.data))
        self.assertTrue(all(row["delivery_id"] for row in recipients_response.data))
        self.assertTrue(all(row["delivery_status"] == "Queued" for row in recipients_response.data))
        self.assertTrue(all(row["delivery_channel"] == "EMAIL" for row in recipients_response.data))

    def test_existing_sms_and_push_routes_expose_delivery_references(self):
        send_sms = self.factory.post(
            "/api/communication/sms/send/",
            {"phones": ["+1555010222"], "message": "Legacy SMS bridge", "channel": "SMS"},
            format="json",
        )
        force_authenticate(send_sms, user=self.user)
        sms_response = SmsSendView.as_view()(send_sms)

        self.assertEqual(sms_response.status_code, 202)
        sms_row = sms_response.data[0]
        self.assertTrue(sms_row["message_id"])
        self.assertTrue(sms_row["delivery_id"])
        self.assertEqual(sms_row["delivery_status"], "Queued")
        self.assertEqual(sms_row["delivery_channel"], "SMS")

        sms_status_request = self.factory.get(f"/api/communication/sms/{sms_row['id']}/status/")
        force_authenticate(sms_status_request, user=self.user)
        sms_status_response = SmsStatusView.as_view()(sms_status_request, pk=sms_row["id"])

        self.assertEqual(sms_status_response.status_code, 200)
        self.assertEqual(sms_status_response.data["message_id"], sms_row["message_id"])
        self.assertEqual(sms_status_response.data["delivery_id"], sms_row["delivery_id"])

        push_send = self.factory.post(
            "/api/communication/push/send/",
            {"users": [self.user2.id], "title": "Legacy push bridge", "body": "Push body"},
            format="json",
        )
        force_authenticate(push_send, user=self.user)
        push_response = PushSendView.as_view()(push_send)

        self.assertEqual(push_response.status_code, 202)
        push_row = push_response.data[0]
        self.assertTrue(push_row["message_id"])
        self.assertTrue(push_row["delivery_id"])
        self.assertEqual(push_row["delivery_status"], "Queued")
        self.assertEqual(push_row["delivery_channel"], "PUSH")

        push_logs_request = self.factory.get("/api/communication/push/")
        force_authenticate(push_logs_request, user=self.user)
        push_logs_response = PushLogView.as_view()(push_logs_request)

        self.assertEqual(push_logs_response.status_code, 200)
        self.assertTrue(any(row["id"] == push_row["id"] and row["delivery_id"] == push_row["delivery_id"] for row in push_logs_response.data))

    def test_campaign_stats_snapshot_persists_first_class_metrics(self):
        campaign = EmailCampaign.objects.create(
            title="Stats snapshot campaign",
            subject="Stats subject",
            body_text="Stats body",
            status="Sent",
            sent_at=timezone.now() - timedelta(minutes=10),
            created_by=self.user,
        )
        EmailRecipient.objects.create(campaign=campaign, email="sent@school.local", status="Sent")
        EmailRecipient.objects.create(campaign=campaign, email="delivered@school.local", status="Delivered")
        EmailRecipient.objects.create(campaign=campaign, email="opened@school.local", status="Opened", open_count=2)
        EmailRecipient.objects.create(campaign=campaign, email="clicked@school.local", status="Clicked", open_count=1, click_count=1)
        EmailRecipient.objects.create(campaign=campaign, email="failed@school.local", status="Bounced")

        stats = sync_campaign_stats(campaign)

        self.assertEqual(stats.campaign_id, campaign.id)
        self.assertEqual(stats.total_recipients, 5)
        self.assertEqual(stats.successful_recipients, 4)
        self.assertEqual(stats.delivered_recipients, 3)
        self.assertEqual(stats.opened_recipients, 2)
        self.assertEqual(stats.clicked_recipients, 1)
        self.assertEqual(stats.bounced_recipients, 1)
        self.assertEqual(stats.failed_recipients, 1)
        self.assertEqual(stats.open_events, 3)
        self.assertEqual(stats.click_events, 1)
        self.assertEqual(float(stats.delivery_rate), 80.0)
        self.assertEqual(float(stats.open_rate), 40.0)
        self.assertEqual(float(stats.click_rate), 20.0)

        campaign_stats_request = self.factory.get(f"/api/communication/email-campaigns/{campaign.id}/stats/")
        force_authenticate(campaign_stats_request, user=self.user)
        campaign_stats_response = EmailCampaignViewSet.as_view({"get": "stats"})(campaign_stats_request, pk=campaign.id)

        self.assertEqual(campaign_stats_response.status_code, 200)
        self.assertEqual(campaign_stats_response.data["bounced"], 1)
        self.assertEqual(campaign_stats_response.data["failed"], 1)
        self.assertEqual(campaign_stats_response.data["open_events"], 3)

        performance_request = self.factory.get("/api/communication/analytics/campaign-performance/", {"limit": 5})
        force_authenticate(performance_request, user=self.user)
        performance_response = CommunicationAnalyticsCampaignPerformanceView.as_view()(performance_request)

        self.assertEqual(performance_response.status_code, 200)
        row = performance_response.data["results"][0]
        self.assertEqual(row["campaign_id"], campaign.id)
        self.assertEqual(row["total_recipients"], 5)
        self.assertEqual(row["bounced_recipients"], 1)
        self.assertEqual(row["open_events"], 3)
        self.assertEqual(row["click_events"], 1)
        self.assertEqual(row["delivery_rate"], 80.0)
        self.assertTrue(row["last_synced_at"])

    @override_settings(COMMUNICATION_WEBHOOK_TOKEN="test-webhook-token")
    def test_email_webhook_updates_campaign_stats_snapshot(self):
        campaign = EmailCampaign.objects.create(
            title="Webhook stats campaign",
            subject="Webhook subject",
            body_text="Webhook body",
            status="Sending",
            created_by=self.user,
        )
        recipient = EmailRecipient.objects.create(
            campaign=campaign,
            email="family@school.local",
            provider_id="email-webhook-stats-001",
            status="Sent",
            sent_at=timezone.now() - timedelta(minutes=2),
        )
        sync_campaign_stats(campaign)

        email_webhook = self.factory.post(
            "/api/communication/webhooks/email/",
            {"provider_id": recipient.provider_id, "status": "open"},
            format="json",
            HTTP_X_WEBHOOK_TOKEN="test-webhook-token",
        )
        email_webhook_response = EmailWebhookView.as_view()(email_webhook)

        self.assertEqual(email_webhook_response.status_code, 200)
        stats = CampaignStats.objects.get(campaign=campaign)
        self.assertEqual(stats.total_recipients, 1)
        self.assertEqual(stats.successful_recipients, 1)
        self.assertEqual(stats.opened_recipients, 1)
        self.assertEqual(stats.open_events, 1)
        self.assertEqual(float(stats.open_rate), 100.0)
        self.assertIsNotNone(stats.last_event_at)

    def test_dispatch_queue_health_reports_retry_and_failure_details(self):
        now = timezone.now()
        CommunicationDispatchTask.objects.create(
            channel="SMS",
            status="Queued",
            source_type="SmsMessage",
            source_id=101,
            recipient="+1555010101",
            payload={"channel": "SMS"},
            dedupe_key="health-ready-task",
            available_at=now - timedelta(minutes=5),
        )
        CommunicationDispatchTask.objects.create(
            channel="PUSH",
            status="Queued",
            source_type="PushNotificationLog",
            source_id=202,
            recipient=str(self.user2.id),
            payload={},
            dedupe_key="health-retrying-task",
            attempts=1,
            available_at=now + timedelta(minutes=2),
            last_error="Temporary push outage",
        )
        CommunicationDispatchTask.objects.create(
            channel="EMAIL",
            status="Failed",
            source_type="DirectEmail",
            recipient="ops@school.local",
            payload={"subject": "Alert"},
            dedupe_key="health-failed-task",
            attempts=3,
            max_attempts=3,
            processed_at=now,
            last_error="Provider rejected request",
        )

        analytics = self.factory.get("/api/communication/analytics/summary/")
        force_authenticate(analytics, user=self.user)
        analytics_response = CommunicationAnalyticsSummaryView.as_view()(analytics)

        self.assertEqual(analytics_response.status_code, 200)
        queue_health = analytics_response.data["dispatch_queue"]
        self.assertEqual(queue_health["total"], 3)
        self.assertEqual(queue_health["ready"], 1)
        self.assertEqual(queue_health["delayed"], 1)
        self.assertEqual(queue_health["retrying"], 1)
        self.assertGreaterEqual(queue_health["oldest_ready_age_seconds"], 240)
        self.assertTrue(queue_health["oldest_ready_at"])
        self.assertEqual(queue_health["by_channel"]["sms"]["ready"], 1)
        self.assertEqual(queue_health["by_channel"]["push"]["delayed"], 1)
        self.assertEqual(queue_health["by_channel"]["push"]["retrying"], 1)
        self.assertEqual(queue_health["by_channel"]["email"]["failed"], 1)
        self.assertEqual(queue_health["recent_failures"][0]["recipient"], "ops@school.local")
        self.assertIn("Provider rejected", queue_health["recent_failures"][0]["last_error"])

    @patch("communication.services.requests.post")
    def test_dispatch_queue_worker_command_channel_filter_processes_selected_channel_only(self, mock_post):
        self._configure_sms_transport(mock_post, provider_id="ATPid-filter-001")
        TenantSettings.objects.create(
            key="integrations.push",
            value={"enabled": True},
            category="integrations",
        )
        set_tenant_secret(
            tenant_setting_secret_key("integrations.push", "server_key"),
            "push-secret-123",
            updated_by=self.user,
            description="integrations.push.server_key",
        )
        register_device = self.factory.post(
            "/api/communication/push/devices/",
            {"token": "token-filter-123", "platform": "Web"},
            format="json",
        )
        force_authenticate(register_device, user=self.user2)
        register_response = PushDeviceViewSet.as_view({"post": "create"})(register_device)
        self.assertEqual(register_response.status_code, 201)

        send_sms = self.factory.post(
            "/api/communication/sms/send/",
            {"phones": ["+1555010555"], "message": "SMS only pass", "channel": "SMS"},
            format="json",
        )
        force_authenticate(send_sms, user=self.user)
        sms_response = SmsSendView.as_view()(send_sms)
        self.assertEqual(sms_response.status_code, 202)

        push_send = self.factory.post(
            "/api/communication/push/send/",
            {"users": [self.user2.id], "title": "Push later", "body": "Channel filter"},
            format="json",
        )
        force_authenticate(push_send, user=self.user)
        push_response = PushSendView.as_view()(push_send)
        self.assertEqual(push_response.status_code, 202)

        sms_stdout = StringIO()
        call_command(
            "process_communication_dispatch_queue",
            schema_name=self.tenant.schema_name,
            channels=["SMS"],
            stdout=sms_stdout,
        )
        self.assertIn("processed=1", sms_stdout.getvalue())
        self.assertIn("sent=1", sms_stdout.getvalue())

        sms_row = SmsMessage.objects.get(id=sms_response.data[0]["id"])
        push_row = PushNotificationLog.objects.get(id=push_response.data[0]["id"])
        self.assertEqual(sms_row.status, "Sent")
        self.assertEqual(push_row.status, "Queued")
        self.assertEqual(mock_post.call_count, 1)

        push_http_response = Mock()
        push_http_response.status_code = 200
        push_http_response.json.return_value = {
            "success": 1,
            "failure": 0,
            "results": [{"message_id": "fcm-filter-001"}],
        }
        mock_post.return_value = push_http_response

        push_stdout = StringIO()
        call_command(
            "process_communication_dispatch_queue",
            schema_name=self.tenant.schema_name,
            channels=["PUSH"],
            stdout=push_stdout,
        )
        self.assertIn("processed=1", push_stdout.getvalue())
        self.assertEqual(mock_post.call_count, 2)

        push_row.refresh_from_db()
        self.assertEqual(push_row.status, "Sent")
        self.assertEqual(push_row.provider_id, "fcm-filter-001")

    def test_process_dispatch_queue_command_all_tenants_processes_each_schema(self):
        second_tenant = self._create_additional_tenant("communication_test_queue_two")
        current_task = CommunicationDispatchTask.objects.create(
            channel="EMAIL",
            status="Queued",
            source_type="DirectEmail",
            recipient="primary-ops@school.local",
            payload={
                "recipient": "primary-ops@school.local",
                "subject": "Primary ops",
                "body": "Primary body",
            },
            dedupe_key="primary-direct-email-task",
        )

        with schema_context(second_tenant.schema_name):
            second_task = CommunicationDispatchTask.objects.create(
                channel="EMAIL",
                status="Queued",
                source_type="DirectEmail",
                recipient="secondary-ops@school.local",
                payload={
                    "recipient": "secondary-ops@school.local",
                    "subject": "Secondary ops",
                    "body": "Secondary body",
                },
                dedupe_key="secondary-direct-email-task",
            )
            second_task_id = second_task.id

        stdout = StringIO()
        call_command("process_communication_dispatch_queue", all_tenants=True, stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("Running across 2 tenant schema(s).", output)
        self.assertIn(f"[{self.tenant.schema_name}] processed=1 sent=1 retried=0 failed=0", output)
        self.assertIn(f"[{second_tenant.schema_name}] processed=1 sent=1 retried=0 failed=0", output)

        current_task.refresh_from_db()
        self.assertEqual(current_task.status, "Sent")
        self.assertTrue(current_task.provider_id.startswith("email-local-"))

        with schema_context(second_tenant.schema_name):
            second_task = CommunicationDispatchTask.objects.get(id=second_task_id)
            self.assertEqual(second_task.status, "Sent")
            self.assertTrue(second_task.provider_id.startswith("email-local-"))

    def test_alert_rule_command_opens_and_resolves_queue_backlog_event(self):
        now = timezone.now()
        rule = CommunicationAlertRule.objects.create(
            name="SMS ready backlog",
            rule_type=CommunicationAlertRule.RULE_QUEUE_READY_BACKLOG,
            severity=CommunicationAlertRule.SEVERITY_WARNING,
            channel="SMS",
            threshold=2,
            created_by=self.user,
        )
        CommunicationDispatchTask.objects.create(
            channel="SMS",
            status="Queued",
            source_type="SmsMessage",
            recipient="+1555010101",
            payload={"channel": "SMS"},
            dedupe_key="alert-rule-sms-ready-1",
            available_at=now - timedelta(minutes=3),
        )
        CommunicationDispatchTask.objects.create(
            channel="SMS",
            status="Queued",
            source_type="SmsMessage",
            recipient="+1555010102",
            payload={"channel": "SMS"},
            dedupe_key="alert-rule-sms-ready-2",
            available_at=now - timedelta(minutes=1),
        )

        output = self._run_alert_rule_evaluator_command()

        self.assertIn("evaluated=1", output)
        self.assertIn("triggered=1", output)
        self.assertIn("open=1", output)
        event = CommunicationAlertEvent.objects.get(rule=rule)
        self.assertEqual(event.status, CommunicationAlertEvent.STATUS_OPEN)
        self.assertEqual(event.channel, "SMS")
        self.assertEqual(event.metadata["current_value"], 2)
        self.assertEqual(event.metadata["threshold"], 2)

        summary_request = self.factory.get("/api/communication/alerts/events/summary/")
        force_authenticate(summary_request, user=self.user)
        summary_response = CommunicationAlertEventViewSet.as_view({"get": "summary"})(summary_request)

        self.assertEqual(summary_response.status_code, 200)
        self.assertEqual(summary_response.data["open"], 1)
        self.assertEqual(summary_response.data["by_severity"]["warning_open"], 1)
        self.assertEqual(summary_response.data["recent"][0]["rule_name"], rule.name)

        CommunicationDispatchTask.objects.filter(dedupe_key__in=["alert-rule-sms-ready-1", "alert-rule-sms-ready-2"]).delete()

        rerun_output = self._run_alert_rule_evaluator_command()

        self.assertIn("resolved=1", rerun_output)
        event.refresh_from_db()
        self.assertEqual(event.status, CommunicationAlertEvent.STATUS_RESOLVED)
        self.assertIsNotNone(event.resolved_at)

    def test_alert_rule_api_evaluate_acknowledge_and_auto_resolve_gateway_event(self):
        rule = CommunicationAlertRule.objects.create(
            name="SMS gateway required",
            rule_type=CommunicationAlertRule.RULE_GATEWAY_UNCONFIGURED,
            severity=CommunicationAlertRule.SEVERITY_CRITICAL,
            channel="SMS",
            threshold=1,
            created_by=self.user,
        )

        evaluate_request = self.factory.post("/api/communication/alerts/rules/evaluate/", {}, format="json")
        force_authenticate(evaluate_request, user=self.user)
        evaluate_response = CommunicationAlertRuleViewSet.as_view({"post": "evaluate"})(evaluate_request)

        self.assertEqual(evaluate_response.status_code, 200)
        self.assertEqual(evaluate_response.data["opened"], 1)
        event = CommunicationAlertEvent.objects.get(rule=rule)
        self.assertEqual(event.status, CommunicationAlertEvent.STATUS_OPEN)
        self.assertEqual(event.severity, CommunicationAlertRule.SEVERITY_CRITICAL)

        list_request = self.factory.get("/api/communication/alerts/events/", {"status": "OPEN"})
        force_authenticate(list_request, user=self.user)
        list_response = CommunicationAlertEventViewSet.as_view({"get": "list"})(list_request)

        self.assertEqual(list_response.status_code, 200)
        rows = as_rows(list_response.data)
        self.assertTrue(any(row["id"] == event.id and row["rule_name"] == rule.name for row in rows))

        acknowledge_request = self.factory.post(
            f"/api/communication/alerts/events/{event.id}/acknowledge/",
            {},
            format="json",
        )
        force_authenticate(acknowledge_request, user=self.user)
        acknowledge_response = CommunicationAlertEventViewSet.as_view({"post": "acknowledge"})(
            acknowledge_request,
            pk=event.id,
        )

        self.assertEqual(acknowledge_response.status_code, 200)
        event.refresh_from_db()
        self.assertEqual(event.status, CommunicationAlertEvent.STATUS_ACKNOWLEDGED)
        self.assertIsNotNone(event.acknowledged_at)

        profile = SchoolProfile.objects.create(
            school_name="Configured SMS School",
            phone="+254700000002",
            sms_provider="africastalking",
            sms_username="sandbox",
            sms_sender_id="SCHOOL",
            is_active=True,
        )
        store_school_profile_secrets(profile, {"sms_api_key": "sms-secret-123"}, updated_by=self.user)

        second_evaluate_request = self.factory.post("/api/communication/alerts/rules/evaluate/", {}, format="json")
        force_authenticate(second_evaluate_request, user=self.user)
        second_evaluate_response = CommunicationAlertRuleViewSet.as_view({"post": "evaluate"})(second_evaluate_request)

        self.assertEqual(second_evaluate_response.status_code, 200)
        self.assertEqual(second_evaluate_response.data["resolved"], 1)
        event.refresh_from_db()
        self.assertEqual(event.status, CommunicationAlertEvent.STATUS_RESOLVED)
        self.assertIsNotNone(event.resolved_at)

    def test_alert_rule_command_all_tenants_processes_each_schema(self):
        second_tenant = self._create_additional_tenant("communication_test_alerts_two")
        CommunicationAlertRule.objects.create(
            name="Primary queue backlog",
            rule_type=CommunicationAlertRule.RULE_QUEUE_READY_BACKLOG,
            severity=CommunicationAlertRule.SEVERITY_WARNING,
            channel="EMAIL",
            threshold=1,
            created_by=self.user,
        )
        CommunicationDispatchTask.objects.create(
            channel="EMAIL",
            status="Queued",
            source_type="DirectEmail",
            recipient="primary-alerts@school.local",
            payload={"recipient": "primary-alerts@school.local"},
            dedupe_key="primary-alert-rule-email",
            available_at=timezone.now() - timedelta(minutes=2),
        )

        with schema_context(second_tenant.schema_name):
            second_user, _ = User.objects.get_or_create(
                username="comm_admin_alerts_two",
                defaults={"email": "admin-alerts-two@school.local"},
            )
            CommunicationAlertRule.objects.create(
                name="Secondary queue backlog",
                rule_type=CommunicationAlertRule.RULE_QUEUE_READY_BACKLOG,
                severity=CommunicationAlertRule.SEVERITY_WARNING,
                channel="EMAIL",
                threshold=1,
                created_by=second_user,
            )
            CommunicationDispatchTask.objects.create(
                channel="EMAIL",
                status="Queued",
                source_type="DirectEmail",
                recipient="secondary-alerts@school.local",
                payload={"recipient": "secondary-alerts@school.local"},
                dedupe_key="secondary-alert-rule-email",
                available_at=timezone.now() - timedelta(minutes=2),
            )

        stdout = StringIO()
        call_command("evaluate_communication_alert_rules", all_tenants=True, stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("Running across 2 tenant schema(s).", output)
        self.assertIn(f"[{self.tenant.schema_name}] evaluated=1 triggered=1 open=1", output)
        self.assertIn(f"[{second_tenant.schema_name}] evaluated=1 triggered=1 open=1", output)
        self.assertEqual(CommunicationAlertEvent.objects.filter(status=CommunicationAlertEvent.STATUS_OPEN).count(), 1)

        with schema_context(second_tenant.schema_name):
            self.assertEqual(CommunicationAlertEvent.objects.filter(status=CommunicationAlertEvent.STATUS_OPEN).count(), 1)

    def test_alerts_feed_combines_stored_alerts_announcements_and_backend_reminders(self):
        now = timezone.now()
        rule = CommunicationAlertRule.objects.create(
            name="Email failures",
            rule_type=CommunicationAlertRule.RULE_QUEUE_FAILED_ITEMS,
            severity=CommunicationAlertRule.SEVERITY_CRITICAL,
            channel="EMAIL",
            threshold=1,
            created_by=self.user,
        )
        CommunicationAlertEvent.objects.create(
            rule=rule,
            event_key="communication-alert-rule:test-email-failures",
            title="Email failures require attention",
            details="One or more email dispatches have failed.",
            severity=CommunicationAlertRule.SEVERITY_CRITICAL,
            status=CommunicationAlertEvent.STATUS_OPEN,
            channel="EMAIL",
            metadata={"current_value": 2, "threshold": 1},
            first_triggered_at=now - timedelta(minutes=5),
            last_triggered_at=now - timedelta(minutes=2),
        )
        Announcement.objects.create(
            title="Parent meeting schedule",
            body="The parent meeting schedule is now available for review.",
            priority="Important",
            audience_type="Parents",
            is_pinned=True,
            publish_at=now - timedelta(hours=1),
            created_by=self.user,
            is_active=True,
        )
        EmailCampaign.objects.create(
            title="Upcoming fee reminder campaign",
            subject="Fee Reminder",
            body_text="Reminder body",
            status="Scheduled",
            scheduled_at=now + timedelta(days=1),
            created_by=self.user,
            is_active=True,
        )
        EmailCampaign.objects.create(
            title="Draft transport notice",
            subject="Transport notice",
            body_text="Draft body",
            status="Draft",
            created_by=self.user,
            is_active=True,
        )

        feed_request = self.factory.get(
            "/api/communication/alerts/feed/",
            {"alert_limit": 5, "announcement_limit": 5, "reminder_limit": 5},
        )
        force_authenticate(feed_request, user=self.user)
        feed_response = CommunicationAlertsFeedView.as_view()(feed_request)

        self.assertEqual(feed_response.status_code, 200)
        payload = feed_response.data
        self.assertEqual(payload["summary"]["system_alerts"], 1)
        self.assertEqual(payload["summary"]["announcements"], 1)
        self.assertGreaterEqual(payload["summary"]["reminders"], 3)
        self.assertEqual(payload["summary"]["critical_alerts"], 1)

        self.assertEqual(payload["alerts"][0]["title"], "Email failures require attention")
        self.assertEqual(payload["alerts"][0]["severity"], "CRITICAL")
        self.assertEqual(payload["alerts"][0]["channel"], "EMAIL")

        self.assertEqual(payload["announcements"][0]["title"], "Parent meeting schedule")
        self.assertTrue(payload["announcements"][0]["is_pinned"])

        reminder_ids = {row["id"] for row in payload["reminders"]}
        self.assertIn("scheduled-campaigns", reminder_ids)
        self.assertIn("draft-campaigns", reminder_ids)
        self.assertIn("missing-templates", reminder_ids)

    def test_backfill_communication_backbone_command_rebuilds_historical_rows_idempotently(self):
        now = timezone.now()
        campaign = EmailCampaign.objects.create(
            title="Historical campaign",
            subject="Historical subject",
            body_text="Historical body",
            status="Sent",
            sent_at=now - timedelta(minutes=7),
            created_by=self.user,
        )
        recipient = EmailRecipient.objects.create(
            campaign=campaign,
            email="legacy-guardian@school.local",
            provider_id="email-historical-001",
            status="Opened",
            sent_at=now - timedelta(minutes=6),
            delivered_at=now - timedelta(minutes=5),
            opened_at=now - timedelta(minutes=4),
            open_count=1,
        )
        email_task = CommunicationDispatchTask.objects.create(
            channel="EMAIL",
            status="Sent",
            source_type="EmailRecipient",
            source_id=recipient.id,
            recipient=recipient.email,
            payload={"campaign_id": campaign.id},
            dedupe_key=f"email-recipient:{recipient.id}",
            attempts=1,
            processed_at=now - timedelta(minutes=6),
            provider_id=recipient.provider_id,
        )
        sms_row = SmsMessage.objects.create(
            recipient_phone="+1555010888",
            message="Historical SMS body",
            channel="SMS",
            status="Delivered",
            provider_id="sms-historical-001",
            sent_at=now - timedelta(minutes=3),
            delivered_at=now - timedelta(minutes=2),
            created_by=self.user,
        )
        sms_task = CommunicationDispatchTask.objects.create(
            channel="SMS",
            status="Sent",
            source_type="SmsMessage",
            source_id=sms_row.id,
            recipient=sms_row.recipient_phone,
            payload={"channel": "SMS"},
            dedupe_key=f"sms-message:{sms_row.id}",
            attempts=1,
            processed_at=now - timedelta(minutes=3),
            provider_id=sms_row.provider_id,
        )
        push_row = PushNotificationLog.objects.create(
            user=self.user2,
            title="Historical push title",
            body="Historical push body",
            status="Sent",
            provider_id="push-historical-001",
            sent_at=now - timedelta(minutes=1),
            created_by=self.user,
        )
        push_task = CommunicationDispatchTask.objects.create(
            channel="PUSH",
            status="Sent",
            source_type="PushNotificationLog",
            source_id=push_row.id,
            recipient=str(self.user2.id),
            payload={},
            dedupe_key=f"push-log:{push_row.id}",
            attempts=1,
            processed_at=now - timedelta(minutes=1),
            provider_id=push_row.provider_id,
        )
        direct_task = CommunicationDispatchTask.objects.create(
            channel="EMAIL",
            status="Failed",
            source_type="DirectEmail",
            recipient="ops@school.local",
            payload={
                "recipient": "ops@school.local",
                "subject": "Historical direct email",
                "body": "SMTP outage",
                "from_email": "noreply@school.local",
            },
            dedupe_key="historical-direct-email-task",
            attempts=3,
            max_attempts=3,
            processed_at=now,
            last_error="SMTP rejected request",
        )

        self.assertEqual(UnifiedMessage.objects.count(), 0)
        self.assertEqual(MessageDelivery.objects.count(), 0)
        self.assertEqual(CampaignStats.objects.count(), 0)
        self.assertEqual(GatewayStatus.objects.count(), 0)

        output = self._run_backfill_command()

        self.assertIn("campaigns=1", output)
        self.assertIn("email_recipients=1", output)
        self.assertIn("sms=1", output)
        self.assertIn("push=1", output)
        self.assertIn("direct_email_tasks=1", output)
        self.assertIn("task_links=4", output)

        campaign_message = UnifiedMessage.objects.get(source_type="EmailCampaign", source_id=campaign.id)
        email_delivery = MessageDelivery.objects.get(source_type="EmailRecipient", source_id=recipient.id)
        sms_delivery = MessageDelivery.objects.get(source_type="SmsMessage", source_id=sms_row.id)
        push_delivery = MessageDelivery.objects.get(source_type="PushNotificationLog", source_id=push_row.id)
        direct_message = UnifiedMessage.objects.get(source_type="DirectEmail", source_id=direct_task.id)
        direct_delivery = MessageDelivery.objects.get(source_type="DirectEmail", source_id=direct_task.id)
        stats = CampaignStats.objects.get(campaign=campaign)

        email_task.refresh_from_db()
        sms_task.refresh_from_db()
        push_task.refresh_from_db()
        direct_task.refresh_from_db()

        self.assertEqual(campaign_message.status, "Sent")
        self.assertEqual(email_delivery.unified_message_id, campaign_message.id)
        self.assertEqual(email_delivery.status, "Opened")
        self.assertEqual(email_delivery.provider_id, recipient.provider_id)
        self.assertEqual(email_task.delivery_id, email_delivery.id)
        self.assertEqual(stats.total_recipients, 1)
        self.assertEqual(stats.opened_recipients, 1)
        self.assertEqual(stats.successful_recipients, 1)

        self.assertEqual(sms_delivery.status, "Delivered")
        self.assertEqual(sms_delivery.provider_id, sms_row.provider_id)
        self.assertEqual(sms_task.delivery_id, sms_delivery.id)

        self.assertEqual(push_delivery.status, "Sent")
        self.assertEqual(push_delivery.provider_id, push_row.provider_id)
        self.assertEqual(push_task.delivery_id, push_delivery.id)

        self.assertEqual(direct_message.status, "Failed")
        self.assertEqual(direct_delivery.status, "Failed")
        self.assertIn("SMTP rejected", direct_delivery.failure_reason)
        self.assertEqual(direct_task.delivery_id, direct_delivery.id)

        self.assertEqual(GatewayStatus.objects.count(), 4)

        message_count = UnifiedMessage.objects.count()
        delivery_count = MessageDelivery.objects.count()
        stats_count = CampaignStats.objects.count()
        gateway_count = GatewayStatus.objects.count()

        rerun_output = self._run_backfill_command()

        self.assertIn("task_links=0", rerun_output)
        self.assertEqual(UnifiedMessage.objects.count(), message_count)
        self.assertEqual(MessageDelivery.objects.count(), delivery_count)
        self.assertEqual(CampaignStats.objects.count(), stats_count)
        self.assertEqual(GatewayStatus.objects.count(), gateway_count)

    def test_backfill_communication_backbone_command_all_tenants_processes_each_schema(self):
        second_tenant = self._create_additional_tenant("communication_test_backfill_two")
        current_sms = SmsMessage.objects.create(
            recipient_phone="+1555010991",
            message="Primary historical SMS",
            channel="SMS",
            status="Sent",
            provider_id="sms-primary-historical-001",
            sent_at=timezone.now() - timedelta(minutes=2),
            created_by=self.user,
        )

        with schema_context(second_tenant.schema_name):
            second_user, _ = User.objects.get_or_create(
                username="comm_admin_backfill_two",
                defaults={"email": "admin-backfill-two@school.local"},
            )
            second_sms = SmsMessage.objects.create(
                recipient_phone="+1555010992",
                message="Secondary historical SMS",
                channel="SMS",
                status="Delivered",
                provider_id="sms-secondary-historical-001",
                sent_at=timezone.now() - timedelta(minutes=2),
                delivered_at=timezone.now() - timedelta(minutes=1),
                created_by=second_user,
            )
            second_sms_id = second_sms.id

        stdout = StringIO()
        call_command("backfill_communication_backbone", all_tenants=True, stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("Running across 2 tenant schema(s).", output)
        self.assertIn(f"[{self.tenant.schema_name}] campaigns=0 email_recipients=0 sms=1", output)
        self.assertIn(f"[{second_tenant.schema_name}] campaigns=0 email_recipients=0 sms=1", output)
        self.assertTrue(UnifiedMessage.objects.filter(source_type="SmsMessage", source_id=current_sms.id).exists())

        with schema_context(second_tenant.schema_name):
            self.assertTrue(UnifiedMessage.objects.filter(source_type="SmsMessage", source_id=second_sms_id).exists())
            self.assertTrue(MessageDelivery.objects.filter(source_type="SmsMessage", source_id=second_sms_id).exists())

    def test_verify_communication_rollout_command_reports_contract_health(self):
        Notification.objects.create(
            recipient=self.user,
            notification_type="System",
            title="Verifier notice",
            message="Smoke verification notification",
            priority="Normal",
        )
        ensure_unified_message(
            message_key="verify-rollout-unified-001",
            kind="DIRECT",
            source_type="DirectEmailBatch",
            title="Verifier unified message",
            body="Verifier body preview",
            created_by=self.user,
            metadata={"channel": "EMAIL"},
        )

        output = self._run_rollout_verifier_command(schema_name=self.tenant.schema_name)

        self.assertIn(f"[{self.tenant.schema_name}] ok", output)
        self.assertIn("routes=6", output)
        self.assertIn("websocket_enabled=yes", output)
        self.assertIn("gateway_rows=4", output)

    def test_verify_communication_rollout_command_all_tenants_processes_each_schema(self):
        second_tenant = self._create_additional_tenant("communication_test_verify_two")

        output = self._run_rollout_verifier_command(all_tenants=True)

        self.assertIn("Running across 2 tenant schema(s).", output)
        self.assertIn(f"[{self.tenant.schema_name}] ok", output)
        self.assertIn(f"[{second_tenant.schema_name}] ok", output)

    def test_finalize_communication_deployment_dry_run_writes_report(self):
        report_rel_path = Path("artifacts/reports/communication_finalize_dry_run_test.md")
        report_abs_path = Path(settings.BASE_DIR).parent / report_rel_path
        if report_abs_path.exists():
            report_abs_path.unlink()

        output = self._run_deployment_finalizer_command(
            schema_name=self.tenant.schema_name,
            dry_run=True,
            report_path=str(report_rel_path),
        )

        self.assertIn("Communication deployment finalization complete.", output)
        self.assertTrue(report_abs_path.exists())
        report_text = report_abs_path.read_text(encoding="utf-8")
        self.assertIn("Dry run: `yes`", report_text)
        self.assertIn("Execution Plan", report_text)
        self.assertIn("`verify_communication_rollout`", report_text)

    @patch("communication.management.commands.finalize_communication_deployment.call_command")
    def test_finalize_communication_deployment_executes_expected_command_sequence(self, mock_call_command):
        report_rel_path = Path("artifacts/reports/communication_finalize_exec_test.md")
        report_abs_path = Path(settings.BASE_DIR).parent / report_rel_path
        if report_abs_path.exists():
            report_abs_path.unlink()

        output = self._run_deployment_finalizer_command(
            schema_name=self.tenant.schema_name,
            report_path=str(report_rel_path),
        )

        self.assertIn("Communication deployment finalization complete.", output)
        self.assertTrue(report_abs_path.exists())

        command_names = [call.args[0] for call in mock_call_command.call_args_list]
        self.assertEqual(
            command_names,
            [
                "migrate_schemas",
                "migrate_schemas",
                "backfill_communication_backbone",
                "dispatch_due_email_campaigns",
                "process_communication_dispatch_queue",
                "evaluate_communication_alert_rules",
                "verify_communication_rollout",
            ],
        )

        backfill_call = mock_call_command.call_args_list[2]
        self.assertEqual(backfill_call.kwargs["schema_name"], self.tenant.schema_name)
        self.assertNotIn("include_balance", backfill_call.kwargs)

        verifier_call = mock_call_command.call_args_list[-1]
        self.assertEqual(verifier_call.kwargs["schema_name"], self.tenant.schema_name)

    def test_delivery_history_normalizes_cross_channel_activity(self):
        now = timezone.now()
        campaign = EmailCampaign.objects.create(
            title="Delivery history campaign",
            subject="History subject",
            body_text="History body text for families",
            status="Sent",
            sent_at=now - timedelta(minutes=7),
            created_by=self.user,
        )
        email_row = EmailRecipient.objects.create(
            campaign=campaign,
            email="guardian@school.local",
            provider_id="email-provider-001",
            status="Opened",
            sent_at=now - timedelta(minutes=6),
            delivered_at=now - timedelta(minutes=5),
            opened_at=now - timedelta(minutes=4),
            open_count=2,
        )
        sms_row = SmsMessage.objects.create(
            recipient_phone="+1555010666",
            message="History SMS",
            channel="SMS",
            status="Delivered",
            provider_id="sms-provider-001",
            sent_at=now - timedelta(minutes=3),
            delivered_at=now - timedelta(minutes=2),
            created_by=self.user,
        )
        push_row = PushNotificationLog.objects.create(
            user=self.user2,
            title="History push",
            body="Push body text",
            status="Sent",
            provider_id="push-provider-001",
            sent_at=now - timedelta(minutes=1),
            created_by=self.user,
        )
        CommunicationDispatchTask.objects.create(
            channel="EMAIL",
            status="Failed",
            source_type="DirectEmail",
            recipient="ops@school.local",
            payload={"subject": "Ops alert", "body": "SMTP outage"},
            dedupe_key="history-direct-email-task",
            attempts=3,
            max_attempts=3,
            processed_at=now,
            last_error="SMTP rejected request",
        )

        history_request = self.factory.get("/api/communication/analytics/delivery-history/", {"limit": 4})
        force_authenticate(history_request, user=self.user)
        history_response = CommunicationAnalyticsDeliveryHistoryView.as_view()(history_request)

        self.assertEqual(history_response.status_code, 200)
        self.assertEqual(history_response.data["count"], 4)
        rows = history_response.data["results"]
        self.assertEqual(rows[0]["source_type"], "DirectEmail")
        lookup = {(row["channel"], row["source_type"]): row for row in rows}
        self.assertEqual(lookup[("EMAIL", "EmailRecipient")]["source_id"], email_row.id)
        self.assertEqual(lookup[("EMAIL", "EmailRecipient")]["campaign_id"], campaign.id)
        self.assertEqual(lookup[("SMS", "SmsMessage")]["source_id"], sms_row.id)
        self.assertEqual(lookup[("PUSH", "PushNotificationLog")]["source_id"], push_row.id)
        self.assertIn("SMTP rejected", lookup[("EMAIL", "DirectEmail")]["failure_reason"])

        email_only_request = self.factory.get("/api/communication/analytics/delivery-history/", {"channel": "email"})
        force_authenticate(email_only_request, user=self.user)
        email_only_response = CommunicationAnalyticsDeliveryHistoryView.as_view()(email_only_request)
        self.assertEqual(email_only_response.status_code, 200)
        self.assertTrue(email_only_response.data["count"] >= 2)
        self.assertTrue(all(row["channel"] == "EMAIL" for row in email_only_response.data["results"]))

    def test_campaign_performance_reports_first_class_metrics(self):
        campaign = EmailCampaign.objects.create(
            title="Performance campaign",
            subject="Performance subject",
            body_text="Performance body",
            status="Sent",
            sent_at=timezone.now() - timedelta(minutes=10),
            created_by=self.user,
        )
        EmailRecipient.objects.create(campaign=campaign, email="sent@school.local", status="Sent")
        EmailRecipient.objects.create(campaign=campaign, email="delivered@school.local", status="Delivered")
        EmailRecipient.objects.create(
            campaign=campaign,
            email="opened@school.local",
            status="Opened",
            open_count=2,
        )
        EmailRecipient.objects.create(
            campaign=campaign,
            email="clicked@school.local",
            status="Clicked",
            open_count=1,
            click_count=1,
        )
        EmailRecipient.objects.create(campaign=campaign, email="failed@school.local", status="Failed")

        performance_request = self.factory.get("/api/communication/analytics/campaign-performance/", {"limit": 5})
        force_authenticate(performance_request, user=self.user)
        performance_response = CommunicationAnalyticsCampaignPerformanceView.as_view()(performance_request)

        self.assertEqual(performance_response.status_code, 200)
        self.assertGreaterEqual(performance_response.data["count"], 1)
        row = performance_response.data["results"][0]
        self.assertEqual(row["campaign_id"], campaign.id)
        self.assertEqual(row["total_recipients"], 5)
        self.assertEqual(row["successful_recipients"], 4)
        self.assertEqual(row["delivered_recipients"], 3)
        self.assertEqual(row["opened_recipients"], 2)
        self.assertEqual(row["clicked_recipients"], 1)
        self.assertEqual(row["failed_recipients"], 1)
        self.assertEqual(row["open_events"], 3)
        self.assertEqual(row["click_events"], 1)
        self.assertEqual(row["delivery_rate"], 80.0)
        self.assertEqual(row["open_rate"], 40.0)
        self.assertEqual(row["click_rate"], 20.0)

    @override_settings(DEFAULT_FROM_EMAIL="noreply@test.local")
    @patch("communication.services.requests.get")
    def test_gateway_status_snapshot_persists_cross_channel_state(self, mock_get):
        profile = SchoolProfile.objects.create(
            school_name="Gateway Snapshot School",
            phone="+254700000001",
            sms_provider="africastalking",
            sms_username="sandbox",
            sms_sender_id="SCHOOL",
            whatsapp_phone_id="1234567890",
            is_active=True,
        )
        store_school_profile_secrets(
            profile,
            {"sms_api_key": "sms-secret-123", "whatsapp_api_key": "wa-secret-123"},
            updated_by=self.user,
        )
        TenantSettings.objects.create(
            key="integrations.push",
            value={"enabled": True},
            category="integrations",
        )
        set_tenant_secret(
            tenant_setting_secret_key("integrations.push", "server_key"),
            "push-secret-123",
            updated_by=self.user,
            description="integrations.push.server_key",
        )
        PushDevice.objects.create(user=self.user2, token="gateway-snapshot-token", platform="Web", is_active=True)

        now = timezone.now()
        EmailRecipient.objects.create(
            campaign=EmailCampaign.objects.create(
                title="Gateway snapshot campaign",
                subject="Gateway subject",
                body_text="Gateway body",
                status="Sent",
                sent_at=now - timedelta(minutes=9),
                created_by=self.user,
            ),
            email="family@school.local",
            status="Sent",
            provider_id="email-gateway-001",
            sent_at=now - timedelta(minutes=8),
        )
        SmsMessage.objects.create(
            recipient_phone="+1555010777",
            message="Delivered SMS",
            channel="SMS",
            status="Delivered",
            provider_id="sms-gateway-001",
            sent_at=now - timedelta(minutes=7),
            delivered_at=now - timedelta(minutes=6),
            created_by=self.user,
        )
        SmsMessage.objects.create(
            recipient_phone="+1555010888",
            message="Failed WhatsApp",
            channel="WhatsApp",
            status="Failed",
            failure_reason="Rejected by provider",
            created_by=self.user,
        )
        PushNotificationLog.objects.create(
            user=self.user2,
            title="Gateway push",
            body="Gateway push body",
            status="Sent",
            provider_id="push-gateway-001",
            sent_at=now - timedelta(minutes=5),
            created_by=self.user,
        )
        CommunicationDispatchTask.objects.create(
            channel="EMAIL",
            status="Queued",
            source_type="DirectEmail",
            recipient="ops@school.local",
            payload={"subject": "Ops alert", "body": "Email retry"},
            dedupe_key="gateway-status-email-queue",
        )
        CommunicationDispatchTask.objects.create(
            channel="PUSH",
            status="Failed",
            source_type="PushNotificationLog",
            recipient=str(self.user2.id),
            payload={},
            dedupe_key="gateway-status-push-failure",
            last_error="Push provider rejected request",
            processed_at=now,
        )

        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"UserData": {"balance": "KES 123.45"}}

        rows = sync_gateway_statuses(include_balance=True)

        self.assertEqual(set(rows.keys()), {"EMAIL", "SMS", "WHATSAPP", "PUSH"})
        self.assertEqual(GatewayStatus.objects.count(), 4)
        sms_status = GatewayStatus.objects.get(channel="SMS")
        self.assertEqual(sms_status.provider, "africastalking")
        self.assertTrue(sms_status.configured)
        self.assertEqual(sms_status.metadata["sender_id"], "SCHOOL")
        self.assertEqual(sms_status.balance_payload["balance"], "KES 123.45")
        self.assertEqual(sms_status.queue_queued_total, 0)
        self.assertIsNotNone(sms_status.last_success_at)

        whatsapp_status = GatewayStatus.objects.get(channel="WHATSAPP")
        self.assertTrue(whatsapp_status.configured)
        self.assertEqual(whatsapp_status.metadata["phone_id"], "1234567890")
        self.assertIsNotNone(whatsapp_status.last_failure_at)

        push_status = GatewayStatus.objects.get(channel="PUSH")
        self.assertTrue(push_status.configured)
        self.assertEqual(push_status.active_devices, 1)
        self.assertEqual(push_status.queue_failed, 1)
        self.assertIsNotNone(push_status.last_success_at)

    @override_settings(DEFAULT_FROM_EMAIL="noreply@test.local")
    @patch("communication.services.requests.get")
    def test_gateway_health_reports_cross_channel_configuration_and_queue_state(self, mock_get):
        profile = SchoolProfile.objects.create(
            school_name="Gateway School",
            phone="+254700000001",
            sms_provider="africastalking",
            sms_username="sandbox",
            sms_sender_id="SCHOOL",
            whatsapp_phone_id="1234567890",
            is_active=True,
        )
        store_school_profile_secrets(
            profile,
            {"sms_api_key": "sms-secret-123", "whatsapp_api_key": "wa-secret-123"},
            updated_by=self.user,
        )
        TenantSettings.objects.create(
            key="integrations.push",
            value={"enabled": True},
            category="integrations",
        )
        set_tenant_secret(
            tenant_setting_secret_key("integrations.push", "server_key"),
            "push-secret-123",
            updated_by=self.user,
            description="integrations.push.server_key",
        )
        PushDevice.objects.create(user=self.user2, token="gateway-push-token", platform="Web", is_active=True)

        now = timezone.now()
        campaign = EmailCampaign.objects.create(
            title="Gateway campaign",
            subject="Gateway subject",
            body_text="Gateway body",
            status="Sent",
            sent_at=now - timedelta(minutes=10),
            created_by=self.user,
        )
        EmailRecipient.objects.create(
            campaign=campaign,
            email="family@school.local",
            status="Sent",
            provider_id="email-gateway-001",
            sent_at=now - timedelta(minutes=9),
        )
        SmsMessage.objects.create(
            recipient_phone="+1555010777",
            message="Delivered SMS",
            channel="SMS",
            status="Delivered",
            provider_id="sms-gateway-001",
            sent_at=now - timedelta(minutes=8),
            delivered_at=now - timedelta(minutes=7),
            created_by=self.user,
        )
        SmsMessage.objects.create(
            recipient_phone="+1555010888",
            message="Failed SMS",
            channel="SMS",
            status="Failed",
            failure_reason="Rejected by provider",
            created_by=self.user,
        )
        SmsMessage.objects.create(
            recipient_phone="+1555010999",
            message="WhatsApp delivered",
            channel="WhatsApp",
            status="Sent",
            provider_id="wa-gateway-001",
            sent_at=now - timedelta(minutes=6),
            created_by=self.user,
        )
        PushNotificationLog.objects.create(
            user=self.user2,
            title="Gateway push",
            body="Gateway push body",
            status="Sent",
            provider_id="push-gateway-001",
            sent_at=now - timedelta(minutes=5),
            created_by=self.user,
        )
        CommunicationDispatchTask.objects.create(
            channel="EMAIL",
            status="Queued",
            source_type="DirectEmail",
            recipient="ops@school.local",
            payload={"subject": "Ops alert", "body": "Email retry"},
            dedupe_key="gateway-email-queue",
        )
        CommunicationDispatchTask.objects.create(
            channel="SMS",
            status="Queued",
            source_type="SmsMessage",
            recipient="+1555010666",
            payload={"channel": "SMS"},
            dedupe_key="gateway-sms-queue",
        )
        CommunicationDispatchTask.objects.create(
            channel="PUSH",
            status="Failed",
            source_type="PushNotificationLog",
            recipient=str(self.user2.id),
            payload={},
            dedupe_key="gateway-push-failure",
            last_error="Push provider rejected request",
            processed_at=now,
        )

        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"UserData": {"balance": "KES 123.45"}}

        gateway_request = self.factory.get("/api/communication/analytics/gateway-health/")
        force_authenticate(gateway_request, user=self.user)
        gateway_response = CommunicationAnalyticsGatewayHealthView.as_view()(gateway_request)

        self.assertEqual(gateway_response.status_code, 200)
        payload = gateway_response.data
        self.assertEqual(payload["email"]["provider"], "django_email")
        self.assertTrue(payload["email"]["configured"])
        self.assertEqual(payload["email"]["queue"]["queued_total"], 1)
        self.assertTrue(payload["email"]["last_success_at"])
        self.assertTrue(payload["email"]["recent_failures"])
        self.assertEqual(payload["sms"]["provider"], "africastalking")
        self.assertTrue(payload["sms"]["configured"])
        self.assertEqual(payload["sms"]["sender_id"], "SCHOOL")
        self.assertEqual(payload["sms"]["balance"]["balance"], "KES 123.45")
        self.assertEqual(payload["sms"]["queue"]["queued_total"], 1)
        self.assertTrue(payload["sms"]["last_success_at"])
        self.assertTrue(payload["sms"]["last_failure_at"])
        self.assertTrue(payload["sms"]["recent_successes"])
        self.assertTrue(payload["sms"]["recent_failures"])
        self.assertTrue(payload["whatsapp"]["configured"])
        self.assertEqual(payload["whatsapp"]["phone_id"], "1234567890")
        self.assertTrue(payload["whatsapp"]["last_success_at"])
        self.assertTrue(payload["whatsapp"]["recent_successes"])
        self.assertTrue(payload["push"]["configured"])
        self.assertEqual(payload["push"]["active_devices"], 1)
        self.assertEqual(payload["push"]["queue"]["failed"], 1)
        self.assertTrue(payload["push"]["last_success_at"])
        self.assertTrue(payload["push"]["recent_failures"])

        summary_request = self.factory.get("/api/communication/analytics/summary/")
        force_authenticate(summary_request, user=self.user)
        summary_response = CommunicationAnalyticsSummaryView.as_view()(summary_request)
        self.assertEqual(summary_response.status_code, 200)
        self.assertIn("gateway_health", summary_response.data)
        self.assertEqual(summary_response.data["gateway_health"]["sms"]["provider"], "africastalking")
        self.assertEqual(GatewayStatus.objects.count(), 4)
        self.assertTrue(GatewayStatus.objects.filter(channel="EMAIL").exists())

    @override_settings(DEFAULT_FROM_EMAIL="noreply@test.local")
    def test_gateway_settings_view_returns_secret_backed_channel_configuration(self):
        profile = SchoolProfile.objects.create(
            school_name="Gateway Settings School",
            phone="+254700000001",
            email_address="office@school.local",
            smtp_host="smtp.gateway.local",
            smtp_port=465,
            smtp_user="mailer@school.local",
            smtp_use_tls=True,
            sms_provider="africastalking",
            sms_username="sandbox",
            sms_sender_id="SCHOOL",
            whatsapp_phone_id="1234567890",
            is_active=True,
        )
        store_school_profile_secrets(
            profile,
            {
                "smtp_password": "smtp-secret-123",
                "sms_api_key": "sms-secret-123",
                "whatsapp_api_key": "wa-secret-123",
            },
            updated_by=self.user,
        )
        TenantSettings.objects.create(
            key="integrations.push",
            value={"enabled": True, "project_id": "school-fcm"},
            category="integrations",
        )
        set_tenant_secret(
            tenant_setting_secret_key("integrations.push", "server_key"),
            "push-secret-123",
            updated_by=self.user,
            description="integrations.push.server_key",
        )

        request = self.factory.get("/api/communication/settings/gateways/")
        force_authenticate(request, user=self.user)
        response = CommunicationGatewaySettingsView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        payload = response.data
        self.assertEqual(payload["profile"]["school_name"], "Gateway Settings School")
        self.assertEqual(payload["email"]["settings"]["smtp_host"], "smtp.gateway.local")
        self.assertEqual(payload["email"]["settings"]["smtp_port"], 465)
        self.assertEqual(payload["email"]["settings"]["test_recipient"], "mailer@school.local")
        self.assertTrue(payload["email"]["settings"]["smtp_password"]["configured"])
        self.assertNotEqual(payload["email"]["settings"]["smtp_password"]["preview"], "smtp-secret-123")
        self.assertTrue(payload["email"]["settings_configured"])
        self.assertEqual(payload["sms"]["settings"]["provider"], "africastalking")
        self.assertEqual(payload["sms"]["settings"]["username"], "sandbox")
        self.assertTrue(payload["sms"]["settings"]["api_key"]["configured"])
        self.assertTrue(payload["sms"]["settings_configured"])
        self.assertEqual(payload["whatsapp"]["settings"]["phone_id"], "1234567890")
        self.assertTrue(payload["whatsapp"]["settings"]["api_key"]["configured"])
        self.assertTrue(payload["whatsapp"]["settings_configured"])
        self.assertEqual(payload["push"]["settings"]["setting_key"], "integrations.push")
        self.assertEqual(payload["push"]["settings"]["project_id"], "school-fcm")
        self.assertTrue(payload["push"]["settings"]["server_key"]["configured"])
        self.assertTrue(payload["push"]["settings_configured"])

    @override_settings(DEFAULT_FROM_EMAIL="noreply@test.local")
    def test_gateway_settings_view_persists_school_profile_and_push_updates(self):
        request = self.factory.patch(
            "/api/communication/settings/gateways/",
            {
                "profile": {
                    "school_name": "Gateway Control School",
                    "phone": "+254700000999",
                    "email_address": "ops@school.local",
                },
                "email": {
                    "smtp_host": "smtp.gateway.local",
                    "smtp_port": 465,
                    "smtp_user": "mailer@school.local",
                    "smtp_password": "smtp-secret-123",
                    "smtp_use_tls": True,
                },
                "sms": {
                    "provider": "africastalking",
                    "username": "sandbox",
                    "sender_id": "SCHOOL",
                    "api_key": "sms-secret-123",
                },
                "whatsapp": {
                    "phone_id": "1234567890",
                    "api_key": "wa-secret-123",
                },
                "push": {
                    "enabled": True,
                    "project_id": "school-fcm",
                    "sender_id": "project-sender",
                    "server_key": "push-secret-123",
                },
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = CommunicationGatewaySettingsView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        profile = SchoolProfile.objects.get(is_active=True)
        self.assertEqual(profile.school_name, "Gateway Control School")
        self.assertEqual(profile.phone, "+254700000999")
        self.assertEqual(profile.email_address, "ops@school.local")
        self.assertEqual(profile.smtp_host, "smtp.gateway.local")
        self.assertEqual(profile.smtp_port, 465)
        self.assertEqual(profile.smtp_user, "mailer@school.local")
        self.assertEqual(profile.sms_provider, "africastalking")
        self.assertEqual(profile.sms_username, "sandbox")
        self.assertEqual(profile.sms_sender_id, "SCHOOL")
        self.assertEqual(profile.whatsapp_phone_id, "1234567890")
        self.assertEqual(resolve_school_profile_secret(profile, "smtp_password"), "smtp-secret-123")
        self.assertEqual(resolve_school_profile_secret(profile, "sms_api_key"), "sms-secret-123")
        self.assertEqual(resolve_school_profile_secret(profile, "whatsapp_api_key"), "wa-secret-123")

        push_row = TenantSettings.objects.get(key="integrations.push")
        self.assertEqual(push_row.category, "integrations")
        self.assertEqual(push_row.value["enabled"], True)
        self.assertEqual(push_row.value["project_id"], "school-fcm")
        self.assertEqual(push_row.value["sender_id"], "project-sender")
        self.assertEqual(push_row.value["provider"], "fcm")
        self.assertNotIn("server_key", push_row.value)
        self.assertEqual(
            get_tenant_secret(tenant_setting_secret_key("integrations.push", "server_key")),
            "push-secret-123",
        )
        self.assertTrue(response.data["email"]["settings"]["smtp_password"]["configured"])
        self.assertTrue(response.data["push"]["settings"]["server_key"]["configured"])
        self.assertTrue(response.data["sms"]["configured"])
        self.assertTrue(response.data["push"]["configured"])

    @override_settings(DEFAULT_FROM_EMAIL="noreply@test.local")
    @patch("communication.services.requests.post")
    def test_gateway_test_view_runs_email_and_sms_checks(self, mock_post):
        profile = SchoolProfile.objects.create(
            school_name="Gateway Test School",
            phone="+254700000001",
            email_address="office@school.local",
            smtp_host="smtp.gateway.local",
            smtp_user="mailer@school.local",
            sms_provider="africastalking",
            sms_username="sandbox",
            sms_sender_id="SCHOOL",
            is_active=True,
        )
        store_school_profile_secrets(profile, {"sms_api_key": "sms-secret-123"}, updated_by=self.user)
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {
            "SMSMessageData": {
                "Recipients": [
                    {
                        "status": "Success",
                        "messageId": "ATPid-test-001",
                        "cost": "KES 0.8000",
                    }
                ]
            }
        }

        mail.outbox = []
        gateway_email_request = self.factory.post(
            "/api/communication/settings/gateways/test/",
            {"channel": "EMAIL"},
            format="json",
        )
        force_authenticate(gateway_email_request, user=self.user)
        gateway_email_response = CommunicationGatewayTestView.as_view()(gateway_email_request)
        self.assertEqual(gateway_email_response.status_code, 200)
        self.assertEqual(gateway_email_response.data["channel"], "EMAIL")
        self.assertEqual(gateway_email_response.data["message"], "Test email sent to mailer@school.local.")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["mailer@school.local"])

        gateway_sms_request = self.factory.post(
            "/api/communication/settings/gateways/test/",
            {"channel": "SMS"},
            format="json",
        )
        force_authenticate(gateway_sms_request, user=self.user)
        gateway_sms_response = CommunicationGatewayTestView.as_view()(gateway_sms_request)
        self.assertEqual(gateway_sms_response.status_code, 200)
        self.assertEqual(gateway_sms_response.data["channel"], "SMS")
        self.assertEqual(gateway_sms_response.data["provider_id"], "ATPid-test-001")

    @patch("communication.services.requests.post")
    def test_gateway_test_view_runs_whatsapp_and_push_checks(self, mock_post):
        profile = SchoolProfile.objects.create(
            school_name="Gateway Test School",
            phone="+254700000001",
            whatsapp_phone_id="1234567890",
            is_active=True,
        )
        store_school_profile_secrets(profile, {"whatsapp_api_key": "wa-secret-123"}, updated_by=self.user)
        TenantSettings.objects.create(
            key="integrations.push",
            value={"enabled": True},
            category="integrations",
        )
        set_tenant_secret(
            tenant_setting_secret_key("integrations.push", "server_key"),
            "push-secret-123",
            updated_by=self.user,
            description="integrations.push.server_key",
        )
        PushDevice.objects.create(user=self.user, token="push-test-token", platform="Web", is_active=True)
        mock_post.side_effect = [
            Mock(status_code=200, json=Mock(return_value={"messages": [{"id": "wamid.test.001"}]})),
            Mock(
                status_code=200,
                json=Mock(return_value={"success": 1, "failure": 0, "results": [{"message_id": "fcm-msg-001"}]}),
            ),
        ]

        whatsapp_request = self.factory.post(
            "/api/communication/settings/gateways/test/",
            {"channel": "WHATSAPP"},
            format="json",
        )
        force_authenticate(whatsapp_request, user=self.user)
        whatsapp_response = CommunicationGatewayTestView.as_view()(whatsapp_request)
        self.assertEqual(whatsapp_response.status_code, 200)
        self.assertEqual(whatsapp_response.data["channel"], "WHATSAPP")
        self.assertEqual(whatsapp_response.data["provider_id"], "wamid.test.001")

        push_request = self.factory.post(
            "/api/communication/settings/gateways/test/",
            {"channel": "PUSH"},
            format="json",
        )
        force_authenticate(push_request, user=self.user)
        push_response = CommunicationGatewayTestView.as_view()(push_request)
        self.assertEqual(push_response.status_code, 200)
        self.assertEqual(push_response.data["channel"], "PUSH")
        self.assertEqual(push_response.data["provider_id"], "fcm-msg-001")

    def test_engagement_analytics_reports_actual_reply_lag(self):
        conversation = Conversation.objects.create(
            conversation_type="Direct",
            title="Reply timing",
            created_by=self.user,
        )
        conversation.participants.create(user=self.user, role="Admin", is_active=True)
        conversation.participants.create(user=self.user2, role="Member", is_active=True)

        base_message = CommunicationMessage.objects.create(
            conversation=conversation,
            sender=self.user,
            content="Original message",
            delivery_status="Delivered",
        )
        CommunicationMessage.objects.filter(pk=base_message.pk).update(sent_at=timezone.now() - timedelta(minutes=12))
        base_message.refresh_from_db()
        CommunicationMessage.objects.create(
            conversation=conversation,
            sender=self.user2,
            content="Reply message",
            reply_to=base_message,
            delivery_status="Sent",
        )

        analytics_request = self.factory.get("/api/communication/analytics/engagement/")
        force_authenticate(analytics_request, user=self.user)
        analytics_response = CommunicationAnalyticsEngagementView.as_view()(analytics_request)
        self.assertEqual(analytics_response.status_code, 200)
        self.assertGreater(analytics_response.data["average_response_time_minutes"], 0)
        self.assertEqual(
            analytics_response.data["average_response_time_label"],
            "Actual average reply lag between a message and its reply.",
        )

    @patch("communication.services.requests.post")
    def test_sms_send_uses_tenant_secret_backed_provider_dispatch(self, mock_post):
        self._configure_sms_transport(mock_post, provider_id="ATPid-live-001")

        send_sms = self.factory.post(
            "/api/communication/sms/send/",
            {"phones": ["+1555010999"], "message": "Live transport", "channel": "SMS"},
            format="json",
        )
        force_authenticate(send_sms, user=self.user)
        response = SmsSendView.as_view()(send_sms)

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data[0]["status"], "Queued")
        self.assertEqual(mock_post.call_count, 0)
        worker_output = self._run_dispatch_queue_worker()
        row = SmsMessage.objects.get(id=response.data[0]["id"])
        self.assertEqual(row.status, "Sent")
        self.assertEqual(row.provider_id, "ATPid-live-001")
        self._run_dispatch_queue_worker()
        self.assertEqual(mock_post.call_count, 1)
        self.assertIn("processed=1", worker_output)

    @patch("communication.services.requests.post")
    def test_whatsapp_send_uses_tenant_secret_backed_provider_dispatch(self, mock_post):
        profile = SchoolProfile.objects.create(
            school_name="Communication School",
            phone="+254700000001",
            whatsapp_phone_id="1234567890",
            is_active=True,
        )
        store_school_profile_secrets(profile, {"whatsapp_api_key": "wa-secret-123"}, updated_by=self.user)
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"messages": [{"id": "wamid.HBgLMDEyMzQ1"}]}

        send_sms = self.factory.post(
            "/api/communication/sms/send/",
            {"phones": ["+1555010888"], "message": "WhatsApp hello", "channel": "WhatsApp"},
            format="json",
        )
        force_authenticate(send_sms, user=self.user)
        response = SmsSendView.as_view()(send_sms)

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data[0]["status"], "Queued")
        self._run_dispatch_queue_worker()
        row = SmsMessage.objects.get(id=response.data[0]["id"])
        self.assertEqual(row.status, "Sent")
        self.assertEqual(row.provider_id, "wamid.HBgLMDEyMzQ1")

    @patch("communication.services.requests.post")
    def test_push_send_uses_tenant_setting_secret_store(self, mock_post):
        TenantSettings.objects.create(
            key="integrations.push",
            value={"enabled": True},
            category="integrations",
        )
        set_tenant_secret(
            tenant_setting_secret_key("integrations.push", "server_key"),
            "push-secret-123",
            updated_by=self.user,
            description="integrations.push.server_key",
        )
        register_device = self.factory.post(
            "/api/communication/push/devices/",
            {"token": "token-push-123", "platform": "Web"},
            format="json",
        )
        force_authenticate(register_device, user=self.user2)
        register_response = PushDeviceViewSet.as_view({"post": "create"})(register_device)
        self.assertEqual(register_response.status_code, 201)

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "success": 1,
            "failure": 0,
            "results": [{"message_id": "fcm-msg-001"}],
        }

        push_send = self.factory.post(
            "/api/communication/push/send/",
            {"users": [self.user2.id], "title": "Push", "body": "Hello"},
            format="json",
        )
        force_authenticate(push_send, user=self.user)
        response = PushSendView.as_view()(push_send)

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data[0]["status"], "Queued")
        self._run_dispatch_queue_worker()
        row = PushNotificationLog.objects.get(id=response.data[0]["id"])
        self.assertEqual(row.status, "Sent")
        self.assertEqual(row.provider_id, "fcm-msg-001")

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
        self.assertEqual(send_campaign_response.status_code, 202)

        send_sms = self.factory.post(
            "/api/communication/sms/send/",
            {"phones": ["+1555010001"], "message": "Hello parents", "channel": "SMS"},
            format="json",
        )
        force_authenticate(send_sms, user=self.user)
        sms_response = SmsSendView.as_view()(send_sms)
        self.assertEqual(sms_response.status_code, 202)

        analytics = self.factory.get("/api/communication/analytics/summary/")
        force_authenticate(analytics, user=self.user)
        analytics_response = CommunicationAnalyticsSummaryView.as_view()(analytics)
        self.assertEqual(analytics_response.status_code, 200)
        self.assertGreaterEqual(analytics_response.data["total_messages"], 1)
        self.assertGreaterEqual(analytics_response.data["total_unified_messages"], 1)
        self.assertGreaterEqual(analytics_response.data["total_message_deliveries"], 2)
        self.assertGreaterEqual(analytics_response.data["dispatch_queue"]["ready"], 2)

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

        with patch("communication.services.requests.post") as mock_post:
            self._configure_sms_transport(mock_post, provider_id="ATPid-webhook-001")
            send_sms = self.factory.post(
                "/api/communication/sms/send/",
                {"phones": ["+1555010002"], "message": "Webhook test", "channel": "SMS"},
                format="json",
            )
            force_authenticate(send_sms, user=self.user)
            sms_response = SmsSendView.as_view()(send_sms)
            self.assertEqual(sms_response.status_code, 202)
            self._run_dispatch_queue_worker()
            row = SmsMessage.objects.get(id=sms_response.data[0]["id"])
            self.assertEqual(row.status, "Sent")
            provider_id = row.provider_id
            self.assertTrue(provider_id)

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
        self.assertEqual(push_response.status_code, 202)

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
        with patch("communication.services.requests.post") as mock_post:
            self._configure_sms_transport(mock_post, provider_id="ATPid-signature-001")
            send_sms = self.factory.post(
                "/api/communication/sms/send/",
                {"phones": ["+1555010003"], "message": "Signature test", "channel": "SMS"},
                format="json",
            )
            force_authenticate(send_sms, user=self.user)
            sms_response = SmsSendView.as_view()(send_sms)
            self.assertEqual(sms_response.status_code, 202)
            self._run_dispatch_queue_worker()
            row = SmsMessage.objects.get(id=sms_response.data[0]["id"])
            self.assertEqual(row.status, "Sent")
            provider_id = row.provider_id
            self.assertTrue(provider_id)

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
        self.assertEqual(send_response.status_code, 202)
        self._run_dispatch_queue_worker()

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
        with patch("communication.services.requests.post") as mock_post:
            self._configure_sms_transport(mock_post, provider_id="ATPid-nonstrict-001")
            send_sms = self.factory.post(
                "/api/communication/sms/send/",
                {"phones": ["+1555010004"], "message": "Non-strict webhook test", "channel": "SMS"},
                format="json",
            )
            force_authenticate(send_sms, user=self.user)
            sms_response = SmsSendView.as_view()(send_sms)
            self.assertEqual(sms_response.status_code, 202)
            self._run_dispatch_queue_worker()
            row = SmsMessage.objects.get(id=sms_response.data[0]["id"])
            self.assertEqual(row.status, "Sent")
            provider_id = row.provider_id
            self.assertTrue(provider_id)

        sms_webhook = self.factory.post(
            "/api/communication/webhooks/sms/",
            {"provider_id": provider_id, "status": "Delivered"},
            format="json",
        )
        webhook_response = SmsWebhookView.as_view()(sms_webhook)
        self.assertEqual(webhook_response.status_code, 200)

    def test_summary_websocket_replays_notification_events_from_request_path(self):
        create_notification = self.factory.post(
            "/api/communication/notifications/",
            {
                "title": "Realtime notification",
                "message": "Websocket replay should deliver this notification.",
                "notification_type": "System",
                "priority": "Important",
            },
            format="json",
        )
        force_authenticate(create_notification, user=self.user)
        response = NotificationViewSet.as_view({"post": "create"})(create_notification)
        self.assertEqual(response.status_code, 201)

        event = CommunicationRealtimeEvent.objects.filter(stream="summary").order_by("-id").first()
        self.assertIsNotNone(event)

        async def scenario():
            communicator = ApplicationCommunicator(
                asgi_application,
                self._websocket_scope("/ws/communication/summary/", self._make_access_token(self.user), last_event_id=event.id - 1),
            )
            await communicator.send_input({"type": "websocket.connect"})
            accept = await communicator.receive_output(timeout=2)
            self.assertEqual(accept["type"], "websocket.accept")
            replay = await communicator.receive_output(timeout=2)
            self.assertEqual(replay["type"], "websocket.send")
            payload = json.loads(replay["text"])
            self.assertEqual(payload["type"], "notification.created")
            self.assertEqual(payload["event_id"], event.id)
            self.assertEqual(payload["payload"]["title"], "Realtime notification")
            await communicator.send_input({"type": "websocket.disconnect", "code": 1000})
            await communicator.wait()

        async_to_sync(scenario)()

    def test_conversation_websocket_replays_messages_and_tracks_typing_presence(self):
        conversation = Conversation.objects.create(
            conversation_type="Direct",
            title="Realtime conversation",
            created_by=self.user,
        )
        conversation.participants.create(user=self.user, role="Admin", is_active=True)
        conversation.participants.create(user=self.user2, role="Member", is_active=True)

        create_message = self.factory.post(
            "/api/communication/messages/",
            {"conversation": conversation.id, "content": "Realtime hello"},
            format="json",
        )
        force_authenticate(create_message, user=self.user)
        response = CommunicationMessageViewSet.as_view({"post": "create"})(create_message)
        self.assertEqual(response.status_code, 201)

        message_event = CommunicationRealtimeEvent.objects.filter(
            stream=f"conversation:{conversation.id}",
            event_type="message.created",
        ).order_by("-id").first()
        self.assertIsNotNone(message_event)

        async def scenario():
            communicator = ApplicationCommunicator(
                asgi_application,
                self._websocket_scope(
                    f"/ws/communication/conversations/{conversation.id}/",
                    self._make_access_token(self.user2),
                    last_event_id=message_event.id - 1,
                ),
            )
            await communicator.send_input({"type": "websocket.connect"})
            accept = await communicator.receive_output(timeout=2)
            self.assertEqual(accept["type"], "websocket.accept")

            replay = await communicator.receive_output(timeout=2)
            replay_payload = json.loads(replay["text"])
            self.assertEqual(replay_payload["type"], "message.created")
            self.assertEqual(replay_payload["payload"]["conversation_id"], conversation.id)

            await communicator.send_input(
                {
                    "type": "websocket.receive",
                    "text": json.dumps({"action": "typing", "is_typing": True}),
                }
            )
            typing_payload = None
            for _ in range(3):
                typing_output = await communicator.receive_output(timeout=2)
                candidate = json.loads(typing_output["text"])
                if candidate.get("type") == "typing.updated":
                    typing_payload = candidate
                    break
            self.assertIsNotNone(typing_payload)
            self.assertEqual(typing_payload["type"], "typing.updated")
            self.assertTrue(typing_payload["payload"]["is_typing"])
            await communicator.send_input({"type": "websocket.disconnect", "code": 1000})
            await communicator.wait()

        async_to_sync(scenario)()
        self.assertEqual(CommunicationRealtimePresence.objects.filter(conversation=conversation).count(), 0)
