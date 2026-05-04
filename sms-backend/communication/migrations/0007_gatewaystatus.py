from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("communication", "0006_campaignstats"),
    ]

    operations = [
        migrations.CreateModel(
            name="GatewayStatus",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("channel", models.CharField(choices=[("EMAIL", "Email"), ("SMS", "SMS"), ("WHATSAPP", "WhatsApp"), ("PUSH", "Push")], max_length=20, unique=True)),
                ("provider", models.CharField(blank=True, max_length=60)),
                ("configured", models.BooleanField(default=False)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("queue_queued_total", models.PositiveIntegerField(default=0)),
                ("queue_ready", models.PositiveIntegerField(default=0)),
                ("queue_delayed", models.PositiveIntegerField(default=0)),
                ("queue_retrying", models.PositiveIntegerField(default=0)),
                ("queue_processing", models.PositiveIntegerField(default=0)),
                ("queue_sent", models.PositiveIntegerField(default=0)),
                ("queue_failed", models.PositiveIntegerField(default=0)),
                ("active_devices", models.PositiveIntegerField(default=0)),
                ("balance_payload", models.JSONField(blank=True, default=dict)),
                ("last_success_at", models.DateTimeField(blank=True, null=True)),
                ("last_failure_at", models.DateTimeField(blank=True, null=True)),
                ("last_synced_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["channel", "id"]},
        ),
    ]
