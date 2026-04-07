from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0026_scholarshipaward'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoiceinstallment',
            name='collected_amount',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=12, validators=[django.core.validators.MinValueValidator(0.0)]),
        ),
        migrations.AddField(
            model_name='invoiceinstallment',
            name='paid_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

