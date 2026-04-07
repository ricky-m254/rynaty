from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('school', '0018_reportcard'),
    ]

    operations = [
        migrations.CreateModel(
            name='Assignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('due_date', models.DateTimeField()),
                ('max_score', models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True)),
                ('publish_date', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(choices=[('Draft', 'Draft'), ('Published', 'Published'), ('Closed', 'Closed'), ('Graded', 'Graded')], default='Draft', max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('class_section', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='school.schoolclass')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='school.subject')),
                ('teacher', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='auth.user')),
            ],
        ),
        migrations.CreateModel(
            name='CalendarEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('event_type', models.CharField(choices=[('Holiday', 'Holiday'), ('Exam', 'Exam'), ('Sports', 'Sports'), ('Trip', 'Trip'), ('Meeting', 'Meeting'), ('Closure', 'Closure'), ('Other', 'Other')], default='Other', max_length=20)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('start_time', models.TimeField(blank=True, null=True)),
                ('end_time', models.TimeField(blank=True, null=True)),
                ('description', models.TextField(blank=True)),
                ('scope', models.CharField(choices=[('School-wide', 'School-wide'), ('Class-specific', 'Class-specific'), ('Staff-only', 'Staff-only')], default='School-wide', max_length=20)),
                ('is_public', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('is_active', models.BooleanField(default=True)),
                ('academic_year', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='school.academicyear')),
                ('class_section', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='school.schoolclass')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='auth.user')),
                ('term', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='school.term')),
            ],
        ),
        migrations.CreateModel(
            name='AssignmentSubmission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('is_late', models.BooleanField(default=False)),
                ('file', models.FileField(blank=True, null=True, upload_to='assignments/submissions/')),
                ('notes', models.TextField(blank=True)),
                ('score', models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True)),
                ('feedback', models.TextField(blank=True)),
                ('graded_at', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('assignment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='submissions', to='school.assignment')),
                ('graded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='auth.user')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='school.student')),
            ],
            options={
                'unique_together': {('assignment', 'student')},
            },
        ),
    ]
