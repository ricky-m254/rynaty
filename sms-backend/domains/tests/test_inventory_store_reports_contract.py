from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from domains.inventory.presentation.views import StoreReportsView
from school.models import Role, StoreItem, StoreTransaction, UserProfile


User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with schema_context("public"):
            cls.tenant, _ = Tenant.objects.get_or_create(
                schema_name="store_reports_contract",
                defaults={
                    "name": "Store Reports Contract School",
                    "paid_until": "2030-01-01",
                },
            )
            Domain.objects.get_or_create(
                domain="store-reports.localhost",
                defaults={"tenant": cls.tenant, "is_primary": True},
            )

    def setUp(self):
        self.ctx = schema_context(self.tenant.schema_name)
        self.ctx.__enter__()

    def tearDown(self):
        self.ctx.__exit__(None, None, None)


class StoreReportsContractTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

        self.admin, _ = User.objects.get_or_create(username="store_reports_admin")
        admin_role, _ = Role.objects.get_or_create(
            name="ADMIN",
            defaults={"description": "School Administrator"},
        )
        UserProfile.objects.get_or_create(user=self.admin, defaults={"role": admin_role})

    def test_reports_payload_uses_live_inventory_and_transaction_data(self):
        today = date.today()
        current_month_start = today.replace(day=1)
        previous_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
        current_day = current_month_start + timedelta(days=min(4, (today - current_month_start).days))
        previous_day = previous_month_start + timedelta(days=4)

        rice = StoreItem.objects.create(
            name="Rice",
            unit="bags",
            item_type="FOOD",
            current_stock=Decimal("0.00"),
            reorder_level=Decimal("5.00"),
            cost_price=Decimal("100.00"),
            is_active=True,
        )
        paper = StoreItem.objects.create(
            name="A4 Paper",
            unit="reams",
            item_type="OFFICE",
            current_stock=Decimal("0.00"),
            reorder_level=Decimal("2.00"),
            cost_price=Decimal("50.00"),
            is_active=True,
        )

        StoreTransaction.objects.create(
            item=rice,
            transaction_type="RECEIPT",
            quantity=Decimal("5.00"),
            date=previous_day,
            performed_by=self.admin,
        )
        StoreTransaction.objects.create(
            item=rice,
            transaction_type="RECEIPT",
            quantity=Decimal("10.00"),
            date=current_day,
            performed_by=self.admin,
        )
        StoreTransaction.objects.create(
            item=paper,
            transaction_type="RECEIPT",
            quantity=Decimal("4.00"),
            date=current_day,
            performed_by=self.admin,
        )
        StoreTransaction.objects.create(
            item=rice,
            transaction_type="ISSUANCE",
            quantity=Decimal("3.00"),
            date=current_day,
            department="Cafeteria",
            performed_by=self.admin,
        )
        StoreTransaction.objects.create(
            item=paper,
            transaction_type="ISSUANCE",
            quantity=Decimal("4.00"),
            date=current_day,
            department="Administration",
            performed_by=self.admin,
        )

        request = self.factory.get("/api/store/reports/")
        force_authenticate(request, user=self.admin)
        response = StoreReportsView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["report_month_label"], current_month_start.strftime("%B %Y"))
        self.assertEqual(response.data["tracked_items"], 2)
        self.assertEqual(response.data["low_stock_items"], 1)
        self.assertEqual(response.data["total_inventory_value"], 1200.0)
        self.assertEqual(response.data["monthly_procurement_total"], 1200.0)
        self.assertEqual(response.data["monthly_consumption_total"], 500.0)
        self.assertEqual(response.data["procurement_change_pct"], 140.0)
        self.assertEqual(len(response.data["monthly_procurement"]), 6)
        self.assertEqual(response.data["department_usage"][0], {"dept": "Cafeteria", "value": 300.0, "pct": 60})
        self.assertEqual(response.data["department_usage"][1], {"dept": "Administration", "value": 200.0, "pct": 40})
        self.assertEqual(
            response.data["top_consumed_items"][0],
            {
                "item": "Rice",
                "department": "Cafeteria",
                "consumed": 3.0,
                "unit": "bags",
                "value": 300.0,
            },
        )
