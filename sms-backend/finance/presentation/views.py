from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import HttpResponse

from finance.application.report_queries import (
    get_arrears_by_term_payload,
    get_arrears_payload,
    get_budget_variance_payload,
    get_cashbook_summary_payload,
    get_class_balances_payload,
    get_financial_summary_payload,
    get_installment_aging_payload,
    get_overdue_accounts_payload,
    get_receivables_aging_payload,
    get_vote_head_allocation_payload,
    get_vote_head_budget_payload,
)
from finance.application.reference_queries import (
    get_enrollment_reference_queryset,
    get_student_reference_queryset,
    list_class_references,
    paginate_queryset,
)
from finance.application.billing_setup import (
    assign_fee_structure_to_class,
    assign_optional_charge_to_class,
)
from finance.application.receivables import (
    get_student_ledger_payload,
    resolve_tenant_pdf_meta,
    safe_cell,
)
from finance.presentation.serializers import (
    FinanceEnrollmentRefSerializer,
    FinanceStudentRefSerializer,
)
from school.models import Payment, VoteHeadPaymentAllocation
from school.payment_receipts import build_payment_receipt_payload
from school.permissions import HasModuleAccess, IsAccountant
from school.views import (
    FinanceOverdueAccountsCsvExportView as SchoolFinanceOverdueAccountsCsvExportView,
    FinanceReceivablesAgingCsvExportView as SchoolFinanceReceivablesAgingCsvExportView,
    FinanceStudentDetailView as SchoolFinanceStudentDetailView,
    FinanceSummaryCsvExportView as SchoolFinanceSummaryCsvExportView,
    FinanceSummaryPdfExportView as SchoolFinanceSummaryPdfExportView,
)

import logging

logger = logging.getLogger(__name__)



