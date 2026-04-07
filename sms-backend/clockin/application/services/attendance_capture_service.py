"""
AttendanceCaptureService — Phase 1 entry point.

Responsibilities (Phase 1 only):
  1. Validate the inbound device by device_id + api_key (tenant isolation is
     automatic because this runs inside the tenant schema).
  2. Record a raw AttendanceCaptureLog with status=PENDING.
  3. Return the log + device so the view can respond.

Phase 2 (identity resolution) and Phase 3 (access control) will extend this
service. Do NOT add logic beyond the steps above until the next phase.
"""
from datetime import datetime
from django.utils import timezone


class AttendanceCaptureService:
    """
    Thin application-layer facade for the device-capture pipeline.

    Methods are deliberately kept one-phase-at-a-time per the implementation
    specification.  The view calls `receive_scan()` and gets back a result dict.
    """

    # ── Phase 1 ───────────────────────────────────────────────────────────────

    def receive_scan(
        self,
        *,
        device_id: str,
        api_key: str,
        method: str,
        identifier: str,
        timestamp: datetime | None = None,
        raw_payload: dict | None = None,
    ) -> dict:
        """
        Entry point for POST /api/attendance/capture/.

        Returns a result dict:
            {
                'ok':       bool,
                'log_id':   int | None,
                'device':   str,
                'status':   'pending' | 'failed',
                'error':    str | None,   # present only when ok=False
            }
        """
        from clockin.models import BiometricDevice, AttendanceCaptureLog

        ts = timestamp or timezone.now()

        # ── Step 1: Device validation ─────────────────────────────────────────
        device = self._validate_device(device_id, api_key)
        if device is None:
            return {
                'ok':     False,
                'log_id': None,
                'device': device_id,
                'status': 'failed',
                'error':  'Device not found or API key invalid.',
            }

        if not device.is_active:
            log = AttendanceCaptureLog.objects.create(
                device=device,
                method=method,
                identifier=identifier,
                timestamp=ts,
                status='failed',
                failure_reason='Device is inactive.',
                raw_payload=raw_payload or {},
            )
            return {
                'ok':     False,
                'log_id': log.pk,
                'device': device.name,
                'status': 'failed',
                'error':  'Device is inactive.',
            }

        # ── Step 2: Method validation ─────────────────────────────────────────
        valid_methods = {'card', 'fingerprint', 'face'}
        if method not in valid_methods:
            log = AttendanceCaptureLog.objects.create(
                device=device,
                method=method if len(method) <= 20 else 'card',
                identifier=identifier,
                timestamp=ts,
                status='failed',
                failure_reason=f'Unknown method: {method}. Expected one of {valid_methods}.',
                raw_payload=raw_payload or {},
            )
            return {
                'ok':     False,
                'log_id': log.pk,
                'device': device.name,
                'status': 'failed',
                'error':  f'Invalid method "{method}".',
            }

        # ── Step 3: Store raw log with status=PENDING ─────────────────────────
        log = AttendanceCaptureLog.objects.create(
            device=device,
            method=method,
            identifier=identifier,
            timestamp=ts,
            status='pending',
            raw_payload=raw_payload or {},
        )

        # Update device last_seen
        BiometricDevice.objects.filter(pk=device.pk).update(last_seen=ts)

        return {
            'ok':     True,
            'log_id': log.pk,
            'device': device.name,
            'status': 'pending',
            'error':  None,
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _validate_device(device_id: str, api_key: str):
        """
        Return BiometricDevice if device_id + api_key match, else None.
        Tenant isolation is enforced by the schema context (django-tenants).
        """
        from clockin.models import BiometricDevice
        try:
            return BiometricDevice.objects.get(device_id=device_id, api_key=api_key)
        except BiometricDevice.DoesNotExist:
            return None
