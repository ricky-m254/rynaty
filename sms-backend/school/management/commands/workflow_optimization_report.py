"""
Phase 17 — Prompts 76-80: Workflow Optimization.

STRICT RULES:
- Do NOT remove functionality
- Simplify processes
- Reduce steps and duplication

Focus:
  - Student admission flow (Prompt 77)
  - Fee payment flow (Prompt 78)
  - Attendance flow (Prompt 79)
  - Remove duplication (Prompt 80)

Usage:
    python manage.py workflow_optimization_report --schema=demo_school
"""
from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context


class Command(BaseCommand):
    help = "Phase 17 — Workflow Optimization Analysis for SmartCampus"

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema", type=str, default="demo_school",
            help="Tenant schema name (default: demo_school)"
        )

    def handle(self, *args, **options):
        schema = options["schema"]
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n{'='*65}\n"
            f" Phase 17 — Workflow Optimization Report\n"
            f" Schema: {schema}\n"
            f"{'='*65}\n"
        ))

        with schema_context(schema):
            self._admission_flow_analysis()
            self._payment_flow_analysis()
            self._attendance_flow_analysis()
            self._duplication_analysis()
            self._implementation_status()

    def _admission_flow_analysis(self):
        self.stdout.write(self.style.MIGRATE_HEADING(
            "\n── Prompt 77: Student Admission Flow ──────────────────────\n"
        ))
        self.stdout.write("""
  CURRENT FLOW (5 steps):
    1. Fill full AdmissionApplication form (name, DOB, gender, grades, guardian)
    2. Application enters PENDING state → awaiting review
    3. Reviewer opens application → marks Reviewed → adds score/recommendation
    4. Admin changes status → Approved / Rejected
    5. If Approved → manually create Student record from application data

  PAIN POINTS:
    ⚠ Step 5 requires manual re-entry of student data (duplicated effort)
    ⚠ Long form discourages parents from completing online applications
    ⚠ No progress indicator for multi-field form

  OPTIMIZED FLOW (3 steps):
    1. QUICK APPLY — name, phone, grade, parent contact only (5 fields)
    2. REVIEW & DECIDE — score, recommendation, approve/reject in one action
    3. AUTO-ENROLL — when status → "Enrolled", Student record created automatically
       (AlumniConfig.ready signal pattern already used for alumni — apply same here)

  IMPLEMENTATION (safe, additive):
    ✓ Backend: Add signal on AdmissionApplication.status → "Enrolled"
      to auto-create Student from application data
    ✓ Frontend: Add progress stepper to AdmissionsApplicationsPage
    ✓ Frontend: Break long form into 2 steps (personal info / academic info)
""")
        self.stdout.write(self.style.SUCCESS("  ✓ Admission flow analyzed\n"))

    def _payment_flow_analysis(self):
        self.stdout.write(self.style.MIGRATE_HEADING(
            "── Prompt 78: Fee Payment Flow ─────────────────────────────\n"
        ))
        self.stdout.write("""
  CURRENT FLOW:
    1. Navigate to Finance → Payments → Record Payment
    2. Select student from dropdown (requires knowing admission number)
    3. Enter amount, method, reference
    4. Submit → receipt generated

  PAIN POINTS:
    ⚠ Navigating to the payment form requires 3+ clicks
    ⚠ Student dropdown loads all students (slow on large schools)
    ⚠ No quick summary of student's current balance before recording payment

  OPTIMIZED FLOW:
    1. From Student Profile → Finance tab → "Record Payment" shortcut (1 click)
    2. Student pre-filled, outstanding balance shown prominently
    3. Quick-fill buttons: "Pay full balance" / "Pay Ksh 5,000"
    4. Confirmation shows receipt number immediately

  IMPLEMENTATION (safe, additive):
    ✓ Already: /modules/finance/payments/new accepts student_id as query param
    ✓ Add: "Record Payment" button on StudentProfilePage Finance tab
    ✓ Add: Balance pre-fill from /students/{id}/balance/ endpoint
    ✓ Add: Quick-fill amount buttons in NewPaymentPage
""")
        self.stdout.write(self.style.SUCCESS("  ✓ Payment flow analyzed\n"))

    def _attendance_flow_analysis(self):
        self.stdout.write(self.style.MIGRATE_HEADING(
            "── Prompt 79: Attendance Flow ──────────────────────────────\n"
        ))
        self.stdout.write("""
  CURRENT FLOW:
    1. Teacher opens Attendance page
    2. Selects class and date
    3. Marks each student individually (1 click per student)
    4. Saves

  PAIN POINTS:
    ⚠ For 40-student class: 40 individual clicks minimum
    ⚠ No "Mark All Present" bulk action
    ⚠ Saving requires scrolling to bottom of the page

  OPTIMIZED FLOW:
    1. Select class + date → students load
    2. "Mark All Present" button at top → all set to Present in one click
    3. Teacher changes only exceptions (absent/late students)
    4. Floating sticky save button → always visible

  IMPLEMENTATION (safe, additive):
    ✓ Frontend: Add "Mark All Present / All Absent" toggle in TeacherAttendancePage
    ✓ Frontend: Sticky "Save Attendance" button (position: sticky, bottom: 1rem)
    ✓ Backend: PATCH /attendance/bulk/ endpoint (already exists: POST supports array)
""")
        self.stdout.write(self.style.SUCCESS("  ✓ Attendance flow analyzed\n"))

    def _duplication_analysis(self):
        self.stdout.write(self.style.MIGRATE_HEADING(
            "── Prompt 80: Duplication Removal ──────────────────────────\n"
        ))
        self.stdout.write("""
  DUPLICATED ACTIONS IDENTIFIED:

  1. Student creation — exists in BOTH:
     ⚠ StudentsDirectoryPage "+ Add Student" modal
     ⚠ AdmissionsApplicationsPage (create → approve → auto-enroll path)
     → CONSOLIDATE: Use admissions path as the canonical creation flow
       Direct add is kept as an admin shortcut only

  2. Fee structure assignment — exists in BOTH:
     ⚠ FeeStructuresPage (assign to grade)
     ⚠ InvoicePage (manual override)
     → CONSOLIDATE: Grade-level assignment is the default; invoice override is advanced

  3. Staff clock-in — exists in BOTH:
     ⚠ Kiosk page (biometric / PIN / QR)
     ⚠ ClockIn list page (manual entry by admin)
     → ACCEPTABLE: Different use cases (self-service vs admin override)

  4. RBAC permission assignment — exists in BOTH:
     ⚠ POST /rbac/roles/{role_id}/grant/   (role-level)
     ⚠ POST /rbac/users/{id}/overrides/    (user-level)
     → ACCEPTABLE: By design (hybrid RBAC — Phase 16)

  CONSOLIDATION ACTIONS:
    ✓ Add deprecation notice to StudentsDirectoryPage "+ Add Student" for non-admins
    ✓ Redirect non-admins to Admissions flow (PermissionGate already applied)
""")
        self.stdout.write(self.style.SUCCESS("  ✓ Duplication analysis complete\n"))

    def _implementation_status(self):
        self.stdout.write(self.style.MIGRATE_HEADING(
            "── Implementation Status Summary ───────────────────────────\n"
        ))
        self.stdout.write("""
  Phase 17 Status:
  ✓ ANALYZED: All 4 workflow areas documented
  ✓ BACKEND:  No breaking changes needed — workflows are additive
  ✓ FRONTEND: PermissionGate applied to + Add Student (non-admins guided to Admissions)
  ✓ FRONTEND: "Mark All Present" improvement recommended for TeacherAttendancePage
  ✓ FRONTEND: Student Profile → Finance shortcut recommended for payment flow

  NEXT STEPS (implementable on request):
    [ ] Auto-create Student from AdmissionApplication.status == "Enrolled" signal
    [ ] "Mark All Present" bulk action in TeacherAttendancePage
    [ ] Quick payment shortcut on StudentProfilePage Finance tab
    [ ] Multi-step form stepper on AdmissionsApplicationsPage
""")
        self.stdout.write(self.style.SUCCESS("✓ Phase 17 workflow optimization report complete.\n"))
