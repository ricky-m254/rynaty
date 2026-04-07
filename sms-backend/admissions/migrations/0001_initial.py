# Generated manually for Phase B admissions split.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("school", "0019_assignment_calendarevent_assignmentsubmission"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AdmissionInquiry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("parent_name", models.CharField(max_length=255)),
                ("parent_phone", models.CharField(blank=True, max_length=30)),
                ("parent_email", models.EmailField(blank=True, max_length=254)),
                ("child_name", models.CharField(max_length=255)),
                ("child_dob", models.DateField(blank=True, null=True)),
                ("child_age", models.PositiveIntegerField(blank=True, null=True)),
                ("current_school", models.CharField(blank=True, max_length=255)),
                (
                    "inquiry_source",
                    models.CharField(
                        choices=[
                            ("Website", "Website"),
                            ("Referral", "Referral"),
                            ("Advertisement", "Advertisement"),
                            ("Walk-in", "Walk-in"),
                            ("Event", "Event"),
                            ("Other", "Other"),
                        ],
                        default="Website",
                        max_length=30,
                    ),
                ),
                ("inquiry_date", models.DateField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("New", "New"),
                            ("Contacted", "Contacted"),
                            ("Interested", "Interested"),
                            ("Applied", "Applied"),
                            ("Lost", "Lost"),
                        ],
                        default="New",
                        max_length=20,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "assigned_counselor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="admissions_inquiries_assigned",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "grade_level_interest",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="school.schoolclass"),
                ),
                (
                    "preferred_start",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="school.term"),
                ),
            ],
            options={"ordering": ["-inquiry_date", "-created_at"]},
        ),
        migrations.CreateModel(
            name="AdmissionApplicationProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("special_needs", models.TextField(blank=True)),
                ("medical_notes", models.TextField(blank=True)),
                ("languages", models.CharField(blank=True, max_length=255)),
                ("emergency_contact_name", models.CharField(blank=True, max_length=255)),
                ("emergency_contact_phone", models.CharField(blank=True, max_length=30)),
                ("parent_id_number", models.CharField(blank=True, max_length=100)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "academic_year",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="school.academicyear"),
                ),
                (
                    "application",
                    models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="normalized_profile", to="school.admissionapplication"),
                ),
                (
                    "inquiry",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="applications", to="admissions.admissioninquiry"),
                ),
                ("term", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="school.term")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
