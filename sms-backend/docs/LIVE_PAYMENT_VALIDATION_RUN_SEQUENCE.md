# Live Payment Validation Run Sequence

Last updated: 2026-04-27

Use this for `P1` after secret rotation is stable.

Primary references:

- [payments_launch_runbook.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/docs/payments_launch_runbook.md:1)
- [PAYMENT_SYSTEMS_LAUNCH_EVIDENCE.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/PAYMENT_SYSTEMS_LAUNCH_EVIDENCE.md:1)
- [PAYMENT_SYSTEMS_TASK_PLAN.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/PAYMENT_SYSTEMS_TASK_PLAN.md:1)

## Scope Note

As of April 27, 2026:

- the current Kenya launch gate is still M-Pesa and bank-transfer focused
- Stripe remains implemented and should be validated if it is enabled in the target environment or if launch scope has been reopened
- if Stripe stays out of launch scope, record an explicit waiver note with date and owner during this run

## Operator Inputs

Before starting, confirm:

- target tenant name
- target environment URL
- named operator
- bursar test student or invoice
- parent or student test account
- test phone number for M-Pesa STK
- whether Stripe is enabled for this environment

Recommended evidence naming:

- `YYYY-MM-DD_<tenant>_P1-01_bursar-stk.png`
- `YYYY-MM-DD_<tenant>_P1-02_portal-mpesa.png`
- `YYYY-MM-DD_<tenant>_P1-03_receipt-proof.png`
- `YYYY-MM-DD_<tenant>_P1-04_gateway-events.png`

## Step 1. Capture Readiness Snapshot

Run:

```text
GET /api/finance/launch-readiness/
POST /api/finance/mpesa/test-connection/
GET /api/finance/mpesa/callback-url/
```

Capture:

- readiness response
- M-Pesa test-connection result
- callback URL result

Do not continue if:

- M-Pesa test connection fails
- callback URL is not HTTPS
- callback source still falls back incorrectly

## Step 2. Bursar STK Validation

From the finance admin or bursar payment form:

1. select a real test student with an open invoice
2. choose `M-Pesa STK Push`
3. enter the target phone number
4. submit the payment
5. complete the prompt on the handset

Confirm:

- initiation succeeds
- checkout request ID or equivalent reference is visible
- callback settles the transaction
- a real payment record is created
- invoice balance updates correctly
- downloadable receipt becomes available

Evidence to save:

- form success state
- resulting receipt view or receipt link
- payment list row showing the new payment

## Step 3. Portal M-Pesa Validation

Use either a parent portal account or a student portal account.

Run:

1. open an unpaid invoice
2. choose `M-Pesa`
3. enter the phone number
4. initiate payment
5. complete the handset prompt
6. wait for polling or refresh until final status appears

Confirm:

- initiation returns a checkout request ID
- final status is shown in the portal
- payment history updates
- downloadable receipt is available
- school-side payment record reflects the same settlement

Evidence to save:

- payment modal or initiation screen
- final success state
- portal payment history row
- receipt proof

## Step 4. Bank-Transfer Portal Sanity Check

Even though the main live proof is M-Pesa, capture one quick bank-transfer initiation in the same environment.

Run:

1. open an unpaid invoice
2. choose `Bank Transfer`
3. create the transfer reference

Confirm:

- a manual reference is generated
- narration or deposit instructions are shown
- the UI does not pretend the balance is already settled

Evidence to save:

- reference/instruction screen

## Step 5. Conditional Stripe Validation

Only run this if Stripe is enabled in the target environment or if launch scope has been reopened.

Run:

1. initiate Stripe from the relevant flow
2. complete checkout
3. confirm webhook settlement
4. confirm payment record creation
5. confirm receipt availability

If Stripe is not in scope:

- record `Stripe validation waived for current Kenya rollout`
- include owner and date in the evidence notes

## Step 6. Reconciliation And Event Sanity Check

Immediately after the payment validations:

```text
GET /api/finance/gateway/events/?processed=false
GET /api/finance/gateway/events/?provider=mpesa
```

Confirm:

- no unexpected failed events remain for the successful validations
- any expected event rows show processed state after settlement

If a recoverable failed event exists:

- capture the error
- reprocess only if the underlying issue is already fixed

## Step 7. Receipt Confirmation Checklist

For every successful live flow above, confirm all of the following:

1. payment record exists
2. receipt number exists
3. downloadable receipt opens
4. student or invoice allocation looks correct
5. no duplicate payment was created

## Step 8. Record Results Into Launch Evidence

Update [PAYMENT_SYSTEMS_LAUNCH_EVIDENCE.md](/c:/Users/emuri/OneDrive/Desktop/Sms-Deployment/PAYMENT_SYSTEMS_LAUNCH_EVIDENCE.md:1) for:

- `TP-103`
- `TP-104`
- `TP-106`
- `TP-107`
- `TP-109`
- `TP-115` if the walkthrough was done during the same session

For each row, include:

- exact date
- tenant
- environment
- operator
- result
- payment reference or gateway event ID where available
- receipt proof location

## Step 9. Exit Decision

`P1` is complete when:

- one bursar STK payment completes end to end
- one portal M-Pesa payment completes end to end
- downloadable receipts are confirmed on resulting records
- Stripe is either validated end to end or explicitly waived with owner and date

## Failure Handling

If any live validation fails:

1. stop opening the next payment path
2. capture the exact failing screen or API response
3. capture the payment reference or event ID
4. inspect gateway events
5. log the blocker into launch evidence with owner and date
6. do not mark `P1` complete
