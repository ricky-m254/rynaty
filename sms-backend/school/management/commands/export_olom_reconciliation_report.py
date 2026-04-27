import csv
import json
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Sum
from django_tenants.utils import schema_context

from school.models import Payment, PaymentAllocation, SchoolProfile


class Command(BaseCommand):
    help = "Export a reconciliation report for the Olom tenant."

    def add_arguments(self, parser):
        parser.add_argument("--schema-name", default="olom")
        parser.add_argument(
            "--output",
            default="",
            help="Optional CSV output path. A companion _summary.csv file will be created alongside it.",
        )

    def handle(self, *args, **options):
        schema_name = options["schema_name"].strip()
        requested_output = (options.get("output") or "").strip()
        if requested_output:
            detail_path = Path(requested_output).resolve()
        else:
            stamp = datetime.now().date().isoformat()
            detail_path = (Path.cwd() / "artifacts" / "reports" / f"{schema_name}_reconciliation_report_{stamp}.csv").resolve()
        if detail_path.suffix.lower() != ".csv":
            raise CommandError("Output path must use a .csv extension.")
        summary_path = detail_path.with_name(f"{detail_path.stem}_summary.csv")
        detail_path.parent.mkdir(parents=True, exist_ok=True)

        with schema_context(schema_name):
            profile = SchoolProfile.objects.filter(is_active=True).order_by("id").first()
            school_name = getattr(profile, "school_name", "") or schema_name

            allocations = (
                PaymentAllocation.objects.select_related(
                    "payment__student",
                    "invoice__student",
                    "invoice__term__academic_year",
                )
                .order_by("payment__payment_date", "payment__reference_number", "id")
            )
            if not allocations.exists():
                raise CommandError(f"No payment allocations found in schema '{schema_name}'.")

            self._write_detail_csv(detail_path, schema_name, school_name, allocations)
            self._write_summary_csv(summary_path)

            payload = {
                "schema": schema_name,
                "school_name": school_name,
                "detail_report": str(detail_path),
                "summary_report": str(summary_path),
                "allocation_rows": allocations.count(),
                "payments": Payment.objects.count(),
                "allocated_total": str(
                    PaymentAllocation.objects.aggregate(total=Sum("amount_allocated"))["total"] or 0
                ),
            }
        self.stdout.write(json.dumps(payload, indent=2))

    def _write_detail_csv(self, detail_path: Path, schema_name: str, school_name: str, allocations) -> None:
        headers = [
            "schema_name",
            "school_name",
            "student_admission_number",
            "student_name",
            "payment_reference_number",
            "payment_receipt_number",
            "payment_date",
            "payment_amount",
            "allocated_amount",
            "payment_method",
            "source_workbook",
            "source_sheet",
            "legacy_fees_id",
            "legacy_receipt",
            "legacy_mode",
            "legacy_source",
            "invoice_number",
            "invoice_type",
            "invoice_status",
            "academic_year",
            "term",
            "invoice_date",
            "invoice_due_date",
            "invoice_total_amount",
        ]
        with detail_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            for allocation in allocations.iterator(chunk_size=500):
                payment = allocation.payment
                invoice = allocation.invoice
                student = payment.student
                note = self._parse_note(payment.notes)
                writer.writerow(
                    {
                        "schema_name": schema_name,
                        "school_name": school_name,
                        "student_admission_number": student.admission_number,
                        "student_name": f"{student.first_name} {student.last_name}".strip(),
                        "payment_reference_number": payment.reference_number,
                        "payment_receipt_number": payment.receipt_number or "",
                        "payment_date": payment.payment_date.isoformat(sep=" "),
                        "payment_amount": payment.amount,
                        "allocated_amount": allocation.amount_allocated,
                        "payment_method": payment.payment_method,
                        "source_workbook": note.get("source_workbook", ""),
                        "source_sheet": note.get("source_sheet", ""),
                        "legacy_fees_id": note.get("legacy_fees_id", ""),
                        "legacy_receipt": note.get("legacy_receipt", ""),
                        "legacy_mode": note.get("legacy_mode", ""),
                        "legacy_source": note.get("legacy_source", ""),
                        "invoice_number": invoice.invoice_number or "",
                        "invoice_type": self._invoice_type(invoice.invoice_number or ""),
                        "invoice_status": invoice.status,
                        "academic_year": invoice.term.academic_year.name,
                        "term": invoice.term.name,
                        "invoice_date": invoice.invoice_date.isoformat(),
                        "invoice_due_date": invoice.due_date.isoformat(),
                        "invoice_total_amount": invoice.total_amount,
                    }
                )

    def _write_summary_csv(self, summary_path: Path) -> None:
        headers = [
            "scope",
            "group_key",
            "payments_count",
            "invoices_count",
            "payments_total",
            "allocated_total",
        ]
        payment_total = Payment.objects.aggregate(total=Sum("amount"))["total"] or 0
        allocated_total = PaymentAllocation.objects.aggregate(total=Sum("amount_allocated"))["total"] or 0
        invoice_type_rows = (
            PaymentAllocation.objects.values("invoice__invoice_number")
            .annotate(
                payments_count=Count("payment_id", distinct=True),
                invoices_count=Count("invoice_id", distinct=True),
                allocated_total=Sum("amount_allocated"),
            )
        )
        type_summary: dict[str, dict] = {}
        for row in invoice_type_rows:
            key = self._invoice_type(row["invoice__invoice_number"] or "")
            bucket = type_summary.setdefault(
                key,
                {
                    "payments_count": 0,
                    "invoices_count": set(),
                    "allocated_total": 0,
                },
            )
            bucket["payments_count"] += row["payments_count"]
            bucket["allocated_total"] += row["allocated_total"] or 0
            bucket["invoices_count"].add(row["invoice__invoice_number"] or "")

        year_summary = (
            PaymentAllocation.objects.values("invoice__term__academic_year__name")
            .annotate(
                payments_count=Count("payment_id", distinct=True),
                invoices_count=Count("invoice_id", distinct=True),
                allocated_total=Sum("amount_allocated"),
            )
            .order_by("invoice__term__academic_year__name")
        )

        with summary_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            writer.writerow(
                {
                    "scope": "overall",
                    "group_key": "all",
                    "payments_count": Payment.objects.count(),
                    "invoices_count": PaymentAllocation.objects.values("invoice_id").distinct().count(),
                    "payments_total": payment_total,
                    "allocated_total": allocated_total,
                }
            )
            for invoice_type in sorted(type_summary):
                bucket = type_summary[invoice_type]
                writer.writerow(
                    {
                        "scope": "invoice_type",
                        "group_key": invoice_type,
                        "payments_count": bucket["payments_count"],
                        "invoices_count": len(bucket["invoices_count"]),
                        "payments_total": "",
                        "allocated_total": bucket["allocated_total"],
                    }
                )
            for row in year_summary:
                writer.writerow(
                    {
                        "scope": "academic_year",
                        "group_key": row["invoice__term__academic_year__name"],
                        "payments_count": row["payments_count"],
                        "invoices_count": row["invoices_count"],
                        "payments_total": "",
                        "allocated_total": row["allocated_total"] or 0,
                    }
                )

    def _parse_note(self, note: str) -> dict:
        if not note:
            return {}
        try:
            value = json.loads(note)
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}

    def _invoice_type(self, invoice_number: str) -> str:
        if invoice_number.startswith("LEGACY-STMT-"):
            return "statement"
        if invoice_number.startswith("LEGACY-PAY-"):
            return "placeholder"
        return "other"
