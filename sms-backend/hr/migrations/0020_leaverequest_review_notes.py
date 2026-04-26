from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hr", "0019_session9_exit_and_clearance"),
    ]

    operations = [
        migrations.AddField(
            model_name="leaverequest",
            name="review_notes",
            field=models.TextField(blank=True),
        ),
    ]
