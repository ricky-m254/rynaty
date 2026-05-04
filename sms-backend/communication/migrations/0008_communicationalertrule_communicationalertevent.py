from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("communication", "0007_gatewaystatus"),
    ]

    operations = [
        migrations.CreateModel(
            name="CommunicationAlertRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=180)),
                (
                    "rule_type",
                    models.CharField(
                        choices=[
                            ("QUEUE_READY_BACKLOG", "Queue ready backlog"),
                            ("QUEUE_FAILED_ITEMS", "Queue failed items"),
                            ("QUEUE_RETRYING_BACKLOG", "Queue retrying backlog"),
                            ("GATEWAY_UNCONFIGURED", "Gateway unconfigured"),
                        ],
                        max_length=40,
                    ),
                ),
                (
                    "severity",
                    models.CharField(
                        choices=[("INFO", "Info"), ("WARNING", "Warning"), ("CRITICAL", "Critical")],
                        default="WARNING",
                        max_length=20,
                    ),
                ),
                (
                    "channel",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("", "All channels"),
                            ("EMAIL", "Email"),
                            ("SMS", "SMS"),
                            ("WHATSAPP", "WhatsApp"),
                            ("PUSH", "Push"),
                        ],
                        max_length=20,
                    ),
                ),
                ("threshold", models.PositiveIntegerField(default=1)),
                ("config", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("last_evaluated_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="communication_alert_rules",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["name", "id"],
            },
        ),
        migrations.CreateModel(
            name="CommunicationAlertEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_key", models.CharField(max_length=200, unique=True)),
                ("title", models.CharField(max_length=255)),
                ("details", models.TextField(blank=True)),
                (
                    "severity",
                    models.CharField(
                        choices=[("INFO", "Info"), ("WARNING", "Warning"), ("CRITICAL", "Critical")],
                        default="WARNING",
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("OPEN", "Open"), ("ACKNOWLEDGED", "Acknowledged"), ("RESOLVED", "Resolved")],
                        default="OPEN",
                        max_length=20,
                    ),
                ),
                (
                    "channel",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("", "All channels"),
                            ("EMAIL", "Email"),
                            ("SMS", "SMS"),
                            ("WHATSAPP", "WhatsApp"),
                            ("PUSH", "Push"),
                        ],
                        max_length=20,
                    ),
                ),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("first_triggered_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_triggered_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("acknowledged_at", models.DateTimeField(blank=True, null=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "rule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to="communication.communicationalertrule",
                    ),
                ),
            ],
            options={
                "ordering": ["-last_triggered_at", "-id"],
            },
        ),
    ]
