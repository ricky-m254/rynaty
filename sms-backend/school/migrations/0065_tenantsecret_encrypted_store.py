import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings
from django.db import migrations, models


def _derive_fernet_key(source: str) -> bytes:
    digest = hashlib.sha256(str(source).encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _key_sources():
    configured = list(getattr(settings, "DJANGO_TENANT_SECRET_KEYS", []) or [])
    if configured:
        return [str(item).strip() for item in configured if str(item).strip()]
    return [f"{settings.SECRET_KEY}:tenant-secret-store:v1"]


def _primary_fernet():
    source = _key_sources()[0]
    version = hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
    return Fernet(_derive_fernet_key(source)), version


def _encrypt(raw_value: str) -> tuple[str, str]:
    fernet, version = _primary_fernet()
    return fernet.encrypt(raw_value.encode("utf-8")).decode("utf-8"), version


def _store_secret(TenantSecret, key: str, value: str):
    normalized = str(value or "").strip()
    if not normalized:
        return
    ciphertext, version = _encrypt(normalized)
    TenantSecret.objects.update_or_create(
        key=key,
        defaults={
            "ciphertext": ciphertext,
            "key_version": version,
            "description": key,
        },
    )


def migrate_plaintext_secrets(apps, schema_editor):
    SchoolProfile = apps.get_model("school", "SchoolProfile")
    TenantSettings = apps.get_model("school", "TenantSettings")
    TenantSecret = apps.get_model("school", "TenantSecret")

    profile = SchoolProfile.objects.filter(is_active=True).order_by("id").first()
    if profile:
        if getattr(profile, "smtp_password", ""):
            _store_secret(TenantSecret, "school_profile:smtp_password", profile.smtp_password)
        if getattr(profile, "sms_api_key", ""):
            _store_secret(TenantSecret, "school_profile:sms_api_key", profile.sms_api_key)
        if getattr(profile, "whatsapp_api_key", ""):
            _store_secret(TenantSecret, "school_profile:whatsapp_api_key", profile.whatsapp_api_key)
        for field_name in ("smtp_password", "sms_api_key", "whatsapp_api_key"):
            if getattr(profile, field_name, ""):
                setattr(profile, field_name, "")
        profile.save(update_fields=["smtp_password", "sms_api_key", "whatsapp_api_key", "updated_at"])

    integration_secret_fields = {
        "integrations.mpesa": {"consumer_key", "consumer_secret", "passkey"},
        "integrations.stripe": {"secret_key", "webhook_secret"},
    }
    for setting_key, fields in integration_secret_fields.items():
        setting = TenantSettings.objects.filter(key=setting_key).first()
        config = setting.value if setting and isinstance(setting.value, dict) else None
        if not config:
            continue
        updated = dict(config)
        touched = False
        for field_name in fields:
            if field_name in updated and str(updated.get(field_name) or "").strip():
                _store_secret(
                    TenantSecret,
                    f"tenant_setting:{setting_key}:{field_name}",
                    updated[field_name],
                )
                updated.pop(field_name, None)
                touched = True
        if touched:
            setting.value = updated
            setting.save(update_fields=["value", "updated_at"])


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0064_schoolprofile_sensitive_field_validators"),
    ]

    operations = [
        migrations.CreateModel(
            name="TenantSecret",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=150, unique=True)),
                ("ciphertext", models.TextField()),
                ("key_version", models.CharField(max_length=32)),
                ("description", models.CharField(blank=True, max_length=255)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["key"],
                "verbose_name": "Tenant Secret",
                "verbose_name_plural": "Tenant Secrets",
            },
        ),
        migrations.RunPython(migrate_plaintext_secrets, migrations.RunPython.noop),
    ]
