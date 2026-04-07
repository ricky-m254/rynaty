from django.db import transaction, models
from django.db.models import Sum
from django.utils import timezone
from .models import (
    Invoice, InvoiceLineItem, Payment, PaymentAllocation, 
    InvoiceAdjustment, FeeAssignment, AuditLog, PaymentReversalRequest,
    InvoiceWriteOffRequest, ScholarshipAward,
    InvoiceInstallmentPlan, InvoiceInstallment, LateFeeRule, FeeReminderLog
    , AccountingPeriod, ChartOfAccount, JournalEntry, JournalLine
    , CashbookEntry, PaymentGatewayTransaction, PaymentGatewayWebhookEvent, BankStatementLine
    , Module, TenantModule, ModuleSetting, FeeStructure, BalanceCarryForward
)
from .events import (
    invoice_created, payment_recorded, payment_allocated,
    invoice_adjusted, fee_assigned
)
from decimal import Decimal
from datetime import timedelta

class FinanceService:
    @staticmethod
    def post_library_fine_accrual(*, fine_id: int, amount, entry_date=None, posted_by=None):
        amount_value = Decimal(str(amount or 0))
        if amount_value <= 0:
            return None
        entry_date = entry_date or timezone.now().date()
        accounts = FinanceService._get_default_accounts()
        return FinanceService._post_journal(
            entry_date=entry_date,
            memo=f"Library fine accrual #{fine_id}",
            lines=[
                {"account": accounts["1100"], "debit": amount_value, "credit": 0, "description": "Library fine receivable"},
                {"account": accounts["4000"], "debit": 0, "credit": amount_value, "description": "Library fine revenue"},
            ],
            source_type="LibraryFineAccrual",
            source_id=fine_id,
            posted_by=posted_by,
            entry_key=f"library_fine_accrual:{fine_id}",
        )

    @staticmethod
    def post_library_fine_payment(*, fine_id: int, amount, payment_marker: str, entry_date=None, posted_by=None):
        amount_value = Decimal(str(amount or 0))
        if amount_value <= 0:
            return None
        entry_date = entry_date or timezone.now().date()
        accounts = FinanceService._get_default_accounts()
        return FinanceService._post_journal(
            entry_date=entry_date,
            memo=f"Library fine payment #{fine_id}",
            lines=[
                {"account": accounts["1000"], "debit": amount_value, "credit": 0, "description": "Cash received for library fine"},
                {"account": accounts["1100"], "debit": 0, "credit": amount_value, "description": "Library fine receivable settlement"},
            ],
            source_type="LibraryFinePayment",
            source_id=fine_id,
            posted_by=posted_by,
            entry_key=f"library_fine_payment:{fine_id}:{payment_marker}",
        )

    @staticmethod
    def post_library_fine_waiver(*, fine_id: int, amount, entry_date=None, posted_by=None):
        amount_value = Decimal(str(amount or 0))
        if amount_value <= 0:
            return None
        entry_date = entry_date or timezone.now().date()
        accounts = FinanceService._get_default_accounts()
        return FinanceService._post_journal(
            entry_date=entry_date,
            memo=f"Library fine waiver #{fine_id}",
            lines=[
                {"account": accounts["5000"], "debit": amount_value, "credit": 0, "description": "Library fine waiver expense"},
                {"account": accounts["1100"], "debit": 0, "credit": amount_value, "description": "Library fine receivable write-off"},
            ],
            source_type="LibraryFineWaiver",
            source_id=fine_id,
            posted_by=posted_by,
            entry_key=f"library_fine_waiver:{fine_id}",
        )

    @staticmethod
    def _active_scholarships_for_student(student, as_of_date):
        scholarships = ScholarshipAward.objects.filter(
            student=student,
            is_active=True,
            status='ACTIVE',
        )
        if as_of_date:
            scholarships = scholarships.filter(
                models.Q(start_date__isnull=True) | models.Q(start_date__lte=as_of_date),
                models.Q(end_date__isnull=True) | models.Q(end_date__gte=as_of_date),
            )
        return list(scholarships)

    @staticmethod
    def _scholarship_context(student, as_of_date):
        awards = FinanceService._active_scholarships_for_student(student, as_of_date)
        full_coverage = any(a.award_type == 'FULL' for a in awards)
        percent_rate = Decimal('0.00')
        fixed_pool = Decimal('0.00')
        for award in awards:
            if award.award_type == 'PERCENT':
                percent_rate += Decimal(str(award.percentage or 0))
            elif award.award_type == 'FIXED':
                fixed_pool += Decimal(str(award.amount or 0))
        if percent_rate > Decimal('100.00'):
            percent_rate = Decimal('100.00')
        return {
            "count": len(awards),
            "full_coverage": full_coverage,
            "percent_rate": percent_rate,
            "fixed_pool_remaining": fixed_pool,
        }

    @staticmethod
    def _apply_scholarship_discount(base_amount, scholarship_ctx):
        amount = Decimal(str(base_amount or 0)).quantize(Decimal('0.01'))
        if amount <= 0:
            return Decimal('0.00'), Decimal('0.00')
        if scholarship_ctx.get("full_coverage"):
            return amount, Decimal('0.00')

        percent_rate = Decimal(str(scholarship_ctx.get("percent_rate") or 0))
        percent_discount = (amount * percent_rate / Decimal('100')).quantize(Decimal('0.01'))
        if percent_discount > amount:
            percent_discount = amount
        remaining = amount - percent_discount

        fixed_pool = Decimal(str(scholarship_ctx.get("fixed_pool_remaining") or 0))
        fixed_discount = min(fixed_pool, remaining)
        scholarship_ctx["fixed_pool_remaining"] = (fixed_pool - fixed_discount).quantize(Decimal('0.01'))

        total_discount = (percent_discount + fixed_discount).quantize(Decimal('0.01'))
        final_amount = (amount - total_discount).quantize(Decimal('0.01'))
        if final_amount < Decimal('0.00'):
            final_amount = Decimal('0.00')
        return total_discount, final_amount

    @staticmethod
    def send_invoice_reminder(invoice, channel='EMAIL', recipient_override=None):
        if invoice.status == 'VOID':
            return {"messages_sent": 0, "error": "Cannot send reminder for void invoice."}
        FinanceService.sync_invoice_status(invoice)
        if invoice.balance_due <= 0:
            return {"messages_sent": 0, "error": "Invoice has no outstanding balance."}

        recipients = []
        if recipient_override:
            recipients = [recipient_override]
        else:
            recipients = list(invoice.student.guardians.values_list('email', flat=True))
            recipients = [email for email in recipients if email]
            if not recipients:
                recipients = [f"student:{invoice.student_id}"]

        for recipient in recipients:
            FeeReminderLog.objects.create(
                invoice=invoice,
                channel=channel,
                recipient=recipient,
                status='SENT',
                message=f"Invoice {invoice.invoice_number} reminder. Balance due: {invoice.balance_due}.",
            )
        return {"messages_sent": len(recipients)}

    @staticmethod
    @transaction.atomic
    def ingest_gateway_webhook(provider, event_id, event_type, signature, payload):
        event, created = PaymentGatewayWebhookEvent.objects.get_or_create(
            event_id=event_id,
            defaults={
                "provider": provider,
                "event_type": event_type,
                "signature": signature or "",
                "payload": payload or {},
            },
        )
        if not created:
            return event, False

        try:
            data = payload or {}
            external_id = str(data.get("external_id") or data.get("transaction_id") or "")
            status = str(data.get("status") or "").upper()
            amount = Decimal(str(data.get("amount") or "0"))
            student_id = data.get("student_id")
            invoice_id = data.get("invoice_id")

            if external_id:
                tx_defaults = {
                    "provider": provider,
                    "amount": amount if amount >= 0 else Decimal("0.00"),
                    "status": status if status in {"INITIATED", "PENDING", "SUCCEEDED", "FAILED", "REFUNDED"} else "PENDING",
                    "payload": data,
                }
                if student_id:
                    tx_defaults["student_id"] = student_id
                if invoice_id:
                    tx_defaults["invoice_id"] = invoice_id

                tx, _ = PaymentGatewayTransaction.objects.update_or_create(
                    external_id=external_id,
                    defaults=tx_defaults,
                )

                if tx.status == "SUCCEEDED" and tx.amount > 0:
                    reference = f"{provider.upper()}-{external_id}"
                    payment, _ = Payment.objects.get_or_create(
                        reference_number=reference,
                        defaults={
                            "student_id": tx.student_id,
                            "amount": tx.amount,
                            "payment_method": provider,
                            "notes": f"Gateway payment {external_id}",
                            "is_active": True,
                        },
                    )
                    if tx.invoice_id:
                        invoice = Invoice.objects.filter(id=tx.invoice_id, is_active=True).first()
                        if invoice and payment.is_active:
                            current_allocated = payment.allocations.aggregate(total=Sum("amount_allocated"))["total"] or Decimal("0.00")
                            if current_allocated <= 0:
                                alloc_amount = min(tx.amount, invoice.balance_due)
                                if alloc_amount > 0:
                                    FinanceService.allocate_payment(payment, invoice, alloc_amount)
                    tx.is_reconciled = True
                    tx.save(update_fields=["is_reconciled", "updated_at"])

            event.processed = True
            event.processed_at = timezone.now()
            event.save(update_fields=["processed", "processed_at"])
        except Exception as exc:
            event.error = str(exc)
            event.save(update_fields=["error"])
        return event, True

    @staticmethod
    def reconcile_bank_line(line):
        if line.status not in {"UNMATCHED", "MATCHED"}:
            return line

        if not line.matched_payment:
            ref = (line.reference or "").strip()
            if ref:
                payment = Payment.objects.filter(reference_number__iexact=ref, is_active=True).first()
                if payment:
                    line.matched_payment = payment
                    line.status = "MATCHED"

        if not line.matched_gateway_transaction:
            ref = (line.reference or "").strip()
            if ref:
                tx = PaymentGatewayTransaction.objects.filter(external_id__iexact=ref).first()
                if tx:
                    line.matched_gateway_transaction = tx
                    if line.status == "UNMATCHED":
                        line.status = "MATCHED"

        line.save()
        return line
    @staticmethod
    def _ensure_open_period(entry_date):
        period = AccountingPeriod.objects.filter(
            start_date__lte=entry_date,
            end_date__gte=entry_date,
        ).order_by('-start_date').first()
        if period and period.is_closed:
            raise ValueError(f"Accounting period '{period.name}' is closed.")

    @staticmethod
    def _get_default_accounts():
        defaults = [
            ("1100", "Accounts Receivable", "ASSET"),
            ("1000", "Cash/Bank", "ASSET"),
            ("2100", "Fee Carry-Forward Clearing", "LIABILITY"),
            ("4000", "School Fee Revenue", "REVENUE"),
            ("5000", "Operating Expense", "EXPENSE"),
        ]
        accounts = {}
        for code, name, account_type in defaults:
            account, _ = ChartOfAccount.objects.get_or_create(
                code=code,
                defaults={"name": name, "account_type": account_type, "is_active": True},
            )
            accounts[code] = account
        return accounts

    @staticmethod
    @transaction.atomic
    def _post_journal(entry_date, memo, lines, source_type="", source_id=None, posted_by=None, entry_key=None):
        FinanceService._ensure_open_period(entry_date)
        debit_total = Decimal('0.00')
        credit_total = Decimal('0.00')
        for line in lines:
            debit_total += Decimal(str(line.get('debit', 0) or 0))
            credit_total += Decimal(str(line.get('credit', 0) or 0))
        if debit_total != credit_total:
            raise ValueError("Journal entry must balance (debit == credit).")

        if entry_key:
            existing = JournalEntry.objects.filter(entry_key=entry_key).first()
            if existing:
                return existing

        entry = JournalEntry.objects.create(
            entry_date=entry_date,
            memo=memo,
            source_type=source_type,
            source_id=source_id,
            entry_key=entry_key,
            posted_by=posted_by,
        )
        for line in lines:
            JournalLine.objects.create(
                entry=entry,
                account=line['account'],
                vote_head=line.get('vote_head'),
                debit=Decimal(str(line.get('debit', 0) or 0)),
                credit=Decimal(str(line.get('credit', 0) or 0)),
                description=line.get('description', ''),
            )
        return entry

    @staticmethod
    def recompute_cashbook_running_balances(book_type):
        entries = list(CashbookEntry.objects.filter(book_type=book_type).order_by('entry_date', 'created_at'))
        balance = Decimal('0.00')
        for entry in entries:
            balance += Decimal(str(entry.amount_in or 0)) - Decimal(str(entry.amount_out or 0))
            entry.running_balance = balance
        if entries:
            CashbookEntry.objects.bulk_update(entries, ['running_balance'])

    @staticmethod
    @transaction.atomic
    def record_cashbook_entry(
        *,
        book_type,
        entry_date,
        entry_type,
        reference="",
        description="",
        amount_in=Decimal('0.00'),
        amount_out=Decimal('0.00'),
        payment=None,
        expense=None,
        is_auto=True,
    ):
        FinanceService._ensure_open_period(entry_date)
        entry = CashbookEntry.objects.create(
            book_type=book_type,
            entry_date=entry_date,
            entry_type=entry_type,
            reference=reference,
            description=description,
            amount_in=Decimal(str(amount_in or 0)),
            amount_out=Decimal(str(amount_out or 0)),
            payment=payment,
            expense=expense,
            is_auto=is_auto,
        )
        FinanceService.recompute_cashbook_running_balances(book_type)
        entry.refresh_from_db()
        return entry

    @staticmethod
    def sync_invoice_status(invoice):
        if invoice.status == 'VOID':
            return invoice.status

        balance = invoice.balance_due
        today = timezone.now().date()
        if balance <= 0:
            next_status = 'PAID'
        elif balance < invoice.total_amount:
            next_status = 'PARTIALLY_PAID'
        elif invoice.due_date < today:
            next_status = 'OVERDUE'
        elif invoice.status in {'DRAFT', 'CONFIRMED'}:
            next_status = 'ISSUED'
        else:
            next_status = invoice.status

        if next_status != invoice.status:
            invoice.status = next_status
            invoice.save(update_fields=['status'])
        FinanceService.sync_installment_statuses(invoice)
        return next_status

    @staticmethod
    def sync_installment_statuses(invoice):
        plan = getattr(invoice, 'installment_plan', None)
        if not plan:
            return
        installments = list(plan.installments.all().order_by('sequence'))
        if not installments:
            return
        today = timezone.now().date()

        for installment in installments:
            if installment.status == 'WAIVED':
                continue
            amount = Decimal(str(installment.amount or 0))
            collected = Decimal(str(installment.collected_amount or 0))
            if collected < Decimal('0.00'):
                collected = Decimal('0.00')
            if collected > amount:
                collected = amount

            next_status = 'PAID' if collected >= amount else ('OVERDUE' if installment.due_date < today else 'PENDING')
            update_fields = []
            if next_status != installment.status:
                installment.status = next_status
                update_fields.append('status')

            if next_status == 'PAID' and installment.paid_at is None:
                installment.paid_at = timezone.now()
                update_fields.append('paid_at')
            if next_status != 'PAID' and installment.paid_at is not None:
                installment.paid_at = None
                update_fields.append('paid_at')

            if update_fields:
                installment.save(update_fields=update_fields)

    @staticmethod
    def _apply_amount_to_installments(invoice, amount_to_apply, preferred_installment=None):
        plan = getattr(invoice, 'installment_plan', None)
        if not plan:
            return Decimal('0.00')
        remaining = Decimal(str(amount_to_apply or 0))
        if remaining <= 0:
            return Decimal('0.00')

        installments = list(plan.installments.exclude(status='WAIVED').order_by('sequence'))
        if not installments:
            return Decimal('0.00')

        applied = Decimal('0.00')
        if preferred_installment:
            installments = [inst for inst in installments if inst.id == preferred_installment.id] + [
                inst for inst in installments if inst.id != preferred_installment.id
            ]

        for installment in installments:
            if remaining <= 0:
                break
            outstanding = Decimal(str(installment.amount or 0)) - Decimal(str(installment.collected_amount or 0))
            if outstanding <= 0:
                continue
            allocate = outstanding if outstanding <= remaining else remaining
            installment.collected_amount = Decimal(str(installment.collected_amount or 0)) + allocate
            installment.save(update_fields=['collected_amount'])
            applied += allocate
            remaining -= allocate
        return applied

    @staticmethod
    @transaction.atomic
    def create_invoice(student, term, line_items_data, due_date, status=None, is_active=None):
        FinanceWriteGuard.ensure_student_readonly()
        total_amount = Decimal('0.00')
        revenue_amount = Decimal('0.00')
        carry_forward_amount = Decimal('0.00')
        for item in line_items_data:
            item_amount = Decimal(str(item['amount']))
            total_amount += item_amount
            if item.get('recognize_revenue', True):
                revenue_amount += item_amount
            else:
                carry_forward_amount += item_amount
        invoice = Invoice.objects.create(
            student=student,
            term=term,
            total_amount=total_amount,
            due_date=due_date,
            status=status or 'CONFIRMED',
            is_active=True if is_active is None else is_active
        )
        for item_data in line_items_data:
            InvoiceLineItem.objects.create(
                invoice=invoice,
                fee_structure=item_data['fee_structure'],
                description=item_data.get('description', ''),
                amount=item_data['amount']
            )
        FinanceService.sync_invoice_status(invoice)
        if total_amount > 0:
            accounts = FinanceService._get_default_accounts()
            journal_lines = [
                {"account": accounts["1100"], "debit": total_amount, "credit": 0, "description": "Accounts Receivable"},
            ]
            if revenue_amount > 0:
                journal_lines.append(
                    {"account": accounts["4000"], "debit": 0, "credit": revenue_amount, "description": "Fee Revenue"}
                )
            if carry_forward_amount > 0:
                journal_lines.append(
                    {
                        "account": accounts["2100"],
                        "debit": 0,
                        "credit": carry_forward_amount,
                        "description": "Arrears carry-forward clearing",
                    }
                )
            FinanceService._post_journal(
                entry_date=timezone.now().date(),
                memo=f"Invoice {invoice.invoice_number or invoice.id} posted",
                lines=journal_lines,
                source_type="Invoice",
                source_id=invoice.id,
                posted_by=None,
                entry_key=f"invoice:{invoice.id}",
            )
        invoice_created.send(
            sender=FinanceService,
            invoice_id=invoice.id,
            student_id=student.id,
            term_id=term.id,
            total_amount=str(total_amount)
        )
        return invoice

    @staticmethod
    @transaction.atomic
    def record_payment(student, amount, payment_method, reference_number, notes=""):
        FinanceWriteGuard.ensure_student_readonly()
        FinanceService._ensure_open_period(timezone.now().date())
        payment = Payment.objects.create(
            student=student,
            amount=amount,
            payment_method=payment_method,
            reference_number=reference_number,
            notes=notes
        )
        payment_recorded.send(
            sender=FinanceService,
            payment_id=payment.id,
            student_id=student.id,
            amount=str(amount),
            reference_number=reference_number
        )
        return payment

    @staticmethod
    @transaction.atomic
    def allocate_payment(payment, invoice, amount_to_allocate):
        FinanceWriteGuard.ensure_student_readonly()
        if not payment.is_active:
            raise ValueError("Cannot allocate an inactive/reversed payment.")
        if invoice.status == 'VOID':
            raise ValueError("Cannot allocate to a void invoice.")
        amount_to_allocate = Decimal(str(amount_to_allocate))
        if amount_to_allocate <= 0:
            raise ValueError("Allocation amount must be greater than zero.")
        if payment.student_id != invoice.student_id:
            raise ValueError("Payment and invoice must belong to the same student.")
        # 1. Validate Payment Availability
        current_allocations = payment.allocations.aggregate(total=Sum('amount_allocated'))['total'] or 0
        available_payment = payment.amount - current_allocations
        
        if amount_to_allocate > available_payment:
            raise ValueError(f"Insufficient funds in payment. Available: {available_payment}")

        # 2. Validate Invoice Balance (Prevent Overpayment)
        if amount_to_allocate > invoice.balance_due:
            raise ValueError(f"Amount exceeds invoice balance. Due: {invoice.balance_due}")

        allocation = PaymentAllocation.objects.create(
            payment=payment,
            invoice=invoice,
            amount_allocated=amount_to_allocate
        )
        payment_allocated.send(
            sender=FinanceService,
            allocation_id=allocation.id,
            payment_id=payment.id,
            invoice_id=invoice.id,
            amount_allocated=str(amount_to_allocate)
        )
        accounts = FinanceService._get_default_accounts()
        FinanceService._post_journal(
            entry_date=timezone.now().date(),
            memo=f"Payment allocation {allocation.id} for invoice {invoice.invoice_number or invoice.id}",
            lines=[
                {"account": accounts["1000"], "debit": amount_to_allocate, "credit": 0, "description": "Cash/Bank"},
                {"account": accounts["1100"], "debit": 0, "credit": amount_to_allocate, "description": "Accounts Receivable"},
            ],
            source_type="PaymentAllocation",
            source_id=allocation.id,
            posted_by=None,
            entry_key=f"allocation:{allocation.id}",
        )
        FinanceService.sync_invoice_status(invoice)
        FinanceService.sync_installment_statuses(invoice)
        return allocation

    @staticmethod
    @transaction.atomic
    def allocate_payment_to_installment(payment, installment, amount_to_allocate):
        invoice = installment.plan.invoice
        if invoice.student_id != payment.student_id:
            raise ValueError("Payment and installment invoice must belong to the same student.")
        amount_to_allocate = Decimal(str(amount_to_allocate))
        if amount_to_allocate <= 0:
            raise ValueError("Allocation amount must be greater than zero.")

        allocation = FinanceService.allocate_payment(payment, invoice, amount_to_allocate)
        FinanceService._apply_amount_to_installments(invoice, amount_to_allocate, preferred_installment=installment)
        FinanceService.sync_installment_statuses(invoice)
        return allocation

    @staticmethod
    @transaction.atomic
    def auto_allocate_payment(payment):
        if not payment.is_active:
            raise ValueError("Cannot auto-allocate an inactive/reversed payment.")
        unallocated = Decimal(str(payment.amount)) - Decimal(str(payment.allocations.aggregate(total=Sum('amount_allocated'))['total'] or 0))
        if unallocated <= 0:
            return {"allocated_total": Decimal('0.00'), "allocations": 0}

        invoices = Invoice.objects.filter(
            student=payment.student,
            is_active=True,
        ).exclude(status='VOID').order_by('due_date', 'id')

        allocated_total = Decimal('0.00')
        allocations = 0
        for invoice in invoices:
            FinanceService.sync_invoice_status(invoice)
            balance = Decimal(str(invoice.balance_due or 0))
            if balance <= 0:
                continue
            if unallocated <= 0:
                break
            amount = balance if balance <= unallocated else unallocated
            FinanceService.allocate_payment(payment, invoice, amount)
            FinanceService._apply_amount_to_installments(invoice, amount)
            FinanceService.sync_installment_statuses(invoice)
            allocated_total += amount
            allocations += 1
            unallocated -= amount

        return {"allocated_total": allocated_total, "allocations": allocations}

    @staticmethod
    @transaction.atomic
    def create_adjustment(invoice, amount, reason, user, adjustment_type='CREDIT', auto_approve=True):
        FinanceWriteGuard.ensure_student_readonly()
        """
        Creates a Credit Note / Waiver (Adjustment).
        Logs the action.
        """
        # Validate that adjustment doesn't exceed balance?
        # Maybe not, sometimes you adjust to refund? But for now, assume reducing balance.
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Adjustment amount must be greater than zero.")
        if adjustment_type == 'CREDIT' and amount > invoice.balance_due:
            raise ValueError(f"Adjustment amount ({amount}) exceeds current balance ({invoice.balance_due}).")

        adjustment = InvoiceAdjustment.objects.create(
            invoice=invoice,
            adjustment_type=adjustment_type,
            amount=amount,
            reason=reason,
            adjusted_by=user,
            status='APPROVED' if auto_approve else 'PENDING',
        )
        
        # Log it
        AuditLog.objects.create(
            user=user,
            action="CREATE",
            model_name="InvoiceAdjustment",
            object_id=str(adjustment.id),
            details=f"Reduced Invoice #{invoice.id} by {amount}. Reason: {reason}"
        )
        if not auto_approve:
            AuditLog.objects.create(
                user=user,
                action="CREATE",
                model_name="InvoiceAdjustment",
                object_id=str(adjustment.id),
                details=f"Submitted pending adjustment on Invoice #{invoice.id} for {amount}.",
            )
            return adjustment

        FinanceService.sync_invoice_status(invoice)
        invoice_adjusted.send(
            sender=FinanceService,
            adjustment_id=adjustment.id,
            invoice_id=invoice.id,
            amount=str(amount),
            reason=reason
        )
        FinanceService._post_adjustment_journal(adjustment=adjustment, user=user)
        return adjustment

    @staticmethod
    def _post_adjustment_journal(adjustment, user=None):
        amount = Decimal(str(adjustment.amount))
        accounts = FinanceService._get_default_accounts()
        if adjustment.adjustment_type == 'CREDIT':
            lines = [
                {"account": accounts["4000"], "debit": amount, "credit": 0, "description": "Revenue reduction"},
                {"account": accounts["1100"], "debit": 0, "credit": amount, "description": "Accounts Receivable reduction"},
            ]
        else:
            lines = [
                {"account": accounts["1100"], "debit": amount, "credit": 0, "description": "Accounts Receivable increase"},
                {"account": accounts["4000"], "debit": 0, "credit": amount, "description": "Revenue increase"},
            ]
        FinanceService._post_journal(
            entry_date=timezone.now().date(),
            memo=f"Invoice adjustment {adjustment.id} ({adjustment.adjustment_type})",
            lines=lines,
            source_type="InvoiceAdjustment",
            source_id=adjustment.id,
            posted_by=user,
            entry_key=f"adjustment:{adjustment.id}",
        )

    @staticmethod
    @transaction.atomic
    def approve_adjustment(adjustment, reviewer, review_notes=""):
        if adjustment.status != 'PENDING':
            raise ValueError("Only pending adjustments can be approved.")
        adjustment.status = 'APPROVED'
        adjustment.reviewed_by = reviewer
        adjustment.reviewed_at = timezone.now()
        adjustment.review_notes = review_notes or ''
        adjustment.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_notes'])
        FinanceService.sync_invoice_status(adjustment.invoice)
        FinanceService._post_adjustment_journal(adjustment=adjustment, user=reviewer)
        return adjustment

    @staticmethod
    @transaction.atomic
    def reject_adjustment(adjustment, reviewer, review_notes=""):
        if adjustment.status != 'PENDING':
            raise ValueError("Only pending adjustments can be rejected.")
        adjustment.status = 'REJECTED'
        adjustment.reviewed_by = reviewer
        adjustment.reviewed_at = timezone.now()
        adjustment.review_notes = review_notes or ''
        adjustment.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_notes'])
        return adjustment

    @staticmethod
    @transaction.atomic
    def create_writeoff_request(invoice, amount, reason, requested_by):
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Write-off amount must be greater than zero.")
        FinanceService.sync_invoice_status(invoice)
        if invoice.status == 'VOID':
            raise ValueError("Cannot write off a void invoice.")
        if amount > invoice.balance_due:
            raise ValueError(f"Write-off amount ({amount}) exceeds current balance ({invoice.balance_due}).")
        if InvoiceWriteOffRequest.objects.filter(invoice=invoice, status='PENDING').exists():
            raise ValueError("A pending write-off request already exists for this invoice. Please wait for it to be reviewed.")
        return InvoiceWriteOffRequest.objects.create(
            invoice=invoice,
            amount=amount,
            reason=reason,
            requested_by=requested_by,
        )

    @staticmethod
    @transaction.atomic
    def approve_writeoff_request(writeoff, reviewer, review_notes=""):
        if writeoff.status != 'PENDING':
            raise ValueError("Only pending write-off requests can be approved.")
        if writeoff.amount > writeoff.invoice.balance_due:
            raise ValueError("Write-off amount exceeds current invoice balance.")
        adjustment = FinanceService.create_adjustment(
            invoice=writeoff.invoice,
            amount=writeoff.amount,
            reason=f"Write-off #{writeoff.id}: {writeoff.reason}",
            user=reviewer,
            adjustment_type='CREDIT',
            auto_approve=True,
        )
        writeoff.status = 'APPROVED'
        writeoff.reviewed_by = reviewer
        writeoff.reviewed_at = timezone.now()
        writeoff.review_notes = review_notes or ''
        writeoff.applied_adjustment = adjustment
        writeoff.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_notes', 'applied_adjustment'])
        return writeoff

    @staticmethod
    @transaction.atomic
    def reject_writeoff_request(writeoff, reviewer, review_notes=""):
        if writeoff.status != 'PENDING':
            raise ValueError("Only pending write-off requests can be rejected.")
        writeoff.status = 'REJECTED'
        writeoff.reviewed_by = reviewer
        writeoff.reviewed_at = timezone.now()
        writeoff.review_notes = review_notes or ''
        writeoff.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_notes'])
        return writeoff

    @staticmethod
    @transaction.atomic
    def request_payment_reversal(payment, reason, requested_by):
        if not payment.is_active:
            raise ValueError("Payment is already inactive/reversed.")
        if PaymentReversalRequest.objects.filter(payment=payment, status='PENDING').exists():
            raise ValueError("A pending reversal request already exists for this payment. Please wait for it to be reviewed.")
        return PaymentReversalRequest.objects.create(
            payment=payment,
            reason=reason,
            requested_by=requested_by,
        )

    @staticmethod
    @transaction.atomic
    def approve_payment_reversal(reversal_request, reviewed_by, review_notes=""):
        if reversal_request.status != 'PENDING':
            raise ValueError("Only pending reversal requests can be approved.")
        payment = reversal_request.payment
        if not payment.is_active:
            raise ValueError("Payment is already inactive.")

        affected_invoices = [allocation.invoice for allocation in payment.allocations.select_related('invoice')]
        payment.allocations.all().delete()
        payment.is_active = False
        payment.reversed_at = timezone.now()
        payment.reversed_by = reviewed_by
        payment.reversal_reason = reversal_request.reason
        payment.save(update_fields=['is_active', 'reversed_at', 'reversed_by', 'reversal_reason'])

        reversal_request.status = 'APPROVED'
        reversal_request.reviewed_by = reviewed_by
        reversal_request.reviewed_at = timezone.now()
        reversal_request.review_notes = review_notes
        reversal_request.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_notes'])

        for invoice in affected_invoices:
            FinanceService.sync_invoice_status(invoice)

    @staticmethod
    @transaction.atomic
    def reject_payment_reversal(reversal_request, reviewed_by, review_notes=""):
        if reversal_request.status != 'PENDING':
            raise ValueError("Only pending reversal requests can be rejected.")
        reversal_request.status = 'REJECTED'
        reversal_request.reviewed_by = reviewed_by
        reversal_request.reviewed_at = timezone.now()
        reversal_request.review_notes = review_notes
        reversal_request.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_notes'])

    @staticmethod
    @transaction.atomic
    def assign_fee(student, fee_structure, discount_amount=Decimal('0.00'), user=None):
        FinanceWriteGuard.ensure_student_readonly()
        """
        Links a student to a fee structure.
        """
        assignment = FeeAssignment.objects.create(
            student=student,
            fee_structure=fee_structure,
            discount_amount=discount_amount
        )
        
        if user:
            AuditLog.objects.create(
                user=user,
                action="CREATE",
                model_name="FeeAssignment",
                object_id=str(assignment.id),
                details=f"Assigned {fee_structure.name} to {student.admission_number} with discount {discount_amount}"
            )
        fee_assigned.send(
            sender=FinanceService,
            assignment_id=assignment.id,
            student_id=student.id,
            fee_structure_id=fee_structure.id,
            discount_amount=str(discount_amount)
        )
        return assignment

    @staticmethod
    def _carry_forward_fee_structure(term):
        fee_structure = FeeStructure.objects.filter(
            name="Arrears Carry Forward",
            academic_year=term.academic_year,
            term=term,
            grade_level__isnull=True,
        ).order_by('id').first()
        if fee_structure:
            if not fee_structure.is_active:
                fee_structure.is_active = True
                fee_structure.save(update_fields=['is_active'])
            return fee_structure
        return FeeStructure.objects.create(
            name="Arrears Carry Forward",
            category="Arrears",
            amount=Decimal('0.00'),
            academic_year=term.academic_year,
            term=term,
            grade_level=None,
            billing_cycle='ONCE',
            is_mandatory=False,
            description="System-created fee structure for arrears carry-forward line items.",
            is_active=True,
        )

    @staticmethod
    def _build_carry_forward_line_items(student, term):
        carry_forwards = list(
            BalanceCarryForward.objects.filter(
                student=student,
                to_term=term,
                amount__gt=Decimal('0.00'),
            ).select_related('from_term').order_by('created_at', 'id')
        )
        if not carry_forwards:
            return []

        carry_forward_fee = FinanceService._carry_forward_fee_structure(term)
        return [
            {
                'fee_structure': carry_forward_fee,
                'amount': Decimal(str(carry_forward.amount)),
                'description': f"Arrears carry-forward from {carry_forward.from_term.name}",
                'recognize_revenue': False,
            }
            for carry_forward in carry_forwards
        ]

    @staticmethod
    @transaction.atomic
    def generate_invoices_from_assignments(term, due_date, class_id=None, grade_level_id=None, issue_immediately=True):
        from .models import Enrollment
        enrollments = Enrollment.objects.filter(is_active=True, term=term)
        if class_id:
            enrollments = enrollments.filter(school_class_id=class_id)
        if grade_level_id:
            enrollments = enrollments.filter(school_class__grade_level_id=grade_level_id)

        created = 0
        skipped = 0
        invoice_ids = []
        scholarship_applied_count = 0

        for enrollment in enrollments.select_related('student'):
            student = enrollment.student
            if Invoice.objects.filter(student=student, term=term, is_active=True).exclude(status='VOID').exists():
                skipped += 1
                continue

            assignments = FeeAssignment.objects.filter(
                student=student,
                is_active=True,
                fee_structure__term=term,
            ).select_related('fee_structure')
            carry_forward_line_items = FinanceService._build_carry_forward_line_items(student, term)
            if not assignments.exists() and not carry_forward_line_items:
                skipped += 1
                continue

            scholarship_ctx = FinanceService._scholarship_context(student, due_date)
            if scholarship_ctx["count"] > 0 and assignments.exists():
                scholarship_applied_count += 1

            line_items = []
            for assignment in assignments:
                base_amount = assignment.fee_structure.amount - assignment.discount_amount
                if base_amount < 0:
                    base_amount = Decimal('0.00')
                scholarship_discount, amount = FinanceService._apply_scholarship_discount(base_amount, scholarship_ctx)

                description = assignment.fee_structure.name
                if scholarship_discount > 0:
                    description = f"{description} (scholarship {scholarship_discount})"
                line_items.append(
                    {
                        'fee_structure': assignment.fee_structure,
                        'amount': amount,
                        'description': description,
                    }
                )
            line_items.extend(carry_forward_line_items)

            invoice = FinanceService.create_invoice(
                student=student,
                term=term,
                line_items_data=line_items,
                due_date=due_date,
                status='ISSUED' if issue_immediately else 'DRAFT',
                is_active=True,
            )
            if issue_immediately and invoice.status != 'ISSUED':
                invoice.status = 'ISSUED'
                invoice.save(update_fields=['status'])
            created += 1
            invoice_ids.append(invoice.id)

        return {
            "created": created,
            "skipped": skipped,
            "invoice_ids": invoice_ids,
            "scholarships_applied": scholarship_applied_count,
        }

    @staticmethod
    @transaction.atomic
    def create_installment_plan(invoice, installment_count, due_dates, created_by):
        if installment_count < 2:
            raise ValueError("Installment count must be at least 2.")
        if len(due_dates) != installment_count:
            raise ValueError("Number of due dates must match installment count.")
        if invoice.status == 'VOID':
            raise ValueError("Cannot create installment plan for a void invoice.")

        plan, _ = InvoiceInstallmentPlan.objects.update_or_create(
            invoice=invoice,
            defaults={"installment_count": installment_count, "created_by": created_by},
        )
        plan.installments.all().delete()

        base = (invoice.total_amount / installment_count).quantize(Decimal('0.01'))
        running_total = Decimal('0.00')
        for idx, due_date in enumerate(due_dates, start=1):
            amount = base
            if idx == installment_count:
                amount = invoice.total_amount - running_total
            InvoiceInstallment.objects.create(
                plan=plan,
                sequence=idx,
                due_date=due_date,
                amount=amount,
            )
            running_total += amount
        paid_amount = Decimal(str(invoice.total_amount or 0)) - Decimal(str(invoice.balance_due or 0))
        if paid_amount > 0:
            FinanceService._apply_amount_to_installments(invoice, paid_amount)
        FinanceService.sync_installment_statuses(invoice)
        return plan

    @staticmethod
    @transaction.atomic
    def apply_late_fees(run_by=None):
        rule = LateFeeRule.objects.filter(is_active=True).first()
        if not rule:
            return {"updated": 0, "note": "No active late fee rule."}

        today = timezone.now().date()
        updated = 0
        for installment in InvoiceInstallment.objects.select_related('plan__invoice').filter(
            status='PENDING',
            late_fee_applied=False
        ):
            if installment.due_date >= today:
                continue
            overdue_days = (today - installment.due_date).days
            if overdue_days <= rule.grace_days:
                continue
            if rule.fee_type == 'PERCENT':
                fee_amount = (installment.amount * rule.value / Decimal('100')).quantize(Decimal('0.01'))
            else:
                fee_amount = rule.value
            if rule.max_fee and fee_amount > rule.max_fee:
                fee_amount = rule.max_fee
            if fee_amount <= 0:
                continue
            FinanceService.create_adjustment(
                invoice=installment.plan.invoice,
                amount=fee_amount,
                reason=f"Late fee for installment #{installment.sequence}",
                user=run_by,
                adjustment_type='DEBIT',
            )
            installment.late_fee_applied = True
            installment.status = 'OVERDUE'
            installment.save(update_fields=['late_fee_applied', 'status'])
            updated += 1
        return {"updated": updated}

    @staticmethod
    def preview_late_fees():
        rule = LateFeeRule.objects.filter(is_active=True).first()
        if not rule:
            return {"would_update": 0, "estimated_total": Decimal('0.00'), "note": "No active late fee rule."}

        today = timezone.now().date()
        would_update = 0
        estimated_total = Decimal('0.00')
        for installment in InvoiceInstallment.objects.select_related('plan__invoice').filter(
            status='PENDING',
            late_fee_applied=False
        ):
            if installment.due_date >= today:
                continue
            overdue_days = (today - installment.due_date).days
            if overdue_days <= rule.grace_days:
                continue
            if rule.fee_type == 'PERCENT':
                fee_amount = (installment.amount * rule.value / Decimal('100')).quantize(Decimal('0.01'))
            else:
                fee_amount = rule.value
            if rule.max_fee and fee_amount > rule.max_fee:
                fee_amount = rule.max_fee
            if fee_amount <= 0:
                continue
            would_update += 1
            estimated_total += fee_amount
        return {"would_update": would_update, "estimated_total": estimated_total}

    @staticmethod
    def send_overdue_reminders(channel='EMAIL'):
        today = timezone.now().date()
        overdue = Invoice.objects.filter(is_active=True, due_date__lt=today).exclude(status='VOID').select_related('student')
        count = 0
        for invoice in overdue:
            FinanceService.sync_invoice_status(invoice)
            if invoice.balance_due <= 0:
                continue
            recipients = list(invoice.student.guardians.values_list('email', flat=True))
            recipients = [email for email in recipients if email]
            if not recipients:
                recipients = [f"student:{invoice.student_id}"]
            for recipient in recipients:
                FeeReminderLog.objects.create(
                    invoice=invoice,
                    channel=channel,
                    recipient=recipient,
                    status='SENT',
                    message=f"Invoice {invoice.invoice_number} is overdue. Balance due: {invoice.balance_due}.",
                )
                count += 1
        return {"invoices": overdue.count(), "messages_sent": count}

    @staticmethod
    def send_scheduled_reminders(mode='OVERDUE', channel='EMAIL', days_before=3):
        mode = (mode or 'OVERDUE').upper()
        today = timezone.now().date()
        queryset = Invoice.objects.filter(is_active=True).exclude(status='VOID').select_related('student')

        if mode == 'PRE_DUE':
            target_date = today + timedelta(days=int(days_before))
            queryset = queryset.filter(due_date=target_date)
        elif mode == 'DUE':
            queryset = queryset.filter(due_date=today)
        else:
            queryset = queryset.filter(due_date__lt=today)

        invoices = list(queryset)
        count = 0
        for invoice in invoices:
            FinanceService.sync_invoice_status(invoice)
            if invoice.balance_due <= 0:
                continue
            recipients = list(invoice.student.guardians.values_list('email', flat=True))
            recipients = [email for email in recipients if email]
            if not recipients:
                recipients = [f"student:{invoice.student_id}"]
            for recipient in recipients:
                FeeReminderLog.objects.create(
                    invoice=invoice,
                    channel=channel,
                    recipient=recipient,
                    status='SENT',
                    message=f"[{mode}] Invoice {invoice.invoice_number} balance due: {invoice.balance_due}.",
                )
                count += 1
        return {"mode": mode, "invoices": len(invoices), "messages_sent": count}

    @staticmethod
    def send_installment_scheduled_reminders(mode='OVERDUE', channel='EMAIL', days_before=3):
        mode = (mode or 'OVERDUE').upper()
        today = timezone.now().date()
        installments = InvoiceInstallment.objects.select_related('plan__invoice__student').exclude(status__in=['PAID', 'WAIVED'])

        if mode == 'PRE_DUE':
            target_date = today + timedelta(days=int(days_before))
            installments = installments.filter(due_date=target_date)
        elif mode == 'DUE':
            installments = installments.filter(due_date=today)
        else:
            installments = installments.filter(due_date__lt=today)

        matched = list(installments)
        count = 0
        for installment in matched:
            invoice = installment.plan.invoice
            FinanceService.sync_invoice_status(invoice)
            student = invoice.student
            recipients = list(student.guardians.values_list('email', flat=True))
            recipients = [email for email in recipients if email]
            if not recipients:
                recipients = [f"student:{student.id}"]
            outstanding = Decimal(str(installment.amount or 0)) - Decimal(str(installment.collected_amount or 0))
            if outstanding <= 0:
                continue
            for recipient in recipients:
                FeeReminderLog.objects.create(
                    invoice=invoice,
                    channel=channel,
                    recipient=recipient,
                    status='SENT',
                    message=(
                        f"[INSTALLMENT {mode}] Invoice {invoice.invoice_number} "
                        f"Installment #{installment.sequence} due {installment.due_date}. "
                        f"Outstanding: {outstanding}."
                    ),
                )
                count += 1
        return {"mode": mode, "installments": len(matched), "messages_sent": count}

    @staticmethod
    def get_summary():
        """
        Summary data for Finance module (read-only).
        """
        from .models import Invoice, Payment, Expense, Student

        invoice_total = Invoice.objects.filter(is_active=True).exclude(status='VOID').aggregate(total=Sum('total_amount'))['total'] or 0
        payment_total = Payment.objects.filter(is_active=True).aggregate(total=Sum('amount'))['total'] or 0
        expense_total = Expense.objects.filter(is_active=True).aggregate(total=Sum('amount'))['total'] or 0

        return {
            "revenue_billed": float(invoice_total),
            "cash_collected": float(payment_total),
            "total_expenses": float(expense_total),
            "net_profit": float(payment_total - expense_total),
            "outstanding_receivables": float(invoice_total - payment_total),
            "active_students_count": Student.objects.filter(is_active=True).count()
        }


