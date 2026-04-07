from school.serializers import (
    BudgetSerializer as SchoolBudgetSerializer,
    ExpenseSerializer as SchoolExpenseSerializer,
    ScholarshipAwardSerializer as SchoolScholarshipAwardSerializer,
    TermSerializer as SchoolTermSerializer,
    VoteHeadPaymentAllocationSerializer as SchoolVoteHeadPaymentAllocationSerializer,
)


class TermSerializer(SchoolTermSerializer):
    pass


class ExpenseSerializer(SchoolExpenseSerializer):
    pass


class BudgetSerializer(SchoolBudgetSerializer):
    pass


class ScholarshipAwardSerializer(SchoolScholarshipAwardSerializer):
    pass


class VoteHeadPaymentAllocationSerializer(SchoolVoteHeadPaymentAllocationSerializer):
    pass

