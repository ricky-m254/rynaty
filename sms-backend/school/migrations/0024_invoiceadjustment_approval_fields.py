from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0023_paymentgatewaytransaction_paymentgatewaywebhookevent_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoiceadjustment",
            name="review_notes",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="invoiceadjustment",
            name="reviewed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="invoiceadjustment",
            name="reviewed_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_invoice_adjustments", to="auth.user"),
        ),
        migrations.AddField(
            model_name="invoiceadjustment",
            name="status",
            field=models.CharField(choices=[("PENDING", "Pending"), ("APPROVED", "Approved"), ("REJECTED", "Rejected")], default="APPROVED", max_length=20),
        ),
    ]
