# M-Pesa SaaS Reference Package

> **REFERENCE ONLY** — These files are NOT installed as Django apps and are NOT included in `INSTALLED_APPS`. Do not import from this directory in production code.

## Purpose

This directory contains the `mpesa-school-saas` reference implementation used as the architectural blueprint for the M-Pesa payment integration in RynatySchool SmartCampus.

The patterns here guided decisions around:
- `PaymentGatewayTransaction` model design (status lifecycle, tenant scoping)
- `PaymentGatewayWebhookEvent` for raw callback logging
- Fraud detection rule structures
- Double-entry ledger patterns
- SaaS billing concepts

## What Was Adopted vs What Is Different

| Reference Pattern | SmartCampus Implementation | Notes |
|---|---|---|
| `Transaction` model (UUID PK) | `PaymentGatewayTransaction` (integer PK) | Same fields, different PK type |
| `MpesaRawLog` (separate model) | `PaymentGatewayWebhookEvent` | Already existed, now used by callback |
| `Wallet` / `LedgerEntry` | `JournalEntry` / `JournalLine` | Full double-entry already in place |
| `FraudDetectionEngine` | Not implemented | Future work — needs production volume |
| `AuditLog` (hash-chained) | `PaymentGatewayWebhookEvent` | Webhook events cover compliance needs |
| `BillingEngine` (SaaS) | Not implemented | Platform-level concern |
| `STKPushView` | `MpesaStkPushView` + `ParentFinancePayView` | Split by user context |
| `MpesaCallbackView` | `MpesaStkCallbackView` | Enhanced with raw logging |
| `B2C Withdrawal` | Not implemented | Requires Safaricom approval |

## Reference Files

- `TASK.md` — Full enterprise implementation guide
- `payments/models.py` — Transaction, MpesaRawLog, WithdrawalRequest models
- `payments/mpesa_client.py` — MpesaClient class with B2C support
- `audit/models.py` — Tamper-proof hash-chained AuditLog
- `fraud_detection/engine.py` — Rule-based fraud scoring engine
- `billing/engine.py` — SaaS subscription billing engine
- `ledger/models.py` — LedgerEntry, Wallet models
