# Payments Launch Runbook

This runbook covers the remaining fast-track launch work for tenant payments:

- confirm Stripe and M-Pesa configuration
- confirm public webhook and callback URLs
- validate one real bank CSV import in staging
- recover failed webhook events without database access

It is intended for finance admins, bursars, and support staff working with the payment launch.

## 1. Readiness Snapshot

Start with the tenant readiness endpoint:

```text
GET /api/finance/launch-readiness/
```

Review these fields first:

- `ready`
- `blocking_issues`
- `warnings`
- `stripe`
- `mpesa`
- `operations`
- `next_actions`

Launch should pause if `ready` is `false`.

Typical blocking items:

- missing `integrations.stripe.secret_key`
- missing `integrations.stripe.webhook_secret`
- missing `integrations.mpesa` credentials
- public base URL still falling back to the request host
- non-HTTPS Stripe or M-Pesa callback URLs

Typical warnings:

- unprocessed webhook events
- unmatched or uncleared bank statement lines
- no CSV imports recorded yet for staging validation

## 2. Stripe Validation

Confirm the tenant has Stripe credentials in Settings -> Integrations -> Stripe.

Then run:

```text
POST /api/finance/stripe/test-connection/
```

Expected result:

- `success: true`
- correct account name
- correct mode (`test` before go-live, `live` for production launch)

Confirm the readiness endpoint reports:

- `stripe.configured = true`
- `stripe.webhook_url` points to `/api/finance/gateway/webhooks/stripe/`
- `stripe.webhook_url` is HTTPS

## 3. M-Pesa Validation

Confirm the tenant has M-Pesa credentials in Settings -> Integrations -> M-Pesa.

Then run:

```text
POST /api/finance/mpesa/test-connection/
GET /api/finance/mpesa/callback-url/
```

Expected result:

- Daraja test connection succeeds
- callback URL is public and HTTPS
- callback URL ends with `/api/finance/mpesa/callback/`

If the callback host is wrong, update it through Settings or with:

```text
python manage.py configure_mpesa_callback
```

Confirm the readiness endpoint reports:

- `mpesa.configured = true`
- `mpesa.callback_source` is not `request_fallback`
- `mpesa.callback_url` is the intended tenant callback URL

## 4. Portal Smoke Test

For both parent and student portals, validate:

1. Stripe initiation returns a hosted checkout URL.
2. M-Pesa initiation returns a checkout request ID.
3. Bank transfer initiation returns a reference and manual-confirmation message.

Expected portal behavior:

- Stripe redirects to hosted checkout
- M-Pesa stays in the portal and polls for status
- Bank transfer gives the user a reference to include in narration or deposit slip

## 5. Bank CSV Validation

Use one real staging statement file before launch.

Import path:

```text
POST /api/finance/reconciliation/bank-lines/import-csv/
```

Supported CSV columns:

- required: `statement_date`, `amount`
- optional: `value_date`, `reference`, `narration`, `source`

Validation checklist:

1. Import completes without row-level parse failures.
2. At least one line auto-matches.
3. At least one unmatched line is visible to finance staff.
4. A matched line can be cleared.
5. An incorrect match can be unmatched and corrected.

Follow-up endpoints:

```text
POST /api/finance/reconciliation/bank-lines/{id}/auto-match/
POST /api/finance/reconciliation/bank-lines/{id}/clear/
POST /api/finance/reconciliation/bank-lines/{id}/unmatch/
POST /api/finance/reconciliation/bank-lines/{id}/ignore/
```

## 6. Failed Webhook Recovery

Finance staff can inspect gateway events here:

```text
GET /api/finance/gateway/events/
GET /api/finance/gateway/events/?processed=false
```

If the underlying transaction or config problem has been fixed, reprocess with:

```text
POST /api/finance/gateway/events/{id}/reprocess/
```

Current supported manual reprocess flows:

- `mpesa:stk_callback`
- `stripe:checkout.session.*`

Use reprocess when:

- a webhook arrived before its gateway transaction existed
- a recoverable configuration issue blocked settlement
- support has verified the event payload is valid and should be replayed

Do not reprocess blindly:

- check the event error first
- confirm the missing transaction or setting has been corrected
- verify duplicate settlement protections are still in place

## 7. Go-Live Checklist

Do not launch until all of these are true:

1. `GET /api/finance/launch-readiness/` returns `ready: true`.
2. Stripe and M-Pesa test-connection checks succeed.
3. Stripe webhook URL and M-Pesa callback URL are public and HTTPS.
4. Parent portal payment methods work for Stripe, M-Pesa, and bank transfer.
5. Student portal payment methods work for Stripe, M-Pesa, and bank transfer.
6. One real bank CSV file has been imported and validated in staging.
7. Finance staff can list failed webhook events and reprocess recoverable ones.
8. Support knows which endpoint to use for readiness, bank import, and event reprocess.

## 8. Rollback Notes

If launch validation fails:

1. stop new live payment promotion
2. keep existing portal methods limited to known-good flows
3. fix credentials or callback/webhook URLs
4. re-run readiness
5. retry staged portal payments before reopening launch

If settlement fails after an event already landed:

1. inspect `/api/finance/gateway/events/?processed=false`
2. fix the missing transaction or configuration issue
3. reprocess the event
4. confirm payment creation and invoice update
5. document the incident for support follow-up
