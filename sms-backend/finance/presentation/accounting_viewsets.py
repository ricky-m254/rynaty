from finance.presentation.accounting_serializers import (
    AccountingPeriodSerializer,
    ChartOfAccountSerializer,
    JournalEntrySerializer,
)
from school.views import (
    AccountingPeriodViewSet as SchoolAccountingPeriodViewSet,
    ChartOfAccountViewSet as SchoolChartOfAccountViewSet,
    JournalEntryViewSet as SchoolJournalEntryViewSet,
)


class AccountingPeriodViewSet(SchoolAccountingPeriodViewSet):
    serializer_class = AccountingPeriodSerializer


class ChartOfAccountViewSet(SchoolChartOfAccountViewSet):
    serializer_class = ChartOfAccountSerializer


class JournalEntryViewSet(SchoolJournalEntryViewSet):
    serializer_class = JournalEntrySerializer

