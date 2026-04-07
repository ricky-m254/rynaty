from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0028_schoolprofile_admission_number_settings"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TenantModule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_enabled", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("module", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="tenant_module", to="school.module")),
            ],
            options={
                "ordering": ["sort_order", "module__key"],
            },
        ),
        migrations.CreateModel(
            name="ModuleSetting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("theme_preset", models.CharField(choices=[("DEFAULT", "Default"), ("MODERN", "Modern"), ("CLASSIC", "Classic"), ("MINIMAL", "Minimal"), ("DARK", "Dark")], default="DEFAULT", max_length=20)),
                ("primary_color", models.CharField(default="#10b981", max_length=16)),
                ("secondary_color", models.CharField(default="#0ea5e9", max_length=16)),
                ("sidebar_style", models.CharField(choices=[("COLLAPSED", "Collapsed"), ("EXPANDED", "Expanded"), ("ICON_ONLY", "Icon-only")], default="EXPANDED", max_length=20)),
                ("feature_toggles", models.JSONField(blank=True, default=dict)),
                ("config", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_module_settings", to=settings.AUTH_USER_MODEL)),
                ("tenant_module", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="settings", to="school.tenantmodule")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_module_settings", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["tenant_module__module__key"],
            },
        ),
    ]
