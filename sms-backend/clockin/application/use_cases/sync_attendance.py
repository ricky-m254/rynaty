"""
SyncAttendanceUseCase
=====================
Orchestrates pulling attendance records from an external source
(SmartPSS Lite API or CSV upload) and processing each record
through the ProcessScanUseCase pipeline.

Domain rule: external source data is normalised to
{ card_no, employee_id, name, time, status } before processing.
"""
from datetime import datetime
from typing import List, Optional


class SyncAttendanceUseCase:
    """
    Single entry point for ALL attendance import operations.
    Delegates actual processing to ProcessScanUseCase per record.
    """

    def __init__(self, person_repo, clock_event_repo, shift_repo,
                 attendance_service, notification_service, import_log_repo):
        self.person_repo          = person_repo
        self.clock_event_repo     = clock_event_repo
        self.shift_repo           = shift_repo
        self.attendance_service   = attendance_service
        self.notification_service = notification_service
        self.import_log_repo      = import_log_repo

    def execute(self, records: List[dict], source_id: Optional[int],
                source_type: str, triggered_by: str) -> dict:
        """
        Process a batch of normalised attendance records.

        Each record dict must have:
          card_no, employee_id, name, time (str), status ('IN'|'OUT')

        Returns summary: { records_found, records_saved, skipped, errors }
        """
        saved = skipped = errors = 0
        error_detail = []

        for rec in records:
            try:
                person = self._resolve_person(rec)
                if not person:
                    skipped += 1
                    continue

                event_ts = self._parse_time(rec.get('time', ''))
                event_type = rec.get('status', 'IN')
                event_date = event_ts.date()

                if self.clock_event_repo.duplicate_exists(person.id, event_type, event_ts):
                    skipped += 1
                    continue

                from clockin.domain.rules.attendance import is_late_arrival, minutes_late, determine_event_type
                from clockin.domain.entities.clock_event import ClockEventEntity

                entity = ClockEventEntity(
                    person_id=person.id,
                    event_type=event_type,
                    timestamp=event_ts,
                    event_date=event_date,
                    is_late=False,
                )
                shift_data = self.shift_repo.find_active_shift_for_person_type(person.person_type)
                if shift_data and event_type == 'IN':
                    entity.is_late = is_late_arrival(event_ts, shift_data['expected_arrival'], shift_data['grace_period_minutes'])

                entity.validate()
                self.clock_event_repo.save(entity)
                self.attendance_service.update(person, event_type, event_ts, event_date, entity.is_late)
                saved += 1

            except Exception as exc:
                errors += 1
                error_detail.append(f"{rec.get('name', '?')}: {exc}")

        summary = {
            'records_found': len(records),
            'records_saved': saved,
            'skipped':       skipped,
            'errors':        errors,
        }
        self.import_log_repo.finalise(source_id, source_type, triggered_by, summary, '\n'.join(error_detail))
        return summary

    def _resolve_person(self, rec: dict):
        """Lookup person by card_no → employee_id → name."""
        card_no = rec.get('card_no', '').strip()
        emp_id  = rec.get('employee_id', '').strip()
        name    = rec.get('name', '').strip()

        if card_no:
            p = self.person_repo.find_by_card_no(card_no)
            if p:
                return p
        if emp_id:
            p = self.person_repo.find_by_user_id(emp_id)
            if p:
                return p
        if name:
            return self.person_repo.find_by_name(name)
        return None

    @staticmethod
    def _parse_time(time_str: str) -> datetime:
        from clockin.infrastructure.dahua.utils import parse_device_time
        return parse_device_time(time_str)
