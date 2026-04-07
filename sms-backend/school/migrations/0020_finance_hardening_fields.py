from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0019_assignment_calendarevent_assignmentsubmission"),
    ]

    operations = [
        migrations.AddField(
            model_name="expense",
            name="approval_status",
            field=models.CharField(
                choices=[("Pending", "Pending"), ("Approved", "Approved"), ("Rejected", "Rejected")],
                default="Pending",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="expense",
            name="invoice_number",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="expense",
            name="payment_method",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="expense",
            name="vendor",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name="feeassignment",
            name="end_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="feeassignment",
            name="start_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="feestructure",
            name="category",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="feestructure",
            name="grade_level",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="school.gradelevel",
            ),
        ),
    ]
