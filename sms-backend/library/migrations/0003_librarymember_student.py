from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0028_schoolprofile_admission_number_settings"),
        ("library", "0002_inventoryaudit_acquisitionrequest"),
    ]

    operations = [
        migrations.AddField(
            model_name="librarymember",
            name="student",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="library_member_profile",
                to="school.student",
            ),
        ),
    ]

