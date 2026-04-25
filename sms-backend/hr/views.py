from html import escape
from datetime import datetime, timedelta
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.db.models import Avg, Count, Q, Sum
from django.http import FileResponse, HttpResponse
from django.utils import timezone
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from school.permissions import HasModuleAccess, IsSchoolAdmin, request_has_module_access
from school.models import Department as SchoolDepartment
from school.role_scope import iter_seed_role_names, normalize_role_name
from .events import staff_created, staff_updated, staff_deactivated
from .identity import (
    ensure_employment_profile,
    generate_employee_id,
    generate_staff_id,
    infer_staff_category,
    normalize_staff_category,
    seed_default_onboarding_tasks,
    suggest_account_role_name,
)
from .domain.attendance_operations import (
    auto_resolve_alert_for_attendance,
    escalate_alert,
    evaluate_absence_alert,
    manually_resolve_alert,
    refresh_record_for_clock_in,
    refresh_record_for_manual_update,
)
from .domain.career_operations import (
    CareerWorkflowError,
    apply_career_action,
    complete_transfer,
    end_acting_appointment,
    sync_career_action_assignment_fields,
    sync_transfer_assignment_fields,
)
from .domain.discipline_operations import (
    DisciplineWorkflowError,
    close_disciplinary_case,
    create_disciplinary_case,
)
from .domain.exit_operations import (
    ExitWorkflowError,
    archive_employee,
    complete_exit_case,
    create_compatibility_exit_case,
    create_exit_case,
    start_exit_clearance,
    sync_exit_clearance_item_completion_fields,
)
from .domain.leave_operations import (
    cancel_leave,
    complete_return_reconciliation,
    final_approve_leave,
    initialize_leave_request_state,
    manager_approve_leave,
    reject_leave,
    reopen_return_reconciliation,
)
from .domain.lifecycle_events import append_transfer_requested_event
from .domain.payroll_feed import build_workforce_feed
from .domain.payroll_operations import (
    PROCESS_LOCKED_STATUSES,
    PayrollWorkflowError,
    build_payroll_exception_summary,
    finance_approve_payroll,
    mark_payroll_disbursed,
    rebuild_payroll_batch,
    start_payroll_disbursement,
)
from .domain.payroll_posting import build_payroll_posting_summary, post_payroll_to_finance
from .onboarding import compute_onboarding_summary, sync_onboarding_status
from .models import (
    AbsenceAlert,
    AttendanceRecord,
    Department,
    Employee,
    EmployeeEmploymentProfile,
    EmployeeDocument,
    EmployeeQualification,
    EmergencyContact,
    ShiftTemplate,
    TeachingSubstituteAssignment,
    Position,
    Staff,
    WorkSchedule,
    LeaveType,
    LeavePolicy,
    LeaveBalance,
    LeaveRequest,
    ReturnToWorkReconciliation,
    SalaryStructure,
    SalaryComponent,
    StatutoryDeductionBand,
    StatutoryDeductionRule,
    PayrollBatch,
    PayrollDisbursement,
    PayrollItem,
    JobPosting,
    JobApplication,
    Interview,
    OnboardingTask,
    PerformanceGoal,
    PerformanceReview,
    TrainingProgram,
    TrainingEnrollment,
    StaffLifecycleEvent,
    StaffCareerAction,
    DisciplinaryCase,
    ExitCase,
    ExitClearanceItem,
    StaffTransfer,
)
from .provisioning import link_employee_biometric, provision_employee_account
from .serializers import (
    AttendanceRecordSerializer,
    AbsenceAlertEscalateSerializer,
    AbsenceAlertEvaluateSerializer,
    AbsenceAlertResolveSerializer,
    AbsenceAlertSerializer,
    BiometricLinkSerializer,
    DepartmentSerializer,
    EmployeeDocumentSerializer,
    EmployeeEmploymentProfileSerializer,
    EmployeeArchiveSerializer,
    EmployeeQualificationSerializer,
    EmployeeSerializer,
    EmergencyContactSerializer,
    PositionSerializer,
    ShiftTemplateSerializer,
    StaffSerializer,
    TeachingSubstituteAssignmentSerializer,
    WorkScheduleSerializer,
    LeaveTypeSerializer,
    LeavePolicySerializer,
    LeaveBalanceSerializer,
    LeaveRequestSerializer,
    LeaveRejectSerializer,
    SalaryStructureSerializer,
    SalaryComponentSerializer,
    StatutoryDeductionBandSerializer,
    StatutoryDeductionRuleSerializer,
    PayrollBatchSerializer,
    PayrollDisbursementSerializer,
    PayrollItemSerializer,
    JobPostingSerializer,
    JobApplicationSerializer,
    InterviewSerializer,
    OnboardingTaskSerializer,
    PerformanceGoalSerializer,
    PerformanceReviewSerializer,
    ProvisionAccountSerializer,
    ReturnToWorkCompleteSerializer,
    ReturnToWorkReconciliationSerializer,
    ReturnToWorkReopenSerializer,
    TrainingProgramSerializer,
    TrainingEnrollmentSerializer,
    StaffLifecycleEventSerializer,
    StaffCareerActionEndActingSerializer,
    StaffCareerActionSerializer,
    DisciplinaryCaseCloseSerializer,
    DisciplinaryCaseSerializer,
    ExitCaseSerializer,
    ExitClearanceItemSerializer,
    StaffTransferSerializer,
)

import logging

logger = logging.getLogger(__name__)

SUPPORTED_ROLE_NAMES = set(iter_seed_role_names())


class HrModuleAccessMixin:
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "HR"
    action_module_keys = {}

    def get_module_keys(self):
        return self.action_module_keys.get(getattr(self, "action", None), self.module_key)


class StaffRefView(HrModuleAccessMixin, APIView):
    def get(self, request):
        data = Staff.objects.values(
            "id", "employee_id", "first_name", "last_name", "role", "phone", "is_active"
        ).order_by("employee_id")
        return Response(list(data), status=status.HTTP_200_OK)


class StaffViewSet(viewsets.ModelViewSet):
    queryset = Staff.objects.filter(is_active=True)
    serializer_class = StaffSerializer
    permission_classes = [IsSchoolAdmin, HasModuleAccess]
    module_key = "HR"

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()
        staff_deactivated.send(sender=StaffViewSet, staff_id=instance.id, employee_id=instance.employee_id)

    def perform_create(self, serializer):
        staff = serializer.save()
        staff_created.send(sender=StaffViewSet, staff_id=staff.id, employee_id=staff.employee_id)

    def perform_update(self, serializer):
        staff = serializer.save()
        staff_updated.send(sender=StaffViewSet, staff_id=staff.id, employee_id=staff.employee_id)


def _generate_employee_id() -> str:
    return generate_employee_id()


def _generate_staff_id() -> str:
    return generate_staff_id()


def _refresh_onboarding_summary(employee: Employee) -> dict:
    summary = compute_onboarding_summary(employee)
    sync_onboarding_status(employee, summary=summary)
    return compute_onboarding_summary(employee)


def _ensure_department_shadow(department: Department) -> SchoolDepartment:
    school_department = department.school_department
    head_user = department.head.user if department.head and department.head.user_id else None
    target_name = (department.name or "").strip() or department.code

    if school_department is None:
        school_department = (
            SchoolDepartment.objects.filter(name__iexact=target_name, hr_department_profile__isnull=True).first()
            if target_name
            else None
        )
        if school_department is None:
            school_department = SchoolDepartment.objects.create(
                name=target_name,
                description=department.description or "",
                head=head_user,
                is_active=department.is_active,
            )

    update_fields = []
    if target_name and school_department.name != target_name:
        collision = SchoolDepartment.objects.filter(name__iexact=target_name).exclude(pk=school_department.pk).exists()
        if not collision:
            school_department.name = target_name
            update_fields.append("name")
    if school_department.description != (department.description or ""):
        school_department.description = department.description or ""
        update_fields.append("description")
    if school_department.head_id != (head_user.id if head_user else None):
        school_department.head = head_user
        update_fields.append("head")
    if school_department.is_active != department.is_active:
        school_department.is_active = department.is_active
        update_fields.append("is_active")
    if update_fields:
        school_department.save(update_fields=update_fields)

    if department.school_department_id != school_department.id:
        department.school_department = school_department
        department.save(update_fields=["school_department"])

    return school_department


class EmployeeViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = Employee.objects.all().order_by("employee_id", "first_name", "last_name")
    serializer_class = EmployeeSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        include_archived = str(self.request.query_params.get("include_archived", "")).lower() in {"1", "true", "yes"}
        archived_only = str(self.request.query_params.get("archived", "")).lower() in {"1", "true", "yes"}
        department = self.request.query_params.get("department")
        status_value = self.request.query_params.get("status")
        employment_type = self.request.query_params.get("employment_type")
        if archived_only:
            queryset = queryset.filter(status="Archived")
        elif include_archived:
            queryset = queryset.filter(Q(is_active=True) | Q(status="Archived"))
        else:
            queryset = queryset.filter(is_active=True).exclude(status="Archived")
        if department:
            queryset = queryset.filter(department_id=department)
        if status_value:
            queryset = queryset.filter(status=status_value)
        if employment_type:
            queryset = queryset.filter(employment_type=employment_type)
        return queryset

    def perform_create(self, serializer):
        position = serializer.validated_data.get("position")
        explicit_category = serializer.validated_data.get("staff_category", "")
        staff_category = infer_staff_category(getattr(position, "title", ""), explicit_category)
        account_role_name = serializer.validated_data.get("account_role_name", "") or suggest_account_role_name(
            getattr(position, "title", ""),
            staff_category,
        )
        with transaction.atomic():
            employee = serializer.save(
                employee_id=_generate_employee_id(),
                staff_id=_generate_staff_id(),
                staff_category=staff_category,
                onboarding_status="PENDING",
                account_role_name=account_role_name,
            )
            ensure_employment_profile(employee)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])

    def perform_update(self, serializer):
        position = serializer.validated_data.get("position", serializer.instance.position)
        explicit_category = (
            serializer.validated_data.get("staff_category")
            if "staff_category" in serializer.validated_data
            else serializer.instance.staff_category
        )
        staff_category = infer_staff_category(getattr(position, "title", ""), explicit_category)
        if "account_role_name" in serializer.validated_data:
            account_role_name = serializer.validated_data.get("account_role_name", "")
        else:
            account_role_name = serializer.instance.account_role_name or suggest_account_role_name(
                getattr(position, "title", ""),
                staff_category,
            )
        employee = serializer.save(
            staff_category=staff_category,
            account_role_name=account_role_name,
        )
        _refresh_onboarding_summary(employee)

    @action(detail=True, methods=["get"], url_path="onboarding-summary")
    def onboarding_summary(self, request, pk=None):
        employee = self.get_object()
        return Response(_refresh_onboarding_summary(employee), status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="link-biometric")
    def link_biometric(self, request, pk=None):
        employee = self.get_object()
        serializer = BiometricLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        registry = link_employee_biometric(employee, **serializer.validated_data)
        summary = _refresh_onboarding_summary(employee)
        return Response(
            {
                "message": "Biometric identity linked successfully.",
                "registry_id": registry.id,
                "summary": summary,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="provision-account")
    def provision_account(self, request, pk=None):
        employee = self.get_object()
        serializer = ProvisionAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = provision_employee_account(
            employee,
            role_name=serializer.validated_data.get("role_name"),
            username=serializer.validated_data.get("username"),
            assigned_by=request.user,
            send_welcome_email=serializer.validated_data.get("send_welcome_email", True),
        )
        summary = _refresh_onboarding_summary(employee)
        return Response(
            {
                "message": "Staff account provisioned successfully.",
                "user_id": result["user"].id,
                "username": result["username"],
                "role_name": result["role_name"],
                "temporary_password": result["temporary_password"],
                "module_baseline": result["module_baseline"],
                "welcome_email": result["welcome_email"],
                "summary": summary,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="employment")
    def employment(self, request, pk=None):
        employee = self.get_object()
        data = {
            "employee_id": employee.employee_id,
            "staff_id": employee.staff_id,
            "staff_category": employee.staff_category,
            "employment_type": employee.employment_type,
            "status": employee.status,
            "onboarding_status": employee.onboarding_status,
            "account_role_name": employee.account_role_name,
            "department": employee.department.name if employee.department else "",
            "position": employee.position.title if employee.position else "",
            "join_date": employee.join_date,
            "probation_end": employee.probation_end,
            "confirmation_date": employee.confirmation_date,
            "contract_start": employee.contract_start,
            "contract_end": employee.contract_end,
            "reporting_to": f"{employee.reporting_to.first_name} {employee.reporting_to.last_name}".strip()
            if employee.reporting_to
            else "",
            "work_location": employee.work_location,
            "notice_period_days": employee.notice_period_days,
        }
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, pk=None):
        employee = self.get_object()
        employee.confirmation_date = request.data.get("confirmation_date") or timezone.now().date()
        employee.status = "Active"
        employee.save(update_fields=["confirmation_date", "status"])
        return Response({"message": "Employee probation confirmed."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="exit")
    def exit(self, request, pk=None):
        employee = self.get_object()
        try:
            with transaction.atomic():
                exit_case = create_compatibility_exit_case(
                    employee,
                    exit_date=request.data.get("exit_date") or timezone.now().date(),
                    exit_reason=request.data.get("exit_reason", "Resignation"),
                    exit_notes=request.data.get("exit_notes", ""),
                    recorded_by=request.user if request.user.is_authenticated else None,
                )
        except ExitWorkflowError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "message": "Employee exit processed.",
                "exit_case_id": exit_case.id,
                "exit_case_status": exit_case.status,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="archive")
    def archive(self, request, pk=None):
        employee = Employee.objects.select_related("user").filter(pk=pk).first()
        if employee is None:
            return Response({"error": "Employee not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = EmployeeArchiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                employee = archive_employee(
                    employee,
                    archive_reason=serializer.validated_data.get("archive_reason", ""),
                    recorded_by=request.user if request.user.is_authenticated else None,
                )
        except ExitWorkflowError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(employee).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="timeline")
    def timeline(self, request, pk=None):
        employee = (
            Employee.objects.filter(Q(is_active=True) | Q(status="Archived"))
            .select_related("department", "position")
            .filter(pk=pk)
            .first()
        )
        if employee is None:
            return Response({"error": "Employee not found."}, status=status.HTTP_404_NOT_FOUND)
        queryset = employee.lifecycle_events.select_related("recorded_by").order_by("-effective_date", "-occurred_at", "-id")
        serializer = StaffLifecycleEventSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class EmergencyContactViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = EmergencyContact.objects.filter(is_active=True).order_by("-is_primary", "name")
    serializer_class = EmergencyContactSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        employee = self.request.query_params.get("employee")
        if employee:
            queryset = queryset.filter(employee_id=employee)
        return queryset

    def perform_create(self, serializer):
        contact = serializer.save()
        if contact.is_primary:
            EmergencyContact.objects.filter(employee=contact.employee, is_active=True).exclude(pk=contact.pk).update(
                is_primary=False
            )
        _refresh_onboarding_summary(contact.employee)

    def perform_update(self, serializer):
        contact = serializer.save()
        if contact.is_primary:
            EmergencyContact.objects.filter(employee=contact.employee, is_active=True).exclude(pk=contact.pk).update(
                is_primary=False
            )
        _refresh_onboarding_summary(contact.employee)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        _refresh_onboarding_summary(instance.employee)


class EmployeeEmploymentProfileViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = EmployeeEmploymentProfile.objects.select_related("employee").order_by("employee__employee_id", "id")
    serializer_class = EmployeeEmploymentProfileSerializer
    http_method_names = ["get", "post", "patch", "put", "head", "options"]

    def get_queryset(self):
        queryset = super().get_queryset()
        employee = self.request.query_params.get("employee")
        if employee:
            queryset = queryset.filter(employee_id=employee)
        return queryset

    def create(self, request, *args, **kwargs):
        employee_id = request.data.get("employee")
        existing = None
        if employee_id not in (None, ""):
            existing = EmployeeEmploymentProfile.objects.filter(employee_id=employee_id).first()
        if existing is not None:
            update_serializer = self.get_serializer(existing, data=request.data, partial=True)
            update_serializer.is_valid(raise_exception=True)
            profile = update_serializer.save()
            _refresh_onboarding_summary(profile.employee)
            return Response(update_serializer.data, status=status.HTTP_200_OK)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        profile = serializer.save()
        _refresh_onboarding_summary(profile.employee)

    def perform_update(self, serializer):
        profile = serializer.save()
        _refresh_onboarding_summary(profile.employee)


class EmployeeQualificationViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = EmployeeQualification.objects.filter(is_active=True).select_related("employee").order_by(
        "-is_primary",
        "-year_obtained",
        "-id",
    )
    serializer_class = EmployeeQualificationSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        employee = self.request.query_params.get("employee")
        if employee:
            queryset = queryset.filter(employee_id=employee)
        return queryset

    def perform_create(self, serializer):
        qualification = serializer.save()
        if qualification.is_primary:
            EmployeeQualification.objects.filter(employee=qualification.employee, is_active=True).exclude(
                pk=qualification.pk
            ).update(is_primary=False)
        _refresh_onboarding_summary(qualification.employee)

    def perform_update(self, serializer):
        qualification = serializer.save()
        if qualification.is_primary:
            EmployeeQualification.objects.filter(employee=qualification.employee, is_active=True).exclude(
                pk=qualification.pk
            ).update(is_primary=False)
        _refresh_onboarding_summary(qualification.employee)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        _refresh_onboarding_summary(instance.employee)


class EmployeeDocumentViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = EmployeeDocument.objects.filter(is_active=True).order_by("-uploaded_at")
    serializer_class = EmployeeDocumentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        employee = self.request.query_params.get("employee")
        document_type = self.request.query_params.get("document_type")
        if employee:
            queryset = queryset.filter(employee_id=employee)
        if document_type:
            queryset = queryset.filter(document_type=document_type)
        return queryset

    def perform_create(self, serializer):
        file_obj = serializer.validated_data.get("file")
        file_name = file_obj.name if file_obj else ""
        serializer.save(uploaded_by=self.request.user, file_name=file_name)

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        document = self.get_object()
        if not document.file:
            return Response({"error": "No file attached."}, status=status.HTTP_404_NOT_FOUND)
        return FileResponse(document.file.open("rb"), as_attachment=True, filename=document.file_name or document.file.name)

    @action(detail=False, methods=["get"], url_path="expiring")
    def expiring(self, request):
        try:
            days = int(request.query_params.get("days", 30))
        except (TypeError, ValueError):
            return Response({"error": "days must be an integer."}, status=status.HTTP_400_BAD_REQUEST)
        threshold = timezone.now().date() + timedelta(days=days)
        queryset = self.get_queryset().filter(expiry_date__isnull=False, expiry_date__lte=threshold)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class DepartmentViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = Department.objects.filter(is_active=True).select_related("parent", "head", "school_department").order_by("name")
    serializer_class = DepartmentSerializer

    def perform_create(self, serializer):
        department = serializer.save()
        _ensure_department_shadow(department)

    def perform_update(self, serializer):
        department = serializer.save()
        _ensure_department_shadow(department)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        if instance.school_department_id and instance.school_department.is_active:
            instance.school_department.is_active = False
            instance.school_department.save(update_fields=["is_active"])

    @action(detail=True, methods=["get"], url_path="employees")
    def employees(self, request, pk=None):
        department = self.get_object()
        queryset = Employee.objects.filter(department=department, is_active=True).order_by("employee_id", "first_name")
        serializer = EmployeeSerializer(queryset, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="org-chart")
    def org_chart(self, request):
        departments = Department.objects.filter(is_active=True).select_related("head", "parent", "school_department").order_by("name")
        data = []
        for department in departments:
            data.append(
                {
                    "id": department.id,
                    "name": department.name,
                    "code": department.code,
                    "parent_id": department.parent_id,
                    "head": (
                        f"{department.head.first_name} {department.head.last_name}".strip()
                        if department.head
                        else ""
                    ),
                    "employee_count": Employee.objects.filter(department=department, is_active=True).count(),
                }
            )
        return Response(data, status=status.HTTP_200_OK)


class PositionViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = Position.objects.filter(is_active=True).order_by("title")
    serializer_class = PositionSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        department = self.request.query_params.get("department")
        if department:
            queryset = queryset.filter(department_id=department)
        return queryset

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])

    @action(detail=True, methods=["get"], url_path="vacancies")
    def vacancies(self, request, pk=None):
        position = self.get_object()
        filled = Employee.objects.filter(position=position, is_active=True, status__in=["Active", "On Leave"]).count()
        vacancies = max(position.headcount - filled, 0)
        return Response(
            {"position_id": position.id, "headcount": position.headcount, "filled": filled, "vacancies": vacancies},
            status=status.HTTP_200_OK,
        )


