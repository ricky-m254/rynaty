from finance.presentation.collection_ops_serializers import (
    BankStatementLineSerializer,
    FeeReminderLogSerializer,
    LateFeeRuleSerializer,
    PaymentGatewayTransactionSerializer,
    PaymentGatewayWebhookEventSerializer,
)
from school.views import (
    BankStatementLineViewSet as SchoolBankStatementLineViewSet,
    FeeReminderLogViewSet as SchoolFeeReminderLogViewSet,
    LateFeeRuleViewSet as SchoolLateFeeRuleViewSet,
    PaymentGatewayTransactionViewSet as SchoolPaymentGatewayTransactionViewSet,
    PaymentGatewayWebhookEventViewSet as SchoolPaymentGatewayWebhookEventViewSet,
)


class LateFeeRuleViewSet(SchoolLateFeeRuleViewSet):
    serializer_class = LateFeeRuleSerializer


class FeeReminderLogViewSet(SchoolFeeReminderLogViewSet):
    serializer_class = FeeReminderLogSerializer


class PaymentGatewayTransactionViewSet(SchoolPaymentGatewayTransactionViewSet):
    serializer_class = PaymentGatewayTransactionSerializer


class PaymentGatewayWebhookEventViewSet(SchoolPaymentGatewayWebhookEventViewSet):
    serializer_class = PaymentGatewayWebhookEventSerializer


class BankStatementLineViewSet(SchoolBankStatementLineViewSet):
    serializer_class = BankStatementLineSerializer

