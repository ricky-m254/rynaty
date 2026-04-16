from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.contrib.auth import update_session_auth_hash
from django.db.models import Count
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from communication.models import Announcement, Notification
from elearning.models import Course, CourseMaterial
from hr.models import Employee
from school.models import (
    Assessment,
    AssessmentGrade,
    AttendanceRecord,
    Department,
    Enrollment,
    GradeBand,
    GradingScheme,
    SchoolClass,
    TeacherAssignment,
    UserProfile,
)
from school.permissions import IsTeacher
from timetable.models import TimetableSlot


class TeacherPortalAccessMixin:
    permission_classes = [IsTeacher]


def _teacher_assignment_queryset(user):
    return (
        TeacherAssignment.objects.filter(teacher=user, is_active=True)
        .select_related("class_section", "class_section__grade_level", "subject")
        .order_by(
            "class_section__grade_level__order",
            "class_section__name",
            "class_section__stream",
            "subject__name",
            "id",
        )
    )


def _teacher_assigned_class_ids(user):
    return list(
        _teacher_assignment_queryset(user)
        .values_list("class_section_id", flat=True)
        .distinct()
    )


def _teacher_classes(user):
    class_ids = _teacher_assigned_class_ids(user)
    if not class_ids:
        return SchoolClass.objects.none()
    return (
        SchoolClass.objects.filter(id__in=class_ids, is_active=True)
        .select_related("grade_level")
        .order_by("grade_level__order", "name", "stream", "section_name", "id")
    )


def _class_student_count_map(class_ids):
    if not class_ids:
        return {}
    return {
        row["school_class_id"]: row["student_count"]
        for row in (
            Enrollment.objects.filter(
                school_class_id__in=class_ids,
                is_active=True,
                status="Active",
                student__is_active=True,
            )
            .values("school_class_id")
            .annotate(student_count=Count("student_id", distinct=True))
        )
    }


def _serialize_classes(class_rows):
    class_ids = [row.id for row in class_rows]
    count_map = _class_student_count_map(class_ids)
    return [
        {
            "id": row.id,
            "name": row.display_name,
            "stream": row.stream or row.section_name or "",
            "student_count": count_map.get(row.id, 0),
        }
        for row in class_rows
    ]


def _teacher_can_access_class(user, class_id):
    class_ids = {int(value) for value in _teacher_assigned_class_ids(user)}
    if not class_ids or int(class_id) not in class_ids:
        raise PermissionDenied("Teachers can only access assigned classes.")


def _teacher_subject_rows(user, class_id):
    subject_map = {}
    for assignment in _teacher_assignment_queryset(user).filter(class_section_id=class_id):
        if assignment.subject_id not in subject_map:
            subject_map[assignment.subject_id] = {
                "id": assignment.subject_id,
                "name": assignment.subject.name,
                "code": assignment.subject.code,
            }
    return list(subject_map.values())


def _teacher_rosters(class_ids):
    if not class_ids:
        return {}

    roster_map = defaultdict(list)
    seen = defaultdict(set)
    rows = (
        Enrollment.objects.filter(
            school_class_id__in=class_ids,
            is_active=True,
            status="Active",
            student__is_active=True,
        )
        .select_related("student", "school_class")
        .order_by("school_class_id", "student__first_name", "student__last_name", "student_id", "-id")
    )
    for row in rows:
        if row.student_id in seen[row.school_class_id]:
            continue
        seen[row.school_class_id].add(row.student_id)
        roster_map[str(row.school_class_id)].append({
            "id": row.student_id,
            "full_name": f"{row.student.first_name} {row.student.last_name}".strip(),
            "admission_number": row.student.admission_number,
        })
    return dict(roster_map)


def _selected_class_or_default(user, requested_class_id):
    classes = list(_teacher_classes(user))
    if not classes:
        return classes, None
    if requested_class_id:
        _teacher_can_access_class(user, requested_class_id)
        selected = next((row for row in classes if row.id == int(requested_class_id)), None)
        if selected:
            return classes, selected
    return classes, classes[0]


def _active_roster_for_class(class_id):
    seen = set()
    students = []
    rows = (
        Enrollment.objects.filter(
            school_class_id=class_id,
            is_active=True,
            status="Active",
            student__is_active=True,
        )
        .select_related("student")
        .order_by("student__first_name", "student__last_name", "student_id", "-id")
    )
    for row in rows:
        if row.student_id in seen:
            continue
        seen.add(row.student_id)
        students.append({
            "id": row.student_id,
            "full_name": f"{row.student.first_name} {row.student.last_name}".strip(),
            "admission_number": row.student.admission_number,
        })
    return students