class FinanceStudentRefView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        queryset = get_student_reference_queryset(
            is_active=request.query_params.get("active"),
            class_id=request.query_params.get("class_id"),
            term_id=request.query_params.get("term_id"),
            order_by=request.query_params.get("order_by", "admission_number"),
            order_dir=request.query_params.get("order_dir", "asc"),
        )

        try:
            page = paginate_queryset(
                queryset,
                limit=request.query_params.get("limit"),
                offset=request.query_params.get("offset"),
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if page is not None:
            serializer = FinanceStudentRefSerializer(page.results, many=True)
            return Response(
                {
                    "count": page.count,
                    "next_offset": page.next_offset,
                    "results": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        serializer = FinanceStudentRefSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class FinanceEnrollmentRefView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        queryset = get_enrollment_reference_queryset(
            is_active=request.query_params.get("active"),
            class_id=request.query_params.get("class_id"),
            term_id=request.query_params.get("term_id"),
            student_id=request.query_params.get("student_id"),
            order_by=request.query_params.get("order_by", "id"),
            order_dir=request.query_params.get("order_dir", "asc"),
        )

        try:
            page = paginate_queryset(
                queryset,
                limit=request.query_params.get("limit"),
                offset=request.query_params.get("offset"),
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if page is not None:
            serializer = FinanceEnrollmentRefSerializer(page.results, many=True)
            return Response(
                {
                    "count": page.count,
                    "next_offset": page.next_offset,
                    "results": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        serializer = FinanceEnrollmentRefSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class FinanceClassRefView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        return Response(
            list_class_references(term_id=request.query_params.get("term_id")),
            status=status.HTTP_200_OK,
        )


class FinancialSummaryView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        return Response(get_financial_summary_payload(), status=status.HTTP_200_OK)


class FinanceReceivablesAgingView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        return Response(get_receivables_aging_payload(), status=status.HTTP_200_OK)


class FinanceOverdueAccountsView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        return Response(
            get_overdue_accounts_payload(search=request.query_params.get("search") or ""),
            status=status.HTTP_200_OK,
        )


class FinanceInstallmentAgingView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        return Response(get_installment_aging_payload(), status=status.HTTP_200_OK)


class CashbookSummaryView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        return Response(get_cashbook_summary_payload(), status=status.HTTP_200_OK)


class FinanceVoteHeadAllocationReportView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        return Response(
            get_vote_head_allocation_payload(
                date_from=request.query_params.get("date_from"),
                date_to=request.query_params.get("date_to"),
            ),
            status=status.HTTP_200_OK,
        )


class FinanceArrearsView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        return Response(
            get_arrears_payload(
                term_id=request.query_params.get("term"),
                group_by=request.query_params.get("group_by", "student"),
            ),
            status=status.HTTP_200_OK,
        )


class FinanceClassBalancesReportView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        return Response(
            get_class_balances_payload(term_id=request.query_params.get("term")),
            status=status.HTTP_200_OK,
        )


class FinanceArrearsByTermReportView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        return Response(get_arrears_by_term_payload(), status=status.HTTP_200_OK)


class FinanceBudgetVarianceReportView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        return Response(
            get_budget_variance_payload(
                academic_year=request.query_params.get("academic_year"),
                term=request.query_params.get("term"),
            ),
            status=status.HTTP_200_OK,
        )


class FinanceVoteHeadBudgetReportView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        return Response(
            get_vote_head_budget_payload(
                date_from=request.query_params.get("date_from"),
                date_to=request.query_params.get("date_to"),
            ),
            status=status.HTTP_200_OK,
        )


class BulkFeeAssignByClassView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def post(self, request):
        try:
            payload = assign_fee_structure_to_class(
                class_id=request.data.get("class_id"),
                fee_structure_id=request.data.get("fee_structure_id"),
                term_id=request.data.get("term_id"),
                discount_amount=request.data.get("discount_amount", 0),
            )
            return Response(payload, status=status.HTTP_200_OK)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except LookupError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)


class BulkOptionalChargeByClassView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def post(self, request):
        try:
            payload = assign_optional_charge_to_class(
                class_id=request.data.get("class_id"),
                optional_charge_id=request.data.get("optional_charge_id"),
                term_id=request.data.get("term_id"),
            )
            return Response(payload, status=status.HTTP_200_OK)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except LookupError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)


class FinanceReceiptPdfView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request, pk):
        from io import BytesIO

        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        try:
            payment = Payment.objects.select_related("student").prefetch_related(
                "allocations__invoice",
                "vote_head_allocations__vote_head",
            ).get(pk=pk)
        except Payment.DoesNotExist:
            return Response({"detail": "Payment not found."}, status=status.HTTP_404_NOT_FOUND)

        payload = build_payment_receipt_payload(payment)
        tenant_meta = resolve_tenant_pdf_meta(request)
        buffer = BytesIO()
        document = SimpleDocTemplate(buffer, pagesize=A4, title=f"Receipt {payload['receipt_no']}")
        styles = getSampleStyleSheet()
        story = []

        if tenant_meta.get("logo_path"):
            try:
                story.append(Image(tenant_meta["logo_path"], width=60, height=60))
            except Exception:
                logger.warning("Caught and logged", exc_info=True)

        school_name = tenant_meta.get("school_name", "School")
        story.append(Paragraph(f"<b>{safe_cell(school_name)}</b>", styles["Title"]))
        if tenant_meta.get("address"):
            story.append(Paragraph(safe_cell(tenant_meta["address"]), styles["Normal"]))
        if tenant_meta.get("phone"):
            story.append(Paragraph(f"Tel: {safe_cell(tenant_meta['phone'])}", styles["Normal"]))
        story.append(Spacer(1, 18))

        story.append(Paragraph("<b>OFFICIAL RECEIPT</b>", styles["Heading2"]))
        story.append(Spacer(1, 8))

        details = [
            ["Receipt No.", safe_cell(payload["receipt_no"])],
            ["Date", safe_cell(payload["date"] or "")],
            ["Student", safe_cell(payload["student"])],
            ["Admission No.", safe_cell(payload["admission_number"])],
            ["Amount", f"KES {payload['amount']:,.2f}"],
            ["Method", safe_cell(payload["method"])],
            ["Transaction Code", safe_cell(payload["transaction_code"])],
        ]

        vote_allocations = payload["vote_head_allocations"]
        if vote_allocations:
            story.append(Spacer(1, 8))
            allocation_rows = [["Vote Head", "Amount"]]
            for allocation in vote_allocations:
                allocation_rows.append([
                    safe_cell(allocation["vote_head"]),
                    f"KES {allocation['amount']:,.2f}",
                ])
            allocation_table = Table(allocation_rows, colWidths=[200, 120])
            allocation_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ]
                )
            )
            details.append(["Vote Head Breakdown", ""])
            table = Table(details, colWidths=[160, 280])
            table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )
            story.append(table)
            story.append(Spacer(1, 6))
            story.append(allocation_table)
        else:
            table = Table(details, colWidths=[160, 280])
            table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )
            story.append(table)

        story.append(Spacer(1, 24))
        story.append(Paragraph("____________________________", styles["Normal"]))
        story.append(Paragraph("Authorised Signature", styles["Normal"]))
        story.append(Spacer(1, 8))
        story.append(Paragraph("<i>This is a computer-generated receipt.</i>", styles["Italic"]))

        document.build(story)
        pdf_data = buffer.getvalue()
        buffer.close()

        response = HttpResponse(pdf_data, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="receipt_{payload["receipt_no"]}.pdf"'
        return response


class FinanceStudentLedgerView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request, student_id):
        try:
            payload = get_student_ledger_payload(
                student_id,
                term_id=request.query_params.get("term"),
                date_from=request.query_params.get("date_from"),
                date_to=request.query_params.get("date_to"),
            )
        except LookupError:
            return Response({"detail": "Student not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(payload, status=status.HTTP_200_OK)


class FinanceReceivablesAgingCsvExportView(SchoolFinanceReceivablesAgingCsvExportView):
    pass


class FinanceOverdueAccountsCsvExportView(SchoolFinanceOverdueAccountsCsvExportView):
    pass


class FinanceSummaryCsvExportView(SchoolFinanceSummaryCsvExportView):
    pass


class FinanceSummaryPdfExportView(SchoolFinanceSummaryPdfExportView):
    pass


class FinanceStudentDetailView(SchoolFinanceStudentDetailView):
    pass
