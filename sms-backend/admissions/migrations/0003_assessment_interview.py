from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("admissions", "0002_review_and_shortlist"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AdmissionAssessment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("scheduled_at", models.DateTimeField()),
                ("venue", models.CharField(blank=True, max_length=255)),
                ("score", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("is_pass", models.BooleanField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("Scheduled", "Scheduled"), ("Completed", "Completed"), ("Missed", "Missed")],
                        default="Scheduled",
                        max_length=20,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "application",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assessments", to="school.admissionapplication"),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="admissions_assessments_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-scheduled_at", "-created_at"]},
        ),
        migrations.CreateModel(
            name="AdmissionInterview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("interview_date", models.DateTimeField()),
                (
                    "interview_type",
                    models.CharField(
                        choices=[("Phone", "Phone"), ("Video", "Video"), ("In-person", "In-person")],
                        default="In-person",
                        max_length=20,
                    ),
                ),
                ("location", models.CharField(blank=True, max_length=255)),
                ("panel", models.JSONField(blank=True, default=list)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("Scheduled", "Scheduled"),
                            ("Completed", "Completed"),
                            ("Cancelled", "Cancelled"),
                            ("No-show", "No-show"),
                        ],
                        default="Scheduled",
                        max_length=20,
                    ),
                ),
                ("feedback", models.TextField(blank=True)),
                ("score", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "application",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="interviews", to="school.admissionapplication"),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="admissions_interviews_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-interview_date", "-created_at"]},
        ),
    ]
