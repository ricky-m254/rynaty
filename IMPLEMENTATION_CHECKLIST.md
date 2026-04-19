# Payment Systems - Executive Summary & Implementation Checklist

**Version:** 1.0  
**Date:** April 17, 2026  
**Prepared For:** Finance Director, Technical Lead, Project Manager  
**Document Purpose:** Quick reference guide and implementation roadmap  

---

## SITUATION OVERVIEW

### What We Have
✅ **M-Pesa STK Push** - Fully operational, production-ready  
✅ **Invoice & Payment Models** - Complete database schema  
✅ **Student/Parent Portals** - Basic fee viewing capability  
✅ **Bursar Dashboard** - Payment management interface  
✅ **Webhook Logging** - M-Pesa events captured  

### What We're Missing
❌ **Webhook Processing** - Events logged but not converted to payments  
❌ **Payment Sync** - All 3 channels operate independently  
❌ **Stripe Integration** - Configuration only, no API calls  
❌ **Bank Automation** - Manual import and matching  
❌ **Accounting Sync** - Payments not posted to GL  
❌ **Reconciliation** - No automated matching engine  
❌ **User Endpoints** - Missing for Stripe and Bank payments  
❌ **Payment UI** - Minimal frontend components  

### Financial Risk Level: **CRITICAL**

| Risk | Current State | Impact |
|------|---------------|--------|
| Revenue not recorded | Webhooks logged but not processed | GL incomplete, financial statements wrong |
| Duplicate payments possible | No idempotency checks | Overpayments, accounting errors |
| Cash position unknown | No bank reconciliation | Unable to pay vendors, poor cash management |
| Single payment method | Only M-Pesa works | 0 Stripe payments, 0 Bank payments |
| Manual workarounds | Finance staff doing manual matching | Time-consuming, error-prone, not auditable |

---

## BUSINESS IMPACT ASSESSMENT

### Revenue Recognition Issues

**Scenario:** Student pays 50,000 KES via M-Pesa on April 17

**Current System:**
- Day 1: Safaricom sends webhook (payment confirmed)
- Day 1: Payment logged to PaymentGatewayWebhookEvent table
- **Payment STOPS HERE** - no automatic processing
- Day 2-7: Bursar manually discovers payment in bank account
- Day 8: Bursar manually creates Payment record
- Day 8: Bursar manually updates Invoice status
- **Revenue recognized 7+ days late**

**Under Proposed System:**
- Minute 1: Webhook received
- Minute 1-2: Automatic processing:
  - Payment record created
  - Invoice marked as paid
  - GL entry posted
  - Receipt generated
  - Student notified
- **Revenue recognized instantly**

### Compliance & Audit Issues

**Current:**
- No clear link from Payment → Invoice → GL entry
- Webhook events stored but processing not tracked
- Refund requests not auditable
- Late fee calculations manual and error-prone
- No compliance with IFRS revenue recognition

**Required (Per IFRS 15):**
- Revenue recognized when control of goods/services transfers
- In this case: when student payment is received and matched to invoice
- Must have audit trail showing evidence of each transaction

---

## CRITICAL GAPS - PRIORITY ORDER

### PRIORITY 1: IMMEDIATE (Week 1-2)
**Impact:** Without these, system is non-functional  

| Gap | Current | Required | Owner |
|-----|---------|----------|-------|
| Webhook Processing | ❌ Logged only | ✅ Convert to Payments | Dev Team |
| Invoice-Payment Sync | ❌ Manual | ✅ Automatic | Dev Team |
| GL Posting for M-Pesa | ❌ Missing | ✅ Auto post | Accounting/Dev |
| Duplicate Prevention | ❌ No checks | ✅ Idempotency keys | Dev Team |

### PRIORITY 2: ESSENTIAL (Week 3-6)
**Impact:** Without these, only partial payments work  

| Gap | Current | Required | Owner |
|-----|---------|----------|-------|
| Stripe Implementation | ❌ Config only | ✅ Full API | Dev Team |
| Bank Reconciliation | ❌ Manual | ✅ Automated | Finance/Dev |
| User Endpoints | ⚠️ M-Pesa only | ✅ All 3 methods | Dev Team |
| Error Recovery | ❌ None | ✅ Retry logic | Dev Team |

