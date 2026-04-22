from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("library", "0004_add_digital_url_to_resource"),
    ]

    operations = [
        migrations.CreateModel(
            name="TeacherClassroomLoan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("issue_date", models.DateTimeField(default=django.utils.timezone.now)),
                ("due_date", models.DateField(blank=True, null=True)),
                ("return_date", models.DateTimeField(blank=True, null=True)),
                (
                    "return_destination",
                    models.CharField(
                        blank=True,
                        choices=[("Teacher", "Teacher"), ("Library", "Library")],
                        max_length=20,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "copy",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="classroom_loans",
                        to="library.resourcecopy",
                    ),
                ),
                (
                    "issued_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="teacher_classroom_loans_issued",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "received_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="teacher_classroom_loans_received",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "student_member",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="student_classroom_loans",
                        to="library.librarymember",
                    ),
                ),
                (
                    "teacher_member",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="teacher_classroom_loans",
                        to="library.librarymember",
                    ),
                ),
                (
                    "teacher_transaction",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="classroom_loans",
                        to="library.circulationtransaction",
                    ),
                ),
            ],
            options={
                "ordering": ["-issue_date", "-id"],
            },
        ),
    ]
