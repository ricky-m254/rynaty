from __future__ import annotations

from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone


class Command(BaseCommand):
    help = "Run the remaining communication deployment finalization steps in one command."

    def add_arguments(self, parser):
        parser.add_argument(
            "--all-tenants",
            action="store_true",
            default=False,
            help="Run communication finalization across every non-public tenant schema.",
        )
        parser.add_argument(
            "--schema_name",
            default=None,
            help="Limit tenant-scoped steps to a single schema (overrides --all-tenants).",
        )
        parser.add_argument(
            "--include-balance",
            action="store_true",
            default=False,
            help="Allow rollout verification and backfill to refresh live gateway balance payloads where supported.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Do not execute migration/backfill/worker/verifier commands; only validate readiness and write the report.",
        )
        parser.add_argument(
            "--report-path",
            default=None,
            help="Optional absolute or repo-relative path for the generated rollout report.",
        )

    def handle(self, *args, **options):
        started_at = timezone.now()
        report_lines = [
            "# Communication Deployment Finalization Report",
            "",
            f"- Started at: `{started_at.isoformat()}`",
            f"- Dry run: `{'yes' if options.get('dry_run') else 'no'}`",
            f"- Scope: `{self._scope_label(options)}`",
            "",
        ]

        try:
            self._record_db_probe(report_lines)
            self._record_runtime_probe(report_lines)
            self._record_docs_probe(report_lines)

            if options.get("dry_run"):
                self._record_step(
                    report_lines,
                    title="Execution Plan",
                    status="PLANNED",
                    details=[
                        "`migrate_schemas --shared --noinput --fake-initial`",
                        "`migrate_schemas --noinput --fake-initial`",
                        "`backfill_communication_backbone`",
                        "`dispatch_due_email_campaigns`",
                        "`process_communication_dispatch_queue`",
                        "`evaluate_communication_alert_rules`",
                        "`verify_communication_rollout`",
                    ],
                )
            else:
                self._run_and_record(
                    report_lines,
                    title="Shared Migrations",
                    command_name="migrate_schemas",
                    args=["--shared", "--noinput", "--fake-initial"],
                )
                tenant_args = ["--noinput", "--fake-initial"]
                schema_name = options.get("schema_name")
                if schema_name:
                    tenant_args.insert(0, f"--schema={schema_name}")
                self._run_and_record(
                    report_lines,
                    title="Tenant Migrations",
                    command_name="migrate_schemas",
                    args=tenant_args,
                )
                self._run_and_record(
                    report_lines,
                    title="Communication Backbone Backfill",
                    command_name="backfill_communication_backbone",
                    kwargs=self._tenant_command_kwargs(options, refresh_balance=bool(options.get("include_balance"))),
                )
                self._run_and_record(
                    report_lines,
                    title="Due Campaign Enqueue",
                    command_name="dispatch_due_email_campaigns",
                    kwargs=self._tenant_command_kwargs(options),
                )
                self._run_and_record(
                    report_lines,
                    title="Dispatch Queue Worker",
                    command_name="process_communication_dispatch_queue",
                    kwargs=self._tenant_command_kwargs(options),
                )
                self._run_and_record(
                    report_lines,
                    title="Alert Rule Evaluation",
                    command_name="evaluate_communication_alert_rules",
                    kwargs=self._tenant_command_kwargs(options),
                )
                self._run_and_record(
                    report_lines,
                    title="Automated Rollout Verifier",
                    command_name="verify_communication_rollout",
                    kwargs=self._tenant_command_kwargs(options, include_balance=bool(options.get("include_balance"))),
                )

            self._record_step(
                report_lines,
                title="Manual Acceptance Follow-Up",
                status="DOCUMENTED",
                details=[
                    "Browser/UI and websocket smoke steps remain documented in `sms-backend/docs/COMMUNICATION_P6_P7_ROLLOUT_RUNBOOK.md`.",
                    "Finance phase-6 canonical temp-cluster follow-up remains deferred in `FINANCE_PHASE6_POST_CLOSE_RUNBOOK.md`.",
                ],
            )
        except Exception as exc:
            report_lines.extend(
                [
                    "",
                    "## Final Status",
                    "",
                    f"- Result: `FAILED`",
                    f"- Error: `{exc}`",
                ]
            )
            report_path = self._write_report(report_lines, requested_path=options.get("report_path"))
            raise CommandError(
                f"Communication deployment finalization failed. Report: {report_path}"
            ) from exc

        finished_at = timezone.now()
        report_lines.extend(
            [
                "",
                "## Final Status",
                "",
                "- Result: `READY FOR DEPLOYMENT`" if not options.get("dry_run") else "- Result: `DRY RUN COMPLETE`",
                f"- Finished at: `{finished_at.isoformat()}`",
            ]
        )
        report_path = self._write_report(report_lines, requested_path=options.get("report_path"))
        self.stdout.write(
            self.style.SUCCESS(
                f"Communication deployment finalization complete. Report: {report_path}"
            )
        )

    def _scope_label(self, options):
        if options.get("schema_name"):
            return f"schema={options['schema_name']}"
        if options.get("all_tenants"):
            return "all-tenants"
        return "current-schema"

    def _tenant_command_kwargs(self, options, *, include_balance: bool = False, refresh_balance: bool = False):
        kwargs = {}
        if options.get("schema_name"):
            kwargs["schema_name"] = options["schema_name"]
        elif options.get("all_tenants"):
            kwargs["all_tenants"] = True
        if include_balance:
            kwargs["include_balance"] = True
        if refresh_balance:
            kwargs["refresh_balance"] = True
        return kwargs

    def _record_db_probe(self, report_lines):
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
        if not row or row[0] != 1:
            raise CommandError("Database readiness probe did not return SELECT 1.")
        settings_dict = connection.settings_dict
        self._record_step(
            report_lines,
            title="Database Readiness",
            status="OK",
            details=[
                f"engine=`{settings_dict.get('ENGINE', '')}`",
                f"name=`{settings_dict.get('NAME', '')}`",
                f"host=`{settings_dict.get('HOST', '')}`",
                f"port=`{settings_dict.get('PORT', '')}`",
            ],
        )

    def _record_runtime_probe(self, report_lines):
        if settings.ASGI_APPLICATION != "config.asgi.application":
            raise CommandError("ASGI_APPLICATION is not configured for the communication websocket runtime.")
        requirements_text = (Path(settings.BASE_DIR) / "requirements.txt").read_text(encoding="utf-8")
        if "daphne==4.1.2" not in requirements_text:
            raise CommandError("requirements.txt is missing daphne==4.1.2.")
        start_text = (Path(settings.BASE_DIR) / "start.sh").read_text(encoding="utf-8")
        required_snippets = [
            "python3.11 -m daphne -b 0.0.0.0 -p ${PORT:-8080} config.asgi:application",
            "python3.11 manage.py dispatch_due_email_campaigns --all-tenants",
            "python3.11 manage.py process_communication_dispatch_queue --all-tenants",
            "python3.11 manage.py evaluate_communication_alert_rules --all-tenants",
        ]
        missing = [snippet for snippet in required_snippets if snippet not in start_text]
        if missing:
            raise CommandError(f"start.sh is missing required communication runtime hooks: {missing}")
        self._record_step(
            report_lines,
            title="Runtime Readiness",
            status="OK",
            details=[
                "`ASGI_APPLICATION` points to `config.asgi.application`.",
                "`requirements.txt` includes `daphne==4.1.2`.",
                "`start.sh` includes ASGI boot and communication background-loop hooks.",
            ],
        )

    def _record_docs_probe(self, report_lines):
        repo_root = Path(settings.BASE_DIR).parent
        rollout_doc = repo_root / "sms-backend" / "docs" / "COMMUNICATION_P6_P7_ROLLOUT_RUNBOOK.md"
        finance_doc = repo_root / "FINANCE_PHASE6_POST_CLOSE_RUNBOOK.md"
        missing = [str(path) for path in (rollout_doc, finance_doc) if not path.exists()]
        if missing:
            raise CommandError(f"Required rollout documentation is missing: {missing}")
        self._record_step(
            report_lines,
            title="Runbook Coverage",
            status="OK",
            details=[
                f"rollout=`{rollout_doc}`",
                f"finance_deferral=`{finance_doc}`",
            ],
        )

    def _run_and_record(self, report_lines, *, title: str, command_name: str, args=None, kwargs=None):
        args = list(args or [])
        kwargs = dict(kwargs or {})
        stdout_buffer = StringIO()
        stderr_buffer = StringIO()
        call_command(
            command_name,
            *args,
            stdout=stdout_buffer,
            stderr=stderr_buffer,
            **kwargs,
        )
        command_preview = [line for line in stdout_buffer.getvalue().splitlines() if line.strip()]
        if not command_preview:
            command_preview = [f"{command_name} completed without additional output."]
        self._record_step(
            report_lines,
            title=title,
            status="OK",
            details=command_preview[:8],
        )

    def _record_step(self, report_lines, *, title: str, status: str, details: list[str]):
        report_lines.extend(
            [
                f"## {title}",
                "",
                f"- Status: `{status}`",
            ]
        )
        for detail in details:
            report_lines.append(f"- {detail}")
        report_lines.append("")

    def _write_report(self, report_lines, *, requested_path: str | None):
        report_path = self._resolve_report_path(requested_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("\n".join(report_lines).rstrip() + "\n", encoding="utf-8")
        return report_path

    def _resolve_report_path(self, requested_path: str | None):
        if requested_path:
            candidate = Path(requested_path)
            if not candidate.is_absolute():
                candidate = Path(settings.BASE_DIR).parent / candidate
            return candidate
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        return Path(settings.BASE_DIR).parent / "artifacts" / "reports" / f"communication_deployment_finalize_{timestamp}.md"