### PRIORITY 3: ENHANCED (Week 7-12)
**Impact:** Improves UX and operational efficiency  

| Gap | Current | Required | Owner |
|-----|---------|----------|-------|
| Frontend UI | ⚠️ Limited | ✅ Complete | Frontend/Dev |
| Reporting | ⚠️ Partial | ✅ Comprehensive | Finance/Dev |
| Monitoring | ❌ None | ✅ Real-time alerts | DevOps |
| Documentation | ⚠️ Incomplete | ✅ Complete | Tech Writer |

---

## RESOURCE REQUIREMENTS

### Recommended Team Structure

**For 12-Week Implementation:**

| Role | Full-time | Duration | Skills Required |
|------|-----------|----------|-----------------|
| Backend Developer | 2 | 12 weeks | Django/Python, REST API, Celery, PostgreSQL |
| Frontend Developer | 1 | 12 weeks | React/TypeScript, Stripe integration, Material-UI |
| QA Engineer | 1 | 12 weeks | API testing, integration testing, financial systems |
| Finance Analyst | 0.5 | 12 weeks | GL reconciliation, audit trail requirements |
| DevOps | 0.5 | 12 weeks | Monitoring, alerting, job queue setup |
| **Total** | **5 FTE** | **12 weeks** | |

**Cost Estimate:** $180,000 - $250,000 (varies by market)

### Technology Stack (Recommended)

**Job Queue:** Celery + Redis  
**Background Workers:** 3-4 instances  
**Monitoring:** Sentry + Prometheus + Grafana  
**Testing:** pytest + coverage  
**API Gateway:** Kong or AWS API Gateway  

---

## DETAILED IMPLEMENTATION CHECKLIST

### PHASE 1: FOUNDATION (Weeks 1-2)

#### Database Models & Fields
- [ ] Create PaymentReconciliation model
  - [ ] Add payment_id (FK)
  - [ ] Add bank_statement_line_id (FK, nullable)
  - [ ] Add invoice_id (FK, nullable)
  - [ ] Add status (UNMATCHED|MATCHED|RECONCILED)
  - [ ] Add match_confidence (float)
  - [ ] Add matched_by, matched_at
  - [ ] Create migration & test

- [ ] Create WebhookEventProcessing model
  - [ ] Add webhook_event_id (FK)
  - [ ] Add processing_status
  - [ ] Add error_message
  - [ ] Add retry_count, next_retry_at
  - [ ] Create migration & test

- [ ] Create PaymentGatewayCredentials model (encrypted storage)
  - [ ] Add school_id (FK)
  - [ ] Add gateway_name
  - [ ] Add environment (test|production)
  - [ ] Add encrypted API keys
  - [ ] Add webhook_secret
  - [ ] Create migration & test

- [ ] Add missing fields to Payment model
  - [ ] gateway_name (CharField)
  - [ ] gateway_transaction_id (CharField, nullable)
  - [ ] webhook_event_id (FK, nullable)
  - [ ] idempotency_key (CharField, unique, nullable)
  - [ ] reconciliation_status (CharField)
  - [ ] Create migration & test

- [ ] Add missing fields to Invoice model
  - [ ] payment_method_preference (CharField)
  - [ ] is_payment_plan_eligible (Boolean)
  - [ ] late_fee_waived_reason (TextField, nullable)
  - [ ] custom_due_date (DateField, nullable)
  - [ ] Create migration & test

#### Job Queue Setup
- [ ] Install and configure Celery
  - [ ] Setup Redis as broker
  - [ ] Create Celery app configuration
  - [ ] Setup periodic task scheduler (Beat)
  - [ ] Test task execution
  - [ ] Create logging for background jobs

- [ ] Create base job classes
  - [ ] BaseWebhookProcessor abstract class
  - [ ] BaseGatewayIntegration abstract class
  - [ ] BaseReconciliationJob abstract class

#### Tests (Phase 1)
- [ ] Model creation tests
- [ ] Model field validation tests
- [ ] Migration tests (forward & backward)
- [ ] Job queue tests

**Phase 1 Acceptance Criteria:**
- All models created and migrated
- Celery jobs execute successfully
- Test coverage > 80%

---

