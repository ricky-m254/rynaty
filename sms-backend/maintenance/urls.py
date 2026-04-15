from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import MaintenanceCategoryViewSet, MaintenanceRequestViewSet, MaintenanceChecklistViewSet, MaintenanceDashboardView

router = SimpleRouter()
router.register('categories', MaintenanceCategoryViewSet)
router.register('requests', MaintenanceRequestViewSet)
router.register('checklist', MaintenanceChecklistViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/', MaintenanceDashboardView.as_view(), name='maintenance-dashboard'),
]
