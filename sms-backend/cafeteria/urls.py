from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import (
    MealPlanViewSet,
    WeeklyMenuViewSet,
    StudentMealEnrollmentViewSet,
    MealTransactionViewSet,
    CafeteriaWalletTransactionViewSet,
    CafeteriaDashboardView,
    StudentAccountsView,
    WalletBalanceView,
)

router = SimpleRouter()
router.register('meal-plans', MealPlanViewSet)
router.register('menus', WeeklyMenuViewSet)
router.register('enrollments', StudentMealEnrollmentViewSet)
router.register('transactions', MealTransactionViewSet)
router.register('wallet', CafeteriaWalletTransactionViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/', CafeteriaDashboardView.as_view()),
    path('student-accounts/', StudentAccountsView.as_view()),
    path('wallet/balance/', WalletBalanceView.as_view()),
]
