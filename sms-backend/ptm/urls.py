from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PTMSessionViewSet,
    PTMSlotViewSet,
    PTMBookingViewSet,
    PTMDashboardView,
    MyPTMSlotsView,
)

router = DefaultRouter()
router.register('sessions', PTMSessionViewSet)
router.register('slots', PTMSlotViewSet)
router.register('bookings', PTMBookingViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/', PTMDashboardView.as_view(), name='ptm-dashboard'),
    path('my-slots/', MyPTMSlotsView.as_view(), name='my-ptm-slots'),
]
