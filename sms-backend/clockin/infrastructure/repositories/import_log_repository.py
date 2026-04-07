"""ImportLogRepository — writes SmartPSSImportLog entries."""
from django.utils import timezone


class DjangoImportLogRepository:

    def create(self, source_id, source_type: str, records_found: int, triggered_by: str):
        from clockin.models import SmartPSSImportLog, SmartPSSSource
        source = SmartPSSSource.objects.filter(pk=source_id).first() if source_id else None
        return SmartPSSImportLog.objects.create(
            source=source, source_type=source_type,
            records_found=records_found, triggered_by=triggered_by,
        )

    def finalise(self, source_id, source_type, triggered_by, summary: dict, error_detail: str):
        from clockin.models import SmartPSSImportLog, SmartPSSSource
        source = SmartPSSSource.objects.filter(pk=source_id).first() if source_id else None
        return SmartPSSImportLog.objects.create(
            source        = source,
            source_type   = source_type,
            triggered_by  = triggered_by,
            records_found = summary.get('records_found', 0),
            records_saved = summary.get('records_saved', 0),
            skipped       = summary.get('skipped', 0),
            errors        = summary.get('errors', 0),
            error_detail  = error_detail,
            finished_at   = timezone.now(),
        )