def _compute_hours(clock_in, clock_out) -> Decimal:
    if not clock_in or not clock_out:
        return Decimal("0.00")
    start_dt = datetime.combine(timezone.now().date(), clock_in)
    end_dt = datetime.combine(timezone.now().date(), clock_out)
    if end_dt <= start_dt:
        return Decimal("0.00")
    minutes = int((end_dt - start_dt).total_seconds() // 60)
    return round(Decimal(minutes) / Decimal("60.00"), 2)


def _coerce_date(value):
    if hasattr(value, "year"):
        return value
    if isinstance(value, str):
        return datetime.strptime(value, "%Y-%m-%d").date()
    return timezone.now().date()


def _coerce_time(value):
    if hasattr(value, "hour"):
        return value
    if isinstance(value, str):
        return datetime.strptime(value, "%H:%M:%S").time()
    return timezone.now().time().replace(microsecond=0)


def _coerce_datetime(value):
    if hasattr(value, "hour") and hasattr(value, "date"):
        dt = value
    elif isinstance(value, str):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        return timezone.now()
    if timezone.is_aware(dt):
        return dt.replace(tzinfo=None) if not settings.USE_TZ else dt
    return timezone.make_aware(dt, timezone.get_current_timezone()) if settings.USE_TZ else dt


def _save_attendance_rollup(record, *, attendance_source=None):
    refresh_record_for_manual_update(record, attendance_source=attendance_source or record.attendance_source or "MANUAL")
    record.hours_worked = _compute_hours(record.clock_in, record.clock_out)
    overtime = max(record.hours_worked - Decimal("8.00"), Decimal("0.00"))
    if record.shift_template_id and not record.shift_template.overtime_eligible:
        overtime = Decimal("0.00")
    record.overtime_hours = round(overtime, 2)
    record.save(
        update_fields=[
            "shift_template",
            "scheduled_shift_start",
            "scheduled_shift_end",
            "expected_check_in_deadline",
            "attendance_source",
            "payroll_feed_status",
            "hours_worked",
            "overtime_hours",
        ]
    )
    if record.clock_in:
        auto_resolve_alert_for_attendance(record)
    return record


def _calculate_leave_days(start_date, end_date) -> Decimal:
    if end_date < start_date:
        return Decimal("0.00")
    return Decimal((end_date - start_date).days + 1)


def _resolve_request_employee(request):
    if not request.user.is_authenticated:
        return None
    return Employee.objects.filter(user=request.user, is_active=True).first()


def _resolve_policy_entitlement(leave_type, employment_type, today):
    specific = (
        LeavePolicy.objects.filter(
            leave_type=leave_type,
            is_active=True,
            effective_from__lte=today,
            employment_type=employment_type,
        )
        .order_by("-effective_from")
        .first()
    )
    if specific:
        return specific.entitlement_days

    fallback = (
        LeavePolicy.objects.filter(
            leave_type=leave_type,
            is_active=True,
            effective_from__lte=today,
            employment_type="",
        )
        .order_by("-effective_from")
        .first()
    )
    if fallback:
        return fallback.entitlement_days

    return Decimal("0.00")


def _get_or_create_leave_balance(employee, leave_type, year):
    balance, created = LeaveBalance.objects.get_or_create(
        employee=employee,
        leave_type=leave_type,
        year=year,
        defaults={
            "opening_balance": Decimal("0.00"),
            "accrued": Decimal("0.00"),
            "used": Decimal("0.00"),
            "pending": Decimal("0.00"),
            "available": Decimal("0.00"),
            "is_active": True,
        },
    )
    if created:
        balance.accrued = _resolve_policy_entitlement(leave_type, employee.employment_type, timezone.now().date())
    return balance


def _recompute_leave_available(balance):
    balance.available = (balance.opening_balance + balance.accrued) - (balance.used + balance.pending)


def _round_money(value):
    return Decimal(value).quantize(Decimal("0.01"))


def _refresh_prefetched_instance(instance):
    if hasattr(instance, "_prefetched_objects_cache"):
        instance._prefetched_objects_cache = {}
    instance.refresh_from_db()
    return instance


def _component_amount(component, basic_salary):
    if component.amount_type == "Percentage":
        return _round_money((basic_salary * component.amount) / Decimal("100.00"))
    return _round_money(component.amount)


def _days_in_month(year, month):
    if month == 12:
        next_month = datetime(year + 1, 1, 1).date()
    else:
        next_month = datetime(year, month + 1, 1).date()
    return (next_month - datetime(year, month, 1).date()).days


class ShiftTemplateViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = ShiftTemplate.objects.filter(is_active=True).order_by("name", "id")
    serializer_class = ShiftTemplateSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        staff_category = self.request.query_params.get("staff_category")
        department = self.request.query_params.get("department")
        position = self.request.query_params.get("position")
        if staff_category:
            queryset = queryset.filter(staff_category=staff_category)
        if department:
            queryset = queryset.filter(department_id=department)
        if position:
            queryset = queryset.filter(position_id=position)
        return queryset

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class AttendanceViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = AttendanceRecord.objects.filter(is_active=True).order_by("-date", "-id")
    serializer_class = AttendanceRecordSerializer

    def get_queryset(self):
        queryset = super().get_queryset().select_related("employee", "employee__department", "shift_template", "recorded_by")
        employee = self.request.query_params.get("employee")
        department = self.request.query_params.get("department")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if employee:
            queryset = queryset.filter(employee_id=employee)
        if department:
            queryset = queryset.filter(employee__department_id=department)
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        return queryset

    def perform_create(self, serializer):
        record = serializer.save(recorded_by=self.request.user, attendance_source="MANUAL")
        _save_attendance_rollup(record, attendance_source="MANUAL")

    @action(detail=False, methods=["post"], url_path="clock-in")
    def clock_in(self, request):
        employee_id = request.data.get("employee")
        if not employee_id:
            return Response({"error": "employee is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            today = _coerce_date(request.data.get("date") or timezone.now().date())
            now_time = _coerce_time(request.data.get("clock_in") or timezone.now().time().replace(microsecond=0))
        except ValueError:
            return Response(
                {"error": "Invalid date/time format. Use YYYY-MM-DD and HH:MM:SS."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        obj, _ = AttendanceRecord.objects.get_or_create(
            employee_id=employee_id,
            date=today,
            defaults={
                "clock_in": now_time,
                "status": "Present",
                "recorded_by": request.user,
                "attendance_source": "MANUAL",
                "is_active": True,
            },
        )
        if not obj.clock_in or obj.clock_in != now_time:
            obj.clock_in = now_time
        refresh_record_for_clock_in(
            obj,
            clock_in_time=now_time,
            attendance_source="MANUAL",
            recorded_by=request.user,
        )
        _save_attendance_rollup(obj, attendance_source="MANUAL")
        serializer = self.get_serializer(obj)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="clock-out")
    def clock_out(self, request):
        employee_id = request.data.get("employee")
        if not employee_id:
            return Response({"error": "employee is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            today = _coerce_date(request.data.get("date") or timezone.now().date())
            now_time = _coerce_time(request.data.get("clock_out") or timezone.now().time().replace(microsecond=0))
        except ValueError:
            return Response(
                {"error": "Invalid date/time format. Use YYYY-MM-DD and HH:MM:SS."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            record = AttendanceRecord.objects.get(employee_id=employee_id, date=today, is_active=True)
        except AttendanceRecord.DoesNotExist:
            return Response({"error": "No clock-in record found for employee/date."}, status=status.HTTP_404_NOT_FOUND)
        record.clock_out = now_time
        record.save(update_fields=["clock_out"])
        _save_attendance_rollup(record, attendance_source=record.attendance_source or "MANUAL")
        serializer = self.get_serializer(record)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="bulk")
    def bulk(self, request):
        rows = request.data.get("records", [])
        if not isinstance(rows, list) or not rows:
            return Response({"error": "records[] is required."}, status=status.HTTP_400_BAD_REQUEST)
        created = 0
        updated = 0
        for row in rows:
            employee_id = row.get("employee")
            date_value = row.get("date")
            if not employee_id or not date_value:
                continue
            defaults = {
                "clock_in": row.get("clock_in"),
                "clock_out": row.get("clock_out"),
                "status": row.get("status", "Present"),
                "notes": row.get("notes", ""),
                "recorded_by": request.user,
                "attendance_source": "BULK",
                "is_active": True,
            }
            obj, is_created = AttendanceRecord.objects.update_or_create(
                employee_id=employee_id,
                date=date_value,
                defaults=defaults,
            )
            _save_attendance_rollup(obj, attendance_source="BULK")
            if is_created:
                created += 1
            else:
                updated += 1
        return Response({"message": "Bulk attendance saved.", "created": created, "updated": updated}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        month = int(request.query_params.get("month", timezone.now().month))
        year = int(request.query_params.get("year", timezone.now().year))
        queryset = self.get_queryset().filter(date__year=year, date__month=month)
        total = queryset.count()
        present = queryset.filter(status="Present").count()
        late = queryset.filter(status="Late").count()
        absent = queryset.filter(status="Absent").count()
        overtime = queryset.aggregate(v=Avg("overtime_hours"))["v"] or Decimal("0.00")
        return Response(
            {
                "month": month,
                "year": year,
                "total_records": total,
                "present_count": present,
                "late_count": late,
                "absent_count": absent,
                "average_overtime_hours": round(Decimal(overtime), 2),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="report")
    def report(self, request):
        queryset = self.get_queryset()
        grouped = (
            queryset.values("employee_id", "employee__employee_id", "employee__first_name", "employee__last_name")
            .annotate(
                days=Count("id"),
                present=Count("id", filter=Q(status="Present")),
                absent=Count("id", filter=Q(status="Absent")),
                late=Count("id", filter=Q(status="Late")),
                avg_hours=Avg("hours_worked"),
            )
            .order_by("employee__employee_id")
        )
        data = []
        for row in grouped:
            data.append(
                {
                    "employee_id": row["employee__employee_id"],
                    "employee_name": f'{row["employee__first_name"]} {row["employee__last_name"]}'.strip(),
                    "days": row["days"],
                    "present": row["present"],
                    "absent": row["absent"],
                    "late": row["late"],
                    "average_hours": round(Decimal(row["avg_hours"] or 0), 2),
                }
            )
        return Response(data, status=status.HTTP_200_OK)


class AbsenceAlertViewSet(HrModuleAccessMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = AbsenceAlert.objects.filter(is_active=True).order_by("-alert_date", "-created_at", "-id")
    serializer_class = AbsenceAlertSerializer

    def get_queryset(self):
        queryset = super().get_queryset().select_related("employee", "shift_template", "notified_manager", "resolved_by")
        employee = self.request.query_params.get("employee")
        status_value = self.request.query_params.get("status")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if employee:
            queryset = queryset.filter(employee_id=employee)
        if status_value:
            queryset = queryset.filter(status=status_value)
        if date_from:
            queryset = queryset.filter(alert_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(alert_date__lte=date_to)
        return queryset

    @action(detail=False, methods=["post"], url_path="evaluate")
    def evaluate(self, request):
        serializer = AbsenceAlertEvaluateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee = Employee.objects.filter(pk=serializer.validated_data["employee"], is_active=True).first()
        if employee is None:
            return Response({"error": "Employee not found."}, status=status.HTTP_404_NOT_FOUND)

        triggered_at = serializer.validated_data.get("triggered_at")
        if request.data.get("triggered_at"):
            triggered_at = _coerce_datetime(request.data.get("triggered_at"))

        result = evaluate_absence_alert(
            employee,
            serializer.validated_data["date"],
            triggered_at=triggered_at,
        )

        payload = {
            "created": result["created"],
            "reason": result["reason"],
            "attendance_record": AttendanceRecordSerializer(result["record"]).data,
            "alert": self.get_serializer(result["alert"]).data if result["alert"] else None,
        }
        response_status = status.HTTP_201_CREATED if result["created"] else status.HTTP_200_OK
        return Response(payload, status=response_status)

    @action(detail=True, methods=["post"], url_path="resolve")
    def resolve(self, request, pk=None):
        alert = self.get_object()
        serializer = AbsenceAlertResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        manually_resolve_alert(
            alert,
            resolved_by=request.user,
            reason=serializer.validated_data.get("resolution_reason", ""),
            notes=serializer.validated_data.get("notes", ""),
            attendance_status=serializer.validated_data.get("attendance_status"),
        )
        alert.refresh_from_db()
        return Response(self.get_serializer(alert).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="escalate")
    def escalate(self, request, pk=None):
        alert = self.get_object()
        serializer = AbsenceAlertEscalateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        escalate_alert(alert, notes=serializer.validated_data.get("notes", ""))
        alert.refresh_from_db()
        return Response(self.get_serializer(alert).data, status=status.HTTP_200_OK)


class TeachingSubstituteAssignmentViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = TeachingSubstituteAssignment.objects.filter(is_active=True).order_by("-assignment_date", "-created_at", "-id")
    serializer_class = TeachingSubstituteAssignmentSerializer

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            "absent_employee",
            "substitute_employee",
            "attendance_record",
            "assigned_by",
        )
        absent_employee = self.request.query_params.get("absent_employee")
        substitute_employee = self.request.query_params.get("substitute_employee")
        assignment_date = self.request.query_params.get("assignment_date")
        if absent_employee:
            queryset = queryset.filter(absent_employee_id=absent_employee)
        if substitute_employee:
            queryset = queryset.filter(substitute_employee_id=substitute_employee)
        if assignment_date:
            queryset = queryset.filter(assignment_date=assignment_date)
        return queryset

    def perform_create(self, serializer):
        serializer.save(assigned_by=self.request.user)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class WorkScheduleViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = WorkSchedule.objects.filter(is_active=True).order_by("-effective_from", "-id")
    serializer_class = WorkScheduleSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        employee = self.request.query_params.get("employee")
        department = self.request.query_params.get("department")
        if employee:
            queryset = queryset.filter(employee_id=employee)
        if department:
            queryset = queryset.filter(department_id=department)
        return queryset

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class LeaveTypeViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = LeaveType.objects.filter(is_active=True).order_by("name")
    serializer_class = LeaveTypeSerializer

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class LeavePolicyViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = LeavePolicy.objects.filter(is_active=True).order_by("leave_type__name", "employment_type", "-effective_from")
    serializer_class = LeavePolicySerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        leave_type = self.request.query_params.get("leave_type")
        if leave_type:
            queryset = queryset.filter(leave_type_id=leave_type)
        return queryset

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class LeaveBalanceView(HrModuleAccessMixin, APIView):
    def get(self, request, employee_id):
        year = request.query_params.get("year")
        queryset = LeaveBalance.objects.filter(employee_id=employee_id, is_active=True)
        if year:
            queryset = queryset.filter(year=year)
        serializer = LeaveBalanceSerializer(queryset.order_by("-year", "leave_type__name"), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LeaveRequestViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = LeaveRequest.objects.filter(is_active=True).order_by("-submitted_at", "-id")
    serializer_class = LeaveRequestSerializer
    action_module_keys = {
        "approve": ("HR", "ACADEMICS"),
        "manager_approve": ("HR", "ACADEMICS"),
    }

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            "employee",
            "employee__department",
            "leave_type",
            "current_approver",
            "approved_by",
            "manager_approved_by",
            "hr_approved_by",
            "return_reconciliation",
        )
        status_value = self.request.query_params.get("status")
        employee = self.request.query_params.get("employee")
        leave_type = self.request.query_params.get("leave_type")
        if status_value:
            queryset = queryset.filter(status=status_value)
        if employee:
            queryset = queryset.filter(employee_id=employee)
        if leave_type:
            queryset = queryset.filter(leave_type_id=leave_type)
        return queryset

    def perform_create(self, serializer):
        start_date = _coerce_date(serializer.validated_data["start_date"])
        end_date = _coerce_date(serializer.validated_data["end_date"])
        days_requested = _calculate_leave_days(start_date, end_date)
        leave_type = serializer.validated_data["leave_type"]
        employee = serializer.validated_data["employee"]

        leave_request = serializer.save(days_requested=days_requested, status="Pending")
        initialize_leave_request_state(leave_request)
        leave_request.save(
            update_fields=[
                "long_leave_threshold_days_snapshot",
                "requires_dual_approval",
                "return_reconciliation_required",
                "approval_stage",
                "current_approver",
            ]
        )
        balance = _get_or_create_leave_balance(employee, leave_type, start_date.year)
        balance.pending += days_requested
        _recompute_leave_available(balance)
        balance.save(update_fields=["accrued", "pending", "available", "updated_at"])

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        leave_request = self.get_object()
        if leave_request.status != "Pending":
            return Response({"error": "Only pending requests can be approved."}, status=status.HTTP_400_BAD_REQUEST)

        approver_employee = _resolve_request_employee(request)
        try:
            if leave_request.requires_dual_approval and leave_request.approval_stage == "PENDING_MANAGER":
                manager_approve_leave(leave_request, approver_employee=approver_employee)
                leave_request.refresh_from_db()
                return Response(
                    {
                        "message": "Manager approval recorded. Leave request is now pending HR final approval.",
                        "leave_request": self.get_serializer(leave_request).data,
                    },
                    status=status.HTTP_200_OK,
                )

            if not request_has_module_access(request, "HR"):
                return Response(
                    {"detail": "HR module access is required for final leave approval."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            final_approve_leave(leave_request, approver_employee=approver_employee)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        leave_request.refresh_from_db()
        return Response(
            {"message": "Leave request approved.", "leave_request": self.get_serializer(leave_request).data},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="manager-approve")
    def manager_approve(self, request, pk=None):
        leave_request = self.get_object()
        approver_employee = _resolve_request_employee(request)
        try:
            manager_approve_leave(leave_request, approver_employee=approver_employee)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        leave_request.refresh_from_db()
        return Response(self.get_serializer(leave_request).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="hr-final-approve")
    def hr_final_approve(self, request, pk=None):
        leave_request = self.get_object()
        approver_employee = _resolve_request_employee(request)
        try:
            final_approve_leave(leave_request, approver_employee=approver_employee)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        leave_request.refresh_from_db()
        return Response(self.get_serializer(leave_request).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        leave_request = self.get_object()
        payload = request.data.copy()
        if not payload.get("rejection_reason") and payload.get("reason"):
            payload["rejection_reason"] = payload["reason"]
        serializer = LeaveRejectSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        try:
            reject_leave(leave_request, reason=serializer.validated_data["rejection_reason"])
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"message": "Leave request rejected."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        leave_request = self.get_object()
        try:
            cancel_leave(leave_request)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"message": "Leave request cancelled."}, status=status.HTTP_200_OK)

    def perform_destroy(self, instance):
        if instance.status == "Pending":
            cancel_leave(instance)
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class ReturnToWorkReconciliationViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = ReturnToWorkReconciliation.objects.filter(is_active=True).order_by("-expected_return_date", "-updated_at", "-id")
    serializer_class = ReturnToWorkReconciliationSerializer

    def get_queryset(self):
        queryset = super().get_queryset().select_related("employee", "leave_request", "attendance_record", "completed_by")
        employee = self.request.query_params.get("employee")
        leave_request = self.request.query_params.get("leave_request")
        status_value = self.request.query_params.get("status")
        if employee:
            queryset = queryset.filter(employee_id=employee)
        if leave_request:
            queryset = queryset.filter(leave_request_id=leave_request)
        if status_value:
            queryset = queryset.filter(status=status_value)
        return queryset

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        reconciliation = self.get_object()
        serializer = ReturnToWorkCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        attendance_record = None
        attendance_record_id = serializer.validated_data.get("attendance_record")
        if attendance_record_id:
            attendance_record = AttendanceRecord.objects.filter(
                pk=attendance_record_id,
                employee=reconciliation.employee,
                is_active=True,
            ).first()
            if attendance_record is None:
                return Response({"error": "Attendance record not found for employee."}, status=status.HTTP_400_BAD_REQUEST)

        complete_return_reconciliation(
            reconciliation,
            completed_by=request.user,
            actual_return_date=serializer.validated_data["actual_return_date"],
            attendance_record=attendance_record,
            extension_required=serializer.validated_data.get("extension_required", False),
            attendance_correction_required=serializer.validated_data.get("attendance_correction_required", False),
            payroll_hold_required=serializer.validated_data.get("payroll_hold_required", False),
            substitute_closed=serializer.validated_data.get("substitute_closed", False),
            notes=serializer.validated_data.get("notes", ""),
        )
        reconciliation.refresh_from_db()
        return Response(self.get_serializer(reconciliation).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reopen")
    def reopen(self, request, pk=None):
        reconciliation = self.get_object()
        serializer = ReturnToWorkReopenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reopen_return_reconciliation(reconciliation, notes=serializer.validated_data.get("notes", ""))
        reconciliation.refresh_from_db()
        return Response(self.get_serializer(reconciliation).data, status=status.HTTP_200_OK)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class LeaveCalendarView(HrModuleAccessMixin, APIView):
    def get(self, request):
        queryset = LeaveRequest.objects.filter(is_active=True).exclude(status="Cancelled")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        department = request.query_params.get("department")

        if start_date:
            queryset = queryset.filter(end_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(start_date__lte=end_date)
        if department:
            queryset = queryset.filter(employee__department_id=department)

        data = [
            {
                "id": row.id,
                "employee_id": row.employee_id,
                "employee_name": f"{row.employee.first_name} {row.employee.last_name}".strip(),
                "department": row.employee.department.name if row.employee.department else "",
                "leave_type": row.leave_type.name,
                "start_date": row.start_date,
                "end_date": row.end_date,
                "days_requested": row.days_requested,
                "status": row.status,
            }
            for row in queryset.order_by("-start_date", "-id")
        ]
        return Response(data, status=status.HTTP_200_OK)


class SalaryStructureViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = SalaryStructure.objects.filter(is_active=True).order_by("-effective_from", "-id")
    serializer_class = SalaryStructureSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        employee = self.request.query_params.get("employee")
        if employee:
            queryset = queryset.filter(employee_id=employee)
        return queryset

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class SalaryComponentViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = SalaryComponent.objects.filter(is_active=True).order_by("name", "id")
    serializer_class = SalaryComponentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        structure = self.request.query_params.get("structure")
        if structure:
            queryset = queryset.filter(structure_id=structure)
        return queryset

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class StatutoryDeductionRuleViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = StatutoryDeductionRule.objects.prefetch_related("bands").order_by("priority", "code", "-effective_from", "id")
    serializer_class = StatutoryDeductionRuleSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        code = self.request.query_params.get("code")
        include_inactive = self.request.query_params.get("include_inactive")
        if not include_inactive:
            queryset = queryset.filter(is_active=True)
        if code:
            queryset = queryset.filter(code=code)
        return queryset

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class StatutoryDeductionBandViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = StatutoryDeductionBand.objects.select_related("rule").order_by("rule__priority", "rule__code", "display_order", "id")
    serializer_class = StatutoryDeductionBandSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        rule = self.request.query_params.get("rule")
        include_inactive = self.request.query_params.get("include_inactive")
        if not include_inactive:
            queryset = queryset.filter(is_active=True, rule__is_active=True)
        if rule:
            queryset = queryset.filter(rule_id=rule)
        return queryset

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class PayrollBatchViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = PayrollBatch.objects.filter(is_active=True).prefetch_related(
        "disbursements",
        "finance_postings",
        "items__breakdown_rows",
    ).order_by("-year", "-month", "-id")
    serializer_class = PayrollBatchSerializer
    action_module_keys = {
        "list": ("HR", "FINANCE"),
        "retrieve": ("HR", "FINANCE"),
        "exceptions": ("HR", "FINANCE"),
        "finance_approve": ("HR", "FINANCE"),
        "approve": ("HR", "FINANCE"),
        "disbursement_records": ("HR", "FINANCE"),
        "start_disbursement": ("HR", "FINANCE"),
        "mark_disbursed": ("HR", "FINANCE"),
        "posting_summary": ("HR", "FINANCE"),
        "post_to_finance": ("HR", "FINANCE"),
        "bank_file": ("HR", "FINANCE"),
        "tax_report": ("HR", "FINANCE"),
    }

    def _workflow_error_response(self, exc: PayrollWorkflowError):
        payload = {"error": exc.message}
        payload.update(exc.details)
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    def get_queryset(self):
        queryset = super().get_queryset()
        month = self.request.query_params.get("month")
        year = self.request.query_params.get("year")
        if month:
            queryset = queryset.filter(month=month)
        if year:
            queryset = queryset.filter(year=year)
        return queryset

    @action(detail=False, methods=["get"], url_path="workforce-feed")
    def workforce_feed(self, request):
        try:
            month = int(request.query_params.get("month", timezone.now().month))
            year = int(request.query_params.get("year", timezone.now().year))
        except ValueError:
            return Response({"error": "month and year must be integers."}, status=status.HTTP_400_BAD_REQUEST)

        employee = request.query_params.get("employee")
        payload = build_workforce_feed(month, year, employee_id=employee)
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="process")
    def process(self, request):
        month = int(request.data.get("month", timezone.now().month))
        year = int(request.data.get("year", timezone.now().year))
        payment_date_value = request.data.get("payment_date")

        payroll, _ = PayrollBatch.objects.get_or_create(
            month=month,
            year=year,
            defaults={"status": "Draft", "is_active": True},
        )
        if payroll.status in PROCESS_LOCKED_STATUSES:
            return Response(
                {"error": "Finalized payroll cannot be processed again from this endpoint."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        payroll = rebuild_payroll_batch(
            payroll,
            processed_by=request.user,
            payment_date=_coerce_date(payment_date_value) if payment_date_value else None,
        )
        serializer = self.get_serializer(payroll)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="exceptions")
    def exceptions(self, request, pk=None):
        payroll = self.get_object()
        return Response(build_payroll_exception_summary(payroll), status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="finance-approve")
    def finance_approve(self, request, pk=None):
        payroll = self.get_object()
        try:
            payroll = finance_approve_payroll(
                payroll,
                approved_by=request.user,
                approval_notes=request.data.get("approval_notes", ""),
            )
        except PayrollWorkflowError as exc:
            return self._workflow_error_response(exc)

        payroll = _refresh_prefetched_instance(payroll)
        payload = dict(self.get_serializer(payroll).data)
        payload["message"] = "Payroll finance approved."
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        payroll = self.get_object()
        try:
            payroll = finance_approve_payroll(
                payroll,
                approved_by=request.user,
                approval_notes=request.data.get("approval_notes", ""),
                legacy_status=True,
            )
        except PayrollWorkflowError as exc:
            return self._workflow_error_response(exc)
        return Response({"message": "Payroll approved.", "status": payroll.status}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reprocess")
    def reprocess(self, request, pk=None):
        payroll = self.get_object()
        if payroll.status in PROCESS_LOCKED_STATUSES:
            return Response({"error": "Finalized payroll cannot be reprocessed."}, status=status.HTTP_400_BAD_REQUEST)
        payment_date_value = request.data.get("payment_date")
        payroll = rebuild_payroll_batch(
            payroll,
            processed_by=request.user,
            payment_date=_coerce_date(payment_date_value) if payment_date_value else None,
        )
        serializer = self.get_serializer(payroll)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="disbursements")
    def disbursement_records(self, request, pk=None):
        payroll = self.get_object()
        queryset = PayrollDisbursement.objects.filter(payroll=payroll).order_by("-created_at", "-id")
        serializer = PayrollDisbursementSerializer(queryset, many=True)
        return Response({"count": queryset.count(), "results": serializer.data}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="start-disbursement")
    def start_disbursement(self, request, pk=None):
        payroll = self.get_object()
        method = (request.data.get("method") or "BANK").strip().upper()
        if method not in {"BANK", "CASH", "MOBILE", "MIXED"}:
            return Response(
                {"error": "method must be one of BANK, CASH, MOBILE, or MIXED."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            scheduled_date = (
                _coerce_date(request.data.get("scheduled_date"))
                if request.data.get("scheduled_date")
                else None
            )
            payroll, _ = start_payroll_disbursement(
                payroll,
                method=method,
                scheduled_date=scheduled_date,
                reference=request.data.get("reference", ""),
                notes=request.data.get("notes", ""),
            )
        except ValueError:
            return Response({"error": "scheduled_date must use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        except PayrollWorkflowError as exc:
            return self._workflow_error_response(exc)

        payroll = _refresh_prefetched_instance(payroll)
        payload = dict(self.get_serializer(payroll).data)
        payload["message"] = "Payroll disbursement started."
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="mark-disbursed")
    def mark_disbursed(self, request, pk=None):
        payroll = self.get_object()
        try:
            disbursed_at = (
                _coerce_datetime(request.data.get("disbursed_at"))
                if request.data.get("disbursed_at")
                else None
            )
            payroll, _ = mark_payroll_disbursed(
                payroll,
                disbursed_by=request.user,
                disbursed_at=disbursed_at,
                reference=request.data.get("reference", ""),
                notes=request.data.get("notes", ""),
            )
        except ValueError:
            return Response(
                {"error": "disbursed_at must be an ISO-8601 datetime or YYYY-MM-DD value."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except PayrollWorkflowError as exc:
            return self._workflow_error_response(exc)

        payroll = _refresh_prefetched_instance(payroll)
        payload = dict(self.get_serializer(payroll).data)
        payload["message"] = "Payroll marked as disbursed."
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="posting-summary")
    def posting_summary(self, request, pk=None):
        payroll = self.get_object()
        return Response(build_payroll_posting_summary(payroll), status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="post-to-finance")
    def post_to_finance(self, request, pk=None):
        payroll = self.get_object()
        try:
            entry_date = _coerce_date(request.data.get("entry_date")) if request.data.get("entry_date") else None
            payroll = post_payroll_to_finance(
                payroll,
                posted_by=request.user,
                entry_date=entry_date,
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PayrollWorkflowError as exc:
            return self._workflow_error_response(exc)

        payroll = _refresh_prefetched_instance(payroll)
        payload = dict(self.get_serializer(payroll).data)
        payload["posting_summary"] = build_payroll_posting_summary(payroll)
        payload["message"] = "Payroll posted to finance."
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="bank-file")
    def bank_file(self, request, pk=None):
        payroll = self.get_object()
        lines = ["employee_id,employee_name,net_salary"]
        for item in payroll.items.select_related("employee").all():
            employee_name = f"{item.employee.first_name} {item.employee.last_name}".strip()
            lines.append(f"{item.employee.employee_id},{employee_name},{item.net_salary}")
        response = HttpResponse("\n".join(lines), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="payroll_bank_file_{payroll.year}_{payroll.month:02d}.csv"'
        return response

    @action(detail=False, methods=["get"], url_path="tax-report")
    def tax_report(self, request):
        month = int(request.query_params.get("month", timezone.now().month))
        year = int(request.query_params.get("year", timezone.now().year))
        payroll = PayrollBatch.objects.filter(month=month, year=year, is_active=True).first()
        if not payroll:
            return Response({"error": "Payroll batch not found for period."}, status=status.HTTP_404_NOT_FOUND)

        lines = [
            "employee_id,employee_name,gross_salary,total_deductions,net_payable,estimated_tax,statutory_deductions,employer_statutory"
        ]
        for item in payroll.items.select_related("employee").prefetch_related("breakdown_rows").all():
            employee_name = f"{item.employee.first_name} {item.employee.last_name}".strip()
            estimated_tax = Decimal("0.00")
            statutory_total = Decimal("0.00")
            employer_total = Decimal("0.00")
            for row in item.breakdown_rows.all():
                if row.line_type == "STATUTORY_EMPLOYER":
                    employer_total += row.amount
                    continue
                if row.line_type == "STATUTORY_EMPLOYEE":
                    statutory_total += row.amount
                    if row.code == "PAYE":
                        estimated_tax += row.amount
            lines.append(
                (
                    f"{item.employee.employee_id},"
                    f"{employee_name},"
                    f"{item.gross_salary},"
                    f"{item.total_deductions},"
                    f"{item.net_payable},"
                    f"{estimated_tax},"
                    f"{statutory_total},"
                    f"{employer_total}"
                )
            )
        response = HttpResponse("\n".join(lines), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="payroll_tax_report_{year}_{month:02d}.csv"'
        return response


class PayrollItemViewSet(HrModuleAccessMixin, viewsets.ReadOnlyModelViewSet):
    queryset = PayrollItem.objects.filter(is_active=True).select_related(
        "employee",
        "employee__department",
        "employee__position",
        "payroll",
    ).prefetch_related("breakdown_rows").order_by("employee__employee_id", "id")
    serializer_class = PayrollItemSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        employee = self.request.query_params.get("employee")
        payroll = self.request.query_params.get("payroll")
        if employee:
            queryset = queryset.filter(employee_id=employee)
        if payroll:
            queryset = queryset.filter(payroll_id=payroll)
        return queryset

    @action(detail=True, methods=["get"], url_path="pdf")
    def pdf(self, request, pk=None):
        item = self.get_object()
        if item.pdf_file:
            return FileResponse(item.pdf_file.open("rb"), as_attachment=True, filename=item.pdf_file.name.split("/")[-1])
        emp = item.employee
        emp_name = f"{emp.first_name} {emp.last_name}".strip()
        dept = emp.department.name if emp.department else "-"
        pos = emp.position.title if emp.position else "-"
        currency = item.calculation_snapshot.get("salary_structure", {}).get("currency", "KES")
        breakdown_rows = list(item.breakdown_rows.all())
        earnings_rows = [row for row in breakdown_rows if row.line_type == "ALLOWANCE"]
        deduction_rows = [
            row for row in breakdown_rows
            if row.line_type in {"ATTENDANCE_DEDUCTION", "STATUTORY_EMPLOYEE", "OTHER_DEDUCTION"}
        ]
        employer_rows = [row for row in breakdown_rows if row.line_type == "STATUTORY_EMPLOYER"]

        def render_rows(rows, *, include_category=False, empty_label="No rows recorded"):
            if not rows:
                colspan = 4 if include_category else 3
                return f'<tr><td colspan="{colspan}" style="color:#888">{escape(empty_label)}</td></tr>'
            html_rows = []
            for row in rows:
                category_cell = f"<td>{escape(row.get_line_type_display())}</td>" if include_category else ""
                html_rows.append(
                    "<tr>"
                    f"<td>{escape(row.name)}</td>"
                    f"{category_cell}"
                    f"<td>{escape(str(row.base_amount))}</td>"
                    f"<td>{escape(str(row.amount))}</td>"
                    "</tr>"
                )
            return "".join(html_rows)

        content = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Payslip - {escape(emp_name)}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:Arial,sans-serif;font-size:12px;color:#111;padding:24px;max-width:800px;margin:0 auto}}
h1{{color:#047857;font-size:18px;margin-bottom:4px}}
.subtitle{{color:#555;font-size:11px;margin-bottom:16px}}
table{{width:100%;border-collapse:collapse;margin-bottom:16px}}
th{{background:#f0fdf4;padding:6px 8px;text-align:left;font-size:10px;text-transform:uppercase;color:#047857;border-bottom:2px solid #bbf7d0}}
td{{padding:6px 8px;border-bottom:1px solid #e5e7eb}}
td:last-child,th:last-child{{text-align:right}}
.net{{border:2px solid #047857;border-radius:6px;padding:12px;display:flex;justify-content:space-between;font-size:14px;font-weight:700;color:#047857;margin-bottom:20px}}
@media print{{@page{{size:A4;margin:2cm}}}}
</style></head><body>
<h1>Payslip - {escape(emp.employee_id)}</h1>
<div class="subtitle">Period: {item.payroll.month:02d}/{item.payroll.year} | Payment: {escape(str(item.payroll.payment_date or "-"))}</div>
<table><tr><th>Employee</th><th>Department</th><th>Position</th></tr>
<tr><td>{escape(emp_name)}</td><td>{escape(dept)}</td><td>{escape(pos)}</td></tr></table>
<table><tr><th>Earnings</th><th>Base</th><th>Amount ({escape(currency)})</th></tr>
<tr><td>Basic Salary</td><td>{escape(str(item.basic_salary))}</td><td>{escape(str(item.basic_salary))}</td></tr>
{render_rows(earnings_rows, empty_label="No additional earnings recorded")}
<tr style="font-weight:600"><td>Gross Salary</td><td></td><td>{escape(str(item.gross_salary))}</td></tr></table>
<table><tr><th>Deductions</th><th>Category</th><th>Base</th><th>Amount ({escape(currency)})</th></tr>
{render_rows(deduction_rows, include_category=True, empty_label="No deductions recorded")}
<tr style="font-weight:600"><td>Total Deductions</td><td></td><td></td><td>{escape(str(item.total_deductions))}</td></tr></table>
<table><tr><th>Employer Contributions</th><th>Base</th><th>Amount ({escape(currency)})</th></tr>
{render_rows(employer_rows, empty_label="No employer statutory contributions")}
<tr style="font-weight:600"><td>Total Employer Statutory</td><td></td><td>{escape(str(item.employer_statutory_total))}</td></tr></table>
<div class="net"><span>NET PAY</span><span>{escape(currency)} {escape(str(item.net_payable or item.net_salary))}</span></div>
<p style="font-size:10px;color:#888">Generated by Rynaty School Management System - Rynatyspace Technologies</p>
<script>window.onload=function(){{window.print()}}</script>
</body></html>"""
        response = HttpResponse(content, content_type="text/html; charset=utf-8")
        response["Content-Disposition"] = f'inline; filename="payslip_{item.payroll.year}_{item.payroll.month:02d}_{emp.employee_id}.html"'
        return response
        emp = item.employee
        emp_name = f"{emp.first_name} {emp.last_name}"
        dept = emp.department.name if emp.department else "—"
        pos = emp.position.title if emp.position else "—"
        currency = item.calculation_snapshot.get("salary_structure", {}).get("currency", "KES")
        breakdown_rows = list(item.breakdown_rows.all())
        earnings_rows = [row for row in breakdown_rows if row.line_type == "ALLOWANCE"]
        deduction_rows = [
            row for row in breakdown_rows
            if row.line_type in {"ATTENDANCE_DEDUCTION", "STATUTORY_EMPLOYEE", "OTHER_DEDUCTION"}
        ]
        employer_rows = [row for row in breakdown_rows if row.line_type == "STATUTORY_EMPLOYER"]

        def render_rows(rows, *, include_category=False, empty_label="No rows recorded"):
            if not rows:
                colspan = 4 if include_category else 3
                return f'<tr><td colspan="{colspan}" style="color:#888">{escape(empty_label)}</td></tr>'
            html_rows = []
            for row in rows:
                category_cell = f"<td>{escape(row.get_line_type_display())}</td>" if include_category else ""
                html_rows.append(
                    "<tr>"
                    f"<td>{escape(row.name)}</td>"
                    f"{category_cell}"
                    f"<td>{escape(str(row.base_amount))}</td>"
                    f"<td>{escape(str(row.amount))}</td>"
                    "</tr>"
                )
            return "".join(html_rows)

        content = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Payslip — {escape(emp_name)}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:Arial,sans-serif;font-size:12px;color:#111;padding:24px;max-width:800px;margin:0 auto}}
h1{{color:#047857;font-size:18px;margin-bottom:4px}}
.subtitle{{color:#555;font-size:11px;margin-bottom:16px}}
table{{width:100%;border-collapse:collapse;margin-bottom:16px}}
th{{background:#f0fdf4;padding:6px 8px;text-align:left;font-size:10px;text-transform:uppercase;color:#047857;border-bottom:2px solid #bbf7d0}}
td{{padding:6px 8px;border-bottom:1px solid #e5e7eb}}
td:last-child,th:last-child{{text-align:right}}
.net{{border:2px solid #047857;border-radius:6px;padding:12px;display:flex;justify-content:space-between;font-size:14px;font-weight:700;color:#047857;margin-bottom:20px}}
@media print{{@page{{size:A4;margin:2cm}}}}
</style></head><body>
<h1>Payslip — {escape(emp.employee_id)}</h1>
<div class="subtitle">Period: {item.payroll.month:02d}/{item.payroll.year} | Payment: {escape(str(item.payroll.payment_date or "—"))}</div>
<table><tr><th>Employee</th><th>Department</th><th>Position</th></tr>
<tr><td>{escape(emp_name)}</td><td>{escape(dept)}</td><td>{escape(pos)}</td></tr></table>
<table><tr><th>Earnings</th><th>Base</th><th>Amount ({escape(currency)})</th></tr>
<tr><td>Basic Salary</td><td>{escape(str(item.basic_salary))}</td><td>{escape(str(item.basic_salary))}</td></tr>
{render_rows(earnings_rows)}
<tr style="font-weight:600"><td>Gross Salary</td><td></td><td>{escape(str(item.gross_salary))}</td></tr></table>
<table><tr><th>Deductions</th><th>Category</th><th>Base</th><th>Amount ({escape(currency)})</th></tr>
{render_rows(deduction_rows, include_category=True, empty_label="No deductions recorded")}
<tr style="font-weight:600"><td>Total Deductions</td><td></td><td></td><td>{escape(str(item.total_deductions))}</td></tr></table>
<table><tr><th>Employer Contributions</th><th>Base</th><th>Amount ({escape(currency)})</th></tr>
{render_rows(employer_rows, empty_label="No employer statutory contributions")}
<tr style="font-weight:600"><td>Total Employer Statutory</td><td></td><td>{escape(str(item.employer_statutory_total))}</td></tr></table>
<div class="net"><span>NET PAY</span><span>{escape(currency)} {escape(str(item.net_payable or item.net_salary))}</span></div>
<p style="font-size:10px;color:#888">Generated by Rynaty School Management System — Rynatyspace Technologies</p>
<script>window.onload=function(){{window.print()}}</script>
</body></html>"""
        response = HttpResponse(content, content_type="text/html; charset=utf-8")
        response["Content-Disposition"] = f'inline; filename="payslip_{item.payroll.year}_{item.payroll.month:02d}_{emp.employee_id}.html"'
        return response
        emp = item.employee
        emp_name = f"{emp.first_name} {emp.last_name}"
        dept = emp.department.name if emp.department else "—"
        pos = emp.position.title if emp.position else "—"
        currency = "KES"
        try:
            struct = emp.salary_structures.filter(is_active=True).order_by("-effective_from").first()
            if struct:
                currency = struct.currency
        except Exception:
            logger.warning("Caught and logged", exc_info=True)
        content = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Payslip — {emp_name}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:Arial,sans-serif;font-size:12px;color:#111;padding:24px;max-width:800px;margin:0 auto}}
h1{{color:#047857;font-size:18px;margin-bottom:4px}}
.subtitle{{color:#555;font-size:11px;margin-bottom:16px}}
table{{width:100%;border-collapse:collapse;margin-bottom:16px}}
th{{background:#f0fdf4;padding:6px 8px;text-align:left;font-size:10px;text-transform:uppercase;color:#047857;border-bottom:2px solid #bbf7d0}}
td{{padding:6px 8px;border-bottom:1px solid #e5e7eb}}
td:last-child,th:last-child{{text-align:right}}
.net{{border:2px solid #047857;border-radius:6px;padding:12px;display:flex;justify-content:space-between;font-size:14px;font-weight:700;color:#047857;margin-bottom:20px}}
@media print{{@page{{size:A4;margin:2cm}}}}
</style></head><body>
<h1>Payslip — {emp.employee_id}</h1>
<div class="subtitle">Period: {item.payroll.month:02d}/{item.payroll.year} | Payment: {item.payroll.payment_date or "—"}</div>
<table><tr><th>Employee</th><th>Department</th><th>Position</th></tr>
<tr><td>{emp_name}</td><td>{dept}</td><td>{pos}</td></tr></table>
<table><tr><th>Earnings</th><th>Amount ({currency})</th></tr>
<tr><td>Basic Salary</td><td>{item.basic_salary}</td></tr>
<tr><td>Total Allowances</td><td>{item.total_allowances}</td></tr>
<tr style="font-weight:600"><td>Gross Salary</td><td>{item.gross_salary}</td></tr></table>
<table><tr><th>Deductions</th><th>Amount ({currency})</th></tr>
<tr><td>Total Deductions</td><td>{item.total_deductions}</td></tr></table>
<div class="net"><span>NET PAY</span><span>{currency} {item.net_salary}</span></div>
<p style="font-size:10px;color:#888">Generated by Rynaty School Management System — Rynatyspace Technologies</p>
<script>window.onload=function(){{window.print()}}</script>
</body></html>"""
        response = HttpResponse(content, content_type="text/html; charset=utf-8")
        response["Content-Disposition"] = f'inline; filename="payslip_{item.payroll.year}_{item.payroll.month:02d}_{emp.employee_id}.html"'
        return response

    @action(detail=False, methods=["post"], url_path="email")
    def email(self, request):
        ids = request.data.get("payslip_ids", [])
        if not isinstance(ids, list) or not ids:
            return Response({"error": "payslip_ids[] is required."}, status=status.HTTP_400_BAD_REQUEST)
        updated = PayrollItem.objects.filter(id__in=ids, is_active=True).update(sent_at=timezone.now())
        return Response({"message": "Payslips marked as sent.", "count": updated}, status=status.HTTP_200_OK)


class JobPostingViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = JobPosting.objects.filter(is_active=True).order_by("-created_at", "-id")
    serializer_class = JobPostingSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        status_value = self.request.query_params.get("status")
        department = self.request.query_params.get("department")
        if status_value:
            queryset = queryset.filter(status=status_value)
        if department:
            queryset = queryset.filter(department_id=department)
        return queryset

    def perform_create(self, serializer):
        serializer.save(posted_by=self.request.user)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])

    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, pk=None):
        posting = self.get_object()
        posting.status = "Open"
        posting.posted_by = request.user
        posting.posted_at = timezone.now()
        posting.save(update_fields=["status", "posted_by", "posted_at"])
        return Response({"message": "Job posting published."}, status=status.HTTP_200_OK)


class JobApplicationViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = JobApplication.objects.filter(is_active=True).order_by("-applied_at", "-id")
    serializer_class = JobApplicationSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        status_value = self.request.query_params.get("status")
        posting = self.request.query_params.get("job_posting")
        if status_value:
            queryset = queryset.filter(status=status_value)
        if posting:
            queryset = queryset.filter(job_posting_id=posting)
        return queryset

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])

    @action(detail=True, methods=["post"], url_path="shortlist")
    def shortlist(self, request, pk=None):
        application = self.get_object()
        application.status = "Shortlisted"
        application.save(update_fields=["status"])
        return Response({"message": "Applicant shortlisted."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        application = self.get_object()
        notes = request.data.get("notes", "")
        application.status = "Rejected"
        if notes:
            application.notes = notes
            application.save(update_fields=["status", "notes"])
        else:
            application.save(update_fields=["status"])
        return Response({"message": "Applicant rejected."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="hire")
    def hire(self, request, pk=None):
        application = self.get_object()
        if application.status == "Hired":
            return Response({"error": "Application already hired."}, status=status.HTTP_400_BAD_REQUEST)

        posting = application.job_posting
        join_date = _coerce_date(request.data.get("join_date") or timezone.now().date())
        position = posting.position
        department = posting.department or (position.department if position else None)
        position_title = position.title if position else posting.title
        explicit_category = (request.data.get("staff_category") or "").strip()
        if explicit_category and not normalize_staff_category(explicit_category):
            return Response({"error": "Unsupported staff_category."}, status=status.HTTP_400_BAD_REQUEST)
        staff_category = infer_staff_category(position_title, explicit_category)
        explicit_role_name = normalize_role_name(request.data.get("account_role_name"))
        if explicit_role_name and explicit_role_name not in SUPPORTED_ROLE_NAMES:
            return Response({"error": "Unsupported account_role_name."}, status=status.HTTP_400_BAD_REQUEST)

        work_email = (request.data.get("work_email") or "").strip()
        if work_email and "@" not in work_email:
            return Response({"error": "work_email must be a valid email address."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            employee = Employee.objects.create(
                employee_id=_generate_employee_id(),
                staff_id=_generate_staff_id(),
                first_name=application.first_name,
                last_name=application.last_name,
                date_of_birth=_coerce_date(request.data.get("date_of_birth") or "1990-01-01"),
                gender=request.data.get("gender", "Other"),
                nationality=request.data.get("nationality", ""),
                national_id=request.data.get("national_id", ""),
                personal_email=(request.data.get("personal_email") or "").strip() or application.email,
                work_email=work_email,
                marital_status=request.data.get("marital_status", "Single"),
                department=department,
                position=position,
                staff_category=staff_category,
                employment_type=posting.employment_type,
                status="Active",
                onboarding_status="IN_PROGRESS",
                account_role_name=(
                    explicit_role_name
                    if "account_role_name" in request.data
                    else suggest_account_role_name(position_title, staff_category)
                ),
                join_date=join_date,
                notice_period_days=int(request.data.get("notice_period_days", 30)),
                is_active=True,
            )
            ensure_employment_profile(employee)

            application.status = "Hired"
            application.save(update_fields=["status"])

            seed_default_onboarding_tasks(
                employee,
                assigned_to=request.user,
                due_date=join_date,
            )

        return Response(
            {
                "message": "Applicant hired and onboarding initialized.",
                "employee_id": employee.id,
                "staff_id": employee.staff_id,
                "onboarding_status": employee.onboarding_status,
            },
            status=status.HTTP_200_OK,
        )


class InterviewViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = Interview.objects.filter(is_active=True).order_by("-interview_date", "-id")
    serializer_class = InterviewSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        status_value = self.request.query_params.get("status")
        application = self.request.query_params.get("application")
        if status_value:
            queryset = queryset.filter(status=status_value)
        if application:
            queryset = queryset.filter(application_id=application)
        return queryset

    def perform_create(self, serializer):
        interview = serializer.save(created_by=self.request.user)
        application = interview.application
        if application.status in ["New", "Screening", "Shortlisted"]:
            application.status = "Interview"
            application.save(update_fields=["status"])

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])

    @action(detail=True, methods=["post"], url_path="feedback")
    def feedback(self, request, pk=None):
        interview = self.get_object()
        feedback_value = request.data.get("feedback", "").strip()
        if not feedback_value:
            return Response({"error": "feedback is required."}, status=status.HTTP_400_BAD_REQUEST)
        score = request.data.get("score")
        interview.feedback = feedback_value
        if score is not None:
            interview.score = score
        interview.status = request.data.get("status", "Completed")
        interview.save(update_fields=["feedback", "score", "status"])
        return Response({"message": "Interview feedback recorded."}, status=status.HTTP_200_OK)


class OnboardingTaskViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = OnboardingTask.objects.filter(is_active=True).order_by("status", "due_date", "id")
    serializer_class = OnboardingTaskSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        employee = self.request.query_params.get("employee")
        status_value = self.request.query_params.get("status")
        if employee:
            queryset = queryset.filter(employee_id=employee)
        if status_value:
            queryset = queryset.filter(status=status_value)
        return queryset

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])

    @action(detail=True, methods=["patch"], url_path="complete")
    def complete(self, request, pk=None):
        task = self.get_object()
        task.status = "Completed"
        task.completed_at = timezone.now()
        if "notes" in request.data:
            task.notes = request.data.get("notes", "")
            task.save(update_fields=["status", "completed_at", "notes"])
        else:
            task.save(update_fields=["status", "completed_at"])
        return Response({"message": "Onboarding task completed."}, status=status.HTTP_200_OK)


class OnboardingChecklistView(HrModuleAccessMixin, APIView):
    def get(self, request, employee_id):
        queryset = OnboardingTask.objects.filter(employee_id=employee_id, is_active=True).order_by("status", "due_date", "id")
        serializer = OnboardingTaskSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PerformanceGoalViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = PerformanceGoal.objects.filter(is_active=True).order_by("-created_at", "-id")
    serializer_class = PerformanceGoalSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        employee = self.request.query_params.get("employee")
        status_value = self.request.query_params.get("status")
        if employee:
            queryset = queryset.filter(employee_id=employee)
        if status_value:
            queryset = queryset.filter(status=status_value)
        return queryset

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class PerformanceReviewViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = PerformanceReview.objects.filter(is_active=True).order_by("-created_at", "-id")
    serializer_class = PerformanceReviewSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        employee = self.request.query_params.get("employee")
        reviewer = self.request.query_params.get("reviewer")
        status_value = self.request.query_params.get("status")
        if employee:
            queryset = queryset.filter(employee_id=employee)
        if reviewer:
            queryset = queryset.filter(reviewer_id=reviewer)
        if status_value:
            queryset = queryset.filter(status=status_value)
        return queryset

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])

    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request, pk=None):
        review = self.get_object()
        review.status = "Submitted"
        review.reviewed_at = timezone.now()
        review.save(update_fields=["status", "reviewed_at"])
        return Response({"message": "Performance review submitted."}, status=status.HTTP_200_OK)


class TrainingProgramViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = TrainingProgram.objects.filter(is_active=True).order_by("-start_date", "-id")
    serializer_class = TrainingProgramSerializer

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class TrainingEnrollmentViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = TrainingEnrollment.objects.filter(is_active=True).order_by("-created_at", "-id")
    serializer_class = TrainingEnrollmentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        program = self.request.query_params.get("program")
        employee = self.request.query_params.get("employee")
        status_value = self.request.query_params.get("status")
        if program:
            queryset = queryset.filter(program_id=program)
        if employee:
            queryset = queryset.filter(employee_id=employee)
        if status_value:
            queryset = queryset.filter(status=status_value)
        return queryset

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class HrAnalyticsSummaryView(HrModuleAccessMixin, APIView):
    def get(self, request):
        employees = Employee.objects.filter(is_active=True)
        by_status = (
            employees.values("status")
            .annotate(count=Count("id"))
            .order_by("status")
        )
        by_department = (
            employees.values("department__name")
            .annotate(count=Count("id"))
            .order_by("department__name")
        )
        by_type = (
            employees.values("employment_type")
            .annotate(count=Count("id"))
            .order_by("employment_type")
        )
        attendance_qs = AttendanceRecord.objects.filter(is_active=True)
        attendance_rate = 0.0
        if attendance_qs.exists():
            total = attendance_qs.count()
            present = attendance_qs.filter(status__in=["Present", "Late", "Half-Day"]).count()
            attendance_rate = round((present / total) * 100, 2) if total else 0.0
        return Response(
            {
                "headcount": employees.count(),
                "attendance_rate_percent": attendance_rate,
                "departments": Department.objects.filter(is_active=True).count(),
                "positions": Position.objects.filter(is_active=True).count(),
                "headcount_by_status": [
                    {"status": row["status"], "count": row["count"]} for row in by_status
                ],
                "headcount_by_department": [
                    {"department": row["department__name"] or "Unassigned", "count": row["count"]}
                    for row in by_department
                ],
                "headcount_by_employment_type": [
                    {"employment_type": row["employment_type"], "count": row["count"]}
                    for row in by_type
                ],
            },
            status=status.HTTP_200_OK,
        )


class HrAnalyticsHeadcountView(HrModuleAccessMixin, APIView):
    def get(self, request):
        employees = Employee.objects.filter(is_active=True)
        by_department = employees.values("department__name").annotate(count=Count("id")).order_by("department__name")
        by_position = employees.values("position__title").annotate(count=Count("id")).order_by("position__title")
        by_type = employees.values("employment_type").annotate(count=Count("id")).order_by("employment_type")
        return Response(
            {
                "total": employees.count(),
                "by_department": [{"department": row["department__name"] or "Unassigned", "count": row["count"]} for row in by_department],
                "by_position": [{"position": row["position__title"] or "Unassigned", "count": row["count"]} for row in by_position],
                "by_employment_type": [{"employment_type": row["employment_type"], "count": row["count"]} for row in by_type],
            },
            status=status.HTTP_200_OK,
        )


class HrAnalyticsTurnoverView(HrModuleAccessMixin, APIView):
    def get(self, request):
        year = int(request.query_params.get("year", timezone.now().year))
        employees_total = Employee.objects.filter(is_active=True).count()
        exits = Employee.objects.filter(is_active=True, exit_date__year=year).exclude(exit_reason="").count()
        turnover_rate = round((exits / employees_total) * 100, 2) if employees_total else 0.0
        by_reason = (
            Employee.objects.filter(is_active=True, exit_date__year=year)
            .exclude(exit_reason="")
            .values("exit_reason")
            .annotate(count=Count("id"))
            .order_by("exit_reason")
        )
        return Response(
            {
                "year": year,
                "headcount_base": employees_total,
                "exits": exits,
                "turnover_rate_percent": turnover_rate,
                "by_reason": [{"reason": row["exit_reason"], "count": row["count"]} for row in by_reason],
            },
            status=status.HTTP_200_OK,
        )


class HrAnalyticsAttendanceView(HrModuleAccessMixin, APIView):
    def get(self, request):
        month = int(request.query_params.get("month", timezone.now().month))
        year = int(request.query_params.get("year", timezone.now().year))
        qs = AttendanceRecord.objects.filter(is_active=True, date__month=month, date__year=year)
        total = qs.count()
        present = qs.filter(status__in=["Present", "Late", "Half-Day"]).count()
        absent = qs.filter(status="Absent").count()
        late = qs.filter(status="Late").count()
        overtime = qs.aggregate(total=Sum("overtime_hours"))["total"] or Decimal("0.00")
        return Response(
            {
                "month": month,
                "year": year,
                "total_records": total,
                "present_records": present,
                "absent_records": absent,
                "late_records": late,
                "attendance_rate_percent": round((present / total) * 100, 2) if total else 0.0,
                "overtime_hours_total": _round_money(overtime),
            },
            status=status.HTTP_200_OK,
        )


class HrAnalyticsLeaveView(HrModuleAccessMixin, APIView):
    def get(self, request):
        year = int(request.query_params.get("year", timezone.now().year))
        qs = LeaveBalance.objects.filter(is_active=True, year=year)
        totals = qs.aggregate(
            opening=Sum("opening_balance"),
            accrued=Sum("accrued"),
            used=Sum("used"),
            pending=Sum("pending"),
            available=Sum("available"),
        )
        return Response(
            {
                "year": year,
                "opening_balance_total": _round_money(totals["opening"] or 0),
                "accrued_total": _round_money(totals["accrued"] or 0),
                "used_total": _round_money(totals["used"] or 0),
                "pending_total": _round_money(totals["pending"] or 0),
                "available_total": _round_money(totals["available"] or 0),
            },
            status=status.HTTP_200_OK,
        )


class HrAnalyticsDiversityView(HrModuleAccessMixin, APIView):
    def get(self, request):
        employees = Employee.objects.filter(is_active=True)
        total = employees.count()
        by_gender = employees.values("gender").annotate(count=Count("id")).order_by("gender")
        data = []
        for row in by_gender:
            pct = round((row["count"] / total) * 100, 2) if total else 0.0
            data.append({"gender": row["gender"], "count": row["count"], "percent": pct})
        return Response({"total": total, "by_gender": data}, status=status.HTTP_200_OK)


class HrAnalyticsPayrollCostsView(HrModuleAccessMixin, APIView):
    def get(self, request):
        year = int(request.query_params.get("year", timezone.now().year))
        batches = PayrollBatch.objects.filter(is_active=True, year=year)
        totals = batches.aggregate(gross=Sum("total_gross"), deductions=Sum("total_deductions"), net=Sum("total_net"))
        by_month = (
            batches.values("month")
            .annotate(gross=Sum("total_gross"), deductions=Sum("total_deductions"), net=Sum("total_net"))
            .order_by("month")
        )
        return Response(
            {
                "year": year,
                "total_gross": _round_money(totals["gross"] or 0),
                "total_deductions": _round_money(totals["deductions"] or 0),
                "total_net": _round_money(totals["net"] or 0),
                "by_month": [
                    {
                        "month": row["month"],
                        "gross": _round_money(row["gross"] or 0),
                        "deductions": _round_money(row["deductions"] or 0),
                        "net": _round_money(row["net"] or 0),
                    }
                    for row in by_month
                ],
            },
            status=status.HTTP_200_OK,
        )


class HrAuditLogView(HrModuleAccessMixin, APIView):
    def get(self, request):
        limit = int(request.query_params.get("limit", 50))
        ordering = request.query_params.get("ordering", "-timestamp")

        logs = []

        leave_qs = LeaveRequest.objects.select_related("employee", "employee__user", "approved_by", "approved_by__user").order_by("-submitted_at")[:limit]
        for lr in leave_qs:
            emp_name = (lr.employee.user.get_full_name() or lr.employee.user.username) if lr.employee and lr.employee.user else "—"
            approver = lr.approved_by
            actor = (approver.user.get_full_name() or approver.user.username) if approver and hasattr(approver, 'user') and approver.user else "System"
            action_label = "Approved Leave" if lr.status == "Approved" else ("Rejected Leave" if lr.status == "Rejected" else "Created Record")
            logs.append({
                "id": f"LR-{lr.id}",
                "log_id": f"LR-{str(lr.id).zfill(4)}",
                "user_display": actor,
                "role": "HR Manager",
                "action": action_label,
                "target": f"{emp_name}",
                "module": "Leave",
                "timestamp": (lr.approved_at or lr.submitted_at).isoformat() if (lr.approved_at or lr.submitted_at) else "",
                "ip_address": "—",
            })

        payroll_qs = PayrollBatch.objects.select_related("processed_by", "approved_by").order_by("-created_at")[:20]
        for pb in payroll_qs:
            actor = (pb.processed_by.get_full_name() or pb.processed_by.username) if pb.processed_by else "System"
            logs.append({
                "id": f"PB-{pb.id}",
                "log_id": f"PB-{str(pb.id).zfill(4)}",
                "user_display": actor,
                "role": "Payroll Admin",
                "action": "Modified Payroll",
                "target": f"Payroll — {pb.month}/{pb.year}",
                "module": "Payroll",
                "timestamp": pb.created_at.isoformat() if pb.created_at else "",
                "ip_address": "—",
            })

        emp_qs = Employee.objects.select_related("user").order_by("-created_at")[:20]
        for emp in emp_qs:
            name = emp.user.get_full_name() or emp.user.username if emp.user else "—"
            logs.append({
                "id": f"EMP-{emp.id}",
                "log_id": f"EMP-{str(emp.id).zfill(4)}",
                "user_display": "HR Admin",
                "role": "HR Admin",
                "action": "Added Employee",
                "target": name,
                "module": "Employees",
                "timestamp": emp.created_at.isoformat() if emp.created_at else "",
                "ip_address": "—",
            })

        logs.sort(key=lambda x: x["timestamp"], reverse=(not ordering.startswith("-") or ordering == "-timestamp"))
        return Response(logs[:limit], status=status.HTTP_200_OK)


class HrComplianceView(HrModuleAccessMixin, APIView):
    def get(self, request):
        total_emp = Employee.objects.filter(is_active=True).count()
        pending_leave = LeaveRequest.objects.filter(status="Pending").count()
        incomplete_onboarding = OnboardingTask.objects.filter(is_completed=False).count()
        no_salary = Employee.objects.filter(is_active=True).exclude(salary_structures__is_active=True).count()
        pending_reviews = PerformanceReview.objects.filter(status="Pending").count()
        open_positions = JobPosting.objects.filter(status="Open").count()

        data = [
            {"label": "Pending Leave Requests", "value": pending_leave, "alert": pending_leave > 0},
            {"label": "Incomplete Onboarding Tasks", "value": incomplete_onboarding, "alert": incomplete_onboarding > 0},
            {"label": "Employees Without Salary Structure", "value": no_salary, "alert": no_salary > 0},
            {"label": "Pending Performance Reviews", "value": pending_reviews, "alert": pending_reviews > 0},
            {"label": "Open Job Postings", "value": open_positions, "alert": False},
            {"label": "Active Employees", "value": total_emp, "alert": False},
        ]
        return Response(data, status=status.HTTP_200_OK)


class StaffLifecycleEventViewSet(HrModuleAccessMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = StaffLifecycleEvent.objects.select_related("employee", "recorded_by").order_by(
        "-effective_date",
        "-occurred_at",
        "-id",
    )
    serializer_class = StaffLifecycleEventSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        employee_id = self.request.query_params.get("employee")
        event_group = self.request.query_params.get("event_group")
        event_type = self.request.query_params.get("event_type")
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)
        if event_group:
            queryset = queryset.filter(event_group=event_group)
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        return queryset


class StaffCareerActionViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = StaffCareerAction.objects.select_related(
        "employee",
        "parent_action",
        "from_department",
        "from_position_ref",
        "to_department",
        "to_position_ref",
        "requested_by",
        "applied_by",
    ).order_by("-effective_date", "-created_at", "-id")
    serializer_class = StaffCareerActionSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = super().get_queryset()
        employee_f = self.request.query_params.get("employee")
        action_type_f = self.request.query_params.get("action_type")
        status_f = self.request.query_params.get("status")
        if employee_f:
            queryset = queryset.filter(employee_id=employee_f)
        if action_type_f:
            queryset = queryset.filter(action_type=action_type_f)
        if status_f:
            queryset = queryset.filter(status=status_f)
        return queryset

    def perform_create(self, serializer):
        actor = self.request.user if self.request.user.is_authenticated else None
        with transaction.atomic():
            action = serializer.save(requested_by=actor)
            sync_career_action_assignment_fields(action)

    def _update_action(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        if instance.action_type == "ACTING_APPOINTMENT_END":
            return Response({"error": "Acting appointment end records are read-only."}, status=status.HTTP_400_BAD_REQUEST)

        if instance.status in {"EFFECTIVE", "CANCELLED"}:
            return Response({"error": "Terminal career actions cannot be edited."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                action = serializer.save()
                sync_career_action_assignment_fields(action)
        except CareerWorkflowError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(self.get_serializer(action).data, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        return self._update_action(request, *args, partial=True, **kwargs)

    @action(detail=True, methods=["post"], url_path="apply")
    def apply(self, request, pk=None):
        action_record = self.get_object()
        try:
            with transaction.atomic():
                sync_career_action_assignment_fields(action_record)
                action_record = apply_career_action(action_record, recorded_by=request.user)
        except CareerWorkflowError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(action_record).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="end-acting")
    def end_acting(self, request, pk=None):
        action_record = self.get_object()
        serializer = StaffCareerActionEndActingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                end_action = end_acting_appointment(
                    action_record,
                    recorded_by=request.user,
                    effective_date=serializer.validated_data.get("effective_date"),
                    notes=serializer.validated_data.get("notes", ""),
                )
        except CareerWorkflowError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(end_action).data, status=status.HTTP_200_OK)


class DisciplinaryCaseViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = DisciplinaryCase.objects.select_related(
        "employee",
        "opened_by",
        "closed_by",
    ).order_by("-opened_on", "-created_at", "-id")
    serializer_class = DisciplinaryCaseSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = super().get_queryset()
        employee_f = self.request.query_params.get("employee")
        status_f = self.request.query_params.get("status")
        outcome_f = self.request.query_params.get("outcome")
        category_f = self.request.query_params.get("category")
        if employee_f:
            queryset = queryset.filter(employee_id=employee_f)
        if status_f:
            queryset = queryset.filter(status=status_f)
        if outcome_f:
            queryset = queryset.filter(outcome=outcome_f)
        if category_f:
            queryset = queryset.filter(category__iexact=category_f)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            disciplinary_case = create_disciplinary_case(
                recorded_by=request.user if request.user.is_authenticated else None,
                **serializer.validated_data,
            )
        output = self.get_serializer(disciplinary_case)
        headers = self.get_success_headers(output.data)
        return Response(output.data, status=status.HTTP_201_CREATED, headers=headers)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status != "OPEN":
            return Response({"error": "Only open disciplinary cases can be edited."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        disciplinary_case = serializer.save()
        return Response(self.get_serializer(disciplinary_case).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, pk=None):
        disciplinary_case = self.get_object()
        serializer = DisciplinaryCaseCloseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                disciplinary_case = close_disciplinary_case(
                    disciplinary_case,
                    outcome=serializer.validated_data["outcome"],
                    recorded_by=request.user if request.user.is_authenticated else None,
                    effective_date=serializer.validated_data.get("effective_date"),
                    notes=serializer.validated_data.get("notes", ""),
                )
        except DisciplineWorkflowError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(disciplinary_case).data, status=status.HTTP_200_OK)


class ExitCaseViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = ExitCase.objects.select_related(
        "employee",
        "requested_by",
        "completed_by",
    ).order_by("-effective_date", "-created_at", "-id")
    serializer_class = ExitCaseSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = super().get_queryset()
        employee_f = self.request.query_params.get("employee")
        exit_type_f = self.request.query_params.get("exit_type")
        status_f = self.request.query_params.get("status")
        if employee_f:
            queryset = queryset.filter(employee_id=employee_f)
        if exit_type_f:
            queryset = queryset.filter(exit_type=exit_type_f)
        if status_f:
            queryset = queryset.filter(status=status_f)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                exit_case = create_exit_case(
                    recorded_by=request.user if request.user.is_authenticated else None,
                    **serializer.validated_data,
                )
        except ExitWorkflowError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        output = self.get_serializer(exit_case)
        headers = self.get_success_headers(output.data)
        return Response(output.data, status=status.HTTP_201_CREATED, headers=headers)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status in {"COMPLETED", "ARCHIVED", "CANCELLED"}:
            return Response({"error": "Terminal exit cases cannot be edited."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        exit_case = serializer.save()
        return Response(self.get_serializer(exit_case).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="start-clearance")
    def start_clearance(self, request, pk=None):
        exit_case = self.get_object()
        try:
            with transaction.atomic():
                exit_case = start_exit_clearance(
                    exit_case,
                    recorded_by=request.user if request.user.is_authenticated else None,
                )
        except ExitWorkflowError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(exit_case).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        exit_case = self.get_object()
        try:
            with transaction.atomic():
                exit_case = complete_exit_case(
                    exit_case,
                    recorded_by=request.user if request.user.is_authenticated else None,
                )
        except ExitWorkflowError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(exit_case).data, status=status.HTTP_200_OK)


class ExitClearanceItemViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = ExitClearanceItem.objects.select_related(
        "exit_case",
        "completed_by",
    ).order_by("display_order", "id")
    serializer_class = ExitClearanceItemSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = super().get_queryset()
        exit_case_f = self.request.query_params.get("exit_case")
        status_f = self.request.query_params.get("status")
        if exit_case_f:
            queryset = queryset.filter(exit_case_id=exit_case_f)
        if status_f:
            queryset = queryset.filter(status=status_f)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        exit_case = serializer.validated_data["exit_case"]
        if exit_case.status in {"COMPLETED", "ARCHIVED", "CANCELLED"}:
            return Response({"error": "Cannot add clearance items to a terminal exit case."}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            item = serializer.save()
            sync_exit_clearance_item_completion_fields(
                item,
                recorded_by=request.user if request.user.is_authenticated else None,
            )
        output = self.get_serializer(item)
        headers = self.get_success_headers(output.data)
        return Response(output.data, status=status.HTTP_201_CREATED, headers=headers)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.exit_case.status in {"COMPLETED", "ARCHIVED", "CANCELLED"}:
            return Response({"error": "Cannot edit clearance items on a terminal exit case."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            item = serializer.save()
            sync_exit_clearance_item_completion_fields(
                item,
                recorded_by=request.user if request.user.is_authenticated else None,
            )
        return Response(self.get_serializer(item).data, status=status.HTTP_200_OK)


class StaffTransferViewSet(HrModuleAccessMixin, viewsets.ModelViewSet):
    queryset = StaffTransfer.objects.select_related(
        "employee",
        "from_department",
        "to_department",
        "to_position_ref",
    ).order_by("-created_at")
    serializer_class = StaffTransferSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        status_f = self.request.query_params.get("status")
        transfer_type_f = self.request.query_params.get("transfer_type")
        employee_f = self.request.query_params.get("employee")
        if status_f:
            queryset = queryset.filter(status=status_f)
        if transfer_type_f:
            queryset = queryset.filter(transfer_type=transfer_type_f)
        if employee_f:
            queryset = queryset.filter(employee_id=employee_f)
        return queryset

    def perform_create(self, serializer):
        actor = self.request.user if self.request.user.is_authenticated else None
        with transaction.atomic():
            transfer = serializer.save(requested_by=actor)
            sync_transfer_assignment_fields(transfer)
            append_transfer_requested_event(transfer, recorded_by=actor)

    def _update_transfer(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        original_status = instance.status
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        requested_status = serializer.validated_data.get("status")

        if original_status == "Completed" and requested_status and requested_status != "Completed":
            return Response({"error": "Completed transfer cannot change status."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                save_kwargs = {}
                if requested_status == "Completed" and original_status != "Completed":
                    save_kwargs["status"] = original_status
                transfer = serializer.save(**save_kwargs)
                sync_transfer_assignment_fields(transfer)
                if requested_status == "Completed" and original_status != "Completed":
                    transfer = complete_transfer(transfer, recorded_by=request.user)
        except CareerWorkflowError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(self.get_serializer(transfer).data, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        return self._update_transfer(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        return self._update_transfer(request, *args, partial=True, **kwargs)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        transfer = self.get_object()
        try:
            with transaction.atomic():
                sync_transfer_assignment_fields(transfer)
                transfer = complete_transfer(transfer, recorded_by=request.user)
        except CareerWorkflowError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(transfer).data, status=status.HTTP_200_OK)
