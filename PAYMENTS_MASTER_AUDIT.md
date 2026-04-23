# Payments Master Audit
## School Fees + Super Tenant Billing

**Date:** April 22, 2026  
**Status:** Audit plus implementation notes

---

## Sources Reviewed

- `c:\Users\emuri\OneDrive\Desktop\rsm docs\Rynaty_Payment_System_Spec.pdf`
- `c:\Users\emuri\OneDrive\Desktop\rsm docs\Rynaty_Super_Tenant_Spec.pdf`
- `school payments.png`
- `tenant billing.png`
- `sms-backend/frontend_build/assets/FinancePaymentsPage-Dwws6qtb.js`
- `sms-backend/frontend_build/assets/ParentPortalFinancePage-C4iG-P9o.js`
- `sms-backend/frontend_build/assets/StudentPortalFeesPage-LL9vjGLP.js`
- `sms-backend/frontend_build/assets/PlatformTenantsPage-DwH5gLS8.js`
- `sms-backend/frontend_build/assets/PlatformBillingPage-CEcBPZ52.js`
- `sms-backend/frontend_build/assets/PlatformRevenueAnalyticsPage-BdFivJgi.js`
- `sms-backend/frontend_build/assets/PlatformImpersonationPage-CLkHc1iq.js`
- `sms-backend/clients/platform_views.py`
- `sms-backend/school/models.py`
- `sms-backend/clients/models.py`
- `PAYMENT_SYSTEMS_SECOND_AUDIT.md`
- `PAYMENT_SYSTEMS_TASK_PLAN.md`
- `SUPER_ADMIN_TENANT_PAYMENTS_AUDIT.md`
- `SUPER_ADMIN_TENANT_PAYMENTS_TASK_PLAN.md`

---

## Executive Summary

The repo is not greenfield for payments. It already contains two meaningful payment surfaces:

- school fee collection and reconciliation
- platform subscription billing for school tenants

The attached docs and diagrams add a stricter product contract, but most of the plumbing is already present in the build. The remaining work is mainly about alignment, completion, and hardening.

That means the correct next step is a master implementation plan, not a rebuild.

---

## April 23, 2026 Update

The first school-payment implementation slice has now landed:

- the finance admin capture form now supports admission-number lookup, student autofill, and post-save receipt/SMS actions
- the finance payment list now exposes receipt number, transaction code, vote head summary, status, and created date so the table contract matches the live backend
- successful payment recording now creates a real SMS audit record for the student or guardian contact when a phone number exists
- historical payment imports suppress notification dispatch so migration runs stay quiet
- vote-head allocations now upsert by payment/vote-head pair so duplicate callback replays update the existing allocation instead of creating a second row
- payment create and allocation create now return `200 OK` on replayed duplicates, keeping retry semantics idempotent across the finance workflow
- the student portal now exposes receipt URLs and a printable receipt endpoint for each payment
- the parent and student portal payment sheets now default to M-Pesa first while preserving Stripe and bank transfer fallbacks

## April 23, 2026 Update - Tenant Billing

The first super-tenant billing slice has now landed:

- `PlatformBillingPage-CEcBPZ52.js` now includes a dedicated Tenant Payments queue with `Approve`, `Reject`, `Retry Verification`, and a `View Payments` shortcut
- invoice capture in the billing page now posts to `/api/platform/subscription-payments/` so tenant payments enter the shared platform queue
- payment approval reuses the backend settlement flow that reactivates tenants and settles the linked invoice
- the expiry command already enforces the platform-owned suspend policy for overdue tenants
- paybill settings remain editable in the billing page, and the public `/api/platform/subscription-payments/mpesa/callback/` endpoint now settles and dedupes tenant paybill callbacks

---

## What Already Exists

