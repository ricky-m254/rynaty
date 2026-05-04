from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("communication", "0004_communicationdispatchtask"),
    ]

    operations = [
        migrations.CreateModel(
            name="UnifiedMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("message_key", models.CharField(max_length=160, unique=True)),
                ("kind", models.CharField(choices=[("DIRECT", "Direct"), ("CAMPAIGN", "Campaign"), ("PARENT_NOTICE", "Parent Notice"), ("SYSTEM", "System")], default="DIRECT", max_length=30)),
                ("status", models.CharField(choices=[("Draft", "Draft"), ("Queued", "Queued"), ("Sending", "Sending"), ("Sent", "Sent"), ("Partial", "Partial"), ("Failed", "Failed")], db_index=True, default="Queued", max_length=20)),
                ("source_type", models.CharField(blank=True, max_length=40)),
                ("source_id", models.PositiveIntegerField(blank=True, null=True)),
                ("title", models.CharField(blank=True, max_length=255)),
                ("subject", models.CharField(blank=True, max_length=255)),
                ("body", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("campaign", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="unified_messages", to="communication.emailcampaign")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="unified_messages", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="MessageDelivery",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("delivery_key", models.CharField(max_length=160, unique=True)),
                ("channel", models.CharField(choices=[("EMAIL", "Email"), ("SMS", "SMS"), ("WHATSAPP", "WhatsApp"), ("PUSH", "Push")], max_length=20)),
                ("status", models.CharField(choices=[("Queued", "Queued"), ("Processing", "Processing"), ("Sent", "Sent"), ("Delivered", "Delivered"), ("Opened", "Opened"), ("Clicked", "Clicked"), ("Failed", "Failed"), ("Bounced", "Bounced")], db_index=True, default="Queued", max_length=20)),
                ("source_type", models.CharField(blank=True, max_length=40)),
                ("source_id", models.PositiveIntegerField(blank=True, null=True)),
                ("recipient", models.CharField(blank=True, max_length=255)),
                ("provider_id", models.CharField(blank=True, max_length=120)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("max_attempts", models.PositiveIntegerField(default=3)),
                ("queued_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_attempt_at", models.DateTimeField(blank=True, null=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("opened_at", models.DateTimeField(blank=True, null=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("failure_reason", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("unified_message", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="deliveries", to="communication.unifiedmessage")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddField(
            model_name="communicationdispatchtask",
            name="delivery",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="dispatch_tasks", to="communication.messagedelivery"),
        ),
    ]
