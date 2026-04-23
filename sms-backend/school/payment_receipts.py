from decimal import Decimal


PAYMENT_RECEIPT_BASE_PATH = "/api/finance/payments"


def payment_display_name(student) -> str:
    if not student:
        return ""
    first_name = (getattr(student, "first_name", "") or "").strip()
    last_name = (getattr(student, "last_name", "") or "").strip()
    full_name = f"{first_name} {last_name}".strip()
    return full_name or str(student)


def payment_receipt_number(payment) -> str:
    receipt_number = (getattr(payment, "receipt_number", "") or "").strip()
    if receipt_number:
        return receipt_number
    payment_id = getattr(payment, "pk", None)
    return f"RCT-{payment_id:06d}" if payment_id else ""


def payment_transaction_code(payment) -> str:
    reference_number = (getattr(payment, "reference_number", "") or "").strip()
    return reference_number or payment_receipt_number(payment)


def payment_vote_head_summary(payment) -> str:
    vote_head_names = []
    try:
        allocations = payment.vote_head_allocations.select_related("vote_head").order_by("id")
    except Exception:
        allocations = []

    for allocation in allocations:
        vote_head = getattr(allocation, "vote_head", None)
        vote_head_name = (getattr(vote_head, "name", "") or "").strip()
        if vote_head_name and vote_head_name not in vote_head_names:
            vote_head_names.append(vote_head_name)

    if not vote_head_names:
        return ""
    if len(vote_head_names) == 1:
        return vote_head_names[0]
    if len(vote_head_names) == 2:
        return " / ".join(vote_head_names)
    return " / ".join(vote_head_names[:2]) + f" +{len(vote_head_names) - 2} more"


def payment_status_label(payment) -> str:
    if getattr(payment, "reversed_at", None) or not getattr(payment, "is_active", True):
        return "Reversed"
    return "Active"


def payment_receipt_urls(payment, request=None):
    payment_id = getattr(payment, "pk", None)
    if not payment_id:
        return {"receipt_json_url": "", "receipt_pdf_url": ""}

    receipt_json_path = f"{PAYMENT_RECEIPT_BASE_PATH}/{payment_id}/receipt/?format=json"
    receipt_pdf_path = f"{PAYMENT_RECEIPT_BASE_PATH}/{payment_id}/receipt/pdf/"
    if request is not None:
        return {
            "receipt_json_url": request.build_absolute_uri(receipt_json_path),
            "receipt_pdf_url": request.build_absolute_uri(receipt_pdf_path),
        }
    return {
        "receipt_json_url": receipt_json_path,
        "receipt_pdf_url": receipt_pdf_path,
    }


def build_payment_receipt_payload(payment, request=None):
    student = getattr(payment, "student", None)
    payment_amount = getattr(payment, "amount", Decimal("0.00")) or Decimal("0.00")
    payment_date = getattr(payment, "payment_date", None)

    allocations = []
    allocated_amount = Decimal("0.00")
    for allocation in payment.allocations.select_related("invoice").order_by("id"):
        allocated = getattr(allocation, "amount_allocated", Decimal("0.00")) or Decimal("0.00")
        allocated_amount += allocated
        invoice = getattr(allocation, "invoice", None)
        allocations.append(
            {
                "id": allocation.id,
                "invoice_id": allocation.invoice_id,
                "invoice_number": getattr(invoice, "invoice_number", "") if invoice else "",
                "amount": allocated,
                "allocated_at": allocation.allocated_at.isoformat() if allocation.allocated_at else None,
            }
        )

    vote_head_allocations = []
    for allocation in payment.vote_head_allocations.select_related("vote_head").order_by("id"):
        amount = getattr(allocation, "amount", Decimal("0.00")) or Decimal("0.00")
        vote_head = getattr(allocation, "vote_head", None)
        vote_head_allocations.append(
            {
                "id": allocation.id,
                "vote_head_id": allocation.vote_head_id,
                "vote_head": getattr(vote_head, "name", "") if vote_head else "",
                "amount": amount,
                "allocated_at": allocation.allocated_at.isoformat() if allocation.allocated_at else None,
            }
        )

    urls = payment_receipt_urls(payment, request=request)
    receipt_number = payment_receipt_number(payment)
    transaction_code = payment_transaction_code(payment)

    return {
        "id": payment.id,
        "receipt_no": receipt_number,
        "receipt_number": receipt_number,
        "transaction_code": transaction_code,
        "reference_number": transaction_code,
        "student_id": getattr(student, "id", None),
        "student": payment_display_name(student),
        "student_name": payment_display_name(student),
        "admission_number": getattr(student, "admission_number", ""),
        "amount": payment_amount,
        "method": getattr(payment, "payment_method", ""),
        "payment_method": getattr(payment, "payment_method", ""),
        "date": payment_date.date().isoformat() if payment_date else None,
        "payment_date": payment_date.isoformat() if payment_date else None,
        "status": payment_status_label(payment),
        "is_active": bool(getattr(payment, "is_active", True)),
        "notes": getattr(payment, "notes", ""),
        "allocated_amount": allocated_amount,
        "unallocated_amount": payment_amount - allocated_amount,
        "allocations": allocations,
        "vote_head_allocations": vote_head_allocations,
        "vote_head_summary": payment_vote_head_summary(payment),
        **urls,
    }
