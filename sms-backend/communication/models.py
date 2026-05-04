from django.conf import settings
from django.db import models
from django.utils import timezone


class Conversation(models.Model):
    TYPE_CHOICES = [
        ("Direct", "Direct"),
        ("Group", "Group"),
        ("Broadcast", "Broadcast"),
        ("Class", "Class"),
        ("Department", "Department"),
    ]

    conversation_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="Direct")
    title = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_conversations")
    created_at = models.DateTimeField(auto_now_add=True)
    is_archived = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class ConversationParticipant(models.Model):
    ROLE_CHOICES = [("Admin", "Admin"), ("Member", "Member"), ("Observer", "Observer")]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversation_participations")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="Member")
    joined_at = models.DateTimeField(auto_now_add=True)
    last_read_at = models.DateTimeField(null=True, blank=True)
    is_muted = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("conversation", "user")
        ordering = ["-joined_at", "-id"]


class CommunicationMessage(models.Model):
    TYPE_CHOICES = [("Text", "Text"), ("File", "File"), ("Image", "Image"), ("System", "System")]
    DELIVERY_CHOICES = [("Sent", "Sent"), ("Delivered", "Delivered"), ("Read", "Read"), ("Failed", "Failed")]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="sent_messages")
    content = models.TextField(blank=True)
    message_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="Text")
    reply_to = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="replies")
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    sent_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    delivery_status = models.CharField(max_length=20, choices=DELIVERY_CHOICES, default="Sent")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-sent_at", "-id"]


class MessageAttachment(models.Model):
    message = models.ForeignKey(CommunicationMessage, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="communication/messages/")
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(default=0)
    mime_type = models.CharField(max_length=100, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-uploaded_at", "-id"]


class MessageReadReceipt(models.Model):
    message = models.ForeignKey(CommunicationMessage, on_delete=models.CASCADE, related_name="read_receipts")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="message_read_receipts")
    read_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("message", "user")
        ordering = ["-read_at", "-id"]


class Notification(models.Model):
    TYPE_CHOICES = [
        ("System", "System"),
        ("Financial", "Financial"),
        ("Academic", "Academic"),
        ("Behavioral", "Behavioral"),
        ("HR", "HR"),
        ("Event", "Event"),
        ("Emergency", "Emergency"),
    ]
    PRIORITY_CHOICES = [("Urgent", "Urgent"), ("Important", "Important"), ("Informational", "Informational")]
    DELIVERY_CHOICES = [("Queued", "Queued"), ("Sent", "Sent"), ("Delivered", "Delivered"), ("Failed", "Failed")]

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="System")
    title = models.CharField(max_length=255)
    message = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="Informational")
    action_url = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications_created")
    delivery_status = models.CharField(max_length=20, choices=DELIVERY_CHOICES, default="Sent")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-sent_at", "-id"]


class NotificationPreference(models.Model):
    TYPE_CHOICES = Notification.TYPE_CHOICES

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_preferences")
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="System")
    channel_in_app = models.BooleanField(default=True)
    channel_email = models.BooleanField(default=True)
    channel_sms = models.BooleanField(default=False)
    channel_push = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "notification_type")
        ordering = ["notification_type", "id"]


