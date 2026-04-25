from decimal import Decimal

from django.core import validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0063_alter_mediafile_file_type_alter_mediafile_module"),
    ]

    operations = [
        migrations.AlterField(
            model_name="schoolprofile",
            name="admission_number_prefix",
            field=models.CharField(
                default="ADM-",
                max_length=20,
                validators=[
                    validators.RegexValidator(
                        message="Admission prefix must be uppercase letters, numbers, or hyphens only (max 20 chars).",
                        regex="^[A-Z0-9-]{1,20}$",
                    )
                ],
            ),
        ),
        migrations.AlterField(
            model_name="schoolprofile",
            name="invoice_prefix",
            field=models.CharField(
                default="INV-",
                max_length=10,
                validators=[
                    validators.RegexValidator(
                        message="Prefix must be uppercase letters, numbers, or hyphens only (max 10 chars).",
                        regex="^[A-Z0-9-]{1,10}$",
                    )
                ],
            ),
        ),
        migrations.AlterField(
            model_name="schoolprofile",
            name="late_fee_max",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True,
                validators=[validators.MinValueValidator(Decimal("0"))],
            ),
        ),
        migrations.AlterField(
            model_name="schoolprofile",
            name="late_fee_value",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=10,
                validators=[validators.MinValueValidator(Decimal("0"))],
            ),
        ),
        migrations.AlterField(
            model_name="schoolprofile",
            name="receipt_prefix",
            field=models.CharField(
                default="RCT-",
                max_length=10,
                validators=[
                    validators.RegexValidator(
                        message="Prefix must be uppercase letters, numbers, or hyphens only (max 10 chars).",
                        regex="^[A-Z0-9-]{1,10}$",
                    )
                ],
            ),
        ),
        migrations.AlterField(
            model_name="schoolprofile",
            name="sms_sender_id",
            field=models.CharField(
                blank=True,
                max_length=20,
                validators=[
                    validators.RegexValidator(
                        message="SMS sender ID must be alphanumeric, max 20 chars.",
                        regex="^[A-Za-z0-9]{1,20}$",
                    )
                ],
            ),
        ),
        migrations.AlterField(
            model_name="schoolprofile",
            name="tax_percentage",
            field=models.DecimalField(
                decimal_places=2,
                default=0.0,
                max_digits=5,
                validators=[
                    validators.MinValueValidator(Decimal("0")),
                    validators.MaxValueValidator(Decimal("100")),
                ],
            ),
        ),
    ]