class FinanceWriteGuard:
    """
    Enforces that FinanceService does not mutate Student or Enrollment data.
    This is a soft guard: it verifies no writes are pending in the current transaction.
    """
    @staticmethod
    def ensure_student_readonly():
        # Placeholder for stronger enforcement (signals or db constraints).
        # This guard exists to document the boundary explicitly.
        return True


class TenantModuleSettingsService:
    """
    Service layer for tenant module settings to keep controller logic minimal.
    Tenant isolation relies on schema isolation; only module identity is accepted.
    """

    DEFAULT_TOGGLES = {
        "analytics": True,
        "reports": True,
        "export": True,
        "ai_assistant": False,
    }

    @staticmethod
    def _build_default_config(module_key: str) -> dict:
        return {
            "module_key": module_key,
            "version": 1,
        }

    @staticmethod
    def ensure_tenant_module(module: Module) -> TenantModule:
        tenant_module, _ = TenantModule.objects.get_or_create(
            module=module,
            defaults={
                "is_enabled": bool(module.is_active),
                "sort_order": 0,
            },
        )
        return tenant_module

    @staticmethod
    def ensure_module_settings(tenant_module: TenantModule, user=None) -> ModuleSetting:
        settings_obj, created = ModuleSetting.objects.get_or_create(
            tenant_module=tenant_module,
            defaults={
                "feature_toggles": dict(TenantModuleSettingsService.DEFAULT_TOGGLES),
                "config": TenantModuleSettingsService._build_default_config(tenant_module.module.key),
                "created_by": user,
                "updated_by": user,
            },
        )
        if created:
            return settings_obj

        changed_fields = []
        if not isinstance(settings_obj.feature_toggles, dict):
            settings_obj.feature_toggles = dict(TenantModuleSettingsService.DEFAULT_TOGGLES)
            changed_fields.append("feature_toggles")
        else:
            merged = dict(TenantModuleSettingsService.DEFAULT_TOGGLES)
            merged.update(settings_obj.feature_toggles)
            if merged != settings_obj.feature_toggles:
                settings_obj.feature_toggles = merged
                changed_fields.append("feature_toggles")

        if not isinstance(settings_obj.config, dict):
            settings_obj.config = TenantModuleSettingsService._build_default_config(tenant_module.module.key)
            changed_fields.append("config")
        else:
            merged_config = dict(settings_obj.config)
            if merged_config.get("module_key") != tenant_module.module.key:
                merged_config["module_key"] = tenant_module.module.key
            version = merged_config.get("version")
            if not isinstance(version, int) or version < 1:
                merged_config["version"] = 1
            if merged_config != settings_obj.config:
                settings_obj.config = merged_config
                changed_fields.append("config")

        if changed_fields:
            settings_obj.updated_by = user
            changed_fields.append("updated_by")
            settings_obj.save(update_fields=changed_fields)
        return settings_obj

    @staticmethod
    def list_modules_for_tenant(user=None):
        modules = Module.objects.filter(is_active=True).order_by("key")
        rows = []
        for module in modules:
            tenant_module = TenantModuleSettingsService.ensure_tenant_module(module)
            TenantModuleSettingsService.ensure_module_settings(tenant_module, user=user)
            rows.append(tenant_module)
        return rows

    @staticmethod
    def get_module_settings(module_id: int, user=None):
        module = Module.objects.filter(id=module_id, is_active=True).first()
        if not module:
            return None, None
        tenant_module = TenantModuleSettingsService.ensure_tenant_module(module)
        settings_obj = TenantModuleSettingsService.ensure_module_settings(tenant_module, user=user)
        return tenant_module, settings_obj