class EmailCampaign(models.Model):
    STATUS_CHOICES = [("Draft", "Draft"), ("Scheduled", "Scheduled"), ("Sending", "Sending"), ("Sent", "Sent"), ("Failed", "Failed")]

    title = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)
    body_html = models.TextField(blank=True)
    body_text = models.TextField(blank=True)
    sender_name = models.CharField(max_length=120, blank=True)
    sender_email = models.EmailField(blank=True)
    reply_to = models.EmailField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Draft")
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="email_campaigns")
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class UnifiedMessage(models.Model):
    KIND_CHOICES = [
        ("DIRECT", "Direct"),
        ("CAMPAIGN", "Campaign"),
        ("PARENT_NOTICE", "Parent Notice"),
        ("SYSTEM", "System"),
    ]
    STATUS_CHOICES = [
        ("Draft", "Draft"),
        ("Queued", "Queued"),
        ("Sending", "Sending"),
        ("Sent", "Sent"),
        ("Partial", "Partial"),
        ("Failed", "Failed"),
    ]

    message_key = models.CharField(max_length=160, unique=True)
    kind = models.CharField(max_length=30, choices=KIND_CHOICES, default="DIRECT")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Queued", db_index=True)
    source_type = models.CharField(max_length=40, blank=True)
    source_id = models.PositiveIntegerField(null=True, blank=True)
    campaign = models.ForeignKey(EmailCampaign, on_delete=models.SET_NULL, null=True, blank=True, related_name="unified_messages")
    title = models.CharField(max_length=255, blank=True)
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="unified_messages")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class CampaignStats(models.Model):
    campaign = models.OneToOneField(EmailCampaign, on_delete=models.CASCADE, related_name="stats_snapshot")
    unified_message = models.OneToOneField(
        UnifiedMessage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaign_stats_snapshot",
    )
    total_recipients = models.PositiveIntegerField(default=0)
    queued_recipients = models.PositiveIntegerField(default=0)
    successful_recipients = models.PositiveIntegerField(default=0)
    delivered_recipients = models.PositiveIntegerField(default=0)
    opened_recipients = models.PositiveIntegerField(default=0)
    clicked_recipients = models.PositiveIntegerField(default=0)
    bounced_recipients = models.PositiveIntegerField(default=0)
    failed_recipients = models.PositiveIntegerField(default=0)
    open_events = models.PositiveIntegerField(default=0)
    click_events = models.PositiveIntegerField(default=0)
    delivery_rate = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    open_rate = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    click_rate = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    last_event_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]


class GatewayStatus(models.Model):
    CHANNEL_CHOICES = [
        ("EMAIL", "Email"),
        ("SMS", "SMS"),
        ("WHATSAPP", "WhatsApp"),
        ("PUSH", "Push"),
    ]

    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, unique=True)
    provider = models.CharField(max_length=60, blank=True)
    configured = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    queue_queued_total = models.PositiveIntegerField(default=0)
    queue_ready = models.PositiveIntegerField(default=0)
    queue_delayed = models.PositiveIntegerField(default=0)
    queue_retrying = models.PositiveIntegerField(default=0)
    queue_processing = models.PositiveIntegerField(default=0)
    queue_sent = models.PositiveIntegerField(default=0)
    queue_failed = models.PositiveIntegerField(default=0)
    active_devices = models.PositiveIntegerField(default=0)
    balance_payload = models.JSONField(default=dict, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_failure_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["channel", "id"]


class CommunicationAlertRule(models.Model):
    RULE_QUEUE_READY_BACKLOG = "QUEUE_READY_BACKLOG"
    RULE_QUEUE_FAILED_ITEMS = "QUEUE_FAILED_ITEMS"
    RULE_QUEUE_RETRYING_BACKLOG = "QUEUE_RETRYING_BACKLOG"
    RULE_GATEWAY_UNCONFIGURED = "GATEWAY_UNCONFIGURED"
    RULE_TYPE_CHOICES = [
        (RULE_QUEUE_READY_BACKLOG, "Queue ready backlog"),
        (RULE_QUEUE_FAILED_ITEMS, "Queue failed items"),
        (RULE_QUEUE_RETRYING_BACKLOG, "Queue retrying backlog"),
        (RULE_GATEWAY_UNCONFIGURED, "Gateway unconfigured"),
    ]

    SEVERITY_INFO = "INFO"
    SEVERITY_WARNING = "WARNING"
    SEVERITY_CRITICAL = "CRITICAL"
    SEVERITY_CHOICES = [
        (SEVERITY_INFO, "Info"),
        (SEVERITY_WARNING, "Warning"),
        (SEVERITY_CRITICAL, "Critical"),
    ]

    CHANNEL_CHOICES = [("", "All channels")] + GatewayStatus.CHANNEL_CHOICES

    name = models.CharField(max_length=180)
    rule_type = models.CharField(max_length=40, choices=RULE_TYPE_CHOICES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default=SEVERITY_WARNING)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, blank=True)
    threshold = models.PositiveIntegerField(default=1)
    config = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="communication_alert_rules")
    last_evaluated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]


