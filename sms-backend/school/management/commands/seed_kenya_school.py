"""
seed_kenya_school.py
Comprehensive CBE sample data for a Kenyan secondary school (St. Mary's Nairobi High School).
Includes: academic structure, 40 students, 12 teachers, fee structures, payments,
admissions applications, HR leave requests, library acquisitions, maintenance requests,
communication data, and more — designed to populate all approval workflows.
Usage: python manage.py seed_kenya_school [--schema_name demo_school]
"""
from datetime import date, timedelta
from decimal import Decimal
import random
import uuid

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django_tenants.utils import schema_context

from clients.models import Tenant, Domain
from school.models import (
    Role, UserProfile, Student, Guardian, Enrollment, SchoolClass,
    FeeStructure, FeeAssignment, Invoice, InvoiceLineItem, Payment, PaymentAllocation,
    Expense, AdmissionApplication, AcademicYear, Term,
    Department, Subject,
    GradingScheme, GradeBand,
    Assessment, AssessmentGrade, TermResult, ReportCard,
    VoteHead, Budget, ChartOfAccount, Module, TenantModule,
)
from hr.models import Staff
from communication.models import Message
from school.management.commands.seed_modules import ALL_MODULES
from school.role_scope import iter_seed_role_definitions

User = get_user_model()

KENYAN_MALE_NAMES = [
    ("Peter", "Kamau"), ("John", "Mwangi"), ("David", "Njoroge"),
    ("Michael", "Ochieng"), ("James", "Wafula"), ("Samuel", "Kiprotich"),
    ("Daniel", "Otieno"), ("Francis", "Mutua"), ("Patrick", "Njiru"),
    ("George", "Abuya"), ("Emmanuel", "Kariuki"), ("Brian", "Ndegwa"),
    ("Kevin", "Waweru"), ("Collins", "Omondi"), ("Victor", "Cheruiyot"),
    ("Joseph", "Kimani"), ("Eric", "Ndirangu"), ("Mark", "Kipchoge"),
    ("Andrew", "Mugo"), ("Timothy", "Simiyu"),
]

KENYAN_FEMALE_NAMES = [
    ("Mary", "Wanjiku"), ("Grace", "Murugi"), ("Faith", "Achieng"),
    ("Joyce", "Wangari"), ("Esther", "Chepkoech"), ("Ruth", "Adhiambo"),
    ("Alice", "Nyambura"), ("Susan", "Auma"), ("Caroline", "Kiptoo"),
    ("Janet", "Waweru"), ("Beatrice", "Njeri"), ("Priscilla", "Chebet"),
    ("Mercy", "Atieno"), ("Winnie", "Njoki"), ("Lydia", "Chemutai"),
    ("Tabitha", "Mwende"), ("Naomi", "Awuor"), ("Deborah", "Jeptoo"),
    ("Rachel", "Wairimu"), ("Eunice", "Kerubo"),
]

TEACHER_DATA = [
    ("Samuel", "Otieno", "Mathematics", "0722100001"),
    ("Grace", "Wanjiku", "English", "0722100002"),
    ("David", "Mwangi", "Biology", "0722100003"),
    ("Faith", "Njoroge", "Chemistry", "0722100004"),
    ("Peter", "Kamau", "Physics", "0722100005"),
    ("Mary", "Achieng", "History & Government", "0722100006"),
    ("John", "Mutua", "Geography", "0722100007"),
    ("Susan", "Wafula", "Business Studies", "0722100008"),
    ("James", "Simiyu", "Kiswahili", "0722100009"),
    ("Esther", "Kimani", "CRE", "0722100010"),
    ("George", "Ndegwa", "Agriculture", "0722100011"),
    ("Alice", "Chebet", "Computer Studies", "0722100012"),
]

NON_TEACHING_STAFF_DATA = [
    # (first, last, role, phone)
    ("Joseph", "Karanja",   "Principal",              "0711200001"),
    ("Agnes",  "Wanjiku",   "Deputy Principal",       "0711200002"),
    ("David",  "Murithi",   "Senior Clerk",           "0711200003"),
    ("Rose",   "Atieno",    "Bursar",                 "0711200004"),
    ("Charles","Mutuku",    "Accounts Assistant",     "0711200005"),
    ("Pauline","Njoroge",   "School Secretary",       "0711200006"),
    ("Moses",  "Ochieng",   "Lab Technician",         "0711200007"),
    ("Jane",   "Wafula",    "Librarian",              "0711200008"),
    ("Simon",  "Kipkoech",  "Driver",                 "0711200009"),
    ("Peter",  "Njiru",     "Driver",                 "0711200010"),
    ("Francis","Onyango",   "Security Guard",         "0711200011"),
    ("Mary",   "Auma",      "Security Guard",         "0711200012"),
    ("John",   "Chepkwony","Head Cook",               "0711200013"),
    ("Grace",  "Adhiambo",  "Kitchen Staff",          "0711200014"),
    ("Samuel", "Ndirangu",  "Groundskeeper",          "0711200015"),
    ("Elizabeth","Mwenda",  "Nurse",                  "0711200016"),
    ("James",  "Kiptoo",    "ICT Technician",         "0711200017"),
    ("Naomi",  "Chebet",    "Matron",                 "0711200018"),
]

SUBJECTS_844 = [
    "Mathematics", "English", "Kiswahili",
    "Biology", "Chemistry", "Physics",
    "History & Government", "Geography", "CRE",
    "Business Studies", "Agriculture", "Computer Studies",
]

GRADES = ["Grade 7", "Grade 8", "Grade 9", "Grade 10"]
STREAMS = ["East", "West", "North", "South"]

FEE_ITEMS = [
    ("Tuition Fee", Decimal("12000.00")),
    ("Boarding Fee", Decimal("15000.00")),
    ("Activity Fee", Decimal("2500.00")),
    ("Lunch Fee", Decimal("3500.00")),
    ("ICT Levy", Decimal("1500.00")),
    ("Games & Sports", Decimal("1000.00")),
    ("Caution Money", Decimal("500.00")),
]

MAINTENANCE_ITEMS = [
    ("Science Lab Equipment Repair", "High", "Laboratory Block"),
    ("Library Roof Leak", "Urgent", "Library Building"),
    ("Computer Lab Projector Fault", "Medium", "Computer Lab"),
    ("Sports Ground Fencing", "Low", "Sports Ground"),
    ("Classroom 12B Door Replacement", "Medium", "Grade 8 Block"),
    ("Kitchen Exhaust Fan Repair", "High", "Kitchen"),
    ("Dormitory Bunk Beds Repair", "Medium", "Boarding House"),
    ("School Bus Service", "High", "Garage"),
]


