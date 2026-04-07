from django.db import migrations, models
import django.db.models.deletion
from django.core.validators import MinValueValidator
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('school', '0016_enrollment_status_teacherassignment'),
    ]

    operations = [
        migrations.CreateModel(
            name='Assessment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150)),
                ('category', models.CharField(choices=[('Classwork', 'Classwork'), ('Homework', 'Homework'), ('Test', 'Test'), ('Exam', 'Exam'), ('Project', 'Project'), ('Practical', 'Practical')], default='Test', max_length=20)),
                ('max_score', models.DecimalField(decimal_places=2, max_digits=7, validators=[MinValueValidator(Decimal('0.00'))])),
                ('weight_percent', models.DecimalField(decimal_places=2, default=0.0, max_digits=5, validators=[MinValueValidator(Decimal('0.00'))])),
                ('date', models.DateField()),
                ('is_published', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('class_section', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='school.schoolclass')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='school.subject')),
                ('term', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='school.term')),
            ],
        ),
        migrations.CreateModel(
            name='GradingScheme',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('is_default', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='GradeBand',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=20)),
                ('min_score', models.DecimalField(decimal_places=2, max_digits=5, validators=[MinValueValidator(Decimal('0.00'))])),
                ('max_score', models.DecimalField(decimal_places=2, max_digits=5, validators=[MinValueValidator(Decimal('0.00'))])),
                ('grade_point', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('remark', models.CharField(blank=True, max_length=100)),
                ('is_active', models.BooleanField(default=True)),
                ('scheme', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bands', to='school.gradingscheme')),
            ],
            options={
                'ordering': ['-min_score', '-max_score', 'id'],
            },
        ),
        migrations.CreateModel(
            name='TermResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_score', models.DecimalField(decimal_places=2, default=0.0, max_digits=7)),
                ('class_rank', models.PositiveIntegerField(blank=True, null=True)),
                ('is_pass', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('class_section', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='school.schoolclass')),
                ('grade_band', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='school.gradeband')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='school.student')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='school.subject')),
                ('term', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='school.term')),
            ],
            options={
                'unique_together': {('student', 'class_section', 'term', 'subject')},
            },
        ),
        migrations.CreateModel(
            name='AssessmentGrade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('raw_score', models.DecimalField(decimal_places=2, max_digits=7, validators=[MinValueValidator(Decimal('0.00'))])),
                ('percentage', models.DecimalField(decimal_places=2, default=0.0, max_digits=7)),
                ('entered_at', models.DateTimeField(auto_now=True)),
                ('remarks', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('assessment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='grades', to='school.assessment')),
                ('entered_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='auth.user')),
                ('grade_band', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='school.gradeband')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='school.student')),
            ],
            options={
                'unique_together': {('assessment', 'student')},
            },
        ),
    ]