### PHASE 2: M-PESA WEBHOOK PROCESSING (Weeks 3-4)

#### Webhook Processing Implementation
- [ ] Create M-PesaWebhookProcessor class
  - [ ] Validate Safaricom signature
  - [ ] Extract callback data
  - [ ] Check idempotency key
  - [ ] Log processing attempt
  - [ ] Handle exceptions with retry

- [ ] Create background jobs:
  - [ ] ProcessM-PesaWebhookJob
  - [ ] CreatePaymentFromWebhookJob
  - [ ] CreatePaymentAllocationJob
  - [ ] UpdateInvoiceStatusJob
  - [ ] PostJournalEntryJob
  - [ ] GenerateReceiptJob
  - [ ] SendNotificationJob

#### GL Posting Setup
- [ ] Add Chart of Accounts entries:
  - [ ] 1010 M-Pesa Receivable (Asset)
  - [ ] 1040 Suspense Account (Asset)
  - [ ] 2010 Accounts Receivable (Liability)

- [ ] Create JournalEntry generation logic:
  - [ ] Payment received → DR M-Pesa REC, CR AR
  - [ ] Payment allocated → Update GL balance
  - [ ] Payment reversed → Reversal entry

#### Receipt Generation
- [ ] Create receipt template (HTML/CSS)
- [ ] Create PDF generation job
- [ ] Add QR code generation (verify URL)
- [ ] Store receipt in FileStorage
- [ ] Create receipt download endpoint

#### Notifications
- [ ] Create notification service
- [ ] Implement SMS notification
- [ ] Implement email notification
- [ ] Add notification preferences
- [ ] Test SMS/email delivery

#### Tests (Phase 2)
- [ ] Test webhook validation (valid & invalid signatures)
- [ ] Test idempotency (duplicate webhook)
- [ ] Test payment creation workflow
- [ ] Test invoice status updates
- [ ] Test GL posting
- [ ] Test receipt generation
- [ ] Test notifications
- [ ] Test error scenarios

**Phase 2 Acceptance Criteria:**
- M-Pesa webhooks processed end-to-end
- Payment records created automatically
- Invoices updated correctly
- GL entries posted
- Receipts generated
- Notifications sent
- Test coverage > 85%
- Processing latency < 5 minutes

**Deployment:**
- [ ] Deploy to staging
- [ ] Test with 10% of live webhooks
- [ ] Monitor for errors
- [ ] Gradually increase to 50%
- [ ] Gradually increase to 100%

---

### PHASE 3: STRIPE INTEGRATION (Weeks 5-6)

#### Stripe API Setup
- [ ] Create StripePaymentGateway wrapper class
  - [ ] Initialize Stripe API client
  - [ ] Create Payment Intent
  - [ ] Handle 3D Secure/SCA
  - [ ] Process refunds
  - [ ] List transactions

#### Stripe Webhooks
- [ ] Create StripeWebhookProcessor class
  - [ ] Validate webhook signature
  - [ ] Handle charge.succeeded event
  - [ ] Handle charge.failed event
  - [ ] Handle charge.refunded event

#### Stripe Payment Job
- [ ] Create ProcessStripeWebhookJob
- [ ] Create CreatePaymentFromStripeJob
- [ ] Same flow as M-Pesa (allocation, GL, receipt, notification)

#### User Endpoints
- [ ] Create POST /api/finance/stripe/checkout/
  - [ ] Create Stripe session
  - [ ] Return checkout URL
  - [ ] Handle errors

- [ ] Create POST /api/finance/stripe/webhook/
  - [ ] Process Stripe events
  - [ ] Handle success/failure
  - [ ] Signature verification

#### Frontend Component
- [ ] Create StripeCheckoutForm component
  - [ ] @stripe/react-stripe-js integration
  - [ ] Card element
  - [ ] Error handling
  - [ ] Loading state

#### Tests (Phase 3)
- [ ] Test Stripe API calls
- [ ] Test webhook signature validation
- [ ] Test payment intent creation
- [ ] Test charge processing
- [ ] Test refund processing
- [ ] Test 3D Secure handling
- [ ] Integration test end-to-end

**Phase 3 Acceptance Criteria:**
- Stripe charges processed successfully
- Webhooks handled correctly
- Payment records created
- Invoices updated
- GL entries posted
- Test coverage > 85%

