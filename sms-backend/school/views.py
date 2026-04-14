from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.conf import settings
from django.core.cache import cache
from django.db.models import Sum, Count, Q
from django.db import models
from django.db import connection
from django.http import HttpResponse
from django.utils import timezone
from django.contrib.auth import authenticate, get_user_model
from psycopg2 import sql as pgsql
from datetime import datetime, timedelta
import hashlib
import hmac
import json
import csv
import os
import re
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView as _BaseTokenView

from .models import (
    Student, Guardian, Invoice, Payment, Enrollment, AdmissionApplication,
    FeeStructure, Expense, Budget, InvoiceLineItem, AttendanceRecord, BehaviorIncident,
    FeeAssignment, InvoiceAdjustment, Module, UserModuleAssignment,
    Role, UserProfile, AdmissionDocument, StudentDocument,
    Department,
    MedicalRecord, ImmunizationRecord, ClinicVisit, SchoolProfile,
    PaymentReversalRequest, InvoiceInstallmentPlan, InvoiceInstallment, LateFeeRule, FeeReminderLog,
    InvoiceWriteOffRequest,
    ScholarshipAward, OptionalCharge, StudentOptionalCharge,
    AccountingPeriod, ChartOfAccount, JournalEntry, JournalLine,
    PaymentGatewayTransaction, PaymentGatewayWebhookEvent, BankStatementLine,
    VoteHead, VoteHeadPaymentAllocation, CashbookEntry, BalanceCarryForward,
    DispensaryVisit, DispensaryPrescription, DispensaryStock,
    DispensaryDeliveryNote, DispensaryDeliveryItem,
    InstitutionLifecycleTemplate, InstitutionLifecycleRun, InstitutionLifecycleTaskRun,
)
from hr.models import Staff
from academics.models import AcademicYear, Term, SchoolClass
from communication.models import Message
from communication.services import send_email_placeholder, send_sms_placeholder
from reporting.models import AuditLog
from .control_plane import build_control_plane_summary

# ---------------------------------------------------------------------------
# CSV formula-injection defence
# ---------------------------------------------------------------------------
_CSV_INJECTION_CHARS = ('=', '+', '-', '@', '\t', '\r')

def _csv_safe(value):
    """Prefix any cell that starts with a formula-injection character with a
    single quote so spreadsheet applications treat it as plain text."""
    s = str(value) if value is not None else ''
    if s and s[0] in _CSV_INJECTION_CHARS:
        return "'" + s
    return s


class _SafeCsvWriter:
    """Drop-in replacement for csv.writer that sanitises every cell value
    against CSV formula injection before writing."""
    def __init__(self, *args, **kwargs):
        self._writer = csv.writer(*args, **kwargs)

    def writerow(self, row):
        return self._writer.writerow([_csv_safe(v) for v in row])

    def writerows(self, rows):
        return self._writer.writerows([[_csv_safe(v) for v in row] for row in rows])


from .serializers import (
    ExpenseSerializer, StaffSerializer,
    StudentSerializer, InvoiceSerializer, PaymentSerializer,
    EnrollmentSerializer, TermSerializer, FeeStructureSerializer,
    BudgetSerializer,
    FeeAssignmentSerializer, InvoiceAdjustmentSerializer,
    ScholarshipAwardSerializer,
    OptionalChargeSerializer, StudentOptionalChargeSerializer,
    PaymentReversalRequestSerializer, InvoiceInstallmentPlanSerializer,
    InvoiceInstallmentSerializer, LateFeeRuleSerializer, FeeReminderLogSerializer,
    InvoiceWriteOffRequestSerializer,
    AccountingPeriodSerializer, ChartOfAccountSerializer, JournalEntrySerializer,
    PaymentGatewayTransactionSerializer, PaymentGatewayWebhookEventSerializer, BankStatementLineSerializer,
    ModuleSerializer, UserModuleAssignmentSerializer, TenantModuleSerializer, ModuleSettingSerializer,
    AdmissionApplicationSerializer, StudentDocumentSerializer,
    FinanceStudentRefSerializer, FinanceEnrollmentRefSerializer,
    AttendanceRecordSerializer, BehaviorIncidentSerializer,
    MedicalRecordSerializer, ImmunizationRecordSerializer, ClinicVisitSerializer,
    SchoolProfileSerializer,
    InstitutionSecurityPolicySerializer,
    InstitutionLifecycleTemplateSerializer,
    InstitutionLifecycleRunSerializer,
    InstitutionLifecycleRunDetailSerializer,
    VoteHeadSerializer, VoteHeadPaymentAllocationSerializer,
    CashbookEntrySerializer, BalanceCarryForwardSerializer,
    DispensaryVisitSerializer, DispensaryPrescriptionSerializer, DispensaryStockSerializer,
    DepartmentSerializer,
    HrDepartmentSerializer,
)
from domains.inventory.application.services import get_store_module_summary


_STORAGE_SUFFIX_PATTERN = re.compile(r"^(?P<base>.+)_[A-Za-z0-9]{7}(?P<ext>\.[^./\\]+)$")


def _display_document_name(file_field) -> str:
    if not file_field:
        return ""
    raw_name = os.path.basename(getattr(file_field, "name", "") or "")
    match = _STORAGE_SUFFIX_PATTERN.match(raw_name)
    if match:
        return f"{match.group('base')}{match.group('ext')}"
    return raw_name
from communication.serializers import MessageSerializer
from reporting.serializers import AuditLogSerializer
from .services import (
    FinanceService, StudentsService, AcademicsService, HrService,
    CommunicationService, CoreService, ReportingService, TenantModuleSettingsService
)
from .pagination import FinanceResultsPagination
from .permissions import (
    CanManageModuleSettings,
    CanManageSystemSettings,
    HasModuleAccess,
    IsAccountant,
    IsSchoolAdmin,
    IsTeacher,
)
from .module_focus import is_module_allowed, module_focus_lock_enabled, module_focus_keys
from .lifecycle_automation import (
    LifecycleAutomationError,
    complete_lifecycle_run,
    complete_task_run,
    create_lifecycle_run,
    ensure_lifecycle_templates,
    refresh_lifecycle_run,
    start_lifecycle_run,
    waive_task_run,
)
from .security_policy import (
    extract_security_policy_payload,
    get_or_create_security_policy,
)


def _role_name(user):
    profile = getattr(user, 'userprofile', None)
    role = getattr(profile, 'role', None)
    return getattr(role, 'name', '')


def _requires_password_change(user):
    profile = getattr(user, 'userprofile', None)
    return bool(getattr(profile, 'force_password_change', False))


def _is_admin_like(user):
    return _role_name(user) in {'ADMIN', 'TENANT_SUPER_ADMIN'}


def _approval_threshold():
    return 10000


def _active_school_profile():
    return SchoolProfile.objects.filter(is_active=True).first()


def _resolve_admission_number_mode(profile: SchoolProfile | None) -> tuple[str, str, int]:
    mode = "AUTO"
    prefix = "ADM-"
    padding = 4
    if profile:
        mode = (profile.admission_number_mode or "AUTO").upper()
        prefix = (profile.admission_number_prefix or "ADM-").strip() or "ADM-"
        padding = profile.admission_number_padding or 4
    if mode not in {"AUTO", "MANUAL"}:
        mode = "AUTO"
    if padding < 1:
        padding = 1
    return mode, prefix, padding


def _generate_next_admission_number(prefix: str, padding: int) -> str:
    max_number = 0
    for value in Student.objects.filter(admission_number__startswith=prefix).values_list("admission_number", flat=True):
        suffix = str(value or "")[len(prefix):]
        if suffix.isdigit():
            max_number = max(max_number, int(suffix))
    next_number = max_number + 1
    return f"{prefix}{str(next_number).zfill(padding)}"


def _resolve_student_admission_number(requested: str | None) -> str:
    profile = _active_school_profile()
    mode, prefix, padding = _resolve_admission_number_mode(profile)
    candidate = (requested or "").strip()

    if mode == "MANUAL":
        if not candidate:
            raise ValidationError(
                {
                    "admission_number": "admission_number is required when admission number mode is MANUAL."
                }
            )
        return candidate

    if candidate:
        return candidate

    auto_candidate = _generate_next_admission_number(prefix, padding)
    while Student.objects.filter(admission_number=auto_candidate).exists():
        auto_candidate = _generate_next_admission_number(prefix, padding)
    return auto_candidate


def _sync_library_member_for_student(student: Student) -> None:
    try:
        from library.models import LibraryMember
    except Exception:
        return

    member_code = f"LIB-STU-{student.id}"
    member = (
        LibraryMember.objects.filter(student=student).first()
        or LibraryMember.objects.filter(member_id=member_code).first()
    )
    if member:
        changed_fields = []
        if member.student_id != student.id:
            member.student = student
            changed_fields.append("student")
        if member.member_type != "Student":
            member.member_type = "Student"
            changed_fields.append("member_type")
        if not member.is_active:
            member.is_active = True
            changed_fields.append("is_active")
        if member.status != "Active":
            member.status = "Active"
            changed_fields.append("status")
        if changed_fields:
            member.save(update_fields=changed_fields)
        return

    LibraryMember.objects.create(
        member_id=member_code,
        member_type="Student",
        status="Active",
        student=student,
        is_active=True,
    )

# ... existing ViewSets

class TermViewSet(viewsets.ModelViewSet):
    queryset = Term.objects.filter(is_active=True)
    serializer_class = TermSerializer
    permission_classes = [IsSchoolAdmin, HasModuleAccess]
    module_key = "ACADEMICS"

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()

class FeeStructureViewSet(viewsets.ModelViewSet):
    queryset = FeeStructure.objects.all()
    serializer_class = FeeStructureSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        queryset = super().get_queryset().select_related('academic_year', 'term', 'grade_level')
        search = self.request.query_params.get('search')
        category = self.request.query_params.get('category')
        is_active = self.request.query_params.get('is_active')

        if search:
            queryset = queryset.filter(name__icontains=search)
        if category:
            queryset = queryset.filter(category__iexact=category)
        if is_active is not None:
            normalized = str(is_active).lower()
            if normalized in ('true', '1'):
                queryset = queryset.filter(is_active=True)
            elif normalized in ('false', '0'):
                queryset = queryset.filter(is_active=False)

        return queryset.order_by('-id')

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()