def _assessment_can_be_accessed_by_teacher(user, assessment):
    return TeacherAssignment.objects.filter(
        teacher=user,
        class_section_id=assessment.class_section_id,
        subject_id=assessment.subject_id,
        is_active=True,
    ).exists()


def _grade_band_for_percentage(percentage):
    scheme = (
        GradingScheme.objects.filter(is_default=True, is_active=True).first()
        or GradingScheme.objects.filter(is_active=True).first()
    )
    if not scheme:
        return None
    return (
        GradeBand.objects.filter(
            scheme=scheme,
            is_active=True,
            min_score__lte=percentage,
            max_score__gte=percentage,
        )
        .order_by("-min_score", "-max_score", "id")
        .first()
    )


def _resource_type_to_frontend(material_type):
    mapping = {
        "PDF": "document",
        "Video": "video",
        "Link": "link",
        "Presentation": "slide",
        "Note": "document",
    }
    return mapping.get(material_type, "document")


def _resource_type_to_model(resource_type):
    mapping = {
        "document": "PDF",
        "video": "Video",
        "link": "Link",
        "slide": "Presentation",
    }
    return mapping.get(resource_type, "PDF")


def _serialize_material(row):
    return {
        "id": row.id,
        "title": row.title,
        "type": _resource_type_to_frontend(row.material_type),
        "subject": row.course.subject.name if row.course and row.course.subject_id else row.course.title,
        "url": row.link_url or row.file_url or "",
        "description": row.content,
        "created_at": row.created_at.date().isoformat() if row.created_at else "",
        "course_id": row.course_id,
        "course_title": row.course.title if row.course_id else "",
    }


class TeacherPortalDashboardView(TeacherPortalAccessMixin, APIView):
    def get(self, request):
        class_rows = list(_teacher_classes(request.user))
        classes = _serialize_classes(class_rows)
        announcements = Announcement.objects.filter(is_active=True).order_by("-publish_at", "-id")[:4]

        today = timezone.now().date()
        rosters = _teacher_rosters([row.id for row in class_rows])
        all_student_ids = {
            student["id"]
            for students in rosters.values()
            for student in students
        }
        present_today = set(
            AttendanceRecord.objects.filter(
                student_id__in=all_student_ids,
                date=today,
            ).values_list("student_id", flat=True)
        )
        attendance_pending = sum(
            1 for students in rosters.values()
            if students and not any(student["id"] in present_today for student in students)
        )

        timetable_today = TimetableSlot.objects.filter(
            teacher=request.user,
            is_active=True,
            day_of_week=today.isoweekday(),
        ).count()

        return Response({
            "summary": {
                "classes_count": len(classes),
                "attendance_pending": attendance_pending,
                "unread_messages": Notification.objects.filter(
                    recipient=request.user,
                    is_active=True,
                    is_read=False,
                ).count(),
                "announcements_count": announcements.count(),
                "today_timetable_count": timetable_today,
            },
            "classes": classes[:6],
            "announcements": [
                {
                    "id": row.id,
                    "title": row.title,
                    "created_at": row.publish_at,
                    "content": row.body,
                }
                for row in announcements
            ],
        })


class TeacherPortalClassesView(TeacherPortalAccessMixin, APIView):
    def get(self, request):
        class_rows = list(_teacher_classes(request.user))
        class_ids = [row.id for row in class_rows]
        return Response({
            "classes": _serialize_classes(class_rows),
            "rosters": _teacher_rosters(class_ids),
        })


