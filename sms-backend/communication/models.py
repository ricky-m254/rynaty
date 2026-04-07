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
