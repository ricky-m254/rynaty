from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('school', '0015_department_subject_subjectmapping_syllabustopic'),
    ]

    operations = [
        migrations.AddField(
            model_name='enrollment',
            name='left_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='enrollment',
            name='status',
            field=models.CharField(choices=[('Active', 'Active'), ('Completed', 'Completed'), ('Withdrawn', 'Withdrawn'), ('Transferred', 'Transferred')], default='Active', max_length=20),
        ),
        migrations.CreateModel(
            name='TeacherAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_primary', models.BooleanField(default=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('academic_year', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='school.academicyear')),
                ('class_section', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='school.schoolclass')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='school.subject')),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='teacher_assignments', to='auth.user')),
                ('term', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='school.term')),
            ],
            options={
                'unique_together': {('teacher', 'subject', 'class_section', 'academic_year', 'term')},
            },
        ),
    ]
