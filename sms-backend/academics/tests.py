from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from clients.models import Domain, Tenant
from school.models import (
    Module,
    Role,
    UserProfile,
    Department,
    Subject,
    SubjectMapping,
    SyllabusTopic,
    Enrollment,
    TeacherAssignment,
    Student,
    GradingScheme,
    GradeBand,
    Assessment,
    AssessmentGrade,
    TermResult,
    ReportCard,
    Assignment,
    AssignmentSubmission,
    CalendarEvent,
    AttendanceRecord,
)
from .models import AcademicYear, GradeLevel, SchoolClass, Term
from .views import (
    AcademicYearViewSet,
    SchoolClassViewSet,
    TermViewSet,
    DepartmentViewSet,
    SubjectViewSet,
    SubjectMappingViewSet,
    SyllabusTopicViewSet,
    SyllabusProgressView,
    AcademicEnrollmentViewSet,
    TeacherAssignmentViewSet,
    GradingSchemeViewSet,
    GradeBandViewSet,
    AssessmentViewSet,
    AssessmentGradeViewSet,
    TermResultViewSet,
    ReportCardViewSet,
    AssignmentViewSet,
    AssignmentSubmissionViewSet,
    CalendarEventViewSet,
    AnalyticsSummaryView,
    AnalyticsClassPerformanceView,
    AnalyticsSubjectPerformanceView,
    AnalyticsAtRiskView,
    AnalyticsStudentProfileView,
    AnalyticsTeacherPerformanceView,
    AnalyticsTrendView,
)

User = get_user_model()


class TenantTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django_tenants.utils import schema_context

        with schema_context("public"):
            cls.tenant = Tenant.objects.create(
                schema_name="academics_test",
                name="Academics Test School",
                paid_until="2030-01-01",
            )
            Domain.objects.create(domain="academics.localhost", tenant=cls.tenant, is_primary=True)

    def setUp(self):
        from django_tenants.utils import schema_context

        self.schema_context = schema_context(self.tenant.schema_name)
        self.schema_context.__enter__()

    def tearDown(self):
        self.schema_context.__exit__(None, None, None)


class AcademicsStructureTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="acad_admin", password="pass1234")
        role = Role.objects.create(name="ADMIN", description="School Administrator")
        UserProfile.objects.create(user=self.user, role=role)
        Module.objects.create(key="ACADEMICS", name="Academics")

    def test_academic_year_set_current_unsets_previous(self):
        first = AcademicYear.objects.create(
            name="2025-2026",
            start_date="2025-01-01",
            end_date="2025-12-31",
            is_active=True,
            is_current=True,
        )

        create_request = self.factory.post(
            "/api/academics/years/",
            {
                "name": "2026-2027",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "is_active": True,
                "is_current": True,
            },
            format="json",
        )
        force_authenticate(create_request, user=self.user)
        create_response = AcademicYearViewSet.as_view({"post": "create"})(create_request)
        self.assertEqual(create_response.status_code, 201)

        first.refresh_from_db()
        self.assertFalse(first.is_current)

    def test_term_set_current_unsets_previous(self):
        year = AcademicYear.objects.create(
            name="2026-2027",
            start_date="2026-01-01",
            end_date="2026-12-31",
            is_active=True,
            is_current=True,
        )
        first = Term.objects.create(
            academic_year=year,
            name="Term 1",
            start_date="2026-01-01",
            end_date="2026-04-30",
            is_active=True,
            is_current=True,
        )

        create_request = self.factory.post(
            "/api/academics/terms/",
            {
                "academic_year": year.id,
                "name": "Term 2",
                "start_date": "2026-05-01",
                "end_date": "2026-08-31",
                "billing_date": "2026-05-01",
                "is_active": True,
                "is_current": True,
            },
            format="json",
        )
        force_authenticate(create_request, user=self.user)
        create_response = TermViewSet.as_view({"post": "create"})(create_request)
        self.assertEqual(create_response.status_code, 201)

        first.refresh_from_db()
        self.assertFalse(first.is_current)

    def test_create_class_syncs_legacy_name_and_stream(self):
        year = AcademicYear.objects.create(
            name="2026-2027",
            start_date="2026-01-01",
            end_date="2026-12-31",
            is_active=True,
            is_current=True,
        )
        grade = GradeLevel.objects.create(name="Grade 7", order=7, is_active=True)

        create_request = self.factory.post(
            "/api/academics/classes/",
            {
                "academic_year": year.id,
                "grade_level": grade.id,
                "section_name": "A",
                "capacity": 35,
                "is_active": True,
            },
            format="json",
        )
        force_authenticate(create_request, user=self.user)
        create_response = SchoolClassViewSet.as_view({"post": "create"})(create_request)
        self.assertEqual(create_response.status_code, 201)

        created = SchoolClass.objects.get(pk=create_response.data["id"])
        self.assertEqual(created.name, "Grade 7")
        self.assertEqual(created.stream, "A")

    def test_clone_structure_creates_target_year_terms_and_classes(self):
        source_year = AcademicYear.objects.create(
            name="2025-2026",
            start_date="2025-01-01",
            end_date="2025-12-31",
            is_active=True,
            is_current=True,
        )
        grade = GradeLevel.objects.create(name="Grade 6", order=6, is_active=True)
        Term.objects.create(
            academic_year=source_year,
            name="Term 1",
            start_date="2025-01-01",
            end_date="2025-04-30",
            billing_date="2025-01-10",
            is_active=True,
            is_current=False,
        )
        SchoolClass.objects.create(
            name="Grade 6",
            stream="Blue",
            academic_year=source_year,
            grade_level=grade,
            section_name="Blue",
            capacity=40,
            is_active=True,
        )

        clone_request = self.factory.post(
            f"/api/academics/years/{source_year.id}/clone-structure/",
            {
                "name": "2026-2027",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "copy_terms": True,
                "copy_classes": True,
                "set_current": True,
            },
            format="json",
        )
        force_authenticate(clone_request, user=self.user)
        clone_response = AcademicYearViewSet.as_view({"post": "clone_structure"})(
            clone_request, pk=source_year.id
        )
        self.assertEqual(clone_response.status_code, 201)
        self.assertEqual(clone_response.data["cloned_terms"], 1)
        self.assertEqual(clone_response.data["cloned_classes"], 1)

        target_year = AcademicYear.objects.get(pk=clone_response.data["target_year_id"])
        self.assertTrue(target_year.is_current)
        source_year.refresh_from_db()
        self.assertFalse(source_year.is_current)

        cloned_term = Term.objects.get(academic_year=target_year, name="Term 1")
        self.assertEqual(str(cloned_term.start_date), "2026-01-01")
        self.assertEqual(str(cloned_term.end_date), "2026-04-30")
        self.assertEqual(str(cloned_term.billing_date), "2026-01-10")

        cloned_class = SchoolClass.objects.get(academic_year=target_year, section_name="Blue")
        self.assertEqual(cloned_class.grade_level_id, grade.id)


class AcademicsSubjectsCurriculumTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="acad_subjects", password="pass1234")
        role = Role.objects.create(name="ADMIN", description="School Administrator")
        UserProfile.objects.create(user=self.user, role=role)
        Module.objects.create(key="ACADEMICS", name="Academics")

        self.year = AcademicYear.objects.create(
            name="2026-2027",
            start_date="2026-01-01",
            end_date="2026-12-31",
            is_active=True,
            is_current=True,
        )
        self.term = Term.objects.create(
            academic_year=self.year,
            name="Term 1",
            start_date="2026-01-01",
            end_date="2026-04-30",
            is_active=True,
            is_current=True,
        )
        self.grade = GradeLevel.objects.create(name="Grade 8", order=8, is_active=True)

    def test_subjects_curriculum_flow(self):
        department_request = self.factory.post(
            "/api/academics/departments/",
            {"name": "Sciences", "description": "Science department", "is_active": True},
            format="json",
        )
        force_authenticate(department_request, user=self.user)
        department_response = DepartmentViewSet.as_view({"post": "create"})(department_request)
        self.assertEqual(department_response.status_code, 201)
        department_id = department_response.data["id"]

        subject_request = self.factory.post(
            "/api/academics/subjects/",
            {
                "name": "Biology",
                "code": "BIO",
                "department": department_id,
                "subject_type": "Compulsory",
                "periods_week": 4,
                "is_active": True,
            },
            format="json",
        )
        force_authenticate(subject_request, user=self.user)
        subject_response = SubjectViewSet.as_view({"post": "create"})(subject_request)
        self.assertEqual(subject_response.status_code, 201)
        subject_id = subject_response.data["id"]

        mapping_request = self.factory.post(
            "/api/academics/subject-mappings/",
            {
                "subject": subject_id,
                "grade_level": self.grade.id,
                "academic_year": self.year.id,
                "is_compulsory": True,
                "is_active": True,
            },
            format="json",
        )
        force_authenticate(mapping_request, user=self.user)
        mapping_response = SubjectMappingViewSet.as_view({"post": "create"})(mapping_request)
        self.assertEqual(mapping_response.status_code, 201)
        self.assertEqual(SubjectMapping.objects.count(), 1)

        syllabus_request = self.factory.post(
            "/api/academics/syllabus/",
            {
                "subject": subject_id,
                "grade_level": self.grade.id,
                "term": self.term.id,
                "topic_name": "Cell Structure",
                "order": 1,
                "is_active": True,
            },
            format="json",
        )
        force_authenticate(syllabus_request, user=self.user)
        syllabus_response = SyllabusTopicViewSet.as_view({"post": "create"})(syllabus_request)
        self.assertEqual(syllabus_response.status_code, 201)
        topic_id = syllabus_response.data["id"]

        complete_request = self.factory.patch(
            f"/api/academics/syllabus/{topic_id}/complete/",
            {"completed_date": "2026-02-01"},
            format="json",
        )
        force_authenticate(complete_request, user=self.user)
        complete_response = SyllabusTopicViewSet.as_view({"patch": "complete"})(
            complete_request, pk=topic_id
        )
        self.assertEqual(complete_response.status_code, 200)
        topic = SyllabusTopic.objects.get(pk=topic_id)
        self.assertTrue(topic.is_completed)
        self.assertEqual(str(topic.completed_date), "2026-02-01")

        progress_request = self.factory.get(f"/api/academics/syllabus/progress/?term={self.term.id}")
        force_authenticate(progress_request, user=self.user)
        progress_response = SyllabusProgressView.as_view()(progress_request)
        self.assertEqual(progress_response.status_code, 200)
        self.assertEqual(len(progress_response.data), 1)
        self.assertEqual(progress_response.data[0]["completion_percent"], 100.0)


class AcademicsClassManagementTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="acad_class", password="pass1234")
        role = Role.objects.create(name="ADMIN", description="School Administrator")
        UserProfile.objects.create(user=self.user, role=role)
        Module.objects.create(key="ACADEMICS", name="Academics")

        self.year1 = AcademicYear.objects.create(
            name="2026-2027", start_date="2026-01-01", end_date="2026-12-31", is_active=True, is_current=True
        )
        self.year2 = AcademicYear.objects.create(
            name="2027-2028", start_date="2027-01-01", end_date="2027-12-31", is_active=True, is_current=False
        )
        self.term1 = Term.objects.create(
            academic_year=self.year1, name="Term 1", start_date="2026-01-01", end_date="2026-04-30", is_active=True
        )
        self.term2 = Term.objects.create(
            academic_year=self.year2, name="Term 1", start_date="2027-01-01", end_date="2027-04-30", is_active=True
        )
        self.grade7 = GradeLevel.objects.create(name="Grade 7", order=7, is_active=True)
        self.grade8 = GradeLevel.objects.create(name="Grade 8", order=8, is_active=True)
        self.class7 = SchoolClass.objects.create(
            name="Grade 7", stream="A", grade_level=self.grade7, section_name="A", academic_year=self.year1, is_active=True
        )
        self.class8 = SchoolClass.objects.create(
            name="Grade 8", stream="A", grade_level=self.grade8, section_name="A", academic_year=self.year2, is_active=True
        )
        self.student = Student.objects.create(
            admission_number="ST900", first_name="Lina", last_name="Kai", gender="F", date_of_birth="2011-01-01"
        )
        self.teacher = User.objects.create_user(username="teacher_a", password="pass1234")
        self.department = Department.objects.create(name="Sciences", is_active=True)
        self.subject = Subject.objects.create(
            name="Biology", code="BIO", department=self.department, subject_type="Compulsory", periods_week=4, is_active=True
        )

    def test_enrollment_and_teacher_assignment_and_bulk_promote(self):
        enrollment_request = self.factory.post(
            "/api/academics/enrollments/",
            {"student": self.student.id, "school_class": self.class7.id, "term": self.term1.id, "status": "Active", "is_active": True},
            format="json",
        )
        force_authenticate(enrollment_request, user=self.user)
        enrollment_response = AcademicEnrollmentViewSet.as_view({"post": "create"})(enrollment_request)
        self.assertEqual(enrollment_response.status_code, 201)
        self.assertEqual(Enrollment.objects.count(), 1)

        assignment_request = self.factory.post(
            "/api/academics/teacher-assignments/",
            {
                "teacher": self.teacher.id,
                "subject": self.subject.id,
                "class_section": self.class7.id,
                "academic_year": self.year1.id,
                "term": self.term1.id,
                "is_primary": True,
                "is_active": True,
            },
            format="json",
        )
        force_authenticate(assignment_request, user=self.user)
        assignment_response = TeacherAssignmentViewSet.as_view({"post": "create"})(assignment_request)
        self.assertEqual(assignment_response.status_code, 201)
        self.assertEqual(TeacherAssignment.objects.count(), 1)

        promote_request = self.factory.post(
            "/api/academics/enrollments/bulk-promote/",
            {
                "from_academic_year": self.year1.id,
                "to_academic_year": self.year2.id,
                "from_term": self.term1.id,
                "to_term": self.term2.id,
            },
            format="json",
        )
        force_authenticate(promote_request, user=self.user)
        promote_response = AcademicEnrollmentViewSet.as_view({"post": "bulk_promote"})(promote_request)
        self.assertEqual(promote_response.status_code, 200)
        self.assertEqual(promote_response.data["promoted"], 1)
        self.assertEqual(Enrollment.objects.filter(term_id=self.term2.id).count(), 1)


class AcademicsGradebookTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="acad_gradebook", password="pass1234")
        role = Role.objects.create(name="ADMIN", description="School Administrator")
        UserProfile.objects.create(user=self.user, role=role)
        Module.objects.create(key="ACADEMICS", name="Academics")

        self.year = AcademicYear.objects.create(
            name="2026-2027", start_date="2026-01-01", end_date="2026-12-31", is_active=True, is_current=True
        )
        self.term = Term.objects.create(
            academic_year=self.year, name="Term 1", start_date="2026-01-01", end_date="2026-04-30", is_active=True, is_current=True
        )
        self.grade = GradeLevel.objects.create(name="Grade 9", order=9, is_active=True)
        self.class9 = SchoolClass.objects.create(
            name="Grade 9", stream="A", grade_level=self.grade, section_name="A", academic_year=self.year, is_active=True
        )
        self.department = Department.objects.create(name="Math", is_active=True)
        self.subject = Subject.objects.create(
            name="Mathematics", code="MATH", department=self.department, subject_type="Compulsory", periods_week=5, is_active=True
        )
        self.student1 = Student.objects.create(
            admission_number="ST901", first_name="Ana", last_name="West", gender="F", date_of_birth="2010-01-01"
        )
        self.student2 = Student.objects.create(
            admission_number="ST902", first_name="Ben", last_name="East", gender="M", date_of_birth="2010-01-02"
        )

    def test_gradebook_flow(self):
        scheme_request = self.factory.post(
            "/api/academics/grading-schemes/",
            {"name": "Default Scheme", "is_default": True, "is_active": True},
            format="json",
        )
        force_authenticate(scheme_request, user=self.user)
        scheme_response = GradingSchemeViewSet.as_view({"post": "create"})(scheme_request)
        self.assertEqual(scheme_response.status_code, 201)
        scheme_id = scheme_response.data["id"]

        for payload in [
            {"label": "A", "min_score": "80.00", "max_score": "100.00"},
            {"label": "B", "min_score": "60.00", "max_score": "79.99"},
            {"label": "C", "min_score": "0.00", "max_score": "59.99"},
        ]:
            band_request = self.factory.post(
                "/api/academics/grade-bands/",
                {"scheme": scheme_id, **payload, "is_active": True},
                format="json",
            )
            force_authenticate(band_request, user=self.user)
            band_response = GradeBandViewSet.as_view({"post": "create"})(band_request)
            self.assertEqual(band_response.status_code, 201)
        self.assertEqual(GradeBand.objects.count(), 3)

        assessment_request = self.factory.post(
            "/api/academics/assessments/",
            {
                "name": "Mid Term Test",
                "category": "Test",
                "subject": self.subject.id,
                "class_section": self.class9.id,
                "term": self.term.id,
                "max_score": "100.00",
                "weight_percent": "100.00",
                "date": "2026-02-01",
                "is_active": True,
            },
            format="json",
        )
        force_authenticate(assessment_request, user=self.user)
        assessment_response = AssessmentViewSet.as_view({"post": "create"})(assessment_request)
        self.assertEqual(assessment_response.status_code, 201)
        assessment_id = assessment_response.data["id"]

        bulk_request = self.factory.post(
            "/api/academics/grades/bulk/",
            {
                "assessment": assessment_id,
                "grades": [
                    {"student": self.student1.id, "raw_score": "85.00", "remarks": ""},
                    {"student": self.student2.id, "raw_score": "65.00", "remarks": ""},
                ],
            },
            format="json",
        )
        force_authenticate(bulk_request, user=self.user)
        bulk_response = AssessmentGradeViewSet.as_view({"post": "bulk"})(bulk_request)
        self.assertEqual(bulk_response.status_code, 200)
        self.assertEqual(AssessmentGrade.objects.count(), 2)

        publish_request = self.factory.post(f"/api/academics/assessments/{assessment_id}/publish/", {}, format="json")
        force_authenticate(publish_request, user=self.user)
        publish_response = AssessmentViewSet.as_view({"post": "publish"})(publish_request, pk=assessment_id)
        self.assertEqual(publish_response.status_code, 200)
        self.assertTrue(Assessment.objects.get(pk=assessment_id).is_published)

        compute_request = self.factory.post(
            "/api/academics/term-results/compute/",
            {"class_section": self.class9.id, "term": self.term.id, "grading_scheme": scheme_id},
            format="json",
        )
        force_authenticate(compute_request, user=self.user)
        compute_response = TermResultViewSet.as_view({"post": "compute"})(compute_request)
        self.assertEqual(compute_response.status_code, 200)
        self.assertEqual(TermResult.objects.count(), 2)


class AcademicsReportCardsTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="acad_reportcards", password="pass1234")
        role = Role.objects.create(name="ADMIN", description="School Administrator")
        UserProfile.objects.create(user=self.user, role=role)
        Module.objects.create(key="ACADEMICS", name="Academics")

        self.year = AcademicYear.objects.create(
            name="2026-2027", start_date="2026-01-01", end_date="2026-12-31", is_active=True, is_current=True
        )
        self.term = Term.objects.create(
            academic_year=self.year, name="Term 1", start_date="2026-01-01", end_date="2026-04-30", is_active=True, is_current=True
        )
        self.grade = GradeLevel.objects.create(name="Grade 10", order=10, is_active=True)
        self.class10 = SchoolClass.objects.create(
            name="Grade 10", stream="A", grade_level=self.grade, section_name="A", academic_year=self.year, is_active=True
        )
        self.department = Department.objects.create(name="Languages", is_active=True)
        self.subject = Subject.objects.create(
            name="English", code="ENG", department=self.department, subject_type="Compulsory", periods_week=5, is_active=True
        )
        self.student1 = Student.objects.create(
            admission_number="ST911", first_name="Nia", last_name="Kay", gender="F", date_of_birth="2010-01-01"
        )
        self.student2 = Student.objects.create(
            admission_number="ST912", first_name="Omar", last_name="Lee", gender="M", date_of_birth="2010-01-02"
        )
        Enrollment.objects.create(student=self.student1, school_class_id=self.class10.id, term_id=self.term.id, status="Active", is_active=True)
        Enrollment.objects.create(student=self.student2, school_class_id=self.class10.id, term_id=self.term.id, status="Active", is_active=True)

        scheme = GradingScheme.objects.create(name="Default Scheme", is_default=True, is_active=True)
        band_a = GradeBand.objects.create(
            scheme=scheme, label="A", min_score="80.00", max_score="100.00", is_active=True
        )
        band_b = GradeBand.objects.create(
            scheme=scheme, label="B", min_score="60.00", max_score="79.99", is_active=True
        )
        TermResult.objects.create(
            student=self.student1,
            class_section_id=self.class10.id,
            term_id=self.term.id,
            subject_id=self.subject.id,
            total_score="84.00",
            grade_band=band_a,
            class_rank=1,
            is_pass=True,
            is_active=True,
        )
        TermResult.objects.create(
            student=self.student2,
            class_section_id=self.class10.id,
            term_id=self.term.id,
            subject_id=self.subject.id,
            total_score="72.00",
            grade_band=band_b,
            class_rank=2,
            is_pass=True,
            is_active=True,
        )

    def test_report_card_flow(self):
        generate_request = self.factory.post(
            "/api/academics/report-cards/generate/",
            {"class_section": self.class10.id, "term": self.term.id},
            format="json",
        )
        force_authenticate(generate_request, user=self.user)
        generate_response = ReportCardViewSet.as_view({"post": "generate"})(generate_request)
        self.assertEqual(generate_response.status_code, 200)
        self.assertEqual(ReportCard.objects.count(), 2)

        report_card = ReportCard.objects.order_by("id").first()
        approve_request = self.factory.post(f"/api/academics/report-cards/{report_card.id}/approve/", {}, format="json")
        force_authenticate(approve_request, user=self.user)
        approve_response = ReportCardViewSet.as_view({"post": "approve"})(approve_request, pk=report_card.id)
        self.assertEqual(approve_response.status_code, 200)

        publish_request = self.factory.post(f"/api/academics/report-cards/{report_card.id}/publish/", {}, format="json")
        force_authenticate(publish_request, user=self.user)
        publish_response = ReportCardViewSet.as_view({"post": "publish"})(publish_request, pk=report_card.id)
        self.assertEqual(publish_response.status_code, 200)

        distribute_request = self.factory.post(
            "/api/academics/report-cards/distribute/",
            {"report_card_ids": [report_card.id]},
            format="json",
        )
        force_authenticate(distribute_request, user=self.user)
        distribute_response = ReportCardViewSet.as_view({"post": "distribute"})(distribute_request)
        self.assertEqual(distribute_response.status_code, 200)
        report_card.refresh_from_db()
        self.assertEqual(report_card.status, "Distributed")

        pdf_request = self.factory.get(f"/api/academics/report-cards/{report_card.id}/pdf/")
        force_authenticate(pdf_request, user=self.user)
        pdf_response = ReportCardViewSet.as_view({"get": "pdf"})(pdf_request, pk=report_card.id)
        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response["Content-Type"], "application/pdf")


class AcademicsAssignmentsCalendarTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="acad_phase5", password="pass1234")
        role = Role.objects.create(name="ADMIN", description="School Administrator")
        UserProfile.objects.create(user=self.user, role=role)
        Module.objects.create(key="ACADEMICS", name="Academics")

        self.year = AcademicYear.objects.create(
            name="2026-2027", start_date="2026-01-01", end_date="2026-12-31", is_active=True, is_current=True
        )
        self.term = Term.objects.create(
            academic_year=self.year, name="Term 2", start_date="2026-05-01", end_date="2026-08-31", is_active=True
        )
        self.grade = GradeLevel.objects.create(name="Grade 11", order=11, is_active=True)
        self.class11 = SchoolClass.objects.create(
            name="Grade 11", stream="A", grade_level=self.grade, section_name="A", academic_year=self.year, is_active=True
        )
        self.department = Department.objects.create(name="Sciences", is_active=True)
        self.subject = Subject.objects.create(
            name="Chemistry", code="CHEM", department=self.department, subject_type="Compulsory", periods_week=4, is_active=True
        )
        self.student = Student.objects.create(
            admission_number="ST930", first_name="Ria", last_name="Stone", gender="F", date_of_birth="2010-03-01"
        )
        Enrollment.objects.create(student=self.student, school_class_id=self.class11.id, term_id=self.term.id, status="Active", is_active=True)

    def test_assignments_and_calendar_flow(self):
        assignment_request = self.factory.post(
            "/api/academics/assignments/",
            {
                "title": "Chemistry Homework 1",
                "subject": self.subject.id,
                "class_section": self.class11.id,
                "description": "Complete chapters 1-2",
                "due_date": "2026-06-10T12:00:00Z",
                "max_score": "20.00",
                "publish_date": "2026-06-01T08:00:00Z",
                "status": "Published",
                "is_active": True,
            },
            format="json",
        )
        force_authenticate(assignment_request, user=self.user)
        assignment_response = AssignmentViewSet.as_view({"post": "create"})(assignment_request)
        self.assertEqual(assignment_response.status_code, 201)
        assignment_id = assignment_response.data["id"]

        submission_request = self.factory.post(
            "/api/academics/submissions/",
            {
                "assignment": assignment_id,
                "student": self.student.id,
                "notes": "Completed",
            },
            format="json",
        )
        force_authenticate(submission_request, user=self.user)
        submission_response = AssignmentSubmissionViewSet.as_view({"post": "create"})(submission_request)
        self.assertEqual(submission_response.status_code, 201)
        submission_id = submission_response.data["id"]

        grade_request = self.factory.patch(
            f"/api/academics/submissions/{submission_id}/grade/",
            {"score": "18.00", "feedback": "Good work"},
            format="json",
        )
        force_authenticate(grade_request, user=self.user)
        grade_response = AssignmentSubmissionViewSet.as_view({"patch": "grade"})(grade_request, pk=submission_id)
        self.assertEqual(grade_response.status_code, 200)
        self.assertEqual(str(AssignmentSubmission.objects.get(pk=submission_id).score), grade_response.data["score"])

        stats_request = self.factory.get(f"/api/academics/assignments/{assignment_id}/stats/")
        force_authenticate(stats_request, user=self.user)
        stats_response = AssignmentViewSet.as_view({"get": "stats"})(stats_request, pk=assignment_id)
        self.assertEqual(stats_response.status_code, 200)
        self.assertEqual(stats_response.data["submitted_count"], 1)

        calendar_request = self.factory.post(
            "/api/academics/calendar/",
            {
                "title": "Science Fair",
                "event_type": "Other",
                "start_date": "2026-06-20",
                "end_date": "2026-06-20",
                "description": "Annual fair",
                "academic_year": self.year.id,
                "term": self.term.id,
                "scope": "School-wide",
                "is_public": True,
                "is_active": True,
            },
            format="json",
        )
        force_authenticate(calendar_request, user=self.user)
        calendar_response = CalendarEventViewSet.as_view({"post": "create"})(calendar_request)
        self.assertEqual(calendar_response.status_code, 201)
        event_id = calendar_response.data["id"]
        self.assertEqual(CalendarEvent.objects.count(), 1)

        export_request = self.factory.get("/api/academics/calendar/export/")
        force_authenticate(export_request, user=self.user)
        export_response = CalendarEventViewSet.as_view({"get": "export"})(export_request)
        self.assertEqual(export_response.status_code, 200)
        self.assertEqual(export_response["Content-Type"], "text/calendar")

        delete_request = self.factory.delete(f"/api/academics/calendar/{event_id}/")
        force_authenticate(delete_request, user=self.user)
        delete_response = CalendarEventViewSet.as_view({"delete": "destroy"})(delete_request, pk=event_id)
        self.assertEqual(delete_response.status_code, 204)
        self.assertFalse(CalendarEvent.objects.get(pk=event_id).is_active)