class TeacherPortalAttendanceView(TeacherPortalAccessMixin, APIView):
    def get(self, request):
        requested_class_id = request.query_params.get("class_id")
        date_value = request.query_params.get("date") or str(timezone.now().date())
        class_rows, selected_class = _selected_class_or_default(request.user, requested_class_id)
        classes = _serialize_classes(class_rows)

        if not selected_class:
            return Response({
                "classes": classes,
                "selected_class_id": None,
                "date": date_value,
                "students": [],
            })

        students = _active_roster_for_class(selected_class.id)
        attendance_map = {}
        for row in (
            AttendanceRecord.objects.filter(
                student_id__in=[student["id"] for student in students],
                date=date_value,
            )
            .order_by("-id")
        ):
            attendance_map.setdefault(row.student_id, row)

        return Response({
            "classes": classes,
            "selected_class_id": selected_class.id,
            "date": date_value,
            "students": [
                {
                    **student,
                    "status": getattr(attendance_map.get(student["id"]), "status", "Present"),
                    "notes": getattr(attendance_map.get(student["id"]), "notes", ""),
                }
                for student in students
            ],
        })

    def post(self, request):
        class_id = request.data.get("class_id")
        date_value = request.data.get("date")
        records = request.data.get("records", [])

        if not class_id or not date_value or not isinstance(records, list):
            return Response(
                {"error": "class_id, date, and records[] are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        _teacher_can_access_class(request.user, class_id)
        allowed_students = {
            student["id"] for student in _active_roster_for_class(int(class_id))
        }
        valid_statuses = {"Present", "Absent", "Late", "Excused"}

        saved = 0
        for row in records:
            student_id = row.get("student_id")
            status_value = row.get("status")
            if student_id not in allowed_students or status_value not in valid_statuses:
                continue

            existing = (
                AttendanceRecord.objects.filter(student_id=student_id, date=date_value)
                .order_by("-id")
                .first()
            )
            if existing:
                existing.status = status_value
                existing.notes = row.get("notes", "")
                existing.recorded_by = request.user
                existing.save(update_fields=["status", "notes", "recorded_by"])
            else:
                AttendanceRecord.objects.create(
                    student_id=student_id,
                    date=date_value,
                    status=status_value,
                    notes=row.get("notes", ""),
                    recorded_by=request.user,
                )
            saved += 1

        return Response(
            {"message": "Attendance saved.", "count": saved},
            status=status.HTTP_200_OK,
        )


class TeacherPortalGradebookView(TeacherPortalAccessMixin, APIView):
    def get(self, request):
        requested_class_id = request.query_params.get("class_id")
        requested_subject_id = request.query_params.get("subject_id")
        requested_assessment_id = request.query_params.get("assessment_id")

        class_rows, selected_class = _selected_class_or_default(request.user, requested_class_id)
        classes = _serialize_classes(class_rows)

        if not selected_class:
            return Response({
                "classes": classes,
                "subjects": [],
                "assessments": [],
                "selected_class_id": None,
                "selected_subject_id": None,
                "selected_assessment_id": None,
                "assessment": None,
                "students": [],
            })

        subjects = _teacher_subject_rows(request.user, selected_class.id)
        if not subjects:
            return Response({
                "classes": classes,
                "subjects": [],
                "assessments": [],
                "selected_class_id": selected_class.id,
                "selected_subject_id": None,
                "selected_assessment_id": None,
                "assessment": None,
                "students": [],
            })

        subject_ids = {int(row["id"]) for row in subjects}
        selected_subject_id = int(requested_subject_id) if requested_subject_id and int(requested_subject_id) in subject_ids else subjects[0]["id"]

        assessments = list(
            Assessment.objects.filter(
                class_section_id=selected_class.id,
                subject_id=selected_subject_id,
                is_active=True,
            )
            .order_by("-date", "-id")
        )
        assessment_payload = [
            {
                "id": row.id,
                "name": row.name,
                "category": row.category,
                "date": row.date,
                "max_score": row.max_score,
            }
            for row in assessments
        ]

        assessment_ids = {row.id for row in assessments}
        selected_assessment = None
        if requested_assessment_id and int(requested_assessment_id) in assessment_ids:
            selected_assessment = next(
                row for row in assessments if row.id == int(requested_assessment_id)
            )
        elif assessments:
            selected_assessment = assessments[0]

        students = _active_roster_for_class(selected_class.id)
        grade_map = {}
        if selected_assessment:
            for row in (
                AssessmentGrade.objects.filter(
                    assessment=selected_assessment,
                    student_id__in=[student["id"] for student in students],
                    is_active=True,
                )
                .select_related("grade_band")
                .order_by("-id")
            ):
                grade_map.setdefault(row.student_id, row)

        return Response({
            "classes": classes,
            "subjects": subjects,
            "assessments": assessment_payload,
            "selected_class_id": selected_class.id,
            "selected_subject_id": selected_subject_id,
            "selected_assessment_id": selected_assessment.id if selected_assessment else None,
            "assessment": {
                "id": selected_assessment.id,
                "name": selected_assessment.name,
                "category": selected_assessment.category,
                "max_score": selected_assessment.max_score,
            } if selected_assessment else None,
            "students": [
                {
                    **student,
                    "raw_score": getattr(grade_map.get(student["id"]), "raw_score", None),
                    "remarks": getattr(grade_map.get(student["id"]), "remarks", ""),
                    "grade_band_label": getattr(getattr(grade_map.get(student["id"]), "grade_band", None), "label", ""),
                }
                for student in students
            ],
        })

    def post(self, request):
        assessment_id = request.data.get("assessment")
        rows = request.data.get("grades", [])
        if not assessment_id or not isinstance(rows, list):
            return Response(
                {"error": "assessment and grades[] are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assessment = Assessment.objects.filter(id=assessment_id, is_active=True).first()
        if not assessment or not _assessment_can_be_accessed_by_teacher(request.user, assessment):
            raise PermissionDenied("Teachers can only access assessments for assigned classes.")

        allowed_students = {
            student["id"] for student in _active_roster_for_class(assessment.class_section_id)
        }
        created = 0
        updated = 0

        for row in rows:
            student_id = row.get("student")
            raw_score_value = row.get("raw_score")
            if student_id not in allowed_students or raw_score_value in [None, ""]:
                continue

            try:
                raw_score = Decimal(str(raw_score_value))
            except (InvalidOperation, TypeError, ValueError):
                return Response(
                    {"error": "raw_score must be numeric."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if raw_score < 0 or raw_score > Decimal(assessment.max_score):
                return Response(
                    {"error": f"raw_score must be between 0 and {assessment.max_score}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            percentage = (
                raw_score / Decimal(assessment.max_score) * Decimal("100.00")
                if Decimal(assessment.max_score) > 0
                else Decimal("0.00")
            )
            band = _grade_band_for_percentage(percentage)
            _, was_created = AssessmentGrade.objects.update_or_create(
                assessment=assessment,
                student_id=student_id,
                defaults={
                    "raw_score": raw_score,
                    "percentage": round(percentage, 2),
                    "grade_band": band,
                    "entered_by": request.user,
                    "remarks": row.get("remarks", ""),
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        return Response(
            {"message": "Grades saved.", "created": created, "updated": updated},
            status=status.HTTP_200_OK,
        )


class TeacherPortalResourcesView(TeacherPortalAccessMixin, APIView):
    def get(self, request):
        courses = list(
            Course.objects.filter(teacher=request.user)
            .select_related("subject", "school_class")
            .order_by("title", "id")
        )
        materials = (
            CourseMaterial.objects.filter(course__teacher=request.user, is_active=True)
            .select_related("course", "course__subject", "course__school_class")
            .order_by("-created_at", "sequence", "id")
        )
        return Response({
            "courses": [
                {
                    "id": row.id,
                    "title": row.title,
                    "subject": row.subject.name if row.subject_id else "",
                    "class_name": row.school_class.display_name if row.school_class_id else "",
                }
                for row in courses
            ],
            "materials": [_serialize_material(row) for row in materials],
        })

    def post(self, request):
        course_id = request.data.get("course")
        title = (request.data.get("title") or "").strip()
        resource_type = request.data.get("type")
        url = (request.data.get("url") or "").strip()
        description = request.data.get("description") or ""

        if not course_id or not title:
            return Response(
                {"error": "course and title are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        course = Course.objects.filter(id=course_id, teacher=request.user).first()
        if not course:
            raise PermissionDenied("Teachers can only add materials to their own courses.")

        material_type = _resource_type_to_model(resource_type)
        material = CourseMaterial.objects.create(
            course=course,
            title=title,
            material_type=material_type,
            file_url=url if material_type in {"PDF", "Presentation"} else "",
            link_url=url if material_type in {"Video", "Link"} else "",
            content=description,
            sequence=(course.materials.count() + 1),
            is_active=True,
        )
        material = (
            CourseMaterial.objects.filter(id=material.id)
            .select_related("course", "course__subject", "course__school_class")
            .first()
        )
        return Response(_serialize_material(material), status=status.HTTP_201_CREATED)


class TeacherPortalResourceDetailView(TeacherPortalAccessMixin, APIView):
    def delete(self, request, material_id):
        material = CourseMaterial.objects.filter(
            id=material_id,
            course__teacher=request.user,
            is_active=True,
        ).first()
        if not material:
            return Response({"error": "Resource not found."}, status=status.HTTP_404_NOT_FOUND)
        material.is_active = False
        material.save(update_fields=["is_active"])
        return Response({"message": "Resource deleted."}, status=status.HTTP_200_OK)


class TeacherPortalTimetableView(TeacherPortalAccessMixin, APIView):
    def get(self, request):
        rows = (
            TimetableSlot.objects.filter(teacher=request.user, is_active=True)
            .select_related("subject", "school_class")
            .order_by("day_of_week", "period_number", "start_time", "id")
        )
        return Response([
            {
                "id": row.id,
                "day": row.get_day_of_week_display(),
                "start_time": row.start_time,
                "end_time": row.end_time,
                "subject_name": row.subject.name if row.subject_id else "",
                "class_name": row.school_class.display_name if row.school_class_id else "",
                "room": row.room or None,
                "period_number": row.period_number,
            }
            for row in rows
        ])


class TeacherPortalProfileView(TeacherPortalAccessMixin, APIView):
    """
    GET  /api/teacher-portal/profile/  — Teacher profile + assigned subjects/classes
    PATCH /api/teacher-portal/profile/ — Update first/last name, email, phone, bio, photo, password
    """
    def get(self, request):
        user = request.user
        profile = getattr(user, "userprofile", None)

        photo_url = None
        if profile and profile.photo:
            try:
                photo_url = request.build_absolute_uri(profile.photo.url)
            except Exception:
                pass

        # HR employee record (provides employee_id + department)
        employee = Employee.objects.filter(user=user).select_related("department").first()
        employee_id = ""
        department_name = ""
        if employee:
            employee_id = employee.employee_id or employee.staff_id or ""
            department_name = employee.department.name if employee.department_id else ""

        assignments = (
            TeacherAssignment.objects.filter(teacher=user, is_active=True)
            .select_related("subject", "class_section", "class_section__grade_level")
            .order_by("class_section__grade_level__order", "subject__name")
        )

        subjects_seen = set()
        classes_seen = set()
        subject_list = []
        class_list = []
        for a in assignments:
            if a.subject_id and a.subject_id not in subjects_seen:
                subjects_seen.add(a.subject_id)
                subject_list.append({
                    "id": a.subject_id,
                    "name": a.subject.name,
                    "code": a.subject.code,
                })
            if a.class_section_id and a.class_section_id not in classes_seen:
                classes_seen.add(a.class_section_id)
                class_list.append({
                    "id": a.class_section_id,
                    "name": getattr(a.class_section, "display_name", a.class_section.name),
                })

        return Response({
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "phone": profile.phone if profile else "",
            "bio": profile.bio if profile else "",
            "photo_url": photo_url,
            "role": getattr(getattr(profile, "role", None), "name", "TEACHER"),
            "employee_id": employee_id,
            "department": department_name,
            "subjects": subject_list,
            "classes": class_list,
            "force_password_change": bool(getattr(profile, "force_password_change", False)),
        })

    def patch(self, request):
        user = request.user
        profile = getattr(user, "userprofile", None)

        user_fields_changed = []
        for field in ("first_name", "last_name", "email"):
            if field in request.data:
                setattr(user, field, (request.data[field] or "").strip())
                user_fields_changed.append(field)
        if user_fields_changed:
            user.save(update_fields=user_fields_changed)

        if profile:
            profile_fields_changed = []
            for field in ("phone", "bio"):
                if field in request.data:
                    setattr(profile, field, (request.data[field] or "").strip())
                    profile_fields_changed.append(field)
            if "photo" in request.FILES:
                profile.photo = request.FILES["photo"]
                profile_fields_changed.append("photo")
            if profile_fields_changed:
                profile.save(update_fields=profile_fields_changed)

        if "current_password" in request.data and "new_password" in request.data:
            current = request.data.get("current_password", "")
            new_pw = request.data.get("new_password", "")
            if not user.check_password(current):
                return Response(
                    {"error": "Current password is incorrect."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if len(new_pw) < 8:
                return Response(
                    {"error": "New password must be at least 8 characters."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.set_password(new_pw)
            user.save(update_fields=["password"])
            if profile and profile.force_password_change:
                profile.force_password_change = False
                profile.save(update_fields=["force_password_change"])
            update_session_auth_hash(request, user)

        return self.get(request)
