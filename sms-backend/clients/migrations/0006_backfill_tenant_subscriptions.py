from django.db import migrations
from django.utils import timezone


def backfill_subscriptions(apps, schema_editor):
    Tenant = apps.get_model("clients", "Tenant")
    TenantSubscription = apps.get_model("clients", "TenantSubscription")

    for tenant in Tenant.objects.filter(subscription_plan__isnull=False):
        if TenantSubscription.objects.filter(tenant=tenant, is_current=True).exists():
            continue
        starts_on = tenant.trial_start or tenant.created_at.date() or timezone.now().date()
        trial_end = tenant.trial_end
        status = "TRIAL" if tenant.status == "TRIAL" else "ACTIVE"
        TenantSubscription.objects.create(
            tenant=tenant,
            plan=tenant.subscription_plan,
            billing_cycle="MONTHLY",
            status=status,
            starts_on=starts_on,
            trial_end=trial_end,
            next_billing_date=(trial_end if trial_end else starts_on),
            grace_period_days=7,
            is_current=True,
        )


def reverse_backfill(apps, schema_editor):
    TenantSubscription = apps.get_model("clients", "TenantSubscription")
    TenantSubscription.objects.filter(is_current=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("clients", "0005_subscriptioninvoice_tenantsubscription_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_subscriptions, reverse_backfill),
    ]
