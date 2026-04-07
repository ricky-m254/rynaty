from django.dispatch import Signal

# Finance events (optional hooks)
invoice_created = Signal()
payment_recorded = Signal()
payment_allocated = Signal()
invoice_adjusted = Signal()
fee_assigned = Signal()
