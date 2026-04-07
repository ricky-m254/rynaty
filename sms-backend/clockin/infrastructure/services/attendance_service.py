"""
AttendanceService — cross-domain write adapter.

FIXES the DBMA violation: clockin/views.py previously imported
  from school.models import AttendanceRecord
  from hr.models import AttendanceRecord
directly. This service is the ONLY place those imports occur, and it is
in the infrastructure layer — not in domain or application.
"""
from datetime import datetime, date as date_type


class DjangoAttendanceService:
    def update(self, person, event_type: str, event_timestamp: datetime,
               event_date: date_type, is_late: bool) -> bool:
        try:
            if person.person_type == 'STUDENT' and person.student_id:
                return self._update_student(person.student_id, event_type, event_timestamp, event_date, is_late)
            elif person.person_type in ('TEACHER', 'STAFF') and person.employee_id:
                return self._update_employee(person.employee_id, event_type, event_timestamp, event_date, is_late)
        except Exception as exc:
            print(f"[AttendanceService] update failed: {exc}")
        return False

    @staticmethod
    def _update_student(student_id, event_type, event_timestamp, event_date, is_late):
        from school.models import AttendanceRecord
        if event_type == 'IN':
            AttendanceRecord.objects.update_or_create(
                student_id=student_id, date=event_date,
                defaults={'status': 'Late' if is_late else 'Present',
                          'notes': f'Clock-in at {event_timestamp.time()}'},
            )
            return True
        return False

    @staticmethod
    def _update_employee(employee_id, event_type, event_timestamp, event_date, is_late):
        from hr.models import AttendanceRecord
        from datetime import datetime as _dt
        if event_type == 'IN':
            AttendanceRecord.objects.update_or_create(
                employee_id=employee_id, date=event_date,
                defaults={'clock_in': event_timestamp.time(),
                          'status': 'Late' if is_late else 'Present',
                          'notes': 'Clock-in event'},
            )
            return True
        elif event_type == 'OUT':
            rec = AttendanceRecord.objects.filter(employee_id=employee_id, date=event_date).first()
            if rec:
                rec.clock_out = event_timestamp.time()
                if rec.clock_in:
                    s = _dt.combine(event_date, rec.clock_in)
                    e = _dt.combine(event_date, rec.clock_out)
                    rec.hours_worked = round((e - s).total_seconds() / 3600.0, 2)
                rec.save()
                return True
        return False
