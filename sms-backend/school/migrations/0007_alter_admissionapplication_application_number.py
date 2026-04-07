from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0006_admissionapplication'),
    ]

    operations = [
        migrations.AlterField(
            model_name='admissionapplication',
            name='application_number',
            field=models.CharField(blank=True, max_length=50, null=True, unique=True),
        ),
    ]
