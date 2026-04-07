# Generated manually for Library inventory + acquisition baseline.
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("library", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="InventoryAudit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("audit_date", models.DateField(default=django.utils.timezone.now)),
                ("total_expected", models.PositiveIntegerField(default=0)),
                ("total_found", models.PositiveIntegerField(default=0)),
                ("missing_count", models.PositiveIntegerField(default=0)),
                ("status", models.CharField(choices=[("In Progress", "In Progress"), ("Completed", "Completed")], default="In Progress", max_length=20)),
                ("notes", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "conducted_by",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="library_inventory_audits", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={"ordering": ["-audit_date", "-id"]},
        ),
        migrations.CreateModel(
            name="AcquisitionRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("author", models.CharField(blank=True, max_length=255)),
                ("isbn", models.CharField(blank=True, max_length=40)),
                ("quantity", models.PositiveIntegerField(default=1)),
                ("justification", models.TextField(blank=True)),
                ("estimated_cost", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("status", models.CharField(choices=[("Pending", "Pending"), ("Approved", "Approved"), ("Rejected", "Rejected"), ("Ordered", "Ordered"), ("Received", "Received")], default="Pending", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "approved_by",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="library_acquisition_requests_approved", to=settings.AUTH_USER_MODEL),
                ),
                (
                    "requested_by",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="library_acquisition_requests", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
    ]
