from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0065_tenantsecret_encrypted_store"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="journalentry",
            index=models.Index(fields=["entry_date", "id"], name="school_jent_date_id_idx"),
        ),
        migrations.AddIndex(
            model_name="journalline",
            index=models.Index(fields=["account", "entry"], name="school_jlin_acct_entry_idx"),
        ),
    ]
