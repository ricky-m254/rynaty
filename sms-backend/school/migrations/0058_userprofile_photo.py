from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0057_lifecycle_automation"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="photo",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="user_profiles/photos/",
                help_text="Profile photo for portal display.",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="bio",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Short professional bio (teachers/staff).",
            ),
        ),
    ]
