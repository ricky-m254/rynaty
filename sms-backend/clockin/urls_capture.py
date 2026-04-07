"""
Thin URL module that exposes ONLY the Phase-1 capture endpoint.
Mounted at /api/attendance/capture/ from school/urls.py.

Keeping this separate avoids importing all clockin views into school/urls.py
and prevents accidental exposure of other clockin routes under /attendance/.
"""
from django.urls import path
from .views import CaptureView, AttendanceCaptureLogViewSet

urlpatterns = [
    path('',      CaptureView.as_view(),                              name='attendance_capture'),
    path('logs/', AttendanceCaptureLogViewSet.as_view({'get': 'list'}), name='capture_logs_list'),
]
