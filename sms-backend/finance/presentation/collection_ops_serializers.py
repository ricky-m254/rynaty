from school.serializers import (
    BankStatementLineSerializer as SchoolBankStatementLineSerializer,
    FeeReminderLogSerializer as SchoolFeeReminderLogSerializer,
    LateFeeRuleSerializer as SchoolLateFeeRuleSerializer,
    PaymentGatewayTransactionSerializer as SchoolPaymentGatewayTransactionSerializer,
    PaymentGatewayWebhookEventSerializer as SchoolPaymentGatewayWebhookEventSerializer,
)


class LateFeeRuleSerializer(SchoolLateFeeRuleSerializer):
    pass


class FeeReminderLogSerializer(SchoolFeeReminderLogSerializer):
    pass


class PaymentGatewayTransactionSerializer(SchoolPaymentGatewayTransactionSerializer):
    pass


class PaymentGatewayWebhookEventSerializer(SchoolPaymentGatewayWebhookEventSerializer):
    pass


class BankStatementLineSerializer(SchoolBankStatementLineSerializer):
    pass