class Command(BaseCommand):
    help = "Seeds comprehensive Kenyan high school demo data (St. Mary's Nairobi High School)."

    def add_arguments(self, parser):
        parser.add_argument("--schema_name", type=str, default="demo_school")
        parser.add_argument(
            "--library-only",
            action="store_true",
            default=False,
            help="Only seed library resources, members, transactions and fines (fast, safe to run in build).",
        )

    def handle(self, *args, **options):
        schema_name = options["schema_name"]
        library_only = options["library_only"]

        if not library_only:
            with schema_context("public"):
                tenant, _ = Tenant.objects.get_or_create(
                    schema_name=schema_name,
                    defaults={
                        "name": "St. Mary's Nairobi High School",
                        "paid_until": date(2030, 1, 1),
                        "is_active": True,
                    },
                )
                Domain.objects.get_or_create(
                    domain="demo.localhost",
                    tenant=tenant,
                    defaults={"is_primary": True},
                )

        with schema_context(schema_name):
            if library_only:
                self.stdout.write("  Seeding library data only (fast mode)…")
                from django.contrib.auth.models import User
                from school.models import Student
                admin = User.objects.filter(is_superuser=True).first() or User.objects.filter(username="Riqs#.").first()
                if not admin:
                    self.stdout.write("  No admin user found — skipping library seed")
                    return
                students = list(Student.objects.filter(is_active=True))
                self._seed_library(students, admin)
            else:
                self._seed_all(schema_name)

        self.stdout.write(self.style.SUCCESS(
            f"Kenyan school data seeded successfully for schema '{schema_name}'."
        ))

    def _seed_all(self, schema_name):
        self.stdout.write("  Seeding roles and modules…")
        self._seed_roles_modules()

        self.stdout.write("  Seeding admin user…")
        admin = self._seed_admin_user()

        self.stdout.write("  Seeding academic structure…")
        year, terms, classes = self._seed_academics()

        self.stdout.write("  Seeding staff / teachers…")
        self._seed_staff(admin)

        self.stdout.write("  Seeding students (40)…")
        students = self._seed_students(classes, terms)

        self.stdout.write("  Seeding fee structures and invoices…")
        self._seed_fees(year, terms, students)

        self.stdout.write("  Seeding fee assignments (student → fee structure links)…")
        self._seed_fee_assignments(terms, students)

        self.stdout.write("  Seeding admission applications…")
        self._seed_admissions(year, terms)

        self.stdout.write("  Seeding maintenance requests…")
        self._seed_maintenance(admin)

        self.stdout.write("  Seeding communication messages…")
        self._seed_communication(students, admin)

        self.stdout.write("  Seeding Kenyan CBE curriculum (departments + subjects)…")
        self._seed_curriculum_base()

        self.stdout.write("  Seeding gradebook (assessments + marks + term results + report cards)…")
        self._seed_gradebook_and_reports(year, terms, classes)

        self.stdout.write("  Seeding library resources + members + transactions…")
        self._seed_library(students, admin)

        self.stdout.write("  Seeding e-learning courses + materials + quizzes…")
        self._seed_elearning(classes, terms, admin)

        self.stdout.write("  Seeding cafeteria (meal plans + menus + enrollments)…")
        self._seed_cafeteria(students)

        self.stdout.write("  Seeding sports clubs + tournaments + awards…")
        self._seed_sports(students, admin)

        self.stdout.write("  Seeding assets + categories…")
        self._seed_assets(admin)

        self.stdout.write("  Seeding transport (vehicles, routes, assignments)…")
        self._seed_transport(students, terms)

        self.stdout.write("  Seeding hostel (dormitories, beds, allocations)…")
        self._seed_hostel(students, terms)

        self.stdout.write("  Seeding timetable (periods Mon–Fri)…")
        self._seed_timetable(classes, terms, admin)

        self.stdout.write("  Seeding visitor log…")
        self._seed_visitors()

        self.stdout.write("  Seeding Chart of Accounts (IPSAS-aligned)…")
        self._seed_chart_of_accounts()

        self.stdout.write("  Seeding HR Employee records for teaching + non-teaching staff…")
        self._seed_hr_employees()

        self.stdout.write("  Seeding Staff Management member records…")
        self._seed_staff_mgmt_members()

        self.stdout.write("  Seeding examination sessions, papers and results…")
        self._seed_examinations(year, terms, classes, admin)

        self.stdout.write("  Seeding alumni profiles, events, mentorships and donations…")
        self._seed_alumni()

        self.stdout.write("  Seeding parent-teacher meeting (PTM) sessions…")
        self._seed_ptm(terms, students)

        self.stdout.write("  Seeding clock-in shifts, person registry and attendance events…")
        self._seed_clockin(students, admin)

        self.stdout.write("  Seeding parent portal account links…")
        self._seed_parent_portal(students, admin)

        self.stdout.write("  Seeding admissions pipeline (inquiries → decisions)…")
        self._seed_admissions_pipeline(year, terms, classes, admin)

        self.stdout.write("  Seeding curriculum (schemes of work, lesson plans, resources)…")
        self._seed_curriculum(year, terms, classes, admin)

        self.stdout.write("  Seeding comprehensive HR (departments, payroll, recruitment, performance)…")
        self._seed_hr_comprehensive(admin)

        self.stdout.write("  Seeding staff management (qualifications, attendance, appraisals, observations)…")
        self._seed_staff_mgmt_comprehensive(admin, classes)

        self.stdout.write("  Seeding communication (conversations, notifications, campaigns)…")
        self._seed_communication_data(admin)

        self.stdout.write("  Seeding asset assignments, maintenance and warranties…")
        self._seed_assets_comprehensive(admin)

        self.stdout.write("  Seeding cafeteria meal transactions and wallet top-ups…")
        self._seed_cafeteria_comprehensive(students, admin)

        self.stdout.write("  Seeding hostel attendance and leave records…")
        self._seed_hostel_comprehensive(students, admin)

        self.stdout.write("  Seeding timetable duty slots for staff…")
        self._seed_timetable_comprehensive(terms)

        self.stdout.write("  Seeding transport incidents…")
        self._seed_transport_comprehensive()

        self.stdout.write("  Seeding visitor authorized pickups and pickup logs…")
        self._seed_visitor_comprehensive(students, admin)

        self.stdout.write("  Seeding library reservations, inventory audit and acquisition requests…")
        self._seed_library_comprehensive(admin)

        self.stdout.write("  Seeding e-learning quiz attempts…")
        self._seed_elearning_comprehensive(students)

        self.stdout.write("  Seeding maintenance checklist items…")
        self._seed_maintenance_comprehensive()

        self.stdout.write("  Seeding school store (categories, items, transactions, orders)…")
        self._seed_store_comprehensive(admin)

        self.stdout.write("  Seeding dispensary (stock, visits, prescriptions)…")
        self._seed_dispensary(students, admin)

        self.stdout.write("  Seeding examination setter assignments…")
        self._seed_exam_setter_assignments(admin)

        self.stdout.write("  Seeding school profile (logo + branding)…")
        self._seed_school_profile()

        self.stdout.write("  Seeding assignments + submissions…")
        self._seed_assignments(students, admin)

        self.stdout.write("  Activating all modules for this tenant (TenantModule)…")
        self._seed_tenant_modules()

    # ── Gradebook + Report Cards ──────────────────────────────────────────────
    def _seed_gradebook_and_reports(self, year, terms, classes):
        import random
        random.seed(42)

        # 1. CBE Grading Scheme — rename legacy KNEC Standard if it exists
        GradingScheme.objects.filter(name="KNEC Standard").update(name="CBE Standard")
        scheme, _ = GradingScheme.objects.get_or_create(
            name="CBE Standard",
            defaults={"is_default": True, "is_active": True},
        )
        # Remove legacy KCSE A-E bands so CBE bands can be inserted cleanly
        GradeBand.objects.filter(scheme=scheme, label__in=["A","A-","B+","B","B-","C+","C","C-","D+","D","D-","E"]).delete()
        CBE_BANDS = [
            ("EE", 86, 100, 4.0, "Exceeding Expectations"),
            ("ME", 61,  85, 3.0, "Meeting Expectations"),
            ("AE", 41,  60, 2.0, "Approaching Expectations"),
            ("BE",  0,  40, 1.0, "Below Expectations"),
        ]
        bands = {}
        for label, mn, mx, pts, rem in CBE_BANDS:
            b, _ = GradeBand.objects.get_or_create(
                scheme=scheme, label=label,
                defaults={"min_score": mn, "max_score": mx, "grade_point": pts, "remark": rem, "is_active": True},
            )
            bands[label] = b

        def score_to_band(score):
            for label, mn, mx, _, _ in CBE_BANDS:
                if mn <= score <= mx:
                    return bands.get(label)
            return None

        # 2. Core subjects to assess
        CORE_CODES = ["MTH", "ENG", "KSW", "BIO", "CHE", "PHY", "HIS", "GEO"]
        core_subjects = list(Subject.objects.filter(code__in=CORE_CODES, is_active=True))
        if not core_subjects:
            core_subjects = list(Subject.objects.filter(is_active=True)[:6])

        term1 = terms[0]
        admin_user = User.objects.filter(is_superuser=True).first()

        # Assessment definitions per term
        ASSESSMENTS = [
            ("CAT 1",    "Test", "2025-02-07",  30, 30.0),
            ("Mid-Term", "Exam", "2025-02-28", 100, 40.0),
            ("CAT 2",    "Test", "2025-03-14",  30, 30.0),
        ]

        total_cards = 0
        total_grades = 0

        # Seed all active classes that have enrolled students
        target_classes = list(SchoolClass.objects.filter(is_active=True))

        for cls in target_classes:
            # Get enrolled students for this class
            enrolled = list(
                Enrollment.objects.filter(
                    school_class=cls, is_active=True
                ).select_related("student")
            )
            students_in_class = [e.student for e in enrolled]
            if not students_in_class:
                continue

            for subject in core_subjects[:6]:
                subject_term_scores = {}  # student_id -> weighted total

                for aname, acat, adate, amax, aweight in ASSESSMENTS:
                    # Generate plausible marks (normal-ish distribution, centre ~58/100)
                    # Scale marks to amax
                    asmnt, _ = Assessment.objects.get_or_create(
                        name=f"{aname} – {subject.code} – {cls.display_name}",
                        defaults={
                            "category": acat,
                            "subject": subject,
                            "class_section": cls,
                            "term": term1,
                            "max_score": amax,
                            "weight_percent": aweight,
                            "date": adate,
                            "is_published": True,
                            "is_active": True,
                        },
                    )

                    for student in students_in_class:
                        # Realistic Kenyan distribution: peak around 55-65%
                        base = random.gauss(58, 15)  # mean 58%, sd 15
                        base = max(5, min(98, base))  # clamp
                        raw = round(base / 100 * amax, 1)
                        pct = round(raw / amax * 100, 2)
                        band = score_to_band(pct)

                        AssessmentGrade.objects.get_or_create(
                            assessment=asmnt,
                            student=student,
                            defaults={
                                "raw_score": raw,
                                "percentage": pct,
                                "grade_band": band,
                                "entered_by": admin_user,
                                "is_active": True,
                            },
                        )
                        total_grades += 1

                        # Accumulate weighted score toward term result
                        contrib = (raw / amax) * 100 * (aweight / 100)
                        subject_term_scores[student.id] = subject_term_scores.get(student.id, 0) + contrib

                # Build TermResults for this subject
                scores = [(sid, sc) for sid, sc in subject_term_scores.items()]
                scores.sort(key=lambda x: -x[1])
                for rank, (sid, total) in enumerate(scores, 1):
                    total_rounded = round(total, 2)
                    band = score_to_band(total_rounded)
                    TermResult.objects.update_or_create(
                        student_id=sid,
                        class_section=cls,
                        term=term1,
                        subject=subject,
                        defaults={
                            "total_score": total_rounded,
                            "grade_band": band,
                            "class_rank": rank,
                            "is_pass": total_rounded >= 40.0,
                            "is_active": True,
                        },
                    )

            # Generate Report Cards (one per student per class per term)
            for student in students_in_class:
                # calculate mean score across subjects for overall grade
                results = TermResult.objects.filter(
                    student=student, class_section=cls, term=term1, is_active=True
                )
                if results.exists():
                    avg = sum(float(r.total_score) for r in results) / results.count()
                    band = score_to_band(round(avg, 2))
                    grade_label = band.label if band else "C"
                else:
                    avg = 55.0
                    grade_label = "C+"

                # rank among class
                class_rank = None
                ranked = list(
                    TermResult.objects.filter(
                        class_section=cls, term=term1, subject=core_subjects[0], is_active=True
                    ).order_by("class_rank")
                )
                for i, tr in enumerate(ranked, 1):
                    if tr.student_id == student.id:
                        class_rank = i
                        break

                REMARKS = [
                    "Excellent performance! Keep it up.",
                    "Very good effort. Aim higher next term.",
                    "Satisfactory performance. More effort needed.",
                    "Needs to improve concentration in class.",
                    "Good improvement shown this term.",
                ]
                PRINCIPAL = [
                    "A diligent student. Continue with the same spirit.",
                    "Good performance. We expect even better results.",
                    "Consistent effort. Keep working hard.",
                ]
                rc, _ = ReportCard.objects.get_or_create(
                    student=student,
                    class_section=cls,
                    term=term1,
                    academic_year=year,
                    defaults={
                        "status": "Approved",
                        "overall_grade": grade_label,
                        "class_rank": class_rank,
                        "attendance_days": random.randint(58, 65),
                        "teacher_remarks": random.choice(REMARKS),
                        "principal_remarks": random.choice(PRINCIPAL),
                        "approved_by": admin_user,
                        "approved_at": timezone.now(),
                        "is_active": True,
                    },
                )
                total_cards += 1

        self.stdout.write(
            f"    → Grades entered: {total_grades}, Report cards: {total_cards}"
        )

    # ── Kenyan CBE Curriculum (Departments + Subjects) ────────────────────────
    def _seed_curriculum_base(self):
        # Departments
        DEPT_DATA = [
            ("Sciences", "Biology, Chemistry, Physics, Agriculture"),
            ("Mathematics", "Mathematics, Additional Mathematics"),
            ("Languages", "English, Kiswahili, French, German"),
            ("Humanities", "History & Government, Geography, CRE, IRE, HRE"),
            ("Technical", "Computer Studies, Home Science, Art & Design"),
            ("Business", "Business Studies, Economics, Accounting"),
            ("Creative Arts", "Music, Drama, Art"),
            ("Physical Education", "Physical Education & Sports"),
        ]
        depts = {}
        for name, desc in DEPT_DATA:
            d, _ = Department.objects.get_or_create(
                name=name, defaults={"description": desc, "is_active": True}
            )
            depts[name] = d

        # Kenyan CBE Junior and Senior Secondary subjects
        SUBJECT_DATA = [
            # (name, code, dept_key, subject_type, periods_week)
            ("Mathematics",              "MTH", "Mathematics",  "Compulsory", 8),
            ("English",                  "ENG", "Languages",    "Compulsory", 8),
            ("Kiswahili",                "KSW", "Languages",    "Compulsory", 5),
            ("Biology",                  "BIO", "Sciences",     "Compulsory", 4),
            ("Chemistry",                "CHE", "Sciences",     "Compulsory", 4),
            ("Physics",                  "PHY", "Sciences",     "Compulsory", 4),
            ("History & Government",     "HIS", "Humanities",   "Elective",   4),
            ("Geography",                "GEO", "Humanities",   "Elective",   4),
            ("Christian Religious Ed.",  "CRE", "Humanities",   "Elective",   4),
            ("Business Studies",         "BST", "Business",     "Elective",   4),
            ("Agriculture",              "AGR", "Sciences",     "Elective",   4),
            ("Computer Studies",         "CMP", "Technical",    "Elective",   4),
            ("Home Science",             "HMS", "Technical",    "Elective",   4),
            ("Art & Design",             "ART", "Creative Arts","Elective",   3),
            ("Music",                    "MUS", "Creative Arts","Elective",   3),
            ("Physical Education",       "PE",  "Physical Education", "Compulsory", 3),
            # CBE strands
            ("Integrated Science",       "ISC", "Sciences",     "Compulsory", 5),
            ("Social Studies",           "SST", "Humanities",   "Compulsory", 5),
            ("Creative Arts & Sports",   "CAS", "Creative Arts","Compulsory", 4),
            ("Pre-Technical Studies",    "PTS", "Technical",    "Compulsory", 4),
            ("Life Skills Education",    "LSE", "Humanities",   "Compulsory", 2),
            ("Religious Education",      "RE",  "Humanities",   "Elective",   2),
        ]
        for name, code, dept_key, s_type, periods in SUBJECT_DATA:
            dept = depts.get(dept_key)
            Subject.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "department": dept,
                    "subject_type": s_type,
                    "periods_week": periods,
                    "is_active": True,
                },
            )

    # ── Roles & Modules ─────────────────────────────────────────────────────
    def _seed_roles_modules(self):
        for name, desc in iter_seed_role_definitions():
            Role.objects.get_or_create(name=name, defaults={"description": desc})

        try:
            for key, name, _ in ALL_MODULES:
                Module.objects.get_or_create(key=key, defaults={"name": name})
        except ImportError:
            pass

    # ── Admin User ───────────────────────────────────────────────────────────
    def _seed_admin_user(self):
        user, _ = User.objects.get_or_create(
            username="Riqs#.",
            defaults={
                "email": "emurithi593@gmail.com",
                "first_name": "Principal",
                "last_name": "Mwangi",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if not user.check_password("Ointment.54.#"):
            user.set_password("Ointment.54.#")
            user.save()
        role = Role.objects.get(name="TENANT_SUPER_ADMIN")
        UserProfile.objects.get_or_create(user=user, defaults={"role": role})
        return user

    # ── Academic Structure ────────────────────────────────────────────────────
    def _seed_academics(self):
        year, _ = AcademicYear.objects.get_or_create(
            name="2025",
            defaults={
                "start_date": date(2025, 1, 6),
                "end_date": date(2025, 11, 28),
                "is_active": True,
            },
        )

        term_defs = [
            ("Term 1 2025", date(2025, 1, 6), date(2025, 4, 4)),
            ("Term 2 2025", date(2025, 4, 28), date(2025, 8, 1)),
            ("Term 3 2025", date(2025, 8, 25), date(2025, 11, 28)),
        ]
        terms = []
        for i, (name, start, end) in enumerate(term_defs):
            t, _ = Term.objects.get_or_create(
                academic_year=year,
                name=name,
                defaults={"start_date": start, "end_date": end, "is_active": i == 0},
            )
            terms.append(t)

        classes = {}
        for grade in GRADES:
            classes[grade] = {}
            for stream in STREAMS:
                cls, _ = SchoolClass.objects.get_or_create(
                    name=grade,
                    stream=stream,
                    academic_year=year,
                    defaults={"is_active": True},
                )
                classes[grade][stream] = cls

        return year, terms, classes

    # ── Staff ────────────────────────────────────────────────────────────────
    def _seed_staff(self, admin_user):
        teacher_role = Role.objects.filter(name="TEACHER").first()
        for i, (first, last, subject, phone) in enumerate(TEACHER_DATA):
            emp_id = f"TCH{str(i + 1).zfill(3)}"
            Staff.objects.get_or_create(
                employee_id=emp_id,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "role": "Teacher",
                    "phone": phone,
                },
            )
            username = f"{first.lower()}.{last.lower()}"
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "email": f"{username}@stmarysnairobi.ac.ke",
                },
            )
            if created:
                user.set_password("teacher123")
                user.save()
            if teacher_role:
                UserProfile.objects.get_or_create(user=user, defaults={"role": teacher_role})

        # Non-teaching staff
        for i, (first, last, role, phone) in enumerate(NON_TEACHING_STAFF_DATA):
            emp_id = f"NTS{str(i + 1).zfill(3)}"
            Staff.objects.get_or_create(
                employee_id=emp_id,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "role": role,
                    "phone": phone,
                },
            )

        # Seed HR leave requests for approval
        try:
            from hr.models import LeaveRequest, LeaveType
            lt, _ = LeaveType.objects.get_or_create(
                name="Annual Leave",
                defaults={"max_days_year": 21, "is_paid": True},
            )
            leave_data = [
                ("samuel.otieno", date(2025, 3, 10), date(2025, 3, 14), "Personal matter"),
                ("grace.wanjiku", date(2025, 3, 17), date(2025, 3, 19), "Medical appointment"),
                ("david.mwangi", date(2025, 4, 7), date(2025, 4, 11), "Family event"),
                ("faith.njoroge", date(2025, 2, 24), date(2025, 2, 28), "Rest leave"),
            ]
            for username, start, end, reason in leave_data:
                user = User.objects.filter(username=username).first()
                if user:
                    staff = Staff.objects.filter(
                        first_name=user.first_name, last_name=user.last_name
                    ).first()
                    if staff:
                        LeaveRequest.objects.get_or_create(
                            employee=staff,
                            start_date=start,
                            defaults={
                                "end_date": end,
                                "leave_type": lt,
                                "reason": reason,
                                "status": "Pending",
                            },
                        )
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"    Leave requests skipped: {e}"))

    # ── Students ─────────────────────────────────────────────────────────────
    def _seed_students(self, classes, terms):
        students = []
        all_names = (
            [(f, l, "M") for f, l in KENYAN_MALE_NAMES] +
            [(f, l, "F") for f, l in KENYAN_FEMALE_NAMES]
        )
        form_stream_pairs = [
            (g, s) for g in GRADES for s in STREAMS
        ]

        for i, (first, last, gender) in enumerate(all_names):
            adm_no = f"STM{2025}{str(i + 1).zfill(3)}"
            grade, stream = form_stream_pairs[i % len(form_stream_pairs)]
            grade_num = int(grade.split()[-1])
            dob_year = 2025 - (6 + grade_num)
            s, _ = Student.objects.get_or_create(
                admission_number=adm_no,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "gender": gender,
                    "date_of_birth": date(dob_year, random.randint(1, 12), random.randint(1, 28)),
                },
            )
            # Guardian
            g_name = f"Mr./Mrs. {last}"
            Guardian.objects.get_or_create(
                student=s,
                name=g_name,
                defaults={
                    "relationship": "Parent",
                    "phone": f"07{random.randint(10000000, 99999999)}",
                    "email": f"parent.{last.lower()}@gmail.com",
                },
            )
            # Enroll in Term 1 — deactivate any stale enrollments for a
            # different class in the same term so we never have two active
            # enrollments for the same student.
            cls = classes[grade][stream]
            Enrollment.objects.filter(
                student=s,
                term=terms[0],
                is_active=True,
            ).exclude(school_class=cls).update(is_active=False, status="Transferred")
            Enrollment.objects.get_or_create(
                student=s,
                school_class=cls,
                term=terms[0],
                defaults={"is_active": True, "status": "Active"},
            )
            students.append(s)

        return students

    # ── Fees & Invoices ───────────────────────────────────────────────────────
    def _seed_fees(self, year, terms, students):
        # Create fee structures per term
        fee_structs = {}
        for term in terms:
            structs = []
            for name, amount in FEE_ITEMS:
                fs, _ = FeeStructure.objects.get_or_create(
                    name=f"{name} — {term.name}",
                    academic_year=year,
                    term=term,
                    defaults={"amount": amount, "is_active": True},
                )
                structs.append(fs)
            fee_structs[term.id] = structs

        term1 = terms[0]
        structs = fee_structs[term1.id]
        total_term1 = sum(fs.amount for fs in structs)

        # Invoice + payment for each student (idempotent)
        ref_counter = 9000
        for i, student in enumerate(students):
            inv = Invoice.objects.filter(student=student, term=term1).first()
            inv_created = inv is None
            if inv_created:
                inv = Invoice.objects.create(
                    student=student,
                    term=term1,
                    due_date=date(2025, 2, 14),
                    total_amount=total_term1,
                    status="CONFIRMED",
                )
                for fs in structs:
                    InvoiceLineItem.objects.get_or_create(
                        invoice=inv,
                        fee_structure=fs,
                        defaults={
                            "description": fs.name.split(" — ")[0],
                            "amount": fs.amount,
                        },
                    )

            # Varying payment amounts: some full, some partial, some none
            if i % 3 == 0:
                paid_amount = total_term1  # Fully paid
            elif i % 3 == 1:
                paid_amount = total_term1 * Decimal("0.5")  # Half paid
            else:
                paid_amount = Decimal("0")  # Unpaid

            if paid_amount > 0:
                ref_counter += 1
                payment_notes = f"Term 1 2025 payment — {student.admission_number}"
                pmt = Payment.objects.filter(student=student, notes=payment_notes).first()
                if pmt is None:
                    unique_ref = f"RCPT-KE{ref_counter}-{uuid.uuid4().hex[:6].upper()}"
                    pmt = Payment.objects.create(
                        student=student,
                        amount=paid_amount,
                        payment_method=random.choice(["Cash", "M-Pesa", "Bank Transfer", "Cheque"]),
                        reference_number=unique_ref,
                        notes=payment_notes,
                        is_active=True,
                    )
                PaymentAllocation.objects.get_or_create(
                    payment=pmt,
                    invoice=inv,
                    defaults={"amount_allocated": paid_amount},
                )

        # ── Vote Heads ────────────────────────────────────────────────────────
        VOTE_HEAD_DATA = [
            ('Tuition', 'Regular tuition fees', 40.00, 1),
            ('Exam', 'National and internal examination fees', 12.00, 2),
            ('Medical', 'Medical/clinic fund and health services', 8.00, 3),
            ('Activity', 'Co-curricular activities, trips, events', 10.00, 4),
            ('Boarding/Meals', 'Meals, boarding and hostel services', 18.00, 5),
            ('Development', 'School development and building fund', 10.00, 6),
            ('Arrears', 'Arrears carried forward from previous term', 2.00, 7),
        ]
        for name, desc, alloc_pct, order in VOTE_HEAD_DATA:
            VoteHead.objects.get_or_create(
                name=name,
                defaults={
                    'description': desc,
                    'allocation_percentage': Decimal(str(alloc_pct)),
                    'is_preloaded': True,
                    'is_active': True,
                    'order': order,
                }
            )

        # ── Budget Envelopes ──────────────────────────────────────────────────
        term1 = terms[0]
        Budget.objects.get_or_create(
            academic_year=year,
            term=term1,
            name='Term 1 2025 Operational Budget',
            defaults={
                'monthly_budget': Decimal('1800000.00'),
                'quarterly_budget': Decimal('5400000.00'),
                'annual_budget': Decimal('18000000.00'),
                'is_active': True,
                'categories': [
                    {'name': 'Salaries & Allowances', 'amount': 780000},
                    {'name': 'Utilities', 'amount': 85000},
                    {'name': 'Stationery & Supplies', 'amount': 65000},
                    {'name': 'Food & Catering', 'amount': 380000},
                    {'name': 'Maintenance & Repairs', 'amount': 120000},
                    {'name': 'Transport', 'amount': 48000},
                    {'name': 'Security', 'amount': 54000},
                    {'name': 'ICT & Technology', 'amount': 35000},
                    {'name': 'Medical / First Aid', 'amount': 28000},
                    {'name': 'Sports & Co-Curricular', 'amount': 45000},
                    {'name': 'Printing & Communication', 'amount': 22000},
                    {'name': 'Contingency', 'amount': 38000},
                ],
            }
        )

        # ── School Expenses (comprehensive) ───────────────────────────────────
        EXPENSES = [
            ("Salaries", Decimal("780000.00"), "Teaching staff payroll — January 2025", 3),
            ("Salaries", Decimal("420000.00"), "Non-teaching staff payroll — January 2025", 10),
            ("Salaries", Decimal("780000.00"), "Teaching staff payroll — February 2025", 3),
            ("Salaries", Decimal("420000.00"), "Non-teaching staff payroll — February 2025", 10),
            ("Utilities", Decimal("48500.00"), "Electricity bill — January 2025 (KPLC)", 8),
            ("Utilities", Decimal("12000.00"), "Water bill — January 2025 (Nairobi Water)", 8),
            ("Utilities", Decimal("47200.00"), "Electricity bill — February 2025 (KPLC)", 12),
            ("Utilities", Decimal("11500.00"), "Water bill — February 2025 (Nairobi Water)", 15),
            ("Catering", Decimal("185000.00"), "Food supplies — January 2025 (Uchumi Wholesale)", 5),
            ("Catering", Decimal("175000.00"), "Food supplies — February 2025 (Metro Cash & Carry)", 12),
            ("Maintenance", Decimal("38500.00"), "Science lab equipment servicing", 7),
            ("Maintenance", Decimal("22000.00"), "Roof repair — Block B", 14),
            ("Maintenance", Decimal("15500.00"), "Plumbing — hostel blocks A & B", 20),
            ("Maintenance", Decimal("8900.00"), "Electrical repairs — computer lab", 25),
            ("Supplies", Decimal("32000.00"), "Term 1 stationery — exercise books, pens", 4),
            ("Supplies", Decimal("18500.00"), "Printer toner and photocopier paper", 11),
            ("Supplies", Decimal("12000.00"), "Cleaning supplies and detergents", 18),
            ("Transport", Decimal("35000.00"), "Bus fuel — January 2025", 5),
            ("Transport", Decimal("32000.00"), "Bus fuel — February 2025", 12),
            ("Transport", Decimal("8500.00"), "Bus tyre replacement (Route 2)", 20),
            ("Security", Decimal("27000.00"), "Security services — January 2025 (KK Security)", 31),
            ("Security", Decimal("27000.00"), "Security services — February 2025 (KK Security)", 28),
            ("ICT", Decimal("15500.00"), "Internet subscription — January 2025 (Safaricom Fibre)", 2),
            ("ICT", Decimal("15500.00"), "Internet subscription — February 2025 (Safaricom Fibre)", 2),
            ("ICT", Decimal("8900.00"), "Computer lab maintenance contract", 10),
            ("Medical", Decimal("18000.00"), "Medical supplies — clinic restocking", 6),
            ("Medical", Decimal("4500.00"), "First aid kits — 5 classrooms", 18),
            ("Sports", Decimal("22000.00"), "Sports equipment — footballs, nets, jerseys", 8),
            ("Sports", Decimal("15000.00"), "Athletics meet registration fees & transport", 14),
            ("Printing", Decimal("9500.00"), "Term 1 timetables and circulars — printing", 7),
            ("Printing", Decimal("7200.00"), "Report card printing — Term 3 2024", 15),
            # ── March 2025 ────────────────────────────────────────────────────
            ("Salaries", Decimal("780000.00"), "Teaching staff payroll — March 2025", 3),
            ("Salaries", Decimal("420000.00"), "Non-teaching staff payroll — March 2025", 10),
            ("Utilities", Decimal("49100.00"), "Electricity bill — March 2025 (KPLC)", 8),
            ("Utilities", Decimal("11800.00"), "Water bill — March 2025 (Nairobi Water)", 8),
            ("Catering", Decimal("182000.00"), "Food supplies — March 2025 (Uchumi Wholesale)", 5),
            ("Maintenance", Decimal("28000.00"), "Library roof waterproofing", 12),
            ("Maintenance", Decimal("14500.00"), "Gate and perimeter wall repairs", 22),
            ("Supplies", Decimal("21000.00"), "Mid-term stationery restocking", 10),
            ("Transport", Decimal("34000.00"), "Bus fuel — March 2025", 5),
            ("Transport", Decimal("28000.00"), "Driver salaries — March 2025", 10),
            ("Security", Decimal("27000.00"), "Security services — March 2025 (KK Security)", 31),
            ("ICT", Decimal("15500.00"), "Internet subscription — March 2025 (Safaricom Fibre)", 2),
            ("Medical", Decimal("12000.00"), "Clinic restocking — anti-malarials & first aid", 8),
            ("Sports", Decimal("45000.00"), "Football kit, nets & training equipment", 6),
            ("Sports", Decimal("18000.00"), "Inter-school athletics transport & fees", 18),
            ("Printing", Decimal("8500.00"), "Mid-term exam papers printing", 14),
            ("Printing", Decimal("5500.00"), "School newsletter — Term 1 edition", 25),
        ]
        for cat, amt, desc, day in EXPENSES:
            if 'March' in desc:
                month = 3
            elif 'February' in desc:
                month = 2
            else:
                month = 1
            try:
                Expense.objects.create(
                    category=cat, amount=amt,
                    expense_date=date(2025, month, day),
                    description=desc,
                )
            except Exception:
                pass

    # ── Admission Applications ────────────────────────────────────────────────
    def _seed_admissions(self, year, terms):
        candidates = [
            ("Amina", "Hassan", "F", date(2012, 3, 15)),
            ("Caleb", "Kiptanui", "M", date(2012, 7, 22)),
            ("Zipporah", "Muthoni", "F", date(2012, 1, 10)),
            ("Elvis", "Odhiambo", "M", date(2012, 11, 5)),
            ("Vivian", "Chepkemoi", "F", date(2012, 4, 18)),
            ("Arnold", "Gacheru", "M", date(2012, 9, 30)),
            ("Gladys", "Onyango", "F", date(2012, 6, 8)),
            ("Clifford", "Njuguna", "M", date(2012, 2, 14)),
        ]
        statuses = ["Submitted", "Submitted", "Submitted", "Documents Received",
                    "Interview Scheduled", "Assessed", "Submitted", "Documents Received"]

        for i, ((first, last, gender, dob), status) in enumerate(zip(candidates, statuses)):
            num = f"APP2025{str(i + 1).zfill(3)}"
            AdmissionApplication.objects.get_or_create(
                application_number=num,
                defaults={
                    "student_first_name": first,
                    "student_last_name": last,
                    "student_gender": gender,
                    "student_dob": dob,
                    "application_date": date(2024, 11, random.randint(1, 28)),
                    "guardian_name": f"Parent of {first} {last}",
                    "guardian_phone": f"07{random.randint(10000000, 99999999)}",
                    "guardian_email": f"parent.{last.lower()}@gmail.com",
                    "notes": "Applying for Grade 7 admission, 2025 academic year.",
                },
            )

    # ── Maintenance Requests ──────────────────────────────────────────────────
    def _seed_maintenance(self, admin_user):
        try:
            from maintenance.models import MaintenanceCategory, MaintenanceRequest

            cat_names = ["Electrical", "Civil Works", "Plumbing", "ICT Equipment", "Furniture"]
            cats = {}
            for name in cat_names:
                c, _ = MaintenanceCategory.objects.get_or_create(name=name)
                cats[name] = c

            category_map = {
                "Science Lab Equipment Repair": cats["ICT Equipment"],
                "Library Roof Leak": cats["Civil Works"],
                "Computer Lab Projector Fault": cats["ICT Equipment"],
                "Sports Ground Fencing": cats["Civil Works"],
                "Classroom 12B Door Replacement": cats["Civil Works"],
                "Kitchen Exhaust Fan Repair": cats["Electrical"],
                "Dormitory Bunk Beds Repair": cats["Furniture"],
                "School Bus Service": cats["Civil Works"],
            }

            for title, priority, location in MAINTENANCE_ITEMS:
                MaintenanceRequest.objects.get_or_create(
                    title=title,
                    defaults={
                        "description": f"{title} — requires urgent attention at {location}.",
                        "category": category_map.get(title, cats["Civil Works"]),
                        "priority": priority,
                        "status": "Pending",
                        "location": location,
                        "reported_by": admin_user,
                        "cost_estimate": Decimal(str(random.randint(5000, 80000))),
                    },
                )
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"    Maintenance requests skipped: {e}"))

    # ── Communication ─────────────────────────────────────────────────────────
    def _seed_communication(self, students, admin_user):
        announcements_data = [
            ("Term 1 2025 Opening Day", "School will open on Monday 6th January 2025. All students should report by 8:00 AM."),
            ("CBE National Assessment Schedule", "Grade 10 end-of-year national assessments begin on 10th February 2025. Timetables available from the Deputy Principal's office."),
            ("Parents' Meeting — Term 1", "All parents are invited to the annual parents' meeting on 15th February 2025 at 9:00 AM."),
            ("Fee Payment Deadline", "All Term 1 fees must be paid by 14th February 2025. Contact the bursar for payment plans."),
            ("Kenya Science Congress Registration", "Students interested in the Kenya Science Congress should submit proposals to the Head of Science by 20th January."),
        ]
        try:
            from communication.models import Announcement
            for title, body in announcements_data:
                Announcement.objects.get_or_create(
                    title=title,
                    defaults={
                        "body": body,
                        "priority": "Important",
                        "audience_type": "All",
                        "notify_email": True,
                        "notify_sms": True,
                    },
                )
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"    Announcements skipped: {e}"))

        for i, student in enumerate(students[:8]):
            try:
                Message.objects.get_or_create(
                    recipient_type="STUDENT",
                    recipient_id=student.id,
                    subject="Welcome to St. Mary's Nairobi High School",
                    defaults={
                        "body": (
                            f"Dear {student.first_name} {student.last_name},\n\n"
                            "Welcome to St. Mary's Nairobi High School for the 2025 academic year. "
                            "We are committed to providing you with a world-class education that builds "
                            "character, competence, and excellence.\n\n"
                            "Please ensure all fee payments are completed by 14th February 2025.\n\n"
                            "Yours sincerely,\nThe Principal"
                        ),
                        "status": "SENT",
                    },
                )
            except Exception:
                pass

    # ── Library ───────────────────────────────────────────────────────────────
    def _seed_library(self, students, admin_user):
        try:
            from library.models import (
                LibraryCategory, LibraryResource, ResourceCopy,
                LibraryMember, CirculationRule, CirculationTransaction, FineRecord,
            )
        except ImportError:
            self.stdout.write("    Library app not available — skipping")
            return

        import random
        random.seed(99)

        # Categories
        CATS = ['Textbooks', 'Literature', 'Reference', 'Science', 'Humanities', 'Language', 'Mathematics', 'Technology', 'Fiction']
        cats = {}
        for name in CATS:
            c, _ = LibraryCategory.objects.get_or_create(name=name, defaults={'is_active': True})
            cats[name] = c

        # Circulation rules
        for mtype in ['Student', 'Staff']:
            CirculationRule.objects.get_or_create(
                member_type=mtype, resource_type='Book',
                defaults={'max_items': 3 if mtype == 'Student' else 5, 'loan_period_days': 14, 'max_renewals': 2, 'fine_per_day': 5.00, 'is_active': True}
            )

        BOOKS_DATA = [
            ('KLB Mathematics Grade 7', 'Kenya Literature Bureau', 'Mathematics', 'Book', '9789966100', 2022, 8, 'Textbooks'),
            ('KLB Mathematics Grade 8', 'Kenya Literature Bureau', 'Mathematics', 'Book', '9789966101', 2022, 8, 'Textbooks'),
            ('KLB Mathematics Grade 9', 'Kenya Literature Bureau', 'Mathematics', 'Book', '9789966102', 2022, 5, 'Mathematics'),
            ('KLB Mathematics Grade 10', 'Kenya Literature Bureau', 'Mathematics', 'Book', '9789966103', 2023, 5, 'Mathematics'),
            ('KLB Biology Grade 7', 'Kenya Literature Bureau', 'Biology', 'Book', '9789966200', 2022, 8, 'Science'),
            ('KLB Biology Grade 8', 'Kenya Literature Bureau', 'Biology', 'Book', '9789966201', 2022, 8, 'Science'),
            ('KLB Biology Grade 9', 'Kenya Literature Bureau', 'Biology', 'Book', '9789966202', 2023, 6, 'Science'),
            ('KLB Chemistry Grade 8', 'Kenya Literature Bureau', 'Chemistry', 'Book', '9789966300', 2022, 7, 'Science'),
            ('KLB Chemistry Grade 9', 'Kenya Literature Bureau', 'Chemistry', 'Book', '9789966301', 2023, 6, 'Science'),
            ('KLB Physics Grade 8', 'Kenya Literature Bureau', 'Physics', 'Book', '9789966400', 2022, 7, 'Science'),
            ('KLB Physics Grade 9', 'Kenya Literature Bureau', 'Physics', 'Book', '9789966401', 2023, 6, 'Science'),
            ('Things Fall Apart', 'Chinua Achebe', 'English', 'Book', '9780385474542', 1958, 4, 'Literature'),
            ('A Grain of Wheat', 'Ngugi wa Thiong\'o', 'English', 'Book', '9780435906856', 1967, 3, 'Literature'),
            ('The River Between', 'Ngugi wa Thiong\'o', 'English', 'Book', '9780435908843', 1965, 3, 'Literature'),
            ('Blossoms of the Savannah', 'Henry R. Ole Kulet', 'English', 'Book', '9789966254313', 2008, 6, 'Literature'),
            ('Weep Not Child', 'Ngugi wa Thiong\'o', 'English', 'Book', '9780435906863', 1964, 4, 'Literature'),
            ('Kiswahili Sanifu Grade 9', 'Oxford University Press', 'Kiswahili', 'Book', '9780195730883', 2021, 6, 'Language'),
            ('Longman History Grade 9', 'Longman Kenya', 'History', 'Book', '9789966451186', 2022, 5, 'Humanities'),
            ('Oxford Geography Grade 9', 'Oxford Kenya', 'Geography', 'Book', '9780195476804', 2022, 5, 'Humanities'),
            ('Computer Studies Secondary', 'KICD', 'Computer Studies', 'Book', '9789966451001', 2023, 4, 'Technology'),
            ('Business Studies Grade 10', 'Kenya Literature Bureau', 'Business', 'Book', '9789966100789', 2022, 4, 'Textbooks'),
            ('Oral Literature in Africa', 'Ruth Finnegan', 'English', 'Book', '9780198121497', 2012, 2, 'Reference'),
            ('Collins English Dictionary', 'Collins', 'English', 'Book', '9780008309374', 2019, 3, 'Reference'),
            ('Kenya Schools Atlas', 'Macmillan Kenya', 'Geography', 'Book', '9789966190970', 2021, 3, 'Reference'),
            ('CRE Grade 9', 'Longman Kenya', 'CRE', 'Book', '9789966451230', 2022, 4, 'Textbooks'),
            ('Agriculture Grade 8', 'KICD', 'Agriculture', 'Book', '9789966451056', 2021, 4, 'Textbooks'),
            ('Longman English Grade 10', 'Longman Kenya', 'English', 'Book', '9789966451414', 2022, 5, 'Textbooks'),
            ('The Golden Drum', 'Various Authors', 'English', 'Book', '9789966251671', 2015, 3, 'Fiction'),
            ('KLB CRE Grade 7', 'Kenya Literature Bureau', 'CRE', 'Book', '9789966100555', 2022, 4, 'Textbooks'),
            ('Mathematics Revision Guide', 'Longman Kenya', 'Mathematics', 'Book', '9789966451592', 2023, 5, 'Mathematics'),
        ]

        copy_num = 1
        for title, author, subj, rtype, isbn, year, copies, cat_name in BOOKS_DATA:
            resource, _ = LibraryResource.objects.get_or_create(
                isbn=isbn,
                defaults={
                    'title': title, 'authors': author, 'subjects': subj,
                    'resource_type': rtype, 'publication_year': year,
                    'publisher': author, 'language': 'en',
                    'category': cats.get(cat_name),
                    'total_copies': copies,
                    'available_copies': max(0, copies - random.randint(0, min(3, copies))),
                    'is_active': True,
                }
            )
            for j in range(resource.total_copies):
                acc = f'ACC{str(copy_num).zfill(4)}'
                ResourceCopy.objects.get_or_create(
                    accession_number=acc,
                    defaults={
                        'resource': resource,
                        'barcode': f'BAR{copy_num:05d}',
                        'status': 'Available' if j < resource.available_copies else 'Issued',
                        'condition': random.choice(['Excellent', 'Good', 'Good', 'Fair']),
                        'acquisition_date': f'{year}-01-15',
                        'price': round(random.uniform(650, 1800), 2),
                        'is_active': True,
                    }
                )
                copy_num += 1

        # Library Members (students)
        for i, student in enumerate(students):
            user = User.objects.filter(
                first_name=student.first_name, last_name=student.last_name
            ).first()
            LibraryMember.objects.get_or_create(
                member_id=f'LIB-S-{str(i + 1).zfill(3)}',
                defaults={
                    'student': student,
                    'user': user,
                    'member_type': 'Student',
                    'status': 'Active',
                    'is_active': True,
                }
            )

        # ── Circulation transactions and fines ────────────────────────────────
        from datetime import date, timedelta
        from decimal import Decimal as D
        today = date.today()
        members = list(LibraryMember.objects.filter(is_active=True))
        issued_copies = list(ResourceCopy.objects.filter(status='Issued', is_active=True)[:20])
        available_copies = list(ResourceCopy.objects.filter(status='Available', is_active=True)[:10])

        # Only seed if no transactions exist yet
        if CirculationTransaction.objects.count() == 0 and members:
            # 1. Active/overdue transactions — use the "Issued" copies
            for idx, copy in enumerate(issued_copies):
                member = members[idx % len(members)]
                # First 8 copies: issued 20-30 days ago → overdue (14-day loan)
                # Remaining: issued 2-10 days ago → still active
                if idx < 8:
                    issue_dt = today - timedelta(days=random.randint(20, 30))
                else:
                    issue_dt = today - timedelta(days=random.randint(2, 10))
                due_dt = issue_dt + timedelta(days=14)
                overdue = due_dt < today
                overdue_days = max(0, (today - due_dt).days) if overdue else 0
                fine_amt = D(str(round(overdue_days * 5.0, 2))) if overdue else None
                CirculationTransaction.objects.create(
                    copy=copy,
                    member=member,
                    transaction_type='Issue',
                    issue_date=issue_dt,
                    due_date=due_dt,
                    return_date=None,
                    is_overdue=overdue,
                    overdue_days=overdue_days,
                    fine_amount=fine_amt,
                    issued_by=admin_user,
                    is_active=True,
                )

            # 2. Returned transactions — use available copies (returned last week)
            for idx, copy in enumerate(available_copies[:6]):
                member = members[(idx + 3) % len(members)]
                issue_dt = today - timedelta(days=random.randint(15, 25))
                due_dt = issue_dt + timedelta(days=14)
                return_dt = due_dt - timedelta(days=random.randint(0, 3))
                CirculationTransaction.objects.create(
                    copy=copy,
                    member=member,
                    transaction_type='Return',
                    issue_date=issue_dt,
                    due_date=due_dt,
                    return_date=return_dt,
                    is_overdue=False,
                    overdue_days=0,
                    issued_by=admin_user,
                    returned_to=admin_user,
                    condition_at_return='Good',
                    is_active=True,
                )

            # 3. Overdue fines — create FineRecord for first 5 overdue transactions
            overdue_txns = CirculationTransaction.objects.filter(is_overdue=True, fine_amount__gt=0)[:5]
            for txn in overdue_txns:
                FineRecord.objects.get_or_create(
                    transaction=txn,
                    defaults={
                        'member': txn.member,
                        'fine_type': 'Overdue',
                        'amount': txn.fine_amount or D('50.00'),
                        'amount_paid': D('0.00'),
                        'status': 'Pending',
                        'is_active': True,
                    }
                )

            # 4. One paid fine
            if members:
                paid_copy = available_copies[0] if available_copies else issued_copies[0]
                old_issue = today - timedelta(days=30)
                old_due = old_issue + timedelta(days=14)
                old_return = old_due + timedelta(days=7)
                paid_txn = CirculationTransaction.objects.create(
                    copy=paid_copy,
                    member=members[0],
                    transaction_type='Return',
                    issue_date=old_issue,
                    due_date=old_due,
                    return_date=old_return,
                    is_overdue=True,
                    overdue_days=7,
                    fine_amount=D('35.00'),
                    fine_paid=True,
                    issued_by=admin_user,
                    returned_to=admin_user,
                    condition_at_return='Good',
                    is_active=True,
                )
                FineRecord.objects.get_or_create(
                    transaction=paid_txn,
                    defaults={
                        'member': members[0],
                        'fine_type': 'Overdue',
                        'amount': D('35.00'),
                        'amount_paid': D('35.00'),
                        'status': 'Paid',
                        'is_active': True,
                    }
                )

        self.stdout.write(f'    → Library: {LibraryResource.objects.count()} books, {ResourceCopy.objects.count()} copies, {LibraryMember.objects.count()} members, {CirculationTransaction.objects.count()} transactions, {FineRecord.objects.count()} fines')

    # ── E-Learning ────────────────────────────────────────────────────────────
    def _seed_elearning(self, classes, terms, admin_user):
        try:
            from elearning.models import Course, CourseMaterial, OnlineQuiz, QuizQuestion, VirtualSession
        except ImportError:
            self.stdout.write("    E-Learning app not available — skipping")
            return

        import random
        from datetime import date, timedelta
        random.seed(77)

        from school.models import Subject
        from django.contrib.auth.models import User

        term = None
        try:
            from academics.models import Term as AcademicTerm
            term = AcademicTerm.objects.filter(is_active=True).first()
        except Exception:
            pass
        teachers = list(User.objects.exclude(username='Riqs#.')[:12])
        if not teachers:
            teachers = [admin_user]

        # Flatten classes dict {form: {stream: cls}} → flat list
        flat_classes = []
        if isinstance(classes, dict):
            for form_dict in classes.values():
                if isinstance(form_dict, dict):
                    flat_classes.extend(form_dict.values())
                else:
                    flat_classes.append(form_dict)
        else:
            flat_classes = list(classes)

        COURSE_DATA = [
            ('Mathematics Grade 9 — Quadratic Equations', 'MTH301', 'Mathematics', 'Quadratic equations, inequalities and graphs for Grade 9 learners.', 12, 4.8),
            ('Biology Grade 8 — Cell Biology & Genetics', 'BIO201', 'Biology', 'Cell structure, organelles, cell division and basic genetics.', 10, 4.9),
            ('Chemistry Grade 9 — Organic Chemistry', 'CHE301', 'Chemistry', 'Introduction to organic compounds, hydrocarbons and reactions.', 14, 4.7),
            ('Physics Grade 9 — Electromagnetism', 'PHY301', 'Physics', 'Electromagnetic induction, Faraday\'s law and applications.', 11, 4.6),
            ('English Grade 10 — Essay Writing', 'ENG401', 'English', 'Advanced composition, argumentative essays and literary analysis.', 8, 4.5),
            ('Kiswahili Grade 9 — Fasihi', 'KSW301', 'Kiswahili', 'Ushairi, riwaya na tamthilia — uchambuzi wa kina.', 9, 4.4),
            ('History Grade 9 — Nationalism in Africa', 'HIS301', 'History', 'African nationalism, independence movements and post-colonial Africa.', 7, 4.3),
            ('Geography Grade 8 — Climatology', 'GEO201', 'Geography', 'World climate zones, weather patterns and climate change.', 8, 4.5),
            ('Computer Studies Grade 9 — Programming', 'COM301', 'Computer Studies', 'Introduction to Python programming, algorithms and data structures.', 10, 4.8),
            ('Business Studies Grade 10 — Entrepreneurship', 'BST401', 'Business Studies', 'Business planning, financial literacy and entrepreneurial skills.', 6, 4.2),
            ('Agriculture Grade 8 — Crop Production', 'AGR201', 'Agriculture', 'Soil science, crop husbandry and sustainable farming practices.', 7, 4.4),
            ('Mathematics Grade 10 — Matrices & Calculus', 'MTH401', 'Mathematics', 'Matrices, transformations, differentiation and integration.', 14, 4.9),
        ]

        MATERIAL_TYPES = ['PDF', 'Video', 'Note', 'Presentation']
        created_count = 0

        for i, (title, code, subject_name, desc, lessons, rating) in enumerate(COURSE_DATA):
            teacher = teachers[i % len(teachers)]
            subject = Subject.objects.filter(name__icontains=subject_name.split()[0]).first()
            school_class = flat_classes[i % len(flat_classes)] if flat_classes else None

            course, created = Course.objects.get_or_create(
                title=title,
                defaults={
                    'teacher': teacher,
                    'subject': subject,
                    'school_class': school_class,
                    'term': term,
                    'description': desc,
                    'is_published': True,
                }
            )
            if not created:
                continue
            created_count += 1

            # Add materials
            material_titles = [
                (f'{title} — Week 1 Notes', 'PDF'),
                (f'{title} — Introduction Video', 'Video'),
                (f'{title} — Week 2 Notes', 'PDF'),
                (f'{title} — Practice Exercises', 'Note'),
                (f'{title} — Revision Summary', 'Presentation'),
            ]
            for seq, (mat_title, mat_type) in enumerate(material_titles[:3], 1):
                CourseMaterial.objects.get_or_create(
                    course=course,
                    title=mat_title,
                    defaults={
                        'material_type': mat_type,
                        'content': f'Study notes for {title}. Topic {seq}: key concepts and worked examples.',
                        'sequence': seq,
                        'is_active': True,
                    }
                )

            # Add a quiz
            quiz, _ = OnlineQuiz.objects.get_or_create(
                course=course,
                title=f'{title} — End of Topic Quiz',
                defaults={
                    'instructions': 'Answer all questions. Select the best answer for each.',
                    'time_limit_minutes': 30,
                    'max_attempts': 2,
                    'is_published': True,
                }
            )

            # Add questions
            SAMPLE_QUESTIONS = [
                ('What is the main topic covered in this course?', 'A', 'The course subject', 'Mathematics', 'English', 'History'),
                ('Which method is used to solve quadratic equations?', 'B', 'Factorisation', 'Factorisation', 'Painting', 'Singing'),
                ('What does CBE stand for in Kenyan education?', 'A', 'Competency Based Education', 'Competency Based Education', 'Central Bank Committee', 'Class Based Content'),
            ]
            for seq, (qtext, ans, opt_a, opt_b, opt_c, opt_d) in enumerate(SAMPLE_QUESTIONS[:2], 1):
                if not quiz.questions.filter(sequence=seq).exists():
                    QuizQuestion.objects.create(
                        quiz=quiz,
                        question_text=qtext,
                        question_type='MCQ',
                        option_a=opt_a, option_b=opt_b, option_c=opt_c, option_d=opt_d,
                        correct_answer=ans,
                        marks=5,
                        sequence=seq,
                    )

            # Add a virtual session
            session_date = date.today() + timedelta(days=random.randint(1, 14))
            VirtualSession.objects.get_or_create(
                course=course,
                title=f'{title} — Live Q&A Session',
                defaults={
                    'session_date': session_date,
                    'start_time': '14:00:00',
                    'end_time': '15:30:00',
                    'platform': random.choice(['Zoom', 'Google Meet']),
                    'meeting_link': f'https://meet.example.com/{code.lower()}-session',
                    'notes': f'Live interactive session for {title}. Come prepared with questions.',
                }
            )

        self.stdout.write(f'    → E-Learning: {Course.objects.count()} courses, {CourseMaterial.objects.count()} materials, {OnlineQuiz.objects.count()} quizzes')

    # ── Cafeteria ─────────────────────────────────────────────────────────────
    def _seed_cafeteria(self, students):
        try:
            from cafeteria.models import MealPlan, WeeklyMenu, StudentMealEnrollment
        except ImportError:
            self.stdout.write("    Cafeteria app not available — skipping")
            return

        from datetime import date

        # Meal plans
        plans_data = [
            ('Full Board', 'Three meals daily — breakfast, lunch, and supper', 450),
            ('Lunch Only', 'Monday–Friday lunch only', 180),
            ('Breakfast & Lunch', 'Morning and afternoon meals', 320),
        ]
        plans = []
        for name, desc, price in plans_data:
            p, _ = MealPlan.objects.get_or_create(name=name, defaults={'description': desc, 'price_per_day': price, 'is_active': True})
            plans.append(p)

        # Weekly menus
        MENU_DATA = [
            ('monday', 'Uji wa Mtama + Bread + Tea', 'Rice & Beef Stew + Kachumbari', 'Githeri + Avocado'),
            ('tuesday', 'Porridge + Eggs + Chapati', 'Ugali + Sukuma Wiki + Beef', 'Ugali + Beans + Cabbage'),
            ('wednesday', 'Mahamri + Tea + Banana', 'Pilau + Kachumbari + Salad', 'Rice + Fish + Spinach'),
            ('thursday', 'Bread + Butter + Tea', 'Ugali + Fried Chicken + Coleslaw', 'Matoke + Beef Stew'),
            ('friday', 'Porridge + Mandazi', 'Biryani + Raita + Juice', 'Chapati + Lentil Soup'),
        ]
        menu_kwargs = {}
        for day, bfst, lunch, supper in MENU_DATA:
            menu_kwargs[f'{day}_breakfast'] = bfst
            menu_kwargs[f'{day}_lunch'] = lunch
            menu_kwargs[f'{day}_supper'] = supper

        WeeklyMenu.objects.get_or_create(
            week_start=date(2025, 3, 10),
            meal_plan=plans[0],
            defaults=menu_kwargs
        )

        # Enroll students
        import random
        random.seed(77)
        for student in students:
            plan = random.choice(plans)
            try:
                StudentMealEnrollment.objects.get_or_create(
                    student=student,
                    defaults={
                        'meal_plan': plan,
                        'is_active': True,
                    }
                )
            except Exception:
                pass

        self.stdout.write(f'    → Cafeteria: {MealPlan.objects.count()} meal plans, {WeeklyMenu.objects.count()} weekly menus, {StudentMealEnrollment.objects.count()} enrollments')

    # ── Sports ────────────────────────────────────────────────────────────────
    def _seed_sports(self, students, admin_user):
        try:
            from sports.models import Club, ClubMembership, Tournament, StudentAward
        except ImportError:
            self.stdout.write("    Sports app not available — skipping")
            return

        import random
        random.seed(55)

        CLUBS_DATA = [
            ('Football Team', 'Sports', 'Monday', '16:00'),
            ('Volleyball Team', 'Sports', 'Tuesday', '16:00'),
            ('Athletics Club', 'Sports', 'Wednesday', '15:30'),
            ('Basketball Team', 'Sports', 'Thursday', '16:00'),
            ('Swimming Club', 'Sports', 'Friday', '15:00'),
            ('Debate Club', 'Academic', 'Tuesday', '14:00'),
            ('Science Club', 'Academic', 'Wednesday', '14:00'),
            ('Drama Club', 'Arts', 'Friday', '14:00'),
            ('Music Club', 'Arts', 'Monday', '14:00'),
            ('Environmental Club', 'Community', 'Thursday', '14:00'),
        ]
        clubs = []
        for name, ctype, day, time in CLUBS_DATA:
            c, _ = Club.objects.get_or_create(
                name=name,
                defaults={'club_type': ctype, 'patron': admin_user, 'meeting_day': day, 'meeting_time': time, 'is_active': True}
            )
            clubs.append(c)

        # Memberships
        for student in students:
            selected = random.sample(clubs, k=random.randint(1, 3))
            for club in selected:
                try:
                    ClubMembership.objects.get_or_create(
                        student=student, club=club,
                        defaults={'is_active': True}
                    )
                except Exception:
                    pass

        # Tournaments
        TOURNAMENTS = [
            ('Inter-School Football Championship 2025', clubs[0], '2025-03-15', '2025-03-16', 'Nyayo Stadium'),
            ('National Science Congress 2025', clubs[6], '2025-04-10', '2025-04-11', 'Kenyatta University'),
            ('Music & Drama Festival 2025', clubs[7], '2025-05-20', '2025-05-22', 'Kenya National Theatre'),
            ('Athletics Meet 2025', clubs[2], '2025-06-05', '2025-06-06', 'Kasarani Stadium'),
        ]
        for name, club, start, end, loc in TOURNAMENTS:
            try:
                Tournament.objects.get_or_create(
                    name=name,
                    defaults={'club': club, 'start_date': start, 'end_date': end, 'location': loc}
                )
            except Exception:
                pass

        # Awards
        from datetime import date as ddate
        AWARDS = [
            ('Best Athlete of the Year', 'Sports', '2024-11-30'),
            ('Top Debater', 'Academic', '2024-10-15'),
            ('Most Improved Student', 'Academic', '2024-11-30'),
            ('Sports Captain', 'Sports', '2024-07-01'),
            ('Academic Excellence Award', 'Academic', '2024-11-30'),
            ('Community Service Award', 'Community', '2024-11-15'),
            ('Best Drama Performance', 'Arts', '2024-05-22'),
            ('Chess Champion', 'Academic', '2024-09-10'),
            ('Best Goalkeeper', 'Sports', '2024-03-16'),
            ('Music Talent Award', 'Arts', '2024-11-20'),
        ]
        for i, student in enumerate(students[:10]):
            aname, acat, adate = AWARDS[i]
            try:
                StudentAward.objects.get_or_create(
                    student=student,
                    award_name=aname,
                    defaults={
                        'category': acat,
                        'award_date': adate,
                        'awarded_by': 'The Principal',
                        'description': f'Awarded for outstanding performance in {acat.lower()}'
                    }
                )
            except Exception:
                pass

        self.stdout.write(f'    → Sports: {Club.objects.count()} clubs, {ClubMembership.objects.count()} memberships, {Tournament.objects.count()} tournaments')

    # ── Assets ────────────────────────────────────────────────────────────────
    def _seed_assets(self, admin_user):
        try:
            from assets.models import AssetCategory, Asset
        except ImportError:
            self.stdout.write("    Assets app not available — skipping")
            return

        import random
        random.seed(33)
        from datetime import date

        CATEGORIES = [
            ('Furniture', 'Desks, chairs, cabinets'),
            ('Electronics', 'Computers, projectors, TVs'),
            ('Laboratory', 'Lab equipment and apparatus'),
            ('Sports Equipment', 'Balls, nets, gym equipment'),
            ('Library', 'Bookshelves, reading tables'),
            ('Kitchen', 'Cooking equipment and utensils'),
            ('Transport', 'School buses and vehicles'),
            ('Office', 'Office furniture and equipment'),
        ]
        cats = {}
        for name, desc in CATEGORIES:
            c, _ = AssetCategory.objects.get_or_create(name=name, defaults={'description': desc, 'is_active': True})
            cats[name] = c

        ASSETS_DATA = [
            ('AST-001', 'Classroom Desk Set (30 units)', 'Furniture', 'Grade 8 East', 2022, 45000, 0.75),
            ('AST-002', 'HP ProBook Laptops (15 units)', 'Electronics', 'Computer Lab', 2023, 750000, 0.85),
            ('AST-003', 'Epson Projector', 'Electronics', 'Main Hall', 2022, 85000, 0.70),
            ('AST-004', 'Science Lab Microscopes (10 units)', 'Laboratory', 'Biology Lab', 2021, 250000, 0.65),
            ('AST-005', 'Chemistry Burette Set', 'Laboratory', 'Chemistry Lab', 2022, 45000, 0.80),
            ('AST-006', 'Football (Size 5 — 8 units)', 'Sports Equipment', 'Sports Store', 2024, 16000, 0.95),
            ('AST-007', 'Volleyball Net + Posts', 'Sports Equipment', 'Sports Ground', 2023, 28000, 0.90),
            ('AST-008', 'Library Shelving Units (12)', 'Library', 'Library', 2020, 96000, 0.60),
            ('AST-009', 'Industrial Cooking Range', 'Kitchen', 'Kitchen', 2021, 380000, 0.70),
            ('AST-010', 'Isuzu School Bus', 'Transport', 'Garage', 2022, 4500000, 0.75),
            ('AST-011', 'Office Photocopier', 'Office', 'Admin Block', 2023, 180000, 0.88),
            ('AST-012', 'Teacher Whiteboard 120×240 (17 units)', 'Furniture', 'Various Classes', 2022, 85000, 0.80),
            ('AST-013', 'Biology Lab Specimens Set', 'Laboratory', 'Biology Lab', 2022, 35000, 0.75),
            ('AST-014', 'Desktop Computers (20 units)', 'Electronics', 'Computer Lab', 2022, 1200000, 0.72),
            ('AST-015', 'PA System + Microphones', 'Electronics', 'Assembly Hall', 2023, 145000, 0.90),
        ]
        for code, name, cat_name, loc, year, cost, value_factor in ASSETS_DATA:
            try:
                Asset.objects.get_or_create(
                    asset_code=code,
                    defaults={
                        'name': name,
                        'category': cats.get(cat_name),
                        'location': loc,
                        'purchase_date': date(year, 3, 15),
                        'purchase_cost': cost,
                        'current_value': round(cost * value_factor, 2),
                        'status': 'Active',
                    }
                )
            except Exception:
                pass

        self.stdout.write(f'    → Assets: {AssetCategory.objects.count()} categories, {Asset.objects.count()} assets')

    # ── Transport ─────────────────────────────────────────────────────────────
    def _seed_transport(self, students, terms):
        try:
            from transport.models import Vehicle, Route, RouteStop, StudentTransport
        except ImportError:
            self.stdout.write("    Transport app not available — skipping")
            return

        import random
        random.seed(42)

        VEHICLES_DATA = [
            ('KCB 123A', 'Isuzu', 'NQR Bus', 52),
            ('KDA 456B', 'Toyota', 'Coaster', 30),
            ('KDB 789C', 'Isuzu', 'NQR Bus', 52),
            ('KCA 321D', 'Mitsubishi', 'Rosa Bus', 42),
        ]
        vehicles = []
        for reg, make, model, cap in VEHICLES_DATA:
            v, _ = Vehicle.objects.get_or_create(
                registration=reg,
                defaults={'make': make, 'model': model, 'capacity': cap, 'status': 'Active'}
            )
            vehicles.append(v)

        ROUTES_DATA = [
            ('Westlands – Parklands Route', vehicles[0], 'BOTH'),
            ('Karen – Langata Route', vehicles[1], 'BOTH'),
            ('Eastlands – Umoja Route', vehicles[2], 'BOTH'),
            ('South B – Nairobi West Route', vehicles[3], 'BOTH'),
        ]
        routes = []
        for name, veh, direction in ROUTES_DATA:
            r, _ = Route.objects.get_or_create(
                name=name,
                defaults={'vehicle': veh, 'direction': direction, 'is_active': True}
            )
            routes.append(r)

        STOPS_DATA = [
            (routes[0], [('Westlands Roundabout', 1, '06:45'), ('Museum Hill', 2, '06:55'), ('Parklands Stage', 3, '07:05'), ('State House Road', 4, '07:15')]),
            (routes[1], [('Karen Shopping Centre', 1, '06:30'), ('Hardy', 2, '06:40'), ('Langata Road', 3, '06:55'), ('Bomas Junction', 4, '07:10')]),
            (routes[2], [('Umoja 1 Stage', 1, '06:20'), ('Fedha Estate', 2, '06:30'), ('Pipeline', 3, '06:45'), ('Industrial Area', 4, '07:00')]),
            (routes[3], [('South B Stage', 1, '06:35'), ('Nairobi West', 2, '06:45'), ('Wilson Airport', 3, '07:00'), ('Community', 4, '07:10')]),
        ]
        all_stops = {}
        for route, stops in STOPS_DATA:
            all_stops[route.id] = []
            for stop_name, seq, time in stops:
                s, _ = RouteStop.objects.get_or_create(
                    route=route, sequence=seq,
                    defaults={'stop_name': stop_name, 'estimated_time': time}
                )
                all_stops[route.id].append(s)

        try:
            from academics.models import Term as AcademicsTerm
            term1 = AcademicsTerm.objects.first()
        except Exception:
            term1 = None
        day_students = random.sample(list(students), min(30, len(students)))
        for i, student in enumerate(day_students):
            route = routes[i % len(routes)]
            stops_list = all_stops.get(route.id, [])
            stop = random.choice(stops_list) if stops_list else None
            try:
                StudentTransport.objects.get_or_create(
                    student=student, term=term1,
                    defaults={'route': route, 'boarding_stop': stop, 'is_active': True}
                )
            except Exception:
                pass

        self.stdout.write(f'    → Transport: {Vehicle.objects.count()} vehicles, {Route.objects.count()} routes, {StudentTransport.objects.count()} assignments')

    # ── Hostel ────────────────────────────────────────────────────────────────
    def _seed_hostel(self, students, terms):
        try:
            from hostel.models import Dormitory, BedSpace, HostelAllocation
        except ImportError:
            self.stdout.write("    Hostel app not available — skipping")
            return

        import random
        from datetime import date
        random.seed(88)

        DORMS_DATA = [
            ('Boys Wing A', 'Male', 60),
            ('Boys Wing B', 'Male', 60),
            ('Girls Wing A', 'Female', 60),
            ('Girls Wing B', 'Female', 60),
        ]
        dorms = []
        for name, gender, cap in DORMS_DATA:
            d, _ = Dormitory.objects.get_or_create(name=name, defaults={'gender': gender, 'capacity': cap})
            dorms.append(d)

        for dorm in dorms:
            for bed_num in range(1, 31):
                BedSpace.objects.get_or_create(
                    dormitory=dorm, bed_number=f'B{bed_num:02d}',
                    defaults={'is_occupied': False, 'is_active': True}
                )

        try:
            from academics.models import Term as AcademicsTerm
            term1 = AcademicsTerm.objects.first()
        except Exception:
            term1 = None
        boarding_students = random.sample(list(students), min(40, len(students)))
        for i, student in enumerate(boarding_students):
            dorm = dorms[i % len(dorms)]
            bed_num = f'B{(i // len(dorms) + 1):02d}'
            bed = BedSpace.objects.filter(dormitory=dorm, bed_number=bed_num, is_occupied=False).first()
            if bed:
                try:
                    HostelAllocation.objects.get_or_create(
                        student=student,
                        term=term1,
                        defaults={
                            'bed': bed,
                            'check_in_date': date(2025, 1, 6),
                            'status': 'Active',
                        }
                    )
                except Exception:
                    pass

        self.stdout.write(f'    → Hostel: {Dormitory.objects.count()} dorms, {BedSpace.objects.count()} beds, {HostelAllocation.objects.count()} allocations')

    # ── Timetable ─────────────────────────────────────────────────────────────
    def _seed_timetable(self, classes, terms, admin_user):
        try:
            from timetable.models import TimetableSlot
        except ImportError:
            self.stdout.write("    Timetable app not available — skipping")
            return

        from django.contrib.auth import get_user_model
        User = get_user_model()

        term1 = terms[0] if terms else None
        subjects = list(Subject.objects.filter(is_active=True)[:8])
        teachers = list(User.objects.filter(is_staff=False, is_superuser=False)[:8])

        PERIODS = [
            (1, '07:30', '08:20'),
            (2, '08:20', '09:10'),
            (3, '09:10', '10:00'),
            (4, '10:20', '11:10'),
            (5, '11:10', '12:00'),
            (6, '13:00', '13:50'),
            (7, '13:50', '14:40'),
            (8, '14:40', '15:30'),
        ]
        ROOMS = ['Room 1A', 'Room 1B', 'Room 2A', 'Room 2B', 'Room 3A', 'Room 3B', 'Lab 1', 'Lab 2']

        created = 0
        # Prefer CBE Grade 7-10 classes; fall back to any 4 active classes.
        all_classes = list(
            SchoolClass.objects.filter(is_active=True, name__startswith="Grade").order_by("id")[:4]
        )
        if not all_classes:
            all_classes = list(SchoolClass.objects.filter(is_active=True).order_by("id")[:4])
        for day in range(1, 6):
            for cls_idx, school_class in enumerate(all_classes):
                for period_num, start, end in PERIODS:
                    subject = subjects[(cls_idx + period_num) % len(subjects)] if subjects else None
                    teacher = teachers[(cls_idx + period_num) % len(teachers)] if teachers else None
                    _, new = TimetableSlot.objects.get_or_create(
                        day_of_week=day,
                        period_number=period_num,
                        school_class=school_class,
                        defaults={
                            'start_time': start,
                            'end_time': end,
                            'subject': subject,
                            'teacher': teacher,
                            'room': ROOMS[(cls_idx + period_num) % len(ROOMS)],
                            'term': term1,
                            'is_active': True,
                        }
                    )
                    if new:
                        created += 1

        self.stdout.write(f'    → Timetable: {TimetableSlot.objects.count()} period slots seeded')

    # ── Visitors ──────────────────────────────────────────────────────────────
    def _seed_visitors(self):
        try:
            from visitor_mgmt.models import Visitor
        except ImportError:
            self.stdout.write("    Visitor management app not available — skipping")
            return

        from datetime import datetime, timedelta
        from django.utils import timezone
        import random
        random.seed(21)

        VISITORS_DATA = [
            ('James Kamau Njoroge', '12345678', '+254721001001', 'Parent', 'Collecting student report card', 'Principal'),
            ('Faith Wanjiru Mwangi', '23456789', '+254722002002', 'Parent', 'Parent-teacher meeting', 'Mr. Ochieng (Grade 8E)'),
            ('George Omondi Otieno', '34567890', '+254723003003', 'Official', 'Ministry of Education inspection', 'Deputy Principal'),
            ('Electrician — John Doe', '45678901', '+254724004004', 'Contractor', 'Electrical fault repair in Science Block', 'Bursar'),
            ('Mary Achieng Ouma', '56789012', '+254725005005', 'Parent', 'Fee balance discussion', 'Bursar'),
            ('Peter Mwangi Kamau', '67890123', '+254726006006', 'Parent', 'Student welfare concern', 'Counsellor'),
            ('KNEC Official — Ms. Ruth', '78901234', '+254727007007', 'Official', 'CBE National Assessment registration', 'Principal'),
            ('Plumber — David Kariuki', '89012345', '+254728008008', 'Contractor', 'Fix blocked drains in hostel block', 'Maintenance'),
            ('Sarah Njeri Kamau', '90123456', '+254729009009', 'Parent', 'Transport fee enquiry', 'Transport Office'),
            ('Leroy Oduya Ochieng', '01234567', '+254720010010', 'Other', 'Alumni visit — career talk', 'Deputy Principal'),
            ('Josephine Wambui', '11223344', '+254721111222', 'Parent', 'Student medical records pickup', 'Nurse'),
            ('Nairobi Water — Technician', '22334455', '+254722222333', 'Contractor', 'Routine water meter reading', 'Bursar'),
        ]
        base_date = timezone.now() - timedelta(days=14)
        for i, (name, id_num, phone, vtype, purpose, host) in enumerate(VISITORS_DATA):
            sign_in = base_date + timedelta(days=i % 10, hours=random.randint(8, 15))
            signed_out = i % 3 != 0
            try:
                if not Visitor.objects.filter(full_name=name, id_number=id_num).exists():
                    v = Visitor(
                        full_name=name,
                        id_number=id_num,
                        phone=phone,
                        visitor_type=vtype,
                        purpose=purpose,
                        host_name=host,
                        badge_number=f'V{(i + 1):03d}',
                        status='Out' if signed_out else 'In',
                        notes='',
                    )
                    v.save()
                    if signed_out:
                        Visitor.objects.filter(pk=v.pk).update(
                            sign_out_time=sign_in + timedelta(hours=random.randint(1, 3))
                        )
            except Exception:
                pass

        self.stdout.write(f'    → Visitors: {Visitor.objects.count()} visitor entries seeded')

    # ── Fee Assignments ────────────────────────────────────────────────────────
    def _seed_fee_assignments(self, terms, students):
        """Link each student to a fee structure from Term 1 (tuition + activity fees)."""
        if not terms or not students:
            return
        term1 = terms[0]
        structs = list(FeeStructure.objects.filter(
            term=term1,
            name__icontains='fee',
            is_active=True,
        )[:8])
        if not structs:
            return
        created = 0
        for i, student in enumerate(students):
            fs = structs[i % len(structs)]
            _, made = FeeAssignment.objects.get_or_create(
                student=student,
                fee_structure=fs,
                defaults={'discount_amount': 0, 'is_active': True},
            )
            if made:
                created += 1
        self.stdout.write(f'    → Fee Assignments: {created} created')

    # ── Chart of Accounts ─────────────────────────────────────────────────────
    def _seed_chart_of_accounts(self):
        ACCOUNTS = [
            ('1001', 'Cash in Hand',                     'ASSET'),
            ('1002', 'M-Pesa Float Account',             'ASSET'),
            ('1003', 'Bank Account — KCB',               'ASSET'),
            ('1004', 'Bank Account — Equity',            'ASSET'),
            ('1010', 'Student Fee Receivables',          'ASSET'),
            ('1020', 'Prepaid Expenses',                 'ASSET'),
            ('1030', 'Stationery & Supplies Inventory',  'ASSET'),
            ('1040', 'Library Books & Resources',        'ASSET'),
            ('1050', 'Furniture and Fixtures',           'ASSET'),
            ('1060', 'Computers & ICT Equipment',        'ASSET'),
            ('1070', 'School Vehicles',                  'ASSET'),
            ('1080', 'Land and Buildings',               'ASSET'),
            ('2001', 'Accounts Payable',                 'LIABILITY'),
            ('2002', 'Fees Received in Advance',         'LIABILITY'),
            ('2003', 'Accrued Staff Salaries',           'LIABILITY'),
            ('2010', 'NHIF/NSSF Payable',               'LIABILITY'),
            ('2020', 'Tax Withholding Payable',          'LIABILITY'),
            ('3001', 'School Development Fund',          'EQUITY'),
            ('3002', 'Retained Surplus',                 'EQUITY'),
            ('3003', 'General Reserve',                  'EQUITY'),
            ('4001', 'Tuition Fees Revenue',             'REVENUE'),
            ('4002', 'Boarding Fees Revenue',            'REVENUE'),
            ('4003', 'Activity Fees Revenue',            'REVENUE'),
            ('4004', 'Cafeteria / Lunch Revenue',        'REVENUE'),
            ('4005', 'ICT Levy Revenue',                 'REVENUE'),
            ('4006', 'Exam Fees Revenue',                'REVENUE'),
            ('4007', 'Transport Fees Revenue',           'REVENUE'),
            ('4010', 'Donations and Grants',             'REVENUE'),
            ('4020', 'Miscellaneous Income',             'REVENUE'),
            ('5001', 'Teaching Staff Salaries',          'EXPENSE'),
            ('5002', 'Non-Teaching Staff Salaries',      'EXPENSE'),
            ('5003', 'NHIF Employer Contribution',       'EXPENSE'),
            ('5004', 'NSSF Employer Contribution',       'EXPENSE'),
            ('5010', 'Electricity and Water',            'EXPENSE'),
            ('5011', 'Telephone and Internet',           'EXPENSE'),
            ('5012', 'Fuel and Lubricants',              'EXPENSE'),
            ('5020', 'Teaching Materials',               'EXPENSE'),
            ('5021', 'Laboratory Supplies',              'EXPENSE'),
            ('5022', 'Library Acquisitions',             'EXPENSE'),
            ('5030', 'Repairs and Maintenance',          'EXPENSE'),
            ('5040', 'Security Services',                'EXPENSE'),
            ('5050', 'Catering / Meals',                 'EXPENSE'),
            ('5060', 'Sports & Extra-curricular',        'EXPENSE'),
            ('5070', 'Advertising and Printing',         'EXPENSE'),
            ('5080', 'Bank Charges',                     'EXPENSE'),
            ('5090', 'Depreciation Expense',             'EXPENSE'),
            ('5099', 'Miscellaneous Expenses',           'EXPENSE'),
        ]
        created = 0
        for code, name, account_type in ACCOUNTS:
            _, was_created = ChartOfAccount.objects.get_or_create(
                code=code,
                defaults={'name': name, 'account_type': account_type, 'is_active': True},
            )
            if was_created:
                created += 1
        self.stdout.write(
            f'    → Chart of Accounts: {created} new accounts added '
            f'(total: {ChartOfAccount.objects.count()})'
        )

    # ── HR Employees ──────────────────────────────────────────────────────────
    def _seed_hr_employees(self):
        try:
            from hr.models import Department as HrDepartment
            from hr.models import Employee
        except ImportError:
            self.stdout.write(self.style.WARNING('    → hr.models.Employee not found — skipped'))
            return

        # Employee.department FK points to school.models.Department
        dept = HrDepartment.objects.filter(is_active=True).first()

        MALE_FIRST = {
            'Samuel', 'David', 'Peter', 'John', 'James', 'George',
            'Joseph', 'Charles', 'Moses', 'Simon', 'Francis', 'James',
            'Michael', 'Daniel', 'Patrick', 'Emmanuel', 'Brian', 'Kevin',
            'Collins', 'Victor', 'Eric', 'Mark', 'Andrew', 'Timothy',
        }

        created = 0
        # Teaching staff
        for i, (first, last, subject, phone) in enumerate(TEACHER_DATA):
            emp_id = f"TCH{str(i + 1).zfill(3)}"
            gender = 'Male' if first in MALE_FIRST else 'Female'
            _, was_created = Employee.objects.get_or_create(
                employee_id=emp_id,
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'date_of_birth': date(1985, (i % 12) + 1, 15),
                    'gender': gender,
                    'nationality': 'Kenyan',
                    'national_id': f"3{str(20000000 + i).zfill(8)}",
                    'marital_status': 'Married' if i % 2 == 0 else 'Single',
                    'employment_type': 'Full-time',
                    'status': 'Active',
                    'join_date': date(2020, 1, 15),
                    'notice_period_days': 30,
                    'is_active': True,
                    'department': dept,
                },
            )
            if was_created:
                created += 1

        # Non-teaching staff
        for i, (first, last, role, phone) in enumerate(NON_TEACHING_STAFF_DATA):
            emp_id = f"NTS{str(i + 1).zfill(3)}"
            gender = 'Male' if first in MALE_FIRST else 'Female'
            _, was_created = Employee.objects.get_or_create(
                employee_id=emp_id,
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'date_of_birth': date(1982, (i % 12) + 1, 10),
                    'gender': gender,
                    'nationality': 'Kenyan',
                    'national_id': f"2{str(30000000 + i).zfill(8)}",
                    'marital_status': 'Married' if i % 3 != 0 else 'Single',
                    'employment_type': 'Full-time',
                    'status': 'Active',
                    'join_date': date(2018, 3, 1),
                    'notice_period_days': 30,
                    'is_active': True,
                    'department': dept,
                },
            )
            if was_created:
                created += 1

        self.stdout.write(
            f'    → HR Employees: {created} new records created '
            f'(total: {Employee.objects.count()})'
        )

    # ── Staff Management Members ──────────────────────────────────────────────
    def _seed_staff_mgmt_members(self):
        try:
            from staff_mgmt.models import StaffMember
        except ImportError:
            self.stdout.write(self.style.WARNING('    → staff_mgmt.models.StaffMember not found — skipped'))
            return

        MALE_FIRST = {
            'Samuel', 'David', 'Peter', 'John', 'James', 'George',
            'Joseph', 'Charles', 'Moses', 'Simon', 'Francis',
            'Michael', 'Daniel', 'Patrick', 'Emmanuel', 'Brian', 'Kevin',
            'Collins', 'Victor', 'Eric', 'Mark', 'Andrew', 'Timothy',
        }
        ADMIN_ROLES = {
            'Principal', 'Deputy Principal', 'Senior Clerk', 'Bursar',
            'Accounts Assistant', 'School Secretary',
        }

        created = 0
        # Teaching staff
        for i, (first, last, subject, phone) in enumerate(TEACHER_DATA):
            staff_id = f"TCH{str(i + 1).zfill(3)}"
            username = f"{first.lower()}.{last.lower()}"
            user = User.objects.filter(username=username).first()
            gender = 'Male' if first in MALE_FIRST else 'Female'
            _, was_created = StaffMember.objects.get_or_create(
                staff_id=staff_id,
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'gender': gender,
                    'nationality': 'Kenyan',
                    'phone_primary': phone,
                    'phone_alternate': '',
                    'email_personal': '',
                    'email_work': f"{username}@stmarysnairobi.ac.ke",
                    'address_current': 'Nairobi, Kenya',
                    'address_permanent': 'Nairobi, Kenya',
                    'staff_type': 'Teaching',
                    'employment_type': 'Full-time',
                    'status': 'Active',
                    'join_date': date(2020, 1, 15),
                    'is_active': True,
                    'user': user,
                },
            )
            if was_created:
                created += 1

        # Non-teaching staff
        for i, (first, last, role, phone) in enumerate(NON_TEACHING_STAFF_DATA):
            staff_id = f"NTS{str(i + 1).zfill(3)}"
            gender = 'Male' if first in MALE_FIRST else 'Female'
            staff_type = 'Administrative' if role in ADMIN_ROLES else 'Support'
            _, was_created = StaffMember.objects.get_or_create(
                staff_id=staff_id,
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'gender': gender,
                    'nationality': 'Kenyan',
                    'phone_primary': phone,
                    'phone_alternate': '',
                    'email_personal': '',
                    'email_work': '',
                    'address_current': 'Nairobi, Kenya',
                    'address_permanent': 'Nairobi, Kenya',
                    'staff_type': staff_type,
                    'employment_type': 'Full-time',
                    'status': 'Active',
                    'join_date': date(2018, 3, 1),
                    'is_active': True,
                },
            )
            if was_created:
                created += 1

        self.stdout.write(
            f'    → Staff Members: {created} new records created '
            f'(total: {StaffMember.objects.count()})'
        )

    # ── Examinations ─────────────────────────────────────────────────────────
    def _seed_examinations(self, year, terms, classes, admin_user):
        try:
            from examinations.models import (
                ExamSession, ExamPaper, ExamGradeBoundary, ExamResult, ExamSeatAllocation,
            )
        except ImportError:
            self.stdout.write("    Examinations app not available — skipping")
            return
        import random
        random.seed(55)
        from time import time as _time
        from datetime import time as dt_time

        term1 = terms[0] if terms else None

        # 1. Exam sessions
        SESSIONS = [
            ("Mid-Term Examinations – Term 1 2025", date(2025, 2, 24), date(2025, 2, 28), "Completed"),
            ("End-of-Term Examinations – Term 1 2025", date(2025, 3, 24), date(2025, 3, 28), "Completed"),
            ("Mid-Term Examinations – Term 2 2025", date(2025, 6, 9),  date(2025, 6, 13),  "Upcoming"),
        ]
        sessions = []
        for name, start, end, status in SESSIONS:
            s, _ = ExamSession.objects.get_or_create(
                name=name,
                defaults={
                    "term": term1,
                    "academic_year": year,
                    "start_date": start,
                    "end_date": end,
                    "status": status,
                    "notes": f"Formal examination session for {name}.",
                },
            )
            sessions.append(s)

        # 2. Grade boundaries (CBE EE/ME/AE/BE)
        BOUNDARIES = [
            ("EE", 86, 100, "Exceeding Expectations"),
            ("ME", 61,  85, "Meeting Expectations"),
            ("AE", 41,  60, "Approaching Expectations"),
            ("BE",  0,  40, "Below Expectations"),
        ]
        for session in sessions:
            for grade, mn, mx, remarks in BOUNDARIES:
                ExamGradeBoundary.objects.get_or_create(
                    session=session, grade=grade,
                    defaults={"min_marks": mn, "max_marks": mx, "remarks": remarks},
                )

        # 3. ExamPapers for the first (Completed) session – core subjects x Grade 7–10 East
        EXAM_SUBJECTS = ["MTH", "ENG", "KSW", "BIO", "PHY", "CHE", "HIS", "GEO"]
        core_subjects = list(Subject.objects.filter(code__in=EXAM_SUBJECTS, is_active=True))

        flat_classes = []
        if isinstance(classes, dict):
            for form_dict in classes.values():
                if isinstance(form_dict, dict):
                    east = form_dict.get("East")
                    if east:
                        flat_classes.append(east)
        else:
            flat_classes = list(classes)[:4]

        session0 = sessions[0]  # Completed mid-term
        start_time = dt_time(8, 0)
        end_time   = dt_time(10, 0)
        rooms = ["Hall A", "Hall B", "Science Block", "Computer Lab"]
        paper_count = 0
        for i, cls in enumerate(flat_classes):
            for j, subj in enumerate(core_subjects[:6]):
                exam_date = date(2025, 2, 24) + timedelta(days=(j % 5))
                paper, paper_created = ExamPaper.objects.get_or_create(
                    session=session0, subject=subj, school_class=cls,
                    defaults={
                        "exam_date": exam_date,
                        "start_time": start_time,
                        "end_time":   end_time,
                        "exam_room":  rooms[i % len(rooms)],
                        "total_marks": 100,
                        "pass_mark":   40,
                        "invigilator": admin_user,
                    },
                )
                paper_count += 1 if paper_created else 0

                # 4. Seat allocations + results for enrolled students
                enrolled_students = list(
                    Enrollment.objects.filter(school_class=cls, is_active=True)
                    .select_related("student")
                )
                for seat_num, enr in enumerate(enrolled_students[:10], start=1):
                    ExamSeatAllocation.objects.get_or_create(
                        paper=paper, student=enr.student,
                        defaults={"seat_number": str(seat_num)},
                    )
                    score = round(random.gauss(58, 15), 1)
                    score = max(5.0, min(100.0, score))
                    if   score >= 75: grade = "A"
                    elif score >= 60: grade = "B"
                    elif score >= 45: grade = "C"
                    elif score >= 30: grade = "D"
                    else:             grade = "E"
                    ExamResult.objects.get_or_create(
                        paper=paper, student=enr.student,
                        defaults={
                            "marks_obtained": Decimal(str(score)),
                            "grade": grade,
                            "is_absent": False,
                            "entered_by": admin_user,
                        },
                    )

        self.stdout.write(
            f"    → Examinations: {ExamSession.objects.count()} sessions, "
            f"{ExamPaper.objects.count()} papers, "
            f"{ExamResult.objects.count()} results, "
            f"{ExamGradeBoundary.objects.count()} boundaries"
        )

    # ── Alumni ────────────────────────────────────────────────────────────────
    def _seed_alumni(self):
        try:
            from alumni.models import AlumniProfile, AlumniEvent, AlumniEventAttendee, AlumniMentorship, AlumniDonation
        except ImportError:
            self.stdout.write("    Alumni app not available — skipping")
            return
        import random
        random.seed(88)

        ALUMNI_DATA = [
            # (first, last, grad_year, institution, occupation, city)
            ("Peter",     "Kamau",     2015, "University of Nairobi",             "Software Engineer",       "Nairobi"),
            ("Grace",     "Wanjiku",   2014, "Strathmore University",             "Accountant",              "Nairobi"),
            ("David",     "Mwangi",    2013, "Kenya Medical Training College",    "Clinical Officer",        "Nakuru"),
            ("Faith",     "Njoroge",   2016, "Moi University",                    "Secondary School Teacher","Eldoret"),
            ("James",     "Wafula",    2012, "Kenyatta University",               "University Lecturer",     "Nairobi"),
            ("Mary",      "Achieng",   2015, "USIU Africa",                       "Marketing Manager",       "Nairobi"),
            ("John",      "Mutua",     2011, "Technical University of Kenya",     "Civil Engineer",          "Mombasa"),
            ("Susan",     "Wafula",    2014, "KCA University",                    "Business Analyst",        "Nairobi"),
            ("Samuel",    "Kiprotich", 2013, "University of Eldoret",             "Agronomist",              "Rift Valley"),
            ("Esther",    "Chepkoech", 2016, "Daystar University",               "Broadcast Journalist",    "Nairobi"),
            ("George",    "Abuya",     2012, "Maseno University",                 "Economist",               "Kisumu"),
            ("Alice",     "Nyambura",  2015, "Mount Kenya University",            "Pharmacist",              "Thika"),
            ("Kevin",     "Waweru",    2014, "Multimedia University of Kenya",    "Graphic Designer",        "Nairobi"),
            ("Joyce",     "Wangari",   2013, "Egerton University",               "Agricultural Officer",    "Nakuru"),
            ("Victor",    "Cheruiyot", 2017, "Kabarak University",               "Counsellor",              "Nakuru"),
            ("Ruth",      "Adhiambo",  2011, "Catholic University of East Africa","Social Worker",           "Kisumu"),
            ("Brian",     "Ndegwa",    2016, "Africa Nazarene University",        "IT Administrator",        "Nairobi"),
            ("Caroline",  "Kiptoo",    2015, "South Eastern Kenya University",    "Microbiologist",          "Machakos"),
            ("Emmanuel",  "Kariuki",   2013, "Jomo Kenyatta University",          "Mechanical Engineer",     "Nairobi"),
            ("Janet",     "Waweru",    2014, "Kenya School of Law",               "Advocate",                "Nairobi"),
        ]

        profiles = []
        created = 0
        for i, (first, last, grad_yr, institution, occupation, city) in enumerate(ALUMNI_DATA):
            adm_no = f"ADM{grad_yr}{str(i + 1).zfill(3)}"
            profile, was_created = AlumniProfile.objects.get_or_create(
                admission_number=adm_no,
                defaults={
                    "first_name": first,
                    "last_name":  last,
                    "graduation_year": grad_yr,
                    "email":      f"{first.lower()}.{last.lower()}@alumni.stmarys.ac.ke",
                    "phone":      f"07{random.randint(10_000_000, 99_999_999)}",
                    "current_institution": institution,
                    "current_occupation":  occupation,
                    "country": "Kenya",
                    "city":    city,
                    "linkedin_url": f"https://linkedin.com/in/{first.lower()}-{last.lower()}",
                    "bio": (
                        f"{first} {last} graduated from St. Mary's Nairobi in {grad_yr} and "
                        f"pursued a career as a {occupation.lower()}. Currently based in {city}, Kenya."
                    ),
                    "is_verified": (i % 3 != 0),
                },
            )
            profiles.append(profile)
            if was_created:
                created += 1

        # Reunion events
        EVENTS = [
            (
                "Class of 2013–2015 Reunion",
                "Annual reunion for the 2013–2015 graduating classes. Old boys and girls are welcome.",
                date(2025, 8, 23),
                "School Hall, St. Mary's Nairobi",
                "Joseph Karanja (Principal)",
            ),
            (
                "Alumni Career Fair 2025",
                "Connect with employers and explore internship opportunities. Open to all alumni and current Grade 10 learners.",
                date(2025, 9, 13),
                "KICC Nairobi – Ground Floor",
                "Alumni Secretariat",
            ),
            (
                "Annual Golf Fundraiser",
                "Golf tournament in aid of the School Scholarship Fund. Alumni and corporate sponsors welcome.",
                date(2025, 10, 4),
                "Karen Country Club, Nairobi",
                "George Abuya (Class of 2012)",
            ),
        ]
        event_objects = []
        for title, desc, ev_date, location, organizer in EVENTS:
            ev, _ = AlumniEvent.objects.get_or_create(
                title=title,
                defaults={
                    "description": desc,
                    "event_date":  ev_date,
                    "location":    location,
                    "is_virtual":  False,
                    "organizer":   organizer,
                },
            )
            event_objects.append(ev)

        # Attendee registrations
        for alum in profiles[:10]:
            AlumniEventAttendee.objects.get_or_create(event=event_objects[0], alumni=alum)
        for alum in profiles[:7]:
            AlumniEventAttendee.objects.get_or_create(event=event_objects[1], alumni=alum)
        for alum in profiles[10:17]:
            AlumniEventAttendee.objects.get_or_create(event=event_objects[2], alumni=alum)

        # Mentorships
        MENTORSHIPS = [
            (profiles[0],  "Victor Omondi",    "student", "Software Engineering",   "Python, Django, Cloud DevOps",            "active"),
            (profiles[1],  "Grace Nyambura",   "student", "Finance & Accounting",   "CPA, Financial Modelling, Excel",         "active"),
            (profiles[2],  "Daniel Otieno",    "student", "Medicine & Health",      "Clinical Practice, Medical Research",     "matched"),
            (profiles[4],  "James Kipkemboi",  "student", "Education",              "Secondary Teaching, Curriculum Design",   "open"),
            (profiles[6],  "Francis Mwenda",   "student", "Civil Engineering",      "Structural Design, AutoCAD, Site Safety", "active"),
            (profiles[9],  "Mary Cherono",     "student", "Journalism & Media",     "Broadcast Journalism, Social Media",      "open"),
            (profiles[11], "Beatrice Njeri",   "student", "Pharmacy & Healthcare",  "Drug Dispensing, Community Health",       "active"),
        ]
        for mentor, mentee_name, mentee_type, industry, skills, status in MENTORSHIPS:
            AlumniMentorship.objects.get_or_create(
                mentor=mentor, mentee_name=mentee_name,
                defaults={
                    "mentee_type":     mentee_type,
                    "industry":        industry,
                    "skills_offered":  skills,
                    "status":          status,
                    "started_at":      date(2025, 1, 15) if status in ("active", "matched") else None,
                },
            )

        # Donations: (profile, campaign, amount, method, status, donation_date)
        DONATIONS = [
            (profiles[0],  "Library Renovation Fund",  Decimal("25000.00"), "mobile_money",  "received",     date(2025, 1, 20)),
            (profiles[1],  "Scholarship Fund 2025",    Decimal("15000.00"), "bank_transfer", "received",     date(2025, 2, 5)),
            (profiles[4],  "Sports Equipment Drive",   Decimal("10000.00"), "mobile_money",  "acknowledged", date(2025, 2, 14)),
            (profiles[6],  "Science Lab Upgrade",      Decimal("50000.00"), "bank_transfer", "pledged",      date(2025, 3, 1)),
            (profiles[9],  "General Fund",             Decimal("5000.00"),  "mobile_money",  "received",     date(2025, 3, 10)),
            (profiles[11], "Scholarship Fund 2025",    Decimal("20000.00"), "mobile_money",  "received",     date(2025, 3, 22)),
            (profiles[14], "Library Renovation Fund",  Decimal("8000.00"),  "mobile_money",  "acknowledged", date(2025, 4, 3)),
            (profiles[19], "ICT Equipment Fund",       Decimal("35000.00"), "bank_transfer", "pledged",      date(2025, 4, 10)),
        ]
        for alum, campaign, amount, method, status, don_date in DONATIONS:
            AlumniDonation.objects.get_or_create(
                alumni=alum, campaign_name=campaign, amount=amount,
                defaults={
                    "currency":      "KES",
                    "payment_method": method,
                    "status":        status,
                    "donation_date": don_date,
                },
            )

        self.stdout.write(
            f"    → Alumni: {created} new profiles (total: {AlumniProfile.objects.count()}), "
            f"{AlumniEvent.objects.count()} events, "
            f"{AlumniMentorship.objects.count()} mentorships, "
            f"{AlumniDonation.objects.count()} donations"
        )

    # ── Parent-Teacher Meetings (PTM) ─────────────────────────────────────────
    def _seed_ptm(self, terms, students):
        try:
            from ptm.models import PTMSession, PTMSlot, PTMBooking
        except ImportError:
            self.stdout.write("    PTM app not available — skipping")
            return
        from datetime import time as dt_time
        import random
        random.seed(66)

        # PTMSession.term is a FK to academics.Term, not school.Term
        try:
            from academics.models import Term as AcademicsTerm
            acad_term1 = AcademicsTerm.objects.first()
        except Exception:
            acad_term1 = None

        SESSIONS_DEF = [
            (
                "Term 1 2025 Parent-Teacher Meeting",
                date(2025, 3, 8),
                "School Main Hall",
                acad_term1,
                dt_time(8, 0),
                dt_time(16, 0),
            ),
            (
                "Grade 10 Parents' Consultation Day",
                date(2025, 3, 15),
                "Principal's Conference Room",
                acad_term1,
                dt_time(9, 0),
                dt_time(15, 0),
            ),
        ]

        teachers = list(User.objects.exclude(username="Riqs#.")[:10])
        if not teachers:
            teachers = [User.objects.filter(is_superuser=True).first()]

        for title, sess_date, venue, term, start_t, end_t in SESSIONS_DEF:
            session, _ = PTMSession.objects.get_or_create(
                title=title,
                defaults={
                    "date": sess_date,
                    "venue": venue,
                    "term": term,
                    "slot_duration_minutes": 15,
                    "start_time": start_t,
                    "end_time":   end_t,
                    "is_virtual": False,
                    "notes": f"Scheduled parents' consultation for {title}.",
                },
            )

            # Create one slot per teacher at staggered times
            from datetime import datetime, timedelta as td
            base_dt = datetime(2000, 1, 1, start_t.hour, start_t.minute)
            for i, teacher in enumerate(teachers):
                slot_time = (base_dt + td(minutes=15 * i)).time()
                slot, _ = PTMSlot.objects.get_or_create(
                    session=session,
                    teacher=teacher,
                    slot_time=slot_time,
                    defaults={"is_booked": False},
                )

                # Book the first 3 slots with students
                if i < 3 and students:
                    student = students[i % len(students)]
                    guardian = Guardian.objects.filter(student=student).first()
                    PTMBooking.objects.get_or_create(
                        slot=slot,
                        student=student,
                        defaults={
                            "parent_name":  guardian.name if guardian else f"Parent of {student.first_name}",
                            "parent_phone": guardian.phone if guardian else "",
                            "parent_email": guardian.email if guardian else "",
                            "notes": "Booked during Term 1 consultation period.",
                            "status": "Confirmed",
                        },
                    )

        self.stdout.write(
            f"    → PTM: {PTMSession.objects.count()} sessions, "
            f"{PTMSlot.objects.count()} slots, "
            f"{PTMBooking.objects.count()} bookings"
        )

    # ── Clock-In / Biometric Attendance ──────────────────────────────────────
    def _seed_clockin(self, students, admin_user):
        try:
            from clockin.models import SchoolShift, PersonRegistry, ClockEvent
        except ImportError:
            self.stdout.write("    Clockin app not available — skipping")
            return
        import random
        from datetime import time as dt_time, datetime, timedelta as td
        random.seed(77)

        # 1. School shifts
        SHIFTS = [
            ("Morning Arrival (Students)", "STUDENT", dt_time(6, 30), 30, dt_time(16, 30)),
            ("Morning Arrival (Staff)",    "STAFF",   dt_time(7, 0),  15, dt_time(17, 0)),
            ("All-Person Gate Check",      "ALL",     dt_time(6, 30), 30, dt_time(18, 0)),
        ]
        for name, ptype, arrival, grace, departure in SHIFTS:
            SchoolShift.objects.get_or_create(
                name=name,
                defaults={
                    "person_type":          ptype,
                    "expected_arrival":     arrival,
                    "grace_period_minutes": grace,
                    "expected_departure":   departure,
                    "is_active":            True,
                },
            )

        # 2. Person registry — register first 20 students
        registry_entries = []
        for i, student in enumerate(students[:20]):
            fp_id = f"FP-STU-{str(i + 1).zfill(4)}"
            card  = f"CARD{str(100 + i).zfill(6)}"
            entry, _ = PersonRegistry.objects.get_or_create(
                fingerprint_id=fp_id,
                defaults={
                    "card_no":     card,
                    "person_type": "STUDENT",
                    "student":     student,
                    "display_name": f"{student.first_name} {student.last_name}",
                    "is_active":   True,
                },
            )
            registry_entries.append(entry)

        # 3. Clock events — simulate 5 school days (Mon–Fri last week)
        today = date.today()
        monday = today - timedelta(days=today.weekday())  # most recent Monday
        events_created = 0
        for day_offset in range(5):
            school_day = monday + timedelta(days=day_offset)
            for person in registry_entries[:15]:
                # Morning IN
                arrival_hour = random.randint(6, 7)
                arrival_min  = random.randint(0, 55)
                in_ts = datetime(school_day.year, school_day.month, school_day.day,
                                 arrival_hour, arrival_min)
                is_late = arrival_hour >= 7 and arrival_min > 30
                existing_in = ClockEvent.objects.filter(
                    person=person, date=school_day, event_type="IN"
                ).exists()
                if not existing_in:
                    ClockEvent.objects.create(
                        person=person,
                        device=None,
                        event_type="IN",
                        timestamp=in_ts,
                        date=school_day,
                        is_late=is_late,
                    )
                    events_created += 1

                # Afternoon OUT
                out_hour = random.randint(15, 17)
                out_min  = random.randint(0, 55)
                out_ts = datetime(school_day.year, school_day.month, school_day.day,
                                  out_hour, out_min)
                existing_out = ClockEvent.objects.filter(
                    person=person, date=school_day, event_type="OUT"
                ).exists()
                if not existing_out:
                    ClockEvent.objects.create(
                        person=person,
                        device=None,
                        event_type="OUT",
                        timestamp=out_ts,
                        date=school_day,
                        is_late=False,
                    )
                    events_created += 1

        self.stdout.write(
            f"    → Clockin: {SchoolShift.objects.count()} shifts, "
            f"{PersonRegistry.objects.count()} registered persons, "
            f"{ClockEvent.objects.count()} clock events"
        )

    # ── Parent Portal Links ───────────────────────────────────────────────────
    def _seed_parent_portal(self, students, admin_user):
        try:
            from parent_portal.models import ParentStudentLink
        except ImportError:
            self.stdout.write("    Parent portal app not available — skipping")
            return
        import random
        random.seed(99)

        parent_role = Role.objects.filter(name="PARENT").first()
        student_role = Role.objects.filter(name="STUDENT").first()

        created = 0
        for student in students[:20]:
            guardian = Guardian.objects.filter(student=student).first()
            if not guardian:
                continue

            # Create a portal user for the guardian (username = parent.<adm_no>)
            portal_username = f"parent.{student.admission_number.lower()}"
            parent_user, user_created = User.objects.get_or_create(
                username=portal_username,
                defaults={
                    "first_name": guardian.name.replace("Mr./Mrs. ", "").split()[0] if guardian.name else "Parent",
                    "last_name":  student.last_name,
                    "email":      guardian.email or f"{portal_username}@stmarys.ac.ke",
                },
            )
            if user_created:
                parent_user.set_password("parent123")
                parent_user.save()

            # ── Assign PARENT role via UserProfile ──────────────────────────
            if parent_role:
                profile, _ = UserProfile.objects.get_or_create(
                    user=parent_user,
                    defaults={"role": parent_role},
                )
                if profile.role_id != parent_role.id:
                    profile.role = parent_role
                    profile.save(update_fields=["role"])

            _, link_created = ParentStudentLink.objects.get_or_create(
                parent_user=parent_user,
                student=student,
                defaults={
                    "guardian":      guardian,
                    "relationship":  guardian.relationship or "Parent",
                    "is_primary":    True,
                    "is_active":     True,
                    "created_by":    admin_user,
                },
            )
            if link_created:
                created += 1

        # ── Create student login accounts ────────────────────────────────────
        student_logins = 0
        if student_role:
            for student in students[:40]:
                stu_username = student.admission_number  # keep original case — matches seed_portal_accounts
                stu_user, stu_created = User.objects.get_or_create(
                    username=stu_username,
                    defaults={
                        "first_name": student.first_name,
                        "last_name":  student.last_name,
                        "email":      f"{stu_username.lower()}@stmarys.ac.ke",
                    },
                )
                if stu_created:
                    stu_user.set_password("student123")
                    stu_user.save()
                if student_role:
                    adm = student.admission_number
                    stu_profile = (
                        UserProfile.objects.filter(user=stu_user).first()
                        or UserProfile.objects.filter(admission_number=adm).first()
                    )
                    if stu_profile is None:
                        try:
                            stu_profile = UserProfile.objects.create(
                                user=stu_user,
                                role=student_role,
                                admission_number=adm,
                                force_password_change=False,
                            )
                        except Exception:
                            stu_profile = UserProfile.objects.filter(admission_number=adm).first()
                    if stu_profile:
                        changed = False
                        if stu_profile.user_id != stu_user.pk:
                            stu_profile.user = stu_user
                            changed = True
                        if stu_profile.role_id != student_role.id:
                            stu_profile.role = student_role
                            changed = True
                        if stu_profile.admission_number != adm:
                            stu_profile.admission_number = adm
                            changed = True
                        if changed:
                            stu_profile.save()
                student_logins += 1 if stu_created else 0

        self.stdout.write(
            f"    → Parent Portal: {created} new links "
            f"(total: {ParentStudentLink.objects.count()} links for "
            f"{User.objects.filter(username__startswith='parent.').count()} parent accounts, "
            f"{student_logins} new student logins)"
        )

    # ── Admissions Pipeline ───────────────────────────────────────────────────
    def _seed_admissions_pipeline(self, year, terms, classes, admin_user):
        try:
            from admissions.models import (
                AdmissionInquiry, AdmissionApplicationProfile,
                AdmissionReview, AdmissionAssessment,
                AdmissionInterview, AdmissionDecision,
            )
        except ImportError:
            self.stdout.write("    Admissions app not available — skipping")
            return
        import random
        random.seed(41)
        from datetime import datetime as _dt

        term1 = terms[0] if terms else None
        flat_classes = []
        if isinstance(classes, dict):
            for fd in classes.values():
                if isinstance(fd, dict):
                    east = fd.get("East")
                    if east:
                        flat_classes.append(east)
        flat_classes = flat_classes[:4]

        INQUIRIES = [
            ("Mr. Daniel Kiprotich",  "0722345678", "david.kiprotich@gmail.com",   "Leon Kiprotich",    date(2014, 3, 12), "Referral"),
            ("Mrs. Gladys Mwende",    "0733456789", "gladys.mwende@gmail.com",     "Sharon Mwende",     date(2014, 7, 5),  "Website"),
            ("Mr. Festus Oduor",      "0701234567", "festus.oduor@gmail.com",      "Caleb Oduor",       date(2014, 9, 20), "Walk-in"),
            ("Mrs. Lydia Njeri",      "0754321098", "lydia.njeri@gmail.com",       "Brian Njeri",       date(2014, 2, 14), "Event"),
            ("Mr. Patrick Otieno",    "0789012345", "patrick.otieno@gmail.com",    "Millicent Otieno",  date(2014, 5, 3),  "Advertisement"),
            ("Mrs. Christine Waweru", "0712345890", "christine.waweru@gmail.com",  "Elvis Waweru",      date(2014, 8, 17), "Referral"),
        ]

        inquiries = []
        for parent_name, phone, email, child_name, child_dob, source in INQUIRIES:
            inq, _ = AdmissionInquiry.objects.get_or_create(
                parent_email=email,
                defaults={
                    "parent_name":   parent_name,
                    "parent_phone":  phone,
                    "child_name":    child_name,
                    "child_dob":     child_dob,
                    "inquiry_source": source,
                    "inquiry_date":   date(2025, 1, random.randint(5, 28)),
                    "preferred_start": term1,
                    "status":         "Applied",
                    "assigned_counselor": admin_user,
                    "grade_level_interest": flat_classes[0] if flat_classes else None,
                },
            )
            inquiries.append(inq)

        # Seed full pipeline using existing AdmissionApplications in school.AdmissionApplication
        from school.models import AdmissionApplication
        apps = list(AdmissionApplication.objects.all()[:6])

        for i, app in enumerate(apps):
            # AdmissionApplicationProfile
            AdmissionApplicationProfile.objects.get_or_create(
                application=app,
                defaults={
                    "inquiry": inquiries[i] if i < len(inquiries) else None,
                    "academic_year": year,
                    "term": term1,
                    "is_shortlisted": i < 4,
                    "special_needs": "",
                    "emergency_contact_name": app.guardian_name,
                    "emergency_contact_phone": app.guardian_phone,
                    "languages": "English, Swahili",
                },
            )

            # AdmissionReview
            if not AdmissionReview.objects.filter(application=app).exists():
                AdmissionReview.objects.create(
                    application=app,
                    reviewer=admin_user,
                    academic_score=Decimal(str(round(random.uniform(60, 95), 1))),
                    test_score=Decimal(str(round(random.uniform(55, 90), 1))),
                    interview_score=Decimal(str(round(random.uniform(65, 95), 1))) if i < 4 else None,
                    overall_score=Decimal(str(round(random.uniform(60, 92), 1))),
                    recommendation="Accept" if i < 4 else "Waitlist",
                    comments="Candidate meets all required admission criteria." if i < 4 else "Strong candidate; on waiting list.",
                )

            # AdmissionAssessment
            if not AdmissionAssessment.objects.filter(application=app).exists():
                AdmissionAssessment.objects.create(
                    application=app,
                    scheduled_at=_dt(2025, 1, 18, 9, 0),
                    venue="Examination Hall, Block A",
                    score=Decimal(str(round(random.uniform(55, 95), 1))),
                    is_pass=(i < 4),
                    status="Completed",
                    notes="Assessment conducted as part of admission screening.",
                    created_by=admin_user,
                )

            # AdmissionInterview (for shortlisted)
            if i < 4 and not AdmissionInterview.objects.filter(application=app).exists():
                AdmissionInterview.objects.create(
                    application=app,
                    interview_date=_dt(2025, 1, 25, 10, 0),
                    interview_type="In-person",
                    location="Principal's Office",
                    panel=["Principal", "Deputy Principal", "HOD"],
                    status="Completed",
                    feedback="Candidate demonstrated strong academic potential and good character.",
                    score=Decimal(str(round(random.uniform(70, 95), 1))),
                    created_by=admin_user,
                )

            # AdmissionDecision
            AdmissionDecision.objects.get_or_create(
                application=app,
                defaults={
                    "decision":        "Accept" if i < 4 else "Waitlist",
                    "decision_date":   date(2025, 2, 1),
                    "decision_notes":  "Decision made after full review of application, assessment and interview." if i < 4 else "Placed on waiting list; will be notified if space opens.",
                    "offer_deadline":  date(2025, 2, 15),
                    "response_status": "Accepted" if i < 3 else "Pending",
                    "decided_by":      admin_user,
                },
            )

        self.stdout.write(
            f"    → Admissions: {AdmissionInquiry.objects.count()} inquiries, "
            f"{AdmissionApplicationProfile.objects.count()} profiles, "
            f"{AdmissionReview.objects.count()} reviews, "
            f"{AdmissionAssessment.objects.count()} assessments, "
            f"{AdmissionInterview.objects.count()} interviews, "
            f"{AdmissionDecision.objects.count()} decisions"
        )

    # ── Curriculum ────────────────────────────────────────────────────────────
    def _seed_curriculum(self, year, terms, classes, admin_user):
        try:
            from curriculum.models import SchemeOfWork, SchemeTopic, LessonPlan, LearningResource
        except ImportError:
            self.stdout.write("    Curriculum app not available — skipping")
            return
        import random
        random.seed(42)
        from datetime import datetime as _dt

        term1 = terms[0] if terms else None
        core_subjects = list(Subject.objects.filter(is_active=True)[:6])

        flat_classes = []
        if isinstance(classes, dict):
            for fd in classes.values():
                if isinstance(fd, dict):
                    east = fd.get("East")
                    if east:
                        flat_classes.append(east)
        flat_classes = flat_classes[:4]

        TOPICS = [
            ("Introduction and Overview",            "Sub-topic 1; Sub-topic 2",     "Understand key concepts"),
            ("Core Concepts and Principles",          "Sub-topic A; Sub-topic B",     "Apply principles to problems"),
            ("Problem Solving and Application",       "Case studies; Exercises",       "Solve structured problems"),
            ("Assessment and Review",                 "Practice questions; Summary",   "Review and consolidate learning"),
            ("Extension and Enrichment",              "Research tasks; Projects",      "Explore advanced applications"),
            ("Mid-Term Revision",                     "Past papers; Key topics",       "Prepare for mid-term exam"),
            ("Project Work",                          "Group work; Presentations",     "Develop collaborative skills"),
            ("End of Term Summary",                   "Summary notes; Class quiz",     "Consolidate term learning"),
        ]

        scheme_count = topic_count = plan_count = resource_count = 0
        for cls in flat_classes[:2]:
            for subj in core_subjects[:3]:
                scheme, s_created = SchemeOfWork.objects.get_or_create(
                    subject=subj, school_class=cls, term=term1,
                    defaults={
                        "title": f"{subj.name} – {cls.name} – Term 1 2025",
                        "objectives": f"By the end of Term 1, learners will master foundational {subj.name} concepts.",
                        "created_by": admin_user,
                    },
                )
                if s_created:
                    scheme_count += 1

                for week, (topic, sub_topics, outcomes) in enumerate(TOPICS, start=1):
                    st, t_created = SchemeTopic.objects.get_or_create(
                        scheme=scheme, week_number=week,
                        defaults={
                            "topic":             f"{subj.name}: {topic}",
                            "sub_topics":        sub_topics,
                            "learning_outcomes": outcomes,
                            "teaching_methods":  "Lecture, Discussion, Group Work, Q&A",
                            "resources":         "Textbook, Whiteboard, Worksheets",
                            "assessment_type":   "Quiz" if week % 2 == 0 else "Class Exercise",
                            "is_covered":        week <= 5,
                            "covered_date":      date(2025, 1, 6) + timedelta(weeks=week - 1) if week <= 5 else None,
                        },
                    )
                    if t_created:
                        topic_count += 1

                    # Lesson plan for first 3 topics
                    if week <= 3 and t_created:
                        lesson_date = date(2025, 1, 6) + timedelta(weeks=week - 1)
                        lp, lp_created = LessonPlan.objects.get_or_create(
                            topic=st, date=lesson_date,
                            defaults={
                                "lesson_objectives": f"Students will understand {topic.lower()} in {subj.name}.",
                                "introduction":       "Review of previous lesson. Brainstorm activity.",
                                "presentation":       "Teacher-led explanation with examples on whiteboard.",
                                "conclusion":         "Summary of key points. Q&A session.",
                                "assessment_activity": "Short written exercise (5 questions).",
                                "homework":           "Read pages 10–15 and attempt exercise set A.",
                                "is_approved":        True,
                                "approved_by":        admin_user,
                            },
                        )
                        if lp_created:
                            plan_count += 1

        # Learning resources
        RESOURCES = [
            ("Mathematics Revision Notes – Grade 7",   "Link",     "MTH", "https://kenyacurriculumhub.ac.ke/maths-g7"),
            ("English Grammar Handbook",               "Document", "ENG", "https://kenyacurriculumhub.ac.ke/eng-grammar"),
            ("Biology Diagrams and Notes",             "Document", "BIO", "https://kenyacurriculumhub.ac.ke/bio-diagrams"),
            ("Chemistry Formula Sheet",                "Document", "CHE", "https://kenyacurriculumhub.ac.ke/chem-formulae"),
            ("Physics Formula Sheet",                  "Document", "PHY", "https://kenyacurriculumhub.ac.ke/phys-formulae"),
            ("History & Government Past Papers",       "Link",     "HIS", "https://kenyacurriculumhub.ac.ke/hist-papers"),
        ]
        for title, rtype, subj_code, url in RESOURCES:
            subj = Subject.objects.filter(code=subj_code).first()
            if subj:
                _, r_created = LearningResource.objects.get_or_create(
                    title=title,
                    defaults={
                        "resource_type": rtype,
                        "subject":       subj,
                        "external_url":  url,
                        "description":   f"Reference resource for {subj.name}.",
                        "uploaded_by":   admin_user,
                    },
                )
                if r_created:
                    resource_count += 1

        self.stdout.write(
            f"    → Curriculum: {SchemeOfWork.objects.count()} schemes, "
            f"{SchemeTopic.objects.count()} topics, "
            f"{LessonPlan.objects.count()} lesson plans, "
            f"{LearningResource.objects.count()} resources"
        )

    # ── Comprehensive HR Data ─────────────────────────────────────────────────
    def _seed_hr_comprehensive(self, admin_user):
        try:
            from hr.models import (
                Department, Position, Employee,
                EmployeeEmploymentProfile, EmployeeQualification, EmergencyContact,
                ShiftTemplate, WorkSchedule, AttendanceRecord,
                LeaveType, LeavePolicy, LeaveBalance, LeaveRequest,
                SalaryStructure, SalaryComponent,
                PayrollBatch, PayrollItem, PayrollItemBreakdown,
                JobPosting, JobApplication, Interview,
                OnboardingTask, PerformanceGoal, PerformanceReview,
                TrainingProgram, TrainingEnrollment,
                DisciplinaryCase,
            )
        except ImportError:
            self.stdout.write("    HR app not available — skipping")
            return
        import random
        from datetime import time as dt_time
        random.seed(43)

        # 1. Departments
        DEPTS = [
            ("Mathematics & Science",  "MATH-SCI", "Academic"),
            ("Languages & Humanities", "LANG-HUM", "Academic"),
            ("Technical & Vocational", "TECH-VOC", "Academic"),
            ("Administration",         "ADMIN",    "Administrative"),
            ("Support Services",       "SUPPORT",  "Support"),
        ]
        dept_map = {}
        for name, code, _ in DEPTS:
            dept, _ = Department.objects.get_or_create(code=code, defaults={"name": name, "is_active": True})
            dept_map[code] = dept

        # 2. Positions
        POSITIONS = [
            ("Head of Department – Mathematics", "MATH-SCI", 80000, 120000),
            ("Head of Department – Languages",   "LANG-HUM", 80000, 120000),
            ("Senior Teacher",                   "MATH-SCI", 65000, 90000),
            ("Class Teacher",                    "LANG-HUM", 55000, 80000),
            ("Administrative Officer",           "ADMIN",    45000, 65000),
            ("ICT Technician",                   "TECH-VOC", 40000, 60000),
            ("Laboratory Technician",            "MATH-SCI", 38000, 55000),
            ("School Counsellor",                "ADMIN",    50000, 70000),
        ]
        pos_map = {}
        for title, dept_code, sal_min, sal_max in POSITIONS:
            pos, _ = Position.objects.get_or_create(
                title=title,
                defaults={
                    "department": dept_map.get(dept_code),
                    "salary_min": Decimal(str(sal_min)),
                    "salary_max": Decimal(str(sal_max)),
                    "is_active":  True,
                },
            )
            pos_map[title] = pos

        # 3. EmployeeEmploymentProfile + Qualifications + EmergencyContacts
        employees = list(Employee.objects.all())
        QUAL_DATA = [
            ("Degree", "Bachelor of Education (Mathematics)", "University of Nairobi",        "Education",    2010),
            ("Degree", "Bachelor of Arts (English)",           "Kenyatta University",           "English",      2008),
            ("Degree", "Bachelor of Science (Biology)",        "Moi University",                "Biology",      2012),
            ("Diploma", "Diploma in Education",               "Kenya National Polytechnic",    "Education",    2009),
            ("Degree", "Bachelor of Commerce",                 "Strathmore University",         "Commerce",     2011),
            ("Professional", "TSC Professional Certificate",  "Teachers Service Commission",  "Education",    2007),
        ]
        EMERGENCY_NAMES = [
            ("Grace Mwangi",    "Spouse",  "0722100200"),
            ("Paul Kamau",      "Brother", "0733200300"),
            ("Jane Wanjiku",    "Spouse",  "0744300400"),
            ("David Otieno",    "Father",  "0755400500"),
            ("Susan Achieng",   "Spouse",  "0766500600"),
            ("Peter Mutua",     "Brother", "0777600700"),
        ]
        KRA_PINS = [f"A{random.randint(1000000,9999999)}K" for _ in employees]
        BANK_NAMES = ["Equity Bank", "KCB Bank", "Co-operative Bank", "NCBA Bank", "Family Bank"]
        for i, emp in enumerate(employees[:20]):
            # EmployeeEmploymentProfile
            EmployeeEmploymentProfile.objects.get_or_create(
                employee=emp,
                defaults={
                    "kra_pin":         KRA_PINS[i % len(KRA_PINS)],
                    "nhif_number":     f"NHIF{random.randint(100000, 999999)}",
                    "nssf_number":     f"NSSF{random.randint(100000, 999999)}",
                    "tsc_number":      f"TSC{random.randint(10000, 99999)}" if emp.staff_category == "TEACHING" else "",
                    "bank_name":       BANK_NAMES[i % len(BANK_NAMES)],
                    "bank_branch":     "Nairobi Central Branch",
                    "bank_account_name": f"{emp.first_name} {emp.last_name}",
                    "bank_account_number": str(random.randint(10000000000, 99999999999)),
                    "position_grade":  f"T-{random.randint(1,5)}" if emp.staff_category == "TEACHING" else f"A-{random.randint(1,3)}",
                    "salary_scale":    f"Job Group {chr(75 + (i % 8))}",
                    "probation_months": 3,
                    "confirmation_due_date": date(2024, 6, 1),
                },
            )
            # EmployeeQualification
            if not emp.qualifications.exists():
                qtype, qtitle, qinst, qfield, qyear = QUAL_DATA[i % len(QUAL_DATA)]
                EmployeeQualification.objects.create(
                    employee=emp,
                    qualification_type=qtype,
                    title=qtitle,
                    institution=qinst,
                    field_of_study=qfield,
                    year_obtained=qyear,
                    is_primary=True,
                    is_active=True,
                )
            # EmergencyContact
            if not emp.emergency_contacts.exists():
                ename, erel, ephone = EMERGENCY_NAMES[i % len(EMERGENCY_NAMES)]
                EmergencyContact.objects.create(
                    employee=emp,
                    name=ename,
                    relationship=erel,
                    phone_primary=ephone,
                    is_primary=True,
                    is_active=True,
                )

        # 4. ShiftTemplate
        SHIFTS = [
            ("Standard Teaching Shift",  "TEACH-STD",  "TEACHING",  dt_time(7, 0), dt_time(17, 0), [1, 2, 3, 4, 5]),
            ("Admin Office Hours",        "ADMIN-STD",  "ADMIN",     dt_time(8, 0), dt_time(17, 0), [1, 2, 3, 4, 5]),
            ("Support Services Shift",    "SUPPORT-STD","SUPPORT",   dt_time(6, 0), dt_time(18, 0), [1, 2, 3, 4, 5]),
        ]
        shift_map = {}
        for name, code, cat, start, end, days in SHIFTS:
            sh, _ = ShiftTemplate.objects.get_or_create(
                code=code,
                defaults={
                    "name": name, "staff_category": cat, "shift_start": start,
                    "shift_end": end, "working_days": days, "grace_minutes": 15,
                    "break_duration_minutes": 60, "is_active": True,
                },
            )
            shift_map[cat] = sh

        # 5. WorkSchedule for first 10 employees
        for emp in employees[:10]:
            cat = emp.staff_category or "TEACHING"
            sh = shift_map.get(cat, shift_map.get("TEACHING"))
            if sh:
                WorkSchedule.objects.get_or_create(
                    employee=emp,
                    shift_template=sh,
                    effective_from=date(2025, 1, 6),
                    defaults={
                        "shift_start": sh.shift_start,
                        "shift_end":   sh.shift_end,
                        "working_days": sh.working_days,
                        "break_duration": sh.break_duration_minutes,
                        "is_active": True,
                    },
                )

        # 6. AttendanceRecord — 5 days for first 15 employees
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        for day_offset in range(5):
            school_day = monday + timedelta(days=day_offset)
            for emp in employees[:15]:
                status = "Present" if random.random() > 0.1 else "Late"
                AttendanceRecord.objects.get_or_create(
                    employee=emp, date=school_day,
                    defaults={
                        "status": status,
                        "clock_in": dt_time(7, random.randint(0, 35)),
                        "clock_out": dt_time(17, random.randint(0, 30)),
                        "hours_worked": Decimal("8.5"),
                        "attendance_source": "MANUAL",
                    },
                )

        # 7. Leave data
        leave_type = LeaveType.objects.first()
        if leave_type:
            # LeavePolicy
            LeavePolicy.objects.get_or_create(
                leave_type=leave_type, employment_type="Full-time",
                defaults={
                    "entitlement_days": Decimal("21.00"),
                    "accrual_method":   "Annual",
                    "carry_forward_max": 5,
                    "effective_from":   date(2025, 1, 1),
                    "is_active":        True,
                },
            )
            # LeaveBalance + LeaveRequest for first 5 employees
            for emp in employees[:5]:
                LeaveBalance.objects.get_or_create(
                    employee=emp, leave_type=leave_type, year=2025,
                    defaults={
                        "opening_balance": Decimal("21.00"),
                        "accrued":         Decimal("21.00"),
                        "used":            Decimal("3.00"),
                        "pending":         Decimal("0.00"),
                        "available":       Decimal("18.00"),
                        "is_active":       True,
                    },
                )
            # One approved leave request per first 3 employees
            for emp in employees[:3]:
                LeaveRequest.objects.get_or_create(
                    employee=emp, leave_type=leave_type, start_date=date(2025, 3, 10),
                    defaults={
                        "end_date":      date(2025, 3, 12),
                        "days_requested": Decimal("3.00"),
                        "reason":        "Personal leave for family matter.",
                        "status":        "Approved",
                        "approved_by":   employees[0] if employees else None,
                        "approved_at":   date(2025, 3, 5),
                    },
                )

        # 8. SalaryStructure + SalaryComponent + PayrollBatch + PayrollItems
        sal_structures = []
        for i, emp in enumerate(employees[:10]):
            basic = Decimal(str(random.randint(50000, 120000)))
            struct, _ = SalaryStructure.objects.get_or_create(
                employee=emp,
                defaults={
                    "basic_salary":  basic,
                    "currency":      "KES",
                    "pay_frequency": "Monthly",
                    "effective_from": date(2025, 1, 1),
                    "is_active":     True,
                },
            )
            sal_structures.append((emp, struct, basic))
            if not struct.components.exists():
                SalaryComponent.objects.create(
                    structure=struct, component_type="Allowance",
                    name="House Allowance", amount_type="Fixed",
                    amount=Decimal("15000.00"), is_taxable=True, is_active=True,
                )
                SalaryComponent.objects.create(
                    structure=struct, component_type="Allowance",
                    name="Transport Allowance", amount_type="Fixed",
                    amount=Decimal("5000.00"), is_taxable=False, is_active=True,
                )

        # PayrollBatch for March 2025
        batch, _ = PayrollBatch.objects.get_or_create(
            month=3, year=2025,
            defaults={
                "status":        "Paid",
                "total_gross":   Decimal("0.00"),
                "total_deductions": Decimal("0.00"),
                "total_net":     Decimal("0.00"),
                "processed_by":  admin_user,
                "approved_by":   admin_user,
                "approved_at":   None,
                "payment_date":  date(2025, 3, 28),
            },
        )
        total_gross = Decimal("0.00")
        total_net   = Decimal("0.00")
        for emp, struct, basic in sal_structures[:8]:
            allowances  = Decimal("20000.00")
            gross       = basic + allowances
            deductions  = (gross * Decimal("0.10")).quantize(Decimal("0.01"))
            net         = gross - deductions
            total_gross += gross
            total_net   += net
            PayrollItem.objects.get_or_create(
                payroll=batch, employee=emp,
                defaults={
                    "basic_salary":          basic,
                    "total_allowances":      allowances,
                    "gross_salary":          gross,
                    "statutory_deduction_total": deductions,
                    "total_deductions":      deductions,
                    "net_salary":            net,
                },
            )
        if not batch.total_gross:
            PayrollBatch.objects.filter(pk=batch.pk).update(
                total_gross=total_gross, total_net=total_net,
                total_deductions=total_gross - total_net,
            )

        # 9. JobPosting + JobApplication + Interview
        senior_dept = dept_map.get("MATH-SCI")
        posting, _ = JobPosting.objects.get_or_create(
            title="Senior Mathematics Teacher",
            defaults={
                "department": senior_dept,
                "description": "We seek a qualified and experienced Mathematics teacher.",
                "requirements": "B.Ed Mathematics or BSc Mathematics with PGDE. TSC registered.",
                "employment_type": "Full-time",
                "salary_min": Decimal("70000.00"),
                "salary_max": Decimal("100000.00"),
                "deadline": date(2025, 2, 28),
                "status": "Closed",
                "posted_by": admin_user,
            },
        )
        APPLICANTS = [
            ("Francis", "Wangari",  "francis.wangari@gmail.com",   "Shortlisted"),
            ("Diana",   "Achieng",  "diana.achieng@gmail.com",     "Shortlisted"),
            ("George",  "Bett",     "george.bett@gmail.com",       "Rejected"),
            ("Mercy",   "Ndungu",   "mercy.ndungu@gmail.com",      "Hired"),
        ]
        app_objects = []
        for first, last, email, status in APPLICANTS:
            app_obj, _ = JobApplication.objects.get_or_create(
                job_posting=posting, email=email,
                defaults={
                    "first_name": first, "last_name": last,
                    "cover_letter": f"I am {first} {last}, applying for the mathematics teacher position.",
                    "status": status, "rating": random.randint(3, 5),
                    "is_active": True,
                },
            )
            app_objects.append(app_obj)
        for idx, app_obj in enumerate(app_objects[:2]):
            if not app_obj.interviews.exists():
                from datetime import datetime as _dt
                idate = _dt(2025, 2, 20 + idx, 14, 0)
                Interview.objects.create(
                    application=app_obj,
                    interview_date=idate,
                    interview_type="In-person",
                    location="School Board Room",
                    interviewers=["Principal", "Deputy Principal"],
                    status="Completed",
                    feedback="Strong candidate with excellent subject knowledge.",
                    score=Decimal(str(round(random.uniform(75, 92), 1))),
                    created_by=admin_user,
                )

        # 10. OnboardingTask for first 3 employees (newly hired)
        ONBOARDING = [
            ("COLLECT_ID",    "Collect and photocopy national ID/passport"),
            ("TSC_LETTER",    "Obtain TSC posting letter"),
            ("BANK_FORM",     "Complete bank account / salary payment form"),
            ("NHIF_REG",      "Register with NHIF and obtain membership card"),
            ("NSSF_REG",      "Register with NSSF and obtain membership number"),
            ("INTRO_TOUR",    "Conduct school orientation tour"),
        ]
        for emp in employees[:3]:
            for code, task in ONBOARDING:
                OnboardingTask.objects.get_or_create(
                    employee=emp, task_code=code,
                    defaults={
                        "task":         task,
                        "assigned_to":  admin_user,
                        "due_date":     emp.join_date + timedelta(days=7) if emp.join_date else date(2025, 1, 14),
                        "status":       "Completed",
                        "is_required":  True,
                        "completed_at": None,
                        "notes":        "Completed during induction week.",
                    },
                )

        # 11. PerformanceGoal + PerformanceReview
        for emp in employees[:8]:
            PerformanceGoal.objects.get_or_create(
                employee=emp,
                title=f"Improve student pass rate to 80% — Term 1 2025",
                defaults={
                    "description": "Focus on weaker students through extra lessons and personalized support.",
                    "target_date": date(2025, 3, 28),
                    "status":      "In Progress",
                    "weight":      Decimal("30.00"),
                    "is_active":   True,
                },
            )
        if len(employees) >= 2:
            PerformanceReview.objects.get_or_create(
                employee=employees[0],
                review_period="Term 1 2025",
                defaults={
                    "reviewer":          employees[1] if len(employees) > 1 else None,
                    "overall_rating":    Decimal("3.80"),
                    "strengths":         "Excellent classroom management; strong student rapport.",
                    "areas_improvement": "Could improve formative assessment frequency.",
                    "status":            "Submitted",
                    "reviewed_at":       None,
                    "is_active":         True,
                },
            )

        # 12. TrainingProgram + TrainingEnrollment
        PROGRAMS = [
            ("KNEC Curriculum Implementation Workshop", "KNEC Secretariat",      date(2025, 4, 7),  date(2025, 4, 9)),
            ("Digital Literacy for Educators",           "Kenya ICT Authority",   date(2025, 5, 12), date(2025, 5, 14)),
            ("School Leadership and Management",         "Kenya Education Staff", date(2025, 6, 2),  date(2025, 6, 5)),
        ]
        prog_objects = []
        for title, trainer, start, end in PROGRAMS:
            prog, _ = TrainingProgram.objects.get_or_create(
                title=title,
                defaults={"trainer": trainer, "start_date": start, "end_date": end, "capacity": 30, "is_active": True},
            )
            prog_objects.append(prog)
        for prog in prog_objects:
            for emp in employees[:5]:
                TrainingEnrollment.objects.get_or_create(
                    program=prog, employee=emp,
                    defaults={"status": "Completed", "completion_date": prog.end_date, "is_active": True},
                )

        # 13. DisciplinaryCase
        if employees:
            DisciplinaryCase.objects.get_or_create(
                case_number="DC-2025-001",
                defaults={
                    "employee":     employees[-1],
                    "category":     "Lateness",
                    "opened_on":    date(2025, 2, 10),
                    "incident_date": date(2025, 2, 7),
                    "summary":      "Repeated late arrivals — 4 incidents in 3 weeks.",
                    "details":      "Employee arrived more than 30 minutes late on 4 separate occasions without prior notification.",
                    "status":       "CLOSED",
                    "outcome":      "WARNING",
                    "effective_date": date(2025, 2, 17),
                    "opened_by":    admin_user,
                    "notes":        "Written warning issued. Employee acknowledged and signed. Counselled.",
                },
            )

        self.stdout.write(
            f"    → HR: {Department.objects.count()} depts, {Position.objects.count()} positions, "
            f"{EmployeeEmploymentProfile.objects.count()} employment profiles, "
            f"{EmployeeQualification.objects.count()} qualifications, "
            f"{EmergencyContact.objects.count()} emergency contacts, "
            f"{AttendanceRecord.objects.count()} attendance records, "
            f"{PayrollBatch.objects.count()} payroll batches, "
            f"{PayrollItem.objects.count()} payroll items, "
            f"{LeaveRequest.objects.count()} leave requests, "
            f"{JobPosting.objects.count()} job postings, "
            f"{TrainingProgram.objects.count()} training programs, "
            f"{DisciplinaryCase.objects.count()} disciplinary cases"
        )

    # ── Staff Management Comprehensive ───────────────────────────────────────
    def _seed_staff_mgmt_comprehensive(self, admin_user, classes):
        try:
            from staff_mgmt.models import (
                StaffMember, StaffQualification, StaffEmergencyContact,
                StaffDepartment, StaffRole, StaffAssignment,
                StaffAttendance, StaffObservation, StaffAppraisal,
            )
        except ImportError:
            self.stdout.write("    Staff Mgmt app not available — skipping")
            return
        import random
        from datetime import time as dt_time
        random.seed(44)

        members = list(StaffMember.objects.all())
        if not members:
            return

        # 1. StaffDepartment
        DEPTS = [
            ("Mathematics & Science",  "SMS-MATH", "Academic"),
            ("Languages & Humanities", "SMS-LANG", "Academic"),
            ("Administration",         "SMS-ADMIN","Administrative"),
        ]
        dept_map = {}
        for name, code, dtype in DEPTS:
            dept, _ = StaffDepartment.objects.get_or_create(
                code=code,
                defaults={"name": name, "department_type": dtype, "is_active": True},
            )
            dept_map[code] = dept

        # 2. StaffRole
        ROLES = [
            ("Head of Department",  "SMS-HOD",  3),
            ("Senior Teacher",      "SMS-SRTCH", 2),
            ("Class Teacher",       "SMS-CLTCH", 1),
            ("Support Staff",       "SMS-SUPP",  1),
        ]
        role_map = {}
        for name, code, level in ROLES:
            role, _ = StaffRole.objects.get_or_create(
                code=code,
                defaults={"name": name, "level": level, "is_active": True},
            )
            role_map[code] = role

        # 3. StaffQualification (first 20 members)
        QUALS = [
            ("Degree",  "B.Ed Mathematics",         "University of Nairobi",   "Mathematics Education", 2010),
            ("Degree",  "B.A English & Literature",  "Kenyatta University",     "English",               2009),
            ("Degree",  "B.Sc Biology",              "Moi University",          "Biological Sciences",   2011),
            ("Diploma", "Diploma in Education",      "Kenya National Poly",     "Education",             2008),
            ("Degree",  "B.Ed Physical Education",  "JKUAT",                   "Physical Education",    2013),
        ]
        for i, member in enumerate(members[:20]):
            if not member.qualifications.exists():
                qtype, qtitle, qinst, qfield, qyear = QUALS[i % len(QUALS)]
                StaffQualification.objects.create(
                    staff=member,
                    qualification_type=qtype,
                    title=qtitle,
                    institution=qinst,
                    field_of_study=qfield,
                    year_obtained=qyear,
                    is_active=True,
                )

        # 4. StaffEmergencyContact (first 20 members)
        CONTACTS = [
            ("Grace Kamau",    "Spouse",  "0722111222"),
            ("Peter Oduor",    "Brother", "0733222333"),
            ("Lydia Njoroge",  "Spouse",  "0744333444"),
            ("Samuel Kipkos",  "Father",  "0755444555"),
            ("Judith Achieng", "Spouse",  "0766555666"),
        ]
        for i, member in enumerate(members[:20]):
            if not member.emergency_contacts.exists():
                cname, crel, cphone = CONTACTS[i % len(CONTACTS)]
                StaffEmergencyContact.objects.create(
                    staff=member,
                    name=cname,
                    relationship=crel,
                    phone_primary=cphone,
                    is_primary=True,
                    is_active=True,
                )

        # 5. StaffAssignment (first 15 members)
        for i, member in enumerate(members[:15]):
            dept = dept_map.get("SMS-MATH" if member.staff_type == "Teaching" else "SMS-ADMIN")
            role = role_map.get("SMS-CLTCH" if member.staff_type == "Teaching" else "SMS-SUPP")
            if dept and role:
                StaffAssignment.objects.get_or_create(
                    staff=member, department=dept, role=role,
                    defaults={
                        "is_primary":    True,
                        "effective_from": date(2025, 1, 6),
                        "is_active":     True,
                    },
                )

        # 6. StaffAttendance — 5 days for first 15 members
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        for day_offset in range(5):
            school_day = monday + timedelta(days=day_offset)
            for member in members[:15]:
                status = "Present" if random.random() > 0.08 else "Late"
                StaffAttendance.objects.get_or_create(
                    staff=member, date=school_day,
                    defaults={
                        "status":    status,
                        "clock_in":  dt_time(7, random.randint(0, 40)),
                        "clock_out": dt_time(17, random.randint(0, 30)),
                        "marked_by": admin_user,
                        "is_active": True,
                    },
                )

        # 7. StaffObservation (first 5 teachers)
        flat_classes = []
        if isinstance(classes, dict):
            for fd in classes.values():
                if isinstance(fd, dict):
                    east = fd.get("East")
                    if east:
                        flat_classes.append(east)
        from datetime import datetime as _dt
        observer = members[0] if members else None
        obs_base_date = _dt(2025, 2, 15, 9, 0)
        for i, member in enumerate(members[1:6]):
            obs_dt = _dt(2025, 2, 15 + i, 9, 0)
            StaffObservation.objects.get_or_create(
                staff=member,
                observer=observer,
                observation_date=obs_dt,
                defaults={
                    "class_observed":    flat_classes[i % len(flat_classes)] if flat_classes else None,
                    "lesson_topic":      "Algebra — Solving Linear Equations" if i % 2 == 0 else "Reading Comprehension",
                    "overall_rating":    Decimal(str(round(random.uniform(3.0, 4.8), 1))),
                    "strengths":         "Clear explanations; good student engagement.",
                    "areas_improvement": "Could use more visual aids and group activities.",
                    "recommendations":   "Attend collaborative teaching workshop.",
                    "status":            "Submitted",
                    "is_active":         True,
                },
            )

        # 8. StaffAppraisal (first 8 members)
        appraiser = members[0] if members else None
        for member in members[1:9]:
            StaffAppraisal.objects.get_or_create(
                staff=member,
                appraisal_period="Term 1 2025",
                defaults={
                    "appraiser":         appraiser,
                    "self_rating":       Decimal(str(round(random.uniform(3.0, 4.5), 1))),
                    "supervisor_rating": Decimal(str(round(random.uniform(3.0, 4.8), 1))),
                    "overall_rating":    Decimal(str(round(random.uniform(3.0, 4.6), 1))),
                    "strengths":         "Consistent performance; reliable and punctual.",
                    "areas_development": "Leadership skills and curriculum innovation.",
                    "goals_next_period": "Lead one inter-school academic competition.",
                    "status":            "Submitted",
                    "appraisal_date":    date(2025, 3, 20),
                    "is_active":         True,
                },
            )

        self.stdout.write(
            f"    → Staff Mgmt: {StaffQualification.objects.count()} qualifications, "
            f"{StaffEmergencyContact.objects.count()} emergency contacts, "
            f"{StaffDepartment.objects.count()} departments, "
            f"{StaffRole.objects.count()} roles, "
            f"{StaffAssignment.objects.count()} assignments, "
            f"{StaffAttendance.objects.count()} attendance records, "
            f"{StaffObservation.objects.count()} observations, "
            f"{StaffAppraisal.objects.count()} appraisals"
        )

    # ── Communication Data ────────────────────────────────────────────────────
    def _seed_communication_data(self, admin_user):
        try:
            from communication.models import (
                Conversation, ConversationParticipant, CommunicationMessage,
                Notification, NotificationPreference,
                EmailCampaign, SmsMessage, MessageTemplate,
            )
        except ImportError:
            self.stdout.write("    Communication app not available — skipping")
            return
        import random
        random.seed(45)

        users = list(User.objects.all()[:8])
        if not users:
            return

        # 1. Message Templates
        TEMPLATES = [
            ("Fee Reminder",     "Financial","Dear Parent,\nThis is a reminder that school fees of KES {amount} are due on {due_date}.\nKindly ensure timely payment.\n\nRegards,\nBursary Office"),
            ("Event Invitation", "Event",   "Dear {name},\nYou are cordially invited to {event_name} on {event_date} at {venue}.\n\nRegards,\nSt. Mary's Nairobi"),
            ("Exam Results",     "Academic","Dear Parent,\nYour child {student_name} has received their {exam_name} results.\nOverall grade: {grade}.\n\nFor more details, please contact the class teacher."),
            ("Absence Alert",    "Alert",   "Dear Parent,\nYour child {student_name} was absent from school on {date}.\nPlease contact the school if this was unplanned.\n\nBest regards,\nSchool Administration"),
        ]
        for name, category, body in TEMPLATES:
            MessageTemplate.objects.get_or_create(
                name=name,
                defaults={"category": category, "body": body, "created_by": admin_user},
            )

        # 2. Conversations + Messages
        CONV_DATA = [
            ("Fee Clarification – Term 1 2025",           "Group"),
            ("Parent Portal Announcement",                 "Group"),
            ("Staff Noticeboard – April 2025",             "Group"),
        ]
        for title, ctype in CONV_DATA:
            conv, c_created = Conversation.objects.get_or_create(
                title=title,
                defaults={"conversation_type": ctype, "created_by": admin_user},
            )
            if c_created:
                for user in users[:4]:
                    ConversationParticipant.objects.get_or_create(
                        conversation=conv, user=user,
                        defaults={"role": "Admin" if user == admin_user else "Member"},
                    )
                CommunicationMessage.objects.create(
                    conversation=conv,
                    sender=admin_user,
                    content=f"Welcome to '{title}'. Please check notices regularly.",
                    message_type="Text",
                    delivery_status="Read",
                )

        # 3. Notifications for all users
        NOTIF_MESSAGES = [
            ("Fee Statement Available",  "Your Term 1 2025 fee statement is ready for download.",  "Finance"),
            ("Exam Timetable Released",  "The Term 2 mid-term exam timetable has been published.",  "Academic"),
            ("Meeting Reminder",         "Parent-Teacher Meeting is scheduled for 8 March 2025.",   "System"),
            ("Library Book Due",         "You have a library book due for return on 15 March 2025.", "System"),
        ]
        for user in users[:6]:
            for i, (title, message, ntype) in enumerate(NOTIF_MESSAGES):
                Notification.objects.get_or_create(
                    recipient=user,
                    title=title,
                    defaults={
                        "notification_type": ntype,
                        "message":           message,
                        "priority":          "Informational",
                        "is_read":           (i % 2 == 0),
                        "delivery_status":   "Delivered" if i % 2 == 0 else "Sent",
                        "created_by":        admin_user,
                    },
                )
            # NotificationPreference
            NotificationPreference.objects.get_or_create(
                user=user,
                notification_type="System",
                defaults={
                    "channel_in_app": True,
                    "channel_email":  True,
                    "channel_sms":    False,
                    "channel_push":   False,
                },
            )

        # 4. EmailCampaign
        EmailCampaign.objects.get_or_create(
            title="Term 2 2025 Welcome Newsletter",
            defaults={
                "subject":      "Welcome to Term 2 2025 – St. Mary's Nairobi",
                "body_text":    "Dear Parent,\n\nWe welcome you to Term 2 2025. Please find enclosed the term calendar and key dates.\n\nBest regards,\nThe Principal",
                "body_html":    "<p>Dear Parent,</p><p>We welcome you to Term 2 2025. Please find enclosed the term calendar and key dates.</p><p>Best regards,<br>The Principal</p>",
                "sender_name":  "St. Mary's Nairobi",
                "sender_email": "info@stmarys.ac.ke",
                "status":       "Sent",
                "sent_at":      None,
                "created_by":   admin_user,
            },
        )

        # 5. SmsMessage
        SMS_MSGS = [
            ("0722000001", "Dear Parent, your child's Term 1 fee balance is outstanding. Please settle by 15 Jan 2025. Thank you."),
            ("0733000002", "Exam timetable for Term 2 has been published. Log in to parent portal to view the schedule."),
            ("0744000003", "School reopens 6 Jan 2025 (Term 1). Please ensure all fees are paid before first day. Regards, Administration."),
        ]
        for phone, msg in SMS_MSGS:
            SmsMessage.objects.get_or_create(
                recipient_phone=phone,
                message=msg,
                defaults={
                    "channel":    "SMS",
                    "status":     "Delivered",
                    "created_by": admin_user,
                },
            )

        self.stdout.write(
            f"    → Communication: {Conversation.objects.count()} conversations, "
            f"{CommunicationMessage.objects.count()} messages, "
            f"{Notification.objects.count()} notifications, "
            f"{EmailCampaign.objects.count()} campaigns, "
            f"{SmsMessage.objects.count()} SMS messages, "
            f"{MessageTemplate.objects.count()} templates"
        )

    # ── Assets Comprehensive ──────────────────────────────────────────────────
    def _seed_assets_comprehensive(self, admin_user):
        try:
            from assets.models import Asset, AssetAssignment, AssetMaintenanceRecord, AssetWarranty, AssetDepreciation
            from hr.models import Employee
        except ImportError:
            self.stdout.write("    Assets app not available — skipping")
            return
        import random
        random.seed(46)

        assets = list(Asset.objects.all())
        employees = list(Employee.objects.all()[:5])
        students  = list(Student.objects.all()[:5])

        for i, asset in enumerate(assets[:8]):
            # AssetAssignment (alternate employee and student)
            if not asset.assignments.exists():
                if i % 2 == 0 and employees:
                    AssetAssignment.objects.create(
                        asset=asset,
                        assigned_to_employee=employees[i % len(employees)],
                        assigned_date=date(2025, 1, 15),
                        return_due_date=date(2025, 12, 31),
                        status="Active",
                        notes=f"Assigned for school use — {asset.name}",
                    )
                elif students:
                    AssetAssignment.objects.create(
                        asset=asset,
                        assigned_to_student=students[i % len(students)],
                        assigned_date=date(2025, 1, 15),
                        return_due_date=date(2025, 3, 31),
                        status="Active",
                    )

            # AssetMaintenanceRecord for first 5 assets
            if i < 5 and not asset.maintenance_records.exists():
                AssetMaintenanceRecord.objects.create(
                    asset=asset,
                    maintenance_type="Service" if i % 2 == 0 else "Inspection",
                    scheduled_date=date(2025, 2, 10),
                    completion_date=date(2025, 2, 12),
                    cost=Decimal(str(random.randint(2000, 15000))),
                    performed_by="Mwangi Electrical Services Ltd",
                    description=f"Routine maintenance of {asset.name}.",
                    status="Completed",
                )

            # AssetWarranty for first 6 assets
            if i < 6 and not asset.warranties.exists():
                AssetWarranty.objects.create(
                    asset=asset,
                    provider=f"{['Samsung', 'HP', 'Dell', 'LG', 'Epson', 'Lenovo'][i % 6]} East Africa",
                    start_date=date(2024, 1, 1),
                    expiry_date=date(2027, 1, 1),
                    coverage_details="Full parts and labour warranty against manufacturing defects.",
                    status="active",
                )

            # AssetDepreciation for first 8 assets
            if not asset.depreciations.exists():
                book_value = asset.purchase_cost if hasattr(asset, 'purchase_cost') and asset.purchase_cost else Decimal("50000.00")
                depr_rate  = Decimal("0.20")
                depr_amt   = (book_value * depr_rate).quantize(Decimal("0.01"))
                AssetDepreciation.objects.create(
                    asset=asset,
                    period_label="FY 2024",
                    depreciation_amount=depr_amt,
                    accumulated_depreciation=depr_amt,
                    net_book_value=book_value - depr_amt,
                )

        self.stdout.write(
            f"    → Assets: {AssetAssignment.objects.count()} assignments, "
            f"{AssetMaintenanceRecord.objects.count()} maintenance records, "
            f"{AssetWarranty.objects.count()} warranties, "
            f"{AssetDepreciation.objects.count()} depreciations"
        )

    # ── Cafeteria Comprehensive ───────────────────────────────────────────────
    def _seed_cafeteria_comprehensive(self, students, admin_user):
        try:
            from cafeteria.models import MealTransaction, CafeteriaWalletTransaction
        except ImportError:
            self.stdout.write("    Cafeteria app not available — skipping")
            return
        import random
        random.seed(47)

        today = date.today()
        monday = today - timedelta(days=today.weekday())

        # MealTransactions — 5 days x 3 meals x first 20 students
        meals_created = 0
        for day_offset in range(5):
            school_day = monday + timedelta(days=day_offset)
            for student in students[:20]:
                for meal_type in ["Breakfast", "Lunch", "Supper"]:
                    _, created = MealTransaction.objects.get_or_create(
                        student=student, date=school_day, meal_type=meal_type,
                        defaults={"served": True},
                    )
                    if created:
                        meals_created += 1

        # CafeteriaWalletTransactions — top-ups and debits for first 15 students
        wallet_created = 0
        for student in students[:15]:
            # Credit (top-up)
            wt, created = CafeteriaWalletTransaction.objects.get_or_create(
                student=student,
                transaction_type="Credit",
                amount=Decimal("5000.00"),
                defaults={
                    "description":   "Term 1 2025 meal plan top-up",
                    "balance_after": Decimal("5000.00"),
                },
            )
            if created:
                wallet_created += 1
            # Debit (meal costs)
            MealTransaction.objects.filter(student=student).first()
            CafeteriaWalletTransaction.objects.get_or_create(
                student=student,
                transaction_type="Debit",
                amount=Decimal("100.00"),
                defaults={
                    "description":   "Daily meal deduction",
                    "balance_after": Decimal("4900.00"),
                },
            )

        self.stdout.write(
            f"    → Cafeteria: {MealTransaction.objects.count()} meal transactions, "
            f"{CafeteriaWalletTransaction.objects.count()} wallet transactions"
        )

    # ── Hostel Comprehensive ──────────────────────────────────────────────────
    def _seed_hostel_comprehensive(self, students, admin_user):
        try:
            from hostel.models import HostelAttendance, HostelLeave
        except ImportError:
            self.stdout.write("    Hostel app not available — skipping")
            return
        import random
        random.seed(48)

        today = date.today()
        monday = today - timedelta(days=today.weekday())

        # HostelAttendance — 5 nights x 3 roll-calls x first 20 students
        for day_offset in range(5):
            school_day = monday + timedelta(days=day_offset)
            for student in students[:20]:
                for roll_time in ["Morning", "Evening", "Night"]:
                    status = "Present" if random.random() > 0.05 else "Absent"
                    HostelAttendance.objects.get_or_create(
                        student=student, date=school_day, roll_call_time=roll_time,
                        defaults={"status": status, "recorded_by": admin_user},
                    )

        # HostelLeave — 5 students with approved exeat leave
        for i, student in enumerate(students[:5]):
            HostelLeave.objects.get_or_create(
                student=student,
                leave_from=date(2025, 2, 14),
                leave_to=date(2025, 2, 16),
                defaults={
                    "reason":      "Half-term mid-week exeat (parents' request).",
                    "approved_by": admin_user,
                    "status":      "Approved",
                },
            )

        self.stdout.write(
            f"    → Hostel: {HostelAttendance.objects.count()} attendance records, "
            f"{HostelLeave.objects.count()} leave requests"
        )

    # ── Timetable Duty Slots ──────────────────────────────────────────────────
    def _seed_timetable_comprehensive(self, terms):
        try:
            from timetable.models import StaffDutySlot
            from hr.models import Employee
        except ImportError:
            self.stdout.write("    Timetable/HR app not available — skipping")
            return
        from datetime import time as dt_time
        import random
        random.seed(49)

        term1 = terms[0] if terms else None
        employees = list(Employee.objects.all()[:10])

        DUTIES = [
            (1, "Gate Duty – Morning",       dt_time(6, 30), dt_time(7, 30),  "School Main Gate"),
            (2, "Library Supervision",        dt_time(13, 0), dt_time(14, 0), "School Library"),
            (3, "Dining Hall Supervision",    dt_time(12, 30), dt_time(13, 30), "Dining Hall"),
            (4, "Games & Sports Supervision", dt_time(15, 30), dt_time(17, 0), "Sports Ground"),
            (5, "Evening Prep Supervision",   dt_time(19, 0), dt_time(21, 0), "Main Classroom Block"),
            (1, "Dormitory Inspection",       dt_time(21, 30), dt_time(22, 0), "Dormitory Block A"),
            (3, "Gate Duty – Afternoon",      dt_time(16, 30), dt_time(17, 30), "School Main Gate"),
        ]

        for i, (day_of_week, description, start, end, location) in enumerate(DUTIES):
            if i < len(employees):
                emp = employees[i]
                StaffDutySlot.objects.get_or_create(
                    employee=emp, day_of_week=day_of_week, description=description,
                    defaults={
                        "duty_start": start,
                        "duty_end":   end,
                        "location":   location,
                        "term":       term1,
                        "is_active":  True,
                    },
                )

        self.stdout.write(f"    → Duty Slots: {StaffDutySlot.objects.count()} seeded")

    # ── Transport Incidents ───────────────────────────────────────────────────
    def _seed_transport_comprehensive(self):
        try:
            from transport.models import TransportIncident, Vehicle
        except ImportError:
            self.stdout.write("    Transport app not available — skipping")
            return

        vehicles = list(Vehicle.objects.all())
        if not vehicles:
            return

        INCIDENTS = [
            (vehicles[0], date(2025, 2, 5),  "Minor", "Flat tyre on Ngong Road. Students were safe. Spare changed on-site.", True),
            (vehicles[1], date(2025, 2, 28), "Minor", "Minor fender bender in school parking area. No injuries. Driver reprimanded.", True),
            (vehicles[0], date(2025, 3, 12), "Minor", "Engine warning light activated en route. Vehicle returned to school and serviced.", True),
        ]
        for vehicle, inc_date, severity, desc, resolved in INCIDENTS:
            TransportIncident.objects.get_or_create(
                vehicle=vehicle, incident_date=inc_date,
                defaults={
                    "description":   desc,
                    "severity":      severity,
                    "reported_by":   "Joseph Mwangi (Driver)",
                    "resolved":      resolved,
                },
            )

        self.stdout.write(f"    → Transport: {TransportIncident.objects.count()} incidents seeded")

    # ── Visitor Authorized Pickups + Logs ────────────────────────────────────
    def _seed_visitor_comprehensive(self, students, admin_user):
        try:
            from visitor_mgmt.models import AuthorizedPickup, StudentPickupLog
        except ImportError:
            self.stdout.write("    Visitor Mgmt app not available — skipping")
            return
        import random
        random.seed(50)

        authorized_list = []
        for student in students[:15]:
            guardian = Guardian.objects.filter(student=student).first()
            if guardian:
                ap, _ = AuthorizedPickup.objects.get_or_create(
                    student=student,
                    guardian_name=guardian.name,
                    defaults={
                        "relationship": guardian.relationship or "Parent",
                        "id_number":    f"ID{random.randint(10000000, 39999999)}",
                        "phone":        guardian.phone or "0722000000",
                        "is_active":    True,
                    },
                )
                authorized_list.append((student, ap))

        # StudentPickupLog — one entry per authorized pair
        for student, ap in authorized_list[:8]:
            if not StudentPickupLog.objects.filter(student=student, picked_up_by=ap).exists():
                StudentPickupLog.objects.create(
                    student=student,
                    picked_up_by=ap,
                    authorized=True,
                    notes="",
                )

        self.stdout.write(
            f"    → Visitor: {AuthorizedPickup.objects.count()} authorized pickups, "
            f"{StudentPickupLog.objects.count()} pickup logs"
        )

    # ── Library Comprehensive ─────────────────────────────────────────────────
    def _seed_library_comprehensive(self, admin_user):
        try:
            from library.models import (
                LibraryResource, LibraryMember, Reservation,
                InventoryAudit, AcquisitionRequest,
            )
        except ImportError:
            self.stdout.write("    Library app not available — skipping")
            return
        import random
        random.seed(51)

        resources = list(LibraryResource.objects.all()[:10])
        members   = list(LibraryMember.objects.all()[:10])

        # Reservations
        for i, (member, resource) in enumerate(zip(members[:8], resources[:8])):
            status = "Picked" if i < 4 else "Waiting"
            Reservation.objects.get_or_create(
                resource=resource, member=member,
                defaults={
                    "status":           status,
                    "pickup_deadline":  date(2025, 3, 31) if status == "Waiting" else None,
                },
            )

        # InventoryAudit
        total = LibraryResource.objects.count()
        InventoryAudit.objects.get_or_create(
            audit_date=date(2025, 1, 10),
            defaults={
                "conducted_by":  admin_user,
                "total_expected": total,
                "total_found":    total - random.randint(0, 3),
                "status":        "Completed",
            },
        )

        # AcquisitionRequests
        BOOKS = [
            ("Advanced Chemistry for Secondary Schools – Grade 9", "Kimani Muturi",    "9789966252"),
            ("Physics Concepts and Applications – Grade 10",        "James Wanyoike",   "9789966253"),
            ("Kenya History & Government – Comprehensive Guide",   "Grace Njeri",      "9789966254"),
        ]
        for title, author, isbn in BOOKS:
            AcquisitionRequest.objects.get_or_create(
                title=title,
                defaults={
                    "requested_by": admin_user,
                    "author":       author,
                    "isbn":         isbn,
                    "quantity":     5,
                    "justification": "High student demand; existing copies are insufficient.",
                    "status":       "Approved",
                },
            )

        self.stdout.write(
            f"    → Library: {Reservation.objects.count()} reservations, "
            f"{InventoryAudit.objects.count()} inventory audits, "
            f"{AcquisitionRequest.objects.count()} acquisition requests"
        )

    # ── E-Learning Quiz Attempts ──────────────────────────────────────────────
    def _seed_elearning_comprehensive(self, students):
        try:
            from elearning.models import OnlineQuiz, QuizAttempt
        except ImportError:
            self.stdout.write("    E-Learning app not available — skipping")
            return
        import random
        from django.utils import timezone as tz
        random.seed(52)

        quizzes = list(OnlineQuiz.objects.all()[:5])
        if not quizzes:
            return

        for quiz in quizzes:
            for student in students[:10]:
                score = Decimal(str(round(random.gauss(70, 15), 1)))
                score = max(Decimal("0"), min(Decimal("100"), score))
                percentage = score  # 100-point scale
                QuizAttempt.objects.get_or_create(
                    quiz=quiz, student=student,
                    defaults={
                        "score":        score,
                        "percentage":   percentage,
                        "submitted_at": tz.now(),
                        "status":       "Graded",
                    },
                )

        self.stdout.write(f"    → E-Learning: {QuizAttempt.objects.count()} quiz attempts seeded")

    # ── Maintenance Checklist Items ────────────────────────────────────────────
    def _seed_maintenance_comprehensive(self):
        try:
            from maintenance.models import MaintenanceRequest, MaintenanceChecklist
        except ImportError:
            self.stdout.write("    Maintenance app not available — skipping")
            return
        from django.utils import timezone as tz

        requests = list(MaintenanceRequest.objects.all())
        TASKS = [
            "Inspect and diagnose the reported fault",
            "Source required materials / spare parts",
            "Carry out repair work",
            "Test and verify the fix is effective",
            "Clean up and restore work area",
        ]
        count = 0
        for req in requests[:6]:
            if not req.checklist_items.exists():
                for i, task_desc in enumerate(TASKS):
                    is_done = i < 3
                    MaintenanceChecklist.objects.create(
                        request=req,
                        task_description=task_desc,
                        is_completed=is_done,
                        completed_at=tz.now() if is_done else None,
                    )
                    count += 1

        self.stdout.write(f"    → Maintenance: {MaintenanceChecklist.objects.count()} checklist items seeded")

    # ── School Store ──────────────────────────────────────────────────────────
    def _seed_store_comprehensive(self, admin_user):
        try:
            from school.models import (
                StoreCategory, StoreSupplier, StoreItem,
                StoreTransaction, StoreOrderRequest, StoreOrderItem,
            )
        except ImportError:
            self.stdout.write("    Store app not available — skipping")
            return
        import random
        random.seed(53)

        # 1. StoreCategory
        CATEGORIES = [
            ("Stationery & Office Supplies", "OFFICE",   "OFFICE"),
            ("Food & Provisions",            "FOOD",     "FOOD"),
            ("Cleaning & Hygiene",           "CLEANING", "OFFICE"),
            ("Sports Equipment",             "SPORTS",   "OFFICE"),
            ("Laboratory Supplies",          "LAB",      "OFFICE"),
        ]
        cat_map = {}
        for name, _, itype in CATEGORIES:
            cat, _ = StoreCategory.objects.get_or_create(
                name=name,
                defaults={"item_type": itype, "is_active": True},
            )
            cat_map[name] = cat

        # 2. StoreSupplier
        SUPPLIERS = [
            ("Kenya Office Supplies Ltd",  "James Kimani",  "0722300400", "supplies@kenyaoffice.co.ke"),
            ("Nairobi Food Distributors",  "Mary Wanjiku",  "0733400500", "orders@nairobifood.co.ke"),
            ("CleanPro Kenya Ltd",         "Peter Mwangi",  "0744500600", "info@cleanpro.co.ke"),
        ]
        supplier_map = {}
        for name, contact, phone, email in SUPPLIERS:
            sup, _ = StoreSupplier.objects.get_or_create(
                name=name,
                defaults={
                    "contact_person": contact, "phone": phone,
                    "email": email, "is_active": True,
                },
            )
            supplier_map[name] = sup

        # 3. StoreItem
        ITEMS = [
            ("A4 Copy Paper (Ream 80gsm)",   "PAP-A4-80",  "Stationery & Office Supplies", "reams",  "OFFICE", 120, 20,  200,  Decimal("420.00")),
            ("Ballpoint Pens (Box of 50)",   "PEN-BP-50",  "Stationery & Office Supplies", "boxes",  "OFFICE",  45, 10,   80,  Decimal("350.00")),
            ("Whiteboard Markers (Box 12)",  "MRK-WB-12",  "Stationery & Office Supplies", "boxes",  "OFFICE",  30,  8,   60,  Decimal("480.00")),
            ("Maize Meal (2 kg bag)",        "FD-MAZ-2KG", "Food & Provisions",            "bags",   "FOOD",   200, 50,  400,  Decimal("130.00")),
            ("Cooking Oil (5 L jerry)",      "FD-OIL-5L",  "Food & Provisions",            "jerries","FOOD",    40, 15,   80,  Decimal("950.00")),
            ("Hand Sanitiser (500 ml)",      "CLN-SAN-500","Cleaning & Hygiene",           "bottles","OFFICE",  60, 20,  100,  Decimal("280.00")),
            ("Detergent Powder (2 kg)",      "CLN-DET-2KG","Cleaning & Hygiene",           "packets","OFFICE",  35, 10,   70,  Decimal("350.00")),
            ("Football (Size 5)",            "SPT-FB-5",   "Sports Equipment",             "pcs",    "OFFICE",  10,  3,   20,  Decimal("2200.00")),
        ]
        item_map = {}
        for name, sku, cat_name, unit, itype, curr_stk, reorder, max_stk, cost in ITEMS:
            cat = cat_map.get(cat_name)
            item, _ = StoreItem.objects.get_or_create(
                name=name,
                defaults={
                    "sku":           sku,
                    "category":      cat,
                    "unit":          unit,
                    "item_type":     itype,
                    "current_stock": Decimal(str(curr_stk)),
                    "reorder_level": Decimal(str(reorder)),
                    "max_stock":     Decimal(str(max_stk)),
                    "cost_price":    cost,
                    "is_active":     True,
                },
            )
            item_map[name] = item

        # 4. StoreTransactions — OPENING stock for first 5 items (only once)
        for name, item in list(item_map.items())[:5]:
            if not item.transactions.filter(transaction_type="OPENING").exists():
                StoreTransaction.objects.create(
                    item=item,
                    transaction_type="OPENING",
                    quantity=item.current_stock,
                    reference="OPENING-JAN-2025",
                    department="Store",
                    purpose="Opening stock entry for FY 2025",
                    performed_by=admin_user,
                    date=date(2025, 1, 3),
                )

        # 5. StoreOrderRequest + StoreOrderItems
        items_list = list(item_map.values())
        order, _ = StoreOrderRequest.objects.get_or_create(
            title="Q1 2025 Stationery and Provisions Requisition",
            defaults={
                "description":   "Quarterly requisition for office supplies and food provisions.",
                "requested_by":  admin_user,
                "send_to":       "FINANCE",
                "status":        "APPROVED",
                "notes":         "Approved by Principal on 20 Jan 2025.",
            },
        )
        for item in items_list[:4]:
            StoreOrderItem.objects.get_or_create(
                order=order, item=item,
                defaults={
                    "item_name":          item.name,
                    "unit":               item.unit,
                    "quantity_requested": Decimal("20.00"),
                    "quantity_approved":  Decimal("20.00"),
                },
            )

        self.stdout.write(
            f"    → Store: {StoreCategory.objects.count()} categories, "
            f"{StoreSupplier.objects.count()} suppliers, "
            f"{StoreItem.objects.count()} items, "
            f"{StoreTransaction.objects.count()} transactions, "
            f"{StoreOrderRequest.objects.count()} orders"
        )

    # ── Dispensary ────────────────────────────────────────────────────────────
    def _seed_dispensary(self, students, admin_user):
        try:
            from school.models import DispensaryVisit, DispensaryPrescription, DispensaryStock
        except ImportError:
            self.stdout.write("    Dispensary app not available — skipping")
            return
        import random
        random.seed(54)
        from datetime import time as dt_time

        # 1. DispensaryStock
        STOCK = [
            ("Paracetamol 500mg",        "PCM-500",  500,  "tablets", 50, date(2027, 6, 30), "Cosmos Ltd"),
            ("Ibuprofen 400mg",           "IBU-400",  200,  "tablets", 30, date(2027, 3, 31), "Dawa Ltd"),
            ("Amoxicillin 250mg Capsules","AMX-250",  100,  "capsules",20, date(2026, 12, 31),"Universal Corp"),
            ("ORS Sachets",               "ORS-SAC",  150,  "sachets", 30, date(2027, 1, 31), "Cosmos Ltd"),
            ("Antiseptic Cream (50g)",    "ANT-50G",   40,  "tubes",   10, date(2026, 9, 30), "Dawa Ltd"),
            ("Bandages (7.5cm roll)",     "BAN-75",    80,  "rolls",   15, date(2028, 1, 1),  "Universal Corp"),
            ("Eye Drops (10ml)",          "EYE-10ML",  60,  "bottles", 10, date(2026, 6, 30), "Cosmos Ltd"),
        ]
        for name, generic, qty, unit, reorder, expiry, supplier in STOCK:
            DispensaryStock.objects.get_or_create(
                medication_name=name,
                defaults={
                    "generic_name":    generic,
                    "current_quantity": Decimal(str(qty)),
                    "unit":            unit,
                    "reorder_level":   Decimal(str(reorder)),
                    "expiry_date":     expiry,
                    "supplier":        supplier,
                },
            )

        # 2. DispensaryVisit + DispensaryPrescription for 10 students
        COMPLAINTS = [
            ("Headache and mild fever",               "Febrile illness — pyrexia",          "Paracetamol 500mg",        "500mg twice daily",   "3 days",   2),
            ("Stomach pain and nausea",               "Gastritis",                           "Ibuprofen 400mg",          "400mg with meals",    "2 days",   1),
            ("Sore throat and cough",                 "Upper respiratory tract infection",   "Amoxicillin 250mg Capsules","3 capsules daily",   "5 days",   5),
            ("Diarrhoea and dehydration signs",       "Mild dehydration — gastroenteritis",  "ORS Sachets",              "1 sachet per hour",   "2 days",   3),
            ("Eye irritation and redness",            "Conjunctivitis",                      "Eye Drops (10ml)",         "2 drops 3x daily",    "5 days",   1),
            ("Cut on right hand",                     "Minor laceration — cleaned",          "Antiseptic Cream (50g)",   "Apply twice daily",   "3 days",   1),
            ("Leg pain after sports",                 "Sports strain — soft tissue injury",  "Ibuprofen 400mg",          "400mg twice daily",   "3 days",   1),
            ("Dizzy spells and weakness",             "Low blood sugar — hypoglycaemia",     "ORS Sachets",              "Oral rehydration",    "1 day",    1),
            ("Toothache",                             "Dental pain — referred to dentist",   "Paracetamol 500mg",        "500mg as needed",     "2 days",   2),
            ("Skin rash on arms",                     "Allergic contact dermatitis",         "Antiseptic Cream (50g)",   "Apply morning/evening","5 days",  1),
        ]
        visit_dates = [date(2025, 2, 10), date(2025, 2, 17), date(2025, 3, 3),
                       date(2025, 3, 10), date(2025, 3, 17)]

        for i, student in enumerate(students[:10]):
            complaint, diagnosis, med_name, dosage, duration, qty = COMPLAINTS[i]
            v_date = visit_dates[i % len(visit_dates)]
            visit, v_created = DispensaryVisit.objects.get_or_create(
                student=student, visit_date=v_date,
                defaults={
                    "visit_time":       dt_time(10, random.randint(0, 59)),
                    "complaint":        complaint,
                    "diagnosis":        diagnosis,
                    "treatment":        "Medication dispensed as per prescription below.",
                    "attended_by":      admin_user,
                    "severity":         "MINOR",
                    "parent_notified":  i < 3,
                    "referred":         i == 8,
                    "referred_to":      "Kenyatta National Hospital Dental Clinic" if i == 8 else "",
                    "follow_up_date":   v_date + timedelta(days=5) if i < 5 else None,
                },
            )
            if v_created:
                DispensaryPrescription.objects.create(
                    visit=visit,
                    medication_name=med_name,
                    dosage=dosage,
                    frequency=f"For {duration}",
                    quantity_dispensed=Decimal(str(qty)),
                    unit="tablets" if "tablet" in med_name.lower() else "units",
                )

        self.stdout.write(
            f"    → Dispensary: {DispensaryStock.objects.count()} stock items, "
            f"{DispensaryVisit.objects.count()} visits, "
            f"{DispensaryPrescription.objects.count()} prescriptions"
        )

    # ── Examination Setter Assignments ────────────────────────────────────────
    def _seed_exam_setter_assignments(self, admin_user):
        try:
            from examinations.models import ExamSession, ExamSetterAssignment
        except ImportError:
            self.stdout.write("    Examinations app not available — skipping")
            return
        import random
        random.seed(56)

        sessions = list(ExamSession.objects.all()[:2])
        teachers  = list(User.objects.exclude(username="Riqs#.")[:8])
        core_subjects = list(Subject.objects.filter(is_active=True)[:8])
        flat_classes  = list(SchoolClass.objects.all()[:4])

        if not sessions or not teachers or not core_subjects:
            return

        session = sessions[-1]  # Upcoming session
        for i, subj in enumerate(core_subjects):
            for cls in flat_classes[:2]:
                teacher = teachers[i % len(teachers)]
                ExamSetterAssignment.objects.get_or_create(
                    session=session, subject=subj, school_class=cls,
                    defaults={
                        "teacher":     teacher,
                        "deadline":    date(2025, 5, 16),
                        "notes":       f"Please prepare the {subj.name} exam paper for {cls.name}.",
                        "assigned_by": admin_user,
                    },
                )

        self.stdout.write(f"    → Exam Setter Assignments: {ExamSetterAssignment.objects.count()} seeded")

    # ── Assignments + Submissions ─────────────────────────────────────────────
    def _seed_assignments(self, students, admin_user):
        import random
        from datetime import datetime, timedelta, timezone as tz
        from school.models import SchoolClass, Subject, Assignment, AssignmentSubmission

        random.seed(99)
        now = datetime.now(tz=tz.utc)
        subjects = list(Subject.objects.all()[:10])
        classes = list(SchoolClass.objects.all())
        TEMPLATES = [
            ('Mathematics Problem Set 1', 'Solve 20 quadratic equations using CBE methodology.', 'Published', now - timedelta(days=14)),
            ('Essay: Environmental Conservation', 'Write a 500-word essay on environmental conservation in Kenya.', 'Graded', now - timedelta(days=10)),
            ('Science Lab Report: Photosynthesis', 'Document the photosynthesis experiment conducted in the lab.', 'Published', now + timedelta(days=3)),
            ('Geography Map Exercise', 'Draw and label major geographical features of East Africa.', 'Graded', now - timedelta(days=7)),
            ('History Research: Colonial Kenya', 'Research and summarize the impact of colonialism on Kenya.', 'Published', now + timedelta(days=5)),
            ('English Comprehension Exercise', 'Read and answer comprehension questions from Unit 4.', 'Closed', now - timedelta(days=2)),
            ('Biology: Cell Structures Diagram', 'Draw and label plant and animal cell structures.', 'Graded', now - timedelta(days=5)),
            ('Chemistry: Periodic Table Quiz Prep', 'Memorize elements 1-20 and their properties for next lesson.', 'Published', now + timedelta(days=7)),
            ('Physics: Forces and Motion Problems', 'Complete 15 problems on Newton laws of motion.', 'Graded', now - timedelta(days=9)),
            ('Computer Studies: Python Basics', 'Write a program that calculates BMI for 5 students.', 'Published', now + timedelta(days=10)),
        ]
        a_created = 0
        for cls in classes:
            for i, (title, desc, status, due_date) in enumerate(TEMPLATES):
                subj = subjects[i % len(subjects)]
                _, was_created = Assignment.objects.get_or_create(
                    title=title, class_section=cls, subject=subj,
                    defaults={'description': desc, 'status': status, 'due_date': due_date,
                              'teacher': admin_user, 'is_active': True, 'max_score': 100},
                )
                if was_created:
                    a_created += 1
        s_created = 0
        for student in students[:20]:
            from school.models import Enrollment
            enrollment = Enrollment.objects.filter(student=student, is_active=True, status='Active').first()
            if not enrollment:
                continue
            for asgn in Assignment.objects.filter(class_section=enrollment.school_class, status__in=['Graded', 'Closed'], is_active=True):
                _, was_created = AssignmentSubmission.objects.get_or_create(
                    assignment=asgn, student=student,
                    defaults={'notes': 'Submitted via portal.', 'is_late': False,
                              'score': random.randint(65, 98), 'feedback': 'Good work! Keep applying CBE competency standards.',
                              'is_active': True},
                )
                if was_created:
                    s_created += 1
        self.stdout.write(f'    → Assignments: {a_created} created, Submissions: {s_created} created')

    # ── School Profile (Logo + Branding) ─────────────────────────────────────
    def _seed_school_profile(self):
        from school.models import SchoolProfile
        profile, created = SchoolProfile.objects.get_or_create(is_active=True, defaults={
            'school_name': 'RynatySchool SmartCampus',
            'primary_color': '#10b981',
            'secondary_color': '#0d1117',
        })
        profile.logo = 'school_logos/rynaty-logo.png'
        profile.save(update_fields=['logo'])
        action = 'Created' if created else 'Updated'
        self.stdout.write(f'    → {action} SchoolProfile with logo: {profile.logo}')

    # ── TenantModule Activations ──────────────────────────────────────────────
    def _seed_tenant_modules(self):
        from school.management.commands.seed_modules import ALL_MODULES
        created = 0
        for key, name, sort_order in ALL_MODULES:
            module, _ = Module.objects.get_or_create(
                key=key,
                defaults={'name': name, 'is_active': True},
            )
            _, was_created = TenantModule.objects.get_or_create(
                module=module,
                defaults={'is_enabled': True, 'sort_order': sort_order},
            )
            if was_created:
                created += 1
        self.stdout.write(
            f'    → TenantModule: {created} new activations '
            f'(total active: {TenantModule.objects.filter(is_enabled=True).count()})'
        )
