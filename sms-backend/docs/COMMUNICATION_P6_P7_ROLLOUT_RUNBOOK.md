# Communication P6/P7 Rollout Runbook

## Purpose

This runbook covers rollout, smoke verification, and rollback for the additive communication changes delivered in phases `P6` and `P7`:

- ASGI + websocket communication streams
- DB-backed realtime event buffer and presence state
- queue-backed communication dispatch processing
- stored alert rules and alert events
- gateway settings and gateway test endpoints
- shipped alerts/settings/notifications UI cutovers
- unified communication backbone read models

This runbook is intentionally scoped to communication rollout. The deferred finance phase-6 canonical temp-cluster runner issue remains tracked separately in `FINANCE_PHASE6_POST_CLOSE_RUNBOOK.md`.

## Release Scope

The communication rollout includes these additive schema changes:

- `communication/migrations/0004_communicationdispatchtask.py`
- `communication/migrations/0005_unifiedmessage_messagedelivery_and_task_delivery.py`
- `communication/migrations/0006_campaignstats.py`
- `communication/migrations/0007_gatewaystatus.py`
- `communication/migrations/0008_communicationalertrule_communicationalertevent.py`
- `communication/migrations/0009_communicationrealtimeevent_communicationrealtimepresence.py`

It also includes these runtime changes:

- `requirements.txt`: `daphne==4.1.2`
- `config/settings.py`: `ASGI_APPLICATION = "config.asgi.application"`
- `config/asgi.py`: routes `/ws/communication/*` to `communication.realtime.communication_websocket_application`
- `start.sh`: boots the app with `daphne` and starts communication queue / alert loops

## Preconditions

Before rollout:

1. Confirm the release artifact contains the communication migrations above.
2. Confirm the runtime image/environment includes the updated Python dependencies from `requirements.txt`.
3. Confirm the deploy entrypoint uses `sms-backend/start.sh` or an equivalent command that starts `daphne`.
4. Confirm `DATABASE_URL` and tenant routing domains are already valid for the target environment.
5. Confirm a database backup or platform snapshot exists for the deployment window.

## Recommended Rollout Order

### One-command path

If you want the repo to run the remaining rollout steps in one command and emit an evidence report, use:

```bash
python3.11 manage.py finalize_communication_deployment --all-tenants
```

Safe local validation:

```bash
python3.11 manage.py finalize_communication_deployment --all-tenants --dry-run
```

The finalizer performs database readiness checks, runtime/runbook checks, migrations, backbone backfill, worker one-shot passes, the automated rollout verifier, and report generation under `artifacts/reports/`.

### 1. Deploy code and dependencies

Deploy the release that includes:

- `communication/realtime.py`
- `communication/models.py`
- `communication/views.py`
- `communication/dispatch_queue.py`
- `communication/alert_rules.py`
- `communication/gateway_settings.py`
- `communication/gateway_status.py`
- the updated built assets in `frontend_build/assets`

### 2. Run schema migrations

The repo startup path already performs tenant-aware migrations:

```bash
python3.11 manage.py migrate_schemas --shared --noinput --fake-initial
python3.11 manage.py migrate_schemas --noinput --fake-initial
```

If you are rehearsing or recovering manually, run the same tenant-aware migration flow before starting the web process.

### 3. Backfill the communication backbone once

Run the historical backfill once after the communication migrations are present:

```bash
python3.11 manage.py backfill_communication_backbone --all-tenants
```

Optional balance refresh:

```bash
python3.11 manage.py backfill_communication_backbone --all-tenants --refresh-balance
```

This step is idempotent and should be retained in operator notes even if the first rollout already executed it.

### 4. Start the ASGI web process

The repo's current production start path is:

```bash
python3.11 -m daphne -b 0.0.0.0 -p ${PORT:-8080} config.asgi:application
```

This is required for `/ws/communication/summary/` and `/ws/communication/conversations/<id>/`.

### 5. Start background communication loops

The current repo-native worker pattern is already in `start.sh` and should be active after deployment:

```bash
python3.11 manage.py dispatch_due_email_campaigns --all-tenants
python3.11 manage.py process_communication_dispatch_queue --all-tenants
python3.11 manage.py evaluate_communication_alert_rules --all-tenants
```

Then the repeating loops:

- due campaign enqueue: every 60 seconds
- dispatch queue worker: every 30 seconds
- alert rule evaluation: every 120 seconds

## Smoke Verification

Run these checks in order after deployment.

### HTTP contract smoke checks

Use an authenticated communication admin account and verify:

1. `GET /api/communication/analytics/summary/`
   - returns queue summary, unified counts, and gateway health
2. `GET /api/communication/alerts/feed/`
   - returns alerts, announcements, and reminders payloads
3. `GET /api/communication/settings/gateways/`
   - returns email / SMS / WhatsApp / push configuration with masked secret state
