from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AssetCategoryViewSet,
    AssetViewSet,
    AssetAssignmentViewSet,
    AssetMaintenanceRecordViewSet,
    AssetDepreciationViewSet,
    AssetDisposalViewSet,
    AssetTransferViewSet,
    AssetWarrantyViewSet,
    RunDepreciationView,
    AssetsDashboardView,
)

router = DefaultRouter()
router.register(r'categories', AssetCategoryViewSet, basename='asset-category')
router.register(r'assignments', AssetAssignmentViewSet, basename='asset-assignment')
router.register(r'maintenance', AssetMaintenanceRecordViewSet, basename='asset-maintenance')
router.register(r'depreciation', AssetDepreciationViewSet, basename='asset-depreciation')
router.register(r'disposals', AssetDisposalViewSet, basename='asset-disposal')
router.register(r'transfers', AssetTransferViewSet, basename='asset-transfer')
router.register(r'warranties', AssetWarrantyViewSet, basename='asset-warranty')
router.register(r'', AssetViewSet, basename='asset')

urlpatterns = [
    path('dashboard/', AssetsDashboardView.as_view(), name='assets-dashboard'),
    path('depreciation/run/', RunDepreciationView.as_view(), name='assets-run-depreciation'),
    path('', include(router.urls)),
]
