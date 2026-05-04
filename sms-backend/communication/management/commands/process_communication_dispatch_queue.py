from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Process queued communication dispatch work across one or more tenant schemas."

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
            "--batch-size",
            type=int,
            default=50,
            help="Maximum queued dispatch tasks to claim per schema run.",
        )
        parser.add_argument(
            "--channel",
            action="append",
            dest="channels",
            default=None,
            help="Optional channel filter (EMAIL, SMS, WHATSAPP, PUSH). May be repeated.",
        )

    def handle(self, *args, **options):
        from django_tenants.utils import get_tenant_model, schema_context

        all_tenants = options.get("all_tenants", False)
        schema_name = options.get("schema_name")

        if schema_name:
            with schema_context(schema_name):
                self._process_schema(schema_name, options)
            return

        if all_tenants:
            client_model = get_tenant_model()
            schemas = list(
                client_model.objects.exclude(schema_name="public").order_by("schema_name").values_list("schema_name", flat=True)
            )
            self.stdout.write(
                f"[process_communication_dispatch_queue] Running across {len(schemas)} tenant schema(s)."
            )
            for schema in schemas:
                with schema_context(schema):
                    self._process_schema(schema, options)
            return

        self._process_schema("<current>", options)

    def _process_schema(self, schema_label, options):
        from communication.dispatch_queue import process_dispatch_queue

        channels = [str(channel).upper() for channel in (options.get("channels") or [])]
        result = process_dispatch_queue(
            batch_size=int(options.get("batch_size") or 50),
            channels=channels or None,
        )
        self.stdout.write(
            f"[{schema_label}] processed={result['processed']} sent={result['sent']} retried={result['retried']} failed={result['failed']}"
        )
