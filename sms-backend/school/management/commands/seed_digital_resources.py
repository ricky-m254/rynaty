"""
seed_digital_resources.py

Seeds KICD-approved digital textbooks and open learning materials (Harvard CS50,
Khan Academy, KICD OER) into the Library and E-Learning modules.

All resources are free, openly-licensed, and aligned with Kenya's CBE curriculum
for Grades 7-10.  The command is idempotent — safe to re-run at any time.

Usage:
    python manage.py seed_digital_resources --schema_name demo_school
    python manage.py seed_digital_resources --all-tenants
"""
from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context, get_tenant_model

import logging

logger = logging.getLogger(__name__)



class Command(BaseCommand):
    help = "Seed KICD digital textbooks and Harvard/open e-learning materials (CBE Grade 7-10)"

    def add_arguments(self, parser):
        parser.add_argument("--schema_name", type=str, default="demo_school",
                            help="Target tenant schema name")
        parser.add_argument("--all-tenants", action="store_true",
                            help="Run for every non-public tenant schema")

    def handle(self, *args, **options):
        if options["all_tenants"]:
            TenantModel = get_tenant_model()
            schemas = list(
                TenantModel.objects.exclude(schema_name="public")
                                   .values_list("schema_name", flat=True)
            )
        else:
            schemas = [options["schema_name"]]

        for schema in schemas:
            self.stdout.write(f"[seed_digital_resources] Seeding schema: {schema}")
            with schema_context(schema):
                lib_stats = self._seed_library_digital(schema)
                el_stats = self._seed_elearning_courses(schema)
            self.stdout.write(
                self.style.SUCCESS(
                    f"[seed_digital_resources] {schema}: "
                    f"Library → {lib_stats['created']} created / {lib_stats['skipped']} skipped | "
                    f"E-Learning → {el_stats['created']} courses / {el_stats['materials']} materials"
                )
            )

    # ─────────────────────────────────────────────────────────────────────────
    # LIBRARY — KICD OER Digital Textbooks
    # ─────────────────────────────────────────────────────────────────────────
    def _seed_library_digital(self, schema):
        try:
            from library.models import LibraryCategory, LibraryResource, ResourceCopy
        except ImportError:
            self.stdout.write("  Library app not available — skipping")
            return {"created": 0, "skipped": 0}

        KICD_BASE = "https://kicd.ac.ke/digital-library"
        OER_BASE  = "https://kicd.ac.ke/services/open-educational-resources"

        # ── Extra categories for digital resources ────────────────────────────
        EXTRA_CATS = [
            "KICD Digital Textbooks",
            "Harvard Open Learning",
            "Open Educational Resources",
            "Life Skills & PE",
            "Creative Arts",
            "Vocational Studies",
        ]
        cats = {}
        for name in EXTRA_CATS:
            c, _ = LibraryCategory.objects.get_or_create(
                name=name, defaults={"is_active": True}
            )
            cats[name] = c

        # Also pull/create the standard Textbooks category
        tb_cat, _ = LibraryCategory.objects.get_or_create(
            name="Textbooks", defaults={"is_active": True}
        )

        # ── KICD Digital Textbooks — all 19 CBE subjects, Grades 7-10 ─────────
        # Format: (title, authors, subjects_tag, isbn_stub, pub_year, cat_key, digital_url, description)
        KICD_BOOKS = [
            # ── Mathematics ──────────────────────────────────────────────────
            (
                "KICD Mathematics Learner's Book — Grade 7",
                "Kenya Institute of Curriculum Development",
                "Mathematics, CBE, Grade 7",
                "KICD-MATH-G7-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/mathematics-grade-7/",
                "Official KICD CBE Mathematics textbook for Grade 7. Covers numbers, algebra, geometry and statistics aligned with the Competency-Based Curriculum.",
            ),
            (
                "KICD Mathematics Learner's Book — Grade 8",
                "Kenya Institute of Curriculum Development",
                "Mathematics, CBE, Grade 8",
                "KICD-MATH-G8-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/mathematics-grade-8/",
                "Official KICD CBE Mathematics textbook for Grade 8. Extends algebraic thinking, trigonometry and data handling.",
            ),
            (
                "KICD Mathematics Learner's Book — Grade 9",
                "Kenya Institute of Curriculum Development",
                "Mathematics, CBE, Grade 9",
                "KICD-MATH-G9-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/mathematics-grade-9/",
                "Official KICD CBE Mathematics textbook for Grade 9. Covers quadratic equations, matrices, sequences and financial mathematics.",
            ),
            (
                "KICD Mathematics Learner's Book — Grade 10",
                "Kenya Institute of Curriculum Development",
                "Mathematics, CBE, Grade 10",
                "KICD-MATH-G10-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/mathematics-grade-10/",
                "Official KICD CBE Mathematics textbook for Grade 10. Covers calculus introduction, vectors and probability.",
            ),
            # ── English ──────────────────────────────────────────────────────
            (
                "KICD English Learner's Book — Grade 7",
                "Kenya Institute of Curriculum Development",
                "English, Language, CBE, Grade 7",
                "KICD-ENG-G7-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/english-grade-7/",
                "Official KICD CBE English Language textbook for Grade 7. Grammar, reading comprehension, essay writing and oral communication.",
            ),
            (
                "KICD English Learner's Book — Grade 8",
                "Kenya Institute of Curriculum Development",
                "English, Language, CBE, Grade 8",
                "KICD-ENG-G8-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/english-grade-8/",
                "Official KICD CBE English Language textbook for Grade 8.",
            ),
            (
                "KICD English Learner's Book — Grade 9",
                "Kenya Institute of Curriculum Development",
                "English, Language, CBE, Grade 9",
                "KICD-ENG-G9-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/english-grade-9/",
                "Official KICD CBE English Language textbook for Grade 9. Advanced grammar, literary analysis and creative writing.",
            ),
            (
                "KICD English Learner's Book — Grade 10",
                "Kenya Institute of Curriculum Development",
                "English, Language, CBE, Grade 10",
                "KICD-ENG-G10-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/english-grade-10/",
                "Official KICD CBE English Language textbook for Grade 10.",
            ),
            # ── Kiswahili ────────────────────────────────────────────────────
            (
                "KICD Kiswahili Kitabu cha Mwanafunzi — Darasa la 7",
                "Kenya Institute of Curriculum Development",
                "Kiswahili, Language, CBE, Grade 7",
                "KICD-KSW-G7-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/kiswahili-grade-7/",
                "Kitabu rasmi cha KICD CBE Kiswahili kwa Darasa la 7. Inashughulikia sarufi, ushairi, hadithi na mazungumzo.",
            ),
            (
                "KICD Kiswahili Kitabu cha Mwanafunzi — Darasa la 9",
                "Kenya Institute of Curriculum Development",
                "Kiswahili, Language, CBE, Grade 9",
                "KICD-KSW-G9-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/kiswahili-grade-9/",
                "Kitabu rasmi cha KICD CBE Kiswahili kwa Darasa la 9. Tamthilia, riwaya, na uandishi wa makala.",
            ),
            # ── Integrated Science ───────────────────────────────────────────
            (
                "KICD Integrated Science Learner's Book — Grade 7",
                "Kenya Institute of Curriculum Development",
                "Integrated Science, Biology, Chemistry, Physics, CBE, Grade 7",
                "KICD-SCI-G7-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/integrated-science-grade-7/",
                "Official KICD CBE Integrated Science textbook for Grade 7. Combines concepts from Biology, Chemistry and Physics in an inquiry-based approach.",
            ),
            (
                "KICD Integrated Science Learner's Book — Grade 8",
                "Kenya Institute of Curriculum Development",
                "Integrated Science, CBE, Grade 8",
                "KICD-SCI-G8-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/integrated-science-grade-8/",
                "Official KICD CBE Integrated Science textbook for Grade 8.",
            ),
            # ── Social Studies ───────────────────────────────────────────────
            (
                "KICD Social Studies Learner's Book — Grade 7",
                "Kenya Institute of Curriculum Development",
                "Social Studies, History, Geography, CBE, Grade 7",
                "KICD-SS-G7-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/social-studies-grade-7/",
                "Official KICD CBE Social Studies textbook for Grade 7. Kenya and the world — geography, history and civics integrated.",
            ),
            (
                "KICD Social Studies Learner's Book — Grade 8",
                "Kenya Institute of Curriculum Development",
                "Social Studies, CBE, Grade 8",
                "KICD-SS-G8-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/social-studies-grade-8/",
                "Official KICD CBE Social Studies textbook for Grade 8.",
            ),
            # ── Biology ──────────────────────────────────────────────────────
            (
                "KICD Biology Learner's Book — Grade 9",
                "Kenya Institute of Curriculum Development",
                "Biology, CBE, Grade 9",
                "KICD-BIO-G9-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/biology-grade-9/",
                "Official KICD CBE Biology textbook for Grade 9. Cell biology, genetics, ecology and human physiology.",
            ),
            (
                "KICD Biology Learner's Book — Grade 10",
                "Kenya Institute of Curriculum Development",
                "Biology, CBE, Grade 10",
                "KICD-BIO-G10-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/biology-grade-10/",
                "Official KICD CBE Biology textbook for Grade 10. Evolution, biotechnology and applied biology.",
            ),
            # ── Chemistry ────────────────────────────────────────────────────
            (
                "KICD Chemistry Learner's Book — Grade 9",
                "Kenya Institute of Curriculum Development",
                "Chemistry, CBE, Grade 9",
                "KICD-CHEM-G9-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/chemistry-grade-9/",
                "Official KICD CBE Chemistry textbook for Grade 9. Atomic structure, bonding, acids/bases and organic chemistry introduction.",
            ),
            (
                "KICD Chemistry Learner's Book — Grade 10",
                "Kenya Institute of Curriculum Development",
                "Chemistry, CBE, Grade 10",
                "KICD-CHEM-G10-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/chemistry-grade-10/",
                "Official KICD CBE Chemistry textbook for Grade 10. Electrochemistry, industrial chemistry and environmental chemistry.",
            ),
            # ── Physics ──────────────────────────────────────────────────────
            (
                "KICD Physics Learner's Book — Grade 9",
                "Kenya Institute of Curriculum Development",
                "Physics, CBE, Grade 9",
                "KICD-PHY-G9-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/physics-grade-9/",
                "Official KICD CBE Physics textbook for Grade 9. Mechanics, waves, electricity and electromagnetism.",
            ),
            (
                "KICD Physics Learner's Book — Grade 10",
                "Kenya Institute of Curriculum Development",
                "Physics, CBE, Grade 10",
                "KICD-PHY-G10-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/physics-grade-10/",
                "Official KICD CBE Physics textbook for Grade 10. Nuclear physics, electronics and astronomy.",
            ),
            # ── History & Government ─────────────────────────────────────────
            (
                "KICD History & Government Learner's Book — Grade 9",
                "Kenya Institute of Curriculum Development",
                "History, Government, CBE, Grade 9",
                "KICD-HIST-G9-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/history-government-grade-9/",
                "Official KICD CBE History & Government textbook for Grade 9. African nationalism, Kenya's political history and governance.",
            ),
            (
                "KICD History & Government Learner's Book — Grade 10",
                "Kenya Institute of Curriculum Development",
                "History, Government, CBE, Grade 10",
                "KICD-HIST-G10-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/history-government-grade-10/",
                "Official KICD CBE History & Government textbook for Grade 10.",
            ),
            # ── Geography ────────────────────────────────────────────────────
            (
                "KICD Geography Learner's Book — Grade 9",
                "Kenya Institute of Curriculum Development",
                "Geography, CBE, Grade 9",
                "KICD-GEO-G9-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/geography-grade-9/",
                "Official KICD CBE Geography textbook for Grade 9. Physical and human geography, Kenya environment and climate change.",
            ),
            (
                "KICD Geography Learner's Book — Grade 10",
                "Kenya Institute of Curriculum Development",
                "Geography, CBE, Grade 10",
                "KICD-GEO-G10-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/geography-grade-10/",
                "Official KICD CBE Geography textbook for Grade 10.",
            ),
            # ── CRE ──────────────────────────────────────────────────────────
            (
                "KICD Christian Religious Education — Grade 7",
                "Kenya Institute of Curriculum Development",
                "CRE, Religious Education, CBE, Grade 7",
                "KICD-CRE-G7-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/christian-religious-education-grade-7/",
                "Official KICD CBE CRE textbook for Grade 7. Biblical studies, Christian values and moral development.",
            ),
            (
                "KICD Christian Religious Education — Grade 9",
                "Kenya Institute of Curriculum Development",
                "CRE, Religious Education, CBE, Grade 9",
                "KICD-CRE-G9-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/christian-religious-education-grade-9/",
                "Official KICD CBE CRE textbook for Grade 9.",
            ),
            # ── Business Studies ─────────────────────────────────────────────
            (
                "KICD Business Studies Learner's Book — Grade 9",
                "Kenya Institute of Curriculum Development",
                "Business Studies, Entrepreneurship, CBE, Grade 9",
                "KICD-BUS-G9-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/business-studies-grade-9/",
                "Official KICD CBE Business Studies textbook for Grade 9. Entrepreneurship, trade, money and financial literacy.",
            ),
            (
                "KICD Business Studies Learner's Book — Grade 10",
                "Kenya Institute of Curriculum Development",
                "Business Studies, Entrepreneurship, CBE, Grade 10",
                "KICD-BUS-G10-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/business-studies-grade-10/",
                "Official KICD CBE Business Studies textbook for Grade 10.",
            ),
            # ── Agriculture ──────────────────────────────────────────────────
            (
                "KICD Agriculture Learner's Book — Grade 7",
                "Kenya Institute of Curriculum Development",
                "Agriculture, CBE, Grade 7",
                "KICD-AGR-G7-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/agriculture-grade-7/",
                "Official KICD CBE Agriculture textbook for Grade 7. Soil, crop production, livestock and agribusiness basics.",
            ),
            (
                "KICD Agriculture Learner's Book — Grade 9",
                "Kenya Institute of Curriculum Development",
                "Agriculture, CBE, Grade 9",
                "KICD-AGR-G9-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/agriculture-grade-9/",
                "Official KICD CBE Agriculture textbook for Grade 9.",
            ),
            # ── Computer Studies ─────────────────────────────────────────────
            (
                "KICD Computer Studies Learner's Book — Grade 7",
                "Kenya Institute of Curriculum Development",
                "Computer Studies, ICT, CBE, Grade 7",
                "KICD-CS-G7-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/computer-studies-grade-7/",
                "Official KICD CBE Computer Studies textbook for Grade 7. Digital literacy, hardware, software and internet safety.",
            ),
            (
                "KICD Computer Studies Learner's Book — Grade 9",
                "Kenya Institute of Curriculum Development",
                "Computer Studies, Programming, CBE, Grade 9",
                "KICD-CS-G9-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/computer-studies-grade-9/",
                "Official KICD CBE Computer Studies textbook for Grade 9. Programming fundamentals, databases and web design.",
            ),
            # ── Home Science ─────────────────────────────────────────────────
            (
                "KICD Home Science Learner's Book — Grade 7",
                "Kenya Institute of Curriculum Development",
                "Home Science, CBE, Grade 7",
                "KICD-HS-G7-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/home-science-grade-7/",
                "Official KICD CBE Home Science textbook for Grade 7. Food, nutrition, textiles, child care and household management.",
            ),
            (
                "KICD Home Science Learner's Book — Grade 9",
                "Kenya Institute of Curriculum Development",
                "Home Science, CBE, Grade 9",
                "KICD-HS-G9-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/home-science-grade-9/",
                "Official KICD CBE Home Science textbook for Grade 9.",
            ),
            # ── Creative Arts & Sports ───────────────────────────────────────
            (
                "KICD Creative Arts & Sports — Grade 7",
                "Kenya Institute of Curriculum Development",
                "Creative Arts, Sports, CBE, Grade 7",
                "KICD-CAS-G7-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/creative-arts-sports-grade-7/",
                "Official KICD CBE Creative Arts & Sports textbook for Grade 7. Visual arts, performing arts, music and physical education integrated.",
            ),
            # ── Pre-Technical Studies ────────────────────────────────────────
            (
                "KICD Pre-Technical Studies — Grade 7",
                "Kenya Institute of Curriculum Development",
                "Pre-Technical Studies, Technology, CBE, Grade 7",
                "KICD-PTS-G7-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/pre-technical-studies-grade-7/",
                "Official KICD CBE Pre-Technical Studies textbook for Grade 7. Introduction to metalwork, woodwork, electricity and technical drawing.",
            ),
            (
                "KICD Pre-Technical Studies — Grade 9",
                "Kenya Institute of Curriculum Development",
                "Pre-Technical Studies, Technology, CBE, Grade 9",
                "KICD-PTS-G9-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/pre-technical-studies-grade-9/",
                "Official KICD CBE Pre-Technical Studies textbook for Grade 9.",
            ),
            # ── Life Skills Education ────────────────────────────────────────
            (
                "KICD Life Skills Education — Grade 7",
                "Kenya Institute of Curriculum Development",
                "Life Skills, CBE, Grade 7",
                "KICD-LS-G7-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/life-skills-education-grade-7/",
                "Official KICD CBE Life Skills Education for Grade 7. Self-awareness, decision making, communication, peer influence and puberty.",
            ),
            # ── Physical Education ───────────────────────────────────────────
            (
                "KICD Physical Education — Grade 7",
                "Kenya Institute of Curriculum Development",
                "Physical Education, Sports, CBE, Grade 7",
                "KICD-PE-G7-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/physical-education-grade-7/",
                "Official KICD CBE Physical Education for Grade 7. Athletics, team sports, gymnastics, swimming and health-related fitness.",
            ),
            # ── Religious Education (IRE/HRE) ─────────────────────────────────
            (
                "KICD Religious Education — Grade 7",
                "Kenya Institute of Curriculum Development",
                "Religious Education, Islamic RE, Hindu RE, CBE, Grade 7",
                "KICD-RE-G7-2023",
                2023,
                "KICD Digital Textbooks",
                f"{KICD_BASE}/religious-education-grade-7/",
                "Official KICD CBE Religious Education (IRE/HRE) for Grade 7.",
            ),
            # ── OER Supplementary ────────────────────────────────────────────
            (
                "KICD CBE Curriculum Design Guide",
                "Kenya Institute of Curriculum Development",
                "Curriculum, CBE, Teacher Resource",
                "KICD-CDG-2023",
                2023,
                "Open Educational Resources",
                f"{OER_BASE}/cbe-curriculum-design-guide/",
                "KICD comprehensive guide to Competency-Based Education — philosophy, assessment, lesson planning and differentiation for Grades 7-10.",
            ),
            (
                "KICD CBE Assessment Handbook — Grades 7-10",
                "Kenya Institute of Curriculum Development",
                "Assessment, CBE, Teacher Resource, EE, ME, AE, BE",
                "KICD-ASS-2023",
                2023,
                "Open Educational Resources",
                f"{OER_BASE}/cbe-assessment-handbook/",
                "KICD handbook on formative and summative assessment using CBE bands: Exceeding Expectations (EE), Meeting Expectations (ME), Approaching Expectations (AE) and Below Expectations (BE).",
            ),
            # ── Harvard Open Materials ────────────────────────────────────────
            (
                "Harvard CS50's Introduction to Computer Science (CS50x)",
                "David J. Malan, Harvard University",
                "Computer Science, Programming, Algorithms, CBE",
                "HARV-CS50X-2024",
                2024,
                "Harvard Open Learning",
                "https://cs50.harvard.edu/x/2024/",
                "Free Harvard University introductory computer science course. Covers C, Python, SQL, HTML/CSS/JavaScript. Freely available with certificate option. Aligns with KICD CBE Computer Studies Grade 9-10.",
            ),
            (
                "Harvard CS50's Introduction to Programming with Python (CS50P)",
                "David J. Malan, Harvard University",
                "Python, Programming, Computer Science, CBE",
                "HARV-CS50P-2022",
                2022,
                "Harvard Open Learning",
                "https://cs50.harvard.edu/python/2022/",
                "Free Harvard Python programming course — functions, conditionals, loops, exceptions, libraries and file I/O. Aligns with KICD CBE Computer Studies programming strand.",
            ),
            (
                "Harvard CS50's Introduction to Artificial Intelligence with Python",
                "Brian Yu, Harvard University",
                "Artificial Intelligence, Machine Learning, Python, CBE",
                "HARV-CS50AI-2024",
                2024,
                "Harvard Open Learning",
                "https://cs50.harvard.edu/ai/2024/",
                "Free Harvard course on AI fundamentals — search algorithms, neural networks, natural language processing and computer vision using Python.",
            ),
            (
                "Harvard CS50's Web Programming with Python and JavaScript",
                "Brian Yu, David J. Malan, Harvard University",
                "Web Development, Python, JavaScript, Django, CBE",
                "HARV-CS50W-2020",
                2020,
                "Harvard Open Learning",
                "https://cs50.harvard.edu/web/2020/",
                "Free Harvard course on full-stack web development. Covers HTML, CSS, Django, SQL, JavaScript and React. Aligns with advanced Computer Studies strands.",
            ),
            (
                "Harvard CS50's Understanding Technology",
                "David J. Malan, Harvard University",
                "Digital Literacy, Technology, Internet Safety, CBE",
                "HARV-CS50T-2017",
                2017,
                "Harvard Open Learning",
                "https://cs50.harvard.edu/technology/2017/",
                "Free Harvard technology literacy course for non-programmers. Covers hardware, internet, multimedia, security and programming basics. Aligns with Grade 7-8 Computer Studies digital literacy strand.",
            ),
        ]

        cat_digital, _ = LibraryCategory.objects.get_or_create(
            name="KICD Digital Textbooks", defaults={"is_active": True}
        )

        created = 0
        skipped = 0

        for (title, authors, subjects, isbn, year, cat_key, url, desc) in KICD_BOOKS:
            cat_obj = cats.get(cat_key, cat_digital)
            resource, was_created = LibraryResource.objects.get_or_create(
                isbn=isbn,
                defaults={
                    "title": title,
                    "authors": authors,
                    "subjects": subjects,
                    "resource_type": "Digital",
                    "publication_year": year,
                    "publisher": authors.split(",")[0].strip(),
                    "language": "en",
                    "category": cat_obj,
                    "digital_url": url,
                    "description": desc,
                    "total_copies": 0,
                    "available_copies": 0,
                    "is_active": True,
                    "edition": "CBE Edition",
                },
            )
            if was_created:
                created += 1
            else:
                if not resource.digital_url:
                    resource.digital_url = url
                    resource.save(update_fields=["digital_url"])
                skipped += 1

        return {"created": created, "skipped": skipped}

    # ─────────────────────────────────────────────────────────────────────────
    # E-LEARNING — Harvard CS50 + KICD Video Materials
    # ─────────────────────────────────────────────────────────────────────────
    def _seed_elearning_courses(self, schema):
        try:
            from elearning.models import Course, CourseMaterial, VirtualSession
        except ImportError:
            self.stdout.write("  E-Learning app not available — skipping")
            return {"created": 0, "materials": 0}

        from django.contrib.auth.models import User
        from school.models import Subject

        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            admin = User.objects.first()
        if not admin:
            return {"created": 0, "materials": 0}

        term = None
        try:
            from academics.models import Term as AcademicTerm
            term = AcademicTerm.objects.filter(is_active=True).first()
        except Exception:
            logger.warning("Caught and logged", exc_info=True)

        # ── Course + Materials catalogue ─────────────────────────────────────
        # Each entry: (title, code, subject_hint, description, [(mat_title, mat_type, link_url), ...])
        OPEN_COURSES = [
            # ── Harvard CS50 series ──────────────────────────────────────────
            (
                "Harvard CS50x — Introduction to Computer Science",
                "HARV-CS50X",
                "Computer Studies",
                "David Malan's world-famous CS50 course, free from Harvard. Covers algorithms, data structures, web development and more. Directly aligned with KICD CBE Computer Studies Grade 9-10 programming strand.",
                [
                    ("CS50x Week 0 — Scratch & Computational Thinking",    "Video",        "https://www.youtube.com/watch?v=3LPJfIKxwWc"),
                    ("CS50x Week 1 — C Programming",                        "Video",        "https://www.youtube.com/watch?v=cwtpLIWylAw"),
                    ("CS50x Week 2 — Arrays & Compilation",                 "Video",        "https://www.youtube.com/watch?v=4vU4aEFmAQo"),
                    ("CS50x Week 6 — Python",                               "Video",        "https://www.youtube.com/watch?v=EHi0RDZ31VA"),
                    ("CS50x Week 8 — HTML, CSS & JavaScript",               "Video",        "https://www.youtube.com/watch?v=5g0x2QB3Tvk"),
                    ("CS50x Week 9 — Flask Web Framework",                  "Video",        "https://www.youtube.com/watch?v=x_c8pTW8ZUc"),
                    ("CS50x Full Course Notes",                             "PDF",          "https://cs50.harvard.edu/x/2024/notes/"),
                    ("CS50x Problem Sets & Labs",                           "Note",         "https://cs50.harvard.edu/x/2024/psets/"),
                    ("CS50x — Enrol Free on edX",                           "Link",         "https://www.edx.org/course/introduction-computer-science-harvardx-cs50x"),
                ],
            ),
            (
                "Harvard CS50P — Python Programming",
                "HARV-CS50P",
                "Computer Studies",
                "Harvard's free Python programming course. Covers functions, loops, exceptions, file I/O, libraries and OOP. Aligns with KICD CBE Computer Studies programming competencies for Grade 9-10.",
                [
                    ("CS50P Lecture 0 — Functions & Variables",  "Video", "https://www.youtube.com/watch?v=JP7ITIXGpHk"),
                    ("CS50P Lecture 1 — Conditionals",           "Video", "https://www.youtube.com/watch?v=p_8p1xmRBsY"),
                    ("CS50P Lecture 2 — Loops",                  "Video", "https://www.youtube.com/watch?v=WgX8e_O7eG8"),
                    ("CS50P Lecture 3 — Exceptions",             "Video", "https://www.youtube.com/watch?v=LW7g1169v7w"),
                    ("CS50P Lecture 4 — Libraries",              "Video", "https://www.youtube.com/watch?v=-7xg8pGcP6w"),
                    ("CS50P Lecture 5 — Unit Tests",             "Video", "https://www.youtube.com/watch?v=tIrcxwLqzjQ"),
                    ("CS50P Lecture 6 — File I/O",               "Video", "https://www.youtube.com/watch?v=KD-Yoel6EVQ"),
                    ("CS50P Lecture 9 — Et Cetera (OOP recap)",  "Video", "https://www.youtube.com/watch?v=6pgodt1mezg"),
                    ("CS50P Course Notes & Problem Sets",        "PDF",   "https://cs50.harvard.edu/python/2022/notes/"),
                ],
            ),
            (
                "Harvard CS50 AI — Introduction to Artificial Intelligence",
                "HARV-CS50AI",
                "Computer Studies",
                "Harvard's free AI course using Python. Covers search, knowledge, neural networks and NLP. Excellent enrichment for advanced Grade 10 Computer Studies learners.",
                [
                    ("CS50 AI Lecture 0 — Search Algorithms",       "Video", "https://www.youtube.com/watch?v=D5aJNFWsWew"),
                    ("CS50 AI Lecture 1 — Knowledge Representation", "Video", "https://www.youtube.com/watch?v=HWQLez87vqM"),
                    ("CS50 AI Lecture 4 — Learning (ML Intro)",      "Video", "https://www.youtube.com/watch?v=mFZazxxADM8"),
                    ("CS50 AI Lecture 5 — Neural Networks",          "Video", "https://www.youtube.com/watch?v=J1QD9hLDEDY"),
                    ("CS50 AI Lecture 6 — Language (NLP)",           "Video", "https://www.youtube.com/watch?v=QAZc9xsQNjQ"),
                    ("CS50 AI — Full Course Notes",                  "PDF",   "https://cs50.harvard.edu/ai/2024/notes/"),
                ],
            ),
            (
                "Harvard CS50T — Understanding Technology",
                "HARV-CS50T",
                "Computer Studies",
                "Harvard's free technology literacy course for non-programmers. Covers hardware, internet, security and programming basics. Aligns with KICD CBE Computer Studies digital literacy strand Grades 7-8.",
                [
                    ("CS50T — Hardware",          "Video", "https://www.youtube.com/watch?v=tI7Z5a9G5Z4"),
                    ("CS50T — Internet",          "Video", "https://www.youtube.com/watch?v=n_KghQP86Sw"),
                    ("CS50T — Multimedia",        "Video", "https://www.youtube.com/watch?v=pMH4wJW0HS4"),
                    ("CS50T — Security",          "Video", "https://www.youtube.com/watch?v=AuYNXgO_f3Y"),
                    ("CS50T — Programming",       "Video", "https://www.youtube.com/watch?v=AMIH-xz14lU"),
                    ("CS50T Web Programming",     "Video", "https://www.youtube.com/watch?v=cNR5DVYlb9A"),
                ],
            ),
            # ── Mathematics (Khan Academy aligned) ───────────────────────────
            (
                "CBE Mathematics — Grade 7 Video Lessons",
                "OPEN-MATH-G7",
                "Mathematics",
                "Free video lessons covering the KICD CBE Mathematics Grade 7 curriculum. Topics include integers, fractions, decimals, basic algebra and introductory geometry.",
                [
                    ("Whole Numbers & Place Value",          "Video", "https://www.khanacademy.org/math/cc-sixth-grade-math"),
                    ("Fractions — Adding & Subtracting",     "Video", "https://www.khanacademy.org/math/arithmetic/fractions"),
                    ("Introduction to Algebra",              "Video", "https://www.khanacademy.org/math/algebra/x2f8bb11595b61c86:foundation-algebra"),
                    ("Geometry — Angles & Shapes",           "Video", "https://www.khanacademy.org/math/basic-geo"),
                    ("Data & Statistics Basics",             "Video", "https://www.khanacademy.org/math/cc-sixth-grade-math/cc-6th-data-statistics"),
                    ("KICD Grade 7 Mathematics OER",         "PDF",   "https://kicd.ac.ke/digital-library/mathematics-grade-7/"),
                ],
            ),
            (
                "CBE Mathematics — Grade 9 Video Lessons",
                "OPEN-MATH-G9",
                "Mathematics",
                "Free video lessons for KICD CBE Mathematics Grade 9 — quadratic equations, simultaneous equations, trigonometry, statistics and financial mathematics.",
                [
                    ("Quadratic Equations — Factorisation",         "Video", "https://www.khanacademy.org/math/algebra/x2f8bb11595b61c86:quadratics-multiplying-factoring"),
                    ("Simultaneous Equations",                       "Video", "https://www.khanacademy.org/math/algebra/x2f8bb11595b61c86:systems-of-equations"),
                    ("Trigonometry — Sine, Cosine, Tangent",        "Video", "https://www.khanacademy.org/math/trigonometry"),
                    ("Statistics — Measures of Central Tendency",   "Video", "https://www.khanacademy.org/math/statistics-probability"),
                    ("Financial Mathematics",                        "Video", "https://www.khanacademy.org/math/math2/x10d71b1cb4bdb76a:math2-financial-math"),
                    ("KICD Grade 9 Mathematics OER",                "PDF",   "https://kicd.ac.ke/digital-library/mathematics-grade-9/"),
                ],
            ),
            # ── Biology ──────────────────────────────────────────────────────
            (
                "CBE Biology — Grade 9 Video Lessons",
                "OPEN-BIO-G9",
                "Biology",
                "Free Biology video lessons aligned with the KICD CBE Grade 9 syllabus. Topics: cell biology, genetics, ecology, human physiology and health.",
                [
                    ("Cell Biology — Structure & Function",    "Video", "https://www.khanacademy.org/science/biology/structure-of-a-cell"),
                    ("DNA and Genetics",                       "Video", "https://www.khanacademy.org/science/biology/classical-genetics"),
                    ("Ecology — Ecosystems & Food Webs",       "Video", "https://www.khanacademy.org/science/biology/ecology"),
                    ("Human Physiology — Digestive System",    "Video", "https://www.khanacademy.org/science/biology/human-biology"),
                    ("Evolution & Natural Selection",          "Video", "https://www.khanacademy.org/science/biology/her-biology"),
                    ("KICD Grade 9 Biology OER",               "PDF",   "https://kicd.ac.ke/digital-library/biology-grade-9/"),
                ],
            ),
            # ── Chemistry ────────────────────────────────────────────────────
            (
                "CBE Chemistry — Grade 9 Video Lessons",
                "OPEN-CHEM-G9",
                "Chemistry",
                "Free Chemistry video lessons for KICD CBE Grade 9 — atomic structure, periodic table, chemical bonding, acids/bases and organic chemistry introduction.",
                [
                    ("Atomic Structure & The Periodic Table",   "Video", "https://www.khanacademy.org/science/chemistry/atomic-structure-and-properties"),
                    ("Chemical Bonding",                        "Video", "https://www.khanacademy.org/science/chemistry/chemical-bonds"),
                    ("Acids, Bases & Salts",                    "Video", "https://www.khanacademy.org/science/chemistry/acids-and-bases-topic"),
                    ("Organic Chemistry Introduction",          "Video", "https://www.khanacademy.org/science/organic-chemistry"),
                    ("Electrochemistry",                        "Video", "https://www.khanacademy.org/science/chemistry/oxidation-reduction"),
                    ("KICD Grade 9 Chemistry OER",              "PDF",   "https://kicd.ac.ke/digital-library/chemistry-grade-9/"),
                ],
            ),
            # ── Physics ──────────────────────────────────────────────────────
            (
                "CBE Physics — Grade 9 Video Lessons",
                "OPEN-PHY-G9",
                "Physics",
                "Free Physics video lessons for KICD CBE Grade 9 — mechanics, waves, electricity and electromagnetism.",
                [
                    ("Forces & Newton's Laws",                 "Video", "https://www.khanacademy.org/science/physics/forces-newtons-laws"),
                    ("Waves — Properties & Types",             "Video", "https://www.khanacademy.org/science/physics/mechanical-waves-and-sound"),
                    ("Electricity — Circuits & Ohm's Law",    "Video", "https://www.khanacademy.org/science/physics/circuits-topic"),
                    ("Electromagnetism",                       "Video", "https://www.khanacademy.org/science/physics/magnetic-forces-and-magnetic-fields"),
                    ("Light & Optics",                         "Video", "https://www.khanacademy.org/science/physics/light-waves"),
                    ("KICD Grade 9 Physics OER",               "PDF",   "https://kicd.ac.ke/digital-library/physics-grade-9/"),
                ],
            ),
            # ── English ──────────────────────────────────────────────────────
            (
                "CBE English — Grade 7-10 Language Skills",
                "OPEN-ENG-G7",
                "English",
                "Free English language resources for KICD CBE Grades 7-10. Grammar, reading comprehension, essay writing, oral communication and literature.",
                [
                    ("Grammar — Parts of Speech",             "Video", "https://www.khanacademy.org/humanities/grammar"),
                    ("Reading Comprehension Strategies",       "Video", "https://www.khanacademy.org/ela/cc-2nd-reading-vocab"),
                    ("Essay Writing — Argumentative",          "PDF",   "https://owl.purdue.edu/owl/general_writing/academic_writing/essay_writing/argumentative_essays.html"),
                    ("Things Fall Apart — Study Guide",        "PDF",   "https://www.sparknotes.com/lit/things-fall-apart/"),
                    ("Oral Communication Skills",              "Note",  "https://kicd.ac.ke/digital-library/english-grade-7/"),
                ],
            ),
            # ── History & Government ─────────────────────────────────────────
            (
                "CBE History & Government — Grade 9 Video Lessons",
                "OPEN-HIST-G9",
                "History",
                "Free History & Government video lessons for KICD CBE Grade 9 — African nationalism, Kenya's independence, governance and democracy.",
                [
                    ("African Nationalism — Overview",             "Video", "https://www.youtube.com/watch?v=MHGqMGC5_OE"),
                    ("Kenya's Road to Independence",               "PDF",   "https://kicd.ac.ke/digital-library/history-government-grade-9/"),
                    ("Democracy & Governance in Africa",           "Video", "https://www.youtube.com/watch?v=V2xMNk3bVT0"),
                    ("Cold War & Africa",                          "Video", "https://www.khanacademy.org/humanities/us-history/postwarera/cold-war-1/v/cold-war-overview"),
                    ("Kenya Constitution 2010 — Key Chapters",     "PDF",   "https://www.kenyalaw.org/kl/fileadmin/pdfdownloads/Constitution_of_Kenya__2010.pdf"),
                ],
            ),
            # ── Geography ────────────────────────────────────────────────────
            (
                "CBE Geography — Grade 9 Video Lessons",
                "OPEN-GEO-G9",
                "Geography",
                "Free Geography video lessons aligned with KICD CBE Grade 9 — physical geography, climate, natural resources and human geography.",
                [
                    ("Climate & Weather Patterns",               "Video", "https://www.khanacademy.org/science/ms-earth-and-space-science/ms-weather-and-climate"),
                    ("Plate Tectonics & Earthquakes",             "Video", "https://www.khanacademy.org/science/ms-earth-and-space-science/ms-earth-systems"),
                    ("Natural Resources in Kenya",                "PDF",   "https://kicd.ac.ke/digital-library/geography-grade-9/"),
                    ("Population & Settlement Geography",         "Video", "https://www.youtube.com/watch?v=b5rhyiPTXUA"),
                    ("Climate Change — Causes & Effects",         "Video", "https://www.khanacademy.org/science/ms-earth-and-space-science/ms-weather-and-climate/climate-and-climate-change/v/climate-and-climate-change"),
                ],
            ),
            # ── Agriculture ──────────────────────────────────────────────────
            (
                "CBE Agriculture — Grade 7-9 Video Lessons",
                "OPEN-AGR-G7",
                "Agriculture",
                "Free Agriculture video and reading resources for KICD CBE Grades 7-9. Soil science, crop production, livestock management and agribusiness.",
                [
                    ("Soil — Types, Structure & Fertility",      "Video", "https://www.youtube.com/watch?v=oBsR7LHZRVM"),
                    ("Crop Production — Planting & Harvesting",  "Video", "https://www.youtube.com/watch?v=5voKrQZZiGw"),
                    ("Livestock Management",                     "PDF",   "https://kicd.ac.ke/digital-library/agriculture-grade-7/"),
                    ("Agribusiness & Entrepreneurship",         "Video", "https://www.youtube.com/watch?v=7bCWEXrGWXQ"),
                    ("Sustainable Farming Practices",            "PDF",   "https://www.fao.org/sustainable-development-goals/resources/detail/en/c/1273498/"),
                ],
            ),
            # ── Business Studies ─────────────────────────────────────────────
            (
                "CBE Business Studies & Entrepreneurship — Grade 9-10",
                "OPEN-BUS-G9",
                "Business Studies",
                "Free Business Studies video lessons for KICD CBE Grades 9-10. Trade, business planning, financial literacy, banking and entrepreneurship.",
                [
                    ("Introduction to Entrepreneurship",         "Video", "https://www.khanacademy.org/college-careers-more/entrepreneurship2"),
                    ("Financial Literacy — Budgeting & Saving",  "Video", "https://www.khanacademy.org/college-careers-more/financial-literacy"),
                    ("Supply & Demand",                          "Video", "https://www.khanacademy.org/economics-finance-domain/ap-macroeconomics"),
                    ("Business Plan Writing",                    "PDF",   "https://kicd.ac.ke/digital-library/business-studies-grade-9/"),
                    ("Marketing & Trade Basics",                 "Note",  "https://www.khanacademy.org/economics-finance-domain/core-finance"),
                ],
            ),
        ]

        courses_created = 0
        materials_created = 0

        for (title, code, subject_hint, desc, materials) in OPEN_COURSES:
            subject = Subject.objects.filter(
                name__icontains=subject_hint.split()[0]
            ).first()

            course, was_created = Course.objects.get_or_create(
                title=title,
                defaults={
                    "teacher": admin,
                    "subject": subject,
                    "school_class": None,
                    "term": term,
                    "description": desc,
                    "is_published": True,
                },
            )

            if was_created:
                courses_created += 1

            for seq, (mat_title, mat_type, link) in enumerate(materials, start=1):
                mat, mat_created = CourseMaterial.objects.get_or_create(
                    course=course,
                    title=mat_title,
                    defaults={
                        "material_type": mat_type if mat_type in ["PDF", "Video", "Note", "Presentation", "Link"] else "Note",
                        "link_url": link,
                        "content": f"Open educational resource — {mat_title}",
                        "is_active": True,
                        "sequence": seq,
                    },
                )
                if mat_created:
                    materials_created += 1

        return {"created": courses_created, "materials": materials_created}
