from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from school.permissions import HasModuleAccess
from .models import SchemeOfWork, SchemeTopic, LessonPlan, LearningResource
from .serializers import SchemeOfWorkSerializer, SchemeTopicSerializer, LessonPlanSerializer, LearningResourceSerializer


class SchemeOfWorkViewSet(viewsets.ModelViewSet):
    queryset = SchemeOfWork.objects.all().order_by('-created_at')
    serializer_class = SchemeOfWorkSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "CURRICULUM"
    filterset_fields = ['subject', 'school_class', 'term', 'is_template']

    @action(detail=False, methods=['get'], url_path='templates')
    def list_templates(self, request):
        """Return all schemes marked as templates, optionally filtered by subject."""
        qs = SchemeOfWork.objects.filter(is_template=True).order_by('template_name', 'title')
        subject_id = request.query_params.get('subject')
        if subject_id:
            qs = qs.filter(subject_id=subject_id)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='use-template')
    def use_template(self, request, pk=None):
        """
        Clone a template SchemeOfWork (and all its SchemeTopic rows) into a new
        working copy bound to the class and term provided in the request body.

        Required body fields:
          - school_class  (int, SchoolClass pk)
          - term          (int, Term pk)

        Optional:
          - title         (str, defaults to the template title)
        """
        template = self.get_object()
        if not template.is_template:
            return Response(
                {"detail": "This scheme is not a template."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        school_class_id = request.data.get('school_class')
        term_id = request.data.get('term')
        if not school_class_id or not term_id:
            return Response(
                {"detail": "Both 'school_class' and 'term' are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check for duplicate (same subject/class/term non-template)
        if SchemeOfWork.objects.filter(
            subject=template.subject,
            school_class_id=school_class_id,
            term_id=term_id,
            is_template=False,
        ).exists():
            return Response(
                {"detail": "A scheme of work already exists for this subject, class, and term."},
                status=status.HTTP_409_CONFLICT,
            )

        # Clone the scheme
        new_scheme = SchemeOfWork.objects.create(
            subject=template.subject,
            school_class_id=school_class_id,
            term_id=term_id,
            title=request.data.get('title') or template.title,
            objectives=template.objectives,
            created_by=request.user,
            is_template=False,
        )

        # Clone every topic row
        topic_rows = list(template.topics.order_by('week_number'))
        SchemeTopic.objects.bulk_create([
            SchemeTopic(
                scheme=new_scheme,
                week_number=t.week_number,
                topic=t.topic,
                sub_topics=t.sub_topics,
                learning_outcomes=t.learning_outcomes,
                teaching_methods=t.teaching_methods,
                resources=t.resources,
                assessment_type=t.assessment_type,
                is_covered=False,
            )
            for t in topic_rows
        ])

        serializer = self.get_serializer(new_scheme)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class SchemeTopicViewSet(viewsets.ModelViewSet):
    queryset = SchemeTopic.objects.all().order_by('week_number')
    serializer_class = SchemeTopicSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "CURRICULUM"
    filterset_fields = ['scheme', 'is_covered']

class LessonPlanViewSet(viewsets.ModelViewSet):
    queryset = LessonPlan.objects.all().order_by('-date')
    serializer_class = LessonPlanSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "CURRICULUM"
    filterset_fields = ['topic', 'is_approved']

class LearningResourceViewSet(viewsets.ModelViewSet):
    queryset = LearningResource.objects.all().order_by('-created_at')
    serializer_class = LearningResourceSerializer
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "CURRICULUM"
    filterset_fields = ['subject', 'grade_level', 'resource_type']

class CurriculumDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasModuleAccess]
    module_key = "CURRICULUM"

    def get(self, request):
        total_schemes = SchemeOfWork.objects.count()
        total_topics = SchemeTopic.objects.count()
        covered_topics = SchemeTopic.objects.filter(is_covered=True).count()
        pending_lessons = LessonPlan.objects.filter(is_approved=False).count()
        total_resources = LearningResource.objects.count()
        
        return Response({
            "total_schemes": total_schemes,
            "total_topics": total_topics,
            "covered_topics": covered_topics,
            "coverage_percentage": (covered_topics / total_topics * 100) if total_topics > 0 else 0,
            "pending_lessons": pending_lessons,
            "total_resources": total_resources
        })
