from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import (
    TimetableSlotViewSet,
    StaffDutySlotViewSet,
    TimetableChangeRequestViewSet,
    LessonCoverageViewSet,
    WeeklyGridView,
    MyScheduleView,
    TodayCoverageView
)

router = SimpleRouter()
router.register(r'slots', TimetableSlotViewSet)
router.register(r'duty-slots', StaffDutySlotViewSet)
router.register(r'change-requests', TimetableChangeRequestViewSet)
router.register(r'coverage', LessonCoverageViewSet)

urlpatterns = [
    path('grid/', WeeklyGridView.as_view()),
    path('my-schedule/', MyScheduleView.as_view()),
    path('today-coverage/', TodayCoverageView.as_view()),
    path('', include(router.urls)),
]
