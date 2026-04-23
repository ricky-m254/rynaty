# Super Admin Tenant Payments Audit
## Current Build Review

> Note: the combined school + tenant payments source of truth is now `PAYMENTS_MASTER_AUDIT.md`.  
> Keep this file as the super-admin tenant-billing subtrack reference.

**Date:** April 22, 2026  
**Scope:** Super admin tenant billing, tenant payment processing, subscription expiry, and revenue analytics  
**Status:** AUDIT ONLY - NO IMPLEMENTATION

---

## Sources Reviewed

- `attached_assets/SmartCampus_SuperAdmin_Spec_1776271963249.docx`
- `sms-backend/frontend_build/assets/PlatformTenantsPage-DwH5gLS8.js`
- `sms-backend/frontend_build/assets/PlatformBillingPage-CEcBPZ52.js`
- `sms-backend/frontend_build/assets/PlatformRevenueAnalyticsPage-BdFivJgi.js`
- `sms-backend/frontend_build/assets/PlatformImpersonationPage-CLkHc1iq.js`
- `sms-backend/clients/platform_views.py`
- `PAYMENT_SYSTEMS_SECOND_AUDIT.md`
- `PAYMENT_SYSTEMS_TASK_PLAN.md`

---

## Executive Summary

The super-admin layer is not greenfield. The current build already has a working admin shell for tenant management, billing, revenue analytics, and impersonation. The missing work is a dedicated tenant-payments operations lane plus the backend automation that keeps subscription status, paybill receipts, and tenant access in sync.

The attached spec confirms the intended direction:

- super admin only, never visible to school tenants
- tenant lifecycle controls
- billing and subscription controls
- M-Pesa paybill for platform-level tenant payments
- revenue analytics and projections
- trial/subscription expiry automation
- impersonation banner for debug flows

That means the right next step is to extend the existing UI and backend, not rebuild the dashboard.

---

## Current Build Snapshot

| Surface | Current State | What It Already Does | Remaining Gap |
|---------|---------------|----------------------|---------------|
| `PlatformTenantsPage` | Present | Create tenant, edit profile, activate/suspend/resume, assign plan, generate invoice, reset school admin credentials | No dedicated tenant-payment history or payment-operation actions |
| `PlatformBillingPage` | Present | Plan CRUD, paybill setting, subscription creation, invoice list, manual payment capture | No dedicated tenant payments queue with approve/reject/retry workflow |
| `PlatformRevenueAnalyticsPage` | Present | MRR, ARR, churn, LTV, ARPT, charts and trend breakdowns | Needs platform payment-specific projections and clearer operations signals |
| `PlatformImpersonationPage` | Present | Request, approve, start, and end impersonation sessions | Should remain debug-only support, not a payment workflow substitute |
| `clients/platform_views.py` billing endpoints | Present | `record-payment`, `revenue`, `revenue/overview` and invoice/subscription operations | No dedicated tenant-payments ledger or verification queue endpoint |
| Subscription expiry automation | Partial | Trial and billing-related status logic exists in the codebase | Needs a single explicit platform-owned expiry/disable/reactivation flow tied to tenant billing |

---

## What Is In Scope

1. Reuse the existing super admin shell.
2. Add a tenant payments operations surface inside that shell.
3. Make platform-owned M-Pesa paybill the primary collection rail for tenant subscriptions.
4. Tie payment confirmation to subscription extension and tenant reactivation.
5. Surface revenue analytics that reflect the real billing engine.
6. Keep impersonation available only as a debug tool.

## What Is Not In Scope Yet

1. Rebuilding the admin UI from scratch.
2. School-owned payment collection flows.
3. Flutterwave rollout unless it is explicitly reintroduced later.
4. New product areas outside tenant billing and revenue operations.

---

## Key Gaps To Close

- No dedicated `Tenant Payments` page or queue with `Approve`, `Reject`, and `Retry Verification`.
- No direct `View Payments` drill-down from the tenant row into the payment history and settlement state.
- No explicit platform-owned subscription expiry job that auto-disables overdue tenants and reactivates them after payment.
- No single hardened callback-verification path for tenant payment intake.
- No payment-centric audit trail visible to super admins as an operational surface.
- Revenue analytics exists, but it still needs clearer projections and payment-ops context.

---

## Audit Conclusion

The build is close enough to extend, but not complete enough to approve implementation without a plan. The super admin payment work should be approached as a phased enhancement of the existing shell, with tenant payments, subscription expiry, M-Pesa intake, and analytics each treated as separate deliverables.
