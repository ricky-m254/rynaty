from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("admissions", "0003_assessment_interview"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AdmissionDecision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("decision", models.CharField(choices=[("Accept", "Accept"), ("Reject", "Reject"), ("Waitlist", "Waitlist")], max_length=20)),
                ("decision_date", models.DateField()),
                ("decision_notes", models.TextField(blank=True)),
                ("offer_deadline", models.DateField(blank=True, null=True)),
                (
                    "response_status",
                    models.CharField(
                        choices=[("Pending", "Pending"), ("Accepted", "Accepted"), ("Declined", "Declined")],
                        default="Pending",
                        max_length=20,
                    ),
                ),
                ("response_notes", models.TextField(blank=True)),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "application",
                    models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="decision_record", to="school.admissionapplication"),
                ),
                (
                    "decided_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="admissions_decisions_made",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-decision_date", "-created_at"]},
        ),
    ]
