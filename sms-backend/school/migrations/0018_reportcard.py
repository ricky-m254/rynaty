from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('school', '0017_gradebook_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReportCard',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('Draft', 'Draft'), ('Submitted', 'Submitted'), ('Approved', 'Approved'), ('Published', 'Published'), ('Distributed', 'Distributed')], default='Draft', max_length=20)),
                ('teacher_remarks', models.TextField(blank=True)),
                ('principal_remarks', models.TextField(blank=True)),
                ('class_rank', models.PositiveIntegerField(blank=True, null=True)),
                ('overall_grade', models.CharField(blank=True, max_length=50)),
                ('attendance_days', models.PositiveIntegerField(default=0)),
                ('pdf_file', models.FileField(blank=True, null=True, upload_to='report_cards/')),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('published_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('is_active', models.BooleanField(default=True)),
                ('academic_year', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='school.academicyear')),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='auth.user')),
                ('class_section', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='school.schoolclass')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='school.student')),
                ('term', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='school.term')),
            ],
            options={
                'unique_together': {('student', 'class_section', 'term', 'academic_year')},
            },
        ),
    ]
