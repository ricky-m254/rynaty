from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("communication", "0008_communicationalertrule_communicationalertevent"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CommunicationRealtimeEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("stream", models.CharField(db_index=True, max_length=120)),
                ("event_type", models.CharField(max_length=80)),
                ("entity_type", models.CharField(max_length=60)),
                ("entity_id", models.CharField(blank=True, max_length=120)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("occurred_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["id"],
            },
        ),
        migrations.CreateModel(
            name="CommunicationRealtimePresence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("session_key", models.CharField(max_length=120)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("last_seen_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("presence_expires_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("typing_expires_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "conversation",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="realtime_presence", to="communication.conversation"),
                ),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="communication_realtime_presence", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "ordering": ["conversation_id", "user_id", "session_key"],
                "unique_together": {("conversation", "user", "session_key")},
            },
        ),
    ]
