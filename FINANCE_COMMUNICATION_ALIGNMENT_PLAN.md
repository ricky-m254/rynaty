# Finance + Communications Alignment Plan

Date: 2026-04-28

## Purpose

This document is the current source of truth for aligning the repo with:

- [FINANCE_AUDIT.md](</c:/Users/emuri/OneDrive/Desktop/rsm docs/FINANCE_AUDIT.md>)
- [Unified_Communications_Platform_Production_Specification.pdf](</c:/Users/emuri/OneDrive/Desktop/rsm docs/Unified_Communications_Platform_Production_Specification.pdf>)

It is intentionally separate from [task.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/task.md) because that file is a completed historical register for an earlier implementation pass.

## Executive Summary

- The highest-risk finance corrective items are now functionally implemented in code.
- The remaining finance uncertainty in this wave is the canonical phase-6 disposable-cluster verification path, not a newly confirmed functional regression.
- The communications module already has substantial product surface area in backend code and built frontend bundles.
- The communications PDF is not a description of the current repo. It is a target-state architecture that would require a multi-phase implementation, not a one-pass patch.
- The recommended strategy is:
  - keep finance corrective work functionally closed unless the deferred phase-6 runner investigation proves otherwise
  - preserve the current communication product surface
  - incrementally introduce the spec capabilities underneath that surface
  - avoid a big-bang rewrite unless literal PDF compliance is the explicit goal

## Inputs Reviewed

- [FINANCE_AUDIT.md](</c:/Users/emuri/OneDrive/Desktop/rsm docs/FINANCE_AUDIT.md>)
- [Unified_Communications_Platform_Production_Specification.pdf](</c:/Users/emuri/OneDrive/Desktop/rsm docs/Unified_Communications_Platform_Production_Specification.pdf>)
- [school/urls.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/urls.py:1)
- [school/views.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/views.py:1)
- [school/services.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/services.py:1)
- [finance/urls.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/finance/urls.py:1)
- [finance/presentation/views.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/finance/presentation/views.py:1)
- [finance/presentation/viewsets.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/finance/presentation/viewsets.py:1)
- [finance/application/receivables.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/finance/application/receivables.py:1)
- [finance/application/report_queries.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/finance/application/report_queries.py:1)
- [finance/application/billing_setup.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/finance/application/billing_setup.py:1)
- [finance/application/cashbook.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/finance/application/cashbook.py:1)
- [communication/models.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/communication/models.py:1)
- [communication/urls.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/communication/urls.py:1)
- [communication/views.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/communication/views.py:1)
- [communication/services.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/communication/services.py:1)
- [config/asgi.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/config/asgi.py:1)
- [config/settings.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/config/settings.py:345)
- [start.sh](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/start.sh:1)
- [school/test_phase6_architecture_guardrails.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/test_phase6_architecture_guardrails.py:1)

## Confirmed Current State

### Finance Audit Items Already Corrected

- Finance webhook verification is implemented in [school/views.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/views.py:2523).
- Write-off approval now routes through adjustment creation and adjustment journaling in [school/services.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/services.py:1646).
- A staged finance presentation layer exists and is already mounted for a large portion of the finance surface in [school/urls.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/urls.py:179) and [finance/urls.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/finance/urls.py:1).
- Finance reference endpoints now have pagination helpers in [finance/application/reference_queries.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/finance/application/reference_queries.py:1).
- `finance/terms` is cut over to the finance presentation term viewset in [school/urls.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/urls.py:179).
- Finance student detail is registered on the finance-safe route in [school/urls.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/urls.py:320).
- Migration repair now includes school migration `0065` in [start.sh](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/start.sh:47).
- Invoice and payment journaling are now service-owned, atomic/idempotent code paths in [school/services.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/services.py:1481).
- Payment reversal approval now creates explicit GL reversal entries in [school/services.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/services.py:1896).
- Bulk fee assignment is now transaction-wrapped and locked in [finance/application/billing_setup.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/finance/application/billing_setup.py:82).
- Cashbook running-balance recomputation now uses transactional locking in [finance/application/cashbook.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/finance/application/cashbook.py:17).
- Finance report queries have already been moved away from the earlier Python-heavy loop shape in [finance/application/report_queries.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/finance/application/report_queries.py:1).

### Finance Audit Items Still Open

- The canonical disposable-cluster phase-6 runner is still unresolved as an accepted end-to-end verification path.
- That runner issue is deferred to [FINANCE_PHASE6_POST_CLOSE_RUNBOOK.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/FINANCE_PHASE6_POST_CLOSE_RUNBOOK.md:1).
- [finance/urls.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/finance/urls.py:1) remains unmounted duplicate code because [config/urls.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/config/urls.py:58) only mounts `school.urls`.

