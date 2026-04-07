"""
SmartPSS Lite infrastructure module (canonical location).
The root clockin/smartpss_client.py forwards to this file.

SmartPSS Lite v2.x REST API Client
====================================
Infrastructure layer — HTTP client for Dahua SmartPSS Lite.

SmartPSS Lite runs on a Windows PC on the school's local network and
aggregates attendance data from ALL connected Dahua devices
(e.g. Dahua AS16214S fingerprint readers, door controllers, etc.).

Base URL (default):  http://<host>:8443/evo-apigw/
Auth:  POST /evo-apigw/evo/doLogin → token (used in Authorization header)

Network note
------------
SmartPSS Lite is a LOCAL service. For this client to reach it from the cloud:
  Option A: School router port-forwards port 8443 → SmartPSS PC
  Option B: Always-on VPN between school and server
  Option C: Use CSV import instead (no network required)

Supported record field patterns (SmartPSS Lite API response)
-----------------------------------------------------------
attendStatus : 0 = Check In,  1 = Check Out,  255 = unknown
personId     : SmartPSS internal person ID
cardNo       : RFID card number (matches PersonRegistry.card_no)
personName   : display name
time         : "YYYY-MM-DD HH:MM:SS"
deviceName   : name of the Dahua device that captured the event
"""


import json
import urllib.request
import urllib.error
from datetime import datetime, timezone as dt_tz
from typing import Optional


CONNECT_TIMEOUT = 10.0   # seconds — for login / test
SYNC_TIMEOUT    = 60.0   # seconds — attendance search can be slow

SMARTPSS_CODES = {
    1000: 'Success',
    1001: 'Need login',
    1002: 'Wrong user or password',
    1003: 'User locked',
    1004: 'System error',
    1005: 'Timeout',
}


class SmartPSSError(Exception):
    """Raised when SmartPSS Lite returns a non-success code or is unreachable."""
    def __init__(self, message: str, code: int = 0):
        super().__init__(message)
        self.code = code


class SmartPSSLiteClient:
    """
    Thin HTTP wrapper around the SmartPSS Lite v2.x local REST API.

    Usage:
        client = SmartPSSLiteClient(host='192.168.1.200', port=8443,
                                    username='admin', password='<from-db-or-env>')
        with client.session() as token:
            records = client.search_attendance(token, start_dt, end_dt)
    """

    def __init__(self, host: str, port: int = 8443, username: str = 'admin',
                 password: str = '', use_https: bool = False):
        import os
        scheme = 'https' if use_https else 'http'
        self.base = f'{scheme}://{host.strip()}:{port}/evo-apigw'
        self.username = username
        # Never fall back to a hardcoded credential; require the caller to supply
        # the password explicitly or via the SMARTPSS_PASSWORD environment variable.
        self.password = password or os.environ.get('SMARTPSS_PASSWORD') or ''
        if not self.password:
            raise ValueError(
                'SmartPSSLiteClient: password must be provided explicitly or via '
                'the SMARTPSS_PASSWORD environment variable.'
            )

    # ── low-level helpers ────────────────────────────────────────────────────

    def _request(self, method: str, path: str, body: Optional[dict] = None,
                 token: Optional[str] = None, timeout: float = CONNECT_TIMEOUT,
                 _retry: int = 1) -> dict:
        """
        Make an HTTP request to SmartPSS Lite.
        Retries once on URLError (connection reset / brief network blip).
        """
        import time as _time
        url = f'{self.base}{path}'
        data = json.dumps(body or {}).encode('utf-8') if body is not None else b'{}'
        headers = {
            'Content-Type':  'application/json;charset=UTF-8',
            'Accept':        'application/json',
            'User-Agent':    'SmartCampus/1.0 (SmartPSS-Lite-Sync)',
        }
        if token:
            headers['Authorization'] = token
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode('utf-8', errors='replace')
        except urllib.error.HTTPError as e:
            raise SmartPSSError(f'HTTP {e.code} from SmartPSS Lite at {url}', code=e.code)
        except urllib.error.URLError as e:
            if _retry > 0:
                _time.sleep(2)
                return self._request(method, path, body, token, timeout, _retry=_retry - 1)
            raise SmartPSSError(
                f'Cannot reach SmartPSS Lite at {self.base}: {e.reason}. '
                'Check host/port and ensure port forwarding is configured.', code=0)
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            raise SmartPSSError(f'SmartPSS Lite returned non-JSON: {raw[:200]}', code=0)
        code = result.get('code', -1)
        if code != 1000:
            desc = result.get('desc') or SMARTPSS_CODES.get(code, f'code={code}')
            raise SmartPSSError(f'SmartPSS Lite error: {desc}', code=code)
        return result.get('data', {})

    # ── authentication ───────────────────────────────────────────────────────

    def login(self) -> str:
        """Authenticate and return a session token string."""
        data = self._request('POST', '/evo/doLogin', {
            'userName':   self.username,
            'userPwd':    self.password,
            'ipAddress':  '127.0.0.1',
            'clientType': 0,
        }, timeout=CONNECT_TIMEOUT)
        token = data.get('token') or data.get('sessionId') or data.get('access_token')
        if not token:
            raise SmartPSSError('SmartPSS Lite login succeeded but returned no token. '
                                 'Check SmartPSS Lite version compatibility.')
        return str(token)

    def logout(self, token: str) -> None:
        """Invalidate the session token (best-effort, errors are silenced)."""
        try:
            self._request('POST', '/evo/doLogout', {}, token=token, timeout=CONNECT_TIMEOUT)
        except SmartPSSError:
            pass

    class _SessionContext:
        """Context manager: login on enter, logout on exit."""
        def __init__(self, client: 'SmartPSSLiteClient'):
            self.client = client
            self.token: str = ''

        def __enter__(self) -> str:
            self.token = self.client.login()
            return self.token

        def __exit__(self, *_):
            if self.token:
                self.client.logout(self.token)

    def session(self) -> '_SessionContext':
        """Return a context manager that logs in on enter and logs out on exit."""
        return SmartPSSLiteClient._SessionContext(self)

    # ── data retrieval ───────────────────────────────────────────────────────

    def search_attendance(self, token: str, start_dt: datetime, end_dt: datetime,
                          page: int = 1, page_size: int = 500) -> dict:
        """
        Fetch attendance records from SmartPSS Lite.

        Returns dict: { 'list': [...], 'totalNum': int }
        Each item has: personId, personName, cardNo, time, attendStatus,
                       deviceId, deviceName, channelName
        """
        start_s = start_dt.strftime('%Y-%m-%d %H:%M:%S')
        end_s   = end_dt.strftime('%Y-%m-%d %H:%M:%S')
        return self._request('POST', '/evo/AttendanceSearch', {
            'startTime': start_s,
            'endTime':   end_s,
            'pageNum':   page,
            'pageSize':  page_size,
        }, token=token, timeout=SYNC_TIMEOUT)

    def search_attendance_all(self, token: str, start_dt: datetime,
                              end_dt: datetime, page_size: int = 500) -> list:
        """Paginate through all attendance records for the given date range."""
        records = []
        page = 1
        while True:
            data = self.search_attendance(token, start_dt, end_dt, page, page_size)
            batch = data.get('list') or []
            records.extend(batch)
            total = data.get('totalNum', 0)
            if len(records) >= total or not batch:
                break
            page += 1
        return records

    def test_connection(self) -> dict:
        """
        Login and immediately logout.  Returns { 'ok': True } or raises SmartPSSError.
        """
        token = self.login()
        self.logout(token)
        return {'ok': True, 'base_url': self.base}


