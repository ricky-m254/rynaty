from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import ClubViewSet, ClubMembershipViewSet, TournamentViewSet, StudentAwardViewSet, SportsDashboardView

router = SimpleRouter()
router.register('clubs', ClubViewSet)
router.register('memberships', ClubMembershipViewSet)
router.register('tournaments', TournamentViewSet)
router.register('awards', StudentAwardViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/', SportsDashboardView.as_view()),
]
