from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('clockin', '0005_add_smartpss_device_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='biometricdevice',
            name='use_context',
            field=models.CharField(
                choices=[
                    ('gate',           'Gate / Entrance'),
                    ('classroom',      'Classroom'),
                    ('staff_terminal', 'Staff Terminal'),
                ],
                default='gate',
                help_text='Functional context: gate entry scanner, classroom scanner, or staff punch terminal',
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name='AttendanceCaptureLog',
            fields=[
                ('id',             models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('method',         models.CharField(choices=[('card', 'Card / RFID'), ('fingerprint', 'Fingerprint'), ('face', 'Face Recognition')], max_length=20)),
                ('identifier',     models.CharField(help_text='Raw card UID / fingerprint ID / face template ID sent by the device', max_length=200)),
                ('timestamp',      models.DateTimeField()),
                ('status',         models.CharField(choices=[('pending', 'Pending'), ('success', 'Success'), ('failed', 'Failed')], default='pending', max_length=10)),
                ('failure_reason', models.CharField(blank=True, max_length=500)),
                ('raw_payload',    models.JSONField(blank=True, default=dict, help_text='Full request body for audit / debugging')),
                ('created_at',     models.DateTimeField(auto_now_add=True)),
                ('device',         models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='capture_logs', to='clockin.biometricdevice')),
                ('person',         models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='capture_logs', to='clockin.personregistry')),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='attendancecapturelog',
            index=models.Index(fields=['timestamp'], name='clockin_cap_ts_idx'),
        ),
        migrations.AddIndex(
            model_name='attendancecapturelog',
            index=models.Index(fields=['device', 'timestamp'], name='clockin_cap_dev_ts_idx'),
        ),
        migrations.AddIndex(
            model_name='attendancecapturelog',
            index=models.Index(fields=['status'], name='clockin_cap_status_idx'),
        ),
    ]
