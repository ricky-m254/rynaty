from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0027_invoiceinstallment_collected_amount_paid_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="schoolprofile",
            name="admission_number_mode",
            field=models.CharField(
                choices=[("AUTO", "Auto generate"), ("MANUAL", "Manual entry")],
                default="AUTO",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="schoolprofile",
            name="admission_number_padding",
            field=models.PositiveIntegerField(default=4),
        ),
        migrations.AddField(
            model_name="schoolprofile",
            name="admission_number_prefix",
            field=models.CharField(default="ADM-", max_length=20),
        ),
    ]

