from django.db import models
from django.utils import timezone
from datetime import date


class BiometricDevice(models.Model):
    DEVICE_TYPE_CHOICES = [
        ('ENTRY', 'Entry Only'),
        ('EXIT', 'Exit Only'),
        ('BOTH', 'Entry & Exit'),
    ]
    USE_CONTEXT_CHOICES = [
        ('gate',           'Gate / Entrance'),
        ('classroom',      'Classroom'),
        ('staff_terminal', 'Staff Terminal'),
    ]

    # Core identity
    device_id   = models.CharField(max_length=100, unique=True)
    name        = models.CharField(max_length=150)
    location    = models.CharField(max_length=200)
    device_type = models.CharField(max_length=10, choices=DEVICE_TYPE_CHOICES)
    use_context = models.CharField(
        max_length=20, choices=USE_CONTEXT_CHOICES, default='gate',
        help_text='Functional context: gate entry scanner, classroom scanner, or staff punch terminal',
    )

    # Network / connection (Dahua ASI6214S defaults pre-filled)
    ip_address  = models.GenericIPAddressField(null=True, blank=True,
                    help_text='Device IP address (Dahua factory default: 192.168.1.108)')
    port        = models.PositiveIntegerField(default=37777,
                    help_text='SDK/main port (Dahua default: 37777)')
    http_port   = models.PositiveIntegerField(default=80,
                    help_text='HTTP web port (Dahua default: 80)')
    rtsp_port   = models.PositiveIntegerField(default=37778,
                    help_text='RTSP stream port (Dahua default: 37778)')
    channel     = models.PositiveIntegerField(default=1,
                    help_text='Device channel number (Dahua default: 1)')

    # Credentials (Dahua factory defaults)
    username    = models.CharField(max_length=100, default='admin',
                    help_text='Device login username (Dahua default: admin)')
    password    = models.CharField(max_length=200, default='',
                    blank=True,
                    help_text='Device login password. Required for sync/export. '
                              'Dahua factory default is "admin123" — change it on the device and enter the new password here.')

    # Device identity (populated during auto-discovery)
    brand             = models.CharField(max_length=100, default='Dahua',
                          help_text='Device brand (Dahua / ZKTeco / Anviz / FingerTec / Suprema)')
    model             = models.CharField(max_length=150, blank=True,
                          help_text='Device model (e.g. ASI6214S)')
    serial_number     = models.CharField(max_length=100, blank=True)
    mac_address       = models.CharField(max_length=50, blank=True)
    firmware_version  = models.CharField(max_length=100, blank=True)
    discovery_method  = models.CharField(max_length=100, blank=True,
                          help_text='How the device was found (SADP / TCP / Manual)')

    # Operational
    api_key   = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    notes     = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.ip_address:
            return f"{self.name} ({self.ip_address}:{self.port})"
        return str(self.name)

    class Meta:
        ordering = ['location', 'name']


class SchoolShift(models.Model):
    PERSON_TYPE_CHOICES = [
        ('ALL', 'All'),
        ('STUDENT', 'Students Only'),
        ('STAFF', 'Staff Only'),
    ]
    name                 = models.CharField(max_length=100)
    person_type          = models.CharField(max_length=10, choices=PERSON_TYPE_CHOICES)
    expected_arrival     = models.TimeField()
    grace_period_minutes = models.PositiveIntegerField(default=15)
    expected_departure   = models.TimeField(null=True, blank=True)
    is_active            = models.BooleanField(default=True)
    notes                = models.TextField(blank=True)
    created_at           = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.name)


class PersonRegistry(models.Model):
    PERSON_TYPE_CHOICES = [
        ('STUDENT', 'Student'),
        ('TEACHER', 'Teaching Staff'),
        ('STAFF', 'Non-Teaching Staff'),
    ]
    fingerprint_id     = models.CharField(max_length=100, unique=True,
                           help_text='Primary biometric ID — also used as Dahua Employee No / UserID')
    # Dahua-specific identity fields
    card_no            = models.CharField(max_length=100, blank=True, db_index=True,
                           help_text='RFID card number (Dahua CardNo field)')
    dahua_user_id      = models.CharField(max_length=100, blank=True, db_index=True,
                           help_text='Dahua device UserID (EmployeeNoString). Leave blank to use fingerprint_id.')

    person_type  = models.CharField(max_length=10, choices=PERSON_TYPE_CHOICES)
    student      = models.ForeignKey('school.Student', null=True, blank=True, on_delete=models.SET_NULL)
    employee     = models.ForeignKey('hr.Employee',    null=True, blank=True, on_delete=models.SET_NULL)
    display_name = models.CharField(max_length=200)
    enrolled_at  = models.DateTimeField(auto_now_add=True)
    is_active    = models.BooleanField(default=True)
    notes        = models.TextField(blank=True)

    def __str__(self):
        return str(self.display_name)


