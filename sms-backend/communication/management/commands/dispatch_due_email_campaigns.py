from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Enqueue scheduled communication email campaigns that are now due."

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
            "--campaign-id",
            action="append",
            dest="campaign_ids",
            type=int,
            help="Limit dispatch to one or more campaign IDs.",
        )

    def handle(self, *args, **options):
        from django_tenants.utils import get_tenant_model, schema_context

        all_tenants = options.get("all_tenants", False)
        schema_name = options.get("schema_name")

        if schema_name:
            with schema_context(schema_name):
                self._dispatch_schema(schema_name, options)
            return

        if all_tenants:
            client_model = get_tenant_model()
            schemas = list(
                client_model.objects.exclude(schema_name="public").order_by("schema_name").values_list("schema_name", flat=True)
            )
            self.stdout.write(
                f"[dispatch_due_email_campaigns] Running across {len(schemas)} tenant schema(s)."
            )
            for schema in schemas:
                with schema_context(schema):
                    self._dispatch_schema(schema, options)
            return

        self._dispatch_schema("<current>", options)

    def _dispatch_schema(self, schema_label, options):
        from communication.campaign_dispatch import dispatch_due_email_campaigns

        result = dispatch_due_email_campaigns(campaign_ids=options.get("campaign_ids"))
        self.stdout.write(
            f"[{schema_label}] dispatched={result['dispatched']}"
        )
        for row in result["results"]:
            self.stdout.write(
                f"  campaign_id={row['campaign_id']} status={row['status']} queued={row['queued']} processed={row['processed']}"
            )
