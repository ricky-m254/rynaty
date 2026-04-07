from django.contrib import admin
from .models import (
    # Core Admin
    SchoolProfile, Role, UserProfile, Module, UserModuleAssignment,
    # Students
    Student, Guardian, Enrollment,
    # Finance
    FeeStructure, Invoice, InvoiceLineItem, Payment, PaymentAllocation, Expense,
    FeeAssignment, InvoiceAdjustment,
    # Phase 16 Advanced RBAC
    Permission, RolePermissionGrant, UserPermissionOverride,
)

# ==========================================
# 1. CORE ADMINISTRATION
# ==========================================
@admin.register(SchoolProfile)
class SchoolProfileAdmin(admin.ModelAdmin):
    list_display = ['school_name', 'phone', 'is_active']
    search_fields = ['school_name']

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    search_fields = ['name']

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'phone']
    search_fields = ['user__username', 'user__email']

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ['key', 'name', 'is_active', 'created_at']
    search_fields = ['key', 'name']

@admin.register(UserModuleAssignment)
class UserModuleAssignmentAdmin(admin.ModelAdmin):
    list_display = ['user', 'module', 'is_active', 'assigned_at']
    search_fields = ['user__username', 'module__key']
    list_filter = ['is_active', 'module']

# ==========================================
# 2. STUDENT MANAGEMENT
# ==========================================
class GuardianInline(admin.TabularInline):
    model = Guardian
    extra = 0

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['admission_number', 'first_name', 'last_name', 'gender', 'is_active']
    search_fields = ['admission_number', 'first_name', 'last_name']
    list_filter = ['gender', 'is_active']
    inlines = [GuardianInline]

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'school_class', 'term', 'enrollment_date']
    list_filter = ['term', 'school_class']

# ==========================================
# 5. FINANCE (PRIMARY)
# ==========================================
class InvoiceLineItemInline(admin.TabularInline):
    model = InvoiceLineItem
    extra = 0
    readonly_fields = ['invoice'] # Prevent changing invoice link

@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ['name', 'amount', 'term', 'is_active']
    list_filter = ['term']

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['id', 'student', 'term', 'total_amount', 'status', 'balance_due_display', 'created_at']
    list_filter = ['status', 'term', 'created_at']
    search_fields = ['student__admission_number', 'student__first_name']
    readonly_fields = ['invoice_date', 'created_at', 'balance_due_display']
    inlines = [InvoiceLineItemInline]

    def balance_due_display(self, obj):
        # Display the derived balance in the list view
        return f"${obj.balance_due}"
    balance_due_display.short_description = 'Balance Due'

class PaymentAllocationInline(admin.TabularInline):
    model = PaymentAllocation
    extra = 0
    readonly_fields = ['allocated_at']

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['reference_number', 'student', 'amount', 'payment_method', 'is_active', 'payment_date']
    list_filter = ['payment_method', 'is_active', 'payment_date']
    search_fields = ['reference_number', 'student__admission_number']
    readonly_fields = ['payment_date']
    inlines = [PaymentAllocationInline]

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['category', 'amount', 'expense_date', 'description']
    list_filter = ['category', 'expense_date']

@admin.register(FeeAssignment)
class FeeAssignmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'fee_structure', 'discount_amount', 'is_active']
    search_fields = ['student__admission_number', 'fee_structure__name']

@admin.register(InvoiceAdjustment)
class InvoiceAdjustmentAdmin(admin.ModelAdmin):
    list_display = ['invoice', 'amount', 'reason', 'adjusted_by', 'created_at']
    readonly_fields = ['created_at', 'adjusted_by']


# ==========================================
# Phase 16 Advanced RBAC Admin
# ==========================================

class RolePermissionGrantInline(admin.TabularInline):
    model = RolePermissionGrant
    extra = 0
    autocomplete_fields = ['permission']


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ['name', 'module', 'action', 'description']
    list_filter = ['module', 'action']
    search_fields = ['name', 'module', 'description']
    ordering = ['module', 'name']


@admin.register(RolePermissionGrant)
class RolePermissionGrantAdmin(admin.ModelAdmin):
    list_display = ['role', 'permission']
    list_filter = ['role']
    autocomplete_fields = ['permission']


@admin.register(UserPermissionOverride)
class UserPermissionOverrideAdmin(admin.ModelAdmin):
    list_display = ['user', 'permission', 'is_allowed', 'reason', 'created_at']
    list_filter = ['is_allowed', 'permission__module']
    search_fields = ['user__username', 'permission__name', 'reason']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['permission']

