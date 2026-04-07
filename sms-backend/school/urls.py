from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenRefreshView
from .views import SmartCampusTokenObtainPairView, RoleSwitchView
from .views import (
    StudentSearchForUserCreateView, StudentsByClassForUserCreateView,
    BulkCreateStudentUsersView,
    TransferListView, TransferInitiateView, TransferDetailView,
    TransferApproveFromView, TransferApproveToView, TransferRejectView,
    TransferCancelView, TransferExecuteView, TransferPackageView,
    StudentTransferHistoryView, StaffTransferHistoryView,
    AdmissionSettingsView, AdmissionNumberPreviewView,
    MediaUploadView, MediaFileListView,
    ImportTemplateDownloadView, StudentsBulkImportView, StaffBulkImportView,
    TenantSettingsView, TenantSettingDeleteView,
    FinanceSettingsView, GeneralSettingsView,
    ControlPlaneSummaryView, SecurityPolicyView,
    LifecycleTemplateListView, LifecycleRunListCreateView,
    LifecycleRunDetailView, LifecycleRunStartView,
    LifecycleRunCompleteView, LifecycleTaskCompleteView, LifecycleTaskWaiveView,
)
from .rbac_views import (
    RbacPermissionListView,
    RbacPermissionSeedView,
    RbacRoleListView,
    RbacRoleGrantPermissionView,
    RbacRoleRevokePermissionView,
    RbacUserEffectivePermissionsView,
    RbacUserOverrideListView,
    RbacUserOverrideDeleteView,
)
from .domain_views import (
    SchoolDomainStatusView,
    SchoolDomainRequestView,
    SchoolDomainVerifyView,
)
from domains.inventory.presentation.views import (
    StoreCategoryViewSet,
    StoreSupplierViewSet,
    StoreItemViewSet,
    StoreTransactionViewSet,
    StoreOrderRequestViewSet,
    StoreOrderReviewView,
    StoreDashboardView,
    StoreReportsView,
)
from finance.presentation.views import (
    BulkFeeAssignByClassView as FinanceBulkFeeAssignByClassView,
    BulkOptionalChargeByClassView as FinanceBulkOptionalChargeByClassView,
    CashbookSummaryView,
    FinanceArrearsByTermReportView,
    FinanceArrearsView,
    FinanceBudgetVarianceReportView,
    FinanceClassRefView,
    FinanceClassBalancesReportView,
    FinanceEnrollmentRefView,
    FinanceInstallmentAgingView,
    FinanceOverdueAccountsView,
    FinanceReceiptPdfView as FinanceReceiptPdfView,
    FinanceReceivablesAgingView,
    FinanceStudentRefView,
    FinanceStudentLedgerView as FinanceStudentLedgerView,
    FinanceVoteHeadAllocationReportView,
    FinanceVoteHeadBudgetReportView,
    FinancialSummaryView,
)
from finance.presentation.viewsets import (
    BalanceCarryForwardViewSet as FinanceBalanceCarryForwardViewSet,
    CashbookEntryViewSet as FinanceCashbookEntryViewSet,
    FeeAssignmentViewSet as FinanceFeeAssignmentViewSet,
    FeeStructureViewSet as FinanceFeeStructureViewSet,
    InvoiceAdjustmentViewSet as FinanceInvoiceAdjustmentViewSet,
    InvoiceViewSet as FinanceInvoiceViewSet,
    InvoiceWriteOffRequestViewSet as FinanceInvoiceWriteOffRequestViewSet,
    OptionalChargeViewSet as FinanceOptionalChargeViewSet,
    PaymentReversalRequestViewSet as FinancePaymentReversalRequestViewSet,
    PaymentViewSet as FinancePaymentViewSet,
    StudentOptionalChargeViewSet as FinanceStudentOptionalChargeViewSet,
    VoteHeadViewSet as FinanceVoteHeadViewSet,
)
from finance.presentation.accounting_views import (
    AccountingLedgerView as FinanceAccountingLedgerView,
    AccountingTrialBalanceView as FinanceAccountingTrialBalanceView,
)
from finance.presentation.accounting_viewsets import (
    AccountingPeriodViewSet as FinanceAccountingPeriodViewSet,
    ChartOfAccountViewSet as FinanceChartOfAccountViewSet,
    JournalEntryViewSet as FinanceJournalEntryViewSet,
)
from finance.presentation.governance_viewsets import (
    BudgetViewSet as FinanceBudgetViewSet,
)
from .views import (
    EnrollmentViewSet, ExpenseViewSet, MessageViewSet, 
    StaffViewSet, StudentViewSet,
    DepartmentViewSet,
    PaymentGatewayTransactionViewSet,
    PaymentGatewayWebhookEventViewSet,
    BankStatementLineViewSet,
    FinanceGatewayWebhookView,
    LateFeeRuleViewSet,
    FeeReminderLogViewSet,
    TermViewSet, ModuleViewSet, UserModuleAssignmentViewSet,
    DashboardRoutingView, DashboardSummaryView, StudentsSummaryView, StudentsDashboardView,
    SchoolProfileView, SchoolTestEmailView, SchoolTestSmsView,
    AcademicsSummaryView, HrSummaryView, CommunicationSummaryView,
    AcademicsCurrentContextView,
    CoreSummaryView, ReportingSummaryView,
    StudentsModuleReportView, StudentReportView, StudentOperationalSummaryView,
    StudentsModuleReportCsvExportView, StudentReportCsvExportView,
    StudentsModuleReportPdfExportView, StudentReportPdfExportView,
    StudentsDirectoryCsvExportView, StudentsDirectoryPdfExportView,
    FinanceSummaryCsvExportView, FinanceSummaryPdfExportView,
    FinanceReceivablesAgingCsvExportView, FinanceOverdueAccountsCsvExportView,
    AttendanceSummaryCsvExportView, AttendanceSummaryPdfExportView,
    AttendanceRecordsCsvExportView, AttendanceRecordsPdfExportView,
    BehaviorIncidentsCsvExportView, BehaviorIncidentsPdfExportView,
    MedicalProfilesCsvExportView, MedicalProfilesPdfExportView,
    MedicalImmunizationsCsvExportView, MedicalImmunizationsPdfExportView,
    MedicalClinicVisitsCsvExportView, MedicalClinicVisitsPdfExportView,
    StudentsDocumentsCsvExportView, StudentsDocumentsPdfExportView,
    ScholarshipAwardViewSet,
    TenantSequenceResetView,
    AttendanceRecordViewSet,
    AttendanceSummaryView,
    BehaviorIncidentViewSet,
    MedicalRecordViewSet,
    ImmunizationRecordViewSet,
    ClinicVisitViewSet,
    TenantModuleListView,
    TenantModuleSettingsView,
    VoteHeadPaymentAllocationViewSet,
    DispensaryVisitViewSet, DispensaryPrescriptionViewSet, DispensaryStockViewSet, DispensaryDashboardView,
    DispensaryDeliveryNoteViewSet, DispensaryOutsideTreatmentViewSet,
    StudentTransferViewSet,
    RoleListView,
    RoleModuleAccessView,
    SubmodulePermissionView,
    UserManagementListCreateView,
    UserManagementDetailView,
    DemoResetView,
    CurrentUserView,
    SchoolClassListView,
    ModuleSeedView,
)

