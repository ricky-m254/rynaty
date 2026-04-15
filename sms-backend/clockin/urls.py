from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import (
    BiometricDeviceViewSet,
    SchoolShiftViewSet,
    PersonRegistryViewSet,
    ClockEventViewSet,
    ScanView,
    DashboardView,
    RealtimeView,
    DeviceDiscoverView,
    DahuaEventView,
    DahuaSyncView,
    SmartPSSSourceViewSet,
    SmartPSSImportLogViewSet,
    SmartPSSTestView,
    SmartPSSSyncView,
    SmartPSSCSVImportView,
    CaptureView,
    AttendanceCaptureLogViewSet,
)

router = SimpleRouter()
router.register(r'devices',       BiometricDeviceViewSet)
router.register(r'registry',      PersonRegistryViewSet)
router.register(r'shifts',        SchoolShiftViewSet)
router.register(r'events',        ClockEventViewSet)
router.register(r'capture-logs',  AttendanceCaptureLogViewSet, basename='capture-log')

smartpss_router = SimpleRouter()
smartpss_router.register(r'sources', SmartPSSSourceViewSet, basename='smartpss-source')
smartpss_router.register(r'logs',    SmartPSSImportLogViewSet, basename='smartpss-log')

urlpatterns = [
    # Generic scan (existing)
    path('scan/',             ScanView.as_view()),
    path('kiosk/scan/',       ScanView.as_view()),

    # Phase 1 — raw device capture (also exposed at /api/attendance/capture/)
    path('capture/', CaptureView.as_view()),

    # Dahua ASI6214S native endpoints
    path('dahua/event/',                  DahuaEventView.as_view()),
    path('dahua/<int:device_id>/sync/',   DahuaSyncView.as_view()),

    # SmartPSS Lite — test, pull sync, CSV import
    path('smartpss/sources/<int:pk>/test/', SmartPSSTestView.as_view()),
    path('smartpss/sources/<int:pk>/sync/', SmartPSSSyncView.as_view()),
    path('smartpss/import-csv/',            SmartPSSCSVImportView.as_view()),
    path('smartpss/', include(smartpss_router.urls)),

    # Dashboard / realtime
    path('dashboard/',        DashboardView.as_view()),
    path('realtime/',         RealtimeView.as_view()),

    # Device discovery
    path('devices/discover/', DeviceDiscoverView.as_view()),

    path('', include(router.urls)),
]
