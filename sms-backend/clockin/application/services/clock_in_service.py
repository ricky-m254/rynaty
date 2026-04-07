"""
ClockInService — application service that wires use cases with their dependencies.
Entry point for the presentation layer (views.py) to call instead of inline logic.
"""
from clockin.infrastructure.repositories.person_repository import DjangoPersonRepository
from clockin.infrastructure.repositories.clock_event_repository import DjangoClockEventRepository
from clockin.infrastructure.repositories.shift_repository import DjangoShiftRepository
from clockin.infrastructure.repositories.import_log_repository import DjangoImportLogRepository
from clockin.infrastructure.services.attendance_service import DjangoAttendanceService
from clockin.infrastructure.services.notification_service import DjangoNotificationService
from clockin.application.use_cases.process_scan import ProcessScanUseCase
from clockin.application.use_cases.sync_attendance import SyncAttendanceUseCase


def _build_process_scan_use_case() -> ProcessScanUseCase:
    return ProcessScanUseCase(
        person_repo          = DjangoPersonRepository(),
        clock_event_repo     = DjangoClockEventRepository(),
        shift_repo           = DjangoShiftRepository(),
        attendance_service   = DjangoAttendanceService(),
        notification_service = DjangoNotificationService(),
    )


def _build_sync_use_case() -> SyncAttendanceUseCase:
    return SyncAttendanceUseCase(
        person_repo          = DjangoPersonRepository(),
        clock_event_repo     = DjangoClockEventRepository(),
        shift_repo           = DjangoShiftRepository(),
        attendance_service   = DjangoAttendanceService(),
        notification_service = DjangoNotificationService(),
        import_log_repo      = DjangoImportLogRepository(),
    )


class ClockInService:
    """
    Facade over all ClockIn use cases.
    Views.py and API endpoints call THIS class — never use cases directly.

    Usage:
        svc = ClockInService()
        result = svc.process_scan(person_obj, device_obj, timestamp, direction)
        summary = svc.sync_records(records, source_id, source_type, user)
    """

    def process_scan(self, person_obj, device_obj, event_timestamp, direction='auto', deduplicate=True):
        """Process a single biometric scan. Returns created ClockEvent ORM object."""
        use_case = _build_process_scan_use_case()
        return use_case.execute_from_person_obj(
            person_obj,
            device_obj,
            event_timestamp,
            direction,
            deduplicate=deduplicate,
        )

    def sync_records(self, records: list, source_id, source_type: str, triggered_by: str) -> dict:
        """Bulk-import normalised attendance records. Returns summary dict."""
        use_case = _build_sync_use_case()
        return use_case.execute(records, source_id, source_type, triggered_by)
