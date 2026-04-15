from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import (
    AlumniProfileViewSet,
    AlumniEventViewSet,
    AlumniEventAttendeeViewSet,
    AlumniMentorshipViewSet,
    AlumniDonationViewSet,
    AlumniDashboardView,
)

router = SimpleRouter()
router.register('profiles', AlumniProfileViewSet)
router.register('events', AlumniEventViewSet)
router.register('attendees', AlumniEventAttendeeViewSet)
router.register('mentorships', AlumniMentorshipViewSet)
router.register('donations', AlumniDonationViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/', AlumniDashboardView.as_view(), name='alumni-dashboard'),
]