### Finance Architecture Drift

- The staged finance layer is real and largely wired.
- The live tenant router is still mixed across:
  - `finance.presentation.*`
  - `school.views`
- The current cutover state is explicitly codified in [school/test_phase6_architecture_guardrails.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/test_phase6_architecture_guardrails.py:1), which means route corrections will require test updates alongside code changes.

### Communication Features Already Present

- Conversations, participants, threaded messages, attachments, read receipts, unread counts, and reply tracking exist in [communication/models.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/communication/models.py:1) and [communication/views.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/communication/views.py:223).
- Notifications and notification preferences exist, including quiet hours and read/unread operations, in [communication/models.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/communication/models.py:79) and [communication/views.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/communication/views.py:395).
- Email campaigns, recipients, stats, and scheduled dispatch endpoints exist in [communication/views.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/communication/views.py:534).
- SMS and WhatsApp sending exist with tenant-scoped provider configuration in [communication/services.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/communication/services.py:349).
- Push sending and push device registration exist in [communication/views.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/communication/views.py:682).
- Template preview and announcements exist in [communication/views.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/communication/views.py:814).
- Communication analytics endpoints exist in [communication/urls.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/communication/urls.py:1) and [communication/views.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/communication/views.py:859).
- Communication webhook verification exists in [communication/services.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/communication/services.py:481) and is used by [communication/views.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/communication/views.py:751).
- Built frontend bundles exist for:
  - dashboard
  - messaging
  - email
  - SMS
  - notifications
  - announcements
  - templates
  - analytics
  - communication settings
  - alerts center

### Communication Gaps Against the PDF

- An additive `UnifiedMessage` + `MessageDelivery` backbone now exists for queued outbound delivery work, and a tenant-aware backfill command now projects older campaign, SMS, push, and direct-email rows into it, but the broader communication domain still uses additive sync rather than a full event-sourced rebuild path.
- A first-class `CampaignStats` snapshot model now exists for email campaign performance, but the broader communication domain still relies on additive sync rather than a full event-sourced projection layer.
- A first-class `GatewayStatus` snapshot model now exists for cross-channel gateway health/state, but it is still an additive snapshot layer rather than a full operational control plane.
- No vendor-specific Vendel or SIM-farm domain model exists in the live app path; the operational closeout is implemented over the existing SMS / WhatsApp gateway-health and queue surfaces instead.
- A DB-backed websocket/event-buffer layer now exists for communication summary and conversation streams, with replay, presence, and typing state persisted in the communication app rather than relying on browser-only state.
- Scheduled campaign dispatch now has a queue-driven scheduler/management-command path, but the manual HTTP action still exists as an operator trigger.
- Current send paths now enqueue onto DB-backed worker execution, but the route payloads and most screens still center on legacy channel tables rather than the unified domain objects.
- Celery and Redis-style worker infrastructure appears only in reference/example folders, not in the live app path.
- No main-app Docker Compose, Dockerfile, NGINX config, or Prometheus config was found under `sms-backend/`.
- The shipped alerts, settings, and notifications pages are now wired to the communication-owned backend contracts instead of relying primarily on synthetic browser composition or school-owned settings endpoints.

### Communication Areas That Are Partial Rather Than Missing

- API security is not blank:
  - JWT auth is configured in [config/settings.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/config/settings.py:345)
  - generic DRF throttling is configured in [config/settings.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/config/settings.py:359)
  - webhook verification exists for finance and communication
- Tenant isolation is not missing:
  - the live app already uses tenant schema separation
  - this diverges from the PDF's early shared-database examples, but it is not a regression
- Frontend coverage is broader than the backend architecture:
  - many pages already exist as built bundles
  - the missing pieces are mostly backend contract, worker, realtime, and ops layers

## Document-to-Repo Gap Matrix

### Finance Audit

- Audit `8.1` migration 0065 repair: `Fixed`
- Audit `8.2` `finance/terms` routing fix: `Fixed`
- Audit `9.2` webhook verification: `Fixed`
- Audit `11.3` finance student detail route registration: `Fixed`
- Audit silent journal failure handling: `Fixed`
- Audit invoice + journal atomicity: `Fixed`
- Audit write-off accounting gap: `Substantially improved`
- Audit payment reversal accounting gap: `Fixed`
- Audit duplicate `finance/urls.py`: `Open`
- Audit bulk assignment atomicity and cashbook race concerns: `Substantially improved`

### Communications PDF

