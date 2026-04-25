"""
Management command: reconcile_mpesa_pending

Queries the Daraja STK Push Query API for each PENDING
PaymentGatewayTransaction older than a configurable threshold and reconciles
the record to SUCCEEDED or FAILED based on the live Safaricom response.

Successful transactions are posted through the same payment recording path
used by the real-time callback handler (FinanceService.record_payment,
invoice allocation, wallet credit).

By default the command runs against ALL tenant schemas so it can be called
from a simple background loop in start.sh.  Use --schema_name to target one
schema during debugging.

Usage
-----
    # All tenants (production cron):
    python manage.py reconcile_mpesa_pending --all-tenants

    # Single tenant (debug):
    python manage.py tenant_command reconcile_mpesa_pending --schema=school1

    # Preview without saving:
    python manage.py reconcile_mpesa_pending --all-tenants --dry-run

    # Use a longer threshold:
    python manage.py reconcile_mpesa_pending --all-tenants --minutes 30
"""
import logging

from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Query Daraja for PENDING M-Pesa STK transactions and reconcile "
        "their status to SUCCEEDED or FAILED."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--minutes",
            type=int,
            default=None,
            help=(
                "Only reconcile PENDING transactions older than this many "
                "minutes (defaults to finance.operations.mpesa_reconciliation_minutes "
                "or 15). Avoids racing a callback that is "
                "still in flight."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Query Daraja and log what would happen, but do not save changes.",
        )
        parser.add_argument(
            "--all-tenants",
            action="store_true",
            default=False,
            help="Run reconciliation across every non-public tenant schema.",
        )
        parser.add_argument(
            "--schema_name",
            default=None,
            help="Limit to a single tenant schema (overrides --all-tenants).",
        )

    def handle(self, *args, **options):
        from django_tenants.utils import get_tenant_model, schema_context

        all_tenants = options.get("all_tenants", False)
        schema_name = options.get("schema_name")

        if schema_name:
            # Single schema targeting: switch into the requested schema context
            # before reconciling so queries hit the correct tenant tables.
            # (When invoked via `tenant_command --schema=x`, django-tenants has
            # already switched context; schema_context is idempotent so this is
            # safe in both cases.)
            with schema_context(schema_name):
                self._reconcile_schema(schema_name, options)
        elif all_tenants:
            Client = get_tenant_model()
            schemas = list(
                Client.objects.exclude(schema_name="public").values_list(
                    "schema_name", flat=True
                )
            )
            self.stdout.write(
                f"[reconcile_mpesa_pending] Running across {len(schemas)} tenant schema(s)."
            )
            for schema in schemas:
                try:
                    with schema_context(schema):
                        self._reconcile_schema(schema, options)
                except Exception as exc:
                    logger.error(
                        "reconcile_mpesa_pending: schema=%s unhandled error: %s",
                        schema, exc, exc_info=True,
                    )
                    self.stdout.write(
                        self.style.ERROR(
                            f"  [{schema}] ERROR — {exc}"
                        )
                    )
        else:
            # No flag: run in the current schema context (useful when invoked
            # via tenant_command which switches context before calling handle).
            self._reconcile_schema("<current>", options)

    def _reconcile_schema(self, schema_label, options):
        from school.finance_ops import get_finance_operations_settings, notify_finance_mpesa_failure
        from school.models import PaymentGatewayTransaction, Payment, Invoice
        from school.services import FinanceService
        from school.mpesa import query_stk_status, MpesaError

        dry_run = options["dry_run"]
        configured_minutes = get_finance_operations_settings()["mpesa_reconciliation_minutes"]
        minutes = options["minutes"] if options["minutes"] is not None else configured_minutes
        threshold = timezone.now() - timedelta(minutes=minutes)

        pending_qs = PaymentGatewayTransaction.objects.filter(
            provider="mpesa",
            status="PENDING",
            created_at__lt=threshold,
        ).select_related("student", "invoice")

        total = pending_qs.count()
        self.stdout.write(
            f"  [{schema_label}] Found {total} PENDING M-Pesa "
            f"transaction(s) older than {minutes} min."
            + (" (DRY RUN)" if dry_run else "")
        )

        if total == 0:
            return

        reconciled_ok = 0
        reconciled_fail = 0
        skipped = 0

        for tx in pending_qs:
            checkout_id = tx.external_id
            self.stdout.write(
                f"    [{schema_label}] Querying Daraja: checkout_id={checkout_id} "
                f"amount={tx.amount} KES created={tx.created_at.isoformat()}"
            )

            try:
                result = query_stk_status(checkout_id)
            except MpesaError as exc:
                logger.warning(
                    "reconcile_mpesa_pending: [%s] Daraja query failed for %s: %s",
                    schema_label, checkout_id, exc,
                )
                self.stdout.write(
                    self.style.WARNING(
                        f"    [{schema_label}] SKIPPED (Daraja error): {exc}"
                    )
                )
                skipped += 1
                continue

            if result["success"]:
                mpesa_receipt = result.get("mpesa_receipt")
                daraja_amount = result.get("amount")
                payment_amount = daraja_amount if daraja_amount else tx.amount

                if not mpesa_receipt:
                    # Daraja confirmed the payment but returned no receipt number.
                    # Keep PENDING so the next reconciliation cycle retries —
                    # marking SUCCEEDED without being able to create a Payment
                    # would silently drop the payment recording step.
                    logger.warning(
                        "reconcile_mpesa_pending: [%s] Daraja reports SUCCESS for "
                        "%s but returned no MpesaReceiptNumber — keeping PENDING "
                        "to retry next cycle.",
                        schema_label, checkout_id,
                    )
                    self.stdout.write(
                        self.style.WARNING(
                            f"    [{schema_label}] SUCCESS from Daraja but no receipt "
                            f"number returned — keeping PENDING, will retry."
                        )
                    )
                    skipped += 1
                    continue

                self.stdout.write(
                    self.style.SUCCESS(
                        f"    [{schema_label}] SUCCEEDED — receipt={mpesa_receipt} "
                        f"amount={payment_amount}"
                    )
                )
                logger.info(
                    "reconcile_mpesa_pending: [%s] SUCCEEDED checkout_id=%s "
                    "receipt=%s amount=%s",
                    schema_label, checkout_id, mpesa_receipt, payment_amount,
                )

                if dry_run:
                    reconciled_ok += 1
                    continue

                try:
                    self._apply_success(
                        tx=tx,
                        mpesa_receipt=mpesa_receipt,
                        payment_amount=payment_amount,
                        checkout_id=checkout_id,
                        schema_label=schema_label,
                        FinanceService=FinanceService,
                        Payment=Payment,
                        Invoice=Invoice,
                    )
                    reconciled_ok += 1
                except Exception as save_exc:
                    logger.error(
                        "reconcile_mpesa_pending: [%s] failed to apply SUCCEEDED "
                        "for checkout_id=%s: %s",
                        schema_label, checkout_id, save_exc, exc_info=True,
                    )
                    self.stdout.write(
                        self.style.ERROR(
                            f"    [{schema_label}] ERROR saving SUCCEEDED: {save_exc}"
                        )
                    )
                    skipped += 1

            else:
                result_code = result.get("result_code")
                result_desc = result.get("result_desc", "")
                self.stdout.write(
                    self.style.WARNING(
                        f"    [{schema_label}] FAILED — code={result_code} "
                        f"desc={result_desc}"
                    )
                )
                logger.info(
                    "reconcile_mpesa_pending: [%s] FAILED checkout_id=%s "
                    "code=%s desc=%s",
                    schema_label, checkout_id, result_code, result_desc,
                )

                if dry_run:
                    reconciled_fail += 1
                    continue

                try:
                    tx.status = "FAILED"
                    tx.is_reconciled = True
                    tx.payload.update({
                        "result_code": result_code,
                        "result_desc": result_desc,
                        "reconciled_at": timezone.now().isoformat(),
                    })
                    tx.save(update_fields=["status", "is_reconciled", "payload", "updated_at"])
                    notify_finance_mpesa_failure(
                        tx,
                        result_code=result_code,
                        result_desc=result.get("friendly_message") or result_desc,
                        checkout_id=checkout_id,
                    )
                    reconciled_fail += 1
                except Exception as save_exc:
                    logger.error(
                        "reconcile_mpesa_pending: [%s] failed to save FAILED "
                        "state for checkout_id=%s: %s",
                        schema_label, checkout_id, save_exc, exc_info=True,
                    )
                    self.stdout.write(
                        self.style.ERROR(
                            f"    [{schema_label}] ERROR saving FAILED: {save_exc}"
                        )
                    )
                    skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"  [{schema_label}] Done. "
                f"SUCCEEDED={reconciled_ok} FAILED={reconciled_fail} SKIPPED={skipped}"
                + (" (DRY RUN)" if dry_run else "")
            )
        )
        logger.info(
            "reconcile_mpesa_pending [%s]: total=%d succeeded=%d failed=%d "
            "skipped=%d dry_run=%s",
            schema_label, total, reconciled_ok, reconciled_fail, skipped, dry_run,
        )

    def _apply_success(
        self, tx, mpesa_receipt, payment_amount, checkout_id, schema_label,
        FinanceService, Payment, Invoice
    ):
        """
        Atomically mark the gateway transaction SUCCEEDED and trigger the full
        payment recording path (Payment record, invoice allocation, wallet credit)
        — identical to the live MpesaStkCallbackView handler.
        """
        with db_transaction.atomic():
            tx.status = "SUCCEEDED"
            tx.is_reconciled = True
            tx.payload.update({
                "mpesa_receipt": mpesa_receipt,
                "reconciled_at": timezone.now().isoformat(),
            })
            tx.save(update_fields=["status", "is_reconciled", "payload", "updated_at"])

            if Payment.objects.filter(reference_number=mpesa_receipt).exists():
                self.stdout.write(
                    f"    [{schema_label}] Payment with receipt {mpesa_receipt} "
                    f"already exists — skipping creation."
                )
                return

            payment = FinanceService.record_payment(
                student=tx.student,
                amount=payment_amount,
                payment_method="M-Pesa",
                reference_number=mpesa_receipt,
                notes=(
                    f"M-Pesa STK Push (reconciled) | "
                    f"checkout_id={checkout_id}"
                ),
            )

            # Invoice allocation
            try:
                if tx.invoice_id and tx.student:
                    invoice = Invoice.objects.filter(
                        id=tx.invoice_id,
                        student=tx.student,
                        is_active=True,
                    ).exclude(status="VOID").first()
                    if invoice and invoice.balance_due > 0:
                        alloc_amt = min(payment.amount, invoice.balance_due)
                        FinanceService.allocate_payment(payment, invoice, alloc_amt)
                    else:
                        FinanceService.auto_allocate_payment(payment)
                elif tx.student:
                    FinanceService.auto_allocate_payment(payment)
            except Exception as alloc_exc:
                logger.warning(
                    "reconcile_mpesa_pending: [%s] payment %s created but "
                    "allocation failed: %s",
                    schema_label, payment.id, alloc_exc,
                )

        # Wallet credit is done outside the atomic block (non-fatal)
        try:
            from school.models import Wallet, FinanceAuditLog, UserProfile
            wallet_user = None
            if tx.student and tx.student.admission_number:
                try:
                    wallet_user = UserProfile.objects.get(
                        admission_number=tx.student.admission_number
                    ).user
                except UserProfile.DoesNotExist:
                    pass
            if wallet_user:
                wallet = Wallet.get_or_create_for_user(wallet_user)
                wallet.credit(
                    amount=payment.amount,
                    entry_type="DEPOSIT",
                    reference=mpesa_receipt,
                    description=f"M-Pesa STK reconciled: {checkout_id}",
                )
                FinanceAuditLog.log_action(
                    action="WALLET_CREDITED",
                    entity="PAYMENT",
                    entity_id=str(payment.id),
                    metadata={
                        "mpesa_receipt": mpesa_receipt,
                        "amount": str(payment.amount),
                        "reconciled": True,
                        "checkout_id": checkout_id,
                    },
                )
        except Exception as wallet_exc:
            logger.warning(
                "reconcile_mpesa_pending: [%s] wallet credit error (non-fatal): %s",
                schema_label, wallet_exc,
            )