class ClockEvent(models.Model):
    EVENT_TYPE_CHOICES = [
        ('IN',  'Clock In'),
        ('OUT', 'Clock Out'),
    ]
    person             = models.ForeignKey(PersonRegistry, on_delete=models.CASCADE, related_name='events')
    device             = models.ForeignKey(BiometricDevice, null=True, blank=True, on_delete=models.SET_NULL)
    event_type         = models.CharField(max_length=5, choices=EVENT_TYPE_CHOICES)
    timestamp          = models.DateTimeField(default=timezone.now)
    date               = models.DateField(default=date.today)
    is_late            = models.BooleanField(default=False)
    attendance_updated = models.BooleanField(default=False)
    notes              = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        name = self.person.display_name if self.person else 'Unknown'
        return f"{name} - {self.event_type} at {self.timestamp}"


# ── SmartPSS Lite Integration ─────────────────────────────────────────────────

class SmartPSSSource(models.Model):
    """
    Represents a SmartPSS Lite instance installed on a Windows PC at the school.
    SmartPSS Lite aggregates attendance from ALL connected Dahua devices into one
    central database and exposes a local REST API on port 8443 by default.

    Pull mode: backend calls the SmartPSS Lite REST API (requires network access).
    CSV mode:  user exports CSV from SmartPSS Lite and uploads via the portal.
    Both modes feed into the same ClockEvent pipeline.
    """
    name          = models.CharField(max_length=150,
                      help_text='Friendly label, e.g. "Main Office SmartPSS"')
    host          = models.CharField(max_length=255,
                      help_text='IP address or hostname of the Windows PC running SmartPSS Lite '
                                '(e.g. 192.168.1.10). Must be reachable from this server.')
    port          = models.PositiveIntegerField(default=8443,
                      help_text='SmartPSS Lite API port (default 8443)')
    use_https     = models.BooleanField(default=False,
                      help_text='Use HTTPS instead of HTTP for the SmartPSS Lite API')
    username      = models.CharField(max_length=100, default='admin')
    password      = models.CharField(max_length=200, default='', blank=True,
                      help_text='SmartPSS Lite login password. Required for sync. '
                                'Enter the password configured in SmartPSS Lite.')
    device_model  = models.CharField(max_length=100, blank=True, default='',
                      help_text='Dahua device model managed by this SmartPSS instance, '
                                'e.g. "AS16214S", "ASI7213X-T1", "ASI3214S"')

    sync_days_back = models.PositiveIntegerField(default=7,
                       help_text='How many days back to pull on each sync')
    is_active      = models.BooleanField(default=True)
    last_sync_at   = models.DateTimeField(null=True, blank=True)
    last_sync_result = models.TextField(blank=True,
                        help_text='JSON summary of the last sync result')
    notes          = models.TextField(blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.host}:{self.port})"

    class Meta:
        ordering = ['name']
        verbose_name        = 'SmartPSS Lite Source'
        verbose_name_plural = 'SmartPSS Lite Sources'


class SmartPSSImportLog(models.Model):
    """Records every CSV import or API sync from a SmartPSS Lite source."""
    SOURCE_TYPE_CHOICES = [
        ('API', 'API Pull'),
        ('CSV', 'CSV Upload'),
    ]
    source        = models.ForeignKey(SmartPSSSource, null=True, blank=True,
                      on_delete=models.SET_NULL, related_name='import_logs')
    source_type   = models.CharField(max_length=5, choices=SOURCE_TYPE_CHOICES)
    started_at    = models.DateTimeField(auto_now_add=True)
    finished_at   = models.DateTimeField(null=True, blank=True)
    records_found = models.IntegerField(default=0)
    records_saved = models.IntegerField(default=0)
    skipped       = models.IntegerField(default=0,
                      help_text='Records skipped (unknown person / duplicate)')
    errors        = models.IntegerField(default=0)
    error_detail  = models.TextField(blank=True)
    triggered_by  = models.CharField(max_length=150, blank=True,
                      help_text='Username or system trigger')

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        src = self.source.name if self.source else 'CSV'
        return f"{src} {self.source_type} @ {self.started_at:%Y-%m-%d %H:%M} ({self.records_saved} saved)"


# ── Phase 1: Raw Capture Log ──────────────────────────────────────────────────

class AttendanceCaptureLog(models.Model):
    """
    Raw log of every inbound scan from any device before identity resolution.
    Status lifecycle: pending → success | failed
    One log entry per POST to /api/attendance/capture/.
    """
    METHOD_CHOICES = [
        ('card',        'Card / RFID'),
        ('fingerprint', 'Fingerprint'),
        ('face',        'Face Recognition'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed',  'Failed'),
    ]

    device          = models.ForeignKey(
                        BiometricDevice, null=True, blank=True,
                        on_delete=models.SET_NULL, related_name='capture_logs',
                      )
    person          = models.ForeignKey(
                        PersonRegistry, null=True, blank=True,
                        on_delete=models.SET_NULL, related_name='capture_logs',
                      )
    method          = models.CharField(max_length=20, choices=METHOD_CHOICES)
    identifier      = models.CharField(
                        max_length=200,
                        help_text='Raw card UID / fingerprint ID / face template ID sent by the device',
                      )
    timestamp       = models.DateTimeField()
    status          = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    failure_reason  = models.CharField(max_length=500, blank=True)
    raw_payload     = models.JSONField(default=dict, blank=True,
                        help_text='Full request body for audit / debugging')
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes  = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['device', 'timestamp']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        who = self.person.display_name if self.person else 'Unknown'
        return f"{who} [{self.method}] {self.status} @ {self.timestamp}"