- Section `2` system architecture: `Partial`
- Section `3` unified core models: `Missing`
- Section `4` channel worker architecture: `Missing in live app`
- Section `5.1` REST endpoints: `Partial but materially different contract`
- Section `5.2` websocket events: `Implemented additively`
- Section `6` frontend UI/UX: `Mostly present at page level, partial at behavior/data-contract level`
- Section `7` realtime layer: `Implemented additively`
- Section `8` security/access control: `Partial`
- Section `9` deployment playbook: `Mostly missing from live app path`
- Section `10` scaling runbook: `Missing as implemented infrastructure`
- Section `11` implementation checklist: `Only partially completed`

## Strategic Recommendation

### Phase-6 Verification Note

- Do not spend more retries on the temp-cluster canonical phase-6 runner during the current wave.
- Treat the runner issue as a deferred environment/runbook item, not as the active blocker for communication `P4`.
- Reopen that investigation only through [FINANCE_PHASE6_POST_CLOSE_RUNBOOK.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/FINANCE_PHASE6_POST_CLOSE_RUNBOOK.md:1).

### Recommended Track

- Treat the finance work as corrective production work.
- Treat the communication PDF as a target-state epic.
- Preserve current route shapes where possible:
  - `/api/communication/*`
  - existing finance tenant routes
- Build compatibility layers under the current surface instead of replacing the surface immediately.

### Avoid

- Do not re-open the completed historical register in [task.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/task.md).
- Do not do a one-step rewrite to the PDF's `/api/v1/*` contract unless the team explicitly chooses literal spec compliance over incremental evolution.
- Do not replace current tenant schema isolation with the PDF's earlier shared-database examples.

## Execution Plan

### P0. Finance Runtime Blockers

Status: `Functionally complete`

Why this comes first:

- It closes known production and routing hazards.
- It finishes the staged-finance cutover in the most visibly broken places.
- It is lower-risk than starting communication architecture work first.

Primary work items:

- add migration-0065 repair logic to [start.sh](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/start.sh:47)
- switch `finance/terms` to the finance presentation term viewset in [school/urls.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/urls.py:179)
- register `FinanceStudentDetailView` from [school/views.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/views.py:4665)
- update route ownership expectations in [school/test_phase6_architecture_guardrails.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/test_phase6_architecture_guardrails.py:1)

Acceptance criteria:

- tenant startup repair handles schemas missing migration 0065 state
- accountants can use `/api/finance/terms/` without being blocked by academics permissions
- finance-only users can load student detail from a finance-safe route
- guardrail tests describe the new intended cutover state instead of preserving the old mixed state

### P1. Finance Accounting Integrity

Status: `Functionally complete`

Why this comes second:

- These are correctness issues, not just cleanup.
- They touch money, ledgers, and auditability.

Primary work items:

- move invoice creation + GL posting into one atomic/idempotent boundary
- replace silent journal swallow in [finance/application/receivables.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/finance/application/receivables.py:207)
- add explicit GL reversal logic to payment reversal approval
- verify write-off journaling with focused regression coverage

Acceptance criteria:

- invoice creation cannot leave an invoice without the intended journal entry
- journal post failures surface clearly and fail safely
- payment reversal approval creates a reversible accounting trail
- focused accounting tests cover invoice create, payment reversal, and write-off approval paths

### P2. Finance Cleanup and Performance

Status: `Do Next`

Primary work items:

- decide whether to remove or mount [finance/urls.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/finance/urls.py:1)
- make bulk fee and optional-charge assignment atomic
- add safer running-balance recomputation or incremental rebalance strategy
- optimize arrears, class balances, and aging queries
- review trial balance and ledger query scaling behavior

Acceptance criteria:

- no dead-code URL surface remains ambiguous
- bulk class assignment either fully succeeds or fully rolls back
- cashbook updates are safe under concurrent writes
- key finance reports avoid unnecessary Python-side fanout for common workloads

### P3. Communication Decision Gate

Status: `Decided`

Decision to record:

- `Incremental alignment`

Recommended choice:

- `Incremental alignment`

Reason:

- the repo already has working communication features and built pages
- the PDF implies a bigger infrastructure and model overhaul than the current app needs for a first pass
- preserving current routes and user-visible screens reduces rollout risk

Recorded implementation note:

- communication alignment is proceeding on the `Incremental alignment` track
- the first foundation slice is shared scheduled-campaign dispatch logic plus a tenant-aware management-command execution path so scheduled email campaigns no longer depend only on the manual HTTP dispatch action

### P4. Communication Foundation Layer

Status: `Functionally complete`

Primary work items:

