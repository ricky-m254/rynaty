# Generated manually for Library baseline module.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import decimal


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LibraryCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "parent",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="children", to="library.librarycategory"),
                ),
            ],
            options={"ordering": ["name", "id"]},
        ),
        migrations.CreateModel(
            name="LibraryMember",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("member_id", models.CharField(max_length=60, unique=True)),
                ("member_type", models.CharField(choices=[("Student", "Student"), ("Staff", "Staff"), ("Parent", "Parent"), ("Alumni", "Alumni"), ("External", "External")], default="Student", max_length=20)),
                ("status", models.CharField(choices=[("Active", "Active"), ("Suspended", "Suspended"), ("Expired", "Expired")], default="Active", max_length=20)),
                ("join_date", models.DateField(default=django.utils.timezone.now)),
                ("expiry_date", models.DateField(blank=True, null=True)),
                ("total_fines", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=12)),
                ("notes", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="library_memberships", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["member_id", "id"]},
        ),
        migrations.CreateModel(
            name="LibraryResource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("resource_type", models.CharField(choices=[("Book", "Book"), ("Periodical", "Periodical"), ("Multimedia", "Multimedia"), ("Digital", "Digital"), ("Equipment", "Equipment")], default="Book", max_length=20)),
                ("title", models.CharField(max_length=255)),
                ("subtitle", models.CharField(blank=True, max_length=255)),
                ("authors", models.TextField(blank=True)),
                ("publisher", models.CharField(blank=True, max_length=255)),
                ("publication_year", models.PositiveIntegerField(blank=True, null=True)),
                ("edition", models.CharField(blank=True, max_length=80)),
                ("isbn", models.CharField(blank=True, max_length=40)),
                ("language", models.CharField(default="en", max_length=20)),
                ("classification", models.CharField(blank=True, max_length=80)),
                ("subjects", models.TextField(blank=True)),
                ("description", models.TextField(blank=True)),
                ("cover_image", models.ImageField(blank=True, null=True, upload_to="library/resources/covers/")),
                ("total_copies", models.PositiveIntegerField(default=0)),
                ("available_copies", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("is_active", models.BooleanField(default=True)),
                ("category", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="resources", to="library.librarycategory")),
            ],
            options={"ordering": ["title", "id"]},
        ),
        migrations.CreateModel(
            name="CirculationRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("member_type", models.CharField(choices=[("Student", "Student"), ("Staff", "Staff"), ("Parent", "Parent"), ("Alumni", "Alumni"), ("External", "External")], max_length=20)),
                ("resource_type", models.CharField(choices=[("Book", "Book"), ("Periodical", "Periodical"), ("Multimedia", "Multimedia"), ("Digital", "Digital"), ("Equipment", "Equipment")], max_length=20)),
                ("max_items", models.PositiveIntegerField(default=3)),
                ("loan_period_days", models.PositiveIntegerField(default=14)),
                ("max_renewals", models.PositiveIntegerField(default=2)),
                ("fine_per_day", models.DecimalField(decimal_places=2, default=decimal.Decimal("5.00"), max_digits=10)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["member_type", "resource_type", "id"], "unique_together": {("member_type", "resource_type")}},
        ),
        migrations.CreateModel(
            name="Reservation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("Waiting", "Waiting"), ("Ready", "Ready"), ("Picked", "Picked"), ("Cancelled", "Cancelled"), ("Expired", "Expired")], default="Waiting", max_length=20)),
                ("reserved_at", models.DateTimeField(auto_now_add=True)),
                ("ready_at", models.DateTimeField(blank=True, null=True)),
                ("pickup_deadline", models.DateField(blank=True, null=True)),
                ("picked_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("queue_position", models.PositiveIntegerField(default=1)),
                ("is_active", models.BooleanField(default=True)),
                ("member", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reservations", to="library.librarymember")),
                ("resource", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reservations", to="library.libraryresource")),
            ],
            options={"ordering": ["resource_id", "queue_position", "id"]},
        ),
        migrations.CreateModel(
            name="ResourceCopy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("accession_number", models.CharField(max_length=80, unique=True)),
                ("barcode", models.CharField(blank=True, db_index=True, max_length=80)),
                ("rfid_tag", models.CharField(blank=True, max_length=80)),
                ("location", models.CharField(blank=True, max_length=120)),
                ("status", models.CharField(choices=[("Available", "Available"), ("Issued", "Issued"), ("Reserved", "Reserved"), ("Lost", "Lost"), ("Damaged", "Damaged"), ("Repair", "Repair")], default="Available", max_length=20)),
                ("condition", models.CharField(choices=[("Excellent", "Excellent"), ("Good", "Good"), ("Fair", "Fair"), ("Poor", "Poor")], default="Good", max_length=20)),
                ("acquisition_date", models.DateField(blank=True, null=True)),
                ("acquisition_source", models.CharField(blank=True, max_length=180)),
                ("price", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("notes", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("resource", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="copies", to="library.libraryresource")),
            ],
            options={"ordering": ["resource__title", "accession_number", "id"]},
        ),
        migrations.CreateModel(
            name="CirculationTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("transaction_type", models.CharField(choices=[("Issue", "Issue"), ("Return", "Return"), ("Renew", "Renew"), ("Lost", "Lost"), ("Damage", "Damage")], default="Issue", max_length=20)),
                ("issue_date", models.DateTimeField(default=django.utils.timezone.now)),
                ("due_date", models.DateField(blank=True, null=True)),
                ("return_date", models.DateTimeField(blank=True, null=True)),
                ("renewal_count", models.PositiveIntegerField(default=0)),
                ("is_overdue", models.BooleanField(default=False)),
                ("overdue_days", models.PositiveIntegerField(default=0)),
                ("fine_amount", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("fine_paid", models.BooleanField(default=False)),
                ("condition_at_return", models.CharField(blank=True, choices=[("Excellent", "Excellent"), ("Good", "Good"), ("Damaged", "Damaged")], max_length=20)),
                ("notes", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("copy", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="transactions", to="library.resourcecopy")),
                ("issued_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="library_transactions_issued", to=settings.AUTH_USER_MODEL)),
                ("member", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="transactions", to="library.librarymember")),
                ("returned_to", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="library_transactions_returned", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-issue_date", "-id"]},
        ),
        migrations.CreateModel(
            name="FineRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fine_type", models.CharField(choices=[("Overdue", "Overdue"), ("Lost", "Lost"), ("Damage", "Damage"), ("Late Pickup", "Late Pickup"), ("Other", "Other")], default="Overdue", max_length=20)),
                ("amount", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=12)),
                ("amount_paid", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=12)),
                ("status", models.CharField(choices=[("Pending", "Pending"), ("Paid", "Paid"), ("Waived", "Waived")], default="Pending", max_length=20)),
                ("waiver_reason", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("member", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="fines", to="library.librarymember")),
                ("transaction", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="fines", to="library.circulationtransaction")),
                ("waived_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
    ]