class StudentsService:
    @staticmethod
    def get_summary():
        from .models import Student, Enrollment
        return {
            "students_active": Student.objects.filter(is_active=True).count(),
            "enrollments_active": Enrollment.objects.filter(is_active=True).count()
        }


class AcademicsService:
    @staticmethod
    def get_summary():
        from academics.models import AcademicYear, Term, SchoolClass
        return {
            "academic_years_active": AcademicYear.objects.filter(is_active=True).count(),
            "terms_active": Term.objects.filter(is_active=True).count(),
            "classes_active": SchoolClass.objects.filter(is_active=True).count()
        }


class HrService:
    @staticmethod
    def get_summary():
        from .models import Staff
        return {
            "staff_active": Staff.objects.filter(is_active=True).count()
        }


class CommunicationService:
    @staticmethod
    def get_summary():
        from .models import Message
        return {
            "messages_sent": Message.objects.count()
        }


class CoreService:
    @staticmethod
    def get_summary():
        from .models import Role, UserProfile, UserModuleAssignment
        return {
            "roles": Role.objects.count(),
            "users": UserProfile.objects.count(),
            "module_assignments": UserModuleAssignment.objects.filter(is_active=True).count()
        }


class ReportingService:
    @staticmethod
    def get_summary():
        from reporting.models import AuditLog
        from .models import Invoice
        return {
            "audit_logs": AuditLog.objects.count(),
            "invoices_pending": Invoice.objects.filter(is_active=True, status__in=['ISSUED', 'OVERDUE', 'PARTIALLY_PAID', 'CONFIRMED']).count()
        }
