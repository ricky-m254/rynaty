from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django_tenants.utils import schema_context

from clients.models import Tenant, Domain
from school.models import (
    Role, UserProfile, Student, Guardian, Enrollment,
    FeeStructure, Invoice, InvoiceLineItem, Payment, PaymentAllocation,
    Expense, SchoolProfile
)
from academics.models import AcademicYear, Term, SchoolClass
from hr.models import Staff
from communication.models import Message
from reporting.models import AuditLog
from school.management.commands.seed_modules import ALL_MODULES
from school.role_scope import iter_seed_role_definitions


User = get_user_model()


class Command(BaseCommand):
    help = "Seeds a demo tenant with sample data for frontend development."

    def add_arguments(self, parser):
        parser.add_argument("--schema_name", type=str, default="demo_school", help="Tenant schema name")
        parser.add_argument("--name", type=str, default="Demo School", help="Tenant display name")
        parser.add_argument("--domain", type=str, default="demo.localhost", help="Tenant domain")
        parser.add_argument("--admin_user", type=str, default="admin", help="Tenant admin username")
        parser.add_argument("--admin_pass", type=str, default="admin123", help="Tenant admin password")
        parser.add_argument("--admin_email", type=str, default="admin@demo.localhost", help="Tenant admin email")

    def handle(self, *args, **options):
        schema_name = options["schema_name"]
        name = options["name"]
        domain = options["domain"]
        admin_user = options["admin_user"]
        admin_pass = options["admin_pass"]
        admin_email = options["admin_email"]

        # Create tenant + domain in public schema
        with schema_context("public"):
            tenant, created = Tenant.objects.get_or_create(
                schema_name=schema_name,
                defaults={"name": name, "paid_until": date(2030, 1, 1), "is_active": True},
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created tenant: {name}"))
            Domain.objects.get_or_create(domain=domain, tenant=tenant, defaults={"is_primary": True})

        # Seed data in tenant schema
        with schema_context(schema_name):
            # Roles
            for name, desc in iter_seed_role_definitions():
                Role.objects.get_or_create(name=name, defaults={"description": desc})

            # Modules
            from school.models import Module
            for key, name, _ in ALL_MODULES:
                Module.objects.get_or_create(key=key, defaults={"name": name})

            # School Profile
            SchoolProfile.objects.get_or_create(
                is_active=True,
                defaults={
                    "school_name": "RSM Demo School",
                    "motto": "Excellence Through Knowledge",
                    "address": "123 Education Lane, Nairobi, Kenya",
                    "phone": "+254 700 000 000",
                    "email_address": "info@rsm-demo.ac.ke",
                    "website": "https://rsm-demo.ac.ke",
                    "county": "Nairobi",
                    "country": "Kenya",
                    "currency": "KES",
                    "tax_percentage": "0.00",
                    "receipt_prefix": "RCT-",
                    "invoice_prefix": "INV-",
                    "admission_number_mode": "AUTO",
                    "admission_number_prefix": "ADM-",
                    "admission_number_padding": 4,
                    "primary_color": "#10b981",
                    "secondary_color": "#0ea5e9",
                },
            )

            # Admin user
            user, _ = User.objects.get_or_create(
                username=admin_user,
                defaults={"email": admin_email, "is_staff": True, "is_superuser": True},
            )
            if not user.check_password(admin_pass):
                user.set_password(admin_pass)
                user.save()

            tenant_role = Role.objects.get(name="TENANT_SUPER_ADMIN")
            UserProfile.objects.get_or_create(user=user, defaults={"role": tenant_role})

            # Academics
            year, _ = AcademicYear.objects.get_or_create(
                name="2025-2026",
                defaults={"start_date": date(2025, 1, 1), "end_date": date(2025, 12, 31), "is_active": True},
            )
            term, _ = Term.objects.get_or_create(
                academic_year=year,
                name="Term 1",
                defaults={"start_date": date(2025, 1, 1), "end_date": date(2025, 4, 30), "is_active": True},
            )
            cls, _ = SchoolClass.objects.get_or_create(
                name="Grade 1",
                stream="A",
                academic_year=year,
                defaults={"is_active": True},
            )

            # Students
            s1, _ = Student.objects.get_or_create(
                admission_number="ST001",
                defaults={
                    "first_name": "Alice",
                    "last_name": "Zephyr",
                    "gender": "F",
                    "date_of_birth": date(2010, 1, 1),
                },
            )
            s2, _ = Student.objects.get_or_create(
                admission_number="ST002",
                defaults={
                    "first_name": "Bob",
                    "last_name": "Yellow",
                    "gender": "M",
                    "date_of_birth": date(2010, 1, 2),
                },
            )
            Guardian.objects.get_or_create(
                student=s1, name="Mary Zephyr", relationship="Mother", phone="0700000001"
            )
            Guardian.objects.get_or_create(
                student=s2, name="John Yellow", relationship="Father", phone="0700000002"
            )

            Enrollment.objects.get_or_create(student=s1, school_class_id=cls.id, term_id=term.id)
            Enrollment.objects.get_or_create(student=s2, school_class_id=cls.id, term_id=term.id)

            # HR
            Staff.objects.get_or_create(
                employee_id="EMP001",
                defaults={"first_name": "Jane", "last_name": "Doe", "role": "Teacher", "phone": "0710000001"},
            )

            # Finance
            fee, _ = FeeStructure.objects.get_or_create(
                name="Term 1 Tuition",
                academic_year_id=year.id,
                term_id=term.id,
                defaults={"amount": Decimal("1500.00"), "is_active": True},
            )
            invoice = Invoice.objects.create(
                student=s1,
                term_id=term.id,
                due_date=date.today() + timedelta(days=30),
                total_amount=Decimal("1500.00"),
                status="CONFIRMED",
            )
            InvoiceLineItem.objects.create(
                invoice=invoice,
                fee_structure=fee,
                description="Tuition",
                amount=Decimal("1500.00"),
            )
            base_ref = "RCPT-1001"
            reference_number = base_ref
            suffix = 1
            while Payment.objects.filter(reference_number=reference_number).exists():
                suffix += 1
                reference_number = f"{base_ref}-{suffix}"

            payment = Payment.objects.create(
                student=s1,
                amount=Decimal("500.00"),
                payment_method="Cash",
                reference_number=reference_number,
                notes="Initial deposit",
            )
            PaymentAllocation.objects.create(
                payment=payment,
                invoice=invoice,
                amount_allocated=Decimal("500.00"),
            )
            Expense.objects.create(
                category="Utilities",
                amount=Decimal("200.00"),
                expense_date=date.today(),
                description="Electricity bill",
            )

            # Communication
            Message.objects.create(
                recipient_type="STUDENT",
                recipient_id=s1.id,
                subject="Welcome",
                body="Welcome to the new term!",
                status="SENT",
            )

            # Reporting
            AuditLog.objects.create(
                action="CREATE",
                model_name="Student",
                object_id=str(s1.id),
                details="Seeded student record",
                user_id=user.id,
                timestamp=timezone.now(),
            )

        self.stdout.write(self.style.SUCCESS(f"Seeded demo data for schema '{schema_name}'"))
