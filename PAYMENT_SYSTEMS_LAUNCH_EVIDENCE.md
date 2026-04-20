# Payment Systems Launch Evidence
## Baseline And Validation Tracker

**Created:** April 19, 2026  
**Purpose:** Central place to freeze the current launch-candidate baseline and capture evidence for payment launch validation

---

## Frozen Validation Baseline

Use this baseline for all launch-validation evidence unless a newer candidate is explicitly approved.

| Field | Value |
|------|-------|
| Frozen at | April 19, 2026 23:32:25 -07:00 |
| Git branch | `main` |
| Candidate commit | `e96e303d865f75cf43402d669a61f318611f3c47` |
| Source docs | `PAYMENT_SYSTEMS_SECOND_AUDIT.md`, `PAYMENT_SYSTEMS_FASTTRACK_PLAN.md`, `PAYMENT_SYSTEMS_TASK_PLAN.md` |

### Workspace note at freeze time

The workspace was not fully clean when this baseline was recorded.

Observed local changes:

- `PAYMENT_SYSTEMS_FASTTRACK_PLAN.md` modified
- `PAYMENT_SYSTEMS_SECOND_AUDIT.md` untracked
- `PAYMENT_SYSTEMS_TASK_PLAN.md` untracked
- `sms-backend/parent_portal/student_portal_views.py` modified for a non-functional docstring clarification

Interpretation:

- payment code paths were already repo-verified before this freeze
- the local workspace overlay is documentation-focused, not a new unverified payment implementation phase
- any staging validation should still record the exact environment, tenant, and build used

---

## Evidence Rules

Every completed task should capture at least one of:

- API response capture
- screenshot
- test run output
- staging payment reference
- gateway event ID
- bank import file name and result summary
- signoff note from finance / support / bursar

Recommended naming convention:

- `YYYY-MM-DD_<tenant>_<task-id>_<short-description>`

Examples:

- `2026-04-20_demo-school_TP-101_launch-readiness.json`
- `2026-04-20_demo-school_TP-108_stripe-checkout-success.png`
- `2026-04-20_demo-school_TP-114_gateway-event-reprocess.md`

---

## Evidence Tracker

| Task ID | Task | Status | Evidence Location | Evidence Summary | Notes |
|--------|------|--------|-------------------|------------------|-------|
| TP-001 | Confirm launch tenant list | In Progress | `docs/finance_test_report.md`, `sms-backend/clients/management/commands/seed_platform_data.py`, `sms-backend/parent_portal/tests.py` | Repo/docs show `demo_school` as the primary demo tenant under finance test and `demo_school_smoke_test` as a smoke-test-only tenant | Final staging/production launch list still needs owner confirmation |
| TP-002 | Confirm access and credentials ownership | Blocked | TBD | TBD | Waiting on platform / finance owner confirmation |
| TP-003 | Freeze launch-candidate baseline | Complete | `PAYMENT_SYSTEMS_LAUNCH_EVIDENCE.md` | Baseline frozen at commit `e96e303d865f75cf43402d669a61f318611f3c47` on `main` | Workspace note captured above |
| TP-004 | Create evidence tracker | Complete | `PAYMENT_SYSTEMS_LAUNCH_EVIDENCE.md` | Central validation tracker created | Use this file to append results and links |
| TP-101 | Run readiness endpoint per tenant | Pending | TBD | TBD | Add one row per tenant if needed |
| TP-102 | Validate Stripe test connection | Pending | TBD | TBD | Record account name and mode |
| TP-103 | Validate M-Pesa test connection | Pending | TBD | TBD | Record environment and callback host |
| TP-104 | Validate public callback and webhook URLs | Pending | TBD | TBD | Capture readiness and callback-url proof |
| TP-105 | Resolve tenant config gaps | Pending | TBD | TBD | Link rerun readiness output |
| TP-106 | Parent portal staging smoke test | Pending | TBD | TBD | Capture all three payment method results |
| TP-107 | Student portal staging smoke test | Pending | TBD | TBD | Capture all three payment method results |
| TP-108 | Stripe end-to-end staging settlement | Pending | TBD | TBD | Include payment ref + event ID |
| TP-109 | M-Pesa end-to-end staging settlement | Pending | TBD | TBD | Include checkout request ID + receipt/event |
| TP-110 | Collect real bank statement samples | Pending | TBD | TBD | Track bank name and sample owner |
| TP-111 | Import real statement file | Pending | TBD | TBD | Record import file and result |
| TP-112 | Validate reconciliation outcomes | Pending | TBD | TBD | Capture match / unmatched / clear examples |
| TP-113 | Exercise failed-event inspection | Pending | TBD | TBD | Capture filtered event list |
| TP-114 | Exercise manual reprocess | Pending | TBD | TBD | Capture event ID and result |
| TP-115 | Run support / bursar walkthrough | Pending | TBD | TBD | Signoff note or annotated runbook |
| TP-116 | Produce launch go/no-go summary | Pending | TBD | TBD | Final decision note |

---

## Tenant And Owner Register

Fill this in before staging execution begins.

| Tenant | Environment | Owner | Stripe Owner | M-Pesa Owner | Bank Sample Owner | Notes |
|--------|-------------|-------|--------------|--------------|-------------------|-------|
| demo_school | Candidate staging/demo tenant | TBD | TBD | TBD | TBD | Referenced as the tenant under finance end-to-end test in `docs/finance_test_report.md` and as the default demo tenant in `sms-backend/clients/management/commands/seed_platform_data.py` |
| demo_school_smoke_test | Test-only smoke tenant | N/A | N/A | N/A | N/A | Created in `sms-backend/parent_portal/tests.py`; useful for smoke coverage reference, not a launch tenant by default |
| TBD | TBD | TBD | TBD | TBD | TBD | TBD |

---

## Signoff Log

| Date | Area | Decision / Signoff | Owner | Notes |
|------|------|--------------------|-------|-------|
| TBD | TBD | TBD | TBD | TBD |
