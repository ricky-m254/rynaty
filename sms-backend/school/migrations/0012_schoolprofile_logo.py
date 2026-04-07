from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('school', '0011_medical_records'),
    ]

    operations = [
        migrations.AddField(
            model_name='schoolprofile',
            name='logo',
            field=models.ImageField(blank=True, null=True, upload_to='school_logos/'),
        ),
    ]