- keep the current route surface and move outbound dispatch onto DB-backed queue/outbox records
- automate scheduled campaign dispatch through tenant-aware management commands
- introduce worker processing for email, SMS/WhatsApp, and push delivery work
- wire background command loops into [start.sh](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/start.sh:365)
- add baseline observability for delivery, failure, and queue health

Acceptance criteria:

- scheduled campaigns do not depend on a manual HTTP endpoint call
- outbound campaign, SMS/WhatsApp, and push dispatch no longer perform all provider work in request threads
- queue health and delivery failures are observable in a machine-readable way

### P5. Communication Domain and API Alignment

Status: `Active next stream`

Primary work items:

- introduce a unified communication core:
  - unified message aggregate
  - per-channel delivery records
  - campaign statistics
  - gateway health/state
- adapt current endpoints to the new service layer
- decide whether to add a versioned API alongside current routes or keep current route shapes with richer payloads

Current implementation note:

- additive `P5` read-model slices are now in place through unified delivery-history analytics, first-class campaign-performance analytics, and cross-channel gateway-health analytics while preserving current send routes and worker flows
- the first unified write-model slice is now in place through `UnifiedMessage` and `MessageDelivery`, with queued campaign, direct email, SMS/WhatsApp, and push dispatch dual-writing into the new backbone while keeping the legacy channel tables active
- the backbone is now queryable through unified-message list/detail API views so route responses that return `message_id` can be followed into delivery fan-out state without forcing a frontend rewrite to legacy table joins
- the existing campaign, recipient, SMS, and push payloads now surface unified `message_id` / delivery reference fields directly so current screens can bridge into the new backbone incrementally
- campaign performance is now backed by a persistent `CampaignStats` snapshot that is synchronized from recipient enqueue/send/webhook lifecycle changes instead of being only a read-time aggregate
- gateway health/state is now backed by a persistent `GatewayStatus` snapshot that is refreshed from queue/send/webhook/device lifecycle changes and by the gateway-health read path
- a tenant-aware `backfill_communication_backbone` command now rebuilds historical campaign, SMS, push, and queued direct-email rows into `UnifiedMessage`, `MessageDelivery`, `CampaignStats`, and `GatewayStatus` so older legacy rows can bridge into the unified domain without waiting for new outbound traffic

Acceptance criteria:

- a single communication event can be represented centrally and fan out to one or more delivery attempts
- delivery history is no longer fragmented across unrelated tables only
- campaign metrics are first-class rather than inferred ad hoc
- current frontend screens can consume the new backend without a forced rewrite

### P6. Communication Realtime and Ops Layer

Status: `Functionally complete`

Primary work items:

- add websocket routing and connection management
- implement presence, typing, and delivery-status fanout
- add event buffering / replay for reconnecting clients
- build real gateway-status and SIM/Vendel operations backend
- replace alerts-page synthetic behavior with a backend alert-rule model and execution path

Current implementation note:

- the first `P6` ops slice is now in place through stored `CommunicationAlertRule` / `CommunicationAlertEvent` models, admin alert rule/event APIs, a tenant-aware `evaluate_communication_alert_rules` command, and a startup/background loop that evaluates queue and gateway alert conditions outside the browser
- the alerts-center backend contract is now additive and explicit through `/api/communication/alerts/feed/`, which consolidates stored alert events, live announcements, and backend-generated operational reminders so the UI no longer needs to synthesize those sections entirely in-browser
- websocket-capable ASGI serving is now in place through [config/asgi.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/config/asgi.py:1), [config/settings.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/config/settings.py:253), [requirements.txt](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/requirements.txt:1), and [start.sh](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/start.sh:200)
- a DB-backed realtime event buffer and presence store now exist through [communication/models.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/communication/models.py:1), [communication/migrations/0009_communicationrealtimeevent_communicationrealtimepresence.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/communication/migrations/0009_communicationrealtimeevent_communicationrealtimepresence.py:1), and [communication/realtime.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/communication/realtime.py:1)
- existing message, notification, dispatch-queue, webhook, alert, and gateway-status mutation paths now append replayable realtime events instead of requiring a separate fanout infrastructure path
- the SMS / WhatsApp operational closeout now rides on stored `GatewayStatus` snapshots with queue backlog, recent successes, recent failures, balance, and push-device state rather than a separate vendor-specific backend

Acceptance criteria:

- message read and delivery changes can appear without polling
- connected clients can subscribe to rooms or scoped streams safely
- the alerts center is backed by stored alert rules rather than only frontend composition
- SMS operations UI has a real gateway status source of truth

### P7. Communication UI Alignment

