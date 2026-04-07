from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CourseViewSet, CourseMaterialViewSet, OnlineQuizViewSet,
    QuizQuestionViewSet, QuizAttemptViewSet, VirtualSessionViewSet,
    ELearningDashboardView
)

router = DefaultRouter()
router.register('courses', CourseViewSet)
router.register('materials', CourseMaterialViewSet)
router.register('quizzes', OnlineQuizViewSet)
router.register('questions', QuizQuestionViewSet)
router.register('attempts', QuizAttemptViewSet)
router.register('sessions', VirtualSessionViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/', ELearningDashboardView.as_view(), name='elearning-dashboard'),
]
