"""
Management command: seed_curriculum_templates
---------------------------------------------
Seeds CBE-aligned starter templates for Schemes of Work.
Templates are generic (no class/term) so they can be cloned for any class.

Usage:
    python manage.py seed_curriculum_templates
"""
from django.core.management.base import BaseCommand


TEMPLATES = [
    {
        "subject_name": "Mathematics",
        "template_name": "CBE Mathematics — Grade 4 (Full Term)",
        "template_description": (
            "A 12-week CBE-aligned Mathematics scheme covering Number Sense, "
            "Fractions, Geometry, Measurement, and Data Handling."
        ),
        "title": "Mathematics Scheme of Work",
        "objectives": (
            "Develop learners' numeracy skills through problem solving, critical thinking, "
            "and real-life application of mathematical concepts as per CBE competency framework."
        ),
        "topics": [
            {
                "week_number": 1,
                "topic": "Whole Numbers — Place Value",
                "sub_topics": "Reading and writing numbers up to 1,000,000; place value charts",
                "learning_outcomes": "Learner can read, write and identify place value of digits up to millions",
                "teaching_methods": "Discussion, Number charts, Group work",
                "resources": "Abacus, Place value charts, Textbook pg 1–10",
                "assessment_type": "Oral questions, Written exercises",
            },
            {
                "week_number": 2,
                "topic": "Whole Numbers — Addition and Subtraction",
                "sub_topics": "Adding and subtracting up to 6-digit numbers with and without regrouping",
                "learning_outcomes": "Learner can add and subtract large numbers accurately",
                "teaching_methods": "Demonstration, Guided practice",
                "resources": "Textbook pg 11–22, Worksheets",
                "assessment_type": "Classwork, Homework",
            },
            {
                "week_number": 3,
                "topic": "Whole Numbers — Multiplication",
                "sub_topics": "Multiplying 3-digit by 2-digit numbers; word problems",
                "learning_outcomes": "Learner can multiply numbers and solve real-life multiplication problems",
                "teaching_methods": "Think-pair-share, Practice drills",
                "resources": "Multiplication tables chart, Textbook pg 23–35",
                "assessment_type": "Timed drills, Written test",
            },
            {
                "week_number": 4,
                "topic": "Fractions — Concept and Types",
                "sub_topics": "Proper, improper, mixed fractions; equivalent fractions",
                "learning_outcomes": "Learner can identify and compare different types of fractions",
                "teaching_methods": "Concrete objects, Fraction strips, Discussion",
                "resources": "Fraction strips, Textbook pg 40–52",
                "assessment_type": "Classwork, Group presentation",
            },
            {
                "week_number": 5,
                "topic": "Fractions — Addition and Subtraction",
                "sub_topics": "Adding/subtracting fractions with same and different denominators",
                "learning_outcomes": "Learner can add and subtract fractions correctly",
                "teaching_methods": "Step-by-step worked examples, Peer teaching",
                "resources": "Textbook pg 53–65",
                "assessment_type": "Written exercises, Peer assessment",
            },
            {
                "week_number": 6,
                "topic": "Decimals",
                "sub_topics": "Place value of decimals; converting fractions to decimals and vice versa",
                "learning_outcomes": "Learner understands the relationship between fractions and decimals",
                "teaching_methods": "Number line, Demonstration",
                "resources": "Number line chart, Textbook pg 66–80",
                "assessment_type": "Classwork",
            },
            {
                "week_number": 7,
                "topic": "Geometry — 2D Shapes",
                "sub_topics": "Properties of triangles, quadrilaterals, circles; perimeter and area",
                "learning_outcomes": "Learner can identify properties and calculate perimeter/area of 2D shapes",
                "teaching_methods": "Hands-on drawing, Geoboards, Measurement",
                "resources": "Rulers, Geoboards, Textbook pg 90–105",
                "assessment_type": "Practical activity, Written test",
            },
            {
                "week_number": 8,
                "topic": "Geometry — 3D Shapes",
                "sub_topics": "Cuboids, cylinders, cones, spheres; faces, edges, vertices",
                "learning_outcomes": "Learner can identify and describe properties of 3D shapes",
                "teaching_methods": "Models, Real-life objects, Group work",
                "resources": "3D shape models, Textbook pg 106–118",
                "assessment_type": "Oral, Group project",
            },
            {
                "week_number": 9,
                "topic": "Measurement — Length, Mass, Capacity",
                "sub_topics": "Units of measurement; conversions; real-life problems",
                "learning_outcomes": "Learner can measure and convert units of length, mass, and capacity",
                "teaching_methods": "Practical measurement, Group experiments",
                "resources": "Rulers, Weighing scales, Measuring cylinders, Textbook pg 120–138",
                "assessment_type": "Practical assessment",
            },
            {
                "week_number": 10,
                "topic": "Time and Money",
                "sub_topics": "Reading time (12/24 hr); Kenyan currency; profit and loss",
                "learning_outcomes": "Learner can read time and handle money-related calculations",
                "teaching_methods": "Clock models, Role play (shop activity)",
                "resources": "Clock models, Play money, Textbook pg 139–155",
                "assessment_type": "Role play, Written test",
            },
            {
                "week_number": 11,
                "topic": "Data Handling",
                "sub_topics": "Collecting, recording, and interpreting data; bar graphs, pictographs",
                "learning_outcomes": "Learner can collect data, draw graphs, and interpret results",
                "teaching_methods": "Data collection activity, Graph drawing",
                "resources": "Graph paper, Textbook pg 160–175",
                "assessment_type": "Project, Written exercise",
            },
            {
                "week_number": 12,
                "topic": "Revision and End-of-Term Assessment",
                "sub_topics": "Review of all topics covered; exam techniques",
                "learning_outcomes": "Learner demonstrates mastery of all term concepts",
                "teaching_methods": "Q&A, Revision exercises",
                "resources": "Past papers, Textbook",
                "assessment_type": "End-of-term exam",
            },
        ],
    },
    {
        "subject_name": "English",
        "template_name": "CBE English Language — Grade 5 (Full Term)",
        "template_description": (
            "A 12-week CBE-aligned English scheme covering Listening & Speaking, "
            "Reading, Writing, Grammar, and Creative Writing."
        ),
        "title": "English Language Scheme of Work",
        "objectives": (
            "Develop learners' communicative competence through integrated skills "
            "of listening, speaking, reading, and writing aligned to CBE values."
        ),
        "topics": [
            {
                "week_number": 1,
                "topic": "Listening and Speaking — Greetings and Introductions",
                "sub_topics": "Formal and informal greetings; introducing oneself and others",
                "learning_outcomes": "Learner can greet appropriately and introduce themselves confidently",
                "teaching_methods": "Role play, Pair work",
                "resources": "Audio clips, Textbook Unit 1",
                "assessment_type": "Oral presentation",
            },
            {
                "week_number": 2,
                "topic": "Reading — Comprehension Passages",
                "sub_topics": "Literal and inferential comprehension; vocabulary in context",
                "learning_outcomes": "Learner can read fluently and answer comprehension questions",
                "teaching_methods": "Guided reading, Think-aloud strategy",
                "resources": "Reading passages, Textbook Unit 2",
                "assessment_type": "Comprehension exercise",
            },
            {
                "week_number": 3,
                "topic": "Grammar — Nouns and Pronouns",
                "sub_topics": "Common, proper, collective nouns; personal and possessive pronouns",
                "learning_outcomes": "Learner can identify and use nouns and pronouns correctly in sentences",
                "teaching_methods": "Explanation, Sentence construction, Games",
                "resources": "Grammar charts, Textbook Unit 3",
                "assessment_type": "Written exercises",
            },
            {
                "week_number": 4,
                "topic": "Writing — Guided Composition",
                "sub_topics": "Paragraph writing; topic sentences; supporting details",
                "learning_outcomes": "Learner can write a coherent paragraph with a clear topic sentence",
                "teaching_methods": "Modelled writing, Guided practice",
                "resources": "Writing frames, Textbook Unit 4",
                "assessment_type": "Composition marking",
            },
            {
                "week_number": 5,
                "topic": "Grammar — Verbs and Tenses",
                "sub_topics": "Action verbs; simple past, present, future tenses; regular/irregular verbs",
                "learning_outcomes": "Learner can use verb tenses correctly in speech and writing",
                "teaching_methods": "Drills, Gap-fill exercises, Story retelling",
                "resources": "Tense charts, Textbook Unit 5",
                "assessment_type": "Fill-in exercises, Oral",
            },
            {
                "week_number": 6,
                "topic": "Reading — Functional Texts",
                "sub_topics": "Reading notices, timetables, menus, instructions",
                "learning_outcomes": "Learner can extract information from functional/everyday texts",
                "teaching_methods": "Real-life materials, Discussion",
                "resources": "Newspapers, Printed schedules, Textbook Unit 6",
                "assessment_type": "Comprehension questions",
            },
            {
                "week_number": 7,
                "topic": "Grammar — Adjectives and Adverbs",
                "sub_topics": "Descriptive adjectives; degrees of comparison; adverbs of manner/time",
                "learning_outcomes": "Learner can use adjectives and adverbs to enrich writing",
                "teaching_methods": "Word sort activity, Sentence expansion",
                "resources": "Word wall, Textbook Unit 7",
                "assessment_type": "Sentence writing",
            },
            {
                "week_number": 8,
                "topic": "Writing — Letter Writing",
                "sub_topics": "Formal and informal letters; layout, tone, and purpose",
                "learning_outcomes": "Learner can write a correctly formatted formal or informal letter",
                "teaching_methods": "Model letters, Peer editing",
                "resources": "Sample letters, Textbook Unit 8",
                "assessment_type": "Letter writing task",
            },
            {
                "week_number": 9,
                "topic": "Listening and Speaking — Debates and Discussions",
                "sub_topics": "Giving opinions; agreeing/disagreeing politely; debate structure",
                "learning_outcomes": "Learner can participate confidently in structured discussions",
                "teaching_methods": "Structured debate, Fishbowl discussion",
                "resources": "Debate topics, Textbook Unit 9",
                "assessment_type": "Oral debate assessment",
            },
            {
                "week_number": 10,
                "topic": "Creative Writing — Narrative Composition",
                "sub_topics": "Story structure; characters, setting, plot, climax, resolution",
                "learning_outcomes": "Learner can write a creative story with a clear beginning, middle, and end",
                "teaching_methods": "Story mapping, Brainstorming",
                "resources": "Story map template, Textbook Unit 10",
                "assessment_type": "Creative writing portfolio",
            },
            {
                "week_number": 11,
                "topic": "Grammar — Punctuation and Spelling",
                "sub_topics": "Full stop, comma, question mark, exclamation mark; common spelling rules",
                "learning_outcomes": "Learner can punctuate and spell correctly in their writing",
                "teaching_methods": "Proofreading activity, Spelling bees",
                "resources": "Dictionaries, Textbook Unit 11",
                "assessment_type": "Proofreading exercise, Spelling test",
            },
            {
                "week_number": 12,
                "topic": "Revision and End-of-Term Assessment",
                "sub_topics": "Comprehensive review; exam skills",
                "learning_outcomes": "Learner demonstrates mastery across all language skills",
                "teaching_methods": "Mixed revision activities",
                "resources": "Past papers",
                "assessment_type": "End-of-term written exam",
            },
        ],
    },
    {
        "subject_name": "Integrated Science",
        "template_name": "CBE Integrated Science — Grade 6 (Full Term)",
        "template_description": (
            "A 12-week CBE-aligned Science scheme covering Living Things, "
            "Matter, Energy, Environment, and Health."
        ),
        "title": "Integrated Science Scheme of Work",
        "objectives": (
            "Foster scientific inquiry, critical thinking, and environmental stewardship "
            "through hands-on experiments and observations aligned to CBE."
        ),
        "topics": [
            {
                "week_number": 1,
                "topic": "Living Things — Classification",
                "sub_topics": "Kingdoms of living things; characteristics of living things",
                "learning_outcomes": "Learner can classify organisms into kingdoms using observable characteristics",
                "teaching_methods": "Observation, Classification activity",
                "resources": "Charts, Specimens, Textbook pg 1–12",
                "assessment_type": "Classification exercise",
            },
            {
                "week_number": 2,
                "topic": "Plants — Structure and Functions",
                "sub_topics": "Parts of a plant and their functions; photosynthesis basics",
                "learning_outcomes": "Learner can label plant parts and explain their functions",
                "teaching_methods": "Dissection activity, Drawing",
                "resources": "Live plants, Textbook pg 13–25",
                "assessment_type": "Labelled diagram, Oral questions",
            },
            {
                "week_number": 3,
                "topic": "Animals — Nutrition and Feeding",
                "sub_topics": "Herbivores, carnivores, omnivores; food chains and webs",
                "learning_outcomes": "Learner can construct food chains and webs from given organisms",
                "teaching_methods": "Card sort, Diagrams, Discussion",
                "resources": "Food chain cards, Textbook pg 26–38",
                "assessment_type": "Food web diagram",
            },
            {
                "week_number": 4,
                "topic": "Human Body — Digestive System",
                "sub_topics": "Organs of digestion; process of digestion; balanced diet",
                "learning_outcomes": "Learner can trace the path of food through the digestive system",
                "teaching_methods": "Body diagram, Experiment (iodine test for starch)",
                "resources": "Digestive system chart, Textbook pg 40–55",
                "assessment_type": "Labelling exercise, Experiment report",
            },
            {
                "week_number": 5,
                "topic": "Matter — States and Properties",
                "sub_topics": "Solids, liquids, gases; properties and changes of state",
                "learning_outcomes": "Learner can describe properties of matter and explain changes of state",
                "teaching_methods": "Experiments (heating/cooling), Observation",
                "resources": "Bunsen burner/hotplate, Ice, Textbook pg 60–75",
                "assessment_type": "Experiment write-up",
            },
            {
                "week_number": 6,
                "topic": "Matter — Mixtures and Solutions",
                "sub_topics": "Soluble/insoluble substances; separating mixtures (filtering, evaporation)",
                "learning_outcomes": "Learner can separate mixtures using appropriate methods",
                "teaching_methods": "Practical experiment, Group work",
                "resources": "Filter paper, Salt, Sand, Textbook pg 76–90",
                "assessment_type": "Practical assessment",
            },
            {
                "week_number": 7,
                "topic": "Energy — Forms and Sources",
                "sub_topics": "Heat, light, sound, electrical energy; renewable vs non-renewable sources",
                "learning_outcomes": "Learner can identify forms of energy and classify energy sources",
                "teaching_methods": "Demonstrations, Video clip, Discussion",
                "resources": "Torch, Magnets, Textbook pg 92–108",
                "assessment_type": "Written questions",
            },
            {
                "week_number": 8,
                "topic": "Electricity — Simple Circuits",
                "sub_topics": "Conductors and insulators; making a simple circuit; series circuits",
                "learning_outcomes": "Learner can construct a simple electric circuit and test conductors",
                "teaching_methods": "Practical (circuit kit), Drawing circuit diagrams",
                "resources": "Battery, Bulb, Wire, Switches, Textbook pg 109–122",
                "assessment_type": "Practical task, Circuit diagram",
            },
            {
                "week_number": 9,
                "topic": "Environment — Soil and Water",
                "sub_topics": "Types of soil; water cycle; water conservation",
                "learning_outcomes": "Learner can describe soil types and explain the water cycle",
                "teaching_methods": "Soil sampling, Diagram drawing",
                "resources": "Soil samples, Water cycle chart, Textbook pg 125–140",
                "assessment_type": "Labelled water cycle, Soil test report",
            },
            {
                "week_number": 10,
                "topic": "Environment — Pollution and Conservation",
                "sub_topics": "Types of pollution; effects; conservation strategies; recycling",
                "learning_outcomes": "Learner can explain causes and effects of pollution and suggest solutions",
                "teaching_methods": "Field observation, Debate, Poster making",
                "resources": "Environment charts, Textbook pg 141–155",
                "assessment_type": "Poster project",
            },
            {
                "week_number": 11,
                "topic": "Health — Diseases and Prevention",
                "sub_topics": "Communicable and non-communicable diseases; hygiene; immunisation",
                "learning_outcomes": "Learner can explain how diseases spread and how to prevent them",
                "teaching_methods": "Case studies, Role play (health campaign)",
                "resources": "Health posters, Textbook pg 158–172",
                "assessment_type": "Health poster, Written test",
            },
            {
                "week_number": 12,
                "topic": "Revision and End-of-Term Assessment",
                "sub_topics": "Comprehensive topic review; exam preparation",
                "learning_outcomes": "Learner demonstrates mastery of all science concepts for the term",
                "teaching_methods": "Q&A, Past paper practice",
                "resources": "Past papers, Revision notes",
                "assessment_type": "End-of-term exam",
            },
        ],
    },
]


