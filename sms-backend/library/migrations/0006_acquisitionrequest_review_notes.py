from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("library", "0005_teacherclassroomloan"),
    ]

    operations = [
        migrations.AddField(
            model_name="acquisitionrequest",
            name="review_notes",
            field=models.TextField(blank=True),
        ),
    ]