# ── Normalisation helpers ─────────────────────────────────────────────────────

def normalise_attend_status(raw) -> str:
    """
    Convert SmartPSS Lite attendStatus to 'IN' or 'OUT'.
    0  → Check In   (IN)
    1  → Check Out  (OUT)
    255 / other → 'IN' (default — most school gates are IN-only)
    """
    try:
        val = int(raw)
    except (TypeError, ValueError):
        return 'IN'
    return 'OUT' if val == 1 else 'IN'


def parse_smartpss_time(time_str: Optional[str]) -> datetime:
    """Parse SmartPSS Lite time string ('YYYY-MM-DD HH:MM:SS') to aware datetime."""
    if not time_str:
        from django.utils import timezone
        return timezone.now()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ'):
        try:
            dt = datetime.strptime(time_str.strip(), fmt)
            if dt.tzinfo is None:
                from django.utils import timezone
                return timezone.make_aware(dt)
            return dt
        except ValueError:
            continue
    from django.utils import timezone
    return timezone.now()


# ── CSV parser for SmartPSS Lite exported reports ────────────────────────────

import csv
import io

SMARTPSS_CSV_COLUMN_ALIASES = {
    'name':            ['name', 'employee name', 'person name', '员工姓名', 'student name'],
    'employee_id':     ['employee id', 'employee no', 'employee no.', '工号', 'person id', 'staff id'],
    'card_no':         ['card number', 'card no', 'card no.', '卡号', 'cardno'],
    'time':            ['time', 'datetime', 'check-in time', 'check time', '时间', 'date time'],
    'status':          ['status', 'check status', 'check state', 'in/out', 'check-in/out', '状态'],
    'device':          ['device name', 'reader name', 'device', '设备名', 'door name'],
}


def _match_header(header: str) -> Optional[str]:
    """Map a raw CSV column header to a canonical field name."""
    h = header.strip().lower()
    for canonical, aliases in SMARTPSS_CSV_COLUMN_ALIASES.items():
        if h in aliases:
            return canonical
    return None


def parse_smartpss_csv(file_content: bytes | str) -> list:
    """
    Parse a CSV file exported from SmartPSS Lite.

    Returns a list of normalised dicts:
        { name, employee_id, card_no, time (str), status ('IN'|'OUT'), device }
    Rows where 'time' is missing/unparseable are silently skipped.
    """
    if isinstance(file_content, bytes):
        # Try UTF-8 with BOM, then latin-1 (some SmartPSS exports use latin-1)
        for enc in ('utf-8-sig', 'utf-8', 'latin-1', 'gbk'):
            try:
                text = file_content.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = file_content.decode('latin-1', errors='replace')
    else:
        text = file_content

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return []

    # Map raw headers → canonical names
    col_map = {}
    for raw_header in reader.fieldnames:
        canonical = _match_header(raw_header)
        if canonical:
            col_map[raw_header] = canonical

    records = []
    for row in reader:
        mapped: dict = {}
        for raw_header, canonical in col_map.items():
            mapped[canonical] = (row.get(raw_header) or '').strip()

        time_str = mapped.get('time', '')
        if not time_str:
            continue

        # Normalise status
        raw_status = mapped.get('status', '').lower()
        if any(x in raw_status for x in ('out', 'check out', '1', 'exit')):
            status = 'OUT'
        else:
            status = 'IN'

        records.append({
            'name':        mapped.get('name', ''),
            'employee_id': mapped.get('employee_id', ''),
            'card_no':     mapped.get('card_no', ''),
            'time':        time_str,
            'status':      status,
            'device':      mapped.get('device', ''),
        })
    return records
