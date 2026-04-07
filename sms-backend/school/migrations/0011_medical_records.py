from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0010_student_uploads'),
    ]

    operations = [
        migrations.CreateModel(
            name='MedicalRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('blood_type', models.CharField(blank=True, max_length=10)),
                ('allergies', models.TextField(blank=True)),
                ('chronic_conditions', models.TextField(blank=True)),
                ('current_medications', models.TextField(blank=True)),
                ('doctor_name', models.CharField(blank=True, max_length=255)),
                ('doctor_phone', models.CharField(blank=True, max_length=20)),
                ('notes', models.TextField(blank=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('student', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='medical_record', to='school.student')),
            ],
        ),
        migrations.CreateModel(
            name='ImmunizationRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('vaccine_name', models.CharField(max_length=255)),
                ('date_administered', models.DateField()),
                ('booster_due_date', models.DateField(blank=True, null=True)),
                ('certificate', models.FileField(blank=True, null=True, upload_to='students/immunizations/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='immunizations', to='school.student')),
            ],
        ),
        migrations.CreateModel(
            name='ClinicVisit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('visit_date', models.DateField()),
                ('visit_time', models.TimeField(blank=True, null=True)),
                ('complaint', models.TextField(blank=True)),
                ('treatment', models.TextField(blank=True)),
                ('parent_notified', models.BooleanField(default=False)),
                ('severity', models.CharField(blank=True, choices=[('Minor', 'Minor'), ('Moderate', 'Moderate'), ('Serious', 'Serious')], max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('attended_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='clinic_visits', to='school.student')),
            ],
        ),
    ]