4. `GET /api/communication/notifications/unread-count/`
   - returns a valid unread count payload
5. `GET /api/communication/unified-messages/`
   - returns unified communication history rows
6. `GET /api/communication/messages/`
   - summary mode still returns the blended dashboard feed

### Automated verifier

For a repo-native smoke pass that exercises the rollout contracts without sending manual requests one by one, run:

```bash
python3.11 manage.py verify_communication_rollout --all-tenants
```

Optional balance refresh:

```bash
python3.11 manage.py verify_communication_rollout --all-tenants --include-balance
```

Expected result:

- one `ok` line per tenant schema
- route resolution for the core communication HTTP surfaces
- gateway settings / gateway health payload verification
- alerts feed payload verification
- unified-message feed verification
- ASGI websocket contract verification

### Queue / worker smoke checks

1. Create a scheduled campaign due now.
2. Run:

```bash
python3.11 manage.py dispatch_due_email_campaigns --all-tenants
python3.11 manage.py process_communication_dispatch_queue --all-tenants
```

3. Verify:
   - recipients move from `Queued` to `Sent`
   - `CommunicationDispatchTask` rows move out of ready backlog
   - summary queue counts update

### Alerting smoke checks

1. Verify at least one alert rule exists, or create one from the alerts page.
2. Run:

```bash
python3.11 manage.py evaluate_communication_alert_rules --all-tenants
```

3. Verify:
   - `/api/communication/alerts/events/summary/` returns current open counts
   - `/api/communication/alerts/feed/` shows stored alert events

### Websocket smoke checks

1. Obtain a valid access token for a communication-enabled user.
2. Connect to:

- `/ws/communication/summary/?token=<access_token>`
- `/ws/communication/conversations/<conversation_id>/?token=<access_token>`

3. Verify:
   - summary stream accepts the connection
   - a new notification or queue/update action emits a replayable event
   - conversation stream accepts the connection
   - typing and presence events appear for active conversation participants

### UI smoke checks

Verify the shipped built pages load and use backend contracts successfully:

- communication alerts center
- communication settings page
- communication notifications page

Specifically confirm:

- alerts page is reading backend alerts/feed data
- settings page reads and patches `/api/communication/settings/gateways/`
- settings page can invoke `/api/communication/settings/gateways/test/`
- notifications page can read unread count, mark all read, and load preferences

## Known Residual Verification Gap

The disposable local Postgres helper used during implementation is still unstable when it falls back from `pg_ctl` to direct `postgres.exe`. That issue caused partial DB-backed verification gaps for some focused websocket tests during local implementation.

This does **not** change the rollout path above. Treat it as a local disposable-cluster issue unless a stable staging or production-like Postgres environment reproduces the same failures.

## Rollback Strategy

The communication schema changes are additive. The safest rollback is application/runtime rollback, not destructive database rollback.

### Preferred rollback

1. Stop the new release.
2. Redeploy the previous application artifact/image.
3. Restore the previous process entrypoint if your deployment system overrides `start.sh`.
4. Leave the additive communication tables in place.

Do **not** drop:

- `CommunicationDispatchTask`
- `UnifiedMessage`
- `MessageDelivery`
- `CampaignStats`
- `GatewayStatus`
- `CommunicationAlertRule`
- `CommunicationAlertEvent`
- `CommunicationRealtimeEvent`
- `CommunicationRealtimePresence`

Older route paths were preserved intentionally, so the previous application version should remain compatible with the additive schema.

### Partial rollback for operational pressure

If the web app is healthy but communication background activity is causing issues:

1. Stop or disable only the communication worker loops:
   - `dispatch_due_email_campaigns`
   - `process_communication_dispatch_queue`
   - `evaluate_communication_alert_rules`
2. Keep the web process up.
3. Verify that read-only communication pages still load.
4. Re-enable the loops after the root cause is fixed.

### Realtime-specific rollback

If websocket behavior is the only problem:

1. Roll back the application/runtime release to the previous version.
2. Keep the additive realtime tables in the database.
3. Continue serving communication over the previous HTTP-only behavior until the websocket issue is resolved.

## Post-Rollout Evidence to Capture

Capture and retain:

- migration logs
- `backfill_communication_backbone` output
- one successful `dispatch_due_email_campaigns` run
- one successful `process_communication_dispatch_queue` run
- one successful `evaluate_communication_alert_rules` run
- screenshots or HAR evidence for:
  - alerts page
  - settings page
  - notifications page
- websocket connect and event replay evidence from a staging or production-like environment

## Closeout Criteria

This communication rollout can be considered operationally closed when:

1. migrations complete on shared + tenant schemas
2. backbone backfill has run at least once
3. ASGI/daphne serving is live
4. background communication loops are running
5. alerts/settings/notifications pages pass smoke checks
6. websocket summary and conversation streams connect successfully in a stable environment
7. rollback instructions have been rehearsed or accepted by the deployment owner