**Deployment:**
- [ ] Deploy to staging
- [ ] Test in Stripe test mode
- [ ] Manual testing with sample card
- [ ] Go live with limited schools
- [ ] Monitor transaction volume

---

### PHASE 4: BANK INTEGRATION (Weeks 7-8)

#### Bank Import
- [ ] Create BankStatementImportJob
  - [ ] Connect to bank API (or handle CSV)
  - [ ] Parse transactions
  - [ ] Normalize data
  - [ ] Create BankStatementLine records
  - [ ] Detect duplicates

#### Auto-Reconciliation
- [ ] Create AutoReconciliationJob
  - [ ] Implement fuzzy matching algorithm
  - [ ] Amount matching (exact or within tolerance)
  - [ ] Date matching (within 3 days)
  - [ ] Reference number matching
  - [ ] Phone number matching

- [ ] Create PaymentReconciliation records:
  - [ ] Confidence > 95% → Auto-match
  - [ ] Confidence 80-94% → Flag for review
  - [ ] Confidence < 80% → Unmatched

#### Manual Reconciliation UI
- [ ] Create BankReconciliationUI component
  - [ ] List unmatched transactions
  - [ ] Show fuzzy match suggestions
  - [ ] One-click match confirmation
  - [ ] Manual lookup option
  - [ ] Bulk action support

#### GL Posting for Bank
- [ ] Create GL posting for bank deposits
  - [ ] DR Bank Account, CR AR
  - [ ] Create bank reconciliation entries

#### Tests (Phase 4)
- [ ] Test CSV parsing
- [ ] Test fuzzy matching accuracy
- [ ] Test duplicate detection
- [ ] Test manual reconciliation workflow
- [ ] Test GL posting

**Phase 4 Acceptance Criteria:**
- Bank statements imported automatically
- Auto-matching confidence > 95%
- Manual reconciliation workflow functional
- GL entries posted
- Test coverage > 80%

**Deployment:**
- [ ] Deploy to staging
- [ ] Test with historical bank data
- [ ] Bursar reviews matches
- [ ] Manual testing with real bank
- [ ] Schedule automated imports

---

### PHASE 5: USER INTERFACE (Weeks 9-10)

#### Payment Method Selector
- [ ] Create PaymentMethodSelector component
  - [ ] Show available methods per school
  - [ ] Icons and descriptions
  - [ ] Feature flags

#### Payment Components
- [ ] Create PaymentHistoryChart component
  - [ ] Timeline visualization
  - [ ] Filter by method, date range
  - [ ] Export CSV/PDF

- [ ] Create ReceiptDownloadComponent
  - [ ] Display receipt details
  - [ ] Download as PDF
  - [ ] Email option

- [ ] Create ReceiptViewComponent
  - [ ] Show payment confirmation
  - [ ] QR code for verification
  - [ ] Print option

#### Student Portal Updates
- [ ] Update invoice view
  - [ ] Show payment methods
  - [ ] Show payment history
  - [ ] Download receipt link

- [ ] Create payment selection flow
  - [ ] Show balance
  - [ ] Select amount
  - [ ] Choose payment method
  - [ ] Confirmation screen

#### Parent Portal Updates
- [ ] Similar updates for parent portal
- [ ] Multi-child support

#### Bursar Dashboard Updates
- [ ] Add payment method breakdown chart
  - [ ] M-Pesa, Stripe, Bank, Cash percentages
  - [ ] Daily/monthly trends

- [ ] Add gateway performance widget
  - [ ] Success/failure rates
  - [ ] Processing time
  - [ ] Alerts for failures

- [ ] Add reconciliation status widget
  - [ ] Unmatched count
  - [ ] Oldest unmatched date
  - [ ] Link to reconciliation UI

#### Bank Reconciliation UI
- [ ] Create bank statement view
  - [ ] Unmatched transactions list
  - [ ] Fuzzy match suggestions
  - [ ] Match confirmation workflow
  - [ ] Bulk actions

#### Tests (Phase 5)
- [ ] Component unit tests
- [ ] Integration tests
- [ ] User flow tests
- [ ] Responsive design tests
- [ ] Accessibility tests

