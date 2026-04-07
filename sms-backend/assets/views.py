from decimal import Decimal
from django.db.models import Sum
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response

from school.permissions import HasModuleAccess
from .models import AssetCategory, Asset, AssetAssignment, AssetMaintenanceRecord, AssetDepreciation, AssetDisposal, AssetTransfer, AssetWarranty
from .serializers import (
    AssetCategorySerializer,
    AssetSerializer,
    AssetAssignmentSerializer,
    AssetMaintenanceRecordSerializer,
    AssetDepreciationSerializer,
    AssetDisposalSerializer,
    AssetTransferSerializer,
    AssetWarrantySerializer,
)


class AssetCategoryViewSet(viewsets.ModelViewSet):
    queryset = AssetCategory.objects.all().order_by('name')
    serializer_class = AssetCategorySerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "ASSETS"


class AssetViewSet(viewsets.ModelViewSet):
    queryset = Asset.objects.all().order_by('-created_at')
    serializer_class = AssetSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "ASSETS"
    filterset_fields = ['status', 'category']

    def perform_create(self, serializer):
        year = timezone.now().year
        count = Asset.objects.filter(created_at__year=year).count() + 1
        asset_code = f"AST-{year}-{count:05d}"
        serializer.save(asset_code=asset_code)


class AssetAssignmentViewSet(viewsets.ModelViewSet):
    queryset = AssetAssignment.objects.all().order_by('-assigned_date')
    serializer_class = AssetAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "ASSETS"
    filterset_fields = ['asset', 'status']


class AssetMaintenanceRecordViewSet(viewsets.ModelViewSet):
    queryset = AssetMaintenanceRecord.objects.all().order_by('-scheduled_date')
    serializer_class = AssetMaintenanceRecordSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "ASSETS"
    filterset_fields = ['asset', 'status']


class AssetDepreciationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AssetDepreciation.objects.all().select_related('asset')
    serializer_class = AssetDepreciationSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "ASSETS"
    filterset_fields = ['asset']


class AssetDisposalViewSet(viewsets.ModelViewSet):
    queryset = AssetDisposal.objects.all().select_related('asset').order_by('-disposal_date')
    serializer_class = AssetDisposalSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "ASSETS"
    filterset_fields = ['status', 'disposal_type', 'asset']

    def perform_create(self, serializer):
        disposal = serializer.save()
        if disposal.status == 'completed':
            disposal.asset.status = 'Disposed'
            disposal.asset.save(update_fields=['status'])


class AssetTransferViewSet(viewsets.ModelViewSet):
    queryset = AssetTransfer.objects.all().select_related('asset').order_by('-transfer_date')
    serializer_class = AssetTransferSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "ASSETS"
    filterset_fields = ['status', 'asset']

    def perform_create(self, serializer):
        transfer = serializer.save()
        if transfer.status == 'completed':
            transfer.asset.location = transfer.to_location
            transfer.asset.save(update_fields=['location'])


class AssetWarrantyViewSet(viewsets.ModelViewSet):
    queryset = AssetWarranty.objects.all().select_related('asset').order_by('expiry_date')
    serializer_class = AssetWarrantySerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "ASSETS"
    filterset_fields = ['status', 'asset']


class RunDepreciationView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "ASSETS"

    def post(self, request):
        period_label = request.data.get('period_label', str(timezone.now().year))
        assets = Asset.objects.filter(status='Active').select_related('category')
        results = []
        skipped = []

        for asset in assets:
            cat = asset.category
            if not cat or cat.depreciation_method == 'none' or not cat.useful_life_years:
                skipped.append(f"{asset.asset_code} (no depreciation method)")
                continue

            if AssetDepreciation.objects.filter(asset=asset, period_label=period_label).exists():
                skipped.append(f"{asset.asset_code} (already run for {period_label})")
                continue

            purchase_cost = Decimal(str(asset.purchase_cost))
            current_value = Decimal(str(asset.current_value))

            if current_value <= 0:
                skipped.append(f"{asset.asset_code} (fully depreciated)")
                continue

            if cat.depreciation_method == 'straight_line':
                annual_dep = purchase_cost / Decimal(str(cat.useful_life_years))
            elif cat.depreciation_method == 'declining_balance':
                rate = Decimal('2') / Decimal(str(cat.useful_life_years))
                annual_dep = current_value * rate
            else:
                skipped.append(f"{asset.asset_code} (unknown method)")
                continue

            annual_dep = annual_dep.quantize(Decimal('0.01'))
            if annual_dep > current_value:
                annual_dep = current_value

            accumulated = purchase_cost - current_value + annual_dep
            nbv = current_value - annual_dep

            AssetDepreciation.objects.create(
                asset=asset,
                period_label=period_label,
                depreciation_amount=annual_dep,
                accumulated_depreciation=accumulated,
                net_book_value=nbv,
                notes=f"{cat.get_depreciation_method_display()} — {cat.useful_life_years}yr useful life",
            )
            asset.current_value = nbv
            asset.save(update_fields=['current_value'])

            results.append({
                'asset_code': asset.asset_code,
                'name': asset.name,
                'depreciation_amount': str(annual_dep),
                'net_book_value': str(nbv),
            })

        return Response({
            'period_label': period_label,
            'processed': len(results),
            'skipped': len(skipped),
            'entries': results,
            'skipped_codes': skipped,
        }, status=status.HTTP_200_OK)


class AssetsDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "ASSETS"

    def get(self, request):
        total_assets = Asset.objects.count()
        active = Asset.objects.filter(status='Active').count()
        in_repair = Asset.objects.filter(status='In Repair').count()
        retired = Asset.objects.filter(status='Retired').count()
        disposed = Asset.objects.filter(status='Disposed').count()

        total_cost = Asset.objects.aggregate(s=Sum('purchase_cost'))['s'] or Decimal('0')
        total_nbv = Asset.objects.filter(status='Active').aggregate(s=Sum('current_value'))['s'] or Decimal('0')
        total_accumulated = Decimal(str(total_cost)) - Decimal(str(total_nbv))

        categories_count = AssetCategory.objects.count()
        assignments_active = AssetAssignment.objects.filter(status='Active').count()
        maintenance_pending = AssetMaintenanceRecord.objects.filter(status='Pending').count()

        return Response({
            "total_assets": total_assets,
            "active": active,
            "in_repair": in_repair,
            "retired": retired,
            "disposed": disposed,
            "total_value": float(total_nbv),
            "total_cost": float(total_cost),
            "total_accumulated_depreciation": float(total_accumulated),
            "categories_count": categories_count,
            "assignments_active": assignments_active,
            "maintenance_pending": maintenance_pending,
        }, status=status.HTTP_200_OK)
