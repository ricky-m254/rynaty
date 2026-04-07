from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0040_seed_parent_student_roles'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='admission_number',
            field=models.CharField(
                blank=True,
                help_text='For STUDENT/PARENT accounts: student admission number used as login identifier.',
                max_length=50,
                null=True,
                unique=True,
            ),
        ),
    ]