class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [IsSchoolAdmin | IsTeacher, HasModuleAccess]
    module_key = "STUDENTS"
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        # Phase 18: prefetch guardians to eliminate N+1 on student detail pages
        queryset = Student.objects.prefetch_related('guardians').order_by('-id')
        search = (self.request.query_params.get('search') or '').strip()
        gender = (self.request.query_params.get('gender') or '').strip()
        is_active = self.request.query_params.get('is_active')

        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(admission_number__icontains=search)
            )
        if gender:
            queryset = queryset.filter(gender=gender)
        if is_active is not None and str(is_active).strip() != '':
            normalized = str(is_active).lower()
            if normalized in ('true', '1'):
                queryset = queryset.filter(is_active=True)
            elif normalized in ('false', '0'):
                queryset = queryset.filter(is_active=False)
        return queryset

    def perform_create(self, serializer):
        requested_admission_number = serializer.validated_data.get("admission_number")
        admission_number = _resolve_student_admission_number(requested_admission_number)
        if Student.objects.filter(admission_number=admission_number).exists():
            raise ValidationError({"admission_number": "Admission number already exists."})
        student = serializer.save(admission_number=admission_number)
        _sync_library_member_for_student(student)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()

    def perform_update(self, serializer):
        instance = serializer.instance
        if not instance.is_active:
            raise ValidationError("Inactive/graduated student records are read-only.")
        serializer.save()

    @action(detail=True, methods=['post'], url_path='graduate')
    def graduate(self, request, pk=None):
        student = self.get_object()
        student.is_active = False
        student.save(update_fields=['is_active'])
        Enrollment.objects.filter(student=student, is_active=True).update(
            is_active=False,
            status='Completed',
            left_date=timezone.now().date(),
        )
        AuditLog.objects.create(
            user_id=request.user.id if getattr(request.user, "is_authenticated", False) else None,
            action="GRADUATE",
            model_name="Student",
            object_id=str(student.id),
            details=f"Student {student.admission_number} marked as graduated/inactive.",
        )
        return Response({"message": "Student graduated successfully.", "student_id": student.id}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='photo')
    def upload_photo(self, request, pk=None):
        student = self.get_object()
        photo = request.data.get('photo')
        if not photo:
            return Response({"error": "photo is required"}, status=status.HTTP_400_BAD_REQUEST)
        student.photo = photo
        student.save(update_fields=['photo'])
        return Response({"id": student.id, "photo": student.photo.url}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='documents')
    def upload_documents(self, request, pk=None):
        student = self.get_object()
        files = request.FILES.getlist('documents')
        if not files:
            return Response({"error": "documents are required"}, status=status.HTTP_400_BAD_REQUEST)
        created = []
        for upload in files:
            doc = StudentDocument.objects.create(student=student, file=upload)
            created.append({"id": doc.id, "name": doc.file.name, "url": doc.file.url})
        return Response({"documents": created}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path='documents/(?P<doc_id>[^/.]+)')
    def delete_document(self, request, pk=None, doc_id=None):
        student = self.get_object()
        try:
            doc = StudentDocument.objects.get(id=doc_id, student=student)
        except StudentDocument.DoesNotExist:
            return Response({"error": "Document not found"}, status=status.HTTP_404_NOT_FOUND)
        doc.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='documents')
    def documents(self, request):
        queryset = _student_documents_queryset(request)
        page = self.paginate_queryset(queryset)
        target = page if page is not None else queryset

        rows = []
        for doc in target:
            file_url = doc.file.url if doc.file else ''
            rows.append(
                {
                    "id": doc.id,
                    "student_id": doc.student_id,
                    "student_name": f"{doc.student.first_name} {doc.student.last_name}".strip(),
                    "admission_number": doc.student.admission_number,
                    "file_name": _display_document_name(doc.file),
                    "url": request.build_absolute_uri(file_url) if file_url else '',
                    "uploaded_at": doc.uploaded_at,
                }
            )
        if page is not None:
            return self.get_paginated_response(rows)
        return Response({"count": len(rows), "results": rows}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get', 'post'], url_path='guardians')
    def guardians(self, request, pk=None):
        """
        GET  /students/{id}/guardians/  — list guardians for this student
        POST /students/{id}/guardians/  — add a guardian to this student
        """
        student = self.get_object()
        if request.method == 'GET':
            qs = Guardian.objects.filter(student=student, is_active=True)
            return Response([
                {'id': g.id, 'name': g.name, 'relationship': g.relationship,
                 'phone': g.phone, 'email': g.email}
                for g in qs
            ])
        # POST — create a new guardian
        name = (request.data.get('name') or '').strip()
        if not name:
            return Response({'error': 'Guardian name is required.'}, status=status.HTTP_400_BAD_REQUEST)
        guardian = Guardian.objects.create(
            student=student,
            name=name,
            relationship=(request.data.get('relationship') or 'Guardian').strip(),
            phone=(request.data.get('phone') or '').strip(),
            email=(request.data.get('email') or '').strip(),
            is_active=True,
        )
        AuditLog.objects.create(
            user_id=request.user.id if getattr(request.user, 'is_authenticated', False) else None,
            action='CREATE',
            model_name='Guardian',
            object_id=str(guardian.id),
            details=f'Guardian "{guardian.name}" added to student {student.admission_number}.',
        )
        return Response(
            {'id': guardian.id, 'name': guardian.name, 'relationship': guardian.relationship,
             'phone': guardian.phone, 'email': guardian.email},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='create-login')
    def create_login(self, request, pk=None):
        """
        POST /students/{id}/create-login/
        Creates (or re-activates) a Django login account for the student.
        Returns: { created, username, message }
        """
        student = self.get_object()
        from django.contrib.auth.models import User as DjangoUser
        username = student.admission_number
        password = (request.data.get('password') or username)

        student_role = Role.objects.filter(name='STUDENT').first()
        user, created = DjangoUser.objects.get_or_create(
            username=username,
            defaults={
                'first_name': student.first_name,
                'last_name': student.last_name,
                'is_active': True,
            },
        )
        if created:
            user.set_password(password)
            user.save()
        else:
            # Always reset password + re-enable on explicit create-login call
            user.set_password(password)
            user.is_active = True
            user.first_name = student.first_name
            user.last_name = student.last_name
            user.save()

        if student_role:
            profile, _ = UserProfile.objects.get_or_create(
                user=user,
                defaults={'role': student_role, 'admission_number': username},
            )
            profile_updates = []
            if profile.role_id != student_role.id:
                profile.role = student_role
                profile_updates.append('role')
            if profile.admission_number != username:
                profile.admission_number = username
                profile_updates.append('admission_number')
            if profile.force_password_change:
                profile.force_password_change = False
                profile_updates.append('force_password_change')
            if profile_updates:
                profile.save(update_fields=profile_updates)

        AuditLog.objects.create(
            user_id=request.user.id if getattr(request.user, 'is_authenticated', False) else None,
            action='CREATE_LOGIN',
            model_name='Student',
            object_id=str(student.id),
            details=f'Portal login account {"created" if created else "verified"} for student {username}.',
        )
        return Response({
            'created': created,
            'username': username,
            'password_hint': password,
            'message': f'Login account {"created" if created else "reset"} for {username}.',
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


def _journal_get_or_create_account(code, name, account_type):
    """Find or create a Chart of Account entry for auto-journaling."""
    try:
        account, _ = ChartOfAccount.objects.get_or_create(
            code=code,
            defaults={'name': name, 'account_type': account_type, 'is_active': True},
        )
        return account
    except Exception:
        return None


def _auto_post_journal(entry_key, entry_date, memo, source_type, source_id, lines):
    """
    Create a balanced double-entry journal entry.
    `lines` is a list of (account, debit, credit, description) tuples.
    Skips silently if already posted or if any account is None.
    """
    try:
        if JournalEntry.objects.filter(entry_key=entry_key).exists():
            return
        if any(acct is None for acct, _, _, _ in lines):
            return
        entry = JournalEntry.objects.create(
            entry_date=entry_date,
            memo=memo,
            source_type=source_type,
            source_id=source_id,
            entry_key=entry_key,
        )
        for account, debit, credit, desc in lines:
            JournalLine.objects.create(
                entry=entry,
                account=account,
                debit=debit,
                credit=credit,
                description=desc,
            )
    except Exception:
        pass


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.filter(is_active=True)
    serializer_class = InvoiceSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    http_method_names = ['get', 'post', 'delete', 'head', 'options'] # Disable PUT/PATCH (Immutability)
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        queryset = super().get_queryset().select_related('student', 'term')
        search = self.request.query_params.get('search')
        status_param = self.request.query_params.get('status')
        student = self.request.query_params.get('student')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')

        if status_param:
            queryset = queryset.filter(status=status_param)
        if student:
            queryset = queryset.filter(student_id=student)
        if date_from:
            queryset = queryset.filter(invoice_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(invoice_date__lte=date_to)
        if search:
            query = (
                models.Q(student__admission_number__icontains=search)
                | models.Q(student__first_name__icontains=search)
                | models.Q(student__last_name__icontains=search)
            )
            digits = ''.join(ch for ch in str(search) if ch.isdigit())
            if digits:
                query |= models.Q(id=int(digits))
            queryset = queryset.filter(query)

        return queryset.order_by('-invoice_date', '-id')

    def perform_destroy(self, instance):
        # "Void" the invoice efficiently by hiding it
        instance.is_active = False
        instance.save()

    def create(self, request, *args, **kwargs):
        """ 
        Override create to use FinanceService.
        Expected Payload:
        {
            "student": 1,
            "term": 1,
            "due_date": "2023-12-31",
            "line_items": [
                {"fee_structure": 1, "amount": 500.00, "description": "Tuition"},
                {"fee_structure": 2, "amount": 100.00, "description": "Lab"}
            ]
        }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Extract data safely
        student = serializer.validated_data.get('student')
        term = serializer.validated_data.get('term')
        line_items = serializer.validated_data.get('line_items')
        due_date = serializer.validated_data.get('due_date')

        missing_fields = [
            field
            for field, value in {
                "student": student,
                "term": term,
                "due_date": due_date,
                "line_items": line_items,
            }.items()
            if not value
        ]

        if missing_fields:
            return Response(
                {
                    "error": "Required fields are missing.",
                    "missing": missing_fields,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Call Service
        try:
            invoice = FinanceService.create_invoice(
                student=student,
                term=term,
                line_items_data=line_items,
                due_date=due_date,
                status=serializer.validated_data.get('status'),
                is_active=serializer.validated_data.get('is_active'),
            )
            # IPSAS: Auto double-entry journal — DR Accounts Receivable / CR Revenue
            total = sum(float(li.get('amount', 0)) for li in line_items) if line_items else 0
            if total > 0:
                ar = _journal_get_or_create_account('1100', 'Accounts Receivable', 'ASSET')
                rev = _journal_get_or_create_account('4000', 'Tuition & Fees Revenue', 'REVENUE')
                _auto_post_journal(
                    entry_key=f"INV-{invoice.id}",
                    entry_date=invoice.issue_date or invoice.created_at.date(),
                    memo=f"Invoice INV-{invoice.id} – Student {invoice.student_id}",
                    source_type='Invoice',
                    source_id=invoice.id,
                    lines=[
                        (ar, total, 0, 'Accounts Receivable'),
                        (rev, 0, total, 'Tuition & Fees Revenue'),
                    ],
                )
            # Return the created invoice
            response_serializer = self.get_serializer(invoice)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='status')
    def update_status(self, request, pk=None):
        invoice = self.get_object()
        target = request.data.get('status')
        if not target:
            return Response({"error": "status is required"}, status=status.HTTP_400_BAD_REQUEST)
        target = str(target).upper()

        allowed = {
            'DRAFT': {'ISSUED', 'VOID', 'CONFIRMED'},
            'CONFIRMED': {'ISSUED', 'VOID'},
            'ISSUED': {'PARTIALLY_PAID', 'PAID', 'OVERDUE', 'VOID'},
            'PARTIALLY_PAID': {'PAID', 'OVERDUE', 'VOID'},
            'OVERDUE': {'PARTIALLY_PAID', 'PAID', 'VOID'},
            'PAID': {'VOID'},
            'VOID': set(),
        }

        if invoice.status == 'PAID' and target == 'VOID' and not _is_admin_like(request.user):
            return Response({"error": "Only admin can void paid invoices."}, status=status.HTTP_403_FORBIDDEN)
        if target not in allowed.get(invoice.status, set()):
            return Response(
                {"error": f"Invalid transition from {invoice.status} to {target}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invoice.status = target
        invoice.save(update_fields=['status'])
        return Response(self.get_serializer(invoice).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='issue')
    def issue(self, request, pk=None):
        invoice = self.get_object()
        if invoice.status not in {'DRAFT', 'CONFIRMED'}:
            return Response({"error": "Only draft/confirmed invoices can be issued."}, status=status.HTTP_400_BAD_REQUEST)
        invoice.status = 'ISSUED'
        invoice.save(update_fields=['status'])
        return Response(self.get_serializer(invoice).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='generate-batch')
    def generate_batch(self, request):
        term_id = request.data.get('term')
        due_date = request.data.get('due_date')
        class_id = request.data.get('class_id')
        grade_level_id = request.data.get('grade_level_id')
        issue_immediately = bool(request.data.get('issue_immediately', True))

        if not term_id or not due_date:
            return Response({"error": "term and due_date are required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            due_date_value = datetime.fromisoformat(str(due_date)).date()
        except ValueError:
            return Response({"error": "Invalid due_date"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            # Finance invoices still persist against the finance-side term model.
            term = Invoice._meta.get_field('term').remote_field.model.objects.get(id=term_id)
            result = FinanceService.generate_invoices_from_assignments(
                term=term,
                due_date=due_date_value,
                class_id=class_id,
                grade_level_id=grade_level_id,
                issue_immediately=issue_immediately,
            )
            return Response(result, status=status.HTTP_200_OK)
        except Term.DoesNotExist:
            return Response({"error": "Invalid term"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get', 'post'], url_path='installments')
    def create_installment_plan(self, request, pk=None):
        invoice = self.get_object()
        if request.method.lower() == 'get':
            plan = getattr(invoice, 'installment_plan', None)
            if not plan:
                return Response({"invoice": invoice.id, "installment_count": 0, "installments": []}, status=status.HTTP_200_OK)
            serializer = InvoiceInstallmentPlanSerializer(plan)
            return Response(serializer.data, status=status.HTTP_200_OK)
        installment_count = int(request.data.get('installment_count', 0))
        due_dates = request.data.get('due_dates') or []
        if not installment_count or not isinstance(due_dates, list):
            return Response(
                {"error": "installment_count and due_dates[] are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            plan = FinanceService.create_installment_plan(
                invoice=invoice,
                installment_count=installment_count,
                due_dates=due_dates,
                created_by=request.user,
            )
            serializer = InvoiceInstallmentPlanSerializer(plan)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='send-reminder')
    def send_reminder(self, request, pk=None):
        invoice = self.get_object()
        channel = str(request.data.get('channel') or 'EMAIL').upper()
        recipient = request.data.get('recipient')
        if channel not in {'EMAIL', 'SMS', 'INAPP'}:
            return Response({"error": "Unsupported channel"}, status=status.HTTP_400_BAD_REQUEST)
        result = FinanceService.send_invoice_reminder(
            invoice=invoice,
            channel=channel,
            recipient_override=recipient,
        )
        if result.get('error'):
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_200_OK)

class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.filter(is_active=True)
    serializer_class = PaymentSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    http_method_names = ['get', 'post', 'delete', 'head', 'options'] # Disable PUT/PATCH
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        queryset = super().get_queryset().select_related('student')
        search = self.request.query_params.get('search')
        student = self.request.query_params.get('student')
        payment_method = self.request.query_params.get('payment_method')
        allocation_status = self.request.query_params.get('allocation_status')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')

        if student:
            queryset = queryset.filter(student_id=student)
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)
        if date_from:
            queryset = queryset.filter(payment_date__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(payment_date__date__lte=date_to)
        if search:
            queryset = queryset.filter(
                models.Q(reference_number__icontains=search)
                | models.Q(receipt_number__icontains=search)
                | models.Q(invoice_number__icontains=search)
                | models.Q(payment_method__icontains=search)
                | models.Q(student__first_name__icontains=search)
                | models.Q(student__last_name__icontains=search)
                | models.Q(student__admission_number__icontains=search)
                | models.Q(allocations__invoice__invoice_number__icontains=search)
            ).distinct()
        if allocation_status in {'allocated', 'partial', 'unallocated'}:
            queryset = queryset.annotate(allocated_total=Sum('allocations__amount_allocated'))
            if allocation_status == 'allocated':
                queryset = queryset.filter(allocated_total__gte=models.F('amount'))
            elif allocation_status == 'partial':
                queryset = queryset.filter(allocated_total__gt=0, allocated_total__lt=models.F('amount'))
            elif allocation_status == 'unallocated':
                queryset = queryset.filter(models.Q(allocated_total__isnull=True) | models.Q(allocated_total=0))

        return queryset.order_by('-payment_date', '-id')

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()

    def create(self, request, *args, **kwargs):
        """
        Records a payment.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            payment = FinanceService.record_payment(
                student=serializer.validated_data['student'],
                amount=serializer.validated_data['amount'],
                payment_method=serializer.validated_data['payment_method'],
                reference_number=serializer.validated_data['reference_number'],
                notes=serializer.validated_data.get('notes', '')
            )
            # IPSAS: Auto double-entry journal — DR Cash & Bank / CR Accounts Receivable
            amount = float(payment.amount or 0)
            if amount > 0:
                cash = _journal_get_or_create_account('1000', 'Cash and Bank', 'ASSET')
                ar = _journal_get_or_create_account('1100', 'Accounts Receivable', 'ASSET')
                _auto_post_journal(
                    entry_key=f"PAY-{payment.id}",
                    entry_date=payment.payment_date or payment.created_at.date(),
                    memo=f"Payment {payment.receipt_number or payment.id} – {payment.payment_method}",
                    source_type='Payment',
                    source_id=payment.id,
                    lines=[
                        (cash, amount, 0, 'Cash received'),
                        (ar, 0, amount, 'Accounts Receivable cleared'),
                    ],
                )
            response_serializer = self.get_serializer(payment)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def allocate(self, request, pk=None):
        """
        Custom Action: /api/payments/{id}/allocate/
        Payload: { "invoice_id": 5, "amount": 200.00 }
        """
        payment = self.get_object()
        invoice_id = request.data.get('invoice_id')
        installment_id = request.data.get('installment_id')
        amount = request.data.get('amount')
        if not invoice_id or amount is None:
            return Response({"error": "invoice_id and amount are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from .models import Invoice
            invoice = Invoice.objects.get(id=invoice_id, is_active=True)
            if installment_id:
                installment = InvoiceInstallment.objects.select_related('plan__invoice').get(
                    id=installment_id,
                    plan__invoice_id=invoice.id,
                )
                FinanceService.allocate_payment_to_installment(payment, installment, amount)
            else:
                FinanceService.allocate_payment(payment, invoice, amount)
            
            return Response({"message": "Allocation successful"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='auto-allocate')
    def auto_allocate(self, request, pk=None):
        payment = self.get_object()
        try:
            result = FinanceService.auto_allocate_payment(payment)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], url_path='receipt')
    def receipt(self, request, pk=None):
        payment = self.get_object()
        lines = [
            f"Receipt: {payment.receipt_number or 'N/A'}",
            f"Reference: {payment.reference_number}",
            f"Student: {payment.student}",
            f"Amount: {payment.amount}",
            f"Method: {payment.payment_method}",
            f"Date: {payment.payment_date}",
            f"Status: {'Reversed' if not payment.is_active else 'Active'}",
        ]
        content = "\n".join(lines)
        response = HttpResponse(content, content_type="text/plain")
        response["Content-Disposition"] = f'attachment; filename="receipt_{payment.id}.txt"'
        return response

    @action(detail=True, methods=['post'], url_path='reversal-request')
    def reversal_request(self, request, pk=None):
        payment = self.get_object()
        reason = (request.data.get('reason') or '').strip()
        if not reason:
            return Response({"error": "reason is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            reversal = FinanceService.request_payment_reversal(
                payment=payment,
                reason=reason,
                requested_by=request.user,
            )
            return Response(PaymentReversalRequestSerializer(reversal).data, status=status.HTTP_201_CREATED)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='reverse-approve')
    def reverse_approve(self, request, pk=None):
        if not _is_admin_like(request.user):
            return Response({"error": "Only admin can approve reversals."}, status=status.HTTP_403_FORBIDDEN)
        payment = self.get_object()
        reversal = payment.reversal_requests.filter(status='PENDING').order_by('-requested_at').first()
        if not reversal:
            return Response({"error": "No pending reversal request found."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            FinanceService.approve_payment_reversal(
                reversal_request=reversal,
                reviewed_by=request.user,
                review_notes=request.data.get('review_notes', ''),
            )
            return Response({"message": "Payment reversed successfully."}, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='reverse-reject')
    def reverse_reject(self, request, pk=None):
        if not _is_admin_like(request.user):
            return Response({"error": "Only admin can reject reversals."}, status=status.HTTP_403_FORBIDDEN)
        payment = self.get_object()
        reversal = payment.reversal_requests.filter(status='PENDING').order_by('-requested_at').first()
        if not reversal:
            return Response({"error": "No pending reversal request found."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            FinanceService.reject_payment_reversal(
                reversal_request=reversal,
                reviewed_by=request.user,
                review_notes=request.data.get('review_notes', ''),
            )
            return Response({"message": "Reversal request rejected."}, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        # ==========================================
class EnrollmentViewSet(viewsets.ModelViewSet):
    queryset = Enrollment.objects.filter(is_active=True)
    serializer_class = EnrollmentSerializer
    permission_classes = [IsSchoolAdmin | IsTeacher, HasModuleAccess]
    module_key = "STUDENTS"

    def get_queryset(self):
        qs = super().get_queryset()
        class_id = self.request.query_params.get('school_class_id')
        term_id = self.request.query_params.get('term_id')
        student_id = self.request.query_params.get('student_id')
        if class_id:
            qs = qs.filter(school_class_id=class_id)
        if term_id:
            qs = qs.filter(term_id=term_id)
        if student_id:
            qs = qs.filter(student_id=student_id)
        return qs.select_related('student', 'school_class', 'term')

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()
        
class StaffViewSet(viewsets.ModelViewSet):
    queryset = Staff.objects.filter(is_active=True)
    serializer_class = StaffSerializer
    permission_classes = [IsSchoolAdmin, HasModuleAccess]
    module_key = "HR"

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response["Warning"] = "299 - Deprecated; use /api/hr/staff/"
        return response

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        response["Warning"] = "299 - Deprecated; use /api/hr/staff/"
        return response

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()

class AttendanceRecordViewSet(viewsets.ModelViewSet):
    queryset = AttendanceRecord.objects.all().order_by('-date', '-created_at')
    serializer_class = AttendanceRecordSerializer
    permission_classes = [IsSchoolAdmin | IsTeacher, HasModuleAccess]
    module_key = "STUDENTS"
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        student_id = self.request.query_params.get('student_id') or self.request.query_params.get('student')
        status_param = self.request.query_params.get('status')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')

        if student_id:
            queryset = queryset.filter(student_id=student_id)
        if status_param:
            queryset = queryset.filter(status=status_param)
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        return queryset

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)

    @action(detail=False, methods=['post'], url_path='batch')
    def batch_create(self, request):
        date_str = request.data.get('date')
        records = request.data.get('records', [])
        if not date_str or not records:
            return Response({'error': 'date and records are required'}, status=status.HTTP_400_BAD_REQUEST)
        results = []
        for rec in records:
            try:
                obj, created = AttendanceRecord.objects.update_or_create(
                    student_id=rec['student_id'],
                    date=date_str,
                    defaults={
                        'status': rec.get('status', 'Present'),
                        'notes': rec.get('notes', ''),
                        'recorded_by': request.user,
                    }
                )
                results.append({'id': obj.id, 'student_id': obj.student_id, 'status': obj.status, 'created': created})
            except Exception:
                pass
        return Response({'count': len(results), 'records': results}, status=status.HTTP_201_CREATED)

class SchoolClassListView(APIView):
    permission_classes = [IsSchoolAdmin | IsTeacher]

    def get(self, request):
        classes = SchoolClass.objects.filter(is_active=True).select_related('academic_year', 'grade_level')
        data = [{'id': c.id, 'name': c.display_name, 'stream': c.stream, 'section': c.section_name} for c in classes]
        return Response(data)

class AttendanceSummaryView(APIView):
    permission_classes = [IsSchoolAdmin | IsTeacher, HasModuleAccess]
    module_key = "STUDENTS"

    def get(self, request):
        student_id = request.query_params.get('student_id')
        queryset = AttendanceRecord.objects.all()
        if student_id:
            queryset = queryset.filter(student_id=student_id)

        total = queryset.count()
        present = queryset.filter(status='Present').count()
        absent = queryset.filter(status='Absent').count()
        late = queryset.filter(status='Late').count()

        attendance_rate = round((present / total) * 100, 2) if total else 0

        return Response({
            "attendance_rate": attendance_rate,
            "present": present,
            "absent": absent,
            "late": late,
            "period_label": "All time"
        }, status=status.HTTP_200_OK)

class BehaviorIncidentViewSet(viewsets.ModelViewSet):
    queryset = BehaviorIncident.objects.all().order_by('-incident_date', '-created_at')
    serializer_class = BehaviorIncidentSerializer
    permission_classes = [IsSchoolAdmin | IsTeacher, HasModuleAccess]
    module_key = "STUDENTS"
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        student_id = self.request.query_params.get('student_id') or self.request.query_params.get('student')
        incident_type = self.request.query_params.get('incident_type')
        severity = self.request.query_params.get('severity')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')

        if student_id:
            queryset = queryset.filter(student_id=student_id)
        if incident_type:
            queryset = queryset.filter(incident_type=incident_type)
        if severity:
            queryset = queryset.filter(severity=severity)
        if date_from:
            queryset = queryset.filter(incident_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(incident_date__lte=date_to)
        return queryset

    def perform_create(self, serializer):
        serializer.save(reported_by=self.request.user)

class MedicalRecordViewSet(viewsets.ModelViewSet):
    queryset = MedicalRecord.objects.all().order_by('-updated_at')
    serializer_class = MedicalRecordSerializer
    permission_classes = [IsSchoolAdmin | IsTeacher, HasModuleAccess]
    module_key = "STUDENTS"
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        student_id = self.request.query_params.get('student_id') or self.request.query_params.get('student')
        search = (self.request.query_params.get('search') or '').strip()
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        if search:
            queryset = queryset.filter(
                Q(student__admission_number__icontains=search)
                | Q(student__first_name__icontains=search)
                | Q(student__last_name__icontains=search)
                | Q(allergies__icontains=search)
                | Q(chronic_conditions__icontains=search)
                | Q(current_medications__icontains=search)
                | Q(doctor_name__icontains=search)
            )
        return queryset


class ImmunizationRecordViewSet(viewsets.ModelViewSet):
    queryset = ImmunizationRecord.objects.all().order_by('-date_administered', '-created_at')
    serializer_class = ImmunizationRecordSerializer
    permission_classes = [IsSchoolAdmin | IsTeacher, HasModuleAccess]
    module_key = "STUDENTS"
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        student_id = self.request.query_params.get('student_id') or self.request.query_params.get('student')
        search = (self.request.query_params.get('search') or '').strip()
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        if search:
            queryset = queryset.filter(
                Q(student__admission_number__icontains=search)
                | Q(student__first_name__icontains=search)
                | Q(student__last_name__icontains=search)
                | Q(vaccine_name__icontains=search)
            )
        if date_from:
            queryset = queryset.filter(date_administered__gte=date_from)
        if date_to:
            queryset = queryset.filter(date_administered__lte=date_to)
        return queryset


class ClinicVisitViewSet(viewsets.ModelViewSet):
    queryset = ClinicVisit.objects.all().order_by('-visit_date', '-created_at')
    serializer_class = ClinicVisitSerializer
    permission_classes = [IsSchoolAdmin | IsTeacher, HasModuleAccess]
    module_key = "STUDENTS"
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        student_id = self.request.query_params.get('student_id') or self.request.query_params.get('student')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        severity = self.request.query_params.get('severity')
        search = (self.request.query_params.get('search') or '').strip()
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        if date_from:
            queryset = queryset.filter(visit_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(visit_date__lte=date_to)
        if severity:
            queryset = queryset.filter(severity=severity)
        if search:
            queryset = queryset.filter(
                Q(student__admission_number__icontains=search)
                | Q(student__first_name__icontains=search)
                | Q(student__last_name__icontains=search)
                | Q(complaint__icontains=search)
                | Q(treatment__icontains=search)
            )
        return queryset

    def perform_create(self, serializer):
        serializer.save(attended_by=self.request.user)

class AdmissionApplicationViewSet(viewsets.ModelViewSet):
    queryset = AdmissionApplication.objects.all().order_by('-created_at')
    serializer_class = AdmissionApplicationSerializer
    permission_classes = [IsSchoolAdmin | IsTeacher, HasModuleAccess]
    module_key = "STUDENTS"
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        queryset = super().get_queryset()
        status_param = self.request.query_params.get('status')
        search = self.request.query_params.get('search')
        grade = self.request.query_params.get('grade')

        if status_param:
            queryset = queryset.filter(status=status_param)
        if grade:
            queryset = queryset.filter(applying_for_grade_id=grade)
        if search:
            queryset = queryset.filter(
                models.Q(application_number__icontains=search) |
                models.Q(student_first_name__icontains=search) |
                models.Q(student_last_name__icontains=search)
            )
        return queryset

    @action(detail=True, methods=['post'])
    def enroll(self, request, pk=None):
        """
        Converts an application into a Student + Enrollment.
        Payload: {
          "assign_admission_number": true,
          "admission_number": "ADM-1001" (optional),
          "school_class": 1,
          "term": 2,
          "enrollment_date": "2026-02-20"
        }
        """
        application = self.get_object()
        if application.student_id:
            return Response({"error": "Application already enrolled."}, status=status.HTTP_400_BAD_REQUEST)

        school_class = request.data.get('school_class')
        term = request.data.get('term')
        if not school_class or not term:
            return Response({"error": "school_class and term are required."}, status=status.HTTP_400_BAD_REQUEST)

        gender_map = {'Male': 'M', 'Female': 'F', 'M': 'M', 'F': 'F'}
        gender = gender_map.get(application.student_gender)
        if not gender:
            return Response({"error": "Invalid student gender in application."}, status=status.HTTP_400_BAD_REQUEST)

        requested_admission_number = request.data.get('admission_number')
        try:
            admission_number = _resolve_student_admission_number(requested_admission_number)
        except ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        if Student.objects.filter(admission_number=admission_number).exists():
            return Response({"error": "admission_number already exists."}, status=status.HTTP_400_BAD_REQUEST)

        student = Student.objects.create(
            first_name=application.student_first_name,
            last_name=application.student_last_name,
            date_of_birth=application.student_dob,
            admission_number=admission_number,
            gender=gender,
            is_active=True,
        )
        enrollment_date = request.data.get('enrollment_date')
        Enrollment.objects.create(
            student=student,
            school_class_id=school_class,
            term_id=term,
            enrollment_date=enrollment_date or application.application_date,
            is_active=True,
        )

        application.student = student
        application.status = 'Enrolled'
        application.decision = 'Admitted'
        application.save(update_fields=['student', 'status', 'decision'])
        _sync_library_member_for_student(student)

        return Response({
            "message": "Enrollment complete",
            "student_id": student.id,
            "admission_number": student.admission_number
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='documents')
    def upload_documents(self, request, pk=None):
        application = self.get_object()
        files = request.FILES.getlist('documents_upload')
        if not files:
            return Response({"error": "documents_upload is required"}, status=status.HTTP_400_BAD_REQUEST)
        created = []
        for upload in files:
            doc = AdmissionDocument.objects.create(application=application, file=upload)
            created.append({"id": doc.id, "name": doc.file.name, "url": doc.file.url})
        if created:
            if not application.documents:
                application.documents = []
            application.documents.extend([{"type": d["name"], "received": True} for d in created])
            application.save(update_fields=['documents'])
        return Response({"documents": created}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path='documents/(?P<doc_id>[^/.]+)')
    def delete_document(self, request, pk=None, doc_id=None):
        application = self.get_object()
        try:
            doc = AdmissionDocument.objects.get(id=doc_id, application=application)
        except AdmissionDocument.DoesNotExist:
            return Response({"error": "Document not found"}, status=status.HTTP_404_NOT_FOUND)
        doc.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class AdmissionsPipelineSummaryView(APIView):
    """
    Summary counts for admissions pipeline stages.
    """
    permission_classes = [IsSchoolAdmin | IsTeacher, HasModuleAccess]
    module_key = "STUDENTS"

    def get(self, request):
        queryset = AdmissionApplication.objects.all()
        status_param = request.query_params.get('status')
        grade = request.query_params.get('grade')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        if status_param:
            queryset = queryset.filter(status=status_param)
        if grade:
            queryset = queryset.filter(applying_for_grade_id=grade)
        if date_from:
            queryset = queryset.filter(application_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(application_date__lte=date_to)

        counts = dict(
            queryset.values('status').annotate(total=Count('id')).values_list('status', 'total')
        )

        stages = [choice[0] for choice in AdmissionApplication.STATUS_CHOICES]
        ordered = {stage: counts.get(stage, 0) for stage in stages}

        return Response({
            "total": queryset.count(),
            "stages": stages,
            "counts": ordered,
        }, status=status.HTTP_200_OK)

class LogoutView(APIView):
    """
    Blacklist the supplied refresh token, effectively logging the user out
    on the server side. The client should also clear its stored tokens.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"detail": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            from rest_framework_simplejwt.tokens import RefreshToken as JWTRefreshToken
            token = JWTRefreshToken(refresh_token)
            token.blacklist()
            return Response({"detail": "Logged out successfully."}, status=status.HTTP_200_OK)
        except Exception:
            # Token already expired/blacklisted — still treat as logged-out
            return Response({"detail": "Logged out."}, status=status.HTTP_200_OK)


class CurrentUserView(APIView):
    """Return the currently authenticated user's profile, role and assigned modules."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        profile = getattr(user, 'userprofile', None)
        role = getattr(profile, 'role', None)
        role_name = getattr(role, 'name', 'ADMIN') if role else 'ADMIN'
        # Use Django's get_FOO_display() for the human-readable role label
        role_display = role.get_name_display() if role else role_name

        # Super-admin / admin roles get ALL active modules
        if role_name in ('ADMIN', 'TENANT_SUPER_ADMIN') or user.is_superuser:
            module_keys = list(Module.objects.filter(is_active=True).values_list('key', flat=True).order_by('key'))
        elif role_name == 'PARENT':
            # Parent users have inherent access to the parent portal — no module assignment needed
            module_keys = ['PARENTS', 'PARENT_PORTAL']
        elif role_name == 'STUDENT':
            # Student users have inherent access to the student portal — no module assignment needed
            module_keys = ['STUDENT_PORTAL']
        else:
            module_keys = list(
                UserModuleAssignment.objects.filter(
                    user=user, is_active=True, module__is_active=True
                ).values_list('module__key', flat=True)
            )

        return Response({
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'role': role_name,
            'role_display': role_display,
            'is_superuser': user.is_superuser,
            'assigned_module_keys': module_keys,
            'force_password_change': bool(getattr(profile, 'force_password_change', False)),
        })


class TenantSequenceResetView(APIView):
    permission_classes = [IsSchoolAdmin, HasModuleAccess]
    module_key = "CORE"

    def post(self, request):
        schema = getattr(request.tenant, "schema_name", None)
        if not schema:
            return Response({"error": "Tenant schema not resolved."}, status=status.HTTP_400_BAD_REQUEST)

        reset = []
        with connection.cursor() as cursor:
            cursor.execute("SET search_path TO %s", [schema])
            cursor.execute(
                """
                SELECT tc.table_schema, tc.table_name, kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = %s
                """,
                [schema],
            )
            rows = cursor.fetchall()
            for table_schema, table_name, column_name in rows:
                cursor.execute(
                    "SELECT pg_get_serial_sequence(%s, %s)",
                    [f"{table_schema}.{table_name}", column_name],
                )
                seq_name = cursor.fetchone()[0]
                if not seq_name:
                    continue
                query = pgsql.SQL(
                    """
                    SELECT setval(
                        {seq},
                        COALESCE((SELECT MAX({col}) FROM {schema}.{table}), 1),
                        (SELECT MAX({col}) IS NOT NULL FROM {schema}.{table})
                    )
                    """
                ).format(
                    seq=pgsql.Literal(seq_name),
                    col=pgsql.Identifier(column_name),
                    schema=pgsql.Identifier(table_schema),
                    table=pgsql.Identifier(table_name),
                )
                cursor.execute(query)
                reset.append({"table": f"{table_schema}.{table_name}", "sequence": seq_name})

        return Response({"schema": schema, "reset": reset}, status=status.HTTP_200_OK)

class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [IsSchoolAdmin | IsTeacher, HasModuleAccess]
    module_key = "COMMUNICATION"

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response["Warning"] = "299 - Deprecated; use /api/communication/legacy-messages/"
        return response

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        response["Warning"] = "299 - Deprecated; use /api/communication/legacy-messages/"
        return response

class ModuleViewSet(viewsets.ModelViewSet):
    queryset = Module.objects.filter(is_active=True)
    serializer_class = ModuleSerializer
    permission_classes = [IsSchoolAdmin, HasModuleAccess]
    module_key = "CORE"

    def get_queryset(self):
        queryset = Module.objects.filter(is_active=True)
        if module_focus_lock_enabled():
            queryset = queryset.filter(key__in=module_focus_keys())
        return queryset.order_by("key")

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()

    @action(detail=False, methods=['get'])
    def mine(self, request):
        """
        Returns active modules assigned to the current user.
        """
        assignments = UserModuleAssignment.objects.filter(
            is_active=True,
            user=request.user,
            module__is_active=True
        ).select_related('module')
        if module_focus_lock_enabled():
            assignments = assignments.filter(module__key__in=module_focus_keys())
        modules = [a.module for a in assignments]
        serializer = self.get_serializer(modules, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class UserModuleAssignmentViewSet(viewsets.ModelViewSet):
    queryset = UserModuleAssignment.objects.filter(is_active=True)
    serializer_class = UserModuleAssignmentSerializer
    permission_classes = [IsSchoolAdmin, HasModuleAccess]
    module_key = "CORE"

    def get_queryset(self):
        queryset = super().get_queryset()
        if module_focus_lock_enabled():
            queryset = queryset.filter(module__key__in=module_focus_keys())
        user_id = self.request.query_params.get('user_id')
        module_key = self.request.query_params.get('module_key')

        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if module_key:
            queryset = queryset.filter(module__key=module_key)

        return queryset

    def perform_create(self, serializer):
        serializer.save(assigned_by=self.request.user)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def mine(self, request):
        """
        Returns active module assignments (with metadata) for the current user.
        """
        assignments = UserModuleAssignment.objects.filter(
            is_active=True,
            user=request.user,
            module__is_active=True
        ).select_related('module', 'assigned_by')
        if module_focus_lock_enabled():
            assignments = assignments.filter(module__key__in=module_focus_keys())
        serializer = self.get_serializer(assignments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def bulk_assign(self, request):
        """
        Assign multiple modules to a user in one request.
        Payload: { "user_id": 1, "module_keys": ["FINANCE", "STUDENTS"] }
        """
        user_id = request.data.get('user_id')
        module_keys = request.data.get('module_keys', [])

        if not user_id or not isinstance(module_keys, list) or len(module_keys) == 0:
            return Response(
                {"error": "user_id and module_keys[] are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        normalized_keys = [str(key).strip().upper() for key in module_keys if str(key).strip()]
        if module_focus_lock_enabled():
            blocked = [key for key in normalized_keys if not is_module_allowed(key)]
            if blocked:
                return Response(
                    {
                        "error": "Requested modules are locked in focus mode.",
                        "blocked": blocked,
                        "allowed": sorted(list(module_focus_keys())),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        modules = list(Module.objects.filter(key__in=normalized_keys, is_active=True))
        found_keys = {m.key for m in modules}
        missing = [k for k in normalized_keys if k not in found_keys]
        if missing:
            return Response(
                {"error": "Invalid module_keys", "missing": missing},
                status=status.HTTP_400_BAD_REQUEST
            )

        created = 0
        reactivated = 0
        for module in modules:
            assignment, was_created = UserModuleAssignment.objects.get_or_create(
                user_id=user_id,
                module=module,
                defaults={'assigned_by': request.user, 'is_active': True}
            )
            if was_created:
                created += 1
            elif not assignment.is_active:
                assignment.is_active = True
                assignment.assigned_by = request.user
                assignment.save(update_fields=['is_active', 'assigned_by'])
                reactivated += 1

        return Response(
            {
                "message": "Bulk assignment complete",
                "created": created,
                "reactivated": reactivated,
                "modules": sorted(list(found_keys))
            },
            status=status.HTTP_200_OK
        )


class TenantModuleListView(APIView):
    """
    GET /api/tenant/modules
    Lists tenant-assigned modules with current module theme settings.
    """
    permission_classes = [CanManageModuleSettings]

    def get(self, request):
        tenant_modules = TenantModuleSettingsService.list_modules_for_tenant(user=request.user)
        serializer = TenantModuleSerializer(tenant_modules, many=True)
        return Response({"count": len(serializer.data), "results": serializer.data}, status=status.HTTP_200_OK)


class TenantModuleSettingsView(APIView):
    """
    GET /api/tenant/modules/{id}/settings
    PUT /api/tenant/modules/{id}/settings
    """
    permission_classes = [CanManageModuleSettings]

    def get(self, request, module_id: int):
        tenant_module, settings_obj = TenantModuleSettingsService.get_module_settings(module_id, user=request.user)
        if not tenant_module or not settings_obj:
            return Response({"detail": "Module not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ModuleSettingSerializer(settings_obj).data, status=status.HTTP_200_OK)

    def put(self, request, module_id: int):
        tenant_module, settings_obj = TenantModuleSettingsService.get_module_settings(module_id, user=request.user)
        if not tenant_module or not settings_obj:
            return Response({"detail": "Module not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ModuleSettingSerializer(settings_obj, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save(updated_by=request.user)
        return Response(ModuleSettingSerializer(updated).data, status=status.HTTP_200_OK)

class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.all()
    serializer_class = ExpenseSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get('search')
        category = self.request.query_params.get('category')
        approval_status = self.request.query_params.get('approval_status')
        vendor = self.request.query_params.get('vendor')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')

        if search:
            queryset = queryset.filter(
                models.Q(category__icontains=search)
                | models.Q(description__icontains=search)
                | models.Q(vendor__icontains=search)
            )
        if category:
            queryset = queryset.filter(category=category)
        if approval_status:
            queryset = queryset.filter(approval_status=approval_status)
        if vendor:
            queryset = queryset.filter(vendor__icontains=vendor)
        if date_from:
            queryset = queryset.filter(expense_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(expense_date__lte=date_to)

        return queryset.order_by('-expense_date', '-id')

    def perform_create(self, serializer):
        expense = serializer.save()
        # IPSAS: Auto double-entry journal — DR Operating Expense / CR Cash & Bank
        amount = float(expense.amount or 0)
        if amount > 0:
            exp_acct = _journal_get_or_create_account('6000', 'Operating Expenses', 'EXPENSE')
            cash = _journal_get_or_create_account('1000', 'Cash and Bank', 'ASSET')
            _auto_post_journal(
                entry_key=f"EXP-{expense.id}",
                entry_date=expense.expense_date,
                memo=f"Expense: {expense.category} – {expense.vendor or ''}".strip(' –'),
                source_type='Expense',
                source_id=expense.id,
                lines=[
                    (exp_acct, amount, 0, expense.category),
                    (cash, 0, amount, 'Cash disbursed'),
                ],
            )

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()


class DepartmentViewSet(viewsets.ModelViewSet):
    """Shared department endpoint — reads from school.Department (managed via Academics module)."""
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Department.objects.filter(is_active=True).order_by('name')

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active'])


class BudgetViewSet(viewsets.ModelViewSet):
    queryset = Budget.objects.filter(is_active=True).select_related('academic_year', 'term')
    serializer_class = BudgetSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        academic_year = self.request.query_params.get('academic_year')
        term = self.request.query_params.get('term')

        if academic_year:
            if str(academic_year).isdigit():
                queryset = queryset.filter(academic_year_id=academic_year)
            else:
                queryset = queryset.filter(academic_year__name=academic_year)
        if term:
            queryset = queryset.filter(term_id=term)
        return queryset.order_by('-updated_at', '-id')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        out = self.get_serializer(instance)
        return Response(out.data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active', 'updated_at'])


class FeeAssignmentViewSet(viewsets.ModelViewSet):
    queryset = FeeAssignment.objects.all()
    serializer_class = FeeAssignmentSerializer
    permission_classes = [IsSchoolAdmin | IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        queryset = super().get_queryset().select_related('student', 'fee_structure')
        search = self.request.query_params.get('search')
        student = self.request.query_params.get('student')
        fee_structure = self.request.query_params.get('fee_structure')
        is_active = self.request.query_params.get('is_active')

        if search:
            queryset = queryset.filter(
                models.Q(student__first_name__icontains=search)
                | models.Q(student__last_name__icontains=search)
                | models.Q(student__admission_number__icontains=search)
                | models.Q(fee_structure__name__icontains=search)
            )
        if student:
            queryset = queryset.filter(student_id=student)
        if fee_structure:
            queryset = queryset.filter(fee_structure_id=fee_structure)
        if is_active is not None:
            normalized = str(is_active).lower()
            if normalized in ('true', '1'):
                queryset = queryset.filter(is_active=True)
            elif normalized in ('false', '0'):
                queryset = queryset.filter(is_active=False)
        return queryset.order_by('-id')

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()

    def perform_create(self, serializer):
        try:
            assignment = FinanceService.assign_fee(
                student=serializer.validated_data['student'],
                fee_structure=serializer.validated_data['fee_structure'],
                discount_amount=serializer.validated_data.get('discount_amount', 0),
                user=self.request.user
            )
            assignment.start_date = serializer.validated_data.get('start_date')
            assignment.end_date = serializer.validated_data.get('end_date')
            assignment.is_active = serializer.validated_data.get('is_active', True)
            assignment.save(update_fields=['start_date', 'end_date', 'is_active'])
            serializer.instance = assignment
        except Exception as exc:
            raise ValidationError(str(exc))


class OptionalChargeViewSet(viewsets.ModelViewSet):
    queryset = OptionalCharge.objects.all()
    serializer_class = OptionalChargeSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        queryset = super().get_queryset().select_related('academic_year', 'term')
        category = self.request.query_params.get('category')
        is_active = self.request.query_params.get('is_active')
        if category:
            queryset = queryset.filter(category=category)
        if is_active is not None:
            normalized = str(is_active).lower()
            queryset = queryset.filter(is_active=(normalized in ('true', '1')))
        return queryset

class StudentOptionalChargeViewSet(viewsets.ModelViewSet):
    queryset = StudentOptionalCharge.objects.all()
    serializer_class = StudentOptionalChargeSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        queryset = super().get_queryset().select_related('student', 'optional_charge')
        student = self.request.query_params.get('student')
        optional_charge = self.request.query_params.get('optional_charge')
        is_paid = self.request.query_params.get('is_paid')
        if student:
            queryset = queryset.filter(student_id=student)
        if optional_charge:
            queryset = queryset.filter(optional_charge_id=optional_charge)
        if is_paid is not None:
            normalized = str(is_paid).lower()
            queryset = queryset.filter(is_paid=(normalized in ('true', '1')))
        return queryset


class ScholarshipAwardViewSet(viewsets.ModelViewSet):
    queryset = ScholarshipAward.objects.all().select_related('student', 'created_by', 'approved_by')
    serializer_class = ScholarshipAwardSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get('search')
        student = self.request.query_params.get('student')
        status_param = self.request.query_params.get('status')
        is_active = self.request.query_params.get('is_active')

        if search:
            queryset = queryset.filter(
                models.Q(program_name__icontains=search)
                | models.Q(student__first_name__icontains=search)
                | models.Q(student__last_name__icontains=search)
                | models.Q(student__admission_number__icontains=search)
            )
        if student:
            queryset = queryset.filter(student_id=student)
        if status_param:
            queryset = queryset.filter(status=status_param.upper())
        if is_active is not None:
            normalized = str(is_active).lower()
            if normalized in {'true', '1'}:
                queryset = queryset.filter(is_active=True)
            elif normalized in {'false', '0'}:
                queryset = queryset.filter(is_active=False)
        return queryset.order_by('-created_at', '-id')

    def perform_create(self, serializer):
        approved_by = self.request.user if _is_admin_like(self.request.user) else None
        serializer.save(created_by=self.request.user, approved_by=approved_by)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.status = 'ENDED'
        instance.save(update_fields=['is_active', 'status', 'updated_at'])


class InvoiceAdjustmentViewSet(viewsets.ModelViewSet):
    queryset = InvoiceAdjustment.objects.all()
    serializer_class = InvoiceAdjustmentSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    http_method_names = ['get', 'post', 'head', 'options']
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        queryset = super().get_queryset().select_related('adjusted_by', 'reviewed_by')
        search = self.request.query_params.get('search')
        invoice = self.request.query_params.get('invoice')
        min_amount = self.request.query_params.get('min_amount')
        max_amount = self.request.query_params.get('max_amount')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        status_filter = self.request.query_params.get('status')

        if search:
            query = models.Q(reason__icontains=search)
            if str(search).isdigit():
                query |= models.Q(invoice_id=int(search))
            queryset = queryset.filter(query)
        if invoice:
            queryset = queryset.filter(invoice_id=invoice)
        if min_amount:
            queryset = queryset.filter(amount__gte=min_amount)
        if max_amount:
            queryset = queryset.filter(amount__lte=max_amount)
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        if status_filter:
            queryset = queryset.filter(status=status_filter.upper())
        return queryset.order_by('-created_at', '-id')

    def perform_create(self, serializer):
        try:
            amount = serializer.validated_data['amount']
            auto_approve = _is_admin_like(self.request.user) and amount < _approval_threshold()
            adjustment = FinanceService.create_adjustment(
                invoice=serializer.validated_data['invoice'],
                amount=amount,
                reason=serializer.validated_data['reason'],
                user=self.request.user,
                adjustment_type=serializer.validated_data.get('adjustment_type', 'CREDIT'),
                auto_approve=auto_approve,
            )
            serializer.instance = adjustment
        except Exception as exc:
            raise ValidationError(str(exc))

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        if not _is_admin_like(request.user):
            return Response({"error": "Only admin can approve adjustments."}, status=status.HTTP_403_FORBIDDEN)
        adjustment = self.get_object()
        try:
            review_notes = request.data.get('review_notes') or ''
            adjustment = FinanceService.approve_adjustment(adjustment, reviewer=request.user, review_notes=review_notes)
            return Response(self.get_serializer(adjustment).data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        if not _is_admin_like(request.user):
            return Response({"error": "Only admin can reject adjustments."}, status=status.HTTP_403_FORBIDDEN)
        adjustment = self.get_object()
        try:
            review_notes = request.data.get('review_notes') or ''
            adjustment = FinanceService.reject_adjustment(adjustment, reviewer=request.user, review_notes=review_notes)
            return Response(self.get_serializer(adjustment).data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class PaymentReversalRequestViewSet(viewsets.ModelViewSet):
    queryset = PaymentReversalRequest.objects.all().select_related('payment', 'requested_by', 'reviewed_by')
    serializer_class = PaymentReversalRequestSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    http_method_names = ['get', 'post', 'head', 'options']
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        status_param = self.request.query_params.get('status')
        payment_id = self.request.query_params.get('payment')
        search = self.request.query_params.get('search')
        if status_param:
            queryset = queryset.filter(status=status_param.upper())
        if payment_id:
            queryset = queryset.filter(payment_id=payment_id)
        if search:
            queryset = queryset.filter(
                models.Q(reason__icontains=search)
                | models.Q(payment__reference_number__icontains=search)
                | models.Q(payment__receipt_number__icontains=search)
                | models.Q(payment__student__admission_number__icontains=search)
                | models.Q(payment__student__first_name__icontains=search)
                | models.Q(payment__student__last_name__icontains=search)
            )
        return queryset.order_by('-requested_at')

    def perform_create(self, serializer):
        try:
            reversal = FinanceService.request_payment_reversal(
                payment=serializer.validated_data['payment'],
                reason=serializer.validated_data['reason'],
                requested_by=self.request.user,
            )
            serializer.instance = reversal
        except Exception as exc:
            raise ValidationError(str(exc))

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        if not _is_admin_like(request.user):
            return Response({"error": "Only admin can approve reversals."}, status=status.HTTP_403_FORBIDDEN)
        reversal = self.get_object()
        try:
            review_notes = request.data.get('review_notes') or ''
            reversal = FinanceService.approve_payment_reversal(
                reversal_request=reversal,
                reviewed_by=request.user,
                review_notes=review_notes,
            )
            return Response(self.get_serializer(reversal).data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        if not _is_admin_like(request.user):
            return Response({"error": "Only admin can reject reversals."}, status=status.HTTP_403_FORBIDDEN)
        reversal = self.get_object()
        try:
            review_notes = request.data.get('review_notes') or ''
            reversal = FinanceService.reject_payment_reversal(
                reversal_request=reversal,
                reviewed_by=request.user,
                review_notes=review_notes,
            )
            return Response(self.get_serializer(reversal).data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class InvoiceWriteOffRequestViewSet(viewsets.ModelViewSet):
    queryset = InvoiceWriteOffRequest.objects.all().select_related('invoice__student', 'requested_by', 'reviewed_by', 'applied_adjustment')
    serializer_class = InvoiceWriteOffRequestSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    http_method_names = ['get', 'post', 'head', 'options']
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        status_param = self.request.query_params.get('status')
        invoice = self.request.query_params.get('invoice')
        search = self.request.query_params.get('search')
        if status_param:
            queryset = queryset.filter(status=status_param.upper())
        if invoice:
            queryset = queryset.filter(invoice_id=invoice)
        if search:
            queryset = queryset.filter(
                models.Q(reason__icontains=search)
                | models.Q(invoice__invoice_number__icontains=search)
                | models.Q(invoice__student__admission_number__icontains=search)
                | models.Q(invoice__student__first_name__icontains=search)
                | models.Q(invoice__student__last_name__icontains=search)
            )
        return queryset.order_by('-requested_at', '-id')

    def perform_create(self, serializer):
        try:
            writeoff = FinanceService.create_writeoff_request(
                invoice=serializer.validated_data['invoice'],
                amount=serializer.validated_data['amount'],
                reason=serializer.validated_data['reason'],
                requested_by=self.request.user,
            )
            serializer.instance = writeoff
        except Exception as exc:
            raise ValidationError(str(exc))

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        if not _is_admin_like(request.user):
            return Response({"error": "Only admin can approve write-offs."}, status=status.HTTP_403_FORBIDDEN)
        writeoff = self.get_object()
        try:
            review_notes = request.data.get('review_notes') or ''
            writeoff = FinanceService.approve_writeoff_request(writeoff=writeoff, reviewer=request.user, review_notes=review_notes)
            return Response(self.get_serializer(writeoff).data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        if not _is_admin_like(request.user):
            return Response({"error": "Only admin can reject write-offs."}, status=status.HTTP_403_FORBIDDEN)
        writeoff = self.get_object()
        try:
            review_notes = request.data.get('review_notes') or ''
            writeoff = FinanceService.reject_writeoff_request(writeoff=writeoff, reviewer=request.user, review_notes=review_notes)
            return Response(self.get_serializer(writeoff).data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class LateFeeRuleViewSet(viewsets.ModelViewSet):
    queryset = LateFeeRule.objects.all()
    serializer_class = LateFeeRuleSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    pagination_class = None

    @action(detail=False, methods=['post'], url_path='apply')
    def apply_rules(self, request):
        dry_run = str(request.data.get('dry_run', '')).lower() in {'true', '1', 'yes'}
        if dry_run:
            result = FinanceService.preview_late_fees()
            return Response(result, status=status.HTTP_200_OK)
        result = FinanceService.apply_late_fees(run_by=request.user)
        return Response(result, status=status.HTTP_200_OK)


class FeeReminderLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FeeReminderLog.objects.all().select_related('invoice').order_by('-sent_at', '-id')
    serializer_class = FeeReminderLogSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    pagination_class = FinanceResultsPagination

    @action(detail=False, methods=['post'], url_path='send-overdue')
    def send_overdue(self, request):
        channel = (request.data.get('channel') or 'EMAIL').upper()
        if channel not in {'EMAIL', 'SMS', 'INAPP'}:
            return Response({"error": "Unsupported channel"}, status=status.HTTP_400_BAD_REQUEST)
        result = FinanceService.send_overdue_reminders(channel=channel)
        return Response(result, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='send-scheduled')
    def send_scheduled(self, request):
        channel = (request.data.get('channel') or 'EMAIL').upper()
        mode = (request.data.get('mode') or 'OVERDUE').upper()
        days_before = request.data.get('days_before', 3)
        if channel not in {'EMAIL', 'SMS', 'INAPP'}:
            return Response({"error": "Unsupported channel"}, status=status.HTTP_400_BAD_REQUEST)
        if mode not in {'PRE_DUE', 'DUE', 'OVERDUE'}:
            return Response({"error": "Unsupported mode"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = FinanceService.send_scheduled_reminders(mode=mode, channel=channel, days_before=int(days_before))
            return Response(result, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='send-installment-scheduled')
    def send_installment_scheduled(self, request):
        channel = (request.data.get('channel') or 'EMAIL').upper()
        mode = (request.data.get('mode') or 'OVERDUE').upper()
        days_before = request.data.get('days_before', 3)
        if channel not in {'EMAIL', 'SMS', 'INAPP'}:
            return Response({"error": "Unsupported channel"}, status=status.HTTP_400_BAD_REQUEST)
        if mode not in {'PRE_DUE', 'DUE', 'OVERDUE'}:
            return Response({"error": "Unsupported mode"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = FinanceService.send_installment_scheduled_reminders(
                mode=mode,
                channel=channel,
                days_before=int(days_before),
            )
            return Response(result, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class AccountingPeriodViewSet(viewsets.ModelViewSet):
    queryset = AccountingPeriod.objects.all()
    serializer_class = AccountingPeriodSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        return super().get_queryset().order_by('-start_date', '-id')

    @action(detail=True, methods=['post'], url_path='close')
    def close_period(self, request, pk=None):
        period = self.get_object()
        if not _is_admin_like(request.user):
            return Response({"error": "Only admin can close periods."}, status=status.HTTP_403_FORBIDDEN)
        if period.is_closed:
            return Response({"error": "Period already closed."}, status=status.HTTP_400_BAD_REQUEST)
        period.is_closed = True
        period.closed_by = request.user
        period.closed_at = timezone.now()
        period.save(update_fields=['is_closed', 'closed_by', 'closed_at'])
        return Response(self.get_serializer(period).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='reopen')
    def reopen_period(self, request, pk=None):
        period = self.get_object()
        if not _is_admin_like(request.user):
            return Response({"error": "Only admin can reopen periods."}, status=status.HTTP_403_FORBIDDEN)
        if not period.is_closed:
            return Response({"error": "Period is not closed."}, status=status.HTTP_400_BAD_REQUEST)
        period.is_closed = False
        period.closed_by = None
        period.closed_at = None
        period.save(update_fields=['is_closed', 'closed_by', 'closed_at'])
        return Response(self.get_serializer(period).data, status=status.HTTP_200_OK)


class ChartOfAccountViewSet(viewsets.ModelViewSet):
    queryset = ChartOfAccount.objects.all()
    serializer_class = ChartOfAccountSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get('search')
        account_type = self.request.query_params.get('account_type')
        if search:
            queryset = queryset.filter(models.Q(code__icontains=search) | models.Q(name__icontains=search))
        if account_type:
            queryset = queryset.filter(account_type=account_type)
        return queryset.order_by('code')


class JournalEntryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = JournalEntry.objects.all().prefetch_related('lines__account')
    serializer_class = JournalEntrySerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        account_id = self.request.query_params.get('account_id')
        if date_from:
            queryset = queryset.filter(entry_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(entry_date__lte=date_to)
        if account_id:
            queryset = queryset.filter(lines__account_id=account_id).distinct()
        return queryset.order_by('-entry_date', '-id')


class AccountingTrialBalanceView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        lines = JournalLine.objects.select_related('account', 'entry')
        if date_from:
            lines = lines.filter(entry__entry_date__gte=date_from)
        if date_to:
            lines = lines.filter(entry__entry_date__lte=date_to)

        by_account = {}
        for line in lines:
            key = line.account_id
            if key not in by_account:
                by_account[key] = {
                    "account_id": line.account_id,
                    "code": line.account.code,
                    "name": line.account.name,
                    "type": line.account.account_type,
                    "debit": 0,
                    "credit": 0,
                }
            by_account[key]["debit"] += float(line.debit)
            by_account[key]["credit"] += float(line.credit)

        rows = sorted(by_account.values(), key=lambda x: x["code"])
        total_debit = round(sum(row["debit"] for row in rows), 2)
        total_credit = round(sum(row["credit"] for row in rows), 2)
        return Response(
            {
                "rows": rows,
                "total_debit": total_debit,
                "total_credit": total_credit,
                "is_balanced": round(total_debit - total_credit, 2) == 0,
            },
            status=status.HTTP_200_OK,
        )


class AccountingLedgerView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        account_id = request.query_params.get('account_id')
        if not account_id:
            return Response({"error": "account_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        lines = JournalLine.objects.select_related('entry', 'account').filter(account_id=account_id)
        if date_from:
            lines = lines.filter(entry__entry_date__gte=date_from)
        if date_to:
            lines = lines.filter(entry__entry_date__lte=date_to)
        lines = lines.order_by('entry__entry_date', 'id')

        running = 0.0
        rows = []
        for line in lines:
            running += float(line.debit) - float(line.credit)
            rows.append(
                {
                    "entry_id": line.entry_id,
                    "entry_date": line.entry.entry_date,
                    "memo": line.entry.memo,
                    "source_type": line.entry.source_type,
                    "source_id": line.entry.source_id,
                    "debit": float(line.debit),
                    "credit": float(line.credit),
                    "running_balance": round(running, 2),
                }
            )

        return Response({"account_id": int(account_id), "rows": rows, "closing_balance": round(running, 2)})


class PaymentGatewayTransactionViewSet(viewsets.ModelViewSet):
    queryset = PaymentGatewayTransaction.objects.all().select_related('student', 'invoice')
    serializer_class = PaymentGatewayTransactionSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    pagination_class = FinanceResultsPagination
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        queryset = super().get_queryset()
        provider = self.request.query_params.get('provider')
        status_param = self.request.query_params.get('status')
        is_reconciled = self.request.query_params.get('is_reconciled')
        student_id = self.request.query_params.get('student')
        invoice_id = self.request.query_params.get('invoice')
        search = self.request.query_params.get('search')

        if provider:
            queryset = queryset.filter(provider__iexact=provider)
        if status_param:
            queryset = queryset.filter(status=status_param.upper())
        if is_reconciled is not None:
            normalized = str(is_reconciled).lower()
            if normalized in {'true', '1'}:
                queryset = queryset.filter(is_reconciled=True)
            elif normalized in {'false', '0'}:
                queryset = queryset.filter(is_reconciled=False)
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        if invoice_id:
            queryset = queryset.filter(invoice_id=invoice_id)
        if search:
            queryset = queryset.filter(
                models.Q(external_id__icontains=search)
                | models.Q(provider__icontains=search)
            )
        return queryset.order_by('-created_at', '-id')

    @action(detail=True, methods=['post'], url_path='mark-reconciled')
    def mark_reconciled(self, request, pk=None):
        tx = self.get_object()
        tx.is_reconciled = True
        tx.save(update_fields=['is_reconciled', 'updated_at'])
        return Response(self.get_serializer(tx).data, status=status.HTTP_200_OK)


class PaymentGatewayWebhookEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PaymentGatewayWebhookEvent.objects.all()
    serializer_class = PaymentGatewayWebhookEventSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    pagination_class = FinanceResultsPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        provider = self.request.query_params.get('provider')
        processed = self.request.query_params.get('processed')
        if provider:
            queryset = queryset.filter(provider__iexact=provider)
        if processed is not None:
            normalized = str(processed).lower()
            if normalized in {'true', '1'}:
                queryset = queryset.filter(processed=True)
            elif normalized in {'false', '0'}:
                queryset = queryset.filter(processed=False)
        return queryset.order_by('-received_at', '-id')


class FinanceGatewayWebhookView(APIView):
    permission_classes = [permissions.AllowAny]

    @staticmethod
    def _extract_token(request):
        header_token = request.headers.get('X-Webhook-Token', '')
        if header_token:
            return header_token.strip()
        auth = request.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            return auth.split(' ', 1)[1].strip()
        return ''

    @staticmethod
    def _extract_signature(request):
        signature = request.headers.get('X-Webhook-Signature', '') or request.headers.get('X-Signature', '')
        return signature.strip()

    @staticmethod
    def _verify_request(request, raw_body):
        expected_token = getattr(settings, "FINANCE_WEBHOOK_TOKEN", "")
        expected_secret = getattr(settings, "FINANCE_WEBHOOK_SHARED_SECRET", "")
        strict_mode = bool(getattr(settings, "FINANCE_WEBHOOK_STRICT_MODE", True))

        if not expected_token and not expected_secret:
            if strict_mode:
                return False, "Finance webhook verification is not configured."
            return True, ""

        token = FinanceGatewayWebhookView._extract_token(request)
        if expected_token and token != expected_token:
            return False, "Invalid webhook token"

        signature = FinanceGatewayWebhookView._extract_signature(request)
        if expected_secret:
            digest = hmac.new(
                expected_secret.encode('utf-8'),
                raw_body,
                hashlib.sha256,
            ).hexdigest()
            provided = signature
            if provided.lower().startswith('sha256='):
                provided = provided.split('=', 1)[1].strip()
            if not provided or not hmac.compare_digest(provided, digest):
                return False, "Invalid webhook signature"

        return True, ""

    def post(self, request, provider):
        raw_body = request.body or b""
        ok, error = self._verify_request(request, raw_body)
        if not ok:
            return Response({"error": error}, status=status.HTTP_401_UNAUTHORIZED)

        payload = request.data if isinstance(request.data, dict) else {}
        event_id = (
            payload.get("event_id")
            or payload.get("id")
            or payload.get("webhook_id")
        )
        if not event_id:
            body_hash = hashlib.sha256(raw_body or json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()
            event_id = f"{provider}-{body_hash}"
        event_type = payload.get("event_type") or payload.get("type") or "unknown"
        signature = self._extract_signature(request)

        event, created = FinanceService.ingest_gateway_webhook(
            provider=provider,
            event_id=str(event_id),
            event_type=str(event_type),
            signature=signature,
            payload=payload,
        )
        return Response(
            {
                "id": event.id,
                "event_id": event.event_id,
                "processed": event.processed,
                "duplicate": not created,
                "error": event.error,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class BankStatementLineViewSet(viewsets.ModelViewSet):
    queryset = BankStatementLine.objects.all().select_related('matched_payment', 'matched_gateway_transaction')
    serializer_class = BankStatementLineSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"
    pagination_class = FinanceResultsPagination
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        queryset = super().get_queryset()
        status_param = self.request.query_params.get('status')
        source = self.request.query_params.get('source')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        search = self.request.query_params.get('search')
        if status_param:
            queryset = queryset.filter(status=status_param.upper())
        if source:
            queryset = queryset.filter(source__iexact=source)
        if date_from:
            queryset = queryset.filter(statement_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(statement_date__lte=date_to)
        if search:
            queryset = queryset.filter(
                models.Q(reference__icontains=search) | models.Q(narration__icontains=search)
            )
        return queryset.order_by('-statement_date', '-id')

    @action(detail=False, methods=['post'], url_path='import-csv')
    def import_csv(self, request):
        upload = request.FILES.get('file')
        if not upload:
            return Response({"error": "file is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            decoded = upload.read().decode('utf-8-sig')
        except Exception:
            return Response({"error": "Unable to read CSV file."}, status=status.HTTP_400_BAD_REQUEST)

        reader = csv.DictReader(decoded.splitlines())
        if not reader.fieldnames:
            return Response({"error": "CSV header is missing."}, status=status.HTTP_400_BAD_REQUEST)

        created = 0
        errors = []
        for idx, row in enumerate(reader, start=2):
            try:
                statement_date_raw = (row.get('statement_date') or '').strip()
                amount_raw = (row.get('amount') or '').strip()
                if not statement_date_raw or not amount_raw:
                    raise ValueError("statement_date and amount are required")
                statement_date = datetime.strptime(statement_date_raw, '%Y-%m-%d').date()
                value_date_raw = (row.get('value_date') or '').strip()
                value_date = datetime.strptime(value_date_raw, '%Y-%m-%d').date() if value_date_raw else None

                BankStatementLine.objects.create(
                    statement_date=statement_date,
                    value_date=value_date,
                    amount=amount_raw,
                    reference=(row.get('reference') or '').strip(),
                    narration=(row.get('narration') or '').strip(),
                    source=(row.get('source') or 'csv').strip() or 'csv',
                    status='UNMATCHED',
                )
                created += 1
            except Exception as exc:
                errors.append({"row": idx, "error": str(exc)})

        return Response(
            {
                "created": created,
                "failed": len(errors),
                "errors": errors[:25],
            },
            status=status.HTTP_201_CREATED if created > 0 else status.HTTP_400_BAD_REQUEST,
        )

    @action(detail=False, methods=['get'], url_path='export-csv')
    def export_csv(self, request):
        lines = self.get_queryset()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="finance_bank_statement_lines.csv"'
        writer = _SafeCsvWriter(response)
        writer.writerow([
            'id', 'statement_date', 'value_date', 'amount', 'reference',
            'narration', 'source', 'status', 'matched_payment_reference', 'matched_gateway_external_id'
        ])
        for line in lines:
            writer.writerow([
                line.id,
                line.statement_date,
                line.value_date or '',
                line.amount,
                line.reference,
                line.narration,
                line.source,
                line.status,
                getattr(line.matched_payment, 'reference_number', ''),
                getattr(line.matched_gateway_transaction, 'external_id', ''),
            ])
        return response

    @action(detail=True, methods=['post'], url_path='auto-match')
    def auto_match(self, request, pk=None):
        line = self.get_object()
        line = FinanceService.reconcile_bank_line(line)
        return Response(self.get_serializer(line).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='clear')
    def clear(self, request, pk=None):
        line = self.get_object()
        if not line.matched_payment and not line.matched_gateway_transaction:
            return Response(
                {"error": "Line must be matched before clearing."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        line.status = 'CLEARED'
        line.save(update_fields=['status'])
        return Response(self.get_serializer(line).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='ignore')
    def ignore(self, request, pk=None):
        line = self.get_object()
        line.status = 'IGNORED'
        line.save(update_fields=['status'])
        return Response(self.get_serializer(line).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='unmatch')
    def unmatch(self, request, pk=None):
        line = self.get_object()
        line.matched_payment = None
        line.matched_gateway_transaction = None
        line.status = 'UNMATCHED'
        line.save(update_fields=['matched_payment', 'matched_gateway_transaction', 'status'])
        return Response(self.get_serializer(line).data, status=status.HTTP_200_OK)

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all().order_by('-timestamp')
    serializer_class = AuditLogSerializer
    permission_classes = [IsSchoolAdmin | IsAccountant, HasModuleAccess]
    module_key = "REPORTING"

class FinancialSummaryView(APIView):
    """
    Reporting Endpoint: Aggregates financial data.
    Read-only. No state changes.
    """
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        return Response(FinanceService.get_summary())


class FinanceReceivablesAgingView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        today = timezone.now().date()
        buckets = {
            "0_30": {"count": 0, "amount": 0.0},
            "31_60": {"count": 0, "amount": 0.0},
            "61_90": {"count": 0, "amount": 0.0},
            "90_plus": {"count": 0, "amount": 0.0},
        }
        invoices = Invoice.objects.filter(is_active=True).exclude(status='VOID').select_related('student')
        for invoice in invoices:
            FinanceService.sync_invoice_status(invoice)
            balance = float(invoice.balance_due)
            if balance <= 0:
                continue
            overdue_days = max(0, (today - invoice.due_date).days)
            if overdue_days <= 30:
                key = "0_30"
            elif overdue_days <= 60:
                key = "31_60"
            elif overdue_days <= 90:
                key = "61_90"
            else:
                key = "90_plus"
            buckets[key]["count"] += 1
            buckets[key]["amount"] += balance

        for key in buckets:
            buckets[key]["amount"] = round(buckets[key]["amount"], 2)
        return Response({"as_of": str(today), "buckets": buckets}, status=status.HTTP_200_OK)


class FinanceOverdueAccountsView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        today = timezone.now().date()
        search = (request.query_params.get('search') or '').strip().lower()
        rows = []
        invoices = Invoice.objects.filter(is_active=True).exclude(status='VOID').select_related('student').order_by('due_date', 'id')
        for invoice in invoices:
            FinanceService.sync_invoice_status(invoice)
            balance = float(invoice.balance_due)
            if balance <= 0:
                continue
            overdue_days = max(0, (today - invoice.due_date).days)
            if overdue_days <= 0 and invoice.status not in {'OVERDUE', 'PARTIALLY_PAID', 'ISSUED', 'CONFIRMED'}:
                continue
            student_name = f"{invoice.student.first_name} {invoice.student.last_name}".strip()
            row = {
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number or f"INV-{invoice.id}",
                "student_id": invoice.student_id,
                "student_name": student_name,
                "admission_number": invoice.student.admission_number,
                "due_date": str(invoice.due_date),
                "status": invoice.status,
                "balance_due": round(balance, 2),
                "overdue_days": overdue_days,
            }
            searchable = f"{row['invoice_number']} {row['student_name']} {row['admission_number']}".lower()
            if search and search not in searchable:
                continue
            rows.append(row)
        return Response({"count": len(rows), "results": rows}, status=status.HTTP_200_OK)


class FinanceInstallmentAgingView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        today = timezone.now().date()
        buckets = {
            "0_30": {"count": 0, "amount": 0.0},
            "31_60": {"count": 0, "amount": 0.0},
            "61_90": {"count": 0, "amount": 0.0},
            "90_plus": {"count": 0, "amount": 0.0},
        }
        installments = InvoiceInstallment.objects.select_related('plan__invoice').exclude(status='WAIVED')
        for installment in installments:
            if installment.status == 'PAID':
                continue
            overdue_days = max(0, (today - installment.due_date).days)
            if overdue_days <= 30:
                key = "0_30"
            elif overdue_days <= 60:
                key = "31_60"
            elif overdue_days <= 90:
                key = "61_90"
            else:
                key = "90_plus"
            buckets[key]["count"] += 1
            buckets[key]["amount"] += float(installment.amount)

        for key in buckets:
            buckets[key]["amount"] = round(buckets[key]["amount"], 2)
        return Response({"as_of": str(today), "buckets": buckets}, status=status.HTTP_200_OK)


class FinanceReceivablesAgingCsvExportView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        today = timezone.now().date()
        buckets = {
            "0_30": {"count": 0, "amount": 0.0},
            "31_60": {"count": 0, "amount": 0.0},
            "61_90": {"count": 0, "amount": 0.0},
            "90_plus": {"count": 0, "amount": 0.0},
        }
        invoices = Invoice.objects.filter(is_active=True).exclude(status='VOID').select_related('student')
        for invoice in invoices:
            FinanceService.sync_invoice_status(invoice)
            balance = float(invoice.balance_due)
            if balance <= 0:
                continue
            overdue_days = max(0, (today - invoice.due_date).days)
            if overdue_days <= 30:
                key = "0_30"
            elif overdue_days <= 60:
                key = "31_60"
            elif overdue_days <= 90:
                key = "61_90"
            else:
                key = "90_plus"
            buckets[key]["count"] += 1
            buckets[key]["amount"] += balance

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="finance_receivables_aging.csv"'
        writer = _SafeCsvWriter(response)
        writer.writerow(['as_of', str(today)])
        writer.writerow(['bucket', 'invoice_count', 'amount'])
        for key, label in [('0_30', '0-30'), ('31_60', '31-60'), ('61_90', '61-90'), ('90_plus', '90+')]:
            writer.writerow([label, buckets[key]['count'], round(buckets[key]['amount'], 2)])
        return response


class FinanceOverdueAccountsCsvExportView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        today = timezone.now().date()
        search = (request.query_params.get('search') or '').strip().lower()
        rows = []
        invoices = Invoice.objects.filter(is_active=True).exclude(status='VOID').select_related('student').order_by('due_date', 'id')
        for invoice in invoices:
            FinanceService.sync_invoice_status(invoice)
            balance = float(invoice.balance_due)
            if balance <= 0:
                continue
            overdue_days = max(0, (today - invoice.due_date).days)
            if overdue_days <= 0 and invoice.status not in {'OVERDUE', 'PARTIALLY_PAID', 'ISSUED', 'CONFIRMED'}:
                continue
            student_name = f"{invoice.student.first_name} {invoice.student.last_name}".strip()
            invoice_number = invoice.invoice_number or f"INV-{invoice.id}"
            searchable = f"{invoice_number} {student_name} {invoice.student.admission_number}".lower()
            if search and search not in searchable:
                continue
            rows.append({
                "invoice_id": invoice.id,
                "invoice_number": invoice_number,
                "student_name": student_name,
                "admission_number": invoice.student.admission_number,
                "due_date": str(invoice.due_date),
                "status": invoice.status,
                "balance_due": round(balance, 2),
                "overdue_days": overdue_days,
            })

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="finance_overdue_accounts.csv"'
        writer = _SafeCsvWriter(response)
        writer.writerow(['invoice_id', 'invoice_number', 'student_name', 'admission_number', 'due_date', 'status', 'balance_due', 'overdue_days'])
        for row in rows:
            writer.writerow([
                row['invoice_id'],
                row['invoice_number'],
                row['student_name'],
                row['admission_number'],
                row['due_date'],
                row['status'],
                row['balance_due'],
                row['overdue_days'],
            ])
        return response

class StudentsSummaryView(APIView):
    """
    Summary endpoint for Students module.
    """
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    def get(self, request):
        return Response(StudentsService.get_summary())


class StudentsDashboardView(APIView):
    """
    Operational dashboard payload for Students module.
    """
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    def get(self, request):
        summary = StudentsService.get_summary()
        attendance_qs = AttendanceRecord.objects.all()
        total_attendance = attendance_qs.count()
        present = attendance_qs.filter(status='Present').count()
        attendance_rate = round((present / total_attendance) * 100, 2) if total_attendance else 0

        pending_statuses = ['Submitted', 'Documents Received', 'Interview Scheduled', 'Assessed']
        pending_admissions = AdmissionApplication.objects.filter(status__in=pending_statuses).count()

        low_attendance_students = (
            attendance_qs.values('student_id')
            .annotate(
                total=Count('id'),
                present=Count('id', filter=Q(status='Present')),
            )
        )
        low_attendance_count = 0
        for row in low_attendance_students:
            total = row.get('total', 0) or 0
            if total < 3:
                continue
            rate = ((row.get('present', 0) or 0) / total) * 100
            if rate < 85:
                low_attendance_count += 1

        # Track critical incidents over a full month so operational alerts don't miss
        # serious issues that happened outside a strict 2-week window.
        recent_cutoff = timezone.now().date() - timedelta(days=30)
        critical_behavior_count = BehaviorIncident.objects.filter(
            incident_date__gte=recent_cutoff,
            severity__in=['High', 'Critical'],
        ).count()

        activity = []
        for record in AttendanceRecord.objects.select_related('student').order_by('-date', '-id')[:4]:
            activity.append(
                {
                    "type": "Attendance",
                    "date": record.date.isoformat(),
                    "label": f"{record.student.first_name} {record.student.last_name}: {record.status}",
                    "student_id": record.student_id,
                }
            )
        for incident in BehaviorIncident.objects.select_related('student').order_by('-incident_date', '-id')[:4]:
            activity.append(
                {
                    "type": "Behavior",
                    "date": incident.incident_date.isoformat(),
                    "label": (
                        f"{incident.student.first_name} {incident.student.last_name}: "
                        f"{incident.incident_type} ({incident.severity or 'Unspecified'})"
                    ),
                    "student_id": incident.student_id,
                }
            )
        for app in AdmissionApplication.objects.order_by('-application_date', '-id')[:4]:
            activity.append(
                {
                    "type": "Admission",
                    "date": app.application_date.isoformat(),
                    "label": f"{app.student_first_name} {app.student_last_name}: {app.status}",
                    "student_id": app.student_id,
                }
            )
        activity.sort(key=lambda row: row['date'], reverse=True)

        return Response(
            {
                "kpis": {
                    "students_active": summary.get('students_active', 0),
                    "enrollments_active": summary.get('enrollments_active', 0),
                    "attendance_rate": attendance_rate,
                    "pending_admissions": pending_admissions,
                },
                "alerts": {
                    "low_attendance_students": low_attendance_count,
                    "critical_behavior_incidents": critical_behavior_count,
                },
                "recent_activity": activity[:8],
            },
            status=status.HTTP_200_OK,
        )

class SchoolProfileView(APIView):
    """
    Tenant school profile for branding/print headers.
    """
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    def get(self, request):
        profile = SchoolProfile.objects.filter(is_active=True).first()
        serializer = SchoolProfileSerializer(profile) if profile else None
        profile_data = serializer.data if serializer else None
        if profile_data and profile_data.get("logo_url"):
            profile_data["logo_url"] = request.build_absolute_uri(profile_data["logo_url"])
        tenant = getattr(request, "tenant", None)
        return Response({
            "tenant": {
                "name": getattr(tenant, "name", None),
                "schema": getattr(tenant, "schema_name", None),
            },
            "profile": profile_data,
        }, status=status.HTTP_200_OK)

    def patch(self, request):
        if not _is_admin_like(request.user):
            return Response(
                {"error": "Only tenant admins can update school profile settings."},
                status=status.HTTP_403_FORBIDDEN,
            )

        profile = SchoolProfile.objects.filter(is_active=True).first()
        if not profile:
            tenant = getattr(request, "tenant", None)
            profile = SchoolProfile.objects.create(
                school_name=getattr(tenant, "name", None) or "School",
                is_active=True,
            )

        profile_payload = request.data.copy()
        security_payload = extract_security_policy_payload(profile_payload.get("security_config"))
        if hasattr(profile_payload, "pop"):
            profile_payload.pop("security_config", None)

        if security_payload:
            security_policy = get_or_create_security_policy()
            security_serializer = InstitutionSecurityPolicySerializer(
                security_policy,
                data=security_payload,
                partial=True,
            )
            security_serializer.is_valid(raise_exception=True)
            security_serializer.save(updated_by=request.user)

        serializer = SchoolProfileSerializer(profile, data=profile_payload, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        payload = serializer.data
        if payload.get("logo_url"):
            payload["logo_url"] = request.build_absolute_uri(payload["logo_url"])
        return Response(payload, status=status.HTTP_200_OK)


class SchoolTestEmailView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    def post(self, request):
        if not _is_admin_like(request.user):
            return Response(
                {"error": "Only tenant admins can run communication tests."},
                status=status.HTTP_403_FORBIDDEN,
            )

        profile = _active_school_profile()
        if not profile:
            return Response(
                {"error": "Save school communication settings before running the email test."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        smtp_host = (profile.smtp_host or "").strip()
        recipient = (profile.smtp_user or profile.email_address or "").strip()
        if not smtp_host:
            return Response(
                {"error": "Set the SMTP host before running the email test."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not recipient:
            return Response(
                {"error": "Set the SMTP username/email before running the email test."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        school_name = (profile.school_name or getattr(getattr(request, "tenant", None), "name", "") or "School").strip()
        result = send_email_placeholder(
            subject=f"{school_name} test email",
            body=(
                f"This is a test email from {school_name}. "
                "If you received this message, the communication test endpoint is working."
            ),
            recipients=[recipient],
            from_email=recipient,
        )
        if result.status != "Sent":
            return Response(
                {"error": result.failure_reason or "Email test failed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = {
            "message": f"Test email sent to {recipient}.",
            "provider_id": result.provider_id,
        }
        if result.failure_reason:
            payload["note"] = result.failure_reason
        return Response(payload, status=status.HTTP_200_OK)


class SchoolTestSmsView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    def post(self, request):
        if not _is_admin_like(request.user):
            return Response(
                {"error": "Only tenant admins can run communication tests."},
                status=status.HTTP_403_FORBIDDEN,
            )

        profile = _active_school_profile()
        if not profile:
            return Response(
                {"error": "Save school communication settings before running the SMS test."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        phone = (profile.phone or "").strip()
        provider = (profile.sms_provider or "").strip()
        if not provider:
            return Response(
                {"error": "Set the SMS provider before running the SMS test."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not phone:
            return Response(
                {"error": "Set the school phone number before running the SMS test."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        school_name = (profile.school_name or getattr(getattr(request, "tenant", None), "name", "") or "School").strip()
        result = send_sms_placeholder(
            phone=phone,
            message=f"{school_name}: this is a test SMS from the communication settings page.",
            channel="SMS",
        )
        if result.status != "Sent":
            return Response(
                {"error": result.failure_reason or "SMS test failed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = {
            "message": f"Test SMS sent to {phone}.",
            "provider_id": result.provider_id,
        }
        if result.failure_reason:
            payload["note"] = result.failure_reason
        return Response(payload, status=status.HTTP_200_OK)


class ControlPlaneSummaryView(APIView):
    permission_classes = [CanManageSystemSettings]

    def get(self, request):
        return Response(build_control_plane_summary(), status=status.HTTP_200_OK)


class SecurityPolicyView(APIView):
    permission_classes = [CanManageSystemSettings]

    def get(self, request):
        policy = get_or_create_security_policy()
        serializer = InstitutionSecurityPolicySerializer(policy)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        policy = get_or_create_security_policy()
        payload = extract_security_policy_payload(request.data)
        serializer = InstitutionSecurityPolicySerializer(
            policy,
            data=payload,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


def _lifecycle_error_response(exc: LifecycleAutomationError, *, run: InstitutionLifecycleRun | None = None):
    payload = {
        "error": exc.message,
        "code": exc.code,
        "blockers": exc.blockers,
        "details": exc.details,
    }
    if run is not None:
        payload["run"] = InstitutionLifecycleRunDetailSerializer(refresh_lifecycle_run(run)).data
    return Response(payload, status=status.HTTP_400_BAD_REQUEST)


class LifecycleTemplateListView(APIView):
    permission_classes = [CanManageSystemSettings]

    def get(self, request):
        templates = ensure_lifecycle_templates()
        serializer = InstitutionLifecycleTemplateSerializer(templates, many=True)
        return Response({"count": len(serializer.data), "results": serializer.data}, status=status.HTTP_200_OK)


class LifecycleRunListCreateView(APIView):
    permission_classes = [CanManageSystemSettings]

    def get(self, request):
        ensure_lifecycle_templates()
        queryset = InstitutionLifecycleRun.objects.select_related(
            "template",
            "started_by",
            "completed_by",
            "target_academic_year",
            "target_term",
        ).order_by("-created_at", "-id")
        template_code = (request.query_params.get("template_code") or "").strip().upper()
        status_filter = (request.query_params.get("status") or "").strip().upper()
        if template_code:
            queryset = queryset.filter(template__code=template_code)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        runs = [refresh_lifecycle_run(run) for run in queryset]
        serializer = InstitutionLifecycleRunSerializer(runs, many=True)
        return Response({"count": len(serializer.data), "results": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        try:
            run = create_lifecycle_run(
                template_code=(request.data.get("template_code") or "").strip().upper(),
                target_academic_year_id=request.data.get("target_academic_year"),
                target_term_id=request.data.get("target_term"),
                metadata=request.data.get("metadata") if isinstance(request.data.get("metadata"), dict) else None,
            )
        except LifecycleAutomationError as exc:
            return _lifecycle_error_response(exc)
        serializer = InstitutionLifecycleRunDetailSerializer(run)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class LifecycleRunDetailView(APIView):
    permission_classes = [CanManageSystemSettings]

    def get(self, request, run_id: int):
        run = InstitutionLifecycleRun.objects.select_related(
            "template",
            "started_by",
            "completed_by",
            "target_academic_year",
            "target_term",
        ).prefetch_related("task_runs__template_task").filter(pk=run_id).first()
        if not run:
            return Response({"detail": "Lifecycle run not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = InstitutionLifecycleRunDetailSerializer(refresh_lifecycle_run(run))
        return Response(serializer.data, status=status.HTTP_200_OK)


class LifecycleRunStartView(APIView):
    permission_classes = [CanManageSystemSettings]

    def post(self, request, run_id: int):
        run = InstitutionLifecycleRun.objects.select_related("template").filter(pk=run_id).first()
        if not run:
            return Response({"detail": "Lifecycle run not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            run = start_lifecycle_run(run, started_by=request.user)
        except LifecycleAutomationError as exc:
            return _lifecycle_error_response(exc, run=run)
        serializer = InstitutionLifecycleRunDetailSerializer(run)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LifecycleRunCompleteView(APIView):
    permission_classes = [CanManageSystemSettings]

    def post(self, request, run_id: int):
        run = InstitutionLifecycleRun.objects.select_related("template").prefetch_related("task_runs__template_task").filter(
            pk=run_id
        ).first()
        if not run:
            return Response({"detail": "Lifecycle run not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            run = complete_lifecycle_run(run, completed_by=request.user)
        except LifecycleAutomationError as exc:
            return _lifecycle_error_response(exc, run=run)
        serializer = InstitutionLifecycleRunDetailSerializer(run)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LifecycleTaskCompleteView(APIView):
    permission_classes = [CanManageSystemSettings]

    def post(self, request, run_id: int, task_id: int):
        run = InstitutionLifecycleRun.objects.select_related("template").prefetch_related("task_runs__template_task").filter(
            pk=run_id
        ).first()
        if not run:
            return Response({"detail": "Lifecycle run not found."}, status=status.HTTP_404_NOT_FOUND)
        task_run = InstitutionLifecycleTaskRun.objects.select_related("template_task").filter(pk=task_id, run_id=run.id).first()
        if not task_run:
            return Response({"detail": "Lifecycle task not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            run = complete_task_run(
                run,
                task_run,
                completed_by=request.user,
                notes=(request.data.get("notes") or "").strip(),
                evidence=request.data.get("evidence") if isinstance(request.data.get("evidence"), dict) else None,
            )
        except LifecycleAutomationError as exc:
            return _lifecycle_error_response(exc, run=run)
        serializer = InstitutionLifecycleRunDetailSerializer(run)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LifecycleTaskWaiveView(APIView):
    permission_classes = [CanManageSystemSettings]

    def post(self, request, run_id: int, task_id: int):
        run = InstitutionLifecycleRun.objects.select_related("template").prefetch_related("task_runs__template_task").filter(
            pk=run_id
        ).first()
        if not run:
            return Response({"detail": "Lifecycle run not found."}, status=status.HTTP_404_NOT_FOUND)
        task_run = InstitutionLifecycleTaskRun.objects.select_related("template_task").filter(pk=task_id, run_id=run.id).first()
        if not task_run:
            return Response({"detail": "Lifecycle task not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            run = waive_task_run(
                run,
                task_run,
                waived_by=request.user,
                notes=(request.data.get("notes") or "").strip(),
            )
        except LifecycleAutomationError as exc:
            return _lifecycle_error_response(exc, run=run)
        serializer = InstitutionLifecycleRunDetailSerializer(run)
        return Response(serializer.data, status=status.HTTP_200_OK)


class StudentsModuleReportView(APIView):
    """
    Module-wide report summary for Students.
    """
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    @staticmethod
    def build_report_data():
        students_qs = Student.objects.filter(is_active=True)
        enrollments_qs = Enrollment.objects.filter(is_active=True)

        gender_counts = dict(
            students_qs.values('gender').annotate(total=Count('id')).values_list('gender', 'total')
        )

        attendance_qs = AttendanceRecord.objects.all()
        total_attendance = attendance_qs.count()
        present = attendance_qs.filter(status='Present').count()
        absent = attendance_qs.filter(status='Absent').count()
        late = attendance_qs.filter(status='Late').count()
        attendance_rate = round((present / total_attendance) * 100, 2) if total_attendance else 0

        behavior_qs = BehaviorIncident.objects.all()
        behavior_counts = dict(
            behavior_qs.values('incident_type').annotate(total=Count('id')).values_list('incident_type', 'total')
        )

        return {
            "students_active": students_qs.count(),
            "enrollments_active": enrollments_qs.count(),
            "demographics": gender_counts,
            "attendance": {
                "attendance_rate": attendance_rate,
                "present": present,
                "absent": absent,
                "late": late,
            },
            "behavior": behavior_counts,
        }

    def get(self, request):
        return Response(self.build_report_data(), status=status.HTTP_200_OK)


class StudentReportView(APIView):
    """
    Individual student report summary for printing.
    """
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    @staticmethod
    def build_report_data(student_id):
        try:
            student = Student.objects.get(id=student_id)
        except Student.DoesNotExist:
            return None

        guardians = list(student.guardians.values('id', 'name', 'relationship', 'phone', 'email'))
        enrollment = Enrollment.objects.filter(student=student, is_active=True).order_by('-id').first()

        attendance_qs = AttendanceRecord.objects.filter(student=student)
        total_attendance = attendance_qs.count()
        present = attendance_qs.filter(status='Present').count()
        absent = attendance_qs.filter(status='Absent').count()
        late = attendance_qs.filter(status='Late').count()
        attendance_rate = round((present / total_attendance) * 100, 2) if total_attendance else 0

        behavior_qs = BehaviorIncident.objects.filter(student=student).order_by('-incident_date')[:10]
        behavior_items = list(behavior_qs.values('incident_type', 'category', 'incident_date', 'severity', 'description'))

        medical_record = MedicalRecord.objects.filter(student=student).first()
        clinic_visits = list(
            ClinicVisit.objects.filter(student=student).order_by('-visit_date')[:5].values(
                'visit_date', 'complaint', 'treatment', 'severity', 'parent_notified'
            )
        )

        documents = [
            {"id": doc.id, "name": doc.file.name, "url": doc.file.url, "uploaded_at": doc.uploaded_at}
            for doc in student.uploaded_documents.all()
        ]

        return {
            "student": {
                "id": student.id,
                "admission_number": student.admission_number,
                "first_name": student.first_name,
                "last_name": student.last_name,
                "gender": student.gender,
                "date_of_birth": student.date_of_birth,
                "photo": student.photo.url if student.photo else None,
            },
            "guardians": guardians,
            "enrollment": {
                "class_id": enrollment.school_class_id if enrollment else None,
                "term_id": enrollment.term_id if enrollment else None,
                "enrollment_date": enrollment.enrollment_date if enrollment else None,
            },
            "attendance": {
                "attendance_rate": attendance_rate,
                "present": present,
                "absent": absent,
                "late": late,
            },
            "behavior": behavior_items,
            "medical": {
                "record": MedicalRecordSerializer(medical_record).data if medical_record else None,
                "visits": clinic_visits,
            },
            "documents": documents,
        }

    def get(self, request, student_id):
        report = self.build_report_data(student_id)
        if report is None:
            return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(report, status=status.HTTP_200_OK)


class StudentOperationalSummaryView(APIView):
    """
    Consolidated operational data endpoint for Student Profile drilldown tabs.
    """
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    def get(self, request, student_id):
        try:
            student = Student.objects.get(id=student_id)
        except Student.DoesNotExist:
            return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

        attendance_qs = AttendanceRecord.objects.filter(student=student)
        total_attendance = attendance_qs.count()
        present = attendance_qs.filter(status='Present').count()
        absent = attendance_qs.filter(status='Absent').count()
        late = attendance_qs.filter(status='Late').count()
        attendance_rate = round((present / total_attendance) * 100, 2) if total_attendance else 0

        attendance_records = list(
            attendance_qs.order_by('-date', '-created_at').values(
                'id', 'date', 'status', 'notes'
            )[:10]
        )

        behavior_records = list(
            BehaviorIncident.objects.filter(student=student)
            .order_by('-incident_date', '-created_at')
            .values('id', 'incident_type', 'category', 'incident_date', 'severity', 'description')[:10]
        )

        medical_record = MedicalRecord.objects.filter(student=student).first()
        clinic_visits = list(
            ClinicVisit.objects.filter(student=student)
            .order_by('-visit_date', '-created_at')
            .values('id', 'visit_date', 'complaint', 'treatment', 'severity', 'parent_notified')[:5]
        )

        return Response(
            {
                "attendance": {
                    "summary": {
                        "attendance_rate": attendance_rate,
                        "present": present,
                        "absent": absent,
                        "late": late,
                        "period_label": "All time",
                    },
                    "records": attendance_records,
                },
                "behavior": behavior_records,
                "academics": [],
                "medical": {
                    "record": MedicalRecordSerializer(medical_record).data if medical_record else None,
                    "visits": clinic_visits,
                },
            },
            status=status.HTTP_200_OK,
        )


class StudentsModuleReportCsvExportView(APIView):
    """
    CSV export for module-wide students report.
    """
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    def get(self, request):
        report = StudentsModuleReportView.build_report_data()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="students_module_report.csv"'
        writer = _SafeCsvWriter(response)
        writer.writerow(['section', 'metric', 'value'])
        writer.writerow(['summary', 'students_active', report.get('students_active', 0)])
        writer.writerow(['summary', 'enrollments_active', report.get('enrollments_active', 0)])

        attendance = report.get('attendance', {})
        writer.writerow(['attendance', 'attendance_rate', attendance.get('attendance_rate', 0)])
        writer.writerow(['attendance', 'present', attendance.get('present', 0)])
        writer.writerow(['attendance', 'absent', attendance.get('absent', 0)])
        writer.writerow(['attendance', 'late', attendance.get('late', 0)])

        for gender, total in (report.get('demographics') or {}).items():
            writer.writerow(['demographics', gender, total])

        for incident_type, total in (report.get('behavior') or {}).items():
            writer.writerow(['behavior', incident_type, total])

        return response


class StudentReportCsvExportView(APIView):
    """
    CSV export for individual student report.
    """
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    def get(self, request, student_id):
        report = StudentReportView.build_report_data(student_id)
        if report is None:
            return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="student_report_{student_id}.csv"'
        writer = _SafeCsvWriter(response)
        writer.writerow(['section', 'field', 'value'])

        student = report.get('student', {})
        writer.writerow(['student', 'id', student.get('id')])
        writer.writerow(['student', 'admission_number', student.get('admission_number')])
        writer.writerow(['student', 'first_name', student.get('first_name')])
        writer.writerow(['student', 'last_name', student.get('last_name')])
        writer.writerow(['student', 'gender', student.get('gender')])
        writer.writerow(['student', 'date_of_birth', student.get('date_of_birth')])

        enrollment = report.get('enrollment', {})
        writer.writerow(['enrollment', 'class_id', enrollment.get('class_id')])
        writer.writerow(['enrollment', 'term_id', enrollment.get('term_id')])
        writer.writerow(['enrollment', 'enrollment_date', enrollment.get('enrollment_date')])

        attendance = report.get('attendance', {})
        writer.writerow(['attendance', 'attendance_rate', attendance.get('attendance_rate')])
        writer.writerow(['attendance', 'present', attendance.get('present')])
        writer.writerow(['attendance', 'absent', attendance.get('absent')])
        writer.writerow(['attendance', 'late', attendance.get('late')])

        for guardian in report.get('guardians', []):
            writer.writerow(['guardian', 'name', guardian.get('name')])
            writer.writerow(['guardian', 'relationship', guardian.get('relationship')])
            writer.writerow(['guardian', 'phone', guardian.get('phone')])
            writer.writerow(['guardian', 'email', guardian.get('email')])

        for incident in report.get('behavior', []):
            writer.writerow(['behavior', 'incident_type', incident.get('incident_type')])
            writer.writerow(['behavior', 'category', incident.get('category')])
            writer.writerow(['behavior', 'incident_date', incident.get('incident_date')])
            writer.writerow(['behavior', 'severity', incident.get('severity')])
            writer.writerow(['behavior', 'description', incident.get('description')])

        medical_record = (report.get('medical') or {}).get('record') or {}
        writer.writerow(['medical', 'blood_type', medical_record.get('blood_type')])
        writer.writerow(['medical', 'allergies', medical_record.get('allergies')])
        writer.writerow(['medical', 'chronic_conditions', medical_record.get('chronic_conditions')])
        writer.writerow(['medical', 'current_medications', medical_record.get('current_medications')])
        writer.writerow(['medical', 'doctor_name', medical_record.get('doctor_name')])
        writer.writerow(['medical', 'doctor_phone', medical_record.get('doctor_phone')])

        for visit in (report.get('medical') or {}).get('visits', []):
            writer.writerow(['clinic_visit', 'visit_date', visit.get('visit_date')])
            writer.writerow(['clinic_visit', 'complaint', visit.get('complaint')])
            writer.writerow(['clinic_visit', 'treatment', visit.get('treatment')])
            writer.writerow(['clinic_visit', 'severity', visit.get('severity')])
            writer.writerow(['clinic_visit', 'parent_notified', visit.get('parent_notified')])

        for doc in report.get('documents', []):
            writer.writerow(['document', 'name', doc.get('name')])
            writer.writerow(['document', 'url', doc.get('url')])
            writer.writerow(['document', 'uploaded_at', doc.get('uploaded_at')])

        return response


def _resolve_tenant_pdf_meta(request):
    profile = SchoolProfile.objects.filter(is_active=True).first()
    tenant = getattr(request, "tenant", None)
    return {
        "school_name": (profile.school_name if profile else None) or getattr(tenant, "name", None) or getattr(tenant, "schema_name", "Tenant"),
        "address": profile.address if profile else "",
        "phone": profile.phone if profile else "",
        "logo_path": profile.logo.path if profile and profile.logo else None,
        "schema": getattr(tenant, "schema_name", None),
    }


def _safe_cell(value):
    if value is None:
        return ""
    return str(value)


def _students_directory_queryset(request):
    queryset = Student.objects.all().order_by('-id')
    search = (request.query_params.get('search') or '').strip()
    gender = (request.query_params.get('gender') or '').strip()
    is_active = request.query_params.get('is_active')

    if search:
        queryset = queryset.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(admission_number__icontains=search)
        )
    if gender:
        queryset = queryset.filter(gender=gender)
    if is_active is not None and str(is_active).strip() != '':
        normalized = str(is_active).lower()
        if normalized in ('true', '1'):
            queryset = queryset.filter(is_active=True)
        elif normalized in ('false', '0'):
            queryset = queryset.filter(is_active=False)
    return queryset


def _student_documents_queryset(request):
    queryset = StudentDocument.objects.select_related('student').all().order_by('-uploaded_at')
    student_id = request.query_params.get('student_id') or request.query_params.get('student')
    search = (request.query_params.get('search') or '').strip()
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    if student_id:
        queryset = queryset.filter(student_id=student_id)
    if search:
        queryset = queryset.filter(
            Q(file__icontains=search)
            | Q(student__admission_number__icontains=search)
            | Q(student__first_name__icontains=search)
            | Q(student__last_name__icontains=search)
        )
    if date_from:
        queryset = queryset.filter(uploaded_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(uploaded_at__date__lte=date_to)
    return queryset


class StudentsModuleReportPdfExportView(APIView):
    """
    PDF export for module-wide students report.
    """
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    def get(self, request):
        try:
            from io import BytesIO
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        except ImportError:
            return Response(
                {"error": "PDF export dependency missing. Install reportlab."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        report = StudentsModuleReportView.build_report_data()
        tenant_meta = _resolve_tenant_pdf_meta(request)

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, title="Students Module Report")
        styles = getSampleStyleSheet()
        story = []

        if tenant_meta.get("logo_path"):
            try:
                story.append(Image(tenant_meta["logo_path"], width=48, height=48))
            except Exception:
                pass

        story.append(Paragraph(f"<b>{_safe_cell(tenant_meta.get('school_name'))}</b>", styles["Title"]))
        story.append(Paragraph(f"Tenant: {_safe_cell(tenant_meta.get('schema'))}", styles["Normal"]))
        if tenant_meta.get("address"):
            story.append(Paragraph(_safe_cell(tenant_meta["address"]), styles["Normal"]))
        if tenant_meta.get("phone"):
            story.append(Paragraph(f"Phone: {_safe_cell(tenant_meta['phone'])}", styles["Normal"]))
        story.append(Spacer(1, 12))

        story.append(Paragraph("<b>Students Module Report</b>", styles["Heading2"]))
        story.append(Spacer(1, 6))

        summary_data = [
            ["Metric", "Value"],
            ["Active Students", _safe_cell(report.get("students_active"))],
            ["Active Enrollments", _safe_cell(report.get("enrollments_active"))],
            ["Attendance Rate", f"{_safe_cell((report.get('attendance') or {}).get('attendance_rate'))}%"],
            ["Present", _safe_cell((report.get("attendance") or {}).get("present"))],
            ["Absent", _safe_cell((report.get("attendance") or {}).get("absent"))],
            ["Late", _safe_cell((report.get("attendance") or {}).get("late"))],
        ]
        summary_table = Table(summary_data, colWidths=[220, 220])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 12))

        demographics = report.get("demographics") or {}
        if demographics:
            story.append(Paragraph("<b>Demographics</b>", styles["Heading3"]))
            demo_rows = [["Gender", "Count"]] + [[_safe_cell(k), _safe_cell(v)] for k, v in demographics.items()]
            demo_table = Table(demo_rows, colWidths=[220, 220])
            demo_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ]))
            story.append(demo_table)
            story.append(Spacer(1, 12))

        behavior = report.get("behavior") or {}
        if behavior:
            story.append(Paragraph("<b>Behavior Summary</b>", styles["Heading3"]))
            behavior_rows = [["Incident Type", "Count"]] + [[_safe_cell(k), _safe_cell(v)] for k, v in behavior.items()]
            behavior_table = Table(behavior_rows, colWidths=[220, 220])
            behavior_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ]))
            story.append(behavior_table)

        doc.build(story)
        pdf_data = buffer.getvalue()
        buffer.close()

        response = HttpResponse(pdf_data, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="students_module_report.pdf"'
        return response


class StudentReportPdfExportView(APIView):
    """
    PDF export for individual student report.
    """
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    def get(self, request, student_id):
        try:
            from io import BytesIO
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        except ImportError:
            return Response(
                {"error": "PDF export dependency missing. Install reportlab."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        report = StudentReportView.build_report_data(student_id)
        if report is None:
            return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

        tenant_meta = _resolve_tenant_pdf_meta(request)
        student = report.get("student", {})
        attendance = report.get("attendance") or {}
        enrollment = report.get("enrollment") or {}

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, title="Student Report")
        styles = getSampleStyleSheet()
        story = []

        if tenant_meta.get("logo_path"):
            try:
                story.append(Image(tenant_meta["logo_path"], width=48, height=48))
            except Exception:
                pass

        story.append(Paragraph(f"<b>{_safe_cell(tenant_meta.get('school_name'))}</b>", styles["Title"]))
        story.append(Paragraph(f"Tenant: {_safe_cell(tenant_meta.get('schema'))}", styles["Normal"]))
        if tenant_meta.get("address"):
            story.append(Paragraph(_safe_cell(tenant_meta["address"]), styles["Normal"]))
        if tenant_meta.get("phone"):
            story.append(Paragraph(f"Phone: {_safe_cell(tenant_meta['phone'])}", styles["Normal"]))
        story.append(Spacer(1, 12))

        story.append(
            Paragraph(
                f"<b>Student Report: {_safe_cell(student.get('first_name'))} {_safe_cell(student.get('last_name'))}</b>",
                styles["Heading2"],
            )
        )

        student_data = [
            ["Field", "Value"],
            ["Admission Number", _safe_cell(student.get("admission_number"))],
            ["Gender", _safe_cell(student.get("gender"))],
            ["Date of Birth", _safe_cell(student.get("date_of_birth"))],
            ["Class ID", _safe_cell(enrollment.get("class_id"))],
            ["Term ID", _safe_cell(enrollment.get("term_id"))],
            ["Enrollment Date", _safe_cell(enrollment.get("enrollment_date"))],
            ["Attendance Rate", f"{_safe_cell(attendance.get('attendance_rate'))}%"],
            ["Present", _safe_cell(attendance.get("present"))],
            ["Absent", _safe_cell(attendance.get("absent"))],
            ["Late", _safe_cell(attendance.get("late"))],
        ]
        student_table = Table(student_data, colWidths=[200, 240])
        student_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ]))
        story.append(student_table)
        story.append(Spacer(1, 12))

        guardians = report.get("guardians") or []
        if guardians:
            story.append(Paragraph("<b>Guardians</b>", styles["Heading3"]))
            guardian_rows = [["Name", "Relationship", "Phone", "Email"]]
            for guardian in guardians:
                guardian_rows.append([
                    _safe_cell(guardian.get("name")),
                    _safe_cell(guardian.get("relationship")),
                    _safe_cell(guardian.get("phone")),
                    _safe_cell(guardian.get("email")),
                ])
            guardian_table = Table(guardian_rows, colWidths=[120, 110, 100, 110])
            guardian_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]))
            story.append(guardian_table)
            story.append(Spacer(1, 12))

        behavior_items = report.get("behavior") or []
        if behavior_items:
            story.append(Paragraph("<b>Behavior (Latest)</b>", styles["Heading3"]))
            behavior_rows = [["Type", "Category", "Date", "Severity"]]
            for incident in behavior_items:
                behavior_rows.append([
                    _safe_cell(incident.get("incident_type")),
                    _safe_cell(incident.get("category")),
                    _safe_cell(incident.get("incident_date")),
                    _safe_cell(incident.get("severity")),
                ])
            behavior_table = Table(behavior_rows, colWidths=[100, 160, 100, 80])
            behavior_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]))
            story.append(behavior_table)
            story.append(Spacer(1, 12))

        documents = report.get("documents") or []
        if documents:
            story.append(Paragraph("<b>Documents</b>", styles["Heading3"]))
            doc_rows = [["Name", "Uploaded At"]]
            for doc_item in documents:
                doc_rows.append([
                    _safe_cell(doc_item.get("name")),
                    _safe_cell(doc_item.get("uploaded_at")),
                ])
            doc_table = Table(doc_rows, colWidths=[300, 140])
            doc_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]))
            story.append(doc_table)

        doc.build(story)
        pdf_data = buffer.getvalue()
        buffer.close()

        response = HttpResponse(pdf_data, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="student_report_{student_id}.pdf"'
        return response


class StudentsDirectoryCsvExportView(APIView):
    """CSV export for student directory."""
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    def get(self, request):
        queryset = _students_directory_queryset(request)
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="students_directory.csv"'
        writer = _SafeCsvWriter(response)
        writer.writerow(['admission_number', 'first_name', 'last_name', 'gender', 'date_of_birth', 'status'])
        for student in queryset:
            writer.writerow([
                student.admission_number,
                student.first_name,
                student.last_name,
                student.gender,
                student.date_of_birth,
                'Active' if student.is_active else 'Inactive',
            ])
        return response


class StudentsDirectoryPdfExportView(APIView):
    """PDF export for student directory."""
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    def get(self, request):
        try:
            from io import BytesIO
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        except ImportError:
            return Response(
                {"error": "PDF export dependency missing. Install reportlab."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        queryset = _students_directory_queryset(request)
        tenant_meta = _resolve_tenant_pdf_meta(request)
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, title="Students Directory")
        styles = getSampleStyleSheet()
        story = []

        if tenant_meta.get("logo_path"):
            try:
                story.append(Image(tenant_meta["logo_path"], width=48, height=48))
            except Exception:
                pass

        story.append(Paragraph(f"<b>{_safe_cell(tenant_meta.get('school_name'))}</b>", styles["Title"]))
        story.append(Paragraph(f"Tenant: {_safe_cell(tenant_meta.get('schema'))}", styles["Normal"]))
        if tenant_meta.get("address"):
            story.append(Paragraph(_safe_cell(tenant_meta["address"]), styles["Normal"]))
        if tenant_meta.get("phone"):
            story.append(Paragraph(f"Phone: {_safe_cell(tenant_meta['phone'])}", styles["Normal"]))
        story.append(Spacer(1, 12))
        story.append(Paragraph("<b>Students Directory</b>", styles["Heading2"]))
        story.append(Spacer(1, 6))

        rows = [['Admission #', 'Name', 'Gender', 'DOB', 'Status']]
        for student in queryset[:300]:
            rows.append([
                _safe_cell(student.admission_number),
                _safe_cell(f"{student.first_name} {student.last_name}"),
                _safe_cell(student.gender),
                _safe_cell(student.date_of_birth),
                'Active' if student.is_active else 'Inactive',
            ])

        table = Table(rows, colWidths=[90, 150, 70, 90, 70])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
        ]))
        story.append(table)

        if queryset.count() > 300:
            story.append(Spacer(1, 8))
            story.append(Paragraph("Note: Export truncated to first 300 rows for PDF readability.", styles["Italic"]))

        doc.build(story)
        pdf_data = buffer.getvalue()
        buffer.close()

        response = HttpResponse(pdf_data, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="students_directory.pdf"'
        return response


class MedicalProfilesCsvExportView(APIView):
    """CSV export for student medical profiles."""
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    def get(self, request):
        queryset = MedicalRecord.objects.select_related('student').all().order_by('-updated_at')
        student_id = request.query_params.get('student_id') or request.query_params.get('student')
        if student_id:
            queryset = queryset.filter(student_id=student_id)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="medical_profiles_report.csv"'
        writer = _SafeCsvWriter(response)
        writer.writerow([
            'student_name', 'student_id', 'blood_type', 'allergies', 'chronic_conditions',
            'current_medications', 'doctor_name', 'doctor_phone', 'updated_at'
        ])
        for row in queryset:
            writer.writerow([
                f"{row.student.first_name} {row.student.last_name}".strip(),
                row.student_id,
                row.blood_type or '',
                row.allergies or '',
                row.chronic_conditions or '',
                row.current_medications or '',
                row.doctor_name or '',
                row.doctor_phone or '',
                row.updated_at,
            ])
        return response


class MedicalProfilesPdfExportView(APIView):
    """PDF export for student medical profiles."""
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    def get(self, request):
        try:
            from io import BytesIO
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        except ImportError:
            return Response(
                {"error": "PDF export dependency missing. Install reportlab."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        queryset = MedicalRecord.objects.select_related('student').all().order_by('-updated_at')
        student_id = request.query_params.get('student_id') or request.query_params.get('student')
        if student_id:
            queryset = queryset.filter(student_id=student_id)

        tenant_meta = _resolve_tenant_pdf_meta(request)
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, title="Medical Profiles Report")
        styles = getSampleStyleSheet()
        story = []

        if tenant_meta.get("logo_path"):
            try:
                story.append(Image(tenant_meta["logo_path"], width=48, height=48))
            except Exception:
                pass
        story.append(Paragraph(f"<b>{_safe_cell(tenant_meta.get('school_name'))}</b>", styles["Title"]))
        story.append(Paragraph("<b>Medical Profiles Report</b>", styles["Heading2"]))
        story.append(Spacer(1, 8))

        rows = [["Student", "Blood Type", "Allergies", "Updated"]]
        for row in queryset[:300]:
            rows.append([
                _safe_cell(f"{row.student.first_name} {row.student.last_name}"),
                _safe_cell(row.blood_type),
                _safe_cell((row.allergies or '')[:40]),
                _safe_cell(row.updated_at.date()),
            ])
        table = Table(rows, colWidths=[160, 70, 170, 70])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
        ]))
        story.append(table)
        doc.build(story)

        pdf_data = buffer.getvalue()
        buffer.close()
        response = HttpResponse(pdf_data, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="medical_profiles_report.pdf"'
        return response


class MedicalImmunizationsCsvExportView(APIView):
    """CSV export for student immunizations."""
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    def get(self, request):
        queryset = ImmunizationRecord.objects.select_related('student').all().order_by('-date_administered', '-created_at')
        student_id = request.query_params.get('student_id') or request.query_params.get('student')
        if student_id:
            queryset = queryset.filter(student_id=student_id)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="medical_immunizations_report.csv"'
        writer = _SafeCsvWriter(response)
        writer.writerow(['student_name', 'student_id', 'vaccine_name', 'date_administered', 'booster_due_date'])
        for row in queryset:
            writer.writerow([
                f"{row.student.first_name} {row.student.last_name}".strip(),
                row.student_id,
                row.vaccine_name,
                row.date_administered,
                row.booster_due_date or '',
            ])
        return response


class MedicalImmunizationsPdfExportView(APIView):
    """PDF export for student immunizations."""
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    def get(self, request):
        try:
            from io import BytesIO
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        except ImportError:
            return Response(
                {"error": "PDF export dependency missing. Install reportlab."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        queryset = ImmunizationRecord.objects.select_related('student').all().order_by('-date_administered', '-created_at')
        student_id = request.query_params.get('student_id') or request.query_params.get('student')
        if student_id:
            queryset = queryset.filter(student_id=student_id)

        tenant_meta = _resolve_tenant_pdf_meta(request)
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, title="Medical Immunizations Report")
        styles = getSampleStyleSheet()
        story = []
        if tenant_meta.get("logo_path"):
            try:
                story.append(Image(tenant_meta["logo_path"], width=48, height=48))
            except Exception:
                pass
        story.append(Paragraph(f"<b>{_safe_cell(tenant_meta.get('school_name'))}</b>", styles["Title"]))
        story.append(Paragraph("<b>Medical Immunizations Report</b>", styles["Heading2"]))
        story.append(Spacer(1, 8))

        rows = [["Student", "Vaccine", "Date", "Booster Due"]]
        for row in queryset[:300]:
            rows.append([
                _safe_cell(f"{row.student.first_name} {row.student.last_name}"),
                _safe_cell(row.vaccine_name),
                _safe_cell(row.date_administered),
                _safe_cell(row.booster_due_date),
            ])
        table = Table(rows, colWidths=[140, 150, 80, 100])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
        ]))
        story.append(table)
        doc.build(story)

        pdf_data = buffer.getvalue()
        buffer.close()
        response = HttpResponse(pdf_data, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="medical_immunizations_report.pdf"'
        return response


class MedicalClinicVisitsCsvExportView(APIView):
    """CSV export for clinic visits."""
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    def get(self, request):
        queryset = ClinicVisit.objects.select_related('student').all().order_by('-visit_date', '-created_at')
        student_id = request.query_params.get('student_id') or request.query_params.get('student')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        if date_from:
            queryset = queryset.filter(visit_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(visit_date__lte=date_to)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="medical_clinic_visits_report.csv"'
        writer = _SafeCsvWriter(response)
        writer.writerow(['student_name', 'student_id', 'visit_date', 'complaint', 'treatment', 'severity', 'parent_notified'])
        for row in queryset:
            writer.writerow([
                f"{row.student.first_name} {row.student.last_name}".strip(),
                row.student_id,
                row.visit_date,
                row.complaint or '',
                row.treatment or '',
                row.severity or '',
                'Yes' if row.parent_notified else 'No',
            ])
        return response


class MedicalClinicVisitsPdfExportView(APIView):
    """PDF export for clinic visits."""
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    def get(self, request):
        try:
            from io import BytesIO
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        except ImportError:
            return Response(
                {"error": "PDF export dependency missing. Install reportlab."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        queryset = ClinicVisit.objects.select_related('student').all().order_by('-visit_date', '-created_at')
        student_id = request.query_params.get('student_id') or request.query_params.get('student')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        if date_from:
            queryset = queryset.filter(visit_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(visit_date__lte=date_to)

        tenant_meta = _resolve_tenant_pdf_meta(request)
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, title="Clinic Visits Report")
        styles = getSampleStyleSheet()
        story = []
        if tenant_meta.get("logo_path"):
            try:
                story.append(Image(tenant_meta["logo_path"], width=48, height=48))
            except Exception:
                pass
        story.append(Paragraph(f"<b>{_safe_cell(tenant_meta.get('school_name'))}</b>", styles["Title"]))
        story.append(Paragraph("<b>Clinic Visits Report</b>", styles["Heading2"]))
        story.append(Spacer(1, 8))

        rows = [["Student", "Visit Date", "Complaint", "Severity", "Parent Notified"]]
        for row in queryset[:300]:
            rows.append([
                _safe_cell(f"{row.student.first_name} {row.student.last_name}"),
                _safe_cell(row.visit_date),
                _safe_cell((row.complaint or '')[:35]),
                _safe_cell(row.severity),
                'Yes' if row.parent_notified else 'No',
            ])
        table = Table(rows, colWidths=[120, 80, 160, 60, 80])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
        ]))
        story.append(table)
        doc.build(story)

        pdf_data = buffer.getvalue()
        buffer.close()
        response = HttpResponse(pdf_data, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="medical_clinic_visits_report.pdf"'
        return response


class StudentsDocumentsCsvExportView(APIView):
    """CSV export for student documents register."""
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    def get(self, request):
        queryset = _student_documents_queryset(request)
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="students_documents_report.csv"'
        writer = _SafeCsvWriter(response)
        writer.writerow(['student_name', 'admission_number', 'file_name', 'file_url', 'uploaded_at'])
        for doc in queryset:
            file_url = doc.file.url if doc.file else ''
            writer.writerow([
                f"{doc.student.first_name} {doc.student.last_name}".strip(),
                doc.student.admission_number,
                _display_document_name(doc.file),
                request.build_absolute_uri(file_url) if file_url else '',
                doc.uploaded_at,
            ])
        return response


class StudentsDocumentsPdfExportView(APIView):
    """PDF export for student documents register."""
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    def get(self, request):
        try:
            from io import BytesIO
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        except ImportError:
            return Response(
                {"error": "PDF export dependency missing. Install reportlab."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        queryset = _student_documents_queryset(request)
        tenant_meta = _resolve_tenant_pdf_meta(request)
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, title="Students Documents Report")
        styles = getSampleStyleSheet()
        story = []
        if tenant_meta.get("logo_path"):
            try:
                story.append(Image(tenant_meta["logo_path"], width=48, height=48))
            except Exception:
                pass
        story.append(Paragraph(f"<b>{_safe_cell(tenant_meta.get('school_name'))}</b>", styles["Title"]))
        story.append(Paragraph("<b>Students Documents Report</b>", styles["Heading2"]))
        story.append(Spacer(1, 8))

        rows = [["Student", "Admission #", "File", "Uploaded At"]]
        for doc_row in queryset[:300]:
            rows.append([
                _safe_cell(f"{doc_row.student.first_name} {doc_row.student.last_name}"),
                _safe_cell(doc_row.student.admission_number),
                _safe_cell(doc_row.file.name.split('/')[-1] if doc_row.file else ''),
                _safe_cell(doc_row.uploaded_at.date()),
            ])
        table = Table(rows, colWidths=[130, 90, 150, 90])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
        ]))
        story.append(table)
        doc.build(story)

        pdf_data = buffer.getvalue()
        buffer.close()
        response = HttpResponse(pdf_data, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="students_documents_report.pdf"'
        return response


class AcademicsSummaryView(APIView):
    """
    Summary endpoint for Academics module.
    """
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "ACADEMICS"

    def get(self, request):
        return Response(AcademicsService.get_summary())

class HrSummaryView(APIView):
    """
    Summary endpoint for Human Resources module.
    """
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "HR"

    def get(self, request):
        return Response(HrService.get_summary())

class CommunicationSummaryView(APIView):
    """
    Summary endpoint for Communication module.
    """
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "COMMUNICATION"

    def get(self, request):
        return Response(CommunicationService.get_summary())

class CoreSummaryView(APIView):
    """
    Summary endpoint for Core Administration module.
    """
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "CORE"

    def get(self, request):
        return Response(CoreService.get_summary())

class ReportingSummaryView(APIView):
    """
    Summary endpoint for Reporting module.
    """
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "REPORTING"

    def get(self, request):
        return Response(ReportingService.get_summary())

class FinanceStudentRefView(APIView):
    """
    Read-only reference data for Finance module.
    """
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        is_active = request.query_params.get('active')
        class_id = request.query_params.get('class_id')
        term_id = request.query_params.get('term_id')
        order_by = request.query_params.get('order_by', 'admission_number')
        order_dir = request.query_params.get('order_dir', 'asc')
        limit = request.query_params.get('limit')
        offset = request.query_params.get('offset')

        allowed_order = {'id', 'admission_number', 'first_name', 'last_name'}
        if order_by not in allowed_order:
            order_by = 'admission_number'
        if order_dir == 'desc':
            order_by = f"-{order_by}"

        queryset = Student.objects.all()
        if is_active is None or is_active.lower() == 'true':
            queryset = queryset.filter(is_active=True)
        elif is_active.lower() == 'false':
            queryset = queryset.filter(is_active=False)

        if class_id or term_id:
            enrollments = Enrollment.objects.filter(is_active=True)
            if class_id:
                enrollments = enrollments.filter(school_class_id=class_id)
            if term_id:
                enrollments = enrollments.filter(term_id=term_id)
            queryset = queryset.filter(id__in=enrollments.values_list('student_id', flat=True))

        queryset = queryset.order_by(order_by)

        if limit is not None or offset is not None:
            try:
                limit_val = int(limit) if limit is not None else 50
                offset_val = int(offset) if offset is not None else 0
            except ValueError:
                return Response({"error": "limit and offset must be integers"}, status=status.HTTP_400_BAD_REQUEST)

            if limit_val > 200:
                limit_val = 200

            total = queryset.count()
            page = list(queryset[offset_val:offset_val + limit_val])
            serializer = FinanceStudentRefSerializer(page, many=True)
            next_offset = offset_val + limit_val
            if next_offset >= total:
                next_offset = None

            return Response({
                "count": total,
                "next_offset": next_offset,
                "results": serializer.data
            }, status=status.HTTP_200_OK)

        serializer = FinanceStudentRefSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class FinanceStudentDetailView(APIView):
    """
    Finance-safe student detail endpoint (includes guardians).
    This avoids requiring STUDENTS module access for finance workflows.
    """
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request, student_id):
        student = get_object_or_404(Student, id=student_id)
        serializer = StudentSerializer(student)
        return Response(serializer.data, status=status.HTTP_200_OK)

class FinanceEnrollmentRefView(APIView):
    """
    Read-only enrollment references for Finance module.
    """
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        is_active = request.query_params.get('active')
        class_id = request.query_params.get('class_id')
        term_id = request.query_params.get('term_id')
        student_id = request.query_params.get('student_id')
        order_by = request.query_params.get('order_by', 'id')
        order_dir = request.query_params.get('order_dir', 'asc')
        limit = request.query_params.get('limit')
        offset = request.query_params.get('offset')

        allowed_order = {'id', 'student_id', 'school_class_id', 'term_id'}
        if order_by not in allowed_order:
            order_by = 'id'
        if order_dir == 'desc':
            order_by = f"-{order_by}"

        queryset = Enrollment.objects.all()
        if is_active is None or is_active.lower() == 'true':
            queryset = queryset.filter(is_active=True)
        elif is_active.lower() == 'false':
            queryset = queryset.filter(is_active=False)

        if class_id:
            queryset = queryset.filter(school_class_id=class_id)
        if term_id:
            queryset = queryset.filter(term_id=term_id)
        if student_id:
            queryset = queryset.filter(student_id=student_id)

        queryset = queryset.order_by(order_by)

        if limit is not None or offset is not None:
            try:
                limit_val = int(limit) if limit is not None else 50
                offset_val = int(offset) if offset is not None else 0
            except ValueError:
                return Response({"error": "limit and offset must be integers"}, status=status.HTTP_400_BAD_REQUEST)

            if limit_val > 200:
                limit_val = 200

            total = queryset.count()
            page = list(queryset[offset_val:offset_val + limit_val])
            serializer = FinanceEnrollmentRefSerializer(page, many=True)
            next_offset = offset_val + limit_val
            if next_offset >= total:
                next_offset = None

            return Response({
                "count": total,
                "next_offset": next_offset,
                "results": serializer.data
            }, status=status.HTTP_200_OK)

        serializer = FinanceEnrollmentRefSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class FinanceClassRefView(APIView):
    """
    Returns active SchoolClass list with enrolled student counts.
    Used by fee-assignment-by-class form.
    """
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        term_id = request.query_params.get('term_id')
        qs = SchoolClass.objects.filter(is_active=True).order_by('name')
        result = []
        for sc in qs:
            enrollment_qs = Enrollment.objects.filter(school_class_id=sc.id, is_active=True)
            if term_id:
                enrollment_qs = enrollment_qs.filter(term_id=term_id)
            result.append({
                'id': sc.id,
                'name': sc.display_name,
                'stream': sc.stream,
                'student_count': enrollment_qs.count(),
            })
        return Response(result)


class BulkFeeAssignByClassView(APIView):
    """
    POST: Assigns a fee structure to every enrolled student in a given class/term.
    Body: { class_id, fee_structure_id, term_id (optional), discount_amount (optional) }
    Returns: { created, updated, skipped, student_count }
    """
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def post(self, request):
        class_id = request.data.get('class_id')
        fee_structure_id = request.data.get('fee_structure_id')
        term_id = request.data.get('term_id')
        discount_amount = request.data.get('discount_amount', 0)

        if not class_id:
            return Response({'error': 'class_id is required.'}, status=400)
        if not fee_structure_id:
            return Response({'error': 'fee_structure_id is required.'}, status=400)

        try:
            school_class = SchoolClass.objects.get(id=class_id)
        except SchoolClass.DoesNotExist:
            return Response({'error': 'Class not found.'}, status=404)

        try:
            fee_structure = FeeStructure.objects.get(id=fee_structure_id)
        except FeeStructure.DoesNotExist:
            return Response({'error': 'Fee structure not found.'}, status=404)

        try:
            discount = float(discount_amount or 0)
        except (ValueError, TypeError):
            return Response({'error': 'discount_amount must be a number.'}, status=400)

        enrollments = Enrollment.objects.filter(school_class_id=school_class.id, is_active=True)
        if term_id:
            enrollments = enrollments.filter(term_id=term_id)

        student_ids = list(enrollments.values_list('student_id', flat=True).distinct())
        if not student_ids:
            return Response({
                'created': 0, 'updated': 0, 'student_count': 0,
                'message': 'No enrolled students found in this class/term combination.'
            })

        created_count = 0
        updated_count = 0
        for student_id in student_ids:
            existing = FeeAssignment.objects.filter(
                student_id=student_id, fee_structure=fee_structure, is_active=True
            ).first()
            if existing:
                existing.discount_amount = discount
                existing.save(update_fields=['discount_amount'])
                updated_count += 1
            else:
                FeeAssignment.objects.create(
                    student_id=student_id,
                    fee_structure=fee_structure,
                    discount_amount=discount,
                    is_active=True,
                )
                created_count += 1

        return Response({
            'created': created_count,
            'updated': updated_count,
            'student_count': len(student_ids),
            'class_name': school_class.display_name,
            'fee_structure': fee_structure.name,
            'message': f'Assigned "{fee_structure.name}" to {len(student_ids)} students in {school_class.display_name}.',
        })


class SchoolDashboardView(APIView):
    """
    Executive Overview for Tenant Admin.
    Aggregates high-level counts. Read-Only.
    """
    permission_classes = [IsSchoolAdmin | IsAccountant, HasModuleAccess]
    module_key = "REPORTING"

    def get(self, request):
        return Response({
            "students_active": Student.objects.filter(is_active=True).count(),
            "staff_active": Staff.objects.filter(is_active=True).count(),
            "invoices_pending": Invoice.objects.filter(is_active=True, status='CONFIRMED').count(), # Approximate
            "enrollments_this_year": Enrollment.objects.filter(is_active=True).count()
        })

_ROLE_REDIRECT_PATHS = {
    'STUDENT': '/student-portal',
    'PARENT': '/modules/parent-portal/dashboard',
    'TEACHER': '/dashboard',
    'ACCOUNTANT': '/dashboard',
    'FINANCE_STAFF': '/dashboard',
    'OPERATIONS_STAFF': '/dashboard',
    'ADMIN': '/dashboard',
    'TENANT_SUPER_ADMIN': '/dashboard',
}


def _role_redirect_path(role_name):
    """Return the frontend path a user should land on given their role."""
    if not role_name:
        return '/dashboard'
    return _ROLE_REDIRECT_PATHS.get(role_name.upper(), '/dashboard')


def _post_login_redirect_path(role_name, user=None):
    """Resolve the final redirect path, including forced-password-change detours."""
    base_path = _role_redirect_path(role_name)
    if role_name and role_name.upper() == 'PARENT' and user is not None and _requires_password_change(user):
        return '/modules/parent-portal/library-profile?force_password_change=1'
    return base_path


def _normalize_login_identifier(identifier):
    return (identifier or '').strip()


def _normalize_phone_number(phone_value):
    return ''.join(ch for ch in str(phone_value or '') if ch.isdigit())


def _single_active_user(queryset):
    matches = list(queryset[:2])
    if len(matches) != 1:
        return None
    return matches[0]


def _resolve_user_from_login_identifier(identifier):
    normalized = _normalize_login_identifier(identifier)
    if not normalized:
        return None, None

    user_model = get_user_model()

    username_match = _single_active_user(
        user_model.objects.filter(username__iexact=normalized, is_active=True).order_by('id')
    )
    if username_match is not None:
        return username_match, 'username'

    email_match = _single_active_user(
        user_model.objects.filter(email__iexact=normalized, is_active=True).exclude(email='').order_by('id')
    )
    if email_match is not None:
        return email_match, 'email'

    normalized_phone = _normalize_phone_number(normalized)
    if not normalized_phone:
        return None, None

    phone_matches = []
    for profile in (
        UserProfile.objects
        .select_related('user')
        .filter(user__is_active=True)
        .exclude(phone='')
        .order_by('id')
    ):
        if _normalize_phone_number(profile.phone) == normalized_phone:
            phone_matches.append(profile.user)
            if len(phone_matches) > 1:
                return None, None
    if len(phone_matches) == 1:
        return phone_matches[0], 'phone'

    return None, None


class SmartCampusTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT login serializer.
    Four-stage fallback:
      1. Normal Django username auth
      2. Username/email/phone lookup on active accounts
      3. Student-only UserProfile.admission_number lookup
      4. Student.admission_number lookup      (students whose username == admission_number)

    Enriches the response with: role, available_roles, redirect_to, tenant_id.
    Writes a LOGIN AuditLog entry on every successful authentication.
    Embeds role + tenant_id as custom JWT claims.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        try:
            role = user.userprofile.role.name if (
                hasattr(user, 'userprofile') and user.userprofile and user.userprofile.role
            ) else None
            token['role'] = role
        except Exception:
            token['role'] = None
        try:
            token['tenant_id'] = getattr(connection, 'schema_name', 'public')
        except Exception:
            token['tenant_id'] = 'public'
        return token

    def _enrich(self, data, login_method='username'):
        """Add routing + tenant metadata to the token response and create audit log."""
        role_name = None
        force_password_change = False
        try:
            if hasattr(self.user, 'userprofile') and self.user.userprofile:
                force_password_change = bool(self.user.userprofile.force_password_change)
                if self.user.userprofile.role:
                    role_name = self.user.userprofile.role.name
        except Exception:
            pass

        tenant_id = getattr(connection, 'schema_name', 'public')
        redirect_to = _post_login_redirect_path(role_name, self.user)
        available_roles = [role_name] if role_name else []

        try:
            from school.models import AuditLog as _AuditLog
            _AuditLog.objects.create(
                user=self.user,
                action='LOGIN',
                model_name='User',
                object_id=str(self.user.id),
                details=json.dumps({
                    'role': role_name,
                    'tenant_id': tenant_id,
                    'redirect_to': redirect_to,
                    'event': 'login',
                    'login_method': login_method,
                    'force_password_change': force_password_change,
                }),
            )
        except Exception:
            pass

        data['role'] = role_name
        data['available_roles'] = available_roles
        data['redirect_to'] = redirect_to
        data['tenant_id'] = tenant_id
        data['force_password_change'] = force_password_change
        return data

    def _enrich_platform_admin(self, user, gsa):
        """Build a login response for a GlobalSuperAdmin who authenticated via public schema."""
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        refresh['role'] = gsa.role
        refresh['tenant_id'] = 'public'
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            },
            'role': gsa.role,
            'available_roles': [gsa.role],
            'redirect_to': '/platform',
            'tenant_id': 'public',
            'force_password_change': False,
        }

    def validate(self, attrs):
        username = _normalize_login_identifier(attrs.get(self.username_field, ''))
        password = attrs.get('password', '')
        attrs[self.username_field] = username

        # Stage 0: check public schema for GlobalSuperAdmin users
        try:
            from django_tenants.utils import schema_context, get_public_schema_name
            with schema_context(get_public_schema_name()):
                from django.contrib.auth.models import User as _PublicUser
                from clients.models import GlobalSuperAdmin
                pub_user = _PublicUser.objects.filter(
                    username__iexact=username, is_active=True
                ).first()
                if pub_user and pub_user.check_password(password):
                    gsa = GlobalSuperAdmin.objects.filter(user=pub_user, is_active=True).first()
                    if gsa:
                        self.user = pub_user
                        return self._enrich_platform_admin(pub_user, gsa)
        except Exception as _stage0_exc:
            import logging as _log
            _log.getLogger(__name__).warning(
                "Stage 0 (GlobalSuperAdmin check) failed for '%s': %s",
                username, _stage0_exc, exc_info=True,
            )

        # Stage 1: normal Django username auth
        try:
            data = super().validate(attrs)
            return self._enrich(data, login_method='username')
        except Exception:
            pass

        # Stage 2: username/email/phone lookup
        resolved_user, login_method = _resolve_user_from_login_identifier(username)
        if resolved_user is not None:
            user = authenticate(
                request=self.context.get('request'),
                username=resolved_user.username,
                password=password,
            )
            if user is not None:
                attrs[self.username_field] = resolved_user.username
                data = super().validate(attrs)
                return self._enrich(data, login_method=login_method)

        # Stage 3: student-only UserProfile admission bridge
        student_profile = _single_active_user(
            UserProfile.objects
            .select_related('user', 'role')
            .filter(
                admission_number__iexact=username,
                user__is_active=True,
                role__name='STUDENT',
            )
            .order_by('id')
        )
        if student_profile is not None:
            user = authenticate(
                request=self.context.get('request'),
                username=student_profile.user.username,
                password=password,
            )
            if user is not None:
                attrs[self.username_field] = student_profile.user.username
                data = super().validate(attrs)
                return self._enrich(data, login_method='student_admission_number_bridge')

        # Stage 4: Student admission number to username fallback
        try:
            student = Student.objects.get(admission_number__iexact=username, is_active=True)
            student_user = _single_active_user(
                get_user_model().objects.filter(
                    username__iexact=student.admission_number,
                    is_active=True,
                ).order_by('id')
            )
            if student_user is not None:
                attrs[self.username_field] = student_user.username
                data = super().validate(attrs)
                return self._enrich(data, login_method='student_username_admission_number')
        except Student.DoesNotExist:
            pass
        except Exception:
            pass

        # All stages failed - raise standard error
        raise ValidationError({'detail': 'No active account found with the given credentials.'})


class SmartCampusTokenObtainPairView(_BaseTokenView):
    serializer_class = SmartCampusTokenObtainPairSerializer


class RoleSwitchView(APIView):
    """
    POST /auth/role-switch/
    Body: { "role": "TEACHER" }
    Validates the requested role is available to the authenticated user,
    then returns new routing info. Logs the role switch in AuditLog.
    For multi-role users, this switches the active role within the session.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        requested_role = request.data.get('role', '').strip().upper()
        if not requested_role:
            return Response({'error': 'role is required.'}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        current_role = None
        try:
            if hasattr(user, 'userprofile') and user.userprofile and user.userprofile.role:
                current_role = user.userprofile.role.name
        except Exception:
            pass

        available_roles = [current_role] if current_role else []
        if requested_role not in available_roles:
            return Response(
                {'error': f'Role "{requested_role}" is not available for this account.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        tenant_id = getattr(connection, 'schema_name', 'public')
        redirect_to = _post_login_redirect_path(requested_role, user)

        try:
            from school.models import AuditLog as _AuditLog
            _AuditLog.objects.create(
                user=user,
                action='ROLE_SWITCH',
                model_name='User',
                object_id=str(user.id),
                details=json.dumps({
                    'from_role': current_role,
                    'to_role': requested_role,
                    'tenant_id': tenant_id,
                }),
            )
        except Exception:
            pass

        return Response({
            'role': requested_role,
            'available_roles': available_roles,
            'redirect_to': redirect_to,
            'tenant_id': tenant_id,
            'force_password_change': _requires_password_change(user),
        })


class DashboardRoutingView(APIView):
    """
    Returns routing instructions based on module assignments.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        role_name = None
        if hasattr(request.user, 'userprofile'):
            role_name = request.user.userprofile.role.name

        # Parent and Student roles go directly to their dedicated portals
        if role_name == 'PARENT':
            return Response({
                "user": request.user.username,
                "role": role_name,
                "available_roles": [role_name],
                "permissions": ["parent-portal:access"],
                "module_count": 1,
                "modules": [{"key": "PARENTS", "name": "Parent Portal"}],
                "target": "PARENT_PORTAL",
                "target_module": "PARENTS",
                "redirect_path": _post_login_redirect_path(role_name, request.user),
                "force_password_change": _requires_password_change(request.user),
            })

        if role_name == 'STUDENT':
            return Response({
                "user": request.user.username,
                "role": role_name,
                "available_roles": [role_name],
                "permissions": ["student-portal:access"],
                "module_count": 1,
                "modules": [{"key": "STUDENT_PORTAL", "name": "Student Portal"}],
                "target": "STUDENT_PORTAL",
                "target_module": "STUDENT_PORTAL",
                "redirect_path": _post_login_redirect_path(role_name, request.user),
                "force_password_change": _requires_password_change(request.user),
            })

        if role_name in ['ADMIN', 'TENANT_SUPER_ADMIN']:
            modules = list(Module.objects.filter(is_active=True).order_by('key').values('key', 'name'))
        else:
            assignments = UserModuleAssignment.objects.filter(
                is_active=True,
                user=request.user,
                module__is_active=True
            ).select_related('module').order_by('module__key')
            modules = [{'key': a.module.key, 'name': a.module.name} for a in assignments]

        modules = [module for module in modules if is_module_allowed(module.get("key"))]

        module_count = len(modules)
        if module_count == 1:
            target = "MODULE"
            target_module = modules[0]['key']
        else:
            target = "MAIN"
            target_module = None

        return Response({
            "user": request.user.username,
            "role": role_name,
            "available_roles": [role_name] if role_name else [],
            "permissions": self._build_permissions(role_name, modules),
            "module_count": module_count,
            "modules": modules,
            "target": target,
            "target_module": target_module,
            "redirect_path": _post_login_redirect_path(role_name, request.user),
            "force_password_change": _requires_password_change(request.user),
        })

    @staticmethod
    def _build_permissions(role_name, modules):
        permissions = {"settings:view"}
        module_keys = {m["key"] for m in modules}

        if role_name in ["ADMIN", "TENANT_SUPER_ADMIN"]:
            permissions.update({"settings:debug", "finance:settings:view"})
        elif role_name in ["ACCOUNTANT"]:
            permissions.add("finance:settings:view")

        if "FINANCE" in module_keys:
            permissions.add("finance:settings:view")

        return sorted(permissions)

class DashboardSummaryView(APIView):
    """
    Aggregated, read-only summaries across modules for the main dashboard.
    Phase 18 — Prompt 84: Caching strategy.
    Cache per tenant + user role for 2 minutes to reduce DB load.
    """
    permission_classes = [permissions.IsAuthenticated]
    CACHE_TTL = 120  # seconds

    def _cache_key(self, request) -> str:
        from django.db import connection as _conn
        schema = getattr(_conn, 'schema_name', 'public')
        user_id = request.user.id
        return f"dashboard_summary_{schema}_{user_id}"

    def get(self, request):
        cache_key = self._cache_key(request)
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        role_name = None
        if hasattr(request.user, 'userprofile'):
            role_name = request.user.userprofile.role.name

        if role_name in ['ADMIN', 'TENANT_SUPER_ADMIN']:
            modules = list(Module.objects.filter(is_active=True).order_by('key').values('key', 'name'))
        else:
            modules = list(UserModuleAssignment.objects.filter(
                is_active=True,
                user=request.user,
                module__is_active=True
            ).select_related('module').order_by('module__key').values('module__key', 'module__name'))

            # Normalize keys for non-admin users
            modules = [{'key': m['module__key'], 'name': m['module__name']} for m in modules]

        modules = [module for module in modules if is_module_allowed(module.get("key"))]

        module_keys = [m['key'] for m in modules]

        summary = {}
        unavailable = []

        if "STUDENTS" in module_keys:
            try:
                summary["students"] = {
                    "active": Student.objects.filter(is_active=True).count(),
                    "enrollments": Enrollment.objects.filter(is_active=True).count(),
                }
            except Exception:
                summary["students"] = {"active": 0, "enrollments": 0}
                unavailable.append("STUDENTS")

        if "ADMISSIONS" in module_keys:
            try:
                summary["admissions"] = {
                    "applications": AdmissionApplication.objects.count(),
                    "enrolled": AdmissionApplication.objects.filter(status="Enrolled").count(),
                }
            except Exception:
                summary["admissions"] = {"applications": 0, "enrolled": 0}
                unavailable.append("ADMISSIONS")

        if "HR" in module_keys:
            try:
                summary["hr"] = {
                    "staff_active": Staff.objects.filter(is_active=True).count()
                }
            except Exception:
                summary["hr"] = {"staff_active": 0}
                unavailable.append("HR")

        if "STAFF" in module_keys:
            try:
                from staff_mgmt.models import StaffMember

                summary["staff"] = {
                    "active": StaffMember.objects.filter(is_active=True).count(),
                }
            except Exception:
                summary["staff"] = {"active": 0}
                unavailable.append("STAFF")

        if "PARENTS" in module_keys:
            try:
                summary["parents"] = {
                    "guardian_profiles": Guardian.objects.filter(is_active=True).count(),
                }
            except Exception:
                summary["parents"] = {"guardian_profiles": 0}
                unavailable.append("PARENTS")

        if "LIBRARY" in module_keys:
            try:
                from library.models import (
                    CirculationTransaction,
                    FineRecord,
                    LibraryMember,
                    LibraryResource,
                )

                summary["library"] = {
                    "resources": LibraryResource.objects.filter(is_active=True).count(),
                    "members": LibraryMember.objects.filter(is_active=True).count(),
                    "active_borrowings": CirculationTransaction.objects.filter(
                        is_active=True,
                        transaction_type="Issue",
                        return_date__isnull=True,
                    ).count(),
                    "pending_fines": FineRecord.objects.filter(
                        is_active=True,
                        status="Pending",
                    ).count(),
                }
            except Exception:
                summary["library"] = {
                    "resources": 0,
                    "members": 0,
                    "active_borrowings": 0,
                    "pending_fines": 0,
                }
                unavailable.append("LIBRARY")

        if "FINANCE" in module_keys:
            try:
                invoice_total = Invoice.objects.aggregate(total=Sum('total_amount'))['total'] or 0
                payment_total = Payment.objects.aggregate(total=Sum('amount'))['total'] or 0
                expense_total = Expense.objects.aggregate(total=Sum('amount'))['total'] or 0
                summary["finance"] = {
                    "revenue_billed": float(invoice_total),
                    "cash_collected": float(payment_total),
                    "total_expenses": float(expense_total),
                    "net_profit": float(payment_total - expense_total),
                    "outstanding_receivables": float(invoice_total - payment_total)
                }
            except Exception:
                summary["finance"] = {
                    "revenue_billed": 0.0,
                    "cash_collected": 0.0,
                    "total_expenses": 0.0,
                    "net_profit": 0.0,
                    "outstanding_receivables": 0.0,
                }
                unavailable.append("FINANCE")

        if "REPORTING" in module_keys:
            try:
                summary["reporting"] = {
                    "invoices_pending": Invoice.objects.filter(is_active=True, status='CONFIRMED').count()
                }
            except Exception:
                summary["reporting"] = {"invoices_pending": 0}
                unavailable.append("REPORTING")

        if "STORE" in module_keys:
            try:
                summary["store"] = get_store_module_summary()
            except Exception:
                summary["store"] = {"total_items": 0, "low_stock": 0, "pending_orders": 0}
                unavailable.append("STORE")

        if "DISPENSARY" in module_keys:
            try:
                import datetime
                summary["dispensary"] = {
                    "visits_today": DispensaryVisit.objects.filter(visit_date=datetime.date.today()).count(),
                    "stock_items": DispensaryStock.objects.count(),
                    "low_stock": DispensaryStock.objects.filter(current_quantity__lte=models.F('reorder_level')).count(),
                }
            except Exception:
                summary["dispensary"] = {"visits_today": 0, "stock_items": 0, "low_stock": 0}
                unavailable.append("DISPENSARY")

        handled = {
            "STUDENTS",
            "ADMISSIONS",
            "HR",
            "FINANCE",
            "REPORTING",
            "ACADEMICS",
            "COMMUNICATION",
            "CORE",
            "ASSETS",
            "LIBRARY",
            "PARENTS",
            "STAFF",
            "STORE",
            "DISPENSARY",
            "CLOCKIN",
            "TIMETABLE",
            "TRANSPORT",
            "VISITOR_MGMT",
            "EXAMINATIONS",
            "ALUMNI",
            "HOSTEL",
            "PTM",
            "SPORTS",
            "CAFETERIA",
            "CURRICULUM",
            "MAINTENANCE",
            "ELEARNING",
            "ANALYTICS",
        }
        for key in module_keys:
            if key not in handled:
                unavailable.append(key)

        # Phase 18: cache dashboard summary for 2 minutes per tenant+user
        response_data = {
            "modules": module_keys,
            "modules_detail": modules,
            "unavailable_modules": sorted(list(set(unavailable))),
            "summary": summary
        }
        try:
            cache.set(cache_key, response_data, self.CACHE_TTL)
        except Exception:
            pass  # cache failure must never break the view
        return Response(response_data)

class FinanceSummaryCsvExportView(APIView):
    """CSV export for finance summary."""
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        report = FinanceService.get_summary()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="finance_summary_report.csv"'
        writer = _SafeCsvWriter(response)
        writer.writerow(['section', 'metric', 'value'])
        writer.writerow(['summary', 'revenue_billed', report.get('revenue_billed', 0)])
        writer.writerow(['summary', 'cash_collected', report.get('cash_collected', 0)])
        writer.writerow(['summary', 'total_expenses', report.get('total_expenses', 0)])
        writer.writerow(['summary', 'net_profit', report.get('net_profit', 0)])
        writer.writerow(['summary', 'outstanding_receivables', report.get('outstanding_receivables', 0)])
        writer.writerow(['summary', 'active_students_count', report.get('active_students_count', 0)])
        return response


class FinanceSummaryPdfExportView(APIView):
    """PDF export for finance summary."""
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        try:
            from io import BytesIO
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        except ImportError:
            return Response(
                {"error": "PDF export dependency missing. Install reportlab."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        report = FinanceService.get_summary()
        tenant_meta = _resolve_tenant_pdf_meta(request)

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, title="Finance Summary Report")
        styles = getSampleStyleSheet()
        story = []

        if tenant_meta.get("logo_path"):
            try:
                story.append(Image(tenant_meta["logo_path"], width=48, height=48))
            except Exception:
                pass

        story.append(Paragraph(f"<b>{_safe_cell(tenant_meta.get('school_name'))}</b>", styles["Title"]))
        story.append(Paragraph(f"Tenant: {_safe_cell(tenant_meta.get('schema'))}", styles["Normal"]))
        if tenant_meta.get("address"):
            story.append(Paragraph(_safe_cell(tenant_meta["address"]), styles["Normal"]))
        if tenant_meta.get("phone"):
            story.append(Paragraph(f"Phone: {_safe_cell(tenant_meta['phone'])}", styles["Normal"]))
        story.append(Spacer(1, 12))
        story.append(Paragraph("<b>Finance Summary Report</b>", styles["Heading2"]))
        story.append(Spacer(1, 6))

        summary_rows = [
            ["Metric", "Value"],
            ["Revenue Billed", _safe_cell(report.get("revenue_billed"))],
            ["Cash Collected", _safe_cell(report.get("cash_collected"))],
            ["Total Expenses", _safe_cell(report.get("total_expenses"))],
            ["Net Profit", _safe_cell(report.get("net_profit"))],
            ["Outstanding Receivables", _safe_cell(report.get("outstanding_receivables"))],
            ["Active Students", _safe_cell(report.get("active_students_count"))],
        ]
        summary_table = Table(summary_rows, colWidths=[220, 220])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ]))
        story.append(summary_table)

        doc.build(story)
        pdf_data = buffer.getvalue()
        buffer.close()

        response = HttpResponse(pdf_data, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="finance_summary_report.pdf"'
        return response

class AttendanceSummaryCsvExportView(APIView):
    """CSV export for attendance summary."""
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    def get(self, request):
        student_id = request.query_params.get('student_id')
        queryset = AttendanceRecord.objects.all()
        if student_id:
            queryset = queryset.filter(student_id=student_id)

        total = queryset.count()
        present = queryset.filter(status='Present').count()
        absent = queryset.filter(status='Absent').count()
        late = queryset.filter(status='Late').count()
        attendance_rate = round((present / total) * 100, 2) if total else 0

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="attendance_summary_report.csv"'
        writer = _SafeCsvWriter(response)
        writer.writerow(['section', 'metric', 'value'])
        writer.writerow(['summary', 'attendance_rate', attendance_rate])
        writer.writerow(['summary', 'present', present])
        writer.writerow(['summary', 'absent', absent])
        writer.writerow(['summary', 'late', late])
        writer.writerow(['summary', 'period_label', 'All time'])
        return response


class AttendanceSummaryPdfExportView(APIView):
    """PDF export for attendance summary."""
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    def get(self, request):
        try:
            from io import BytesIO
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        except ImportError:
            return Response(
                {"error": "PDF export dependency missing. Install reportlab."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        student_id = request.query_params.get('student_id')
        queryset = AttendanceRecord.objects.all()
        if student_id:
            queryset = queryset.filter(student_id=student_id)

        total = queryset.count()
        present = queryset.filter(status='Present').count()
        absent = queryset.filter(status='Absent').count()
        late = queryset.filter(status='Late').count()
        attendance_rate = round((present / total) * 100, 2) if total else 0

        tenant_meta = _resolve_tenant_pdf_meta(request)
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, title="Attendance Summary Report")
        styles = getSampleStyleSheet()
        story = []

        if tenant_meta.get("logo_path"):
            try:
                story.append(Image(tenant_meta["logo_path"], width=48, height=48))
            except Exception:
                pass

        story.append(Paragraph(f"<b>{_safe_cell(tenant_meta.get('school_name'))}</b>", styles["Title"]))
        story.append(Paragraph(f"Tenant: {_safe_cell(tenant_meta.get('schema'))}", styles["Normal"]))
        if tenant_meta.get("address"):
            story.append(Paragraph(_safe_cell(tenant_meta["address"]), styles["Normal"]))
        if tenant_meta.get("phone"):
            story.append(Paragraph(f"Phone: {_safe_cell(tenant_meta['phone'])}", styles["Normal"]))
        story.append(Spacer(1, 12))
        story.append(Paragraph("<b>Attendance Summary Report</b>", styles["Heading2"]))
        story.append(Spacer(1, 6))

        summary_rows = [
            ["Metric", "Value"],
            ["Attendance Rate", f"{attendance_rate}%"],
            ["Present", _safe_cell(present)],
            ["Absent", _safe_cell(absent)],
            ["Late", _safe_cell(late)],
            ["Period", "All time"],
        ]
        summary_table = Table(summary_rows, colWidths=[220, 220])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ]))
        story.append(summary_table)

        doc.build(story)
        pdf_data = buffer.getvalue()
        buffer.close()

        response = HttpResponse(pdf_data, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="attendance_summary_report.pdf"'
        return response


class AttendanceRecordsCsvExportView(APIView):
    """CSV export for attendance records."""
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    def get(self, request):
        queryset = AttendanceRecord.objects.select_related('student').all().order_by('-date', '-created_at')
        student_id = request.query_params.get('student_id') or request.query_params.get('student')
        status_param = request.query_params.get('status')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        if student_id:
            queryset = queryset.filter(student_id=student_id)
        if status_param:
            queryset = queryset.filter(status=status_param)
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="attendance_records_report.csv"'
        writer = _SafeCsvWriter(response)
        writer.writerow(['student_name', 'student_id', 'status', 'date', 'notes'])
        for record in queryset:
            writer.writerow([
                f"{record.student.first_name} {record.student.last_name}".strip(),
                record.student_id,
                record.status,
                record.date,
                record.notes or '',
            ])
        return response


class AttendanceRecordsPdfExportView(APIView):
    """PDF export for attendance records."""
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    def get(self, request):
        try:
            from io import BytesIO
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        except ImportError:
            return Response(
                {"error": "PDF export dependency missing. Install reportlab."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        queryset = AttendanceRecord.objects.select_related('student').all().order_by('-date', '-created_at')
        student_id = request.query_params.get('student_id') or request.query_params.get('student')
        status_param = request.query_params.get('status')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        if student_id:
            queryset = queryset.filter(student_id=student_id)
        if status_param:
            queryset = queryset.filter(status=status_param)
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)

        tenant_meta = _resolve_tenant_pdf_meta(request)
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, title="Attendance Records Report")
        styles = getSampleStyleSheet()
        story = []

        if tenant_meta.get("logo_path"):
            try:
                story.append(Image(tenant_meta["logo_path"], width=48, height=48))
            except Exception:
                pass

        story.append(Paragraph(f"<b>{_safe_cell(tenant_meta.get('school_name'))}</b>", styles["Title"]))
        story.append(Paragraph(f"Tenant: {_safe_cell(tenant_meta.get('schema'))}", styles["Normal"]))
        if tenant_meta.get("address"):
            story.append(Paragraph(_safe_cell(tenant_meta["address"]), styles["Normal"]))
        if tenant_meta.get("phone"):
            story.append(Paragraph(f"Phone: {_safe_cell(tenant_meta['phone'])}", styles["Normal"]))
        story.append(Spacer(1, 12))
        story.append(Paragraph("<b>Attendance Records Report</b>", styles["Heading2"]))
        story.append(Spacer(1, 6))

        table_rows = [["Student", "Status", "Date", "Notes"]]
        for record in queryset:
            table_rows.append([
                f"{record.student.first_name} {record.student.last_name}".strip(),
                record.status,
                _safe_cell(record.date),
                _safe_cell(record.notes),
            ])

        attendance_table = Table(table_rows, colWidths=[130, 80, 90, 170])
        attendance_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(attendance_table)

        doc.build(story)
        pdf_data = buffer.getvalue()
        buffer.close()

        response = HttpResponse(pdf_data, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="attendance_records_report.pdf"'
        return response


class BehaviorIncidentsCsvExportView(APIView):
    """CSV export for behavior incidents."""
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    def get(self, request):
        queryset = BehaviorIncident.objects.select_related('student').all().order_by('-incident_date', '-created_at')
        student_id = request.query_params.get('student_id') or request.query_params.get('student')
        incident_type = request.query_params.get('incident_type')
        severity = request.query_params.get('severity')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        if student_id:
            queryset = queryset.filter(student_id=student_id)
        if incident_type:
            queryset = queryset.filter(incident_type=incident_type)
        if severity:
            queryset = queryset.filter(severity=severity)
        if date_from:
            queryset = queryset.filter(incident_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(incident_date__lte=date_to)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="behavior_incidents_report.csv"'
        writer = _SafeCsvWriter(response)
        writer.writerow(['student_name', 'student_id', 'incident_type', 'category', 'incident_date', 'severity', 'description'])
        for incident in queryset:
            writer.writerow([
                f"{incident.student.first_name} {incident.student.last_name}".strip(),
                incident.student_id,
                incident.incident_type,
                incident.category,
                incident.incident_date,
                incident.severity or '',
                incident.description or '',
            ])
        return response


class BehaviorIncidentsPdfExportView(APIView):
    """PDF export for behavior incidents."""
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "STUDENTS"

    def get(self, request):
        try:
            from io import BytesIO
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        except ImportError:
            return Response(
                {"error": "PDF export dependency missing. Install reportlab."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        queryset = BehaviorIncident.objects.select_related('student').all().order_by('-incident_date', '-created_at')
        student_id = request.query_params.get('student_id') or request.query_params.get('student')
        incident_type = request.query_params.get('incident_type')
        severity = request.query_params.get('severity')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        if student_id:
            queryset = queryset.filter(student_id=student_id)
        if incident_type:
            queryset = queryset.filter(incident_type=incident_type)
        if severity:
            queryset = queryset.filter(severity=severity)
        if date_from:
            queryset = queryset.filter(incident_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(incident_date__lte=date_to)

        tenant_meta = _resolve_tenant_pdf_meta(request)
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, title="Behavior Incidents Report")
        styles = getSampleStyleSheet()
        story = []

        if tenant_meta.get("logo_path"):
            try:
                story.append(Image(tenant_meta["logo_path"], width=48, height=48))
            except Exception:
                pass

        story.append(Paragraph(f"<b>{_safe_cell(tenant_meta.get('school_name'))}</b>", styles["Title"]))
        story.append(Paragraph(f"Tenant: {_safe_cell(tenant_meta.get('schema'))}", styles["Normal"]))
        if tenant_meta.get("address"):
            story.append(Paragraph(_safe_cell(tenant_meta["address"]), styles["Normal"]))
        if tenant_meta.get("phone"):
            story.append(Paragraph(f"Phone: {_safe_cell(tenant_meta['phone'])}", styles["Normal"]))
        story.append(Spacer(1, 12))
        story.append(Paragraph("<b>Behavior Incidents Report</b>", styles["Heading2"]))
        story.append(Spacer(1, 6))

        table_rows = [["Student", "Type", "Category", "Date", "Severity"]]
        for incident in queryset:
            table_rows.append([
                f"{incident.student.first_name} {incident.student.last_name}".strip(),
                incident.incident_type,
                incident.category,
                _safe_cell(incident.incident_date),
                _safe_cell(incident.severity),
            ])

        incidents_table = Table(table_rows, colWidths=[120, 70, 120, 80, 70])
        incidents_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(incidents_table)

        doc.build(story)
        pdf_data = buffer.getvalue()
        buffer.close()

        response = HttpResponse(pdf_data, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="behavior_incidents_report.pdf"'
        return response


# ==========================================
# VOTE HEADS
# ==========================================

class VoteHeadViewSet(viewsets.ModelViewSet):
    serializer_class = VoteHeadSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get_queryset(self):
        qs = VoteHead.objects.all()
        if self.request.query_params.get('active_only') == 'true':
            qs = qs.filter(is_active=True)
        return qs

    def perform_create(self, serializer):
        serializer.save()

    @action(detail=False, methods=['post'], url_path='seed-defaults')
    def seed_defaults(self, request):
        created = []
        for i, name in enumerate(VoteHead.PRELOADED_NAMES):
            vh, is_new = VoteHead.objects.get_or_create(
                name=name,
                defaults={'is_preloaded': True, 'order': i, 'is_active': True}
            )
            if is_new:
                created.append(name)
        return Response({'seeded': created, 'message': f'{len(created)} vote heads seeded.'})


class VoteHeadPaymentAllocationViewSet(viewsets.ModelViewSet):
    serializer_class = VoteHeadPaymentAllocationSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get_queryset(self):
        qs = VoteHeadPaymentAllocation.objects.select_related('payment', 'vote_head').all()
        payment_id = self.request.query_params.get('payment')
        if payment_id:
            qs = qs.filter(payment_id=payment_id)
        vote_head_id = self.request.query_params.get('vote_head')
        if vote_head_id:
            qs = qs.filter(vote_head_id=vote_head_id)
        return qs


# ==========================================
# CASHBOOK & BANKBOOK
# ==========================================

def _recompute_running_balances(book_type):
    entries = list(CashbookEntry.objects.filter(book_type=book_type).order_by('entry_date', 'created_at'))
    running = Decimal('0.00') if not entries else None
    from decimal import Decimal as D
    balance = D('0.00')
    for entry in entries:
        balance += (entry.amount_in or D('0.00')) - (entry.amount_out or D('0.00'))
        entry.running_balance = balance
    if entries:
        CashbookEntry.objects.bulk_update(entries, ['running_balance'])


class CashbookEntryViewSet(viewsets.ModelViewSet):
    serializer_class = CashbookEntrySerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get_queryset(self):
        qs = CashbookEntry.objects.all()
        book_type = self.request.query_params.get('book_type')
        if book_type:
            qs = qs.filter(book_type=book_type.upper())
        date_from = self.request.query_params.get('date_from')
        if date_from:
            qs = qs.filter(entry_date__gte=date_from)
        date_to = self.request.query_params.get('date_to')
        if date_to:
            qs = qs.filter(entry_date__lte=date_to)
        return qs.order_by('book_type', 'entry_date', 'created_at')

    def perform_create(self, serializer):
        from decimal import Decimal as D
        obj = serializer.save()
        _recompute_running_balances(obj.book_type)
        obj.refresh_from_db()

    def perform_update(self, serializer):
        obj = serializer.save()
        _recompute_running_balances(obj.book_type)

    def perform_destroy(self, instance):
        book_type = instance.book_type
        instance.delete()
        _recompute_running_balances(book_type)


class CashbookSummaryView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        from decimal import Decimal as D
        result = {}
        for book_type in ['CASH', 'BANK']:
            entries = CashbookEntry.objects.filter(book_type=book_type).order_by('entry_date', 'created_at')
            total_in = entries.aggregate(t=Sum('amount_in'))['t'] or D('0.00')
            total_out = entries.aggregate(t=Sum('amount_out'))['t'] or D('0.00')
            closing = entries.last()
            opening = entries.filter(entry_type='OPENING').first()
            result[book_type.lower()] = {
                'total_in': float(total_in),
                'total_out': float(total_out),
                'closing_balance': float(closing.running_balance) if closing else 0.0,
                'opening_balance': float(opening.amount_in) if opening else 0.0,
                'entry_count': entries.count(),
            }
        return Response(result)


# ==========================================
# BALANCE CARRY FORWARD
# ==========================================

class BalanceCarryForwardViewSet(viewsets.ModelViewSet):
    serializer_class = BalanceCarryForwardSerializer
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get_queryset(self):
        qs = BalanceCarryForward.objects.select_related('student', 'from_term', 'to_term').all()
        student_id = self.request.query_params.get('student')
        if student_id:
            qs = qs.filter(student_id=student_id)
        from_term = self.request.query_params.get('from_term')
        if from_term:
            qs = qs.filter(from_term_id=from_term)
        to_term = self.request.query_params.get('to_term')
        if to_term:
            qs = qs.filter(to_term_id=to_term)
        return qs.order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ==========================================
# ARREARS REPORT
# ==========================================

class FinanceArrearsView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        from decimal import Decimal as D
        term_id = request.query_params.get('term')
        group_by = request.query_params.get('group_by', 'student')

        invoices_qs = Invoice.objects.filter(is_active=True).exclude(status__in=['PAID', 'VOID'])
        if term_id:
            invoices_qs = invoices_qs.filter(term_id=term_id)

        rows = []
        for inv in invoices_qs.select_related('student', 'term'):
            balance = float(inv.balance_due)
            if balance <= 0:
                continue
            enrollment = inv.student.enrollment_set.filter(is_active=True).select_related('school_class').first()
            class_name = enrollment.school_class.name if enrollment and enrollment.school_class else 'N/A'
            rows.append({
                'invoice_id': inv.id,
                'invoice_number': inv.invoice_number,
                'student_id': inv.student.id,
                'student_name': f"{inv.student.first_name} {inv.student.last_name}".strip(),
                'admission_number': inv.student.admission_number,
                'class_name': class_name,
                'term': inv.term.name if inv.term else '',
                'total_amount': float(inv.total_amount),
                'balance_due': balance,
                'due_date': str(inv.due_date),
                'status': inv.status,
            })

        if group_by == 'class':
            from collections import defaultdict
            grouped = defaultdict(lambda: {'class_name': '', 'student_count': 0, 'total_balance': 0.0, 'invoices': []})
            for row in rows:
                key = row['class_name']
                grouped[key]['class_name'] = key
                grouped[key]['student_count'] += 1
                grouped[key]['total_balance'] += row['balance_due']
                grouped[key]['invoices'].append(row)
            return Response({'group_by': 'class', 'data': list(grouped.values())})

        return Response({'group_by': 'student', 'count': len(rows), 'results': rows})


# ==========================================
# VOTE HEAD ALLOCATION REPORT
# ==========================================

class FinanceVoteHeadAllocationReportView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        from decimal import Decimal as D
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        qs = VoteHeadPaymentAllocation.objects.select_related('vote_head', 'payment')
        if date_from:
            qs = qs.filter(payment__payment_date__date__gte=date_from)
        if date_to:
            qs = qs.filter(payment__payment_date__date__lte=date_to)

        totals = qs.values('vote_head__id', 'vote_head__name').annotate(
            total_allocated=Sum('amount'),
            transaction_count=Count('id')
        ).order_by('vote_head__order', 'vote_head__name')

        grand_total = sum(float(r['total_allocated'] or 0) for r in totals)

        return Response({
            'date_from': date_from,
            'date_to': date_to,
            'grand_total': grand_total,
            'rows': [
                {
                    'vote_head_id': r['vote_head__id'],
                    'vote_head_name': r['vote_head__name'],
                    'total_allocated': float(r['total_allocated'] or 0),
                    'transaction_count': r['transaction_count'],
                    'percentage_of_total': round(float(r['total_allocated'] or 0) / grand_total * 100, 2) if grand_total else 0,
                }
                for r in totals
            ]
        })


# ==========================================
# CLASS BALANCES REPORT
# ==========================================

class FinanceClassBalancesReportView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        term_id = request.query_params.get('term')
        invoices_qs = Invoice.objects.filter(is_active=True)
        if term_id:
            invoices_qs = invoices_qs.filter(term_id=term_id)

        from collections import defaultdict
        class_data = defaultdict(lambda: {
            'class_name': '', 'student_count': 0,
            'total_billed': 0.0, 'total_paid': 0.0, 'total_outstanding': 0.0
        })

        for inv in invoices_qs.select_related('student'):
            enrollment = inv.student.enrollment_set.filter(is_active=True).select_related('school_class').first()
            class_name = enrollment.school_class.name if enrollment and enrollment.school_class else 'Unassigned'
            balance = float(inv.balance_due)
            class_data[class_name]['class_name'] = class_name
            class_data[class_name]['total_billed'] += float(inv.total_amount)
            class_data[class_name]['total_paid'] += float(inv.total_amount) - balance
            class_data[class_name]['total_outstanding'] += max(balance, 0)
        student_counts = defaultdict(set)
        for inv in invoices_qs.select_related('student'):
            enrollment = inv.student.enrollment_set.filter(is_active=True).select_related('school_class').first()
            class_name = enrollment.school_class.name if enrollment and enrollment.school_class else 'Unassigned'
            student_counts[class_name].add(inv.student_id)
        for class_name, students in student_counts.items():
            class_data[class_name]['student_count'] = len(students)

        return Response({
            'term_id': term_id,
            'rows': sorted(class_data.values(), key=lambda x: x['class_name'])
        })


# ==========================================
# ARREARS BY TERM REPORT
# ==========================================

class FinanceArrearsByTermReportView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        from collections import defaultdict
        invoices_qs = Invoice.objects.filter(is_active=True).exclude(status__in=['PAID', 'VOID'])
        term_data = defaultdict(lambda: {
            'term_id': None, 'term_name': '', 'student_count': 0,
            'total_outstanding': 0.0, 'invoice_count': 0
        })
        for inv in invoices_qs.select_related('term'):
            balance = float(inv.balance_due)
            if balance <= 0:
                continue
            key = inv.term_id
            term_data[key]['term_id'] = inv.term_id
            term_data[key]['term_name'] = inv.term.name if inv.term else 'N/A'
            term_data[key]['total_outstanding'] += balance
            term_data[key]['invoice_count'] += 1

        student_counts = defaultdict(set)
        for inv in invoices_qs.select_related('term'):
            if float(inv.balance_due) > 0:
                student_counts[inv.term_id].add(inv.student_id)
        for term_id, students in student_counts.items():
            term_data[term_id]['student_count'] = len(students)

        return Response({
            'rows': sorted(term_data.values(), key=lambda x: (x['term_name']))
        })


# ==========================================
# IPSAS BUDGET VARIANCE REPORT
# ==========================================

class FinanceBudgetVarianceReportView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request):
        from collections import defaultdict
        academic_year = request.query_params.get('academic_year')
        term = request.query_params.get('term')

        budgets_qs = Budget.objects.filter(is_active=True)
        if academic_year:
            budgets_qs = budgets_qs.filter(academic_year_id=academic_year)
        if term:
            budgets_qs = budgets_qs.filter(term_id=term)

        expenses_qs = Expense.objects.all()
        if term:
            try:
                term_obj = Term.objects.get(id=term)
                expenses_qs = expenses_qs.filter(
                    expense_date__gte=term_obj.start_date,
                    expense_date__lte=term_obj.end_date,
                )
            except Exception:
                pass
        elif academic_year:
            try:
                year_obj = AcademicYear.objects.get(id=academic_year)
                expenses_qs = expenses_qs.filter(
                    expense_date__gte=year_obj.start_date,
                    expense_date__lte=year_obj.end_date,
                )
            except Exception:
                pass

        expense_by_category = defaultdict(float)
        for exp in expenses_qs:
            expense_by_category[exp.category] += float(exp.amount or 0)

        total_actual = sum(expense_by_category.values())

        rows = []
        for budget in budgets_qs.select_related('academic_year', 'term'):
            annual = float(budget.annual_budget or 0)
            monthly = float(budget.monthly_budget or 0)
            quarterly = float(budget.quarterly_budget or 0)
            variance = annual - total_actual
            utilization_pct = round((total_actual / annual * 100), 1) if annual > 0 else None
            rows.append({
                'budget_id': budget.id,
                'academic_year': budget.academic_year.name,
                'term': budget.term.name,
                'monthly_budget': monthly,
                'quarterly_budget': quarterly,
                'annual_budget': annual,
                'total_actual_spend': round(total_actual, 2),
                'variance': round(variance, 2),
                'utilization_pct': utilization_pct,
                'status': 'UNDER' if variance >= 0 else 'OVER',
            })

        by_category = [
            {'category': cat, 'actual': round(amt, 2)}
            for cat, amt in sorted(expense_by_category.items(), key=lambda x: -x[1])
        ]

        return Response({
            'rows': rows,
            'by_category': by_category,
            'total_actual': round(total_actual, 2),
        })


# ==========================================
# RECEIPT PDF
# ==========================================

class FinanceReceiptPdfView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request, pk):
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
        from io import BytesIO

        try:
            payment = Payment.objects.select_related('student').get(pk=pk)
        except Payment.DoesNotExist:
            return Response({'detail': 'Payment not found.'}, status=status.HTTP_404_NOT_FOUND)

        tenant_meta = _resolve_tenant_pdf_meta(request)
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, title=f"Receipt {payment.receipt_number}")
        styles = getSampleStyleSheet()
        story = []

        if tenant_meta.get('logo_path'):
            try:
                story.append(Image(tenant_meta['logo_path'], width=60, height=60))
            except Exception:
                pass

        school_name = tenant_meta.get('school_name', 'School')
        story.append(Paragraph(f"<b>{_safe_cell(school_name)}</b>", styles['Title']))
        if tenant_meta.get('address'):
            story.append(Paragraph(_safe_cell(tenant_meta['address']), styles['Normal']))
        if tenant_meta.get('phone'):
            story.append(Paragraph(f"Tel: {_safe_cell(tenant_meta['phone'])}", styles['Normal']))
        story.append(Spacer(1, 18))

        story.append(Paragraph("<b>OFFICIAL RECEIPT</b>", styles['Heading2']))
        story.append(Spacer(1, 8))

        details = [
            ['Receipt No.', _safe_cell(payment.receipt_number)],
            ['Date', _safe_cell(payment.payment_date.strftime('%d %b %Y') if payment.payment_date else '')],
            ['Student', f"{payment.student.first_name} {payment.student.last_name}".strip()],
            ['Admission No.', _safe_cell(payment.student.admission_number)],
            ['Amount', f"KES {float(payment.amount):,.2f}"],
            ['Method', _safe_cell(payment.payment_method)],
            ['Reference', _safe_cell(payment.reference_number)],
        ]

        vote_allocs = VoteHeadPaymentAllocation.objects.filter(payment=payment).select_related('vote_head')
        if vote_allocs.exists():
            story.append(Spacer(1, 8))
            alloc_rows = [['Vote Head', 'Amount']]
            for va in vote_allocs:
                alloc_rows.append([_safe_cell(va.vote_head.name), f"KES {float(va.amount):,.2f}"])
            alloc_table = Table(alloc_rows, colWidths=[200, 120])
            alloc_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ]))
            details.append(['Vote Head Breakdown', ''])
            table = Table(details, colWidths=[160, 280])
            table.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(table)
            story.append(Spacer(1, 6))
            story.append(alloc_table)
        else:
            table = Table(details, colWidths=[160, 280])
            table.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(table)

        story.append(Spacer(1, 24))
        story.append(Paragraph("____________________________", styles['Normal']))
        story.append(Paragraph("Authorised Signature", styles['Normal']))
        story.append(Spacer(1, 8))
        story.append(Paragraph("<i>This is a computer-generated receipt.</i>", styles['Italic']))

        doc.build(story)
        pdf_data = buffer.getvalue()
        buffer.close()

        response = HttpResponse(pdf_data, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="receipt_{payment.receipt_number}.pdf"'
        return response


# ==========================================
# STUDENT ACCOUNT LEDGER
# ==========================================

class FinanceStudentLedgerView(APIView):
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def get(self, request, student_id):
        from decimal import Decimal as D
        try:
            student = Student.objects.get(id=student_id)
        except Student.DoesNotExist:
            return Response({'detail': 'Student not found.'}, status=404)
        term_id = request.query_params.get('term')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        entries = []

        inv_qs = Invoice.objects.filter(student=student, is_active=True)
        if term_id:
            inv_qs = inv_qs.filter(term_id=term_id)
        if date_from:
            inv_qs = inv_qs.filter(invoice_date__gte=date_from)
        if date_to:
            inv_qs = inv_qs.filter(invoice_date__lte=date_to)
        for inv in inv_qs.select_related('term').order_by('invoice_date', 'id'):
            entries.append({
                'date': str(inv.invoice_date),
                'type': 'INVOICE',
                'reference': inv.invoice_number or f'INV-{inv.id}',
                'description': f'Invoice – {inv.term.name if inv.term else ""}',
                'debit': float(inv.total_amount),
                'credit': 0.0,
                'term': inv.term.name if inv.term else '',
                'status': inv.status,
                'invoice_id': inv.id,
            })

        pay_qs = Payment.objects.filter(student=student, is_active=True)
        if date_from:
            pay_qs = pay_qs.filter(payment_date__date__gte=date_from)
        if date_to:
            pay_qs = pay_qs.filter(payment_date__date__lte=date_to)
        for pay in pay_qs.order_by('payment_date', 'id'):
            pay_date = pay.payment_date.date() if hasattr(pay.payment_date, 'date') else pay.payment_date
            entries.append({
                'date': str(pay_date),
                'type': 'PAYMENT',
                'reference': pay.receipt_number or pay.reference_number,
                'description': f'Payment – {pay.payment_method}',
                'debit': 0.0,
                'credit': float(pay.amount),
                'term': '',
                'status': 'REVERSED' if pay.reversed_at else 'ACTIVE',
                'payment_id': pay.id,
            })

        adj_qs = InvoiceAdjustment.objects.filter(invoice__student=student)
        if date_from:
            adj_qs = adj_qs.filter(created_at__date__gte=date_from)
        if date_to:
            adj_qs = adj_qs.filter(created_at__date__lte=date_to)
        for adj in adj_qs.select_related('invoice').order_by('created_at', 'id'):
            signed = float(adj.signed_amount)
            adj_date = adj.created_at.date() if hasattr(adj.created_at, 'date') else adj.created_at
            entries.append({
                'date': str(adj_date),
                'type': 'ADJUSTMENT',
                'reference': f'ADJ-{adj.id}',
                'description': f'{adj.adjustment_type} – {adj.reason[:60] if adj.reason else ""}',
                'debit': max(-signed, 0.0),
                'credit': max(signed, 0.0),
                'term': '',
                'status': 'POSTED',
            })

        cf_qs = BalanceCarryForward.objects.filter(student=student)
        if term_id:
            cf_qs = cf_qs.filter(to_term_id=term_id)
        for cf in cf_qs.select_related('from_term', 'to_term').order_by('created_at'):
            cf_date = cf.created_at.date() if hasattr(cf.created_at, 'date') else cf.created_at
            entries.append({
                'date': str(cf_date),
                'type': 'CARRY_FORWARD',
                'reference': f'CF-{cf.id}',
                'description': f'Balance carried forward from {cf.from_term.name} → {cf.to_term.name}',
                'debit': float(cf.amount),
                'credit': 0.0,
                'term': cf.to_term.name if cf.to_term else '',
                'status': 'POSTED',
            })

        entries.sort(key=lambda e: e['date'])

        balance = D('0.00')
        for entry in entries:
            balance += D(str(entry['debit'])) - D(str(entry['credit']))
            entry['balance'] = float(balance)

        enrollment = student.enrollment_set.filter(is_active=True).select_related('school_class', 'term').first()
        student_data = {
            'id': student.id,
            'name': f"{student.first_name} {student.last_name}".strip(),
            'admission_number': student.admission_number,
            'class_name': enrollment.school_class.name if enrollment and enrollment.school_class else 'N/A',
            'current_term': enrollment.term.name if enrollment and enrollment.term else 'N/A',
        }

        return Response({
            'student': student_data,
            'entry_count': len(entries),
            'closing_balance': float(balance),
            'entries': entries,
        })


# ==========================================
# TENANT USER MANAGEMENT
# ==========================================

class RoleListView(APIView):
    """List all available roles for tenant users."""
    permission_classes = [IsSchoolAdmin]

    def get(self, request):
        roles = Role.objects.all().order_by('name')
        data = [{'id': r.id, 'name': r.name, 'description': r.description} for r in roles]
        return Response(data)


class RoleModuleAccessView(APIView):
    """
    GET  – Returns all roles with the modules assigned to each role.
            For admin-level roles (ADMIN, TENANT_SUPER_ADMIN) every active
            module is returned.  For other roles the union of active
            UserModuleAssignments for users of that role is returned.
    POST – Body: { role_name: str, module_keys: [str] }
            Replaces module assignments for ALL currently active users of
            that role.  Admin-level roles are skipped (they always have all
            modules).
    """
    permission_classes = [IsSchoolAdmin]

    _ADMIN_ROLES = {'ADMIN', 'TENANT_SUPER_ADMIN'}

    def get(self, request):
        from django.contrib.auth.models import User as AuthUser
        all_modules = list(Module.objects.filter(is_active=True).order_by('key').values('key', 'name'))
        roles = Role.objects.all().order_by('name')
        result = []
        for role in roles:
            user_ids = list(
                AuthUser.objects.filter(
                    userprofile__role=role, is_active=True
                ).values_list('id', flat=True)
            )
            user_count = len(user_ids)
            if role.name in self._ADMIN_ROLES:
                assigned_keys = [m['key'] for m in all_modules]
                editable = False
            else:
                assigned_keys = list(
                    UserModuleAssignment.objects.filter(
                        user_id__in=user_ids, is_active=True, module__is_active=True
                    ).values_list('module__key', flat=True).distinct()
                )
                editable = True
            result.append({
                'id': role.id,
                'name': role.name,
                'description': role.description,
                'user_count': user_count,
                'assigned_module_keys': sorted(assigned_keys),
                'editable': editable,
            })
        return Response({'roles': result, 'all_modules': all_modules})

    def post(self, request):
        from django.contrib.auth.models import User as AuthUser
        role_name = request.data.get('role_name', '').strip().upper()
        module_keys = request.data.get('module_keys', [])
        if not role_name:
            return Response({'error': 'role_name is required.'}, status=400)
        if role_name in self._ADMIN_ROLES:
            return Response({'error': 'Admin-level role assignments cannot be restricted.'}, status=400)
        try:
            role = Role.objects.get(name=role_name)
        except Role.DoesNotExist:
            return Response({'error': f'Role "{role_name}" not found.'}, status=404)
        modules = {m.key: m for m in Module.objects.filter(key__in=module_keys, is_active=True)}
        users = AuthUser.objects.filter(userprofile__role=role, is_active=True)
        for user in users:
            UserModuleAssignment.objects.filter(user=user).update(is_active=False)
            for key in module_keys:
                mod = modules.get(key)
                if mod:
                    UserModuleAssignment.objects.update_or_create(
                        user=user,
                        module=mod,
                        defaults={'is_active': True, 'assigned_by': request.user},
                    )
        return Response({
            'updated_users': users.count(),
            'assigned_module_keys': sorted(module_keys),
            'role': role_name,
        })


class SubmodulePermissionView(APIView):
    """
    GET  – Returns all submodule permissions for all roles.
    POST – Body: { permissions: [{ role, module_key, submodule_key, can_view, can_create, can_edit, can_delete, can_approve }] }
            Bulk upsert submodule permissions.
    """
    permission_classes = [IsSchoolAdmin]

    def get(self, request):
        from .models import SubmodulePermission as SP
        perms = SP.objects.select_related('role').all()
        data = [
            {
                'role': p.role.name,
                'module_key': p.module_key,
                'submodule_key': p.submodule_key,
                'can_view': p.can_view,
                'can_create': p.can_create,
                'can_edit': p.can_edit,
                'can_delete': p.can_delete,
                'can_approve': p.can_approve,
            }
            for p in perms
        ]
        return Response({'permissions': data})

    def post(self, request):
        from .models import SubmodulePermission as SP
        perm_list = request.data.get('permissions', [])
        if not isinstance(perm_list, list):
            return Response({'error': 'permissions must be a list.'}, status=400)
        updated = 0
        for item in perm_list:
            role_name = (item.get('role') or '').strip().upper()
            module_key = (item.get('module_key') or '').strip().upper()
            submodule_key = (item.get('submodule_key') or '').strip()
            if not role_name or not module_key or not submodule_key:
                continue
            try:
                role = Role.objects.get(name=role_name)
            except Role.DoesNotExist:
                continue
            SP.objects.update_or_create(
                role=role,
                module_key=module_key,
                submodule_key=submodule_key,
                defaults={
                    'can_view': bool(item.get('can_view', True)),
                    'can_create': bool(item.get('can_create', False)),
                    'can_edit': bool(item.get('can_edit', False)),
                    'can_delete': bool(item.get('can_delete', False)),
                    'can_approve': bool(item.get('can_approve', False)),
                }
            )
            updated += 1
        return Response({'updated': updated})


class UserManagementListCreateView(APIView):
    """List all tenant users with roles / create a new tenant user."""
    permission_classes = [IsSchoolAdmin]

    def get(self, request):
        from django.contrib.auth.models import User as AuthUser
        include_inactive = request.query_params.get('include_inactive', '0') in ('1', 'true', 'yes')
        qs = AuthUser.objects.select_related('userprofile__role').order_by('username')
        if not include_inactive:
            qs = qs.filter(is_active=True)
        data = []
        for u in qs:
            profile = getattr(u, 'userprofile', None)
            role = getattr(profile, 'role', None)
            data.append({
                'id': u.id,
                'username': u.username,
                'email': u.email,
                'first_name': u.first_name,
                'last_name': u.last_name,
                'is_active': u.is_active,
                'is_staff': u.is_staff,
                'date_joined': u.date_joined.strftime('%Y-%m-%d') if u.date_joined else None,
                'last_login': u.last_login.strftime('%Y-%m-%d %H:%M') if u.last_login else None,
                'role_id': role.id if role else None,
                'role_name': role.name if role else None,
                'phone': profile.phone if profile else '',
                'admission_number': profile.admission_number if profile else '',
                'force_password_change': bool(profile.force_password_change) if profile else False,
            })
        return Response({'results': data, 'count': len(data)})

    def post(self, request):
        from django.contrib.auth.models import User as AuthUser
        data = request.data
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        email = data.get('email', '').strip()
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        phone = data.get('phone', '').strip()
        role_id = data.get('role_id')
        admission_number = data.get('admission_number', '').strip() or None

        if not username or not password:
            return Response({'detail': 'Username and password are required.'}, status=400)
        if AuthUser.objects.filter(username=username).exists():
            return Response({'detail': f'Username "{username}" is already taken.'}, status=400)
        if not role_id:
            return Response({'detail': 'A role must be assigned.'}, status=400)
        try:
            role = Role.objects.get(id=role_id)
        except Role.DoesNotExist:
            return Response({'detail': 'Invalid role.'}, status=400)

        if admission_number and UserProfile.objects.filter(admission_number=admission_number).exists():
            return Response({'detail': f'Admission number "{admission_number}" is already linked to another account.'}, status=400)

        user = AuthUser.objects.create_user(
            username=username,
            password=password,
            email=email,
            first_name=first_name,
            last_name=last_name,
        )
        UserProfile.objects.create(user=user, role=role, phone=phone, admission_number=admission_number)
        return Response({
            'id': user.id,
            'username': user.username,
            'role_name': role.name,
        }, status=201)


class UserManagementDetailView(APIView):
    """Retrieve, update, or deactivate a specific tenant user."""
    permission_classes = [IsSchoolAdmin]

    def _get_user(self, user_id):
        from django.contrib.auth.models import User as AuthUser
        try:
            return AuthUser.objects.select_related('userprofile__role').get(id=user_id)
        except AuthUser.DoesNotExist:
            return None

    def get(self, request, user_id):
        u = self._get_user(user_id)
        if not u:
            return Response({'detail': 'User not found.'}, status=404)
        profile = getattr(u, 'userprofile', None)
        role = getattr(profile, 'role', None)
        return Response({
            'id': u.id, 'username': u.username, 'email': u.email,
            'first_name': u.first_name, 'last_name': u.last_name,
            'is_active': u.is_active, 'is_staff': u.is_staff,
            'date_joined': u.date_joined.strftime('%Y-%m-%d') if u.date_joined else None,
            'last_login': u.last_login.strftime('%Y-%m-%d %H:%M') if u.last_login else None,
            'role_id': role.id if role else None,
            'role_name': role.name if role else None,
            'phone': profile.phone if profile else '',
            'admission_number': profile.admission_number if profile else '',
            'force_password_change': bool(profile.force_password_change) if profile else False,
        })

    def patch(self, request, user_id):
        u = self._get_user(user_id)
        if not u:
            # Allow finding deactivated users too
            from django.contrib.auth.models import User as AuthUser
            try:
                u = AuthUser.objects.select_related('userprofile__role').get(id=user_id)
            except AuthUser.DoesNotExist:
                return Response({'detail': 'User not found.'}, status=404)
        data = request.data
        if 'email' in data:
            u.email = data['email']
        if 'first_name' in data:
            u.first_name = data['first_name']
        if 'last_name' in data:
            u.last_name = data['last_name']
        if 'password' in data and data['password']:
            u.set_password(data['password'])
        if 'is_active' in data:
            if str(user_id) == str(request.user.id) and not data['is_active']:
                return Response({'detail': 'You cannot deactivate your own account.'}, status=400)
            u.is_active = bool(data['is_active'])
        u.save()

        profile = getattr(u, 'userprofile', None)
        admission_number = data.get('admission_number', '').strip() or None

        if 'role_id' in data and data['role_id']:
            try:
                role = Role.objects.get(id=data['role_id'])
                if profile:
                    profile.role = role
                    if 'phone' in data:
                        profile.phone = data.get('phone', '')
                    if 'admission_number' in data:
                        if admission_number and UserProfile.objects.filter(admission_number=admission_number).exclude(pk=profile.pk).exists():
                            return Response({'detail': f'Admission number "{admission_number}" is already linked to another account.'}, status=400)
                        profile.admission_number = admission_number
                    profile.save()
                else:
                    UserProfile.objects.create(user=u, role=role, phone=data.get('phone', ''), admission_number=admission_number)
            except Role.DoesNotExist:
                return Response({'detail': 'Invalid role.'}, status=400)
        elif profile:
            if 'phone' in data:
                profile.phone = data.get('phone', '')
            if 'admission_number' in data:
                if admission_number and UserProfile.objects.filter(admission_number=admission_number).exclude(pk=profile.pk).exists():
                    return Response({'detail': f'Admission number "{admission_number}" is already linked to another account.'}, status=400)
                profile.admission_number = admission_number
            profile.save()

        return Response({'detail': 'User updated.'})

    def delete(self, request, user_id):
        from django.contrib.auth.models import User as AuthUser
        if str(user_id) == str(request.user.id):
            return Response({'detail': 'You cannot delete your own account.'}, status=400)
        try:
            u = AuthUser.objects.get(id=user_id)
        except AuthUser.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=404)
        username = u.username
        u.delete()
        return Response({'detail': f'User "{username}" has been permanently deleted.'})


class AcademicsCurrentContextView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        from academics.models import AcademicYear, Term
        year = AcademicYear.objects.filter(is_current=True).first()
        term = Term.objects.filter(is_current=True).first()
        return Response({
            'academic_year': {'id': year.id, 'name': year.name} if year else None,
            'term': {'id': term.id, 'name': term.name} if term else None,
        })

class BulkOptionalChargeByClassView(APIView):
    """
    POST: Assigns an optional charge to every enrolled student in a given class.
    Body: { class_id, optional_charge_id, term_id (optional) }
    Returns: { created, skipped, student_count }
    """
    permission_classes = [IsAccountant, HasModuleAccess]
    module_key = "FINANCE"

    def post(self, request):
        class_id = request.data.get('class_id')
        optional_charge_id = request.data.get('optional_charge_id')
        term_id = request.data.get('term_id')

        if not class_id:
            return Response({'error': 'class_id is required.'}, status=400)
        if not optional_charge_id:
            return Response({'error': 'optional_charge_id is required.'}, status=400)

        try:
            school_class = SchoolClass.objects.get(id=class_id)
        except SchoolClass.DoesNotExist:
            return Response({'error': 'Class not found.'}, status=404)

        try:
            optional_charge = OptionalCharge.objects.get(id=optional_charge_id)
        except OptionalCharge.DoesNotExist:
            return Response({'error': 'Optional charge not found.'}, status=404)

        enrollments = Enrollment.objects.filter(school_class_id=school_class.id, is_active=True)
        if term_id:
            enrollments = enrollments.filter(term_id=term_id)

        student_ids = list(enrollments.values_list('student_id', flat=True).distinct())
        if not student_ids:
            return Response({'created': 0, 'skipped': 0, 'student_count': 0,
                             'message': 'No enrolled students found in this class.'})

        created_count = 0
        skipped_count = 0
        for student_id in student_ids:
            _, created = StudentOptionalCharge.objects.get_or_create(
                student_id=student_id,
                optional_charge=optional_charge,
            )
            if created:
                created_count += 1
            else:
                skipped_count += 1

        return Response({
            'created': created_count,
            'skipped': skipped_count,
            'student_count': len(student_ids),
            'message': f'Assigned to {created_count} new students ({skipped_count} already had this charge).',
        })


# ==========================================
# DISPENSARY VIEWS
# ==========================================

class DispensaryVisitViewSet(viewsets.ModelViewSet):
    serializer_class = DispensaryVisitSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "DISPENSARY"

    def get_queryset(self):
        qs = DispensaryVisit.objects.select_related('student', 'attended_by').prefetch_related('prescriptions').all()
        student_id = self.request.query_params.get('student')
        if student_id:
            qs = qs.filter(student_id=student_id)
        severity = self.request.query_params.get('severity')
        if severity:
            qs = qs.filter(severity=severity.upper())
        date_from = self.request.query_params.get('date_from')
        if date_from:
            qs = qs.filter(visit_date__gte=date_from)
        date_to = self.request.query_params.get('date_to')
        if date_to:
            qs = qs.filter(visit_date__lte=date_to)
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                models.Q(student__first_name__icontains=search) |
                models.Q(student__last_name__icontains=search) |
                models.Q(student__admission_number__icontains=search)
            )
        return qs.order_by('-visit_date', '-created_at')

    def perform_create(self, serializer):
        visit = serializer.save()
        prescriptions = self.request.data.get('prescriptions', [])
        for p in prescriptions:
            DispensaryPrescription.objects.create(
                visit=visit,
                medication_name=p.get('medication_name', ''),
                dosage=p.get('dosage', ''),
                frequency=p.get('frequency', ''),
                quantity_dispensed=p.get('quantity_dispensed', 0),
                unit=p.get('unit', ''),
                notes=p.get('notes', ''),
            )


class DispensaryPrescriptionViewSet(viewsets.ModelViewSet):
    serializer_class = DispensaryPrescriptionSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "DISPENSARY"

    def get_queryset(self):
        qs = DispensaryPrescription.objects.select_related('visit__student').all()
        visit_id = self.request.query_params.get('visit')
        if visit_id:
            qs = qs.filter(visit_id=visit_id)
        return qs.order_by('-created_at')


class DispensaryStockViewSet(viewsets.ModelViewSet):
    serializer_class = DispensaryStockSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "DISPENSARY"

    def get_queryset(self):
        qs = DispensaryStock.objects.all()
        low_stock = self.request.query_params.get('low_stock')
        if low_stock == 'true':
            from django.db.models import F
            qs = qs.filter(current_quantity__lte=F('reorder_level'))
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                models.Q(medication_name__icontains=search) |
                models.Q(generic_name__icontains=search)
            )
        return qs.order_by('medication_name')


class DispensaryDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "DISPENSARY"

    def get(self, request):
        from django.db.models import F
        import datetime
        today = datetime.date.today()
        first_of_month = today.replace(day=1)
        visits_today = DispensaryVisit.objects.filter(visit_date=today).count()
        visits_month = DispensaryVisit.objects.filter(visit_date__gte=first_of_month).count()
        low_stock_meds = DispensaryStock.objects.filter(current_quantity__lte=F('reorder_level')).count()
        referred_count = DispensaryVisit.objects.filter(visit_date__gte=first_of_month, referred=True).count()
        recent_visits = list(
            DispensaryVisit.objects.select_related('student')
            .values('id', 'visit_date', 'complaint', 'diagnosis', 'severity',
                    'student__first_name', 'student__last_name', 'student__admission_number',
                    'referred', 'parent_notified')
            .order_by('-visit_date', '-created_at')[:10]
        )
        return Response({
            'visits_today': visits_today,
            'visits_month': visits_month,
            'low_stock_meds': low_stock_meds,
            'referred_count': referred_count,
            'recent_visits': recent_visits,
        })


class DispensaryDeliveryNoteViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "DISPENSARY"

    def get_serializer_class(self):
        from .serializers import DispensaryDeliveryNoteSerializer
        return DispensaryDeliveryNoteSerializer

    def get_queryset(self):
        qs = DispensaryDeliveryNote.objects.prefetch_related('items').select_related('received_by').all()
        supplier = self.request.query_params.get('supplier')
        if supplier:
            qs = qs.filter(supplier__icontains=supplier)
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def perform_create(self, serializer):
        note = serializer.save(received_by=self.request.user)
        items_data = self.request.data.get('items', [])
        for item in items_data:
            DispensaryDeliveryItem.objects.create(
                delivery_note=note,
                medication_name=item.get('medication_name', ''),
                quantity=item.get('quantity', 0),
                unit=item.get('unit', 'tablets'),
                unit_cost=item.get('unit_cost', 0),
                stock_id=item.get('stock') or None,
            )

    @action(detail=True, methods=['post'], url_path='add-item')
    def add_item(self, request, pk=None):
        from .serializers import DispensaryDeliveryNoteSerializer
        note = self.get_object()
        DispensaryDeliveryItem.objects.create(
            delivery_note=note,
            medication_name=request.data.get('medication_name', ''),
            quantity=request.data.get('quantity', 0),
            unit=request.data.get('unit', 'tablets'),
            unit_cost=request.data.get('unit_cost', 0),
        )
        note.refresh_from_db()
        return Response(DispensaryDeliveryNoteSerializer(note).data)

    @action(detail=True, methods=['post'], url_path='mark-received')
    def mark_received(self, request, pk=None):
        note = self.get_object()
        note.status = 'Received'
        note.received_by = request.user
        note.save(update_fields=['status', 'received_by'])
        for item in note.items.all():
            if item.stock:
                item.stock.current_quantity += item.quantity
                item.stock.save(update_fields=['current_quantity'])
        from .serializers import DispensaryDeliveryNoteSerializer
        return Response(DispensaryDeliveryNoteSerializer(note).data)

    @action(detail=True, methods=['post'], url_path='link-finance')
    def link_finance(self, request, pk=None):
        from .serializers import DispensaryDeliveryNoteSerializer
        note = self.get_object()
        from .models import Expense
        grand_total = sum(item.total_cost for item in note.items.all())
        try:
            expense = Expense.objects.create(
                amount=grand_total,
                description=f"Dispensary delivery - {note.supplier} ({note.delivery_date})",
                expense_type='Supplies',
                date=note.delivery_date,
                notes=f"Auto-linked from Delivery Note {note.reference_number or note.id}",
            )
            note.finance_expense_id = expense.id
            note.save(update_fields=['finance_expense_id'])
        except Exception:
            pass
        return Response(DispensaryDeliveryNoteSerializer(note).data)


class DispensaryOutsideTreatmentViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "DISPENSARY"

    def get_serializer_class(self):
        from .serializers import DispensaryOutsideTreatmentSerializer
        return DispensaryOutsideTreatmentSerializer

    def get_queryset(self):
        from .models import DispensaryOutsideTreatment
        qs = DispensaryOutsideTreatment.objects.select_related('student').all()
        patient_type = self.request.query_params.get('patient_type')
        if patient_type:
            qs = qs.filter(patient_type=patient_type)
        facility = self.request.query_params.get('facility')
        if facility:
            qs = qs.filter(facility_name__icontains=facility)
        return qs


class DemoResetView(APIView):
    """
    POST /school/demo/reset/
    Resets demo_school tenant to original seed data.
    Only available when the current tenant schema is 'demo_school'.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        tenant = getattr(request, 'tenant', None)
        schema = getattr(tenant, 'schema_name', None)
        if schema != 'demo_school':
            return Response(
                {'error': 'Demo reset is only available in the demo_school environment.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            from django.core.management import call_command
            import io
            out = io.StringIO()
            call_command('reset_demo', '--schema', 'demo_school', stdout=out)
            return Response({
                'success': True,
                'message': 'Demo data has been reset to the original Kenya school seed.',
            })
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        tenant = getattr(request, 'tenant', None)
        schema = getattr(tenant, 'schema_name', None)
        return Response({
            'demo_mode': schema == 'demo_school',
            'schema': schema,
            'message': 'POST to this endpoint to reset demo data.',
        })


class ModuleSeedView(APIView):
    """
    POST /seed/ — seed the current tenant with comprehensive sample data.
    Runs the seed_kenya_school management command for the current tenant schema.
    Admin only.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not _is_admin_like(request.user):
            return Response(
                {'detail': 'Admin access required to seed data.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        tenant = getattr(request, 'tenant', None)
        schema = getattr(tenant, 'schema_name', None)
        if not schema:
            return Response({'detail': 'Could not determine tenant schema.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            from django.core.management import call_command
            import io
            out = io.StringIO()
            call_command('seed_kenya_school', f'--schema_name={schema}', stdout=out)

            # Phase 16 Advanced RBAC — seed default permissions and role grants
            try:
                perm_out = io.StringIO()
                call_command('seed_default_permissions', '--assign-roles', f'--schema={schema}', stdout=perm_out)
            except Exception:
                pass

            # Create portal login accounts for all seeded students and guardians
            counts = self._create_portal_accounts()

            return Response({
                'detail': 'Sample data seeded successfully.',
                'schema': schema,
                'student_accounts_created': counts['students'],
                'parent_accounts_created': counts['parents'],
                'output': out.getvalue()[-500:] if out.getvalue() else '',
            }, status=status.HTTP_201_CREATED)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _create_portal_accounts(self):
        """Create Django user accounts for all students and guardians so they can log in."""
        from django.contrib.auth.models import User as DjangoUser
        from parent_portal.models import ParentStudentLink
        student_role = Role.objects.filter(name='STUDENT').first()
        parent_role = Role.objects.filter(name='PARENT').first()
        student_count = 0
        parent_count = 0

        for student in Student.objects.filter(is_active=True):
            adm = student.admission_number
            username = adm  # username = admission number (e.g. STM2025001)
            user, created = DjangoUser.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': student.first_name,
                    'last_name': student.last_name,
                    'is_active': True,
                },
            )
            if created:
                user.set_password(adm)
                user.save()
                student_count += 1
            if student_role:
                profile, _ = UserProfile.objects.get_or_create(
                    user=user,
                    defaults={'role': student_role, 'admission_number': adm},
                )
                profile_updates = []
                if profile.role_id != student_role.id:
                    profile.role = student_role
                    profile_updates.append('role')
                if profile.admission_number != adm:
                    profile.admission_number = adm
                    profile_updates.append('admission_number')
                if profile.force_password_change:
                    profile.force_password_change = False
                    profile_updates.append('force_password_change')
                if profile_updates:
                    profile.save(update_fields=profile_updates)

        for guardian in Guardian.objects.filter(is_active=True):
            # Derive a unique username from email or name
            if guardian.email:
                base = guardian.email.split('@')[0].lower().replace('.', '_').replace('+', '_')
            else:
                base = (guardian.name or 'parent').lower().replace(' ', '_').replace('.', '')
            username = base[:30]

            existing = DjangoUser.objects.filter(username=username).first()
            existing_profile = getattr(existing, 'userprofile', None) if existing else None
            existing_role_name = getattr(getattr(existing_profile, 'role', None), 'name', None)

            if existing:
                if guardian.email:
                    email_matches = (existing.email or '').strip().lower() == guardian.email.strip().lower()
                    if not email_matches and existing_role_name != 'PARENT':
                        existing = None
                elif existing_role_name != 'PARENT':
                    existing = None

            if existing:
                user = existing
                created = False
            else:
                suffix = 0
                candidate = username
                while DjangoUser.objects.filter(username=candidate).exists():
                    suffix += 1
                    candidate = f'{username}{suffix}'
                username = candidate
                user = DjangoUser.objects.create(
                    username=username,
                    first_name=(guardian.name or '').split()[0] if guardian.name else '',
                    email=guardian.email or '',
                    is_active=True,
                )
                user.set_password('parent123')
                user.save()
                parent_count += 1
                created = True
            if not created:
                update_fields = []
                desired_first_name = (guardian.name or '').split()[0] if guardian.name else ''
                if desired_first_name and user.first_name != desired_first_name:
                    user.first_name = desired_first_name
                    update_fields.append('first_name')
                if guardian.email and user.email != guardian.email:
                    user.email = guardian.email
                    update_fields.append('email')
                if not user.is_active:
                    user.is_active = True
                    update_fields.append('is_active')
                if update_fields:
                    user.save(update_fields=update_fields)
            if parent_role:
                require_password_change = created or user.check_password('parent123')
                profile, _ = UserProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'role': parent_role,
                        'phone': guardian.phone or '',
                        'force_password_change': require_password_change,
                    },
                )
                profile_updates = []
                if profile.role_id != parent_role.id:
                    profile.role = parent_role
                    profile_updates.append('role')
                if guardian.phone and not profile.phone:
                    profile.phone = guardian.phone
                    profile_updates.append('phone')
                if require_password_change and not profile.force_password_change:
                    profile.force_password_change = True
                    profile_updates.append('force_password_change')
                if profile_updates:
                    profile.save(update_fields=profile_updates)

            link_defaults = {
                'guardian': guardian,
                'relationship': guardian.relationship or '',
                'is_active': True,
                'is_primary': not ParentStudentLink.objects.filter(
                    parent_user=user,
                    is_active=True,
                    is_primary=True,
                ).exclude(student=guardian.student).exists(),
            }
            ParentStudentLink.objects.update_or_create(
                parent_user=user,
                student=guardian.student,
                defaults=link_defaults,
            )

        return {'students': student_count, 'parents': parent_count}

    def get(self, request):
        return Response({
            'detail': 'POST to this endpoint to seed sample data for the current tenant.',
            'warning': 'This will add sample students, teachers, fees, and other data.',
        })


class StudentSearchForUserCreateView(APIView):
    """Lightweight student search for user-account creation (admin only)."""
    permission_classes = [IsSchoolAdmin]

    def get(self, request):
        q = (request.query_params.get('q') or '').strip()
        if not q or len(q) < 2:
            return Response({'results': []})
        students = Student.objects.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(admission_number__icontains=q),
            is_active=True,
        ).order_by('first_name', 'last_name')[:20]
        existing = set(UserProfile.objects.filter(
            admission_number__in=[s.admission_number for s in students]
        ).values_list('admission_number', flat=True))
        return Response({'results': [
            {
                'id': s.id,
                'first_name': s.first_name,
                'last_name': s.last_name,
                'admission_number': s.admission_number,
                'full_name': f"{s.first_name} {s.last_name}".strip(),
                'has_account': s.admission_number in existing,
            }
            for s in students
        ]})


class StudentsByClassForUserCreateView(APIView):
    """Return all active students enrolled in a class for bulk user creation."""
    permission_classes = [IsSchoolAdmin]

    def get(self, request):
        class_id = request.query_params.get('class_id')
        if not class_id:
            return Response({'results': []})
        enrollments = Enrollment.objects.filter(
            school_class_id=class_id, is_active=True
        ).select_related('student')
        students = [e.student for e in enrollments if e.student.is_active]
        existing = set(UserProfile.objects.filter(
            admission_number__in=[s.admission_number for s in students]
        ).values_list('admission_number', flat=True))
        return Response({'results': [
            {
                'id': s.id,
                'first_name': s.first_name,
                'last_name': s.last_name,
                'admission_number': s.admission_number,
                'full_name': f"{s.first_name} {s.last_name}".strip(),
                'has_account': s.admission_number in existing,
            }
            for s in students
        ]})


class BulkCreateStudentUsersView(APIView):
    """Create login accounts for multiple students in one request."""
    permission_classes = [IsSchoolAdmin]

    def post(self, request):
        from django.contrib.auth.models import User as AuthUser
        student_ids = request.data.get('student_ids', [])
        role_name = request.data.get('role', 'STUDENT')
        try:
            role = Role.objects.get(name=role_name)
        except Role.DoesNotExist:
            return Response({'detail': f'Role "{role_name}" not found.'}, status=400)

        students = Student.objects.filter(id__in=student_ids, is_active=True)
        created, skipped = [], []

        for student in students:
            adm = student.admission_number
            if UserProfile.objects.filter(admission_number=adm).exists():
                skipped.append({'admission_number': adm, 'name': f"{student.first_name} {student.last_name}", 'reason': 'Account already exists'})
                continue
            if AuthUser.objects.filter(username=adm).exists():
                skipped.append({'admission_number': adm, 'name': f"{student.first_name} {student.last_name}", 'reason': f'Username "{adm}" taken'})
                continue
            user = AuthUser.objects.create_user(
                username=adm,
                password=adm,
                first_name=student.first_name,
                last_name=student.last_name,
            )
            UserProfile.objects.create(user=user, role=role, admission_number=adm)
            created.append({'username': adm, 'admission_number': adm, 'name': f"{student.first_name} {student.last_name}"})

        return Response({
            'created_count': len(created),
            'skipped_count': len(skipped),
            'created': created,
            'skipped': skipped,
        }, status=201)


class VoteHeadBudgetReportView(APIView):
    """Vote head budget vs actual allocation report."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        total_annual_budget = float(
            Budget.objects.filter(is_active=True).aggregate(total=Sum('annual_budget'))['total'] or 0
        )

        alloc_qs = VoteHeadPaymentAllocation.objects.select_related('vote_head')
        if date_from:
            alloc_qs = alloc_qs.filter(payment__payment_date__date__gte=date_from)
        if date_to:
            alloc_qs = alloc_qs.filter(payment__payment_date__date__lte=date_to)

        totals = alloc_qs.values(
            'vote_head__id', 'vote_head__name', 'vote_head__allocation_percentage', 'vote_head__order'
        ).annotate(actual_collected=Sum('amount')).order_by('vote_head__order', 'vote_head__name')

        all_vote_heads = {vh.id: vh for vh in VoteHead.objects.filter(is_active=True)}
        rows = []
        seen_ids = set()

        for r in totals:
            vh_id = r['vote_head__id']
            seen_ids.add(vh_id)
            pct = float(r['vote_head__allocation_percentage'] or 0)
            budgeted = round(total_annual_budget * pct / 100, 2)
            actual = round(float(r['actual_collected'] or 0), 2)
            variance = round(actual - budgeted, 2)
            rows.append({
                'vote_head_id': vh_id,
                'vote_head_name': r['vote_head__name'],
                'allocation_percentage': pct,
                'budgeted_amount': budgeted,
                'actual_collected': actual,
                'variance': variance,
                'utilization_pct': round(actual / budgeted * 100, 2) if budgeted > 0 else None,
                'status': 'OVER' if actual > budgeted else 'UNDER',
            })

        for vh_id, vh in all_vote_heads.items():
            if vh_id not in seen_ids:
                pct = float(vh.allocation_percentage or 0)
                budgeted = round(total_annual_budget * pct / 100, 2)
                rows.append({
                    'vote_head_id': vh.id,
                    'vote_head_name': vh.name,
                    'allocation_percentage': pct,
                    'budgeted_amount': budgeted,
                    'actual_collected': 0.0,
                    'variance': round(-budgeted, 2),
                    'utilization_pct': 0.0 if budgeted > 0 else None,
                    'status': 'UNDER',
                })

        rows.sort(key=lambda x: x['allocation_percentage'], reverse=True)
        total_budgeted = sum(r['budgeted_amount'] for r in rows)
        total_actual = sum(r['actual_collected'] for r in rows)

        return Response({
            'date_from': date_from,
            'date_to': date_to,
            'total_annual_budget': total_annual_budget,
            'total_budgeted_via_allocation': round(total_budgeted, 2),
            'total_actual_collected': round(total_actual, 2),
            'overall_variance': round(total_actual - total_budgeted, 2),
            'overall_utilization_pct': round(total_actual / total_budgeted * 100, 2) if total_budgeted > 0 else None,
            'rows': rows,
        })


class StudentTransferViewSet(viewsets.ModelViewSet):
    def get_serializer_class(self):
        from .serializers import StudentTransferSerializer
        return StudentTransferSerializer

    def get_queryset(self):
        from .models import StudentTransfer
        qs = StudentTransfer.objects.select_related('student', 'processed_by')
        status_f = self.request.query_params.get('status')
        direction_f = self.request.query_params.get('direction')
        student_f = self.request.query_params.get('student')
        if status_f:
            qs = qs.filter(status=status_f)
        if direction_f:
            qs = qs.filter(direction=direction_f)
        if student_f:
            qs = qs.filter(student_id=student_f)
        return qs


# ═══════════════════════════════════════════════════════════════════
# TRANSFER SYSTEM  —  Cross-Tenant + Internal Transfers
# ═══════════════════════════════════════════════════════════════════

def _transfer_generate_package(transfer):
    """Build a JSON data snapshot of the entity being transferred."""
    from django.utils import timezone
    snapshot = {
        'generated_at': timezone.now().isoformat(),
        'transfer_type': transfer.transfer_type,
        'entity_id': transfer.entity_id,
        'from_tenant': transfer.from_tenant_id,
        'to_tenant': transfer.to_tenant_id,
    }
    try:
        if 'student' in transfer.transfer_type:
            from .models import Student, Enrollment, AttendanceRecord, Invoice
            student = Student.objects.filter(id=transfer.entity_id).first()
            if student:
                # Profile
                snapshot['profile'] = {
                    'admission_number': student.admission_number,
                    'first_name': student.first_name,
                    'last_name': student.last_name,
                    'date_of_birth': str(student.date_of_birth) if student.date_of_birth else None,
                    'gender': student.gender,
                    'phone': student.phone or '',
                    'email': student.email or '',
                    'address': student.address or '',
                    'is_active': student.is_active,
                }
                # Academic history (Enrollment records)
                try:
                    enrollments = Enrollment.objects.filter(student=student).select_related('school_class', 'term').values(
                        'school_class__name', 'term__name', 'enrollment_date', 'status'
                    )[:20]
                    snapshot['academic_history'] = list(enrollments)
                except Exception:
                    snapshot['academic_history'] = []
                # Attendance summary
                try:
                    att_total = AttendanceRecord.objects.filter(student=student).count()
                    att_present = AttendanceRecord.objects.filter(student=student, status='Present').count()
                    snapshot['attendance_summary'] = {
                        'total': att_total,
                        'present': att_present,
                        'rate': round(att_present / att_total * 100, 1) if att_total else 0,
                    }
                except Exception:
                    snapshot['attendance_summary'] = {}
                # Fee balance (Invoice model)
                try:
                    invoices = Invoice.objects.filter(student=student)
                    total_due  = sum(float(i.total_amount or 0) for i in invoices)
                    total_paid = sum(float(i.amount_paid or 0) for i in invoices)
                    balance = total_due - total_paid
                    snapshot['fee_summary'] = {
                        'total_invoiced': round(total_due, 2),
                        'total_paid': round(total_paid, 2),
                        'balance': round(balance, 2),
                    }
                    if balance > 0:
                        transfer.fee_balance_cleared = False
                        transfer.save(update_fields=['fee_balance_cleared'])
                except Exception:
                    snapshot['fee_summary'] = {}
        else:
            # Staff snapshot
            try:
                from hr.models import Employee, Department
                emp = Employee.objects.filter(id=transfer.entity_id).first()
                if emp:
                    snapshot['profile'] = {
                        'employee_id': emp.employee_id,
                        'first_name': emp.first_name,
                        'last_name': emp.last_name,
                        'designation': emp.designation or '',
                        'email': emp.email or '',
                        'phone': emp.phone or '',
                        'date_joined': str(emp.date_joined) if emp.date_joined else None,
                    }
                    dept = emp.department
                    snapshot['department'] = dept.name if dept else ''
            except Exception:
                pass
    except Exception as e:
        snapshot['error'] = str(e)

    import json as _json
    from datetime import date, datetime as _dt

    def _serialize(obj):
        if isinstance(obj, (date, _dt)):
            return obj.isoformat()
        raise TypeError(f'Not serializable: {type(obj)}')

    clean_snapshot = _json.loads(_json.dumps(snapshot, default=_serialize))

    from .models import TransferPackage as TP
    pkg, _ = TP.objects.get_or_create(transfer=transfer)
    pkg.data_snapshot = clean_snapshot
    pkg.save()
    return clean_snapshot


def _is_transfer_admin(user):
    from .models import UserProfile
    try:
        profile = UserProfile.objects.get(user=user)
        return profile.role.name in ('ADMIN', 'TENANT_SUPER_ADMIN')
    except Exception:
        return _is_admin_like(user)


def _is_transfer_parent(user):
    from .models import UserProfile
    try:
        profile = UserProfile.objects.get(user=user)
        return profile.role.name == 'PARENT'
    except Exception:
        return False


class TransferListView(APIView):
    """GET /transfers/ — list all transfers for this tenant (filtered by role)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .models import CrossTenantTransfer
        from .serializers import CrossTenantTransferSerializer
        tenant = getattr(request.tenant, 'schema_name', '')

        qs = CrossTenantTransfer.objects.filter(
            models.Q(from_tenant_id=tenant) | models.Q(to_tenant_id=tenant)
        ).select_related('initiated_by', 'approved_from_by', 'approved_to_by', 'rejected_by')

        # Filter params
        status_f = request.query_params.get('status')
        type_f   = request.query_params.get('transfer_type')
        dir_f    = request.query_params.get('direction')  # 'in' | 'out'

        if status_f:
            qs = qs.filter(status=status_f)
        if type_f:
            qs = qs.filter(transfer_type=type_f)
        if dir_f == 'in':
            qs = qs.filter(to_tenant_id=tenant)
        elif dir_f == 'out':
            qs = qs.filter(from_tenant_id=tenant)

        # Parents see only transfers for their children
        if _is_transfer_parent(request.user):
            from .models import UserProfile, Guardian
            try:
                profile = UserProfile.objects.get(user=request.user)
                guardian = Guardian.objects.filter(user=request.user).first()
                if guardian:
                    student_ids = list(guardian.students.values_list('id', flat=True))
                    qs = qs.filter(entity_id__in=student_ids, transfer_type__in=['student', 'internal_student'])
                else:
                    qs = qs.none()
            except Exception:
                qs = qs.none()

        serializer = CrossTenantTransferSerializer(qs, many=True)
        stats = {
            'pending': qs.filter(status='pending').count(),
            'approved_from': qs.filter(status='approved_from').count(),
            'approved_to': qs.filter(status='approved_to').count(),
            'completed': qs.filter(status='completed').count(),
            'rejected': qs.filter(status='rejected').count(),
            'incoming': qs.filter(to_tenant_id=tenant).count(),
            'outgoing': qs.filter(from_tenant_id=tenant).count(),
        }
        return Response({'results': serializer.data, 'count': qs.count(), 'stats': stats})


class TransferInitiateView(APIView):
    """POST /transfers/initiate/ — initiate a new transfer."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from .models import CrossTenantTransfer, Student, StudentHistory
        from .serializers import CrossTenantTransferSerializer

        # RBAC: admin or parent (parent only for student transfer)
        is_admin = _is_transfer_admin(request.user)
        is_parent = _is_transfer_parent(request.user)
        if not (is_admin or is_parent):
            return Response({'detail': 'Only admins or parents can initiate transfers.'},
                            status=status.HTTP_403_FORBIDDEN)

        data = request.data
        transfer_type = data.get('transfer_type', 'student')
        if is_parent and 'staff' in transfer_type:
            return Response({'detail': 'Parents can only initiate student transfers.'},
                            status=status.HTTP_403_FORBIDDEN)

        entity_id  = data.get('entity_id')
        to_tenant  = data.get('to_tenant_id', '')
        reason     = data.get('reason', '')

        if not entity_id:
            return Response({'detail': 'entity_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        tenant = getattr(request.tenant, 'schema_name', '')

        # Edge case: check for active exams
        exam_flag = False
        mid_term_flag = False
        fee_balance = False

        if 'student' in transfer_type:
            try:
                student = Student.objects.get(id=entity_id)
                # Check fee balance
                from .models import FeeInvoice
                invoices = FeeInvoice.objects.filter(student=student)
                total_due  = sum(i.amount_due for i in invoices)
                total_paid = sum(i.amount_paid for i in invoices)
                if float(total_due - total_paid) > 0:
                    fee_balance = True
            except Student.DoesNotExist:
                return Response({'detail': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)
            except Exception:
                pass

        transfer = CrossTenantTransfer.objects.create(
            transfer_type=transfer_type,
            entity_id=entity_id,
            from_tenant_id=tenant,
            to_tenant_id=to_tenant,
            reason=reason,
            status='pending',
            initiated_by=request.user,
            exam_in_progress=exam_flag,
            mid_term=mid_term_flag,
            fee_balance_cleared=not fee_balance,
            effective_date=data.get('effective_date'),
            from_class=data.get('from_class', ''),
            to_class=data.get('to_class', ''),
            from_stream=data.get('from_stream', ''),
            to_stream=data.get('to_stream', ''),
            from_department=data.get('from_department', ''),
            to_department=data.get('to_department', ''),
            from_role=data.get('from_role', ''),
            to_role=data.get('to_role', ''),
            notes=data.get('notes', ''),
        )

        # Generate transfer package immediately
        _transfer_generate_package(transfer)

        warnings = []
        if fee_balance:
            warnings.append('Student has outstanding fee balance. Transfer flagged.')
        if exam_flag:
            warnings.append('Exam in progress detected. Please verify before proceeding.')

        return Response({
            'detail': 'Transfer initiated successfully.',
            'transfer': CrossTenantTransferSerializer(transfer).data,
            'warnings': warnings,
        }, status=status.HTTP_201_CREATED)


class TransferDetailView(APIView):
    """GET /transfers/{id}/ — retrieve transfer details."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, transfer_id):
        from .models import CrossTenantTransfer
        from .serializers import CrossTenantTransferSerializer
        tenant = getattr(request.tenant, 'schema_name', '')
        try:
            transfer = CrossTenantTransfer.objects.get(
                id=transfer_id,
                **({'from_tenant_id': tenant} if not _is_transfer_admin(request.user) else {})
            )
        except CrossTenantTransfer.DoesNotExist:
            try:
                transfer = CrossTenantTransfer.objects.get(id=transfer_id, to_tenant_id=tenant)
            except CrossTenantTransfer.DoesNotExist:
                return Response({'detail': 'Transfer not found.'}, status=status.HTTP_404_NOT_FOUND)

        return Response(CrossTenantTransferSerializer(transfer).data)


class TransferApproveFromView(APIView):
    """POST /transfers/{id}/approve-from/ — source school approves."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, transfer_id):
        from .models import CrossTenantTransfer
        from .serializers import CrossTenantTransferSerializer
        if not _is_transfer_admin(request.user):
            return Response({'detail': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            transfer = CrossTenantTransfer.objects.get(id=transfer_id)
        except CrossTenantTransfer.DoesNotExist:
            return Response({'detail': 'Transfer not found.'}, status=status.HTTP_404_NOT_FOUND)

        if transfer.status != 'pending':
            return Response({'detail': f'Cannot approve from — current status is "{transfer.status}".'}, status=status.HTTP_400_BAD_REQUEST)
        if transfer.exam_in_progress:
            return Response({'detail': 'Cannot approve transfer while exam is in progress.'}, status=status.HTTP_400_BAD_REQUEST)

        transfer.status = 'approved_from'
        transfer.approved_from_by = request.user
        transfer.save()

        # Regenerate package
        _transfer_generate_package(transfer)

        return Response({
            'detail': 'Transfer approved by source school.',
            'transfer': CrossTenantTransferSerializer(transfer).data,
        })


class TransferApproveToView(APIView):
    """POST /transfers/{id}/approve-to/ — destination school approves (both approvals → ready to execute)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, transfer_id):
        from .models import CrossTenantTransfer
        from .serializers import CrossTenantTransferSerializer
        if not _is_transfer_admin(request.user):
            return Response({'detail': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            transfer = CrossTenantTransfer.objects.get(id=transfer_id)
        except CrossTenantTransfer.DoesNotExist:
            return Response({'detail': 'Transfer not found.'}, status=status.HTTP_404_NOT_FOUND)

        # For internal transfers, only one approval needed
        is_internal = transfer.transfer_type.startswith('internal_')
        if is_internal:
            if transfer.status not in ('pending', 'approved_from'):
                return Response({'detail': f'Cannot approve — current status is "{transfer.status}".'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            if transfer.status != 'approved_from':
                return Response({'detail': 'Source school must approve first.'}, status=status.HTTP_400_BAD_REQUEST)

        transfer.status = 'approved_to'
        transfer.approved_to_by = request.user
        transfer.save()
        return Response({
            'detail': 'Transfer approved by destination. Ready to execute.',
            'transfer': CrossTenantTransferSerializer(transfer).data,
        })


class TransferRejectView(APIView):
    """POST /transfers/{id}/reject/ — reject a transfer."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, transfer_id):
        from .models import CrossTenantTransfer
        from .serializers import CrossTenantTransferSerializer
        if not _is_transfer_admin(request.user):
            return Response({'detail': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            transfer = CrossTenantTransfer.objects.get(id=transfer_id)
        except CrossTenantTransfer.DoesNotExist:
            return Response({'detail': 'Transfer not found.'}, status=status.HTTP_404_NOT_FOUND)

        if transfer.status in ('completed', 'cancelled'):
            return Response({'detail': 'Cannot reject a completed or cancelled transfer.'}, status=status.HTTP_400_BAD_REQUEST)

        transfer.status = 'rejected'
        transfer.rejected_by = request.user
        transfer.rejection_reason = request.data.get('reason', '')
        transfer.save()
        return Response({
            'detail': 'Transfer rejected.',
            'transfer': CrossTenantTransferSerializer(transfer).data,
        })


class TransferCancelView(APIView):
    """POST /transfers/{id}/cancel/ — cancel before execution (rollback)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, transfer_id):
        from .models import CrossTenantTransfer
        from .serializers import CrossTenantTransferSerializer
        try:
            transfer = CrossTenantTransfer.objects.get(id=transfer_id)
        except CrossTenantTransfer.DoesNotExist:
            return Response({'detail': 'Transfer not found.'}, status=status.HTTP_404_NOT_FOUND)

        if transfer.status == 'completed':
            return Response({'detail': 'Cannot cancel an already completed transfer.'}, status=status.HTTP_400_BAD_REQUEST)

        is_admin = _is_transfer_admin(request.user)
        is_parent = _is_transfer_parent(request.user)
        if not (is_admin or is_parent):
            return Response({'detail': 'Not authorized to cancel this transfer.'}, status=status.HTTP_403_FORBIDDEN)

        transfer.status = 'cancelled'
        transfer.notes = (transfer.notes + f'\nCancelled by {request.user.username}: {request.data.get("reason","")}').strip()
        transfer.save()
        return Response({
            'detail': 'Transfer cancelled successfully.',
            'transfer': CrossTenantTransferSerializer(transfer).data,
        })


class TransferExecuteView(APIView):
    """POST /transfers/{id}/execute/ — execute a fully-approved transfer."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, transfer_id):
        from django.utils import timezone
        from .models import CrossTenantTransfer, StudentHistory, StaffHistory
        from .serializers import CrossTenantTransferSerializer

        if not _is_transfer_admin(request.user):
            return Response({'detail': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            transfer = CrossTenantTransfer.objects.get(id=transfer_id)
        except CrossTenantTransfer.DoesNotExist:
            return Response({'detail': 'Transfer not found.'}, status=status.HTTP_404_NOT_FOUND)

        if transfer.status != 'approved_to':
            return Response({'detail': f'Transfer must be fully approved before execution (current: {transfer.status}).'}, status=status.HTTP_400_BAD_REQUEST)

        is_internal = transfer.transfer_type.startswith('internal_')
        today = timezone.now().date()

        if 'student' in transfer.transfer_type:
            from .models import Student
            try:
                student = Student.objects.get(id=transfer.entity_id)
            except Student.DoesNotExist:
                return Response({'detail': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)

            if is_internal:
                # Close current history record
                StudentHistory.objects.filter(student=student, end_date__isnull=True).update(end_date=today)
                # Open new history record
                StudentHistory.objects.create(
                    student=student,
                    tenant_id=transfer.from_tenant_id,
                    school_name=transfer.from_tenant_id,
                    class_name=transfer.to_class,
                    stream=transfer.to_stream,
                    start_date=today,
                    transfer=transfer,
                )
            else:
                # Cross-tenant: mark active enrollments as Transferred, deactivate student
                from .models import Enrollment as _Enrollment
                _Enrollment.objects.filter(student=student, status='Active').update(status='Transferred')
                student.is_active = False
                student.save(update_fields=['is_active'])
                # Close history
                StudentHistory.objects.filter(student=student, end_date__isnull=True).update(end_date=today)
                # Open a placeholder history at destination tenant
                StudentHistory.objects.create(
                    student=student,
                    tenant_id=transfer.to_tenant_id,
                    school_name=transfer.to_tenant_id,
                    class_name=transfer.to_class,
                    stream=transfer.to_stream,
                    start_date=today,
                    transfer=transfer,
                )

        else:
            # Staff transfer
            try:
                from hr.models import Employee
                emp = Employee.objects.filter(id=transfer.entity_id).first()
                if emp:
                    StaffHistory.objects.filter(employee_id=transfer.entity_id, end_date__isnull=True).update(end_date=today)
                    StaffHistory.objects.create(
                        employee_id=transfer.entity_id,
                        employee_name=f"{emp.first_name} {emp.last_name}",
                        tenant_id=transfer.to_tenant_id or transfer.from_tenant_id,
                        school_name=transfer.to_tenant_id or transfer.from_tenant_id,
                        role=transfer.to_role or getattr(emp, 'designation', ''),
                        department=transfer.to_department,
                        start_date=today,
                        transfer=transfer,
                    )
                    if not is_internal:
                        emp.is_active = False
                        emp.save(update_fields=['is_active'])
            except Exception as e:
                pass

        transfer.status = 'completed'
        transfer.executed_at = timezone.now()
        transfer.save()

        return Response({
            'detail': 'Transfer executed successfully.',
            'transfer': CrossTenantTransferSerializer(transfer).data,
        })


class TransferPackageView(APIView):
    """GET /transfers/{id}/package/ — retrieve or regenerate the data package."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, transfer_id):
        from .models import CrossTenantTransfer
        from .serializers import TransferPackageSerializer
        try:
            transfer = CrossTenantTransfer.objects.get(id=transfer_id)
        except CrossTenantTransfer.DoesNotExist:
            return Response({'detail': 'Transfer not found.'}, status=status.HTTP_404_NOT_FOUND)

        snapshot = _transfer_generate_package(transfer)
        from .models import TransferPackage
        pkg = TransferPackage.objects.get(transfer=transfer)
        return Response(TransferPackageSerializer(pkg).data)


class StudentTransferHistoryView(APIView):
    """GET /students/{student_id}/transfer-history/ — all history entries for a student."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, student_id):
        from .models import StudentHistory
        from .serializers import StudentHistorySerializer
        qs = StudentHistory.objects.filter(student_id=student_id).select_related('transfer')
        return Response(StudentHistorySerializer(qs, many=True).data)


class StaffTransferHistoryView(APIView):
    """GET /staff/{employee_id}/transfer-history/ — all history entries for a staff member."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, employee_id):
        from .models import StaffHistory
        from .serializers import StaffHistorySerializer
        qs = StaffHistory.objects.filter(employee_id=employee_id)
        return Response(StaffHistorySerializer(qs, many=True).data)


# ═══════════════════════════════════════════════════════════════
# SETTINGS & ADMISSION SYSTEM — API Views
# ═══════════════════════════════════════════════════════════════

class AdmissionSettingsView(APIView):
    """GET / PATCH tenant admission-number configuration."""
    permission_classes = [CanManageSystemSettings]

    def _get_or_create(self):
        from .models import AdmissionSettings
        obj, _ = AdmissionSettings.objects.get_or_create(pk=1)
        return obj

    def get(self, request):
        from .models import AdmissionSettings
        obj = self._get_or_create()
        profile = SchoolProfile.objects.filter(is_active=True).first()
        data = {
            'prefix':           obj.prefix,
            'year':             obj.year,
            'sequence':         obj.sequence,
            'padding':          obj.padding,
            'include_year':     obj.include_year,
            'reset_policy':     obj.reset_policy,
            'transfer_policy':  obj.transfer_policy,
            'auto_generate':    obj.auto_generate,
            'updated_at':       obj.updated_at,
            # legacy fields from SchoolProfile (kept in sync)
            'legacy_prefix':    profile.admission_number_prefix if profile else 'ADM-',
            'legacy_mode':      profile.admission_number_mode if profile else 'AUTO',
        }
        return Response(data)

    def patch(self, request):
        obj = self._get_or_create()
        allowed = ['prefix', 'year', 'sequence', 'padding', 'include_year',
                   'reset_policy', 'transfer_policy', 'auto_generate']
        for field in allowed:
            if field in request.data:
                setattr(obj, field, request.data[field])
        obj.save()
        # Keep SchoolProfile.admission_number_prefix in sync
        profile = SchoolProfile.objects.filter(is_active=True).first()
        if profile and 'prefix' in request.data:
            profile.admission_number_prefix = request.data['prefix']
            profile.save(update_fields=['admission_number_prefix'])
        from .models import AuditLog
        AuditLog.objects.create(
            user=request.user,
            action='UPDATE',
            model_name='AdmissionSettings',
            object_id='1',
            details=f"Updated by {request.user.username}",
        )
        return Response({'detail': 'Admission settings updated.', 'sequence': obj.sequence})


class AdmissionNumberPreviewView(APIView):
    """GET — preview what the next admission number will look like without consuming it."""
    permission_classes = [CanManageSystemSettings]

    def get(self, request):
        from .models import AdmissionSettings
        obj, _ = AdmissionSettings.objects.get_or_create(pk=1)
        next_seq = obj.sequence + 1
        seq_str = str(next_seq).zfill(obj.padding)
        if obj.include_year:
            preview = f"{obj.prefix}{obj.year}-{seq_str}"
        else:
            preview = f"{obj.prefix}{seq_str}"
        return Response({
            'preview': preview,
            'next_sequence': next_seq,
            'format': f"{obj.prefix}{'YEAR-' if obj.include_year else ''}{seq_str}",
        })


class MediaUploadView(APIView):
    """POST multipart file upload → returns stored MediaFile record."""
    permission_classes = [CanManageSystemSettings]
    parser_classes = [MultiPartParser, FormParser]

    _MIME_MAP = {
        'image/jpeg': 'image', 'image/png': 'image', 'image/gif': 'image',
        'image/webp': 'image', 'image/svg+xml': 'image',
        'application/pdf': 'pdf',
        'application/msword': 'doc',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'doc',
        'application/vnd.ms-excel': 'spreadsheet',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'spreadsheet',
        'text/csv': 'spreadsheet',
    }

    def post(self, request):
        from .models import MediaFile
        upload = request.FILES.get('file')
        if not upload:
            return Response({'error': 'file is required'}, status=status.HTTP_400_BAD_REQUEST)

        module = (request.data.get('module') or 'OTHER').upper()
        valid_modules = ['STUDENTS', 'STAFF', 'FINANCE', 'BRANDING', 'COMMUNICATION', 'OTHER']
        if module not in valid_modules:
            module = 'OTHER'

        content_type = upload.content_type or ''
        file_type = self._MIME_MAP.get(content_type, 'other')

        mf = MediaFile.objects.create(
            module=module,
            file_type=file_type,
            file=upload,
            original_name=upload.name,
            size_bytes=upload.size,
            uploaded_by=request.user,
            description=request.data.get('description', ''),
        )
        url = request.build_absolute_uri(mf.file.url)
        mf.url = url
        mf.save(update_fields=['url'])

        return Response({
            'id':            mf.id,
            'module':        mf.module,
            'file_type':     mf.file_type,
            'original_name': mf.original_name,
            'size_bytes':    mf.size_bytes,
            'url':           url,
            'created_at':    mf.created_at,
        }, status=status.HTTP_201_CREATED)


class MediaFileListView(APIView):
    """GET list of uploaded media files, optionally filtered by module."""
    permission_classes = [CanManageSystemSettings]

    def get(self, request):
        from .models import MediaFile
        module = request.query_params.get('module', '').upper()
        qs = MediaFile.objects.all()
        if module:
            qs = qs.filter(module=module)
        data = []
        for mf in qs[:100]:
            data.append({
                'id': mf.id, 'module': mf.module, 'file_type': mf.file_type,
                'original_name': mf.original_name, 'size_bytes': mf.size_bytes,
                'url': request.build_absolute_uri(mf.file.url) if mf.file else mf.url,
                'description': mf.description, 'created_at': mf.created_at,
                'uploaded_by': mf.uploaded_by.get_full_name() if mf.uploaded_by else '',
            })
        return Response({'count': len(data), 'results': data})


class ImportTemplateDownloadView(APIView):
    """GET — download a blank CSV import template for the given module."""
    permission_classes = [CanManageSystemSettings]

    _TEMPLATES = {
        'students': [
            'first_name', 'last_name', 'gender', 'date_of_birth',
            'admission_number', 'class_name', 'stream',
            'parent_name', 'parent_phone', 'parent_email',
            'address', 'national_id',
        ],
        'staff': [
            'first_name', 'last_name', 'gender', 'date_of_birth',
            'employee_id', 'department', 'designation', 'date_joined',
            'email', 'phone', 'national_id', 'tsc_number',
        ],
        'fees': [
            'admission_number', 'student_name', 'fee_item', 'amount',
            'academic_year', 'term', 'due_date',
        ],
        'payments': [
            'admission_number', 'amount', 'payment_date', 'reference',
            'payment_method', 'notes',
        ],
    }

    def get(self, request, module):
        module = module.lower()
        headers = self._TEMPLATES.get(module)
        if not headers:
            return Response(
                {'error': f"No template for module '{module}'. Valid: {list(self._TEMPLATES)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{module}_import_template.csv"'
        writer = _SafeCsvWriter(response)
        writer.writerow(headers)
        # Write 3 example rows to guide the user
        if module == 'students':
            writer.writerow(['Jane', 'Doe', 'Female', '2015-03-14', '', 'Grade 4', 'East', 'John Doe', '0700000001', 'jdoe@example.com', 'Nairobi', ''])
        elif module == 'staff':
            writer.writerow(['Samuel', 'Otieno', 'Male', '1985-06-01', '', 'Science', 'Teacher', '2020-01-15', 'samuel@school.ac.ke', '0711222333', '12345678', 'TSC12345'])
        return response


class StudentsBulkImportView(APIView):
    """
    POST multipart CSV upload to bulk-import students.
    Pass validate_only=true to preview errors without committing.
    """
    permission_classes = [CanManageSystemSettings]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    _REQUIRED = {'first_name', 'last_name', 'gender', 'date_of_birth', 'class_name'}

    def post(self, request):
        upload = request.FILES.get('file')
        validate_only = str(request.data.get('validate_only', 'false')).lower() in ('true', '1', 'yes')

        if not upload:
            return Response({'error': 'file is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            decoded = upload.read().decode('utf-8-sig')
        except Exception:
            return Response({'error': 'Cannot decode file. Use UTF-8 CSV.'}, status=status.HTTP_400_BAD_REQUEST)

        reader = csv.DictReader(decoded.splitlines())
        if not reader.fieldnames:
            return Response({'error': 'CSV has no headers.'}, status=status.HTTP_400_BAD_REQUEST)

        rows = list(reader)
        errors = []
        previews = []

        for idx, row in enumerate(rows, start=2):
            row_errors = []
            for f in self._REQUIRED:
                if not (row.get(f) or '').strip():
                    row_errors.append(f"'{f}' is required")
            if row_errors:
                errors.append({'row': idx, 'errors': row_errors})
                continue

            # Check for duplicate admission number
            adm = (row.get('admission_number') or '').strip()
            if adm and Student.objects.filter(admission_number=adm).exists():
                errors.append({'row': idx, 'errors': [f"Admission number '{adm}' already exists"]})
                continue

            # Check duplicate by name + DOB
            dob_raw = (row.get('date_of_birth') or '').strip()
            try:
                dob = datetime.strptime(dob_raw, '%Y-%m-%d').date() if dob_raw else None
            except ValueError:
                errors.append({'row': idx, 'errors': [f"date_of_birth '{dob_raw}' must be YYYY-MM-DD"]})
                continue

            previews.append({'row': idx, 'first_name': row.get('first_name', '').strip(),
                             'last_name': row.get('last_name', '').strip(), 'admission_number': adm or '(auto)'})

        if validate_only or errors:
            return Response({
                'valid_rows': len(previews),
                'error_rows': len(errors),
                'errors': errors[:50],
                'preview': previews[:20],
                'committed': False,
            })

        # Commit import
        from .models import AdmissionSettings
        admission_cfg, _ = AdmissionSettings.objects.get_or_create(pk=1)
        created_ids = []
        commit_errors = []

        for idx, row in enumerate(rows, start=2):
            for f in self._REQUIRED:
                if not (row.get(f) or '').strip():
                    continue

            try:
                dob_raw = (row.get('date_of_birth') or '').strip()
                dob = datetime.strptime(dob_raw, '%Y-%m-%d').date() if dob_raw else None

                adm = (row.get('admission_number') or '').strip()
                if not adm:
                    if admission_cfg.auto_generate:
                        adm = admission_cfg.generate_next()
                        while Student.objects.filter(admission_number=adm).exists():
                            adm = admission_cfg.generate_next()
                    else:
                        adm = _resolve_student_admission_number(None)

                # Resolve class
                class_name = (row.get('class_name') or '').strip()
                school_class = SchoolClass.objects.filter(name__iexact=class_name).first() if class_name else None

                student = Student.objects.create(
                    first_name=(row.get('first_name') or '').strip(),
                    last_name=(row.get('last_name') or '').strip(),
                    gender=(row.get('gender') or 'Other').strip(),
                    date_of_birth=dob,
                    admission_number=adm,
                    address=(row.get('address') or '').strip(),
                    is_active=True,
                )
                if school_class:
                    Enrollment.objects.create(
                        student=student,
                        school_class=school_class,
                        stream=(row.get('stream') or '').strip(),
                        status='Active',
                        is_active=True,
                        enrollment_date=timezone.now().date(),
                    )
                created_ids.append(student.id)
            except Exception as exc:
                commit_errors.append({'row': idx, 'errors': [str(exc)]})

        return Response({
            'valid_rows': len(previews),
            'created': len(created_ids),
            'failed': len(commit_errors),
            'errors': commit_errors[:25],
            'committed': True,
        }, status=status.HTTP_201_CREATED)


class StaffBulkImportView(APIView):
    """
    POST CSV to bulk-import staff (HR employees).
    Pass validate_only=true for a dry run.
    """
    permission_classes = [CanManageSystemSettings]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    _REQUIRED = {'first_name', 'last_name', 'gender', 'department', 'designation'}

    def post(self, request):
        upload = request.FILES.get('file')
        validate_only = str(request.data.get('validate_only', 'false')).lower() in ('true', '1', 'yes')

        if not upload:
            return Response({'error': 'file is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            decoded = upload.read().decode('utf-8-sig')
        except Exception:
            return Response({'error': 'Cannot decode file. Use UTF-8 CSV.'}, status=status.HTTP_400_BAD_REQUEST)

        reader = csv.DictReader(decoded.splitlines())
        rows = list(reader)
        errors = []
        previews = []

        for idx, row in enumerate(rows, start=2):
            row_errors = []
            for f in self._REQUIRED:
                if not (row.get(f) or '').strip():
                    row_errors.append(f"'{f}' is required")
            if row_errors:
                errors.append({'row': idx, 'errors': row_errors})
            else:
                previews.append({'row': idx, 'name': f"{row.get('first_name','')} {row.get('last_name','')}".strip(),
                                 'department': row.get('department', ''), 'designation': row.get('designation', '')})

        if validate_only or errors:
            return Response({
                'valid_rows': len(previews),
                'error_rows': len(errors),
                'errors': errors[:50],
                'preview': previews[:20],
                'committed': False,
            })

        # Commit — delegate to HR Employee model
        created_count = 0
        commit_errors = []

        try:
            from hr.models import Employee, Department
        except ImportError:
            return Response({'error': 'HR module not available.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        for idx, row in enumerate(rows, start=2):
            missing = [f for f in self._REQUIRED if not (row.get(f) or '').strip()]
            if missing:
                continue
            try:
                dept_name = (row.get('department') or '').strip()
                dept = Department.objects.filter(name__iexact=dept_name).first()

                dob_raw = (row.get('date_of_birth') or '').strip()
                dob = datetime.strptime(dob_raw, '%Y-%m-%d').date() if dob_raw else None
                joined_raw = (row.get('date_joined') or '').strip()
                joined = datetime.strptime(joined_raw, '%Y-%m-%d').date() if joined_raw else timezone.now().date()

                Employee.objects.create(
                    first_name=(row.get('first_name') or '').strip(),
                    last_name=(row.get('last_name') or '').strip(),
                    gender=(row.get('gender') or 'Male').strip(),
                    date_of_birth=dob,
                    date_joined=joined,
                    email=(row.get('email') or '').strip(),
                    phone=(row.get('phone') or '').strip(),
                    designation=(row.get('designation') or '').strip(),
                    department=dept,
                    tsc_number=(row.get('tsc_number') or '').strip(),
                    employment_status='Active',
                )
                created_count += 1
            except Exception as exc:
                commit_errors.append({'row': idx, 'errors': [str(exc)]})

        return Response({
            'created': created_count,
            'failed': len(commit_errors),
            'errors': commit_errors[:25],
            'committed': True,
        }, status=status.HTTP_201_CREATED)


# ═══════════════════════════════════════════════════════════════
# TENANT SETTINGS KV STORE
# ═══════════════════════════════════════════════════════════════

class TenantSettingsView(APIView):
    """
    GET  /settings/          → return all settings as {key: value} dict, grouped by category
    POST /settings/          → upsert one or many {key, value, description?, category?} entries
    DELETE /settings/{key}/  → delete a setting key
    """
    permission_classes = [CanManageSystemSettings]

    def get(self, request):
        from .models import TenantSettings
        category = request.query_params.get('category', '')
        qs = TenantSettings.objects.all()
        if category:
            qs = qs.filter(category=category)

        # Return as flat dict AND grouped structure
        flat = {}
        grouped = {}
        for s in qs:
            flat[s.key] = s.value
            grouped.setdefault(s.category, {})[s.key] = {
                'value': s.value,
                'description': s.description,
                'updated_at': s.updated_at,
            }

        return Response({
            'settings': flat,
            'grouped': grouped,
            'count': qs.count(),
        })

    def post(self, request):
        from .models import TenantSettings, AuditLog
        data = request.data

        # Accept a single dict OR a list
        if isinstance(data, dict) and 'key' in data:
            entries = [data]
        elif isinstance(data, list):
            entries = data
        elif isinstance(data, dict):
            # Shorthand: {key: value, key2: value2}  (no 'key' field, just a flat mapping)
            entries = [{'key': k, 'value': v} for k, v in data.items() if k != 'key']
        else:
            return Response({'error': 'Expected a dict or list of {key, value} entries.'}, status=status.HTTP_400_BAD_REQUEST)

        upserted = []
        for entry in entries:
            key = str(entry.get('key', '')).strip()
            if not key:
                continue
            obj, _ = TenantSettings.objects.update_or_create(
                key=key,
                defaults={
                    'value': entry.get('value'),
                    'description': entry.get('description', ''),
                    'category': entry.get('category', 'general'),
                    'updated_by': request.user,
                },
            )
            upserted.append(key)

        AuditLog.objects.create(
            user=request.user,
            action='UPSERT',
            model_name='TenantSettings',
            object_id='bulk',
            details=f"Updated keys: {', '.join(upserted[:20])}",
        )
        return Response({'upserted': upserted, 'count': len(upserted)})


class TenantSettingDeleteView(APIView):
    """DELETE /settings/<key>/ — remove a single setting key."""
    permission_classes = [CanManageSystemSettings]

    def delete(self, request, setting_key):
        from .models import TenantSettings
        deleted, _ = TenantSettings.objects.filter(key=setting_key).delete()
        return Response({'deleted': deleted, 'key': setting_key})


class FinanceSettingsView(APIView):
    """
    GET/PATCH finance-specific settings from SchoolProfile:
    currency, tax_percentage, receipt_prefix, invoice_prefix,
    late_fee_grace_days, late_fee_type, late_fee_value, late_fee_max,
    accepted_payment_methods.
    """
    permission_classes = [CanManageSystemSettings]

    _FINANCE_FIELDS = [
        'currency', 'tax_percentage', 'receipt_prefix', 'invoice_prefix',
        'late_fee_grace_days', 'late_fee_type', 'late_fee_value', 'late_fee_max',
        'accepted_payment_methods',
    ]

    def _get_profile(self):
        profile = SchoolProfile.objects.filter(is_active=True).first()
        if not profile:
            tenant = None
            profile = SchoolProfile.objects.create(school_name='School', is_active=True)
        return profile

    def get(self, request):
        profile = self._get_profile()
        data = {f: getattr(profile, f) for f in self._FINANCE_FIELDS}
        # Include late fee rules list
        from .models import LateFeeRule
        rules = list(LateFeeRule.objects.filter(is_active=True).values(
            'id', 'grace_days', 'fee_type', 'value', 'max_fee', 'is_active'
        ))
        data['late_fee_rules'] = rules
        return Response(data)

    def patch(self, request):
        profile = self._get_profile()
        for field in self._FINANCE_FIELDS:
            if field in request.data:
                setattr(profile, field, request.data[field])
        profile.save(update_fields=self._FINANCE_FIELDS + ['updated_at'])
        data = {f: getattr(profile, f) for f in self._FINANCE_FIELDS}
        return Response({'detail': 'Finance settings updated.', **data})


class MpesaStkPushView(APIView):
    """
    POST /api/finance/mpesa/push/
    Admin / finance staff can initiate an STK push for any student or invoice.

    Body:
        phone        (str, required)  — customer's Kenyan phone number
        amount       (str, required)  — amount in KES
        student_id   (int, optional)  — link transaction to a student
        invoice_id   (int, optional)  — link transaction to a specific invoice
        description  (str, optional)  — max 13 chars shown on phone
    """
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "FINANCE"

    def post(self, request):
        from .mpesa import initiate_stk_push, MpesaError, _normalise_phone
        from .models import PaymentGatewayTransaction
        from decimal import Decimal, InvalidOperation
        import uuid

        phone = (request.data.get("phone") or "").strip()
        if not phone:
            return Response({"error": "Phone number is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount = Decimal(str(request.data.get("amount") or "0"))
        except InvalidOperation:
            return Response({"error": "Invalid amount."}, status=status.HTTP_400_BAD_REQUEST)
        if amount <= 0:
            return Response({"error": "Amount must be greater than zero."}, status=status.HTTP_400_BAD_REQUEST)

        student_id = request.data.get("student_id")
        invoice_id = request.data.get("invoice_id")
        description = (request.data.get("description") or "School Fees")[:13]

        # Build callback URL — Safaricom requires HTTPS in production
        callback_url = request.build_absolute_uri("/api/finance/mpesa/callback/")
        if not callback_url.startswith("https://") and settings.DEBUG:
            # In sandbox mode Daraja accepts http; just log a warning
            import logging
            logging.getLogger(__name__).warning(
                "MPesa callback URL is not HTTPS: %s. This is only acceptable in sandbox mode.", callback_url
            )

        reference = f"FEES-{uuid.uuid4().hex[:6].upper()}"

        try:
            result = initiate_stk_push(
                phone=phone,
                amount=amount,
                account_ref=reference,
                callback_url=callback_url,
                description=description,
            )
        except MpesaError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # Record the pending transaction
        tx = PaymentGatewayTransaction.objects.create(
            provider="mpesa",
            external_id=result["checkout_request_id"],
            student_id=student_id,
            invoice_id=invoice_id,
            amount=amount,
            currency="KES",
            status="PENDING",
            payload={
                "checkout_request_id": result["checkout_request_id"],
                "merchant_request_id": result["merchant_request_id"],
                "phone": phone,
                "reference": reference,
                "description": description,
                "environment": result["environment"],
                "initiated_by_user_id": request.user.id,
                "initiated_by_username": request.user.username,
            },
        )

        return Response(
            {
                "transaction_id": tx.id,
                "checkout_request_id": result["checkout_request_id"],
                "reference": reference,
                "message": result["customer_message"] or "STK push sent. Please check your phone.",
                "status": "PENDING",
            },
            status=status.HTTP_201_CREATED,
        )


class MpesaStkCallbackView(APIView):
    """
    POST /api/finance/mpesa/callback/
    Safaricom Daraja posts the STK push result here.
    This endpoint is public (no auth) — Safaricom cannot send auth headers.
    On success: updates the PaymentGatewayTransaction and creates a Payment record.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from .mpesa import parse_stk_callback
        from .models import PaymentGatewayTransaction, Payment
        from django.utils import timezone as tz
        import logging

        log = logging.getLogger(__name__)
        payload = request.data if isinstance(request.data, dict) else {}
        parsed = parse_stk_callback(payload)

        checkout_id = parsed.get("checkout_request_id", "")
        if not checkout_id:
            return Response({"ResultCode": 0, "ResultDesc": "Accepted (no checkout id)"})

        try:
            tx = PaymentGatewayTransaction.objects.filter(
                provider="mpesa",
                external_id=checkout_id,
            ).first()

            if tx:
                if parsed["success"]:
                    tx.status = "SUCCEEDED"
                    tx.payload.update({
                        "mpesa_receipt": parsed["mpesa_receipt"],
                        "transaction_date": parsed["transaction_date"],
                        "phone": parsed["phone"],
                        "callback_result_desc": parsed["result_desc"],
                    })
                    tx.save(update_fields=["status", "payload", "updated_at"])

                    # Create a Payment record if one doesn't already exist for this receipt
                    if parsed["mpesa_receipt"] and not Payment.objects.filter(
                        reference_number=parsed["mpesa_receipt"]
                    ).exists():
                        payment = FinanceService.record_payment(
                            student=tx.student,
                            amount=parsed["amount"] or tx.amount,
                            payment_method="M-Pesa",
                            reference_number=parsed["mpesa_receipt"],
                            notes=f"M-Pesa STK Push | {parsed['phone']} | {parsed['transaction_date']}",
                        )
                        # Allocate against the specific invoice if known, otherwise auto-allocate
                        try:
                            if tx.invoice_id and tx.student:
                                invoice = Invoice.objects.filter(
                                    id=tx.invoice_id, student=tx.student, is_active=True
                                ).exclude(status="VOID").first()
                                if invoice and invoice.balance_due > 0:
                                    alloc_amt = min(payment.amount, invoice.balance_due)
                                    FinanceService.allocate_payment(payment, invoice, alloc_amt)
                                else:
                                    FinanceService.auto_allocate_payment(payment)
                            elif tx.student:
                                FinanceService.auto_allocate_payment(payment)
                        except Exception as alloc_exc:
                            log.warning(
                                "MPesa callback: payment %s created but allocation failed: %s",
                                payment.id, alloc_exc,
                            )
                else:
                    tx.status = "FAILED"
                    tx.payload.update({
                        "result_code": parsed["result_code"],
                        "result_desc": parsed["result_desc"],
                    })
                    tx.save(update_fields=["status", "payload", "updated_at"])
            else:
                log.warning("MPesa callback received for unknown checkout_id: %s", checkout_id)

        except Exception as exc:
            log.error("Error processing MPesa callback: %s", exc, exc_info=True)

        # Always return 200 — Safaricom retries on non-200
        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})


class MpesaStkStatusView(APIView):
    """
    GET /api/finance/mpesa/status/?checkout_request_id=xxx
    Poll the status of a pending STK push transaction.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .models import PaymentGatewayTransaction

        checkout_id = request.query_params.get("checkout_request_id", "").strip()
        if not checkout_id:
            return Response({"error": "checkout_request_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        tx = PaymentGatewayTransaction.objects.filter(
            provider="mpesa", external_id=checkout_id
        ).first()
        if not tx:
            return Response({"error": "Transaction not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            "transaction_id": tx.id,
            "status": tx.status,
            "amount": str(tx.amount),
            "mpesa_receipt": tx.payload.get("mpesa_receipt"),
            "result_desc": tx.payload.get("callback_result_desc") or tx.payload.get("result_desc"),
            "updated_at": tx.updated_at,
        })


class GeneralSettingsView(APIView):
    """
    GET/PATCH general school settings: timezone, language, default_date_format
    and school identity (name, motto, address, phone, email, website, country, county).
    """
    permission_classes = [CanManageSystemSettings]

    _GENERAL_FIELDS = [
        'school_name', 'motto', 'address', 'phone', 'email_address',
        'website', 'county', 'country',
        'timezone', 'language', 'default_date_format',
    ]

    def get(self, request):
        profile = SchoolProfile.objects.filter(is_active=True).first()
        if not profile:
            return Response({f: '' for f in self._GENERAL_FIELDS})
        data = {f: getattr(profile, f) for f in self._GENERAL_FIELDS}
        data['logo_url'] = request.build_absolute_uri(profile.logo.url) if profile.logo else None
        return Response(data)

    def patch(self, request):
        profile = SchoolProfile.objects.filter(is_active=True).first()
        if not profile:
            profile = SchoolProfile.objects.create(school_name='School', is_active=True)
        for field in self._GENERAL_FIELDS:
            if field in request.data:
                setattr(profile, field, request.data[field])
        profile.save(update_fields=self._GENERAL_FIELDS + ['updated_at'])
        return Response({'detail': 'General settings updated.'})


# ─────────────────────────────────────────────────────────────────────────────
# BULK REPORT CARD PRINT  (GET /api/academics/report-cards/bulk-print/)
# ─────────────────────────────────────────────────────────────────────────────
class BulkReportCardPrintView(APIView):
    """
    Bulk-print all report cards for a class/term as a single printable HTML page.

    GET without params  → selection form (class + term dropdowns)
    GET ?class_id=X&term_id=Y[&status=Approved][&academic_year_id=Z]
        → printable HTML; one student per page-break section
    """
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "ACADEMICS"

    # CBE grade-band colours
    _BAND_COLOUR = {"EE": "#166534", "ME": "#1e40af", "AE": "#92400e", "BE": "#991b1b"}
    _GRADE_MAP = {
        "A": "EE", "A+": "EE", "A-": "EE",
        "B+": "ME", "B": "ME", "B-": "ME",
        "C+": "AE", "C": "AE", "C-": "AE",
        "D+": "BE", "D": "BE", "D-": "BE", "E": "BE",
    }

    def get(self, request):
        class_id = request.query_params.get("class_id", "").strip()
        term_id  = request.query_params.get("term_id", "").strip()
        status_f = request.query_params.get("status", "").strip()

        if not class_id or not term_id:
            return HttpResponse(self._form_html(request), content_type="text/html")
        return HttpResponse(
            self._print_html(request, int(class_id), int(term_id), status_f),
            content_type="text/html",
        )

    # ── selection form ────────────────────────────────────────────────────────
    def _form_html(self, request):
        from academics.models import SchoolClass as _SC, Term as _Term
        classes = _SC.objects.all().order_by("name")
        terms   = _Term.objects.select_related("academic_year").order_by("-id")
        cls_opts = "\n".join(
            f"<option value='{c.id}'>{getattr(c, 'display_name', c.name)}</option>"
            for c in classes
        )
        term_opts = "\n".join(
            f"<option value='{t.id}'>{t.name} &bull; {t.academic_year.name}</option>"
            for t in terms
        )
        base = request.build_absolute_uri(request.path)
        return f"""<!doctype html><html lang='en'><head>
<meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Bulk Report Card Print — RynatySchool SmartCampus</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:Arial,sans-serif;background:#f1f5f9;min-height:100vh;display:flex;align-items:center;justify-content:center}}
  .card{{background:#fff;border-radius:12px;box-shadow:0 4px 24px rgba(0,0,0,.10);padding:40px;max-width:480px;width:100%}}
  .logo{{color:#10b981;font-size:22px;font-weight:bold;margin-bottom:4px}}
  .subtitle{{color:#64748b;font-size:13px;margin-bottom:28px}}
  h2{{font-size:18px;font-weight:700;color:#1e293b;margin-bottom:20px}}
  label{{display:block;font-size:12px;font-weight:600;color:#475569;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px;margin-top:16px}}
  select{{width:100%;padding:10px 12px;border:1px solid #cbd5e1;border-radius:8px;font-size:14px;color:#1e293b;background:#f8fafc;appearance:none}}
  select:focus{{outline:none;border-color:#10b981;box-shadow:0 0 0 2px rgba(16,185,129,.2)}}
  .btn{{display:block;width:100%;margin-top:28px;padding:12px;background:#10b981;color:#fff;border:none;border-radius:8px;font-size:15px;font-weight:600;cursor:pointer;text-align:center;text-decoration:none}}
  .btn:hover{{background:#059669}}
  .tip{{margin-top:16px;font-size:12px;color:#94a3b8;text-align:center}}
</style></head>
<body><div class='card'>
  <div class='logo'>RynatySchool SmartCampus</div>
  <div class='subtitle'>Competency-Based Education (CBE) System</div>
  <h2>Bulk Report Card Print</h2>
  <form method='GET' action='{base}'>
    <label for='cls'>Class / Stream</label>
    <select id='cls' name='class_id' required>
      <option value='' disabled selected>— Select class —</option>
      {cls_opts}
    </select>
    <label for='trm'>Term</label>
    <select id='trm' name='term_id' required>
      <option value='' disabled selected>— Select term —</option>
      {term_opts}
    </select>
    <label for='sts'>Filter by Status (optional)</label>
    <select id='sts' name='status'>
      <option value=''>All Statuses</option>
      <option value='Draft'>Draft</option>
      <option value='Submitted'>Submitted</option>
      <option value='Approved'>Approved</option>
      <option value='Published'>Published</option>
      <option value='Distributed'>Distributed</option>
    </select>
    <button type='submit' class='btn'>Generate Printable Report Cards</button>
  </form>
  <p class='tip'>Each student's report card will appear on a separate printed page.</p>
</div></body></html>"""

    # ── bulk print page ───────────────────────────────────────────────────────
    def _print_html(self, request, class_id: int, term_id: int, status_f: str) -> str:
        from school.models import (
            ReportCard, TermResult, SchoolProfile, SchoolClass,
            Student, AttendanceRecord,
        )
        from academics.models import Term as _Term

        cls  = SchoolClass.objects.filter(id=class_id).first()
        term = _Term.objects.select_related("academic_year").filter(id=term_id).first()
        if not cls or not term:
            return "<h2 style='padding:40px'>Invalid class or term selected.</h2>"

        profile     = SchoolProfile.objects.filter(is_active=True).first()
        school_name = getattr(profile, "school_name", "RynatySchool SmartCampus")
        school_phone = getattr(profile, "phone", "+254 700 000 000")
        school_email = getattr(profile, "email_address", "info@rynatyschool.app")
        cls_name    = getattr(cls, "display_name", None) or cls.name
        term_name   = term.name
        year_name   = term.academic_year.name if term.academic_year else "—"
        generated   = timezone.now().strftime("%d %b %Y %H:%M")

        qs = ReportCard.objects.filter(
            class_section_id=class_id, term_id=term_id, is_active=True,
        ).select_related("student")
        if status_f:
            qs = qs.filter(status=status_f)
        cards = list(qs.order_by("class_rank", "student__last_name", "student__first_name"))

        if not cards:
            return f"""<div style='font-family:Arial;padding:60px;text-align:center'>
              <h2>No report cards found</h2>
              <p style='color:#666;margin-top:12px'>
                Class: <b>{cls_name}</b> &bull; Term: <b>{term_name}</b>
                {f' &bull; Status: <b>{status_f}</b>' if status_f else ''}
              </p>
              <a href='javascript:history.back()' style='color:#10b981'>← Back to selection</a>
            </div>"""

        # Pre-fetch all TermResults for this class+term in one query
        all_results = TermResult.objects.filter(
            class_section_id=class_id, term_id=term_id, is_active=True,
        ).select_related("subject", "grade_band").order_by("subject__name")
        results_map: dict[int, list] = {}
        for r in all_results:
            results_map.setdefault(r.student_id, []).append(r)

        # Pre-fetch attendance counts
        att_qs = AttendanceRecord.objects.filter(
            student__in=[c.student_id for c in cards],
        ).values("student_id", "status")
        att_map: dict[int, dict] = {}
        for row in att_qs:
            sid = row["student_id"]
            att_map.setdefault(sid, {"Present": 0, "Absent": 0, "Late": 0})
            att_map[sid][row["status"]] = att_map[sid].get(row["status"], 0) + 1

        cards_html = ""
        for i, card in enumerate(cards):
            student  = card.student
            name     = f"{student.first_name} {student.last_name}"
            adm      = student.admission_number
            grade_lv = cls_name
            rank_txt = f"{card.class_rank}" if card.class_rank else "—"
            total_stu = len(cards)
            att      = att_map.get(student.id, {})
            days_p   = card.attendance_days or att.get("Present", 0)
            days_a   = att.get("Absent", 0)
            days_l   = att.get("Late", 0)
            remarks_t  = card.teacher_remarks or "—"
            remarks_p  = card.principal_remarks or "—"

            raw_grade  = card.overall_grade or ""
            cbe_grade  = self._GRADE_MAP.get(raw_grade, raw_grade) or "—"
            g_colour   = self._BAND_COLOUR.get(cbe_grade, "#475569")
            g_desc = {"EE": "Exceeding Expectations", "ME": "Meeting Expectations",
                      "AE": "Approaching Expectations", "BE": "Below Expectations"}.get(cbe_grade, "")

            # Subject rows from TermResult
            rows = results_map.get(student.id, [])
            subj_rows = ""
            for r in rows:
                band = r.grade_band.label if r.grade_band else self._GRADE_MAP.get(str(r.total_score), "AE")
                bcolour = self._BAND_COLOUR.get(band, "#475569")
                score   = float(r.total_score)
                remark  = r.grade_band.remark if r.grade_band else ""
                subj_rows += (
                    f"<tr>"
                    f"<td>{r.subject.name}</td>"
                    f"<td style='text-align:center'>{score:.1f}</td>"
                    f"<td style='text-align:center'>"
                    f"  <span style='background:{bcolour};color:#fff;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:bold'>{band}</span>"
                    f"</td>"
                    f"<td style='color:#64748b;font-size:12px'>{remark}</td>"
                    f"</tr>"
                )
            if not subj_rows:
                subj_rows = "<tr><td colspan='4' style='text-align:center;color:#888;padding:20px'>No subject results recorded for this term.</td></tr>"

            is_last = (i == len(cards) - 1)
            page_cls = "" if is_last else " page-break"

            cards_html += f"""
<section class='report-page{page_cls}'>
  <div class='rc-header'>
    <div>
      <div class='rc-school'>{school_name}</div>
      <div class='rc-contact'>{school_phone} &bull; {school_email}</div>
      <div class='rc-title'>STUDENT ACADEMIC REPORT CARD</div>
      <div class='rc-period'>{year_name} &bull; {term_name}</div>
    </div>
    <div class='rc-badge' style='border-color:{g_colour};color:{g_colour}'>{cbe_grade}</div>
  </div>

  <div class='info-grid'>
    <div class='ib'><span class='il'>Student Name</span><strong>{name}</strong></div>
    <div class='ib'><span class='il'>Admission No.</span><strong>{adm}</strong></div>
    <div class='ib'><span class='il'>Class</span><strong>{cls_name}</strong></div>
    <div class='ib'><span class='il'>Class Rank</span><strong>{rank_txt} of {total_stu}</strong></div>
    <div class='ib'><span class='il'>Days Present</span><strong>{days_p}</strong></div>
    <div class='ib'><span class='il'>Days Absent</span><strong>{days_a}</strong></div>
  </div>

  <table>
    <thead>
      <tr>
        <th>Subject</th>
        <th style='text-align:center;width:90px'>Score</th>
        <th style='text-align:center;width:90px'>CBE Band</th>
        <th>Competency Remark</th>
      </tr>
    </thead>
    <tbody>{subj_rows}</tbody>
  </table>

  <div class='summary-row'>
    <div class='summary-box'>
      <div class='sum-label'>Overall CBE Performance</div>
      <div class='sum-grade' style='color:{g_colour}'>{cbe_grade}</div>
      <div class='sum-desc'>{g_desc}</div>
    </div>
    <div class='remarks-grid'>
      <div class='remark-box'>
        <div class='remark-label'>Class Teacher's Remarks</div>
        <div class='remark-text'>{remarks_t}</div>
        <div class='sig-line'>Signature: _________________</div>
      </div>
      <div class='remark-box'>
        <div class='remark-label'>Principal's Remarks</div>
        <div class='remark-text'>{remarks_p}</div>
        <div class='sig-line'>Signature: _________________</div>
      </div>
    </div>
  </div>

  <div class='rc-footer'>
    {school_name} &bull; Generated {generated} &bull; rynatyschool.app
    &bull; Student {i + 1} of {len(cards)}
  </div>
</section>"""

        back_url = request.build_absolute_uri(request.path)
        status_badge = f" &bull; Status: <b>{status_f}</b>" if status_f else ""
        return f"""<!doctype html><html lang='en'><head>
<meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Report Cards — {cls_name} {term_name}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:Arial,sans-serif;background:#f1f5f9;color:#1e293b}}

  /* ─── print controls (hidden when printing) ─── */
  .print-bar{{background:#1e293b;color:#fff;padding:12px 24px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}}
  .print-bar h1{{font-size:15px;font-weight:600}}
  .print-bar .meta{{font-size:12px;color:#94a3b8;margin-top:2px}}
  .print-actions{{display:flex;gap:10px}}
  .btn-print{{background:#10b981;color:#fff;border:none;padding:9px 20px;border-radius:6px;font-size:13px;font-weight:600;cursor:pointer}}
  .btn-back{{background:transparent;color:#94a3b8;border:1px solid #475569;padding:9px 16px;border-radius:6px;font-size:13px;cursor:pointer;text-decoration:none}}

  /* ─── report page ─── */
  .report-page{{background:#fff;max-width:760px;margin:20px auto;padding:32px;border-radius:8px;box-shadow:0 2px 12px rgba(0,0,0,.08)}}
  .page-break{{page-break-after:always}}

  /* ─── header ─── */
  .rc-header{{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:3px solid #10b981;padding-bottom:16px;margin-bottom:20px}}
  .rc-school{{font-size:20px;font-weight:bold;color:#10b981}}
  .rc-contact{{font-size:12px;color:#64748b;margin-top:3px}}
  .rc-title{{font-size:16px;font-weight:bold;margin-top:8px;color:#1e293b}}
  .rc-period{{font-size:13px;color:#64748b;margin-top:2px}}
  .rc-badge{{border:3px solid;border-radius:50%;width:64px;height:64px;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:900;flex-shrink:0}}

  /* ─── info grid ─── */
  .info-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:20px}}
  .ib{{background:#f8fafc;border-radius:6px;padding:10px 12px}}
  .il{{display:block;font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px}}
  .ib strong{{font-size:13px;color:#1e293b}}

  /* ─── subject table ─── */
  table{{width:100%;border-collapse:collapse;margin-bottom:20px}}
  th{{background:#10b981;color:#fff;padding:10px 12px;text-align:left;font-size:13px}}
  td{{padding:9px 12px;border-bottom:1px solid #f1f5f9;font-size:13px}}
  tr:last-child td{{border-bottom:none}}

  /* ─── summary ─── */
  .summary-row{{display:flex;gap:16px;margin-bottom:20px}}
  .summary-box{{background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:16px 20px;min-width:140px;text-align:center;flex-shrink:0}}
  .sum-label{{font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.05em}}
  .sum-grade{{font-size:42px;font-weight:900;margin:4px 0}}
  .sum-desc{{font-size:11px;font-weight:600}}
  .remarks-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;flex:1}}
  .remark-box{{background:#f8fafc;border-radius:6px;padding:12px}}
  .remark-label{{font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px;font-weight:600}}
  .remark-text{{font-size:13px;color:#1e293b;min-height:40px;margin-bottom:8px}}
  .sig-line{{font-size:11px;color:#94a3b8;border-top:1px solid #e2e8f0;padding-top:6px}}

  /* ─── footer ─── */
  .rc-footer{{text-align:center;font-size:11px;color:#94a3b8;border-top:1px solid #e2e8f0;padding-top:12px;margin-top:8px}}

  /* ─── print media ─── */
  @media print{{
    body{{background:#fff}}
    .print-bar{{display:none!important}}
    .report-page{{margin:0;padding:20px;box-shadow:none;border-radius:0;max-width:none}}
    .page-break{{page-break-after:always!important}}
  }}
</style></head>
<body>
<div class='print-bar no-print'>
  <div>
    <div class='meta'>
      {cls_name} &bull; {term_name} &bull; {year_name}{status_badge}
      &bull; <b>{len(cards)}</b> student{'s' if len(cards) != 1 else ''}
    </div>
  </div>
  <div class='print-actions'>
    <a href='{back_url}' class='btn-back'>&#8592; Change Selection</a>
    <button class='btn-print' onclick='window.print()'>&#128438; Print / Save PDF</button>
  </div>
</div>
{cards_html}
</body></html>"""