| Area | Current Build State | Notes |
|------|---------------------|-------|
| School payment ledger | Present | `school.Payment` already stores student-linked payments, references, receipt numbers, reversals, and active state |
| Vote-head allocation | Present | `VoteHeadPaymentAllocation` already models allocation across fee heads |
| Finance admin UI | Present | `FinancePaymentsPage` already lists payments, receipts, reversals, and operator context |
| Parent portal payments | Present | `ParentPortalFinancePage` already exposes balance, invoices, and payment initiation paths |
| Student portal payments | Present | `StudentPortalFeesPage` already exposes balance, invoices, and payment initiation paths |
| Super admin tenant shell | Present | `PlatformTenantsPage`, `PlatformBillingPage`, `PlatformRevenueAnalyticsPage`, and `PlatformImpersonationPage` already exist |
| Tenant subscription ledger | Present | `clients.SubscriptionPayment` already records platform-side tenant payments |
| Tenant billing endpoints | Present | `clients/platform_views.py` already includes invoice, payment, and revenue operations |
| Revenue analytics | Complete | MRR, ARR, churn, trend charts, projections, and tenant-risk signals now exist in the compiled build |
| Payment recovery tools | Present | Reprocess and audit flows already exist for payment event recovery |

---

## Requested Contract Versus Current Models

The user-supplied `payments` table should be treated as a contract, not a reason to add a duplicate ledger.

| Requested Field / Concept | Best Current Match | Notes |
|---------------------------|-------------------|-------|
| `student_id` | `school.Payment.student` | Use the existing student FK |
| `amount` | `school.Payment.amount` | Existing field already matches |
| `method` | `school.Payment.payment_method` | Existing field already matches the intent |
| `transaction_code` | `reference_number` and gateway reference fields | Keep gateway codes normalized and searchable |
| `vote_head` | `VoteHeadPaymentAllocation` | Do not denormalize this into a single text field unless a reporting need appears |
| `status` | `Payment.is_active` plus reversal/reconciliation state | Use the existing lifecycle instead of inventing a second status system |
| `created_at` | Existing timestamp fields | Already present in the model layer |
| `receipt_no` | `Payment.receipt_number` | Existing field already matches |
| tenant subscription payment | `clients.SubscriptionPayment` | Separate ledger for platform billing is already in place |

The plan should only add migration-backed schema changes if a real gap remains after mapping these fields to the existing models.

---

## Gaps That Still Matter

- School receipt output now has one stable contract across JSON, PDF, and text; tenant billing receipts can reuse the same pattern if/when those views are exposed separately.
- Tenant billing callback hardening is now in place; the dedicated tenant payments operations lane and lifecycle policy are in place end to end.
- The repo now has a consolidated rollout runbook and go/no-go proof trail for both payment tracks.

---

## April 23, 2026 Update - Revenue Analytics

The platform-owner dashboard analytics slice is now implemented:

- the revenue analytics bundle now shows a forecast card and a clearer risk-oriented subtitle
- the analytics backend now returns forecast, plan breakdown, and tenant risk summaries
- the platform analytics API now aligns the month-by-month series with the compiled dashboard
- focused regression coverage now proves the revenue projection and risk-signaling contract

---

## April 23, 2026 Update - Rollout Evidence

The final rollout evidence slice is now captured:

- the school regression suite passed after verifying receipt generation and allocation behavior
- the tenant billing regression suite passed after verifying approval, callback, expiry, and replay handling
- the demo-school portal smoke suite passed after verifying parent and student payment flows
- the compiled frontend bundles passed syntax checks after the finance, portal, billing, analytics, and student edits
- the launch runbook and go/no-go note now live in `docs/` for support and release review

---

## Audit Conclusion

The current build already proves the core architecture. The requested Phase 5 rollout evidence is now complete, and the current build is ready for production rollout and post-launch monitoring:

- school payments should extend the existing school finance ledger and parent/student portal
- tenant billing now extends the existing super admin tenant shell and subscription ledger through the new Tenant Payments review lane
- revenue analytics now extends the platform owner dashboard with forecasts and risk signals
- receipts, callbacks, and audit trails are standardized across both tracks
- rollout support now has a runbook and go/no-go decision note

This is ready for production rollout and post-launch monitoring.