**Phase 5 Acceptance Criteria:**
- All components created
- User flows complete
- Responsive design verified
- Accessibility WCAG 2.1 AA
- Student/parent testing completed

**Deployment:**
- [ ] Deploy to staging
- [ ] Beta test with limited users
- [ ] Gather feedback
- [ ] Iterate design
- [ ] Full rollout

---

### PHASE 6: MONITORING & HARDENING (Weeks 11-12)

#### Monitoring Setup
- [ ] Create payment processing metrics
  - [ ] Webhook delivery rate
  - [ ] Processing latency
  - [ ] Success/failure rate
  - [ ] Match confidence distribution

- [ ] Setup alerting
  - [ ] Webhook failures (> 5 in 1 hour)
  - [ ] Processing latency (> 5 minutes)
  - [ ] High error rate (> 5%)
  - [ ] Stripe API errors
  - [ ] Bank import failures

- [ ] Create dashboards
  - [ ] Real-time payment processing
  - [ ] Daily collection summary
  - [ ] Error log viewer
  - [ ] Reconciliation status

#### Documentation
- [ ] Create user guides
  - [ ] Student payment guide
  - [ ] Parent payment guide
  - [ ] Bursar operation manual
  - [ ] Emergency procedures

- [ ] Create technical documentation
  - [ ] System architecture diagram
  - [ ] API documentation (auto-generate)
  - [ ] Troubleshooting guide
  - [ ] Disaster recovery plan

- [ ] Create audit documentation
  - [ ] Payment audit trail guide
  - [ ] GL reconciliation procedure
  - [ ] Period-end closing checklist
  - [ ] Compliance checklist (IFRS 15)

#### Training
- [ ] Create training materials
- [ ] Finance staff training
- [ ] System administrator training
- [ ] Support staff training

#### Security Hardening
- [ ] Webhook signature verification (all gateways)
- [ ] Encrypt sensitive credentials in database
- [ ] Add rate limiting to payment endpoints
- [ ] Implement audit logging for all financial transactions
- [ ] Add PCI DSS compliance checks
- [ ] Penetration testing for payment endpoints

#### Optimization
- [ ] Database indexing review
  - [ ] Payment.payment_date
  - [ ] Payment.student_id
  - [ ] PaymentGatewayWebhookEvent.processed
  - [ ] Invoice.status

- [ ] Query optimization
  - [ ] Payment list (complex filters)
  - [ ] GL balance calculations
  - [ ] Reconciliation matching

- [ ] Caching strategy
  - [ ] Cache invoice list (5 min)
  - [ ] Cache payment methods (30 min)
  - [ ] Cache GL balances (1 hour)

#### Tests (Phase 6)
- [ ] Load testing (1000s payments/day)
- [ ] Stress testing (high concurrent webhooks)
- [ ] Security testing (penetration test)
- [ ] Documentation review

**Phase 6 Acceptance Criteria:**
- Monitoring in place
- Alerts functional
- Documentation complete
- Training completed
- Staff comfortable with new system

---

## QUICK REFERENCE: STATUS BY FEATURE

### M-Pesa Payments
| Component | Current | Target | Timeline |
|-----------|---------|--------|----------|
| Webhook receipt | ✅ | ✅ | Already done |
| Payment creation | ❌ | ✅ | Phase 2, Week 3 |
| Invoice update | ❌ | ✅ | Phase 2, Week 3 |
| GL posting | ❌ | ✅ | Phase 2, Week 4 |
| Receipt generation | ❌ | ✅ | Phase 2, Week 4 |
| Notification | ❌ | ✅ | Phase 2, Week 4 |
| Status: **IN PROGRESS** | | | Starts Week 3 |

### Stripe Payments
| Component | Current | Target | Timeline |
|-----------|---------|--------|----------|
| API integration | ❌ | ✅ | Phase 3, Week 5 |
| Webhook handler | ❌ | ✅ | Phase 3, Week 5 |
| Payment processing | ❌ | ✅ | Phase 3, Week 6 |
| Refund support | ❌ | ✅ | Phase 3, Week 6 |
| User endpoint | ❌ | ✅ | Phase 3, Week 5 |
| Frontend component | ❌ | ✅ | Phase 3, Week 6 |
| Status: **NOT STARTED** | | | Starts Week 5 |

