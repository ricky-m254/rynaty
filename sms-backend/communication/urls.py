from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    AnnouncementViewSet,
    CommunicationAnalyticsByChannelView,
    CommunicationAnalyticsDeliveryRateView,
    CommunicationAnalyticsEngagementView,
    CommunicationAnalyticsSummaryView,
    CommunicationMessageViewSet,
    ConversationViewSet,
    EmailCampaignViewSet,
    LegacyMessageViewSet,
    MessageTemplateViewSet,
    NotificationPreferenceView,
    NotificationViewSet,
    ParentAttendanceAlertView,
    ParentFeeReminderView,
    ParentMeetingInviteView,
    ParentReportCardNotifyView,
    PushDeviceViewSet,
    PushLogView,
    PushSendView,
    SmsBalanceView,
    SmsGatewayView,
    SmsSendView,
    SmsStatusView,
    EmailWebhookView,
    SmsWebhookView,
)

router = SimpleRouter()
router.register(r"conversations", ConversationViewSet, basename="communication_conversations")
router.register(r"legacy-messages", LegacyMessageViewSet, basename="communication_legacy_messages")
router.register(r"messages", CommunicationMessageViewSet, basename="communication_messages")
router.register(r"notifications", NotificationViewSet, basename="communication_notifications")
router.register(r"email-campaigns", EmailCampaignViewSet, basename="communication_email_campaigns")
router.register(r"templates", MessageTemplateViewSet, basename="communication_templates")
router.register(r"announcements", AnnouncementViewSet, basename="communication_announcements")
router.register(r"push/devices", PushDeviceViewSet, basename="communication_push_devices")

urlpatterns = [
    path("notification-preferences/", NotificationPreferenceView.as_view(), name="communication_notification_preferences"),
    path("sms/", SmsGatewayView.as_view(), name="communication_sms_list"),
    path("sms/send/", SmsSendView.as_view(), name="communication_sms_send"),
    path("sms/<int:pk>/status/", SmsStatusView.as_view(), name="communication_sms_status"),
    path("sms/balance/", SmsBalanceView.as_view(), name="communication_sms_balance"),
    path("push/send/", PushSendView.as_view(), name="communication_push_send"),
    path("push/", PushLogView.as_view(), name="communication_push_logs"),
    path("analytics/summary/", CommunicationAnalyticsSummaryView.as_view(), name="communication_analytics_summary"),
    path("analytics/by-channel/", CommunicationAnalyticsByChannelView.as_view(), name="communication_analytics_by_channel"),
    path("analytics/delivery-rate/", CommunicationAnalyticsDeliveryRateView.as_view(), name="communication_analytics_delivery_rate"),
    path("analytics/engagement/", CommunicationAnalyticsEngagementView.as_view(), name="communication_analytics_engagement"),
    path("parent/report-card-notify/", ParentReportCardNotifyView.as_view(), name="communication_parent_report_card_notify"),
    path("parent/fee-reminder/", ParentFeeReminderView.as_view(), name="communication_parent_fee_reminder"),
    path("parent/attendance-alert/", ParentAttendanceAlertView.as_view(), name="communication_parent_attendance_alert"),
    path("parent/meeting-invite/", ParentMeetingInviteView.as_view(), name="communication_parent_meeting_invite"),
    path("webhooks/email/", EmailWebhookView.as_view(), name="communication_webhooks_email"),
    path("webhooks/sms/", SmsWebhookView.as_view(), name="communication_webhooks_sms"),
    path("", include(router.urls)),
]