class AcademicsAnalyticsTests(TenantTestBase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="acad_analytics", password="pass1234")
        role = Role.objects.create(name="ADMIN", description="School Administrator")
        UserProfile.objects.create(user=self.user, role=role)
        Module.objects.create(key="ACADEMICS", name="Academics")

        self.year = AcademicYear.objects.create(
            name="2026-2027", start_date="2026-01-01", end_date="2026-12-31", is_active=True, is_current=True
        )
        self.term1 = Term.objects.create(
            academic_year=self.year, name="Term 1", start_date="2026-01-01", end_date="2026-04-30", is_active=True
        )
        self.term2 = Term.objects.create(
            academic_year=self.year, name="Term 2", start_date="2026-05-01", end_date="2026-08-31", is_active=True
        )
        self.grade = GradeLevel.objects.create(name="Grade 12", order=12, is_active=True)
        self.school_class = SchoolClass.objects.create(
            name="Grade 12", stream="A", grade_level=self.grade, section_name="A", academic_year=self.year, is_active=True
        )
        self.department = Department.objects.create(name="Math", is_active=True)
        self.subject1 = Subject.objects.create(name="Mathematics", code="MTH12", department=self.department, subject_type="Compulsory", periods_week=5, is_active=True)
        self.subject2 = Subject.objects.create(name="Physics", code="PHY12", department=self.department, subject_type="Compulsory", periods_week=5, is_active=True)
        self.student1 = Student.objects.create(admission_number="ST950", first_name="Alex", last_name="Ray", gender="M", date_of_birth="2009-01-01")
        self.student2 = Student.objects.create(admission_number="ST951", first_name="Bea", last_name="May", gender="F", date_of_birth="2009-01-02")
        self.teacher = User.objects.create_user(username="teacher_analytics", password="pass1234")

        TeacherAssignment.objects.create(
            teacher=self.teacher,
            subject=self.subject1,
            class_section_id=self.school_class.id,
            academic_year_id=self.year.id,
            term_id=self.term1.id,
            is_primary=True,
            is_active=True,
        )

        TermResult.objects.create(student=self.student1, class_section_id=self.school_class.id, term_id=self.term1.id, subject_id=self.subject1.id, total_score="70.00", is_pass=True, is_active=True)
        TermResult.objects.create(student=self.student1, class_section_id=self.school_class.id, term_id=self.term1.id, subject_id=self.subject2.id, total_score="45.00", is_pass=False, is_active=True)
        TermResult.objects.create(student=self.student2, class_section_id=self.school_class.id, term_id=self.term1.id, subject_id=self.subject1.id, total_score="40.00", is_pass=False, is_active=True)
        TermResult.objects.create(student=self.student2, class_section_id=self.school_class.id, term_id=self.term1.id, subject_id=self.subject2.id, total_score="35.00", is_pass=False, is_active=True)
        TermResult.objects.create(student=self.student1, class_section_id=self.school_class.id, term_id=self.term2.id, subject_id=self.subject1.id, total_score="80.00", is_pass=True, is_active=True)

        AttendanceRecord.objects.create(student=self.student1, date="2026-01-10", status="Present")
        AttendanceRecord.objects.create(student=self.student1, date="2026-01-11", status="Absent")

    def test_analytics_endpoints(self):
        req = self.factory.get("/api/academics/analytics/summary/")
        force_authenticate(req, user=self.user)
        resp = AnalyticsSummaryView.as_view()(req)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("average_score", resp.data)

        req = self.factory.get("/api/academics/analytics/class-performance/")
        force_authenticate(req, user=self.user)
        resp = AnalyticsClassPerformanceView.as_view()(req)
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data), 1)

        req = self.factory.get("/api/academics/analytics/subject-performance/")
        force_authenticate(req, user=self.user)
        resp = AnalyticsSubjectPerformanceView.as_view()(req)
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data), 1)

        req = self.factory.get("/api/academics/analytics/at-risk/")
        force_authenticate(req, user=self.user)
        resp = AnalyticsAtRiskView.as_view()(req)
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data), 1)

        req = self.factory.get(f"/api/academics/analytics/student/{self.student1.id}/")
        force_authenticate(req, user=self.user)
        resp = AnalyticsStudentProfileView.as_view()(req, student_id=self.student1.id)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["student_id"], self.student1.id)

        req = self.factory.get(f"/api/academics/analytics/teacher/{self.teacher.id}/")
        force_authenticate(req, user=self.user)
        resp = AnalyticsTeacherPerformanceView.as_view()(req, teacher_id=self.teacher.id)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["teacher_id"], self.teacher.id)

        req = self.factory.get("/api/academics/analytics/trend/")
        force_authenticate(req, user=self.user)
        resp = AnalyticsTrendView.as_view()(req)
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data), 1)
