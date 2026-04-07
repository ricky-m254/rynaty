from django.db import migrations


def seed_plans(apps, schema_editor):
    SubscriptionPlan = apps.get_model("clients", "SubscriptionPlan")
    plans = [
        {
            "code": "STARTER",
            "name": "Starter",
            "description": "Up to 200 students, core modules.",
            "monthly_price": "99.00",
            "annual_price": "990.00",
            "max_students": 200,
            "max_storage_gb": 5,
            "enabled_modules": ["CORE", "STUDENTS", "ACADEMICS", "FINANCE"],
        },
        {
            "code": "PROFESSIONAL",
            "name": "Professional",
            "description": "Up to 500 students, all modules.",
            "monthly_price": "299.00",
            "annual_price": "2990.00",
            "max_students": 500,
            "max_storage_gb": 20,
            "enabled_modules": [],
        },
        {
            "code": "ENTERPRISE",
            "name": "Enterprise",
            "description": "Up to 2000 students, all modules + custom.",
            "monthly_price": "799.00",
            "annual_price": "7990.00",
            "max_students": 2000,
            "max_storage_gb": 100,
            "enabled_modules": [],
        },
        {
            "code": "UNLIMITED",
            "name": "Unlimited",
            "description": "Unlimited students with high storage and white-label options.",
            "monthly_price": "0.00",
            "annual_price": "0.00",
            "max_students": 999999,
            "max_storage_gb": 500,
            "enabled_modules": [],
        },
    ]
    for plan in plans:
        SubscriptionPlan.objects.update_or_create(code=plan["code"], defaults=plan)


def unseed_plans(apps, schema_editor):
    SubscriptionPlan = apps.get_model("clients", "SubscriptionPlan")
    SubscriptionPlan.objects.filter(code__in=["STARTER", "PROFESSIONAL", "ENTERPRISE", "UNLIMITED"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("clients", "0003_subscriptionplan_tenant_activated_at_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_plans, unseed_plans),
    ]