Status: `Functionally complete`

Primary work items:

- wire existing communication pages to the evolved backend contracts
- close the biggest PDF-to-UI gaps:
  - SIM/Vendel dashboard behaviors
  - richer dashboard live feed
  - notification center behavior
  - alerts rule builder
  - settings gateway configuration depth
- verify mobile and desktop behavior against existing product expectations

Acceptance criteria:

- existing built pages still function after backend changes
- missing spec-backed screens or behaviors are implemented without regressing current flows
- communication settings can manage the real operational configuration needed by the backend

Current implementation note:

- communication now exposes a first-class `/api/communication/settings/gateways/` contract that reads and writes the real school-profile and tenant-setting-backed gateway configuration paths, returns masked secret state for email/SMS/WhatsApp/push credentials, and includes live communication gateway health beside the editable settings payload
- gateway test execution now also runs through a shared backend path, with `/api/communication/settings/gateways/test/` added for communication-owned checks while the existing school test-email and test-sms routes reuse the same helper so the live settings UI and the new communication contract stay aligned
- the live communication dashboard now gets a richer backend-driven recent-activity feed through summary-mode `/api/communication/messages/` responses, which blend unified delivery backbone items, announcements, and conversation messages without changing the conversation-thread contract used by the messaging page
- the shipped alerts-center asset now consumes `/api/communication/alerts/feed/` plus stored alert rule/event APIs instead of synthesizing its main state from dashboard values
- the shipped communication settings asset now uses `/api/communication/settings/gateways/` and `/api/communication/settings/gateways/test/`, and surfaces email/SMS/WhatsApp/push secret state, queue state, recent outcomes, and live gateway health
- the shipped notifications asset now uses unread-count, read-all, admin recipient lookup, scoped admin list behavior, and notification-preferences instead of only basic CRUD operations

### P8. Verification and Rollout

Status: `Required for each phase`

Primary work items:

- add route-resolution tests for finance cutover
- add tenant migration repair tests for 0065
- add accounting integrity tests for invoice, reversal, and write-off flows
- add communication worker tests
- add webhook verification tests
- add websocket tests if realtime is introduced
- rehearse migrations on a non-production tenant schema
- stage rollout with rollback notes

Current implementation note:

- focused websocket regression coverage is now present in [communication/tests.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/communication/tests.py:2611) for summary-stream replay and conversation-stream replay/presence/typing behavior, alongside the expanded gateway-health assertions at [communication/tests.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/communication/tests.py:1792)
- syntax and import-level validation are green for the additive realtime/ASGI path, but disposable Postgres verification for the new websocket tests remains partially open because the temp cluster still falls back to direct `postgres.exe` startup and has not stayed stable across repeated DB-backed test invocations
- rollout order, smoke checks, and rollback guidance for the additive communication P6/P7 release are now documented in [COMMUNICATION_P6_P7_ROLLOUT_RUNBOOK.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/docs/COMMUNICATION_P6_P7_ROLLOUT_RUNBOOK.md:1)
- a tenant-aware `verify_communication_rollout` management command now exists to automate the core rollout smoke checks for routes, gateway payloads, alerts feed payloads, unified-message feed availability, and ASGI websocket enablement
- a tenant-aware `finalize_communication_deployment` management command now exists to run the remaining rollout steps in one command, including readiness checks, migrations, backbone backfill, worker one-shot passes, rollout verification, and evidence report generation

Acceptance criteria:

- every high-risk path has focused regression coverage
- data migrations are rehearsed before production use
- rollout order and rollback steps are documented before deployment

## First Implementation Batch

This batch is now historical and functionally complete:

1. [start.sh](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/start.sh:47)
2. [school/urls.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/urls.py:179)
3. [school/views.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/views.py:4665)
4. [school/test_phase6_architecture_guardrails.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/test_phase6_architecture_guardrails.py:1)
5. [finance/application/receivables.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/finance/application/receivables.py:207)
6. [finance/presentation/viewsets.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/finance/presentation/viewsets.py:175)
7. [school/services.py](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/school/services.py:1846)

## Non-Goals for the First Batch

- no big-bang communication rewrite
- no forced route renaming to `/api/v1/*`
- no speculative FastAPI split
- no schema-model churn for communication until the foundation decision is recorded

## Closure Condition

This register is complete only when:

- P0 and P1 are functionally complete and any remaining canonical phase-6 runner follow-up is captured in the post-close runbook
- P3 is explicitly decided
- either:
  - the communication work is scheduled as an incremental multi-phase roadmap
  - or a deliberate decision is made to pursue literal PDF compliance as a separate epic