# ==========================================
# URL ROUTER (TENANT DATA)
# ==========================================
router = DefaultRouter()

# Shared / cross-module
router.register(r'school/departments', DepartmentViewSet, basename='department')

# Modules
router.register(r'students', StudentViewSet, basename='student')
router.register(r'enrollments', EnrollmentViewSet, basename='enrollment')
router.register(r'staff', StaffViewSet, basename='staff')
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'modules', ModuleViewSet, basename='module')
router.register(r'module-assignments', UserModuleAssignmentViewSet, basename='module-assignment')
router.register(r'attendance', AttendanceRecordViewSet, basename='attendance')
router.register(r'behavior/incidents', BehaviorIncidentViewSet, basename='behavior-incident')
router.register(r'medical/records', MedicalRecordViewSet, basename='medical-record')
router.register(r'medical/immunizations', ImmunizationRecordViewSet, basename='medical-immunization')
router.register(r'medical/visits', ClinicVisitViewSet, basename='medical-visit')

# Finance (Primary)
router.register(r'finance/terms', TermViewSet, basename='term') 
router.register(r'finance/fees', FinanceFeeStructureViewSet, basename='feestructure')
router.register(r'finance/fee-assignments', FinanceFeeAssignmentViewSet, basename='feeassignment')
router.register(r'finance/scholarships', ScholarshipAwardViewSet, basename='scholarshipaward')
router.register(r'finance/optional-charges', FinanceOptionalChargeViewSet, basename='optional-charge')
router.register(r'finance/student-optional-charges', FinanceStudentOptionalChargeViewSet, basename='student-optional-charge')
router.register(r'finance/invoice-adjustments', FinanceInvoiceAdjustmentViewSet, basename='invoiceadjustment')
router.register(r'finance/invoices', FinanceInvoiceViewSet, basename='invoice')
router.register(r'finance/payments', FinancePaymentViewSet, basename='payment')
router.register(r'finance/expenses', ExpenseViewSet, basename='expense')
router.register(r'finance/budgets', FinanceBudgetViewSet, basename='budget')
router.register(r'finance/payment-reversals', FinancePaymentReversalRequestViewSet, basename='payment-reversal')
router.register(r'finance/write-offs', FinanceInvoiceWriteOffRequestViewSet, basename='invoice-writeoff-request')
router.register(r'finance/gateway/transactions', PaymentGatewayTransactionViewSet, basename='payment-gateway-transaction')
router.register(r'finance/gateway/events', PaymentGatewayWebhookEventViewSet, basename='payment-gateway-event')
router.register(r'finance/reconciliation/bank-lines', BankStatementLineViewSet, basename='bank-statement-line')
router.register(r'finance/late-fee-rules', LateFeeRuleViewSet, basename='late-fee-rule')
router.register(r'finance/reminders', FeeReminderLogViewSet, basename='fee-reminder')
router.register(r'finance/accounting/periods', FinanceAccountingPeriodViewSet, basename='accounting-period')
router.register(r'finance/accounting/accounts', FinanceChartOfAccountViewSet, basename='accounting-account')
router.register(r'finance/accounting/journals', FinanceJournalEntryViewSet, basename='accounting-journal')
router.register(r'finance/vote-heads', FinanceVoteHeadViewSet, basename='vote-head')
router.register(r'finance/vote-head-allocations', VoteHeadPaymentAllocationViewSet, basename='vote-head-allocation')
router.register(r'finance/cashbook', FinanceCashbookEntryViewSet, basename='cashbook-entry')
router.register(r'finance/carry-forwards', FinanceBalanceCarryForwardViewSet, basename='carry-forward')
router.register(r'store/categories', StoreCategoryViewSet, basename='store-category')
router.register(r'store/suppliers', StoreSupplierViewSet, basename='store-supplier')
router.register(r'store/items', StoreItemViewSet, basename='store-item')
router.register(r'store/transactions', StoreTransactionViewSet, basename='store-transaction')
router.register(r'store/orders', StoreOrderRequestViewSet, basename='store-order')
router.register(r'dispensary/visits', DispensaryVisitViewSet, basename='dispensary-visit')
router.register(r'dispensary/prescriptions', DispensaryPrescriptionViewSet, basename='dispensary-prescription')
router.register(r'dispensary/stock', DispensaryStockViewSet, basename='dispensary-stock')
router.register(r'dispensary/delivery-notes', DispensaryDeliveryNoteViewSet, basename='dispensary-delivery-note')
router.register(r'dispensary/outside-treatments', DispensaryOutsideTreatmentViewSet, basename='dispensary-outside-treatment')
router.register(r'student-transfers', StudentTransferViewSet, basename='student-transfer')

