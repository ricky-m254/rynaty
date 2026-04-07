from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MaintenanceCategoryViewSet, MaintenanceRequestViewSet, MaintenanceChecklistViewSet, MaintenanceDashboardView

router = DefaultRouter()
router.register('categories', MaintenanceCategoryViewSet)
router.register('requests', MaintenanceRequestViewSet)
router.register('checklist', MaintenanceChecklistViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/', MaintenanceDashboardView.as_view(), name='maintenance-dashboard'),
]
