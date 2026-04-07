"""
seed_kenya_school.py
Comprehensive sample data for a Kenyan 8-4-4 high school (St. Mary's Nairobi High School).
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

FORMS = ["Form 1", "Form 2", "Form 3", "Form 4"]
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
    ("Classroom 12B Door Replacement", "Medium", "Form 2 Block"),
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
                admin = User.objects.filter(is_superuser=True).first() or User.objects.filter(username="admin").first()
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

        self.stdout.write("  Seeding Kenyan CBC curriculum…")
        self._seed_curriculum()

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

        self.stdout.write("  Activating all modules for this tenant (TenantModule)…")
        self._seed_tenant_modules()

    # ── Gradebook + Report Cards ──────────────────────────────────────────────
    def _seed_gradebook_and_reports(self, year, terms, classes):
        import random
        random.seed(42)

        # 1. KNEC Grading Scheme
        scheme, _ = GradingScheme.objects.get_or_create(
            name="KNEC Standard",
            defaults={"is_default": True, "is_active": True},
        )
        KNEC_BANDS = [
            ("A",  75, 100, 12.0, "Excellent"),
            ("A-", 70,  74, 11.0, "Very Good"),
            ("B+", 65,  69, 10.0, "Good"),
            ("B",  60,  64,  9.0, "Good"),
            ("B-", 55,  59,  8.0, "Above Average"),
            ("C+", 50,  54,  7.0, "Average"),
            ("C",  45,  49,  6.0, "Average"),
            ("C-", 40,  44,  5.0, "Below Average"),
            ("D+", 35,  39,  4.0, "Below Average"),
            ("D",  30,  34,  3.0, "Poor"),
            ("D-", 25,  29,  2.0, "Very Poor"),
            ("E",   0,  24,  1.0, "Fail"),
        ]
        bands = {}
        for label, mn, mx, pts, rem in KNEC_BANDS:
            b, _ = GradeBand.objects.get_or_create(
                scheme=scheme, label=label,
                defaults={"min_score": mn, "max_score": mx, "grade_point": pts, "remark": rem, "is_active": True},
            )
            bands[label] = b

        def score_to_band(score):
            for label, mn, mx, _, _ in KNEC_BANDS:
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

    # ── Kenyan CBC Curriculum ─────────────────────────────────────────────────
    def _seed_curriculum(self):
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

        # Kenyan 8-4-4 and CBC Senior Secondary subjects
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
            # CBC strands
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
            username="admin",
            defaults={
                "email": "admin@stmarysnairobi.ac.ke",
                "first_name": "Principal",
                "last_name": "Mwangi",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if not user.check_password("admin123"):
            user.set_password("admin123")
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
        for form in FORMS:
            classes[form] = {}
            for stream in STREAMS:
                cls, _ = SchoolClass.objects.get_or_create(
                    name=form,
                    stream=stream,
                    academic_year=year,
                    defaults={"is_active": True},
                )
                classes[form][stream] = cls

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
            (f, s) for f in FORMS for s in STREAMS
        ]

        for i, (first, last, gender) in enumerate(all_names):
            adm_no = f"STM{2025}{str(i + 1).zfill(3)}"
            form, stream = form_stream_pairs[i % len(form_stream_pairs)]
            dob_year = 2025 - (14 + int(form[-1]))
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
            # Enroll in Term 1
            cls = classes[form][stream]
            Enrollment.objects.get_or_create(
                student=s,
                school_class=cls,
                term=terms[0],
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

        # Invoice + payment for each student
        ref_counter = 9000
        for i, student in enumerate(students):
            inv = Invoice.objects.create(
                student=student,
                term=term1,
                due_date=date(2025, 2, 14),
                total_amount=total_term1,
                status="CONFIRMED",
            )
            for fs in structs:
                InvoiceLineItem.objects.create(
                    invoice=inv,
                    fee_structure=fs,
                    description=fs.name.split(" — ")[0],
                    amount=fs.amount,
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
                unique_ref = f"RCPT-KE{ref_counter}-{uuid.uuid4().hex[:6].upper()}"
                pmt, _ = Payment.objects.get_or_create(
                    student=student,
                    notes=f"Term 1 2025 payment — {student.admission_number}",
                    defaults={
                        "amount": paid_amount,
                        "payment_method": random.choice(["Cash", "M-Pesa", "Bank Transfer", "Cheque"]),
                        "reference_number": unique_ref,
                    },
                )
                PaymentAllocation.objects.create(
                    payment=pmt,
                    invoice=inv,
                    amount_allocated=paid_amount,
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
                    "notes": "Applying for Form 1 admission, 2025 academic year.",
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
            ("KCSE Mock Examinations Schedule", "Form 4 mock exams begin on 10th February 2025. Timetables available from the Deputy Principal's office."),
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
            ('KLB Mathematics Form 1', 'Kenya Literature Bureau', 'Mathematics', 'Book', '9789966100', 2022, 8, 'Textbooks'),
            ('KLB Mathematics Form 2', 'Kenya Literature Bureau', 'Mathematics', 'Book', '9789966101', 2022, 8, 'Textbooks'),
            ('KLB Mathematics Form 3', 'Kenya Literature Bureau', 'Mathematics', 'Book', '9789966102', 2022, 5, 'Mathematics'),
            ('KLB Mathematics Form 4', 'Kenya Literature Bureau', 'Mathematics', 'Book', '9789966103', 2023, 5, 'Mathematics'),
            ('KLB Biology Form 1', 'Kenya Literature Bureau', 'Biology', 'Book', '9789966200', 2022, 8, 'Science'),
            ('KLB Biology Form 2', 'Kenya Literature Bureau', 'Biology', 'Book', '9789966201', 2022, 8, 'Science'),
            ('KLB Biology Form 3', 'Kenya Literature Bureau', 'Biology', 'Book', '9789966202', 2023, 6, 'Science'),
            ('KLB Chemistry Form 2', 'Kenya Literature Bureau', 'Chemistry', 'Book', '9789966300', 2022, 7, 'Science'),
            ('KLB Chemistry Form 3', 'Kenya Literature Bureau', 'Chemistry', 'Book', '9789966301', 2023, 6, 'Science'),
            ('KLB Physics Form 2', 'Kenya Literature Bureau', 'Physics', 'Book', '9789966400', 2022, 7, 'Science'),
            ('KLB Physics Form 3', 'Kenya Literature Bureau', 'Physics', 'Book', '9789966401', 2023, 6, 'Science'),
            ('Things Fall Apart', 'Chinua Achebe', 'English', 'Book', '9780385474542', 1958, 4, 'Literature'),
            ('A Grain of Wheat', 'Ngugi wa Thiong\'o', 'English', 'Book', '9780435906856', 1967, 3, 'Literature'),
            ('The River Between', 'Ngugi wa Thiong\'o', 'English', 'Book', '9780435908843', 1965, 3, 'Literature'),
            ('Blossoms of the Savannah', 'Henry R. Ole Kulet', 'English', 'Book', '9789966254313', 2008, 6, 'Literature'),
            ('Weep Not Child', 'Ngugi wa Thiong\'o', 'English', 'Book', '9780435906863', 1964, 4, 'Literature'),
            ('Kiswahili Sanifu Form 3', 'Oxford University Press', 'Kiswahili', 'Book', '9780195730883', 2021, 6, 'Language'),
            ('Longman History Form 3', 'Longman Kenya', 'History', 'Book', '9789966451186', 2022, 5, 'Humanities'),
            ('Oxford Geography Form 3', 'Oxford Kenya', 'Geography', 'Book', '9780195476804', 2022, 5, 'Humanities'),
            ('Computer Studies Secondary', 'KICD', 'Computer Studies', 'Book', '9789966451001', 2023, 4, 'Technology'),
            ('Business Studies Form 4', 'Kenya Literature Bureau', 'Business', 'Book', '9789966100789', 2022, 4, 'Textbooks'),
            ('Oral Literature in Africa', 'Ruth Finnegan', 'English', 'Book', '9780198121497', 2012, 2, 'Reference'),
            ('Collins English Dictionary', 'Collins', 'English', 'Book', '9780008309374', 2019, 3, 'Reference'),
            ('Kenya Schools Atlas', 'Macmillan Kenya', 'Geography', 'Book', '9789966190970', 2021, 3, 'Reference'),
            ('CRE Form 3', 'Longman Kenya', 'CRE', 'Book', '9789966451230', 2022, 4, 'Textbooks'),
            ('Agriculture Form 2', 'KICD', 'Agriculture', 'Book', '9789966451056', 2021, 4, 'Textbooks'),
            ('Longman English Form 4', 'Longman Kenya', 'English', 'Book', '9789966451414', 2022, 5, 'Textbooks'),
            ('The Golden Drum', 'Various Authors', 'English', 'Book', '9789966251671', 2015, 3, 'Fiction'),
            ('KLB CRE Form 1', 'Kenya Literature Bureau', 'CRE', 'Book', '9789966100555', 2022, 4, 'Textbooks'),
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
        teachers = list(User.objects.exclude(username='admin')[:12])
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
            ('Mathematics Form 3 — Quadratic Equations', 'MTH301', 'Mathematics', 'Quadratic equations, inequalities and graphs for Form 3 students.', 12, 4.8),
            ('Biology Form 2 — Cell Biology & Genetics', 'BIO201', 'Biology', 'Cell structure, organelles, cell division and basic genetics.', 10, 4.9),
            ('Chemistry Form 3 — Organic Chemistry', 'CHE301', 'Chemistry', 'Introduction to organic compounds, hydrocarbons and reactions.', 14, 4.7),
            ('Physics Form 3 — Electromagnetism', 'PHY301', 'Physics', 'Electromagnetic induction, Faraday\'s law and applications.', 11, 4.6),
            ('English Form 4 — Essay Writing', 'ENG401', 'English', 'Advanced composition, argumentative essays and literary analysis.', 8, 4.5),
            ('Kiswahili Form 3 — Fasihi', 'KSW301', 'Kiswahili', 'Ushairi, riwaya na tamthilia — uchambuzi wa kina.', 9, 4.4),
            ('History Form 3 — Nationalism in Africa', 'HIS301', 'History', 'African nationalism, independence movements and post-colonial Africa.', 7, 4.3),
            ('Geography Form 2 — Climatology', 'GEO201', 'Geography', 'World climate zones, weather patterns and climate change.', 8, 4.5),
            ('Computer Studies Form 3 — Programming', 'COM301', 'Computer Studies', 'Introduction to Python programming, algorithms and data structures.', 10, 4.8),
            ('Business Studies Form 4 — Entrepreneurship', 'BST401', 'Business Studies', 'Business planning, financial literacy and entrepreneurial skills.', 6, 4.2),
            ('Agriculture Form 2 — Crop Production', 'AGR201', 'Agriculture', 'Soil science, crop husbandry and sustainable farming practices.', 7, 4.4),
            ('Mathematics Form 4 — Matrices & Calculus', 'MTH401', 'Mathematics', 'Matrices, transformations, differentiation and integration.', 14, 4.9),
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
                ('What does CBC stand for in Kenyan education?', 'A', 'Competency Based Curriculum', 'Competency Based Curriculum', 'Central Bank Committee', 'Class Based Content'),
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
            ('AST-001', 'Classroom Desk Set (30 units)', 'Furniture', 'Form 2 East', 2022, 45000, 0.75),
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
        all_classes = list(SchoolClass.objects.filter(is_active=True)[:4])
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
            ('Faith Wanjiru Mwangi', '23456789', '+254722002002', 'Parent', 'Parent-teacher meeting', 'Mr. Ochieng (Form 2E)'),
            ('George Omondi Otieno', '34567890', '+254723003003', 'Official', 'Ministry of Education inspection', 'Deputy Principal'),
            ('Electrician — John Doe', '45678901', '+254724004004', 'Contractor', 'Electrical fault repair in Science Block', 'Bursar'),
            ('Mary Achieng Ouma', '56789012', '+254725005005', 'Parent', 'Fee balance discussion', 'Bursar'),
            ('Peter Mwangi Kamau', '67890123', '+254726006006', 'Parent', 'Student welfare concern', 'Counsellor'),
            ('KNEC Official — Ms. Ruth', '78901234', '+254727007007', 'Official', 'KCSE registration verification', 'Principal'),
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

        # 2. Grade boundaries (KNEC A–E)
        BOUNDARIES = [
            ("A",  75, 100, "Excellent"),
            ("B",  60,  74, "Good"),
            ("C",  45,  59, "Average"),
            ("D",  30,  44, "Below Average"),
            ("E",   0,  29, "Fail"),
        ]
        for session in sessions:
            for grade, mn, mx, remarks in BOUNDARIES:
                ExamGradeBoundary.objects.get_or_create(
                    session=session, grade=grade,
                    defaults={"min_marks": mn, "max_marks": mx, "remarks": remarks},
                )

        # 3. ExamPapers for the first (Completed) session – core subjects x Form 1–4 East
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
                "Connect with employers and explore internship opportunities. Open to all alumni and current Form 4 students.",
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
                "Form 4 Parents' Consultation Day",
                date(2025, 3, 15),
                "Principal's Conference Room",
                acad_term1,
                dt_time(9, 0),
                dt_time(15, 0),
            ),
        ]

        teachers = list(User.objects.exclude(username="admin")[:10])
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
                    "first_name": guardian.name.replace("Mr./Mrs. ", ""),
                    "last_name":  student.last_name,
                    "email":      guardian.email or f"{portal_username}@stmarys.ac.ke",
                },
            )
            if user_created:
                parent_user.set_password("parent123")
                parent_user.save()

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

        self.stdout.write(
            f"    → Parent Portal: {created} new links "
            f"(total: {ParentStudentLink.objects.count()} links for "
            f"{User.objects.filter(username__startswith='parent.').count()} parent accounts)"
        )

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
