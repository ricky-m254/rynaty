import re
import base64
import json
import socket
import time
import urllib.request
import urllib.error
import urllib.parse
import concurrent.futures
import ipaddress


def _validate_device_ip(ip_str: str) -> str:
    """Return the canonical IP string if valid, raise ValueError otherwise.

    Clockin devices are Dahua hardware on the school LAN, so private addresses
    are intentional and expected.  This function only guards against non-IP
    strings (e.g. hostnames that could be manipulated for DNS rebinding attacks)
    and ensures the value is a properly-formed IPv4/IPv6 address before use in
    outbound HTTP requests.
    """
    try:
        return str(ipaddress.ip_address(ip_str.strip()))
    except ValueError:
        raise ValueError(f'Invalid device IP address: {ip_str!r}')


from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from datetime import date, datetime, timedelta
from .models import (
    BiometricDevice, SchoolShift, PersonRegistry, ClockEvent,
    SmartPSSSource, SmartPSSImportLog, AttendanceCaptureLog,
)
from .serializers import (
    BiometricDeviceSerializer,
    SchoolShiftSerializer,
    PersonRegistrySerializer,
    ClockEventSerializer,
    SmartPSSSourceSerializer,
    SmartPSSImportLogSerializer,
    AttendanceCaptureLogSerializer,
)
from .smartpss_client import (
    SmartPSSLiteClient, SmartPSSError,
    normalise_attend_status, parse_smartpss_time, parse_smartpss_csv,
)
from school.permissions import HasModuleAccess
from django.db.models import Q

import logging

logger = logging.getLogger(__name__)

# ── DBMA cross-domain imports removed from module level ──────────────────────
# school.models, hr.models, communication.models are accessed ONLY through
# infrastructure layer services:
#   clockin/infrastructure/services/attendance_service.py   (school + hr)
#   clockin/infrastructure/services/notification_service.py (communication)
# This fixes DBMA Rule 4.2 (no direct cross-domain model imports at module level)

# Ports associated with known biometric device brands.
# PRIMARY: Dahua ASI6214S — probed first on its default ports.
BIOMETRIC_PROBE_PORTS = [
    # ── PRIMARY: Dahua ASI6214S ───────────────────────────────
    (37777, 'Dahua ASI6214S',         'Fingerprint / RFID'),  # Dahua SDK (primary)
    (37778, 'Dahua ASI6214S (RTSP)',  'Fingerprint / RFID'),  # Dahua stream port
    (80,    'Dahua ASI6214S (Web)',   'Web / HTTP'),           # Dahua web interface
    # ── Other Dahua access control series ─────────────────────
    (8000,  'Dahua (alt port)',       'Fingerprint / RFID'),
    # ── ZKTeco series ────────────────────────────────────────
    (4370,  'ZKTeco',                'Fingerprint / RFID'),   # ZKPCP protocol
    (5005,  'ZKTeco (alt port)',     'Fingerprint / RFID'),
    # ── Anviz series ─────────────────────────────────────────
    (5010,  'Anviz',                 'Fingerprint / RFID'),
    (6000,  'Anviz (alt port)',      'Fingerprint / RFID'),
    # ── FingerTec ────────────────────────────────────────────
    (4008,  'FingerTec',             'Fingerprint'),
    # ── Suprema ──────────────────────────────────────────────
    (9922,  'Suprema BioStar',       'Fingerprint'),
    # ── Generic HTTP terminals ────────────────────────────────
    (8080,  'HTTP Biometric Terminal', 'Web-based'),
]

