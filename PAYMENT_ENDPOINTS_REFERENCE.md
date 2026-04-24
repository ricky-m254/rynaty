# Banking Payments Experience Guide

**Version:** 2.0  
**Date:** April 23, 2026  
**Document Type:** Product, UX, and API guide for banking payments  
**Primary Audience:** Figma designer, frontend engineer, backend engineer, QA  

---

## Purpose

This document explains how the current school payment system works across:

- manual payment capture by finance staff
- bank-transfer initiation from parent and student portals
- online payment sync through M-Pesa and Stripe
- reconciliation of bank statements and webhook/callback events
- payment receipts, reversals, auditability, and operator recovery

Use this as the source guide for designing finance/payment screens in Figma.

This guide is intentionally broader than a pure API list. It explains:

- what each user is trying to do
- which screens and components are required
- which states the UI must represent
- which backend entities and endpoints support each flow

---

## Design Goal

The payment experience is not one screen. It is a connected system with four distinct jobs:

1. `Collect` money or start a payment request.
2. `Confirm` whether the money actually arrived.
3. `Reconcile` the money against invoices, receipts, and statements.
4. `Recover` safely when a callback, webhook, or bank match fails.

For design purposes, think of the system as four surfaces:

- `Finance Admin Workspace`
- `Parent Portal`
- `Student Portal`
- `Ops / Reconciliation / Support Layer`

---

## Main User Types

### 1. Finance Admin / Bursar

Owns:

- recording manual payments
- launching Stripe checkout for in-person or assisted flows
- reviewing payment history
- downloading receipts
- requesting reversals
- reviewing imported bank lines
- matching and clearing reconciliation items
- reviewing failed gateway events and reprocessing them

### 2. Parent User

Owns:

- viewing a child's invoices and balances
- paying by M-Pesa
- generating a bank-transfer reference
- launching Stripe checkout
- viewing payment history
- opening receipts
- downloading fee statements

### 3. Student User

Owns:

- viewing own invoices and balance
- paying by M-Pesa
- generating a bank-transfer reference
- launching Stripe checkout
- viewing payment history
- opening receipts

### 4. Platform / Operations User

Owns:

- tenant-level payment readiness
- tenant billing and revenue analytics
- gateway callback readiness
- support visibility for failed payment events

This role matters for admin operations, but the day-to-day school banking/payment design is centered on Finance Admin, Parent, and Student.

---

## Scope Of Payment Modes

The system currently supports these payment modes in the experience:

### A. Manual capture inside the finance office

Captured by finance staff from the finance payment form:

- `Cash`
- `Bank Transfer`
- `Card`
- `Mobile Money`
- `Cheque`
- `Other`

These create real `Payment` records and generate receipts immediately.

### B. Online or async-verified payment flows

- `M-Pesa STK Push`
- `Stripe Checkout`

These start as `PaymentGatewayTransaction` records, then settle later through:

- M-Pesa callback processing
- Stripe webhook processing
- optional operator recovery / reprocess actions

### C. Manual-but-online-assisted bank transfer

Parent or student users can create a transfer reference online, but settlement is not immediate.

The user gets a generated reference and instructions like:

- use the reference in bank narration
- the balance updates after reconciliation

This means the design must show:

- a successful initiation state
- a pending / awaiting reconciliation state
- a later "reflected in balance" state

---

## Core Domain Objects

These are the key backend records your Figma flows need to account for.

### 1. `Invoice`

Represents what the student owes.

Important fields:

- `invoice_number`
- `student`
- `term`
- `invoice_date`
- `due_date`
- `total_amount`
- `status`
- `balance_due`

Statuses:

- `DRAFT`
- `ISSUED`
- `PARTIALLY_PAID`
- `PAID`
- `OVERDUE`
- `VOID`
- `CONFIRMED`

### 2. `Payment`

Represents a real recorded payment.

Important fields:

- `student`
- `payment_date`
- `amount`
- `payment_method`
- `reference_number`
- `receipt_number`
- `notes`
- `is_active`
- `reversed_at`
- `reversal_reason`

Derived display fields used in UI:

- `receipt_no`
- `transaction_code`
- `vote_head_summary`
- `status`
- `receipt_json_url`
- `receipt_pdf_url`
- `allocated_amount`
- `unallocated_amount`

### 3. `PaymentGatewayTransaction`

Represents a payment attempt or initiated external payment before full settlement.

