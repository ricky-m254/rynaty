from finance.presentation.governance_serializers import (
    BudgetSerializer,
    ExpenseSerializer,
    ScholarshipAwardSerializer,
    TermSerializer,
    VoteHeadPaymentAllocationSerializer,
)
from school.permissions import HasModuleAccess, IsAccountant
from school.views import (
    BudgetViewSet as SchoolBudgetViewSet,
    ExpenseViewSet as SchoolExpenseViewSet,
    ScholarshipAwardViewSet as SchoolScholarshipAwardViewSet,
    TermViewSet as SchoolTermViewSet,
    VoteHeadPaymentAllocationViewSet as SchoolVoteHeadPaymentAllocationViewSet,
)


class TermViewSet(SchoolTermViewSet):
    serializer_class = TermSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"


class ExpenseViewSet(SchoolExpenseViewSet):
    serializer_class = ExpenseSerializer


class BudgetViewSet(SchoolBudgetViewSet):
    serializer_class = BudgetSerializer


class ScholarshipAwardViewSet(SchoolScholarshipAwardViewSet):
    serializer_class = ScholarshipAwardSerializer


class VoteHeadPaymentAllocationViewSet(SchoolVoteHeadPaymentAllocationViewSet):
    serializer_class = VoteHeadPaymentAllocationSerializer