class CommunicationAlertEvent(models.Model):
    STATUS_OPEN = "OPEN"
    STATUS_ACKNOWLEDGED = "ACKNOWLEDGED"
    STATUS_RESOLVED = "RESOLVED"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_ACKNOWLEDGED, "Acknowledged"),
        (STATUS_RESOLVED, "Resolved"),
    ]

    CHANNEL_CHOICES = [("", "All channels")] + GatewayStatus.CHANNEL_CHOICES

    rule = models.ForeignKey(CommunicationAlertRule, on_delete=models.CASCADE, related_name="events")
    event_key = models.CharField(max_length=200, unique=True)
    title = models.CharField(max_length=255)
    details = models.TextField(blank=True)
    severity = models.CharField(max_length=20, choices=CommunicationAlertRule.SEVERITY_CHOICES, default=CommunicationAlertRule.SEVERITY_WARNING)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    first_triggered_at = models.DateTimeField(default=timezone.now)
    last_triggered_at = models.DateTimeField(default=timezone.now)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_triggered_at", "-id"]


class CommunicationRealtimeEvent(models.Model):
    stream = models.CharField(max_length=120, db_index=True)
    event_type = models.CharField(max_length=80)
    entity_type = models.CharField(max_length=60)
    entity_id = models.CharField(max_length=120, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]


class CommunicationRealtimePresence(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="realtime_presence")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="communication_realtime_presence")
    session_key = models.CharField(max_length=120)
    metadata = models.JSONField(default=dict, blank=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    presence_expires_at = models.DateTimeField(default=timezone.now, db_index=True)
    typing_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("conversation", "user", "session_key")
        ordering = ["conversation_id", "user_id", "session_key"]


class EmailRecipient(models.Model):
    STATUS_CHOICES = [("Queued", "Queued"), ("Sent", "Sent"), ("Delivered", "Delivered"), ("Opened", "Opened"), ("Clicked", "Clicked"), ("Bounced", "Bounced"), ("Failed", "Failed")]

    campaign = models.ForeignKey(EmailCampaign, on_delete=models.CASCADE, related_name="recipients")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="email_recipients")
    email = models.EmailField()
    provider_id = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Queued")
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    open_count = models.PositiveIntegerField(default=0)
    click_count = models.PositiveIntegerField(default=0)
    bounce_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-id"]


class SmsMessage(models.Model):
    STATUS_CHOICES = [("Queued", "Queued"), ("Sent", "Sent"), ("Delivered", "Delivered"), ("Failed", "Failed")]
    CHANNEL_CHOICES = [("SMS", "SMS"), ("WhatsApp", "WhatsApp")]

    recipient_phone = models.CharField(max_length=30)
    message = models.TextField()
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default="SMS")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Queued")
    provider_id = models.CharField(max_length=100, blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="sms_messages")
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class MessageTemplate(models.Model):
    CATEGORY_CHOICES = [("Academic", "Academic"), ("Financial", "Financial"), ("Event", "Event"), ("Alert", "Alert"), ("System", "System")]
    CHANNEL_CHOICES = [("Email", "Email"), ("SMS", "SMS"), ("InApp", "InApp"), ("Push", "Push"), ("WhatsApp", "WhatsApp")]

    name = models.CharField(max_length=180)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="System")
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default="Email")
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField()
    language = models.CharField(max_length=10, default="en")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="message_templates")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "-id"]


