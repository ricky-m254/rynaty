from django.db import migrations, models
import django.db.models.deletion
from decimal import Decimal
from django.core.validators import MinValueValidator


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0022_chartofaccount_journalentry_journalline_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentGatewayTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(default="manual", max_length=40)),
                ("external_id", models.CharField(max_length=120, unique=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12, validators=[MinValueValidator(Decimal("0.00"))])),
                ("currency", models.CharField(default="KES", max_length=10)),
                ("status", models.CharField(choices=[("INITIATED", "Initiated"), ("PENDING", "Pending"), ("SUCCEEDED", "Succeeded"), ("FAILED", "Failed"), ("REFUNDED", "Refunded")], default="PENDING", max_length=20)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("is_reconciled", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("invoice", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="school.invoice")),
                ("student", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="school.student")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="PaymentGatewayWebhookEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_id", models.CharField(max_length=120, unique=True)),
                ("provider", models.CharField(max_length=40)),
                ("event_type", models.CharField(max_length=80)),
                ("signature", models.CharField(blank=True, max_length=255)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("processed", models.BooleanField(default=False)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("error", models.TextField(blank=True)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-received_at"],
            },
        ),
        migrations.CreateModel(
            name="BankStatementLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("statement_date", models.DateField()),
                ("value_date", models.DateField(blank=True, null=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("reference", models.CharField(blank=True, max_length=160)),
                ("narration", models.TextField(blank=True)),
                ("source", models.CharField(default="manual", max_length=40)),
                ("status", models.CharField(choices=[("UNMATCHED", "Unmatched"), ("MATCHED", "Matched"), ("CLEARED", "Cleared"), ("IGNORED", "Ignored")], default="UNMATCHED", max_length=20)),
                ("imported_at", models.DateTimeField(auto_now_add=True)),
                ("matched_gateway_transaction", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="statement_matches", to="school.paymentgatewaytransaction")),
                ("matched_payment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="statement_matches", to="school.payment")),
            ],
            options={
                "ordering": ["-statement_date", "-id"],
            },
        ),
    ]
