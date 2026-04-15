from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import SchemeOfWorkViewSet, SchemeTopicViewSet, LessonPlanViewSet, LearningResourceViewSet, CurriculumDashboardView

router = SimpleRouter()
router.register('schemes', SchemeOfWorkViewSet)
router.register('topics', SchemeTopicViewSet)
router.register('lessons', LessonPlanViewSet)
router.register('resources', LearningResourceViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/', CurriculumDashboardView.as_view(), name='curriculum-dashboard'),
]
