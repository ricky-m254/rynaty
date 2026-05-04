from datetime import datetime

from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from academics.models import Term
from finance.application.billing_setup import (
    create_fee_assignment,
    get_fee_assignment_queryset,
    get_fee_structure_queryset,
    get_optional_charge_queryset,
    get_student_optional_charge_queryset,
)
from finance.application.cashbook import (
    get_cashbook_queryset,
    recompute_running_balances,
)
from finance.application.master_data import (
    get_balance_carry_forward_queryset,
    get_vote_head_queryset,
    seed_default_vote_heads,
)
from finance.application.receivables import (
    approval_threshold,
    get_invoice_adjustment_queryset,
    get_invoice_queryset,
    get_invoice_writeoff_request_queryset,
    get_payment_queryset,
    get_payment_reversal_request_queryset,
    is_admin_like,
)
from school.payment_receipts import build_payment_receipt_payload
from finance.presentation.serializers import (
    BalanceCarryForwardSerializer,
    CashbookEntrySerializer,
    FeeAssignmentSerializer,
    FeeStructureSerializer,
    InvoiceAdjustmentSerializer,
    InvoiceInstallmentPlanSerializer,
    InvoiceSerializer,
    InvoiceWriteOffRequestSerializer,
    OptionalChargeSerializer,
    PaymentReversalRequestSerializer,
    PaymentSerializer,
    StudentOptionalChargeSerializer,
    VoteHeadSerializer,
)
from school.models import Invoice, InvoiceInstallment
from school.pagination import FinanceResultsPagination
from school.permissions import HasModuleAccess, IsAccountant, IsSchoolAdmin, request_has_approval_category
from school.services import FinanceService


def _approval_forbidden(category_key: str) -> Response:
    label_map = {
        "adjustments": "adjustments",
        "reversals": "reversals",
        "writeoffs": "write-offs",
    }
    label = label_map.get(category_key, category_key.replace("_", " "))
    return Response(
        {"error": f"You are not allowed to approve or reject {label}."},
        status=status.HTTP_403_FORBIDDEN,
    )


class VoteHeadViewSet(viewsets.ModelViewSet):
    serializer_class = VoteHeadSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get_queryset(self):
        return get_vote_head_queryset(
            active_only=self.request.query_params.get("active_only"),
        )

    def perform_create(self, serializer):
        serializer.save()

    @action(detail=False, methods=["post"], url_path="seed-defaults")
    def seed_defaults(self, request):
        created = seed_default_vote_heads()
        return Response(
            {
                "seeded": created,
                "message": f"{len(created)} vote heads seeded.",
            }
        )


class BalanceCarryForwardViewSet(viewsets.ModelViewSet):
    serializer_class = BalanceCarryForwardSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get_queryset(self):
        return get_balance_carry_forward_queryset(
            student_id=self.request.query_params.get("student"),
            from_term=self.request.query_params.get("from_term"),
            to_term=self.request.query_params.get("to_term"),
        )

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class CashbookEntryViewSet(viewsets.ModelViewSet):
    serializer_class = CashbookEntrySerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get_queryset(self):
        return get_cashbook_queryset(
            book_type=self.request.query_params.get("book_type"),
            date_from=self.request.query_params.get("date_from"),
            date_to=self.request.query_params.get("date_to"),
        )

    def perform_create(self, serializer):
        entry = serializer.save()
        recompute_running_balances(entry.book_type)
        entry.refresh_from_db()

    def perform_update(self, serializer):
        entry = serializer.save()
        recompute_running_balances(entry.book_type)

    def perform_destroy(self, instance):
        book_type = instance.book_type
        instance.delete()
        recompute_running_balances(book_type)


class FeeStructureViewSet(viewsets.ModelViewSet):
    serializer_class = FeeStructureSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        return get_fee_structure_queryset(
            search=self.request.query_params.get("search"),
            category=self.request.query_params.get("category"),
            is_active=self.request.query_params.get("is_active"),
        )

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()


