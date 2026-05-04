from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Backfill historical communication rows into the unified message, delivery, stats, and gateway snapshots."

    def add_arguments(self, parser):
        parser.add_argument(
            "--all-tenants",
            action="store_true",
            default=False,
            help="Run across every non-public tenant schema.",
        )
        parser.add_argument(
            "--schema_name",
            default=None,
            help="Limit to a single tenant schema (overrides --all-tenants).",
        )
        parser.add_argument(
            "--refresh-balance",
            action="store_true",
            default=False,
            help="Refresh live gateway balance payloads where supported during the snapshot sync.",
        )

    def handle(self, *args, **options):
        from django_tenants.utils import get_tenant_model, schema_context

        all_tenants = options.get("all_tenants", False)
        schema_name = options.get("schema_name")

        if schema_name:
            with schema_context(schema_name):
                self._backfill_schema(schema_name, options)
            return

        if all_tenants:
            client_model = get_tenant_model()
            schemas = list(
                client_model.objects.exclude(schema_name="public").order_by("schema_name").values_list("schema_name", flat=True)
            )
            self.stdout.write(
                f"[backfill_communication_backbone] Running across {len(schemas)} tenant schema(s)."
            )
            for schema in schemas:
                with schema_context(schema):
                    self._backfill_schema(schema, options)
            return

        self._backfill_schema("<current>", options)

    def _backfill_schema(self, schema_label, options):
        from communication.historical_backfill import backfill_communication_backbone

        result = backfill_communication_backbone(
            include_balance=bool(options.get("refresh_balance")),
        )
        self.stdout.write(
            f"[{schema_label}] campaigns={result['campaigns_synced']} "
            f"email_recipients={result['email_recipients_synced']} "
            f"sms={result['sms_rows_synced']} "
            f"push={result['push_logs_synced']} "
            f"direct_email_tasks={result['direct_email_tasks_synced']} "
            f"task_links={result['task_links_attached']} "
            f"campaign_stats={result['campaign_stats_synced']} "
            f"gateway_channels={','.join(result['gateway_channels_synced'])}"
        )
