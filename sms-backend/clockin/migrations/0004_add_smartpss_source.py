from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('clockin', '0003_add_dahua_card_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='SmartPSSSource',
            fields=[
                ('id',              models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name',            models.CharField(help_text='Friendly label, e.g. "Main Office SmartPSS"', max_length=150)),
                ('host',            models.CharField(help_text='IP address or hostname of the Windows PC running SmartPSS Lite (e.g. 192.168.1.10). Must be reachable from this server.', max_length=255)),
                ('port',            models.PositiveIntegerField(default=8443, help_text='SmartPSS Lite API port (default 8443)')),
                ('use_https',       models.BooleanField(default=False, help_text='Use HTTPS instead of HTTP for the SmartPSS Lite API')),
                ('username',        models.CharField(default='admin', max_length=100)),
                ('password',        models.CharField(default='admin123', max_length=200)),
                ('sync_days_back',  models.PositiveIntegerField(default=7, help_text='How many days back to pull on each sync')),
                ('is_active',       models.BooleanField(default=True)),
                ('last_sync_at',    models.DateTimeField(blank=True, null=True)),
                ('last_sync_result', models.TextField(blank=True, help_text='JSON summary of the last sync result')),
                ('notes',           models.TextField(blank=True)),
                ('created_at',      models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name':        'SmartPSS Lite Source',
                'verbose_name_plural': 'SmartPSS Lite Sources',
                'ordering':            ['name'],
            },
        ),
        migrations.CreateModel(
            name='SmartPSSImportLog',
            fields=[
                ('id',            models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source',        models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='import_logs', to='clockin.smartpsssource')),
                ('source_type',   models.CharField(choices=[('API', 'API Pull'), ('CSV', 'CSV Upload')], max_length=5)),
                ('started_at',    models.DateTimeField(auto_now_add=True)),
                ('finished_at',   models.DateTimeField(blank=True, null=True)),
                ('records_found', models.IntegerField(default=0)),
                ('records_saved', models.IntegerField(default=0)),
                ('skipped',       models.IntegerField(default=0, help_text='Records skipped (unknown person / duplicate)')),
                ('errors',        models.IntegerField(default=0)),
                ('error_detail',  models.TextField(blank=True)),
                ('triggered_by',  models.CharField(blank=True, help_text='Username or system trigger', max_length=150)),
            ],
            options={
                'ordering': ['-started_at'],
            },
        ),
    ]