Important fields:

- `provider`
- `external_id`
- `student`
- `invoice`
- `amount`
- `currency`
- `status`
- `payload`
- `is_reconciled`

Statuses:

- `INITIATED`
- `PENDING`
- `SUCCEEDED`
- `FAILED`
- `REFUNDED`

Typical providers:

- `mpesa`
- `parent_portal`
- `student_portal`
- Stripe-related finance/portal transactions

### 4. `PaymentGatewayWebhookEvent`

Stores raw incoming gateway events for traceability and recovery.

Important fields:

- `event_id`
- `provider`
- `event_type`
- `signature`
- `payload`
- `processed`
- `processed_at`
- `error`
- `received_at`

This powers the support/recovery UI.

### 5. `BankStatementLine`

Represents a bank line imported or created for reconciliation.

Important fields:

- `statement_date`
- `value_date`
- `amount`
- `reference`
- `narration`
- `source`
- `status`
- `matched_payment`
- `matched_gateway_transaction`

Statuses:

- `UNMATCHED`
- `MATCHED`
- `CLEARED`
- `IGNORED`

### 6. `PaymentReversalRequest`

Represents a maker/checker reversal workflow.

Important fields:

- `payment`
- `reason`
- `requested_by`
- `requested_at`
- `status`
- `reviewed_by`
- `reviewed_at`
- `review_notes`

Statuses:

- `PENDING`
- `APPROVED`
- `REJECTED`

---

## High-Level Experience Map

### Flow 1. Finance office records a manual payment

1. Finance staff opens `Record Payment`.
2. Searches or selects a student.
3. Chooses a manual payment method.
4. Enters amount, reference number, date, notes.
5. Submits the payment.
6. System creates a `Payment`.
7. Receipt becomes immediately available.
8. Payment appears in payment list and student ledger.

### Flow 2. Parent or student initiates bank transfer

1. User opens outstanding invoice.
2. Chooses `Bank Transfer`.
3. Enters amount.
4. System creates a `PaymentGatewayTransaction` with a generated reference.
5. User sees transfer instructions and reference.
6. Actual balance update happens later after reconciliation.

### Flow 3. Parent or student pays by M-Pesa

1. User chooses `M-Pesa`.
2. Enters phone number.
3. System initiates STK push and creates `PaymentGatewayTransaction` in `PENDING`.
4. User sees "check phone / enter PIN".
5. Portal polls payment status.
6. M-Pesa callback settles transaction.
7. If successful, real `Payment` is created and invoice balance updates.
8. Receipt becomes available in payment history.

### Flow 4. Parent or student pays by Stripe

1. User chooses `Stripe Checkout`.
2. System creates hosted checkout session and pending gateway transaction.
3. User is redirected to Stripe.
4. Stripe webhook confirms payment.
5. System settles the transaction into a real `Payment`.
6. Balance and payment history update.

### Flow 5. Finance team reconciles bank activity

1. Finance imports CSV bank statement lines.
2. System stores `BankStatementLine` records as `UNMATCHED`.
3. Finance runs `auto-match` or manual matching.
4. Once a line is confirmed, it can be `CLEARED`.
5. If wrongly matched, finance can `unmatch`.
6. Non-relevant entries can be `IGNORED`.

### Flow 6. Support or finance recovers failed sync events

1. Failed or unprocessed webhook/callback event appears in gateway event list.
2. User filters by provider and processed status.
3. User inspects payload and error.
4. User clicks `Reprocess`.
5. System retries settlement logic.
6. If successful, payment is created and event is cleared.

---

## Frontend Surface Inventory

## 1. Finance Admin Payment List

Compiled page:

- `sms-backend/frontend_build/assets/FinancePaymentsPage-Dwws6qtb.js`

Purpose:

- central workspace for reviewing all school payments
- downloading receipts
- seeing allocation state
- accessing student context
- starting deletion or reversal request actions
- opening reversal request queue

### Required layout blocks

#### A. Header

- page title: `Payments`
- helper copy: `Track collections and payment history`
- button: `Record payment`
- optional print/export utilities

#### B. Filters row

The existing UI already supports:

- search by admission number
- receipt number
- transaction code
- vote head summary
- student filter
- payment method filter
- allocation status filter
- date from
- date to

#### C. Payment table

Current columns:

- `Receipt`
- `Transaction`
- `Student`
- `Vote Head`
- `Method`
- `Amount`
- `Status`
- `Created`
- `Action`

