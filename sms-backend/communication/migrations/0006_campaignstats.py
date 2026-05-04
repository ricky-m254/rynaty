from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("communication", "0005_unifiedmessage_messagedelivery_and_task_delivery"),
    ]

    operations = [
        migrations.CreateModel(
            name="CampaignStats",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("total_recipients", models.PositiveIntegerField(default=0)),
                ("queued_recipients", models.PositiveIntegerField(default=0)),
                ("successful_recipients", models.PositiveIntegerField(default=0)),
                ("delivered_recipients", models.PositiveIntegerField(default=0)),
                ("opened_recipients", models.PositiveIntegerField(default=0)),
                ("clicked_recipients", models.PositiveIntegerField(default=0)),
                ("bounced_recipients", models.PositiveIntegerField(default=0)),
                ("failed_recipients", models.PositiveIntegerField(default=0)),
                ("open_events", models.PositiveIntegerField(default=0)),
                ("click_events", models.PositiveIntegerField(default=0)),
                ("delivery_rate", models.DecimalField(decimal_places=2, default=0, max_digits=6)),
                ("open_rate", models.DecimalField(decimal_places=2, default=0, max_digits=6)),
                ("click_rate", models.DecimalField(decimal_places=2, default=0, max_digits=6)),
                ("last_event_at", models.DateTimeField(blank=True, null=True)),
                ("last_synced_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("campaign", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="stats_snapshot", to="communication.emailcampaign")),
                ("unified_message", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="campaign_stats_snapshot", to="communication.unifiedmessage")),
            ],
            options={"ordering": ["-updated_at", "-id"]},
        ),
    ]
