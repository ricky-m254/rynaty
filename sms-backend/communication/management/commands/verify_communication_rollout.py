from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.urls import Resolver404, resolve


class Command(BaseCommand):
    help = "Verify the additive communication rollout contracts across one or more tenant schemas."

    REQUIRED_HTTP_PATHS = (
        "/api/communication/analytics/summary/",
        "/api/communication/alerts/feed/",
        "/api/communication/settings/gateways/",
        "/api/communication/settings/gateways/test/",
        "/api/communication/notifications/unread-count/",
        "/api/communication/unified-messages/",
    )

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
            "--include-balance",
            action="store_true",
            default=False,
            help="Allow gateway verification to refresh live SMS balance payloads where supported.",
        )

    def handle(self, *args, **options):
        from django_tenants.utils import get_tenant_model, schema_context

        all_tenants = options.get("all_tenants", False)
        schema_name = options.get("schema_name")

        if schema_name:
            with schema_context(schema_name):
                self._verify_schema(schema_name, options)
            return

        if all_tenants:
            client_model = get_tenant_model()
            schemas = list(
                client_model.objects.exclude(schema_name="public").order_by("schema_name").values_list("schema_name", flat=True)
            )
            self.stdout.write(
                f"[verify_communication_rollout] Running across {len(schemas)} tenant schema(s)."
            )
            for schema in schemas:
                with schema_context(schema):
                    self._verify_schema(schema, options)
            return

        self._verify_schema("<current>", options)

    def _resolve_required_paths(self):
        resolved = {}
        for path in self.REQUIRED_HTTP_PATHS:
            try:
                match = resolve(path)
            except Resolver404 as exc:
                raise CommandError(f"Required communication route does not resolve: {path}") from exc
            resolved[path] = getattr(getattr(match.func, "view_class", None), "__name__", "") or str(match.func)
        return resolved

    def _verify_schema(self, schema_label, options):
        from communication.dispatch_queue import get_dispatch_queue_health_payload
        from communication.gateway_settings import build_communication_gateway_settings_payload
        from communication.models import (
            CommunicationAlertEvent,
            CommunicationDispatchTask,
            CommunicationRealtimeEvent,
            CommunicationRealtimePresence,
            GatewayStatus,
            MessageDelivery,
            Notification,
            PushDevice,
            UnifiedMessage,
        )
        from communication.read_models import (
            build_alerts_center_payload,
            build_gateway_health_payload,
            build_unified_message_feed,
        )
        from communication.realtime import communication_websocket_application

        route_map = self._resolve_required_paths()
        queue_health = get_dispatch_queue_health_payload()
        gateway_health = build_gateway_health_payload(include_balance=bool(options.get("include_balance")))
        gateway_settings = build_communication_gateway_settings_payload()
        alerts_payload = build_alerts_center_payload(alert_limit=5, announcement_limit=5, reminder_limit=5)
        unified_feed = build_unified_message_feed(limit=5)

        for key in ("email", "sms", "whatsapp", "push"):
            if key not in gateway_health:
                raise CommandError(f"Gateway health payload missing channel '{key}' on schema '{schema_label}'.")
            if key not in gateway_settings:
                raise CommandError(f"Gateway settings payload missing channel '{key}' on schema '{schema_label}'.")
            if "configured" not in gateway_health[key]:
                raise CommandError(f"Gateway health channel '{key}' is missing the configured flag on schema '{schema_label}'.")
            if "settings_configured" not in gateway_settings[key]:
                raise CommandError(f"Gateway settings channel '{key}' is missing settings_configured on schema '{schema_label}'.")

        for key in ("summary", "announcements", "alerts", "reminders"):
            if key not in alerts_payload:
                raise CommandError(f"Alerts payload missing '{key}' on schema '{schema_label}'.")

        websocket_enabled = (
            settings.ASGI_APPLICATION == "config.asgi.application"
            and callable(communication_websocket_application)
        )
        if not websocket_enabled:
            raise CommandError(
                f"Realtime ASGI websocket contract is not enabled on schema '{schema_label}'."
            )

        summary = alerts_payload["summary"]
        self.stdout.write(
            f"[{schema_label}] ok "
            f"routes={len(route_map)} "
            f"queue_total={queue_health['total']} "
            f"queue_ready={queue_health['ready']} "
            f"announcements={summary['announcements']} "
            f"alerts={summary['system_alerts']} "
            f"reminders={summary['reminders']} "
            f"unified_messages={UnifiedMessage.objects.count()} "
            f"deliveries={MessageDelivery.objects.count()} "
            f"dispatch_tasks={CommunicationDispatchTask.objects.count()} "
            f"notifications={Notification.objects.count()} "
            f"gateway_rows={GatewayStatus.objects.count()} "
            f"alert_events={CommunicationAlertEvent.objects.count()} "
            f"realtime_events={CommunicationRealtimeEvent.objects.count()} "
            f"realtime_presence={CommunicationRealtimePresence.objects.count()} "
            f"push_devices={PushDevice.objects.filter(is_active=True).count()} "
            f"feed_preview={len(unified_feed)} "
            f"websocket_enabled={'yes' if websocket_enabled else 'no'}"
        )