def _tcp_probe(ip: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


# ── Dahua SADP (Smart Adaptive Discovery Protocol) ────────────────────────────
# Standard 32-byte SADP v2 broadcast discovery packet
_DAHUA_SADP_PACKET = b'\x42\x44\x00\x05\x00\x20' + b'\x00' * 26


def _dahua_sadp_discover(sadp_timeout: float = 3.0) -> list:
    """
    Broadcast the Dahua SADP discovery packet to UDP port 37020.
    Devices on the LAN (ASI6214S, IPC, NVR, etc.) reply with XML
    containing their model, serial and IP — no target IP needed.
    """
    results = []
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(sadp_timeout)
        sock.bind(('', 0))
        sock.sendto(_DAHUA_SADP_PACKET, ('255.255.255.255', 37020))
        deadline = time.monotonic() + sadp_timeout
        while time.monotonic() < deadline:
            try:
                data, addr = sock.recvfrom(8192)
                text = data.decode('utf-8', errors='ignore')
                model  = _xml_field(text, 'DeviceModel') or _xml_field(text, 'DeviceType') or 'Dahua Device'
                serial = _xml_field(text, 'SN') or ''
                mac    = _xml_field(text, 'MACAddress') or ''
                results.append({'ip': addr[0], 'model': model, 'serial': serial, 'mac': mac})
            except socket.timeout:
                break
    except Exception:
        logger.warning("Caught and logged", exc_info=True)
    finally:
        try:
            sock.close()
        except Exception:
            logger.warning("Caught and logged", exc_info=True)
    return results


def _xml_field(text: str, tag: str) -> str:
    """Extract the first <Tag>value</Tag> from an XML string."""
    m = re.search(rf'<{tag}>(.*?)</{tag}>', text, re.DOTALL)
    return m.group(1).strip() if m else ''


def _dahua_http_identify(ip: str, timeout: float = 1.5) -> dict:
    """
    Query the Dahua CGI API on port 80 to get device type and model.
    Works without authentication on most Dahua access control devices.
    Returns a dict with 'model' and/or 'type' when successful.
    """
    # Validate that ip is a properly-formed IP address before embedding it in
    # a URL — prevents hostname-injection / DNS rebinding via the device config.
    try:
        ip = _validate_device_ip(ip)
    except ValueError:
        return {}

    info: dict = {}
    for action, key in [
        ('getDeviceType',                        'type'),
        ('getProductDefinition&name=ProductModel', 'model'),
    ]:
        try:
            url = f'http://{ip}/cgi-bin/magicBox.cgi?action={action}'
            req = urllib.request.Request(url, headers={'User-Agent': 'SmartCampus/1.0'})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode('utf-8', errors='ignore')
                m = re.search(r'(?:type|value)=(.+)', body)
                if m:
                    info[key] = m.group(1).strip()
        except Exception:
            logger.warning("Caught and logged", exc_info=True)
    return info

def _notify_admins(title, message, priority='Important', action_url=''):
    """
    Compatibility helper for non-clockin modules that still broadcast admin alerts.
    Scan processing no longer uses this path directly.
    """
    try:
        from communication.models import Notification
        from school.models import UserProfile

        admin_users = UserProfile.objects.filter(
            role__name__in=['ADMIN', 'TENANT_SUPER_ADMIN'],
            user__is_active=True,
        ).select_related('user')
        for up in admin_users:
            Notification.objects.create(
                recipient=up.user,
                notification_type='System',
                title=title,
                message=message,
                priority=priority,
                action_url=action_url,
                delivery_status='Sent',
            )
    except Exception:
        logger.warning("Caught and logged", exc_info=True)

class ClockInModuleMixin:
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "CLOCKIN"

class BiometricDeviceViewSet(ClockInModuleMixin, viewsets.ModelViewSet):
    queryset = BiometricDevice.objects.all()
    serializer_class = BiometricDeviceSerializer

class SchoolShiftViewSet(ClockInModuleMixin, viewsets.ModelViewSet):
    queryset = SchoolShift.objects.all()
    serializer_class = SchoolShiftSerializer

class PersonRegistryViewSet(ClockInModuleMixin, viewsets.ModelViewSet):
    queryset = PersonRegistry.objects.all()
    serializer_class = PersonRegistrySerializer

class ClockEventViewSet(ClockInModuleMixin, viewsets.ReadOnlyModelViewSet):
    queryset = ClockEvent.objects.all()
    serializer_class = ClockEventSerializer
    filterset_fields = ['date', 'person__person_type']

class ScanView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        fingerprint_id = request.data.get('fingerprint_id')
        device_id = request.data.get('device_id')
        timestamp_str = request.data.get('timestamp')
        
        # 1. Device Auth (if device_id provided and not kiosk route)
        device = None
        if device_id:
            device = BiometricDevice.objects.filter(device_id=device_id, is_active=True).first()
            if not device:
                return Response({"error": "Device not found or inactive"}, status=status.HTTP_404_NOT_FOUND)
            
            # Simple X-Device-Key check if not kiosk
            if 'kiosk' not in request.path:
                api_key = request.headers.get('X-Device-Key')
                if api_key != device.api_key:
                    return Response({"error": "Invalid Device Key"}, status=status.HTTP_401_UNAUTHORIZED)
            
            device.last_seen = timezone.now()
            device.save(update_fields=['last_seen'])

        # 2. Lookup Person
        person = PersonRegistry.objects.filter(fingerprint_id=fingerprint_id, is_active=True).first()
        if not person:
            return Response({"error": "Person not found in registry"}, status=status.HTTP_404_NOT_FOUND)

        # 3. Handle Timestamp
        if timestamp_str:
            try:
                event_timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except ValueError:
                event_timestamp = timezone.now()
        else:
            event_timestamp = timezone.now()

        # 4. Delegate to the shared application service.
        # Raw scan ingestion intentionally keeps deduplication disabled so
        # kiosk/device retries preserve the endpoint's existing behaviour.
        event = _process_scan_event(
            person,
            device,
            event_timestamp,
            direction='auto',
            deduplicate=False,
        )

        return Response({
            "event_type": event.event_type,
            "is_late": event.is_late,
            "person": {
                "display_name": person.display_name,
                "person_type": person.person_type,
                "fingerprint_id": person.fingerprint_id,
                "admission_number_or_employee_id": person.student.admission_number if person.student else (person.employee.employee_id if person.employee else None)
            },
            "message": f"Successfully clocked {event.event_type.lower()}"
        }, status=status.HTTP_201_CREATED)

class DashboardView(ClockInModuleMixin, APIView):
    def get(self, request):
        today = date.today()
        # Stats
        students_in = ClockEvent.objects.filter(date=today, event_type='IN', person__person_type='STUDENT').count()
        students_late = ClockEvent.objects.filter(date=today, event_type='IN', person__person_type='STUDENT', is_late=True).count()
        staff_in = ClockEvent.objects.filter(date=today, event_type='IN', person__person_type__in=['TEACHER', 'STAFF']).count()
        staff_late = ClockEvent.objects.filter(date=today, event_type='IN', person__person_type__in=['TEACHER', 'STAFF'], is_late=True).count()
        
        recent_events = ClockEvent.objects.all()[:20]
        serializer = ClockEventSerializer(recent_events, many=True)
        
        return Response({
            "students_in": students_in,
            "students_late": students_late,
            "staff_in": staff_in,
            "staff_late": staff_late,
            "recent_events": serializer.data
        })

class RealtimeView(ClockInModuleMixin, APIView):
    def get(self, request):
        today = date.today()
        scanned_today = PersonRegistry.objects.filter(events__date=today).distinct()
        results = []
        for person in scanned_today:
            last_event = ClockEvent.objects.filter(person=person, date=today).order_by('-timestamp').first()
            if last_event and last_event.event_type == 'IN':
                results.append({
                    "name": person.display_name,
                    "role": person.person_type,
                    "person_type": person.person_type,
                    "time_in": last_event.timestamp
                })
        return Response(results)


# ── Shared helper: process one scan event ─────────────────────────────────────
def _process_scan_event(person, device, event_timestamp, direction='auto', deduplicate=True):
    """
    Phase 4 thin adapter — delegates to ClockInService application layer.

    Signature and return type are preserved for full backward compatibility
    with all Dahua / SmartPSS views that call this function.

    direction: 'in' | 'out' | 'auto'
    deduplicate: False only for raw scan ingestion that must preserve retries
    Returns:   ClockEvent ORM instance, or None on duplicate.
    """
    from clockin.application.services.clock_in_service import ClockInService
    return ClockInService().process_scan(
        person,
        device,
        event_timestamp,
        direction,
        deduplicate=deduplicate,
    )

def _lookup_person(card_no=None, user_id=None, fingerprint_id=None):
    """
    Find a PersonRegistry record using Dahua's card/user fields.
    Priority: card_no → dahua_user_id → fingerprint_id (direct match)
    """
    if card_no:
        p = PersonRegistry.objects.filter(card_no=card_no, is_active=True).first()
        if p:
            return p
    if user_id:
        p = (PersonRegistry.objects.filter(dahua_user_id=user_id, is_active=True).first() or
             PersonRegistry.objects.filter(fingerprint_id=user_id, is_active=True).first())
        if p:
            return p
    if fingerprint_id:
        return PersonRegistry.objects.filter(fingerprint_id=fingerprint_id, is_active=True).first()
    return None


def _parse_dahua_time(time_str):
    """
    Phase 4 thin adapter — delegates to infrastructure/dahua/utils.parse_device_time.
    Signature preserved for full backward compatibility.
    """
    from clockin.infrastructure.dahua.utils import parse_device_time
    return parse_device_time(time_str)


# ── Dahua ASI6214S HTTP Upload webhook ────────────────────────────────────────
@method_decorator(csrf_exempt, name='dispatch')
class DahuaEventView(APIView):
    """
    POST /clockin/dahua/event/

    Receives HTTP Upload events from a Dahua ASI6214S (or any Dahua access
    control device that supports HTTP Upload / Alarm Output push).

    Authentication (any one of these, checked in order):
      1. Query param:   ?key=<api_key>
      2. Header:        X-Device-Key: <api_key>
      3. Basic Auth:    Authorization: Basic base64(admin:<api_key>)
      4. IP match:      The device's ip_address must match REMOTE_ADDR

    Supported Dahua event formats
    ─────────────────────────────
    Format A — AccessControl / AttendanceRecord (JSON body):
      { "Events": [{ "Code": "AccessControl", "Data": { "CardNo": "...",
        "UserID": "...", "Direction": 0, "Time": "2026-03-22 12:00:00" }}] }

    Format B — Records push:
      { "Records": [{ "CardNo": "...", "EmployeeNoString": "...",
        "Punch": 0, "Time": "2026-03-22 12:00:00" }] }

    Format C — Heartbeat (device keep-alive):
      {}  →  returns HTTP 200 immediately.

    Device configuration (Dahua web UI):
      Setup → Network → Integration Protocol → HTTP Subscription
        URL:    https://<your-server>/api/clockin/dahua/event/?key=<api_key>
        Method: POST
        Format: JSON

    The device's API key is the one shown in the Devices page (Webhook Config section).
    """
    permission_classes = [permissions.AllowAny]

    def _authenticate_device(self, request):
        """Return (BiometricDevice, error_response) — one of them is None."""
        # 1. Query param
        key = request.query_params.get('key') or request.query_params.get('api_key')
        # 2. Header
        if not key:
            key = request.headers.get('X-Device-Key')
        # 3. Basic Auth
        if not key:
            auth = request.headers.get('Authorization', '')
            if auth.lower().startswith('basic '):
                try:
                    decoded = base64.b64decode(auth[6:]).decode('utf-8')
                    _, _, pw = decoded.partition(':')
                    key = pw
                except Exception:
                    logger.warning("Caught and logged", exc_info=True)

        if key:
            device = BiometricDevice.objects.filter(api_key=key, is_active=True).first()
            if device:
                return device, None
            return None, Response({'error': 'Invalid API key.'}, status=status.HTTP_401_UNAUTHORIZED)

        # 4. IP address fallback
        remote_ip = (
            request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or
            request.META.get('REMOTE_ADDR', '')
        )
        if remote_ip:
            device = BiometricDevice.objects.filter(ip_address=remote_ip, is_active=True).first()
            if device:
                return device, None

        return None, Response({'error': 'Authentication required. Add ?key=<api_key> to the URL.'}, status=status.HTTP_401_UNAUTHORIZED)

    def post(self, request):
        # ── Heartbeat / keep-alive (empty body) ──
        body = request.data
        if not body:
            return Response({'ok': True, 'message': 'Heartbeat received.'})

        # ── Authenticate ──
        device, err = self._authenticate_device(request)
        if err:
            return err

        device.last_seen = timezone.now()
        device.save(update_fields=['last_seen'])

        processed = []
        errors = []

        # ── Parse Format A: Events array (AccessControl / AttendanceRecord) ──
        events = body.get('Events') or body.get('events') or []
        for ev in events:
            ev_code = ev.get('Code', '')
            if ev_code not in ('AccessControl', 'AttendanceRecord', 'AlarmLocal', ''):
                continue
            data = ev.get('Data') or ev.get('data') or ev
            try:
                result = self._handle_event_data(data, device)
                if result:
                    processed.append(result)
            except Exception as e:
                errors.append(str(e))

        # ── Parse Format B: Records array ──
        records = body.get('Records') or body.get('records') or []
        for rec in records:
            try:
                result = self._handle_record_data(rec, device)
                if result:
                    processed.append(result)
            except Exception as e:
                errors.append(str(e))

        # ── Single event in root body (some Dahua firmware versions) ──
        if not events and not records and body:
            # Try root-level event data
            try:
                result = self._handle_event_data(body, device)
                if result:
                    processed.append(result)
            except Exception:
                logger.warning("Caught and logged", exc_info=True)

        return Response({
            'ok': True,
            'processed': len(processed),
            'errors': errors,
            'events': [{'person': e['person'], 'event_type': e['event_type']} for e in processed],
        })

    def _handle_event_data(self, data, device):
        """Parse Dahua AccessControl event data dict."""
        card_no   = str(data.get('CardNo') or data.get('cardNo') or '').strip()
        user_id   = str(data.get('UserID') or data.get('userId') or
                        data.get('EmployeeNoString') or data.get('employeeNoString') or '').strip()
        time_str  = data.get('Time') or data.get('time') or data.get('Timestamp') or ''
        direction_val = data.get('Direction', data.get('direction', -1))

        if not card_no and not user_id:
            return None  # No identity info — skip (could be a door open event)

        person = _lookup_person(card_no=card_no or None, user_id=user_id or None)
        if not person:
            # Auto-create stub if we have a name (optional — disabled by default)
            return None

        direction = 'in' if direction_val == 0 else ('out' if direction_val == 1 else 'auto')
        event_timestamp = _parse_dahua_time(time_str)
        event = _process_scan_event(person, device, event_timestamp, direction=direction)
        return {
            'person': person.display_name,
            'event_type': event.event_type,
            'is_late': event.is_late,
        }

    def _handle_record_data(self, rec, device):
        """Parse Dahua Records push format."""
        card_no   = str(rec.get('CardNo') or rec.get('cardNo') or '').strip()
        user_id   = str(rec.get('EmployeeNoString') or rec.get('employeeNoString') or
                        rec.get('UserID') or '').strip()
        time_str  = rec.get('Time') or rec.get('time') or ''
        punch     = rec.get('Punch', rec.get('punch', -1))  # 0=IN, 1=OUT

        if not card_no and not user_id:
            return None

        person = _lookup_person(card_no=card_no or None, user_id=user_id or None)
        if not person:
            return None

        direction = 'in' if punch == 0 else ('out' if punch == 1 else 'auto')
        event_timestamp = _parse_dahua_time(time_str)
        event = _process_scan_event(person, device, event_timestamp, direction=direction)
        return {
            'person': person.display_name,
            'event_type': event.event_type,
            'is_late': event.is_late,
        }


# ── Dahua attendance sync (pull from device HTTP API) ─────────────────────────
class DahuaSyncView(ClockInModuleMixin, APIView):
    """
    POST /clockin/dahua/{device_id}/sync/
    Body: { "date": "2026-03-22" }   (optional — defaults to today)

    Connects to the Dahua device's HTTP API and pulls attendance records
    for the given date, then creates ClockEvents for any scans not yet in DB.

    Requires the device to have ip_address, username, and password configured.
    Works for Dahua ASI6214S with HTTP API enabled (port 80 accessible).
    """
    module_key = "CLOCKIN"

    def post(self, request, device_id):
        try:
            device = BiometricDevice.objects.get(pk=device_id, is_active=True)
        except BiometricDevice.DoesNotExist:
            return Response({'error': 'Device not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not device.ip_address:
            return Response({'error': 'Device has no IP address configured.'}, status=status.HTTP_400_BAD_REQUEST)

        sync_date_str = request.data.get('date', str(date.today()))
        try:
            sync_date = datetime.strptime(sync_date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

        start_time = f"{sync_date} 00:00:00"
        end_time   = f"{sync_date} 23:59:59"

        try:
            ip = _validate_device_ip(device.ip_address)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        port     = device.http_port or 80
        username = device.username or 'admin'
        # Do not fall back to a hardcoded credential; require the password to be
        # configured on the BiometricDevice record.
        password = device.password or ''
        if not password:
            return Response(
                {'error': 'Device password is not configured. Please set it in the device settings.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # URL-encode datetime strings so spaces become %20 (urllib rejects raw spaces)
        qs_punch = urllib.parse.urlencode({
            'action': 'getAllRecords',
            'StartTime': start_time,
            'EndTime': end_time,
        })
        qs_finder = urllib.parse.urlencode({
            'action': 'find',
            'name': 'AttendanceRecord',
            'StartTime': start_time,
            'EndTime': end_time,
        })

        # Dahua HTTP API endpoint for attendance records
        urls_to_try = [
            f'http://{ip}:{port}/cgi-bin/attendancePunchRecord.cgi?{qs_punch}',
            f'http://{ip}:{port}/cgi-bin/recordFinder.cgi?{qs_finder}',
        ]

        raw_text = None
        last_error = ''
        for url in urls_to_try:
            try:
                auth_bytes = base64.b64encode(f'{username}:{password}'.encode()).decode()
                req = urllib.request.Request(url, headers={
                    'Authorization': f'Basic {auth_bytes}',
                    'User-Agent': 'SmartCampus/1.0',
                })
                with urllib.request.urlopen(req, timeout=10) as resp:
                    raw_text = resp.read().decode('utf-8', errors='ignore')
                break
            except urllib.error.HTTPError as e:
                last_error = f'HTTP {e.code}: {e.reason}'
            except Exception as e:
                last_error = str(e)

        if raw_text is None:
            return Response({
                'error': f'Could not connect to device at {ip}:{port}. {last_error}',
                'hint': 'Ensure the device web UI is reachable at this IP and the credentials are correct.',
            }, status=status.HTTP_502_BAD_GATEWAY)

        # Parse Dahua CGI response (key=value lines or JSON)
        records_created = 0
        records_skipped = 0
        parse_errors    = []

        # Try JSON first
        try:
            data = json.loads(raw_text)
            records = data.get('Records') or data.get('records') or []
            for rec in records:
                try:
                    card_no  = str(rec.get('CardNo') or '').strip()
                    user_id  = str(rec.get('EmployeeNoString') or rec.get('UserID') or '').strip()
                    time_str = rec.get('Time') or rec.get('PunchTime') or ''
                    punch    = rec.get('Punch', -1)
                    person = _lookup_person(card_no=card_no or None, user_id=user_id or None)
                    if not person:
                        records_skipped += 1
                        continue
                    event_timestamp = _parse_dahua_time(time_str)
                    # Dedup: skip if event already exists within 1 minute
                    exists = ClockEvent.objects.filter(
                        person=person, date=event_timestamp.date(),
                        timestamp__range=(event_timestamp - timedelta(minutes=1), event_timestamp + timedelta(minutes=1))
                    ).exists()
                    if exists:
                        records_skipped += 1
                        continue
                    direction = 'in' if punch == 0 else ('out' if punch == 1 else 'auto')
                    _process_scan_event(person, device, event_timestamp, direction=direction)
                    records_created += 1
                except Exception as e:
                    parse_errors.append(str(e))
        except json.JSONDecodeError:
            # Fall back: Dahua CGI key=value text format
            # records.item[0].CardNo=123456\nrecords.item[0].Time=2026-03-22 08:00:00\n...
            items: dict = {}
            for line in raw_text.splitlines():
                line = line.strip()
                if '=' not in line:
                    continue
                key, _, val = line.partition('=')
                m = re.match(r'records?\.item\[(\d+)\]\.(.+)', key.strip())
                if m:
                    idx, field = m.group(1), m.group(2)
                    if idx not in items:
                        items[idx] = {}
                    items[idx][field] = val.strip()

            for rec in items.values():
                try:
                    card_no  = rec.get('CardNo', '')
                    user_id  = rec.get('EmployeeNoString') or rec.get('UserID', '')
                    time_str = rec.get('Time') or rec.get('PunchTime', '')
                    punch    = int(rec.get('Punch', '-1'))
                    person = _lookup_person(card_no=card_no or None, user_id=user_id or None)
                    if not person:
                        records_skipped += 1
                        continue
                    event_timestamp = _parse_dahua_time(time_str)
                    exists = ClockEvent.objects.filter(
                        person=person, date=event_timestamp.date(),
                        timestamp__range=(event_timestamp - timedelta(minutes=1), event_timestamp + timedelta(minutes=1))
                    ).exists()
                    if exists:
                        records_skipped += 1
                        continue
                    direction = 'in' if punch == 0 else ('out' if punch == 1 else 'auto')
                    _process_scan_event(person, device, event_timestamp, direction=direction)
                    records_created += 1
                except Exception as e:
                    parse_errors.append(str(e))

        device.last_seen = timezone.now()
        device.save(update_fields=['last_seen'])

        return Response({
            'ok': True,
            'date': str(sync_date),
            'records_created': records_created,
            'records_skipped': records_skipped,
            'parse_errors': parse_errors[:10],
        })


class DeviceDiscoverView(APIView):
    """
    POST /clockin/devices/discover/
    Body: { "ip_prefix": "192.168.1", "timeout": 0.5, "sadp_timeout": 3 }

    Phase 1 — Dahua SADP broadcast (UDP 37020):
        Broadcasts a discovery packet; Dahua devices reply with model/serial/MAC.

    Phase 2 — TCP port scan across ip_prefix.1–254 (64 threads, pure network I/O):
        No database access inside worker threads — django-tenants stores the
        active schema as a thread-local which is NOT inherited by spawned threads.
        All DB work happens in the main thread AFTER the pool completes.

    Results are de-duplicated by device_id and returned together.
    """
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "CLOCKIN"

    def post(self, request):
        try:
            ip_prefix    = (request.data.get('ip_prefix') or '').strip()
            timeout      = min(max(float(request.data.get('timeout',      0.5)), 0.1), 3.0)
            sadp_timeout = min(max(float(request.data.get('sadp_timeout', 3.0)), 1.0), 10.0)
        except (ValueError, TypeError):
            return Response({'detail': 'Invalid parameter values.'}, status=status.HTTP_400_BAD_REQUEST)

        # Auto-strip: "192.168.1.108" → "192.168.1"
        parts = ip_prefix.split('.')
        if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
            parts = parts[:3]
            ip_prefix = '.'.join(parts)
        if len(parts) != 3 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
            return Response(
                {'detail': 'ip_prefix must be like "192.168.1" (first 3 octets). '
                           'You can paste a full IP like "192.168.1.108" — the last octet is stripped automatically.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Phase 1: Dahua SADP broadcast (main thread, no issues) ─────────
        sadp_hits  = _dahua_sadp_discover(sadp_timeout=sadp_timeout)
        sadp_by_ip = {h['ip']: h for h in sadp_hits}

        # ── Phase 2: TCP port scan — PURE NETWORK I/O, no DB ───────────────
        # worker: only socket calls — no ORM, no django imports
        def probe_host(last_octet: int) -> list:
            ip   = f"{ip_prefix}.{last_octet}"
            hits = []
            for port, brand, tech in BIOMETRIC_PROBE_PORTS:
                if not _tcp_probe(ip, port, timeout):
                    continue

                model  = ''
                serial = ''
                method = 'TCP Port Probe'

                # HTTP identification for Dahua port 80 (urllib only, no ORM)
                if port == 80:
                    http_info = _dahua_http_identify(ip, timeout=min(timeout * 2, 2.0))
                    if http_info:
                        model  = http_info.get('model', '')
                        method = 'TCP + HTTP Identified'
                        brand  = f"Dahua {model}" if model else brand

                # Enrich from SADP if IP was seen
                if ip in sadp_by_ip:
                    sadp   = sadp_by_ip[ip]
                    model  = model  or sadp.get('model', '')
                    serial = serial or sadp.get('serial', '')
                    method = 'SADP + TCP confirmed'

                hits.append({
                    'ip':               ip,
                    'port':             port,
                    'brand':            brand,
                    'model':            model,
                    'serial':           serial,
                    'mac':              '',
                    'technology':       tech,
                    'device_id':        f"{ip}:{port}",
                    'discovery_method': method,
                })
            return hits

        # Collect raw hits (no DB, thread-safe)
        raw_hits: list = []
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=64) as pool:
                futures = [pool.submit(probe_host, i) for i in range(1, 255)]
                for future in concurrent.futures.as_completed(futures, timeout=65):
                    try:
                        raw_hits.extend(future.result())
                    except Exception:
                        logger.warning("Caught and logged", exc_info=True)
        except concurrent.futures.TimeoutError:
            pass  # Return whatever was found before timeout
        except Exception:
            logger.warning("Caught and logged", exc_info=True)

        # ── Back in the main thread: merge + DB check ───────────────────────
        # Deduplicate by device_id (SADP results win over TCP-only)
        seen_ids: set = set()
        found: list   = []

        # SADP results first (highest confidence)
        for h in sadp_hits:
            ip     = h['ip']
            dev_id = f"{ip}:37777"
            if dev_id in seen_ids:
                continue
            seen_ids.add(dev_id)
            found.append({
                'ip':               ip,
                'port':             37777,
                'brand':            f"Dahua {h.get('model', 'Device')}",
                'model':            h.get('model', ''),
                'serial':           h.get('serial', ''),
                'mac':              h.get('mac', ''),
                'technology':       'Fingerprint / RFID',
                'device_id':        dev_id,
                'discovery_method': 'SADP Ethernet Broadcast',
            })

        for item in raw_hits:
            dev_id = item['device_id']
            if dev_id not in seen_ids:
                seen_ids.add(dev_id)
                found.append(item)

        # Single bulk DB query to check registration status (main thread = correct schema)
        all_device_ids = [d['device_id'] for d in found]
        all_ips        = list({d['ip'] for d in found})
        try:
            registered_ids = set(
                BiometricDevice.objects.filter(
                    Q(device_id__in=all_device_ids) |
                    Q(ip_address__in=all_ips)
                ).values_list('device_id', flat=True)
            )
            registered_ips = set(
                BiometricDevice.objects.filter(ip_address__in=all_ips)
                .values_list('ip_address', flat=True)
            )
        except Exception:
            registered_ids = set()
            registered_ips = set()

        for d in found:
            d['already_registered'] = (
                d['device_id'] in registered_ids or
                d['ip']        in registered_ips
            )

        found.sort(key=lambda d: (
            [int(x) for x in d['ip'].split('.') if x.isdigit()],
            d['port']
        ))

        return Response({
            'devices':       found,
            'scanned':       f"{ip_prefix}.1 – {ip_prefix}.254",
            'sadp_found':    len(sadp_hits),
            'tcp_found':     len(found) - len(sadp_hits),
            'ports_checked': [p for p, _, _ in BIOMETRIC_PROBE_PORTS],
        })


# ══════════════════════════════════════════════════════════════════════════════
# SmartPSS Lite Integration
# ══════════════════════════════════════════════════════════════════════════════

class SmartPSSSourceViewSet(ClockInModuleMixin, viewsets.ModelViewSet):
    """
    CRUD for SmartPSS Lite sources.
    GET  /clockin/smartpss/sources/
    POST /clockin/smartpss/sources/
    PUT/PATCH/DELETE /clockin/smartpss/sources/{id}/
    """
    queryset         = SmartPSSSource.objects.all()
    serializer_class = SmartPSSSourceSerializer


class SmartPSSImportLogViewSet(ClockInModuleMixin, viewsets.ReadOnlyModelViewSet):
    """Read-only log of every API sync and CSV import."""
    queryset         = SmartPSSImportLog.objects.all()[:200]
    serializer_class = SmartPSSImportLogSerializer


def _save_smartpss_records(records: list, source: SmartPSSSource | None,
                           source_type: str, triggered_by: str) -> dict:
    """
    Shared pipeline: take a list of normalised attendance records (dicts with
    card_no / employee_id / name / time / status) and create ClockEvents.
    Returns a summary dict.
    """
    log = SmartPSSImportLog.objects.create(
        source=source, source_type=source_type,
        records_found=len(records), triggered_by=triggered_by,
    )
    saved = skipped = errors = 0

    for rec in records:
        try:
            card_no     = rec.get('card_no', '').strip()
            employee_id = rec.get('employee_id', '').strip()
            name        = rec.get('name', '').strip()
            time_str    = rec.get('time', '')
            event_type  = rec.get('status', 'IN')

            # Lookup person — card_no first, then employee ID, then name (last resort)
            person = None
            if card_no:
                person = _lookup_person(card_no=card_no)
            if not person and employee_id:
                person = _lookup_person(user_id=employee_id, fingerprint_id=employee_id)
            if not person and name:
                person = PersonRegistry.objects.filter(
                    display_name__iexact=name, is_active=True
                ).first()

            if not person:
                skipped += 1
                continue

            # Parse timestamp
            event_timestamp = parse_smartpss_time(time_str)

            # Deduplicate: skip if an identical event exists within 60 seconds
            window_start = event_timestamp - timedelta(seconds=60)
            window_end   = event_timestamp + timedelta(seconds=60)
            if ClockEvent.objects.filter(
                person=person, event_type=event_type,
                timestamp__range=(window_start, window_end)
            ).exists():
                skipped += 1
                continue

            _process_scan_event(person, None, event_timestamp,
                                direction='in' if event_type == 'IN' else 'out')
            saved += 1

        except Exception as exc:
            errors += 1
            log.error_detail += f"{rec.get('name', '?')}: {exc}\n"

    log.records_saved = saved
    log.skipped       = skipped
    log.errors        = errors
    log.finished_at   = timezone.now()
    log.save()

    return {
        'records_found': log.records_found,
        'records_saved': saved,
        'skipped':       skipped,
        'errors':        errors,
        'log_id':        log.id,
    }


class SmartPSSTestView(ClockInModuleMixin, APIView):
    """
    POST /clockin/smartpss/sources/{id}/test/
    Tests connectivity to a SmartPSS Lite instance by logging in and immediately
    logging out.  Returns { ok, message, api_url }.
    """
    def post(self, request, pk):
        source = SmartPSSSource.objects.filter(pk=pk).first()
        if not source:
            return Response({'error': 'SmartPSS source not found.'}, status=404)
        client = SmartPSSLiteClient(
            host=source.host, port=source.port,
            username=source.username, password=source.password,
            use_https=source.use_https,
        )
        try:
            result = client.test_connection()
            return Response({
                'ok':      True,
                'message': f'Connected to SmartPSS Lite at {result["base_url"]}',
                'api_url': result['base_url'],
            })
        except SmartPSSError as exc:
            return Response({'ok': False, 'message': str(exc)}, status=200)
        except Exception as exc:
            return Response({'ok': False, 'message': f'Unexpected error: {exc}'}, status=200)


class SmartPSSSyncView(ClockInModuleMixin, APIView):
    """
    POST /clockin/smartpss/sources/{id}/sync/
    Body (optional): { "days_back": 3 }

    Calls the SmartPSS Lite REST API, retrieves attendance records for the
    configured date range, and inserts them as ClockEvents.

    Network prerequisite: the SmartPSS Lite PC must be reachable from this server.
    If it is not (e.g., behind NAT without port forwarding), use CSV import instead.
    """
    def post(self, request, pk):
        source = SmartPSSSource.objects.filter(pk=pk).first()
        if not source:
            return Response({'error': 'SmartPSS source not found.'}, status=404)
        if not source.is_active:
            return Response({'error': 'This SmartPSS source is disabled.'}, status=400)

        try:
            days_back = int(request.data.get('days_back', source.sync_days_back))
            days_back = min(max(days_back, 1), 90)
        except (ValueError, TypeError):
            days_back = source.sync_days_back

        end_dt   = timezone.now()
        start_dt = end_dt - timedelta(days=days_back)

        client = SmartPSSLiteClient(
            host=source.host, port=source.port,
            username=source.username, password=source.password,
            use_https=source.use_https,
        )
        try:
            with client.session() as token:
                raw_records = client.search_attendance_all(token, start_dt, end_dt)
        except SmartPSSError as exc:
            return Response({
                'error': str(exc),
                'tip': (
                    'Cannot reach SmartPSS Lite. Options: '
                    '(1) Enable port forwarding on your router, '
                    '(2) Use a VPN, '
                    '(3) Export CSV from SmartPSS Lite and use CSV Import instead.'
                ),
            }, status=503)
        except Exception as exc:
            return Response({'error': f'Unexpected error during sync: {exc}'}, status=500)

        # Normalise raw records from SmartPSS Lite API format
        normalised = []
        for rec in raw_records:
            normalised.append({
                'card_no':     rec.get('cardNo', ''),
                'employee_id': rec.get('personId', ''),
                'name':        rec.get('personName', ''),
                'time':        rec.get('time', ''),
                'status':      normalise_attend_status(rec.get('attendStatus', 0)),
            })

        summary = _save_smartpss_records(
            normalised, source, 'API',
            triggered_by=getattr(request.user, 'username', 'system'),
        )

        # Update last_sync_at
        source.last_sync_at = timezone.now()
        import json as _json
        source.last_sync_result = _json.dumps(summary)
        source.save(update_fields=['last_sync_at', 'last_sync_result'])

        return Response({
            'ok':      True,
            'source':  source.name,
            'period':  f'{start_dt.date()} → {end_dt.date()}',
            **summary,
        })


class SmartPSSCSVImportView(ClockInModuleMixin, APIView):
    """
    POST /clockin/smartpss/import-csv/
    multipart/form-data: file=<csv_file>, source_id=<optional_int>

    Import a CSV file exported from SmartPSS Lite.  Supported export formats:
      • SmartPSS Lite Attendance Report (English)
      • SmartPSS Lite 出勤记录 (Chinese columns — GBK or UTF-8)

    How to export from SmartPSS Lite:
      Reports → Attendance → Search → Export → CSV / Excel

    This endpoint always works regardless of network configuration and is the
    recommended import method for schools without a static IP or port forwarding.
    """
    def post(self, request):
        csv_file  = request.FILES.get('file')
        source_id = request.data.get('source_id')

        if not csv_file:
            return Response({'error': 'No file uploaded. Send file as multipart field "file".'}, status=400)

        source = None
        if source_id:
            source = SmartPSSSource.objects.filter(pk=source_id).first()

        try:
            content = csv_file.read()
            records = parse_smartpss_csv(content)
        except Exception as exc:
            return Response({'error': f'Failed to parse CSV: {exc}'}, status=400)

        if not records:
            return Response({
                'error': 'No valid rows found in the CSV file.',
                'tip': (
                    'Make sure the file is a SmartPSS Lite attendance export. '
                    'Required columns: Name, Card Number or Employee ID, Time, Status.'
                ),
            }, status=400)

        summary = _save_smartpss_records(
            records, source, 'CSV',
            triggered_by=getattr(request.user, 'username', 'system'),
        )

        return Response({
            'ok':       True,
            'filename': csv_file.name,
            **summary,
        })


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 1 — Attendance Capture Endpoint
# POST /api/attendance/capture/   (also routed at /api/clockin/capture/)
#
# Validates device by device_id + api_key (tenant isolation via schema context),
# persists a raw AttendanceCaptureLog with status=PENDING, returns log id.
# ═══════════════════════════════════════════════════════════════════════════════

@method_decorator(csrf_exempt, name='dispatch')
class CaptureView(APIView):
    """
    Receive a raw biometric scan from a registered device.

    Authentication: device-level API key (no user JWT required).
    The device must be registered in BiometricDevice for this tenant.

    Request body (JSON):
        {
            "device_id":  "GATE-001",
            "api_key":    "<secret>",
            "method":     "card" | "fingerprint" | "face",
            "identifier": "<card_uid or fingerprint_id>",
            "timestamp":  "2026-03-28T07:45:00Z"   // optional, defaults to now
        }

    Responses:
        202 Accepted  — log stored, status=pending, identity resolution pending
        400 Bad Request — missing fields
        401 Unauthorized — invalid device_id / api_key
        422 Unprocessable — invalid method
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from clockin.application.services.attendance_capture_service import AttendanceCaptureService
        from django.utils.dateparse import parse_datetime

        body = request.data

        # ── Required field validation ─────────────────────────────────────────
        required = ['device_id', 'api_key', 'method', 'identifier']
        missing  = [f for f in required if not body.get(f)]
        if missing:
            return Response(
                {'ok': False, 'error': f"Missing required fields: {', '.join(missing)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Optional timestamp ────────────────────────────────────────────────
        ts = None
        raw_ts = body.get('timestamp')
        if raw_ts:
            ts = parse_datetime(raw_ts)
            if ts is None:
                return Response(
                    {'ok': False, 'error': 'Invalid timestamp format. Use ISO-8601 (e.g. 2026-03-28T07:45:00Z).'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # ── Service call ──────────────────────────────────────────────────────
        svc    = AttendanceCaptureService()
        result = svc.receive_scan(
            device_id   = body['device_id'],
            api_key     = body['api_key'],
            method      = body['method'],
            identifier  = body['identifier'],
            timestamp   = ts,
            raw_payload = dict(body),
        )

        if not result['ok']:
            error = result.get('error', 'Capture failed.')
            if 'not found or API key' in error:
                http_status = status.HTTP_401_UNAUTHORIZED
            elif 'Invalid method' in error:
                http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
            else:
                http_status = status.HTTP_400_BAD_REQUEST
            return Response(result, status=http_status)

        return Response(result, status=status.HTTP_202_ACCEPTED)


class AttendanceCaptureLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset for AttendanceCaptureLog.
    Supports filtering: ?status=pending|success|failed  ?device=<id>
    """
    serializer_class   = AttendanceCaptureLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = AttendanceCaptureLog.objects.select_related('device', 'person').all()
        s  = self.request.query_params.get('status')
        d  = self.request.query_params.get('device')
        if s:
            qs = qs.filter(status=s)
        if d:
            qs = qs.filter(device_id=d)
        return qs