# ==========================================
# URL PATTERNS
# ==========================================
urlpatterns = [
    # 1. Authentication (JWT)
    path('auth/login/', SmartCampusTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/me/', CurrentUserView.as_view(), name='current_user'),
    path('auth/role-switch/', RoleSwitchView.as_view(), name='role_switch'),

    # 2. Summary Endpoints (must come before router to avoid /students/{pk} collisions)
    path('finance/summary/', FinancialSummaryView.as_view(), name='financial_summary'),
    path('finance/reports/receivables-aging/', FinanceReceivablesAgingView.as_view(), name='finance_receivables_aging'),
    path('finance/reports/installments-aging/', FinanceInstallmentAgingView.as_view(), name='finance_installments_aging'),
    path('finance/reports/overdue-accounts/', FinanceOverdueAccountsView.as_view(), name='finance_overdue_accounts'),
    path('finance/reports/receivables-aging/export/csv/', FinanceReceivablesAgingCsvExportView.as_view(), name='finance_receivables_aging_csv'),
    path('finance/reports/overdue-accounts/export/csv/', FinanceOverdueAccountsCsvExportView.as_view(), name='finance_overdue_accounts_csv'),
    path('finance/reports/summary/export/csv/', FinanceSummaryCsvExportView.as_view(), name='finance_reports_summary_csv'),
    path('finance/reports/summary/export/pdf/', FinanceSummaryPdfExportView.as_view(), name='finance_reports_summary_pdf'),
    path('finance/accounting/trial-balance/', FinanceAccountingTrialBalanceView.as_view(), name='finance_accounting_trial_balance'),
    path('finance/accounting/ledger/', FinanceAccountingLedgerView.as_view(), name='finance_accounting_ledger'),
    path('finance/gateway/webhooks/<str:provider>/', FinanceGatewayWebhookView.as_view(), name='finance_gateway_webhook'),
    path('dashboard/routing/', DashboardRoutingView.as_view(), name='dashboard_routing'),
    path('dashboard/summary/', DashboardSummaryView.as_view(), name='dashboard_summary'),
    path('students/summary/', StudentsSummaryView.as_view(), name='students_summary'),
    path('students/dashboard/', StudentsDashboardView.as_view(), name='students_dashboard'),
    path('school/profile/', SchoolProfileView.as_view(), name='school_profile'),
    path('school/test-email/', SchoolTestEmailView.as_view(), name='school_test_email'),
    path('school/test-sms/', SchoolTestSmsView.as_view(), name='school_test_sms'),
    path('settings/control-plane/', ControlPlaneSummaryView.as_view(), name='settings_control_plane'),
    path('settings/security-policy/', SecurityPolicyView.as_view(), name='settings_security_policy'),
    path('settings/lifecycle-templates/', LifecycleTemplateListView.as_view(), name='settings_lifecycle_templates'),
    path('settings/lifecycle-runs/', LifecycleRunListCreateView.as_view(), name='settings_lifecycle_runs'),
    path('settings/lifecycle-runs/<int:run_id>/', LifecycleRunDetailView.as_view(), name='settings_lifecycle_run_detail'),
    path('settings/lifecycle-runs/<int:run_id>/start/', LifecycleRunStartView.as_view(), name='settings_lifecycle_run_start'),
    path('settings/lifecycle-runs/<int:run_id>/complete/', LifecycleRunCompleteView.as_view(), name='settings_lifecycle_run_complete'),
    path('settings/lifecycle-runs/<int:run_id>/tasks/<int:task_id>/complete/', LifecycleTaskCompleteView.as_view(), name='settings_lifecycle_task_complete'),
    path('settings/lifecycle-runs/<int:run_id>/tasks/<int:task_id>/waive/', LifecycleTaskWaiveView.as_view(), name='settings_lifecycle_task_waive'),
    path('school/demo/reset/', DemoResetView.as_view(), name='demo_reset'),
    path('school/seed/', ModuleSeedView.as_view(), name='module_seed'),
    path('students/reports/summary/', StudentsModuleReportView.as_view(), name='students_reports_summary'),
    path('students/export/csv/', StudentsDirectoryCsvExportView.as_view(), name='students_directory_csv'),
    path('students/export/pdf/', StudentsDirectoryPdfExportView.as_view(), name='students_directory_pdf'),
    path('students/documents/export/csv/', StudentsDocumentsCsvExportView.as_view(), name='students_documents_csv'),
    path('students/documents/export/pdf/', StudentsDocumentsPdfExportView.as_view(), name='students_documents_pdf'),
    path('students/reports/summary/export/csv/', StudentsModuleReportCsvExportView.as_view(), name='students_reports_summary_csv'),
    path('students/reports/summary/export/pdf/', StudentsModuleReportPdfExportView.as_view(), name='students_reports_summary_pdf'),
    path('students/<int:student_id>/operational-summary/', StudentOperationalSummaryView.as_view(), name='student_operational_summary'),
    path('students/<int:student_id>/report/', StudentReportView.as_view(), name='student_report'),
    path('students/<int:student_id>/report/export/csv/', StudentReportCsvExportView.as_view(), name='student_report_csv'),
    path('students/<int:student_id>/report/export/pdf/', StudentReportPdfExportView.as_view(), name='student_report_pdf'),
    path('school/classes/', SchoolClassListView.as_view(), name='school_classes'),
    path('attendance/capture/', include('clockin.urls_capture')),
    path('attendance/summary/', AttendanceSummaryView.as_view(), name='attendance_summary'),
    path('attendance/summary/export/csv/', AttendanceSummaryCsvExportView.as_view(), name='attendance_summary_csv'),
    path('attendance/summary/export/pdf/', AttendanceSummaryPdfExportView.as_view(), name='attendance_summary_pdf'),
    path('attendance/records/export/csv/', AttendanceRecordsCsvExportView.as_view(), name='attendance_records_csv'),
    path('attendance/records/export/pdf/', AttendanceRecordsPdfExportView.as_view(), name='attendance_records_pdf'),
    path('behavior/incidents/export/csv/', BehaviorIncidentsCsvExportView.as_view(), name='behavior_incidents_csv'),
    path('behavior/incidents/export/pdf/', BehaviorIncidentsPdfExportView.as_view(), name='behavior_incidents_pdf'),
    path('medical/records/export/csv/', MedicalProfilesCsvExportView.as_view(), name='medical_profiles_csv'),
    path('medical/records/export/pdf/', MedicalProfilesPdfExportView.as_view(), name='medical_profiles_pdf'),
    path('medical/immunizations/export/csv/', MedicalImmunizationsCsvExportView.as_view(), name='medical_immunizations_csv'),
    path('medical/immunizations/export/pdf/', MedicalImmunizationsPdfExportView.as_view(), name='medical_immunizations_pdf'),
    path('medical/visits/export/csv/', MedicalClinicVisitsCsvExportView.as_view(), name='medical_clinic_visits_csv'),
    path('medical/visits/export/pdf/', MedicalClinicVisitsPdfExportView.as_view(), name='medical_clinic_visits_pdf'),
    path('academics/current/', AcademicsCurrentContextView.as_view(), name='academics_current'),
    path('finance/optional-charges/by-class/', FinanceBulkOptionalChargeByClassView.as_view(), name='optional_charge_by_class'),
    path('academics/summary/', AcademicsSummaryView.as_view(), name='academics_summary'),
    path('hr/summary/', HrSummaryView.as_view(), name='hr_summary'),
    path('communication/summary/', CommunicationSummaryView.as_view(), name='communication_summary'),
    path('core/summary/', CoreSummaryView.as_view(), name='core_summary'),
    path('reporting/summary/', ReportingSummaryView.as_view(), name='reporting_summary'),
    path('admin/maintenance/reset-sequences/', TenantSequenceResetView.as_view(), name='tenant_reset_sequences'),

    # 3. Finance Reference Endpoints (Read-Only)
    path('finance/ref/students/', FinanceStudentRefView.as_view(), name='finance_ref_students'),
    path('finance/ref/enrollments/', FinanceEnrollmentRefView.as_view(), name='finance_ref_enrollments'),
    path('finance/ref/classes/', FinanceClassRefView.as_view(), name='finance_ref_classes'),
    path('finance/fee-assignments/by-class/', FinanceBulkFeeAssignByClassView.as_view(), name='fee_assign_by_class'),
    path('finance/cashbook/summary/', CashbookSummaryView.as_view(), name='finance_cashbook_summary'),
    path('finance/reports/arrears/', FinanceArrearsView.as_view(), name='finance_arrears_report'),
    path('finance/reports/vote-head-allocation/', FinanceVoteHeadAllocationReportView.as_view(), name='finance_vote_head_allocation_report'),
    path('finance/reports/class-balances/', FinanceClassBalancesReportView.as_view(), name='finance_class_balances_report'),
    path('finance/reports/arrears-by-term/', FinanceArrearsByTermReportView.as_view(), name='finance_arrears_by_term_report'),
    path('finance/reports/budget-variance/', FinanceBudgetVarianceReportView.as_view(), name='finance_budget_variance_report'),
    path('finance/reports/vote-head-budget/', FinanceVoteHeadBudgetReportView.as_view(), name='finance_vote_head_budget_report'),
    path('finance/payments/<int:pk>/receipt/pdf/', FinanceReceiptPdfView.as_view(), name='finance_receipt_pdf'),
    path('finance/students/<int:student_id>/ledger/', FinanceStudentLedgerView.as_view(), name='finance_student_ledger'),

    # Store module
    path('store/orders/<int:pk>/review/', StoreOrderReviewView.as_view(), name='store_order_review'),
    path('store/dashboard/', StoreDashboardView.as_view(), name='store_dashboard'),
    path('store/reports/', StoreReportsView.as_view(), name='store_reports'),

    # Dispensary module
    path('dispensary/dashboard/', DispensaryDashboardView.as_view(), name='dispensary_dashboard'),

    # User management
    path('users/roles/', RoleListView.as_view(), name='user_roles'),
    path('users/role-modules/', RoleModuleAccessView.as_view(), name='role_module_access'),
    path('users/submodule-permissions/', SubmodulePermissionView.as_view(), name='submodule_permissions'),
    path('users/student-search/', StudentSearchForUserCreateView.as_view(), name='user_student_search'),
    path('users/students-by-class/', StudentsByClassForUserCreateView.as_view(), name='user_students_by_class'),
    path('users/bulk-create-students/', BulkCreateStudentUsersView.as_view(), name='user_bulk_create_students'),
    path('users/', UserManagementListCreateView.as_view(), name='user_list_create'),
    path('users/<int:user_id>/', UserManagementDetailView.as_view(), name='user_detail'),

    # 4. Module Apps (Read-Only Reference Contracts)
    path('tenant/modules', TenantModuleListView.as_view(), name='tenant_modules'),
    path('tenant/modules/<int:module_id>/settings', TenantModuleSettingsView.as_view(), name='tenant_module_settings'),
    path('staff/', include('staff_mgmt.urls')),
    path('admissions/', include('admissions.urls')),
    path('academics/', include('academics.urls')),
    path('hr/', include('hr.urls')),
    path('assets/', include('assets.urls')),
    path('communication/', include('communication.urls')),
    path('library/', include('library.urls')),
    path('parent-portal/', include('parent_portal.urls')),
    path('student-portal/', include('parent_portal.student_portal_urls')),
    path('teacher-portal/', include('parent_portal.teacher_portal_urls')),
    path('portal/', include('parent_portal.student_portal_portal_urls')),
    path('reporting/', include('reporting.urls')),
    path('clockin/', include('clockin.urls')),
    path('timetable/', include('timetable.urls')),
    path('transport/', include('transport.urls')),
    path('visitors/', include('visitor_mgmt.urls')),
    path('examinations/', include('examinations.urls')),
    path('alumni/', include('alumni.urls')),
    path('hostel/', include('hostel.urls')),
    path('ptm/', include('ptm.urls')),
    path('sports/', include('sports.urls')),
    path('cafeteria/', include('cafeteria.urls')),
    path('curriculum/', include('curriculum.urls')),
    path('maintenance/', include('maintenance.urls')),
    path('elearning/', include('elearning.urls')),
    path('analytics/', include('analytics.urls')),

    # 5. Tenant API Routes (Router)
    path('', include(router.urls)),

    # â”€â”€ Phase 11 + 16 Advanced RBAC API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # â”€â”€ Transfer System â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    path('transfers/',                                  TransferListView.as_view(),         name='transfer_list'),
    path('transfers/initiate/',                         TransferInitiateView.as_view(),     name='transfer_initiate'),
    path('transfers/<int:transfer_id>/',                TransferDetailView.as_view(),       name='transfer_detail'),
    path('transfers/<int:transfer_id>/approve-from/',   TransferApproveFromView.as_view(),  name='transfer_approve_from'),
    path('transfers/<int:transfer_id>/approve-to/',     TransferApproveToView.as_view(),    name='transfer_approve_to'),
    path('transfers/<int:transfer_id>/reject/',         TransferRejectView.as_view(),       name='transfer_reject'),
    path('transfers/<int:transfer_id>/cancel/',         TransferCancelView.as_view(),       name='transfer_cancel'),
    path('transfers/<int:transfer_id>/execute/',        TransferExecuteView.as_view(),      name='transfer_execute'),
    path('transfers/<int:transfer_id>/package/',        TransferPackageView.as_view(),      name='transfer_package'),
    path('students/<int:student_id>/transfer-history/', StudentTransferHistoryView.as_view(), name='student_transfer_history'),
    path('staff/<int:employee_id>/transfer-history/',   StaffTransferHistoryView.as_view(),   name='staff_transfer_history'),
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # â”€â”€ Settings & Admission System â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    path('settings/admission/',             AdmissionSettingsView.as_view(),        name='admission_settings'),
    path('settings/admission/preview/',     AdmissionNumberPreviewView.as_view(),   name='admission_number_preview'),
    path('settings/media/upload/',          MediaUploadView.as_view(),              name='media_upload'),
    path('settings/media/',                 MediaFileListView.as_view(),            name='media_list'),
    path('settings/import/<str:module>/template/', ImportTemplateDownloadView.as_view(), name='import_template'),
    path('settings/import/students/',       StudentsBulkImportView.as_view(),       name='students_bulk_import'),
    path('settings/import/staff/',          StaffBulkImportView.as_view(),          name='staff_bulk_import'),
    path('settings/finance/',               FinanceSettingsView.as_view(),          name='finance_settings'),
    path('settings/general/',               GeneralSettingsView.as_view(),          name='general_settings'),
    path('settings/',                       TenantSettingsView.as_view(),           name='tenant_settings'),
    path('settings/kv/<str:setting_key>/',  TenantSettingDeleteView.as_view(),      name='tenant_setting_delete'),
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    path('rbac/permissions/',               RbacPermissionListView.as_view(),   name='rbac_permission_list'),
    path('rbac/permissions/seed/',          RbacPermissionSeedView.as_view(),   name='rbac_permission_seed'),
    path('rbac/roles/',                     RbacRoleListView.as_view(),         name='rbac_role_list'),
    path('rbac/roles/<int:role_id>/grant/', RbacRoleGrantPermissionView.as_view(), name='rbac_role_grant'),
    path('rbac/roles/<int:role_id>/revoke/',RbacRoleRevokePermissionView.as_view(), name='rbac_role_revoke'),
    path('rbac/users/<int:user_id>/permissions/', RbacUserEffectivePermissionsView.as_view(), name='rbac_user_effective_permissions'),
    path('rbac/users/<int:user_id>/overrides/',   RbacUserOverrideListView.as_view(),         name='rbac_user_overrides'),
    path('rbac/users/<int:user_id>/overrides/<int:permission_id>/', RbacUserOverrideDeleteView.as_view(), name='rbac_user_override_delete'),
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # â”€â”€ Custom Domain Onboarding â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    path('settings/domain/',                SchoolDomainStatusView.as_view(),   name='school_domain_status'),
    path('settings/domain/request/',        SchoolDomainRequestView.as_view(),  name='school_domain_request'),
    path('settings/domain/verify/',         SchoolDomainVerifyView.as_view(),   name='school_domain_verify'),
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
]






