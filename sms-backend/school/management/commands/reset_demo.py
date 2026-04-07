"""
Management command: reset demo_school tenant to original Kenya school seed data.
Wipes all user-created records and reseeds from scratch.
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django_tenants.utils import schema_context
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Reset demo_school tenant data to original Kenya school seed."

    def add_arguments(self, parser):
        parser.add_argument("--schema", type=str, default="demo_school")

    def handle(self, *args, **options):
        schema = options["schema"]
        self.stdout.write(self.style.WARNING(f"Resetting demo data for schema: {schema}"))

        with schema_context(schema):
            from school.models import (
                Student, Guardian, Enrollment, FeeStructure, Invoice,
                InvoiceLineItem, Payment, PaymentAllocation, Expense,
                SchoolProfile, Department, Subject,
                GradingScheme, GradeBand,
                Assessment, AssessmentGrade, TermResult, ReportCard,
            )
            from school.models import AcademicYear, Term, SchoolClass
            from hr.models import Staff
            from admissions.models import AdmissionApplication
            from maintenance.models import MaintenanceRequest
            from examinations.models import ExamSession, ExamPaper, ExamGradeBoundary

            # ── Gradebook / report cards ─────────────────────────────────────
            self.stdout.write("Clearing gradebook records...")
            AssessmentGrade.objects.all().delete()
            TermResult.objects.all().delete()
            ReportCard.objects.all().delete()
            Assessment.objects.all().delete()
            GradeBand.objects.all().delete()
            GradingScheme.objects.all().delete()

            # ── Examinations ─────────────────────────────────────────────────
            self.stdout.write("Clearing examination records...")
            ExamGradeBoundary.objects.all().delete()
            ExamPaper.objects.all().delete()
            ExamSession.objects.all().delete()

            # ── Finance ──────────────────────────────────────────────────────
            self.stdout.write("Clearing finance records...")
            from school.models import VoteHead, Budget
            PaymentAllocation.objects.all().delete()
            Payment.objects.all().delete()
            InvoiceLineItem.objects.all().delete()
            Invoice.objects.all().delete()
            Expense.objects.all().delete()
            Budget.objects.all().delete()
            FeeStructure.objects.all().delete()
            VoteHead.objects.all().delete()

            # ── Students / Staff ─────────────────────────────────────────────
            self.stdout.write("Clearing student records...")
            Enrollment.objects.all().delete()
            Guardian.objects.all().delete()
            Student.objects.all().delete()

            self.stdout.write("Clearing staff records...")
            Staff.objects.all().delete()

            # ── Curriculum ───────────────────────────────────────────────────
            self.stdout.write("Clearing curriculum records...")
            Subject.objects.all().delete()
            Department.objects.all().delete()

            # ── E-Learning (must be before academic structures due to Term FK) ──
            self.stdout.write("Clearing e-learning records...")
            try:
                from elearning.models import QuizAttempt, QuizQuestion, OnlineQuiz, CourseMaterial, Course
                QuizAttempt.objects.all().delete()
                QuizQuestion.objects.all().delete()
                OnlineQuiz.objects.all().delete()
                CourseMaterial.objects.all().delete()
                Course.objects.all().delete()
            except Exception as e:
                self.stdout.write(f"  E-learning clear warning: {e}")
                # Fallback: use raw SQL to clear FK constraint
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM elearning_quizattempt")
                    cursor.execute("DELETE FROM elearning_quizquestion")
                    cursor.execute("DELETE FROM elearning_onlinequiz")
                    cursor.execute("DELETE FROM elearning_coursematerial")
                    cursor.execute("DELETE FROM elearning_course")

            # ── Timetable (before Term/Class) ────────────────────────────────
            self.stdout.write("Clearing timetable records...")
            try:
                from timetable.models import Period, StaffDutySlot
                Period.objects.all().delete()
                StaffDutySlot.objects.all().delete()
            except Exception:
                pass

            # ── Curriculum (before Term/Subject) ─────────────────────────────
            self.stdout.write("Clearing curriculum (schemes, lesson plans)...")
            try:
                from curriculum.models import LearningResource, LessonPlan, SchemeTopic, SchemeOfWork
                LearningResource.objects.all().delete()
                LessonPlan.objects.all().delete()
                SchemeTopic.objects.all().delete()
                SchemeOfWork.objects.all().delete()
            except Exception:
                pass

            # ── Clear ALL remaining FK references to school_term before deletion
            self.stdout.write("Clearing all remaining Term-linked records...")
            try:
                from ptm.models import PTMBooking, PTMSlot, PTMSession
                PTMBooking.objects.all().delete()
                PTMSlot.objects.all().delete()
                PTMSession.objects.all().delete()
            except Exception:
                pass
            try:
                from admissions.models import (
                    AdmissionDecision, AdmissionInterview, AdmissionAssessment,
                    AdmissionReview, AdmissionApplicationProfile, AdmissionInquiry,
                )
                AdmissionDecision.objects.all().delete()
                AdmissionInterview.objects.all().delete()
                AdmissionAssessment.objects.all().delete()
                AdmissionReview.objects.all().delete()
                AdmissionApplicationProfile.objects.all().delete()
                AdmissionInquiry.objects.all().delete()
            except Exception:
                pass
            try:
                from cafeteria.models import StudentMealEnrollment, CafeteriaWalletTransaction, MealTransaction
                StudentMealEnrollment.objects.all().delete()
                CafeteriaWalletTransaction.objects.all().delete()
                MealTransaction.objects.all().delete()
            except Exception:
                pass
            try:
                from hostel.models import HostelAllocation, HostelLeave, HostelAttendance
                HostelAllocation.objects.all().delete()
                HostelLeave.objects.all().delete()
                HostelAttendance.objects.all().delete()
            except Exception:
                pass
            try:
                from transport.models import StudentTransport
                StudentTransport.objects.all().delete()
            except Exception:
                pass
            # Use raw SQL to null-out any remaining school_term FKs we can't find by model
            from django.db import connection
            term_fk_tables = [
                "school_balancecarryforward", "school_calendarevent",
                "school_institutionlifecyclerun", "school_optionalcharge",
                "school_syllabustopic", "school_teacherassignment",
            ]
            with connection.cursor() as cursor:
                for tbl in term_fk_tables:
                    try:
                        cursor.execute(f"DELETE FROM {tbl}")
                    except Exception:
                        pass

            # ── Academic structures ──────────────────────────────────────────
            self.stdout.write("Clearing academic structures...")
            SchoolClass.objects.all().delete()
            Term.objects.all().delete()
            AcademicYear.objects.all().delete()

            # ── Admissions / Maintenance ──────────────────────────────────────
            self.stdout.write("Clearing admissions & maintenance...")
            try:
                AdmissionApplication.objects.all().delete()
            except Exception:
                pass
            try:
                MaintenanceRequest.objects.all().delete()
            except Exception:
                pass

            # ── Library ───────────────────────────────────────────────────────
            self.stdout.write("Clearing library records...")
            try:
                from library.models import (
                    LibraryMember, CirculationTransaction, Reservation,
                    FineRecord, ResourceCopy, LibraryResource, LibraryCategory, CirculationRule,
                )
                CirculationTransaction.objects.all().delete()
                Reservation.objects.all().delete()
                FineRecord.objects.all().delete()
                LibraryMember.objects.all().delete()
                ResourceCopy.objects.all().delete()
                LibraryResource.objects.all().delete()
                LibraryCategory.objects.all().delete()
                CirculationRule.objects.all().delete()
            except Exception:
                pass

            # ── Cafeteria ─────────────────────────────────────────────────────
            self.stdout.write("Clearing cafeteria records...")
            try:
                from cafeteria.models import (
                    StudentMealEnrollment, MealTransaction, CafeteriaWalletTransaction,
                    WeeklyMenu, MealPlan,
                )
                CafeteriaWalletTransaction.objects.all().delete()
                MealTransaction.objects.all().delete()
                StudentMealEnrollment.objects.all().delete()
                WeeklyMenu.objects.all().delete()
                MealPlan.objects.all().delete()
            except Exception:
                pass

            # ── Sports ────────────────────────────────────────────────────────
            self.stdout.write("Clearing sports records...")
            try:
                from sports.models import StudentAward, ClubMembership, Tournament, Club
                StudentAward.objects.all().delete()
                ClubMembership.objects.all().delete()
                Tournament.objects.all().delete()
                Club.objects.all().delete()
            except Exception:
                pass

            # ── Assets ────────────────────────────────────────────────────────
            self.stdout.write("Clearing asset records...")
            try:
                from assets.models import AssetDepreciation, AssetMaintenanceRecord, AssetAssignment, Asset, AssetCategory
                AssetDepreciation.objects.all().delete()
                AssetMaintenanceRecord.objects.all().delete()
                AssetAssignment.objects.all().delete()
                Asset.objects.all().delete()
                AssetCategory.objects.all().delete()
            except Exception:
                pass

            # ── Transport ─────────────────────────────────────────────────────
            self.stdout.write("Clearing transport records...")
            try:
                from transport.models import StudentTransport, TransportIncident, RouteStop, Route, Vehicle
                StudentTransport.objects.all().delete()
                TransportIncident.objects.all().delete()
                RouteStop.objects.all().delete()
                Route.objects.all().delete()
                Vehicle.objects.all().delete()
            except Exception:
                pass

            # ── Hostel ────────────────────────────────────────────────────────
            self.stdout.write("Clearing hostel records...")
            try:
                from hostel.models import HostelLeave, HostelAttendance, HostelAllocation, BedSpace, Dormitory
                HostelLeave.objects.all().delete()
                HostelAttendance.objects.all().delete()
                HostelAllocation.objects.all().delete()
                BedSpace.objects.all().delete()
                Dormitory.objects.all().delete()
            except Exception:
                pass

            # ── Timetable ─────────────────────────────────────────────────────
            self.stdout.write("Clearing timetable records...")
            try:
                from timetable.models import LessonCoverage, TimetableChangeRequest, StaffDutySlot, TimetableSlot
                LessonCoverage.objects.all().delete()
                TimetableChangeRequest.objects.all().delete()
                StaffDutySlot.objects.all().delete()
                TimetableSlot.objects.all().delete()
            except Exception:
                pass

            # ── Visitor management ────────────────────────────────────────────
            self.stdout.write("Clearing visitor records...")
            try:
                from visitor_mgmt.models import StudentPickupLog, AuthorizedPickup, Visitor
                StudentPickupLog.objects.all().delete()
                AuthorizedPickup.objects.all().delete()
                Visitor.objects.all().delete()
            except Exception:
                pass

            # ── Communication ─────────────────────────────────────────────────
            self.stdout.write("Clearing communication records...")
            try:
                from communication.models import Message
                from communication.models import Announcement
                Message.objects.all().delete()
                Announcement.objects.all().delete()
            except Exception:
                pass

            # ── School profile ────────────────────────────────────────────────
            self.stdout.write("Clearing school profile...")
            SchoolProfile.objects.all().delete()

            # ── Examinations ─────────────────────────────────────────────────
            self.stdout.write("Clearing examination session data...")
            try:
                from examinations.models import ExamResult, ExamSeatAllocation, ExamGradeBoundary, ExamPaper, ExamSession
                ExamResult.objects.all().delete()
                ExamSeatAllocation.objects.all().delete()
                ExamGradeBoundary.objects.all().delete()
                ExamPaper.objects.all().delete()
                ExamSession.objects.all().delete()
            except Exception:
                pass

            # ── Alumni ────────────────────────────────────────────────────────
            self.stdout.write("Clearing alumni records...")
            try:
                from alumni.models import AlumniDonation, AlumniMentorship, AlumniEventAttendee, AlumniEvent, AlumniProfile
                AlumniDonation.objects.all().delete()
                AlumniMentorship.objects.all().delete()
                AlumniEventAttendee.objects.all().delete()
                AlumniEvent.objects.all().delete()
                AlumniProfile.objects.all().delete()
            except Exception:
                pass

            # ── PTM ──────────────────────────────────────────────────────────
            self.stdout.write("Clearing PTM records...")
            try:
                from ptm.models import PTMBooking, PTMSlot, PTMSession
                PTMBooking.objects.all().delete()
                PTMSlot.objects.all().delete()
                PTMSession.objects.all().delete()
            except Exception:
                pass

            # ── Clock-in ─────────────────────────────────────────────────────
            self.stdout.write("Clearing clock-in records...")
            try:
                from clockin.models import ClockEvent, PersonRegistry, SchoolShift
                ClockEvent.objects.all().delete()
                PersonRegistry.objects.all().delete()
                SchoolShift.objects.all().delete()
            except Exception:
                pass

            # ── Parent portal ─────────────────────────────────────────────────
            self.stdout.write("Clearing parent portal links...")
            try:
                from parent_portal.models import ParentStudentLink
                ParentStudentLink.objects.all().delete()
                # Remove seeded parent portal users (username starts with 'parent.')
                from django.contrib.auth import get_user_model
                get_user_model().objects.filter(username__startswith="parent.").delete()
            except Exception:
                pass

            # ── Admissions pipeline ───────────────────────────────────────────
            self.stdout.write("Clearing admissions pipeline...")
            try:
                from admissions.models import (
                    AdmissionDecision, AdmissionInterview, AdmissionAssessment,
                    AdmissionReview, AdmissionApplicationProfile, AdmissionInquiry,
                )
                AdmissionDecision.objects.all().delete()
                AdmissionInterview.objects.all().delete()
                AdmissionAssessment.objects.all().delete()
                AdmissionReview.objects.all().delete()
                AdmissionApplicationProfile.objects.all().delete()
                AdmissionInquiry.objects.all().delete()
            except Exception:
                pass

            # ── Curriculum ────────────────────────────────────────────────────
            self.stdout.write("Clearing curriculum...")
            try:
                from curriculum.models import LearningResource, LessonPlan, SchemeTopic, SchemeOfWork
                LearningResource.objects.all().delete()
                LessonPlan.objects.all().delete()
                SchemeTopic.objects.all().delete()
                SchemeOfWork.objects.all().delete()
            except Exception:
                pass

            # ── HR comprehensive ──────────────────────────────────────────────
            self.stdout.write("Clearing comprehensive HR records...")
            try:
                from hr.models import (
                    DisciplinaryCase, TrainingEnrollment, TrainingProgram,
                    PerformanceReview, PerformanceGoal, OnboardingTask,
                    Interview as HrInterview, JobApplication, JobPosting,
                    PayrollItem, PayrollBatch, SalaryComponent, SalaryStructure,
                    LeaveRequest, LeaveBalance, LeavePolicy,
                    WorkSchedule, AttendanceRecord, ShiftTemplate,
                    EmergencyContact, EmployeeQualification, EmployeeEmploymentProfile,
                )
                DisciplinaryCase.objects.all().delete()
                TrainingEnrollment.objects.all().delete()
                TrainingProgram.objects.all().delete()
                PerformanceReview.objects.all().delete()
                PerformanceGoal.objects.all().delete()
                OnboardingTask.objects.all().delete()
                HrInterview.objects.all().delete()
                JobApplication.objects.all().delete()
                JobPosting.objects.all().delete()
                PayrollItem.objects.all().delete()
                PayrollBatch.objects.all().delete()
                SalaryComponent.objects.all().delete()
                SalaryStructure.objects.all().delete()
                LeaveRequest.objects.all().delete()
                LeaveBalance.objects.all().delete()
                LeavePolicy.objects.all().delete()
                AttendanceRecord.objects.all().delete()
                WorkSchedule.objects.all().delete()
                ShiftTemplate.objects.all().delete()
                EmergencyContact.objects.all().delete()
                EmployeeQualification.objects.all().delete()
                EmployeeEmploymentProfile.objects.all().delete()
            except Exception:
                pass

            # ── Staff management comprehensive ────────────────────────────────
            self.stdout.write("Clearing staff management records...")
            try:
                from staff_mgmt.models import (
                    StaffAppraisal, StaffObservation, StaffAttendance,
                    StaffAssignment, StaffRole, StaffDepartment,
                    StaffEmergencyContact, StaffQualification,
                )
                StaffAppraisal.objects.all().delete()
                StaffObservation.objects.all().delete()
                StaffAttendance.objects.all().delete()
                StaffAssignment.objects.all().delete()
                StaffRole.objects.all().delete()
                StaffDepartment.objects.all().delete()
                StaffEmergencyContact.objects.all().delete()
                StaffQualification.objects.all().delete()
            except Exception:
                pass

            # ── Communication comprehensive ───────────────────────────────────
            self.stdout.write("Clearing comprehensive communication records...")
            try:
                from communication.models import (
                    SmsMessage, EmailCampaign, NotificationPreference,
                    Notification, CommunicationMessage, ConversationParticipant,
                    Conversation, MessageTemplate,
                )
                SmsMessage.objects.all().delete()
                EmailCampaign.objects.all().delete()
                NotificationPreference.objects.all().delete()
                Notification.objects.all().delete()
                CommunicationMessage.objects.all().delete()
                ConversationParticipant.objects.all().delete()
                Conversation.objects.all().delete()
                MessageTemplate.objects.all().delete()
            except Exception:
                pass

            # ── Assets comprehensive ──────────────────────────────────────────
            self.stdout.write("Clearing comprehensive asset records...")
            try:
                from assets.models import AssetDepreciation, AssetWarranty, AssetMaintenanceRecord, AssetAssignment
                AssetDepreciation.objects.all().delete()
                AssetWarranty.objects.all().delete()
                AssetMaintenanceRecord.objects.all().delete()
                AssetAssignment.objects.all().delete()
            except Exception:
                pass

            # ── Cafeteria comprehensive ───────────────────────────────────────
            self.stdout.write("Clearing cafeteria transaction records...")
            try:
                from cafeteria.models import CafeteriaWalletTransaction, MealTransaction
                CafeteriaWalletTransaction.objects.all().delete()
                MealTransaction.objects.all().delete()
            except Exception:
                pass

            # ── Hostel comprehensive ──────────────────────────────────────────
            self.stdout.write("Clearing hostel attendance and leave records...")
            try:
                from hostel.models import HostelLeave, HostelAttendance
                HostelLeave.objects.all().delete()
                HostelAttendance.objects.all().delete()
            except Exception:
                pass

            # ── Timetable duty slots ──────────────────────────────────────────
            self.stdout.write("Clearing timetable duty slots...")
            try:
                from timetable.models import StaffDutySlot
                StaffDutySlot.objects.all().delete()
            except Exception:
                pass

            # ── Transport incidents ───────────────────────────────────────────
            self.stdout.write("Clearing transport incidents...")
            try:
                from transport.models import TransportIncident
                TransportIncident.objects.all().delete()
            except Exception:
                pass

            # ── Library comprehensive ─────────────────────────────────────────
            self.stdout.write("Clearing library reservations, audits and requests...")
            try:
                from library.models import AcquisitionRequest, InventoryAudit, Reservation
                AcquisitionRequest.objects.all().delete()
                InventoryAudit.objects.all().delete()
                Reservation.objects.all().delete()
            except Exception:
                pass

            # ── E-Learning quiz attempts ──────────────────────────────────────
            self.stdout.write("Clearing e-learning quiz attempts...")
            try:
                from elearning.models import QuizAttempt
                QuizAttempt.objects.all().delete()
            except Exception:
                pass

            # ── Maintenance checklist ─────────────────────────────────────────
            self.stdout.write("Clearing maintenance checklist items...")
            try:
                from maintenance.models import MaintenanceChecklist
                MaintenanceChecklist.objects.all().delete()
            except Exception:
                pass

            # ── Store ─────────────────────────────────────────────────────────
            self.stdout.write("Clearing school store data...")
            try:
                from school.models import (
                    StoreOrderItem, StoreOrderRequest, StoreTransaction,
                    StoreItem, StoreSupplier, StoreCategory,
                )
                StoreOrderItem.objects.all().delete()
                StoreOrderRequest.objects.all().delete()
                StoreTransaction.objects.all().delete()
                StoreItem.objects.all().delete()
                StoreSupplier.objects.all().delete()
                StoreCategory.objects.all().delete()
            except Exception:
                pass

            # ── Dispensary ────────────────────────────────────────────────────
            self.stdout.write("Clearing dispensary data...")
            try:
                from school.models import DispensaryPrescription, DispensaryVisit, DispensaryStock
                DispensaryPrescription.objects.all().delete()
                DispensaryVisit.objects.all().delete()
                DispensaryStock.objects.all().delete()
            except Exception:
                pass

            # ── Exam setter assignments ───────────────────────────────────────
            self.stdout.write("Clearing exam setter assignments...")
            try:
                from examinations.models import ExamSetterAssignment
                ExamSetterAssignment.objects.all().delete()
            except Exception:
                pass

        # Reseed everything
        self.stdout.write(self.style.SUCCESS("Reseeding Kenya school data..."))
        call_command("seed_kenya_school", schema_name=schema)
        self.stdout.write(self.style.SUCCESS(f"Demo reset complete for schema: {schema}"))