class Announcement(models.Model):
    PRIORITY_CHOICES = [("Urgent", "Urgent"), ("Important", "Important"), ("Normal", "Normal")]
    AUDIENCE_CHOICES = [("All", "All"), ("Students", "Students"), ("Parents", "Parents"), ("Staff", "Staff"), ("Class", "Class"), ("Department", "Department"), ("Custom", "Custom")]

    title = models.CharField(max_length=255)
    body = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="Normal")
    audience_type = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default="All")
    audience_filter = models.JSONField(default=dict, blank=True)
    publish_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_pinned = models.BooleanField(default=False)
    notify_email = models.BooleanField(default=False)
    notify_sms = models.BooleanField(default=False)
    notify_push = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="announcements")
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-publish_at", "-id"]


class AnnouncementRead(models.Model):
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name="reads")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="announcement_reads")
    read_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("announcement", "user")
        ordering = ["-read_at", "-id"]


class PushDevice(models.Model):
    PLATFORM_CHOICES = [("Android", "Android"), ("iOS", "iOS"), ("Web", "Web")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_devices")
    token = models.CharField(max_length=255)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, default="Web")
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "token")
        ordering = ["-last_seen_at", "-id"]


class PushNotificationLog(models.Model):
    STATUS_CHOICES = [("Queued", "Queued"), ("Sent", "Sent"), ("Delivered", "Delivered"), ("Failed", "Failed")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_notifications")
    title = models.CharField(max_length=255)
    body = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Queued")
    provider_id = models.CharField(max_length=120, blank=True)
    failure_reason = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="push_notifications_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class MessageDelivery(models.Model):
    CHANNEL_CHOICES = [
        ("EMAIL", "Email"),
        ("SMS", "SMS"),
        ("WHATSAPP", "WhatsApp"),
        ("PUSH", "Push"),
    ]
    STATUS_CHOICES = [
        ("Queued", "Queued"),
        ("Processing", "Processing"),
        ("Sent", "Sent"),
        ("Delivered", "Delivered"),
        ("Opened", "Opened"),
        ("Clicked", "Clicked"),
        ("Failed", "Failed"),
        ("Bounced", "Bounced"),
    ]

    unified_message = models.ForeignKey(UnifiedMessage, on_delete=models.CASCADE, related_name="deliveries")
    delivery_key = models.CharField(max_length=160, unique=True)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Queued", db_index=True)
    source_type = models.CharField(max_length=40, blank=True)
    source_id = models.PositiveIntegerField(null=True, blank=True)
    recipient = models.CharField(max_length=255, blank=True)
    provider_id = models.CharField(max_length=120, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)
    queued_at = models.DateTimeField(default=timezone.now)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class CommunicationDispatchTask(models.Model):
    CHANNEL_CHOICES = [
        ("EMAIL", "Email"),
        ("SMS", "SMS"),
        ("WHATSAPP", "WhatsApp"),
        ("PUSH", "Push"),
    ]
    STATUS_CHOICES = [
        ("Queued", "Queued"),
        ("Processing", "Processing"),
        ("Sent", "Sent"),
        ("Failed", "Failed"),
    ]

    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Queued", db_index=True)
    source_type = models.CharField(max_length=40, blank=True)
    source_id = models.PositiveIntegerField(null=True, blank=True)
    recipient = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    dedupe_key = models.CharField(max_length=160, unique=True)
    delivery = models.ForeignKey("MessageDelivery", on_delete=models.SET_NULL, null=True, blank=True, related_name="dispatch_tasks")
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)
    available_at = models.DateTimeField(default=timezone.now, db_index=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    provider_id = models.CharField(max_length=120, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["available_at", "id"]


class Message(models.Model):
    """
    Legacy unmanaged wrapper for school.Message references.
    """
    recipient_type = models.CharField(max_length=20)
    recipient_id = models.IntegerField()
    subject = models.CharField(max_length=200)
    body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20)

    class Meta:
        managed = False
        db_table = "school_message"
