from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import VisitorViewSet, AuthorizedPickupViewSet, StudentPickupLogViewSet, VisitorDashboardView

router = SimpleRouter()
router.register('visitors', VisitorViewSet)
router.register('authorized-pickups', AuthorizedPickupViewSet)
router.register('pickup-logs', StudentPickupLogViewSet)

urlpatterns = [
    path('dashboard/', VisitorDashboardView.as_view()),
    path('', include(router.urls)),
]
