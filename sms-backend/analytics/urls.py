from django.urls import path
from .views import ExecutiveDashboardView, EnrollmentTrendView, AttendanceTrendView, AtRiskStudentsView

urlpatterns = [
    path('executive/', ExecutiveDashboardView.as_view(), name='analytics-executive'),
    path('enrollment-trend/', EnrollmentTrendView.as_view(), name='analytics-enrollment'),
    path('attendance-trend/', AttendanceTrendView.as_view(), name='analytics-attendance'),
    path('at-risk/', AtRiskStudentsView.as_view(), name='analytics-at-risk'),
]
