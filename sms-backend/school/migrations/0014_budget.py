from django.db import migrations, models
import django.db.models.deletion
from django.core.validators import MinValueValidator
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0013_gradelevel_academicyear_is_current_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Budget',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('monthly_budget', models.DecimalField(decimal_places=2, default=0.0, max_digits=12, validators=[MinValueValidator(Decimal('0.00'))])),
                ('quarterly_budget', models.DecimalField(decimal_places=2, default=0.0, max_digits=12, validators=[MinValueValidator(Decimal('0.00'))])),
                ('annual_budget', models.DecimalField(decimal_places=2, default=0.0, max_digits=12, validators=[MinValueValidator(Decimal('0.00'))])),
                ('categories', models.JSONField(blank=True, default=list)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('academic_year', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='school.academicyear')),
                ('term', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='school.term')),
            ],
            options={
                'unique_together': {('academic_year', 'term')},
            },
        ),
    ]