#### D. Row actions

Current actions:

- `Context`
- `Receipt PDF`
- `Delete`
- `Request reversal`

#### E. Expandable context panel

When opened, the system shows:

- class / term
- parents / guardians
- contact details when available

#### F. Reversal request queue

Separate section on same page:

- search
- status filter
- table of reversal requests
- `Approve` / `Reject` actions for privileged users

### Important payment row states

The UI currently expresses:

- `Active / Allocated`
- `Active / Partial`
- `Active / Unallocated`
- `Reversed`

This allocation state is essential for design. It tells finance staff whether money is still waiting to be distributed across invoices or vote heads.

### Designer notes

- prioritize scannability over decorative density
- make receipt / transaction / amount visually stronger than secondary metadata
- reversal actions should feel guarded and irreversible
- allocation state should be glanceable with colored chips
- expanded student context should not dominate the table by default

---

## 2. Finance Admin Record Payment Form

Compiled page:

- `sms-backend/frontend_build/assets/FinancePaymentFormPage-Dh2R-Fpu.js`

Purpose:

- record manual payments
- launch Stripe checkout from admin workspace
- return immediate receipt and SMS-ready confirmation text

### Supported payment methods in UI

Manual methods:

- `Cash`
- `Bank Transfer`
- `Card`
- `Mobile Money`
- `Cheque`
- `Other`

Online method:

- `Stripe Checkout`

### Required layout blocks

#### A. Student selection

The current form supports:

- admission-number search
- name search
- dropdown fallback
- selected student summary

This is not a generic dropdown. It is a search-first student picker.

#### B. Student context card

Expected fields:

- student name
- admission number
- active enrollment/class
- SMS target / guardian phone when available

#### C. Payment form

Required fields and logic:

- student
- amount
- payment date
- payment method
- reference number
- notes

Behavior:

- for manual methods, submit records a payment immediately
- for Stripe Checkout, submit creates hosted checkout instead of immediate payment record

#### D. Stripe summary state

When Stripe session is created:

- show success state
- show `Open checkout`
- show `Reset` or re-create option

#### E. Receipt success panel

After manual save:

- show success flash
- show `Receipt`
- show `Receipt JSON`
- show aligned SMS text
- show ability to copy SMS confirmation content

### Designer notes

- manual and Stripe modes should feel related, but not identical
- switch the form clearly between `record now` and `launch hosted payment`
- success state should keep the next actions visible: receipt, JSON, SMS
- reference-number field should adapt its helper text by method

---

## 3. Parent Portal Finance Screen

Compiled page:

- `sms-backend/frontend_build/assets/ParentPortalFinancePage-C4iG-P9o.js`

Purpose:

- let parent view child finances and pay from portal

### Main content blocks

- finance summary
- invoice list
- payment history
- payment action panel
- receipt links
- fee statement access

### Supported payment actions

- `M-Pesa`
- `Bank Transfer`
- `Stripe Checkout`

### Important experience behaviors

#### M-Pesa

- user enters phone number
- sees pending confirmation text
- screen can poll for status
- timeout message is supported

#### Bank transfer

- system creates a unique transfer reference
- copy explicitly tells user to include the reference in transfer narration or deposit slip
- balance updates only after reconciliation

#### Stripe

- creates hosted checkout link
- supports success/cancel return messages

### Payment history block

Should show:

- payment date
- amount
- method
- reference
- receipt link

### Designer notes

- the parent needs confidence, not accounting complexity
- keep the child context visible
- emphasize outstanding balance and invoice-to-payment relationship
- for bank transfer, instructions are part of the product, not just a backend detail

---

## 4. Student Portal Fees Screen

Compiled page:

- `sms-backend/frontend_build/assets/StudentPortalFeesPage-LL9vjGLP.js`

Purpose:

- self-service fees page for the student

### Similarities to parent portal

- invoice list
- payment history
- M-Pesa flow
- bank-transfer initiation
- Stripe Checkout
- receipt links

### Important copy already implied in current build

- overdue invoices can still be settled here
- payment methods include M-Pesa, bank transfer, and Stripe Checkout
- M-Pesa requires phone number
- bank transfer gives a reference and waits for reconciliation

### Designer notes

- this screen should feel simpler than the parent version
- remove guardian/child complexity
- keep status messaging short and direct
- payment progress and history should be easy to understand on mobile

