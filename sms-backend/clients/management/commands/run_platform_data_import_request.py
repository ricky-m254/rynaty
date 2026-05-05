import json
import shutil
import tempfile
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand, CommandError, call_command
from django.utils import timezone
from django_tenants.utils import get_public_schema_name, schema_context

from clients.models import TenantDataImportRequest
from clients.platform_views import _data_import_profile_spec


class Command(BaseCommand):
    help = "Run a queued platform tenant data import request against its target tenant."

    def add_arguments(self, parser):
        parser.add_argument("--request-id", type=int, required=True)
        parser.add_argument(
            "--archive-raw",
            action="store_true",
            help="Force archival of the uploaded bundle into tenant media during import execution.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Allow rerunning a request even if it is already marked completed.",
        )
        parser.add_argument(
            "--keep-working-dir",
            action="store_true",
            help="Keep the temporary working directory after the command finishes.",
        )

    def handle(self, *args, **options):
        request_id = options["request_id"]
        force = bool(options["force"])
        keep_working_dir = bool(options["keep_working_dir"])
        public_schema = get_public_schema_name()

        with schema_context(public_schema):
            import_request = (
                TenantDataImportRequest.objects.select_related("tenant")
                .prefetch_related("files")
                .filter(pk=request_id)
                .first()
            )
            if not import_request:
                raise CommandError(f"Import request {request_id} was not found.")
            if import_request.status == TenantDataImportRequest.STATUS_COMPLETED and not force:
                raise CommandError(
                    f"Import request {request_id} is already completed. Use --force to rerun it."
                )

            spec = _data_import_profile_spec(import_request.import_profile)
            command_name = spec.get("command_name") or ""
            if not command_name:
                raise CommandError(
                    f"Import request {request_id} uses profile '{import_request.import_profile}' which has no runnable command."
                )

            files = list(import_request.files.all())
            if not files:
                raise CommandError(f"Import request {request_id} has no attached files.")

            attached_names = {row.original_name for row in files}
            missing_required = [name for name in spec.get("required_files", []) if name not in attached_names]
            if missing_required:
                raise CommandError(
                    "Import request is missing required files: " + ", ".join(sorted(missing_required))
                )

            import_request.status = TenantDataImportRequest.STATUS_PROCESSING
            import_request.last_error = ""
            import_request.processed_at = None
            import_request.save(update_fields=["status", "last_error", "processed_at", "updated_at"])

        run_root = Path(settings.BASE_DIR) / "artifacts" / "tenant_import_runs"
        run_root.mkdir(parents=True, exist_ok=True)
        working_dir_path = Path(tempfile.mkdtemp(prefix=f"request-{request_id}-", dir=run_root))
        stdout_buffer = StringIO()
        archive_raw = bool(options["archive_raw"] or import_request.archive_raw_to_media)

        try:
            for row in files:
                if not row.file:
                    continue
                destination = working_dir_path / row.original_name
                destination.write_bytes(Path(row.file.path).read_bytes())

            command_kwargs = {
                "schema_name": import_request.tenant.schema_name,
                "source_dir": str(working_dir_path),
                "school_name_override": import_request.school_name_override or "",
                "stdout": stdout_buffer,
            }
            if archive_raw:
                command_kwargs["archive_raw"] = True

            call_command(command_name, **command_kwargs)

            raw_output = stdout_buffer.getvalue().strip()
            try:
                summary_payload = json.loads(raw_output) if raw_output else {}
            except json.JSONDecodeError:
                summary_payload = {"raw_output": raw_output}

            result_payload = {
                "command": command_name,
                "tenant_schema": import_request.tenant.schema_name,
                "working_dir": str(working_dir_path),
                "working_dir_retained": bool(keep_working_dir),
                "archive_raw": archive_raw,
                "executed_at": timezone.now().isoformat(),
                "attached_files": sorted(attached_names),
                "import_summary": summary_payload,
            }

            with schema_context(public_schema):
                import_request = TenantDataImportRequest.objects.get(pk=request_id)
                import_request.status = TenantDataImportRequest.STATUS_COMPLETED
                import_request.last_error = ""
                import_request.processed_at = timezone.now()
                import_request.result_payload = result_payload
                import_request.save(
                    update_fields=["status", "last_error", "processed_at", "result_payload", "updated_at"]
                )

            self.stdout.write(json.dumps(result_payload, indent=2, default=str))
        except Exception as exc:
            error_payload = {
                "command": spec.get("command_name") or "",
                "tenant_schema": import_request.tenant.schema_name,
                "working_dir": str(working_dir_path),
                "working_dir_retained": True,
                "archive_raw": archive_raw,
                "failed_at": timezone.now().isoformat(),
                "attached_files": sorted(attached_names),
                "raw_output": stdout_buffer.getvalue().strip(),
            }
            with schema_context(public_schema):
                import_request = TenantDataImportRequest.objects.get(pk=request_id)
                import_request.status = TenantDataImportRequest.STATUS_FAILED
                import_request.last_error = str(exc)
                import_request.processed_at = timezone.now()
                import_request.result_payload = error_payload
                import_request.save(
                    update_fields=["status", "last_error", "processed_at", "result_payload", "updated_at"]
                )
            keep_working_dir = True
            if isinstance(exc, CommandError):
                raise
            raise CommandError(str(exc)) from exc
        finally:
            if working_dir_path.exists() and not keep_working_dir:
                shutil.rmtree(working_dir_path, ignore_errors=True)
