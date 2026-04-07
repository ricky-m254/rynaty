from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("admissions", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="admissionapplicationprofile",
            name="is_shortlisted",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="admissionapplicationprofile",
            name="shortlisted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="AdmissionReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("academic_score", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("test_score", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("interview_score", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("overall_score", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                (
                    "recommendation",
                    models.CharField(
                        choices=[
                            ("Accept", "Accept"),
                            ("Reject", "Reject"),
                            ("Waitlist", "Waitlist"),
                            ("Further Review", "Further Review"),
                        ],
                        default="Further Review",
                        max_length=20,
                    ),
                ),
                ("comments", models.TextField(blank=True)),
                ("reviewed_at", models.DateTimeField(auto_now_add=True)),
                (
                    "application",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reviews", to="school.admissionapplication"),
                ),
                (
                    "reviewer",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="admissions_reviews",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-reviewed_at"]},
        ),
    ]