class FeeAssignmentViewSet(viewsets.ModelViewSet):
    serializer_class = FeeAssignmentSerializer
    permission_classes = [IsSchoolAdmin | IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        return get_fee_assignment_queryset(
            search=self.request.query_params.get("search"),
            student=self.request.query_params.get("student"),
            fee_structure=self.request.query_params.get("fee_structure"),
            is_active=self.request.query_params.get("is_active"),
        )

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()

    def perform_create(self, serializer):
        try:
            serializer.instance = create_fee_assignment(serializer.validated_data, self.request.user)
        except Exception as exc:
            raise ValidationError(str(exc))


class OptionalChargeViewSet(viewsets.ModelViewSet):
    serializer_class = OptionalChargeSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        return get_optional_charge_queryset(
            category=self.request.query_params.get("category"),
            is_active=self.request.query_params.get("is_active"),
        )


class StudentOptionalChargeViewSet(viewsets.ModelViewSet):
    serializer_class = StudentOptionalChargeSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        return get_student_optional_charge_queryset(
            student=self.request.query_params.get("student"),
            optional_charge=self.request.query_params.get("optional_charge"),
            is_paid=self.request.query_params.get("is_paid"),
        )


class InvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    http_method_names = ["get", "post", "delete", "head", "options"]
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        return get_invoice_queryset(
            search=self.request.query_params.get("search"),
            status_param=self.request.query_params.get("status"),
            student=self.request.query_params.get("student"),
            date_from=self.request.query_params.get("date_from"),
            date_to=self.request.query_params.get("date_to"),
        )

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        student = serializer.validated_data.get("student")
        term = serializer.validated_data.get("term")
        line_items = serializer.validated_data.get("line_items")
        due_date = serializer.validated_data.get("due_date")

        missing_fields = [
            field
            for field, value in {
                "student": student,
                "term": term,
                "due_date": due_date,
                "line_items": line_items,
            }.items()
            if not value
        ]
        if missing_fields:
            return Response(
                {
                    "error": "Required fields are missing.",
                    "missing": missing_fields,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            invoice = FinanceService.create_invoice(
                student=student,
                term=term,
                line_items_data=line_items,
                due_date=due_date,
                status=serializer.validated_data.get("status"),
                is_active=serializer.validated_data.get("is_active"),
            )
            response_serializer = self.get_serializer(invoice)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="status")
    def update_status(self, request, pk=None):
        invoice = self.get_object()
        target = request.data.get("status")
        if not target:
            return Response({"error": "status is required"}, status=status.HTTP_400_BAD_REQUEST)
        target = str(target).upper()

        allowed = {
            "DRAFT": {"ISSUED", "VOID", "CONFIRMED"},
            "CONFIRMED": {"ISSUED", "VOID"},
            "ISSUED": {"PARTIALLY_PAID", "PAID", "OVERDUE", "VOID"},
            "PARTIALLY_PAID": {"PAID", "OVERDUE", "VOID"},
            "OVERDUE": {"PARTIALLY_PAID", "PAID", "VOID"},
            "PAID": {"VOID"},
            "VOID": set(),
        }

        if invoice.status == "PAID" and target == "VOID" and not is_admin_like(request.user):
            return Response({"error": "Only admin can void paid invoices."}, status=status.HTTP_403_FORBIDDEN)
        if target not in allowed.get(invoice.status, set()):
            return Response(
                {"error": f"Invalid transition from {invoice.status} to {target}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invoice.status = target
        invoice.save(update_fields=["status"])
        return Response(self.get_serializer(invoice).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="issue")
    def issue(self, request, pk=None):
        invoice = self.get_object()
        if invoice.status not in {"DRAFT", "CONFIRMED"}:
            return Response(
                {"error": "Only draft/confirmed invoices can be issued."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        invoice.status = "ISSUED"
        invoice.save(update_fields=["status"])
        return Response(self.get_serializer(invoice).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="generate-batch")
    def generate_batch(self, request):
        term_id = request.data.get("term")
        due_date = request.data.get("due_date")
        class_id = request.data.get("class_id")
        grade_level_id = request.data.get("grade_level_id")
        issue_immediately = bool(request.data.get("issue_immediately", True))

        if not term_id or not due_date:
            return Response({"error": "term and due_date are required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            due_date_value = datetime.fromisoformat(str(due_date)).date()
        except ValueError:
            return Response({"error": "Invalid due_date"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            term = Invoice._meta.get_field("term").remote_field.model.objects.get(id=term_id)
            result = FinanceService.generate_invoices_from_assignments(
                term=term,
                due_date=due_date_value,
                class_id=class_id,
                grade_level_id=grade_level_id,
                issue_immediately=issue_immediately,
            )
            return Response(result, status=status.HTTP_200_OK)
        except Term.DoesNotExist:
            return Response({"error": "Invalid term"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get", "post"], url_path="installments")
    def create_installment_plan(self, request, pk=None):
        invoice = self.get_object()
        if request.method.lower() == "get":
            plan = getattr(invoice, "installment_plan", None)
            if not plan:
                return Response(
                    {"invoice": invoice.id, "installment_count": 0, "installments": []},
                    status=status.HTTP_200_OK,
                )
            serializer = InvoiceInstallmentPlanSerializer(plan)
            return Response(serializer.data, status=status.HTTP_200_OK)

        installment_count = int(request.data.get("installment_count", 0))
        due_dates = request.data.get("due_dates") or []
        if not installment_count or not isinstance(due_dates, list):
            return Response(
                {"error": "installment_count and due_dates[] are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            plan = FinanceService.create_installment_plan(
                invoice=invoice,
                installment_count=installment_count,
                due_dates=due_dates,
                created_by=request.user,
            )
            serializer = InvoiceInstallmentPlanSerializer(plan)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="send-reminder")
    def send_reminder(self, request, pk=None):
        invoice = self.get_object()
        channel = str(request.data.get("channel") or "EMAIL").upper()
        recipient = request.data.get("recipient")
        if channel not in {"EMAIL", "SMS", "INAPP"}:
            return Response({"error": "Unsupported channel"}, status=status.HTTP_400_BAD_REQUEST)
        result = FinanceService.send_invoice_reminder(
            invoice=invoice,
            channel=channel,
            recipient_override=recipient,
        )
        if result.get("error"):
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_200_OK)


class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    http_method_names = ["get", "post", "delete", "head", "options"]
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        return get_payment_queryset(
            search=self.request.query_params.get("search"),
            student=self.request.query_params.get("student"),
            payment_method=self.request.query_params.get("payment_method"),
            allocation_status=self.request.query_params.get("allocation_status"),
            date_from=self.request.query_params.get("date_from"),
            date_to=self.request.query_params.get("date_to"),
        )

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            payment = FinanceService.record_payment(
                student=serializer.validated_data["student"],
                amount=serializer.validated_data["amount"],
                payment_method=serializer.validated_data["payment_method"],
                reference_number=serializer.validated_data["reference_number"],
                notes=serializer.validated_data.get("notes", ""),
            )
            response_status = status.HTTP_201_CREATED if getattr(payment, "_was_created", True) else status.HTTP_200_OK
            response_serializer = self.get_serializer(payment)
            return Response(response_serializer.data, status=response_status)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def allocate(self, request, pk=None):
        payment = self.get_object()
        invoice_id = request.data.get("invoice_id")
        installment_id = request.data.get("installment_id")
        amount = request.data.get("amount")
        if not invoice_id or amount is None:
            return Response(
                {"error": "invoice_id and amount are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            invoice = Invoice.objects.get(id=invoice_id, is_active=True)
            if installment_id:
                installment = InvoiceInstallment.objects.select_related("plan__invoice").get(
                    id=installment_id,
                    plan__invoice_id=invoice.id,
                )
                FinanceService.allocate_payment_to_installment(payment, installment, amount)
            else:
                FinanceService.allocate_payment(payment, invoice, amount)

            return Response({"message": "Allocation successful"}, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="auto-allocate")
    def auto_allocate(self, request, pk=None):
        payment = self.get_object()
        try:
            result = FinanceService.auto_allocate_payment(payment)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"], url_path="receipt")
    def receipt(self, request, pk=None):
        payment = self.get_object()
        receipt = build_payment_receipt_payload(payment, request=request)
        if request.query_params.get("format") == "json":
            return Response(receipt)

        receipt_no = receipt["receipt_no"] or payment.id
        lines = [
            f"Receipt: {receipt['receipt_no'] or 'N/A'}",
            f"Transaction Code: {receipt['transaction_code'] or 'N/A'}",
            f"Student: {receipt['student']}",
            f"Admission No: {receipt['admission_number']}",
            f"Amount: {receipt['amount']}",
            f"Method: {receipt['method']}",
            f"Date: {receipt['date']}",
            f"Status: {receipt['status']}",
        ]
        content = "\n".join(lines)
        response = HttpResponse(content, content_type="text/plain")
        response["Content-Disposition"] = f'attachment; filename="receipt_{receipt_no}.txt"'
        return response

    @action(detail=True, methods=["post"], url_path="reversal-request")
    def reversal_request(self, request, pk=None):
        payment = self.get_object()
        reason = (request.data.get("reason") or "").strip()
        if not reason:
            return Response({"error": "reason is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            reversal = FinanceService.request_payment_reversal(
                payment=payment,
                reason=reason,
                requested_by=request.user,
            )
            return Response(PaymentReversalRequestSerializer(reversal).data, status=status.HTTP_201_CREATED)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="reverse-approve")
    def reverse_approve(self, request, pk=None):
        if not request_has_approval_category(request, "reversals"):
            return _approval_forbidden("reversals")
        payment = self.get_object()
        reversal = payment.reversal_requests.filter(status="PENDING").order_by("-requested_at").first()
        if not reversal:
            return Response({"error": "No pending reversal request found."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            FinanceService.approve_payment_reversal(
                reversal_request=reversal,
                reviewed_by=request.user,
                review_notes=request.data.get("review_notes", ""),
            )
            return Response({"message": "Payment reversed successfully."}, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="reverse-reject")
    def reverse_reject(self, request, pk=None):
        if not request_has_approval_category(request, "reversals"):
            return _approval_forbidden("reversals")
        payment = self.get_object()
        reversal = payment.reversal_requests.filter(status="PENDING").order_by("-requested_at").first()
        if not reversal:
            return Response({"error": "No pending reversal request found."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            FinanceService.reject_payment_reversal(
                reversal_request=reversal,
                reviewed_by=request.user,
                review_notes=request.data.get("review_notes", ""),
            )
            return Response({"message": "Reversal request rejected."}, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class InvoiceAdjustmentViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceAdjustmentSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    http_method_names = ["get", "post", "head", "options"]
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        return get_invoice_adjustment_queryset(
            search=self.request.query_params.get("search"),
            invoice=self.request.query_params.get("invoice"),
            min_amount=self.request.query_params.get("min_amount"),
            max_amount=self.request.query_params.get("max_amount"),
            date_from=self.request.query_params.get("date_from"),
            date_to=self.request.query_params.get("date_to"),
            status_filter=self.request.query_params.get("status"),
        )

    def perform_create(self, serializer):
        try:
            amount = serializer.validated_data["amount"]
            auto_approve = is_admin_like(self.request.user) and amount < approval_threshold()
            adjustment = FinanceService.create_adjustment(
                invoice=serializer.validated_data["invoice"],
                amount=amount,
                reason=serializer.validated_data["reason"],
                user=self.request.user,
                adjustment_type=serializer.validated_data.get("adjustment_type", "CREDIT"),
                auto_approve=auto_approve,
            )
            serializer.instance = adjustment
        except Exception as exc:
            raise ValidationError(str(exc))

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        if not request_has_approval_category(request, "adjustments"):
            return _approval_forbidden("adjustments")
        adjustment = self.get_object()
        try:
            review_notes = request.data.get("review_notes") or ""
            adjustment = FinanceService.approve_adjustment(
                adjustment,
                reviewer=request.user,
                review_notes=review_notes,
            )
            return Response(self.get_serializer(adjustment).data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        if not request_has_approval_category(request, "adjustments"):
            return _approval_forbidden("adjustments")
        adjustment = self.get_object()
        try:
            review_notes = request.data.get("review_notes") or ""
            adjustment = FinanceService.reject_adjustment(
                adjustment,
                reviewer=request.user,
                review_notes=review_notes,
            )
            return Response(self.get_serializer(adjustment).data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="clarify")
    def clarify(self, request, pk=None):
        if not request_has_approval_category(request, "adjustments"):
            return _approval_forbidden("adjustments")
        adjustment = self.get_object()
        try:
            review_notes = request.data.get("review_notes") or ""
            adjustment = FinanceService.request_adjustment_clarification(
                adjustment,
                reviewer=request.user,
                review_notes=review_notes,
            )
            return Response(self.get_serializer(adjustment).data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class PaymentReversalRequestViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentReversalRequestSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    http_method_names = ["get", "post", "head", "options"]
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        return get_payment_reversal_request_queryset(
            status_param=self.request.query_params.get("status"),
            payment_id=self.request.query_params.get("payment"),
            search=self.request.query_params.get("search"),
        )

    def perform_create(self, serializer):
        try:
            reversal = FinanceService.request_payment_reversal(
                payment=serializer.validated_data["payment"],
                reason=serializer.validated_data["reason"],
                requested_by=self.request.user,
            )
            serializer.instance = reversal
        except Exception as exc:
            raise ValidationError(str(exc))

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        if not request_has_approval_category(request, "reversals"):
            return _approval_forbidden("reversals")
        reversal = self.get_object()
        try:
            review_notes = request.data.get("review_notes") or ""
            reversal = FinanceService.approve_payment_reversal(
                reversal_request=reversal,
                reviewed_by=request.user,
                review_notes=review_notes,
            )
            return Response(self.get_serializer(reversal).data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        if not request_has_approval_category(request, "reversals"):
            return _approval_forbidden("reversals")
        reversal = self.get_object()
        try:
            review_notes = request.data.get("review_notes") or ""
            reversal = FinanceService.reject_payment_reversal(
                reversal_request=reversal,
                reviewed_by=request.user,
                review_notes=review_notes,
            )
            return Response(self.get_serializer(reversal).data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="clarify")
    def clarify(self, request, pk=None):
        if not request_has_approval_category(request, "reversals"):
            return _approval_forbidden("reversals")
        reversal = self.get_object()
        try:
            review_notes = request.data.get("review_notes") or ""
            reversal = FinanceService.request_payment_reversal_clarification(
                reversal_request=reversal,
                reviewed_by=request.user,
                review_notes=review_notes,
            )
            return Response(self.get_serializer(reversal).data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class InvoiceWriteOffRequestViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceWriteOffRequestSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    http_method_names = ["get", "post", "head", "options"]
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        return get_invoice_writeoff_request_queryset(
            status_param=self.request.query_params.get("status"),
            invoice=self.request.query_params.get("invoice"),
            search=self.request.query_params.get("search"),
        )

    def perform_create(self, serializer):
        try:
            writeoff = FinanceService.create_writeoff_request(
                invoice=serializer.validated_data["invoice"],
                amount=serializer.validated_data["amount"],
                reason=serializer.validated_data["reason"],
                requested_by=self.request.user,
            )
            serializer.instance = writeoff
        except Exception as exc:
            raise ValidationError(str(exc))

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        if not request_has_approval_category(request, "writeoffs"):
            return _approval_forbidden("writeoffs")
        writeoff = self.get_object()
        try:
            review_notes = request.data.get("review_notes") or ""
            writeoff = FinanceService.approve_writeoff_request(
                writeoff=writeoff,
                reviewer=request.user,
                review_notes=review_notes,
            )
            return Response(self.get_serializer(writeoff).data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        if not request_has_approval_category(request, "writeoffs"):
            return _approval_forbidden("writeoffs")
        writeoff = self.get_object()
        try:
            review_notes = request.data.get("review_notes") or ""
            writeoff = FinanceService.reject_writeoff_request(
                writeoff=writeoff,
                reviewer=request.user,
                review_notes=review_notes,
            )
            return Response(self.get_serializer(writeoff).data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="clarify")
    def clarify(self, request, pk=None):
        if not request_has_approval_category(request, "writeoffs"):
            return _approval_forbidden("writeoffs")
        writeoff = self.get_object()
        try:
            review_notes = request.data.get("review_notes") or ""
            writeoff = FinanceService.request_writeoff_clarification(
                writeoff=writeoff,
                reviewer=request.user,
                review_notes=review_notes,
            )
            return Response(self.get_serializer(writeoff).data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