---

## 5. Receipt Experiences

Receipt entry points exist in:

- finance admin workspace
- parent portal
- student portal

### Receipt content model

The receipt payload includes:

- `receipt_no`
- `transaction_code`
- `reference_number`
- `student`
- `admission_number`
- `amount`
- `method`
- `date`
- `status`
- `notes`
- `allocations`
- `vote_head_allocations`
- `vote_head_summary`
- `receipt_json_url`
- `receipt_pdf_url`

### Receipt output types

- finance JSON/plain receipt payload
- finance PDF receipt
- parent HTML printable receipt
- student HTML printable receipt

### Designer notes

- the receipt is both a customer artifact and an audit artifact
- design for print clarity first, branding second
- always show:
  - school identity
  - student identity
  - receipt number
  - date
  - method
  - total paid
  - allocations or invoice references

---

## 6. Reconciliation Workspace

Backend routes exist for:

- bank statement import
- bank line listing
- auto-match
- clear
- ignore
- unmatch

Primary endpoint group:

- `/api/finance/reconciliation/bank-lines/`

### What the reconciliation UI must support

#### A. Bank line list

Columns should include:

- statement date
- value date
- amount
- reference
- narration
- source
- status
- matched payment reference
- matched gateway external ID

#### B. Reconciliation actions

- `Import CSV`
- `Auto-match`
- `Clear`
- `Ignore`
- `Unmatch`

#### C. CSV import behavior

Required columns:

- `statement_date`
- `amount`

Optional columns:

- `value_date`
- `reference`
- `narration`
- `source`

### Reconciliation states

- `UNMATCHED`
- `MATCHED`
- `CLEARED`
- `IGNORED`

### Designer notes

- bank reconciliation is a review tool, not a payment form
- the primary visual hierarchy should be: amount, reference, status, match target
- `CLEAR` should feel like a final confirmation step
- `IGNORE` and `UNMATCH` should be clearly differentiated

---

## 7. Gateway Events / Recovery Workspace

Primary endpoint group:

- `/api/finance/gateway/events/`

Purpose:

- show raw incoming webhook/callback events
- reveal whether they were processed
- show errors
- let operators manually reprocess supported failures

### Current backend support

Filtering:

- `provider`
- `processed`

Manual recovery:

- `POST /api/finance/gateway/events/{id}/reprocess/`

Supported reprocess types:

- M-Pesa STK callback events
- Stripe checkout session events

### Data fields the UI should expose

- event id
- provider
- event type
- received at
- processed true/false
- processed at
- error
- raw payload viewer

### Designer notes

- this is an operations table, not a customer-facing timeline
- default row view should stay compact
- raw payload should live in a drawer, side panel, or expandable JSON inspector
- failed rows must be visually obvious

---

## Backend Capabilities By Area

## A. Finance Admin / Bursar APIs

Base group:

- `/api/finance/`

Key routes:

- `GET/POST /api/finance/payments/`
- `GET /api/finance/payments/{id}/receipt/?format=json`
- `GET /api/finance/payments/{id}/receipt/pdf/`
- `POST /api/finance/payments/{id}/allocate/`
- `POST /api/finance/payments/{id}/auto-allocate/`
- `POST /api/finance/payments/{id}/reversal-request/`
- `GET/POST /api/finance/payment-reversals/`
- `POST /api/finance/payment-reversals/{id}/approve/`
- `POST /api/finance/payment-reversals/{id}/reject/`
- `GET/POST/PATCH /api/finance/reconciliation/bank-lines/`
- `POST /api/finance/reconciliation/bank-lines/import-csv/`
- `POST /api/finance/reconciliation/bank-lines/{id}/auto-match/`
- `POST /api/finance/reconciliation/bank-lines/{id}/clear/`
- `POST /api/finance/reconciliation/bank-lines/{id}/ignore/`
- `POST /api/finance/reconciliation/bank-lines/{id}/unmatch/`
- `GET /api/finance/gateway/events/`
- `POST /api/finance/gateway/events/{id}/reprocess/`
- `POST /api/finance/stripe/checkout-session/`
- `POST /api/finance/mpesa/push/`
- `GET /api/finance/mpesa/status/`
- `POST /api/finance/mpesa/test-connection/`
- `GET/PUT /api/finance/mpesa/callback-url/`
- `GET /api/finance/launch-readiness/`

## B. Parent Portal APIs

