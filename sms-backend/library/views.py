from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, F, Max, Q, Sum
from django.db.models.functions import TruncMonth
from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from communication.services import send_email_placeholder, send_sms_placeholder
from school.permissions import HasModuleAccess
from school.services import FinanceService
from .models import (
    AcquisitionRequest,
    CirculationRule,
    CirculationTransaction,
    FineRecord,
    InventoryAudit,
    LibraryCategory,
    LibraryMember,
    LibraryResource,
    Reservation,
    ResourceCopy,
)
from .serializers import (
    AcquisitionRequestSerializer,
    CirculationRuleSerializer,
    CirculationTransactionSerializer,
    FineRecordSerializer,
    InventoryAuditSerializer,
    LibraryCategorySerializer,
    LibraryMemberSerializer,
    LibraryResourceSerializer,
    ReservationSerializer,
    ResourceCopySerializer,
)

import logging

logger = logging.getLogger(__name__)


class LibraryAccessMixin:
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "LIBRARY"


def _is_admin(user):
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    try:
        return hasattr(user, "userprofile") and user.userprofile.role.name in ["ADMIN", "TENANT_SUPER_ADMIN"]
    except Exception:
        return False


def _create_library_notification(user, title: str, message: str, created_by=None):
    if not user:
        return
    try:
        from communication.models import Notification

        Notification.objects.create(
            recipient=user,
            notification_type="System",
            title=title,
            message=message,
            priority="Informational",
            created_by=created_by,
            delivery_status="Sent",
        )
    except Exception:
        # Keep library workflows non-blocking when communication is unavailable.
        return


def recalc_resource_counts(resource_id: int) -> None:
    totals = ResourceCopy.objects.filter(resource_id=resource_id, is_active=True).aggregate(
        total=Count("id"),
        available=Count("id", filter=Q(status="Available")),
    )
    LibraryResource.objects.filter(id=resource_id).update(
        total_copies=totals.get("total") or 0,
        available_copies=totals.get("available") or 0,
    )


