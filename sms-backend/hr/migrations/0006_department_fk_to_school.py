from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hr', '0005_performancegoal_performancereview_trainingprogram_and_more'),
        ('school', '0034_store_order_request_code_and_expense_link'),
    ]

    operations = [
        migrations.AlterField(
            model_name='employee',
            name='department',
            field=models.ForeignKey(
                'school.Department',
                on_delete=django.db.models.deletion.SET_NULL,
                null=True,
                blank=True,
                related_name='hr_employees',
            ),
        ),
        migrations.AlterField(
            model_name='position',
            name='department',
            field=models.ForeignKey(
                'school.Department',
                on_delete=django.db.models.deletion.SET_NULL,
                null=True,
                blank=True,
                related_name='hr_positions',
            ),
        ),
        migrations.AlterField(
            model_name='workschedule',
            name='department',
            field=models.ForeignKey(
                'school.Department',
                on_delete=django.db.models.deletion.SET_NULL,
                null=True,
                blank=True,
                related_name='hr_schedules',
            ),
        ),
        migrations.AlterField(
            model_name='jobposting',
            name='department',
            field=models.ForeignKey(
                'school.Department',
                on_delete=django.db.models.deletion.SET_NULL,
                null=True,
                blank=True,
                related_name='hr_job_postings',
            ),
        ),
    ]