### Bank Payments
| Component | Current | Target | Timeline |
|-----------|---------|--------|----------|
| CSV import | ⚠️ | ✅ | Phase 4, Week 7 |
| API import | ❌ | ✅ | Phase 4, Week 7 |
| Auto-matching | ❌ | ✅ | Phase 4, Week 7 |
| Manual matching UI | ❌ | ✅ | Phase 4, Week 8 |
| GL posting | ❌ | ✅ | Phase 4, Week 8 |
| Status: **NOT STARTED** | | | Starts Week 7 |

### User Interface
| Component | Current | Target | Timeline |
|-----------|---------|--------|----------|
| Payment method selector | ❌ | ✅ | Phase 5, Week 9 |
| Stripe checkout form | ❌ | ✅ | Phase 5, Week 10 |
| Payment history chart | ❌ | ✅ | Phase 5, Week 9 |
| Receipt download | ❌ | ✅ | Phase 5, Week 10 |
| Reconciliation UI | ❌ | ✅ | Phase 5, Week 10 |
| Bursar dashboard | ⚠️ | ✅ | Phase 5, Week 9 |
| Status: **NOT STARTED** | | | Starts Week 9 |

---

## RISK MITIGATION

### High Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Data loss during migration | Low | CRITICAL | Test migration procedure on staging first, full backup before migration |
| Duplicate payments created | Medium | HIGH | Implement idempotency keys, extensive testing of webhook deduplication |
| Wrong invoice updated | Medium | HIGH | Fuzzy matching with confidence thresholds, bursar review for <95% matches |
| GL out of balance | Low | CRITICAL | Automated GL reconciliation report, monthly verification |
| Payment processing delays | Medium | MEDIUM | Async job queue with retry logic, SLA monitoring |
| Webhook signature failures | Low | MEDIUM | Comprehensive testing, detailed error logging |
| Staff training delays | Medium | MEDIUM | Early training, documentation, support hotline |

---

## SUCCESS METRICS

### By Week 8 (All 3 Payment Methods Implemented)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Payment processing latency | < 5 minutes | Monitor PaymentGatewayWebhookEvent creation to Payment status change |
| Webhook success rate | > 98% | PaymentGatewayWebhookEvent.processed = true / total received |
| Auto-match confidence | > 95% | Matched payments with confidence > 95% / total reconciled |
| GL posting accuracy | 100% | Trial balance balanced monthly |
| System uptime | > 99.9% | Payment processing available 24/7 |
| User adoption (Stripe) | > 10% of payments | Stripe payment count vs M-Pesa count |

---

## SIGN-OFF CHECKLIST

### Executive Approval Required Before Phase 1

- [ ] CFO approval of financial system changes
- [ ] IT Director approval of infrastructure (job queue, monitoring)
- [ ] Legal review of payment PII handling
- [ ] Board approval of Stripe/Bank integrations

### Phase-by-Phase Approval

**Phase 1 Completion Sign-off:**
- [ ] CTO confirms all models created and tested
- [ ] Database architect confirms migration plan
- [ ] Lead developer confirms job queue functional

**Phase 2 Completion Sign-off:**
- [ ] Finance director confirms GL entries match bank records
- [ ] Bursar confirms payment processing working
- [ ] QA lead confirms test coverage > 85%

**Phase 3 Completion Sign-off:**
- [ ] Stripe account manager confirms API integration correct
- [ ] Security lead confirms webhook validation secure
- [ ] CTO confirms production-ready

**Phase 4 Completion Sign-off:**
- [ ] Bank relationship manager confirms data format correct
- [ ] Finance director confirms reconciliation procedures updated
- [ ] Compliance confirms audit trail adequate

**Phase 5 Completion Sign-off:**
- [ ] UX lead confirms user testing completed
- [ ] Accessibility consultant confirms WCAG 2.1 AA
- [ ] Product manager confirms feature complete

**Phase 6 Completion Sign-off:**
- [ ] Operations confirms monitoring alerts working
- [ ] Finance director confirms staff trained
- [ ] CTO confirms system ready for production

---

**Document Version:** 1.0  
**Last Updated:** April 17, 2026  
**Next Review:** May 1, 2026

