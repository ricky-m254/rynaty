from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import (
    DormitoryViewSet,
    BedSpaceViewSet,
    HostelAllocationViewSet,
    HostelAttendanceViewSet,
    HostelLeaveViewSet,
    HostelDashboardView,
)

router = SimpleRouter()
router.register('dormitories', DormitoryViewSet)
router.register('beds', BedSpaceViewSet)
router.register('allocations', HostelAllocationViewSet, basename='allocations')
router.register('attendance', HostelAttendanceViewSet)
router.register('leave', HostelLeaveViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/', HostelDashboardView.as_view(), name='hostel-dashboard'),
]
