from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Evaluate stored communication alert rules and persist alert events across one or more tenant schemas."

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

    def handle(self, *args, **options):
        from django_tenants.utils import get_tenant_model, schema_context

        all_tenants = options.get("all_tenants", False)
        schema_name = options.get("schema_name")

        if schema_name:
            with schema_context(schema_name):
                self._evaluate_schema(schema_name)
            return

        if all_tenants:
            client_model = get_tenant_model()
            schemas = list(
                client_model.objects.exclude(schema_name="public").order_by("schema_name").values_list("schema_name", flat=True)
            )
            self.stdout.write(
                f"[evaluate_communication_alert_rules] Running across {len(schemas)} tenant schema(s)."
            )
            for schema in schemas:
                with schema_context(schema):
                    self._evaluate_schema(schema)
            return

        self._evaluate_schema("<current>")

    def _evaluate_schema(self, schema_label):
        from communication.alert_rules import evaluate_communication_alert_rules

        result = evaluate_communication_alert_rules()
        self.stdout.write(
            f"[{schema_label}] evaluated={result['rules_evaluated']} triggered={result['triggered']} "
            f"open={result['opened']} updated={result['updated']} resolved={result['resolved']}"
        )
