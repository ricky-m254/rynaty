"""
seed_extra_data.py
Idempotent supplementary demo data — ensures 25+ records for every module table.
Runs after the main Kenya seed to fill any gaps.
"""
import random
from datetime import date, time, timedelta, datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context


class Command(BaseCommand):
    help = "Seed supplementary demo data (25+ records per module)"

    def add_arguments(self, parser):
        parser.add_argument("--schema_name", type=str, default="demo_school")

    def handle(self, *args, **options):
        schema = options["schema_name"]
        self.stdout.write(f"[seed_extra_data] Seeding extra data in schema: {schema}")
        with schema_context(schema):
            self._seed_all()
        self.stdout.write(self.style.SUCCESS("[seed_extra_data] Done."))

    def _seed_all(self):
        self._seed_grade_levels()
        self._seed_admissions_extra()
        self._seed_alumni()
        self._seed_hostel()
        self._seed_sports()
        self._seed_cafeteria()
        self._seed_visitors()
        self._seed_ptm()
        self._seed_attendance_extras()
        self._seed_library()
        self._seed_dispensary()
        self._seed_timetable_extras()
        self._seed_clockin()
        self._seed_store()
        self._seed_assets()
        self._seed_hr_extras()

    # ─── GRADE LEVELS ────────────────────────────────────────────────────────

    def _seed_grade_levels(self):
        from school.models import GradeLevel, SchoolClass

        GRADE_LEVELS = [
            ("Grade 7",  1, "Junior Secondary — first year (CBE)"),
            ("Grade 8",  2, "Junior Secondary — second year (CBE)"),
            ("Grade 9",  3, "Junior Secondary — third year (CBE)"),
            ("Grade 10", 4, "Senior Secondary — first year (CBE)"),
        ]

        created = 0
        for name, order, desc in GRADE_LEVELS:
            gl, c = GradeLevel.objects.get_or_create(
                name=name,
                defaults={"order": order, "description": desc, "is_active": True},
            )
            if c:
                created += 1
            SchoolClass.objects.filter(name=name, grade_level__isnull=True).update(grade_level=gl)

        self.stdout.write(f"  GradeLevels: {created} created (4 total)")

    # ─── ADMISSIONS ──────────────────────────────────────────────────────────

    def _seed_admissions_extra(self):
        from school.models import AdmissionApplication, AcademicYear, Term
        from admissions.models import AdmissionApplicationProfile

        year = AcademicYear.objects.order_by("-start_date").first()
        term = Term.objects.order_by("-start_date").first()

        CANDIDATES = [
            ("Aisha",    "Wambua",    "F", date(2011, 3, 5)),
            ("Boniface", "Ochieng",   "M", date(2011, 7, 14)),
            ("Cynthia",  "Chebet",    "F", date(2011, 1, 22)),
            ("Dennis",   "Kirui",     "M", date(2011, 11, 3)),
            ("Esther",   "Mwende",    "F", date(2011, 4, 18)),
            ("Francis",  "Njuguna",   "M", date(2011, 9, 9)),
            ("Gladys",   "Adhiambo",  "F", date(2011, 6, 30)),
            ("Hesbon",   "Kamau",     "M", date(2011, 2, 12)),
            ("Irene",    "Simiyu",    "F", date(2012, 3, 21)),
            ("Joel",     "Kipsang",   "M", date(2012, 8, 7)),
            ("Kellen",   "Wanjiku",   "F", date(2012, 5, 16)),
            ("Lazarus",  "Otieno",    "M", date(2012, 12, 1)),
            ("Mercy",    "Ndegwa",    "F", date(2011, 10, 25)),
            ("Nathan",   "Mbeki",     "M", date(2011, 5, 3)),
            ("Olivia",   "Cherono",   "F", date(2012, 1, 19)),
            ("Patrick",  "Waweru",    "M", date(2012, 4, 8)),
            ("Queen",    "Akinyi",    "F", date(2011, 8, 27)),
            ("Robert",   "Mutiso",    "M", date(2011, 7, 11)),
            ("Sharon",   "Ndirangu",  "F", date(2012, 2, 14)),
            ("Timothy",  "Odhiambo",  "M", date(2012, 6, 5)),
            ("Ursulah",  "Chepkoech", "F", date(2011, 3, 30)),
            ("Victor",   "Gacheru",   "M", date(2012, 10, 17)),
            ("Winnie",   "Anyango",   "F", date(2011, 9, 22)),
            ("Xavier",   "Mwangi",    "M", date(2012, 7, 6)),
            ("Yvonne",   "Kiprop",    "F", date(2011, 11, 13)),
            ("Zacharia", "Kariuki",   "M", date(2012, 8, 2)),
            ("Beatrice", "Ogola",     "F", date(2011, 4, 4)),
            ("Collins",  "Keter",     "M", date(2012, 9, 28)),
            ("Dorothy",  "Maina",     "F", date(2011, 6, 15)),
            ("Edwin",    "Omuya",     "M", date(2012, 3, 11)),
        ]

        STATUSES = [
            "Submitted", "Submitted", "Documents Received", "Documents Received",
            "Interview Scheduled", "Interview Scheduled", "Assessed", "Admitted",
            "Admitted", "Enrolled", "Submitted", "Documents Received",
            "Interview Scheduled", "Assessed", "Admitted", "Enrolled",
            "Submitted", "Documents Received", "Assessed", "Admitted",
            "Submitted", "Interview Scheduled", "Admitted", "Enrolled",
            "Submitted", "Documents Received", "Interview Scheduled", "Assessed",
            "Admitted", "Enrolled",
        ]

        app_created = 0
        profile_created = 0
        for i, (first, last, gender, dob) in enumerate(CANDIDATES):
            app_num = f"APP2026{str(i + 1).zfill(3)}"
            app, ac = AdmissionApplication.objects.get_or_create(
                application_number=app_num,
                defaults={
                    "student_first_name": first,
                    "student_last_name": last,
                    "student_gender": gender,
                    "student_dob": dob,
                    "application_date": date(2025, 10, 1) + timedelta(days=i * 3),
                    "guardian_name": f"Parent of {first} {last}",
                    "guardian_phone": f"07{str(10000000 + i * 777777)[:8]}",
                    "guardian_email": f"parent.{last.lower()}{i}@gmail.com",
                    "status": STATUSES[i % len(STATUSES)],
                    "notes": f"Applying for Grade 7 admission, 2026 academic year.",
                },
            )
            if ac:
                app_created += 1

            _, pc = AdmissionApplicationProfile.objects.get_or_create(
                application=app,
                defaults={
                    "academic_year": year,
                    "term": term,
                    "is_shortlisted": STATUSES[i % len(STATUSES)] in ("Assessed", "Admitted", "Enrolled"),
                    "emergency_contact_name": f"Guardian of {first}",
                    "emergency_contact_phone": f"07{str(20000000 + i * 888888)[:8]}",
                    "languages": "English, Swahili",
                    "special_needs": "",
                    "medical_notes": "",
                },
            )
            if pc:
                profile_created += 1

        self.stdout.write(f"  Admissions: {app_created} applications, {profile_created} profiles created")

    # ─── ALUMNI ──────────────────────────────────────────────────────────────

    def _seed_alumni(self):
        from alumni.models import AlumniProfile, AlumniEvent, AlumniDonation

        ALUMNI_DATA = [
            ("Amina",    "Hassan",    2018, "KE001A", "amina.hassan@alumni.ac.ke",    "University of Nairobi",      "Medicine"),
            ("Brian",    "Otieno",    2018, "KE002A", "brian.otieno@alumni.ac.ke",    "Strathmore University",      "Business"),
            ("Carol",    "Kamau",     2019, "KE003A", "carol.kamau@alumni.ac.ke",     "Kenyatta University",        "Education"),
            ("Dennis",   "Waweru",    2019, "KE004A", "dennis.waweru@alumni.ac.ke",   "JKUAT",                      "Engineering"),
            ("Esther",   "Njeri",     2020, "KE005A", "esther.njeri@alumni.ac.ke",    "Maseno University",          "Nursing"),
            ("Felix",    "Mwangi",    2020, "KE006A", "felix.mwangi@alumni.ac.ke",    "Moi University",             "Agriculture"),
            ("Grace",    "Adhiambo",  2021, "KE007A", "grace.adhiambo@alumni.ac.ke",  "Kabarak University",         "Law"),
            ("Hassan",   "Mohamed",   2021, "KE008A", "hassan.mohamed@alumni.ac.ke",  "Technical University of Kenya","ICT"),
            ("Irene",    "Chepkoech", 2021, "KE009A", "irene.chepkoech@alumni.ac.ke", "Rongo University",           "Social Work"),
            ("James",    "Kipchoge",  2022, "KE010A", "james.kipchoge@alumni.ac.ke",  "Egerton University",         "Agriculture"),
            ("Kezia",    "Wangari",   2022, "KE011A", "kezia.wangari@alumni.ac.ke",   "Daystar University",         "Communications"),
            ("Laban",    "Omondi",    2022, "KE012A", "laban.omondi@alumni.ac.ke",    "Mt. Kenya University",       "Business"),
            ("Mary",     "Akinyi",    2023, "KE013A", "mary.akinyi@alumni.ac.ke",     "Zetech University",          "Hospitality"),
            ("Nathan",   "Njoroge",   2023, "KE014A", "nathan.njoroge@alumni.ac.ke",  "Multimedia University",      "Film"),
            ("Olivia",   "Chebet",    2023, "KE015A", "olivia.chebet@alumni.ac.ke",   "PAUSTI",                     "Data Science"),
            ("Patrick",  "Waiganjo",  2017, "KE016A", "patrick.waiganjo@alumni.ac.ke","Kenya Medical Training",     "Clinical Medicine"),
            ("Queen",    "Moraa",     2017, "KE017A", "queen.moraa@alumni.ac.ke",     "Kisii University",           "Education"),
            ("Robert",   "Kimani",    2016, "KE018A", "robert.kimani@alumni.ac.ke",   "Nairobi University",         "Architecture"),
            ("Salome",   "Wanjiku",   2016, "KE019A", "salome.wanjiku@alumni.ac.ke",  "Pwani University",           "Marine Biology"),
            ("Thomas",   "Kariuki",   2015, "KE020A", "thomas.kariuki@alumni.ac.ke",  "KCA University",             "Accounting"),
            ("Unity",    "Awino",     2015, "KE021A", "unity.awino@alumni.ac.ke",     "Machakos University",        "Education"),
            ("Victor",   "Mugo",      2014, "KE022A", "victor.mugo@alumni.ac.ke",     "University of Eldoret",      "Engineering"),
            ("Winnie",   "Ndirangu",  2014, "KE023A", "winnie.ndirangu@alumni.ac.ke", "Laikipia University",        "Agriculture"),
            ("Xavier",   "Simiyu",    2013, "KE024A", "xavier.simiyu@alumni.ac.ke",   "South Eastern Kenya Univ",   "Education"),
            ("Yvonne",   "Nyambura",  2013, "KE025A", "yvonne.nyambura@alumni.ac.ke", "Chuka University",           "Business"),
            ("Zachary",  "Mwenda",    2012, "KE026A", "zachary.mwenda@alumni.ac.ke",  "Kirinyaga University",       "Horticulture"),
            ("Abigail",  "Rotich",    2012, "KE027A", "abigail.rotich@alumni.ac.ke",  "Masinde Muliro University",  "Health Sciences"),
            ("Benedict", "Ochieng",   2011, "KE028A", "benedict.ochieng@alumni.ac.ke","Jaramogi Oginga Odinga Univ","Commerce"),
            ("Cynthia",  "Mutua",     2011, "KE029A", "cynthia.mutua@alumni.ac.ke",   "Koitalel Samoei University", "Agriculture"),
            ("David",    "Njenga",    2010, "KE030A", "david.njenga@alumni.ac.ke",    "Kenya Defence Force Univ",   "Security"),
        ]

        created = 0
        for first, last, yr, adm, email, institution, field in ALUMNI_DATA:
            profile, c = AlumniProfile.objects.get_or_create(
                admission_number=adm,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "graduation_year": yr,
                    "email": email,
                    "current_institution": institution,
                    "phone": f"+2547{random.randint(10000000, 99999999)}",
                },
            )
            if c:
                created += 1

        # Alumni Events
        events_data = [
            "Annual Alumni Gala 2024", "Mentorship Day 2024", "Homecoming 2023",
            "Career Fair 2024", "Alumni Sports Day 2024", "Charity Walk 2024",
            "Annual General Meeting 2024", "Class of 2020 Reunion", "Alumni Scholarship Launch",
            "Business Networking Evening", "Alumni vs Students Match", "Academic Panel 2024",
            "Alumni Fundraiser Dinner", "Campus Open Day 2024", "Alumni Award Ceremony 2024",
            "Class of 2018 Reunion", "Alumni Art Exhibition", "Annual Lecture Series",
            "Alumni Tech Talk 2024", "Alumni Wellness Day", "Service Day 2024",
            "Alumni Leadership Forum", "Graduation Celebration 2024", "Music Concert 2024",
            "Alumni Investment Club Meet 2024",
        ]
        ev_created = 0
        for i, ev_title in enumerate(events_data):
            ev_date = date.today() - timedelta(days=i * 12)
            ev, ec = AlumniEvent.objects.get_or_create(
                title=ev_title,
                defaults={
                    "event_date": ev_date,
                    "location": "School Main Hall",
                    "description": ev_title,
                },
            )
            if ec:
                ev_created += 1

        # Donations
        don_created = 0
        profiles = list(AlumniProfile.objects.all()[:25])
        for idx, prof in enumerate(profiles):
            amounts = [5000, 10000, 2500, 15000, 7500, 3000, 20000, 8000, 12000, 6000]
            amount = amounts[idx % len(amounts)]
            _, dc = AlumniDonation.objects.get_or_create(
                alumni=prof,
                defaults={
                    "amount": Decimal(str(amount)),
                    "campaign_name": "Library Fund" if idx % 2 == 0 else "Scholarship Fund",
                    "donation_date": date.today() - timedelta(days=idx * 7),
                    "payment_method": "mobile_money",
                    "status": "received",
                },
            )
            if dc:
                don_created += 1

        self.stdout.write(f"  Alumni: {created} profiles, {ev_created} events, {don_created} donations")

    # ─── HOSTEL ──────────────────────────────────────────────────────────────

    def _seed_hostel(self):
        from hostel.models import Dormitory, BedSpace, HostelAllocation
        from school.models import Student
        from academics.models import AcademicYear, Term

        DORMS = [
            ("Eagles Dormitory",   "Male",   60),
            ("Lions Dormitory",    "Male",   60),
            ("Doves Dormitory",    "Female", 60),
            ("Roses Dormitory",    "Female", 60),
            ("Cedars Dormitory",   "Mixed",  40),
        ]

        dorm_created = 0
        for name, gender, cap in DORMS:
            dorm, c = Dormitory.objects.get_or_create(
                name=name,
                defaults={"gender": gender, "capacity": cap},
            )
            if c:
                dorm_created += 1
                for bed_num in range(1, min(cap + 1, 21)):
                    BedSpace.objects.get_or_create(
                        dormitory=dorm,
                        bed_number=str(bed_num),
                        defaults={"is_occupied": False, "is_active": True},
                    )

        # Allocate some students to beds
        students = list(Student.objects.all()[:20])
        beds = list(BedSpace.objects.filter(is_occupied=False)[:20])
        year = AcademicYear.objects.order_by("-start_date").first()
        term = Term.objects.filter(academic_year=year).first() if year else None

        alloc_created = 0
        for i, (student, bed) in enumerate(zip(students, beds)):
            _, ac = HostelAllocation.objects.get_or_create(
                student=student,
                bed=bed,
                defaults={
                    "term": term,
                    "check_in_date": date.today() - timedelta(days=60),
                    "status": "Active",
                },
            )
            if ac:
                alloc_created += 1

        self.stdout.write(f"  Hostel: {dorm_created} dorms, {alloc_created} allocations")

    # ─── SPORTS & CLUBS ──────────────────────────────────────────────────────

    def _seed_sports(self):
        from sports.models import Club, ClubMembership, Tournament, StudentAward
        from school.models import Student

        CLUBS = [
            ("Football Club",         "Sports",   "Weekly training on Tuesdays and Thursdays"),
            ("Basketball Club",       "Sports",   "Practice every Monday and Wednesday"),
            ("Athletics Club",        "Sports",   "Morning training sessions"),
            ("Volleyball Club",       "Sports",   "Afternoon sessions three times a week"),
            ("Swimming Club",         "Sports",   "Swimming pool practice sessions"),
            ("Science Club",          "Academic", "Experiments and science fairs"),
            ("Debate Club",           "Academic", "Weekly debates and public speaking"),
            ("Math Olympiad Club",    "Academic", "Competitions and problem solving"),
            ("Drama Club",            "Arts",     "Rehearsals for school plays and events"),
            ("Music Choir",           "Arts",     "Choir practice and performances"),
            ("Art Club",              "Arts",     "Visual arts and creative projects"),
            ("Environmental Club",    "Community","Tree planting and conservation"),
            ("Red Cross Club",        "Community","First aid and community service"),
            ("Business Club",         "Academic", "Entrepreneurship and business skills"),
            ("ICT Club",              "Academic", "Programming and computer skills"),
            ("Journalism Club",       "Arts",     "School newsletter and media"),
            ("Chess Club",            "Academic", "Strategy and tournament play"),
            ("Badminton Club",        "Sports",   "Court training and tournaments"),
            ("Rugby Club",            "Sports",   "Full contact rugby training"),
            ("Netball Club",          "Sports",   "Tactical play and fitness"),
            ("Scouts",                "Community","Leadership and outdoor skills"),
            ("Junior Achievement",    "Academic", "Youth entrepreneurship program"),
            ("Wildlife Club",         "Community","Nature walks and conservation"),
            ("Table Tennis Club",     "Sports",   "Table tennis drills and tournaments"),
            ("Karate Club",           "Sports",   "Discipline and self-defense"),
            ("Rotaract Club",         "Community","Service above self"),
            ("Young Farmers Club",    "Community","Agriculture and food security"),
            ("Photography Club",      "Arts",     "Digital photography and editing"),
        ]

        club_created = 0
        for name, ctype, desc in CLUBS:
            _, c = Club.objects.get_or_create(
                name=name,
                defaults={"club_type": ctype, "description": desc, "is_active": True},
            )
            if c:
                club_created += 1

        # Add memberships
        students = list(Student.objects.all())
        clubs = list(Club.objects.all())
        mem_created = 0
        roles = ["Member", "Member", "Member", "Captain", "Vice Captain", "Secretary"]
        for i, student in enumerate(students):
            club = clubs[i % len(clubs)]
            role = roles[i % len(roles)]
            _, mc = ClubMembership.objects.get_or_create(
                club=club,
                student=student,
                defaults={"role": role, "is_active": True},
            )
            if mc:
                mem_created += 1

        # Tournaments
        TOURNAMENTS = [
            ("Inter-Schools Football 2024", "Football",    "2024-03-15"),
            ("Athletics Day 2024",          "Athletics",   "2024-04-20"),
            ("Basketball League 2024",      "Basketball",  "2024-05-10"),
            ("Science Fair 2024",           "Science",     "2024-06-08"),
            ("Debate Championship 2024",    "Debate",      "2024-07-12"),
            ("Drama Festival 2024",         "Drama",       "2024-08-03"),
            ("Chess Tournament 2024",       "Chess",       "2024-09-14"),
            ("Swimming Gala 2024",          "Swimming",    "2024-10-05"),
            ("Volleyball Tourney 2024",     "Volleyball",  "2024-11-02"),
            ("End-Year Sports Meet 2024",   "Mixed",       "2024-11-30"),
            ("Rugby 7s 2024",               "Rugby",       "2024-03-22"),
            ("Netball Cup 2024",            "Netball",     "2024-04-28"),
            ("Table Tennis Open 2024",      "Table Tennis","2024-05-17"),
            ("Badminton Tourney 2024",      "Badminton",   "2024-06-21"),
            ("Math Olympiad 2024",          "Mathematics", "2024-07-19"),
            ("Journalism Award 2024",       "Journalism",  "2024-08-16"),
            ("Photography Contest 2024",    "Photography", "2024-09-06"),
            ("Karate Grading 2024",         "Karate",      "2024-10-12"),
            ("Young Farmers Show 2024",     "Agriculture", "2024-11-08"),
            ("Inter-School Scouts 2024",    "Scouting",    "2024-11-22"),
            ("ICT Hackathon 2024",          "Technology",  "2024-06-14"),
            ("Environmental Day 2024",      "Environment", "2024-06-05"),
            ("Red Cross First Aid 2024",    "First Aid",   "2024-07-07"),
            ("Business Plan Comp 2024",     "Business",    "2024-08-24"),
            ("Choir Festival 2024",         "Music",       "2024-12-07"),
        ]

        tour_created = 0
        clubs_list = list(Club.objects.all())
        for i, (name, sport, dt_str) in enumerate(TOURNAMENTS):
            dt = date.fromisoformat(dt_str)
            club_obj = clubs_list[i % len(clubs_list)] if clubs_list else None
            _, tc = Tournament.objects.get_or_create(
                name=name,
                defaults={
                    "club": club_obj,
                    "start_date": dt,
                    "end_date": dt + timedelta(days=1),
                    "location": "School Grounds",
                    "result": "1st Place",
                    "position_achieved": "1st",
                    "notes": f"Participated in {name}",
                },
            )
            if tc:
                tour_created += 1

        # Student Awards
        award_created = 0
        award_names = [
            "Best Athlete", "Most Improved Player", "Best Team Player",
            "Academic Excellence", "Best Debater", "Drama Star Award",
            "Science Star", "Leadership Award", "Sportsmanship Award",
            "Community Service Award", "Music Excellence", "Art Prize",
            "Photography Award", "Chess Champion", "Swimming Champion",
        ]
        for i, student in enumerate(students[:25]):
            award_name = award_names[i % len(award_names)]
            _, ac = StudentAward.objects.get_or_create(
                student=student,
                award_name=award_name,
                defaults={
                    "category": "Sports" if "Athlete" in award_name or "Player" in award_name else "Academic",
                    "award_date": date.today() - timedelta(days=i * 5),
                    "description": f"Awarded for outstanding performance in {award_name}",
                    "awarded_by": "School Administration",
                },
            )
            if ac:
                award_created += 1

        self.stdout.write(f"  Sports: {club_created} clubs, {mem_created} memberships, {tour_created} tournaments, {award_created} awards")

    # ─── CAFETERIA ───────────────────────────────────────────────────────────

    def _seed_cafeteria(self):
        from cafeteria.models import MealPlan, WeeklyMenu, StudentMealEnrollment, MealTransaction
        from school.models import Student

        PLANS = [
            ("Full Board",    "Breakfast, Lunch, Supper",  Decimal("350")),
            ("Half Board",    "Breakfast and Lunch",        Decimal("250")),
            ("Lunch Only",    "Lunch Only",                 Decimal("150")),
            ("Day Scholar",   "Lunch for day students",     Decimal("120")),
            ("Special Diet",  "Medically approved diet",    Decimal("400")),
        ]

        plan_created = 0
        plans = []
        for name, desc, price in PLANS:
            plan, c = MealPlan.objects.get_or_create(
                name=name,
                defaults={"description": desc, "price_per_day": price, "is_active": True},
            )
            plans.append(plan)
            if c:
                plan_created += 1

        # Weekly Menus — WeeklyMenu has week_start + per-day-per-meal fields
        menu_created = 0
        today = date.today()
        for week_offset in range(8):
            # Find the Monday of that week
            wk_start = today - timedelta(days=today.weekday(), weeks=week_offset + 1)
            for plan in plans:
                _, mc = WeeklyMenu.objects.get_or_create(
                    week_start=wk_start,
                    meal_plan=plan,
                    defaults={
                        "monday_breakfast": "Uji + Bread + Egg",
                        "monday_lunch": "Rice + Beans + Kachumbari",
                        "monday_supper": "Ugali + Beef Stew + Greens",
                        "tuesday_breakfast": "Porridge + Mandazi",
                        "tuesday_lunch": "Chapati + Lentils + Salad",
                        "tuesday_supper": "Ugali + Sukuma Wiki + Fish",
                        "wednesday_breakfast": "Uji + Bread",
                        "wednesday_lunch": "Rice + Chicken + Coleslaw",
                        "wednesday_supper": "Ugali + Githeri + Avocado",
                        "thursday_breakfast": "Porridge + Egg",
                        "thursday_lunch": "Ugali + Green Grams + Cabbage",
                        "thursday_supper": "Rice + Beef + Spinach",
                        "friday_breakfast": "Uji + Banana",
                        "friday_lunch": "Pilau + Kachumbari + Raita",
                        "friday_supper": "Ugali + Beans + Greens",
                    },
                )
                if mc:
                    menu_created += 1

        # Enroll students
        students = list(Student.objects.all())
        enroll_created = 0
        for i, student in enumerate(students):
            plan = plans[i % len(plans)]
            _, ec = StudentMealEnrollment.objects.get_or_create(
                student=student,
                meal_plan=plan,
                defaults={"is_active": True},
            )
            if ec:
                enroll_created += 1

        # Meal Transactions
        tx_created = 0
        for i, student in enumerate(students[:25]):
            for days_ago in range(1, 6):
                for meal_type in ["Breakfast", "Lunch", "Supper"]:
                    _, txc = MealTransaction.objects.get_or_create(
                        student=student,
                        date=today - timedelta(days=days_ago),
                        meal_type=meal_type,
                        defaults={"served": True},
                    )
                    if txc:
                        tx_created += 1

        self.stdout.write(f"  Cafeteria: {plan_created} plans, {menu_created} menus, {enroll_created} enrolments, {tx_created} transactions")

    # ─── VISITOR MANAGEMENT ──────────────────────────────────────────────────

    def _seed_visitors(self):
        from visitor_mgmt.models import Visitor

        VISITORS = [
            ("James Mutua",       "23456789", "+254701234567", "Parent",      "Collect my child after early dismissal",   "Admin Office"),
            ("Mercy Njeri",       "34567890", "+254712345678", "Parent",      "Parent-Teacher meeting",                   "Class 7B"),
            ("John Ochieng",      "45678901", "+254723456789", "Contractor",  "Electrical repairs in lab",                "Science Lab"),
            ("Grace Wanjiku",     "56789012", "+254734567890", "Official",    "Ministry of Education inspection",         "Principal Office"),
            ("Peter Kamau",       "67890123", "+254745678901", "Parent",      "Admissions inquiry for next year",         "Registrar"),
            ("Samuel Otieno",     "78901234", "+254756789012", "Official",    "BOM meeting attendance",                   "Boardroom"),
            ("Alice Ndirangu",    "89012345", "+254767890123", "Parent",      "Fee payment and progress query",           "Finance Office"),
            ("David Mwenda",      "90123456", "+254778901234", "Contractor",  "Plumbing works in Girls hostel",           "Hostel Block B"),
            ("Rose Akinyi",       "01234567", "+254789012345", "Parent",      "Collect sick child from dispensary",       "Dispensary"),
            ("Collins Waweru",    "12345678", "+254790123456", "Official",    "Red Cross activity supervision",           "Sports Ground"),
            ("Esther Chepkoech",  "23456780", "+254701234560", "Parent",      "Pick up child for dental appointment",     "Class 8A"),
            ("Felix Njoroge",     "34567891", "+254712345670", "Contractor",  "CCTV camera installation",                 "Security Office"),
            ("Hannah Moraa",      "45678902", "+254723456780", "Parent",      "Submit medical documents",                 "Dispensary"),
            ("Isaac Kariuki",     "56789013", "+254734567891", "Official",    "Water board inspection",                   "Kitchen"),
            ("Janet Adhiambo",    "67890124", "+254745678902", "Parent",      "Collect extra uniform from tuck shop",     "Tuck Shop"),
            ("Kevin Simiyu",      "78901235", "+254756789013", "Contractor",  "Generator servicing",                      "Genset Room"),
            ("Lucy Awino",        "89012346", "+254767890124", "Parent",      "Pick up for family event",                 "Class 6A"),
            ("Michael Njenga",    "90123457", "+254778901235", "Official",    "Drama festival coordination",              "Assembly Hall"),
            ("Naomi Mutua",       "01234568", "+254789012346", "Parent",      "Enrollment documents collection",          "Registrar"),
            ("Oscar Omondi",      "12345679", "+254790123457", "Contractor",  "Library shelving installation",            "Library"),
            ("Pauline Wangari",   "23456781", "+254701234561", "Parent",      "Discuss child's behavior concern",         "Counsellor"),
            ("Quentin Kimani",    "34567892", "+254712345671", "Official",    "Curriculum support visit",                 "Principal Office"),
            ("Rachel Njeri",      "45678903", "+254723456781", "Parent",      "Collect medicine for boarder child",       "Dispensary"),
            ("Steven Mwangi",     "56789014", "+254734567892", "Contractor",  "Painting of classrooms",                   "Block C"),
            ("Tabitha Wanjiku",   "67890125", "+254745678903", "Parent",      "Collect school fee receipts",              "Finance Office"),
            ("Umar Farouk",       "78901236", "+254756789014", "Official",    "Fire safety audit",                        "All Buildings"),
            ("Violet Chebet",     "89012347", "+254767890125", "Parent",      "Submit birth certificate copy",            "Registrar"),
            ("Walter Mugo",       "90123458", "+254778901236", "Contractor",  "Air conditioning repair — staffroom",      "Staffroom"),
            ("Xena Rotich",       "01234569", "+254789012347", "Parent",      "Discuss scholarship eligibility",          "Principal Office"),
            ("Yasmin Ali",        "12345680", "+254790123458", "Official",    "CRE inspection and board review",          "Boardroom"),
        ]

        vis_created = 0
        for i, (name, id_num, phone, vtype, purpose, host) in enumerate(VISITORS):
            _, vc = Visitor.objects.get_or_create(
                id_number=id_num,
                defaults={
                    "full_name": name,
                    "phone": phone,
                    "visitor_type": vtype,
                    "purpose": purpose,
                    "host_name": host,
                    "badge_number": f"VB{i+1:03d}",
                },
            )
            if vc:
                vis_created += 1

        self.stdout.write(f"  Visitors: {vis_created} visitor records")

    # ─── PTM SESSIONS ────────────────────────────────────────────────────────

    def _seed_ptm(self):
        from ptm.models import PTMSession, PTMSlot, PTMBooking
        from academics.models import Term
        from django.contrib.auth import get_user_model

        User = get_user_model()
        teachers = list(User.objects.filter(userprofile__role__name="TEACHER")[:8])
        if not teachers:
            self.stdout.write("  PTM: no teachers found, skipping")
            return

        term = Term.objects.order_by("-start_date").first()

        SESSIONS = [
            ("Term 1 Parent-Teacher Meeting", date(2024, 3, 23), "Main Hall", "08:00", "16:00"),
            ("Term 2 Parent-Teacher Meeting", date(2024, 7, 13), "Main Hall", "08:00", "16:00"),
            ("Term 3 Parent-Teacher Meeting", date(2024, 10, 5), "School Library", "08:00", "15:00"),
            ("Mid-Term Progress Review",       date(2024, 5, 11), "Staffroom",    "09:00", "14:00"),
            ("Grade 8 Transition Counselling", date(2024, 8, 17), "Boardroom",   "10:00", "15:00"),
        ]

        sess_created = 0
        slot_created = 0
        for title, dt, venue, start, end in SESSIONS:
            session, sc = PTMSession.objects.get_or_create(
                title=title,
                defaults={
                    "date": dt,
                    "venue": venue,
                    "start_time": time.fromisoformat(start),
                    "end_time": time.fromisoformat(end),
                    "slot_duration_minutes": 15,
                    "term": term,
                    "is_virtual": False,
                },
            )
            if sc:
                sess_created += 1
            # Create slots for each teacher
            for teacher in teachers:
                for slot_num in range(8):
                    total_minutes = 8 * 60 + slot_num * 15
                    slot_time = time(total_minutes // 60, total_minutes % 60)
                    _, stc = PTMSlot.objects.get_or_create(
                        session=session,
                        teacher=teacher,
                        slot_time=slot_time,
                        defaults={"is_booked": slot_num < 4},
                    )
                    if stc:
                        slot_created += 1

        self.stdout.write(f"  PTM: {sess_created} sessions, {slot_created} slots")

    # ─── ATTENDANCE EXTRAS ────────────────────────────────────────────────────

    def _seed_attendance_extras(self):
        from school.models import AttendanceRecord, Student
        from academics.models import AcademicYear, Term

        year = AcademicYear.objects.order_by("-start_date").first()
        term = Term.objects.filter(academic_year=year).order_by("-start_date").first() if year else None

        students = list(Student.objects.all()[:40])
        today = date.today()
        statuses = ["Present", "Present", "Present", "Present", "Absent", "Late", "Present", "Present"]

        created = 0
        for student in students:
            for days_ago in range(1, 30):
                att_date = today - timedelta(days=days_ago)
                if att_date.weekday() >= 5:
                    continue
                status = statuses[days_ago % len(statuses)]
                _, c = AttendanceRecord.objects.get_or_create(
                    student=student,
                    date=att_date,
                    defaults={
                        "status": status,
                        "notes": "Late arrival" if status == "Late" else "",
                    },
                )
                if c:
                    created += 1

        self.stdout.write(f"  Attendance: {created} extra records")

    # ─── LIBRARY ─────────────────────────────────────────────────────────────

    def _seed_library(self):
        from library.models import LibraryResource, LibraryCategory, ResourceCopy

        CATEGORIES = [
            ("Textbooks",       "Primary and secondary school textbooks"),
            ("Literature",      "Novels, short stories, and poetry"),
            ("Reference",       "Dictionaries, encyclopedias, atlases"),
            ("Science",         "Science and technology resources"),
            ("Social Sciences", "History, geography, social studies"),
            ("Languages",       "English, Kiswahili, French, Arabic resources"),
            ("Arts & Music",    "Fine art and music resources"),
            ("Religious",       "CRE, IRE and related texts"),
        ]
        cat_created = 0
        cats = {}
        for name, desc in CATEGORIES:
            cat, c = LibraryCategory.objects.get_or_create(
                name=name, defaults={"description": desc}
            )
            cats[name] = cat
            if c:
                cat_created += 1

        default_cat = cats.get("Textbooks") or LibraryCategory.objects.first()

        BOOKS = [
            ("English Grammar in Use",         "Raymond Murphy",      "978-0-521-18906-4", "Textbooks",       2019),
            ("Mathematics Standard 8",         "KIE",                 "978-9966-25-001-1", "Textbooks",       2021),
            ("Science Grade 7",                "KIE",                 "978-9966-25-002-8", "Science",         2021),
            ("Social Studies Grade 6",         "KIE",                 "978-9966-25-003-5", "Social Sciences", 2021),
            ("Kiswahili Darasa la 8",          "KIE",                 "978-9966-25-004-2", "Languages",       2021),
            ("Weep Not Child",                 "Ngugi wa Thiong'o",   "978-0-435-90054-6", "Literature",      1964),
            ("The River and the Source",       "Margaret Ogola",      "978-9966-46-961-7", "Literature",      1994),
            ("Blossoms of the Savannah",       "Henry ole Kulet",     "978-9966-25-042-4", "Literature",      2008),
            ("A Grain of Wheat",               "Ngugi wa Thiong'o",   "978-0-435-90210-6", "Literature",      1967),
            ("Junior Secondary Mathematics 1", "Oxford University Press","978-0-19-089710-0","Textbooks",     2023),
            ("Chemistry Grade 7",              "KIE",                 "978-9966-25-010-3", "Science",         2020),
            ("Biology Grade 8",                "KIE",                 "978-9966-25-011-0", "Science",         2020),
            ("Physics Grade 9",                "KIE",                 "978-9966-25-012-7", "Science",         2020),
            ("History & Government Grade 7",   "KIE",                 "978-9966-25-013-4", "Social Sciences", 2020),
            ("Geography Grade 8",              "KIE",                 "978-9966-25-014-1", "Social Sciences", 2020),
            ("CRE Grade 7",                    "KIE",                 "978-9966-25-015-8", "Religious",       2020),
            ("Business Studies Grade 8",       "KIE",                 "978-9966-25-016-5", "Textbooks",       2020),
            ("Computer Studies Grade 7",       "KIE",                 "978-9966-25-017-2", "Science",         2020),
            ("Agriculture Grade 9",            "KIE",                 "978-9966-25-018-9", "Science",         2020),
            ("Home Science Grade 8",           "KIE",                 "978-9966-25-019-6", "Textbooks",       2020),
            ("Longman Dictionary",             "Longman",             "978-1-4082-0299-2", "Reference",       2009),
            ("Oxford English Dictionary",      "Oxford",              "978-0-19-860391-4", "Reference",       2010),
            ("Atlas of Kenya",                 "Survey of Kenya",     "978-9966-25-050-9", "Social Sciences", 2018),
            ("Mastering Mathematics",          "Macmillan",           "978-0-333-68048-6", "Textbooks",       2015),
            ("Junior Secondary Science",       "Oxford",              "978-0-19-089711-7", "Science",         2023),
            ("Kenya Constitution 2010",        "Government of Kenya", "978-9966-25-060-8", "Social Sciences", 2010),
            ("French for Beginners",           "Hachette",            "978-2-01-155336-1", "Languages",       2018),
            ("Arabic Level 1",                 "Al-Kitaab",           "978-1-58901-096-0", "Languages",       2012),
            ("Music Theory Grade 1",           "ABRSM",               "978-1-86096-273-6", "Arts & Music",    2018),
            ("Art Fundamentals",               "KIE",                 "978-9966-25-070-7", "Arts & Music",    2021),
        ]

        res_created = 0
        copy_created = 0
        for title, author, isbn, cat_name, pub_year in BOOKS:
            cat = cats.get(cat_name, default_cat)
            resource, rc = LibraryResource.objects.get_or_create(
                isbn=isbn,
                defaults={
                    "title": title,
                    "authors": author,
                    "resource_type": "Book",
                    "publisher": author if author in ("KIE", "Oxford", "Longman", "Macmillan") else "Publisher",
                    "publication_year": pub_year,
                    "subjects": cat_name,
                },
            )
            if rc:
                res_created += 1
                # Create 5 copies per resource using accession_number as unique key
                for copy_num in range(1, 6):
                    acc_num = f"ACC-{isbn.replace('-','')[-6:]}-{copy_num:02d}"
                    ResourceCopy.objects.get_or_create(
                        accession_number=acc_num,
                        defaults={
                            "resource": resource,
                            "condition": "Good",
                            "status": "Available",
                            "location": "Main Shelf",
                        },
                    )
                    copy_created += 1

        self.stdout.write(f"  Library: {cat_created} categories, {res_created} resources, {copy_created} copies")

    # ─── DISPENSARY ── (no standalone dispensary app — maintenance used instead)

    def _seed_dispensary(self):
        from maintenance.models import MaintenanceRequest, MaintenanceCategory
        from django.contrib.auth import get_user_model
        User = get_user_model()

        reporter = User.objects.filter(is_staff=True).first()

        MAINT_CATEGORIES = [
            "Carpentry", "Plumbing", "Electrical", "Roofing", "Mechanical",
            "Metalwork", "Masonry", "Painting", "Locksmith", "ICT",
            "General", "Cleaning",
        ]
        maint_cats = {}
        for cname in MAINT_CATEGORIES:
            mc, _ = MaintenanceCategory.objects.get_or_create(
                name=cname, defaults={"is_active": True}
            )
            maint_cats[cname] = mc

        REQUESTS = [
            ("Broken window in Class 7A",         "Carpentry",   "Pending"),
            ("Leaking tap - Boys Toilets",         "Plumbing",    "In Progress"),
            ("Projector bulb replacement - Lab",   "Electrical",  "Completed"),
            ("Faulty socket in Staffroom",         "Electrical",  "Pending"),
            ("Roof leak - Block B",                "Roofing",     "In Progress"),
            ("Blocked drain - Kitchen area",       "Plumbing",    "Completed"),
            ("Broken desks in Class 8B (5 desks)", "Carpentry",   "Pending"),
            ("Generator fuel top-up needed",       "Mechanical",  "Completed"),
            ("Library shelving loose screws",      "Carpentry",   "Pending"),
            ("CCTV camera offline - Gate",         "Electrical",  "In Progress"),
            ("Broken gate latch - main gate",      "Metalwork",   "Pending"),
            ("Cracked tiles - Admin corridor",     "Masonry",     "Pending"),
            ("Water pump failure",                 "Mechanical",  "In Progress"),
            ("Ceiling fan wobble - Class 6A",      "Electrical",  "Pending"),
            ("Paint peeling - Hostel Block A",     "Painting",    "Pending"),
            ("Broken chairs - Hall (3 chairs)",    "Carpentry",   "Completed"),
            ("Jammed lock - Science Lab",          "Locksmith",   "In Progress"),
            ("Burst pipe - Under field",           "Plumbing",    "Completed"),
            ("Gutter cleaning needed - Block C",   "General",     "Pending"),
            ("Network switch reset - ICT Lab",     "ICT",         "Completed"),
            ("Broken whiteboard - Class 8A",       "Carpentry",   "Pending"),
            ("Air conditioning not cooling - Principal's office","Electrical","In Progress"),
            ("Septic tank overflow",               "Plumbing",    "Pending"),
            ("Rusted gate hinge",                  "Metalwork",   "Completed"),
            ("Broken padlock - Storeroom",         "Locksmith",   "Pending"),
            ("Sewer smell - Girls dormitory",      "Plumbing",    "In Progress"),
            ("Light bulb replacement - Corridors (10 bulbs)","Electrical","Completed"),
            ("Cracked water tank",                 "Plumbing",    "Pending"),
            ("Broken net posts - Volleyball court","Metalwork",   "Pending"),
            ("Water heater fault - Hostel B",      "Electrical",  "In Progress"),
        ]

        from django.contrib.auth import get_user_model
        User = get_user_model()
        reporter = User.objects.filter(is_staff=True).first() or User.objects.filter(username="admin").first() or User.objects.first()

        created = 0
        for title, category_name, status in REQUESTS:
            try:
                cat_obj = maint_cats.get(category_name)
                _, c = MaintenanceRequest.objects.get_or_create(
                    title=title,
                    defaults={
                        "category": cat_obj,
                        "status": status,
                        "priority": "Medium",
                        "description": f"Maintenance required: {title}",
                        "reported_by": reporter,
                    },
                )
                if c:
                    created += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"    MaintenanceRequest '{title}' failed: {e}"))

        self.stdout.write(f"  Maintenance: {created} requests")

    # ─── TIMETABLE ────────────────────────────────────────────────────────────

    def _seed_timetable_extras(self):
        from timetable.models import TimetableSlot
        from school.models import SchoolClass, Subject
        from django.contrib.auth import get_user_model
        User = get_user_model()

        existing = TimetableSlot.objects.count()
        if existing >= 25:
            self.stdout.write(f"  Timetable: {existing} slots already exist")
            return

        teachers = list(User.objects.filter(userprofile__role__name="TEACHER")[:8])
        classes = list(SchoolClass.objects.all()[:5])
        subjects = list(Subject.objects.all()[:8])

        if not (teachers and classes and subjects):
            self.stdout.write(f"  Timetable: insufficient data (teachers={len(teachers)}, classes={len(classes)}, subjects={len(subjects)}), skipping")
            return

        created = 0
        PERIOD_TIMES = [
            (1, time(7, 30),  time(8, 15)),
            (2, time(8, 15),  time(9, 0)),
            (3, time(9, 0),   time(9, 45)),
            (4, time(10, 5),  time(10, 50)),
            (5, time(10, 50), time(11, 35)),
            (6, time(11, 35), time(12, 20)),
            (7, time(13, 0),  time(13, 45)),
            (8, time(13, 45), time(14, 30)),
        ]

        for day in range(1, 6):
            for period_num, start_t, end_t in PERIOD_TIMES:
                for class_obj in classes[:3]:
                    teacher = teachers[(day + period_num) % len(teachers)]
                    subject = subjects[(day + period_num) % len(subjects)]
                    _, c = TimetableSlot.objects.get_or_create(
                        day_of_week=day,
                        period_number=period_num,
                        school_class=class_obj,
                        defaults={
                            "start_time": start_t,
                            "end_time": end_t,
                            "teacher": teacher,
                            "subject": subject,
                            "room": f"Room {day}{period_num}",
                            "is_active": True,
                        },
                    )
                    if c:
                        created += 1

        self.stdout.write(f"  Timetable: {created} slots created (total: {TimetableSlot.objects.count()})")

    # ─── CLOCKIN ─────────────────────────────────────────────────────────────

    def _seed_clockin(self):
        from clockin.models import PersonRegistry, SchoolShift
        from school.models import Student
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Create a school shift
        shift, _ = SchoolShift.objects.get_or_create(
            name="Regular School Day",
            defaults={
                "person_type": "ALL",
                "expected_arrival": time(7, 0),
                "grace_period_minutes": 30,
                "expected_departure": time(17, 0),
            },
        )

        students = list(Student.objects.all()[:30])
        teachers = list(User.objects.filter(userprofile__role__name="TEACHER")[:12])

        created = 0
        for student in students:
            _, c = PersonRegistry.objects.get_or_create(
                fingerprint_id=f"STU-{student.admission_number}",
                defaults={
                    "person_type": "STUDENT",
                    "student": student,
                    "display_name": f"{student.first_name} {student.last_name}",
                    "is_active": True,
                },
            )
            if c:
                created += 1

        for teacher in teachers:
            _, c = PersonRegistry.objects.get_or_create(
                fingerprint_id=f"TCH-{teacher.username}",
                defaults={
                    "person_type": "TEACHER",
                    "display_name": teacher.get_full_name() or teacher.username,
                    "is_active": True,
                },
            )
            if c:
                created += 1

        self.stdout.write(f"  Clockin: {created} person registrations (1 shift)")

    # ─── STORE / INVENTORY ── (no store app; handled via maintenance storeroom)

    def _seed_store(self):
        self.stdout.write("  Store: no standalone store app — skipping")

    # ─── ASSETS ──────────────────────────────────────────────────────────────

    def _seed_assets(self):
        from assets.models import Asset, AssetCategory

        CATEGORIES = [
            ("ICT Equipment",       "Computers, servers, networking equipment"),
            ("AV Equipment",        "Projectors, PA systems, microphones"),
            ("Vehicles",            "School buses, vans, and motorcycles"),
            ("Office Equipment",    "Printers, photocopiers, furniture"),
            ("Lab Equipment",       "Scientific instruments and lab tools"),
            ("Sports Equipment",    "Sports gear and outdoor equipment"),
            ("Kitchen Equipment",   "Cafeteria cooking and storage equipment"),
            ("Security Equipment",  "CCTV, electric fence, access control"),
            ("Medical Equipment",   "Dispensary and first aid equipment"),
            ("Utilities",           "Generators, water tanks, solar panels"),
        ]

        cats = {}
        for name, desc in CATEGORIES:
            cat, _ = AssetCategory.objects.get_or_create(
                name=name, defaults={"description": desc}
            )
            cats[name] = cat

        ASSETS = [
            ("Desktop Computer - Lab A01",   "ICT Equipment",     "SER-C-001", Decimal("85000"),   "ICT Lab A"),
            ("Desktop Computer - Lab A02",   "ICT Equipment",     "SER-C-002", Decimal("85000"),   "ICT Lab A"),
            ("Desktop Computer - Lab A03",   "ICT Equipment",     "SER-C-003", Decimal("85000"),   "ICT Lab A"),
            ("Desktop Computer - Lab A04",   "ICT Equipment",     "SER-C-004", Decimal("85000"),   "ICT Lab A"),
            ("Desktop Computer - Lab A05",   "ICT Equipment",     "SER-C-005", Decimal("85000"),   "ICT Lab A"),
            ("Projector - Boardroom",         "AV Equipment",     "SER-P-001", Decimal("120000"),  "Boardroom"),
            ("Projector - Class 8A",          "AV Equipment",     "SER-P-002", Decimal("110000"),  "Class 8A"),
            ("Projector - Science Lab",       "AV Equipment",     "SER-P-003", Decimal("110000"),  "Science Lab"),
            ("Generator - Main",              "Utilities",        "SER-G-001", Decimal("450000"),  "Genset Room"),
            ("Water Tank - 10000L",           "Utilities",        "SER-W-001", Decimal("120000"),  "Rooftop"),
            ("School Bus - KBW 456Y",         "Vehicles",         "SER-V-001", Decimal("3500000"), "Garage"),
            ("School Van - KBX 789Z",         "Vehicles",         "SER-V-002", Decimal("2200000"), "Garage"),
            ("School Bus - KBZ 123T",         "Vehicles",         "SER-V-003", Decimal("3200000"), "Garage"),
            ("Photocopier - Admin",           "Office Equipment", "SER-O-001", Decimal("250000"),  "Admin Office"),
            ("Printer - Finance Office",      "Office Equipment", "SER-O-002", Decimal("35000"),   "Finance Office"),
            ("PA System - Hall",              "AV Equipment",     "SER-AV-01", Decimal("180000"),  "Main Hall"),
            ("Microscope - Bio Lab 01",       "Lab Equipment",    "SER-L-001", Decimal("95000"),   "Biology Lab"),
            ("Microscope - Bio Lab 02",       "Lab Equipment",    "SER-L-002", Decimal("95000"),   "Biology Lab"),
            ("Microscope - Bio Lab 03",       "Lab Equipment",    "SER-L-003", Decimal("95000"),   "Biology Lab"),
            ("Science Balance Scale",         "Lab Equipment",    "SER-L-004", Decimal("45000"),   "Chemistry Lab"),
            ("Bunsen Burner Set x10",         "Lab Equipment",    "SER-L-005", Decimal("30000"),   "Chemistry Lab"),
            ("Library Computer",              "ICT Equipment",    "SER-C-010", Decimal("90000"),   "Library"),
            ("CCTV System - 16 cameras",      "Security Equipment","SER-S-001",Decimal("350000"),  "Entire Campus"),
            ("Electric Fence Controller",     "Security Equipment","SER-S-002",Decimal("120000"),  "Security Room"),
            ("Intercom System",               "Security Equipment","SER-S-003",Decimal("75000"),   "Gate"),
            ("Cafeteria Stove - Industrial",  "Kitchen Equipment", "SER-K-001",Decimal("220000"),  "Cafeteria Kitchen"),
            ("Refrigerator - Cafeteria",      "Kitchen Equipment", "SER-K-002",Decimal("95000"),   "Cafeteria Kitchen"),
            ("Water Purifier",                "Kitchen Equipment", "SER-K-003",Decimal("65000"),   "Kitchen"),
            ("Blood Pressure Monitor",        "Medical Equipment", "SER-M-001",Decimal("25000"),   "Dispensary"),
            ("First Aid Cabinet",             "Medical Equipment", "SER-M-002",Decimal("12000"),   "Dispensary"),
        ]

        created = 0
        for name, cat_name, asset_code, cost, location in ASSETS:
            cat = cats.get(cat_name)
            if not cat:
                continue
            try:
                _, c = Asset.objects.get_or_create(
                    asset_code=asset_code,
                    defaults={
                        "name": name,
                        "category": cat,
                        "purchase_date": date(2022, 1, 15),
                        "purchase_cost": cost,
                        "current_value": cost * Decimal("0.8"),
                        "location": location,
                        "status": "Active",
                        "serial_number": asset_code,
                    },
                )
                if c:
                    created += 1
            except Exception:
                pass

        self.stdout.write(f"  Assets: {created} assets")

    # ─── HR EXTRAS: Leave Types, Leave Requests, More PTM ────────────────────

    def _seed_hr_extras(self):
        from hr.models import Employee, LeaveRequest, LeaveType
        from ptm.models import PTMSession, PTMSlot
        from django.contrib.auth import get_user_model
        from academics.models import Term

        User = get_user_model()

        # ── Leave Types ──────────────────────────────────────────────────────
        LEAVE_TYPES = [
            # (name, code, max_days_year, is_paid)
            ("Annual Leave",        "AL",   25, True),
            ("Sick Leave",          "SL",   14, True),
            ("Maternity Leave",     "ML",   90, True),
            ("Paternity Leave",     "PL",   14, True),
            ("Study Leave",         "STL",  30, False),
            ("Compassionate Leave", "CL",    5, True),
            ("Emergency Leave",     "EL",    3, True),
            ("Unpaid Leave",        "UL",   30, False),
            ("Medical Leave",       "MED",  21, True),
            ("Public Holiday",      "PH",    0, True),
        ]

        lt_created = 0
        leave_types = []
        for name, code, max_days, paid in LEAVE_TYPES:
            try:
                lt, lc = LeaveType.objects.get_or_create(
                    code=code,
                    defaults={"name": name, "max_days_year": max_days, "is_paid": paid, "is_active": True},
                )
                leave_types.append(lt)
                if lc:
                    lt_created += 1
            except Exception:
                lt = LeaveType.objects.filter(name=name).first()
                if lt:
                    leave_types.append(lt)

        # ── Leave Requests ────────────────────────────────────────────────────
        employees = list(Employee.objects.all()[:30])
        lr_created = 0
        reasons = [
            "Family health emergency",
            "Personal medical appointment",
            "Continuing education course",
            "Bereavement — immediate family",
            "Annual vacation",
            "Medical procedure recovery",
            "Study for professional exam",
            "Wedding of close relative",
            "Hospital admission",
            "Personal urgent matter",
        ]

        today = date.today()
        for i, employee in enumerate(employees):
            lt = leave_types[i % len(leave_types)]
            start_d = date(2024, 1, 1) + timedelta(days=i * 12)
            end_d = start_d + timedelta(days=(i % 10) + 1)
            days = (end_d - start_d).days + 1
            try:
                _, c = LeaveRequest.objects.get_or_create(
                    employee=employee,
                    leave_type=lt,
                    defaults={
                        "start_date": start_d,
                        "end_date": end_d,
                        "days_requested": days,
                        "reason": reasons[i % len(reasons)],
                        "status": ["Approved", "Approved", "Pending", "Rejected"][i % 4],
                        "approval_stage": "APPROVED",
                    },
                )
                if c:
                    lr_created += 1
            except Exception:
                pass

        # ── Extra PTM Sessions ────────────────────────────────────────────────
        term = Term.objects.order_by("-start_date").first()
        teachers = list(User.objects.filter(userprofile__role__name="TEACHER")[:8])

        PTM_EXTRA = [
            ("Grade 4 Term 1 PTM",    date(2024, 3, 15), "Main Hall",     "08:00", "15:00"),
            ("Grade 5 Term 1 PTM",    date(2024, 3, 16), "Library",       "08:00", "15:00"),
            ("Grade 6 Term 1 PTM",    date(2024, 3, 17), "Staffroom",     "08:00", "14:00"),
            ("Grade 7 Term 2 PTM",    date(2024, 7, 6), "Main Hall",     "08:00", "15:00"),
            ("Grade 8 Term 2 PTM",    date(2024, 7, 7), "Boardroom",     "08:00", "14:00"),
            ("Grade 4 Term 3 PTM",    date(2024, 10, 12), "Main Hall",    "09:00", "15:00"),
            ("Grade 5 Term 3 PTM",    date(2024, 10, 13), "Staffroom",    "09:00", "15:00"),
            ("Grade 6 End Year PTM",  date(2024, 11, 9), "Library",       "08:00", "14:00"),
            ("Grade 7 End Year PTM",  date(2024, 11, 10), "Boardroom",    "08:00", "14:00"),
            ("Grade 8 Prep PTM",      date(2024, 11, 16), "Main Hall",    "08:00", "16:00"),
            ("KCPE Prep Briefing",    date(2024, 8, 24), "Auditorium",    "10:00", "14:00"),
            ("Term 1 Opening PTM",    date(2024, 1, 13), "Main Hall",     "08:00", "15:00"),
            ("Term 2 Opening PTM",    date(2024, 5, 6),  "Library",       "08:00", "13:00"),
            ("Term 3 Opening PTM",    date(2024, 9, 7),  "Staffroom",     "09:00", "14:00"),
            ("Mid-Term Grade 4 Review",date(2024, 2, 24),"Library",       "09:00", "13:00"),
            ("Mid-Term Grade 5 Review",date(2024, 6, 15),"Staffroom",     "09:00", "13:00"),
            ("Mid-Term Grade 6 Review",date(2024, 6, 22),"Boardroom",     "09:00", "13:00"),
            ("Mid-Term Grade 7 Review",date(2024, 2, 10),"Library",       "09:00", "13:00"),
        ]

        ptm_created = 0
        slot_created = 0
        for title, dt, venue, start, end in PTM_EXTRA:
            session, sc = PTMSession.objects.get_or_create(
                title=title,
                defaults={
                    "date": dt,
                    "venue": venue,
                    "start_time": time.fromisoformat(start),
                    "end_time": time.fromisoformat(end),
                    "slot_duration_minutes": 15,
                    "term": term,
                    "is_virtual": False,
                },
            )
            if sc:
                ptm_created += 1
            if teachers:
                for teacher in teachers[:4]:
                    for slot_num in range(4):
                        total_min = 8 * 60 + slot_num * 15
                        slot_t = time(total_min // 60, total_min % 60)
                        _, stc = PTMSlot.objects.get_or_create(
                            session=session, teacher=teacher, slot_time=slot_t,
                            defaults={"is_booked": slot_num < 3},
                        )
                        if stc:
                            slot_created += 1

        self.stdout.write(
            f"  HR extras: {lt_created} leave types, {lr_created} leave requests, "
            f"{ptm_created} PTM sessions, {slot_created} slots"
        )