class Command(BaseCommand):
    help = "Seed CBE-aligned starter templates for Schemes of Work"

    def add_arguments(self, parser):
        parser.add_argument(
            '--schema',
            default='demo_school',
            help='Tenant schema name (default: demo_school)',
        )

    def handle(self, *args, **options):
        from django_tenants.utils import schema_context

        schema = options['schema']
        self.stdout.write(f"Seeding curriculum templates into schema '{schema}'...")

        with schema_context(schema):
            self._seed(schema)

    def _seed(self, schema):
        from school.models import Subject
        from curriculum.models import SchemeOfWork, SchemeTopic

        # Rename any legacy "CBC ..." templates to "CBE ..."
        for scheme in SchemeOfWork.objects.filter(is_template=True, template_name__contains="CBC"):
            scheme.template_name = scheme.template_name.replace("CBC", "CBE")
            scheme.title = (scheme.title or "").replace("CBC", "CBE")
            scheme.objectives = (scheme.objectives or "").replace("CBC", "CBE")
            scheme.save(update_fields=["template_name", "title", "objectives"])

        created_count = 0
        skipped_count = 0

        for tmpl in TEMPLATES:
            subject = Subject.objects.filter(name__iexact=tmpl['subject_name']).first()
            if not subject:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Subject '{tmpl['subject_name']}' not found — skipping"
                    )
                )
                skipped_count += 1
                continue

            scheme, created = SchemeOfWork.objects.get_or_create(
                subject=subject,
                school_class=None,
                term=None,
                is_template=True,
                template_name=tmpl['template_name'],
                defaults={
                    'title': tmpl['title'],
                    'objectives': tmpl['objectives'],
                    'template_description': tmpl['template_description'],
                },
            )

            if not created:
                self.stdout.write(f"  Skipped (already exists): {tmpl['template_name']}")
                skipped_count += 1
                continue

            # Seed topics
            SchemeTopic.objects.bulk_create([
                SchemeTopic(
                    scheme=scheme,
                    week_number=t['week_number'],
                    topic=t['topic'],
                    sub_topics=t.get('sub_topics', ''),
                    learning_outcomes=t.get('learning_outcomes', ''),
                    teaching_methods=t.get('teaching_methods', ''),
                    resources=t.get('resources', ''),
                    assessment_type=t.get('assessment_type', ''),
                    is_covered=False,
                )
                for t in tmpl['topics']
            ])

            self.stdout.write(
                self.style.SUCCESS(
                    f"  Created: {tmpl['template_name']} ({len(tmpl['topics'])} topics)"
                )
            )
            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone — {created_count} template(s) created, {skipped_count} skipped."
            )
        )
