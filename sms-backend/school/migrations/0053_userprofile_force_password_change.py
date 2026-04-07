from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0052_expand_core_role_catalog"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="force_password_change",
            field=models.BooleanField(
                default=False,
                help_text="Require the user to change their password before continuing to the portal.",
            ),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="admission_number",
            field=models.CharField(
                blank=True,
                help_text="Temporary bridge field for student account mapping; not a permanent login identity.",
                max_length=50,
                null=True,
                unique=True,
            ),
        ),
    ]
