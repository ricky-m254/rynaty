from django.db import migrations, models
import django.db.models.deletion
from decimal import Decimal
from django.core.validators import MinValueValidator


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0024_invoiceadjustment_approval_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="InvoiceWriteOffRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12, validators=[MinValueValidator(Decimal("0.00"))])),
                ("reason", models.TextField()),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("APPROVED", "Approved"), ("REJECTED", "Rejected")], default="PENDING", max_length=20)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("review_notes", models.TextField(blank=True)),
                ("applied_adjustment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="source_writeoff_requests", to="school.invoiceadjustment")),
                ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="writeoff_requests", to="school.invoice")),
                ("requested_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="invoice_writeoff_requests", to="auth.user")),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_invoice_writeoffs", to="auth.user")),
            ],
            options={
                "ordering": ["-requested_at", "-id"],
            },
        ),
    ]
