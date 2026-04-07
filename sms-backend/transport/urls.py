from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    VehicleViewSet, RouteViewSet, RouteStopViewSet,
    StudentTransportViewSet, TransportIncidentViewSet,
    TransportDashboardView, TransportSeedView,
)

router = DefaultRouter()
router.register('vehicles', VehicleViewSet)
router.register('routes', RouteViewSet)
router.register('stops', RouteStopViewSet)
router.register('students', StudentTransportViewSet)
router.register('incidents', TransportIncidentViewSet)

urlpatterns = [
    path('dashboard/', TransportDashboardView.as_view()),
    path('seed/', TransportSeedView.as_view()),
    path('', include(router.urls)),
]
