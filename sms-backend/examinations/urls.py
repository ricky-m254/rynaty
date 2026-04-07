from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ExamSessionViewSet, ExamPaperViewSet, ExamSeatAllocationViewSet,
    ExamResultViewSet, ExamGradeBoundaryViewSet, ExamResultAnalyticsView,
    ExamPaperUploadViewSet, ExamSetterAssignmentViewSet,
)

router = DefaultRouter()
router.register('sessions', ExamSessionViewSet)
router.register('papers', ExamPaperViewSet)
router.register('seat-allocations', ExamSeatAllocationViewSet)
router.register('results', ExamResultViewSet)
router.register('grade-boundaries', ExamGradeBoundaryViewSet)
router.register('paper-uploads', ExamPaperUploadViewSet)
router.register('exam-setters', ExamSetterAssignmentViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('analytics/', ExamResultAnalyticsView.as_view(), name='exam-analytics'),
]
