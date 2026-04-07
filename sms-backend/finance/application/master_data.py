from school.models import BalanceCarryForward, VoteHead


def get_vote_head_queryset(active_only=None):
    queryset = VoteHead.objects.all()
    if active_only == "true":
        queryset = queryset.filter(is_active=True)
    return queryset


def seed_default_vote_heads():
    created = []
    for index, name in enumerate(VoteHead.PRELOADED_NAMES):
        _, is_new = VoteHead.objects.get_or_create(
            name=name,
            defaults={
                "is_preloaded": True,
                "order": index,
                "is_active": True,
            },
        )
        if is_new:
            created.append(name)
    return created


def get_balance_carry_forward_queryset(student_id=None, from_term=None, to_term=None):
    queryset = BalanceCarryForward.objects.select_related(
        "student",
        "from_term",
        "to_term",
    ).all()
    if student_id:
        queryset = queryset.filter(student_id=student_id)
    if from_term:
        queryset = queryset.filter(from_term_id=from_term)
    if to_term:
        queryset = queryset.filter(to_term_id=to_term)
    return queryset.order_by("-created_at")