- `GET /api/parent-portal/finance/summary/`
- `GET /api/parent-portal/finance/invoices/`
- `GET /api/parent-portal/finance/payments/`
- `GET /api/parent-portal/finance/payments/{payment_id}/receipt/`
- `POST /api/parent-portal/finance/pay/`
- `GET /api/parent-portal/finance/mpesa-status/`
- `GET /api/parent-portal/finance/statement/`
- `GET /api/parent-portal/finance/statement/download/`

## C. Student Portal APIs

- `GET /api/student-portal/my-invoices/`
- `GET /api/student-portal/my-payments/`
- `GET /api/student-portal/finance/payments/{payment_id}/receipt/`
- `POST /api/student-portal/finance/pay/`
- `GET /api/student-portal/finance/mpesa-status/`

## D. Incoming callback / webhook APIs

- `POST /api/finance/mpesa/callback/`
- `POST /api/finance/gateway/webhooks/{provider}/`

---

## Feature Matrix

| Feature | Finance Admin | Parent | Student | Backend Support |
|------|------|------|------|------|
| Record manual payment | Yes | No | No | `PaymentViewSet.create` |
| Generate receipt immediately | Yes | Indirect | Indirect | Receipt payload + PDF/HTML endpoints |
| Launch Stripe checkout | Yes | Yes | Yes | Stripe checkout session + webhook settlement |
| Start M-Pesa payment | Assisted/admin flow available | Yes | Yes | STK push + callback + status polling |
| Start bank transfer with reference | Admin can manually record or reconcile | Yes | Yes | `PaymentGatewayTransaction` with reference |
| View payment history | Yes | Yes | Yes | payment list endpoints |
| View fee statement | Finance via reports/ledger | Yes | not primary in current portal | statement endpoints |
| Request reversal | Yes | No | No | reversal request workflow |
| Approve/reject reversal | Authorized finance/admin | No | No | maker/checker approval endpoints |
| Import bank statement lines | Yes | No | No | CSV import endpoint |
| Match/clear bank lines | Yes | No | No | reconciliation endpoints |
| Inspect failed events | Yes | No | No | gateway event list |
| Reprocess failed sync event | Yes | No | No | event reprocess endpoint |

---

## Important UX Rules

### 1. Don't show every payment as "complete"

The system distinguishes:

- initiated
- pending
- succeeded
- failed
- reconciled
- reversed

Each state needs its own visual treatment.

### 2. "Bank transfer initiated" is not the same as "school received money"

For portal bank transfer:

- user action creates a transfer reference
- system still waits for reconciliation
- balance should not imply instant settlement

### 3. Receipts are only meaningful after real payment creation

Portal-initiated bank transfer references are not the same thing as a finalized receipt.

### 4. Reconciliation must preserve human control

Auto-match helps, but finance users still need:

- reviewable matches
- clear/unmatch controls
- visible references and narration

### 5. Support tools need payload visibility

A pretty status chip is not enough for ops. Event screens need:

- timestamps
- provider
- raw error
- reprocess button
- raw payload access

---

## Recommended Figma Screen Set

If the design team is starting from scratch, these are the minimum screens to design.

### Finance Admin

1. `Payments List`
2. `Record Manual Payment`
3. `Stripe Checkout Launch State`
4. `Receipt Preview / Download State`
5. `Payment Reversal Request Modal`
6. `Reversal Approval Queue`
7. `Bank Reconciliation List`
8. `Import Statement Modal`
9. `Gateway Event Monitor`
10. `Gateway Event Detail Drawer`

### Parent Portal

1. `Finance Dashboard`
2. `Invoice Details / Outstanding Balance`
3. `Pay Invoice Modal or Panel`
4. `M-Pesa Pending State`
5. `Bank Transfer Instruction State`
6. `Stripe Redirect State`
7. `Payment History`
8. `Receipt View`
9. `Fee Statement View`

### Student Portal

1. `Fees Dashboard`
2. `Invoice List`
3. `Pay Invoice Modal or Panel`
4. `M-Pesa Pending State`
5. `Bank Transfer Reference State`
6. `Stripe Redirect State`
7. `Payment History`
8. `Receipt View`

---

## Field-Level Guidance For Figma

These fields are not optional in the UX because the backend already uses them.

### Manual payment card / table row

- student name
- admission number
- receipt number
- transaction/reference number
- payment method
- amount
- payment date
- allocation status
- active/reversed state

