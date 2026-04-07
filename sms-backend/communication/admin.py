from django.contrib import admin

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
)

admin.site.register(Conversation)
admin.site.register(ConversationParticipant)
admin.site.register(CommunicationMessage)
admin.site.register(MessageAttachment)
admin.site.register(MessageReadReceipt)
admin.site.register(Notification)
admin.site.register(NotificationPreference)
admin.site.register(PushDevice)
admin.site.register(PushNotificationLog)
admin.site.register(EmailCampaign)
admin.site.register(EmailRecipient)
admin.site.register(SmsMessage)
admin.site.register(MessageTemplate)
admin.site.register(Announcement)
admin.site.register(AnnouncementRead)
