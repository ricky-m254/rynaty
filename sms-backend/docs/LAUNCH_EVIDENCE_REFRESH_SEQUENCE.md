# Launch Evidence Refresh Sequence

Last updated: 2026-04-27

Use this for `P2` immediately after the live validation work in [LIVE_PAYMENT_VALIDATION_RUN_SEQUENCE.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/sms-backend/docs/LIVE_PAYMENT_VALIDATION_RUN_SEQUENCE.md:1).

Primary references:

- [PAYMENT_SYSTEMS_LAUNCH_EVIDENCE.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/PAYMENT_SYSTEMS_LAUNCH_EVIDENCE.md:1)
- [PAYMENT_SYSTEMS_TASK_PLAN.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/PAYMENT_SYSTEMS_TASK_PLAN.md:1)
- [payments_launch_runbook.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/docs/payments_launch_runbook.md:1)

## Goal

Turn live execution results into dated launch evidence and a clear go/no-go state.

## Inputs Required

Before updating the tracker, collect:

- tenant name
- environment name and base URL
- operator name
- exact test date
- readiness response
- M-Pesa test-connection result
- callback URL proof
- bursar STK payment reference
- portal M-Pesa payment reference
- receipt proof locations
- Stripe result or waiver note
- gateway event IDs if relevant
- support or bursar signoff if available

## Step 1. Update Tenant And Scope Notes

Open [PAYMENT_SYSTEMS_LAUNCH_EVIDENCE.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/PAYMENT_SYSTEMS_LAUNCH_EVIDENCE.md:1) and refresh:

1. `TP-001` if the active launch tenant list changed
2. `TP-002` if human owners are now known
3. the tenant and owner register if real names can now replace provisional roles

Do not leave stale provisional wording if live owners are now confirmed.

## Step 2. Update Validation Rows

Update these rows first after a live validation pass:

- `TP-103` M-Pesa test connection
- `TP-104` callback URL proof
- `TP-106` parent portal smoke
- `TP-107` student portal smoke if it was run
- `TP-109` live M-Pesa settlement
- `TP-115` support or bursar walkthrough if completed

For each row, replace vague notes with:

- exact date
- tenant
- environment
- operator
- result
- payment reference or event ID
- evidence file or screenshot name

## Step 3. Resolve Status Values Honestly

Use these rules:

- `Complete` only when live evidence exists
- `In Progress` when local or synthetic proof exists but live proof is still missing
- `Blocked` when an external dependency still prevents completion
- `Deferred` only when scope is intentionally excluded

Important:

- do not mark Stripe complete if it was waived
- mark it `Deferred` or keep the existing waiver wording if the current Kenya scope still excludes it

## Step 4. Refresh The Supporting Plan

Open [PAYMENT_SYSTEMS_TASK_PLAN.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/PAYMENT_SYSTEMS_TASK_PLAN.md:1) and update:

1. the current status snapshot table
2. any workstream row whose status changed because of live proof
3. the dependency/status matrix if `TP-115` or `TP-116` can move

Keep the task plan and evidence tracker aligned on:

- tenant config validation
- staging payment validation
- bank CSV validation
- operator recovery drill

## Step 5. Record Remaining Blockers Explicitly

If something is still not done, write it in this form:

- blocker
- owner
- date observed
- next action

Examples:

- real bank sample still missing, owner: bursar, observed: 2026-04-27, next action: provide CSV before TP-111
- Stripe waived for Kenya rollout, owner: platform admin, observed: 2026-04-27, next action: reopen only if scope changes

## Step 6. Produce The Go / No-Go Note

After the evidence table is refreshed, add or update the final note for `TP-116`.

Minimum contents:

1. tenant validated
2. environment validated
3. flows that passed
4. flows waived
5. blockers still open
6. decision: `Go`, `Go with named waiver`, or `No-Go`

Recommended wording:

```text
Decision date: 2026-04-27
Tenant: <tenant>
Environment: <environment>
Decision: Go / Go with waiver / No-Go
Passed: <list>
Waived: <list>
Blocked: <list>
Owner signoff: <name or role>
```

## Step 7. Exit Criteria

`P2` is complete when:

- launch evidence reflects the current tenant list and live smoke results
- callback URL state is refreshed with live-environment proof
- any remaining blockers are named with owner and date
- `TP-116` has an explicit decision note