### Gateway transaction card / row

- provider
- external ID / checkout request ID / checkout session ID
- invoice reference
- amount
- status
- initiated at
- reconciled true/false

### Bank statement line row

- statement date
- value date
- amount
- bank reference
- narration
- source
- status
- matched payment
- matched gateway transaction

### Receipt view

- school brand
- receipt number
- student
- admission number
- amount
- method
- date
- reference
- status
- allocation breakdown

---

## Suggested State Chips

### Payment state chips

- `Active`
- `Reversed`
- `Allocated`
- `Partial`
- `Unallocated`

### Gateway state chips

- `Initiated`
- `Pending`
- `Succeeded`
- `Failed`
- `Refunded`

### Reconciliation state chips

- `Unmatched`
- `Matched`
- `Cleared`
- `Ignored`

### Approval state chips

- `Pending`
- `Approved`
- `Rejected`

Use distinct semantics:

- green for completed/safe
- amber for pending/needs review
- red for failed/reversed/rejected
- neutral/slate for inactive or informational

---

## Error And Empty States To Design

### Errors

- invalid amount
- phone required for M-Pesa
- invoice not found
- invoice already paid
- amount exceeds outstanding balance
- callback/webhook verification failed
- CSV file missing
- CSV header missing
- unsupported reprocess event

### Empty states

- no invoices
- no payments
- no bank statement lines
- no failed gateway events
- no reversal requests

### Long-running states

- waiting for M-Pesa confirmation
- Stripe checkout launched but not yet settled
- bank transfer awaiting reconciliation
- event reprocess in progress

---

## Key Backend Notes For Engineers Working With The Designer

### Manual payment recording

Implemented through:

- `PaymentViewSet.create`
- `FinanceService.record_payment`

### Portal bank-transfer initiation

Creates:

- `PaymentGatewayTransaction`

Does not immediately create:

- `Payment`

### M-Pesa settlement

Initiation:

- `MpesaStkPushView`
- `ParentFinancePayView`
- `StudentFinancePayView`

Settlement:

- `MpesaStkCallbackView`
- `FinanceService.process_mpesa_callback_event`

### Stripe settlement

Initiation:

- finance admin checkout session
- parent portal pay view
- student portal pay view

Settlement:

- `FinanceGatewayWebhookView`
- `FinanceService.process_stripe_webhook_event`

### Bank reconciliation

Primary logic:

- `BankStatementLineViewSet`
- `FinanceService.reconcile_bank_line`

### Ops recovery

Primary logic:

- `PaymentGatewayWebhookEventViewSet.reprocess`

---

## What The Designer Should Prioritize

If time is limited, prioritize the following screens first:

1. `Finance Admin Payments List`
2. `Finance Admin Record Payment Form`
3. `Parent Portal Payment Flow`
4. `Student Portal Payment Flow`
5. `Reconciliation List`
6. `Gateway Event Recovery Table`
7. `Receipt Template`

These seven cover the highest-visibility parts of both manual and synced payment operations.

---

## Appendix: Source Files Behind The Current Experience

### Frontend bundles verified in current build

- `sms-backend/frontend_build/assets/FinancePaymentsPage-Dwws6qtb.js`
- `sms-backend/frontend_build/assets/FinancePaymentFormPage-Dh2R-Fpu.js`
- `sms-backend/frontend_build/assets/ParentPortalFinancePage-C4iG-P9o.js`
- `sms-backend/frontend_build/assets/StudentPortalFeesPage-LL9vjGLP.js`

### Primary backend route files

- `sms-backend/finance/urls.py`
- `sms-backend/parent_portal/urls.py`
- `sms-backend/parent_portal/student_portal_urls.py`
- `sms-backend/school/urls.py`

### Primary backend implementation files

- `sms-backend/finance/presentation/viewsets.py`
- `sms-backend/finance/presentation/collection_ops_viewsets.py`
- `sms-backend/parent_portal/views.py`
- `sms-backend/parent_portal/student_portal_views.py`
- `sms-backend/school/views.py`
- `sms-backend/school/models.py`
- `sms-backend/school/payment_receipts.py`

---

## Final Design Summary

For Figma, think of this payment system as:

- a `collection UI`
- a `verification UI`
- a `reconciliation UI`
- a `recovery UI`

The strongest designs for this system will make those four jobs visually distinct while still feeling like one coherent finance product.