class LibraryCategoryViewSet(LibraryAccessMixin, viewsets.ModelViewSet):
    serializer_class = LibraryCategorySerializer
    queryset = LibraryCategory.objects.filter(is_active=True).order_by("name")

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class LibraryResourceViewSet(LibraryAccessMixin, viewsets.ModelViewSet):
    serializer_class = LibraryResourceSerializer
    queryset = LibraryResource.objects.filter(is_active=True).order_by("title")

    def get_queryset(self):
        qs = super().get_queryset()
        resource_type = self.request.query_params.get("resource_type")
        category = self.request.query_params.get("category")
        available_only = self.request.query_params.get("available")
        q = (self.request.query_params.get("q") or "").strip()
        if resource_type:
            qs = qs.filter(resource_type=resource_type)
        if category:
            qs = qs.filter(category_id=category)
        if available_only in ["1", "true", "True"]:
            qs = qs.filter(available_copies__gt=0)
        if q:
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(authors__icontains=q)
                | Q(isbn__icontains=q)
                | Q(subjects__icontains=q)
            )
        return qs

    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        return Response(self.get_serializer(self.get_queryset()[:100], many=True).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="bulk-add")
    def bulk_add(self, request):
        """
        Bulk add multiple library resources (books/periodicals/etc.) in one request.

        Body (JSON):
        {
          "resources": [
            {
              "title": "Mathematics Grade 8",
              "authors": "KIE",
              "resource_type": "Book",          // default "Book"
              "isbn": "978-9966-123-01-6",
              "publisher": "KICD",
              "publication_year": 2024,
              "edition": "1st",
              "classification": "510",
              "subjects": "Mathematics",
              "category": 3,                    // category ID (optional)
              "language": "en",
              "copies": 5,                      // auto-create N physical copies
              "location": "Section A, Shelf 2", // location for auto-created copies
              "acquisition_source": "KLB",
              "price": 850.00                   // per-copy price
            },
            ...
          ]
        }

        Returns: { created_resources: N, created_copies: M, resources: [...] }
        """
        resources_data = request.data.get("resources")
        if not isinstance(resources_data, list) or not resources_data:
            return Response(
                {"error": "Provide a non-empty 'resources' list"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(resources_data) > 200:
            return Response(
                {"error": "Maximum 200 resources per bulk add request"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created_resources = []
        total_copies_created = 0
        errors = []

        with transaction.atomic():
            for idx, item in enumerate(resources_data):
                title = (item.get("title") or "").strip()
                if not title:
                    errors.append({"index": idx, "error": "title is required"})
                    continue

                try:
                    resource = LibraryResource.objects.create(
                        title=title,
                        subtitle=item.get("subtitle", ""),
                        authors=item.get("authors", ""),
                        publisher=item.get("publisher", ""),
                        publication_year=item.get("publication_year") or None,
                        edition=item.get("edition", ""),
                        isbn=item.get("isbn", ""),
                        language=item.get("language", "en"),
                        classification=item.get("classification", ""),
                        subjects=item.get("subjects", ""),
                        description=item.get("description", ""),
                        digital_url=item.get("digital_url", ""),
                        resource_type=item.get("resource_type", "Book"),
                        category_id=item.get("category") or None,
                        is_active=True,
                    )

                    # Auto-create physical copies if requested
                    copy_count = int(item.get("copies") or 0)
                    if copy_count > 0:
                        copy_count = min(copy_count, 100)
                        acc_nums = _next_accession_numbers(copy_count)
                        location         = item.get("location", "")
                        condition        = item.get("condition", "Good")
                        acq_date         = item.get("acquisition_date") or None
                        acq_source       = item.get("acquisition_source", "")
                        price            = item.get("price") or None

                        for acc_num in acc_nums:
                            ResourceCopy.objects.create(
                                resource=resource,
                                accession_number=acc_num,
                                location=location,
                                condition=condition,
                                acquisition_date=acq_date,
                                acquisition_source=acq_source,
                                price=price,
                                status="Available",
                            )
                        recalc_resource_counts(resource.id)
                        total_copies_created += copy_count

                    created_resources.append(resource)
                except Exception as exc:
                    errors.append({"index": idx, "title": title, "error": str(exc)})

        resp_status = status.HTTP_201_CREATED if created_resources else status.HTTP_400_BAD_REQUEST
        return Response(
            {
                "created_resources": len(created_resources),
                "created_copies": total_copies_created,
                "resources": LibraryResourceSerializer(created_resources, many=True).data,
                "errors": errors,
            },
            status=resp_status,
        )

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class ResourceCopyViewSet(LibraryAccessMixin, viewsets.ModelViewSet):
    serializer_class = ResourceCopySerializer
    queryset = ResourceCopy.objects.filter(is_active=True).order_by("resource__title", "accession_number")

    def get_queryset(self):
        qs = super().get_queryset()
        resource = self.request.query_params.get("resource")
        status_value = self.request.query_params.get("status")
        q = (self.request.query_params.get("q") or "").strip()
        if resource:
            qs = qs.filter(resource_id=resource)
        if status_value:
            qs = qs.filter(status=status_value)
        if q:
            qs = qs.filter(
                Q(accession_number__icontains=q)
                | Q(barcode__icontains=q)
                | Q(location__icontains=q)
                | Q(resource__title__icontains=q)
            )
        return qs

    def perform_create(self, serializer):
        row = serializer.save()
        recalc_resource_counts(row.resource_id)

    def perform_update(self, serializer):
        row = serializer.save()
        recalc_resource_counts(row.resource_id)

    def perform_destroy(self, instance):
        resource_id = instance.resource_id
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        recalc_resource_counts(resource_id)

    @action(detail=False, methods=["get"], url_path="lookup")
    def lookup(self, request):
        """
        Quick copy lookup for the physical circulation desk.
        Accepts: ?barcode=XX  or  ?accession=YY
        Returns copy detail + current borrower if issued.
        """
        barcode   = (request.query_params.get("barcode") or "").strip()
        accession = (request.query_params.get("accession") or "").strip()

        if not barcode and not accession:
            return Response(
                {"error": "Provide ?barcode=XX or ?accession=YY"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = ResourceCopy.objects.select_related("resource").filter(is_active=True)
        if barcode:
            copy = qs.filter(barcode=barcode).first()
        else:
            copy = qs.filter(accession_number=accession).first()

        if not copy:
            return Response({"error": "Copy not found"}, status=status.HTTP_404_NOT_FOUND)

        data = ResourceCopySerializer(copy).data

        # Attach current borrower if the copy is issued
        active_txn = (
            CirculationTransaction.objects.select_related("member", "member__user", "member__student")
            .filter(copy=copy, transaction_type="Issue", return_date__isnull=True, is_active=True)
            .first()
        )
        if active_txn:
            member = active_txn.member
            member_name = ""
            if member.student:
                member_name = f"{getattr(member.student, 'full_name', '') or getattr(member.student, 'first_name', '')} {getattr(member.student, 'last_name', '')}".strip()
            elif member.user:
                member_name = member.user.get_full_name() or member.user.username
            data["current_transaction"] = {
                "id": active_txn.id,
                "member_id": member.member_id,
                "member_name": member_name,
                "issue_date": active_txn.issue_date,
                "due_date": active_txn.due_date,
                "overdue": active_txn.due_date < timezone.now().date() if active_txn.due_date else False,
            }
        else:
            data["current_transaction"] = None

        return Response(data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="bulk-add")
    def bulk_add(self, request):
        """
        Bulk add physical copies to an existing resource.
        Body: {resource, count, location, condition, acquisition_date,
               acquisition_source, price, barcode_prefix}
        Creates `count` new copies with auto-generated accession numbers.
        Returns list of created copies.
        """
        resource_id = request.data.get("resource")
        count = int(request.data.get("count") or 1)
        if not resource_id:
            return Response({"error": "resource is required"}, status=status.HTTP_400_BAD_REQUEST)
        if count < 1 or count > 100:
            return Response({"error": "count must be between 1 and 100"}, status=status.HTTP_400_BAD_REQUEST)

        resource = LibraryResource.objects.filter(id=resource_id, is_active=True).first()
        if not resource:
            return Response({"error": "Resource not found"}, status=status.HTTP_404_NOT_FOUND)

        location          = request.data.get("location", "")
        condition         = request.data.get("condition", "Good")
        acquisition_date  = request.data.get("acquisition_date") or None
        acquisition_source = request.data.get("acquisition_source", "")
        price             = request.data.get("price") or None
        notes             = request.data.get("notes", "")
        barcode_prefix    = (request.data.get("barcode_prefix") or "").strip()

        accession_numbers = _next_accession_numbers(count)
        created_copies = []

        with transaction.atomic():
            for i, acc_num in enumerate(accession_numbers):
                barcode = f"{barcode_prefix}{acc_num}" if barcode_prefix else ""
                copy = ResourceCopy.objects.create(
                    resource=resource,
                    accession_number=acc_num,
                    barcode=barcode,
                    location=location,
                    condition=condition,
                    acquisition_date=acquisition_date,
                    acquisition_source=acquisition_source,
                    price=price,
                    notes=notes,
                    status="Available",
                )
                created_copies.append(copy)
            recalc_resource_counts(resource.id)

        return Response(
            {
                "created": count,
                "resource": resource.title,
                "copies": ResourceCopySerializer(created_copies, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="report-lost")
    def report_lost(self, request, pk=None):
        """
        Report a physical copy as lost.
        If currently issued, automatically creates a Lost fine for the borrower.
        Body: {fine_amount (optional — defaults to copy.price), notes}
        """
        copy = self.get_object()
        if copy.status == "Lost":
            return Response({"error": "Copy is already marked as lost"}, status=status.HTTP_400_BAD_REQUEST)

        notes = (request.data.get("notes") or "").strip()
        fine_amount = request.data.get("fine_amount")

        with transaction.atomic():
            # Find active borrow if any
            active_txn = (
                CirculationTransaction.objects.select_related("member")
                .filter(copy=copy, transaction_type="Issue", return_date__isnull=True, is_active=True)
                .first()
            )

            old_status = copy.status
            copy.status = "Lost"
            copy.notes = f"{copy.notes}\nReported lost by {request.user.username} at {timezone.now().isoformat()}. {notes}".strip()
            copy.save(update_fields=["status", "notes"])
            recalc_resource_counts(copy.resource_id)

            fine_record = None
            if active_txn:
                # Close the transaction
                active_txn.return_date = timezone.now()
                active_txn.transaction_type = "Return"
                active_txn.condition_at_return = "Lost"
                active_txn.notes = f"{active_txn.notes or ''}\nBook lost — reported by {request.user.username}".strip()
                active_txn.returned_to = request.user
                active_txn.save(update_fields=["return_date", "transaction_type", "condition_at_return", "notes", "returned_to"])

                # Create lost fine
                amount = Decimal(str(fine_amount)) if fine_amount else (copy.price or Decimal("500.00"))
                fine_record = FineRecord.objects.create(
                    member=active_txn.member,
                    transaction=active_txn,
                    fine_type="Lost",
                    amount=amount,
                    status="Pending",
                )
                recompute_member_fines(active_txn.member_id)
                _create_library_notification(
                    active_txn.member.user,
                    "Library fine: lost book",
                    f"A fine of KES {amount} has been charged for the lost book '{copy.resource.title}' (Acc: {copy.accession_number}).",
                    created_by=request.user,
                )

        payload = {
            "message": f"Copy {copy.accession_number} marked as Lost.",
            "copy": ResourceCopySerializer(copy).data,
        }
        if fine_record:
            payload["fine"] = {
                "id": fine_record.id,
                "member": active_txn.member.member_id,
                "amount": str(fine_record.amount),
                "type": "Lost",
            }
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="report-damaged")
    def report_damaged(self, request, pk=None):
        """
        Report a physical copy as damaged (on return or in-shelf discovery).
        Optionally creates a Damage fine for the last/current borrower.
        Body: {condition (Fair|Poor), fine_amount, charge_borrower (bool), notes}
        """
        copy = self.get_object()
        condition   = request.data.get("condition", "Poor")
        notes       = (request.data.get("notes") or "").strip()
        fine_amount = request.data.get("fine_amount")
        charge      = str(request.data.get("charge_borrower", "false")).lower() in ("1", "true")

        with transaction.atomic():
            copy.condition = condition
            copy.status = "Damaged"
            copy.notes = f"{copy.notes}\nDamage reported by {request.user.username} at {timezone.now().isoformat()}. {notes}".strip()
            copy.save(update_fields=["status", "condition", "notes"])
            recalc_resource_counts(copy.resource_id)

            fine_record = None
            if charge and fine_amount:
                # Find current or most recent borrower
                txn = (
                    CirculationTransaction.objects.select_related("member")
                    .filter(copy=copy, transaction_type__in=["Issue", "Return"], is_active=True)
                    .order_by("-id")
                    .first()
                )
                if txn:
                    amount = Decimal(str(fine_amount))
                    fine_record = FineRecord.objects.create(
                        member=txn.member,
                        transaction=txn,
                        fine_type="Damage",
                        amount=amount,
                        status="Pending",
                    )
                    recompute_member_fines(txn.member_id)
                    _create_library_notification(
                        txn.member.user,
                        "Library fine: damaged book",
                        f"A damage fine of KES {amount} has been charged for '{copy.resource.title}' (Acc: {copy.accession_number}).",
                        created_by=request.user,
                    )

        payload = {
            "message": f"Copy {copy.accession_number} marked as Damaged (condition: {condition}).",
            "copy": ResourceCopySerializer(copy).data,
        }
        if fine_record:
            payload["fine"] = {
                "id": fine_record.id,
                "member": txn.member.member_id,
                "amount": str(fine_record.amount),
                "type": "Damage",
            }
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="send-to-repair")
    def send_to_repair(self, request, pk=None):
        """Mark a Damaged copy as sent to repair."""
        copy = self.get_object()
        if copy.status not in ("Damaged", "Available"):
            return Response(
                {"error": f"Cannot send to repair from status '{copy.status}'"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        copy.status = "Repair"
        copy.notes = f"{copy.notes}\nSent for repair by {request.user.username} at {timezone.now().isoformat()}".strip()
        copy.save(update_fields=["status", "notes"])
        recalc_resource_counts(copy.resource_id)
        return Response(ResourceCopySerializer(copy).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="return-from-repair")
    def return_from_repair(self, request, pk=None):
        """Mark a copy in Repair as back and available."""
        copy = self.get_object()
        if copy.status != "Repair":
            return Response(
                {"error": "Copy is not in repair status"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        condition = request.data.get("condition", "Good")
        copy.status = "Available"
        copy.condition = condition
        copy.notes = f"{copy.notes}\nReturned from repair by {request.user.username} at {timezone.now().isoformat()}".strip()
        copy.save(update_fields=["status", "condition", "notes"])
        recalc_resource_counts(copy.resource_id)
        return Response(ResourceCopySerializer(copy).data, status=status.HTTP_200_OK)


class LibraryMemberViewSet(LibraryAccessMixin, viewsets.ModelViewSet):
    serializer_class = LibraryMemberSerializer
    queryset = LibraryMember.objects.filter(is_active=True).order_by("member_id")

    def get_queryset(self):
        qs = super().get_queryset()
        member_type = self.request.query_params.get("member_type")
        status_value = self.request.query_params.get("status")
        if member_type:
            qs = qs.filter(member_type=member_type)
        if status_value:
            qs = qs.filter(status=status_value)
        return qs

    @action(detail=False, methods=["post"], url_path="sync")
    def sync(self, request):
        if not _is_admin(request.user):
            return Response({"error": "Only admins can run member sync."}, status=status.HTTP_403_FORBIDDEN)

        created = 0
        reactivated = 0
        unchanged = 0

        try:
            from school.models import Student

            for student in Student.objects.filter(is_active=True).only("id", "admission_number", "first_name", "last_name"):
                member_code = f"LIB-STU-{student.id}"
                member = (
                    LibraryMember.objects.filter(student=student).first()
                    or LibraryMember.objects.filter(member_id=member_code).first()
                )
                was_created = False
                if not member:
                    member = LibraryMember.objects.create(
                        member_id=member_code,
                        member_type="Student",
                        status="Active",
                        student=student,
                        is_active=True,
                    )
                    was_created = True
                if was_created:
                    created += 1
                elif (
                    not member.is_active
                    or member.status != "Active"
                    or member.member_type != "Student"
                    or member.student_id != student.id
                ):
                    member.is_active = True
                    member.status = "Active"
                    member.member_type = "Student"
                    member.student = student
                    member.save(update_fields=["is_active", "status", "member_type", "student"])
                    reactivated += 1
                else:
                    unchanged += 1
        except Exception:
            logger.warning("Caught and logged", exc_info=True)

        try:
            from hr.models import Employee

            for employee in Employee.objects.filter(is_active=True, status="Active").select_related("user").only("id", "user", "employee_id"):
                member_code = f"LIB-HR-{employee.id}"
                member, was_created = LibraryMember.objects.get_or_create(
                    member_id=member_code,
                    defaults={
                        "member_type": "Staff",
                        "status": "Active",
                        "user": employee.user,
                    },
                )
                if was_created:
                    created += 1
                elif not member.is_active or member.status != "Active" or member.user_id != employee.user_id:
                    member.is_active = True
                    member.status = "Active"
                    member.member_type = "Staff"
                    member.user = employee.user
                    member.save(update_fields=["is_active", "status", "member_type", "user"])
                    reactivated += 1
                else:
                    unchanged += 1
        except Exception:
            logger.warning("Caught and logged", exc_info=True)

        try:
            from staff_mgmt.models import StaffMember

            for staff_member in StaffMember.objects.filter(is_active=True, status="Active").select_related("user").only("id", "user", "staff_id"):
                member_code = f"LIB-SM-{staff_member.id}"
                member, was_created = LibraryMember.objects.get_or_create(
                    member_id=member_code,
                    defaults={
                        "member_type": "Staff",
                        "status": "Active",
                        "user": staff_member.user,
                    },
                )
                if was_created:
                    created += 1
                elif not member.is_active or member.status != "Active" or member.user_id != staff_member.user_id:
                    member.is_active = True
                    member.status = "Active"
                    member.member_type = "Staff"
                    member.user = staff_member.user
                    member.save(update_fields=["is_active", "status", "member_type", "user"])
                    reactivated += 1
                else:
                    unchanged += 1
        except Exception:
            logger.warning("Caught and logged", exc_info=True)

        return Response(
            {
                "created": created,
                "reactivated": reactivated,
                "unchanged": unchanged,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="suspend")
    def suspend(self, request, pk=None):
        row = self.get_object()
        row.status = "Suspended"
        row.save(update_fields=["status"])
        return Response(self.get_serializer(row).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="borrowings")
    def borrowings(self, request, pk=None):
        rows = (
            CirculationTransaction.objects.filter(
                member_id=pk,
                transaction_type="Issue",
                return_date__isnull=True,
                is_active=True,
            )
            .order_by("due_date", "-id")
        )
        return Response(CirculationTransactionSerializer(rows, many=True).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None):
        rows = CirculationTransaction.objects.filter(member_id=pk, is_active=True).order_by("-issue_date", "-id")[:300]
        return Response(CirculationTransactionSerializer(rows, many=True).data, status=status.HTTP_200_OK)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class ReservationViewSet(LibraryAccessMixin, viewsets.ModelViewSet):
    serializer_class = ReservationSerializer
    queryset = Reservation.objects.filter(is_active=True).order_by("resource_id", "queue_position")

    def get_queryset(self):
        qs = super().get_queryset()
        member = self.request.query_params.get("member")
        status_value = self.request.query_params.get("status")
        if member:
            qs = qs.filter(member_id=member)
        if status_value:
            qs = qs.filter(status=status_value)
        return qs

    def perform_create(self, serializer):
        resource = serializer.validated_data["resource"]
        max_pos = (
            Reservation.objects.filter(resource=resource, is_active=True, status__in=["Waiting", "Ready"]).aggregate(v=Max("queue_position")).get("v")
            or 0
        )
        serializer.save(queue_position=max_pos + 1, status="Waiting")

    @action(detail=True, methods=["patch"], url_path="cancel")
    def cancel(self, request, pk=None):
        row = self.get_object()
        if row.status in ["Picked", "Cancelled", "Expired"]:
            return Response({"error": "Reservation is already closed."}, status=status.HTTP_400_BAD_REQUEST)
        row.status = "Cancelled"
        row.cancelled_at = timezone.now()
        row.save(update_fields=["status", "cancelled_at"])
        return Response(self.get_serializer(row).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["patch"], url_path="pickup")
    def pickup(self, request, pk=None):
        row = self.get_object()
        if row.status != "Ready":
            return Response({"error": "Only ready reservations can be picked up."}, status=status.HTTP_400_BAD_REQUEST)
        row.status = "Picked"
        row.picked_at = timezone.now()
        row.save(update_fields=["status", "picked_at"])
        return Response(self.get_serializer(row).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path=r"queue/(?P<resource_id>\d+)")
    def queue(self, request, resource_id=None):
        rows = self.get_queryset().filter(resource_id=resource_id, status__in=["Waiting", "Ready"]).order_by("queue_position")
        return Response(self.get_serializer(rows, many=True).data, status=status.HTTP_200_OK)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class FineViewSet(LibraryAccessMixin, viewsets.ModelViewSet):
    serializer_class = FineRecordSerializer
    queryset = FineRecord.objects.filter(is_active=True).order_by("-created_at")

    def get_queryset(self):
        qs = super().get_queryset()
        member = self.request.query_params.get("member")
        status_value = self.request.query_params.get("status")
        if member:
            qs = qs.filter(member_id=member)
        if status_value:
            qs = qs.filter(status=status_value)
        return qs

    @action(detail=True, methods=["post"], url_path="pay")
    def pay(self, request, pk=None):
        try:
            with transaction.atomic():
                row = self.get_object()
                previous_paid = Decimal(str(row.amount_paid or 0))
                amount = Decimal(str(request.data.get("amount") or row.amount - row.amount_paid))
                if amount <= 0:
                    return Response({"error": "Payment amount must be greater than zero."}, status=status.HTTP_400_BAD_REQUEST)
                row.amount_paid = min(row.amount, row.amount_paid + amount)
                if row.amount_paid >= row.amount:
                    row.status = "Paid"
                    row.paid_at = timezone.now()
                row.save(update_fields=["amount_paid", "status", "paid_at"])
                paid_delta = Decimal(str(row.amount_paid or 0)) - previous_paid
                if paid_delta > 0:
                    payment_marker = str(Decimal(str(row.amount_paid)).quantize(Decimal("0.01")))
                    FinanceService.post_library_fine_payment(
                        fine_id=row.id,
                        amount=paid_delta,
                        payment_marker=payment_marker,
                        posted_by=request.user,
                    )
                recompute_member_fines(row.member_id)
                return Response(self.get_serializer(row).data, status=status.HTTP_200_OK)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="waive")
    def waive(self, request, pk=None):
        try:
            with transaction.atomic():
                row = self.get_object()
                if row.status == "Waived":
                    return Response(self.get_serializer(row).data, status=status.HTTP_200_OK)
                outstanding_before_waive = max(Decimal("0.00"), Decimal(str(row.amount or 0)) - Decimal(str(row.amount_paid or 0)))
                row.status = "Waived"
                row.waiver_reason = (request.data.get("reason") or "").strip()
                row.waived_by = request.user
                row.save(update_fields=["status", "waiver_reason", "waived_by"])
                if outstanding_before_waive > 0:
                    FinanceService.post_library_fine_waiver(
                        fine_id=row.id,
                        amount=outstanding_before_waive,
                        posted_by=request.user,
                    )
                recompute_member_fines(row.member_id)
                return Response(self.get_serializer(row).data, status=status.HTTP_200_OK)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"], url_path="finance-postings")
    def finance_postings(self, request, pk=None):
        try:
            from school.models import JournalEntry

            entries = (
                JournalEntry.objects.filter(
                    source_id=int(pk),
                    source_type__in=["LibraryFineAccrual", "LibraryFinePayment", "LibraryFineWaiver"],
                )
                .prefetch_related("lines", "lines__account")
                .order_by("-entry_date", "-id")
            )
            payload = []
            for entry in entries:
                payload.append(
                    {
                        "id": entry.id,
                        "entry_date": entry.entry_date,
                        "memo": entry.memo,
                        "source_type": entry.source_type,
                        "entry_key": entry.entry_key,
                        "lines": [
                            {
                                "account_code": line.account.code,
                                "account_name": line.account.name,
                                "debit": line.debit,
                                "credit": line.credit,
                                "description": line.description,
                            }
                            for line in entry.lines.all()
                        ],
                    }
                )
            return Response(payload, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"], url_path=r"summary/(?P<member_id>\d+)")
    def summary(self, request, member_id=None):
        rows = FineRecord.objects.filter(member_id=member_id, is_active=True)
        payload = rows.aggregate(total=Sum("amount"), paid=Sum("amount_paid"))
        total = payload.get("total") or Decimal("0.00")
        paid = payload.get("paid") or Decimal("0.00")
        return Response(
            {
                "member_id": int(member_id),
                "total": total,
                "paid": paid,
                "outstanding": total - paid,
                "pending_count": rows.filter(status="Pending").count(),
            },
            status=status.HTTP_200_OK,
        )

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        recompute_member_fines(instance.member_id)


def recompute_member_fines(member_id: int) -> None:
    outstanding = (
        FineRecord.objects.filter(member_id=member_id, is_active=True, status="Pending").aggregate(v=Sum(F("amount") - F("amount_paid"))).get("v")
        or Decimal("0.00")
    )
    LibraryMember.objects.filter(id=member_id).update(total_fines=outstanding)


class InventoryAuditViewSet(LibraryAccessMixin, viewsets.ModelViewSet):
    serializer_class = InventoryAuditSerializer
    queryset = InventoryAudit.objects.filter(is_active=True).order_by("-audit_date", "-id")

    def get_queryset(self):
        qs = super().get_queryset()
        status_value = (self.request.query_params.get("status") or "").strip()
        if status_value:
            qs = qs.filter(status=status_value)
        return qs

    def perform_create(self, serializer):
        total_expected = ResourceCopy.objects.filter(is_active=True).count()
        total_found = int(self.request.data.get("total_found") or 0)
        missing_count = max(0, total_expected - total_found)
        serializer.save(
            audit_date=date.today(),
            conducted_by=self.request.user,
            total_expected=total_expected,
            missing_count=missing_count,
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        missing_count = max(0, int(instance.total_expected or 0) - int(instance.total_found or 0))
        if missing_count != instance.missing_count:
            instance.missing_count = missing_count
            instance.save(update_fields=["missing_count"])

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        row = self.get_object()
        total_expected = ResourceCopy.objects.filter(is_active=True).count()
        total_found = int(request.data.get("total_found") or row.total_found or 0)
        row.total_expected = total_expected
        row.total_found = total_found
        row.missing_count = max(0, total_expected - total_found)
        row.status = "Completed"
        row.notes = (request.data.get("notes") or row.notes or "").strip()
        row.save(update_fields=["total_expected", "total_found", "missing_count", "status", "notes", "updated_at"])
        return Response(self.get_serializer(row).data, status=status.HTTP_200_OK)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class AcquisitionRequestViewSet(LibraryAccessMixin, viewsets.ModelViewSet):
    serializer_class = AcquisitionRequestSerializer
    queryset = AcquisitionRequest.objects.filter(is_active=True).order_by("-created_at", "-id")

    def get_queryset(self):
        qs = super().get_queryset()
        status_value = (self.request.query_params.get("status") or "").strip()
        if status_value:
            qs = qs.filter(status=status_value)
        return qs

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        row = self.get_object()
        if row.status in ["Rejected", "Received"]:
            return Response({"error": f"Cannot approve a {row.status.lower()} request."}, status=status.HTTP_400_BAD_REQUEST)
        row.status = "Approved"
        row.approved_by = request.user
        row.save(update_fields=["status", "approved_by", "updated_at"])
        return Response(self.get_serializer(row).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        row = self.get_object()
        if row.status == "Received":
            return Response({"error": "Cannot reject a received request."}, status=status.HTTP_400_BAD_REQUEST)
        row.status = "Rejected"
        row.approved_by = request.user
        row.save(update_fields=["status", "approved_by", "updated_at"])
        return Response(self.get_serializer(row).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="mark-ordered")
    def mark_ordered(self, request, pk=None):
        row = self.get_object()
        if row.status not in ["Approved", "Ordered"]:
            return Response({"error": "Only approved requests can be marked ordered."}, status=status.HTTP_400_BAD_REQUEST)
        row.status = "Ordered"
        row.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(row).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="mark-received")
    def mark_received(self, request, pk=None):
        row = self.get_object()
        if row.status not in ["Ordered", "Received"]:
            return Response({"error": "Only ordered requests can be marked received."}, status=status.HTTP_400_BAD_REQUEST)
        row.status = "Received"
        row.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(row).data, status=status.HTTP_200_OK)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class CirculationRuleView(LibraryAccessMixin, APIView):
    def get(self, request):
        rows = CirculationRule.objects.filter(is_active=True).order_by("member_type", "resource_type")
        return Response(CirculationRuleSerializer(rows, many=True).data, status=status.HTTP_200_OK)

    def post(self, request):
        member_type = request.data.get("member_type")
        resource_type = request.data.get("resource_type")
        if not member_type or not resource_type:
            return Response({"error": "member_type and resource_type are required"}, status=status.HTTP_400_BAD_REQUEST)
        row, _ = CirculationRule.objects.update_or_create(
            member_type=member_type,
            resource_type=resource_type,
            defaults={
                "max_items": request.data.get("max_items", 3),
                "loan_period_days": request.data.get("loan_period_days", 14),
                "max_renewals": request.data.get("max_renewals", 2),
                "fine_per_day": request.data.get("fine_per_day", "5.00"),
                "is_active": True,
            },
        )
        return Response(CirculationRuleSerializer(row).data, status=status.HTTP_200_OK)


def _pick_rule(member: LibraryMember, resource: LibraryResource) -> CirculationRule:
    return CirculationRule.objects.filter(
        member_type=member.member_type,
        resource_type=resource.resource_type,
        is_active=True,
    ).first()


def _next_accession_numbers(count: int) -> list:
    """
    Generate N unique accession numbers for new physical copies.
    Format: ACC-{YYYY}-{seq:05d}
    Thread-safe: checks the DB after each candidate.
    """
    from django.utils import timezone as _tz
    year = _tz.now().year
    base = ResourceCopy.objects.count()
    existing = set(ResourceCopy.objects.values_list("accession_number", flat=True))
    results = []
    seq = base + 1
    while len(results) < count:
        candidate = f"ACC-{year}-{seq:05d}"
        if candidate not in existing:
            results.append(candidate)
            existing.add(candidate)
        seq += 1
    return results


def _resolve_copy(data: dict):
    """
    Resolve a physical copy from request data.
    Accepts: copy (ID), barcode, or accession_number (in that priority).
    Returns ResourceCopy or None.
    """
    copy_id     = data.get("copy")
    barcode     = (data.get("barcode") or "").strip()
    accession   = (data.get("accession_number") or "").strip()

    qs = ResourceCopy.objects.select_related("resource").filter(is_active=True)
    if copy_id:
        return qs.filter(id=copy_id).first()
    if barcode:
        return qs.filter(barcode=barcode).first()
    if accession:
        return qs.filter(accession_number=accession).first()
    return None


class IssueResourceView(LibraryAccessMixin, APIView):
    def post(self, request):
        member_id = request.data.get("member")
        # Support lookup by copy ID, barcode, or accession_number
        copy_id     = request.data.get("copy")
        barcode     = request.data.get("barcode")
        accession   = request.data.get("accession_number")
        if not member_id or not (copy_id or barcode or accession):
            return Response(
                {"error": "member and one of: copy (ID), barcode, or accession_number are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        member = LibraryMember.objects.filter(id=member_id, is_active=True).first()
        copy = _resolve_copy(request.data)
        if not member or not copy:
            return Response({"error": "member/copy not found"}, status=status.HTTP_404_NOT_FOUND)
        if member.status != "Active":
            return Response({"error": "member is not active"}, status=status.HTTP_400_BAD_REQUEST)
        if copy.status != "Available":
            return Response({"error": "copy is not available"}, status=status.HTTP_400_BAD_REQUEST)
        if member.total_fines > Decimal("500.00"):
            return Response({"error": "member has outstanding fines above threshold"}, status=status.HTTP_400_BAD_REQUEST)
        rule = _pick_rule(member, copy.resource)
        if not rule:
            return Response({"error": "no circulation rule for this member/resource type"}, status=status.HTTP_400_BAD_REQUEST)
        active_count = CirculationTransaction.objects.filter(
            member=member,
            transaction_type="Issue",
            return_date__isnull=True,
            is_active=True,
        ).count()
        if active_count >= rule.max_items:
            return Response({"error": "borrowing limit reached"}, status=status.HTTP_400_BAD_REQUEST)
        due_date = (timezone.now() + timedelta(days=rule.loan_period_days)).date()
        row = CirculationTransaction.objects.create(
            copy=copy,
            member=member,
            transaction_type="Issue",
            issue_date=timezone.now(),
            due_date=due_date,
            issued_by=request.user,
        )
        copy.status = "Issued"
        copy.save(update_fields=["status"])
        recalc_resource_counts(copy.resource_id)
        return Response(CirculationTransactionSerializer(row).data, status=status.HTTP_201_CREATED)


class ReturnResourceView(LibraryAccessMixin, APIView):
    def post(self, request):
        transaction_id = request.data.get("transaction")
        # Also support lookup by copy barcode or accession_number for physical desk
        barcode     = (request.data.get("barcode") or "").strip()
        accession   = (request.data.get("accession_number") or "").strip()

        qs = (
            CirculationTransaction.objects
            .select_related("copy", "member", "copy__resource")
            .filter(transaction_type="Issue", return_date__isnull=True, is_active=True)
        )

        if transaction_id:
            row = qs.filter(id=transaction_id).first()
        elif barcode:
            copy = ResourceCopy.objects.filter(barcode=barcode, is_active=True).first()
            row = qs.filter(copy=copy).first() if copy else None
        elif accession:
            copy = ResourceCopy.objects.filter(accession_number=accession, is_active=True).first()
            row = qs.filter(copy=copy).first() if copy else None
        else:
            return Response(
                {"error": "one of: transaction (ID), barcode, or accession_number is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not row:
            return Response({"error": "active issue transaction not found"}, status=status.HTTP_404_NOT_FOUND)
        now = timezone.now()
        overdue_days = max(0, (now.date() - row.due_date).days) if row.due_date else 0
        fine_amount = Decimal("0.00")
        if overdue_days > 0:
            rule = _pick_rule(row.member, row.copy.resource)
            if rule:
                fine_amount = Decimal(overdue_days) * rule.fine_per_day
        row.return_date = now
        row.overdue_days = overdue_days
        row.is_overdue = overdue_days > 0
        row.fine_amount = fine_amount
        row.fine_paid = fine_amount <= 0
        row.condition_at_return = request.data.get("condition_at_return") or ""
        row.returned_to = request.user
        row.transaction_type = "Return"
        row.save(
            update_fields=[
                "return_date",
                "overdue_days",
                "is_overdue",
                "fine_amount",
                "fine_paid",
                "condition_at_return",
                "returned_to",
                "transaction_type",
            ]
        )
        if fine_amount > 0:
            fine = FineRecord.objects.create(
                member=row.member,
                transaction=row,
                fine_type="Overdue",
                amount=fine_amount,
                status="Pending",
            )
            try:
                FinanceService.post_library_fine_accrual(
                    fine_id=fine.id,
                    amount=fine_amount,
                    posted_by=request.user,
                )
            except Exception:
                # Keep return workflow non-blocking; operations can replay postings via finance tooling if needed.
                pass
            recompute_member_fines(row.member_id)
            _create_library_notification(
                row.member.user,
                "Library fine created",
                f"An overdue fine of {fine_amount} has been added to your library account.",
                created_by=request.user,
            )
        next_reservation = (
            Reservation.objects.filter(resource=row.copy.resource, status="Waiting", is_active=True).order_by("queue_position", "id").first()
        )
        if next_reservation:
            row.copy.status = "Reserved"
            next_reservation.status = "Ready"
            next_reservation.ready_at = now
            next_reservation.pickup_deadline = (now + timedelta(days=3)).date()
            next_reservation.save(update_fields=["status", "ready_at", "pickup_deadline"])
            _create_library_notification(
                next_reservation.member.user,
                "Library reservation ready",
                f"Your reservation for '{row.copy.resource.title}' is ready for pickup.",
                created_by=request.user,
            )
        else:
            row.copy.status = "Available"
        row.copy.save(update_fields=["status"])
        recalc_resource_counts(row.copy.resource_id)
        return Response(CirculationTransactionSerializer(row).data, status=status.HTTP_200_OK)


class RenewResourceView(LibraryAccessMixin, APIView):
    def post(self, request):
        transaction_id = request.data.get("transaction")
        if not transaction_id:
            return Response({"error": "transaction is required"}, status=status.HTTP_400_BAD_REQUEST)
        row = (
            CirculationTransaction.objects.select_related("copy", "member", "copy__resource")
            .filter(id=transaction_id, transaction_type="Issue", return_date__isnull=True, is_active=True)
            .first()
        )
        if not row:
            return Response({"error": "active issue transaction not found"}, status=status.HTTP_404_NOT_FOUND)
        waiting_exists = Reservation.objects.filter(resource=row.copy.resource, status="Waiting", is_active=True).exists()
        if waiting_exists:
            return Response({"error": "renewal blocked; resource is reserved by another member"}, status=status.HTTP_400_BAD_REQUEST)
        rule = _pick_rule(row.member, row.copy.resource)
        if not rule:
            return Response({"error": "no circulation rule for this member/resource type"}, status=status.HTTP_400_BAD_REQUEST)
        if row.renewal_count >= rule.max_renewals:
            return Response({"error": "max renewals reached"}, status=status.HTTP_400_BAD_REQUEST)
        row.renewal_count += 1
        row.due_date = (row.due_date or timezone.now().date()) + timedelta(days=rule.loan_period_days)
        row.notes = (row.notes or "") + f"\nRenewed by {request.user.username} at {timezone.now().isoformat()}"
        row.save(update_fields=["renewal_count", "due_date", "notes"])
        return Response(CirculationTransactionSerializer(row).data, status=status.HTTP_200_OK)


class CirculationTransactionsView(LibraryAccessMixin, APIView):
    def get(self, request):
        qs = CirculationTransaction.objects.filter(is_active=True).select_related("copy", "member", "copy__resource")
        member = request.query_params.get("member")
        overdue = request.query_params.get("overdue")
        if member:
            qs = qs.filter(member_id=member)
        if overdue in ["1", "true", "True"]:
            qs = qs.filter(return_date__isnull=True, due_date__lt=timezone.now().date())
        return Response(CirculationTransactionSerializer(qs.order_by("-issue_date", "-id")[:500], many=True).data, status=status.HTTP_200_OK)


class CirculationOverdueView(LibraryAccessMixin, APIView):
    def get(self, request):
        rows = CirculationTransaction.objects.filter(
            transaction_type="Issue",
            return_date__isnull=True,
            due_date__lt=timezone.now().date(),
            is_active=True,
        ).order_by("due_date", "-id")
        return Response(CirculationTransactionSerializer(rows, many=True).data, status=status.HTTP_200_OK)


class CirculationBulkRemindView(LibraryAccessMixin, APIView):
    """
    POST /api/library/circulation/overdue/remind-all/
    Send overdue reminders to ALL current overdue borrowers in one action.
    Returns a summary of successes and failures.
    """

    def post(self, request):
        today = timezone.now().date()
        overdue_rows = (
            CirculationTransaction.objects
            .select_related("copy", "copy__resource", "member", "member__user", "member__student")
            .filter(
                transaction_type="Issue",
                return_date__isnull=True,
                due_date__lt=today,
                is_active=True,
            )
            .order_by("due_date", "id")
        )

        results = {"sent": 0, "skipped": 0, "failed": 0, "details": []}

        for row in overdue_rows:
            member_user    = row.member.user
            member_student = getattr(row.member, "student", None)
            recipient_email = (
                getattr(member_user, "email", "")
                or getattr(member_student, "email", "")
                or ""
            ).strip()
            recipient_phone = (getattr(member_student, "phone", "") or "").strip()
            overdue_days = (today - row.due_date).days
            title   = "Library overdue reminder"
            message = (
                f"'{row.copy.resource.title}' was due on {row.due_date.isoformat()} "
                f"and is now {overdue_days} day(s) overdue. "
                f"Please return it immediately to avoid increased fines."
            )

            channels: list = []
            if member_user:
                try:
                    _create_library_notification(member_user, title, message, created_by=request.user)
                    channels.append("notification")
                except Exception:
                    logger.warning("Caught and logged", exc_info=True)
            if recipient_email:
                try:
                    email_result = send_email_placeholder(subject=title.title(), body=message, recipients=[recipient_email])
                    if email_result.status == "Sent":
                        channels.append("email")
                except Exception:
                    logger.warning("Caught and logged", exc_info=True)
            if recipient_phone:
                try:
                    sms_result = send_sms_placeholder(recipient_phone, message, channel="SMS")
                    if sms_result.status == "Sent":
                        channels.append("sms")
                except Exception:
                    logger.warning("Caught and logged", exc_info=True)

            if channels:
                # Append reminder note to transaction
                note = f"Bulk reminder sent by {request.user.username} at {timezone.now().isoformat()} via {', '.join(channels)}"
                row.notes = f"{(row.notes or '').strip()}\n{note}".strip()
                try:
                    row.save(update_fields=["notes"])
                except Exception:
                    logger.warning("Caught and logged", exc_info=True)
                results["sent"] += 1
                results["details"].append({
                    "transaction": row.id,
                    "member": row.member.member_id,
                    "book": row.copy.resource.title,
                    "overdue_days": overdue_days,
                    "channels": channels,
                })
            elif not member_user and not recipient_email and not recipient_phone:
                results["skipped"] += 1
            else:
                results["failed"] += 1

        results["total_overdue"] = len(overdue_rows)
        return Response(results, status=status.HTTP_200_OK)


class CirculationReminderView(LibraryAccessMixin, APIView):
    def post(self, request, transaction_id):
        row = (
            CirculationTransaction.objects.select_related("copy", "copy__resource", "member", "member__user", "member__student")
            .filter(
                id=transaction_id,
                transaction_type="Issue",
                return_date__isnull=True,
                is_active=True,
            )
            .first()
        )
        if not row:
            return Response({"error": "active issue transaction not found"}, status=status.HTTP_404_NOT_FOUND)
        if not row.due_date or row.due_date >= timezone.now().date():
            return Response({"error": "reminders are only available for overdue transactions"}, status=status.HTTP_400_BAD_REQUEST)

        member_user = row.member.user
        member_student = getattr(row.member, "student", None)
        recipient_email = (
            getattr(member_user, "email", "")
            or getattr(member_student, "email", "")
            or ""
        ).strip()
        recipient_phone = (getattr(member_student, "phone", "") or "").strip()
        overdue_days = (timezone.now().date() - row.due_date).days
        title = "Library overdue reminder"
        message = (
            f"{row.copy.resource.title} was due on {row.due_date.isoformat()} "
            f"and is now {overdue_days} day(s) overdue."
        )

        channels: list[str] = []
        notes: list[str] = []

        if member_user:
            _create_library_notification(member_user, title, message, created_by=request.user)
            channels.append("notification")

        if recipient_email:
            email_result = send_email_placeholder(
                subject=title.title(),
                body=message,
                recipients=[recipient_email],
            )
            if email_result.status == "Sent":
                channels.append("email")
            if email_result.failure_reason:
                notes.append(email_result.failure_reason)

        if recipient_phone:
            sms_result = send_sms_placeholder(recipient_phone, message, channel="SMS")
            if sms_result.status == "Sent":
                channels.append("sms")
            if sms_result.failure_reason:
                notes.append(sms_result.failure_reason)

        if not channels:
            return Response(
                {"error": "No linked notification, email, or phone contact is available for this borrower."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reminder_note = (
            f"Reminder sent by {request.user.username} at {timezone.now().isoformat()} "
            f"via {', '.join(channels)}"
        )
        row.notes = f"{(row.notes or '').strip()}\n{reminder_note}".strip()
        row.save(update_fields=["notes"])

        payload = {
            "message": "Reminder sent successfully.",
            "channels": channels,
        }
        if notes:
            payload["note"] = " ".join(notes)
        return Response(payload, status=status.HTTP_200_OK)


class CirculationMemberBorrowingsView(LibraryAccessMixin, APIView):
    def get(self, request, member_id):
        rows = CirculationTransaction.objects.filter(
            member_id=member_id,
            transaction_type="Issue",
            return_date__isnull=True,
            is_active=True,
        ).order_by("due_date", "-id")
        return Response(CirculationTransactionSerializer(rows, many=True).data, status=status.HTTP_200_OK)


class LibraryReportsCirculationView(LibraryAccessMixin, APIView):
    def get(self, request):
        now = timezone.now()
        six_months_ago = now - timedelta(days=180)
        monthly = (
            CirculationTransaction.objects.filter(is_active=True, issue_date__gte=six_months_ago)
            .annotate(month=TruncMonth("issue_date"))
            .values("month")
            .annotate(
                total=Count("id"),
                issues=Count("id", filter=Q(transaction_type="Issue")),
                returns=Count("id", filter=Q(transaction_type="Return")),
                renewals=Count("id", filter=Q(transaction_type="Renew")),
            )
            .order_by("month")
        )
        payload = [
            {
                "month": row["month"].date().isoformat() if row["month"] else "",
                "total": row["total"],
                "issues": row["issues"],
                "returns": row["returns"],
                "renewals": row["renewals"],
            }
            for row in monthly
        ]
        return Response(
            {
                "active_borrowings": CirculationTransaction.objects.filter(
                    transaction_type="Issue", return_date__isnull=True, is_active=True
                ).count(),
                "overdue_count": CirculationTransaction.objects.filter(
                    transaction_type="Issue", return_date__isnull=True, due_date__lt=timezone.now().date(), is_active=True
                ).count(),
                "monthly": payload,
            },
            status=status.HTTP_200_OK,
        )


class LibraryReportsPopularView(LibraryAccessMixin, APIView):
    def get(self, request):
        limit = int(request.query_params.get("limit") or 10)
        rows = (
            CirculationTransaction.objects.filter(is_active=True, transaction_type="Issue")
            .values("copy__resource_id", "copy__resource__title")
            .annotate(borrow_count=Count("id"))
            .order_by("-borrow_count", "copy__resource__title")[: max(1, min(limit, 100))]
        )
        return Response(
            [
                {
                    "resource_id": row["copy__resource_id"],
                    "title": row["copy__resource__title"],
                    "borrow_count": row["borrow_count"],
                }
                for row in rows
            ],
            status=status.HTTP_200_OK,
        )


class LibraryReportsOverdueView(LibraryAccessMixin, APIView):
    def get(self, request):
        today = timezone.now().date()
        rows = (
            CirculationTransaction.objects.filter(
                transaction_type="Issue",
                return_date__isnull=True,
                due_date__lt=today,
                is_active=True,
            )
            .select_related("copy", "copy__resource", "member")
            .order_by("due_date", "-id")
        )
        payload = []
        for row in rows:
            overdue_days = (today - row.due_date).days if row.due_date else 0
            payload.append(
                {
                    "transaction_id": row.id,
                    "member_id": row.member_id,
                    "member_code": row.member.member_id,
                    "resource_id": row.copy.resource_id,
                    "resource_title": row.copy.resource.title,
                    "copy_accession_number": row.copy.accession_number,
                    "due_date": row.due_date.isoformat() if row.due_date else None,
                    "overdue_days": overdue_days,
                }
            )
        return Response(payload, status=status.HTTP_200_OK)


class LibraryReportsFinesView(LibraryAccessMixin, APIView):
    def get(self, request):
        rows = FineRecord.objects.filter(is_active=True)
        totals = rows.aggregate(total=Sum("amount"), paid=Sum("amount_paid"))
        total = totals.get("total") or Decimal("0.00")
        paid = totals.get("paid") or Decimal("0.00")
        by_status = list(rows.values("status").annotate(count=Count("id"), amount=Sum("amount")).order_by("status"))
        return Response(
            {
                "total_fines": total,
                "total_paid": paid,
                "outstanding": total - paid,
                "pending_count": rows.filter(status="Pending").count(),
                "breakdown": by_status,
            },
            status=status.HTTP_200_OK,
        )


class LibraryReportsMemberActivityView(LibraryAccessMixin, APIView):
    def get(self, request):
        limit = int(request.query_params.get("limit") or 20)
        rows = (
            CirculationTransaction.objects.filter(is_active=True, transaction_type="Issue")
            .values("member_id", "member__member_id")
            .annotate(issues=Count("id"), last_issue=Max("issue_date"))
            .order_by("-issues", "-last_issue")[: max(1, min(limit, 100))]
        )
        return Response(
            [
                {
                    "member_id": row["member_id"],
                    "member_code": row["member__member_id"],
                    "issues": row["issues"],
                    "last_issue": row["last_issue"],
                }
                for row in rows
            ],
            status=status.HTTP_200_OK,
        )


class LibraryDashboardView(LibraryAccessMixin, APIView):
    """Aggregated dashboard statistics for the library module."""

    def get(self, request):
        today = date.today()

        total_resources = LibraryResource.objects.filter(is_active=True).count()
        total_copies = ResourceCopy.objects.filter(is_active=True).count()
        available_copies = ResourceCopy.objects.filter(is_active=True, status="Available").count()
        borrowed_copies = ResourceCopy.objects.filter(is_active=True, status="Issued").count()

        overdue_count = CirculationTransaction.objects.filter(
            return_date__isnull=True, due_date__lt=today
        ).count()

        total_members = LibraryMember.objects.filter(is_active=True).count()

        # Recent transactions (last 6)
        recent_txns = (
            CirculationTransaction.objects
            .select_related("copy__resource", "member")
            .order_by("-issue_date")[:6]
        )
        recent_activity = []
        for txn in recent_txns:
            recent_activity.append({
                "id": txn.id,
                "member": str(txn.member),
                "book": txn.copy.resource.title if txn.copy else "",
                "action": "Returned" if txn.return_date else "Borrowed",
                "date": str(txn.return_date or txn.issue_date),
            })

        # Top 5 popular resources
        popular_raw = (
            CirculationTransaction.objects
            .values("copy__resource__id", "copy__resource__title",
                    "copy__resource__authors")
            .annotate(borrow_count=Count("id"))
            .order_by("-borrow_count")[:5]
        )
        popular = [
            {
                "id": row["copy__resource__id"],
                "title": row["copy__resource__title"],
                "authors": row["copy__resource__authors"],
                "borrow_count": row["borrow_count"],
            }
            for row in popular_raw
        ]

        return Response({
            "total_resources": total_resources,
            "total_copies": total_copies,
            "available_copies": available_copies,
            "borrowed_copies": borrowed_copies,
            "overdue_count": overdue_count,
            "total_members": total_members,
            "recent_activity": recent_activity,
            "popular_resources": popular,
        })
